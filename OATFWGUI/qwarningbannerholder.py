from typing import List

from PySide6.QtCore import Slot, Signal, Qt
from PySide6.QtWidgets import QVBoxLayout, QSizePolicy, QLabel
from qt_extensions import RegisteredCustomWidget


class QWarningBannerHolder(RegisteredCustomWidget):
    add_warning_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.label_widgets: List[QWarningLabel] = []

        self.vbox = QVBoxLayout()
        self.vbox.setAlignment(Qt.AlignHCenter)
        self.setLayout(self.vbox)
        self.add_warning_signal.connect(self.add_warning)

        if self.running_in_designer():
            self.add_warning_signal.emit('Test warning 1')
            self.add_warning_signal.emit('Test warning 2')
            self.add_warning_signal.emit('Test warning 3')

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
