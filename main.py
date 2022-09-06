#!/bin/env python3

import sys
import zipfile
import re
import logging
import enum
import traceback
import html
from pathlib import Path
from typing import List, Tuple, Optional
from collections import namedtuple

from PySide6.QtCore import Slot, Signal, QObject, QRunnable, QThreadPool
from PySide6.QtWidgets import *

from platformio.run.cli import cli as pio_run

import requests


class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(int)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add the callback to our kwargs
        # self.kwargs['progress_callback'] = self.signals.progress

    @Slot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


StageAction = namedtuple('StageAction', ['fn_action', 'fn_result'])
FWVersion = namedtuple('FWVersion', ['nice_name', 'url'])


class LogicState:
    release_list: Optional[List[FWVersion]] = None
    release_idx: Optional[int] = None
    pio_envs: Optional[List[str]] = None
    pio_env: Optional[str] = None
    config_file_path: Optional[str] = None

    def __setattr__(self, key, val):
        log.debug(f'LogicState updated: {key} {getattr(self, key)} -> {val}')
        super().__setattr__(key, val)


class BusinessLogic:
    def __init__(self, main_app: 'MainWidget'):
        self.logic_state = LogicState()

        self.main_app = main_app
        main_app.wBtn_download_fw.setDisabled(False)
        main_app.wBtn_download_fw.clicked.connect(self.spawn_worker_thread(self.download_and_extract_fw))

        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(1)  # Only one worker

        # Manually spawn a worker to grab tags from GitHub
        self.spawn_worker_thread(self.get_fw_versions)()

    def spawn_worker_thread(self, fn):
        @Slot()
        def worker_thread_slot():
            all_threads_removed = self.threadpool.waitForDone(msecs=5000)
            if not all_threads_removed:
                log.fatal(f'Waited too long for threads to exit! {self.threadpool.activeThreadCount()}')
                exit(1)

            log.debug(f'Creating worker {str(fn)}')
            worker = Worker(fn)
            worker.signals.result.connect(self.worker_finished)
            # this fixes a bug with thread signal allocation/deallocation
            worker.setAutoDelete(False)
            self.threadpool.start(worker)
        return worker_thread_slot

    @Slot()
    def worker_finished(self, worker_name: Optional[str] = None):
        # Update all of the gui logic
        if worker_name == self.get_fw_versions.__name__ and self.logic_state.release_list is not None:
            self.get_fw_versions_result(self.main_app, self.logic_state.release_list)
        elif worker_name == self.download_and_extract_fw.__name__ and self.logic_state.pio_envs is not None:
            self.download_and_extract_fw_result(self.main_app, self.logic_state.pio_envs)

    def get_fw_versions(self) -> str:
        fw_api_url = 'https://api.github.com/repos/OpenAstroTech/OpenAstroTracker-Firmware/releases'
        print(f'Grabbing available FW versions from {fw_api_url}')
        response = requests.get(fw_api_url)
        releases_list = [
            FWVersion('develop',
                      'https://github.com/OpenAstroTech/OpenAstroTracker-Firmware/archive/refs/heads/develop.zip'),
        ]
        for release_json in response.json():
            releases_list.append(FWVersion(release_json['name'], release_json['zipball_url']))

        self.logic_state.release_list = releases_list
        return self.get_fw_versions.__name__

    @staticmethod
    def get_fw_versions_result(main_app: 'MainWidget', fw_versions_list: List[FWVersion]):
        # Add all the FW versions to the combo box
        main_app.wCombo_fw_version.clear()
        for fw_version in fw_versions_list:
            main_app.wCombo_fw_version.addItem(fw_version.nice_name)
        main_app.wCombo_fw_version.setCurrentIndex(0)
        main_app.wBtn_download_fw.setDisabled(False)

    def download_and_extract_fw(self) -> str:
        fw_idx = self.main_app.wCombo_fw_version.currentIndex()
        zip_url = self.logic_state.release_list[fw_idx].url
        zipfile_name = self.download_fw(zip_url)
        fw_dir = self.extract_fw(zipfile_name)

        self.logic_state.pio_envs = self.get_pio_environments(fw_dir)
        return self.download_and_extract_fw.__name__

    @staticmethod
    def download_and_extract_fw_result(main_app: 'MainWidget', pio_environments: List[str]):
        # Add all the platformio environments to the combo box
        main_app.wCombo_pio_env.clear()
        for pio_env_name in pio_environments:
            main_app.wCombo_pio_env.addItem(pio_env_name)
        main_app.wCombo_pio_env.setCurrentIndex(0)
        main_app.wBtn_build_fw.setDisabled(False)

    @staticmethod
    def download_fw(zip_url: str) -> str:
        log.info(f'Downloading OAT FW from: {zip_url}')
        resp = requests.get(zip_url)
        zipfile_name = 'OATFW.zip'
        with open(zipfile_name, 'wb') as fd:
            fd.write(resp.content)
            fd.close()
        return zipfile_name

    @staticmethod
    def extract_fw(zipfile_name: str) -> str:
        log.info(f'Extracting FW from {zipfile_name}')
        with zipfile.ZipFile(zipfile_name, 'r') as zip_ref:
            zip_infolist = zip_ref.infolist()
            if len(zip_infolist) > 0 and zip_infolist[0].is_dir():
                fw_dir = zip_infolist[0].filename
            else:
                log.fatal(f'Could not find FW top level directory in {zip_infolist}!')
                exit(1)
            zip_ref.extractall()
        log.info(f'Extracted FW to {fw_dir}')
        return fw_dir

    @staticmethod
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
        log.info(f'Found pio environments: {pio_environments}')
        return pio_environments

    @staticmethod
    def build_fw(pio_environment: str, fw_dir: str):
        print(f'Building FW environment={pio_environment} dir={fw_dir}')
        pio_run(['--environment', pio_environment, '--project-dir', fw_dir])


