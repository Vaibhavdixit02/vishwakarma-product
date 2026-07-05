"""Interactive access point: `python -m cell.cli`

Lets a person play the RFQ-intake role directly -- answer a few prompts (or pass flags) and see
the cell's decision come back -- instead of only reading demo.py's fixed, scripted output.

Since there's no real sensing head yet, the "scenario" prompt stands in for what a scan would find
(cell/sensing/synthetic.py) -- pick it like you're telling the tool what's actually on the part.

Non-interactive / scriptable form, e.g. for a quick one-liner or a shell script:
  python -m cell.cli --family weld --material carbon-steel --thickness 12 \\
      --joint-type butt --level B --scenario porosity --seed 7

Pass `--history PATH` to persist submitted jobs across runs (append-only JSONL); pass
`--list-history PATH` on its own to review what's in one without submitting anything new.
"""

from __future__ import annotations

import argparse
import json
import sys

from cell.intake.models import AcceptanceSpec, PartSpec
from cell.intake.service import JobIntake
from cell.pipeline import run_inspection
from evals.scoring.economic_metric import CostModel

_FAMILIES = ["weld", "casting", "forged", "other"]
_LEVELS = ["B", "C", "D"]
_SCENARIOS = ["clean", "porosity", "slag_inclusion", "lack_of_fusion", "crack"]

_GREEN = "\033[32m"
_RED = "\033[31m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def _colorize(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{code}{text}{_RESET}"


def _prompt_choice(label: str, choices: list[str], default: str) -> str:
    lower_to_choice = {c.lower(): c for c in choices}
    while True:
        raw = input(f"{label} [{'/'.join(choices)}] (default {default}): ").strip().lower()
        if not raw:
            return default
        if raw in lower_to_choice:
            return lower_to_choice[raw]
        print(f"  not one of {choices}, try again")


def _prompt_text(label: str, default: str | None) -> str | None:
    suffix = f" (default {default})" if default is not None else " (optional)"
    raw = input(f"{label}{suffix}: ").strip()
    return raw or default


def _prompt_float(label: str, default: float | None) -> float | None:
    suffix = f" (default {default})" if default is not None else " (optional)"
    raw = input(f"{label}{suffix}: ").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print("  not a number, skipping")
        return default


def _require(flag: str) -> str:
    print(f"error: {flag} is required in --non-interactive mode", file=sys.stderr)
    raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Submit a part to the cell and see its decision.")
    p.add_argument("--family", choices=_FAMILIES)
    p.add_argument("--material")
    p.add_argument("--thickness", type=float)
    p.add_argument("--joint-type")
    p.add_argument("--level", choices=_LEVELS, help="ISO 5817 acceptance class")
    p.add_argument(
        "--scenario",
        choices=_SCENARIOS,
        help="what the (synthetic) sensing head reports -- stands in for a real scan",
    )
    p.add_argument("--seed", type=int, default=None, help="fix for a reproducible synthetic reading")
    p.add_argument("--c-fa", type=float, default=CostModel().c_fa, help="dollar cost of an escape (missed reject)")
    p.add_argument("--c-fr", type=float, default=CostModel().c_fr, help="dollar cost of a scrap (false reject)")
    p.add_argument(
        "--non-interactive",
        action="store_true",
        help="fail on any missing value instead of prompting",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="print one machine-readable JSON object (decision + indications + record) instead of prose",
    )
    p.add_argument(
        "--history",
        metavar="PATH",
        help="append-only JSONL file to persist this job into (and load prior jobs from)",
    )
    p.add_argument(
        "--list-history",
        metavar="PATH",
        help="print jobs previously persisted to PATH and exit -- doesn't submit a new job",
    )
    return p


def _print_history(path: str) -> None:
    intake = JobIntake(persist_path=path)
    jobs = intake.all()
    if not jobs:
        print(f"No jobs recorded in {path} yet.")
        return
    print(f"{len(jobs)} job(s) in {path}:\n")
    for job in jobs:
        print(
            f"  {job.job_id}  {job.created_at:%Y-%m-%d %H:%M:%S}Z  "
            f"{job.part.family}/{job.part.material}  class {job.acceptance.level}"
        )


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.list_history:
        _print_history(args.list_history)
        return

    interactive = not args.non_interactive

    if not args.json:
        print("=== Cell intake -- synthetic sensing, no hardware, uncalibrated thresholds (v0) ===\n")

    family = args.family or (
        _prompt_choice("Part family", _FAMILIES, "weld") if interactive else _require("--family")
    )
    material = args.material or (
        _prompt_text("Material", "carbon-steel") if interactive else _require("--material")
    )
    thickness = (
        args.thickness
        if args.thickness is not None
        else (_prompt_float("Thickness (mm)", 12.0) if interactive else None)
    )
    joint_type = args.joint_type or (_prompt_text("Joint type", "butt") if interactive else None)
    level = args.level or (
        _prompt_choice("Acceptance class (ISO 5817)", _LEVELS, "C") if interactive else _require("--level")
    )
    scenario = args.scenario or (
        _prompt_choice("Scenario the (synthetic) sensing head reports", _SCENARIOS, "clean")
        if interactive
        else "clean"
    )

    job = JobIntake(persist_path=args.history).submit(
        part=PartSpec(family=family, material=material, thickness_mm=thickness, joint_type=joint_type),
        acceptance=AcceptanceSpec(level=level),
    )
    cost_model = CostModel(c_fa=args.c_fa, c_fr=args.c_fr)
    result = run_inspection(job, scenario=scenario, seed=args.seed, cost_model=cost_model)

    if args.json:
        print(
            json.dumps(
                {
                    "job_id": job.job_id,
                    "decision": {
                        "outcome": result.decision.outcome,
                        "reject_score": result.decision.reject_score,
                        "threshold": result.decision.threshold,
                        "rationale": result.decision.rationale,
                    },
                    "indications": [
                        {
                            "id": ind.id,
                            "defect_type": ind.defect_type,
                            "iso6520_ref": ind.iso6520_ref,
                            "size_mm": ind.size_mm,
                            "amplitude_db": ind.amplitude_db,
                        }
                        for ind in result.indications
                    ],
                    "record": result.record,
                },
                indent=2,
                default=str,
            )
        )
        return

    outcome_color = _GREEN if result.decision.outcome == "pass" else _RED
    print(f"\nJob {job.job_id} -- {family}/{material}, class {level}")
    print(f"Decision: {_colorize(result.decision.outcome.upper(), outcome_color + _BOLD)}")
    print(result.decision.rationale)
    if result.indications:
        print("\nIndications:")
        for ind in result.indications:
            print(
                f"  - {ind.defect_type} (ISO 6520-1 {ind.iso6520_ref}) "
                f"size={ind.size_mm}mm amplitude={ind.amplitude_db}dB"
            )

    print("\nRecord (evals/schema/record.schema.json-valid):")
    print(json.dumps(result.record, indent=2, default=str))


if __name__ == "__main__":
    main()
