"""Assemble a completed inspection into an eval-schema record (evals/schema/record.schema.json).

For a synthetic self-check run we know the true indications (we generated them), so we can fill
`ground_truth` here using the shared, canonical rule in evals/taxonomy/acceptance.py -- reject iff
an indication meets or exceeds its limit, or is a never-permitted type -- distinct from the
model's own soft, uncalibrated operating threshold in cell/fusion/decision.py. `derived_by` is
stamped "cell-synthetic-self-check@v0", not evals.taxonomy.acceptance.DERIVED_BY: beyond the rule's
own numeric limits being placeholders, the *indications themselves* are synthetic (we generated
them, nobody inspected a real part), so this is not a calibrated ground truth -- just a
self-consistent demonstration of the record-building loop.

For a real future inspected part, `ground_truth` requires an independently confirmed outcome (e.g.
certified-inspector sign-off) -- this module does not produce that; see cell/README.md.
"""

from __future__ import annotations

from typing import Any

from evals.schema.validate import validate_record
from evals.taxonomy.acceptance import ground_truth_decision

from ..intake.models import Job
from ..sensing.synthetic import Indication

DERIVED_BY = "cell-synthetic-self-check@v0"


def build_eval_record(job: Job, indications: list[Indication]) -> dict[str, Any]:
    gt_decision, gt_governing = ground_truth_decision(indications, job.acceptance.level)

    part: dict[str, Any] = {"family": job.part.family, "material": job.part.material}
    if job.part.thickness_mm is not None:
        part["thickness_mm"] = job.part.thickness_mm
    if job.part.joint_type is not None:
        part["joint_type"] = job.part.joint_type

    acceptance: dict[str, Any] = {"standard": job.acceptance.standard, "class": job.acceptance.level}
    if job.acceptance.spec_override is not None:
        acceptance["spec_override"] = job.acceptance.spec_override

    record: dict[str, Any] = {
        "record_id": job.job_id,
        "part": part,
        "acceptance": acceptance,
        "modalities": {
            "paut": {
                "scan_type": "A-scan",
                "data_ref": f"synthetic://cell-demo/{job.job_id}",
            }
        },
        "annotations": [
            {
                "id": ind.id,
                "defect_type": ind.defect_type,
                "iso6520_ref": ind.iso6520_ref,
                "modality": ind.modality,
                "size_mm": ind.size_mm,
            }
            for ind in indications
        ],
        "ground_truth": {
            "decision": gt_decision,
            "governing_defect": gt_governing,
            "derived_by": DERIVED_BY,
        },
        "provenance": {
            "source": "cell-synthetic-demo",
            "license": "n/a (internal synthetic, not for eval corpus use)",
            "synthetic": True,
            "label_source": "synthetic-generator",
        },
    }

    validate_record(record)
    return record
