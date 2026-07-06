# Baselines — the floor the product must beat

A benchmark is only useful if we run something against it. Baselines establish the **floor**: the
expected cost an off-the-shelf approach achieves, scored by *our* metric (not its native accuracy).
This is what the 0007 spec means by "the eval defines, in dollars, what the product must beat."

## What to run (in order of effort)

| Baseline | Why | Status |
|---|---|---|
| **Trivial: always-pass / always-reject** | Sanity floor + makes the accuracy paradox concrete (always-pass scores high accuracy on rare-defect data, catastrophic escape cost). | **Done** — `models.py::always_pass_scores` / `always_reject_scores` |
| **Single-pore / threshold rule on PAUT amplitude** | The classic NDT heuristic (6 dB-drop sizing). The honest "what a careful technician's rule does." | **Done** — `models.py::amplitude_threshold_scores` |
| **Trained: cost-weighted logistic on indication features** | The first *fitted* entry — exists to make the train/holdout protocol real (split → fit → freeze threshold on train → report held-out cost), so the day real data lands only the model class changes. | **Done** — `trained.py` (pure numpy, no torch/sklearn needed) |
| **Off-the-shelf segmentation (U-Net) on S-scans** | Matches the public-set SOTA approach; gives the "good single-modality vision model" number. | TODO — needs real ingested scans, blocked on `../datasets/sources.md` licensing |
| **YOLO-style detector on B/S-scan images** | The other common published approach (DFW-YOLO etc.). | TODO — same blocker |
| **(v0.1) Fusion: PAUT + RGB** | The first real multimodal entry — the point is to show fusion lowering *expected cost*, not just nudging accuracy. | TODO — needs a second modality |

The easy baselines, the trained tabular baseline, and the harnesses that run them are implemented
and runnable **today** against a synthetic smoke-test manifest (see "Run it" below) — they don't
need the real dataset to exist. The two image-model baselines (U-Net / YOLO) are genuinely blocked
on real ingested scans; that's an honest, external gate, not a corner we cut.

## Run it

```
python -m evals.baselines.run --synthetic 300 --seed 0
python -m evals.baselines.run --synthetic 300 --c-fa 5000 --c-fr 25 --out results/
python -m evals.baselines.run --manifest records.jsonl --baseline amplitude_threshold
python -m evals.baselines.trained --synthetic 300 --seed 0        # train/holdout protocol
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

## The train/holdout protocol (`trained.py`)

`run.py` sweeps each baseline's threshold on the same records it reports — fine for the floors and
an untuned heuristic card, in-sample optimism for anything fitted. `trained.py` is the honest
counterpart, and the protocol every future model-based entry (U-Net, YOLO, fusion) inherits:

1. stratified split (ground-truth decision × acceptance class) into train/test
2. fit on train only — including the featurizer vocabulary and the cost-weighted loss
   (each part weighted by the dollar cost of getting it wrong, so the fit minimizes
   expected-cost-weighted log-loss, not plain accuracy)
3. select each entry's cost-optimal threshold per class **on train**, margin-adjusted to the
   midpoint of its indifference interval (`trained.py::_margin_tau`)
4. report expected cost per part at that frozen threshold **on test** — the comparison baselines
   are re-run under the same protocol on the card, so it's apples-to-apples

Synthetic-manifest runs of this validate the *loop*, not the model — ground truth there is a
deterministic function of the features, so high scores mean nothing. Never quote them as
benchmark results.

## TODO
- [ ] Wire the U-Net / YOLO baselines against the first real ingested public set (girth-weld), once
      `datasets/sources.md`'s licensing question resolves.
- [ ] Standardize the results card into an auto-generated leaderboard page once real baselines
      exist alongside the synthetic-smoke-test ones (keep them clearly separated — never rank a
      synthetic-data result against a real one).
