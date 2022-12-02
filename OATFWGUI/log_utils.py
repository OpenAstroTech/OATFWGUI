import logging
import sys
import os
import enum
import html
from pathlib import Path
from datetime import datetime
from typing import Tuple

from PySide6.QtCore import Signal, QObject

from external_processes import get_install_dir
from platform_check import get_platform, PlatformEnum


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
    def __init__(self, colour_type: LogColourTypes = LogColourTypes.no_colour):
        super().__init__(fmt='%(asctime)s:%(levelname)s:%(message)s')
        self.colour_type = colour_type

    def _colour_terminal(self, levelno: int) -> Tuple[str, str]:
        magenta = "\x1b[35;20m"
        bright_grey = "\x1b[90;20m"
        yellow = "\x1b[33;20m"
        red = "\x1b[31;20m"
        bold_red = "\x1b[31;1m"
        reset = "\x1b[0m"

        pre, post = {
            logging.DEBUG: (magenta, reset),
            logging.INFO: (bright_grey, reset),
            logging.WARNING: (yellow, reset),
            logging.ERROR: (red, reset),
            logging.CRITICAL: (bold_red, reset),
        }.get(levelno, ('', ''))
        return pre, post

    def _colour_html(self, levelno: int) -> Tuple[str, str]:
        pre, post = {
            logging.DEBUG: ('<p style="color:SlateGray">', '</p>'),
            logging.INFO: ('<p style="color:grey">', '</p>'),
            logging.WARNING: ('<p style="color:yellow">', '</p>'),
            logging.ERROR: ('<p style="color:red">', '</p>'),
            logging.CRITICAL: ('<p style="color:red">', '</p>'),
        }.get(levelno, ('', ''))
        return pre, post

    def format(self, record):
        if self.colour_type == LogColourTypes.terminal and get_platform() != PlatformEnum.WINDOWS:
            # only use terminal colors when not in windows, they don't work by default
            pre, post = self._colour_terminal(record.levelno)
            log_str = pre + super().format(record) + post
        elif self.colour_type == LogColourTypes.html:
            pre, post = self._colour_html(record.levelno)
            log_str = pre + html.escape(super().format(record)) + post
        else:
            log_str = super().format(record)
        return log_str


def setup_logging(logger, qt_log_obj: LogObject):
    logger.setLevel(logging.DEBUG)
    # file handler
    log_dir = Path(get_install_dir(), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    date_str = datetime.today().strftime('%Y-%m-%d-%H-%M-%S')
    log_file = str(Path(log_dir, f'oat_fw_gui_{date_str}.log'))
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(CustomFormatter(colour_type=LogColourTypes.no_colour))
    logger.addHandler(fh)
    # console handler
    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(CustomFormatter(colour_type=LogColourTypes.terminal))
    logger.addHandler(ch)
    # gui handler
    gh = logging.StreamHandler(stream=qt_log_obj)
    gh.setLevel(logging.INFO)
    gh.setFormatter(CustomFormatter(colour_type=LogColourTypes.html))
    logger.addHandler(gh)

    logger.debug(f'Logging initialized (logfile={log_file})')
