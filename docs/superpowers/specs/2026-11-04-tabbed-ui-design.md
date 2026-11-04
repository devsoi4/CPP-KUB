# Tabbed UI redesign (VS Code style) — Design

Date: 2026-11-04

## Goal
Make CppLearn modern and easy to use in the classroom: open several files at once as tabs
(like VS Code), with a refreshed look. Must keep: Thai support everywhere, Thai error
translation, preset input, print/PDF, fully offline, existing tests passing.

## 1. Layout
- Activity bar (narrow icon strip, left) toggles the Explorer panel.
- Explorer groups: "ไฟล์ที่เปิดอยู่" (open files), "ตัวอย่างโค้ด" (10 examples; click opens a new tab),
  "โฟลเดอร์งาน" (user-chosen folder, lists .cpp/.cc/.cxx/.h/.hpp).
- Centre: document tabs above the editor.
- Bottom panel (tabbed): ผลลัพธ์ | ปัญหา (N) | ข้อมูลนำเข้าล่วงหน้า. The old right-hand
  problems dock is removed.
- Toolbar reduced to icon buttons: run, stop, save, print. The example combo box is removed
  (examples live in Explorer and the existing menu).
- Status bar: line/column, encoding of active file, run status.

## 2. Document tabs
- Close button, "●" when modified, tooltip = full path, drag to reorder, middle-click closes.
- Ctrl+W close, Ctrl+Tab / Ctrl+Shift+Tab cycle, Ctrl+N new tab "ไม่มีชื่อ-N".
- Opening an already-open file activates its tab (no duplicate).
- A lone untitled, unmodified tab is replaced when opening a file/example.
- Closing a modified tab asks save / don't save / cancel for that tab only; closing the
  app walks all modified tabs.

## 3. Running
- F5 runs the active tab; no concurrent runs (run button disabled while busy).
- The running tab shows a small ▶ marker. Switching tabs mid-run keeps output flowing and
  cin input working.
- Diagnostics (line marks) are applied to the editor of the tab that was run. Clicking a
  problem activates that tab and jumps to the line.
- Preset input is stored per tab and swapped into the preset widget on tab change.
  Console output is a single shared view, cleared on each run.

## 4. Theme
- `theme.py` defines colour tokens for light and dark; one source feeds the Qt stylesheet,
  syntax highlighter and console colours.
- Icons are inline SVG recoloured per theme; no new files or dependencies.
- Default theme stays light (toggle in View menu).

## 5. Code structure and tests
- New: `app/document.py` (editor + path + preset text + modified state per tab),
  `app/sidebar.py`, `app/theme.py`, `app/icons.py`. `main_window.py` keeps orchestration,
  run and file handling.
- `win.editor`, `win.path`, `win.problems` remain as properties delegating to the active
  tab so `tests/test_gui.py` keeps working with minimal edits.
- New tests: multiple tabs, close modified tab, open same file twice, run uses active tab,
  per-tab preset.
- Session restore: on exit save the list of saved-file paths and the active one in
  QSettings; reopen on start (untitled/unsaved content is not restored).

## Out of scope
Split editor panes, find/replace, debugger, per-tab console output.
