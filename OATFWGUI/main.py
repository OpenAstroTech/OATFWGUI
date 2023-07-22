#!/bin/env python3

import sys
import logging
import os
import argparse
import time
import tempfile
import requests
import json
from pathlib import Path
from typing import Dict, Tuple, Optional

import semver
from PySide6.QtCore import Slot, Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QStatusBar, QLabel
from PySide6.QtGui import QAction, QActionGroup

from _version import __version__
from log_utils import LogObject, setup_logging
from gui_logic import MainWidget
from platform_check import get_platform, PlatformEnum
from external_processes import external_processes, add_external_process, get_install_dir
from anon_usage_data import create_anon_stats

parser = argparse.ArgumentParser(usage='Graphical way to build and load OAT Firmware')
parser.add_argument('--no-gui', action='store_true',
                    help='Do not start the graphics, exit just before then (used as a basic functionality test)')
parser.add_argument('-v', '--version', action='version',
                    version=__version__,
                    help='Print version string and exit')


def check_and_warn_directory_path_length(dir_to_check: Path, max_path_len: int, warn_str: str):
    num_chars_in_dir = len(str(dir_to_check))
    if num_chars_in_dir > max_path_len:
        # Make it a big 'ol block warning
        general_warn_str = f'''Path {dir_to_check} might
have too many characters in it ({num_chars_in_dir})! Downloading/building firmware may create files with path
lengths greater than the default Windows path length of 260 characters.
'''
        for log_line in (general_warn_str + warn_str).split('\n'):
            log.warning(log_line)


def setup_environment():
    install_dir = get_install_dir()
    log.debug(f'Install dir is {install_dir}')
    if get_platform() == PlatformEnum.WINDOWS:
        # With 54fa285a dependencies the maximum path length is 180.
        # 260-180=80, but derate to 75 (for possible future increases)
        # pushd {install_dir} && find . -print|awk '{print length($0), $0}'|sort --numeric --reverse|head -n20
        log_msg = f'''If you get 'file not found' errors the easiest solution is to move
the {install_dir.resolve()} folder somewhere with less characters in the path.'''
        check_and_warn_directory_path_length(install_dir, 75, log_msg)

    # Putting the platformio core directory in a temporary folder is only needed because
    # Windows doesn't support long path names... :/
    pio_core_dir = Path(tempfile.gettempdir(), f'.pio_OATFWGUI_{__version__}')
    log.info(f'Setting PLATFORMIO_CORE_DIR to {pio_core_dir}')
    os.environ['PLATFORMIO_CORE_DIR'] = str(pio_core_dir)

    python_interpreter_path = Path(sys.executable)
    log.debug(f'Python interpreter: {python_interpreter_path}')
    python_interpreter_dir = python_interpreter_path.parent
    log.debug(f'Python interpreter dir: {python_interpreter_dir}')
    embedded_python_scripts_dir = Path(python_interpreter_dir, 'Scripts')
    log.debug(f'Embedded scripts dir: {embedded_python_scripts_dir}')

    if embedded_python_scripts_dir.is_dir():
        log.info('Running in embedded python')
        os.environ['PATH'] += os.pathsep + str(embedded_python_scripts_dir)
        add_external_process('platformio', str(python_interpreter_path), ['-m', 'platformio'])
    else:
        log.info('Not running in embedded python')
        add_external_process('platformio', 'platformio', [])

    external_processes['platformio'].start(['system', 'info'], None)
    external_processes['platformio'].start(['settings', 'set', 'check_platformio_interval', '9999'], None)
    external_processes['platformio'].start(['settings', 'set', 'check_prune_system_threshold', '0'], None)


def raw_version_to_semver() -> Optional[semver.VersionInfo]:
    # Needs to work for:
    # - release: 0.0.12-release+4702dd
    # - CI build: 0.0.12-dev+4702dd
    # - local unreleased: 0.0.12
    try:
        semver_ver = semver.VersionInfo.parse(__version__)
    except ValueError as e:
        log.warning(f'Could not parse my own version string {__version__} {e}')
        return None
    return semver_ver


def check_new_oatfwgui_release() -> Optional[Tuple[str, str]]:
    local_ver = raw_version_to_semver()
    if local_ver is None:
        return None

    oatfwgui_api_url = 'https://api.github.com/repos/OpenAstroTech/OATFWGUI/releases'
    log.info(f'Checking for new OATFWGUI release from {oatfwgui_api_url}')
    response = requests.get(oatfwgui_api_url, timeout=2000)
    if response.status_code != requests.codes.ok:
        log.error(f'Failed to check for new release: {response.status_code} {response.reason} {response.text}')
        return None

    releases: Dict[semver.VersionInfo, str] = {}
    latest_release_ver: Optional[semver.VersionInfo] = None
    for release_json in response.json():
        try:
            release_ver = semver.VersionInfo.parse(release_json['tag_name'])
        except ValueError as e:
            log.warning(f'Could not parse tag name as semver {release_json["tag_name"]} {e}')
            continue
        releases[release_ver] = release_json['html_url']
        if latest_release_ver is None or release_ver > latest_release_ver:
            latest_release_ver = release_ver

    if latest_release_ver is None:
        log.debug(f'No latest release? {response.json()}')
        return None

    # need to 'finalize' the version, as we use the prerelease/build fields to indicate a release version
    # i.e. 0.0.12 > 0.0.12-release+4702dd
    latest_release_ver_finialized = latest_release_ver.finalize_version()
    local_ver_finialized = local_ver.finalize_version()

    if latest_release_ver_finialized > local_ver_finialized:
        log.info(f'New version is available! '
                 f'{latest_release_ver_finialized}({latest_release_ver}) > {local_ver_finialized}({local_ver})')
        return str(latest_release_ver), releases[latest_release_ver]
    else:
        log.debug(f'No new version '
                  f'{latest_release_ver_finialized}({latest_release_ver}) <= {local_ver_finialized}({local_ver})')
        return None


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

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        new_release_tup = check_new_oatfwgui_release()
        if new_release_tup is not None:
            new_release_html = f'<a href="{new_release_tup[1]}">New release {new_release_tup[0]} available!</a>'
        else:
            new_release_html = ''
        self.new_release_hyperlink = QLabel(new_release_html)
        self.new_release_hyperlink.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.new_release_hyperlink.setOpenExternalLinks(True)
        self.status_bar.addWidget(self.new_release_hyperlink)  # addWidget == left side

        self.bug_hyperlink = QLabel('<a href="https://github.com/OpenAstroTech/OATFWGUI/issues">Report a bug</a>')
        self.bug_hyperlink.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.bug_hyperlink.setOpenExternalLinks(True)
        self.status_bar.addPermanentWidget(self.bug_hyperlink)  # addPermanentWidget == right side

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
    log.debug('Creating app')
    app = QApplication()

    log.debug('Creating main window')
    widget = MainWindow()
    widget.show()

    if not args.no_gui:
        log.debug('Executing app')
        retcode = app.exec()
    else:
        log.debug('NOT executing app')
        log.debug('Testing anonymous statistics creation')
        anon_stats = create_anon_stats(widget.main_widget.logic.logic_state)
        log.debug(f'Statistics: {json.dumps(anon_stats)}')
        # Wait a bit before exiting, prevents Qt complaining about deleted objects
        time.sleep(1.0)
        retcode = 0
    sys.exit(retcode)


if __name__ == '__main__':
    args = parser.parse_args()
    log = logging.getLogger('')
    l_o = LogObject()
    setup_logging(log, l_o)
    log.debug('Set up logging')
    main()
