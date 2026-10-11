@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
set "PY=%ROOT%.build-venv\Scripts\python.exe"

if not exist "%PY%" (
    echo Creating the build environment. Python 3.10 or newer is required.
    py -3 -m venv "%ROOT%.build-venv"
    if errorlevel 1 goto :failed
)

"%PY%" -m pip install --upgrade pip
if errorlevel 1 goto :failed
"%PY%" -m pip install -r "%ROOT%DataStudio\project\requirements-build.txt"
if errorlevel 1 goto :failed
"%PY%" -m pip install -r "%ROOT%FuzzyStudio\requirements.txt"
if errorlevel 1 goto :failed
"%PY%" -m pip install -r "%ROOT%MCDMVisualStudio\requirements.txt"
if errorlevel 1 goto :failed
"%PY%" -m pip install "pyinstaller>=6,<7"
if errorlevel 1 goto :failed

echo.
echo Building DataStudio...
cd /d "%ROOT%DataStudio\project"
"%PY%" -m PyInstaller --clean --noconfirm --distpath "%ROOT%dist\DataStudio" --workpath "%ROOT%build\DataStudio" DemoDataStudio.spec
if errorlevel 1 goto :failed

echo.
echo Building MCDMVisualStudio...
cd /d "%ROOT%MCDMVisualStudio"
"%PY%" -m PyInstaller --clean --noconfirm --distpath "%ROOT%dist\MCDMVisualStudio" --workpath "%ROOT%build\MCDMVisualStudio" MCDMVisualStudio.spec
if errorlevel 1 goto :failed

echo.
echo Building the fuzzy calculators...
cd /d "%ROOT%FuzzyStudio\tools_spherical"
"%PY%" -m PyInstaller --clean --noconfirm --onefile --windowed --name SphericalFuzzy --distpath "%ROOT%dist\FuzzyStudio" --workpath "%ROOT%build\FuzzySpherical" --add-data "assets;assets" main.py
if errorlevel 1 goto :failed
cd /d "%ROOT%FuzzyStudio\tools_quantum"
"%PY%" -m PyInstaller --clean --noconfirm --onefile --windowed --name QuantumSpherical --distpath "%ROOT%dist\FuzzyStudio" --workpath "%ROOT%build\FuzzyQuantum" --add-data "assets;assets" main.py
if errorlevel 1 goto :failed
cd /d "%ROOT%FuzzyStudio\tools_neutrosophic"
"%PY%" -m PyInstaller --clean --noconfirm --onefile --windowed --name NeutrosophicZ --distpath "%ROOT%dist\FuzzyStudio" --workpath "%ROOT%build\FuzzyNeutrosophic" --add-data "assets;assets" main.py
if errorlevel 1 goto :failed

echo.
echo Building FuzzyStudio...
cd /d "%ROOT%FuzzyStudio"
"%PY%" -m PyInstaller --clean --noconfirm --distpath "%ROOT%dist\FuzzyStudio" --workpath "%ROOT%build\FuzzyStudio" FuzzyStudio.spec
if errorlevel 1 goto :failed

echo.
echo Copying shared templates and VBA modules beside the apps...
for %%A in (DataStudio MCDMVisualStudio FuzzyStudio) do (
    if not exist "%ROOT%dist\%%A" mkdir "%ROOT%dist\%%A"
    xcopy "%ROOT%Templates" "%ROOT%dist\%%A\Templates" /E /I /Y >nul
    if errorlevel 1 goto :failed
)
xcopy "%ROOT%FuzzyStudio\VBA Library" "%ROOT%dist\FuzzyStudio\VBA Library" /E /I /Y >nul
if errorlevel 1 goto :failed

>"%ROOT%dist\BUILD_README.txt" echo Build complete. Each app is in its own folder; keep its Templates folder beside it.
>>"%ROOT%dist\BUILD_README.txt" echo FuzzyStudio also includes SphericalFuzzy.exe, QuantumSpherical.exe and NeutrosophicZ.exe.
>>"%ROOT%dist\BUILD_README.txt" echo Start each studio by opening its matching .exe.
echo.
echo Build complete. Output: "%ROOT%dist"
pause
exit /b 0

:failed
echo.
echo Build failed. Read the first error above, check internet access, and rerun this script.
pause
exit /b 1
