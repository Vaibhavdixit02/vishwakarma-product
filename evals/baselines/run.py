"""Baselines harness — the harness contract from baselines/README.md, made runnable today.

Real public-PAUT ingest is still blocked on license verification (datasets/sources.md), so this
defaults to a synthetic smoke-test manifest (evals/datasets/synthetic.py) instead of a real one.
Every baseline is reported the two ways the README's reporting rule calls for: its native metric
(accuracy) and its expected cost per part, per acceptance class — side by side, so the gap between
"accurate" and "economically good" is visible on the printed card itself.

Swap in a real manifest once ingest lands (`--manifest records.jsonl`, one schema-valid record per
line) — nothing downstream (scoring, reporting) changes.

Usage:
  python -m evals.baselines.run --synthetic 300 --seed 0
  python -m evals.baselines.run --manifest records.jsonl --baseline amplitude_threshold
  python -m evals.baselines.run --synthetic 300 --c-fa 5000 --c-fr 25 --out results/
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from evals.baselines.models import BASELINES, FIXED_THRESHOLD
from evals.datasets.synthetic import generate_manifest
from evals.scoring.economic_metric import CostModel, Report, evaluate_at_by_group, evaluate_by_group


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    if not records:
        raise ValueError(f"{path} contained no records")
    return records


def _truth_and_groups(records: list[dict[str, Any]]) -> tuple[list[int], list[str]]:
    truth = [1 if r["ground_truth"]["decision"] == "reject" else 0 for r in records]
    groups = [r["acceptance"]["class"] for r in records]
    return truth, groups


def run_baseline(
    name: str,
    records: list[dict[str, Any]],
    truth: list[int],
    groups: list[str],
    cost_model: CostModel,
) -> dict[str, Report]:
    """Run one registered baseline and return its per-acceptance-class Report."""
    baseline = BASELINES[name]
    scores = baseline.score_fn(records)
    if baseline.fixed_point:
        return evaluate_at_by_group(truth, scores, groups, FIXED_THRESHOLD, cost_model)
    return evaluate_by_group(truth, scores, groups, cost_model)


def _card(name: str, describe: str, reports: dict[str, Report]) -> str:
    lines = [f"=== {name} ===", f"  {describe}"]
    for cls in sorted(reports):
        o = reports[cls].optimal
        lines.append(
            f"  class {cls}: N={reports[cls].n:<4} native-accuracy={o.accuracy:.1%}   "
            f"expected-cost/part=${o.expected_cost_per_part:7.2f}   "
            f"escapes={o.n_escapes:<3} scraps={o.n_scraps:<3} tau={o.threshold:.2f}"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run baselines against a records manifest, scored by economic_metric."
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument(
        "--synthetic",
        type=int,
        metavar="N",
        help="generate N synthetic smoke-test records instead of loading a manifest (default: 300)",
    )
    src.add_argument("--manifest", type=Path, help="path to a JSONL manifest of schema-valid records")
    p.add_argument("--seed", type=int, default=0, help="seed for --synthetic generation")
    p.add_argument(
        "--defect-rate", type=float, default=0.5, help="fraction of --synthetic records carrying a defect"
    )
    p.add_argument(
        "--baseline",
        action="append",
        choices=sorted(BASELINES),
        help="restrict to one or more baselines (default: all)",
    )
    p.add_argument("--c-fa", type=float, default=CostModel().c_fa, help="dollar cost of an escape")
    p.add_argument("--c-fr", type=float, default=CostModel().c_fr, help="dollar cost of a scrap")
    p.add_argument(
        "--epsilon", type=float, default=None, help="optional cap on escape rate (regulatory floor)"
    )
    p.add_argument(
        "--out", type=Path, help="directory to write one results/<baseline>.json card into"
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.manifest:
        records = _load_manifest(args.manifest)
        source_note = f"manifest: {args.manifest}"
    else:
        n = args.synthetic if args.synthetic is not None else 300
        records = generate_manifest(n, seed=args.seed, defect_rate=args.defect_rate)
        source_note = (
            f"synthetic smoke-test, n={n}, seed={args.seed} "
            "-- NOT the real seed corpus (see datasets/sources.md)"
        )

    truth, groups = _truth_and_groups(records)
    cost_model = CostModel(c_fa=args.c_fa, c_fr=args.c_fr)
    names = args.baseline or sorted(BASELINES)

    print(f"Baselines harness -- {source_note}")
    print(f"N={len(records)}  cost model: escape=${cost_model.c_fa:.0f}  scrap=${cost_model.c_fr:.0f}\n")

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)

    for name in names:
        baseline = BASELINES[name]
        reports = run_baseline(name, records, truth, groups, cost_model)
        print(_card(baseline.name, baseline.describe, reports))
        print()

        if args.out:
            card = {
                "baseline": name,
                "describe": baseline.describe,
                "source": source_note,
                "cost_model": asdict(cost_model),
                "per_class": {cls: asdict(r.optimal) for cls, r in reports.items()},
            }
            out_path = args.out / f"{name}.json"
            out_path.write_text(json.dumps(card, indent=2))

    if args.out:
        print(f"Wrote results cards to {args.out}/")


if __name__ == "__main__":
    main()
