# Visualizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a step debugger with a right-hand Visualizer panel (variables, call stack, loop iteration, pointer/array memory diagram) to the CppLearn app.

**Architecture:** `DebugSession` drives `gdb --interpreter=mi3` over a `QProcess`, and after every stop builds a `Snapshot` (frames + variables). Pure-Python units (`gdbmi`, `model`, `loops`) do all parsing/analysis; Qt units (`session`, `memory_view`, `panel`) only move data and draw. `MainWindow` owns the actions and the dock and marks the current line in the editor.

**Tech Stack:** Python 3.10+, PySide6 (Qt Widgets, QGraphicsView), gdb (MinGW-w64, bundled in `compiler\bin`), pytest (offscreen Qt).

**Spec:** `docs/superpowers/specs/2026-11-04-visualizer-design.md`

## Global Constraints

- No new pip dependencies (PySide6 only). Python 3.10+ syntax (`X | None`), `from __future__ import annotations` in every module, like the existing code.
- All user-visible text is Thai. Colours come from `app/theme.py` tokens (light and dark); never hard-code colours in widgets.
- Fully offline. Compile/work files stay in the ASCII `work_dir()`; the debug build reuses `Runner` (`-g`, `-O0`).
- `gdb.exe` is looked up in `compiler\bin` first, then PATH (same rule as `find_compiler`).
- Arrays show at most 50 elements (`MAX_ELEMENTS = 50`), then "…". Step cap 100 000. Existing 15 s idle kill applies to `continue`.
- Existing behaviour and tests (`tests/`) must keep passing; F5 Run is unchanged when no debug session is active.
- Shortcuts: F9 start, F10 step over, F11 step into, Shift+F11 step out, F8 continue, Shift+F5 stop (shared).
- Run tests with `python -m pytest tests -v`. Tests needing gdb use a `needs_gdb` skip marker (`compiler.find_gdb() is None`).

## Review Focus

- gdb not installed: F9 must not hang or crash; Thai message in the console (Task 7).
- Student code has a compile error: diagnostics appear as usual, no Visualizer panel, no gdb launched (Task 7).
- Program ends or crashes mid-session (e.g. `int *p = nullptr; *p = 1;`): editor becomes writable again, step actions disabled, crash reason in Thai (Tasks 4, 7).
- Thai text in strings/output (`cout << "สวัสดี"`, `string s = "ไทย"`): MI octal escapes decode to the right characters, values not garbled (Tasks 2, 4).
- Large arrays (`int a[10000]`) and garbage/uninitialised pointers: capped at 50 elements, unreadable memory shown as "อ่านไม่ได้", never an exception (Tasks 3, 11).

---

### Task 1: gdb lookup and Windows redirection spike

**Files:**
- Modify: `app/compiler.py` (add `find_gdb`, `NO_GDB_MSG`, `Runner.exe_path`, `-O0` in `build_args`)
- Test: `tests/test_runner.py` (add tests)
- Create (throwaway, scratchpad only): `spike_gdb.py`

**Interfaces:**
- Produces: `compiler.find_gdb() -> str | None`; `compiler.NO_GDB_MSG: str` (Thai); `Runner.exe_path -> Path | None` (path of the last compiled exe).

**Precondition (human):** `compiler\bin\gdb.exe` exists (full WinLibs zip, with the DLLs/data it needs). If it does not, stop and ask the partner to add it before continuing.

