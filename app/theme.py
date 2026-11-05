"""ชุดสีกลางของโปรแกรม (ธีมสว่าง/มืด) และ Qt stylesheet ที่สร้างจากชุดสีนั้น

แยกส่วนต่าง ๆ ด้วยระดับสีพื้นแทนเส้นขอบ: panel (พื้นหน้าต่าง) → bg (การ์ด) → tab_active (ส่วนที่ยกขึ้น/ถูกเลือก)
"""
from __future__ import annotations

_LIGHT = dict(
    bg="#ffffff", panel="#eef0f6", sidebar="#fafbfd", border="#e3e6ee",
    text="#1a1d29", muted="#6a7083", accent="#5468ff", accent_text="#ffffff",
    hover="#f1f3f9", tab_active="#e8ebff", tab_inactive="#ffffff",
    danger="#dc2626", warn="#b45309", ok="#16a34a",
    run="#16a34a", run_hover="#15803d", run_text="#ffffff", scroll="#c9ced8",
    gutter_text="#a0a7b4", line_hl="#f5f7fb", echo="#7c3aed",
    kw="#8839ef", ty="#b45309", fn="#1e66f5", num="#d9480f", st="#2f8a1e", cm="#8c8fa1", pp="#c2185b",
    debug_line="#fff3b0", changed="#ffe9a8",
)
_DARK = dict(
    bg="#151823", panel="#0c0e15", sidebar="#121520", border="#242938",
    text="#e6e8f0", muted="#8b92a8", accent="#7b8cff", accent_text="#0c0e15",
    hover="#1d2130", tab_active="#262c46", tab_inactive="#151823",
    danger="#f87171", warn="#fbbf24", ok="#4ade80",
    run="#2fb36a", run_hover="#3cc87b", run_text="#07140d", scroll="#363c52",
    gutter_text="#4b515c", line_hl="#1a1e2c", echo="#c4b5fd",
    kw="#cba6f7", ty="#f9e2af", fn="#89b4fa", num="#fab387", st="#a6e3a1", cm="#7f849c", pp="#f5c2e7",
    debug_line="#4a4220", changed="#5a4a12",
)


def palette(dark: bool) -> dict[str, str]:
    return dict(_DARK if dark else _LIGHT)


