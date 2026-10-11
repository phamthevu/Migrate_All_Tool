@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run install.bat first.
    pause
    exit /b 1
)
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm DemoDataStudio.spec
if errorlevel 1 goto fail
echo Built dist\DataStudio.exe. Shared templates are embedded and also kept in the package Templates folder.
pause
exit /b 0
:fail
echo Build failed.
pause
exit /b 1
