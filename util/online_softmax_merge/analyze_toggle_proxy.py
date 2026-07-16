#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Stream and analyze probe-gated RTL VCD bit-toggle proxies."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

import run_experiments as common
import run_toggle_proxy as runner

CATEGORIES = (
    "smu_scalar_exp_reciprocal",
    "smu_vector_datapath",
    "smu_control_fsm",
    "tcdm_facing_request_response",
    "core_or_rvv_baseline",
    "global_clock_reset",
    "other_cluster",
)
KNOWN_BITS = frozenset("01")
UNKNOWN_BITS = frozenset("xz")
CLOCK_RESET_PATTERN = re.compile(
    r"(^|[._])(clk|clock|rst|reset)(_|$)", re.IGNORECASE
)


class AnalysisError(ValueError):
    """Raised when toggle evidence is incomplete or inconsistent."""


def load_json(path: Path, expected: type) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisError(f"cannot load {path}: {error}") from error
    if not isinstance(value, expected):
        raise AnalysisError(f"{path} must contain {expected.__name__}")
    return value


def classify_signal(aliases: Iterable[str]) -> str:
    names = tuple(alias.lower() for alias in aliases)
    references = tuple(name.rsplit(".", 1)[-1] for name in names)
    if any(CLOCK_RESET_PATTERN.search(reference) for reference in references):
        return "global_clock_reset"
    engine = tuple(
        name for name in names if ".i_online_merge_update_engine." in name
    )
    if engine:
        if any("tcdm_req" in name or "tcdm_rsp" in name for name in engine):
            return "tcdm_facing_request_response"
        if any(
            marker in name
            for name in engine
            for marker in (
                ".i_old_exp_approx.",
                ".i_tile_exp_approx.",
                ".i_recip_approx.",
            )
        ):
            return "smu_scalar_exp_reciprocal"
        if any(
            marker in reference
            for reference in references
            for marker in (
                "o_old",
                "o_tile",
                "o_new",
                "vector",
                "elem",
                "dst_o",
                "src_o",
            )
        ):
            return "smu_vector_datapath"
        if any(
            marker in reference
            for reference in references
            for marker in (
                "exp",
                "recip",
                "weight",
                "scaled_l",
                "m_new",
                "l_new",
                "scalar",
            )
        ):
            return "smu_scalar_exp_reciprocal"
        return "smu_control_fsm"
    if any(
        marker in name
        for name in names
        for marker in (
            ".i_tcdm_interconnect.",
            ".i_reqrsp_to_tcdm.",
            ".i_tcdm_mux.",
        )
    ):
        return "tcdm_facing_request_response"
    if any(".gen_core[" in name for name in names):
        return "core_or_rvv_baseline"
    return "other_cluster"


def normalize_value(value: str, width: int) -> str | None:
    value = value.lower()
    if not value or any(bit not in KNOWN_BITS | UNKNOWN_BITS for bit in value):
        return None
    if len(value) < width:
        value = value[0] * (width - len(value)) + value
    elif len(value) > width:
        value = value[-width:]
    return value


def transition_counts(previous: str, current: str) -> tuple[int, int]:
    bit_toggles = 0
    unknown_transitions = 0
    for old, new in zip(previous, current):
        if old == new:
            continue
        if old in KNOWN_BITS and new in KNOWN_BITS:
            bit_toggles += 1
        else:
            unknown_transitions += 1
    return bit_toggles, unknown_transitions


