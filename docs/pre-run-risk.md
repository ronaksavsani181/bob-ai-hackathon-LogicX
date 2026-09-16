# Pre-Run Risk Model

## Purpose

The pre-run risk model scores an upcoming lot before it starts processing, based solely on information available at scheduling time. A high risk score triggers an early warning so the engineer can intervene — reschedule, route to a different chamber, or place the lot on hold.

## Safety Rule: No Future Data Leakage

**This is the single most important constraint of the pre-run model.**

The model may ONLY use features that are:
1. Set at lot creation time (product, technology node, priority, planned start).
2. Derived from the historical record of the chambers and equipment that will process the lot — as of the lot's `planned_start_at` timestamp.

The following are **explicitly forbidden** as predictive features:
- `die_yield` (target lot future yield)
- `defect_count` (future inspection results)
- `overlay_error_nm` (future metrology)
- `maintenance_event_after_planned_start` (future maintenance)
- Any column with a timestamp after `planned_start_at`

### Enforcement Mechanism

A `PRE_RUN_FEATURE_WHITELIST` constant in [`scenarios.py`](../src/backend/data/synthetic/scenarios.py) lists every permitted feature. The `audit_for_leakage()` function in [`pre_run_risk.py`](../src/backend/app/services/pre_run_risk.py) checks every column in the feature matrix against this whitelist. If any forbidden column is present, it raises a hard `ValueError` — not a warning. This is called at training time and at inference time. It is also covered by automated unit tests.

## Feature Whitelist

```python
PRE_RUN_FEATURE_WHITELIST = [
    "lot_priority",             # 0=low, 1=normal, 2=high
    "product_encoded",          # category code
    "technology_node_encoded",  # category code
    "planned_recipe_encoded",   # category code (from lot plan)
    "planned_chamber_encoded",  # category code (from lot plan)
    "chamber_yield_30d",        # trailing 30-day chamber mean yield (pre-start)
    "days_since_last_pm",       # days since last PM on assigned chamber
    "chamber_ooc_rate_30d",     # out-of-control parameter rate (trailing 30d)
    "queue_time_planned_h",     # planned queue time in hours
]
```

## Model

**Algorithm:** `GradientBoostingClassifier` (scikit-learn, `random_state=42`).

**Training:**
1. All completed lots with known yield outcomes are used as the training set.
2. Label: `1` if `die_yield < fleet_mean - 1.5 * fleet_std`, else `0`.
3. Features: whitelist columns only (after `audit_for_leakage()` call).
4. Chronological split: the most recent 20% of lots are held out as a test set for performance reporting (not used in production scoring).

**Output:**
- `risk_score`: probability of the positive class [0, 1].
- `risk_class`: `"low"` (< 0.4), `"medium"` (0.4–0.7), `"high"` (> 0.7).
- `top_features`: top feature importances from the trained model.

## Limitations in This Prototype

- **No caching:** The model is retrained from scratch on every HTTP request. In production, the model would be trained on a schedule and cached.
- **Constant derived features:** `chamber_yield_30d`, `days_since_last_pm`, and `chamber_ooc_rate_30d` are approximated with constants in this prototype because those join-based computations are expensive. In production, these would be pre-computed as rolling aggregates.
- **No cross-validation or hyperparameter tuning:** Default GBM parameters are used.
- **Class imbalance:** The dataset is not balanced. In production, a proper class-weighting strategy would be needed.

## How to Interpret the Output

A `risk_class = "high"` means the model has assigned a probability > 0.7 that this lot will produce yield below the excursion threshold, based on pre-run features. It does NOT mean the lot WILL fail. It means the lot's pre-run characteristics historically correlate with lower yield.

Engineers should treat high-risk scores as a trigger for enhanced monitoring or pre-emptive chamber checks — not as a guaranteed prediction.
