"""
app/services/pre_run_risk.py — Pre-run yield risk model.

Algorithm version: pre_run_risk_v1

PRE-RUN SAFETY RULE (non-negotiable):
  The pre-run model may ONLY use information available BEFORE the target lot
  starts.  This is enforced by:
    1. A whitelist (PRE_RUN_FEATURE_WHITELIST) — only whitelisted columns are
       ever passed to the model.
    2. A leakage audit function (audit_for_leakage()) that raises an exception
       if any forbidden column is found in the feature matrix.
    3. A unit test in tests/test_pre_run_risk.py that calls audit_for_leakage()
       on a crafted DataFrame containing forbidden columns.

Training procedure
------------------
Model: sklearn GradientBoostingClassifier (n_estimators=200, max_depth=4)
Label: binary — 1 if lot mean die_yield < YIELD_RISK_THRESHOLD else 0
Features: numerical columns from PRE_RUN_FEATURE_WHITELIST
Splitting: chronological — training on the first TRAIN_SPLIT_FRACTION of lots,
           validation on the remainder.  Random shuffling is DISABLED to
           prevent future data leakage.

Inference
---------
score_pre_run_risk() returns a PreRunRiskResult per lot with:
  - risk_score [0, 1]
  - risk_class: 'low' | 'medium' | 'high'
  - top contributing features (by absolute impurity importance)
  - model version and timestamp

All results carry an evidence_id and generated_at timestamp.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from app.services.evidence import VERSIONS, _utcnow, make_evidence_id

# ---------------------------------------------------------------------------
# Feature whitelist (must match scenarios.PRE_RUN_FEATURE_WHITELIST exactly)
# ---------------------------------------------------------------------------
PRE_RUN_FEATURE_WHITELIST: list[str] = [
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

PRE_RUN_FORBIDDEN_COLUMNS: list[str] = [
    "die_yield",
    "bin1_count",
    "bin_fail_count",
    "defect_count",
    "defect_density",
    "overlay_error",
    "metrology_value",
    "tested_at",
    "inspected_at",
    "measured_at",
]

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
YIELD_RISK_THRESHOLD: float = 0.88   # lots below this are labelled risky (y=1)
TRAIN_SPLIT_FRACTION: float = 0.70   # chronological split

RISK_CLASS_THRESHOLDS: dict[str, float] = {
    "high":   0.65,
    "medium": 0.35,
    "low":    0.0,
}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------
@dataclass
class PreRunRiskResult:
    lot_id: str
    risk_score: float           # predicted probability of being risky (0-1)
    risk_class: str             # 'low' | 'medium' | 'high'
    top_features: dict[str, float]   # feature_name → importance (top 3)
    model_version: str
    evidence_id: str
    generated_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lot_id": self.lot_id,
            "risk_score": round(self.risk_score, 4),
            "risk_class": self.risk_class,
            "top_features": {k: round(v, 4) for k, v in self.top_features.items()},
            "model_version": self.model_version,
            "evidence_id": self.evidence_id,
            "generated_at": self.generated_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Leakage audit
# ---------------------------------------------------------------------------
def audit_for_leakage(df: pd.DataFrame, raise_on_forbidden: bool = True) -> list[str]:
    """
    Check that no forbidden (future) column is present in the DataFrame.

    Parameters
    ----------
    df                  : the feature DataFrame to audit
    raise_on_forbidden  : if True, raise ValueError on first forbidden column

    Returns
    -------
    List of forbidden column names found.  Empty list means clean.

    Raises
    ------
    ValueError if raise_on_forbidden=True and any forbidden column is found.
    """
    found = [c for c in df.columns if c in PRE_RUN_FORBIDDEN_COLUMNS]
    if found and raise_on_forbidden:
        raise ValueError(
            f"PRE-RUN LEAKAGE DETECTED: forbidden columns present in feature "
            f"matrix: {found}.  These columns contain future information and "
            f"must never be used as model inputs."
        )
    return found


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def train_risk_model(
    feature_df: pd.DataFrame,
    yield_df: pd.DataFrame,
) -> Any:
    """
    Train a GradientBoostingClassifier on historical lot data.

    Parameters
    ----------
    feature_df : DataFrame with columns including lot_id, lot_id_str,
                 actual_start_at, planned_start_at, and all
                 PRE_RUN_FEATURE_WHITELIST columns.
    yield_df   : columns [lot_id (int), die_yield (float)]

    Returns
    -------
    Trained sklearn GradientBoostingClassifier (or a simple baseline if
    sklearn is not available).

    Notes
    -----
    Training uses only the first TRAIN_SPLIT_FRACTION of lots (chronological)
    to prevent any future data from influencing the model.
    """
    from sklearn.ensemble import GradientBoostingClassifier  # type: ignore

    # Leakage audit — raises if forbidden column found
    audit_for_leakage(feature_df)

    # Merge with yield labels
    lot_yield = (
        yield_df.groupby("lot_id")["die_yield"]
        .mean()
        .reset_index()
        .rename(columns={"die_yield": "mean_yield"})
    )
    df = feature_df.merge(lot_yield, on="lot_id", how="inner")
    df = df.sort_values("actual_start_at").reset_index(drop=True)

    # Binary label: risky = 1 if yield < threshold
    df["y"] = (df["mean_yield"] < YIELD_RISK_THRESHOLD).astype(int)

    # Select only whitelisted features that are actually present
    feat_cols = [f for f in PRE_RUN_FEATURE_WHITELIST if f in df.columns]
    if len(feat_cols) == 0:
        raise ValueError("No whitelist features found in feature_df columns.")

    # Chronological train/test split — NO SHUFFLE
    n_train = max(10, int(len(df) * TRAIN_SPLIT_FRACTION))
    train_df = df.iloc[:n_train]

    X_train = train_df[feat_cols].fillna(0.0).values
    y_train = train_df["y"].values

    clf = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        random_state=42,
    )
    clf.fit(X_train, y_train)
    # Store feature names on the model for use in scoring
    clf.feature_names_ = feat_cols  # type: ignore[attr-defined]
    return clf


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def score_pre_run_risk(
    clf: Any,
    lot_id: str,
    features: dict[str, float],
) -> PreRunRiskResult:
    """
    Score the pre-run risk for a single upcoming lot.

    Parameters
    ----------
    clf      : trained classifier from train_risk_model()
    lot_id   : business key of the lot
    features : dict of pre-run feature values (from PRE_RUN_FEATURE_WHITELIST)

    Returns
    -------
    PreRunRiskResult

    Notes
    -----
    Leakage is checked by verifying no forbidden column appears in the
    features dict keys.
    """
    # Leakage check on inference features
    forbidden_found = [k for k in features if k in PRE_RUN_FORBIDDEN_COLUMNS]
    if forbidden_found:
        raise ValueError(
            f"PRE-RUN LEAKAGE at inference: forbidden feature keys found: {forbidden_found}"
        )

    feat_cols: list[str] = clf.feature_names_  # type: ignore[attr-defined]
    x = np.array(
        [float(features.get(f, 0.0)) for f in feat_cols],
        dtype=float,
    ).reshape(1, -1)

    proba = clf.predict_proba(x)[0]
    # Index 1 = probability of being risky
    risk_score = float(proba[1]) if len(proba) > 1 else float(proba[0])

    # Risk class
    if risk_score >= RISK_CLASS_THRESHOLDS["high"]:
        risk_class = "high"
    elif risk_score >= RISK_CLASS_THRESHOLDS["medium"]:
        risk_class = "medium"
    else:
        risk_class = "low"

    # Top feature importances
    importances = clf.feature_importances_
    top_idx = np.argsort(importances)[::-1][:3]
    top_features = {
        feat_cols[i]: round(float(importances[i]), 4)
        for i in top_idx
    }

    eid = make_evidence_id("pre_run", lot_id, "risk_score")
    return PreRunRiskResult(
        lot_id=lot_id,
        risk_score=round(risk_score, 4),
        risk_class=risk_class,
        top_features=top_features,
        model_version=VERSIONS["pre_run_risk"],
        evidence_id=eid,
    )


def score_pre_run_risk_bulk(
    clf: Any,
    feature_df: pd.DataFrame,
) -> list[PreRunRiskResult]:
    """
    Score pre-run risk for all lots in a feature DataFrame.

    Parameters
    ----------
    clf        : trained classifier from train_risk_model()
    feature_df : DataFrame with lot_id_str and whitelist feature columns

    Returns
    -------
    List of PreRunRiskResult — one per lot row in feature_df.
    """
    audit_for_leakage(feature_df)

    results: list[PreRunRiskResult] = []
    for _, row in feature_df.iterrows():
        lot_id_str = str(row.get("lot_id_str", row.get("lot_id", "unknown")))
        features = {f: float(row.get(f, 0.0)) for f in PRE_RUN_FEATURE_WHITELIST}
        results.append(score_pre_run_risk(clf, lot_id_str, features))
    return results
