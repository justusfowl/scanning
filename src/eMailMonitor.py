
# coding: utf-8

import os
import logging
import PIL
import time 
import uuid

from exchangelib import DELEGATE, Credentials, Account, Configuration, FileAttachment
from PIL import Image, ExifTags
from logging.handlers import RotatingFileHandler
from fpdf import FPDF

LOG_FILE_NAME = "scanning_email_monitor.log"

logger = logging.getLogger(LOG_FILE_NAME)
handler = logging.StreamHandler()

formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)

rotate = RotatingFileHandler(LOG_FILE_NAME, maxBytes=25000,backupCount=5)
rotate.setFormatter(formatter)

logger.addHandler(rotate)
logger.addHandler(handler)

logger.setLevel(logging.INFO)


# make sure the right certificate bundle is used as reference for trusted CAs
# this ensures no errors with regards to SSL requests through 'normal' request lib in python 
# necessary through private hosting of PKI
os.environ['REQUESTS_CA_BUNDLE'] = os.path.join('/etc/ssl/certs/','ca-certificates.crt')

class eMailMonitor:

    def __init__(self): 

        self.domain = os.environ.get("DOMAIN")
        self.mailuser = os.environ.get("MAILUSER") 
        self.pw = os.environ.get("PASSWORD")
        
        self.allowed_file_extensions = [".jpg", ".jpeg"]
        self.TARGET_PATH_RAW_SCANS = os.environ.get("TARGET_PATH_RAW_SCANS")

        self.credentials = Credentials(self.domain + '\\' + self.mailuser, self.pw)
        self.config = Configuration(server=os.environ.get("MAIL_SERVER"), credentials=self.credentials)
        self.account = Account(primary_smtp_address=os.environ.get("MAILBOX_ADDRESS"), config=self.config, autodiscover=False, access_type=DELEGATE)

    @staticmethod
    def rotate_image(filepath): 
        try:
            image=Image.open(filepath)

            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation]=='Orientation':
                    break
            exif=dict(image._getexif().items())

            if exif[orientation] == 3:
                image=image.rotate(180, expand=True)
            elif exif[orientation] == 6:
                image=image.rotate(270, expand=True)
            elif exif[orientation] == 8:
                image=image.rotate(90, expand=True)
            else:
                print("no info on or no rotation done")
            image.save(filepath)
            image.close()
        except: 
            logging.errort("Something went wrong rotating the image: {} ".format(filepath))

    def create_pdf(self, imagelist):
        try:
            pdf = FPDF('P', 'mm', 'A4')
        
            out_name = uuid.uuid1().hex + ".pdf"

            for image in imagelist:
                pdf.add_page()
                page_image = Image.open(image)
                w_orig, h_orig = page_image.size
                w, h = get_resized(w_orig, h_orig)
                pdf.image(image,0,0,w,h)
            pdf.output(os.path.join(self.TARGET_PATH_RAW_SCANS, out_name), "F")
        except: 
            logging.errort("Something went wrong creating the PDF from image_list: ", " ".join(map(str, imagelist)))
    
    @staticmethod
    def get_resized(w, h): 
        try:
            page_width = 210
            page_height = 297
            if w > h:
                zoom_ratio = page_width / w
                new_height = h*zoom_ratio
                return page_width, new_height
            else:
                zoom_ratio = page_height / h
                new_width = w*zoom_ratio
                return new_width, page_height
        except: 
            logging.error("Something went wrong resizing the image")

    def ensure_jpg(self, infile):
        try:
            f, e = os.path.splitext(infile)

            if e.lower() not in self.allowed_file_extensions:
                outfile = f + ".jpg"
                im = Image.open(infile)
                rgb_im = im.convert('RGB')
                rgb_im.save(outfile)
                os.remove(infile)
                return outfile
            else:
                return infile
        except: 
            logging.error("Something went wrong ensuring JPG for {}".format(infile))

    def check_messages(self):
        
        if len(self.account.inbox.all().order_by('-datetime_received')) == 0:
            logger.info("No messages were found")
        else: 
            logger.info("{} messages were found on the server".format(len(self.account.inbox.all().order_by('-datetime_received'))))

        for item in self.account.inbox.all().order_by('-datetime_received'):
            
            b = item.body

            image_list = []

            for attachment in item.attachments:
                if isinstance(attachment, FileAttachment):

                    tmp_item = os.path.join('/tmp', uuid.uuid1().hex + "_" + attachment.name)

                    with open(tmp_item, 'wb') as f:
                        f.write(attachment.content)

                    filename, file_extension = os.path.splitext(attachment.name)

                    if file_extension.lower() in [".pdf", "pdf"]:
                        local_path = os.path.join(self.TARGET_PATH_RAW_SCANS, uuid.uuid1().hex + "_" + attachment.name)

                        with open(local_path, 'wb') as f:
                            f.write(attachment.content)
                        os.remove(tmp_item)

                    elif file_extension.lower() in [".jpeg", ".jpg", ".png", ".tiff"]:
                        image_path = ensure_jpg(tmp_item)

                        rotate_image(image_path)

                        image_list.append(image_path)

                    logging.info('Saved attachment to {}'.format(tmp_item))
                elif isinstance(attachment, ItemAttachment):
                    if isinstance(attachment.item, Message):
                        logging.info(attachment.item.subject, attachment.item.body)

            # create PDF here from the images 
            self.create_pdf(image_list)

            #clean up tmp files

            for i in image_list:
                os.remove(i)

            item.move_to_trash()
    
    def init_monitoring(self):

        while 1:
            self.check_messages()
            time.sleep (60)