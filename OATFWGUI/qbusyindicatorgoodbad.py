import math
import enum
import logging

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QWidget, QStackedWidget, QHBoxLayout, QSizePolicy
from PySide6.QtGui import QPainter, QColor, QPen

from waitingspinnerwidget import QtWaitingSpinner
from qt_extensions import RegisteredCustomWidget

log = logging.getLogger('')


class BusyIndicatorState(enum.Enum):
    NONE = enum.auto()
    BUSY = enum.auto()
    GOOD = enum.auto()
    BAD = enum.auto()


class QBusyIndicatorGoodBad(RegisteredCustomWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.wSpn = QtWaitingSpinner(self, centerOnParent=False)
        self.wGood = QIndicatorGood(self)
        self.wBad = QIndicatorBad(self)

        self.wStacked = QStackedWidget()
        self.wStacked.addWidget(self.wSpn)
        self.wStacked.addWidget(self.wGood)
        self.wStacked.addWidget(self.wBad)
        self.wSpn.start()

        self.hbox = QHBoxLayout(self)
        self.hbox.addWidget(self.wStacked)
        self.hbox.setAlignment(Qt.AlignCenter)
        self.setLayout(self.hbox)

        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setFixedSize(QSize(50, 50))

        self.size_policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setSizePolicy(self.size_policy)
        if self.running_in_designer():
            self.setState(BusyIndicatorState.BUSY)
        else:
            self.setState(BusyIndicatorState.NONE)

        self.setAttribute(Qt.WA_DontShowOnScreen)
        self.show()

    def setState(self, state: BusyIndicatorState):
        if state == BusyIndicatorState.NONE:
            self.wStacked.hide()
        elif state == BusyIndicatorState.BUSY:
            self.wStacked.setCurrentWidget(self.wSpn)
            self.wStacked.show()
            # self.wSpn.update()
        elif state == BusyIndicatorState.GOOD:
            self.wStacked.setCurrentWidget(self.wGood)
            self.wStacked.show()
        elif state == BusyIndicatorState.BAD:
            self.wStacked.setCurrentWidget(self.wBad)
            self.wStacked.show()
        else:
            log.error(f'Invalid busy indicator state {state}')


class QIndicatorGood(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, QPaintEvent):
        painter = QPainter(self)
        max_width = painter.device().width()
        max_height = painter.device().height()
        bounding_size = min(max_width, max_height)
        pen = QPen()
        pen.setWidth(0.05 * bounding_size)
        pen.setColor(QColor('green'))
        painter.setPen(pen)

        painter.drawEllipse(0, 0,
                            bounding_size, bounding_size)
        bottom_point = (0.5 * bounding_size, 0.9 * bounding_size)
        painter.drawLine(0.2 * bounding_size, 0.6 * bounding_size,
                         *bottom_point)
        painter.drawLine(*bottom_point,
                         0.8 * bounding_size, 0.2 * bounding_size)


class QIndicatorBad(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, QPaintEvent):
        painter = QPainter(self)
        max_width = painter.device().width()
        max_height = painter.device().height()
        bounding_size = min(max_width, max_height)
        pen = QPen()
        pen.setWidth(0.05 * bounding_size)
        pen.setColor(QColor('red'))
        painter.setPen(pen)

        painter.drawEllipse(0, 0,
                            bounding_size, bounding_size)
        circle_width_fudge = 0.00001 * bounding_size  # move the lines into the circle's width just a little
        on_circle_top_half = (0.5 * math.cos(math.pi * 3 / 4) + 0.5) + circle_width_fudge
        on_circle_bot_half = (0.5 * math.cos(math.pi * 1 / 4) + 0.5) - circle_width_fudge
        painter.drawLine(on_circle_top_half * bounding_size, on_circle_top_half * bounding_size,
                         on_circle_bot_half * bounding_size, on_circle_bot_half * bounding_size)
        painter.drawLine(on_circle_top_half * bounding_size, on_circle_bot_half * bounding_size,
                         on_circle_bot_half * bounding_size, on_circle_top_half * bounding_size)
