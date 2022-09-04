#!/bin/env python3

import random
import sys
import zipfile
import re
import logging
import enum
from pathlib import Path
from typing import Dict, List, Tuple

from PySide6.QtCore import Qt, Slot, Signal, QObject
from PySide6.QtWidgets import *

from platformio.run.cli import cli as pio_run

import requests


class MainWidget(QWidget):
    def __init__(self, log_object: QObject):
        QWidget.__init__(self)

        self.hello = [
            "Hallo Welt",
        ]

        # widgets
        self.button = QPushButton('Click me!')
        self.message = QLabel('Hello World')
        self.message.alignment = Qt.AlignCenter
        self.logText = QPlainTextEdit()
        self.logText.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.logText.setReadOnly(True)

        # layout
        self.layout = QGridLayout(self)
        self.layout.addWidget(self.logText, 0, 1)
        self.layout.addWidget(self.message, 0, 0)
        self.layout.addWidget(self.button, 1, 0)

        # signals
        self.button.clicked.connect(self.magic)
        log_object.log_signal.connect(self.logText.appendHtml)

    @Slot()
    def magic(self):
        self.message.setText(random.choice(self.hello))
        log.debug('Debug')
        log.info('Info')
        log.warning('Warning')
        log.critical('Critical')


def get_fw_versions() -> Dict[str, str]:
    fw_api_url = 'https://api.github.com/repos/OpenAstroTech/OpenAstroTracker-Firmware/releases'
    print(f'Grabbing available FW versions from {fw_api_url}')
    response = requests.get(fw_api_url)
    releases_dict = {
        'develop': 'https://github.com/OpenAstroTech/OpenAstroTracker-Firmware/archive/refs/heads/develop.zip',
    }
    for release_json in response.json():
        releases_dict[release_json['name']] = release_json['zipball_url']
    return releases_dict


def download_fw(zip_url: str) -> str:
    print(f'Downloading OAT FW from: {zip_url}')
    resp = requests.get(zip_url)
    zipfile_name = 'OATFW.zip'
    with open(zipfile_name, 'wb') as fd:
        fd.write(resp.content)
        fd.close()
    return zipfile_name


def extract_fw(zipfile_name: str) -> str:
    print('Extracting FW')
    with zipfile.ZipFile(zipfile_name, 'r') as zip_ref:
        zip_infolist = zip_ref.infolist()
        if len(zip_infolist) > 0 and zip_infolist[0].is_dir():
            fw_dir = zip_infolist[0].filename
        else:
            print(f'Could not find FW top level directory in {zip_infolist}!')
            exit(1)
        zip_ref.extractall()
    print(f'Extracted FW to {fw_dir}')
    return fw_dir


def get_pio_environments(fw_dir: str) -> List[str]:
    ini_path = Path(fw_dir, 'platformio.ini')
    with open(ini_path.resolve(), 'r') as fp:
        ini_lines = fp.readlines()
    environment_lines = [ini_line for ini_line in ini_lines if ini_line.startswith('[env:')]
    pio_environments = []
    for environment_line in environment_lines:
        match = re.search(r'\[env:(.+)\]', environment_line)
        if match:
            pio_environments.append(match.group(1))
    print(f'Found pio environments: {pio_environments}')
    return pio_environments


def build_fw(pio_environment: str, fw_dir: str):
    print(f'Building FW environment={pio_environment} dir={fw_dir}')
    pio_run(['--environment', pio_environment, '--project-dir', fw_dir])


class LogObject(QObject):
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()

    def write(self, s):
        # TODO: Could buffer if QMetaMethod.fromSignal worked?
        self.log_signal.emit(s)


class LogColourTypes(enum.Enum):
    no_colour = enum.auto()
    html = enum.auto()
    terminal = enum.auto()


class CustomFormatter(logging.Formatter):
    def __init__(self, colour_type:LogColourTypes=LogColourTypes.no_colour):
        super().__init__(fmt='%(asctime)s:%(levelname)s:%(message)s')
        self.colour_type = colour_type

    def _colour_terminal(self, levelno: int) -> Tuple[str, str]:
        grey = "\x1b[38;20m"
        yellow = "\x1b[33;20m"
        red = "\x1b[31;20m"
        bold_red = "\x1b[31;1m"
        reset = "\x1b[0m"

        pre, post = {
            logging.DEBUG: (grey, reset),
            logging.INFO: (grey, reset),
            logging.WARNING: (yellow, reset),
            logging.ERROR: (red, reset),
            logging.CRITICAL: (bold_red, reset),
        }.get(levelno, ('', ''))
        return pre, post

    def _colour_html(self, levelno: int) -> Tuple[str, str]:
        pre, post = {
            logging.DEBUG: ('<p style="color:grey">', '</p>'),
            logging.INFO: ('<p style="color:grey">', '</p>'),
            logging.WARNING: ('<p style="color:yellow">', '</p>'),
            logging.ERROR: ('<p style="color:red">', '</p>'),
            logging.CRITICAL: ('<p style="color:red">', '</p>'),
        }.get(levelno, ('', ''))
        return pre, post

    def format(self, record):
        if self.colour_type == LogColourTypes.terminal:
            pre, post = self._colour_terminal(record.levelno)
        elif self.colour_type == LogColourTypes.html:
            pre, post = self._colour_html(record.levelno)
        else:
            pre, post = '', ''
        return pre + super().format(record) + post


def main():
    if sys.base_prefix == sys.prefix:
        log.fatal('I should be running in a virtual environment! Something is wrong...')
        exit(1)

    # releases_dict = get_fw_versions()
    # zipfile_name = download_fw(releases_dict['Arduino V1.11.5'])
    # fw_dir = extract_fw(zipfile_name)
    # pio_environments = get_pio_environments(fw_dir)
    # build_fw(pio_environments[0], fw_dir)
    # exit(0)

    app = QApplication(sys.argv)

    widget = MainWidget(l_o)
    widget.show()

    exit(app.exec())


def setup_logging(logger):
    logger.setLevel(logging.DEBUG)
    # file handler
    fh = logging.FileHandler('spam.log')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(CustomFormatter(colour_type=LogColourTypes.no_colour))
    logger.addHandler(fh)
    # console handler
    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(CustomFormatter(colour_type=LogColourTypes.terminal))
    logger.addHandler(ch)
    # gui handler
    gh = logging.StreamHandler(stream=l_o)
    gh.setLevel(logging.DEBUG)
    gh.setFormatter(CustomFormatter(colour_type=LogColourTypes.html))
    logger.addHandler(gh)


if __name__ == '__main__':
    log = logging.getLogger('')
    l_o = LogObject()
    setup_logging(log)
    log.debug('Logging initialized')
    main()
