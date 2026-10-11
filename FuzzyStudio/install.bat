@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo FuzzyStudio dependencies installed. Run run.bat.
pause
exit /b 0
:fail
echo Installation failed. Install 64-bit Python 3.10+ and check internet access.
pause
exit /b 1
