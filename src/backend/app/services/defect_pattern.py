"""
app/services/defect_pattern.py — Wafer defect spatial-pattern classifier.

Algorithm version: defect_pattern_v1

PROTOTYPE DISCLAIMER:
The pattern-detection thresholds in this module are heuristics developed for
the S1 hackathon prototype.  They have NOT been validated against production
semiconductor defect data and should NOT be used as production-certified
defect classification.

The classifier operates purely on defect (x, y) coordinates.
It does NOT read scenario labels or ground-truth metadata.

Supported patterns
------------------
center_heavy      : defects concentrate near the wafer centre (r < 40 mm)
edge_ring         : defects concentrate in an annular edge band (r > 120 mm)
localized_hotspot : tight cluster in one area, not centre or edge
radial            : defects align along radial spokes
scratch_line      : defects form a near-linear streak (PCA axis ratio test)
uniform           : no strong spatial signature (catch-all)
insufficient_data : fewer than MIN_DEFECTS to classify

Algorithm summary
-----------------
1.  Compute radial distances r = sqrt(x² + y²) for all defects.
2.  center_ratio  = fraction with r < 40 mm
3.  edge_ratio    = fraction with r > 120 mm
4.  DBSCAN (eps=10 mm, min_samples=3) → largest_cluster_fraction
5.  radial_score  = angular entropy test (low entropy → spokes)
6.  scratch_score = PCA axis ratio (largest eigenvalue / second eigenvalue)

Decision rules (applied in priority order — first match wins):
  scratch_line      : scratch_score > SCRATCH_THRESHOLD
  center_heavy      : center_ratio > CENTER_THRESHOLD
  edge_ring         : edge_ratio   > EDGE_THRESHOLD
  localized_hotspot : largest_cluster_fraction > CLUSTER_THRESHOLD
                      AND center_ratio < CENTER_THRESHOLD
  radial            : radial_score > RADIAL_THRESHOLD
  uniform           : none of the above
"""
from __future__ import annotations

import math
from datetime import timezone
from typing import Any

import numpy as np
import pandas as pd

from app.services.evidence import (
    VERSIONS,
    DefectPatternResult,
    _utcnow,
    make_evidence_id,
)

# ---------------------------------------------------------------------------
# Documented thresholds
# ---------------------------------------------------------------------------
MIN_DEFECTS = 5            # minimum defect count to attempt classification
WAFER_RADIUS_MM = 150.0

CENTER_THRESHOLD  = 0.45   # fraction of defects in r < 40 mm
EDGE_THRESHOLD    = 0.40   # fraction of defects in r > 120 mm
CLUSTER_THRESHOLD = 0.55   # fraction of defects in largest DBSCAN cluster
RADIAL_THRESHOLD  = 0.65   # low angular entropy score
SCRATCH_THRESHOLD = 6.0    # PCA major/minor eigenvalue ratio

CENTER_RADIUS_MM = 40.0
EDGE_RADIUS_MM   = 120.0

# DBSCAN
DBSCAN_EPS_MM    = 10.0
DBSCAN_MIN_SAMP  = 3


def _pca_axis_ratio(xs: np.ndarray, ys: np.ndarray) -> float:
    """
    Compute the ratio of the largest to second-largest PCA eigenvalue.

    A high ratio (> SCRATCH_THRESHOLD) indicates that the defect cloud is
    strongly elongated in one direction — consistent with a scratch or line.

    Returns 1.0 if fewer than 3 points or matrix is degenerate.
    """
    if len(xs) < 3:
        return 1.0
    data = np.column_stack([xs, ys])
    data -= data.mean(axis=0)
    cov = np.cov(data.T)
    if cov.ndim < 2:
        return 1.0
    eigvals = np.linalg.eigvalsh(cov)
    eigvals = np.sort(eigvals)[::-1]  # descending
    if eigvals[1] < 1e-9:
        return float(eigvals[0] / 1e-9)
    return float(eigvals[0] / eigvals[1])


def _angular_entropy_score(
    xs: np.ndarray,
    ys: np.ndarray,
    n_bins: int = 16,
) -> float:
    """
    Compute a normalised angular entropy score.

    Low score → defects concentrate in a few angular bins → radial/spoke pattern.
    High score → defects spread uniformly across all angles → no radial pattern.

    Returns a value in [0, 1].  Values below RADIAL_THRESHOLD suggest a radial pattern.
    Formula: H_norm = H / log2(n_bins)  where H is Shannon entropy of the angle histogram.
    """
    if len(xs) < MIN_DEFECTS:
        return 1.0  # default to no-radial-signal
    angles = np.arctan2(ys, xs)  # in [-π, π]
    hist, _ = np.histogram(angles, bins=n_bins, range=(-math.pi, math.pi))
    hist = hist + 1e-9   # Laplace smoothing to avoid log(0)
    hist = hist / hist.sum()
    entropy = -np.sum(hist * np.log2(hist))
    return float(entropy / math.log2(n_bins))


