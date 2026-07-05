"""RFQ-style intake model — the entry point into the cell (docs/architecture.md).

One Job = one physical part that will move through sensing -> fusion/decision -> record.
Mirrors the relevant subset of evals/schema/record.schema.json's `part` and `acceptance`
blocks so a completed Job maps onto an eval record without translation surprises.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

PartFamily = Literal["weld", "casting", "forged", "other"]
AcceptanceLevel = Literal["B", "C", "D"]
DefectType = Literal["crack", "lack_of_fusion", "slag_inclusion", "porosity", "none"]


class PartSpec(BaseModel):
    family: PartFamily
    material: str
    thickness_mm: float | None = Field(default=None, ge=0)
    joint_type: str | None = None


class AcceptanceSpec(BaseModel):
    standard: str = "ISO 5817"
    level: AcceptanceLevel
    spec_override: str | None = None


class DefectConcern(BaseModel):
    """What the customer flags upfront. Informational only — sensing finds what's actually
    there independent of this; it doesn't gate or bias the reading."""

    expected_defect_types: list[DefectType] = Field(default_factory=list)
    notes: str | None = None


class Job(BaseModel):
    job_id: str = Field(default_factory=lambda: f"job-{uuid.uuid4().hex[:12]}")
    part: PartSpec
    acceptance: AcceptanceSpec
    defect_concern: DefectConcern = Field(default_factory=DefectConcern)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
