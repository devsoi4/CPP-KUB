"""หน้า Welcome (splash) ตอนเปิดโปรแกรม: logo + ชื่อ + เว็บผู้จัดทำ แล้วหายเองหลังไม่กี่วินาที"""
from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from . import theme
from .compiler import app_dir

SHOW_MS = 5000   # เวลาที่แสดง (มิลลิวินาที)
FADE_MS = 300    # เวลา fade-out


class SplashScreen(QWidget):
    finished = Signal()

    def __init__(self, dark: bool) -> None:
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        p = theme.palette(dark)
        self.setObjectName("splash")
        self.setFixedSize(460, 340)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"#splash {{ background:{p['bg']}; border:1px solid {p['border']}; border-radius:14px; }}"
            f"QLabel {{ background:transparent; color:{p['text']}; }}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 24)
        lay.setSpacing(6)
        lay.setAlignment(Qt.AlignCenter)

        logo = QLabel(alignment=Qt.AlignCenter)
        pm = QPixmap(str(app_dir() / "assets" / "logo.png"))
        if not pm.isNull():
            logo.setPixmap(pm.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(logo)

        title = QLabel("CPP-KUB", alignment=Qt.AlignCenter)
        title.setStyleSheet(f"font-size:30px; font-weight:700; color:{p['accent']};")
        lay.addWidget(title)

        sub = QLabel("โปรแกรมเขียน C++ สำหรับการเรียนการสอน", alignment=Qt.AlignCenter)
        sub.setStyleSheet(f"font-size:13px; color:{p['muted']};")
        lay.addWidget(sub)

        lay.addSpacing(14)
        by = QLabel("By Cerebrega.com  ·  www.cerebrega.com", alignment=Qt.AlignCenter)
        by.setStyleSheet(f"font-size:12px; color:{p['muted']};")
        lay.addWidget(by)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(FADE_MS)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self._done)
        self._closing = False

    def start(self) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())
        self.show()
        QTimer.singleShot(SHOW_MS - FADE_MS, self.dismiss)

    def dismiss(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._fade.start()

    def mousePressEvent(self, event) -> None:  # คลิกเพื่อข้าม
        self.dismiss()

    def _done(self) -> None:
        self.close()
        self.finished.emit()
