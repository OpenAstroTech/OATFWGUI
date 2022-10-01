import sys
import logging
from typing import List, Dict, Optional
from pathlib import Path

from PySide6.QtCore import Slot, QProcess, QStandardPaths

log = logging.getLogger('')


class ExternalProcess:
    def __init__(self, proc_name, base_args):
        self.proc_name = proc_name
        self.base_args = base_args

        self.stdout_text = ''
        self.stderr_text = ''
        self.state = QProcess.NotRunning

        self.qproc: Optional[QProcess] = None

    def start(self, extra_args: List[str], finish_signal: Optional):
        self.qproc = QProcess()
        self.qproc.setProgram(self.proc_name)
        self.qproc.setArguments(self.base_args)

        # signals
        self.qproc.readyReadStandardOutput.connect(self.handle_stdout)
        self.qproc.readyReadStandardError.connect(self.handle_stderr)
        self.qproc.stateChanged.connect(self.handle_state)

        all_args = self.base_args + extra_args
        self.qproc.setArguments(all_args)
        self.qproc.finished.connect(finish_signal)
        log.info(f'Starting {self.proc_name} with args: {all_args}')
        self.qproc.start()
        # Not sure why, but the process doesn't start without these
        proc_started = self.qproc.waitForStarted(10 * 1000)
        if not proc_started:
            log.warning(f'{self.proc_name}:did not start')
        # Basically infinite timeout to wait for the process to finish
        proc_finished = self.qproc.waitForFinished(999 * 60 * 1000)
        if not proc_finished:
            log.warning(f'{self.proc_name}:did not finish')
        self.cleanup()

    def cleanup(self):
        self.stdout_text = ''
        self.stderr_text = ''
        self.qproc.deleteLater()

    @Slot()
    def handle_stderr(self):
        data = self.qproc.readAllStandardError()
        stderr = bytes(data).decode("utf8")
        self.stderr_text += stderr
        log.error(stderr)

    @Slot()
    def handle_stdout(self):
        data = self.qproc.readAllStandardOutput()
        stdout = bytes(data).decode("utf8")
        self.stdout_text += stdout
        log.info(stdout)

    @Slot()
    def handle_state(self, state):
        state_name = {
            QProcess.NotRunning: 'Not running',
            QProcess.Starting: 'Starting',
            QProcess.Running: 'Running',
        }.get(state)
        self.state = state
        log.info(f'{self.proc_name}:State changed: {state_name}')


# Global dict to be modified after we can verify the external process exists
external_processes: Dict[str, ExternalProcess] = {}


def add_external_process(proc_name: str, prog_name: str, base_args: List[str]):
    log.debug(f'Adding external process {proc_name} ({prog_name}, {base_args})')

    exe_path = QStandardPaths.findExecutable(prog_name)
    log.debug(f'Path is {exe_path}')
    if exe_path == '':
        log.fatal(f'Could not find {proc_name}!')
        sys.exit(1)

    external_processes[proc_name] = ExternalProcess(prog_name, base_args)


main_script_parent_dir: Optional[Path] = None


def get_install_dir(cache=True) -> Path:
    global main_script_parent_dir
    if main_script_parent_dir is None or not cache:
        main_script_path = Path(__file__)
        main_script_parent_dir = main_script_path.parent.parent.resolve()
        log.debug(f'Install directory is {main_script_parent_dir}')
    return main_script_parent_dir
