@echo off
setlocal
cd /d "%~dp0"
if exist "..\.build-venv\Scripts\python.exe" (
  "..\.build-venv\Scripts\python.exe" -m app.main
) else (
  py -3 -m app.main
)
