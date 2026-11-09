"""ทดสอบธีม (ชุดสีกลาง) และไอคอน SVG"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import icons, theme  # noqa: E402

NAMES = ["explorer", "run", "stop", "save", "print", "folder", "file", "example"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_palettes_have_same_keys():
    light, dark = theme.palette(False), theme.palette(True)
    assert set(light) == set(dark)
    assert all(v.startswith("#") for v in (*light.values(), *dark.values()))


def test_qss_uses_palette_colors():
    assert theme.palette(True)["bg"] in theme.build_qss(True)
    assert theme.palette(False)["bg"] in theme.build_qss(False)
    assert theme.build_qss(True) != theme.build_qss(False)


@pytest.mark.parametrize("name", NAMES)
def test_icons_render_for_all_names(qapp, name):
    img = icons.icon(name, "#ffffff").pixmap(20, 20).toImage()
    assert any(img.pixelColor(x, y).alpha() > 0 for x in range(20) for y in range(20))


def test_icon_color_is_applied(qapp):
    img = icons.icon("stop", "#ff0000").pixmap(20, 20).toImage()
    c = img.pixelColor(10, 10)
    assert c.alpha() > 0 and c.red() > 200 and c.blue() < 60


def test_unknown_icon_raises(qapp):
    with pytest.raises(KeyError):
        icons.icon("nope", "#fff")


@pytest.mark.parametrize("dark", [False, True])
def test_close_button_icons_are_in_stylesheet_and_exist(qapp, dark):
    import re
    qss = theme.build_qss(dark)
    urls = re.findall(r"QTabBar::close-button[^{]*\{[^}]*image:\s*url\(([^)]+)\)", qss)
    assert len(urls) == 2                         # ปกติ + ตอนเอาเมาส์ชี้
    for u in urls:
        assert Path(u).is_file() and Path(u).stat().st_size > 0


def test_type_category_from_type_and_value():
    cat = theme.type_category
    assert cat("int", "5") == "int" and cat("unsigned long", "5") == "int"
    assert cat("double", "1.5") == "float" and cat("char", "97 'a'") == "char"
    assert cat("bool", "true") == "bool" and cat("std::string", '"x"') == "char"
    assert cat("int *", "0x1", "pointer") == "pointer"
    assert cat("Point", "{...}") == "other"
    # สมาชิก struct ไม่มีชนิด → เดาจากค่า
    assert cat("", "42") == "int" and cat("", "3.14") == "float"
    assert cat("", "97 'a'") == "char" and cat("", "true") == "bool"


def test_teaching_colors_exist_for_both_themes():
    for dark in (False, True):
        for c in ("int", "float", "char", "bool", "pointer", "heap", "array"):
            fill, edge = theme.type_colors(dark, c)
            assert fill.startswith("#") and edge.startswith("#") and fill != edge
        assert theme.type_colors(dark, "other") is None
        assert theme.frame_color(dark, 0) != theme.frame_color(dark, 1)
        assert theme.arrow_color(dark, True) != theme.arrow_color(dark, False)
