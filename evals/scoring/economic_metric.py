"""Economic, decision-oriented scoring for inspection models.

The thesis of this whole benchmark in one file: **accuracy is the wrong metric for
inspection.** A shop does not care about AUROC; it cares about the dollars lost to the two
mistakes an inspector can make:

  - ESCAPE  (false-accept): the model PASSES a part the acceptance class says REJECT.
            The expensive one — warranty, recall, field failure.   cost = c_fa
  - SCRAP   (false-reject): the model REJECTS a part the class says is acceptable.
            Wasted good part + rework.                              cost = c_fr

We score a model by the **expected cost per part** at its cost-optimal operating point,
optionally subject to a hard cap on the escape rate (the "regulatory floor"). We also report
plain accuracy alongside — so the gap between "accurate" and "economically good" is visible.

Ground truth is a per-part pass/reject decision *relative to the part's acceptance class*
(see ../taxonomy/iso5817-acceptance.md). This module is class-agnostic: feed it the decisions
and scores for whatever class slice you want, or use `evaluate_by_group`.

Run `python economic_metric.py` for a synthetic demo that shows a "more accurate" model losing
to a "more cautious" one on expected cost.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Sequence

import numpy as np

# Convention: truth/pred 1 = REJECT (defect beyond limit), 0 = PASS (acceptable).
# Model `scores`: higher => more likely REJECT. Decision at threshold tau: reject if score >= tau.


@dataclass(frozen=True)
class CostModel:
    """Dollar cost of each error type. Defaults are placeholder ranges — the point is that a
    buyer supplies their own; an escaped weld crack and an escaped cosmetic pore are not equal."""

    c_fa: float = 1000.0  # escape (false-accept) — the expensive error
    c_fr: float = 50.0    # scrap (false-reject) — waste + rework

    def __post_init__(self) -> None:
        if self.c_fa < 0 or self.c_fr < 0:
            raise ValueError("costs must be non-negative")


@dataclass(frozen=True)
class OperatingPoint:
    threshold: float
    expected_cost_per_part: float
    n_escapes: int
    n_scraps: int
    escape_rate_of_defects: float  # P(pass | truly reject) — the regulatory-floor quantity
    scrap_rate_of_good: float      # P(reject | truly pass)
    accuracy: float                # plain agreement, reported for contrast


@dataclass(frozen=True)
class Report:
    optimal: OperatingPoint               # unconstrained cost-optimal
    constrained: OperatingPoint | None    # cost-optimal s.t. escape_rate_of_defects <= epsilon
    epsilon: float | None
    n: int
    n_defective: int
    cost_model: dict
    # cost_curve: thresholds and the cost at each, for plotting the full risk/waste tradeoff
    curve_thresholds: list[float]
    curve_costs: list[float]

    def summary(self) -> str:
        o = self.optimal
        lines = [
            f"N={self.n}  defective={self.n_defective}  "
            f"(c_fa={self.cost_model['c_fa']}, c_fr={self.cost_model['c_fr']})",
            f"cost-optimal:   tau*={o.threshold:.3f}  "
            f"cost/part=${o.expected_cost_per_part:.2f}  "
            f"escapes={o.n_escapes} scraps={o.n_scraps}  "
            f"miss-rate={o.escape_rate_of_defects:.1%}  acc={o.accuracy:.1%}",
        ]
        if self.constrained is not None:
            c = self.constrained
            lines.append(
                f"floor (miss<= {self.epsilon:.0%}): tau={c.threshold:.3f}  "
                f"cost/part=${c.expected_cost_per_part:.2f}  "
                f"escapes={c.n_escapes} scraps={c.n_scraps}  miss-rate={c.escape_rate_of_defects:.1%}"
            )
        return "\n".join(lines)


def _as_arrays(truth, scores):
    truth = np.asarray(truth).astype(int).ravel()
    scores = np.asarray(scores, dtype=float).ravel()
    if truth.shape != scores.shape:
        raise ValueError(f"truth {truth.shape} and scores {scores.shape} must match")
    if not np.isin(truth, (0, 1)).all():
        raise ValueError("truth must be 0 (pass) / 1 (reject)")
    return truth, scores


def _point_at(truth: np.ndarray, scores: np.ndarray, tau: float, cm: CostModel) -> OperatingPoint:
    pred = (scores >= tau).astype(int)
    n = truth.size
    n_pos = int(truth.sum())          # truly reject
    n_neg = n - n_pos                 # truly pass
    escapes = int(((pred == 0) & (truth == 1)).sum())  # passed a reject
    scraps = int(((pred == 1) & (truth == 0)).sum())   # rejected a pass
    cost = (cm.c_fa * escapes + cm.c_fr * scraps) / n
    return OperatingPoint(
        threshold=float(tau),
        expected_cost_per_part=cost,
        n_escapes=escapes,
        n_scraps=scraps,
        escape_rate_of_defects=(escapes / n_pos) if n_pos else 0.0,
        scrap_rate_of_good=(scraps / n_neg) if n_neg else 0.0,
        accuracy=float((pred == truth).mean()),
    )


def _candidate_thresholds(scores: np.ndarray) -> np.ndarray:
    # Unique scores plus a point just above the max (predict-all-pass) sweep the full curve.
    uniq = np.unique(scores)
    hi = uniq[-1] + 1.0 if uniq.size else 1.0
    return np.concatenate([uniq, [hi]])


def evaluate(
    truth: Sequence[int],
    scores: Sequence[float],
    cost_model: CostModel | None = None,
    epsilon: float | None = None,
) -> Report:
    """Score one model on one slice.

    truth   : per-part ground-truth decision (1=reject, 0=pass), already relative to the class.
    scores  : model's reject-likelihood per part (higher = more likely reject).
    epsilon : optional cap on escape_rate_of_defects (P(pass|reject)) for the constrained optimum.
    """
    cm = cost_model or CostModel()
    truth, scores = _as_arrays(truth, scores)
    taus = _candidate_thresholds(scores)

    points = [_point_at(truth, scores, t, cm) for t in taus]
    costs = np.array([p.expected_cost_per_part for p in points])

    optimal = points[int(np.argmin(costs))]

    constrained = None
    if epsilon is not None:
        feasible = [p for p in points if p.escape_rate_of_defects <= epsilon]
        if feasible:
            constrained = min(feasible, key=lambda p: p.expected_cost_per_part)

    return Report(
        optimal=optimal,
        constrained=constrained,
        epsilon=epsilon,
        n=int(truth.size),
        n_defective=int(truth.sum()),
        cost_model=asdict(cm),
        curve_thresholds=[float(t) for t in taus],
        curve_costs=[float(c) for c in costs],
    )


def evaluate_by_group(
    truth: Sequence[int],
    scores: Sequence[float],
    groups: Sequence[str],
    cost_model: CostModel | None = None,
    epsilon: float | None = None,
) -> dict[str, Report]:
    """Score per acceptance class (or any grouping). The same defect flips decision across
    classes, so per-class reporting is where the multimodal+economic story actually shows up."""
    truth = np.asarray(truth).astype(int).ravel()
    scores = np.asarray(scores, dtype=float).ravel()
    groups = np.asarray(groups).ravel()
    out: dict[str, Report] = {}
    for g in sorted(set(groups.tolist())):
        m = groups == g
        out[str(g)] = evaluate(truth[m], scores[m], cost_model, epsilon)
    return out


def evaluate_at(
    truth: Sequence[int],
    scores: Sequence[float],
    threshold: float,
    cost_model: CostModel | None = None,
) -> Report:
    """Evaluate at ONE caller-chosen threshold instead of sweeping for the cost-optimal one.

    Useful for a baseline whose operating point is fixed by construction (e.g. an always-pass /
    always-reject trivial floor baseline) rather than something to search over -- sweeping those
    would silently let the "optimizer" pick whichever of the two constant policies is cheaper,
    hiding the point of reporting them as distinct named floors. Returned as a `Report` (with
    `constrained=None`) so callers can treat it the same way as `evaluate()`'s output.
    """
    cm = cost_model or CostModel()
    truth, scores = _as_arrays(truth, scores)
    point = _point_at(truth, scores, threshold, cm)
    return Report(
        optimal=point,
        constrained=None,
        epsilon=None,
        n=int(truth.size),
        n_defective=int(truth.sum()),
        cost_model=asdict(cm),
        curve_thresholds=[threshold],
        curve_costs=[point.expected_cost_per_part],
    )


def evaluate_at_by_group(
    truth: Sequence[int],
    scores: Sequence[float],
    groups: Sequence[str],
    threshold: float,
    cost_model: CostModel | None = None,
) -> dict[str, Report]:
    """`evaluate_at`, sliced per group -- the fixed-threshold counterpart to `evaluate_by_group`."""
    truth = np.asarray(truth).astype(int).ravel()
    scores = np.asarray(scores, dtype=float).ravel()
    groups = np.asarray(groups).ravel()
    out: dict[str, Report] = {}
    for g in sorted(set(groups.tolist())):
        m = groups == g
        out[str(g)] = evaluate_at(truth[m], scores[m], threshold, cost_model)
    return out


def _demo() -> None:
    """Two models with IDENTICAL accuracy but opposite error types — the cleanest proof that
    accuracy can't rank inspectors. Both make exactly `k` mistakes, so both score the same
    accuracy. But Model A's mistakes are all ESCAPES (it passes real defects) and Model B's are
    all SCRAPS (it rejects good parts). With an escape 20x costlier than a scrap, A costs 20x
    more to run while looking exactly as good on an accuracy report. (Construction is deliberate,
    not tuned: this divergence is structural, not a lucky seed.)
    """
    rng = np.random.default_rng(0)
    n = 2000
    truth = (rng.random(n) < 0.12).astype(int)  # ~12% truly reject
    pos_idx = np.flatnonzero(truth == 1)
    neg_idx = np.flatnonzero(truth == 0)
    k = 30  # both models make exactly k errors

    a = truth.astype(float).copy()
    a[pos_idx[:k]] = 0.0   # Model A misses k real defects -> k escapes, 0 scraps
    b = truth.astype(float).copy()
    b[neg_idx[:k]] = 1.0   # Model B falsely rejects k good parts -> 0 escapes, k scraps

    cm = CostModel(c_fa=1000.0, c_fr=50.0)  # escape costs 20x a scrap
    ra = evaluate(truth, a, cm)
    rb = evaluate(truth, b, cm)

    print("Cost model: escape = $1000, scrap = $50  (escape is 20x worse)\n")
    print("MODEL A — errors are all ESCAPES (passes real defects)")
    print(ra.summary())
    print("\nMODEL B — errors are all SCRAPS (rejects good parts)")
    print(rb.summary())
    print(
        f"\n=> Same accuracy ({ra.optimal.accuracy:.1%} vs {rb.optimal.accuracy:.1%}), "
        f"but A costs ${ra.optimal.expected_cost_per_part:.2f}/part vs "
        f"B's ${rb.optimal.expected_cost_per_part:.2f}/part "
        f"({ra.optimal.expected_cost_per_part / rb.optimal.expected_cost_per_part:.0f}x)."
    )
    print("   Accuracy cannot tell these two apart. Expected cost can. That gap is the benchmark.")


if __name__ == "__main__":
    _demo()
