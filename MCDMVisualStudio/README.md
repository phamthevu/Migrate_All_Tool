# MCDMVisualStudio

A desktop analysis and visualization app for final numeric DEMATEL and ranking results. It includes Data and Visual workspaces with a shared studio banner.

## Input formats

### DEMATEL INRM

Import the **final total influence matrix T**. The first row contains factor names, the first column repeats those names in the same order, and the inside cells contain numeric influence values. Example layout:

|   | Factor A | Factor B | Factor C |
|---|---:|---:|---:|
| Factor A | 0.12 | 0.31 | 0.08 |
| Factor B | 0.17 | 0.09 | 0.22 |
| Factor C | 0.03 | 0.14 | 0.11 |

The app calculates `R` as row sums, `C` as column sums, prominence `R+C`, relation `R-C`, normalized prominence weight, rank, and Cause/Effect/Neutral group. It does not recalculate T from a direct or adjacency matrix.

### TOPSIS and other final ranking results

Import `.xlsx`, `.xls`, or `.csv` with alternatives in the first column and one or more numeric result columns after it. For example:

| Alternative | Closeness coefficient | Rank |
|---|---:|---:|
| A1 | 0.72 | 1 |
| A2 | 0.48 | 3 |
| A3 | 0.61 | 2 |

Use the result-column selector to choose the score or rank to display. For `Rank`, distances to the positive ideal, cost, error, and loss columns, lower is better by default; score, closeness, weight, and distance-to-anti-ideal columns default to higher is better. You can change the direction manually. For method comparison, use one numeric score/rank column per method (for example, `TOPSIS`, `AHP`, `WASPAS`).

## Charts

- **DEMATEL:** INRM influence network, prominence–relation quadrants, total influence heatmap, and prominence ranking.
- **Rankings:** score bars, lollipop, ranked dot plot, multi-metric profile, rank-change slope chart, and Spearman ρ / Kendall τ-b correlation heatmaps across result columns.

The INRM uses actual `R+C` and `R-C` coordinates. Each directed edge represents `T[i,j]` (factor i influences factor j). Configure increasing/decreasing axes, range padding, jitter, minimum influence, per-source Top-K, Top-N nodes, node size, arrowhead size, node shapes, weight-driven size/opacity, and weight labels. Toggle factor names and the `R-C = 0` and middle-prominence reference lines. The **Arrow intervals** tab lets you edit each influence bin's bounds, opacity (0–20), and dash style (0–20). Cause, effect, and neutral nodes use different symbols and colors. Reciprocal arrows curve to opposite sides. Hover a node or edge to inspect its values; click a node to highlight its incoming/outgoing links. Labels are auto-spaced and can be dragged; their positions remain until reset.

## Export

Select **Export figure** from the Visual tab. PNG export prompts for image width (800–8000 px) and uses a white background. SVG export preserves vector shapes and text for editing in illustration software. The export includes the current chart and title.

## Run

```bash
python -m pip install -r ..\requirements.txt
python -m app.main
```

Install the suite-root `requirements.txt` once, then run `run_windows.bat`. The complete suite is packaged with `build_all_windows.bat`.

You can also run either command from the project folder; direct script launch also works from the `app` folder or via its full path:

```bash
python -m app.main
python app/main.py
```

From the `app` folder, `python main.py` is supported too.

Python 3.10 or newer is recommended.
