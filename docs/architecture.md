# Product architecture (the cell the eval is specifying)

The eval is M0; this is the M1 it de-risks. Captured here so the eval's schema and metric stay
honest to the thing we'll actually build. Per decision 0007 (strategy repo).

## The end-to-end inspection cell

```
  RFQ-style intake form ──▶  part + acceptance class (ISO 5817 level) + defect concern
        │                         │
        ▼                         ▼
  COTS robot arm  ───────▶  multimodal sensing head
   (cheap, low-compliance        • PAUT (subsurface — v0 modality)
    target makes this viable)    • RGB (surface — fuse next)
        │                        • eddy / thermography (later)
        ▼                         │
  signal capture per part ───────▶ FUSION + decision model
        │                         │
        ▼                         ▼
  decision vs. the acceptance class ──▶  PASS / REJECT + cost-of-error rationale
        │
        ▼
  every inspected part ──▶ labeled multimodal record ──▶ the compounding data moat
```

## Why each piece maps to the eval

- **Intake → acceptance class**: the eval makes the decision *relative to the class*; the product's
  intake is where that class is captured. Same `acceptance` block as `schema/record.schema.json`.
  Implemented in `cell/intake/`.
- **Multimodal head**: the eval's `modalities` block is fusion-ready for exactly this reason —
  PAUT first, others additive, no schema churn when the head gains a sensor. Stood in for today by
  `cell/sensing/synthetic.py` since there's no hardware yet.
- **Fusion + decision**: scored by `scoring/economic_metric.py`. The product must beat the eval's
  published baselines on **expected cost**, per class, before we trust it on a line.
  `cell/fusion/decision.py` is the v0 rule-based version, layered on the same shared rule engine
  (`evals/taxonomy/acceptance.py`) the eval's own baselines harness (`evals/baselines/`) uses to
  derive ground truth — one implementation of "what does this defect mean under this class,"
  not two that could drift apart — with an explicit placeholder threshold pending calibration once
  real labeled data exists.
- **Every part → record**: the cell is also a data-collection apparatus. Inference-time records
  flow back through the same ingest contract, growing the proprietary corpus (the 0007 moat).
  `cell/records/build.py` assembles a `record.schema.json`-valid record from each inspection.

## Sequencing (mirror of the wedge decision)

1. **M0 — eval** (this repo, `evals/`): capital-light, public-data seed, the metric + schema +
   taxonomy + baselines. Publish → credibility → design partners.
2. **M0.1**: second modality (RGB) on the same welds → first true multimodal records + fusion result.
3. **M1 — the cell**: COTS arm + PAUT/RGB head on a low-compliance weld/casting fab partner's parts.
4. **Moat**: the labeled multimodal corpus + the decision-economics layer compound; expand
   modality-by-modality, station-by-station, toward the AI-native factory's inspection layer.

**Update:** M0 and M1's *software* are now being built in parallel, not strictly sequentially. The
eval's remaining work (verifying public PAUT dataset licenses) is slow and externally gated; the
cell's software (intake, fusion/decision, record-building) has no such dependency, so it's
proceeding now as `cell/` — synthetic sensing standing in for hardware that doesn't exist yet. The
eval still defines what the product must beat, in dollars; building the pipeline's plumbing just
doesn't have to wait for that number. See `cell/README.md`.

**Further update:** both sides are now e2e-runnable end to end on synthetic/baseline stand-ins,
pending the two real external blockers (dataset licensing, hardware). The eval's `baselines/run.py`
scores trivial + heuristic baselines against a synthetic smoke-test manifest
(`evals/datasets/synthetic.py`) via the real `economic_metric`; the cell's `cell.cli` runs a full
intake→decision→record loop for a user-specified part. Both sides share one taxonomy
implementation (`evals/taxonomy/acceptance.py`) so "ground truth" can't quietly diverge between
them. Nothing here substitutes for real data or real models — see each side's README for exactly
what's still a placeholder.

## Two deployment modes (decision 0010)

The diagram above (RFQ intake → robot arm → sensing head → fusion → decision) is **Mode A**: we
bring the cell, for accounts with no existing NDT infrastructure — 0007's original wedge,
unchanged. **Mode B**, added per decision 0010 (strategy repo) after a rail-inspection lead forced
the question of whether the software generalizes past owning hardware: for accounts that already
run NDT instruments, skip the cell entirely and read their existing data through an open format or
API. `cell/sensing/nde_ingest.py` is the first concrete instance (Evident `.nde` files). Both modes
feed the *same* fusion/decision/record pipeline — the schema and taxonomy don't fork.

## Explicitly out of scope (per 0007)
- CT / additive internals (vault-bound). Aerospace / ASME / FDA (excluded markets).
- Closed-loop finishing actuation (the demoted v2 in the strategy repo's `verticals/`).
