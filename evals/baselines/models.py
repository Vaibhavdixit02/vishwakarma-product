"""Baseline "models" scored by economic_metric — the floor the real product must beat
(baselines/README.md). None of these are trained; they exist so the harness (run.py) is runnable
end-to-end today, before any real detector is implemented, per baselines/README.md's own
"what to run, in order of effort" list.

Every baseline is a `records -> per-part reject-likelihood scores` function (higher = more likely
reject, matching economic_metric's convention) plus a flag for how its operating point should be
evaluated:

  - fixed_point=True   the policy is a constant regardless of input (always_pass / always_reject);
                        report it at FIXED_THRESHOLD, not swept -- see evaluate_at's docstring for
                        why sweeping would defeat the point of these two floors.
  - fixed_point=False   the score is a genuine (if crude) discriminative signal; sweep for its
                        cost-optimal operating point via the normal evaluate()/evaluate_by_group().
"""

from __future__ import annotations

from typing import Any, Callable, NamedTuple

import numpy as np

# Halfway between always_pass's constant 0.0 and always_reject's constant 1.0 -- any fixed value
# strictly between the two works identically, this one just reads naturally as "the midpoint".
FIXED_THRESHOLD = 0.5


def _peak_amplitude_db(record: dict[str, Any], no_signal_db: float) -> float:
    amps = [a["amplitude_db"] for a in record.get("annotations", []) if "amplitude_db" in a]
    return max(amps) if amps else no_signal_db


def always_pass_scores(records: list[dict[str, Any]]) -> np.ndarray:
    """Never reject anything — the "everything ships" floor. Makes the accuracy paradox concrete:
    on rare-defect data this scores high accuracy while eating every escape."""
    return np.zeros(len(records))


def always_reject_scores(records: list[dict[str, Any]]) -> np.ndarray:
    """Reject everything — the "nothing ships" floor: zero escapes, maximum scrap."""
    return np.ones(len(records))


def amplitude_threshold_scores(
    records: list[dict[str, Any]], no_signal_db: float = -20.0
) -> np.ndarray:
    """The classic NDT heuristic: the hotter a part's strongest reflector, the more likely reject
    (a 6 dB-drop-style sizing rule, operationalized here as the peak annotated `amplitude_db`
    across a part's PAUT indications). A real, if crude, discriminative signal — unlike the two
    trivial baselines above — so it's evaluated by sweeping for its cost-optimal threshold."""
    return np.array([_peak_amplitude_db(r, no_signal_db) for r in records], dtype=float)


class Baseline(NamedTuple):
    name: str
    describe: str
    score_fn: Callable[[list[dict[str, Any]]], np.ndarray]
    fixed_point: bool


BASELINES: dict[str, Baseline] = {
    "always_pass": Baseline(
        name="always_pass",
        describe="Never reject anything (the 'everything ships' floor).",
        score_fn=always_pass_scores,
        fixed_point=True,
    ),
    "always_reject": Baseline(
        name="always_reject",
        describe="Reject everything (the 'nothing ships' floor).",
        score_fn=always_reject_scores,
        fixed_point=True,
    ),
    "amplitude_threshold": Baseline(
        name="amplitude_threshold",
        describe="Classic NDT heuristic: reject on peak reflector amplitude (6dB-drop-style sizing).",
        score_fn=amplitude_threshold_scores,
        fixed_point=False,
    ),
}
