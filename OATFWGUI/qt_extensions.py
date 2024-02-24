import sys
import traceback
import logging
from typing import Optional

from PySide6.QtCore import Slot, Signal, QObject, QRunnable, QMetaMethod
from PySide6.QtWidgets import QWidget

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
        except Exception as e:
            # Catch the exception, send the error signal, then raise the exception for the excepthook
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
            raise e
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


class RegisteredCustomWidget(QWidget):
    """
    See https://doc.qt.io/qt-6/designer-ui-file-format.html for the XML format (it's kind of hard to read tho :/)
    Also see https://doc.qt.io/qt-6/designer-creating-custom-widgets.html
    """
    designer_tooltip = ''
    designer_dom_xml = ''

    @classmethod
    def factory(cls: 'RegisteredCustomWidget'):
        if not cls.designer_tooltip:
            cls.designer_tooltip = f'{cls.__name__} tooltip'
        if cls.designer_dom_xml:
            cls.designer_dom_xml = f'''
<ui language='c++'>
    <widget class='{cls.__name__}' name='{cls.__name__.lower()}'>
    </widget>
</ui>
'''

        cls.designer_module = cls.__name__.lower()

        return cls

    def running_in_designer(self):
        # TODO: This is specific to the .ui file, is there a cleaner way to make it generic?
        return self.window().objectName() != 'TopLevelWidget'


# https://stackoverflow.com/a/68621792/1313872
# Idk why this is so hard for Qt
def get_signal(o_object: QObject, str_signal_name: str) -> Optional[QMetaMethod]:
    o_meta_obj = o_object.metaObject()
    for i in range(o_meta_obj.methodCount()):
        o_meta_method = o_meta_obj.method(i)
        if not o_meta_method.isValid():
            continue
        if o_meta_method.methodType() == QMetaMethod.Signal and o_meta_method.name() == str_signal_name:
            return o_meta_method
    return None
