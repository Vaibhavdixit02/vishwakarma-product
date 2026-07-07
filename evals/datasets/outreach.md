# Data Access Outreach Tracker

Tracks every candidate real-data source researched for the v0 seed corpus (see `sources.md` for
the full catalog/ingest contract), the contact identified for each, the email drafted, and where
things stand. Update the **Status** line as replies come in.

---

## 1. Girth-weld PAUT image set (best taxonomy fit — 4 balanced defect classes)

- **Paper:** Bu, M., Niu, S., Li, X., & Han, B., "Intelligent Defect Identification in Girth Welds
  of Phased Array Ultrasonic Testing Images Using Median Filtering, Spatial Enrichment, and
  YOLOv8," *Metals* 16(5):458 (2026-04-22). Open access: <https://www.mdpi.com/2075-4701/16/5/458>
- **Data Availability Statement (confirmed 2026-07-05):** *"The data presented in this study are
  available on request from the corresponding author. The data are not publicly available due to
  privacy or ethical restrictions."*
- **Contact:** corresponding author marked with `*` in the MDPI author list — email grabbed from
  the article page by hand (MDPI wasn't fetchable by tooling).
- **Status:** ✅ Sent 2026-07-06 (v2 draft). Awaiting reply.

**Draft (v2, 2026-07-05 — reframed as plain research ask, no benchmark/publishing/IP details):**
> **Subject:** Data access inquiry — PAUT girth-weld defect dataset (Metals 16(5):458)
>
> Dear [Author name],
>
> I came across your paper "Intelligent Defect Identification in Girth Welds of Phased Array
> Ultrasonic Testing Images Using Median Filtering, Spatial Enrichment, and YOLOv8" (Metals, 2026).
> I'm doing applied research on automated defect detection for phased-array ultrasonic weld
> inspection, and your dataset (slag inclusion, cracks, porosity, LOF) would be very valuable for
> evaluating our approach against real inspection data.
>
> Would you be willing to share the dataset for research use? Happy to sign an NDA or data use
> agreement, and would of course credit your work in any resulting publication.
>
> Thank you for considering,
> [Your name]

<details>
<summary>v1 (superseded — named the benchmark, mentioned publishing/redistribution)</summary>

> **Subject:** Data access request — PAUT girth-weld defect dataset (Metals 16(5):458)
>
> Dear [Author name],
>
> I read your paper "Intelligent Defect Identification in Girth Welds of Phased Array Ultrasonic
> Testing Images Using Median Filtering, Spatial Enrichment, and YOLOv8" (Metals, 2026) with great
> interest. I'm building an open, economically-weighted benchmark for multimodal weld inspection
> (scoring models on expected cost of missed/false defects against ISO 5817 acceptance classes,
> rather than raw accuracy), and your 800-image PAUT girth-weld dataset (slag inclusion, cracks,
> porosity, LOF) would be an excellent fit as a seed corpus.
>
> Would you be willing to share the dataset for this use? Specifically I'd want to confirm:
> 1. Whether it can be used to derive and publish aggregate benchmark results (not raw image
>    redistribution)
> 2. Whether the underlying images/annotations themselves could be redistributed (e.g., alongside
>    a manifest + checksums) or must remain private with only our derived labels/metrics shared
> 3. Any attribution or citation requirements
>
> Happy to sign a data use agreement if needed, and of course would cite your paper as the
> dataset's origin.
>
> Thank you for considering,
> [Your name]

</details>

---

## 2. S-scan 3D volume set (true 3D PAUT, 196 files, 6dB-drop labeling)

- **Papers (likely the same underlying dataset, two publications):**
  - Zhang, S. & Zhang, Y., "Weld Defect Downscaling Recognition for Phased Array Ultrasonic Data
    Based on Semantic Segmentation," 20th WCNDT (NDT.net, 2024-05, Shanghai Jiao Tong Univ.) — open
    access, CC-BY-4.0, full text read directly.
    <https://www.ndt.net/article/wcndt2024/papers/A20230821-1624_E.pdf>
  - "Automated weld defect segmentation from phased array ultrasonic data based on U-net
    architecture," *NDT&E International* (2024-06-12) — paywalled.
    <https://www.sciencedirect.com/science/article/abs/pii/S0963869524001300>
- **Data Availability Statement (from the NDT&E International paper, confirmed 2026-07-05):**
  *"The data supporting the findings of this study are not publicly available due to security
  restrictions of the providing company. However, the data may be made available upon reasonable
  request and subject to review."* (The WCNDT conference paper has no DAS of its own but describes
  the same shipyard-sourced data, funded by two PRC naval/marine-equipment grants.)
