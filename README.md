# Vishwakarma — Product

The AI-native quality-inspection product: an end-to-end multimodal inspection cell
(RFQ-style intake → robot-mounted sensors → fused pass/fail decision against an acceptance
class), and the **eval/benchmark** that specifies, de-risks, and proves it.

Strategy, decisions, and the "why" live in the separate strategy repo (`../vishwakarma`).
This repo is the **buildable product**. Per decision **0007**, the wedge is multimodal quality
inspection for **low-compliance weld / casting fabrication**, sequenced **eval-first**.

## Layout

| Path | What it is |
|------|------------|
| `evals/` | **The M0.** The multimodal + economically-weighted inspection benchmark: schema, taxonomy rule engine, economic metric, and a baselines harness runnable today on a synthetic smoke-test manifest. PAUT-first (first non-vision modality), built to fuse RGB/eddy/thermography later. |
| `cell/` | **The M1 software skeleton.** Intake → sensing → fusion/decision → labeled record, matching the eval's schema. Runnable end-to-end via `cell.cli`. Sensing has two modes: synthetic (Mode A stand-in, no hardware yet) and a real Evident `.nde` file reader (Mode B — plug into an existing instrument, no cell required; decision 0010 in the strategy repo). See `cell/README.md`. |
| `docs/` | Architecture notes for the cell (intake → sensing → fusion → decision). |

## Why eval-first, and what's now parallel

Every existing PAUT/NDT ML effort is **single-modality, accuracy-only, on a tiny private set**.
None scores the thing a shop actually cares about: the **economic decision** — cost of a missed
defect (escape) vs. cost of scrapping a good part — against a real **acceptance class**
(ISO 5817 weld levels B/C/D). That scoring layer is the differentiator and the credibility asset.
Build the eval, it tells us exactly what the product must beat (in dollars) before we buy a robot.

The eval's remaining work (verifying public PAUT dataset licenses) is slow and externally gated.
The product's software has no such dependency, so `cell/` is being built now, in parallel — with
synthetic sensing standing in for hardware that doesn't exist yet, and its decision thresholds
explicitly flagged as placeholders pending calibration against the eval once real labeled data
exists.

## Status

`v0 — both software tracks are built and run end-to-end`, each standing in for the piece that's
still externally blocked:

- **`evals/`**: schema, taxonomy, economic metric, and a baselines harness (`evals/baselines/`) all
  exist and run — `python -m evals.baselines.run --synthetic 300` scores trivial + heuristic
  baselines against a synthetic smoke-test manifest, per acceptance class, in dollars. What's
  missing is the **real** ingested PAUT dataset (blocked on license verification,
  `evals/datasets/sources.md`) and the two model-based baselines (U-Net/YOLO) that need it.
- **`cell/`**: intake → synthetic sensing → fusion/decision → record runs end-to-end via
  `python -m cell.cli` (see `cell/README.md` for the full flag set — cost overrides, JSON output,
  job history). What's missing is **real hardware** and calibrated decision thresholds, both
  pending real labeled data.

The two tracks share one taxonomy implementation (`evals/taxonomy/acceptance.py`) so "ground
truth" can't quietly diverge between them. No dataset has been ingested, no model has been
trained, and no hardware exists yet — every number either track currently produces is either a
placeholder or derived from synthetic self-check data, and is labeled as such everywhere it
appears.
