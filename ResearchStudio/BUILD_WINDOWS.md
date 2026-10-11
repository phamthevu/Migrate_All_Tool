# Build ResearchStudio with the complete suite

From the suite root, run `build_all_windows.bat`. It installs the deduplicated dependencies from the one root `requirements.txt` and builds the five apps with their own PyInstaller specs. ResearchStudio uses an onedir distribution and the shared `Templates` library is copied beside its executable.

Windows production builds must run on 64-bit Windows 10/11 with Python 3.10+ and internet access for the first dependency installation. SQL Server use requires Microsoft ODBC Driver 18, installed separately. Packaged app users do not need Python.

Project files, app connection settings, and secrets remain in their established user-selected/local credential locations; secrets are not bundled into the build.
