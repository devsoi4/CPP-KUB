"""ชุดสีกลางของโปรแกรม (ธีมสว่าง/มืด) และ Qt stylesheet ที่สร้างจากชุดสีนั้น

แยกส่วนต่าง ๆ ด้วยระดับสีพื้นแทนเส้นขอบ: panel (พื้นหน้าต่าง) → bg (การ์ด) → tab_active (ส่วนที่ยกขึ้น/ถูกเลือก)
"""
from __future__ import annotations

import re

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


# ---------- สีของภาพ Visualizer (โหมดสอน): สีตามชนิดข้อมูล / ตาม stack frame / ตามเป้าหมายของ pointer ----------
# หมวดชนิด → (สีพื้นกล่อง, สีขอบ)
TYPE_LABELS = {"int": "int", "float": "float", "char": "char", "bool": "bool", "pointer": "pointer", "heap": "heap"}
_TYPES_LIGHT = {
    "int": ("#dbeafe", "#2563eb"), "float": ("#d1fae5", "#059669"), "char": ("#ffedd5", "#ea580c"),
    "bool": ("#ede9fe", "#7c3aed"), "pointer": ("#fce7f3", "#db2777"), "heap": ("#fff1e0", "#c2410c"),
    "array": ("#fef9c3", "#ca8a04"),
}
_TYPES_DARK = {
    "int": ("#1e3a5f", "#60a5fa"), "float": ("#0f3d33", "#34d399"), "char": ("#4a2a10", "#fb923c"),
    "bool": ("#35255e", "#a78bfa"), "pointer": ("#4a1d3a", "#f472b6"), "heap": ("#4a2410", "#fb923c"),
    "array": ("#453a0e", "#facc15"),
}
# สีประจำ stack frame (วนตามความลึก นับจาก main = 0)
_FRAMES_LIGHT = ["#4f46e5", "#0d9488", "#c026d3", "#ea580c", "#0284c7", "#65a30d"]
_FRAMES_DARK = ["#818cf8", "#2dd4bf", "#e879f9", "#fb923c", "#38bdf8", "#a3e635"]
# ลูกศร pointer: ชี้ตัวแปรใน stack / ชี้ heap
_ARROWS_LIGHT = {"stack": "#2563eb", "heap": "#ea580c"}
_ARROWS_DARK = {"stack": "#60a5fa", "heap": "#fb923c"}
# ค่าที่เพิ่งเปลี่ยน: (พื้น, ขอบ/เรือง)
_CHANGED_LIGHT = ("#fde047", "#d97706")
_CHANGED_DARK = ("#854d0e", "#fde047")

_RE_CHAR_VAL = re.compile(r"^-?\d+ '")
_RE_INT_VAL = re.compile(r"^-?\d+$")
_RE_FLOAT_VAL = re.compile(r"^-?(\d+\.\d*|\.\d+|\d+(\.\d*)?[eE][-+]?\d+|inf|nan\(.*\)|-?nan.*)$")
_INT_WORDS = ("long", "short", "unsigned", "signed", "size_t", "ptrdiff_t")


def type_category(type_str: str, value: str = "", kind: str = "scalar") -> str:
    """จัดชนิดข้อมูลเป็นหมวดสี: int|float|char|bool|pointer|other (สมาชิก struct ไม่มีชนิด → เดาจากรูปค่า)"""
    if kind == "pointer":
        return "pointer"
    t = type_str.replace("const", "").replace("volatile", "").strip().lower()
    if t:
        if t == "bool":
            return "bool"
        words = re.findall(r"[a-z_][a-z_0-9]*", t)          # เทียบทีละคำ กัน "Point" ไปติดคำว่า int
        if any(w in ("string", "char", "wchar_t") or w.startswith("char") for w in words):
            return "char"
        if any(w in ("float", "double") for w in words):
            return "float"
        if any(w in _INT_WORDS or re.fullmatch(r"u?int\d*(_t)?", w) for w in words):
            return "int"
        return "other"
    v = value.strip()
    if v in ("true", "false"):
        return "bool"
    if v.startswith(("'", '"')) or _RE_CHAR_VAL.match(v):
        return "char"
    if _RE_INT_VAL.match(v):
        return "int"
    if _RE_FLOAT_VAL.match(v):
        return "float"
    return "other"


def type_colors(dark: bool, category: str) -> tuple[str, str] | None:
    """(สีพื้น, สีขอบ) ของหมวดชนิด; None = ไม่มีสีเฉพาะ (ให้ใช้สี panel/border ปกติ)"""
    return (_TYPES_DARK if dark else _TYPES_LIGHT).get(category)


def frame_color(dark: bool, depth: int) -> str:
    colors = _FRAMES_DARK if dark else _FRAMES_LIGHT
    return colors[depth % len(colors)]


def arrow_color(dark: bool, heap: bool) -> str:
    return (_ARROWS_DARK if dark else _ARROWS_LIGHT)["heap" if heap else "stack"]


def changed_colors(dark: bool) -> tuple[str, str]:
    return _CHANGED_DARK if dark else _CHANGED_LIGHT


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