def build_qss(dark: bool) -> str:
    from . import icons
    p = palette(dark)
    p["accent_sel"] = p["text"] if dark else p["accent"]
    p["close_icon"], p["close_icon_hover"] = icons.close_icon_files(p["muted"], p["text"])
    return """
QWidget {{ background:{bg}; color:{text}; font-family:"Segoe UI Variable Text","Segoe UI","Leelawadee UI","Tahoma","Noto Sans Thai"; }}
QMainWindow, QStatusBar, QSplitter#ShellSplit, #Shell, #ActivityBar {{ background:{panel}; }}

/* ---------- เมนู + แถบเครื่องมือ (กลืนกับพื้นหน้าต่าง ไม่มีเส้นขอบ) ---------- */
QMenuBar {{ background:transparent; border:0; padding:3px 6px 0 6px; }}
QMenuBar::item {{ padding:5px 10px; border-radius:6px; background:transparent; color:{muted}; }}
QMenuBar::item:selected, QMenuBar::item:pressed {{ background:{hover}; color:{text}; }}
QMenu {{ background:{bg}; border:1px solid {border}; border-radius:12px; padding:6px; }}
QMenu::item {{ padding:7px 28px 7px 14px; border-radius:6px; background:transparent; }}
QMenu::item:selected {{ background:{tab_active}; color:{text}; }}
QMenu::item:disabled {{ color:{muted}; }}
QMenu::separator {{ height:1px; background:{border}; margin:5px 8px; }}
QMenu::indicator {{ width:14px; height:14px; margin-left:4px; }}
QToolBar {{ background:transparent; border:0; spacing:4px; padding:4px 8px 6px 8px; }}
QToolBar::separator {{ width:1px; background:{border}; margin:6px 6px; }}
QToolButton {{ background:transparent; border:0; border-radius:7px; padding:5px 10px; color:{text}; }}
QToolButton:hover {{ background:{hover}; }}
QToolButton:pressed {{ background:{border}; }}
QToolButton:checked {{ background:{tab_active}; }}
QToolButton:disabled {{ color:{muted}; }}
QToolButton#RunButton {{ background:{run}; color:{run_text}; font-weight:600; padding:6px 18px; border-radius:15px; }}
QToolButton#RunButton:hover {{ background:{run_hover}; }}
QToolButton#RunButton:disabled {{ background:{hover}; color:{muted}; }}
QToolButton#StopButton:enabled {{ color:{danger}; }}
QToolButton#StopButton:enabled:hover {{ background:{hover}; }}

/* ---------- การ์ด (Explorer / โค้ด / แผงล่าง) ---------- */
#Card, #VisualizerPanel {{ background:{bg}; border:1px solid {border}; border-radius:14px; }}
#VisualizerPanel > QLabel {{ background:transparent; padding:8px 10px 4px 10px; color:{muted}; }}
QSplitter::handle {{ background:{border}; }}
QSplitter#ShellSplit::handle {{ background:transparent; }}
QSplitter#ShellSplit::handle:hover {{ background:{tab_active}; border-radius:3px; }}
QHeaderView::section {{ background:{bg}; color:{muted}; border:0; border-bottom:1px solid {border}; padding:5px 8px; }}

/* ---------- ช่องข้อความ ---------- */
QPlainTextEdit, QListWidget, QTreeWidget {{ background:{bg}; border:0;
    selection-background-color:{accent}; selection-color:{accent_text}; }}
QLineEdit, QComboBox {{ background:{panel}; border:1px solid {border}; border-radius:8px; padding:6px 10px;
    selection-background-color:{accent}; selection-color:{accent_text}; }}
QLineEdit:focus, QComboBox:focus {{ border:1px solid {accent}; background:{bg}; }}
QComboBox::drop-down {{ border:0; width:22px; }}
QComboBox QAbstractItemView {{ background:{bg}; border:1px solid {border}; border-radius:8px; padding:4px; outline:0;
    selection-background-color:{tab_active}; selection-color:{text}; }}
QLineEdit:disabled {{ color:{muted}; }}
QTreeWidget::item, QListWidget::item {{ padding:5px 6px; border-radius:6px; }}
QTreeWidget::item:hover, QListWidget::item:hover {{ background:{hover}; }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background:{tab_active}; color:{text}; }}
QTreeWidget::branch {{ background:transparent; }}

/* ---------- ปุ่ม ---------- */
QPushButton {{ background:{bg}; border:1px solid {border}; padding:6px 14px; border-radius:8px; }}
QPushButton:hover {{ background:{hover}; }}
QPushButton:pressed {{ background:{border}; }}
QPushButton:focus {{ border-color:{accent}; }}
QPushButton:checked {{ background:{tab_active}; color:{accent}; border-color:{accent}; }}
QPushButton:disabled {{ color:{muted}; }}
QPushButton#SendButton {{ background:{accent}; color:{accent_text}; border-color:{accent}; font-weight:600; border-radius:16px; padding:6px 18px; }}
QPushButton#SendButton:disabled {{ background:{hover}; color:{muted}; border-color:{border}; }}
QPushButton#GhostButton {{ background:transparent; border:1px dashed {border}; color:{muted}; }}
QPushButton#GhostButton:hover {{ color:{text}; border-color:{accent}; background:{hover}; }}

/* ---------- แท็บ: ไฟล์ = ทรงเม็ดยา, แผงล่าง = ขีดเส้นใต้ ---------- */
QTabWidget::pane {{ border:0; }}
QTabBar {{ background:transparent; qproperty-drawBase:0; }}
QTabBar::tab {{ background:transparent; color:{muted}; }}
#DocTabs QTabBar::tab {{ padding:6px 10px 6px 12px; margin:6px 2px 4px 2px; border-radius:14px; }}
#DocTabs QTabBar::tab:first {{ margin-left:6px; }}
#DocTabs QTabBar::tab:selected {{ background:{tab_active}; color:{accent_sel}; font-weight:600; }}
#DocTabs QTabBar::tab:hover:!selected {{ background:{hover}; color:{text}; }}
#PanelTabs QTabBar::tab {{ padding:9px 4px 7px 4px; margin:0 10px; border-bottom:2px solid transparent; }}
#PanelTabs QTabBar::tab:selected {{ color:{text}; border-bottom-color:{accent}; }}
#PanelTabs QTabBar::tab:hover:!selected {{ color:{text}; }}
#PanelTabs::pane {{ border-top:1px solid {border}; }}
QTabBar::close-button {{ image:url({close_icon}); subcontrol-position:right; border-radius:4px; margin:0 2px; }}
QTabBar::close-button:hover {{ image:url({close_icon_hover}); background:{border}; }}

/* ---------- แถบสถานะ ---------- */
QStatusBar {{ border:0; color:{muted}; }}
QStatusBar::item {{ border:0; }}
QStatusBar QLabel {{ background:transparent; color:{muted}; padding:0 8px; }}

/* ---------- Toast ---------- */
#Toast {{ background:{bg}; border:1px solid {border}; border-left:4px solid {accent}; border-radius:12px; }}
#Toast[kind="ok"] {{ border-left-color:{ok}; }}
#Toast[kind="warn"] {{ border-left-color:{warn}; }}
#Toast[kind="error"] {{ border-left-color:{danger}; }}
#Toast QLabel {{ background:transparent; }}
#ToastIcon {{ color:{accent}; font-weight:700; }}
#Toast[kind="ok"] #ToastIcon {{ color:{ok}; }}
#Toast[kind="warn"] #ToastIcon {{ color:{warn}; }}
#Toast[kind="error"] #ToastIcon {{ color:{danger}; }}

/* ---------- อื่น ๆ ---------- */
QScrollBar:vertical {{ background:transparent; width:12px; margin:2px 3px; }}
QScrollBar:horizontal {{ background:transparent; height:12px; margin:3px 2px; }}
QScrollBar::handle {{ background:{scroll}; border-radius:3px; min-height:28px; min-width:28px; }}
QScrollBar::handle:hover {{ background:{muted}; }}
QPlainTextEdit {{ padding:2px; }}
QPushButton:focus, QLineEdit:focus {{ outline:0; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width:0; height:0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}
QToolTip {{ background:{bg}; color:{text}; border:1px solid {border}; border-radius:8px; padding:6px 10px; }}
#Explorer {{ background:{sidebar}; }}
QStatusBar {{ padding:2px 6px 4px 6px; }}
""".format(**p)
