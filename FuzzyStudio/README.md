# FuzzyStudio

FuzzyStudio brings the fuzzy calculators, VBA function catalog, and equation converter under one navigation window.

- **Spherical Fuzzy**, **Quantum Spherical**, and **Neutrosophic Z** tabs open the supplied calculators with their original operations, formulas, batch aggregation, and workbook templates.
- **VBA Guide** indexes all `.bas` declarations, including PFS/ProPFS, NEU/NEI, BCLDFN, and ISM. Select a function or procedure to see its source-based purpose, signature, arguments, dependencies, setup steps, and example call.
- **VBA Code** displays the selected module and highlights the selected Function/Sub.
- **LaTeX ↔ Word** converts common math syntax into Word's linear equation input and back.

## Run on Windows

1. Install 64-bit Python 3.10 or newer.
2. Open a terminal in this folder and run `python -m pip install -r requirements.txt`.
3. Run `python main.py`.

The app has one VBA Guide and a separate source tab. The fuzzy calculators open as separate windows from their tabs to preserve each original calculator's full workflow and avoid changing its mathematical engine. Word conversion currently handles common scalar expressions; nested fractions, matrices, and advanced LaTeX environments require review.

The VBA Guide is generated from the included `.bas` declarations. Import dependent modules together (for example `GetMemberFunction.bas` plus `CalculateFunction.bas`) into an `.xlsm` workbook. Review each procedure's source comments and cell/range assumptions before running macros that write into a worksheet.
