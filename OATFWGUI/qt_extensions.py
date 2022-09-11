import sys
import traceback
import logging

from PySide6.QtCore import Slot, Signal, QObject, QRunnable, QProcess

log = logging.getLogger('')


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


class ExternalProcess:
    def __init__(self, proc_name, proc_args, finish_signal):
        self.proc_name = proc_name
        self.proc_args = proc_args

        self.qproc = QProcess()
        self.qproc.setProgram(self.proc_name)
        self.qproc.setArguments(self.proc_args)

        # signals
        self.qproc.readyReadStandardOutput.connect(self.handle_stdout)
        self.qproc.readyReadStandardError.connect(self.handle_stderr)
        self.qproc.stateChanged.connect(self.handle_state)
        self.qproc.finished.connect(finish_signal)

    def start(self):
        log.info(f'Starting {self.proc_name} with args: {self.proc_args}')
        self.qproc.start()
        # Not sure why, but the process doesn't start without these
        proc_started = self.qproc.waitForStarted(5000)
        if not proc_started:
            log.warning(f'{self.proc_name}:did not start')
        proc_finished = self.qproc.waitForFinished(60000)
        if not proc_finished:
            log.warning(f'{self.proc_name}:did not finish')

    @Slot()
    def handle_stderr(self):
        data = self.qproc.readAllStandardError()
        stderr = bytes(data).decode("utf8")
        log.error(stderr)

    @Slot()
    def handle_stdout(self):
        data = self.qproc.readAllStandardOutput()
        stdout = bytes(data).decode("utf8")
        log.info(stdout)

    @Slot()
    def handle_state(self, state):
        state_name = {
            QProcess.NotRunning: 'Not running',
            QProcess.Starting: 'Starting',
            QProcess.Running: 'Running',
        }.get(state)
        log.info(f'{self.proc_name}:State changed: {state_name}')
