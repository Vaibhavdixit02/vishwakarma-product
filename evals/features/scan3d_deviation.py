"""Geometric deviation features: a scan3d record vs. an ideal reference scan.

The first *real-data* feature vector in the repo. The synthetic manifest hands the trained
baseline its features for free (`annotations` carry size/amplitude); real scan3d records have
EMPTY annotations, so anything learnable must be derived from the geometry itself. This module
does the classic dimensional-inspection reduction — the same shape as the source paper's method
(Sensors 23(5):2503: align point clouds, then find deviation clusters), reimplemented minimally:

  1. rigid trimmed-ICP alignment of the scan onto the reference (trimming matters: the defect
     regions themselves must not drag the fit — a plain least-squares ICP would split every
     bump's error across the whole part),
  2. per-point deviation = nearest-neighbor distance into the reference cloud,
  3. reduction to a fixed feature dict: tail statistics (p95/p99/max — defects live in the tail,
     the bulk of a mostly-good surface sits near zero) + connected deviation-cluster stats
     (count, largest cluster's size/extent/peak), computed on points beyond an outlier threshold.

Honesty notes:
  - The reference here is the dataset's own ideal-etalon *scan* (dense, same rig/frame — the
    bboxes of all four scans agree to ~3 mm), not the CAD model. The reference record's own
    deviation-vs-itself is zero by construction and is flagged `reference_is_self`; with N=4
    nothing here is a benchmark result — this proves the real-data feature path, nothing more.
  - Different physical specimens have genuinely different boundaries (plate edges, weld ends),
    so some deviation mass at the boundary is specimen variation, not defect. The cluster stats
    are the more defect-shaped signal; the global tail stats include that boundary noise.

Usage (after the ingest adapter has written the base manifest):

  python -m evals.features.scan3d_deviation \\
      --data-dir evals/datasets/raw/abonyilab-3d-scanner \\
      --manifest evals/datasets/manifests/abonyilab_scan3d.jsonl

Rewrites the manifest in place with a `deviation` block inside each record's scan3d modality
(schema-revalidated; `additionalProperties` on scan3d permits it), tagged derived_by/reference.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from evals.datasets.ingest.abonyilab_scan3d import (
    Scan3dIngestError,
    _iter_ply_files,
    read_ply_with_vertices,
)
from evals.schema.validate import validate_record

DERIVED_BY = "scan3d-deviation@v1"
DEFAULT_REFERENCE = "abonyilab-3dscan-ideal-1"


def rigid_icp(
    src: np.ndarray,
    ref: np.ndarray,
    n_sample: int = 20_000,
    max_iter: int = 30,
    trim: float = 0.8,
    tol: float = 1e-4,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Trimmed rigid ICP: return (R, t, rms) aligning `src` onto `ref` (x' = x @ R.T + t).

    Each iteration keeps only the closest `trim` fraction of correspondences for the Kabsch
    update, so non-overlapping regions and the defects themselves don't bias the fit. The
    returned rms is over that trimmed (inlier) set. Assumes a roughly common initial frame
    (true for a fixtured scanner rig — the real scans' bboxes already agree to ~3mm with no
    visible rotation); this is not a global registration method. Point-to-point correspondence
    also converges slowly under large rotation on locally-flat surfaces (the classic ICP
    "aperture problem" — tangential sliding barely changes point-to-point distance); fine for
    this adapter's near-aligned input, but raise `max_iter` well past its default for anything
    starting more than a couple degrees off, or switch to point-to-plane.
    """
    if not 0.0 < trim <= 1.0:
        raise ValueError("trim must be in (0, 1]")
    rng = np.random.default_rng(seed)
    pts = src[rng.choice(len(src), min(n_sample, len(src)), replace=False)]
    tree = cKDTree(ref)

    R = np.eye(3)
    t = ref.mean(axis=0) - pts.mean(axis=0)  # centroid shift as the initial guess
    prev_rms = np.inf
    k = max(3, int(trim * len(pts)))
    for _ in range(max_iter):
        moved = pts @ R.T + t
        dist, idx = tree.query(moved, workers=-1)
        keep = np.argpartition(dist, k - 1)[:k]
        a, b = pts[keep], ref[idx[keep]]

        # Kabsch on the trimmed correspondences
        a0, b0 = a - a.mean(axis=0), b - b.mean(axis=0)
        u, _, vt = np.linalg.svd(a0.T @ b0)
        d = np.sign(np.linalg.det(vt.T @ u.T))
        R = vt.T @ np.diag([1.0, 1.0, d]) @ u.T
        t = b.mean(axis=0) - a.mean(axis=0) @ R.T

        rms = float(np.sqrt(np.mean(dist[keep] ** 2)))
        if abs(prev_rms - rms) < tol:
            break
        prev_rms = rms
    return R, t, rms


