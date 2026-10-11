@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    call "%~dp0setup_windows.bat"
    if errorlevel 1 exit /b 1
)
"%~dp0.venv\Scripts\python.exe" -m app.main
if errorlevel 1 pause
