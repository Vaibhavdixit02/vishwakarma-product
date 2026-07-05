# Defect → Acceptance Mapping (ISO 5817 / ISO 6520-1)

The rule that converts a **defect annotation** into a **pass/reject decision** — and the reason
the same physical defect can be a pass under one class and a reject under another. This mapping is
the ground truth the economic metric scores against.

> Scope: fusion-welded joints in steel (the v0 family). ISO 5817 is the workhorse standard for
> general fabrication weld quality — which is exactly the **non-code-bound** slice we target
> (as opposed to AWS D1.1-bridge, ASME BPVC, or aerospace specs, which are excluded under 0007).

## The three quality levels

ISO 5817 defines three levels, **B (stringent) → C (intermediate) → D (moderate)**. A part is
manufactured to a contractually specified level; the level sets the numeric limit for each
imperfection type. The benchmark stores the level a part ships under and decides against *that*.

| Level | Stringency | Typical use |
|---|---|---|
| **B** | Tightest limits | High-duty / fatigue-loaded / critical structural |
| **C** | Intermediate | General load-bearing structures |
| **D** | Loosest limits | Low-duty / static / non-critical |

## Imperfection types in v0 (ISO 6520-1 reference numbers)

The four defect classes that dominate the public PAUT sets, with their qualitative acceptance
behavior across levels. **Exact numeric limits are thickness- and dimension-dependent** and live in
the standard's tables; v0 encodes **placeholder** common-case thresholds in `acceptance_rules.yaml`
(loaded by `acceptance.py`, the single implementation of this rule shared by the eval baselines
harness and the product's `cell/` — see its module docstring) and flags any part where a real WPS
would override.

| Defect | ISO 6520-1 group | Level B | Level C | Level D | Notes |
|---|---|---|---|---|---|
| **Crack** | 100 | Not permitted | Not permitted | Not permitted | Planar, sharp — never acceptable at any level. The canonical high-`c_fa` escape. |
| **Lack of fusion** | 401 | Not permitted | Not permitted | Permitted, limited (short imperfections) | Planar, dangerous; the level-D allowance is the interesting decision boundary. |
| **Slag inclusion** | 301 | Permitted ≤ small limit | Permitted ≤ larger limit | Permitted ≤ largest limit | Volumetric; limit scales with thickness and tightens B→C→D. |
| **Porosity** | 2017 | Permitted ≤ small limit | Permitted ≤ larger limit | Permitted ≤ largest limit | Volumetric; assessed by single-pore size **and** distributed/cluster area fraction. |

## Why this is the whole point

Take one weld with a **2 mm lack-of-fusion indication**:
- Under **level B/C** → **REJECT** (LOF not permitted).
- Under **level D** → possibly **PASS** (short LOF permitted within limits).

A conventional defect detector outputs "LOF, confidence 0.92" and stops. **Our benchmark requires
the model to make the decision the shop makes** — pass/reject *for the class this part ships under*
— and then prices the error. That is the gap between a detector and an inspector, and it's where
the value is.

## Mapping procedure (per part)

1. Read the part's **acceptance level** `k ∈ {B, C, D}` from the record (`acceptance.class`).
2. For each annotated indication, look up its type's limit at level `k` and its measured size /
   area-fraction.
3. **Ground-truth decision** = REJECT if *any* indication exceeds its limit (or is a
   never-permitted type), else PASS.
4. The model under test produces its own pass/reject (or a score thresholded by the metric).
5. `economic_metric` compares the two and accrues escape / scrap cost.

## Calibration backlog (v0 → v0.1)

- [ ] Replace `acceptance_rules.yaml`'s placeholder numbers with the standard's real numeric
      limits for the common thickness bands (the file exists and is wired in — its `version:
      v0-placeholder` field is the honest flag that this item isn't done yet).
- [ ] Encode the distributed-porosity area-fraction rule (not just single-pore size).
- [ ] Add the "short vs. systematic" imperfection-length distinction ISO 5817 uses for several types.
- [ ] Decide handling of multi-defect interaction (does cumulative volumetric content trip a limit?).
- [ ] Sanity-check the encoded limits against a real WPS from the first design partner.

> Accuracy note: the directional behavior above (cracks never permitted; LOF allowed only at D;
> volumetric limits tightening B→C→D) is the standard's structure. The **exact millimetre limits
> are not reproduced here** — they're parameterized in the rules file and must be set from the
> standard text / a partner's spec before any published number leans on them.
