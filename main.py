#!/bin/env python3

import random
import sys

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

import click
import requests
import zipfile
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

    print('Downloading OAT FW')
    resp = requests.get('https://github.com/OpenAstroTech/OpenAstroTracker-Firmware/archive/refs/tags/V1.11.5.zip')
    zipfile_name = 'OATFW.zip'
    with open(zipfile_name, 'wb') as fd:
        fd.write(resp.content)
        fd.close()
    print('Extracting FW')
    with zipfile.ZipFile(zipfile_name, 'r') as zip_ref:
        zip_ref.extractall()

    print('Building FW')
    pio_run(['--environment', 'mksgenlv21', '--project-dir', 'OpenAstroTracker-Firmware-1.11.5'])
    exit(0)

    app = QApplication(sys.argv)

    widget = MainWidget()
    widget.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
