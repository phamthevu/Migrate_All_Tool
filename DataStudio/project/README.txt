V5.3.1 FACTOR SETUP
Generate tab: click Factor setup to configure each factor in a visible table.
Cause / effect and prominence are independent. HIGH / MEDIUM / LOW choose coarse
weight strength. AUTO derives strength from numeric Weight below the table.
RANK derives strength from Rank (1 = strongest, ties allowed). Rank must be in
1..factor count. Set RANK for factors whose rank should determine strength;
manual HIGH / MEDIUM / LOW overrides rank for that factor. Rank is a soft latent
prominence target, not an exact output rank guarantee. Cause / effect is checked
on actual R-C; rank never assigns that role. All settings save to config/session.

V5.3 DIRECTED DEMATEL DEMO

Open a workbook from Templates/Template/DataStudio/MCDM (or its example in Templates/Demo Data)
as an MCDM configuration. Select DEMATEL. The method-specific factor panel has:
- Prominence: AUTO, HIGH, MEDIUM, LOW. HIGH / LOW are checked relative to mean R+C.
- Role: AUTO, CAUSE, EFFECT, BALANCED. Explicit role checks use the sign of R-C.
- Strength: 0..1 controls the outgoing / incoming latent contrast, not an exact achieved R-C target.
AUTO prominence uses coarse relative weights; AUTO roles alternate independently.
MEDIUM is a soft generation tendency without an exact rank gate.
BALANCED allows abs(R-C)/(R+C) <= 0.1.
DEMATEL uses coarse groups; Order's exact rank gate is disabled for this method.
Only DEMATEL displays these controls. Configuration and sessions retain profiles.

Each directed edge uses BOTH its source activity and target receptivity, plus
shared edge structure and respondent variation. The generator computes normalized
X and total influence T=X inverse(I-X), then checks actual cause / prominence.
Agreement uses per-answer R+C scores when profiles are configured. Pearson and
Spearman min/max still apply to all answer pairs. Impossible targets return best
effort, with failed checks in the separate validation report. Aggregate targets
are checked again on the mean direct matrix; individual successes alone do not
claim aggregate success. Runtime is bounded by the existing attempt limit.

Scalar methodology: Level must be nonnegative. Normalizer is max of maximum row
and column sums; spectral convergence is checked. Weight=(R+C)/sum(R+C).
A fuzzy output is a LABEL representation mapped to Level for scalar validation;
this is NOT a spherical-fuzzy DEMATEL analysis and does not replace a private UDF.
The accompanying workbook makes that distinction explicit and removes external
UDF dependencies from its revised calculation. Editing ANS labels recalculates
Direct Scores, Calculation and the editable scatter chart. Editing configuration
targets requires regeneration in the app. Four regions split at mean R+C and 0;
raw prominence cannot be negative. ISS2 is a high-weight effect, ISS5 low cause.

Legacy API calls without profiles preserve the previous factor-agreement semantics;
the UI always supplies the directed DEMATEL profile configuration.

V5.2 MCDM TWO-SIDED AGREEMENT
- UI: independent Pearson min/max and rank Spearman min/max.
  Defaults: Pearson .65–.90, Spearman .60–.95, initial consensus .78.
- All unordered answer pairs are checked, excluding matrix diagonals.
  Pearson applies to numeric cells and factor scores; rank Spearman to factors.
- Max below 1 rejects exact duplicate numeric answers. Spearman max below 1
  also rejects identical factor rank order, even if magnitudes differ.
- Two-sided feedback increases respondent heterogeneity above max and shared
  tendency below min. Consensus is an initial proposal strength, not the
  measured agreement, and no longer increases monotonically towards 1.
- AHP varies respondent preferences around configured weights, keeps reciprocal
  matrices and checks CI/CR. Preference variation differs from judgment noise.
- Fallback: closest to the requested intervals, then fewer failed checks,
  per answer; failures and duplicates remain labeled and exportable.
- Report: observed min/max, configured targets, individual range PASS/FAIL,
  duplicate flags and full Cell Pearson / Factor Pearson / Factor Spearman.
- Strict pairwise bounds can be infeasible with few criteria, discrete/tied
  ranks, many answers, or strict Order constraints. Best effort is not a PASS.
- Older sessions gain new max defaults when absent. CODE-only data export and
  separate validation export remain available. Quantitative engines unchanged.

