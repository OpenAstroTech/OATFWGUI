#!/bin/env python3

import random
import sys
import zipfile
import re
from pathlib import Path
from typing import Dict, List

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import *

import requests
from platformio.run.cli import cli as pio_run


class MainWidget(QWidget):
    def __init__(self):
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

    @Slot()
    def magic(self):
        self.message.setText(random.choice(self.hello))
        self.logText.appendHtml('aaaaaaa' * 50)
        self.logText.appendHtml('<b>bbbb</b>' * 50)


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
    with open(Path(fw_dir, 'platformio.ini').resolve(), 'r') as fp:
        ini_lines = fp.readlines()
    environment_lines = [l for l in ini_lines if l.startswith('[env:')]
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


def main():
    if sys.base_prefix == sys.prefix:
        print('I should be running in a virtual environment! Something is wrong...')
        exit(1)

    releases_dict = get_fw_versions()
    zipfile_name = download_fw(releases_dict['Arduino V1.11.5'])
    fw_dir = extract_fw(zipfile_name)
    pio_environments = get_pio_environments(fw_dir)
    build_fw(pio_environments[0], fw_dir)
    exit(0)

    app = QApplication(sys.argv)

    widget = MainWidget()
    widget.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
