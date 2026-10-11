# Windows production build — V7.1

Recommended first release: PyInstaller **onedir**, not onefile. It starts faster, is easier to diagnose, and avoids repeatedly unpacking connector libraries.

## Runtime locations
- `.mcdm`: user-selected project location.
- Non-secret app config: `%LOCALAPPDATA%\ResearchStudio\connections.json`
- Machine identity: `%LOCALAPPDATA%\ResearchStudio\instance.json`
- Secrets: Windows Credential Manager via `keyring` service `ResearchStudio`.
- No credentials are bundled in the EXE/spec.

## Dependency strategy
`requirements-core.txt` is the small desktop core. `requirements-connectors.txt` contains optional connector packages. `requirements.txt` installs the full supported build. A production installer may offer connector feature packs later; V7.1 full build keeps all currently supported connectors for compatibility.

## SQL Server
Install Microsoft ODBC Driver 18 for SQL Server separately. It is an OS dependency and cannot be supplied by pip/PyInstaller.

## Build
Run PowerShell on Windows:
`./build_windows.ps1`

Do not cross-build the Windows EXE from Linux. Build and smoke-test on Windows.
