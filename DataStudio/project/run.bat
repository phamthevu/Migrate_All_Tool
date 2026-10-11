@echo off
setlocal
cd /d "%~dp0"
if exist "..\..\.build-venv\Scripts\python.exe" (
  "..\..\.build-venv\Scripts\python.exe" main.py
) else (
  py -3 main.py
)
