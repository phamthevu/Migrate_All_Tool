RESEARCH SUITE — SOURCE PACKAGE

Applications
- ResearchStudio: manage research projects and data collection.
- DataStudio: sample data and foundational data analysis.
- FuzzyStudio: practice foundational Fuzzy methods.
- MCDMStudio: guided numeric practice for weighting and ranking methods.
- MCDMVisualStudio: visualize analysis results.

Build
- Windows 10/11 x64; Python 3.10+; internet connection for first dependency install.
- Install/build dependencies from the single root requirements.txt.
- Run build_all_windows.bat once to create the five applications under dist/.
- SQL Server connectivity in ResearchStudio additionally requires Microsoft ODBC Driver 18.

Workbook library
- Templates/Template contains blank input workbooks.
- Templates/Demo Data contains example data. Synthetic examples are labeled in the workbook.
- The build copies this shared library beside each built app.

MCDMStudio methods
- Criterion weights: AHP, ANP, SWARA, BWM, Shannon entropy, CRITIC, MEREC, standard deviation, and PSI.
- Alternative ranking: SAW, TOPSIS, MOORA, MULTIMOORA, COPRAS-G, ARAS, WASPAS, VIKOR, ELECTRE I, PROMETHEE II, CoCoSo, EDAS, MARCOS, CODAS, MAIRCA, MABAC, and GRA.
- Causal / structural analysis: DEMATEL and ISM.
- Every selected method exposes a Python audit tab with copy and `.py` / `.txt` export actions. The workbook contains dedicated judgment sheets for DEMATEL, ISM, and ANP.
- Import the MCDMStudio workbook, choose a method, view each formula and intermediate table, then export the calculation trail to Excel.
- See MCDMStudio/README.md for method-specific reading notes.

Build scope
- The FuzzyStudio research articles/manuscript PDFs and DOCX files are not included in this source package because they are not application code, workbook templates, or build inputs. The original files remain in the workspace.
- The Windows executables are built on Windows; no Windows binaries are included here.
