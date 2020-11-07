
# coding: utf-8
import os, time
import shutil
import uuid
import notebook
import pika
import json
import datetime
import logging
import ssl
from pathlib import Path

from multiprocessing import Process
from logging.handlers import RotatingFileHandler

LOG_FILE_NAME = "scanning_directory_monitoring.log" 

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

class ScanDirectoryMonitor:

    def __init__(self, directories):

        self.paths_to_watch = directories 
        self.path_processing = os.environ.get("IN_PATH")
        self.allowed_file_extensions = [".pdf"]

        self.total_jobs = len(self.paths_to_watch)

    # After successfully moving file, publish file path as task into queue
    @staticmethod
    def publish_message(msg): 

        try: 
            logging.info('Publishing scan into queue')

            ca = Path(__file__).parent / "../certs/ca.crt"
            crt = Path(__file__).parent / "../certs/client-cert.pem"
            key = Path(__file__).parent / "../certs/client-key.pem"

            context = ssl.create_default_context(cafile=ca)
            context.load_cert_chain(crt, key)
            ssl_options = pika.SSLOptions(context, "kirapp2")

            credentials = pika.PlainCredentials(os.environ.get("MQ_USER"), os.environ.get("MQ_PASS"))
            parameters = pika.ConnectionParameters(os.environ.get("MQ_HOST"),
                                                   os.environ.get("MQ_PORT"),
                                                   os.environ.get("MQ_VIRTUAL_HOST"),
                                                   credentials, heartbeat=0, blocked_connection_timeout=300,
                                                   ssl_options=ssl_options)
            connection = pika.BlockingConnection(parameters)

            # connection = pika.BlockingConnection(pika.ConnectionParameters(os.environ.get("MQ_HOST")))
            channel = connection.channel()
            channel.queue_declare(queue=os.environ.get("MQ_QUEUE_INBOUND"))
            channel.basic_publish(exchange='', routing_key=os.environ.get("MQ_QUEUE_INBOUND"), body=json.dumps(msg, ensure_ascii=False))
        except: 
            logging.error('Something went wrong with publishing the message')


    # Monitoring a folder for changes, even from remote access (e.g. scanner beginning to write a file)
    # monitor file size as proxy before moving file into pipeline
    def watch_in_dir(self, path_to_watch):
        logging.info('Watching path...{}'.format(path_to_watch))
        files_arr = {}

        while 1:
            try:

                time.sleep (10)
                for f in os.listdir(path_to_watch):
                    filename, file_extension = os.path.splitext(f)
                    full_file_path = os.path.join(path_to_watch,f)
                    full_file_processing = os.path.join(self.path_processing, f)

                    if os.path.isfile(full_file_path) and file_extension in self.allowed_file_extensions:
                        filesize = os.path.getsize(full_file_path)

                        if filename not in files_arr:

                            files_arr[filename] = {
                                "size" : filesize
                            }

                            logging.info("new file {} recognized with size {}".format(f, filesize))
                        else:

                            logging.info("filesize: {}".format(filesize))
                            if filesize > files_arr[filename]["size"]:
                                files_arr[filename]["size"] = filesize

                                logging.info("file {} is growing to new size {} ".format(f, filesize))
                            else:
                                if files_arr[filename]["size"] > 0:

                                    logging.info("file is complete {} and moved ".format(f))

                                    file_name = uuid.uuid1().hex
                                    target_file_name = file_name + file_extension
                                    shutil.move(full_file_path, os.path.join(self.path_processing,target_file_name))
                                    files_arr.pop(filename, None)

                                    logging.info("{} complete".format(filename))

                                    message = {
                                        "filename" : file_name,
                                        "filepath" : os.path.join(self.path_processing,target_file_name),
                                        "date" : datetime.datetime.now().isoformat()
                                    }

                                    self.publish_message(message)
                                    logging.info("{} published to queue".format(filename))
            except Exception as e:
                logging.error("{} error monitoring the directory".format(e))

    def init_monitoring(self): 
        
        procs = []

        for path in self.paths_to_watch:
            proc = Process(target=self.watch_in_dir, args=(path,))
            procs.append(proc)
            proc.start()