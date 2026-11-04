"""ชุดสีกลางของโปรแกรม (ธีมสว่าง/มืด) และ Qt stylesheet ที่สร้างจากชุดสีนั้น"""
from __future__ import annotations

_LIGHT = dict(
    bg="#ffffff", panel="#f6f8fa", sidebar="#f0f3f6", border="#d0d7de",
    text="#1f2328", muted="#656d76", accent="#0969da", accent_text="#ffffff",
    hover="#e6ebf1", tab_active="#ffffff", tab_inactive="#eaeef2",
    danger="#cf222e", warn="#9a6700", ok="#1a7f37",
)
_DARK = dict(
    bg="#0d1117", panel="#161b22", sidebar="#11161d", border="#30363d",
    text="#e6edf3", muted="#8b949e", accent="#1f6feb", accent_text="#ffffff",
    hover="#21262d", tab_active="#0d1117", tab_inactive="#161b22",
    danger="#ff7b72", warn="#e3b341", ok="#56d364",
)


def palette(dark: bool) -> dict[str, str]:
    return dict(_DARK if dark else _LIGHT)


def build_qss(dark: bool) -> str:
    p = palette(dark)
    return """
QWidget {{ background:{bg}; color:{text}; }}
QMainWindow, QMenuBar, QMenu, QToolBar, QStatusBar {{ background:{panel}; }}
QToolBar {{ border:0; border-bottom:1px solid {border}; spacing:4px; padding:2px 6px; }}
QToolButton {{ background:transparent; border:1px solid transparent; border-radius:5px; padding:4px 8px; }}
QToolButton:hover {{ background:{hover}; border-color:{border}; }}
QToolButton:checked {{ background:{hover}; border-left:2px solid {accent}; }}
QToolButton:disabled {{ color:{muted}; }}
QMenuBar::item:selected, QMenu::item:selected {{ background:{accent}; color:{accent_text}; }}
QMenu {{ border:1px solid {border}; }}
QStatusBar {{ border-top:1px solid {border}; color:{muted}; }}
QStatusBar QLabel {{ background:transparent; padding:0 8px; }}
QPlainTextEdit, QLineEdit, QListWidget, QTreeWidget, QComboBox {{
    background:{bg}; border:1px solid {border}; selection-background-color:{accent};
    selection-color:{accent_text}; }}
QTreeWidget, QListWidget {{ border:0; }}
QTreeWidget::item, QListWidget::item {{ padding:3px 2px; }}
QTreeWidget::item:hover, QListWidget::item:hover {{ background:{hover}; }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background:{accent}; color:{accent_text}; }}
QPushButton {{ background:{hover}; border:1px solid {border}; padding:4px 10px; border-radius:5px; }}
QPushButton:hover {{ background:{accent}; color:{accent_text}; border-color:{accent}; }}
QPushButton:checked {{ background:{accent}; color:{accent_text}; }}
QPushButton:disabled {{ color:{muted}; }}
QTabWidget::pane {{ border:0; border-top:1px solid {border}; }}
QTabBar::tab {{ background:{tab_inactive}; color:{muted}; padding:7px 14px;
    border-right:1px solid {border}; border-top:2px solid transparent; }}
QTabBar::tab:selected {{ background:{tab_active}; color:{text}; border-top:2px solid {accent}; }}
QTabBar::tab:hover:!selected {{ background:{hover}; }}
QTabBar::close-button {{ subcontrol-position:right; border-radius:3px; }}
QTabBar::close-button:hover {{ background:{border}; }}
QSplitter::handle {{ background:{border}; }}
QSplitter::handle:horizontal {{ width:1px; }}
QSplitter::handle:vertical {{ height:1px; }}
QScrollBar:vertical {{ background:{bg}; width:12px; margin:0; }}
QScrollBar:horizontal {{ background:{bg}; height:12px; margin:0; }}
QScrollBar::handle {{ background:{border}; border-radius:5px; min-height:24px; min-width:24px; }}
QScrollBar::handle:hover {{ background:{muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width:0; height:0; }}
QToolTip {{ background:{panel}; color:{text}; border:1px solid {border}; padding:3px; }}
#ActivityBar {{ background:{sidebar}; border-right:1px solid {border}; }}
#Explorer {{ background:{sidebar}; }}
""".format(**p)
