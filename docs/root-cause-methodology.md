# Root Cause Methodology

## Guiding Principles

1. **No LLM.** Root causes are never generated, suggested, or scored by a language model. All ranking is deterministic.
2. **Evidence attribution.** Every candidate carries `evidence_ids` linking to the specific records that contributed.
3. **Transparent scoring.** Weights are public constants in `services/root_cause.py`. Any engineer can inspect, challenge, or override them.
4. **Not confirmation.** Output is described as "the highest-ranked candidates based on available evidence." The word "confirmed" is never used.
5. **Human approval required.** No automated action is taken based on root-cause output.

## Signal Inventory

The fusion engine aggregates seven independent evidence signals:

| Signal ID | Source Service | Measures |
|---|---|---|
| `yield_excursion` | `anomaly.detect_yield_excursion` | How far below baseline the lot yield is (MAD σ) |
| `param_anomaly` | `anomaly.detect_parameter_anomalies` | Max z-score of process parameters (normalised 0–1) |
| `chamber_recurrence` | `recurrence.analyze_chamber_recurrence` | Systematic yield deficit on the processing chamber |
| `maintenance_proximity` | `temporal.analyze_maintenance_proximity` | Post-PM yield shift severity + temporal precedence |
| `defect_pattern` | `defect_pattern.classify_lot_defect_patterns` | Pattern strength score |
| `similar_lot` | `similar_lot.find_similar_lots` | Yield outcome from historically similar lots |
| `queue_time` | computed in router from lot metadata | Exposure-time correlation with yield outcome |

## Cause Type Vocabulary

All root-cause candidates are drawn from a fixed vocabulary. New cause types can only be added by code change — never by dynamic text generation.

| Cause Type | Description |
|---|---|
| `etch_drift` | Gradual drift in etch rate or uniformity on an etch tool chamber |
| `overlay_excursion` | Lithography overlay error outside specification |
| `particle_contamination` | Particle-induced defects, often spatially clustered |
| `maintenance_shift` | Post-maintenance instability period (seasoning / conditioning) |
| `chamber_recurrence` | Systematic yield deficit recurring specifically on one chamber |
| `temporal_exposure` | Queue-time or exposure-time related yield degradation |
| `unknown` | No single cause type reaches significance threshold |

## Fusion Algorithm

```python
# Pseudo-code — see services/root_cause.py for full implementation

WEIGHTS = {
    "yield_excursion":       0.20,
    "param_anomaly":         0.20,
    "chamber_recurrence":    0.25,
    "maintenance_proximity": 0.15,
    "defect_pattern":        0.10,
    "similar_lot":           0.05,
    "queue_time":            0.05,
}

for cause_type in CAUSE_VOCABULARY:
    signal_scores = compute_signals_for(cause_type)
    fusion_score = sum(WEIGHTS[s] * signal_scores[s] for s in signal_scores)
    fusion_score /= sum(WEIGHTS[s] for s in signal_scores)
    confidence = min(1.0, (len(contributing_signals) / 4) * fusion_score)

candidates = sorted(candidates, key=lambda c: c.score, reverse=True)[:3]
```

## Output Schema

Each of the Top-3 candidates contains:

| Field | Type | Description |
|---|---|---|
| `rank` | int | 1, 2, or 3 |
| `cause_id` | str | Deterministic ID for this result |
| `cause_type` | str | From controlled vocabulary |
| `cause_description` | str | Human-readable, templated (not generated) |
| `score` | float | Fusion score [0, 1] |
| `confidence` | float | Adjusted confidence [0, 1] |
| `evidence_ids` | list[str] | IDs of contributing evidence records |
| `supporting_signals` | dict | Signal name → contributing score |
| `contradicting_signals` | dict | Signal name → negative evidence |
| `temporal_precedence` | bool | True if cause preceded the yield drop |
| `model_version` | str | Algorithm version string |
| `generated_at` | datetime | UTC timestamp |

## What This Is NOT

- Not a root-cause confirmation system.
- Not a causal inference engine.
- Not trained on any real fab dataset.
- Not a replacement for engineering judgment.

The output should be read as: "Given the available evidence, the system's highest-ranked hypothesis is X with score Y. An engineer should investigate whether this hypothesis is consistent with their own knowledge of the equipment and process history."
