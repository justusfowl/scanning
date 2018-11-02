import sys
import argparse
import logging
import sys
import warnings
import yaml

from dotenv import load_dotenv
from os.path import join, dirname

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

from src.OCRProcessor import OCRProcessor
from src.ScanDirectoryMonitor import ScanDirectoryMonitor
from src.eMailMonitor import eMailMonitor

def load_config(filepath):
    with open(filepath, 'r') as configfile:
        return yaml.load(configfile)
        
cfg = load_config(join(dirname(__file__), 'config.yml'))


list_of_choices = [
    'ocrprocess',
    'mailbox',
    'monitor'
]

parser = argparse.ArgumentParser(description='kDatacenter Mail Processing')

parser.add_argument(
    '-r',
    '--routines',
    required=True,
    nargs='+',
    choices=list_of_choices,
    metavar='R',
    help='List of routines to run: {}'.format(', '.join(list_of_choices))
)

parser.add_argument("-d", "--directories", nargs='+',
                    help="directories to be monitored for inbound scans, works with --routines=monitor", metavar="STRINGS")

def main(args=sys.argv[1:]):

    args = parser.parse_args(args)

    if 'ocrprocess' in args.routines:
        processor = OCRProcessor(cfg)
        processor.init_consuming()

    if 'mailbox' in args.routines:
        monitor = eMailMonitor()
        monitor.init_monitoring()

    if 'monitor' in args.routines:

        ##["/mnt/EicScanRaw", "/mnt/KirScanRaw"]
        directories = args.directories

        if len(directories) > 0:
        
            for d in directories:
                logging.info("The following directory should be monitored {}".format(d))
                
            monitor = ScanDirectoryMonitor(directories)
            monitor.init_monitoring()
            
        else: 
            logging.error("Please provide at least one directory to be monitored (-d/--directories)")
            
main(sys.argv[1:])