V5.1.1 SPEED / EXPORT FIX
Generation bootstrap defaults to 100; choose 50 or 100 in Advanced.
Existing generation configurations above 100 are capped at 100 for inference;
requested/used counts are both recorded. CSV options also offer 50 or 100 (engine accepts 50–5000).
Point-screen candidates without bootstrap. Confirm at most three promising
candidates during search, then infer the selected best candidate if necessary.
At exhaustion, keep/export best effort even when checks fail. A failed or
incomplete bootstrap is labeled explicitly; unavailable p-values are NaN.
Status separates attempt x/y, bootstrap b/B and final selection.
Cancel Advanced generation after a candidate exists keeps the best result;
export works after the task stops. Incomplete bootstrap is labeled INCOMPLETE.
Selection uses R first, then failed point checks; Final Selection records the
final complete checks after bootstrap. Data is never labeled passing prematurely.

V5.1 GENERATION UPDATE
- Signal calibrated to observed R/R2; finite-sample predictor/noise orthogonalization
  reduces accidental correlations, VIF inflation and reliability drift.
- Adaptive measurement and path parameters use observed Alpha, beta and R2.
- Every assessed candidate is retained for selection; stop when all required
  criteria pass. At exhaustion, export the best assessed candidate.
- Fallback ranking: highest minimum endogenous R first, then fewest required
  failed checks. R outside the configured range still fails that check.
- PLS candidates use full-refit bootstrap, including best-effort candidates.
- Acceptance and Generation Search identify failures, selected attempt and status.
  Unavailable fit statistics remain NaN; never label unestimated models as passing.
- MCDM uses two-sided agreement feedback; fallback minimizes range deviation
  then failed checks per answer. CI/CR remain independently checked.
- Invalid inputs and deliberate cancellation still stop; conflicting statistical
  goals produce best-effort results. CSV analysis remains on original observations.

DEMO DATA STUDIO 5.3 — NEW REPOSITORY SOURCE

START
Windows source run: install the suite-root requirements.txt once, then run this folder\run.bat. For the complete build, run build_all_windows.bat from the suite root.
The shared root build_all_windows.bat builds all five studios and fuzzy calculators together.
Shared templates are in Templates/Template and Templates/Demo Data.
Linux/macOS source run: install the suite-root requirements.txt and run python main.py. Tkinter/Tcl/Tk must be installed by the OS/Python distribution.

REPO
Extract project/ and use its contents as the root of your new repository.
Use the suite-root requirements.txt, shared Template and Demo Data library, and build_all_windows.bat.
No inherited Git history, environment, build output, cache, test/log files.
Create the remote repo yourself, then git init/add/commit and push as usual.

V5
- Three workspaces: MCDM Generator, Quantitative Generator, Quantitative Analysis.
- CSV import requires model choice; drag CSV columns into the analysis canvas,
  build arrows, edit R/R² ranges and run Regression / CB-SEM / PLS-SEM.
- Imported observations are analyzed once and never adjusted to pass targets.
  Failed criteria remain visible and exportable. Separate generated/CSV results.
- MCDM contextual controls, resizable/collapsible settings, CODE-only data export
  and a separate validation-report workbook (no duplicate Numeric sheets).
- Teaching presets, generation preflight and settings-only session recovery.
- Quick Quantitative: configurable CB-SEM fit/loading/reliability/discriminant/path rules.
- Advanced: CB-SEM, reflective ordinary PLS-SEM, nonlinear/hierarchical regression.
- Model Designer: shared graph, arrows, drag, properties, undo/redo, zoom/pan,
  layout, model JSON, PNG/SVG.
- R or R² min/max per endogenous construct, visible directly in Advanced.
- R defaults in Quick Quantitative and Advanced; both R and R² in output reports.
- All UI labels, help, progress messages and validation dialogs are English.
- Updated indigo/navy theme, clearer outcome targets, fixed Advanced action bar,
  mouse-wheel scrolling and settings preserved when changing tabs.
- VIF gate and separate measurement/path goals.
- Reports computed from generated observed data; never substitute target for actual.

SOURCE MAP
main.py                 Tk entry point
gui/app.py              Existing MCDM/Quantitative/convert workflow and worker queue
gui/criteria_panel.py   Threshold editor shared by Quick Quantitative and Advanced
gui/advanced.py         Advanced settings, reports, export and stale-result guard
gui/model_designer.py   Canvas/properties editor and atomic diagram exports
core/csv_analysis.py     CSV validation, explicit missing policy, one-pass analysis
core/presets.py          Teaching model presets
core/preflight.py        Conflicts and heuristic generation warnings
core/session.py          Atomic settings-only recovery JSON
gui/csv_panel.py         CSV options, mapping, results and exports
gui/column_palette.py    Drag CSV columns into shared model graph
gui/session_manager.py   Autosave and explicit session restore
gui/workspace.py         Grouped navigation
core/model_spec.py      Versioned graph/schema, validation, undo/redo, fingerprints
core/criteria.py        Fixed rule direction, required flags, acceptance table
core/advanced_generate.py  Latent synthesis, candidate search, bootstrap streams
core/cbsem.py            Covariance ML SEM, latent R²/VIF, fit/admissibility checks
core/plssem.py           Mode A/path weighting algorithm and full-refit bootstrap
core/analysis_common.py  Measurement, terms, OLS/HC3, block tests, indirect products
core/quantitative.py    Quick Cronbach/EFA/Pearson/OLS and CB adapter
core/batch.py           MCDM consensus and acceptance
core/delivery.py        Excel report maps and AMOS data bundle
core/exporter.py        Atomic Excel writes

