"""การแจ้งเตือนชั่วคราวมุมขวาล่าง (toast) พร้อมเฟดเข้า/ออก — ใช้แทนกล่องข้อความที่ไม่จำเป็นต้องกดปิด"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QWidget

_ICONS = dict(ok="✔", warn="⚠", error="✖", info="●")


class Toast(QFrame):
    MARGIN = 18

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._icon = QLabel()
        self._icon.setObjectName("ToastIcon")
        self._text = QLabel()
        self._text.setWordWrap(True)
        self._text.setMaximumWidth(380)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 16, 10)
        lay.setSpacing(10)
        lay.addWidget(self._icon)
        lay.addWidget(self._text, 1)
        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(0.0)
        self.setGraphicsEffect(self._fx)
        self._anim = QPropertyAnimation(self._fx, b"opacity", self)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self._hide_if_clear)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self.hide()

    def show_message(self, text: str, kind: str = "info", msec: int = 3200) -> None:
        self._anim.stop()
        self._text.setText(text)
        self._icon.setText(_ICONS.get(kind, _ICONS["info"]))
        self.setProperty("kind", kind)
        self.style().unpolish(self)
        self.style().polish(self)
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._fade(self._fx.opacity(), 1.0, 180)
        self._timer.start(msec)

    def reposition(self) -> None:
        p = self.parentWidget()
        if p is not None:
            self.move(p.width() - self.width() - self.MARGIN, p.height() - self.height() - self.MARGIN)

    def _fade(self, start: float, end: float, ms: int) -> None:
        self._anim.stop()
        self._anim.setDuration(ms)
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()

    def _fade_out(self) -> None:
        self._fade(self._fx.opacity(), 0.0, 260)

    def _hide_if_clear(self) -> None:
        if self._fx.opacity() == 0.0:
            self.hide()
