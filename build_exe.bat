@echo off
rem Builds dist\UltraShot\UltraShot.exe (standalone, no Python needed on the target PC).
rem Requires: pip install pyinstaller pywebview pystray imagecodecs numpy pillow
cd /d "%~dp0"
python make_icon.py
python -m PyInstaller --noconfirm --clean --windowed --onedir ^
  --name UltraShot --icon ui\ultrashot.ico ^
  --add-data "ui;ui" ^
  --collect-all imagecodecs ^
  --collect-submodules webview ^
  --hidden-import pystray._win32 ^
  --exclude-module tkinter --exclude-module matplotlib --exclude-module scipy --exclude-module pandas ^
  --exclude-module IPython --exclude-module PySide6 --exclude-module PyQt5 --exclude-module PyQt6 ^
  ultrashot.py
if errorlevel 1 (echo BUILD FAILED & if not "%1"=="-q" pause & exit /b 1)
echo.
echo Built dist\UltraShot\UltraShot.exe
if not "%1"=="-q" pause
