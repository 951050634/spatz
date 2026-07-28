#!/usr/bin/env python3
"""Check exact-trial reproducibility and cross-configuration fairness."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import experiment_common as common


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--expected-trials", type=int, default=3)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def group_key(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record.get("config"),
        record.get("counter_profile"),
        record.get("N"),
        record.get("D"),
        record.get("seed"),
        record.get("input_pattern"),
    )


def coordinate_key(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record.get("counter_profile"),
        record.get("N"),
        record.get("D"),
        record.get("seed"),
        record.get("input_pattern"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.expected_trials < 3:
        raise SystemExit("--expected-trials must be at least three")
    records_path = args.records.resolve()
    payload = json.loads(records_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit("records file must contain a JSON array")

    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    coordinates: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in payload:
        groups.setdefault(group_key(record), []).append(record)
        coordinates.setdefault(coordinate_key(record), []).append(record)

    group_results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for key, group in sorted(groups.items(), key=lambda item: str(item[0])):
        trials = [record.get("trial") for record in group]
        statuses = [record.get("status") for record in group]
        cycles = [record.get("kernel_cycles") for record in group]
        expected_set = set(range(args.expected_trials))
        exact_trials = set(trials) == expected_set and len(group) == (
            args.expected_trials
        )
        all_pass = all(status == "PASS" for status in statuses)
        exact_cycles = (
            all_pass
            and all(cycle is not None for cycle in cycles)
            and len(set(cycles)) == 1
        )
        input_hashes = {record.get("input_hash") for record in group}
        binary_hashes = {record.get("binary_hash") for record in group}
        has_target_hashes = all(
            "target_result_hash" in record for record in group
        )
        target_hashes = {
            record.get("target_result_hash") for record in group
        }
        stable_artifacts = len(input_hashes) == 1 and len(binary_hashes) == 1
        stable_target_output = (
            None
            if not has_target_hashes
            else None not in target_hashes and len(target_hashes) == 1
        )
        passed = (
            exact_trials
            and exact_cycles
            and stable_artifacts
            and stable_target_output is not False
        )
        result = {
            "group": list(key),
            "record_count": len(group),
            "trials": trials,
            "statuses": statuses,
            "kernel_cycles": cycles,
            "exact_trials": exact_trials,
            "exact_cycles": exact_cycles,
            "stable_input_and_binary": stable_artifacts,
            "stable_target_output": stable_target_output,
            "passed": passed,
        }
        group_results.append(result)
        if not passed:
            failures.append(
                {
                    "kind": "TRIAL_REPRODUCIBILITY",
                    **result,
                }
            )

    fairness_fields = (
        "cfg_hash",
        "simulator_hash",
        "worktree_snapshot_hash",
        "input_hash",
        "compiler_fairness_hash",
        "N",
        "D",
        "seed",
        "input_pattern",
        "logical_N",
        "logical_D",
        "padded_N",
        "padded_D",
        "padding_ratio",
    )
    fairness_results: list[dict[str, Any]] = []
    for key, group in sorted(
        coordinates.items(), key=lambda item: str(item[0])
    ):
        mismatches = {
            field: sorted(
                {str(record.get(field)) for record in group}
            )
            for field in fairness_fields
            if len({str(record.get(field)) for record in group}) != 1
        }
        result = {
            "coordinate": list(key),
            "configurations": sorted(
                {str(record.get("config")) for record in group}
            ),
            "mismatches": mismatches,
            "passed": not mismatches,
        }
        fairness_results.append(result)
        if mismatches:
            failures.append({"kind": "CROSS_CONFIG_FAIRNESS", **result})

    report = {
        "schema_version": 1,
        "records_path": str(records_path),
        "records_sha256": common.sha256_file(records_path),
        "expected_trials": args.expected_trials,
        "record_count": len(payload),
        "status_counts": dict(
            Counter(str(record.get("status")) for record in payload)
        ),
        "group_results": group_results,
        "fairness_results": fairness_results,
        "failures": failures,
        "passed": not failures,
    }
    output = (
        args.output.resolve()
        if args.output
        else records_path.parent / "reproducibility_report.json"
    )
    common.write_json(output, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
