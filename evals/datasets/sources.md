# Dataset Catalog — public PAUT sources for the v0 seed

The v0 strategy (per the wedge decision) is to **aggregate scattered public PAUT datasets** under
our schema and add the missing **acceptance-class labels**. None of these were built for an
economic, multimodal, decision benchmark — that relabeling is exactly our added value.

> ⚠️ **N is small and heterogeneous.** These are hundreds of images/volumes from different probes,
> materials, and rigs. v0 is a **seed corpus**; treat results as directional. Verify every license
> before redistribution — we keep **manifests + checksums** in git, never the raw scan files (see
> `.gitignore`).

## Candidate sources (to verify, license-check, and ingest)

| Source | Form | Defects | Notes / status |
|---|---|---|---|
| Girth-weld PAUT image set (literature) | ~800 PAUT images (200 each) | slag, cracks, porosity, LOF | Balanced across our 4 v0 classes — best fit for the taxonomy. **Find canonical release + license.** |
| S-scan 3D volume set (literature) | ~196 volumes (64×128×128) | segmentation labels (6 dB-drop) | True 3D PAUT — exercises the `volume` scan_type. Labels are masks, need decision-mapping. |
| USimgAIST (AIST, public) | ultrasonic wave-propagation images | NDT pattern research | Public NDT image set; assess relevance to weld defects vs. general wave imaging. |
| Industrial UT B-scan sets (literature) | B-scan images | weld defects | UT (not phased-array) — useful as adjacent modality / domain-gap probe. |
| Simulated PAUT (CIVA-derived, literature) | S-scans w/ placed defects | crack, porosity, inclusion | Not the v0 path (we chose public-first), but a **fallback/augmentation** lever if N is too thin. |

## Ingest contract (every source → our schema)

Each source gets an adapter in `datasets/ingest/<source>.py` that emits records conforming to
`../schema/record.schema.json`. The adapter must:

1. **Normalize the modality block** — map raw scans to `modalities.paut` with `scan_type`, shape,
   probe metadata; write the array to `datasets/cache/` (git-ignored) and record its sha256.
2. **Carry annotations** — convert the source's labels to our `annotation` items
   (defect_type + geometry + size where available).
3. **Assign an acceptance class** — sources rarely state one. v0 policy: assign a **default class
   per source** (documented here) and/or generate **per-class decisions** so a record can be scored
   under B, C, and D. Flag every assumed class.
4. **Derive ground_truth.decision** via the `iso5817-acceptance@v0` mapping (see `../taxonomy/`).
5. **Record provenance** — source, license, synthetic flag, label_source.

## The labeling gap = the moat

The reason this is defensible: turning "here's a PAUT image of a crack" into "this part **fails**
ISO 5817 level B and an escape costs \$X" requires **acceptance interpretation + cost grounding**
that no public set carries. Doing it once, well, and versioned is the proprietary apparatus 0007
calls the compounding asset. Every partner dataset later flows through the same contract.

## Open items
- [ ] Confirm canonical URLs + licenses for each source above (don't ingest anything unlicensed).
- [ ] Decide per-source default acceptance class, or score-under-all-three policy.
- [ ] Write the first adapter (girth-weld set — best taxonomy fit) end-to-end as the reference.
- [ ] Build the manifest format (path, sha256, source, license) and a validator against the schema.
