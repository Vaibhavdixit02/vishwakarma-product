# The Cell — Product Software Skeleton

`Status: v0 — software skeleton complete and e2e-testable (CLI + tests), no hardware, thresholds uncalibrated`

The M1 from `docs/architecture.md`: an end-to-end inspection cell (RFQ-style intake → robot arm →
multimodal sensing → fusion/decision → labeled record). This module is the software spine of that
cell, buildable and testable today even though the robot arm and sensing head don't exist yet.

Being built in parallel with `evals/`, not after it — see "Why this exists now" below.

## The loop

```
  intake (JobIntake)              — RFQ-style: part + acceptance class + defect concern
        │
        ▼
  sensing (synthetic)             — stand-in for the real sensing head; fabricates indications
        │                           (no hardware, no dataset dependency)
        ▼
  fusion + decision                — rule-based scorer + placeholder threshold -> PASS/REJECT
        │                           + cost-of-error rationale (reuses evals' CostModel)
        ▼
  records (build_eval_record)     — assembles a record.schema.json-valid record
```

Run it:
- `python -m cell.demo` (from the repo root) — a fixed, scripted walkthrough: a handful of jobs
  across ISO 5817 classes B/C/D and the v0 defect types, printing each decision and one full record.
- `python -m cell.cli` — **the way to test the e2e flow as a user would.** Prompts you through the
  RFQ-intake questions (part family/material/thickness/joint type, acceptance class) and asks what
  the (synthetic) sensing head should report, then prints the decision, rationale, and the
  resulting record. Also scriptable with flags for one-liners, e.g.:
  `python -m cell.cli --family weld --material carbon-steel --thickness 12 --joint-type butt --level B --scenario porosity --seed 7`
  - `--seed` fixes a reproducible synthetic reading; `--non-interactive` fails instead of prompting
    on anything you didn't pass as a flag (useful in scripts/CI).
  - `--c-fa` / `--c-fr` let you supply your own escape/scrap dollar costs instead of the default
    placeholder `CostModel` — matching the "buyers plug in their own numbers" philosophy in
    `evals/README.md`.
  - `--json` prints one machine-readable object (decision + indications + record) instead of prose,
    for piping into other tools. PASS/REJECT prints in color when your terminal supports it.
  - `--history PATH` persists every submitted job to an append-only JSONL file and reloads it on
    the next run; `--list-history PATH` reviews what's in one without submitting anything new.

Tests: `pytest tests/test_cell_pipeline.py tests/test_intake_persistence.py tests/test_acceptance_taxonomy.py`.

## Why this exists now

`docs/architecture.md` originally sequenced this after the eval (M0 → M0.1 → M1). The eval's
remaining work — verifying PAUT dataset licenses, possibly waiting on paper authors — is slow and
externally gated. The cell's software has no such dependency, so it's being built in parallel: the
eval still defines what the product must beat (in dollars, via `economic_metric.py`), but building
the pipeline's plumbing doesn't need to wait for that number to exist.

## What's real vs. simulated (read before trusting any output)

- **Sensing is synthetic by construction** (`sensing/synthetic.py`). It fabricates indications
  directly — it is not a physics simulation (CIVA-style simulation is the documented fallback in
  `evals/datasets/sources.md` if that's ever needed) and it is not derived from any ingested
  dataset. It exists purely to drive the rest of the pipeline with realistic-shaped inputs.
- **The decision threshold and volumetric size limits are placeholders**, not calibrated ISO 5817
  numbers. `fusion/decision.py` layers a cost-aware threshold on top of the *shared* rule engine in
  `evals/taxonomy/acceptance.py` (loaded from `evals/taxonomy/acceptance_rules.yaml`), which
  operationalizes the qualitative structure in `evals/taxonomy/iso5817-acceptance.md` (cracks never
  permitted, lack-of-fusion permitted only at level D, volumetric limits tightening B→C→D) with
  made-up numbers. That rule engine is the same one the eval's baselines harness uses to derive its
  own ground truth, so the two tracks can't quietly diverge on what "ground truth" means. Replacing
  the placeholder numbers requires the calibration work `iso5817-acceptance.md`'s backlog already
  names (numeric limits from the standard/a partner WPS) plus running `economic_metric.evaluate()`
  against real labeled data to pick a cost-optimal operating threshold instead of the current
  `DEFAULT_THRESHOLD = 0.5`.
- **`ground_truth` in a built record is a self-check, not a real label.** For synthetic runs we
  know the truth because we generated the indications ourselves, so `records/build.py` fills
  `ground_truth` using the taxonomy's hard mapping rule. Its `derived_by` is stamped
  `"cell-synthetic-self-check@v0"` — deliberately not `"iso5817-acceptance@v0"` — so nobody mistakes
  an uncalibrated placeholder rule for a real ISO-5817-calibrated ground truth.
- **No hardware integration.** There is no robot-arm or sensor driver code here. When real hardware
  exists, it slots in by replacing `sensing/synthetic.py`'s output with real signal, unchanged
  downstream — that's the point of matching the eval's schema and taxonomy from day one.

## Mode B: reading real instrument data (no cell required)

Per decision **0010** (strategy repo), the durable asset is this software, not a physical cell —
so for accounts that already run NDT instruments, the sensing head doesn't need to be built at
all. `sensing/nde_ingest.py` reads a real Evident/Olympus `.nde` export (their open HDF5+JSON
format — no vendor cooperation needed, see the module docstring) and produces a schema-valid
`modalities.paut` block, proving *data access* is real today. It does **not** produce indications
— that requires an interpretation model, which doesn't exist yet (see Open TODOs). Requires the
optional `hardware-ingest` extra (`pip install -e '.[hardware-ingest]'`, adds `h5py`). Tested only
against a synthetic fixture matching the documented spec (`tests/test_nde_ingest.py`), not yet
against a real vendor-exported file — flagged in the module docstring, same discipline as
`sensing/synthetic.py`.

## Open TODOs

- [ ] Calibrate `evals/taxonomy/acceptance_rules.yaml`'s volumetric limits and
      `fusion/decision.py`'s `DEFAULT_THRESHOLD` once real labeled data exists (the file and the
      threshold both exist today — see `evals/baselines/run.py` for how the eval side already
      picks a cost-optimal operating point off of a manifest; the same mechanism applies here once
      the manifest is real instead of synthetic).
- [ ] Define how a real inspected part's `ground_truth` gets confirmed (certified-inspector
      sign-off, warranty-claim feedback, etc.) — not built here.
- [ ] Replace `sensing/synthetic.py` with a real sensing-head integration once hardware exists
      (Mode A), or validate `sensing/nde_ingest.py` against a real vendor-exported `.nde` file and
      build the interpretation model that turns its raw array into indications (Mode B, decision 0010).
- [x] Persist `JobIntake` beyond in-memory — `intake/service.py` now supports an optional
      append-only JSONL file (`JobIntake(persist_path=...)`, wired into `cell.cli --history`). A
      real design partner will still want more than a local file (a proper API/DB), but the data
      isn't lost between runs anymore.
