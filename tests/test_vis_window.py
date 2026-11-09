"""ทดสอบการต่อ Visualizer เข้าหน้าต่างหลัก (offscreen) — ใช้ gdb ปลอมเมื่อไม่มี gdb จริง"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from app.visualizer import session as session_mod  # noqa: E402
from test_gui import needs_gpp, qapp, wait_until, win  # noqa: E402,F401
from test_vis_session import CRASH_SRC, LOOP_SRC, needs_gdb  # noqa: E402
from test_vis_session_fake import fake_gdb  # noqa: E402,F401


@pytest.fixture
def dwin(win):
    yield win
    win.debug_session.stop(quiet=True)


def set_code(w, src):
    w.editor.setPlainText(src)
    w.editor.document().setModified(False)


def console_text(w):
    return w.console.output.toPlainText()


def test_actions_exist_with_shortcuts(dwin):
    keys = {"a_debug": "F9", "a_step_over": "F10", "a_step_into": "F11",
            "a_step_out": "Shift+F11", "a_continue": "F8"}
    for name, key in keys.items():
        assert getattr(dwin, name).shortcut().toString() == key
    for name in ("a_step_over", "a_step_into", "a_step_out", "a_continue"):
        assert not getattr(dwin, name).isEnabled()
    assert dwin.a_debug.isEnabled()


def test_debug_menu_lists_actions(dwin):
    menus = {a.text(): a.menu() for a in dwin.menuBar().actions() if a.menu()}
    assert "ดีบัก" in menus
    assert [a.shortcut().toString() for a in menus["ดีบัก"].actions() if not a.isSeparator()][:5] == [
        "F9", "F10", "F11", "Shift+F11", "F8"]


def test_no_gdb_message(dwin, monkeypatch):
    monkeypatch.setattr(session_mod, "find_gdb", lambda: None)
    dwin.start_debug()
    assert "ไม่พบตัวดีบั๊ก" in console_text(dwin)
    assert dwin.visualizer.isHidden()
    assert dwin.a_run.isEnabled() and not dwin.editor.isReadOnly()
    assert dwin._debugging is False


@needs_gpp
def test_compile_error_no_panel(dwin, fake_gdb):
    set_code(dwin, "int main(){ x = 1; }\n")
    dwin.start_debug()
    assert wait_until(lambda: dwin.problems.count() > 0 and not dwin._debugging)
    assert dwin.visualizer.isHidden()
    assert dwin.debug_session.active is False
    assert dwin.a_run.isEnabled() and not dwin.editor.isReadOnly()


@needs_gpp
def test_debug_flow_with_fake_gdb(dwin, fake_gdb):
    set_code(dwin, LOOP_SRC)
    dwin.start_debug()
    assert wait_until(lambda: dwin.editor.debug_line == 3)
    assert not dwin.visualizer.isHidden()
    assert dwin.editor.isReadOnly()
    assert dwin.a_step_over.isEnabled() and not dwin.a_run.isEnabled()
    assert dwin.visualizer.variables.topLevelItemCount() > 0
    dwin.a_step_over.trigger()
    assert wait_until(lambda: dwin.editor.debug_line == 4)
    dwin.a_continue.trigger()
    assert wait_until(lambda: not dwin._debugging)
    assert not dwin.editor.isReadOnly() and dwin.editor.debug_line is None
    assert dwin.visualizer.isHidden()
    assert not dwin.a_step_over.isEnabled() and dwin.a_run.isEnabled()
    assert "ทำงานจบ" in console_text(dwin)


@needs_gpp
def test_stop_ends_debug_with_fake_gdb(dwin, fake_gdb):
    set_code(dwin, LOOP_SRC)
    dwin.start_debug()
    assert wait_until(lambda: dwin.editor.debug_line == 3)
    dwin.stop_run()
    assert wait_until(lambda: not dwin._debugging)
    assert not dwin.editor.isReadOnly() and dwin.visualizer.isHidden() and dwin.a_run.isEnabled()
    assert dwin.debug_session.active is False


@needs_gpp
def test_close_window_kills_session(dwin, fake_gdb):
    set_code(dwin, LOOP_SRC)
    dwin.start_debug()
    assert wait_until(lambda: dwin.editor.debug_line == 3)
    dwin.close()
    assert dwin.debug_session.active is False


@needs_gdb
def test_crash_makes_editor_writable(dwin):
    set_code(dwin, CRASH_SRC)
    dwin.start_debug()
    assert wait_until(lambda: dwin.editor.debug_line == 2)
    dwin.a_continue.trigger()
    assert wait_until(lambda: "หยุดทำงานผิดปกติ" in console_text(dwin))
    dwin.a_continue.trigger()
    assert wait_until(lambda: not dwin._debugging)
    assert not dwin.editor.isReadOnly()


@needs_gpp
def test_loop_badge_and_stack_follow_steps(dwin, fake_gdb):
    set_code(dwin, LOOP_SRC)
    dwin.start_debug()
    assert wait_until(lambda: dwin.editor.debug_line == 3)
    assert dwin.visualizer.loop_label.isHidden()
    assert dwin.visualizer.stack.count() == 1
    dwin.a_step_over.trigger()
    assert wait_until(lambda: dwin.editor.debug_line == 4)
    dwin.a_step_over.trigger()
    assert wait_until(lambda: dwin.editor.debug_line == 5)
    assert not dwin.visualizer.loop_label.isHidden()
    assert "รอบที่ 1" in dwin.visualizer.loop_label.text()


@needs_gpp
def test_clicking_stack_frame_moves_marker(dwin, fake_gdb):
    set_code(dwin, LOOP_SRC)
    dwin.start_debug()
    assert wait_until(lambda: dwin.editor.debug_line == 3)
    dwin.visualizer.frame_selected.emit(4)
    assert dwin.editor.debug_line == 4


def test_preset_input_is_passed_to_session(dwin, monkeypatch):
    calls = []
    monkeypatch.setattr(dwin.debug_session, "start", lambda src, preset="": calls.append((src, preset)))
    set_code(dwin, LOOP_SRC)
    dwin.console.set_preset("21\n", False)
    dwin.start_debug()
    assert calls == [(LOOP_SRC, "21\n")]
    dwin._end_debug()


@needs_gpp
def test_switching_tabs_keeps_session_and_marker(dwin, fake_gdb):
    set_code(dwin, LOOP_SRC)
    first = dwin.doc
    dwin.start_debug()
    assert wait_until(lambda: first.editor.debug_line == 3)
    dwin.new_file()                                       # สลับไปแท็บใหม่ระหว่างดีบัก
    assert dwin.doc is not first
    assert dwin.debug_session.active and dwin._debug_doc is first
    assert first.editor.isReadOnly() and not dwin.doc.editor.isReadOnly()
    dwin.a_step_over.trigger()                            # ก้าวต่อได้แม้ดูแท็บอื่นอยู่ → ลูกศรไปขยับที่แท็บที่ดีบักอยู่
    assert wait_until(lambda: first.editor.debug_line == 4)
    assert dwin.doc.editor.debug_line is None


def test_docs_mention_visualizer_and_gdb():
    root = Path(__file__).resolve().parent.parent
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "Visualizer" in readme and "gdb.exe" in readme and "F10" in readme and "app/visualizer/" in readme
    assert "gdb.exe" in (root / "build_windows.bat").read_text(encoding="utf-8", errors="replace")


def test_runner_problem_during_debug_ends_debug(dwin, fake_gdb, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from app import compiler
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(compiler, "find_compiler", lambda: None)      # Runner.start → problem()
    dwin.start_debug()
    assert dwin._debugging is False
    assert not dwin.editor.isReadOnly() and dwin.a_run.isEnabled() and dwin.a_debug.isEnabled()
    assert dwin.debug_session.active is False


def test_step_error_is_reported_and_actions_refreshed(dwin):
    dwin.debug_session.step_error.emit("Cannot finish")
    assert "Cannot finish" in console_text(dwin)


# ---------- UI สำหรับสอนในห้องเรียน ----------
def test_toolbar_is_simple_and_steps_live_in_panel(dwin):
    shown = set(dwin.toolbar.actions())
    assert {dwin.a_run, dwin.a_stop, dwin.a_debug, dwin.a_present} <= shown
    for a in (dwin.a_step_over, dwin.a_step_into, dwin.a_step_out, dwin.a_continue, dwin.a_print):
        assert a not in shown
    v = dwin.visualizer
    assert not v.btn_over.isEnabled() and not v.btn_into.isEnabled() and not v.btn_out.isEnabled()
    assert v.btn_stop.isEnabled() and v.btn_restart.isEnabled()


def test_presentation_mode_hides_chrome_and_restores_font(dwin):
    before = dwin._font_size
    dwin.show()
    dwin.a_present.trigger()
    assert dwin._presenting and dwin.menuBar().isHidden() and dwin.statusBar().isHidden()
    assert dwin.explorer_card.isHidden()
    assert dwin._font_size == before + dwin.PRESENT_BOOST
    dwin.a_present.trigger()
    assert not dwin._presenting and not dwin.menuBar().isHidden() and not dwin.statusBar().isHidden()
    assert dwin._font_size == before
    assert dwin.settings.value("font_size", before, type=int) in (before,)   # ไม่ถูกบันทึกค่าชั่วคราว


@needs_gpp
def test_step_counter_explanation_and_restart(dwin, fake_gdb):
    set_code(dwin, LOOP_SRC)
    dwin.start_debug()
    assert wait_until(lambda: dwin.editor.debug_line == 3)
    v = dwin.visualizer
    assert v.step_label.text() == "ขั้นที่ 1"
    assert v.btn_over.isEnabled() and not v.explain_label.isHidden()
    v.btn_over.click()
    assert wait_until(lambda: dwin.editor.debug_line == 4)
    assert v.step_label.text() == "ขั้นที่ 2"
    dwin.restart_debug()
    assert wait_until(lambda: dwin._debugging and dwin.editor.debug_line == 3 and v.step_label.text() == "ขั้นที่ 1")
