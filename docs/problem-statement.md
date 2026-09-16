# Problem Statement

## Background

At advanced semiconductor nodes (28 nm and below), a single percentage-point drop in wafer yield translates to millions of dollars in lost revenue per month across a high-volume fab. When yield excursions occur, the root cause is rarely obvious: it may lie in a slow equipment drift invisible in any single run, an interaction between chamber conditioning state and a specific recipe, a maintenance-induced perturbation, contamination spread across several lots, or a combination of all of the above.

## The Manual Correlation Problem

A typical yield investigation today involves a process engineer manually:

1. Pulling yield data from the electrical-test system.
2. Querying the equipment database for tool/chamber history.
3. Cross-referencing defect inspection reports by lot and wafer slot.
4. Checking maintenance logs for timing relative to the excursion.
5. Reviewing metrology trends (overlay, CD, film thickness).
6. Asking colleagues whether similar lots had similar symptoms.

Each of these queries is in a different system, often in a different data format, and timestamped independently. The correlation is done in a spreadsheet or manually in the engineer's head. It can take days or weeks to isolate a root cause, and the correction may come too late to save the affected lots — or, worse, the next excursion.

## Challenge Statement

Build a software system that:

1. **Identifies yield/defect patterns** across lots, wafers, chambers, and process parameters automatically and without manual correlation.
2. **Ranks evidence-supported root-cause candidates** using deterministic, auditable signal fusion — never LLM hallucination.
3. **Recommends corrective actions** that a qualified engineer can approve or reject with full audit trail.
4. **Flags upcoming batches** whose pre-run parameters historically correlate with poor outcomes, allowing intervention before the lot starts.

The system must work on the actual data relationships that exist in a real fab:

```
tool → chamber → lot → wafer → run → recipe → process parameters
     → trace data → metrology → inspection/defects → maintenance → yield
```

Timestamps and genealogy must be preserved end-to-end so temporal precedence can be established for causal reasoning.

## Scope of This Prototype

This prototype demonstrates the core data pipeline and analytics using deterministic synthetic data. It is not a production system and does not process real fab data. All heuristics and thresholds are for demonstration purposes only.

Key demonstrable claims:
- Evidence fusion root-cause ranking without LLM.
- Pre-run risk scoring with enforced data-leakage prevention.
- Wafer defect spatial pattern classification.
- Chamber recurrence analysis with yield gap quantification.
- Human approval boundary for all corrective actions.
