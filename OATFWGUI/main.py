#!/bin/env python3

import sys
import logging
import os
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication


from log_utils import LogObject, setup_logging
from gui_logic import MainWidget


def main():
    setup_environment()
    check_environment()
    app = QApplication(sys.argv)

    widget = MainWidget(l_o)
    widget.show()

    sys.exit(app.exec())


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


if __name__ == '__main__':
    log = logging.getLogger('')
    l_o = LogObject()
    setup_logging(log, l_o)
    log.debug('Logging initialized')
    main()
