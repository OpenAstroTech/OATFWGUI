#!/bin/env python3

import random
import sys
import zipfile
import re
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

import requests
from platformio.run.cli import cli as pio_run


class MainWidget(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self.hello = [
            "Hallo Welt",
        ]

        self.button = QPushButton('Click me!')
        self.message = QLabel('Hello World')
        self.message.alignment = Qt.AlignCenter

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.message)
        self.layout.addWidget(self.button)

        # Connecting the signal
        self.button.clicked.connect(self.magic)

    @Slot()
    def magic(self):
        self.message.setText(random.choice(self.hello))


def in_virtualenv():
    return sys.base_prefix != sys.prefix


def main():
    if not in_virtualenv():
        print('I should be running in a virtual environment! Something is wrong...')
        exit(1)

    response = requests.get('https://api.github.com/repos/OpenAstroTech/OpenAstroTracker-Firmware/releases')
    releases_dict = {
        'develop': 'https://github.com/OpenAstroTech/OpenAstroTracker-Firmware/archive/refs/heads/develop.zip',
    }
    for release_json in response.json():
        releases_dict[release_json['name']] = release_json['zipball_url']

    zip_url = releases_dict['Arduino V1.11.5']
    print(f'Downloading OAT FW from: {zip_url}')
    resp = requests.get(zip_url)
    zipfile_name = 'OATFW.zip'
    with open(zipfile_name, 'wb') as fd:
        fd.write(resp.content)
        fd.close()
    print('Extracting FW')
    with zipfile.ZipFile(zipfile_name, 'r') as zip_ref:
        zip_infolist = zip_ref.infolist()
        if len(zip_infolist) > 0 and zip_infolist[0].is_dir():
            fw_dir = zip_infolist[0].filename
        else:
            print(f'Could not find FW top level directory in {zip_infolist}!')
            exit(1)
        zip_ref.extractall()
    print(f'FW dir: {fw_dir}')

    with open(Path(fw_dir, 'platformio.ini').resolve(), 'r') as fp:
        ini_lines = fp.readlines()
    environment_lines = [l for l in ini_lines if l.startswith('[env:')]
    pio_environments = []
    for environment_line in environment_lines:
        match = re.search(r'\[env:(.+)\]', environment_line)
        if match:
            pio_environments.append(match.group(1))
    print(pio_environments)

    print('Building FW')
    pio_run(['--environment', 'mksgenlv21', '--project-dir', fw_dir])
    exit(0)

    app = QApplication(sys.argv)

    widget = MainWidget()
    widget.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
