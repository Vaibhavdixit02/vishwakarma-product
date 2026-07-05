# Evals — The Multimodal, Economically-Weighted Inspection Benchmark

`Status: v0 — schema/taxonomy/metric/harness built and e2e-runnable on synthetic data ·`
`no real dataset ingested yet (blocked on license verification, see datasets/sources.md) ·`
`Modality v0: PAUT (phased-array ultrasonic) · Built to fuse`

The M0 from decision 0007. A benchmark that scores an inspection model not on accuracy, but on
the **decision a shop actually makes** — pass or reject a part — weighted by the **dollar cost of
getting it wrong**, against a real **acceptance class** (ISO 5817 weld levels B/C/D).

This is the thing nobody has built. It is simultaneously our **spec** (what the product must
beat, in dollars), our **data apparatus** (the labeled multimodal corpus is the compounding
moat), and our **credibility asset** (publish it → attract the design partners 0007 needs).

---

## What's different (and why it's defensible)

| Existing benchmarks (MVTec AD, VisA, Real-IAD; PAUT-ML papers) | This benchmark |
|---|---|
| Single modality (RGB, or UT alone) | **Multimodal by construction** — one record holds PAUT + (later) RGB/eddy/thermography on the *same physical part* |
| Score AUROC / accuracy / IoU | **Score expected cost** — `c_fa·P(escape) + c_fr·P(scrap)`, the shop's real loss function |
| One implicit "is it defective" label | **Decision is relative to an acceptance class** — the *same* defect is a pass at level D and a reject at level B; we score against the class the part actually ships under |
| Academic, no economic grounding | **Tied to ISO 5817 / ISO 6520-1**, the standards real fab QC already runs on |
| Saturating (~98%) | The hard, unsolved, *valuable* question is left open |

The single most important idea: **accuracy is the wrong metric for inspection.** A model that is
99% accurate but concentrates its errors on safety-critical escapes is worthless; a "worse" model
that never lets a crack through is the one a shop buys. Our metric makes that explicit and
rankable.

---

## v0 scope (deliberately narrow, honestly seeded)

- **One application family:** weld inspection (heavy/general fabrication — energy, heavy-equipment,
  automotive-tier; explicitly the **non-code-bound** slice, per 0007).
- **One modality first:** PAUT. It's the dominant subsurface NDT modality and the one with the most
  available public data to bootstrap. The schema is multimodal from day one so RGB/eddy/thermography
  drop in without rework.
- **Data:** **aggregate the scattered public PAUT datasets** under our schema + add acceptance-class
  labels (see `datasets/sources.md`). These are small (hundreds of images/volumes) and inconsistent
  — v0 is a **seed**, not a definitive corpus. We are explicit about N and never oversell it.
- **Defects:** porosity, slag inclusion, lack-of-fusion (LOF), cracks — the four that dominate the
  public sets and the ISO 6520-1 imperfection groups that matter for welds.

### Out of v0 scope (named so we don't drift)
- No CT / additive internals (vault-bound — a different company).
- No aerospace / ASME pressure-vessel / medical (excluded markets; reintroduce compliance drag).
- No real-time / on-robot inference yet — this is an **offline decision benchmark**.
- No closed-loop actuation (that's the finishing moat, demoted under 0007).

---

## The five pieces

| Piece | File | What it pins down |
|---|---|---|
| 1. Defect → acceptance map | `taxonomy/iso5817-acceptance.md`, `taxonomy/acceptance.py`, `taxonomy/acceptance_rules.yaml` | The ground-truth rule that turns a defect annotation into a pass/reject *per class* — implemented, placeholder numbers, shared with `cell/` |
| 2. Multimodal record schema | `schema/record.schema.json`, `schema/validate.py` | One part = one record; modalities + annotations + class + provenance. Fusion-ready. |
| 3. Economic scoring metric | `scoring/economic_metric.py` | The cost-weighted decision metric — the IP. Reference impl + a runnable example. |
| 4. Dataset catalog & ingest | `datasets/sources.md` (real, blocked) / `datasets/synthetic.py` (smoke-test, done) | Which public PAUT sets, licenses, how each maps onto the schema — real ingest still blocked; a synthetic generator exists so the harness runs end-to-end today |
| 5. Baselines | `baselines/README.md`, `baselines/models.py`, `baselines/run.py` | The floor the product must beat — trivial + heuristic baselines, harness, both implemented and runnable |

---

## How a benchmark run works (the loop)

```
  raw public PAUT set ──ingest──▶ records (schema) ──┐
                                                      ├─▶ ground-truth DECISION per acceptance class
  defect annotations ──map (taxonomy)────────────────┘        (pass / reject)
                                                                      │
  model under test ──▶ predicted score/decision per part ────────────┤
                                                                      ▼
                                          economic_metric:  expected $ cost,
                                          escape rate, scrap rate, cost-optimal
                                          operating point — reported PER CLASS (B/C/D)
```

A submission is ranked by **expected cost per part at its cost-optimal threshold**, subject to an
optional **regulatory floor** (a hard cap on escape rate). We also always report the naive accuracy
number — so the gap between "accurate" and "economically good" is visible on the leaderboard itself.

---

## The metric, stated plainly

For a set of parts inspected under acceptance class `k`, with cost of a false-accept (escape)
`c_fa` and cost of a false-reject (scrap good part) `c_fr`:

```
expected_cost_per_part(τ) = c_fa · (#escapes(τ) / N) + c_fr · (#scraps(τ) / N)
```

- **Escape** = model passes a part that the acceptance class says reject (the expensive error).
- **Scrap** = model rejects a part the class says is acceptable (waste + rework).
- We sweep the decision threshold `τ`, report the **cost-optimal `τ*`** and its cost, plus the
  **cost curve** (so a buyer sees the whole risk/waste tradeoff, not one point).
- **Constrained variant:** `minimize cost s.t. P(escape) ≤ ε` — because in some settings an escape
  is not just expensive, it's unacceptable, and you'll spend scrap to avoid it.
- Costs are **configurable per application** (a busbar weld escape ≠ a bracket weld escape). v0
  ships defensible default ranges sourced from weld-defect cost literature; the point is the
  *framework*, and that buyers plug in their own numbers.

Reference implementation + a runnable synthetic example: `scoring/economic_metric.py`.

---

## Honest limits (write them down so we don't fool ourselves)

- **Small N.** v0 aggregates hundreds, not thousands, of samples, from heterogeneous rigs/probes.
  Treat v0 results as **directional**; the corpus grows with partner data.
- **Cost numbers are estimates.** The dollar weights are the most contestable input. We ship
  ranges + citations and make them user-supplied — we are selling the *decision framework*, not a
  universal price of failure.
- **Public-data domain gap.** Lab/simulated welds ≠ a specific shop's parts. The benchmark proves
  the *method*; per-partner calibration is the product.
- **Acceptance mapping is an interpretation.** ISO 5817 limits are thickness- and geometry-
  dependent; our v0 map encodes the common cases and flags where a real WPS/spec would override.

---

## Roadmap

- **v0 (now):** PAUT-only, public-data seed, the metric + schema + taxonomy + one baseline. Publish
  the writeup as the credibility magnet.
- **v0.1:** second modality (RGB on the same welds) → the first *true* multimodal records; show
  fusion beating either modality alone on expected cost.
- **v1:** partner-collected PAUT (+RGB) from a low-compliance fab → real-domain corpus; this is the
  proprietary asset that compounds.
