import argparse
import logging
import sys
import warnings
import yaml
import os
from dotenv import load_dotenv
from os.path import join, dirname

from pathlib import Path, PureWindowsPath


dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

from src.OCRProcessor import OCRProcessor
from src.ScanDirectoryMonitor import ScanDirectoryMonitor
from src.eMailMonitor import eMailMonitor


def load_config(filepath):
    with open(filepath, 'r') as configfile:
        return yaml.load(configfile)


cfg = load_config(join(dirname(__file__), 'config.yml'))

processor = OCRProcessor(cfg, dev=True)

test_file_name = "7f90a25cbd0c11e9b7a2ebe4c4297576"

test_file = test_file_name + ".pdf"

# test_path = os.path.join(os.environ.get("IN_PATH"), test_file + ".pdf")

data_folder = Path("/media/datadrive/scans")

test_path = data_folder / test_file

fp = open(test_path, 'r')

processor.exec_file(test_path, test_file_name)