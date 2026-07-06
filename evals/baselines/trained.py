"""First *trained* baseline + the honest train/holdout protocol around it.

baselines/README.md's model-based rows (U-Net / YOLO on scan images) are genuinely blocked on
real ingested scans — but the *training loop* around any learned model is not, and building it
now is the point of this module: the day a real manifest lands, the only thing that changes is
the model class, not the protocol. The model here is a small pure-numpy logistic regression over
indication-level features (no torch/sklearn — nothing this size needs them, and the core install
stays sufficient).

Protocol — and how it differs from run.py:

  run.py sweeps each baseline's threshold on the SAME records it reports. That is fine for the
  named floors and an untuned heuristic card, but it is in-sample optimism for anything with
  fitted parameters. Here, everything printed is held-out:

    1. stratified split (by ground-truth decision x acceptance class) into train/test
    2. fit the model on train only (featurizer vocabulary included)
    3. select each baseline's cost-optimal threshold per acceptance class ON TRAIN
    4. report expected cost per part at that frozen threshold ON TEST

  The comparison baselines (always_pass / always_reject / amplitude_threshold) are re-run under
  this same protocol so the card is apples-to-apples — the heuristic's threshold is also chosen
  on train and frozen, not swept on test.

Feature convention: features come from `annotations` (the indication a sensing head / upstream
detector would emit — same convention amplitude_threshold_scores already uses), never from
`ground_truth`. On the synthetic smoke-test manifest the ground truth is a deterministic function
of (defect type, size, class), so this model scoring near-perfect there is expected and means
nothing — synthetic runs validate the loop, not the model. Never quote them as benchmark results.

Usage:
  python -m evals.baselines.trained --synthetic 300 --seed 0
  python -m evals.baselines.trained --manifest records.jsonl --train-frac 0.7 --out results/
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from evals.baselines.models import BASELINES, FIXED_THRESHOLD, _peak_amplitude_db
from evals.baselines.run import _card, _load_manifest, _truth_and_groups
from evals.datasets.synthetic import generate_manifest
from evals.scoring.economic_metric import CostModel, Report, evaluate, evaluate_at

NO_SIGNAL_DB = -20.0


# ---------------------------------------------------------------------------- features


@dataclass
class Featurizer:
    """Record -> feature vector. Vocabulary (defect types, acceptance classes) is learned from
    the TRAIN split only, so unseen categories at test time fall into all-zero one-hots instead
    of silently reshaping the matrix."""

    defect_types: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)

    def fit(self, records: list[dict[str, Any]]) -> "Featurizer":
        types: set[str] = set()
        classes: set[str] = set()
        for r in records:
            classes.add(r["acceptance"]["class"])
            for a in r.get("annotations", []):
                if a.get("defect_type"):
                    types.add(a["defect_type"])
        self.defect_types = sorted(types)
        self.classes = sorted(classes)
        return self

    @property
    def names(self) -> list[str]:
        return (
            ["peak_amplitude_db", "max_size_mm", "total_size_mm", "n_indications"]
            + [f"type={t}" for t in self.defect_types]
            + [f"class={c}" for c in self.classes]
            + [f"size*type={t}" for t in self.defect_types]
            + [f"type={t}*class={c}" for t in self.defect_types for c in self.classes]
        )

    def transform(self, records: list[dict[str, Any]]) -> np.ndarray:
        rows = []
        for r in records:
            anns = r.get("annotations", [])
            sizes = [a["size_mm"] for a in anns if "size_mm" in a]
            peak_amp = _peak_amplitude_db(r, NO_SIGNAL_DB)
            # defect type of the governing (peak-amplitude) indication, if any
            governing = max(anns, key=lambda a: a.get("amplitude_db", NO_SIGNAL_DB), default=None)
            gov_type = governing.get("defect_type") if governing else None
            max_size = max(sizes, default=0.0)
            cls = r["acceptance"]["class"]
            type_1h = [1.0 if gov_type == t else 0.0 for t in self.defect_types]
            class_1h = [1.0 if cls == c else 0.0 for c in self.classes]
            row = [peak_amp, max_size, sum(sizes), float(len(anns))]
            row += type_1h
            row += class_1h
            # Interactions: acceptance rules are per-(defect type, class) size thresholds, a
            # function family a linear model over the marginal features above cannot represent
            # ("reject if a_t*size > b_tc" needs size*type and type*class terms). Without these,
            # the model is confidently wrong exactly on borderline-size defects — the expensive
            # records.
            row += [s * max_size for s in type_1h]
            row += [s * c1 for s in type_1h for c1 in class_1h]
            rows.append(row)
        return np.asarray(rows, dtype=float)


# ---------------------------------------------------------------------------- model


@dataclass
class LogisticBaseline:
    """L2-regularized logistic regression fit by IRLS (Newton) — deterministic, no learning-rate
    knob, converges in a handful of iterations at this scale. Features are standardized with
    train-split statistics.

    `sample_weight` is how the cost model reaches the *loss*, not just the threshold: weighting
    each part by the dollar cost of getting it wrong (c_fa if truly-reject, c_fr if truly-pass)
    makes the fit minimize expected-cost-weighted log-loss. Without it, a plain logistic happily
    trades one escape for several avoided scraps — the exact trade the benchmark exists to price —
    and can lose to always_reject on cost while beating it on accuracy (observed on the synthetic
    manifest before this was added)."""

    l2: float = 1e-3
    max_iter: int = 100
    tol: float = 1e-9

    def fit(
        self, X: np.ndarray, y: np.ndarray, sample_weight: np.ndarray | None = None
    ) -> "LogisticBaseline":
        y = np.asarray(y, dtype=float).ravel()
        sw = np.ones_like(y) if sample_weight is None else np.asarray(sample_weight, float).ravel()
        if (sw < 0).any() or sw.sum() == 0:
            raise ValueError("sample_weight must be non-negative and not all zero")
        sw = sw / sw.mean()
        self._mu = X.mean(axis=0)
        self._sigma = np.where(X.std(axis=0) > 0, X.std(axis=0), 1.0)
        Xs = np.column_stack([np.ones(len(X)), (X - self._mu) / self._sigma])

        w = np.zeros(Xs.shape[1])
        if 0.0 < y.mean() < 1.0:  # degenerate single-class train data -> keep the prior intercept
            for _ in range(self.max_iter):
                p = self._sigmoid(Xs @ w)
                grad = Xs.T @ (sw * (p - y)) + self.l2 * np.r_[0.0, w[1:]]
                hess = (Xs * (sw * p * (1 - p))[:, None]).T @ Xs + self.l2 * np.eye(len(w))
                step = np.linalg.solve(hess, grad)
                w -= step
                if float(np.abs(step).max()) < self.tol:
                    break
        else:
            # log-odds of the constant class, clipped away from +/-inf
            w[0] = float(np.log((y.mean() + 1e-6) / (1 - y.mean() + 1e-6)))
        self._w = w
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        Xs = np.column_stack([np.ones(len(X)), (X - self._mu) / self._sigma])
        return self._sigmoid(Xs @ self._w)

    @staticmethod
    def _sigmoid(z: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(z, -35.0, 35.0)))


# ---------------------------------------------------------------------------- protocol


def stratified_split(
    records: list[dict[str, Any]], train_frac: float, seed: int | None
) -> tuple[list[int], list[int]]:
    """Index split stratified by (ground-truth decision, acceptance class), so a small manifest
    can't end up with, say, every class-B defect in test. Any stratum with >= 2 members
    contributes at least one record to each side."""
    if not 0.0 < train_frac < 1.0:
        raise ValueError("train_frac must be in (0, 1)")
    truth, groups = _truth_and_groups(records)
    rng = np.random.default_rng(seed)
    strata: dict[tuple[int, str], list[int]] = {}
    for i, key in enumerate(zip(truth, groups)):
        strata.setdefault(key, []).append(i)
    train_idx: list[int] = []
    test_idx: list[int] = []
    for key in sorted(strata):
        idx = np.array(strata[key])
        rng.shuffle(idx)
        n_train = int(round(train_frac * len(idx)))
        if len(idx) >= 2:
            n_train = min(max(n_train, 1), len(idx) - 1)
        train_idx += idx[:n_train].tolist()
        test_idx += idx[n_train:].tolist()
    return sorted(train_idx), sorted(test_idx)


def _margin_tau(scores_tr: np.ndarray, tau: float) -> float:
    """Move a train-selected threshold to the midpoint of its indifference interval.

    evaluate() sweeps candidate thresholds AT the observed scores, so the tau it returns sits
    exactly on the lowest train score it rejects. Every tau in the open interval down to the next
    train score below has *identical* train cost — but the endpoint has zero margin: a held-out
    defect scoring a hair under the lowest rejected train defect escapes. The midpoint of that
    interval is the max-margin choice among train-cost-equivalent thresholds (same reasoning as
    decision stumps splitting between observed values)."""
    below = scores_tr[scores_tr < tau]
    return float((tau + below.max()) / 2.0) if below.size else tau


def heldout_reports_by_class(
    truth_tr: Sequence[int],
    scores_tr: np.ndarray,
    groups_tr: Sequence[str],
    truth_te: Sequence[int],
    scores_te: np.ndarray,
    groups_te: Sequence[str],
    cost_model: CostModel,
    fixed_threshold: float | None = None,
) -> dict[str, Report]:
    """Steps 3+4 of the protocol: per acceptance class, pick the cost-optimal threshold on the
    train slice (margin-adjusted, see _margin_tau), then evaluate the test slice AT that frozen
    threshold. `fixed_threshold` skips the selection for by-construction policies (the two
    trivial floors). A class absent from train falls back to the threshold selected on all of
    train pooled."""
    truth_tr = np.asarray(truth_tr, dtype=int)
    truth_te = np.asarray(truth_te, dtype=int)
    groups_tr = np.asarray(groups_tr)
    groups_te = np.asarray(groups_te)
    pooled_tau: float | None = None
    out: dict[str, Report] = {}
    for cls in sorted(set(groups_te.tolist())):
        if fixed_threshold is not None:
            tau = fixed_threshold
        elif (groups_tr == cls).any():
            m = groups_tr == cls
            tau = _margin_tau(
                scores_tr[m], evaluate(truth_tr[m], scores_tr[m], cost_model).optimal.threshold
            )
        else:
            if pooled_tau is None:
                pooled_tau = _margin_tau(
                    scores_tr, evaluate(truth_tr, scores_tr, cost_model).optimal.threshold
                )
            tau = pooled_tau
        m_te = groups_te == cls
        out[str(cls)] = evaluate_at(truth_te[m_te], scores_te[m_te], tau, cost_model)
    return out


# ---------------------------------------------------------------------------- harness


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Train the logistic baseline and report held-out cost (train/holdout protocol)."
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--synthetic", type=int, metavar="N", help="generate N synthetic records")
    src.add_argument("--manifest", type=Path, help="path to a JSONL manifest of schema-valid records")
    p.add_argument("--seed", type=int, default=0, help="seed for generation AND the split")
    p.add_argument("--defect-rate", type=float, default=0.5, help="--synthetic defect fraction")
    p.add_argument("--train-frac", type=float, default=0.7, help="fraction of records to train on")
    p.add_argument("--c-fa", type=float, default=CostModel().c_fa, help="dollar cost of an escape")
    p.add_argument("--c-fr", type=float, default=CostModel().c_fr, help="dollar cost of a scrap")
    p.add_argument("--out", type=Path, help="directory to write one results/<name>.json card into")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.manifest:
        records = _load_manifest(args.manifest)
        source_note = f"manifest: {args.manifest}"
    else:
        n = args.synthetic if args.synthetic is not None else 300
        records = generate_manifest(n, seed=args.seed, defect_rate=args.defect_rate)
        source_note = (
            f"synthetic smoke-test, n={n}, seed={args.seed} "
            "-- validates the training loop, NOT the model (see module docstring)"
        )

    train_idx, test_idx = stratified_split(records, args.train_frac, seed=args.seed)
    train = [records[i] for i in train_idx]
    test = [records[i] for i in test_idx]
    truth_tr, groups_tr = _truth_and_groups(train)
    truth_te, groups_te = _truth_and_groups(test)
    cost_model = CostModel(c_fa=args.c_fa, c_fr=args.c_fr)

    featurizer = Featurizer().fit(train)
    truth_arr = np.array(truth_tr)
    cost_weights = np.where(truth_arr == 1, cost_model.c_fa, cost_model.c_fr)
    model = LogisticBaseline().fit(featurizer.transform(train), truth_arr, cost_weights)

    # Trained model + the run.py baselines, all under the same held-out protocol.
    entries: list[tuple[str, str, np.ndarray, np.ndarray, float | None]] = [
        (
            "logistic_indications",
            "Trained: cost-weighted logistic on indication features (fit on train, frozen tau).",
            model.predict_proba(featurizer.transform(train)),
            model.predict_proba(featurizer.transform(test)),
            None,
        )
    ]
    for b in BASELINES.values():
        entries.append(
            (
                b.name,
                b.describe,
                b.score_fn(train),
                b.score_fn(test),
                FIXED_THRESHOLD if b.fixed_point else None,
            )
        )

    print(f"Trained-baseline harness -- {source_note}")
    print(
        f"split: train={len(train)} test={len(test)} (train_frac={args.train_frac}, seed={args.seed})"
        f"  cost model: escape=${cost_model.c_fa:.0f}  scrap=${cost_model.c_fr:.0f}"
    )
    print("all numbers below are HELD-OUT (thresholds selected on train, frozen, applied to test)\n")

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)

    for name, describe, scores_tr, scores_te, fixed in entries:
        reports = heldout_reports_by_class(
            truth_tr, scores_tr, groups_tr, truth_te, scores_te, groups_te, cost_model, fixed
        )
        print(_card(name, describe, reports))
        print()
        if args.out:
            card = {
                "baseline": name,
                "describe": describe,
                "source": source_note,
                "protocol": "train/holdout: thresholds selected on train, reported on test",
                "split": {"train": len(train), "test": len(test), "train_frac": args.train_frac},
                "cost_model": asdict(cost_model),
                "per_class": {cls: asdict(r.optimal) for cls, r in reports.items()},
            }
            (args.out / f"{name}.json").write_text(json.dumps(card, indent=2))

    if args.out:
        print(f"Wrote results cards to {args.out}/")


if __name__ == "__main__":
    main()
