# Demo Scenarios

> All scenarios are implemented using deterministic synthetic data (seed=42). They do not represent any real fabrication facility. Thresholds and parameters are for demonstration only.

## Scenario Overview

| ID | Name | Lots | Primary Signal |
|---|---|---|---|
| S-ETCH | Etch drift | L0001–L0060 | Gradual etch rate drift → yield decline |
| S-OVL | Overlay excursion | L0101–L0130 | Overlay error spike → yield step-change |
| S-PART | Particle excursion | L0201–L0240 | Particle contamination → defect surge |
| S-MAINT | Post-maintenance shift | L0413–L0428 | Post-PM instability |
| S-REC | Chamber recurrence | L0301–L0400 | Systematic yield gap on CHA-1 |
| S-TIME | Temporal/queue-time | L0451–L0475 | Long queue time correlation |
| S-CTRL | Control (normal) | All others | No injected fault — baseline reference |

---

## S-ETCH — Etch Rate Drift

**What happens:** ETCH-A/CHA-1 develops a gradual drift in etch rate starting at lot L0001. The drift is slow enough that no single lot is a catastrophic failure, but a statistical trend is visible in the yield time series.

**What the system should detect:**
- `yield_trend` endpoint shows gradual downward slope over lots L0001–L0060.
- `Investigate` screen shows parameter anomaly on `etch_rate_angs_min` with z > 3.0 for mid-range lots.
- `chamber_recurrence` analysis flags CHA-1 with a growing yield gap.
- Root-cause fusion ranks `etch_drift` as the top candidate.

**Demo steps:**
1. Monitor screen → yield trend chart shows slope change.
2. Investigate screen → select L0040 → see etch_rate z-score anomaly.
3. Evidence screen → root-cause Top-1 = etch_drift.

---

## S-OVL — Overlay Excursion

**What happens:** OVL-B/CHA-3 produces a step-change in overlay error starting at lot L0101 (step event on day 40). Lots L0101–L0130 all show elevated `overlay_error_nm`.

**What the system should detect:**
- Parameter anomaly detection flags `overlay_error_nm` with z > 4.5.
- Yield excursion detection (MAD) flags L0101–L0130 as moderate excursions.
- Root-cause fusion ranks `overlay_excursion` as top candidate.

**Demo steps:**
1. Monitor → excursion table shows L0101 cluster.
2. Investigate → select L0115 → overlay_error_nm z-score shown.
3. Wafer Pattern Lab → edge/ring or radial pattern on overlay-affected wafers.

---

## S-PART — Particle Excursion

**What happens:** CLEAN-C/CHA-5 suffers a particle event between lots L0201–L0240. Defect density spikes dramatically. Center-heavy or localized defect patterns are injected.

**What the system should detect:**
- High defect density on L0201–L0240 wafers.
- Wafer Pattern Lab shows `center_heavy` or `localized_hotspot` pattern.
- Root-cause fusion ranks `particle_contamination` as top candidate.
- Evidence screen shows pattern evidence IDs.

**Demo steps:**
1. Investigate → select L0220 → severe excursion, high defect count.
2. Wafer Pattern Lab → select L0220 → see defect pattern visualisation.
3. Evidence → root-cause Top-1 = particle_contamination.
4. Actions → create hold action, submit engineer review.

---

## S-MAINT — Post-Maintenance Shift

**What happens:** ETCH-A/CHA-2 has an unscheduled PM event at day 120 (lot ~L0408). Lots L0413–L0428 show a temporary yield dip during chamber re-conditioning.

**What the system should detect:**
- Temporal analysis detects PM event at day 120 preceding yield dip.
- `temporal_precedence = True` for L0413–L0428.
- Root-cause fusion ranks `maintenance_shift` for these lots.

**Demo steps:**
1. Investigate → select L0420 → observe yield dip, low parameter anomaly.
2. Evidence → see maintenance_proximity signal in root-cause output.
3. Note `temporal_precedence = True` in the candidate.

---

## S-REC — Chamber Recurrence

**What happens:** ETCH-A/CHA-1 has a persistent, below-average yield across the majority of lots routed through it. This is a chronic chamber health issue rather than an acute event.

**What the system should detect:**
- Monitor → Chamber Recurrence panel shows CHA-1 with `recurrence_score > 0.7`.
- `yield_gap` of 4–8 percentage points below fleet mean.
- Root-cause fusion ranks `chamber_recurrence` for all lots using CHA-1.

**Demo steps:**
1. Monitor → Chamber Recurrence table → CHA-1 highlighted.
2. Investigate → select any lot from L0301–L0400 → chamber_recurrence signal.

---

## S-TIME — Temporal / Queue-Time Exposure

**What happens:** Lots L0451–L0475 have artificially elevated planned queue times (>72 hours). This correlates with a modest yield reduction.

**What the system should detect:**
- Pre-run risk model shows higher risk scores for high-queue-time lots.
- Root-cause fusion has a non-zero `queue_time` signal.

---

## S-CTRL — Control Lots

All lots not falling in the above windows are control lots with baseline yield ~0.93–0.95 (28nm product family). They serve as the statistical baseline for all anomaly detection algorithms.

---

## Running the Demo

1. Start the backend: `cd src/backend && python -m uvicorn app.main:app --reload`
2. Seed the database: `cd src/backend && python data/seed_db.py`
3. Start the frontend: `cd src/frontend && npm run dev`
4. Open `http://localhost:5173`
5. Follow the demo steps above for each scenario.

See [`docs/setup-guide.md`](setup-guide.md) for full environment setup.