R / R² TARGETS
Advanced has an Outcome targets card. Select R or R², then set Min and Max for
each endogenous construct. Example: R .55–.65 means R² .3025–.4225.
Switching the selector converts the range to preserve its meaning. The diagram
properties editor has the same selector and target range. Targets are persisted
in JSON with canonical R² bounds and optional r_metric; older V4 JSON remains
compatible. R is model multiple correlation, not a pairwise Pearson correlation.
CB-SEM R is derived from implied latent R²; PLS R from converged composite R²;
regression R from OLS R². Pairwise Pearson is reported separately.
Maximum supported R² is below .95 (R below .97468); incompatible targets can fail.
Leaving Advanced applies pending settings to the shared model. Export checks the
current analytical settings. To reproduce results, use the metadata effective seed.

V5.1 VALIDATION
23 automated regression/scenario tests passed, plus 18 Likert7 runs across
three quantitative engines (six seeds each) passed within the test budget.
Windows EXE was not built or run here.

PREVIOUS VALIDATION
V3 regression checks and V4 scenario checks passed locally, plus scripted Tk UI
interaction on Linux. Source compiled successfully. See HUONG_DAN.txt for precise
acceptance rules and limitations. Windows EXE and proprietary AMOS/SmartPLS runs
were not tested here; PyInstaller builds for the OS on which it runs.

Scope: DAG, reflective CB/PLS, linear SEM. Nonlinear terms are regression only.
Ordinary PLS is not PLSc. No formative/higher-order latent/multigroup, Q²/PLSpredict,
or arbitrary SEM fit guarantees. Likert CB uses continuous-ML approximation.
Unreliable advanced constructs remain in the model and may make CB inadmissible;
Quick Quantitative explicitly excludes rejected groups from its retained SEM.
Generated data and metadata are marked SYNTHETIC DEMO for teaching/practice.

CSV WORKFLOW & LIMITS
Quantitative Analysis -> Load CSV -> select model type (no implicit default).
Choose empty diagram or reuse shared model. Model Builder: Ctrl/Shift-select
CSV columns in the palette, drag onto blank canvas to create a variable, or
onto a construct to assign indicators. Draw arrows with Connect; use Properties
for R/R² targets and source-column removal. Options sets scale and thresholds. Uncheck Import settings to expand results.
Regression supports a single observed column per variable; its alpha/CR/AVE
are reported N/A. Reflective CB/PLS requires 3–10 indicators per construct.
Supports 100–10,000 retained rows (CB >=200), up to 12 constructs /80 indicators.
CSV <=32 MB, <=2,000 columns, unique nonempty headers. Numeric mapped columns
only; unused columns ignored. Reject missing values unless explicitly choosing
complete-case deletion; excluded original data-row numbers are reported.
Defaults target Likert responses; use CONTINUOUS for other numeric values.
Import records source SHA256 and mapping; canonical indicator names are used
in analysis output. Pearson is reported separately from model R=sqrt(R²).
Model Builder and Generator share one graph; changes invalidate previous results.
Save/export the desired model before replacing it with a preset or empty diagram.
Imported regression uses the same OLS/HC3, measurement and path reports as Advanced.
Quick Quantitative remains the workflow for EFA/KMO/Bartlett generation checks.
Imported SEM analysis does not perform a separate EFA or force any test to pass.

SESSIONS
Autosave every 15 seconds while idle; Restore autosave is explicit. Save/Open
session JSON stores raw input settings, diagram/assignments and source paths,
not source CSV contents or completed results. Keep original sources available.
A changed checksum is flagged. A missing CSV must be reopened before analysis.
Default state: APPDATA (Windows), XDG_STATE_HOME or ~/.local/state (other OS).
Set DEMO_DATA_STATE_DIR to override. Previous save retained as .bak.
Preflight warnings are heuristics, not a guarantee that statistical targets coexist.

V5 VALIDATION
21 backend test cases cover legacy generation, all three analysis engines,
R ranges, CSV preservation/failures, observed regression, input rejection,
model mapping/history/session and MCDM workbook separation. Scripted Tk UI
checks cover model editing, generation, CSV analysis/export and recovery on Linux.
Windows EXE build and proprietary AMOS/SmartPLS execution were not run here.
