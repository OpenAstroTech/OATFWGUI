import logging
import sys
import os
import enum
import html
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Tuple, List, Optional

from PySide6.QtCore import Slot, Signal, QObject, QFileSystemWatcher, QFile, QMetaMethod

from external_processes import get_install_dir
from platform_check import get_platform, PlatformEnum
from qt_extensions import get_signal


class LogObject(QObject):
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.log_buf: List[str] = []
        # Just so we don't call this on every log message
        self.log_signal_meta: QMetaMethod = get_signal(self, 'log_signal')

    def write(self, s: str):
        if not self.isSignalConnected(self.log_signal_meta):
            # if we can't send a signal, just append to a local buffer
            self.log_buf.append(s)
        else:
            # Dump and clear our saved buffer
            for buffered_log in self.log_buf:
                self.log_signal.emit(buffered_log)
            self.log_buf.clear()
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
        # https://coolors.co/contrast-checker/c9cd02-ffffff
        # Light theme background: #FFFFFF
        # Dark theme background: #1B1E20
        pre, post = {
            logging.DEBUG: ('<p style="color:SlateGray">', '</p>'),
            logging.INFO: ('<p style="color:grey">', '</p>'),
            logging.WARNING: ('<p style="color:#C9CD02">', '</p>'),
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


class LoggedExternalFile:
    def __init__(self):
        # Don't want to global the `log` variable here (idk if things will break)
        self.log = logging.getLogger('')

        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.fileChanged.connect(self.file_changed)

        self.tempfile: Optional[tempfile.NamedTemporaryFile] = None

    def create_file(self, file_suffix: str = '') -> Optional[str]:
        self.tempfile = tempfile.NamedTemporaryFile(mode='r', suffix=f'{file_suffix}', delete=False)
        self.log.debug(f'Logging external file {self.tempfile.name}')

        watch_success = self.file_watcher.addPath(self.tempfile.name)
        if not watch_success:
            self.log.warning(f'Could not watch external file: {self.tempfile.name}')
            return None
        return self.tempfile.name

    @Slot()
    def file_changed(self, _path: str):
        lines = self.tempfile.readlines()
        for line in lines:
            if 'error' in line.lower():
                self.log.error(line)
            else:
                self.log.info(line)

    def stop(self):
        self.log.debug(f'Cleaning up logged external file {self.tempfile.name}')
        self.tempfile.close()
        self.file_watcher.removePath(self.tempfile.name)
        remove_ok = QFile.remove(self.tempfile.name)
        if not remove_ok:
            self.log.warning(f'Could not remove temp file {self.tempfile.name}')


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
