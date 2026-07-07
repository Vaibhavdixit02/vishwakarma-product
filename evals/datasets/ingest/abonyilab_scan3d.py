"""Ingest adapter: abonyilab/3D-scanner-data -> schema-valid records (scan3d modality).

The first REAL public data through the schema — every prior end-to-end run used the synthetic
smoke-test manifest. Source: https://github.com/abonyilab/3D-scanner-data, the dataset behind
Hegedűs-Kuti et al., "3D Scanner-Based Identification of Welding Defects — Clustering the Results
of Point Cloud Alignment," Sensors 23(5):2503 (2023). Its Data Availability Statement declares the
dataset publicly available at that repo; the repo itself carries NO license file, so: internal
research/dev use only, never redistribute the raw meshes until the authors add a license
(datasets/outreach.md #3 has the drafted ask).

What the dataset actually is — and therefore what this adapter honestly claims:

  - 4 real structured-light scans of T-welded specimens (1 ideal "etalon" + 3 defective), ~400k
    vertices each, ASCII PLY, plus 7 small binary-PLY CAD models of ISO 5817:2014 defect
    geometries. The CAD models are reference geometry, not parts — they are NOT emitted as
    records.
  - Labels are per-FILE (ideal vs. defective, from the authors' filenames), not per-indication,
    and the fabricated defect types (excessive convexity, throat thickness, end crater pipe,
    undercut) are surface/geometric classes outside the v0 annotation enum anyway. So records
    carry a populated `modalities.scan3d` block and an EMPTY `annotations` list, and
    `ground_truth.decision` comes from the source's own labeling — `derived_by` says so
    explicitly; it is NOT derived via taxonomy/acceptance.py.
  - The source states no ISO 5817 quality level for the specimens, so the acceptance class is an
    ASSUMED default (flagged `assumed_acceptance_class: true` in provenance, settable via
    --acceptance-class).

With N=4 this is a schema/pipeline fixture — the proof that the "multimodal by construction"
claim survives contact with real public data of a second modality — not a training corpus.

Usage (from the repo root; zips downloaded from the GitHub repo into the git-ignored raw dir):

  python -m evals.datasets.ingest.abonyilab_scan3d \\
      --data-dir evals/datasets/raw/abonyilab-3d-scanner \\
      --out evals/datasets/manifests/abonyilab_scan3d.jsonl

Reads .ply files directly or inside the distribution .zip files (zip member checksums equal
extracted-file checksums, so either layout produces the identical manifest).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from evals.schema.validate import validate_record

SOURCE_URL = "https://github.com/abonyilab/3D-scanner-data"
DERIVED_BY = "abonyilab-source-labels@v1 (source-declared ideal/defective, not taxonomy-derived)"

# The complete real-scan inventory, keyed by basename. Explicit rather than pattern-matched:
# with four files, an unknown name is more likely a mistake than a new sample, so we fail loudly.
KNOWN_REAL_SCANS: dict[str, dict[str, Any]] = {
    "ideal_etalon_1.ply": {"record_id": "abonyilab-3dscan-ideal-1", "decision": "pass"},
    "defect2_Hibas_2.ply": {"record_id": "abonyilab-3dscan-defect-2", "decision": "reject"},
    "defect3_Hibas_3.ply": {"record_id": "abonyilab-3dscan-defect-3", "decision": "reject"},
    "defect4_Hibas_4.ply": {"record_id": "abonyilab-3dscan-defect-4", "decision": "reject"},
}

_PLY_DTYPES = {
    "char": "i1", "int8": "i1", "uchar": "u1", "uint8": "u1",
    "short": "<i2", "int16": "<i2", "ushort": "<u2", "uint16": "<u2",
    "int": "<i4", "int32": "<i4", "uint": "<u4", "uint32": "<u4",
    "float": "<f4", "float32": "<f4", "double": "<f8", "float64": "<f8",
}


class Scan3dIngestError(ValueError):
    """Raised when a file isn't a parseable PLY or isn't part of the known dataset inventory."""


@dataclass(frozen=True)
class PlyMesh:
    """The subset of a PLY mesh this adapter needs: enough to fill a scan3d modality block."""

    format: str  # "ply-ascii" | "ply-binary-le"
    n_vertices: int
    n_faces: int
    bbox: tuple[float, float, float, float, float, float]
    checksum_sha256: str


def read_ply(data: bytes, name: str = "<bytes>") -> PlyMesh:
    """Parse a PLY (ascii or binary little-endian) far enough to extract vertex/face counts and
    the vertex bounding box. Faces are counted from the header, never parsed — the modality block
    doesn't need connectivity, and the real meshes' variable-length face lists make skipping them
    the honest cheap option."""
    header, body_offset = _split_header(data, name)
    fmt, elements = _parse_header(header, name)

    if "vertex" not in elements:
        raise Scan3dIngestError(f"{name}: PLY header declares no vertex element")
    n_vertices, vertex_props = elements["vertex"]
    n_faces = elements.get("face", (0, []))[0]

    xyz = (
        _ascii_vertices(data, body_offset, n_vertices, vertex_props, name)
        if fmt == "ply-ascii"
        else _binary_vertices(data, body_offset, n_vertices, vertex_props, name)
    )
    lo, hi = xyz.min(axis=0), xyz.max(axis=0)
    return PlyMesh(
        format=fmt,
        n_vertices=n_vertices,
        n_faces=n_faces,
        bbox=(float(lo[0]), float(lo[1]), float(lo[2]), float(hi[0]), float(hi[1]), float(hi[2])),
        checksum_sha256=hashlib.sha256(data).hexdigest(),
    )


def _split_header(data: bytes, name: str) -> tuple[str, int]:
    if not data.startswith(b"ply"):
        raise Scan3dIngestError(f"{name}: not a PLY file (missing 'ply' magic)")
    end = data.find(b"end_header")
    if end == -1:
        raise Scan3dIngestError(f"{name}: PLY header has no end_header")
    body_offset = data.index(b"\n", end) + 1
    return data[:end].decode("ascii", errors="replace"), body_offset


def _parse_header(header: str, name: str) -> tuple[str, dict[str, tuple[int, list[tuple[str, str]]]]]:
    """Return (format, {element_name: (count, [(prop_type, prop_name), ...])}). List properties
    are recorded with prop_type 'list' — they only ever appear on the face element here."""
    fmt = None
    elements: dict[str, tuple[int, list[tuple[str, str]]]] = {}
    current: str | None = None
    for line in header.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "format":
            if parts[1] == "ascii":
                fmt = "ply-ascii"
            elif parts[1] == "binary_little_endian":
                fmt = "ply-binary-le"
            else:
                raise Scan3dIngestError(f"{name}: unsupported PLY format {parts[1]!r}")
        elif parts[0] == "element":
            current = parts[1]
            elements[current] = (int(parts[2]), [])
        elif parts[0] == "property" and current is not None:
            props = elements[current][1]
            props.append(("list", parts[-1]) if parts[1] == "list" else (parts[1], parts[2]))
    if fmt is None:
        raise Scan3dIngestError(f"{name}: PLY header has no format line")
    return fmt, elements


def _xyz_indices(props: list[tuple[str, str]], name: str) -> tuple[int, int, int]:
    by_name = {p_name: i for i, (_, p_name) in enumerate(props)}
    try:
        return by_name["x"], by_name["y"], by_name["z"]
    except KeyError as e:
        raise Scan3dIngestError(f"{name}: vertex element lacks x/y/z properties") from e


def _ascii_vertices(
    data: bytes, offset: int, n: int, props: list[tuple[str, str]], name: str
) -> np.ndarray:
    ix, iy, iz = _xyz_indices(props, name)
    take = max(ix, iy, iz) + 1
    rows = np.empty((n, 3), dtype=float)
    stream = io.BytesIO(data[offset:])
    for i in range(n):
        line = stream.readline()
        if not line:
            raise Scan3dIngestError(f"{name}: file ends after {i} of {n} declared vertices")
        vals = line.split()[:take]
        rows[i] = float(vals[ix]), float(vals[iy]), float(vals[iz])
    return rows


def _binary_vertices(
    data: bytes, offset: int, n: int, props: list[tuple[str, str]], name: str
) -> np.ndarray:
    if any(t == "list" for t, _ in props):
        raise Scan3dIngestError(f"{name}: list property on the vertex element is unsupported")
    try:
        dtype = np.dtype([(p_name, _PLY_DTYPES[t]) for t, p_name in props])
    except KeyError as e:
        raise Scan3dIngestError(f"{name}: unsupported PLY property type {e.args[0]!r}") from e
    end = offset + n * dtype.itemsize
    if len(data) < end:
        raise Scan3dIngestError(f"{name}: file too short for {n} declared binary vertices")
    verts = np.frombuffer(data[offset:end], dtype=dtype)
    return np.column_stack([verts["x"], verts["y"], verts["z"]]).astype(float)


# ---------------------------------------------------------------------------- record building


def build_record(
    basename: str, mesh: PlyMesh, data_ref: str, acceptance_class: str
) -> dict[str, Any]:
    """One real scan -> one schema-valid record. See module docstring for why annotations are
    empty and ground truth is source-declared."""
    if basename not in KNOWN_REAL_SCANS:
        raise Scan3dIngestError(
            f"{basename}: not in the known abonyilab real-scan inventory "
            f"({sorted(KNOWN_REAL_SCANS)}) — if the upstream repo gained files, extend the map."
        )
    info = KNOWN_REAL_SCANS[basename]
    record: dict[str, Any] = {
        "record_id": info["record_id"],
        "part": {
            "family": "weld",
            "material": "steel (grade unstated in source)",
            "joint_type": "T-joint fillet, a5 (per Sensors 23(5):2503)",
        },
        "acceptance": {"standard": "ISO 5817", "class": acceptance_class},
        "modalities": {
            "scan3d": {
                "data_ref": data_ref,
                "checksum_sha256": mesh.checksum_sha256,
                "format": mesh.format,
                "n_vertices": mesh.n_vertices,
                "n_faces": mesh.n_faces,
                "bbox": [round(v, 3) for v in mesh.bbox],
                "scanner": "HP 3D Structured Light Scanner Pro (DAVID) — per source paper/README",
            }
        },
        "annotations": [],
        "ground_truth": {
            "decision": info["decision"],
            "governing_defect": None,
            "derived_by": DERIVED_BY,
        },
        "provenance": {
            "source": f"abonyilab/3D-scanner-data ({SOURCE_URL})",
            "license": (
                "none declared — public per Sensors 23(5):2503 Data Availability Statement; "
                "internal research use only, no redistribution of raw meshes (outreach.md #3)"
            ),
            "synthetic": False,
            "label_source": "source filenames (ideal/defective), Sensors 23(5):2503 authors",
            "assumed_acceptance_class": True,
        },
    }
    validate_record(record)
    return record


def _iter_ply_files(data_dir: Path):
    """Yield (basename, data_ref, bytes) for every real-scan .ply under data_dir — loose files
    and members of the distribution zips alike. CAD reference models (cad-mesh*) and macOS
    resource-fork noise are skipped by construction, not by special-casing errors later."""
    def wanted(p: str) -> bool:
        base = Path(p).name
        return (
            p.lower().endswith(".ply")
            and "cad-mesh" not in p
            and "__MACOSX" not in p
            and not base.startswith("._")
        )

    for path in sorted(data_dir.rglob("*")):
        rel = path.relative_to(data_dir)
        if path.is_file() and wanted(str(rel)):
            yield path.name, str(rel), path.read_bytes()
        elif path.is_file() and path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as zf:
                for member in sorted(zf.namelist()):
                    if wanted(member):
                        yield Path(member).name, f"{rel}!{member}", zf.read(member)


def ingest(data_dir: Path, acceptance_class: str) -> list[dict[str, Any]]:
    records = []
    seen: set[str] = set()
    for basename, data_ref, data in _iter_ply_files(data_dir):
        if basename in seen:  # same scan present both loose and inside its zip
            continue
        mesh = read_ply(data, basename)
        records.append(build_record(basename, mesh, data_ref, acceptance_class))
        seen.add(basename)
    if not records:
        raise Scan3dIngestError(
            f"{data_dir}: no real-scan .ply files found (expected the GitHub repo's zips or "
            "their extracted contents)"
        )
    return records


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data-dir", type=Path, required=True, help="dir with the repo's zips or extracted .ply files")
    p.add_argument("--out", type=Path, help="manifest JSONL to write (one schema-valid record per line)")
    p.add_argument(
        "--acceptance-class",
        choices=("B", "C", "D"),
        default="C",
        help="ASSUMED class for all records (source states none); flagged in provenance",
    )
    args = p.parse_args(argv)

    records = ingest(args.data_dir, args.acceptance_class)
    for r in records:
        s = r["modalities"]["scan3d"]
        print(
            f"{r['record_id']:<28} {r['ground_truth']['decision']:<7} "
            f"{s['format']:<14} verts={s['n_vertices']:<7} faces={s['n_faces']:<7} "
            f"sha256={s['checksum_sha256'][:12]}…"
        )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"Wrote {len(records)} records to {args.out}")


if __name__ == "__main__":
    main()
