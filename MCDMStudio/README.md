# MCDMStudio

MCDMStudio teaches numerical multi-criteria methods with an Excel input, method-specific intermediate tables, book locations, and a **Python audit** tab. The audit tab shows the calculation function used by the engine and can copy it or export it as `.py` / `.txt`.

## Included methods

| Group | Methods | Input model |
|---|---|---|
| Criterion weights | AHP, ANP, SWARA, BWM, Shannon entropy, CRITIC, MEREC, Standard deviation, PSI | Pairwise comparisons/ranked criteria or numeric decision matrix |
| Alternative ranking | SAW, TOPSIS, MOORA, MULTIMOORA, COPRAS-G, ARAS, WASPAS, VIKOR, ELECTRE I, PROMETHEE II, CoCoSo, EDAS, MARCOS, CODAS, MAIRCA, MABAC, GRA | Numeric alternative × criterion matrix with Benefit/Cost directions |
| Causal / structural | DEMATEL, ISM | DEMATEL direct influence matrix (0–4); ISM SSIM (`V/A/X/O`) |

## Workbook

Open `Templates/Template/MCDMStudio/MCDM_Input_Template.xlsx` or the synthetic example at `Templates/Demo Data/MCDMStudio/MCDM_Demo_Data.xlsx`. Optional method sheets are included for AHP, SWARA, DEMATEL, ISM, and ANP. Blank method-specific sheets are ignored until filled. The DEMATEL and ISM nodes map to the criterion names; rename them in the sheets to model factors instead.

## Book coverage and variants

The implementation follows J. J. Thakkar, *Multi-Criteria Decision Making* (Springer, 2021): SAW (Ch. 2), AHP (Ch. 3), ANP limit priorities (Ch. 4), TOPSIS (Ch. 5), ELECTRE I (Ch. 6), PROMETHEE II (Ch. 7), VIKOR (Ch. 8), DEMATEL (Ch. 9), MOORA / MULTIMOORA components (Ch. 11), COPRAS-G (Ch. 13), ARAS (Ch. 14), WASPAS (Ch. 15), SWARA (Ch. 16), and ISM (Ch. 18). Additional methods from original research papers include BWM, Entropy, CRITIC, MEREC, CoCoSo, EDAS, MARCOS, CODAS, MAIRCA, MABAC, Grey Relational Analysis, PSI, and standard-deviation weighting.

The book also covers LINMAP (Ch. 12), Graph Theoretic Analysis (Ch. 17), grey/fuzzy techniques (Chs. 10, 19–21), and integrated methods. These are not represented as ordinary decision-matrix rankings: LINMAP needs elicited pairwise preferences and ideal-point fitting; GTA needs graph structure and attribute/edge weights; fuzzy-grey variants and hybrid methods need additional data types and model choices. They remain outside this numeric release.

## Method-specific notes

- **AHP:** geometric-mean row approximation and consistency ratio are shown. Uses Saaty RI values.
- **ANP:** calculates limiting priorities from an already weighted, column-stochastic supermatrix. The workbook does not automate cluster modeling and all local pairwise comparisons.
- **SAW:** Chapter 2's worked cost normalization is followed so lower cost scores better. The chapter's summary list contains AHP consistency steps, which is noted in the UI.
- **ELECTRE I:** produces an outranking relation and may leave alternatives incomparable. Default concordance/discordance thresholds are the mean off-diagonal indices.
- **PROMETHEE II:** uses the simplified linear preference function in the book's §7.2, not the six generalized preference shapes.
- **DEMATEL:** uses the conventional total relation matrix `T = D(I−D)⁻¹`. The book's typeset equation on p. 141 omits the final `−I` adjustment in one rendering.
- **ISM:** computes transitive closure and iterative level partitions; expert judgments and model validation remain in the user's SSIM sheet.
- **MULTIMOORA:** displays ratio, reference-point, and full multiplicative components. The final ordering here uses rank-sum for transparency; the classic variant uses dominance theory.
- **COPRAS-G:** the book's variant is interval-based; scalar values are interpreted as degenerate intervals `[x, x]`.
- **SWARA:** the book presents a procedure figure; the UI displays the standard coefficient and normalized-weight arithmetic implementing those steps.
- **WASPAS:** exposes λ (default 0.5). The book's variance-based λ optimization is not silently substituted.
- **BWM:** uses Rezaei's linear minimax formulation. Best and worst criteria are explicitly marked in the workbook.
- **CoCoSo:** combines the weighted sum, power measure, and three compromise appraisals. λ defaults to 0.5.
- **CRITIC / MEREC:** objective weighting methods; unlike AHP/BWM/SWARA, weights are derived from the supplied alternative matrix.
- **PSI:** derives objective weights from criterion preference variation. Negative preference indices are truncated to zero to satisfy the app’s nonnegative-weight contract; the raw values remain visible for audit.
- **MABAC:** ranks by signed distance from each criterion’s geometric-mean border approximation area.
- **GRA:** calculates grey relational coefficients relative to a benefit-oriented ideal sequence, then aggregates them using the selected weights.
- **CODAS:** τ defaults to 0.02; the value is user-adjustable in the method control.