def parse_vcd(
    path: Path, windows: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    if not path.is_file():
        raise AnalysisError(f"VCD does not exist: {path}")
    ordered = sorted(windows, key=lambda item: int(item["start_time"]))
    if len(ordered) != 2:
        raise AnalysisError("each capture must contain exactly two windows")
    for left, right in zip(ordered, ordered[1:]):
        if int(left["end_time"]) >= int(right["start_time"]):
            raise AnalysisError("VCD windows overlap or are unordered")

    widths: dict[str, int] = {}
    aliases: dict[str, list[str]] = defaultdict(list)
    scope: list[str] = []
    in_definitions = True
    categories: dict[str, str] = {}
    values: dict[str, str] = {}
    per_window: list[dict[str, dict[str, int]]] = [
        defaultdict(lambda: {"bit_toggles": 0, "unknown_transitions": 0})
        for _ in ordered
    ]
    initialized: list[set[str]] = [set() for _ in ordered]
    current_time: int | None = None
    active_window: int | None = None
    last_active_window: int | None = None

    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line:
                continue
            if in_definitions:
                tokens = line.split()
                if line.startswith("$scope ") and len(tokens) >= 4:
                    scope.append(tokens[2])
                elif line.startswith("$upscope"):
                    if not scope:
                        raise AnalysisError("VCD has unmatched $upscope")
                    scope.pop()
                elif line.startswith("$var ") and len(tokens) >= 6:
                    try:
                        width = int(tokens[2])
                    except ValueError as error:
                        raise AnalysisError(
                            f"invalid VCD width: {line}"
                        ) from error
                    identifier = tokens[3]
                    reference = tokens[4]
                    widths[identifier] = max(widths.get(identifier, 0), width)
                    aliases[identifier].append(".".join((*scope, reference)))
                elif line.startswith("$enddefinitions"):
                    in_definitions = False
                    categories = {
                        identifier: classify_signal(names)
                        for identifier, names in aliases.items()
                    }
                continue

            if line.startswith("#"):
                try:
                    current_time = int(line[1:])
                except ValueError as error:
                    raise AnalysisError(
                        f"invalid VCD timestamp: {line}"
                    ) from error
                active_window = None
                for index, window in enumerate(ordered):
                    if (
                        int(window["start_time"])
                        <= current_time
                        <= int(window["end_time"])
                    ):
                        active_window = index
                        break
                if (
                    active_window != last_active_window
                    and active_window is not None
                ):
                    values.clear()
                last_active_window = active_window
                continue
            if (
                active_window is None
                or current_time is None
                or line.startswith("$")
            ):
                continue

            value: str | None = None
            identifier: str | None = None
            if line[0].lower() in KNOWN_BITS | UNKNOWN_BITS:
                value = line[0]
                identifier = line[1:].strip()
            elif line[0].lower() == "b":
                parts = line[1:].split(None, 1)
                if len(parts) == 2:
                    value, identifier = parts
            if value is None or identifier is None or identifier not in widths:
                continue
            normalized = normalize_value(value, widths[identifier])
            if normalized is None:
                continue
            if (
                identifier in initialized[active_window]
                and identifier in values
            ):
                toggles, unknown = transition_counts(
                    values[identifier], normalized
                )
                category = categories[identifier]
                per_window[active_window][category]["bit_toggles"] += toggles
                per_window[active_window][category][
                    "unknown_transitions"
                ] += unknown
                per_window[active_window][identifier]["bit_toggles"] += toggles
                per_window[active_window][identifier][
                    "unknown_transitions"
                ] += unknown
            else:
                initialized[active_window].add(identifier)
            values[identifier] = normalized

    if in_definitions:
        raise AnalysisError("VCD lacks $enddefinitions")
    results = []
    for index, window in enumerate(ordered):
        category_rows = []
        total_toggles = 0
        total_unknown = 0
        for category in CATEGORIES:
            metrics = per_window[index].get(category, {})
            toggles = int(metrics.get("bit_toggles", 0))
            unknown = int(metrics.get("unknown_transitions", 0))
            identifiers = [
                identifier
                for identifier, signal_category in categories.items()
                if signal_category == category
            ]
            row = {
                "category": category,
                "signal_count": len(identifiers),
                "declared_bits": sum(widths[item] for item in identifiers),
                "bit_toggles": toggles,
                "unknown_transitions": unknown,
            }
            category_rows.append(row)
            total_toggles += toggles
            total_unknown += unknown
        signal_rows = []
        for identifier in sorted(widths):
            metrics = per_window[index].get(identifier, {})
            toggles = int(metrics.get("bit_toggles", 0))
            unknown = int(metrics.get("unknown_transitions", 0))
            if not toggles and not unknown:
                continue
            signal_rows.append(
                {
                    "identifier": identifier,
                    "canonical_name": sorted(aliases[identifier])[0],
                    "alias_count": len(aliases[identifier]),
                    "width": widths[identifier],
                    "category": categories[identifier],
                    "bit_toggles": toggles,
                    "unknown_transitions": unknown,
                }
            )
        results.append(
            {
                "window": dict(window),
                "total_bit_toggles": total_toggles,
                "unknown_transitions": total_unknown,
                "hierarchy": category_rows,
                "signals": signal_rows,
            }
        )
    return {
        "timescale": (
            "VCD timestamps; capture manifest records half-cycle semantics"
        ),
        "unique_signal_identifiers": len(widths),
        "declared_bits": sum(widths.values()),
        "windows": results,
    }


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        raise AnalysisError(f"cannot write empty CSV: {path.name}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def validate_capture_root(
    root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    required = (
        "run_manifest.json",
        "capture_records.json",
        "failures.json",
        "commands.json",
        "artifact_manifest.json",
    )
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        raise AnalysisError(f"capture root is missing {missing}")
    manifest = load_json(root / "run_manifest.json", dict)
    captures = load_json(root / "capture_records.json", list)
    failures = load_json(root / "failures.json", list)
    if failures:
        raise AnalysisError("formal capture contains retained failures")
    if manifest.get("toggle_proxy_evidence") is not True:
        raise AnalysisError("capture manifest is not formal toggle evidence")
    if any(
        not isinstance(row, dict) or row.get("status") != "pass"
        for row in captures
    ):
        raise AnalysisError("capture records are incomplete or non-passing")
    coordinates = {(row.get("N"), row.get("D")) for row in captures}
    if coordinates != set(runner.MANDATORY_CASES):
        raise AnalysisError("capture does not contain the mandatory case set")
    return manifest, captures


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    script = Path(__file__).resolve()
    root = script.parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument("--result-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    result_root = args.result_root.resolve()
    output_dir = args.output_dir.resolve()
    common.validate_work_dir(output_dir, repo_root)
    if output_dir.exists():
        raise SystemExit(f"output directory already exists: {output_dir}")
    manifest, captures = validate_capture_root(result_root)
    commit = common.git_output(repo_root, "rev-parse", "HEAD")
    dirty = bool(common.git_output(repo_root, "status", "--porcelain"))
    if dirty or commit != manifest.get("git_commit"):
        raise SystemExit("analysis requires the clean captured source commit")
    output_dir.mkdir(parents=True)

    summaries: list[dict[str, Any]] = []
    hierarchy_rows: list[dict[str, Any]] = []
    signal_rows: list[dict[str, Any]] = []
    analyses = []
    for capture in sorted(captures, key=lambda row: (row["N"], row["D"])):
        vcd = Path(str(capture["vcd_path"]))
        if common.sha256_file(vcd) != capture.get("vcd_sha256"):
            raise AnalysisError(f"VCD hash mismatch: {vcd}")
        parsed = parse_vcd(vcd, capture["windows"])
        for window in parsed["windows"]:
            marker = window["window"]
            cycles = int(marker["target_cycles"])
            elements = int(capture["elements"])
            toggles = int(window["total_bit_toggles"])
            key = {
                "N": capture["N"],
                "D": capture["D"],
                "implementation": marker["implementation"],
                "repeat": marker["repeat"],
            }
            summaries.append(
                {
                    **key,
                    "elements": elements,
                    "start_time": marker["start_time"],
                    "end_time": marker["end_time"],
                    "marker_span_half_cycles": marker[
                        "marker_span_half_cycles"
                    ],
                    "target_cycles": cycles,
                    "total_bit_toggles": toggles,
                    "toggles_per_cycle": toggles / cycles,
                    "toggles_per_element": toggles / elements,
                    "unknown_transitions": window["unknown_transitions"],
                }
            )
            for row in window["hierarchy"]:
                hierarchy_rows.append({**key, **row})
            for row in window["signals"]:
                signal_rows.append({**key, **row})
        analyses.append({"capture": capture, "vcd_analysis": parsed})

    write_csv(output_dir / "toggle_summary.csv", summaries)
    write_csv(output_dir / "hierarchy_toggle_summary.csv", hierarchy_rows)
    write_csv(output_dir / "signal_toggle_summary.csv", signal_rows)
    analysis = {
        "schema_version": 1,
        "objective": "representative zero-delay RTL bit-toggle proxy",
        "git_commit": commit,
        "cfg_hash": manifest.get("cfg_hash"),
        "capture_root": str(result_root),
        "capture_files": {
            name: common.sha256_file(result_root / name)
            for name in (
                "run_manifest.json",
                "capture_records.json",
                "failures.json",
                "commands.json",
                "artifact_manifest.json",
            )
        },
        "measurement_semantics": {
            "metric": "known 0/1 Hamming-distance bit toggles",
            "initial_value_policy": (
                "first value per signal per gated window initializes state and "
                "does not count as a toggle"
            ),
            "unknown_policy": "x/z-involving transitions retained separately",
            "alias_policy": "each VCD identifier counted once",
            "window_policy": "inclusive indexed probe-gated marker times",
        },
        "acceptance_gates": {
            "mandatory_cases": [list(case) for case in runner.MANDATORY_CASES],
            "summary_rows": len(summaries),
            "expected_summary_rows": 6,
            "capture_evidence": True,
            "physical_power_energy_supported": False,
        },
        "claim_boundary": manifest.get("claim_boundary"),
        "captures": analyses,
    }
    common.write_json(output_dir / "analysis.json", analysis)
    output_files = (
        "analysis.json",
        "toggle_summary.csv",
        "hierarchy_toggle_summary.csv",
        "signal_toggle_summary.csv",
    )
    common.write_json(
        output_dir / "artifact_manifest.json",
        [
            {
                "path": name,
                "sha256": common.sha256_file(output_dir / name),
                "git_commit": commit,
                "cfg_hash": manifest.get("cfg_hash"),
            }
            for name in output_files
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
