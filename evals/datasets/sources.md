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
| ~~Girth-weld PAUT image set (literature)~~ | ~800 PAUT images (200 each) | slag, cracks, porosity, LOF | **RULED OUT 2026-07-05.** Identified as Metals (MDPI) 16(5):458, "Intelligent Defect Identification in Girth Welds of Phased Array Ultrasonic Testing Images Using Median Filtering, Spatial Enrichment, and YOLOv8" (2026-04-22), <https://www.mdpi.com/2075-4701/16/5/458> — exact match on image counts and defect classes. Its Data Availability Statement: *"The data presented in this study are available on request from the corresponding author. The data are not publicly available due to privacy or ethical restrictions."* Not usable for v0 (no public release; "on request" doesn't satisfy our no-unlicensed-ingest rule and carries unclear redistribution rights even if granted). |
| ~~S-scan 3D volume set (literature)~~ | ~196 volumes (64×128×128) | segmentation labels (6 dB-drop) | **RULED OUT 2026-07-05, but real contact identified.** The exact match: Zhang, S. & Zhang, Y., "Weld Defect Downscaling Recognition for Phased Array Ultrasonic Data Based on Semantic Segmentation," 20th WCNDT (NDT.net, 2024-05, Shanghai Jiao Tong Univ.), open text under CC-BY-4.0, full PDF read directly — confirms **"Professional inspectors labeled the 196 files"**, length 64–128mm resized to 128×128px, 6dB-drop labeling — matches our catalog entry exactly. No data availability statement in this paper (data from shipyard scans, funded by two PRC naval/marine-equipment grants), and it appears to be the **same underlying dataset** as the previously-ruled-out NDT&E International paper (S0963869524001300, same domain/method/similar Dice ~91%, likely a journal extension of this conference paper) — that paper's DAS ("not publicly available... security restrictions of the providing company... available upon reasonable request") almost certainly applies here too. Not usable for v0 without permission. **Real verified email extracted from the PDF: corresponding author YanSong Zhang, `zhangyansong@sjtu.edu.cn` (paper shows a likely OCR-artifact `.com` suffix — verify before sending); co-author Sen Zhang, `zhangs_0427@163.com`.** Outreach email drafted 2026-07-05, pending send. Separately, the XCT+PAUT fusion CNN paper (Applied Sciences 13(10):5933, Caballero Garzón et al.) was checked and ruled out — porosity segmentation in *composite materials*, not welds, no data availability statement published. |
| ~~USimgAIST (AIST, public)~~ | ultrasonic wave-propagation images | NDT pattern research | **LIKELY RULED OUT 2026-07-05** (unverified via primary source — the dataset's own page at `sites.google.com/site/yejiaxingweb/usimgaist` now redirects to a Google login wall, so this could not be independently confirmed). Per search-engine synthesis of the dataset's terms: license is **CC BY-NC-SA 4.0 — non-commercial only**, which would block use in a commercial product/benchmark. Also a **domain mismatch even if license were fine**: it's drill-hole/slit flaws in stainless steel plates for general ultrasonic wave-propagation-imaging research, not weld defects — doesn't map onto our ISO 5817/6520-1 weld taxonomy. Re-verify primary source before fully closing this out. |
| ~~Industrial UT B-scan sets (literature)~~ | B-scan images | weld defects | **Best instance RULED OUT 2026-07-06.** The leading candidate family (MDPI NDT 2(2):7 "Automated Weld Defect Detection in Industrial Ultrasonic B-Scan Images", 359 images/229 LOF annotations, + its two sibling papers from the same Croatian group) states: *"the dataset is proprietary of CRC-Evans"* (confirmed by user from the paper text). No other public industrial UT B-scan set identified yet. |
| Simulated PAUT (CIVA-derived, literature) | S-scans w/ placed defects | crack, porosity, inclusion | Not the v0 path (we chose public-first), but a **fallback/augmentation** lever if N is too thin. |
| **abonyilab/3D-scanner-data (GitHub, public)** | 4 real structured-light weld scans (1 ideal + 3 defective, ~400k-vertex ASCII PLY) + 7 CAD defect models | ISO 5817:2014 geometric defect types (crack, excessive convexity/asymmetry, throat thickness, end crater pipe, intermittent undercut) | **FIRST GENUINELY PUBLIC FIND (verified 2026-07-06)** — the Sensors 23(5):2503 paper's DAS says *"Publicly available datasets... can be found here: github.com/abonyilab/3D-scanner-data"*. **Not PAUT** — surface-geometry modality (dimensional/visual station), and **N=4 real scans**: a real-data *fixture* for a `scan3d` modality adapter + schema proof, not a training corpus. Repo has **no LICENSE file** — fine for internal dev given the DAS, but ask authors to add one before any redistribution (see outreach.md #3). |

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
