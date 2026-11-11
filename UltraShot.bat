@echo off
rem Runs UltraShot from source (no console window). Use UltraShot.exe from dist\ for the packaged app.
cd /d "%~dp0"
start "" pythonw "%~dp0ultrashot.py" %*
