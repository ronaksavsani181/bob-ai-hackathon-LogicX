"""
app/services/similar_lot.py — Historical similar-lot finder.

Algorithm version: similar_lot_v1

Finds historically completed lots whose pre-run feature profile is most
similar to the target lot.  Similarity is measured by cosine distance in
StandardScaler-normalised feature space.

IMPORTANT:
- The target lot itself is EXCLUDED from the similarity fit.
- Only pre-run-safe features (PRE_RUN_FEATURE_WHITELIST) are used.
- Analytics services must NOT import from data/synthetic/scenarios.py.
- No FastAPI, no DB session, no side effects.

Notes
-----
Cosine similarity is chosen over Euclidean distance because it is scale-
invariant along the magnitude dimension; two lots with identical parameter
ratios but different magnitudes will still be similar.  StandardScaler is
applied first so that all features contribute equally.

Reference: Tan, Steinbach, Kumar – "Introduction to Data Mining" ch. 8.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from app.services.evidence import (
    VERSIONS,
    SimilarLotResult,
    _utcnow,
    make_evidence_id,
)

# ---------------------------------------------------------------------------
# Documented thresholds
# ---------------------------------------------------------------------------

# Minimum number of historical lots required to perform similarity search
MIN_HISTORY_LOTS = 15

# Number of similar lots to return
TOP_K = 5

# Minimum cosine similarity to be considered "similar"
MIN_SIMILARITY = 0.70

# Features used for similarity — must match what is available at run time
_SIMILARITY_FEATURES: list[str] = [
    "lot_priority",
    "product_encoded",
    "technology_node_encoded",
    "planned_recipe_encoded",
    "planned_chamber_encoded",
    "chamber_yield_30d",
    "days_since_last_pm",
    "chamber_ooc_rate_30d",
    "queue_time_planned_h",
]


def _safe_cosine(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cosine similarity between two vectors.

    Returns 0.0 if either vector is the zero vector (degenerate case).
    """
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def find_similar_lots(
    target_lot_id: str,
    target_features: dict[str, float],
    historical_lots_df: pd.DataFrame,
    top_k: int = TOP_K,
) -> list[SimilarLotResult]:
    """
    Find the most similar historical lots to the target lot.

    Parameters
    ----------
    target_lot_id     : business key of the lot under investigation
    target_features   : dict of pre-run feature name → value for the target lot
    historical_lots_df : DataFrame of completed lots with columns:
                          [lot_id_str, die_yield, chamber_name, tool_name,
                           recipe_name, <feature columns from _SIMILARITY_FEATURES>]
                         Must NOT include the target lot.
    top_k             : maximum number of similar lots to return

    Returns
    -------
    List of SimilarLotResult, sorted by similarity_score descending.
    Empty list if insufficient history.

    Algorithm
    ---------
    1.  Drop rows with any NaN in feature columns.
    2.  StandardScaler-normalise the historical feature matrix.
    3.  Apply the same mean/std to the target feature vector.
    4.  Compute cosine similarity of target vs each historical lot.
    5.  Return top_k lots with similarity ≥ MIN_SIMILARITY.
    """
    # Identify which feature columns are present in historical_lots_df
    avail_features = [f for f in _SIMILARITY_FEATURES if f in historical_lots_df.columns]

    if len(avail_features) == 0:
        return []

    # Build the target vector from available features
    target_vec = np.array(
        [float(target_features.get(f, 0.0)) for f in avail_features],
        dtype=float,
    )

    # Drop rows with NaN in any feature column
    hist = historical_lots_df.dropna(subset=avail_features).copy()

    if len(hist) < MIN_HISTORY_LOTS:
        return []

    # Ensure target lot not in history
    if "lot_id_str" in hist.columns:
        hist = hist[hist["lot_id_str"] != target_lot_id]

    if len(hist) < MIN_HISTORY_LOTS:
        return []

    feature_matrix = hist[avail_features].values.astype(float)

    # StandardScaler: fit on historical data only
    col_mean = feature_matrix.mean(axis=0)
    col_std  = feature_matrix.std(axis=0)
    col_std[col_std < 1e-9] = 1.0  # avoid division by zero for constant columns

    scaled_matrix = (feature_matrix - col_mean) / col_std
    scaled_target = (target_vec - col_mean) / col_std

    # Compute cosine similarity for each historical lot
    similarities = np.array(
        [_safe_cosine(scaled_target, row) for row in scaled_matrix],
        dtype=float,
    )

    # Sort by descending similarity and take top_k above threshold
    sorted_idx = np.argsort(similarities)[::-1]
    results: list[SimilarLotResult] = []

    for idx in sorted_idx[:top_k]:
        sim_score = float(similarities[idx])
        if sim_score < MIN_SIMILARITY:
            break

        row = hist.iloc[int(idx)]
        lot_id_str = str(row.get("lot_id_str", "unknown"))
        die_yield  = float(row.get("die_yield", float("nan")))

        common_chamber = (
            str(row["chamber_name"]) if "chamber_name" in row.index else None
        )
        common_tool = (
            str(row["tool_name"]) if "tool_name" in row.index else None
        )
        common_recipe = (
            str(row["recipe_name"]) if "recipe_name" in row.index else None
        )

        eid = make_evidence_id("lot", lot_id_str, f"similar_to_{target_lot_id}")
        results.append(SimilarLotResult(
            target_lot_id=target_lot_id,
            similar_lot_id=lot_id_str,
            similarity_score=round(sim_score, 4),
            common_chamber=common_chamber,
            common_tool=common_tool,
            common_recipe=common_recipe,
            historical_yield=round(die_yield, 4) if not np.isnan(die_yield) else float("nan"),
            distance_method="cosine_similarity_standardscaler",
            evidence_id=eid,
            algorithm_version=VERSIONS["similar_lot"],
        ))

    return results
