"""Tests for JobIntake's optional JSONL persistence (cell/intake/service.py) -- closes the
cell/README.md TODO "persist JobIntake beyond in-memory" with the smallest durable thing that
works: an append-only file, reloaded on the next process's startup.
"""

from __future__ import annotations

from pathlib import Path

from cell.intake.models import AcceptanceSpec, PartSpec
from cell.intake.service import JobIntake


def _submit_one(intake: JobIntake, level: str = "B") -> str:
    job = intake.submit(
        part=PartSpec(family="weld", material="carbon-steel"),
        acceptance=AcceptanceSpec(level=level),
    )
    return job.job_id


def test_default_intake_is_in_memory_only_and_not_written_anywhere(tmp_path: Path) -> None:
    intake = JobIntake()
    _submit_one(intake)
    assert len(intake) == 1
    assert list(tmp_path.iterdir()) == []  # nothing written when no persist_path is given


def test_persisted_jobs_survive_a_new_intake_instance(tmp_path: Path) -> None:
    path = tmp_path / "jobs.jsonl"
    first = JobIntake(persist_path=path)
    job_id = _submit_one(first, level="D")

    second = JobIntake(persist_path=path)  # simulates a fresh process picking the file back up
    assert len(second) == 1
    assert second.get(job_id).acceptance.level == "D"


def test_persistence_appends_across_multiple_submissions(tmp_path: Path) -> None:
    path = tmp_path / "jobs.jsonl"
    intake = JobIntake(persist_path=path)
    _submit_one(intake, level="B")
    _submit_one(intake, level="C")

    reloaded = JobIntake(persist_path=path)
    assert len(reloaded) == 2
    assert {job.acceptance.level for job in reloaded.all()} == {"B", "C"}
