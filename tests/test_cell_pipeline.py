"""Tests for the cell software skeleton: intake -> sensing -> fusion -> record.

These exercise the rule-based v0 scorer's *qualitative* behavior (never-permitted types, the
level-D-only lack-of-fusion allowance) and confirm the assembled record is actually valid against
evals/schema/record.schema.json -- the schema is the contract linking product output to the eval.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from cell.intake.models import AcceptanceSpec, Job, PartSpec
from cell.pipeline import run_inspection

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "evals" / "schema" / "record.schema.json"


def _make_job(level: str) -> Job:
    return Job(
        part=PartSpec(family="weld", material="carbon-steel", thickness_mm=10.0),
        acceptance=AcceptanceSpec(level=level),
    )


@pytest.mark.parametrize("level", ["B", "C", "D"])
def test_clean_part_passes(level: str) -> None:
    result = run_inspection(_make_job(level), scenario="clean", seed=0)
    assert result.decision.outcome == "pass"


@pytest.mark.parametrize("level", ["B", "C", "D"])
def test_crack_always_rejects(level: str) -> None:
    result = run_inspection(_make_job(level), scenario="crack", seed=0)
    assert result.decision.outcome == "reject"


def test_lack_of_fusion_is_class_dependent() -> None:
    for level in ("B", "C"):
        result = run_inspection(_make_job(level), scenario="lack_of_fusion", seed=1)
        assert result.decision.outcome == "reject", f"expected reject at level {level}"

    result_d = run_inspection(_make_job("D"), scenario="lack_of_fusion", seed=1)
    assert result_d.decision.outcome == "pass"


def test_record_matches_eval_schema() -> None:
    result = run_inspection(_make_job("C"), scenario="porosity", seed=2)
    schema = json.loads(_SCHEMA_PATH.read_text())
    jsonschema.validate(result.record, schema)


def test_pipeline_is_deterministic_given_seed() -> None:
    job = _make_job("B")
    result_a = run_inspection(job, scenario="slag_inclusion", seed=42)
    result_b = run_inspection(job, scenario="slag_inclusion", seed=42)
    assert result_a.indications == result_b.indications
    assert result_a.decision == result_b.decision
