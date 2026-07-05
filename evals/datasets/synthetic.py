"""Synthetic-but-schema-valid indication/record generator.

NOT the v0 seed corpus -- see sources.md for the real public-PAUT-aggregation plan, currently
blocked on license verification. This exists so the rest of the eval apparatus (the baselines
harness, the economic-metric wiring, the schema) can be exercised end-to-end right now, without
waiting on that external gate. Every record this produces is provenance-tagged `synthetic: true`,
`source: "synthetic-smoke-test"` -- never mix these into a real leaderboard number.

This is also the canonical source of "what a synthetic indication of defect type X looks like":
cell/sensing/synthetic.py (the product's stand-in for a real sensing head) imports `fabricate`
from here instead of duplicating the same magic numbers, so the two tracks' synthetic data share
one definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from evals.schema.validate import validate_record
from evals.taxonomy.acceptance import AcceptanceLevel, ground_truth_decision

DefectType = Literal["crack", "lack_of_fusion", "slag_inclusion", "porosity", "none"]

ISO6520_REF: dict[str, int | None] = {
    "crack": 100,
    "lack_of_fusion": 401,
    "slag_inclusion": 301,
    "porosity": 2017,
    "none": None,
}

DERIVED_BY = "eval-synthetic-smoke-test@v0"

_DEFECT_TYPES: tuple[DefectType, ...] = ("crack", "lack_of_fusion", "slag_inclusion", "porosity")
_LEVELS: tuple[AcceptanceLevel, ...] = ("B", "C", "D")


@dataclass(frozen=True)
class Indication:
    """One defect indication as a sensing head would localize and size it. `amplitude_db` stands
    in for a real PAUT reflector amplitude (e.g. relative to a DAC reference curve) -- the signal
    an amplitude-threshold baseline acts on; `size_mm` is what a technician would measure off it."""

    id: str
    defect_type: DefectType
    iso6520_ref: int | None
    size_mm: float
    amplitude_db: float
    modality: str = "paut"


def fabricate(defect_type: DefectType, rng: np.random.Generator) -> tuple[float, float]:
    """Return (size_mm, amplitude_db) for one indication of `defect_type`. Ranges are chosen to
    be plausible-shaped -- not measured off any real PAUT rig (see module docstring)."""
    if defect_type == "crack":
        return float(rng.uniform(0.5, 3.0)), float(rng.uniform(6.0, 20.0))
    if defect_type == "lack_of_fusion":
        return float(rng.uniform(1.0, 6.0)), float(rng.uniform(4.0, 14.0))
    if defect_type == "slag_inclusion":
        return float(rng.uniform(0.5, 5.0)), float(rng.uniform(-4.0, 8.0))
    if defect_type == "porosity":
        return float(rng.uniform(0.3, 4.0)), float(rng.uniform(-6.0, 6.0))
    raise ValueError(f"no fabrication profile for defect_type={defect_type!r}")


def generate_indications(
    record_id: str, defect_type: DefectType | None, rng: np.random.Generator
) -> list[Indication]:
    """`defect_type=None` (or `"none"`) means a clean part -- no indications."""
    if defect_type is None or defect_type == "none":
        return []
    size, amplitude = fabricate(defect_type, rng)
    return [
        Indication(
            id=f"{record_id}-ind-0",
            defect_type=defect_type,
            iso6520_ref=ISO6520_REF[defect_type],
            size_mm=round(size, 2),
            amplitude_db=round(amplitude, 1),
        )
    ]


def _record(
    record_id: str, level: AcceptanceLevel, indications: list[Indication]
) -> dict[str, Any]:
    gt_decision, gt_governing = ground_truth_decision(indications, level)
    record: dict[str, Any] = {
        "record_id": record_id,
        "part": {"family": "weld", "material": "carbon-steel"},
        "acceptance": {"standard": "ISO 5817", "class": level},
        "modalities": {
            "paut": {
                "scan_type": "A-scan",
                "data_ref": f"synthetic://eval-smoke-test/{record_id}",
            }
        },
        "annotations": [
            {
                "id": ind.id,
                "defect_type": ind.defect_type,
                "iso6520_ref": ind.iso6520_ref,
                "modality": ind.modality,
                "size_mm": ind.size_mm,
                "amplitude_db": ind.amplitude_db,
            }
            for ind in indications
        ],
        "ground_truth": {
            "decision": gt_decision,
            "governing_defect": gt_governing,
            "derived_by": DERIVED_BY,
        },
        "provenance": {
            "source": "synthetic-smoke-test",
            "license": "n/a (internal synthetic, not for eval corpus/leaderboard use)",
            "synthetic": True,
            "label_source": "synthetic-generator",
        },
    }
    validate_record(record)
    return record


def generate_manifest(
    n: int,
    seed: int | None = None,
    levels: tuple[AcceptanceLevel, ...] = _LEVELS,
    defect_rate: float = 0.5,
) -> list[dict[str, Any]]:
    """Generate `n` schema-valid, ground-truth-labeled synthetic records, round-robined across
    `levels`, with `defect_rate` fraction carrying one indication (type drawn uniformly from the
    v0 defect set) and the rest clean. A smoke-test manifest for exercising the baselines harness
    end-to-end -- NOT the real seed corpus (see module docstring and datasets/sources.md)."""
    if not 0.0 <= defect_rate <= 1.0:
        raise ValueError("defect_rate must be in [0, 1]")
    rng = np.random.default_rng(seed)
    records = []
    for i in range(n):
        level = levels[i % len(levels)]
        record_id = f"synth-{i:05d}"
        defect_type = _DEFECT_TYPES[rng.integers(len(_DEFECT_TYPES))] if rng.random() < defect_rate else None
        indications = generate_indications(record_id, defect_type, rng)
        records.append(_record(record_id, level, indications))
    return records