- **Contact (verified — extracted directly from the WCNDT PDF):**
  - YanSong Zhang (corresponding author): `zhangyansong@sjtu.edu.cn` — **PDF shows a trailing
    `.com` (`zhangyansong@sjtu.edu.cn.com`), almost certainly an OCR/extraction artifact. Verify
    before sending.**
  - Sen Zhang (co-author): `zhangs_0427@163.com`
- **Status:** ✅ Sent 2026-07-06 (v2 draft). Awaiting reply.

**Draft (v2, 2026-07-05 — reframed as plain research ask, no benchmark/publishing/IP details):**
> **To:** zhangyansong@sjtu.edu.cn (verify), cc: zhangs_0427@163.com
> **Subject:** Data access inquiry — PAUT ship-weld segmentation dataset (WCNDT 2024)
>
> Dear Dr. Zhang,
>
> I came across your paper "Weld Defect Downscaling Recognition for Phased Array Ultrasonic Data
> Based on Semantic Segmentation" (WCNDT 2024). I'm doing applied research on automated defect
> detection for phased-array ultrasonic weld inspection, and your PAUT volumetric ship-weld dataset
> would be very valuable for evaluating our approach against real 3D inspection data.
>
> I understand the data may be restricted by the providing company. Would you (or the appropriate
> contact there) be open to discussing access — or a de-identified/anonymized subset — for research
> use? Happy to sign an NDA or data use agreement, and to have the company review anything before
> any publication.
>
> Thank you for considering,
> [Your name]

<details>
<summary>v1 (superseded — named the benchmark, mentioned publishing/redistribution)</summary>

> **To:** zhangyansong@sjtu.edu.cn (verify), cc: zhangs_0427@163.com
> **Subject:** Data access request — PAUT ship-weld segmentation dataset (WCNDT 2024 / NDT&E International)
>
> Dear Dr. Zhang,
>
> I read your paper "Weld Defect Downscaling Recognition for Phased Array Ultrasonic Data Based on
> Semantic Segmentation" (WCNDT 2024) with great interest, and I believe it may be the same
> underlying dataset described in your related NDT&E International paper, "Automated weld defect
> segmentation from phased array ultrasonic data based on U-net architecture."
>
> I'm building an open, economically-weighted benchmark for multimodal weld inspection (scoring
> models on expected cost of missed/false defects against ISO 5817 acceptance classes, rather than
> raw Dice/accuracy), and your 196-file PAUT volumetric ship-weld dataset would be an excellent fit
> as a seed corpus — one of the few true 3D (S-scan volume) sources with 6dB-drop labeling that
> we've found.
>
> I understand from the NDT&E International paper's Data Availability Statement that the data is
> restricted by the providing company but may be available on reasonable request. Would you (or
> the appropriate contact at the providing shipyard/company) be willing to discuss:
> 1. Whether the data — or a de-identified/anonymized subset — could be shared for this
>    benchmarking use
> 2. Whether it could be used to derive and publish aggregate benchmark results (not raw volume
>    redistribution), or whether even that requires company approval
> 3. Any attribution, citation, or review requirements before release
>
> Happy to sign a data use/review agreement and to have the company review any planned
> publication.
>
> Thank you for considering,
> [Your name]

</details>

---

## 3. abonyilab/3D-scanner-data (first genuinely public find — license-file ask, low stakes)

- **Repo:** <https://github.com/abonyilab/3D-scanner-data> — 4 real structured-light weld scans
  (1 ideal etalon + 3 defective T-welded specimens, ~400k-vertex ASCII PLY from a DAVID/HP
  structured-light scanner) + 7 CAD models of ISO 5817:2014 defect geometries. Downloaded and
  inspected 2026-07-06.
- **Paper:** Hegedűs-Kuti, Szőlősi, Varga, Abonyi, Andó, Ruppert, "3D Scanner-Based Identification
  of Welding Defects—Clustering the Results of Point Cloud Alignment," *Sensors* 23(5):2503 (2023),
  open access CC BY — <https://www.mdpi.com/1424-8220/23/5/2503>
- **Data Availability Statement (verified 2026-07-06):** *"Publicly available datasets were
  analyzed in this study. This data can be found here: https://github.com/abonyilab/3D-scanner-data"*
  — the authors themselves declare it public. The repo has **no LICENSE file**, so internal
  research/dev use is safe on the DAS, but redistribution/benchmark publication needs them to add
  one (MIT or CC BY).
