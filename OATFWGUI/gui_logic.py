import re
import logging
import sys
import zipfile
import json
import shutil
from typing import List, Optional
from pathlib import Path

from PySide6.QtCore import Slot, QThreadPool, QFile, QProcess
from PySide6.QtWidgets import QWidget, QFileDialog

import requests

from log_utils import LoggedExternalFile
from qt_extensions import Worker
from qbusyindicatorgoodbad import BusyIndicatorState
from external_processes import external_processes, get_install_dir
from gui_state import LogicState, PioEnv, FWVersion
from anon_usage_data import AnonStatsDialog, create_anon_stats, upload_anon_stats
from misc_utils import delete_directory

log = logging.getLogger('')


def read_platformio_ini_file(logic_state: LogicState) -> List[str]:
    ini_path = Path(logic_state.fw_dir, 'platformio.ini')
    with open(ini_path.resolve(), 'r') as fp:
        ini_lines = fp.readlines()
    return ini_lines


def get_pio_environments(ini_lines: List[str]) -> List[PioEnv]:
    environment_lines = [ini_line for ini_line in ini_lines if ini_line.startswith('[env:')]
    raw_pio_envs = []
    for environment_line in environment_lines:
        match = re.search(r'\[env:(.+)\]', environment_line)
        if match:
            raw_pio_envs.append(match.group(1))
    log.info(f'Found pio environments: {raw_pio_envs}')

    # we don't want to build native
    if 'native' in raw_pio_envs:
        raw_pio_envs.remove('native')
    nice_name_lookup = {
        'ramps': 'RAMPS',
        'esp32': 'ESP32',
        'mksgenlv21': 'MKS Gen L v2.1',
        'mksgenlv2': 'MKS Gen L v2',
        'mksgenlv1': 'MKS Gen L v1',
    }
    pio_environments = []
    for raw_env in raw_pio_envs:
        # Try to match a raw env to nice name, fallback to raw env
        pio_env = PioEnv(nice_name_lookup.get(raw_env, raw_env), raw_env)
        pio_environments.append(pio_env)
    return pio_environments


def download_fw(zip_url: str) -> Path:
    log.info(f'Downloading OAT FW from: {zip_url}')
    r = requests.get(zip_url)
    zipfile_name = Path(get_install_dir(), 'OATFW.zip')
    with open(zipfile_name, 'wb') as fd:
        fd.write(r.content)
        fd.close()
    return zipfile_name


def extract_fw(zipfile_name: Path) -> Path:
    # For Windows path length reasons, keep the firmware folder name short
    fw_dir = Path(get_install_dir(), 'OATFW')
    if fw_dir.exists():
        log.info(f'Removing previously downloaded FW from {fw_dir}')
        delete_directory(fw_dir)

    log.info(f'Extracting FW from {zipfile_name}')
    with zipfile.ZipFile(zipfile_name, 'r') as zip_ref:
        zip_infolist = zip_ref.infolist()
        if len(zip_infolist) > 0 and zip_infolist[0].is_dir():
            extracted_dir = Path(get_install_dir(), zip_infolist[0].filename)
        else:
            log.fatal(f'Could not find FW top level directory in {zip_infolist}!')
            sys.exit(1)
        zip_ref.extractall()

    log.info(f'Rename {extracted_dir} to {fw_dir}')
    shutil.move(extracted_dir, fw_dir)
    log.info(f'Extracted FW to {fw_dir}')
    return fw_dir


