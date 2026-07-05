"""Orchestrates the cell's software skeleton end-to-end: intake -> sensing -> fusion -> record.

No hardware in this path -- sensing is synthetic (cell/sensing/synthetic.py) until there's a real
sensing head. See cell/README.md for what's real vs. simulated here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evals.scoring.economic_metric import CostModel

from .fusion.decision import Decision, decide
from .intake.models import Job
from .records.build import build_eval_record
from .sensing.synthetic import Indication, Scenario, generate_reading


@dataclass(frozen=True)
class InspectionResult:
    job: Job
    indications: list[Indication]
    decision: Decision
    record: dict[str, Any]


def run_inspection(
    job: Job,
    scenario: Scenario = "clean",
    seed: int | None = None,
    cost_model: CostModel | None = None,
) -> InspectionResult:
    indications = generate_reading(job, scenario=scenario, seed=seed)
    decision = decide(job, indications, cost_model=cost_model)
    record = build_eval_record(job, indications)
    return InspectionResult(job=job, indications=indications, decision=decision, record=record)
