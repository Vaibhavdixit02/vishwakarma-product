"""Reference implementation of the defect -> acceptance decision described in
iso5817-acceptance.md, parameterized by acceptance_rules.yaml.

This is the ONE place the defect/level -> pass/reject rule is implemented. Both the eval's
baselines harness (deriving ground truth for a manifest) and the product's cell (deriving both
its synthetic ground truth and, layered with a cost model, its own decision) import this, so the
two tracks can never quietly diverge on what "ground truth" means.

PLACEHOLDER WARNING: acceptance_rules.yaml's numbers are not calibrated against the ISO 5817
standard text or a partner WPS -- see that file and iso5817-acceptance.md's calibration backlog.
Anything derived from this module is directionally correct (crack never permitted, lack-of-fusion
only permitted at D, volumetric limits tightening B -> C -> D) but not a real acceptance number.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

import yaml

AcceptanceLevel = Literal["B", "C", "D"]

# Honest label for any ground-truth decision produced by this module: it is the right *shape* of
# rule, applied with placeholder numbers -- never claim a calibrated standard with this label.
DERIVED_BY = "iso5817-acceptance@v0-placeholder"

_RULES_PATH = Path(__file__).resolve().parent / "acceptance_rules.yaml"


class ScorableIndication(Protocol):
    """Anything with these three fields can be scored -- cell's Indication, a synthetic
    annotation, or a plain dict-like object all satisfy this without needing a shared base class."""

    id: str
    defect_type: str
    size_mm: float | None


@dataclass(frozen=True)
class AcceptanceRules:
    never_permitted: frozenset[str]
    level_d_only: frozenset[str]
    volumetric_limit_mm: dict[AcceptanceLevel, float]
    version: str


def _load_rules(path: Path = _RULES_PATH) -> AcceptanceRules:
    raw = yaml.safe_load(path.read_text())
    return AcceptanceRules(
        never_permitted=frozenset(raw["never_permitted"]),
        level_d_only=frozenset(raw["level_d_only"]),
        volumetric_limit_mm={k: float(v) for k, v in raw["volumetric_limit_mm"].items()},
        version=raw["version"],
    )


RULES = _load_rules()


@dataclass(frozen=True)
class ScoredResult:
    reject_score: float  # in [0, 1]
    governing_id: str | None


def score_indications(
    indications: list[ScorableIndication], level: AcceptanceLevel, rules: AcceptanceRules = RULES
) -> ScoredResult:
    """Score a set of indications against one acceptance level.

    Never-permitted types force score=1.0 outright; level-D-only types force score=1.0 unless the
    part ships at level D; everything else is volumetric and scores by how far its measured size
    sits past the level's placeholder limit. The governing indication is whichever one drove the
    highest score (ties keep the first one seen).
    """
    if not indications:
        return ScoredResult(0.0, None)

    best_score = 0.0
    governing: str | None = None

    for ind in indications:
        if ind.defect_type in rules.never_permitted:
            score = 1.0
        elif ind.defect_type in rules.level_d_only:
            score = 0.0 if level == "D" else 1.0
        elif ind.size_mm is not None:
            limit = rules.volumetric_limit_mm[level]
            score = min(1.0, ind.size_mm / limit)
        else:
            score = 0.0

        if score > best_score:
            best_score = score
            governing = ind.id

    return ScoredResult(best_score, governing)


def ground_truth_decision(
    indications: list[ScorableIndication], level: AcceptanceLevel, rules: AcceptanceRules = RULES
) -> tuple[Literal["pass", "reject"], str | None]:
    """The HARD ground-truth rule: reject iff some indication meets or exceeds its limit (score
    >= 1.0). Distinct from a model's own soft, calibratable operating threshold."""
    result = score_indications(indications, level, rules)
    if result.reject_score >= 1.0:
        return "reject", result.governing_id
    return "pass", None
