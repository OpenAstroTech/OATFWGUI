#!/bin/env python3

import sys
import logging
import os
import argparse
import time
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Slot
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtGui import QAction, QActionGroup

from _version import __version__
from log_utils import LogObject, setup_logging
from gui_logic import MainWidget

parser = argparse.ArgumentParser(usage='Graphical way to build and load OAT Firmware')
parser.add_argument('--no-gui', action='store_true',
                    help='Do not start the graphics, exit just before then (used as a basic functionality test)')
parser.add_argument('-v', '--version', action='version',
                    version=__version__,
                    help='Print version string and exit')


def setup_environment():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        log.info('Running in pyinstaller bundle')
        mei_path = getattr(sys, '_MEIPASS')
        log.info(f'_MEIPASS is {mei_path}')
        bin_path = Path(mei_path, 'bin')
        log.info(f'Adding {bin_path} to system path')
        os.environ['PATH'] += os.pathsep + str(bin_path)
    else:
        log.info('Not running in pyinstaller bundle')


def check_environment():
    for exe_name in ['platformio']:
        log.debug(f'Checking path for {exe_name}')
        exe_path = QStandardPaths.findExecutable(exe_name)
        log.debug(f'Path is {exe_path}')
        if exe_path == '':
            log.fatal(f'Could not find {exe_name}! I need it!')
            sys.exit(1)


class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.setWindowTitle(f'OAT FirmWare GUI - {__version__}')

        self.menu_bar = self.menuBar()
        self.file_menu = self.menu_bar.addMenu('&File')

        self.log_level_submenu = self.file_menu.addMenu('Log level')
        self.log_action_group = QActionGroup(self)

        self.add_log_menu_helper('debug', self.log_debug)
        self.add_log_menu_helper('info', self.log_info, True)
        self.add_log_menu_helper('warning', self.log_warn)
        self.add_log_menu_helper('error', self.log_error)

        self.exit_action = QAction('Exit')
        self.exit_action.triggered.connect(self.exit)
        self.file_menu.addAction(self.exit_action)

        log.debug('Creating main widget')
        self.main_widget = MainWidget(l_o)
        self.setCentralWidget(self.main_widget)

    def add_log_menu_helper(self, name: str, cb_fn, is_checked=False):
        action = QAction(name)
        action.setCheckable(True)
        action.triggered.connect(cb_fn)
        if is_checked:
            action.setChecked(True)
        # set self so we don't delete the object when it goes out of scope
        setattr(self, f'_auto_log_action_{name}', action)
        self.log_action_group.addAction(action)
        self.log_level_submenu.addAction(action)

    @staticmethod
    def set_gui_log_level(log_level: int):
        log.debug(f'Setting GUI log level to {logging.getLevelName(log_level)}')
        for handler in log.handlers:
            if hasattr(handler, 'stream') and isinstance(handler.stream, LogObject):
                handler.setLevel(log_level)

    @Slot()
    def log_debug(self):
        self.set_gui_log_level(logging.DEBUG)

    @Slot()
    def log_info(self):
        self.set_gui_log_level(logging.INFO)

    @Slot()
    def log_warn(self):
        self.set_gui_log_level(logging.WARNING)

    @Slot()
    def log_error(self):
        self.set_gui_log_level(logging.ERROR)

    @Slot()
    def exit(self):
        sys.exit(0)


def main():
    setup_environment()
    check_environment()
    log.debug('Creating app')
    app = QApplication(sys.argv)

    log.debug('Creating main window')
    widget = MainWindow()
    widget.show()

    if not args.no_gui:
        log.debug('Executing app')
        retcode = app.exec()
    else:
        log.debug('NOT executing app')
        # Wait a bit before exiting, prevents Qt complaining about deleted objects
        time.sleep(1.0)
        retcode = 0
    sys.exit(retcode)


if __name__ == '__main__':
    args = parser.parse_args()
    log = logging.getLogger('')
    l_o = LogObject()
    setup_logging(log, l_o)
    log.debug('Logging initialized')
    main()
