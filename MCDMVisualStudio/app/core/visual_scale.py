import numpy as np

def min_mid_max(values: np.ndarray):
    vmin = float(np.min(values))
    vmax = float(np.max(values))
    vmid = (vmin + vmax) / 2.0
    return vmin, vmid, vmax

def compute_edges(vmin: float, vmax: float, bins: int):
    bins = max(2, min(20, int(bins)))
    edges = np.linspace(vmin, vmax, bins + 1).tolist()
    return edges

def bin_index(value: float, edges: list[float]):
    bins = len(edges) - 1
    if bins <= 0:
        return 0
    if value <= edges[0]:
        return 0
    if value >= edges[-1]:
        return bins - 1
    for i in range(bins):
        if edges[i] <= value < edges[i + 1]:
            return i
    return bins - 1