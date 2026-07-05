"""Shared loader/validator for record.schema.json.

Both the product's record builder (cell/records/build.py) and the eval's synthetic manifest
generator (evals/datasets/synthetic.py) assemble records against this same schema; this module is
the one place that schema gets loaded from disk, so there's a single source of truth for its path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

_SCHEMA_PATH = Path(__file__).resolve().parent / "record.schema.json"
_SCHEMA: dict[str, Any] | None = None


def schema() -> dict[str, Any]:
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = json.loads(_SCHEMA_PATH.read_text())
    return _SCHEMA


def validate_record(record: dict[str, Any]) -> None:
    jsonschema.validate(record, schema())