def deviation_features(
    src: np.ndarray,
    ref: np.ndarray,
    n_eval: int = 100_000,
    outlier_mm: float = 0.5,
    cluster_radius_mm: float = 1.5,
    min_cluster_points: int = 25,
    seed: int = 0,
) -> dict[str, Any]:
    """Align `src` to `ref` and reduce the deviation field to a fixed, JSON-friendly feature
    dict. Distances are in the clouds' native units (mm for the known source)."""
    R, t, icp_rms = rigid_icp(src, ref, seed=seed)
    rng = np.random.default_rng(seed)
    pts = src[rng.choice(len(src), min(n_eval, len(src)), replace=False)] @ R.T + t

    dist, _ = cKDTree(ref).query(pts, workers=-1)

    outliers = pts[dist > outlier_mm]
    n_clusters, largest_n, largest_extent, largest_max = 0, 0, 0.0, 0.0
    if len(outliers):
        labels = _radius_clusters(outliers, cluster_radius_mm)
        counts = np.bincount(labels)
        big = np.flatnonzero(counts >= min_cluster_points)
        n_clusters = int(len(big))
        if n_clusters:
            top = big[np.argmax(counts[big])]
            members = outliers[labels == top]
            member_dist = dist[dist > outlier_mm][labels == top]
            largest_n = int(counts[top])
            largest_extent = float(np.linalg.norm(members.max(axis=0) - members.min(axis=0)))
            largest_max = float(member_dist.max())

    return {
        "derived_by": DERIVED_BY,
        "n_points_evaluated": int(len(pts)),
        "icp_inlier_rms_mm": round(icp_rms, 4),
        "mean_mm": round(float(dist.mean()), 4),
        "p50_mm": round(float(np.percentile(dist, 50)), 4),
        "p95_mm": round(float(np.percentile(dist, 95)), 4),
        "p99_mm": round(float(np.percentile(dist, 99)), 4),
        "max_mm": round(float(dist.max()), 4),
        "outlier_threshold_mm": outlier_mm,
        "outlier_frac": round(float((dist > outlier_mm).mean()), 6),
        "n_deviation_clusters": n_clusters,
        "largest_cluster_points": largest_n,
        "largest_cluster_extent_mm": round(largest_extent, 3),
        "largest_cluster_max_mm": round(largest_max, 4),
    }


def _radius_clusters(points: np.ndarray, radius: float) -> np.ndarray:
    """Connected components of the radius-neighbor graph — the minimal stand-in for the source
    paper's DBSCAN step (no sklearn in the core deps; for cluster *counting* the distinction
    from DBSCAN is just its noise/min-samples handling, which min_cluster_points covers)."""
    pairs = cKDTree(points).query_pairs(radius, output_type="ndarray")
    n = len(points)
    graph = coo_matrix(
        (np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n)
    )
    _, labels = connected_components(graph, directed=False)
    return labels


# ---------------------------------------------------------------------------- manifest wiring


def enrich_manifest(
    manifest_path: Path, data_dir: Path, reference_id: str = DEFAULT_REFERENCE, seed: int = 0
) -> list[dict[str, Any]]:
    """Compute deviation features for every record in the manifest against the reference record's
    scan, embed them in each record's scan3d block, and return the enriched records."""
    records = [json.loads(line) for line in manifest_path.read_text().splitlines() if line.strip()]
    by_id = {r["record_id"]: r for r in records}
    if reference_id not in by_id:
        raise Scan3dIngestError(f"reference record {reference_id!r} not in {manifest_path}")

    clouds: dict[str, np.ndarray] = {}
    checksum_to_id = {
        r["modalities"]["scan3d"]["checksum_sha256"]: r["record_id"] for r in records
    }
    for basename, _ref, data in _iter_ply_files(data_dir):
        mesh, xyz = read_ply_with_vertices(data, basename)
        rec_id = checksum_to_id.get(mesh.checksum_sha256)
        if rec_id is not None and rec_id not in clouds:
            clouds[rec_id] = xyz
    missing = sorted(set(by_id) - set(clouds))
    if missing:
        raise Scan3dIngestError(
            f"{data_dir}: no scan matching the manifest checksum for {missing} — "
            "raw data absent or modified (re-download from the source repo)"
        )

    ref_cloud = clouds[reference_id]
    for r in records:
        rec_id = r["record_id"]
        feats = deviation_features(clouds[rec_id], ref_cloud, seed=seed)
        feats["reference_record"] = reference_id
        feats["reference_is_self"] = rec_id == reference_id
        r["modalities"]["scan3d"]["deviation"] = feats
        validate_record(r)
    return records


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data-dir", type=Path, required=True, help="dir with the source zips / .ply files")
    p.add_argument("--manifest", type=Path, required=True, help="manifest JSONL to enrich in place")
    p.add_argument("--reference", default=DEFAULT_REFERENCE, help="record_id of the ideal reference scan")
    p.add_argument("--seed", type=int, default=0, help="subsampling seed (results are deterministic)")
    args = p.parse_args(argv)

    records = enrich_manifest(args.manifest, args.data_dir, args.reference, args.seed)
    for r in records:
        d = r["modalities"]["scan3d"]["deviation"]
        marker = " (reference)" if d["reference_is_self"] else ""
        print(
            f"{r['record_id']:<28} {r['ground_truth']['decision']:<7} "
            f"p99={d['p99_mm']:6.3f}mm max={d['max_mm']:6.3f}mm "
            f"outlier_frac={d['outlier_frac']:.4f} clusters={d['n_deviation_clusters']} "
            f"largest={d['largest_cluster_points']}pts/{d['largest_cluster_extent_mm']:.1f}mm{marker}"
        )
    with args.manifest.open("w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Enriched {len(records)} records in {args.manifest}")


if __name__ == "__main__":
    main()