- **Fit:** not PAUT and only N=4 — a real-data *fixture* for a surface-geometry (`scan3d`)
  modality adapter and schema proof (the dimensional/visual station in the rail-inspection story),
  not a training corpus.
- **Contact:** Abonyi lab, University of Pannonia — <https://www.abonyilab.com> (corresponding
  author on the Sensors paper; email on the article page).
- **Status:** ⬜ Outreach optional/not yet sent — only needed before any *redistribution*. Draft:

> **Subject:** License file for abonyilab/3D-scanner-data?
>
> Dear Dr. Ruppert / Dr. Abonyi,
>
> Thank you for publishing the 3D scanner weld dataset accompanying your Sensors 2023 paper
> ("3D Scanner-Based Identification of Welding Defects"). I'm using it in applied research on
> automated weld inspection. The paper's Data Availability Statement marks the dataset as
> publicly available, but the GitHub repository has no license file — would you consider adding
> one (e.g. MIT or CC BY 4.0) so downstream use and attribution are unambiguous? Happy to credit
> the paper in any resulting work either way.
>
> Best regards,
> [Your name]

---

## Ruled out, no outreach planned

| Source | Reason |
|---|---|
| USimgAIST (Jiaxing Ye, AIST) | Likely CC BY-NC-SA (non-commercial only, unverified via primary source — page now login-walled) + domain mismatch (drill-hole/slit flaws, not weld defects). |
| XCT+PAUT fusion CNN paper (Caballero Garzón et al., Applied Sciences 13(10):5933) | Wrong domain — composite-material porosity, not welds. No data availability statement published. |

## Surfaced but not yet investigated (candidates for later — links located 2026-07-06)

- "Fusion Datasets for Ultrasonic Weld Defect Classification with Transfer Learning" —
  <https://www.researchgate.net/publication/379256996_Fusion_Datasets_for_Ultrasonic_Weld_Defect_Classification_with_Transfer_Learning>
- ~~"Automated Weld Defect Detection in Industrial Ultrasonic B-Scan Images Using Deep Learning"
  (MDPI *NDT* 2(2):7, 2024)~~ — 359 B-scan images / 229 LOF annotations —
  <https://www.mdpi.com/2813-477X/2/2/7> — **RULED OUT 2026-07-06 (user checked the paper):**
  *"the dataset is proprietary of CRC-Evans."* This also rules out the two sibling papers below
  (same group, same dataset family).
- WeldNet (Provencal & Laperrière, CIRP Annals 71(1):445–448, 2022) — 3D geometric reconstruction
  from PAUT — <https://www.sciencedirect.com/science/article/abs/pii/S0007850622000683>
  (paywalled; DOI 10.1016/j.cirp.2022.04.033)
- INWELD (Applied Sciences 15(22):12033, 2025-11-12) — **not PAUT, RGB/visual weld images** —
  candidate for the roadmap's v0.1 second-modality (RGB) step instead, separate from this PAUT
  search — <https://www.mdpi.com/2076-3417/15/22/12033>

### New candidates surfaced by the 2026-07-06 link search (not previously cataloged)

- ~~"Automated Weld Defect Classification Enhanced by Synthetic Data Augmentation in Industrial
  Ultrasonic Images" (Applied Sciences 15(23):12811, 2025)~~ — same Croatian oil&gas B-scan group
  as the NDT 2(2):7 paper — <https://www.mdpi.com/2076-3417/15/23/12811> — **ruled out with it
  (CRC-Evans proprietary).**
- ~~"Leveraging SAM for Weld Defect Detection in Industrial Ultrasonic B-Scan Images" (2025)~~ —
  same group/dataset family — <https://pmc.ncbi.nlm.nih.gov/articles/PMC11723471/> — **ruled out
  with it (explicitly proprietary).**
- RIAWELC — radiographic (RT, not PAUT) weld defect classification dataset, claimed novel/public —
  <https://www.researchgate.net/publication/369294451_RIAWELC_A_Novel_Dataset_of_Radiographic_Images_for_Automatic_Weld_Defects_Classification>
  — RT would be a third modality; note for later, not v0.
- ~~Community index of weld-defect datasets~~
  <https://github.com/admin1523/Weld-defect-detection-datasets> — **vetted 2026-07-06, not
  usable:** indexes two X-ray/RT (not UT/PAUT) image sets hosted on Baidu pan, with an explicit
  *"academic research and non-commercial use only"* restriction — blocked for a commercial
  benchmark, and the repo owner's authority to license the images is unverifiable.