class BusinessLogic:
    def __init__(self, main_app: QWidget):
        self.logic_state = LogicState()

        self.main_app = main_app
        main_app.wCombo_fw_version.currentIndexChanged.connect(self.fw_version_combo_box_changed)
        main_app.wBtn_download_fw.setEnabled(True)
        main_app.wBtn_download_fw.clicked.connect(self.spawn_worker_thread(self.download_and_extract_fw))
        main_app.wBtn_select_local_config.clicked.connect(self.open_local_config_file)
        main_app.wCombo_pio_env.currentIndexChanged.connect(self.pio_env_combo_box_changed)
        main_app.wBtn_build_fw.clicked.connect(self.spawn_worker_thread(self.build_fw))
        main_app.wBtn_refresh_ports.clicked.connect(self.spawn_worker_thread(self.refresh_ports))
        main_app.wCombo_serial_port.currentIndexChanged.connect(self.serial_port_combo_box_changed)
        main_app.wBtn_upload_fw.clicked.connect(self.spawn_worker_thread(self.upload_fw))
        main_app.wBtn_what_stats.clicked.connect(self.modal_show_stats)

        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(1)  # Only one worker

        # Manually spawn a worker to grab tags from GitHub
        self.spawn_worker_thread(self.get_fw_versions)()
        # Manually spawn a worker to refresh serial ports
        self.spawn_worker_thread(self.refresh_ports)()

        # Need to create in the main thread else it doesn't work?
        self.avr_dude_logwatch = LoggedExternalFile()

    def spawn_worker_thread(self, fn):
        @Slot()
        def worker_thread_slot():
            msecs = 5000
            all_threads_removed = self.threadpool.waitForDone(msecs)
            if not all_threads_removed:
                log.fatal(f'Waited too long for threads to sys.exit! {self.threadpool.activeThreadCount()}')
                sys.exit(1)

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
            self.logic_state.pio_env = None
            self.download_and_extract_fw_result(self.main_app, self.logic_state.pio_envs)

        if self.logic_state.config_file_path is not None:
            self.main_app.wMsg_config_path.setText(f'Local configuration file:\n{self.logic_state.config_file_path}')

        # check requirements to unlock the build button
        build_reqs_ok = all([
            self.logic_state.config_file_path is not None,
            self.logic_state.pio_env is not None,
        ])
        self.main_app.wBtn_build_fw.setEnabled(build_reqs_ok)

        # check requirements to unlock the upload button
        upload_reqs_ok = all([
            self.logic_state.build_success == True,
            self.logic_state.upload_port is not None,
        ])
        self.main_app.wBtn_upload_fw.setEnabled(upload_reqs_ok)

    def get_fw_versions(self) -> str:
        fw_api_url = 'https://api.github.com/repos/OpenAstroTech/OpenAstroTracker-Firmware/releases'
        log.info(f'Grabbing available FW versions from {fw_api_url}')
        r = requests.get(fw_api_url, timeout=5000)
        releases_list = [
            FWVersion('develop',
                      'https://github.com/OpenAstroTech/OpenAstroTracker-Firmware/archive/refs/heads/develop.zip'),
        ]
        if r.status_code != requests.codes.ok:
            log.error(f'Failed to grab latest FW versions: {r.status_code} {r.reason} {r.text}')
        for release_json in r.json():
            try:
                fw_version = FWVersion(release_json['name'], release_json['zipball_url'])
            except TypeError as e:
                log.error(f'release_json={release_json}')
                raise e
            releases_list.append(fw_version)

        self.logic_state.release_list = releases_list
        return self.get_fw_versions.__name__

    @staticmethod
    def get_fw_versions_result(main_app: 'MainWidget', fw_versions_list: List[FWVersion]):
        # Add all the FW versions to the combo box
        main_app.wCombo_fw_version.clear()
        for fw_version in fw_versions_list:
            main_app.wCombo_fw_version.addItem(fw_version.nice_name)
        main_app.wCombo_fw_version.setCurrentIndex(0)
        main_app.wBtn_download_fw.setEnabled(True)

    def download_and_extract_fw(self) -> str:
        self.main_app.wSpn_download.setState(BusyIndicatorState.BUSY)
        self.logic_state.release_idx = self.main_app.wCombo_fw_version.currentIndex()
        zip_url = self.logic_state.release_list[self.logic_state.release_idx].url
        zipfile_name = download_fw(zip_url)

        self.logic_state.fw_dir = extract_fw(zipfile_name)
        ini_lines = read_platformio_ini_file(self.logic_state)
        self.logic_state.pio_envs = get_pio_environments(ini_lines)
        return self.download_and_extract_fw.__name__

    @staticmethod
    def download_and_extract_fw_result(main_app: 'MainWidget', pio_environments: List[PioEnv]):
        main_app.wSpn_download.setState(BusyIndicatorState.GOOD)
        # Add all the platformio environments to the combo box
        main_app.wCombo_pio_env.clear()
        for pio_env_name in pio_environments:
            main_app.wCombo_pio_env.addItem(pio_env_name.nice_name)
        main_app.wCombo_pio_env.setPlaceholderText('Select Board')

    @Slot()
    def fw_version_combo_box_changed(self, idx: int):
        if idx == self.logic_state.release_idx:
            return  # Nothing changed, nothing to do
        # Clear most state, if FW version is changed we want the user to go through the steps again
        # (technically not necessary but can trip some users up)
        log.debug('FW version changed, clearing some state')
        self.logic_state.pio_envs.clear()
        self.logic_state.pio_env = None
        self.main_app.wSpn_download.setState(BusyIndicatorState.NONE)
        self.main_app.wCombo_pio_env.clear()
        self.main_app.wSpn_build.setState(BusyIndicatorState.NONE)
        self.worker_finished()

    @Slot()
    def pio_env_combo_box_changed(self, idx: int):
        if self.logic_state.pio_envs and idx != -1:
            self.logic_state.pio_env = self.logic_state.pio_envs[idx].raw_name
            # manually update GUI
            self.worker_finished()
        else:
            self.logic_state.pio_env = None

    @Slot()
    def open_local_config_file(self):
        file_path, file_filter = QFileDialog.getOpenFileName(self.main_app, 'Open Local Config', '.',
                                                             'OAT Config (*.h, *.hpp)')
        log.info(f'Selected local config {file_path}')
        self.logic_state.config_file_path = file_path

        # manually update GUI
        self.worker_finished()

    def do_hot_patches(self):
        # Before logging anything, check that we need to do something
        ini_lines = read_platformio_ini_file(self.logic_state)
        bad_git_tag_re = re.compile(r'(github\.com.+)@')
        if any(bad_git_tag_re.search(ini_line) for ini_line in ini_lines):
            log.warning('Hot patching git tag specifiers!!!')
            def patch_line(in_str: str) -> str:
                if bad_git_tag_re.search(in_str):
                    out_str = bad_git_tag_re.sub(r'\1#', in_str)
                    log.warning(f'Replacing {in_str} with {out_str}')
                    return out_str
                else:
                    return in_str
            ini_lines = [
                patch_line(line)
                for line in ini_lines
            ]
            with open(Path(self.logic_state.fw_dir, 'platformio.ini').resolve(), 'w') as fp:
                fp.writelines(ini_lines)

        if self.logic_state.env_is_avr_based():
            # hard match the entire line
            # readline[s]() will always terminate a line with \n (and not \r\n on windows! :D)
            # https://docs.python.org/3.11/tutorial/inputoutput.html#methods-of-file-objects
            bad_platform_line = 'platform = atmelavr\n'
            good_platform_line = 'platform = atmelavr@4.2.0\n'
            if bad_platform_line in ini_lines:
                log.warning('Hot patching platformio AVR platform!!!')
                log.warning(f'Replacing {repr(bad_platform_line)} with {repr(good_platform_line)}')
                ini_lines = [
                    good_platform_line if line == bad_platform_line else line
                    for line in ini_lines
                ]
                with open(Path(self.logic_state.fw_dir, 'platformio.ini').resolve(), 'w') as fp:
                    fp.writelines(ini_lines)

    def build_fw(self):
        self.main_app.wSpn_build.setState(BusyIndicatorState.BUSY)

        # Hot patches, since we can't re-release an old firmware tag
        self.do_hot_patches()

        config_dest_path = str(Path(self.logic_state.fw_dir, 'Configuration_local.hpp').resolve())
        if Path(config_dest_path) != Path(self.logic_state.config_file_path):
            if QFile.exists(config_dest_path):
                log.warning(f'Deleting existing configuration file {config_dest_path}')
                QFile.remove(config_dest_path)
            log.info(f'Copying config file from {self.logic_state.config_file_path} -> {config_dest_path}')
            copy_success = QFile.copy(self.logic_state.config_file_path, config_dest_path)
            if not copy_success:
                log.error(f'Could not copy config file to {config_dest_path}')
                self.main_app.wSpn_build.setState(BusyIndicatorState.BAD)
                return
        else:
            log.info(f'Not copying config file since source and destination are the same: {config_dest_path}')

        log.info(f'Building FW environment={self.logic_state.pio_env} dir={self.logic_state.fw_dir}')

        if external_processes['platformio'].state != QProcess.NotRunning:
            log.error(f"platformio already running! {external_processes['platformio']}")
            self.main_app.wSpn_build.setState(BusyIndicatorState.BAD)
            return

        external_processes['platformio'].start(
            ['run',
             '--environment', self.logic_state.pio_env,
             '--project-dir', str(self.logic_state.fw_dir),
             '--verbose'
             ],
            self.pio_build_finished,
        )

    @Slot()
    def pio_build_finished(self):
        log.info(f'platformio build finished')
        exit_code = external_processes['platformio'].qproc.exitCode()
        if exit_code == 0:
            log.info('Normal exit')
            self.main_app.wSpn_build.setState(BusyIndicatorState.GOOD)
            self.logic_state.build_success = True
        else:
            log.error('Did not exit normally')
            self.main_app.wSpn_build.setState(BusyIndicatorState.BAD)

    def refresh_ports(self):
        if external_processes['platformio'].state != QProcess.NotRunning:
            log.error(f"platformio already running! {external_processes['platformio']}")
            return

        external_processes['platformio'].start(
            ['device', 'list', '--serial', '--json-output'],
            self.pio_refresh_ports_finished,
        )

    @Slot()
    def pio_refresh_ports_finished(self):
        log.info(f'platformio refresh ports finished')
        exit_code = external_processes['platformio'].qproc.exitCode()
        if exit_code == 0:
            log.info('Normal exit')
        else:
            log.error('Did not exit normally')
        stdout_data = external_processes['platformio'].stdout_text
        if stdout_data:
            try:
                all_port_data = json.loads(stdout_data)
            except json.decoder.JSONDecodeError as e:
                log.error(f'JSONDecodeError: {e} with\n{repr(stdout_data)}')
                all_port_data = []
            self.logic_state.serial_ports = [port_data['port'] for port_data in all_port_data]
        else:
            self.logic_state.serial_ports = []

        self.main_app.wCombo_serial_port.clear()
        for serial_port in self.logic_state.serial_ports:
            self.main_app.wCombo_serial_port.addItem(serial_port)

    @Slot()
    def serial_port_combo_box_changed(self, idx: int):
        if self.logic_state.serial_ports and idx != -1:
            self.logic_state.upload_port = self.logic_state.serial_ports[idx]
            # manually update GUI
            self.worker_finished()
        else:
            self.logic_state.upload_port = None

    def upload_fw(self):
        self.main_app.wSpn_upload.setState(BusyIndicatorState.BUSY)
        if external_processes['platformio'].state != QProcess.NotRunning:
            log.error(f"platformio already running! {external_processes['platformio']}")
            return

        # Stupid fix for avrdude outputting to stderr by default
        if self.logic_state.env_is_avr_based():
            avrdude_logfile_name = self.avr_dude_logwatch.create_file(file_suffix='_avrdude_log')
            # Note: avrdude doesn't strip the filename! So no spaces at the beginning
            env_vars = {'PLATFORMIO_UPLOAD_FLAGS': f'-l{avrdude_logfile_name}'}
        else:
            env_vars = {}

        external_processes['platformio'].start(
            ['run',
             '--environment', self.logic_state.pio_env,
             '--project-dir', str(self.logic_state.fw_dir),
             '--verbose',
             '--target', 'upload',
             '--upload-port', self.logic_state.upload_port,
             ],
            self.pio_upload_finished,
            env_vars=env_vars,
        )

    @Slot()
    def pio_upload_finished(self):
        log.info(f'platformio upload finished')
        if self.logic_state.env_is_avr_based():
            self.avr_dude_logwatch.stop()
        exit_code = external_processes['platformio'].qproc.exitCode()
        if exit_code == 0:
            log.info('Normal exit')
            self.main_app.wSpn_upload.setState(BusyIndicatorState.GOOD)
        else:
            log.error('Did not exit normally')
            self.main_app.wSpn_upload.setState(BusyIndicatorState.BAD)

        if self.main_app.wChk_upload_stats.isChecked():
            log.info('Uploading anonymous usage statistics')
            anon_stats = create_anon_stats(self.logic_state)
            upload_anon_stats(anon_stats)
        else:
            log.info('NOT uploading anonymous usage statistics')

    @Slot()
    def modal_show_stats(self):
        dlg = AnonStatsDialog(self.logic_state, self.main_app)
        dlg.exec_()
