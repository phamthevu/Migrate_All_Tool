STUDIO TEMPLATE LIBRARY

Template/ contains blank input workbooks for user entry. Reference scales and generator configuration sheets remain pre-filled because their values define the method. Demo Data/ contains populated example workbooks; synthetic examples are labeled and must not be reported as empirical results.

Folders are grouped by app and workflow: DataStudio (MCDM, Quanti, DEA, Bootstrap), FuzzyStudio (Spherical, Quantum, Neutrosophic, Z-Delphi), and MCDMVisualStudio (DEMATEL matrix and final rankings), ResearchStudio (project/import workbooks), and MCDMStudio (numeric method input).

For DEA, use the Data sheet and keep DMU_ID unique. Input columns start with Input_; desirable outputs start with Output_. For Bootstrap, import both an Ans workbook and the fuzzy-scale reference workbook.

MCDMStudio has two blank workbook templates:
- MCDM_TOPSIS_Input_Template.xlsx: alternatives in rows and factors in columns. Use for TOPSIS-style ranking and criterion-weight methods.
- MCDM_DEMATEL_Input_Template.xlsx: factors in both rows and columns. Use for DEMATEL direct influence scores.

Input cells are pale yellow. Header and fixed cells use blue/gray styling. Matching demo workbooks are in Demo Data/MCDMStudio/ and contain synthetic data. Each MCDMStudio workbook includes a Method Guide sheet that maps worksheets to the methods that use them; each worksheet also has a note in cell A1. In the app, choose a method to see its required sheets and open its primary sheet. Every sheet's cell values can be edited in the app, then saved and processed in one action. The Decision Matrix is shared by all alternative-ranking methods; DEMATEL uses its separate factor-by-factor template.
