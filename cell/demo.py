"""Runnable demo: `python -m cell.demo` (run from the repo root).

Mirrors evals/scoring/economic_metric.py's _demo() -- a runnable proof rather than a paragraph of
description. Submits a handful of jobs across ISO 5817 classes B/C/D and the v0 defect scenarios,
prints each decision + rationale, and prints one full schema-valid record.

Everything here is synthetic (see cell/sensing/synthetic.py) -- no hardware, no real dataset. The
point is to prove the intake -> sensing -> fusion -> record loop works end-to-end and that its
output already matches evals/schema/record.schema.json -- not to claim real inspection results.
"""

from __future__ import annotations

import json

from cell.intake.models import AcceptanceSpec, PartSpec
from cell.intake.service import JobIntake
from cell.pipeline import run_inspection

# lack_of_fusion appears at both D (passes) and B (rejects) -- the exact class-dependent boundary
# iso5817-acceptance.md calls out as "the whole point."
_RUNS = [
    ("clean", "B"),
    ("porosity", "B"),
    ("slag_inclusion", "C"),
    ("lack_of_fusion", "D"),
    ("lack_of_fusion", "B"),
    ("crack", "D"),
]


def main() -> None:
    intake = JobIntake()
    print("Cell software skeleton demo -- synthetic sensing, uncalibrated placeholder thresholds\n")

    example_record = None
    for i, (scenario, level) in enumerate(_RUNS):
        job = intake.submit(
            part=PartSpec(family="weld", material="carbon-steel", thickness_mm=12.0, joint_type="butt"),
            acceptance=AcceptanceSpec(level=level),
        )
        result = run_inspection(job, scenario=scenario, seed=i)
        print(f"[{job.job_id}] scenario={scenario:<15} class={level}  -> {result.decision.outcome.upper()}")
        print(f"    {result.decision.rationale}")
        if example_record is None and result.indications:
            example_record = result.record

    print("\nOne full schema-valid record (evals/schema/record.schema.json):\n")
    print(json.dumps(example_record, indent=2, default=str))


if __name__ == "__main__":
    main()
