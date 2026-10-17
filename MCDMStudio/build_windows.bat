@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "APP=%ROOT%\MCDMStudio"
set "VENV=%APP%\.build-venv"
set "PY=%VENV%\Scripts\python.exe"
set "STAGE=prepare Python environment"

echo Building MCDMStudio for Windows...
if not exist "%ROOT%\Templates\Template\MCDMStudio\MCDM_DEMATEL_Input_Template.xlsx" (
    echo The shared MCDMStudio templates were not found beside the MCDMStudio folder.
    goto :failed
)
if not exist "%PY%" (
    echo Creating an isolated build environment...
    py -3 -m venv "%VENV%"
    if errorlevel 1 goto :failed
)

set "STAGE=install MCDMStudio dependencies"
"%PY%" -m pip install --upgrade pip
if errorlevel 1 goto :failed
"%PY%" -m pip install -r "%APP%\requirements-build.txt"
if errorlevel 1 goto :failed

echo Running MCDMStudio calculation, export and frozen-source tests...
set "STAGE=run MCDMStudio tests"
cd /d "%ROOT%"
if not exist "%ROOT%\build" mkdir "%ROOT%\build"
set "TESTLOG=%ROOT%\build\MCDMStudio-tests.log"
"%PY%" -m unittest MCDMStudio.tests.test_methods MCDMStudio.tests.test_stress_methods -v > "%TESTLOG%" 2>&1
set "TEST_RESULT=%ERRORLEVEL%"
type "%TESTLOG%"
if not "%TEST_RESULT%"=="0" goto :failed

echo Packaging the desktop application...
set "STAGE=build MCDMStudio executable"
if exist "%APP%\dist" rmdir /s /q "%APP%\dist"
"%PY%" -m PyInstaller --clean --noconfirm --distpath "%APP%\dist" --workpath "%ROOT%\build\MCDMStudio" "%APP%\MCDMStudio.spec"
if errorlevel 1 goto :failed

if exist "%APP%\dist\Templates" rmdir /s /q "%APP%\dist\Templates"
mkdir "%APP%\dist\Templates\Template\MCDMStudio"
mkdir "%APP%\dist\Templates\Demo Data\MCDMStudio"
xcopy "%ROOT%\Templates\Template\MCDMStudio" "%APP%\dist\Templates\Template\MCDMStudio" /E /I /Y >nul
if errorlevel 1 goto :failed
xcopy "%ROOT%\Templates\Demo Data\MCDMStudio" "%APP%\dist\Templates\Demo Data\MCDMStudio" /E /I /Y >nul
if errorlevel 1 goto :failed
if not exist "%APP%\dist\MCDMStudio.exe" goto :failed

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
echo Build failed while trying to: %STAGE%.
if exist "%TESTLOG%" echo Full test output: "%TESTLOG%"
pause
exit /b 1
