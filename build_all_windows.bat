@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
set "PY=%ROOT%.build-venv\Scripts\python.exe"

if not exist "%PY%" (
    echo Creating shared build environment. Python 3.10+ and the Python Launcher are required.
    py -3 -m venv "%ROOT%.build-venv"
    if errorlevel 1 goto :failed
)
"%PY%" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
  echo Python 3.10 or newer is required. Select an appropriate Python with the Windows Python Launcher.
  goto :failed
)

"%PY%" -m pip install --upgrade pip
if errorlevel 1 goto :failed
"%PY%" -m pip install -r "%ROOT%requirements.txt"
if errorlevel 1 goto :failed

echo.
echo Running the deterministic MCDMStudio method and stress tests...
cd /d "%ROOT%"
"%PY%" -m unittest MCDMStudio.tests.test_methods MCDMStudio.tests.test_stress_methods -q
if errorlevel 1 goto :failed

call :build DataStudio "%ROOT%DataStudio\project" DemoDataStudio.spec
if errorlevel 1 goto :failed
call :research
if errorlevel 1 goto :failed
call :build MCDMStudio "%ROOT%MCDMStudio" MCDMStudio.spec
if errorlevel 1 goto :failed
call :build MCDMVisualStudio "%ROOT%MCDMVisualStudio" MCDMVisualStudio.spec
if errorlevel 1 goto :failed

call :fuzzy SphericalFuzzy tools_spherical
if errorlevel 1 goto :failed
call :fuzzy QuantumSpherical tools_quantum
if errorlevel 1 goto :failed
call :fuzzy NeutrosophicZ tools_neutrosophic
if errorlevel 1 goto :failed
call :build FuzzyStudio "%ROOT%FuzzyStudio" FuzzyStudio.spec
if errorlevel 1 goto :failed

for %%A in (DataStudio ResearchStudio MCDMStudio MCDMVisualStudio FuzzyStudio) do (
  if not exist "%ROOT%dist\%%A" mkdir "%ROOT%dist\%%A"
  xcopy "%ROOT%Templates" "%ROOT%dist\%%A\Templates" /E /I /Y >nul
  if errorlevel 1 goto :failed
)
xcopy "%ROOT%FuzzyStudio\VBA Library" "%ROOT%dist\FuzzyStudio\VBA Library" /E /I /Y >nul
if errorlevel 1 goto :failed

for %%A in (DataStudio ResearchStudio MCDMStudio MCDMVisualStudio FuzzyStudio) do (
  if not exist "%ROOT%dist\%%A\%%A.exe" (
    echo Expected executable is missing: "%ROOT%dist\%%A\%%A.exe"
    goto :failed
  )
)
for %%A in (SphericalFuzzy QuantumSpherical NeutrosophicZ) do (
  if not exist "%ROOT%dist\FuzzyStudio\%%A.exe" (
    echo Expected FuzzyStudio calculator is missing: "%ROOT%dist\FuzzyStudio\%%A.exe"
    goto :failed
  )
)

(
  echo Build complete. Each application has its own directory and shared Templates folder.
  echo Run each app from dist\APPNAME\APPNAME.exe.
  echo FuzzyStudio folder also contains SphericalFuzzy.exe, QuantumSpherical.exe and NeutrosophicZ.exe.
) > "%ROOT%dist\BUILD_README.txt"
echo.
echo All five Studios built successfully. Output: "%ROOT%dist"
pause
exit /b 0

:build
set "APP=%~1"
set "APPDIR=%~2"
set "SPEC=%~3"
echo.
echo Building %APP%...
cd /d "%APPDIR%"
"%PY%" -m PyInstaller --clean --noconfirm --distpath "%ROOT%dist\%APP%" --workpath "%ROOT%build\%APP%" "%SPEC%"
exit /b %errorlevel%

:research
echo.
echo Building ResearchStudio...
cd /d "%ROOT%ResearchStudio"
"%PY%" -m PyInstaller --clean --noconfirm --distpath "%ROOT%dist" --workpath "%ROOT%build\ResearchStudio" ResearchStudio.spec
exit /b %errorlevel%

:fuzzy
set "EXE=%~1"
set "SUBDIR=%~2"
echo.
echo Building FuzzyStudio calculator %EXE%...
cd /d "%ROOT%FuzzyStudio\%SUBDIR%"
"%PY%" -m PyInstaller --clean --noconfirm --onefile --windowed --name "%EXE%" --distpath "%ROOT%dist\FuzzyStudio" --workpath "%ROOT%build\%EXE%" --add-data "assets;assets" main.py
exit /b %errorlevel%

:failed
echo.
echo Build failed. Review the first error, confirm network access, then rerun.
pause
exit /b 1
