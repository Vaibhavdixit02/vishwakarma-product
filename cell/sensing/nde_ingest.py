"""Mode-B ingest: read a real Evident/Olympus `.nde` export instead of fabricating a reading.

Per decision 0010 (strategy repo), the durable asset is the fusion/decision software, not a
physical cell -- so for accounts that already run NDT instruments (the trigger case: an Evident
OmniScan X3/X4 at BSP's PAUT weld-joint facility), the sensing head doesn't need to be built or
owned at all. Evident publishes `.nde` as an open format (HDF5 + JSON metadata) specifically so
third-party software can read it without their cooperation -- see
https://ndeformat.com (NDE Open File Format, MIT-licensed spec, github.com/Evident-Industrial/
NDE_Open_File_Format).

**Honesty note (read before trusting this against a real file):** this parser targets the
*publicly documented* v4.3 top-level structure (an HDF5 file with `Public`/`Private` groups and
JSON-encoded `Properties`/`Setup` datasets) as described on ndeformat.com. It has been exercised
only against a synthetic `.nde`-shaped fixture built to that same documented structure
(`tests/test_nde_ingest.py`) -- **not against a real vendor-exported file**, since none was
available this session. Treat this as a scaffold proven against the spec, pending validation
against a real OmniScan export (the natural next step once a design partner or the BSP contact
can share one). If a real file's structure diverges from what's documented, `read_nde_paut` fails
loudly (raises `NdeFormatError`) rather than silently guessing.

**What this does NOT do.** It extracts the modality block (scan metadata, probe info, array
shape/checksum) -- proving *data access* is real. It does not extract indications (defect
locations/sizes): that requires an interpretation model, which is a separate, not-yet-built piece
of the roadmap (decision 0010's Phase 1). A record built from this adapter has a populated
`modalities.paut` block and an empty `annotations` list until that model exists.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class NdeFormatError(ValueError):
    """Raised when a `.nde` file doesn't match the documented top-level structure."""


def read_nde_paut(path: str | Path) -> dict[str, Any]:
    """Parse a `.nde` file's PAUT modality metadata into a schema-valid `modalities.paut` block
    (see `evals/schema/record.schema.json`).

    Requires the optional `hardware-ingest` dependency group (`h5py`) -- not a core eval/cell
    dependency, since most of this repo runs with no hardware at all.
    """
    try:
        import h5py
    except ImportError as e:
        raise ImportError(
            "reading .nde files requires h5py -- install with `pip install -e '.[hardware-ingest]'`"
        ) from e

    path = Path(path)
    with h5py.File(path, "r") as f:
        if "Public" not in f:
            raise NdeFormatError(
                f"{path}: missing top-level 'Public' group -- not an NDE Open File Format v4.x file "
                "(see https://ndeformat.com for the documented structure)"
            )
        public = f["Public"]

        setup = _read_json_dataset(public, "Setup", path)
        properties = _read_json_dataset(public, "Properties", path)

        scan_type, array_shape, checksum = _read_ascan(public, path)
        probe = _extract_probe_metadata(setup)

    block: dict[str, Any] = {
        "scan_type": scan_type,
        "data_ref": str(path),
        "checksum_sha256": checksum,
        "shape": list(array_shape),
    }
    if probe:
        block["probe"] = probe
    if properties.get("instrument"):
        block["instrument"] = properties["instrument"]
    return block


def _read_json_dataset(group: Any, name: str, path: Path) -> dict[str, Any]:
    if name not in group:
        raise NdeFormatError(f"{path}: missing 'Public/{name}' JSON metadata dataset")
    raw = group[name][()]
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise NdeFormatError(f"{path}: 'Public/{name}' is not valid JSON") from e


def _read_ascan(public_group: Any, path: Path) -> tuple[str, tuple[int, ...], str]:
    """Find the acquisition data array under Public/DataGroups/... and hash it.

    The documented format nests the actual amplitude array under a data-group hierarchy whose
    exact naming varies by acquisition (A-scan vs S-scan vs FMC/TFM); this reads the first array
    dataset found under 'DataGroups' rather than assuming one fixed path, and reports its ndim to
    pick the closest `scan_type` enum value in our schema.
    """
    if "DataGroups" not in public_group:
        raise NdeFormatError(f"{path}: missing 'Public/DataGroups' -- no acquisition data found")

    dataset = _find_first_dataset(public_group["DataGroups"])
    if dataset is None:
        raise NdeFormatError(f"{path}: 'Public/DataGroups' contains no array datasets")

    data = dataset[()]
    checksum = hashlib.sha256(data.tobytes()).hexdigest()
    shape = data.shape

    scan_type = {1: "A-scan", 2: "B-scan", 3: "S-scan"}.get(len(shape), "volume")
    return scan_type, shape, checksum


def _find_first_dataset(group: Any) -> Any | None:
    import h5py

    for _, item in group.items():
        if isinstance(item, h5py.Dataset):
            return item
        if isinstance(item, h5py.Group):
            found = _find_first_dataset(item)
            if found is not None:
                return found
    return None


def _extract_probe_metadata(setup: dict[str, Any]) -> dict[str, Any]:
    """Best-effort probe geometry extraction from Setup's documented 'Probes' data-model section.
    Returns {} rather than raising if the section is absent or shaped unexpectedly -- probe
    metadata is informative, not required for the modality block to be schema-valid."""
    probes = setup.get("Probes")
    if not probes:
        return {}
    first = probes[0] if isinstance(probes, list) else next(iter(probes.values()), {})
    if not isinstance(first, dict):
        return {}
    return {
        k: first[k]
        for k in ("frequency", "elementCount", "pitch", "numberOfElements")
        if k in first
    }
