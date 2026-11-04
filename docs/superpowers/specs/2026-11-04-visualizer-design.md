# Visualizer (step debugger + memory diagrams) — Design

Date: 2026-11-04

## Goal
A classroom teaching aid: the teacher projects it, students use it. Pointers, recursion and
loops are where students get stuck, so the program's execution is shown as pictures, not just
run. Must keep: Thai UI, fully offline, existing tabs/Explorer/run flow and tests unchanged.

## Capabilities
1. Step through the active tab's code line by line; variable values update live.
2. Memory view: arrays as boxes (with index), pointers as arrows to the variable / element they
   point at, structs as grouped boxes.
3. Call stack panel (essential for recursion): one frame per call with its arguments and locals.
4. Loop indicator: which iteration (รอบที่ N) and the current value of the loop variable.

Non-goals (v1): interactive `cin` while debugging (preset input only), STL containers beyond
`std::string`/`std::vector<int>` shown as plain values, multi-threaded programs, breakpoints
set by clicking the gutter, reverse stepping, auto-play.

## Engine: gdb via GDB/MI
- `gdb.exe` is looked up in `compiler\bin` first, then PATH (same rule as g++). If missing, the
  Debug action shows a Thai message explaining that gdb must be added to `compiler\bin`.
  `build_windows.bat`/README note that the full WinLibs zip includes gdb.
- The program is compiled by the existing `Runner` compile step (already `-g`, no `-O`; the
  debug build forces `-O0`). The existing Thai error translation applies if compile fails.
- `DebugSession` (QObject, QProcess running `gdb --interpreter=mi3 -q`) exposes signals:
  `stopped(Snapshot)`, `output(str)`, `finished(code, reason)`, `failed(msg)`.
  Commands: start (break at `main`, run), `next`, `step`, `finish`, `continue`, `stop`.
- Stepping into non-user code (STL, libc) is avoided: after a `step` that lands outside the
  user's source file, the session issues `finish` and stops back in user code.
- stdin comes from the tab's preset input (`run < file`); stdout/stderr go to a temp file
  that is tailed into the Output panel after each stop. (Risk: Windows gdb redirection —
  verified by the first task of the plan; fallback is `set new-console off` + pipes.)
- Crashes (SIGSEGV, etc.) stop at the faulting line and reuse `describe_exit` Thai text.
- Safety: a runaway `continue` is killed by the existing 15 s idle rule; step count capped
  (e.g. 100 000) with a Thai message.

## Units (new package `app/visualizer/`)
| File | Purpose | Depends on |
|---|---|---|
| `gdbmi.py` | Pure parser for MI records (`^done`, `*stopped`, tuples/lists/c-strings) | — |
| `model.py` | Dataclasses `Snapshot`, `Frame`, `Var` (name, type, value, address, kind: scalar/array/pointer/struct, children); builds a Snapshot from parsed MI | gdbmi |
| `session.py` | `DebugSession`: drives gdb, collects a `Snapshot` after every stop | gdbmi, model, compiler helpers |
| `loops.py` | Pure: finds `for`/`while`/`do` headers in source; counts iterations per frame as the current line revisits a header; extracts the loop variable name | — |
| `memory_view.py` | `QGraphicsView` drawing Snapshot as boxes + arrows (pointer value matched to variable/element addresses; unknown address shown as "→ heap 0x…" with `*p` value when pointer to scalar) | model, theme |
| `panel.py` | Right-hand dock: tabs/sections "ตัวแปร" (table), "หน่วยความจำ" (diagram), "Call stack", plus loop badge | memory_view, loops |

Each unit is testable alone: `gdbmi`, `model`, `loops` are pure Python (no Qt, no gdb).

## UI
- Right-hand dock "ตัวช่วยมองเห็น" beside the editor, hidden until a debug session starts,
  closed on stop. Bottom panel stays for output.
- Actions (menu "ดีบัก" + toolbar icons): เริ่มดีบัก (F9), บรรทัดถัดไป / step over (F10),
  เข้าฟังก์ชัน / step into (F11), ออกจากฟังก์ชัน / step out (Shift+F11), ทำต่อ / continue (F8),
  หยุด (Shift+F5, shared with Stop). F5 Run is disabled while a session is active.
- Editor: current line gets an arrow marker and highlighted line; the editor is read-only
  during a session; line is scrolled into view. Clicking a call-stack frame jumps to its line.
- Variables whose value changed in the last step are highlighted. Colours from `theme.py`
  (light and dark).
- Debugging is bound to the tab that started it; switching tabs keeps the session and the
  tab shows a marker like the run marker.

## Data flow
`F9` → compile → `DebugSession.start` → gdb stops at `main` → session issues
`-stack-list-frames`, `-stack-list-variables --all-values`, plus `-data-evaluate-expression`
for arrays/pointers/struct members (bounded: arrays ≤ 50 elements shown, then "…") →
`Snapshot` → panel renders + editor marks line. Loop tracker consumes (frame depth, line)
from each Snapshot.

## Error handling
- gdb missing / fails to start / compile error → Thai message, no panel.
- gdb dies mid-session → session ends with message, editor made writable again.
- Unreadable memory (bad pointer) → value shown as "อ่านไม่ได้" with red arrow stub, never an
  exception.
- Program exit → panel shows "โปรแกรมจบด้วยรหัส N", stepping disabled, output flushed.

## Testing
- Unit: `gdbmi` parser (records, escapes, nested), `model` built from recorded MI transcripts,
  `loops` iteration counting incl. nested loops and recursion.
- Integration (skipped when gdb absent): debug small programs (loop+array, pointer swap,
  factorial recursion) and assert snapshots (line, vars, stack depth).
- GUI (offscreen Qt, like `test_gui.py`): panel renders a canned Snapshot; actions enable/
  disable correctly; editor read-only toggling.

## Build order (phases, each shippable)
1. Engine: `gdbmi`, `model`, `session` + stepping + current-line marker + variables table.
2. Call stack panel + loop indicator.
3. Memory diagram (arrays, pointers/arrows, structs, heap pointee).
4. Polish: Thai messages, README, build script note, change highlighting.
