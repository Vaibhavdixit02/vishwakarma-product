"""Tests for the shared, canonical rule engine (evals/taxonomy/acceptance.py) — the one place
defect+level -> pass/reject is implemented, shared by cell/fusion/decision.py and the eval
baselines harness. These pin down the *qualitative* behavior from iso5817-acceptance.md; the
underlying numeric limits are placeholders (see acceptance_rules.yaml) and are not asserted here.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from evals.taxonomy.acceptance import ground_truth_decision, score_indications


@dataclass(frozen=True)
class _Ind:
    id: str
    defect_type: str
    size_mm: float | None


@pytest.mark.parametrize("level", ["B", "C", "D"])
def test_crack_never_permitted(level: str) -> None:
    result = score_indications([_Ind("i0", "crack", 0.1)], level)
    assert result.reject_score == 1.0
    assert result.governing_id == "i0"


def test_lack_of_fusion_permitted_only_at_level_d() -> None:
    ind = [_Ind("i0", "lack_of_fusion", 5.0)]
    assert score_indications(ind, "B").reject_score == 1.0
    assert score_indications(ind, "C").reject_score == 1.0
    assert score_indications(ind, "D").reject_score == 0.0


@pytest.mark.parametrize("defect_type", ["slag_inclusion", "porosity"])
def test_volumetric_limits_tighten_b_to_c_to_d(defect_type: str) -> None:
    # A fixed size that's over B's limit, under C's and D's -- same defect, three different
    # decisions purely because of the acceptance class it ships under (the benchmark's whole point).
    ind = [_Ind("i0", defect_type, 2.0)]
    assert score_indications(ind, "B").reject_score >= 1.0
    assert score_indications(ind, "C").reject_score < 1.0
    assert score_indications(ind, "D").reject_score < 1.0


def test_no_indications_is_a_clean_pass() -> None:
    result = score_indications([], "B")
    assert result.reject_score == 0.0
    assert result.governing_id is None


def test_governing_indication_is_the_worst_offender() -> None:
    ind = [_Ind("small", "porosity", 0.1), _Ind("crack", "crack", 0.1)]
    result = score_indications(ind, "D")
    assert result.governing_id == "crack"
    assert result.reject_score == 1.0


def test_ground_truth_decision_matches_hard_cutoff() -> None:
    decision, governing = ground_truth_decision([_Ind("i0", "crack", 1.0)], "D")
    assert decision == "reject"
    assert governing == "i0"

    decision, governing = ground_truth_decision([], "B")
    assert decision == "pass"
    assert governing is None
