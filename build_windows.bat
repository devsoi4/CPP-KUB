@echo off
rem Build CPP-KUB for Windows (PyInstaller, onedir).
rem Put MinGW-w64 in .\compiler so that .\compiler\bin\g++.exe exists BEFORE running this.

cd /d "%~dp0"

rem Find a real Python (skip the Microsoft Store stub that makes "python" fail)
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python -c "import sys" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo [ERROR] Python 3.10+ not found. Install it from python.org, then run this again.
  goto fail
)

if not exist compiler\bin\g++.exe (
  echo [WARNING] compiler\bin\g++.exe not found. The app will be built without a bundled compiler.
  echo           Students would need g++ in PATH. See README.md.
  pause
)

if not exist compiler\bin\gdb.exe (
  echo [WARNING] compiler\bin\gdb.exe not found. The Visualizer (step debugger) will not work.
  echo           Copy gdb.exe and the DLLs it needs from a full MinGW-w64 / WinLibs package. See README.md.
  pause
)

%PY% -m pip install -r requirements.txt
if errorlevel 1 goto fail

%PY% -m PyInstaller --noconfirm --clean --windowed --icon assets\icon.ico --name CPP-KUB main.py
if errorlevel 1 goto fail

xcopy /E /I /Y assets dist\CPP-KUB\assets >nul
if exist compiler (
  xcopy /E /I /Y compiler dist\CPP-KUB\compiler >nul
)

echo.
echo Done. Distribute the whole folder: dist\CPP-KUB
pause
exit /b 0

:fail
echo.
echo Build failed. Check the messages above.
pause
exit /b 1
