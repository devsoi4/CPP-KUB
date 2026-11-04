"""ทดสอบตัวตรวจจับ loop และตัวนับรอบ (Python ล้วน ไม่ต้องมี Qt/gdb)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.visualizer.loops import LoopInfo, LoopStatus, LoopTracker, find_loops  # noqa: E402

LOOP_SRC = """#include <iostream>
int main() {
    int a[3] = {10, 20, 30};
    int sum = 0;
    for (int i = 0; i < 3; i++) {
        sum += a[i];
    }
    std::cout << sum << "\\n";
    return 0;
}
"""


def test_find_for_loop_with_var_and_range():
    assert find_loops(LOOP_SRC) == {5: LoopInfo(5, 7, "for", "i")}


def test_for_without_declaration_and_range_for():
    src = "int main() {\n  int i;\n  for (i = 0; i < 3; i++) {\n  }\n  for (auto x : v) {\n  }\n}\n"
    loops = find_loops(src)
    assert loops[3].var == "i" and loops[5].var == "x"


def test_while_multiline_and_do_while():
    src = ("int main() {\n"        # 1
           "  int x = 3;\n"        # 2
           "  while (x > 0)\n"     # 3
           "  {\n"                 # 4
           "    x--;\n"            # 5
           "  }\n"                 # 6
           "  do {\n"              # 7
           "    x++;\n"            # 8
           "  } while (x < 3);\n"  # 9
           "}\n")
    loops = find_loops(src)
    assert loops[3] == LoopInfo(3, 6, "while", None)
    assert loops[7] == LoopInfo(7, 9, "do", None)
    assert 9 not in loops                       # while ของ do-while ไม่ใช่หัว loop ใหม่


def test_braceless_loop_ends_at_statement():
    src = "int main() {\n  for (int i = 0; i < 3; i++) sum += i;\n}\n"
    assert find_loops(src)[2] == LoopInfo(2, 2, "for", "i")
    src2 = "int main() {\n  for (int i = 0; i < 3; i++)\n    sum += i;\n}\n"
    assert find_loops(src2)[2].end_line == 3


def test_comments_and_strings_are_ignored():
    src = ('int main() {\n'
           '  // for (int i = 0;;) {\n'
           '  /* while (x) { */\n'
           '  const char* s = "for (x) {";\n'
           '}\n')
    assert find_loops(src) == {}


def test_nested_loops_ranges():
    src = ("int main() {\n"                       # 1
           "  for (int i = 0; i < 2; i++) {\n"     # 2
           "    for (int j = 0; j < 2; j++) {\n"   # 3
           "      f(i, j);\n"                      # 4
           "    }\n"                               # 5
           "  }\n"                                 # 6
           "}\n")
    loops = find_loops(src)
    assert (loops[2].end_line, loops[3].end_line) == (6, 5)
    assert loops[3].var == "j"


def _iters(tracker, depth, line):
    return [(s.line, s.iteration) for s in tracker.update(depth, line)]


def test_tracker_counts_header_visits_then_clears_on_exit():
    t = LoopTracker(find_loops(LOOP_SRC))
    seen = [_iters(t, 1, ln) for ln in (3, 4, 5, 6, 5, 6, 5, 6, 5)]
    assert seen[2] == [(5, 1)] and seen[3] == [(5, 1)]
    assert seen[4] == [(5, 2)] and seen[6] == [(5, 3)] and seen[8] == [(5, 4)]
    assert t.update(1, 8) == []
    assert _iters(t, 1, 5) == [(5, 1)]                      # เข้า loop ใหม่เริ่มที่ 1


def test_tracker_status_fields():
    t = LoopTracker(find_loops(LOOP_SRC))
    assert t.update(1, 5) == [LoopStatus(5, "for", "i", 1)]


def test_tracker_nested_inner_restarts_each_outer_iteration():
    src = ("int main() {\n"
           "  for (int i = 0; i < 2; i++) {\n"
           "    for (int j = 0; j < 2; j++) {\n"
           "      f(i, j);\n"
           "    }\n"
           "  }\n"
           "}\n")
    t = LoopTracker(find_loops(src))
    assert _iters(t, 1, 2) == [(2, 1)]
    assert _iters(t, 1, 3) == [(2, 1), (3, 1)]
    assert _iters(t, 1, 4) == [(2, 1), (3, 1)]
    assert _iters(t, 1, 3) == [(2, 1), (3, 2)]
    assert _iters(t, 1, 2) == [(2, 2)]                      # วนกลับหัว loop นอก → loop ในถูกล้าง
    assert _iters(t, 1, 3) == [(2, 2), (3, 1)]


def test_tracker_callee_depth_does_not_advance_caller_loop():
    t = LoopTracker(find_loops(LOOP_SRC))
    t.update(1, 5)
    assert t.update(2, 5) == [LoopStatus(5, "for", "i", 1)]       # บรรทัดเดียวกันแต่เป็นเฟรมลึกกว่า = loop ใหม่ของเฟรมนั้น
    assert t.update(1, 6) == [LoopStatus(5, "for", "i", 1)]       # กลับมาเฟรมเดิม ค่ารอบเดิมไม่เพิ่ม
    assert t.update(1, 5) == [LoopStatus(5, "for", "i", 2)]


def test_do_while_counts_condition_visits():
    src = "int main() {\n  do {\n    x++;\n  } while (x < 3);\n}\n"
    t = LoopTracker(find_loops(src))
    assert _iters(t, 1, 2) == [(2, 1)]
    assert _iters(t, 1, 3) == [(2, 1)]
    assert _iters(t, 1, 4) == [(2, 2)]            # ถึงเงื่อนไข while ท้าย = เริ่มรอบถัดไป
    assert _iters(t, 1, 3) == [(2, 2)]


def test_reset_clears_state():
    t = LoopTracker(find_loops(LOOP_SRC))
    t.update(1, 5)
    t.reset()
    assert t.update(1, 5) == [LoopStatus(5, "for", "i", 1)]
