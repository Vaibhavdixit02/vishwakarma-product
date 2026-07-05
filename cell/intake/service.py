"""Job intake. In-memory by default; optionally durable via an append-only JSONL file, standing
in for a real intake API/DB until there's a design partner (cell/README.md's "persist beyond
in-memory" TODO)."""

from __future__ import annotations

from pathlib import Path

from .models import AcceptanceSpec, DefectConcern, Job, PartSpec


class JobIntake:
    def __init__(self, persist_path: str | Path | None = None) -> None:
        self._jobs: dict[str, Job] = {}
        self._persist_path = Path(persist_path) if persist_path else None
        if self._persist_path and self._persist_path.exists():
            self._load()

    def _load(self) -> None:
        assert self._persist_path is not None
        for line in self._persist_path.read_text().splitlines():
            line = line.strip()
            if line:
                job = Job.model_validate_json(line)
                self._jobs[job.job_id] = job

    def _append(self, job: Job) -> None:
        if self._persist_path is None:
            return
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        with self._persist_path.open("a") as f:
            f.write(job.model_dump_json() + "\n")

    def submit(
        self,
        part: PartSpec,
        acceptance: AcceptanceSpec,
        defect_concern: DefectConcern | None = None,
    ) -> Job:
        job = Job(part=part, acceptance=acceptance, defect_concern=defect_concern or DefectConcern())
        self._jobs[job.job_id] = job
        self._append(job)
        return job

    def get(self, job_id: str) -> Job:
        return self._jobs[job_id]

    def all(self) -> list[Job]:
        return list(self._jobs.values())

    def __len__(self) -> int:
        return len(self._jobs)
