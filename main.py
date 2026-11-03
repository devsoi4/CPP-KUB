"""CppLearn — โปรแกรมเขียน C++ สำหรับการสอน (รองรับภาษาไทย)

รันด้วย:  python main.py
"""
import sys

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow

# ฟอนต์ส่วนติดต่อผู้ใช้: เลือกตัวแรกที่มีในเครื่องและแสดงภาษาไทยได้ดี
UI_FONTS = ["Leelawadee UI", "Tahoma", "Noto Sans Thai", "Sarabun", "TH Sarabun New", "Segoe UI"]


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("CppLearn")
    available = set(QFontDatabase.families())
    for name in UI_FONTS:
        if name in available:
            app.setFont(QFont(name, 11))
            break
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
