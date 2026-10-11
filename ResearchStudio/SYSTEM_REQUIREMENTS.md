# System Requirements — Research Studio V7.1

## Windows production
- Windows 10/11 x64
- Python 3.10+ only for source/development builds; end users of the packaged EXE do not need Python.
- Microsoft ODBC Driver 18 for SQL Server is required only for SQL Server connectivity.
- Windows Credential Manager is used via Python `keyring` for DB/SMTP/S3/Azure/token secrets.

## Runtime data locations
- Project `.mcdm`: user-selected location.
- `%LOCALAPPDATA%\ResearchStudio\connections.json`: non-secret connection settings only.
- `%LOCALAPPDATA%\ResearchStudio\instance.json`: machine/instance identity.
- Windows Credential Manager: secrets.

## Dependency profiles
- `requirements-core.txt`: desktop + Excel core.
- `requirements-standard.txt`: core + PostgreSQL/SQL Server/MySQL/S3 (recommended normal deployment).
- `requirements.txt`: all supported optional connectors.
