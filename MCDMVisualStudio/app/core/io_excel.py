"""Strict readers for final DEMATEL matrices and numeric ranking results."""
from __future__ import annotations
import numpy as np
import pandas as pd


def _read_labeled_square(path: str, sheet=0):
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    if df.shape[0] < 2 or df.shape[1] < 2:
        raise ValueError("Expected a labeled matrix: labels in the first row and first column.")
    headers = df.iloc[0, 1:].dropna().astype(str).str.strip().tolist()
    n = len(headers)
    if n == 0:
        raise ValueError("No column labels found in the first row.")
    data = df.iloc[1:1+n, 1:1+n]
    row_names = df.iloc[1:1+n, 0].astype(str).str.strip().tolist()
    if len(row_names) != n or any(not s or s.lower() == "nan" for s in row_names):
        raise ValueError("Row labels are missing or do not match the number of columns.")
    if len(set(headers)) != n or len(set(row_names)) != n:
        raise ValueError("Labels must be unique.")
    if row_names != headers:
        raise ValueError("Row and column labels must have the same order.")
    try:
        matrix = data.apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
    except Exception as exc:
        raise ValueError("Matrix cells must contain numeric values only.") from exc
    if not np.isfinite(matrix).all():
        raise ValueError("Matrix has blank or non-finite values.")
    return headers, matrix


def load_total_influence_matrix(path: str, sheet=0):
    return _read_labeled_square(path, sheet)


def load_ranking_results(path: str, sheet=0):
    """Read final numeric method outputs (alternative rows, metric columns).

    Accepts .xlsx/.xls/.csv. The first column contains alternative names; all
    remaining columns are final numeric scores, weights, distances, or ranks.
    """
    if str(path).lower().endswith(".csv"):
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path, sheet_name=sheet)
    df = df.dropna(how="all").dropna(axis=1, how="all")
    if df.shape[1] < 2:
        raise ValueError("Ranking input needs an alternative column and at least one numeric result column.")
    names = [str(v).strip() for v in df.iloc[:, 0].tolist()]
    if any(not s or s.lower() == "nan" for s in names):
        raise ValueError("Alternative names cannot be blank.")
    if len(set(names)) != len(names):
        raise ValueError("Alternative names must be unique.")
    columns = [str(c).strip() for c in df.columns[1:]]
    try:
        values = df.iloc[:, 1:].apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
    except Exception as exc:
        raise ValueError("All result columns after the alternative name must be numeric.") from exc
    if not np.isfinite(values).all():
        raise ValueError("Ranking results contain blank or non-finite numeric values.")
    return names, columns, values
