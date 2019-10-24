
# coding: utf-8
import glob, os, time
from PIL import Image
import pytesseract
import argparse
import cv2
import os
import urllib 
import pandas as pd
import pika
import json
import os
import smtplib
import logging
import uuid
import subprocess 

from email.headerregistry import Address
from email.message import EmailMessage
from PyPDF2 import PdfFileWriter, PdfFileReader
from mailer import Mailer
from mailer import Message
from logging.handlers import RotatingFileHandler

LOG_FILE_NAME = "scanning_ocr.log" 

logger = logging.getLogger()
handler = logging.StreamHandler()

formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)

rotate = RotatingFileHandler(LOG_FILE_NAME, maxBytes=25000,backupCount=5)
rotate.setFormatter(formatter)
rotate.setLevel(logging.INFO)

logger.addHandler(rotate)
logger.addHandler(handler)

logger.setLevel(logging.INFO)

class OCRProcessor:

    def __init__(self, cfg, **kwargs):

        self.IN_PATH = os.environ.get("IN_PATH")
        self.TIFF_PATH = os.environ.get("TIFF_PATH")
        self.OUT_PATH = os.environ.get("OUT_PATH")
        self.OUT_PATH_TXT = os.environ.get("OUT_PATH_TXT")
        
        # catch all user if no recipient can be detected from the OCR
        self.catch_all_user = cfg["catch_all_user"]

        # TODO: let config withdraw from DB
        self.config = cfg["users"]

        if 'dev' in kwargs:
            print("Run in development mode...")
        else:
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(os.environ.get("MQ_HOST"),heartbeat=0,blocked_connection_timeout=300))
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=os.environ.get("MQ_QUEUE_INBOUND"))
            self.channel.basic_qos(prefetch_count=1)

    # # Pre-Processing

    # clean working directory of intermetiate results from previous runs on same document
    def clean_intermediate_files(self, filename):
        
        tiffPath = os.path.join(self.TIFF_PATH, filename + "*.*")
        outPath = os.path.join(self.OUT_PATH, filename + "*.*")
        outTxtPath = os.path.join(self.OUT_PATH_TXT, filename + "*.*")
        
        [os.remove(x) for x in glob.glob(tiffPath)]
        [os.remove(x) for x in glob.glob(outPath)]
        [os.remove(x) for x in glob.glob(outTxtPath)]
    
    # basic detection of devider page (i.e. TRENNBLATT)
    @staticmethod
    def check_for_devider(inputStr):
        if os.environ.get("DEVIDER_TEXT_IDENTIFICATOR").lower() in inputStr.replace(" ", "").lower(): 
            return True

    # split the list of pages based on the devider pages detected
    # this serves as the basis for creating the subdocuments for later processing
    @staticmethod
    def get_split_lists(pages, deviders): 
        tuples = []
        
        my_page = None
        
        for i in pages:
            if i in deviders: 
                if my_page is not None: 
                    tuples.append(my_page)
                    my_page = None  
            else: 
                if my_page is None: 
                    my_page = []
                my_page.append(i)
            if i+1 == len(pages):
                tuples.append(my_page)
        return tuples

    # pre-process input file, search for devider pages 
    # create sub-documents based on devider pages and return array of resulting
    # documents
    def pre_process_file(self, file_path, file_name): 
        tiff_path = os.path.join(self.TIFF_PATH, file_name + ".tiff")
        
        logging.info("Conversion preprocessing into TIFF for file {}".format(tiff_path))
        
        convert_cmd = 'convert -density 300 "%s" -quality 7 -depth 8 -normalize "%s"' % (file_path, tiff_path)
        conversion = os.system(convert_cmd)

        img = Image.open(tiff_path)
        raw = ''
        raws = []
        devider_pages = []
        
        for i in range(img.n_frames):
            img.seek(i)
            txt = pytesseract.image_to_string(img)
            raws.append(txt)

            if self.check_for_devider(txt): 
                devider_pages.append(i)
        
        if len(devider_pages) > 0:
            logging.info("Devider pages detection complete, {} deviders were found".format(len(devider_pages)))
        else:
            logging.info("Devider pages detection complete, no deviders found")
        
        inputpdf = PdfFileReader(open(file_path, "rb"))

        result_docs = []

        page_splits = self.get_split_lists(range(inputpdf.numPages), devider_pages)
        
        logging.info("Write sub-pages in case deviders have been detected")
        
        for idx, page_set in enumerate(page_splits):
            
            new_file_name = file_name + "_" + str(idx)
            new_file_path = os.path.join(self.IN_PATH, new_file_name + ".pdf")
            
            output = PdfFileWriter()

            for p in page_set:
                output.addPage(inputpdf.getPage(p))

            with open(new_file_path, "wb") as outputStream:
                output.write(outputStream)
                
            result_docs.append({
                "file_name": new_file_name, 
                "file_path" : new_file_path
            })
        
        
        # clean up temporary TIFF file 
        os.remove(tiff_path)
        
        return result_docs

    # # Primary functions processing
    # Move a file as subprocess within FS
    @staticmethod
    def move_file(file, target_path): 
        try:
            process = subprocess.Popen(
                ['mv', file,  target_path],
                stdout=subprocess.PIPE
            )
            process.wait()
        
            return 0
        except: 
            return 2
    
    # Send an email update with the resulting path to users' inbox
    @staticmethod
    def send_email_update(result): 
        
        try:
            user = result["user_obj"]
            rel_paths = result["rel_paths"]
            
            path_str = ""
            for p in rel_paths: 
                path_str = path_str +  "<a href='file:///\\Y:\{}'>Mail</a><br>".format(p)
            
            message = Message(From=os.environ.get("SMTP_ADDRESS"),
                            To=str(user["email"]))
            message.Subject = "Scanning process"
            message.Html = """<p>Hi """ + user["user"] + """ <br>
            You have received mail, it has been saved in your _mailbox at:<br>
                """ + path_str + """</p>"""

            sender = Mailer(os.environ.get("SMTP_MAIL_SERVER"))
            sender.send(message)

            logging.info("Successfully sent email to {}".format(user["user"]))
            
        except smtplib.SMTPException as e:
            logging.error(e)
            logging.error("Error: unable to send email for {}".format(user["user"]))

    # identify user based on tagging from config object extracting from the OCR text string
    def identify_user(self, string):
        
        res = []
        for u in self.config: 
            for t in u["tags"]:
                if string.lower().find(t) > 0: 
                    res.append({"user" : u["user"], "cnt" : 1})

        total = len(res)

        df_res = pd.DataFrame(res)
        
        if len(res) > 0:
            d = df_res["user"].value_counts()
            df_freq = pd.DataFrame(d).reset_index()
            df_freq.sort_values("user", ascending=False, inplace=True)
            df_freq["freq"] = df_freq["user"]/total

            if df_freq.shape[0] > 0:
                logging.info("User(s) found")
                if df_freq.shape[0] > 1:
                    if df_freq.iloc[0]["freq"] > df_freq.iloc[1]["freq"]:
                        user = df_freq.iloc[0]["index"]
                        return self.get_user_obj(user)
                    else: 
                        logging.warning("Warning: Not one single user could be identified, but multiple equally")
                else:
                    user = df_freq.iloc[0]["index"]
                    logging.info("User was identified:{}".format(str(user)))
                    return self.get_user_obj(user)
        else: 
            return None

    # return user object based on the detected user from OCR string
    def get_user_obj(self, userstring): 
        return_user = None

        for u in self.config: 
            if userstring == u["user"]:
                return_user = u
                
        return return_user


    # # Processing pre-processed file

    # process a pdf file / letter potentially with muliple pages and 
    # convert to sandwich PDF
    # also basic detection of target recipient
    # move processed file into recipient mailbox
    # Add file to fulltext index (SOLR) 
    def process_file(self, file_path, file_name): 
        
        tiff_path = os.path.join(self.TIFF_PATH, file_name + ".tiff")
        
        convert_cmd = 'convert -density 300 "{}" -quality 7 -depth 8 -normalize "{}"'.format(file_path, tiff_path)
        os.system(convert_cmd)
        
        file_path_out = os.path.join(self.OUT_PATH,file_name)
        file_path_txt = os.path.join(self.OUT_PATH_TXT,file_name)
        
        pdf_cmd = 'tesseract -l deu "{}" "{}" pdf'.format(tiff_path, file_path_out)
        os.system(pdf_cmd)

        img = Image.open(tiff_path)
        txt = ''

        for i in range(img.n_frames):
            img.seek(i)
            txt += pytesseract.image_to_string(img)

        user = self.identify_user(txt)
        
        user_mailbox = ""
        
        if user:
            user_mailbox = os.path.join(os.environ.get("PATH_MAILBOX_BASE"), user["folder"], "_mailbox")

            if not os.path.exists(user_mailbox):
                os.makedirs(user_mailbox)
        else:
            user = self.catch_all_user
            user_mailbox = os.path.join(os.environ.get("PATH_MAILBOX_BASE"), "_mailbox")
            
            logging.warning("No unique user defined...moved into group box for KIR")
            
        out_file_path = file_path_out + ".pdf"
        final_path = os.path.join(user_mailbox, file_name + ".pdf")
        rel_letter_path = user["folder"] + '\_mailbox\{}'.format(file_name) + ".pdf"

        params = ""

        params = params + "literal.owner=" + urllib.parse.quote(user["user"])
        params = params + "&literal.rel_letter_path=" + urllib.parse.quote(rel_letter_path)

        # move item into user's mailbox
        logging.info("File should be moved {}".format(out_file_path))
        logging.info("Target mailbox {}".format(user_mailbox))
        
        self.move_file(out_file_path, user_mailbox)

        # index file to SOLR deactivated
        #if os.environ.get("FLAG_ADD_TO_SOLR_INDEX"):
        #    index_cmd = '/opt/solr-7.4.0/bin/post -c {} "{}" -params "{}" '.format(os.environ.get("SOLR_COLLECTION"), final_path,params)
        #    os.system(index_cmd)
        
        #clean tiff and inbound file
        os.remove(file_path)
        os.remove(tiff_path)

        # send update to user
        return user, rel_letter_path

    def exec_file(self, file_path, file_name):

        logging.info("Clean intermediate files {}".format(file_path))

        self.clean_intermediate_files(file_name)

        logging.info("Start processing file {}".format(file_path))

        sub_docs = self.pre_process_file(file_path, file_name)

        result_obj = {}

        for doc in sub_docs:
            f_p = doc["file_path"]
            f_n = doc["file_name"]

            user, rel_letter_path = self.process_file(f_p, f_n)

            if str(user["email"]) not in result_obj:
                result_obj[str(user["email"])] = {
                    "user_obj": user,
                    "rel_paths": []
                }

            result_obj[str(user["email"])]["rel_paths"].append(rel_letter_path)

        return result_obj

    def callback(self, ch, method, properties, body):

        requestParams = json.loads(body.decode('utf-8'))
        
        file_path = requestParams["filepath"] 
        file_name = requestParams["filename"]

        result_obj = self.exec_file(file_path, file_name)

        ch.basic_ack(delivery_tag=method.delivery_tag)
        
        for result in result_obj:
            self.send_email_update(result_obj[result])

    def init_consuming(self):

        logging.info("start consuming...")
        
        # receive message and complete simulation
        self.channel.basic_consume(self.callback, queue='inboundscans')
        self.channel.start_consuming()
