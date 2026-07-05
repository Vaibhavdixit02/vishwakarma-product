# Baselines — the floor the product must beat

A benchmark is only useful if we run something against it. Baselines establish the **floor**: the
expected cost an off-the-shelf approach achieves, scored by *our* metric (not its native accuracy).
This is what the 0007 spec means by "the eval defines, in dollars, what the product must beat."

## What to run (in order of effort)

| Baseline | Why | Status |
|---|---|---|
| **Trivial: always-pass / always-reject** | Sanity floor + makes the accuracy paradox concrete (always-pass scores high accuracy on rare-defect data, catastrophic escape cost). | **Done** — `models.py::always_pass_scores` / `always_reject_scores` |
| **Single-pore / threshold rule on PAUT amplitude** | The classic NDT heuristic (6 dB-drop sizing). The honest "what a careful technician's rule does." | **Done** — `models.py::amplitude_threshold_scores` |
| **Off-the-shelf segmentation (U-Net) on S-scans** | Matches the public-set SOTA approach; gives the "good single-modality vision model" number. | TODO — needs real ingested scans, blocked on `../datasets/sources.md` licensing |
| **YOLO-style detector on B/S-scan images** | The other common published approach (DFW-YOLO etc.). | TODO — same blocker |
| **(v0.1) Fusion: PAUT + RGB** | The first real multimodal entry — the point is to show fusion lowering *expected cost*, not just nudging accuracy. | TODO — needs a second modality |

The two easy baselines and the harness that runs them are implemented and runnable **today**
against a synthetic smoke-test manifest (see "Run it" below) — they don't need the real dataset to
exist. The two model-based baselines are genuinely blocked on real ingested scans; that's an
honest, external gate, not a corner we cut.

## Run it

```
python -m evals.baselines.run --synthetic 300 --seed 0
python -m evals.baselines.run --synthetic 300 --c-fa 5000 --c-fr 25 --out results/
python -m evals.baselines.run --manifest records.jsonl --baseline amplitude_threshold
```

`--synthetic N` generates N schema-valid records via `../datasets/synthetic.py` — provenance-tagged
`synthetic: true`, `source: "synthetic-smoke-test"`, never a stand-in for a real leaderboard
number. Swap in `--manifest records.jsonl` (one schema-valid record per line) once a real ingest
lands; nothing about scoring or reporting changes. Tests: `pytest tests/test_eval_baselines.py`.

## The reporting rule

Every baseline is reported **two ways**, side by side:
1. Its **native metric** (accuracy / IoU / AUROC) — what its paper would quote.
2. Its **expected cost per part** at the cost-optimal operating point, per acceptance class (B/C/D),
   via `../scoring/economic_metric.py`.

The story the leaderboard tells: the ranking by (1) and the ranking by (2) are **different**, and
(2) is the one that matters. A baseline that wins on accuracy but loses on cost is the headline
result that makes the benchmark worth publishing.

## Harness contract (built — `run.py`)

```
run.py [--synthetic N | --manifest <path>] [--c-fa X] [--c-fr Y] [--epsilon E] [--out <dir>]
  -> loads records (schema-validated) or generates a synthetic smoke-test manifest
  -> derives ground-truth decisions via ../taxonomy/acceptance.py (the shared taxonomy mapping)
  -> runs each registered baseline -> per-part scores
  -> trivial (fixed-policy) baselines: economic_metric.evaluate_at_by_group at a fixed threshold
     real (swept) baselines: economic_metric.evaluate_by_group(..., groups=acceptance_class)
  -> prints a results card (native metric + cost, per class); --out writes one <baseline>.json each
```

One deviation from the originally sketched contract, worth calling out: always-pass/always-reject
are evaluated at a **fixed** threshold (`models.py::FIXED_THRESHOLD`), not swept like the other
baselines. Sweeping a constant-score baseline would let the optimizer silently pick whichever of
"reject everyone" / "pass everyone" is cheaper — which defeats the point of reporting the two
trivial floors as distinct, named policies. See `economic_metric.evaluate_at`'s docstring.

## TODO
- [ ] Wire the U-Net / YOLO baselines against the first real ingested public set (girth-weld), once
      `datasets/sources.md`'s licensing question resolves.
- [ ] Standardize the results card into an auto-generated leaderboard page once real baselines
      exist alongside the synthetic-smoke-test ones (keep them clearly separated — never rank a
      synthetic-data result against a real one).
