"""Direction-aware ranking utilities and pairwise rank correlations."""
from __future__ import annotations
import numpy as np


def rank_values(values, higher_is_better=True):
    """Ranks with 1 as best and average ranks for ties."""
    x = np.asarray(values, dtype=float)
    order = np.argsort(-x if higher_is_better else x, kind="stable")
    ranks = np.empty(len(x), dtype=float)
    pos = 0
    while pos < len(order):
        end = pos + 1
        while end < len(order) and x[order[end]] == x[order[pos]]:
            end += 1
        average_rank = ((pos + 1) + end) / 2.0
        ranks[order[pos:end]] = average_rank
        pos = end
    return ranks


def directions_from_names(names):
    """Infer conservative defaults; callers can override in the UI."""
    lower_tokens = ("rank", "distance to ideal", "positive ideal", "cost", "error", "loss", "d+", "d plus")
    return [not any(token in str(name).lower() for token in lower_tokens) for name in names]


def pairwise_rank_correlations(values, names, higher_is_better=None):
    """Return rank vectors and Spearman/Kendall tau-b correlation matrices."""
    x = np.asarray(values, dtype=float)
    if x.ndim != 2 or x.shape[1] != len(names):
        raise ValueError("Ranking data must be alternatives × result columns.")
    if not np.isfinite(x).all():
        raise ValueError("Ranking data must contain finite numeric values only.")
    directions = directions_from_names(names) if higher_is_better is None else list(higher_is_better)
    if len(directions) != x.shape[1]:
        raise ValueError("Provide one ranking direction per result column.")
    n, m = x.shape
    ranks = np.column_stack([rank_values(x[:, j], directions[j]) for j in range(m)])
    spearman = np.eye(m, dtype=float)
    kendall = np.eye(m, dtype=float)
    for a in range(m):
        for b in range(a + 1, m):
            ra, rb = ranks[:, a], ranks[:, b]
            if n < 2 or np.std(ra) == 0 or np.std(rb) == 0:
                sp = np.nan
            else:
                sp = float(np.corrcoef(ra, rb)[0, 1])
            concordant = discordant = ties_a = ties_b = 0
            for i in range(n - 1):
                da = ra[i] - ra[i + 1:]
                db = rb[i] - rb[i + 1:]
                same_a, same_b = da == 0, db == 0
                ties_a += int(np.count_nonzero(same_a & ~same_b))
                ties_b += int(np.count_nonzero(same_b & ~same_a))
                product = da * db
                concordant += int(np.count_nonzero(product > 0))
                discordant += int(np.count_nonzero(product < 0))
            denom = np.sqrt((concordant + discordant + ties_a) * (concordant + discordant + ties_b))
            kt = float((concordant - discordant) / denom) if denom else np.nan
            spearman[a, b] = spearman[b, a] = sp
            kendall[a, b] = kendall[b, a] = kt
    return {"ranks": ranks, "spearman": spearman, "kendall": kendall,
            "directions": directions, "names": [str(v) for v in names]}
