"""Tests for the scan3d deviation features (evals/features/scan3d_deviation.py): ICP recovery of
a known rigid transform, feature extraction against synthetic geometry with a known defect, and
manifest enrichment (integration-tested only when the git-ignored raw data is present)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from evals.datasets.ingest.abonyilab_scan3d import Scan3dIngestError
from evals.features.scan3d_deviation import (
    DEFAULT_REFERENCE,
    deviation_features,
    enrich_manifest,
    rigid_icp,
)
from evals.schema.validate import validate_record

RAW_DIR = Path("evals/datasets/raw/abonyilab-3d-scanner")
MANIFEST = Path("evals/datasets/manifests/abonyilab_scan3d.jsonl")


def wavy_grid(n: int = 12_000, seed: int = 42) -> np.ndarray:
    """A gently undulating, IRREGULARLY sampled surface — not a flat plane (point-to-point ICP on
    a plane can't observe in-plane shift/rotation) and not a regular lattice (a rotated regular
    grid gives nearest-neighbor queries aliased false correspondences to the wrong lattice point,
    a sampling artifact real scans don't have — actual scanner point clouds are irregular)."""
    rng = np.random.default_rng(seed)
    xs = rng.uniform(0, 40, n)
    ys = rng.uniform(0, 20, n)
    zs = 0.8 * np.sin(xs / 3.0) * np.cos(ys / 4.0)
    return np.column_stack([xs, ys, zs])


def rigid(points: np.ndarray, deg: float, shift: tuple[float, float, float]) -> np.ndarray:
    th = np.radians(deg)
    R = np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0], [0, 0, 1]])
    return points @ R.T + np.asarray(shift)


def with_bump(points: np.ndarray, center_xy: tuple[float, float], height: float = 2.0) -> np.ndarray:
    out = points.copy()
    r2 = (out[:, 0] - center_xy[0]) ** 2 + (out[:, 1] - center_xy[1]) ** 2
    out[:, 2] += height * np.exp(-r2 / 2.0)  # sigma = 1mm gaussian bump
    return out


def test_icp_recovers_a_known_rigid_transform() -> None:
    # Misalignment magnitude matches the real use case (a fixtured scanner rig — the four real
    # scans' bboxes already agree to ~3mm with no visible rotation), not an arbitrary large
    # rotation: plain point-to-point ICP has a well-known slow-tangential-convergence "aperture
    # problem" on locally-flat surfaces under large rotation, needing hundreds of iterations to
    # untangle — solvable (point-to-plane ICP) but not needed for this adapter's actual input.
    ref = wavy_grid()
    src = rigid(ref, deg=0.5, shift=(0.3, -0.2, 0.15))
    R, t, rms = rigid_icp(src, ref, seed=0)
    assert rms < 1e-6
    assert np.abs(src @ R.T + t - ref).max() < 1e-6


def test_icp_rejects_bad_trim() -> None:
    ref = wavy_grid(20, 20)
    with pytest.raises(ValueError, match="trim"):
        rigid_icp(ref, ref, trim=0.0)


def test_identical_clouds_have_zero_deviation() -> None:
    ref = wavy_grid()
    feats = deviation_features(ref, ref, seed=0)
    assert feats["max_mm"] == 0.0
    assert feats["outlier_frac"] == 0.0
    assert feats["n_deviation_clusters"] == 0
    assert feats["largest_cluster_points"] == 0


def test_known_bump_is_measured_and_clustered_despite_misalignment() -> None:
    ref = wavy_grid()
    defective = rigid(with_bump(ref, center_xy=(20.0, 10.0), height=2.0), 0.5, (0.3, -0.2, 0.15))
    feats = deviation_features(
        defective, ref, cluster_radius_mm=0.6, min_cluster_points=10, seed=0
    )
    # alignment recovered: the bulk of the (mostly flat) part sits at ~zero deviation
    assert feats["p50_mm"] < 0.05
    # the 2 mm bump is measured (nearest-neighbor distance underestimates height slightly on
    # the slope, hence the loose lower bound) and found as exactly one cluster
    assert 1.5 < feats["max_mm"] <= 2.1
    assert feats["n_deviation_clusters"] == 1
    assert feats["largest_cluster_points"] >= 10
    assert feats["largest_cluster_max_mm"] == feats["max_mm"]
    assert 2.0 < feats["largest_cluster_extent_mm"] < 8.0  # ~the bump footprint, not the part


def test_features_are_deterministic_given_seed() -> None:
    ref = wavy_grid(60, 30)
    src = rigid(with_bump(ref, (5.0, 3.0)), 1.0, (0.5, 0.5, 0.0))
    assert deviation_features(src, ref, seed=3) == deviation_features(src, ref, seed=3)


def test_enrich_manifest_fails_loudly_without_raw_data(tmp_path) -> None:
    record = json.loads(MANIFEST.read_text().splitlines()[0])
    lone = tmp_path / "m.jsonl"
    lone.write_text(json.dumps(record) + "\n")
    with pytest.raises(Scan3dIngestError, match="reference record"):
        enrich_manifest(lone, tmp_path)  # manifest lacks the reference record entirely
    with pytest.raises(Scan3dIngestError, match="no scan matching"):
        enrich_manifest(MANIFEST, tmp_path)  # empty data dir: checksums can't match


@pytest.mark.skipif(not RAW_DIR.exists(), reason="git-ignored raw scans not downloaded")
def test_enrich_real_manifest_end_to_end() -> None:
    records = enrich_manifest(MANIFEST, RAW_DIR)
    assert len(records) == 4
    for r in records:
        validate_record(r)
        d = r["modalities"]["scan3d"]["deviation"]
        assert d["reference_record"] == DEFAULT_REFERENCE
        if d["reference_is_self"]:
            assert d["max_mm"] == 0.0 and r["ground_truth"]["decision"] == "pass"
        else:
            # every defective specimen shows real deviation structure vs. the etalon
            assert r["ground_truth"]["decision"] == "reject"
            assert d["p99_mm"] > 0.5
            assert d["n_deviation_clusters"] >= 1
