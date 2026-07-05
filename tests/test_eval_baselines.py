"""Tests for the eval side's synthetic manifest generator and baselines harness — these are what
makes evals/ end-to-end runnable today (baselines/README.md's harness contract), standing in for
real ingested data and real trained models until both exist.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from evals.baselines.models import BASELINES, FIXED_THRESHOLD, amplitude_threshold_scores
from evals.baselines.run import _truth_and_groups, run_baseline
from evals.datasets.synthetic import generate_manifest
from evals.schema.validate import validate_record
from evals.scoring.economic_metric import CostModel


def test_generated_manifest_is_schema_valid() -> None:
    records = generate_manifest(50, seed=1)
    assert len(records) == 50
    for record in records:
        validate_record(record)  # raises on the first invalid record


def test_generated_manifest_is_deterministic_given_seed() -> None:
    a = generate_manifest(30, seed=7)
    b = generate_manifest(30, seed=7)
    assert a == b


def test_generated_manifest_round_robins_levels() -> None:
    records = generate_manifest(30, seed=2, levels=("B", "C", "D"))
    classes = {r["acceptance"]["class"] for r in records}
    assert classes == {"B", "C", "D"}


def test_defect_rate_zero_is_all_clean_and_pass() -> None:
    records = generate_manifest(20, seed=3, defect_rate=0.0)
    assert all(r["annotations"] == [] for r in records)
    assert all(r["ground_truth"]["decision"] == "pass" for r in records)


def test_defect_rate_out_of_range_raises() -> None:
    with pytest.raises(ValueError):
        generate_manifest(10, defect_rate=1.5)


def test_always_pass_never_rejects_and_always_reject_always_does() -> None:
    records = generate_manifest(200, seed=4, defect_rate=0.5)
    truth, groups = _truth_and_groups(records)
    cm = CostModel()

    pass_reports = run_baseline("always_pass", records, truth, groups, cm)
    reject_reports = run_baseline("always_reject", records, truth, groups, cm)

    for report in pass_reports.values():
        assert report.optimal.n_escapes == report.n_defective
        assert report.optimal.n_scraps == 0
    for report in reject_reports.values():
        assert report.optimal.n_escapes == 0
        assert report.optimal.n_scraps == report.n - report.n_defective


def test_amplitude_threshold_beats_trivial_baselines_on_expected_cost() -> None:
    # The whole point of the benchmark: a real (if crude) discriminative baseline should cost
    # less per part than either trivial floor, once escapes are priced much higher than scraps.
    records = generate_manifest(400, seed=5, defect_rate=0.5)
    truth, groups = _truth_and_groups(records)
    cm = CostModel(c_fa=1000.0, c_fr=50.0)

    reports = {
        name: run_baseline(name, records, truth, groups, cm)
        for name in ("always_pass", "always_reject", "amplitude_threshold")
    }

    for cls in reports["amplitude_threshold"]:
        threshold_cost = reports["amplitude_threshold"][cls].optimal.expected_cost_per_part
        pass_cost = reports["always_pass"][cls].optimal.expected_cost_per_part
        reject_cost = reports["always_reject"][cls].optimal.expected_cost_per_part
        assert threshold_cost <= pass_cost
        assert threshold_cost <= reject_cost


def test_amplitude_threshold_scores_use_no_signal_floor_for_clean_parts() -> None:
    clean_record = {"annotations": []}
    scores = amplitude_threshold_scores([clean_record], no_signal_db=-20.0)
    assert scores[0] == -20.0


def test_baselines_registry_scores_have_one_entry_per_record() -> None:
    records = generate_manifest(10, seed=6)
    for baseline in BASELINES.values():
        scores = baseline.score_fn(records)
        assert len(scores) == len(records)
        assert isinstance(scores, np.ndarray)


def test_fixed_threshold_is_strictly_between_the_two_trivial_constants() -> None:
    assert 0.0 < FIXED_THRESHOLD < 1.0


def test_cli_main_runs_end_to_end_and_writes_results(tmp_path) -> None:
    from evals.baselines.run import main

    out_dir = tmp_path / "results"
    main(["--synthetic", "60", "--seed", "0", "--out", str(out_dir)])

    for name in BASELINES:
        card = json.loads((out_dir / f"{name}.json").read_text())
        assert card["baseline"] == name
        assert set(card["per_class"]) <= {"B", "C", "D"}