class MainWidget(QWidget):
    def __init__(self, log_object: QObject):
        QWidget.__init__(self)

        # widgets
        self.wMsg_fw_version = QLabel('Select firmware version:')
        # self.w_message.alignment = Qt.AlignCenter
        self.wCombo_fw_version = QComboBox()
        self.wCombo_fw_version.setPlaceholderText('Grabbing FW Versions...')
        self.wBtn_download_fw = QPushButton('Download')
        self.wBtn_download_fw.setDisabled(True)

        self.wMsg_pio_env = QLabel('Select board:')
        self.wCombo_pio_env = QComboBox()
        self.wCombo_pio_env.setPlaceholderText('No FW downloaded yet...')
        self.wBtn_select_local_config = QPushButton('Select local config file')
        self.wBtn_build_fw = QPushButton('Build FW')
        self.wBtn_build_fw.setDisabled(True)

        self.wBtn_upload_fw = QPushButton('Upload FW')
        self.wBtn_upload_fw.setDisabled(True)

        self.logText = QPlainTextEdit()
        self.logText.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.logText.setReadOnly(True)

        # layout
        self.layout = QGridLayout(self)
        layout_arr = [
            [self.wMsg_fw_version, self.wCombo_fw_version, self.wBtn_download_fw, None, self.logText],
            [self.wMsg_pio_env, self.wCombo_pio_env, self.wBtn_select_local_config, self.wBtn_build_fw],
            [self.wBtn_upload_fw]
        ]
        for y, row_arr in enumerate(layout_arr):
            for x, widget in enumerate(row_arr):
                if widget is not None:
                    self.layout.addWidget(widget, y, x)

        # signals
        log_object.log_signal.connect(self.logText.appendHtml)
        self.wBtn_select_local_config.clicked.connect(self.open_local_config_file)

        # business logic will connect signals as well
        self.logic = BusinessLogic(self)

    @Slot()
    def open_local_config_file(self):
        file_name, file_filter = QFileDialog.getOpenFileName(self, 'Open Local Config', '.', 'OAT Config (*.h, *.hpp)')
        log.info(f'Selected local config {file_name}')


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
            log_str = pre + super().format(record) + post
        elif self.colour_type == LogColourTypes.html:
            pre, post = self._colour_html(record.levelno)
            log_str = pre + html.escape(super().format(record)) + post
        else:
            log_str = super().format(record)
        return log_str


def main():
    if sys.base_prefix == sys.prefix:
        log.fatal('I should be running in a virtual environment! Something is wrong...')
        exit(1)

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