- [ ] **Step 1: Write failing tests** in `tests/test_runner.py`: `test_find_gdb_prefers_bundled` (monkeypatch `compiler.app_dir` to a tmp dir containing `compiler/bin/gdb.exe` → returns that path), `test_find_gdb_none` (empty tmp dir + monkeypatch `shutil.which` → `None`), `test_build_args_has_O0` (`"-O0" in build_args(...)`).
- [ ] **Step 2: Run** `python -m pytest tests/test_runner.py -k "gdb or O0" -v` — expect FAIL.
- [ ] **Step 3: Implement** `find_gdb` (mirror `find_compiler`, names `gdb.exe`/`gdb`), `NO_GDB_MSG` (Thai: gdb not found; for the packaged build put `gdb.exe` in `compiler\bin`; or install MinGW-w64/MSYS2 with gdb in PATH), `Runner.exe_path` property (returns `self._exe` or `None` before first compile), and add `"-O0"` after `-g` in `build_args`.
- [ ] **Step 4: Run** the same command — expect PASS.
- [ ] **Step 5: Spike (throwaway, not committed).** In the scratchpad, write `spike_gdb.py` that compiles the Task 4 `LOOP_SRC` with `build_args`, then starts `gdb --interpreter=mi3 -q` via `QProcess`, sends `-file-exec-and-symbols`, `-gdb-set args < in.txt > out.txt 2>&1`, `-break-insert main`, `-exec-run`, `-exec-next` ×3, `-exec-continue`. Confirm: (a) MI records arrive over the pipe, (b) the program's stdout lands in `out.txt` with Thai text intact, (c) `< in.txt` feeds `cin`, (d) no console window flashes (set `CREATE_NO_WINDOW` like `Runner._run`). If (b)/(c) fail (`-inferior-tty-set` is unavailable on Windows), fall back to running the program with `-exec-run` after `-gdb-set new-console off` and capturing its stdio through pipes; record the working recipe as a comment block at the top of `app/visualizer/session.py` in Task 4.
- [ ] **Step 6: Commit** `git add app/compiler.py tests/test_runner.py && git commit -m "feat: find_gdb, Runner.exe_path, -O0 debug build"`

### Task 2: MI parser (`gdbmi.py`)

**Files:**
- Create: `app/visualizer/__init__.py` (empty), `app/visualizer/gdbmi.py`
- Test: `tests/test_gdbmi.py`

**Interfaces:**
- Produces: `@dataclass Record(kind: str, cls: str = "", data: dict = {}, token: int | None = None, text: str = "")`; `parse_record(line: str) -> Record`. `kind` ∈ `"result" | "exec" | "notify" | "console" | "target" | "log" | "prompt" | "unknown"`. Never raises.

- [ ] **Step 1: Write failing tests** (`tests/test_gdbmi.py`), each as its own test:
  - `parse_record('12^done,value="5"')` → `kind=="result"`, `cls=="done"`, `token==12`, `data=={"value":"5"}`
  - `*stopped,reason="end-stepping-range",frame={func="main",line="7"},thread-id="1"` → `kind=="exec"`, `data["frame"]=={"func":"main","line":"7"}`
  - `^done,stack=[frame={level="0",func="f"},frame={level="1",func="main"}]` → `data["stack"]==[{"level":"0","func":"f"},{"level":"1","func":"main"}]` (a list of `key=value` items becomes a list of the values)
  - `^done,variables=[{name="a",value="1"},{name="b",value="2"}]` → list of two dicts; `^done,names=["a","b"]` → `["a","b"]`; empty `[]` and `{}` work
  - `~"hello\n"` → `kind=="console"`, `text=="hello\n"`
  - Thai: `'~"\\340\\270\\252"'` → `text=="ส"` (octal escapes are UTF-8 bytes; decode the whole byte sequence)
  - `^error,msg="No symbol \"x\" in current context."` → `cls=="error"`, `data["msg"]=='No symbol "x" in current context.'`
  - `(gdb) ` → `kind=="prompt"`; `garbage((` → `kind=="unknown"`, `text` is the input
- [ ] **Step 2: Run** `python -m pytest tests/test_gdbmi.py -v` — expect FAIL (import error).
- [ ] **Step 3: Implement** `parse_record` with a small recursive-descent parser over the text after the record prefix (`^ * = ~ @ &`, optional leading digits = token); c-strings collect bytes (octal `\ddd`, `\n`, `\t`, `\"`, `\\`) and decode UTF-8 with `errors="replace"`.
- [ ] **Step 4: Run** the tests — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: GDB/MI record parser"`

### Task 3: Snapshot model (`model.py`)

**Files:**
- Create: `app/visualizer/model.py`
- Test: `tests/test_vis_model.py`

