"""Tests for the trained-baseline module (evals/baselines/trained.py): the featurizer, the
pure-numpy logistic model, the stratified split, and the end-to-end train/holdout protocol on
the synthetic smoke-test manifest."""

from __future__ import annotations

import numpy as np
import pytest

from evals.baselines.models import BASELINES, FIXED_THRESHOLD
from evals.baselines.run import _truth_and_groups
from evals.baselines.trained import (
    NO_SIGNAL_DB,
    Featurizer,
    LogisticBaseline,
    heldout_reports_by_class,
    stratified_split,
)
from evals.datasets.synthetic import generate_manifest
from evals.scoring.economic_metric import CostModel


def test_featurizer_clean_record_gets_no_signal_defaults() -> None:
    records = generate_manifest(12, seed=0, defect_rate=0.0)
    fz = Featurizer().fit(records)
    X = fz.transform(records)
    assert X.shape == (12, len(fz.names))
    # peak amplitude falls back to the no-signal floor; sizes and counts are zero
    assert (X[:, 0] == NO_SIGNAL_DB).all()
    assert (X[:, 1:4] == 0.0).all()


def test_featurizer_vocabulary_comes_from_fit_records_only() -> None:
    train = generate_manifest(60, seed=1, defect_rate=1.0)
    fz = Featurizer().fit(train)
    assert set(fz.defect_types) <= {"crack", "lack_of_fusion", "slag_inclusion", "porosity"}
    # a record whose class/type wasn't in fit() still transforms (all-zero one-hots), not a crash
    other = generate_manifest(6, seed=2, levels=("D",), defect_rate=1.0)
    X = fz.transform(other)
    assert X.shape == (6, len(fz.names))


def test_logistic_learns_a_separable_rule() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, 3))
    y = (X[:, 0] > 0).astype(int)
    model = LogisticBaseline().fit(X, y)
    p = model.predict_proba(X)
    assert ((p >= 0.5).astype(int) == y).mean() > 0.98


def test_logistic_degenerate_single_class_predicts_constant() -> None:
    X = np.random.default_rng(1).normal(size=(20, 2))
    model = LogisticBaseline().fit(X, np.zeros(20))
    p = model.predict_proba(X)
    assert (p < 0.01).all()


def test_stratified_split_is_disjoint_exhaustive_deterministic() -> None:
    records = generate_manifest(90, seed=3)
    tr1, te1 = stratified_split(records, 0.7, seed=5)
    tr2, te2 = stratified_split(records, 0.7, seed=5)
    assert (tr1, te1) == (tr2, te2)
    assert set(tr1).isdisjoint(te1)
    assert sorted(tr1 + te1) == list(range(90))
    # every (decision, class) stratum with >=2 members lands on both sides
    truth, groups = _truth_and_groups(records)
    for key in {(t, g) for t, g in zip(truth, groups)}:
        members = [i for i, k in enumerate(zip(truth, groups)) if k == key]
        if len(members) >= 2:
            assert set(members) & set(tr1) and set(members) & set(te1)


def test_split_rejects_bad_train_frac() -> None:
    records = generate_manifest(10, seed=0)
    with pytest.raises(ValueError):
        stratified_split(records, 1.0, seed=0)


def test_heldout_protocol_trained_beats_both_trivial_floors_per_class() -> None:
    records = generate_manifest(240, seed=7)
    tr_idx, te_idx = stratified_split(records, 0.7, seed=7)
    train = [records[i] for i in tr_idx]
    test = [records[i] for i in te_idx]
    truth_tr, groups_tr = _truth_and_groups(train)
    truth_te, groups_te = _truth_and_groups(test)
    cm = CostModel()

    fz = Featurizer().fit(train)
    truth_arr = np.array(truth_tr)
    weights = np.where(truth_arr == 1, cm.c_fa, cm.c_fr)
    model = LogisticBaseline().fit(fz.transform(train), truth_arr, weights)

    def reports(scores_tr, scores_te, fixed=None):
        return heldout_reports_by_class(
            truth_tr, scores_tr, groups_tr, truth_te, scores_te, groups_te, cm, fixed
        )

    trained = reports(model.predict_proba(fz.transform(train)), model.predict_proba(fz.transform(test)))
    for name in ("always_pass", "always_reject"):
        floor_fn = BASELINES[name].score_fn
        floor = reports(floor_fn(train), floor_fn(test), FIXED_THRESHOLD)
        for cls in trained:
            assert (
                trained[cls].optimal.expected_cost_per_part
                <= floor[cls].optimal.expected_cost_per_part
            ), f"trained baseline lost to {name} on class {cls}"


def test_heldout_threshold_is_selected_on_train_not_test() -> None:
    # Train slice where the cost-optimal tau is unambiguous; test slice where sweeping ON TEST
    # would pick a different tau. The report must use the train tau.
    truth_tr, scores_tr = [0, 0, 1, 1], np.array([0.1, 0.2, 0.8, 0.9])
    groups = ["B"] * 4
    truth_te, scores_te = [0, 1, 1, 1], np.array([0.85, 0.9, 0.9, 0.9])
    out = heldout_reports_by_class(
        truth_tr, scores_tr, groups, truth_te, scores_te, groups, CostModel()
    )
    # train tau* = 0.8, margin-adjusted to the midpoint of its indifference interval (0.2, 0.8]
    # -> tau = 0.5. On test, the 0.85 good part gets scrapped (a swept-on-test tau of 0.9 would
    # hide that scrap and report a cheaper, dishonest number).
    assert out["B"].optimal.threshold == pytest.approx(0.5)
    assert out["B"].optimal.n_scraps == 1


def test_class_missing_from_train_falls_back_to_pooled_threshold() -> None:
    truth_tr, scores_tr = [0, 1, 0, 1], np.array([0.1, 0.9, 0.2, 0.8])
    groups_tr = ["B", "B", "C", "C"]
    truth_te, scores_te = [0, 1], np.array([0.1, 0.9])
    groups_te = ["D", "D"]  # never seen in train
    out = heldout_reports_by_class(
        truth_tr, scores_tr, groups_tr, truth_te, scores_te, groups_te, CostModel()
    )
    assert out["D"].optimal.n_escapes == 0 and out["D"].optimal.n_scraps == 0


def test_cli_main_runs_and_writes_cards(tmp_path) -> None:
    from evals.baselines.trained import main

    main(["--synthetic", "120", "--seed", "0", "--out", str(tmp_path)])
    cards = sorted(p.name for p in tmp_path.glob("*.json"))
    assert "logistic_indications.json" in cards
    assert {"always_pass.json", "always_reject.json", "amplitude_threshold.json"} <= set(cards)
