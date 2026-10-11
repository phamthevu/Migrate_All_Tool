$ErrorActionPreference = "Stop"
python -m venv .venv_build
& .\.venv_build\Scripts\Activate.ps1
python -m pip install --upgrade pip wheel
pip install -r requirements.txt
pip install "pyinstaller>=6.10,<7"
python -m pytest -q
python -m compileall -q .
pyinstaller --noconfirm --clean ResearchStudio.spec
Write-Host "Build complete: dist\ResearchStudio\ResearchStudio.exe"
