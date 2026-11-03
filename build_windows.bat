@echo off
rem Build CppLearn for Windows (PyInstaller, onedir).
rem Put MinGW-w64 in .\compiler so that .\compiler\bin\g++.exe exists BEFORE running this.

cd /d "%~dp0"

if not exist compiler\bin\g++.exe (
  echo [WARNING] compiler\bin\g++.exe not found. The app will be built without a bundled compiler.
  echo           Students would need g++ in PATH. See README.md.
  pause
)

python -m pip install -r requirements.txt
if errorlevel 1 goto fail

python -m PyInstaller --noconfirm --clean --windowed --name CppLearn main.py
if errorlevel 1 goto fail

if exist compiler (
  xcopy /E /I /Y compiler dist\CppLearn\compiler >nul
)

echo.
echo Done. Distribute the whole folder: dist\CppLearn
pause
exit /b 0

:fail
echo.
echo Build failed. Check the messages above.
pause
exit /b 1
