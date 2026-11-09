"""CPP-KUB — โปรแกรมเขียน C++ สำหรับการสอน (รองรับภาษาไทย)

รันด้วย:  python main.py
"""
import sys

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from app.compiler import app_dir
from app.main_window import MainWindow
from app.splash import SplashScreen

# ฟอนต์ส่วนติดต่อผู้ใช้: เลือกตัวแรกที่มีในเครื่องและแสดงภาษาไทยได้ดี
UI_FONTS = ["Leelawadee UI", "Tahoma", "Noto Sans Thai", "Sarabun", "TH Sarabun New", "Segoe UI"]


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("CPP-KUB")
    app.setWindowIcon(QIcon(str(app_dir() / "assets" / "icon.png")))  # ไอคอนที่ title bar / taskbar
    available = set(QFontDatabase.families())
    for name in UI_FONTS:
        if name in available:
            app.setFont(QFont(name, 11))
            break
    dark = QSettings("CPP-KUB", "CPP-KUB").value("dark", False, type=bool)
    window = MainWindow()
    splash = SplashScreen(dark)
    splash.finished.connect(window.show)  # แสดงหน้าต่างหลักเมื่อ splash หาย
    splash.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