def _dbscan_largest_cluster_fraction(
    xs: np.ndarray,
    ys: np.ndarray,
    eps: float = DBSCAN_EPS_MM,
    min_samples: int = DBSCAN_MIN_SAMP,
) -> float:
    """
    Run DBSCAN and return the fraction of defects in the largest cluster.

    Uses a pure-numpy distance matrix approach to avoid scikit-learn import
    for minimal-dependency compatibility; falls back to sklearn if available.
    """
    n = len(xs)
    if n < min_samples:
        return 0.0

    # Pairwise distance matrix
    coords = np.column_stack([xs, ys])
    dists = np.sqrt(((coords[:, None, :] - coords[None, :, :]) ** 2).sum(axis=2))

    # Simple BFS-based DBSCAN (avoid sklearn dependency in this service)
    labels = np.full(n, -1, dtype=int)
    cluster_id = 0
    visited = np.zeros(n, dtype=bool)

    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        neighbours = np.where(dists[i] <= eps)[0]
        if len(neighbours) < min_samples:
            labels[i] = -1  # noise
            continue
        labels[i] = cluster_id
        queue = list(neighbours)
        while queue:
            j = queue.pop(0)
            if not visited[j]:
                visited[j] = True
                j_neighbours = np.where(dists[j] <= eps)[0]
                if len(j_neighbours) >= min_samples:
                    queue.extend(j_neighbours.tolist())
            if labels[j] == -1:
                labels[j] = cluster_id
        cluster_id += 1

    if cluster_id == 0:
        return 0.0

    cluster_counts = np.bincount(labels[labels >= 0]) if (labels >= 0).any() else np.array([0])
    largest = int(cluster_counts.max())
    return float(largest / n)


def classify_defect_pattern(
    wafer_id: int,
    defect_coords: list[tuple[float, float]],
) -> DefectPatternResult:
    """
    Classify the spatial pattern of wafer defects from (x, y) coordinates.

    Parameters
    ----------
    wafer_id       : DB primary key of the wafer (used in evidence ID)
    defect_coords  : list of (x_mm, y_mm) defect positions in mm from
                     wafer centre.  Wafer radius = 150 mm.

    Returns
    -------
    DefectPatternResult

    IMPORTANT: This function does NOT read any scenario or ground-truth label.
               The 'defect_class' column in the defects table is never used here.
    """
    eid = make_evidence_id("defect", wafer_id, "spatial_pattern")

    if len(defect_coords) < MIN_DEFECTS:
        return DefectPatternResult(
            wafer_id=wafer_id,
            pattern_type="insufficient_data",
            pattern_score=0.0,
            defect_count=len(defect_coords),
            spatial_statistics={"defect_count": len(defect_coords)},
            evidence_id=eid,
            algorithm_version=VERSIONS["defect_pattern"],
        )

    xs = np.array([c[0] for c in defect_coords], dtype=float)
    ys = np.array([c[1] for c in defect_coords], dtype=float)
    r = np.sqrt(xs ** 2 + ys ** 2)
    n = len(xs)

    # --- Feature computation ---
    center_ratio   = float((r < CENTER_RADIUS_MM).sum() / n)
    edge_ratio     = float((r > EDGE_RADIUS_MM).sum() / n)
    cluster_frac   = _dbscan_largest_cluster_fraction(xs, ys)
    angular_entropy= _angular_entropy_score(xs, ys)
    scratch_score  = _pca_axis_ratio(xs, ys)
    radial_score   = 1.0 - angular_entropy  # high → radial

    stats: dict[str, float] = {
        "center_ratio":    round(center_ratio, 4),
        "edge_ratio":      round(edge_ratio, 4),
        "cluster_fraction":round(cluster_frac, 4),
        "radial_score":    round(radial_score, 4),
        "scratch_score":   round(scratch_score, 4),
        "angular_entropy": round(angular_entropy, 4),
        "mean_radius_mm":  round(float(r.mean()), 2),
        "defect_count":    float(n),
    }

    # --- Decision rules (priority order) ---
    if scratch_score >= SCRATCH_THRESHOLD:
        pattern = "scratch_line"
        score = float(min(1.0, scratch_score / (SCRATCH_THRESHOLD * 3)))
    elif center_ratio >= CENTER_THRESHOLD:
        pattern = "center_heavy"
        score = float(min(1.0, center_ratio / 0.8))
    elif edge_ratio >= EDGE_THRESHOLD:
        pattern = "edge_ring"
        score = float(min(1.0, edge_ratio / 0.8))
    elif cluster_frac >= CLUSTER_THRESHOLD and center_ratio < CENTER_THRESHOLD:
        pattern = "localized_hotspot"
        score = float(min(1.0, cluster_frac / 0.9))
    elif radial_score >= RADIAL_THRESHOLD:
        pattern = "radial"
        score = float(min(1.0, radial_score / 0.9))
    else:
        pattern = "uniform"
        # Score = how close to perfectly uniform (low cluster, low center, low edge)
        uniformity = 1.0 - max(center_ratio, edge_ratio, cluster_frac, radial_score)
        score = float(max(0.0, uniformity))

    return DefectPatternResult(
        wafer_id=wafer_id,
        pattern_type=pattern,
        pattern_score=round(score, 4),
        defect_count=n,
        spatial_statistics=stats,
        evidence_id=eid,
        algorithm_version=VERSIONS["defect_pattern"],
    )


def classify_lot_defect_patterns(
    lot_wafer_ids: list[int],
    defects_df: pd.DataFrame,
    sample_wafers: int = 5,
) -> list[DefectPatternResult]:
    """
    Classify defect patterns for up to `sample_wafers` wafers in a lot.

    Parameters
    ----------
    lot_wafer_ids : list of wafer DB IDs belonging to the target lot
    defects_df    : defects DataFrame with columns [wafer_id, x_coord, y_coord]
    sample_wafers : max wafers to classify (first N by wafer_id)

    Returns list of DefectPatternResult — one per sampled wafer.
    """
    selected = lot_wafer_ids[:sample_wafers]
    results: list[DefectPatternResult] = []
    for wid in selected:
        wdefects = defects_df[defects_df["wafer_id"] == wid]
        coords = list(zip(wdefects["x_coord"].tolist(), wdefects["y_coord"].tolist()))
        results.append(classify_defect_pattern(wid, coords))
    return results