## Run and test

Install the root `requirements.txt`, then run `python MCDMStudio/main.py`; on Windows use `MCDMStudio/run.bat`. `python -m unittest MCDMStudio.tests.test_methods MCDMStudio.tests.test_stress_methods -v` runs deterministic examples, randomized stress cases, structural-method checks, and audit-source compilation.

Educational implementation: verify assumptions, judgment consistency, and method variants before using results in a study.

## References

- Thakkar, J. J. (2021). *Multi-Criteria Decision Making*. Springer. https://doi.org/10.1007/978-981-33-4745-8
- Roy, B. (1968). *Classement et choix en présence de points de vue multiples*. Revue française d'informatique et de recherche opérationnelle. https://www.numdam.org/item/RO_1968__2_1_57_0/
- Brans, J.-P., & Vincke, P. (1985). A preference ranking organisation method. *Management Science, 31*(6), 647–656. https://doi.org/10.1287/mnsc.31.6.647
- Warfield, J. N. (1974). Toward interpretation of complex structural models. *IEEE Transactions on Systems, Man, and Cybernetics, SMC-4*(5), 405–417. https://doi.org/10.1109/TSMC.1974.4309336
- Gabus, A., & Fontela, E. (1972). *World Problems: An Invitation to Further Thought within the Framework of DEMATEL*. Battelle Geneva Research Centre.
- Shannon, C. E. (1948). A mathematical theory of communication. *Bell System Technical Journal, 27*(3), 379–423. https://doi.org/10.1002/j.1538-7305.1948.tb01338.x
- Rezaei, J. (2015). Best-worst multi-criteria decision-making method. *Omega, 53*, 49–57. https://doi.org/10.1016/j.omega.2014.11.009
- Diakoulaki, D., Mavrotas, G., & Papayannakis, L. (1995). Determining objective weights in multiple criteria problems: The CRITIC method. *Computers & Operations Research, 22*(7), 763–770. https://doi.org/10.1016/0305-0548(94)00059-H
- Keshavarz-Ghorabaee, M., Amiri, M., Zavadskas, E. K., Turskis, Z., & Antucheviciene, J. (2021). Determination of objective weights using a new method based on the removal effects of criteria (MEREC). *Symmetry, 13*(4), 525. https://doi.org/10.3390/sym13040525
- Maniya, K. D., & Bhatt, M. G. (2010). A selection of material using a novel type decision-making method: Preference selection index method. *Materials & Design, 31*(4), 1785–1789. https://doi.org/10.1016/j.matdes.2009.11.020
- Yazdani, M., Zarate, P., Zavadskas, E. K., & Turskis, Z. (2019). A combined compromise solution (CoCoSo) method for multi-criteria decision-making problems. *Management Decision, 57*(9), 2501–2519. https://doi.org/10.1108/MD-05-2017-0458
- Keshavarz-Ghorabaee, M., Zavadskas, E. K., Olfat, L., & Turskis, Z. (2015). Multi-criteria inventory classification using a new method of evaluation based on distance from average solution (EDAS). *Informatica, 26*(3), 435–451. https://doi.org/10.15388/Informatica.2015.57
- Stević, Ž., Pamučar, D., Puška, A., & Chatterjee, P. (2020). Sustainable supplier selection in healthcare industries using a new MCDM method: MARCOS. *Computers & Industrial Engineering, 140*, 106231. https://doi.org/10.1016/j.cie.2019.106231
- Keshavarz-Ghorabaee, M., Zavadskas, E. K., Turskis, Z., & Antuchevičienė, J. (2016). A new combinative distance-based assessment (CODAS) method for multi-criteria decision-making. *Economic Computation and Economic Cybernetics Studies and Research, 50*(3), 25–44.
- Pamučar, D., & Ćirović, G. (2015). The selection of transport and handling resources in logistics centers using Multi-Attributive Border Approximation area Comparison (MABAC). *Expert Systems with Applications, 42*(6), 3016–3028. https://doi.org/10.1016/j.eswa.2014.11.057
- Deng, J. (1989). Introduction to grey system theory. *The Journal of Grey System, 1*(1), 1–24.
