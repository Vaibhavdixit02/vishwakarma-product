"""Tests for the Mode-B `.nde` ingest adapter (cell/sensing/nde_ingest.py, decision 0010).

We don't have a real Evident OmniScan export, so this builds a minimal fixture matching the
*documented* NDE Open File Format v4.3 top-level structure (ndeformat.com) -- Public/DataGroups
holding an array dataset, Public/Setup and Public/Properties holding JSON metadata -- and checks
the adapter reads it correctly and produces a schema-valid `modalities.paut` block. This proves
the parser matches the public spec; it does NOT prove it matches a real vendor file byte-for-byte
(see the module docstring's honesty note).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import h5py
import numpy as np
import pytest

from cell.sensing.nde_ingest import NdeFormatError, read_nde_paut


def _write_fixture_nde(path: Path, shape: tuple[int, ...] = (256,)) -> np.ndarray:
    data = np.arange(np.prod(shape), dtype=np.float32).reshape(shape)
    with h5py.File(path, "w") as f:
        public = f.create_group("Public")
        public.create_dataset("Setup", data=json.dumps({
            "Probes": [{"frequency": 5.0, "numberOfElements": 64, "pitch": 0.6}],
        }))
        public.create_dataset("Properties", data=json.dumps({"instrument": "OmniScan X4 (fixture)"}))
        groups = public.create_group("DataGroups")
        groups.create_dataset("ascan-0", data=data)
    return data


def test_reads_fixture_and_matches_schema_shape(tmp_path: Path) -> None:
    nde_path = tmp_path / "sample.nde"
    data = _write_fixture_nde(nde_path)

    block = read_nde_paut(nde_path)

    assert block["scan_type"] == "A-scan"
    assert block["shape"] == list(data.shape)
    assert block["checksum_sha256"] == hashlib.sha256(data.tobytes()).hexdigest()
    assert block["probe"]["frequency"] == 5.0
    assert block["probe"]["numberOfElements"] == 64
    assert block["instrument"] == "OmniScan X4 (fixture)"


def test_scan_type_inferred_from_array_ndim(tmp_path: Path) -> None:
    nde_path = tmp_path / "volume.nde"
    _write_fixture_nde(nde_path, shape=(4, 8, 16, 16))

    block = read_nde_paut(nde_path)

    assert block["scan_type"] == "volume"


def test_missing_public_group_raises(tmp_path: Path) -> None:
    nde_path = tmp_path / "not-nde.nde"
    with h5py.File(nde_path, "w") as f:
        f.create_dataset("junk", data=[1, 2, 3])

    with pytest.raises(NdeFormatError, match="Public"):
        read_nde_paut(nde_path)


def test_missing_datagroups_raises(tmp_path: Path) -> None:
    nde_path = tmp_path / "no-data.nde"
    with h5py.File(nde_path, "w") as f:
        public = f.create_group("Public")
        public.create_dataset("Setup", data=json.dumps({}))
        public.create_dataset("Properties", data=json.dumps({}))

    with pytest.raises(NdeFormatError, match="DataGroups"):
        read_nde_paut(nde_path)


def test_block_is_schema_compatible(tmp_path: Path) -> None:
    """The produced block should slot into modalities.paut without touching the schema."""
    from evals.schema.validate import validate_record
    from evals.taxonomy.acceptance import ground_truth_decision

    nde_path = tmp_path / "sample.nde"
    _write_fixture_nde(nde_path)
    block = read_nde_paut(nde_path)

    gt_decision, gt_governing = ground_truth_decision([], "B")
    record = {
        "record_id": "nde-ingest-smoke-test",
        "part": {"family": "weld", "material": "carbon-steel"},
        "acceptance": {"standard": "ISO 5817", "class": "B"},
        "modalities": {"paut": block},
        "annotations": [],
        "ground_truth": {
            "decision": gt_decision,
            "governing_defect": gt_governing,
            "derived_by": "cell-nde-ingest-smoke-test@v0",
        },
        "provenance": {
            "source": "nde-ingest-fixture",
            "license": "n/a (internal fixture, not for eval corpus use)",
            "synthetic": True,
            "label_source": "none (no interpretation model yet -- decision 0010 Phase 1)",
        },
    }

    validate_record(record)  # raises on failure
