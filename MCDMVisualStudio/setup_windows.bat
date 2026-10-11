@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 (
    echo Could not create the project virtual environment. Install Python 3.10+ and enable the Python Launcher.
    pause
    exit /b 1
)
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :failed
echo.
echo Setup complete. Run run_windows.bat to start the app.
pause
exit /b 0
:failed
echo Dependency installation failed. Check your internet connection and requirements.txt.
pause
exit /b 1