**Interfaces:**
- Consumes: nothing (pure).
- Produces:
  - `MAX_ELEMENTS = 50`
  - `@dataclass Var(name: str, type: str, value: str, kind: str = "scalar", address: int | None = None, size: int | None = None, children: list[Var] = [], target: int | None = None, changed: bool = False, pointee: str | None = None, unreadable: bool = False, more: int = 0)`; `kind` ∈ `scalar|array|pointer|struct`
  - `@dataclass Frame(level: int, func: str, file: str, line: int, args: list[Var], locals: list[Var])`
  - `@dataclass Snapshot(frames: list[Frame], exited: bool = False, exit_code: int | None = None, signal: str | None = None)` with properties `line`, `func`, `file` (of `frames[0]`, or `0`/`""`)
  - `classify(type_str: str, value: str) -> str`
  - `parse_value_text(type_str: str, text: str) -> tuple[list[Var], int]` — children and count of elements hidden beyond `MAX_ELEMENTS`
  - `build_var(mi: dict) -> Var` from one MI variable dict (`name`, `type`, `value`), setting `kind`, `children`, `more`, `target` (parsed from a pointer's leading `0x…`), `unreadable` when value starts with `<error` or `<optimized out>`
  - `build_frame(frame: dict, variables: list[dict]) -> Frame` (`variables` items with `arg="1"` go to `args`)
  - `mark_changes(prev: Snapshot | None, cur: Snapshot) -> None`

- [ ] **Step 1: Write failing tests** (`tests/test_vis_model.py`):
  - `classify("int","5")=="scalar"`, `classify("int *","0x61ff08")=="pointer"`, `classify("int [3]","{1, 2, 3}")=="array"`, `classify("Point","{x = 1, y = 2}")=="struct"`, `classify("std::string","{...}")=="scalar"` (all `std::` types stay scalar)
  - `parse_value_text("int [3]","{10, 20, 30}")` → three children named `[0]`,`[1]`,`[2]` with values `"10","20","30"`, type `"int"`, more 0
  - `parse_value_text("int [5]","{0 <repeats 5 times>}")` → five children `"0"`; `"int [2][2]"` with `{{1, 2}, {3, 4}}` → two children of kind array with type `"int [2]"`
  - `parse_value_text("int [200]","{0 <repeats 200 times>}")` → 50 children, `more==150`
  - `parse_value_text("Point","{x = 1, y = 2}")` → children `x`,`y`; nested `{a = {b = 1}}` works
  - `build_var({"name":"p","type":"int *","value":"0x61ff08"}).target==0x61ff08`; `value="0x0"` → `target==0`; `value="<error: Cannot access memory at address 0x1>"` → `unreadable is True`
  - `mark_changes`: two snapshots where `sum` goes `"0"`→`"10"` and `a[1]` changes → `sum.changed` and `a.children[1].changed` are True, unchanged vars False; `prev=None` → nothing changed; frame keyed by (depth from bottom, func, name) so a recursion step that adds a frame does not mark old frames changed
- [ ] **Step 2: Run** `python -m pytest tests/test_vis_model.py -v` — expect FAIL.
- [ ] **Step 3: Implement** the signatures above. `parse_value_text` needs a depth-aware splitter on top-level commas (ignore commas inside `{}`/strings) and expands `<repeats N times>`; element type for arrays strips the first `[N]` from `type_str`.
- [ ] **Step 4: Run** the tests — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: Visualizer snapshot model"`

### Task 4: Debug session (`session.py`)

**Files:**
- Create: `app/visualizer/session.py`
- Test: `tests/test_vis_session.py`

**Interfaces:**
- Consumes: `Runner` (`start(source, run_after=False)`, `compile_done`, `exe_path`), `compiler.find_gdb`, `compiler.work_dir`, `compiler.describe_exit`, `gdbmi.parse_record`, `model.build_frame/build_var/mark_changes`.
- Produces: `class DebugSession(QObject)`:
  - `__init__(self, runner: Runner, parent: QObject | None = None)`
  - `start(self, source: str, preset: str = "") -> None` — compiles via `runner.start(source, run_after=False)`; on compile ok launches gdb and stops at `main`; if compile fails emits nothing (the window already handles `compile_done`); if `find_gdb()` is `None` emits `failed(NO_GDB_MSG)` before compiling
  - `step_over()`, `step_into()`, `step_out()`, `resume()`, `stop()`
  - property `active: bool` (gdb process alive), `busy: bool` (command in flight)
  - Signals: `stopped(object)` (Snapshot), `output(str)` (new program stdout/stderr text), `finished(int, str)` (exit code, reason: `"ok"|"crash"|"stopped"|"step_limit"|"gdb_died"`), `failed(str)`
- Behaviour: collects, after each `*stopped`, `-stack-list-frames` then per frame `-stack-list-variables --thread 1 --frame N --all-values`, then per variable `-data-evaluate-expression --thread 1 --frame N "&name"` and `sizeof(name)` to fill `address`/`size`, then `mark_changes(prev, cur)`. `std::string` variables are evaluated as `name.c_str()` (best effort, falls back to raw value). Stepping that lands outside the user's `main.cpp` issues `-exec-finish` (up to 5 times) so the student never sees library code. Program stdout/stderr are redirected to a temp file in `work_dir()` per the Task 1 spike recipe and tailed into `output` after each stop and at exit; `preset` is the program's stdin. Counts steps; at 100 000 emits `finished(-1, "step_limit")` and kills gdb. `stop()` kills gdb with `finished(-1, "stopped")`. Exit via `*stopped,reason="exited…"` → final `Snapshot(frames=[], exited=True, exit_code=N)` through `stopped`, then `finished`. Signals (`signal-received`, e.g. SIGSEGV) stop at the faulting line with `Snapshot.signal` set and `finished` fires when the user continues/stops.

- [ ] **Step 1: Write failing tests** (`tests/test_vis_session.py`, marker `needs_gdb`, a `wait_until` helper like `tests/test_gui.py`). Sources (line numbers matter):
  - `LOOP_SRC`: `#include <iostream>` / `int main() {` / `    int a[3] = {10, 20, 30};` / `    int sum = 0;` / `    for (int i = 0; i < 3; i++) {` / `        sum += a[i];` / `    }` / `    std::cout << sum << "\n";` / `    return 0;` / `}`
  - `POINTER_SRC`: lines `int main() {` (2), `int x = 5;` (3), `int *p = &x;` (4), `*p = 9;` (5), `std::cout << x << "\n";` (6), `return 0;` (7)
  - `FACT_SRC`: `int fact(int n) {` (2), `if (n <= 1) return 1;` (3), `return n * fact(n - 1);` (4), `}` (5), `int main() {` (6), `std::cout << fact(3) << "\n";` (7)
  - `test_loop_stepping`: start → first snapshot `line==3`, `func=="main"`; `step_over()` ×2 → `line==5`, variable `a` has kind `array` and children values `["10","20","30"]`; `step_over()` ×2 more → `sum` has value `"10"` and `changed is True`; `resume()` → `finished(0,"ok")` and collected output contains `"60"`
  - `test_pointer_target`: at line 5, `p.kind=="pointer"` and `p.target == x.address`
  - `test_recursion_stack`: `step_into()` at line 7 → `len(frames)==2`, `frames[0].func=="fact"`, arg `n.value=="3"`; after `step_over()` and `step_into()` → depth 3, `n.value=="2"`
  - `test_crash_reports_signal`: source `int main(){ int *p = nullptr; *p = 1; }` → `resume()` → snapshot with `signal` not `None`, and `finished` reason `"crash"`
  - `test_thai_output`: program printing `"สวัสดี\n"` → collected output equals it
  - `test_stop_kills_gdb`: `stop()` → `active is False`, `finished(-1,"stopped")`
  - non-gdb: `test_no_gdb_emits_failed` (monkeypatch `find_gdb` → `None`; `failed` emitted with `NO_GDB_MSG`; runs without gdb)
- [ ] **Step 2: Run** `python -m pytest tests/test_vis_session.py -v` — expect FAIL.
- [ ] **Step 3: Implement** `DebugSession`. Use a token-keyed callback queue for MI commands (one logical command chain at a time; ignore `step_*` calls while `busy`). Put the Task 1 spike recipe in the module docstring.
- [ ] **Step 4: Run** the tests — expect PASS (gdb tests skip with a clear reason if gdb is absent; run them on a machine with gdb before merging).
- [ ] **Step 5: Commit** `git commit -m "feat: gdb-backed DebugSession with snapshots"`

### Task 5: Editor current-line marker and theme tokens

**Files:**
- Modify: `app/theme.py` (add `debug_line`, `changed` tokens to `_LIGHT` and `_DARK`), `app/editor.py` (`CodeEditor`)
- Test: `tests/test_gui.py` (or new `tests/test_vis_editor.py`)

**Interfaces:**
- Produces: `CodeEditor.set_debug_line(line: int | None) -> None` (1-based; `None` clears), property `CodeEditor.debug_line -> int | None`, `CodeEditor.set_debug_mode(on: bool) -> None` (read-only while on, and clears the marker when turned off); theme tokens `debug_line` (line background) and `changed` (value-changed highlight) in both palettes.

- [ ] **Step 1: Write failing tests:** `set_debug_line(3)` → `debug_line==3`, the extra selections include one whose cursor is on block 2 (0-based); `set_debug_line(None)` clears it; `set_debug_mode(True)` → `isReadOnly()`; `set_debug_mode(False)` → not read-only and `debug_line is None`; `theme.palette(dark)` has both new keys for `dark` in `(False, True)`.
- [ ] **Step 2: Run** the new tests — expect FAIL.
- [ ] **Step 3: Implement.** Read `_refresh_extra` and `paint_line_numbers` in `app/editor.py` first: add the debug line to the extra selections (full-width background from `theme.palette(self._dark)["debug_line"]`), draw a "▶" in the line-number area for that line, scroll into view via `goto_line`. Pick light/dark values with enough contrast against `text`.
- [ ] **Step 4: Run** the new tests and `python -m pytest tests -v` — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: editor debug-line marker and theme tokens"`

### Task 6: Panel with variables table

**Files:**
- Create: `app/visualizer/panel.py`
- Test: `tests/test_vis_panel.py`

**Interfaces:**
- Consumes: `model.Snapshot/Frame/Var`, `theme.palette`.
- Produces: `class VisualizerPanel(QWidget)`:
  - `show_snapshot(snap: Snapshot) -> None`, `clear() -> None`, `set_dark(dark: bool) -> None`
  - `variables: QTreeWidget` (columns "ชื่อ", "ชนิด", "ค่า"; arrays/structs expand to children; vars with `changed` get the `changed` colour as background; `unreadable` shows "อ่านไม่ได้"; `more>0` adds a last row "… อีก N ช่อง")
  - `info_label: QLabel` (one-line status, e.g. "โปรแกรมจบด้วยรหัส 0" or the crash reason)
  - Shows frame 0 variables (args then locals); frame selection arrives in Task 9.

- [ ] **Step 1: Write failing tests** (offscreen): build a `Snapshot` by hand (one frame, `sum` scalar changed, `a` array with 3 children, one `more=5` array). Assert top-level item count and texts; `a` item has 3 child items; changed item's background differs from the unchanged one; unreadable var shows `"อ่านไม่ได้"`; `clear()` empties the tree; an `exited=True, exit_code=0` snapshot sets `info_label` text containing `"0"` and empties the tree.
- [ ] **Step 2: Run** `python -m pytest tests/test_vis_panel.py -v` — expect FAIL.
- [ ] **Step 3: Implement** `VisualizerPanel` as a vertical `QSplitter` inside a `QVBoxLayout` so Tasks 9 and 11 can add widgets above/below the table without restructuring.
- [ ] **Step 4: Run** the tests — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: Visualizer panel with variables table"`

### Task 7: MainWindow integration (phase 1 complete)

**Files:**
- Modify: `app/main_window.py` (`MainWindow`: actions, "ดีบัก" menu, toolbar buttons, dock, session wiring), `app/compiler.py` only if needed
- Test: `tests/test_vis_window.py`

**Interfaces:**
- Consumes: `DebugSession`, `VisualizerPanel`, `CodeEditor.set_debug_line/set_debug_mode`, `Document`.
- Produces on `MainWindow`: actions `a_debug` (F9), `a_step_over` (F10), `a_step_into` (F11), `a_step_out` (Shift+F11), `a_continue` (F8); methods `start_debug()`, `_end_debug()`; attributes `visualizer: VisualizerPanel`, `debug_session: DebugSession`, `_debug_doc: Document | None`.

- [ ] **Step 1: Write failing tests** (offscreen, same `qapp`/`win` fixtures as `tests/test_gui.py`):
  - `test_no_gdb_message` (monkeypatch `find_gdb` → `None`): `win.start_debug()` → console text contains the first line of `NO_GDB_MSG`, panel hidden, `a_run` still enabled, no exception
  - `test_compile_error_no_panel` (needs g++): editor holds `int main(){ x = 1; }` → `start_debug()` → problems list gets an entry, panel hidden, `debug_session.active is False`
  - `test_debug_flow` (needs gdb): LOOP_SRC → panel visible, `editor.debug_line == 3`, `editor.isReadOnly()`, step actions enabled, `a_run` disabled; `a_step_over.trigger()` → `debug_line == 4`; `a_continue.trigger()` → after finish: editor writable, `debug_line is None`, panel hidden, step actions disabled, `a_run` enabled
  - `test_stop_ends_debug` (needs gdb): `stop_run()` during a session ends it the same way
  - `test_crash_makes_editor_writable` (needs gdb): the nullptr program, `a_continue.trigger()` → crash text from `describe_exit` in the console and editor writable again
  - `test_close_window_kills_gdb` (needs gdb): closing the window mid-session leaves `debug_session.active is False`
- [ ] **Step 2: Run** `python -m pytest tests/test_vis_window.py -v` — expect FAIL.
- [ ] **Step 3: Implement.** Add the panel as a third widget of `main_split` (hidden until a session starts, theme applied in `_apply_theme`). `start_debug()`: ignore if `runner.busy` or a session is active; record `_debug_doc`, set `self._debugging = True` so `_on_compile_done` skips the "▶ เริ่มรันโปรแกรม" line; clear console/problems like `run_code`; pass `console.preset_text()` as `preset`; `tabs.set_running(doc)`. On `stopped` → `visualizer.show_snapshot`, `_debug_doc.editor.set_debug_line(snap.line)` (None when exited). On `output` → `console.append_*` like the run flow. On `finished`/`failed` → `_end_debug()` (writable editor, hide panel, restore actions, status message, Thai text via `describe_exit` for crashes, step-limit message "หยุดดีบัก: เดินครบ 100,000 ขั้นแล้ว (อาจมีลูปไม่รู้จบ)"). `stop_run` also stops the session. `closeEvent` stops the session. Disable `a_run` while a session is active; enable step actions only when `session.active and not session.busy`. For a missing gdb or failed start, write the message to the console and status bar only (no modal dialog).
- [ ] **Step 4: Run** the tests and `python -m pytest tests -v` — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: debug actions, dock and session wiring in main window"`

### Task 8: Loop analysis (`loops.py`)

**Files:**
- Create: `app/visualizer/loops.py`
- Test: `tests/test_vis_loops.py`

**Interfaces:**
- Produces:
  - `@dataclass LoopInfo(line: int, end_line: int, kind: str, var: str | None)` (`kind` ∈ `for|while|do`)
  - `find_loops(source: str) -> dict[int, LoopInfo]` keyed by header line (1-based). `for (int i = 0; …` and `for (i = 0; …` give `var="i"`; `while`/`do` give `var=None`. `end_line` is the matching `}` or, for braceless loops, the line of the statement's `;`. Ignores loops inside comments and string literals.
  - `@dataclass LoopStatus(line: int, kind: str, var: str | None, iteration: int)`
  - `class LoopTracker`: `update(depth: int, line: int) -> list[LoopStatus]` (outermost first) and `reset() -> None`. `iteration` = number of visits to the header line while the current line stays within `[line, end_line]` at that frame depth; leaving the range (or a shallower depth) resets that loop.

- [ ] **Step 1: Write failing tests:**
  - `find_loops(LOOP_SRC)` → `{5: LoopInfo(5, 7, "for", "i")}`; a `while (x > 0) {` multi-line and a braceless `for (int i=0;i<3;i++) sum += i;` (end_line == header line) are found; a `// for (…)` comment and `"for (x)"` string produce nothing; a nested pair gives two entries with the inner range inside the outer
  - `LoopTracker` fed the line sequence `5,6,5,6,5,6,5,8` (depth 1) → after the 1st `5` iteration 1, after the 2nd `5` iteration 2, after the 3rd 3; at line `8` the returned list is empty; calling again from `5` restarts at iteration 1
  - nested loops: outer header visited twice while the inner restarts at 1 each time
  - recursion: same lines at depth 2 do not advance the loop of depth 1
- [ ] **Step 2: Run** `python -m pytest tests/test_vis_loops.py -v` — expect FAIL.
- [ ] **Step 3: Implement** with a small tokenizer that skips comments/strings/char literals before regex and brace matching.
- [ ] **Step 4: Run** the tests — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: loop detection and iteration tracker"`

### Task 9: Call stack and loop badge (phase 2 complete)

**Files:**
- Modify: `app/visualizer/panel.py`, `app/main_window.py`
- Test: `tests/test_vis_panel.py`, `tests/test_vis_window.py`

**Interfaces:**
- Consumes: `LoopTracker`, `find_loops`, `LoopStatus`.
- Produces on `VisualizerPanel`: `stack: QListWidget` (one row per frame, innermost first, text `f(n=3)  บรรทัด 4`), `loop_label: QLabel` (hidden when no loop), signal `frame_selected(int)` (emits the frame's `line`, and the variables table switches to that frame's variables), `set_loops(statuses: list[LoopStatus], values: dict[str, str]) -> None` where `values` maps the loop variable name to its current value in the shown frame. Badge text e.g. `วนรอบที่ 2 · i = 1`; for `while`/`do` `วนรอบที่ 2`; nested loops joined with ` › `.

- [ ] **Step 1: Write failing tests:** a 3-frame hand-built snapshot (`fact` ×2 + `main`) → `stack.count()==3`, row 0 text contains `"fact"` and `"n=2"`; selecting row 2 → `frame_selected` fired with `main`'s line and the variables table shows `main`'s variables; `set_loops([LoopStatus(5,"for","i",2)], {"i":"1"})` → label visible with text containing `"รอบที่ 2"` and `"i = 1"`; `set_loops([], {})` hides it. Window test (needs gdb): stepping LOOP_SRC to line 6 twice shows `"รอบที่ 1"` then (after returning to the header) `"รอบที่ 2"` in `visualizer.loop_label`; clicking a stack row moves `editor.debug_line` to that frame's line.
- [ ] **Step 2: Run** `python -m pytest tests/test_vis_panel.py tests/test_vis_window.py -v` — expect FAIL.
- [ ] **Step 3: Implement.** In `MainWindow`, build `find_loops(source)` once per session and a `LoopTracker`; on every `stopped` call `tracker.update(len(snap.frames), snap.line)` and `visualizer.set_loops(...)`; reset the tracker at session end. Selecting a stack row calls `editor.set_debug_line(line)` for that frame (frame 0 restores the live line after the next step).
- [ ] **Step 4: Run** the tests and `python -m pytest tests -v` — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: call stack panel and loop iteration badge"`

### Task 10: Pointer target resolution (`model.py`)

**Files:**
- Modify: `app/visualizer/model.py`, `app/visualizer/session.py`
- Test: `tests/test_vis_model.py`, `tests/test_vis_session.py`

**Interfaces:**
- Produces: `@dataclass PointsTo(frame_level: int, var_name: str, index: int | None)`; `Var.points_to: PointsTo | None = None`; `resolve_pointer_targets(snap: Snapshot) -> None` — for every pointer var (any depth, including struct members) with `target` not 0/None, finds the variable or array element (frames searched innermost first) whose `[address, address+size)` contains `target` and sets `points_to`; array elements use `size // len(children)` as element stride. Unresolved non-null targets stay `points_to=None` (treated as heap/unknown by the view). `DebugSession` calls it before emitting `stopped`; for unresolved pointers to scalars it evaluates `*name` and stores the text in `Var.pointee` (`unreadable=True` on error).

- [ ] **Step 1: Write failing tests:** hand-built snapshot: `int x` at `0x100` size 4, `int a[3]` at `0x200` size 12, `int *p` target `0x100`, `int *q` target `0x208`, `int *r` target `0x900`, `int *n` target 0 → `p.points_to==PointsTo(0,"x",None)`, `q.points_to==PointsTo(0,"a",2)`, `r.points_to is None`, `n.points_to is None`; a pointer in frame 1 pointing at a local of frame 0 resolves to `frame_level 0`. Session test (needs gdb): `new int(7)` pointer → `pointee == "7"`; POINTER_SRC at line 5 → `p.points_to == PointsTo(0, "x", None)`.
- [ ] **Step 2: Run** `python -m pytest tests/test_vis_model.py tests/test_vis_session.py -k "pointer or points" -v` — expect FAIL.
- [ ] **Step 3: Implement** as above.
- [ ] **Step 4: Run** the tests — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: resolve pointer targets for memory diagram"`

### Task 11: Memory diagram (`memory_view.py`) (phase 3 complete)

**Files:**
- Create: `app/visualizer/memory_view.py`
- Modify: `app/visualizer/panel.py` (embed below the variables table)
- Test: `tests/test_vis_memory_view.py`

**Interfaces:**
- Consumes: `Snapshot` with `points_to`/`pointee` resolved, `theme.palette`.
- Produces: `class MemoryView(QGraphicsView)`: `show_snapshot(snap: Snapshot) -> None`, `clear() -> None`, `set_dark(dark: bool) -> None`; read-only counters `box_count: int` (one box per scalar variable, per array element, per struct member, plus one per heap pointee) and `arrow_count: int`. Frames are stacked top to bottom, innermost first, each in a labelled group (function name). Scalars: a box with name above and value inside; arrays: a row of boxes with `[i]` index labels (≤ 50, then a "…" box); structs: a titled group of member boxes; pointers: a box showing the address, with an arrow to the target box (`points_to`) or to a "heap" box with address and `pointee`; null pointer shows `nullptr` and no arrow; `unreadable` shows "อ่านไม่ได้" in the danger colour. `changed` boxes use the `changed` token.

- [ ] **Step 1: Write failing tests:** hand-built snapshot with `x`, `a[3]`, `p→x`, `q→a[2]`, `n=nullptr`, heap `r` with `pointee="7"` → `box_count == 9` (x = 1, a[0..2] = 3, pointers p, q, n, r = 4, heap box for r = 1), `arrow_count == 3` (p, q, r); a 200-element array snapshot with `more=150` → `box_count` counts 50 element boxes + the "…" box, completes quickly (< 1 s), and no exception; unreadable pointer → no arrow, no exception; `clear()` resets both counts to 0; `set_dark(True)` re-renders without error.
- [ ] **Step 2: Run** `python -m pytest tests/test_vis_memory_view.py -v` — expect FAIL.
- [ ] **Step 3: Implement** with `QGraphicsScene` items (rects, text, `QPainterPath` arrows with arrowheads); arrow endpoints attach to the target box's edge; `fitInView` on show; fonts via `editor.code_font`.
- [ ] **Step 4: Run** the tests and `python -m pytest tests -v` — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: memory diagram with arrays, pointers and heap boxes"`

### Task 12: Polish and docs (phase 4)

**Files:**
- Modify: `README.md`, `build_windows.bat`, `app/main_window.py` (menu text/tooltips, `_about`), `CppLearn.spec` (only if gdb needs explicit inclusion)
- Test: `tests/test_vis_window.py`

- [ ] **Step 1: Write failing tests:** menu "ดีบัก" exists with the five actions and their shortcuts (`F9`, `F10`, `F11`, `Shift+F11`, `F8`); step actions disabled when no session; a program with `cin` and preset input `"5\n"` debugs to completion with the right output (needs gdb); switching tabs mid-session keeps the session and the debug tab keeps its running marker (needs gdb).
- [ ] **Step 2: Run** `python -m pytest tests/test_vis_window.py -v` — expect FAIL on the new tests only.
- [ ] **Step 3: Implement** the missing pieces found by the tests. Update README: Thai feature list entry "ตัวช่วยมองเห็นการทำงาน (Visualizer)", shortcuts table, requirement that `gdb.exe` sits in `compiler\bin` (full WinLibs zip includes it), and the project-structure listing of `app/visualizer/`. Add the same gdb note to `build_windows.bat`'s pre-check (warn, do not fail, if `compiler\bin\gdb.exe` is missing).
- [ ] **Step 4: Run** `python -m pytest tests -v` — expect all PASS; then manually run `python main.py`, open the "ตัวอย่างโค้ด" examples, press F9 on a loop, a pointer and a recursion example, and confirm the panel, arrow marker, arrays-as-boxes and pointer arrows look right in light and dark themes.
- [ ] **Step 5: Commit** `git commit -m "docs: Visualizer README, shortcuts and build notes"`
