from typing import List, Set

from PySide6.QtCore import Slot, Signal, Qt, QTimer
from PySide6.QtWidgets import QVBoxLayout, QSizePolicy, QLabel
from qt_extensions import RegisteredCustomWidget

global_warning_banners: Set[str] = set()


class QWarningBannerHolder(RegisteredCustomWidget):
    add_warning_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.label_widgets: List[QWarningLabel] = []

        self.vbox = QVBoxLayout()
        self.vbox.setAlignment(Qt.AlignHCenter)
        self.setLayout(self.vbox)

        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.check_global_warnings)
        self.check_timer.setInterval(1000)  # every second
        self.check_timer.start()

        self.add_warning_signal.connect(self.add_warning)

        if self.running_in_designer():
            global_warning_banners.add('Test warning 1')
            global_warning_banners.add('Test warning 2')
            global_warning_banners.add('Test warning 3')

    def check_global_warnings(self):
        # Just go through all of our labels and compare the text
        # Not efficient but whatever
        for warn_str in global_warning_banners:
            if not any(warn_str in wid.text() for wid in self.label_widgets):
                self.add_warning_signal.emit(warn_str)

    # Need to use signals and slots else we get:
    # QObject::setParent: Cannot set parent, new parent is in a different thread
    @Slot()
    def add_warning(self, text: str):
        self.label_widgets.append(QWarningLabel(text))
        self.vbox.addWidget(self.label_widgets[-1])


class QWarningLabel(QLabel):
    def __init__(self, text: str):
        super().__init__(f'WARNING:{text}')
        self.setStyleSheet('QLabel { background-color : yellow; }')
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
