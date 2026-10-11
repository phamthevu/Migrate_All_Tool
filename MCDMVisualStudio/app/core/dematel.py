"""Core DEMATEL calculations from a final total influence matrix T."""
from __future__ import annotations

import numpy as np


def compute_dematel_from_total(T: np.ndarray, labels: list[str]):
    t = np.asarray(T, dtype=float)
    if t.ndim != 2 or t.shape[0] != t.shape[1] or t.shape[0] != len(labels):
        raise ValueError("The total influence matrix must be square and match the factor labels.")
    if not np.isfinite(t).all():
        raise ValueError("The total influence matrix contains missing or non-finite values.")
    if (t < -1e-12).any():
        raise ValueError("Influence values must be non-negative.")
    t = np.maximum(t, 0.0)
    R = t.sum(axis=1)
    C = t.sum(axis=0)
    prominence = R + C
    relation = R - C
    denom = float(prominence.sum())
    weight = prominence / denom if denom > 0 else np.zeros_like(prominence)
    order = np.argsort(-weight, kind="stable")
    rank = np.empty(len(labels), dtype=int)
    rank[order] = np.arange(1, len(labels) + 1)
    group = ["Cause" if value > 1e-12 else "Effect" if value < -1e-12 else "Neutral" for value in relation]
    return [{"Factor": str(name), "R": float(R[i]), "C": float(C[i]),
             "R+C": float(prominence[i]), "R-C": float(relation[i]),
             "Weight": float(weight[i]), "Rank": int(rank[i]), "Group": group[i]}
            for i, name in enumerate(labels)]


