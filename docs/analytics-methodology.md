# Analytics Methodology

> **Disclaimer:** All algorithms in this prototype are implemented for demonstration purposes using synthetic data. Thresholds, weights, and parameters have not been validated against real fab data and do not represent production-certified methods.

## 1. Yield Excursion Detection

**File:** [`src/backend/app/services/anomaly.py`](../src/backend/app/services/anomaly.py)

**Algorithm:** Median Absolute Deviation (MAD)

The MAD is used instead of mean/std because it is robust to outliers — a real fab history may contain extreme excursion events that would inflate a standard-deviation baseline.

```
baseline_yield = median(historical_lot_yields[t < lot_start_at])
MAD = median(|historical_lot_yields - baseline_yield|)
deviation_sigma = (observed_yield - baseline_yield) / (1.4826 * MAD)
```

The 1.4826 scale factor makes MAD consistent with Gaussian σ under normality.

**Excursion thresholds:**
- `|σ| > 2.5` → mild
- `|σ| > 3.5` → moderate  
- `|σ| > 5.0` → severe

Minimum 10 historical lots required; returns `insufficient_data` otherwise.

---

## 2. Process Parameter Anomaly Detection

**File:** [`src/backend/app/services/anomaly.py`](../src/backend/app/services/anomaly.py)

**Algorithm:** Z-score per parameter across the historical run population.

For each parameter seen in the lot's runs:
```
z = (observed_value - baseline_mean) / baseline_std
```

`baseline_mean` and `baseline_std` are computed from all runs of the same parameter across the entire historical population (excluding the lot under investigation).

**Thresholds:**
- `|z| > 3.0` → flagged, severity = "mild"
- `|z| > 4.5` → severity = "moderate"
- `|z| > 6.0` → severity = "severe"

---

## 3. Wafer Defect Spatial Pattern Classification

**File:** [`src/backend/app/services/defect_pattern.py`](../src/backend/app/services/defect_pattern.py)

Defect coordinates (x, y) in mm from wafer centre are used to classify the spatial signature. Five patterns are recognised:

| Pattern | Detection Method |
|---|---|
| `center_heavy` | > 40% of defects within r < 0.4 × wafer_radius |
| `edge_ring` | > 40% of defects with r > 0.8 × wafer_radius |
| `localized_hotspot` | BFS clustering finds a single cluster containing > 50% of defects within a compact region |
| `radial` | Angular entropy < 1.5 bits (defects cluster on specific angular sectors) |
| `scratch_line` | PCA aspect ratio > 5:1 (defect cloud is highly elongated) |
| `uniform` | None of the above thresholds met |

Angular entropy is computed over 8 angular sectors (each 45°).

BFS clustering uses a grid-based adjacency approach rather than scikit-learn DBSCAN to avoid the dependency on spatial indexing overhead.

These heuristics are not production-certified defect classification methods. They are implemented to demonstrate that the system can detect known spatial signatures in synthetic data.

---

## 4. Chamber Recurrence Analysis

**File:** [`src/backend/app/services/recurrence.py`](../src/backend/app/services/recurrence.py)

For each chamber, the algorithm computes:
1. The mean yield of all lots that processed at least one wafer in that chamber.
2. The fleet mean yield across all lots.
3. The yield gap: `fleet_mean - chamber_mean`.
4. A recurrence score: `tanh(yield_gap / fleet_std * 2)` normalised to [0, 1].

A chamber is flagged as recurrent if:
- `yield_gap > 0.04` (4 percentage points below fleet mean), AND
- At least 5 lots have used the chamber.

The `tanh` normalisation prevents a single extreme event from saturating the score.

---

## 5. Temporal Precedence & Maintenance Proximity

**File:** [`src/backend/app/services/temporal.py`](../src/backend/app/services/temporal.py)

For each maintenance event on a chamber used by the target lot:
1. Find all lots processed on that chamber within ±14 days of the maintenance event.
2. Compare their mean yield to the chamber's baseline (pre-maintenance, 30-day window).
3. A `shift_score` is computed: `tanh(|yield_delta| / fleet_std * 3)`.
4. `temporal_precedence = True` if the maintenance event precedes the lot start.

This signal feeds into root-cause fusion as evidence of a post-maintenance instability.

---

## 6. Similar-Lot Historical Matching

**File:** [`src/backend/app/services/similar_lot.py`](../src/backend/app/services/similar_lot.py)

Feature vector for each lot:
- Normalised yield (z-score within product family)
- Mean parameter deviation (z-score)
- Defect density
- Chamber yield gap (of the primary chamber used)

Similarity is measured by cosine similarity after StandardScaler normalisation. The top-5 most similar historical lots are returned with their known outcomes, providing analogy-based evidence.

---

## 7. Evidence Fusion & Root-Cause Ranking

**File:** [`src/backend/app/services/root_cause.py`](../src/backend/app/services/root_cause.py)

Seven signals are combined using fixed weights. The weights reflect the relative diagnostic strength of each signal type. They are hard-coded constants — not trained parameters.

| Signal | Default Weight | Description |
|---|---|---|
| yield_excursion | 0.20 | Severity of the yield drop |
| param_anomaly | 0.20 | Process parameter deviation strength |
| chamber_recurrence | 0.25 | Systematic yield deficit on the chamber |
| maintenance_proximity | 0.15 | Temporal proximity to PM event |
| defect_pattern | 0.10 | Spatial defect signature match |
| similar_lot | 0.05 | Analogy with known-outcome lots |
| queue_time | 0.05 | Exposure time correlation |

For each candidate cause type, scores are fused:
```
final_score = Σ (signal_weight × signal_score) / Σ signal_weights
confidence = min(1.0, (evidence_count / 4) * final_score)
```

Results are sorted by `final_score` descending. The top 3 are returned with full evidence attribution.

**Critical rule:** The fusion function never calls an LLM. It never accepts free-text input as a cause. Cause types are drawn from a fixed vocabulary: `etch_drift`, `overlay_excursion`, `particle_contamination`, `maintenance_shift`, `chamber_recurrence`, `temporal_exposure`, `unknown`.
