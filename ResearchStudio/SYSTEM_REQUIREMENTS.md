# ResearchStudio requirements

- Windows 10/11 x64 for the packaged release.
- Python 3.10+ and internet access when building from source.
- The suite-root `requirements.txt` is the sole Python dependency manifest for all five Studios and all supported ResearchStudio connectors.
- Microsoft ODBC Driver 18 is an OS-level prerequisite for the SQL Server connector; pip/PyInstaller cannot replace it.
- Packaged app users do not need Python.
