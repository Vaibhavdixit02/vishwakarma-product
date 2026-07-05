"""Fusion + decision — the cell's "brain" (docs/architecture.md).

Turns indications from sensing into a pass/reject decision *relative to the part's acceptance
class*, layering a cost-aware operating threshold on top of the shared, canonical rule in
evals/taxonomy/acceptance.py (which itself operationalizes evals/taxonomy/iso5817-acceptance.md:
cracks never permitted, lack-of-fusion only permitted at level D, volumetric defects tightening
B -> C -> D). The rule engine is shared with the eval baselines harness so the two tracks can't
quietly diverge on what "ground truth" means; this module adds the product-specific soft
threshold + cost rationale on top of that shared score.

PLACEHOLDER WARNING: evals/taxonomy/acceptance_rules.yaml's numeric limits and DEFAULT_THRESHOLD
below are not calibrated against the ISO 5817 standard text or a partner WPS -- see that file's
own calibration backlog. Once real labeled data exists, replace DEFAULT_THRESHOLD with the
cost-optimal tau from evals/scoring/economic_metric.evaluate() against it.
"""

from __future__ import annotations

from dataclasses import dataclass

from evals.scoring.economic_metric import CostModel
from evals.taxonomy.acceptance import ScoredResult, score_indications as _score_indications

from ..intake.models import AcceptanceLevel, Job
from ..sensing.synthetic import Indication

DEFAULT_THRESHOLD = 0.5  # placeholder tau; TODO calibrate via economic_metric.evaluate()


@dataclass(frozen=True)
class Decision:
    outcome: str  # "pass" | "reject"
    reject_score: float
    threshold: float
    governing_indication: str | None
    rationale: str


def score_indications(
    indications: list[Indication], level: AcceptanceLevel
) -> tuple[float, str | None]:
    """Return (reject_score in [0, 1], governing indication id or None).

    Thin wrapper around the shared evals.taxonomy.acceptance rule engine, kept for this module's
    existing call sites (cell/records/build.py, tests) and to preserve the tuple-shaped API.
    """
    result: ScoredResult = _score_indications(indications, level)
    return result.reject_score, result.governing_id


def decide(
    job: Job,
    indications: list[Indication],
    cost_model: CostModel | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> Decision:
    cost_model = cost_model or CostModel()
    score, governing = score_indications(indications, job.acceptance.level)
    outcome = "reject" if score >= threshold else "pass"

    if outcome == "reject":
        governing_ind = next(i for i in indications if i.id == governing)
        rationale = (
            f"REJECT: {governing_ind.defect_type} at level {job.acceptance.level} "
            f"(score={score:.2f} >= tau={threshold:.2f}). Escape cost if wrong: "
            f"${cost_model.c_fa:.0f}/part."
        )
    else:
        rationale = (
            f"PASS: no indication exceeded level {job.acceptance.level}'s limit "
            f"(score={score:.2f} < tau={threshold:.2f}). Scrap cost if wrong: "
            f"${cost_model.c_fr:.0f}/part."
        )

    return Decision(
        outcome=outcome,
        reject_score=score,
        threshold=threshold,
        governing_indication=governing,
        rationale=rationale,
    )
