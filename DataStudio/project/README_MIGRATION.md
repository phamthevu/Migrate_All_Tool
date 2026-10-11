# DataStudio

One desktop app with four workspaces:

- **MCDM**: configure, generate, validate, preview, and export MCDM data.
- **Quanti**: generate quantitative survey data and run quantitative analysis.
- **DEA**: Input & Preview, Model & Formula, Results Preview, and Generate Data tabs. Import validation is shown as a readable banner; the blank template contains Guide + Data sheets, and generated input cells are highlighted.
- **Bootstrap**: Import & Preview, Settings & Formula, and Results & Export tabs. The formula guide explains `l`, `m`, `u`, `**`, and sample defuzzification formulas; results include an IRM image preview and separate Excel/image exports.

The original MCDM/Quanti engines and the supplied DEA and Bootstrap numerical engines are retained. DEA and Bootstrap are integrated into the same Tkinter workspace shell. MCDM settings now sit beside the preview in a resizable horizontal pane so they cannot cover it.

## Run on Windows

1. Install 64-bit Python 3.10 or newer and enable **Add Python to PATH**.
2. Run `install.bat` once.
3. Run `run.bat`.

The app requires internet access during initial dependency installation. Once installed, it runs locally. Bootstrap DEMATEL needs both an expert-response workbook and a fuzzy-scale workbook. DEA needs a workbook following the provided DEA template format (`Data`, optional `Config`, and optional `Variables` sheets).

## Build an executable

Run `build.bat` after `install.bat`. The PyInstaller build file is updated to collect the integration code and Bootstrap's plotting dependency. Check `dist\DemoDataStudio.exe` on a clean Windows account before distribution.

