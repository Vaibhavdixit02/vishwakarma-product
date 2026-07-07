"""Tests for the abonyilab scan3d ingest adapter (evals/datasets/ingest/abonyilab_scan3d.py):
the minimal PLY parser (ascii + binary little-endian), record building against the schema, the
directory/zip walker, and the committed manifest itself."""

from __future__ import annotations

import json
import struct
import zipfile
from pathlib import Path

import pytest

from evals.datasets.ingest.abonyilab_scan3d import (
    KNOWN_REAL_SCANS,
    Scan3dIngestError,
    build_record,
    ingest,
    read_ply,
)
from evals.schema.validate import validate_record

MANIFEST = Path("evals/datasets/manifests/abonyilab_scan3d.jsonl")


def ascii_ply() -> bytes:
    return (
        b"ply\nformat ascii 1.0\ncomment test fixture\n"
        b"element vertex 3\nproperty float x\nproperty float y\nproperty float z\n"
        b"element face 1\nproperty list uchar int vertex_index\nend_header\n"
        b"0.0 0.0 0.0\n1.0 2.0 3.0\n-1.0 -2.0 -3.0\n"
        b"3 0 1 2\n"
    )


def binary_ply() -> bytes:
    # x, y, z plus normals — the parser must pick xyz out of a wider property list
    header = (
        b"ply\nformat binary_little_endian 1.0\n"
        b"element vertex 2\n"
        b"property float x\nproperty float y\nproperty float z\n"
        b"property float nx\nproperty float ny\nproperty float nz\n"
        b"end_header\n"
    )
    verts = struct.pack("<6f", 0.5, 1.5, 2.5, 0, 0, 1) + struct.pack("<6f", -0.5, 4.5, 0.0, 0, 1, 0)
    return header + verts


def test_read_ascii_ply_counts_bbox_checksum() -> None:
    mesh = read_ply(ascii_ply(), "fixture")
    assert (mesh.format, mesh.n_vertices, mesh.n_faces) == ("ply-ascii", 3, 1)
    assert mesh.bbox == (-1.0, -2.0, -3.0, 1.0, 2.0, 3.0)
    assert mesh.checksum_sha256 == read_ply(ascii_ply(), "again").checksum_sha256


def test_read_binary_le_ply_extracts_xyz_among_normals() -> None:
    mesh = read_ply(binary_ply(), "fixture")
    assert (mesh.format, mesh.n_vertices, mesh.n_faces) == ("ply-binary-le", 2, 0)
    assert mesh.bbox == (-0.5, 1.5, 0.0, 0.5, 4.5, 2.5)


@pytest.mark.parametrize(
    "data, message",
    [
        (b"not a ply", "magic"),
        (b"ply\nformat ascii 1.0\nelement vertex 1\n", "end_header"),
        (ascii_ply().replace(b"ascii 1.0", b"binary_big_endian 1.0"), "unsupported PLY format"),
        (ascii_ply().replace(b"property float y\n", b""), "x/y/z"),
        (ascii_ply()[:-24], "ends after"),  # truncated vertex block
    ],
)
def test_read_ply_fails_loudly_on_malformed_input(data: bytes, message: str) -> None:
    with pytest.raises(Scan3dIngestError, match=message):
        read_ply(data, "fixture")


def test_build_record_is_schema_valid_with_source_declared_truth() -> None:
    mesh = read_ply(ascii_ply(), "fixture")
    record = build_record("defect2_Hibas_2.ply", mesh, "some/ref.ply", "C")
    validate_record(record)
    assert record["ground_truth"]["decision"] == "reject"
    assert record["annotations"] == []  # no per-indication labels exist in the source
    assert record["provenance"]["assumed_acceptance_class"] is True
    assert "not taxonomy-derived" in record["ground_truth"]["derived_by"]

    ideal = build_record("ideal_etalon_1.ply", mesh, "some/ref.ply", "B")
    assert ideal["ground_truth"]["decision"] == "pass"
    assert ideal["acceptance"]["class"] == "B"


def test_build_record_rejects_unknown_files() -> None:
    mesh = read_ply(ascii_ply(), "fixture")
    with pytest.raises(Scan3dIngestError, match="inventory"):
        build_record("mystery_scan.ply", mesh, "ref", "C")


def test_ingest_walks_zips_skips_cad_and_macosx_and_dedupes(tmp_path) -> None:
    with zipfile.ZipFile(tmp_path / "real-mesh 2.zip", "w") as zf:
        zf.writestr("real-mesh/defect2_Hibas_2.ply", ascii_ply())
        zf.writestr("__MACOSX/real-mesh/._defect2_Hibas_2.ply", b"resource fork junk")
        zf.writestr("cad-mesh/crack_repedes_a5du.ply", binary_ply())
    # the same scan also extracted loose — must not produce a duplicate record
    loose = tmp_path / "real-mesh" / "defect2_Hibas_2.ply"
    loose.parent.mkdir()
    loose.write_bytes(ascii_ply())

    records = ingest(tmp_path, "C")
    assert [r["record_id"] for r in records] == ["abonyilab-3dscan-defect-2"]
    validate_record(records[0])


def test_ingest_empty_dir_fails_loudly(tmp_path) -> None:
    with pytest.raises(Scan3dIngestError, match="no real-scan"):
        ingest(tmp_path, "C")


def test_committed_manifest_is_schema_valid_and_complete() -> None:
    """The manifest in git is the shareable artifact (checksums, no raw meshes) — it must stay
    schema-valid and cover the full known inventory."""
    lines = MANIFEST.read_text().splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    assert len(records) == len(KNOWN_REAL_SCANS)
    ids = set()
    for r in records:
        validate_record(r)
        assert r["provenance"]["synthetic"] is False
        assert r["modalities"]["scan3d"]["checksum_sha256"]
        ids.add(r["record_id"])
    assert ids == {v["record_id"] for v in KNOWN_REAL_SCANS.values()}
