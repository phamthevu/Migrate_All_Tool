@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "APP=%ROOT%\MCDMStudio"
set "VENV=%APP%\.build-venv"
set "PY=%VENV%\Scripts\python.exe"

echo Building MCDMStudio for Windows...
if not exist "%PY%" (
    echo Creating an isolated build environment...
    py -3 -m venv "%VENV%"
    if errorlevel 1 goto :failed
)

"%PY%" -m pip install --upgrade pip
if errorlevel 1 goto :failed
"%PY%" -m pip install -r "%APP%\requirements-build.txt"
if errorlevel 1 goto :failed

echo Running the calculation and workbook tests...
cd /d "%ROOT%"
"%PY%" -m unittest MCDMStudio.tests.test_methods MCDMStudio.tests.test_stress_methods -q
if errorlevel 1 goto :failed

echo Packaging the desktop application...
"%PY%" -m PyInstaller --clean --noconfirm --distpath "%APP%\dist" --workpath "%ROOT%\build\MCDMStudio" "%APP%\MCDMStudio.spec"
if errorlevel 1 goto :failed

if exist "%APP%\dist\Templates" rmdir /s /q "%APP%\dist\Templates"
mkdir "%APP%\dist\Templates\Template\MCDMStudio"
mkdir "%APP%\dist\Templates\Demo Data\MCDMStudio"
xcopy "%ROOT%\Templates\Template\MCDMStudio" "%APP%\dist\Templates\Template\MCDMStudio" /E /I /Y >nul
if errorlevel 1 goto :failed
xcopy "%ROOT%\Templates\Demo Data\MCDMStudio" "%APP%\dist\Templates\Demo Data\MCDMStudio" /E /I /Y >nul
if errorlevel 1 goto :failed

(
    echo MCDMStudio Windows build
    echo Run MCDMStudio.exe from this folder. Keep the Templates folder beside it.
    echo Templates contains the blank TOPSIS and DEMATEL workbooks and demo data.
) > "%APP%\dist\BUILD_README.txt"

echo.
echo Build complete: "%APP%\dist\MCDMStudio.exe"
pause
exit /b 0

:failed
echo.
echo Build failed. Check the first error above and confirm internet access for package installation.
pause
exit /b 1
