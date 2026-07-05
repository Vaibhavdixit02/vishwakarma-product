"""Synthetic multimodal sensing — a stand-in for the real sensing head (docs/architecture.md).

No hardware exists yet. This generates indications directly instead of reading a real PAUT scan,
so the rest of the pipeline (fusion -> decision -> record) is buildable and testable today,
independent of the dataset-licensing question currently blocking the eval side
(evals/datasets/sources.md). Every indication this module produces is synthetic by construction;
records built from it are provenance-tagged accordingly (cell/records/build.py).

Indication fabrication (what a synthetic crack/LOF/slag/porosity reading looks like) is delegated
to evals/datasets/synthetic.py -- the canonical definition shared with the eval's own synthetic
smoke-test manifest generator, so the two tracks' synthetic data don't quietly diverge.
"""

from __future__ import annotations

import numpy as np
from typing import Literal

from evals.datasets.synthetic import Indication, fabricate

from ..intake.models import Job

Scenario = Literal["clean", "crack", "lack_of_fusion", "slag_inclusion", "porosity"]

_ISO6520_REF: dict[str, int | None] = {
    "crack": 100,
    "lack_of_fusion": 401,
    "slag_inclusion": 301,
    "porosity": 2017,
    "none": None,
}


def generate_reading(
    job: Job,
    scenario: Scenario = "clean",
    seed: int | None = None,
) -> list[Indication]:
    """Fabricate the indication(s) a sensing head would report for `job` under `scenario`.

    This is a scripted generator, not a physics simulation (CIVA-style simulation is the
    documented fallback in evals/datasets/sources.md if that's ever needed) — it exists only to
    drive the fusion/decision engine with realistic-shaped inputs while no hardware exists.
    """
    rng = np.random.default_rng(seed)

    if scenario == "clean":
        return []
    if scenario not in _ISO6520_REF:
        raise ValueError(f"unknown scenario: {scenario}")

    size, amplitude = fabricate(scenario, rng)
    return [
        Indication(
            id=f"{job.job_id}-ind-0",
            defect_type=scenario,
            iso6520_ref=_ISO6520_REF[scenario],
            size_mm=round(size, 2),
            amplitude_db=round(amplitude, 1),
        )
    ]
