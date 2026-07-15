#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Analyze C0--C3 core--SMU concurrency and 16 bank phases."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Sequence

import run_concurrency as runner

SCENARIOS = ("C1", "C2", "C3")
BASELINE_CORE = {
    "C1": "C0_REG",
    "C2": "C0_STREAM",
    "C3": "C3_CORE",
}
RATIO_FIELDS = (
    "eta_overlap",
    "slowdown_smu",
    "slowdown_core",
    "congestion_ratio",
    "core_bytes_per_cycle",
    "smu_elements_per_cycle",
    "standalone_smu_elements_per_cycle",
)
SUMMARY_FIELDS = (
    "T_smu",
    "T_core",
    "T_concurrent",
    "T_smu_concurrent",
    "T_core_concurrent",
    "overlap_saved_cycles",
    *RATIO_FIELDS,
    "tcdm_accessed",
    "tcdm_congested",
)
PROVENANCE_RECORD_FIELDS = {
    "source_root",
    "git_commit",
    "git_dirty",
    "cfg_path",
    "cfg_hash",
    "tool_version",
}
RUN_PROVENANCE_FIELDS = (
    "git_commit",
    "git_dirty",
    "cfg_path",
    "cfg_hash",
    "tool_version",
)


class AnalysisError(ValueError):
    """Raised when passing evidence is internally inconsistent."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path, expected: type) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisError(f"cannot load {path}: {error}") from error
    if not isinstance(value, expected):
        raise AnalysisError(
            f"{path} must contain {expected.__name__}, "
            f"got {type(value).__name__}"
        )
    return value


def require_int(
    record: dict[str, Any], field: str, *, minimum: int | None = None
) -> int:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise AnalysisError(f"{field} must be an integer, got {value!r}")
    if minimum is not None and value < minimum:
        raise AnalysisError(f"{field} must be >= {minimum}, got {value}")
    return value


def fraction_json(value: Fraction) -> dict[str, int | float]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal": float(value),
    }


def median_fraction(values: Iterable[int | float | Fraction]) -> Fraction:
    converted: list[Fraction] = []
    for value in values:
        if isinstance(value, Fraction):
            converted.append(value)
        elif (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise AnalysisError(f"invalid median value: {value!r}")
        else:
            converted.append(Fraction(str(value)))
    if not converted:
        raise AnalysisError("cannot take median of an empty sequence")
    converted.sort()
    middle = len(converted) // 2
    if len(converted) % 2:
        return converted[middle]
    return (converted[middle - 1] + converted[middle]) / 2


def set_fraction(
    row: dict[str, Any], field: str, value: Fraction | None
) -> None:
    if value is None:
        row[field] = None
        row[f"{field}_numerator"] = None
        row[f"{field}_denominator"] = None
        return
    row[field] = float(value)
    row[f"{field}_numerator"] = value.numerator
    row[f"{field}_denominator"] = value.denominator


def ratio(numerator: int | Fraction, denominator: int) -> Fraction | None:
    if denominator == 0:
        return None
    return Fraction(numerator, denominator)


def validate_result_root(root: Path) -> None:
    if not root.is_dir():
        raise AnalysisError(f"result root is not a directory: {root}")
    required = (
        "run_manifest.json",
        "concurrency_records.json",
        "concurrency_metadata.json",
        "fsm_records.json",
        "failures.json",
        "commands.json",
        "artifact_manifest.json",
    )
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        raise AnalysisError(f"result root {root} is missing {missing}")


def load_evidence(result_roots: Sequence[Path]) -> dict[str, Any]:
    if not result_roots:
        raise AnalysisError("at least one result root is required")
    roots: list[dict[str, Any]] = []
    bundles: list[dict[str, Any]] = []
    resolved = [supplied.resolve() for supplied in result_roots]
    duplicates = [
        str(root)
        for root, count in Counter(resolved).items()
        if count > 1
    ]
    if duplicates:
        raise AnalysisError(f"duplicate result roots: {sorted(duplicates)}")
    for root in sorted(resolved, key=str):
        validate_result_root(root)
        paths = {
            name: root / name
            for name in (
                "run_manifest.json",
                "concurrency_records.json",
                "concurrency_metadata.json",
                "fsm_records.json",
                "failures.json",
                "commands.json",
                "artifact_manifest.json",
            )
        }
        manifest = load_json(paths["run_manifest.json"], dict)
        records = load_json(paths["concurrency_records.json"], list)
        metadata = load_json(paths["concurrency_metadata.json"], list)
        fsm_records = load_json(paths["fsm_records.json"], list)
        failures = load_json(paths["failures.json"], list)
        commands = load_json(paths["commands.json"], list)
        artifacts = load_json(paths["artifact_manifest.json"], list)
        for kind, values in (
            ("record", records),
            ("metadata", metadata),
            ("FSM record", fsm_records),
            ("failure", failures),
            ("command", commands),
            ("artifact", artifacts),
        ):
            if any(not isinstance(value, dict) for value in values):
                raise AnalysisError(f"non-object {kind} in {root}")
        tool_versions = manifest.get("tool_versions")
        if not isinstance(tool_versions, dict):
            tool_versions = {}
        simulator_version = tool_versions.get("simulator")
        if not isinstance(simulator_version, dict):
            simulator_version = {}
        root_entry = {
            "root": str(root),
            "git_commit": manifest.get("git_commit"),
            "git_dirty": manifest.get("git_dirty"),
            "cfg_path": manifest.get("cfg_path"),
            "cfg_hash": manifest.get("cfg_hash"),
            "simulator_sha256": simulator_version.get("sha256"),
            "tool_versions": manifest.get("tool_versions"),
            "simulator_source": manifest.get("simulator_source"),
            "wall_clock_start_end": manifest.get("wall_clock_start_end"),
            "validation_result": manifest.get("validation_result"),
            "case": manifest.get("case"),
            "expected_schedule": manifest.get("expected_schedule"),
            "files": {name: sha256_file(path) for name, path in paths.items()},
        }
        roots.append(root_entry)
        bundles.append({
            "root": root,
            "manifest": manifest,
            "records": records,
            "metadata": metadata,
            "fsm_records": fsm_records,
            "failures": failures,
            "commands": commands,
            "artifacts": artifacts,
        })
    return {"roots": roots, "bundles": bundles}


def case_from_manifest(manifest: dict[str, Any]) -> tuple[int, int, int]:
    case = manifest.get("case")
    if not isinstance(case, dict):
        raise AnalysisError("run manifest lacks case object")
    n = require_int(case, "n", minimum=1)
    d = require_int(case, "d", minimum=1)
    repeats = require_int(case, "repeats", minimum=3)
    return n, d, repeats


def statuses_for(bundle: dict[str, Any]) -> list[str]:
    return sorted({str(record.get("status")) for record in bundle["records"]})


def equivalent_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in PROVENANCE_RECORD_FIELDS
    }


def validate_provenance(
    record: dict[str, Any], manifest: dict[str, Any], label: str
) -> None:
    for field in RUN_PROVENANCE_FIELDS:
        if field not in record:
            raise AnalysisError(f"{label} lacks provenance field {field}")
        if record[field] != manifest.get(field):
            raise AnalysisError(f"{label} {field} does not match manifest")


def validate_passing_manifest(
    bundle: dict[str, Any], n: int, d: int, repeats: int
) -> None:
    if bundle["failures"]:
        raise AnalysisError("passing result root contains failures")
    if not bundle["commands"]:
        raise AnalysisError("passing result root contains no commands")
    for index, command in enumerate(bundle["commands"]):
        if command.get("status") != "pass" or command.get("returncode") != 0:
            raise AnalysisError(f"passing command {index} is not successful")

    expected = bundle["manifest"].get("expected_schedule")
    if not isinstance(expected, dict):
        raise AnalysisError("passing manifest lacks expected_schedule")
    expected_schedule = {
        "scenario_counts": runner.expected_scenario_counts(repeats),
        "record_count": len(runner.expected_record_keys(repeats)),
        "smu_invocation_count": runner.expected_smu_invocations(repeats),
        "phases_bytes": list(runner.PHASES),
    }
    if expected != expected_schedule:
        raise AnalysisError("manifest expected_schedule does not match the case")

    validation = bundle["manifest"].get("validation_result")
    expected_validation = {
        "statuses": ["pass"],
        "record_count": expected_schedule["record_count"],
        "metadata_count": 1,
        "fsm_record_count": expected_schedule["smu_invocation_count"],
        "failure_count": 0,
    }
    if validation != expected_validation:
        raise AnalysisError("manifest validation_result is not a complete pass")

    metadata = bundle["metadata"][0]
    validate_provenance(metadata, bundle["manifest"], "metadata record")
    for field, value in (("N", n), ("D", d), ("repeats", repeats)):
        if require_int(metadata, field, minimum=1) != value:
            raise AnalysisError(f"metadata {field} does not match manifest")


def validate_pass_record(
    record: dict[str, Any], n: int, d: int, repeats: int
) -> None:
    if record.get("status") != "pass" or record.get("target_status") != "pass":
        raise AnalysisError("passing schedule contains a non-pass target status")
    if record.get("command_status") != "pass":
        raise AnalysisError("passing schedule contains a non-pass command")
    if record.get("command_returncode") != 0:
        raise AnalysisError("passing schedule contains a nonzero command")
    if require_int(record, "N", minimum=1) != n:
        raise AnalysisError("record N does not match manifest")
    if require_int(record, "D", minimum=1) != d:
        raise AnalysisError("record D does not match manifest")
    repeat = require_int(record, "repeat", minimum=-1)
    if repeat >= repeats:
        raise AnalysisError(f"repeat {repeat} exceeds manifest repeat count")
    require_int(record, "phase_bytes", minimum=0)
    require_int(record, "total_cycles", minimum=0)
    require_int(record, "core_cycles", minimum=0)
    require_int(record, "tcdm_accessed", minimum=0)
    require_int(record, "tcdm_congested", minimum=0)
    for field in (
        "status_reads_during_core",
        "counter_reads_inside_window",
        "merge_mismatches",
        "core_mismatches",
    ):
        if require_int(record, field, minimum=0) != 0:
            raise AnalysisError(f"{field} must be zero in passing evidence")


def validate_fsm_record(record: dict[str, Any], n: int, d: int) -> int:
    invocation = require_int(record, "invocation", minimum=0)
    if require_int(record, "N", minimum=1) != n:
        raise AnalysisError(f"FSM invocation {invocation} N mismatch")
    if require_int(record, "D", minimum=1) != d:
        raise AnalysisError(f"FSM invocation {invocation} D mismatch")
    if record.get("terminal_state") != "DONE":
        raise AnalysisError(
            f"FSM invocation {invocation} ended in "
            f"{record.get('terminal_state')!r}"
        )
    state_sum = sum(
        require_int(record, field, minimum=0)
        for field in runner.FSM_STATE_FIELDS
    )
    busy = require_int(record, "busy_cycles", minimum=1)
    if state_sum != busy:
        raise AnalysisError(
            f"FSM invocation {invocation} state sum {state_sum} != busy {busy}"
        )
    return invocation


def index_passing_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    n, d, repeats = case_from_manifest(bundle["manifest"])
    records = bundle["records"]
    if len(bundle["metadata"]) != 1:
        raise AnalysisError(
            f"{bundle['root']} needs exactly one concurrency metadata record"
        )
    validate_passing_manifest(bundle, n, d, repeats)
    expected_keys = runner.expected_record_keys(repeats)
    by_key: dict[tuple[str, int, int], dict[str, Any]] = {}
    for record_index, record in enumerate(records):
        validate_pass_record(record, n, d, repeats)
        validate_provenance(
            record, bundle["manifest"], f"target record {record_index}"
        )
        scenario = str(record.get("scenario"))
        if scenario == "ALL":
            raise AnalysisError("passing schedule contains terminal ALL record")
        key = (
            scenario,
            require_int(record, "phase_bytes", minimum=0),
            require_int(record, "repeat", minimum=-1),
        )
        if key in by_key:
            if equivalent_record(by_key[key]) == equivalent_record(record):
                raise AnalysisError(f"duplicate passing record key {key}")
            raise AnalysisError(f"conflicting passing record key {key}")
        by_key[key] = record
    if set(by_key) != expected_keys:
        missing = sorted(expected_keys - set(by_key))
        unexpected = sorted(set(by_key) - expected_keys)
        raise AnalysisError(
            f"incomplete passing schedule: missing={missing} "
            f"unexpected={unexpected}"
        )

    fsm_by_invocation: dict[int, dict[str, Any]] = {}
    for record_index, record in enumerate(bundle["fsm_records"]):
        invocation = validate_fsm_record(record, n, d)
        validate_provenance(
            record, bundle["manifest"], f"FSM record {record_index}"
        )
        if invocation in fsm_by_invocation:
            raise AnalysisError(f"duplicate FSM invocation {invocation}")
        fsm_by_invocation[invocation] = record
    expected_invocations = set(range(runner.expected_smu_invocations(repeats)))
    if set(fsm_by_invocation) != expected_invocations:
        raise AnalysisError(
            "FSM invocation set mismatch: "
            f"missing={sorted(expected_invocations - set(fsm_by_invocation))} "
            f"unexpected={sorted(set(fsm_by_invocation) - expected_invocations)}"
        )

    smu_records = [
        record
        for record in by_key.values()
        if record.get("scenario") in runner.SMU_SCENARIOS
    ]
    target_invocations: dict[int, dict[str, Any]] = {}
    for record in smu_records:
        invocation = require_int(record, "smu_invocation", minimum=0)
        if invocation in target_invocations:
            raise AnalysisError(f"duplicate target SMU invocation {invocation}")
        target_invocations[invocation] = record
    if set(target_invocations) != set(fsm_by_invocation):
        raise AnalysisError("target/FSM invocation sets do not match exactly")

    return {
        "root": bundle["root"],
        "manifest": bundle["manifest"],
        "n": n,
        "d": d,
        "repeats": repeats,
        "records": by_key,
        "fsm": fsm_by_invocation,
        "metadata": bundle["metadata"][0],
    }


def fsm_for(indexed: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    invocation = require_int(record, "smu_invocation", minimum=0)
    try:
        return indexed["fsm"][invocation]
    except KeyError as error:  # pragma: no cover - guarded by bundle validation
        raise AnalysisError(f"missing FSM invocation {invocation}") from error


def build_observation(
    indexed: dict[str, Any], scenario: str, phase: int, repeat: int
) -> dict[str, Any]:
    records = indexed["records"]
    concurrent = records[(scenario, phase, repeat)]
    smu_alone = records[("C0_SMU", 0, repeat)]
    core_scenario = BASELINE_CORE[scenario]
    core_phase = phase if scenario == "C3" else 0
    core_alone = records[(core_scenario, core_phase, repeat)]
    concurrent_fsm = fsm_for(indexed, concurrent)
    standalone_fsm = fsm_for(indexed, smu_alone)

    t_smu = require_int(standalone_fsm, "busy_cycles", minimum=1)
    t_core = require_int(core_alone, "core_cycles", minimum=1)
    t_concurrent = require_int(concurrent, "total_cycles", minimum=1)
    t_smu_concurrent = require_int(
        concurrent_fsm, "busy_cycles", minimum=1
    )
    t_core_concurrent = require_int(concurrent, "core_cycles", minimum=1)
    standalone_total = require_int(smu_alone, "total_cycles", minimum=1)
    core_standalone_total = require_int(
        core_alone, "total_cycles", minimum=1
    )
    if standalone_total < t_smu:
        raise AnalysisError("standalone SMU busy cycles exceed its total window")
    if core_standalone_total < t_core:
        raise AnalysisError("standalone core cycles exceed its total window")
    if t_concurrent < max(t_smu_concurrent, t_core_concurrent):
        raise AnalysisError(
            "concurrent total window is shorter than a component window"
        )
    accessed = require_int(concurrent, "tcdm_accessed", minimum=0)
    congested = require_int(concurrent, "tcdm_congested", minimum=0)
    core_bytes = require_int(concurrent, "core_bytes", minimum=0)
    elements = indexed["n"] * indexed["d"]
    overlap_saved = t_smu + t_core - t_concurrent

    row: dict[str, Any] = {
        "source_root": str(indexed["root"]),
        "git_commit": indexed["manifest"].get("git_commit"),
        "cfg_hash": indexed["manifest"].get("cfg_hash"),
        "N": indexed["n"],
        "D": indexed["d"],
        "scenario": scenario,
        "phase_bytes": phase,
        "bank_phase": phase // 8,
        "repeat": repeat,
        "measured": repeat >= 0,
        "smu_baseline_scenario": "C0_SMU",
        "core_baseline_scenario": core_scenario,
        "standalone_smu_invocation": require_int(
            smu_alone, "smu_invocation", minimum=0
        ),
        "concurrent_smu_invocation": require_int(
            concurrent, "smu_invocation", minimum=0
        ),
        "T_smu": t_smu,
        "T_core": t_core,
        "T_concurrent": t_concurrent,
        "T_smu_concurrent": t_smu_concurrent,
        "T_core_concurrent": t_core_concurrent,
        "overlap_saved_cycles": overlap_saved,
        "concurrency_faster_than_serial": overlap_saved > 0,
        "tcdm_accessed": accessed,
        "tcdm_congested": congested,
        "core_elements": require_int(concurrent, "core_elements", minimum=0),
        "core_bytes": core_bytes,
        "smu_elements": elements,
        "status_reads": require_int(concurrent, "status_reads", minimum=1),
        "status_reads_during_core": require_int(
            concurrent, "status_reads_during_core", minimum=0
        ),
        "counter_reads_inside_window": require_int(
            concurrent, "counter_reads_inside_window", minimum=0
        ),
        "merge_mismatches": require_int(
            concurrent, "merge_mismatches", minimum=0
        ),
        "core_mismatches": require_int(
            concurrent, "core_mismatches", minimum=0
        ),
        "status": concurrent.get("status"),
    }
    set_fraction(
        row,
        "eta_overlap",
        ratio(overlap_saved, min(t_smu, t_core)),
    )
    set_fraction(
        row,
        "slowdown_smu",
        ratio(t_smu_concurrent, t_smu),
    )
    set_fraction(
        row,
        "slowdown_core",
        ratio(t_core_concurrent, t_core),
    )
    set_fraction(row, "congestion_ratio", ratio(congested, accessed))
    set_fraction(
        row,
        "core_bytes_per_cycle",
        ratio(core_bytes, t_core_concurrent) if core_bytes else None,
    )
    set_fraction(
        row,
        "smu_elements_per_cycle",
        ratio(elements, t_smu_concurrent),
    )
    set_fraction(
        row,
        "standalone_smu_elements_per_cycle",
        ratio(elements, t_smu),
    )
    for field in runner.FSM_STATE_FIELDS:
        row[f"smu_{field}"] = require_int(
            concurrent_fsm, field, minimum=0
        )
    return row


def build_bundle_rows(indexed: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for repeat in range(-1, indexed["repeats"]):
        rows.append(build_observation(indexed, "C1", 0, repeat))
        rows.append(build_observation(indexed, "C2", 0, repeat))
        for phase in runner.PHASES:
            rows.append(build_observation(indexed, "C3", phase, repeat))
    return rows


def summarize_rows(
    rows: Sequence[dict[str, Any]], *, label: str
) -> dict[str, Any]:
    measured = [row for row in rows if row["measured"]]
    if not measured:
        raise AnalysisError(f"{label} has no measured rows")
    medians: dict[str, Any] = {}
    for field in SUMMARY_FIELDS:
        if field in RATIO_FIELDS:
            values = [
                Fraction(
                    row[f"{field}_numerator"],
                    row[f"{field}_denominator"],
                )
                for row in measured
                if row.get(field) is not None
            ]
        else:
            values = [
                row[field]
                for row in measured
                if row.get(field) is not None
            ]
        medians[field] = (
            fraction_json(median_fraction(values)) if values else None
        )
    eta_values = [Fraction(
        row["eta_overlap_numerator"], row["eta_overlap_denominator"]
    ) for row in measured]
    return {
        "label": label,
        "row_count": len(rows),
        "warmup_count": sum(not row["measured"] for row in rows),
        "measured_count": len(measured),
        "negative_overlap_count": sum(value < 0 for value in eta_values),
        "zero_overlap_count": sum(value == 0 for value in eta_values),
        "eta_overlap_min": fraction_json(min(eta_values)),
        "eta_overlap_max": fraction_json(max(eta_values)),
        "medians": medians,
    }


def phase_selection(
    phase_summaries: Sequence[dict[str, Any]], mode: str
) -> dict[str, Any]:
    if len(phase_summaries) != len(runner.PHASES):
        raise AnalysisError("phase selection requires all 16 phases")
    ordered = sorted(
        phase_summaries,
        key=lambda row: (
            Fraction(
                row["medians"]["T_concurrent"]["numerator"],
                row["medians"]["T_concurrent"]["denominator"],
            ),
            row["phase_bytes"],
        ),
    )
    if mode == "best":
        return ordered[0]
    if mode == "worst":
        return ordered[-1]
    values = [
        Fraction(
            row["medians"]["T_concurrent"]["numerator"],
            row["medians"]["T_concurrent"]["denominator"],
        )
        for row in ordered
    ]
    target = median_fraction(values)
    return min(
        ordered,
        key=lambda row: (
            abs(
                Fraction(
                    row["medians"]["T_concurrent"]["numerator"],
                    row["medians"]["T_concurrent"]["denominator"],
                )
                - target
            ),
            Fraction(
                row["medians"]["T_concurrent"]["numerator"],
                row["medians"]["T_concurrent"]["denominator"],
            ),
            row["phase_bytes"],
        ),
    )


def summarize(
    observations: Sequence[dict[str, Any]], required_cases: Sequence[tuple[int, int]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    scenario_summaries = []
    phase_summaries = []
    phase_selections = []
    for n, d in required_cases:
        coordinate_rows = [
            row for row in observations if (row["N"], row["D"]) == (n, d)
        ]
        for scenario in SCENARIOS:
            rows = [row for row in coordinate_rows if row["scenario"] == scenario]
            summary = summarize_rows(rows, label=f"N{n}_D{d}_{scenario}")
            summary.update({"N": n, "D": d, "scenario": scenario})
            scenario_summaries.append(summary)
        phases = []
        for phase in runner.PHASES:
            rows = [
                row
                for row in coordinate_rows
                if row["scenario"] == "C3" and row["phase_bytes"] == phase
            ]
            summary = summarize_rows(
                rows, label=f"N{n}_D{d}_C3_phase{phase}"
            )
            summary.update({
                "N": n,
                "D": d,
                "scenario": "C3",
                "phase_bytes": phase,
                "bank_phase": phase // 8,
            })
            phases.append(summary)
            phase_summaries.append(summary)
        phase_selections.append({
            "N": n,
            "D": d,
            "criterion": "median T_concurrent; median selects closest phase",
            "best": phase_selection(phases, "best"),
            "worst": phase_selection(phases, "worst"),
            "median": phase_selection(phases, "median"),
        })
    return scenario_summaries, phase_summaries, phase_selections


def git_context(repo_root: Path) -> dict[str, Any]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
        ).strip()
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=repo_root, text=True
        ).strip())
    except (OSError, subprocess.CalledProcessError) as error:
        raise AnalysisError(f"cannot inspect analysis Git context: {error}") from error
    return {"commit": commit, "dirty": dirty}


def retained_input(evidence: dict[str, Any]) -> dict[str, Any]:
    records = []
    failures = []
    metadata = []
    commands = []
    artifacts = []
    for bundle in evidence["bundles"]:
        source = str(bundle["root"])
        records.extend({**row, "source_root": source} for row in bundle["records"])
        metadata.extend({**row, "source_root": source} for row in bundle["metadata"])
        failures.extend(
            {"source_root": source, "failure": row}
            for row in bundle["failures"]
        )
        commands.extend(
            {"source_root": source, "command": row}
            for row in bundle["commands"]
        )
        artifacts.extend(
            {"source_root": source, "artifact": row}
            for row in bundle["artifacts"]
        )
    return {
        "status_counts": dict(sorted(Counter(
            str(record.get("status")) for record in records
        ).items())),
        "records": records,
        "metadata": metadata,
        "failures": failures,
        "commands": commands,
        "artifacts": artifacts,
    }


def analyze(
    repo_root: Path,
    result_roots: Sequence[Path],
    required_cases: Sequence[tuple[int, int]],
    tool_path: Path,
) -> dict[str, Any]:
    repo = repo_root.resolve()
    if not required_cases:
        raise AnalysisError("at least one required case is required")
    normalized_cases: list[tuple[int, int]] = []
    for case in required_cases:
        if (
            not isinstance(case, (tuple, list)) or len(case) != 2
            or any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in case
            )
            or any(value <= 0 for value in case)
        ):
            raise AnalysisError(f"invalid required case: {case!r}")
        normalized_cases.append((case[0], case[1]))
    if len(set(normalized_cases)) != len(normalized_cases):
        raise AnalysisError("required cases must not repeat")
    required_cases = normalized_cases
    evidence = load_evidence(result_roots)
    retained = retained_input(evidence)
    observations: list[dict[str, Any]] = []
    analyzed_runs = []
    skipped_runs = []
    coordinates_seen: Counter[tuple[int, int]] = Counter()

    for bundle in evidence["bundles"]:
        statuses = statuses_for(bundle)
        try:
            coordinate = case_from_manifest(bundle["manifest"])[:2]
        except AnalysisError:
            coordinate = (None, None)
        if statuses != ["pass"]:
            skipped_runs.append({
                "source_root": str(bundle["root"]),
                "coordinate": list(coordinate),
                "statuses": statuses,
                "record_count": len(bundle["records"]),
                "fsm_record_count": len(bundle["fsm_records"]),
                "failure_count": len(bundle["failures"]),
            })
            continue
        indexed = index_passing_bundle(bundle)
        coordinate = (indexed["n"], indexed["d"])
        if coordinate not in set(required_cases):
            skipped_runs.append({
                "source_root": str(bundle["root"]),
                "coordinate": list(coordinate),
                "statuses": statuses,
                "reason": "coordinate not requested",
            })
            continue
        rows = build_bundle_rows(indexed)
        observations.extend(rows)
        coordinates_seen[coordinate] += 1
        analyzed_runs.append({
            "source_root": str(bundle["root"]),
            "N": indexed["n"],
            "D": indexed["d"],
            "repeats": indexed["repeats"],
            "observation_count": len(rows),
            "warmup_count": sum(not row["measured"] for row in rows),
            "measured_count": sum(row["measured"] for row in rows),
            "target_fsm_pairs": len(indexed["fsm"]),
        })

    missing_cases = [
        list(case) for case in required_cases if coordinates_seen[case] == 0
    ]
    scenario_summaries: list[dict[str, Any]] = []
    phase_summaries: list[dict[str, Any]] = []
    phase_selections: list[dict[str, Any]] = []
    if not missing_cases:
        scenario_summaries, phase_summaries, phase_selections = summarize(
            observations, required_cases
        )

    provenance = git_context(repo)
    input_commits = {root["git_commit"] for root in evidence["roots"]}
    cfg_hashes = {root["cfg_hash"] for root in evidence["roots"]}
    simulator_hashes = {
        root["simulator_sha256"] for root in evidence["roots"]
    }
    measured = [row for row in observations if row["measured"]]
    expected_retained_counts = {
        key: sum(len(bundle[key]) for bundle in evidence["bundles"])
        for key in ("records", "metadata", "failures", "commands", "artifacts")
    }
    acceptance = {
        "required_cases_have_passing_runs": not missing_cases,
        "at_least_three_measured_repeats": all(
            run["repeats"] >= 3 for run in analyzed_runs
        ) and bool(analyzed_runs),
        "all_16_bank_phases_present": all(
            {
                row["phase_bytes"]
                for row in observations
                if row["measured"]
                and (row["N"], row["D"]) == case
                and row["scenario"] == "C3"
            }
            == set(runner.PHASES)
            for case in required_cases
        ) if not missing_cases else False,
        "warmups_retained_but_excluded_from_statistics": all(
            run["warmup_count"] == 18
            and run["measured_count"] == 18 * run["repeats"]
            for run in analyzed_runs
        ) and bool(analyzed_runs),
        "exact_target_fsm_pairing": all(
            run["target_fsm_pairs"] == runner.expected_smu_invocations(
                run["repeats"]
            )
            for run in analyzed_runs
        ) and bool(analyzed_runs),
        "no_reads_inside_core_window": all(
            row["status_reads_during_core"] == 0
            and row["counter_reads_inside_window"] == 0
            for row in observations
        ) and bool(observations),
        "all_analyzed_rows_pass_correctness": all(
            row["status"] == "pass"
            and row["merge_mismatches"] == 0
            and row["core_mismatches"] == 0
            for row in observations
        ) and bool(observations),
        "raw_overlap_not_clamped": all(
            Fraction(
                row["eta_overlap_numerator"],
                row["eta_overlap_denominator"],
            )
            == Fraction(
                row["T_smu"] + row["T_core"] - row["T_concurrent"],
                min(row["T_smu"], row["T_core"]),
            )
            for row in observations
        ) and bool(observations),
        "all_input_evidence_retained": all(
            len(retained[key]) == count
            for key, count in expected_retained_counts.items()
        ),
        "analysis_git_clean": not provenance["dirty"],
        "input_roots_git_clean": all(
            root["git_dirty"] is False for root in evidence["roots"]
        ),
        "analysis_commit_matches_inputs": input_commits == {provenance["commit"]},
        "input_cfg_identity_complete_and_consistent": (
            len(cfg_hashes) == 1 and None not in cfg_hashes
        ),
        "input_simulator_identity_complete_and_consistent": (
            len(simulator_hashes) == 1 and None not in simulator_hashes
        ),
    }
    return {
        "schema_version": 1,
        "objective": (
            "measure raw C1/C2/C3 overlap, bilateral slowdown, TCDM "
            "congestion, throughput, and all 16 bank phases"
        ),
        "measurement_semantics": {
            "T_smu": "paired C0_SMU OM_FSM busy_cycles at the same repeat",
            "T_core_C1": "same-repeat C0_REG core_cycles",
            "T_core_C2": "same-repeat C0_STREAM core_cycles",
            "T_core_C3": "same-phase/same-repeat C3_CORE core_cycles",
            "T_concurrent": "concurrent target total_cycles",
            "T_smu_concurrent": "exact paired concurrent OM_FSM busy_cycles",
            "T_core_concurrent": "concurrent target core_cycles",
            "eta_overlap": (
                "(T_smu + T_core - T_concurrent) / min(T_smu,T_core); "
                "raw and unclamped"
            ),
            "slowdown_smu": "T_smu_concurrent / T_smu",
            "slowdown_core": "T_core_concurrent / T_core",
            "congestion_ratio": "tcdm_congested / tcdm_accessed",
            "core_bytes_per_cycle": (
                "concurrent core bytes / T_core_concurrent"
            ),
            "smu_elements_per_cycle": (
                "N * D / T_smu_concurrent"
            ),
            "warmup": "repeat=-1 retained in observations, excluded from summaries",
            "phase_selection": (
                "best/worst by median T_concurrent; median is the closest "
                "observed phase to the median of 16 phase medians; ties "
                "choose lower T_concurrent then lower phase"
            ),
        },
        "known_limitations": [
            "Cycle and TCDM values are same-configuration RTL-simulation proxies.",
            "OM_FSM counters are simulation-only observation signals.",
            "No area, frequency, Fmax, power, energy, critical-path, or "
            "physical-efficiency claim is made.",
        ],
        "required_cases": [list(case) for case in required_cases],
        "missing_cases": missing_cases,
        "analyzed_runs": analyzed_runs,
        "skipped_runs": skipped_runs,
        "observations": observations,
        "scenario_summaries": scenario_summaries,
        "bank_phase_summaries": phase_summaries,
        "bank_phase_selection": phase_selections,
        "retained_input": retained,
        "input_evidence": {
            "roots": evidence["roots"],
        },
        "analysis_provenance": {
            "git": provenance,
            "tool_path": str(tool_path.resolve()),
            "tool_sha256": sha256_file(tool_path.resolve()),
            "python": sys.version.split()[0],
        },
        "acceptance_gates": acceptance,
        "all_acceptance_gates_pass": all(acceptance.values()),
        "measured_observation_count": len(measured),
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, Fraction):
        return fraction_json(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(json_ready(value), sort_keys=True, separators=(",", ":"))
    return value


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    fields = sorted({field for row in rows for field in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(value) for key, value in row.items()})


def flatten_summary(summary: dict[str, Any]) -> dict[str, Any]:
    row = {
        key: value
        for key, value in summary.items()
        if key not in {"medians", "eta_overlap_min", "eta_overlap_max"}
    }
    for field in ("eta_overlap_min", "eta_overlap_max"):
        value = summary[field]
        row[field] = value["decimal"]
        row[f"{field}_numerator"] = value["numerator"]
        row[f"{field}_denominator"] = value["denominator"]
    for field, value in summary["medians"].items():
        row[f"{field}_median"] = None if value is None else value["decimal"]
        row[f"{field}_median_numerator"] = (
            None if value is None else value["numerator"]
        )
        row[f"{field}_median_denominator"] = (
            None if value is None else value["denominator"]
        )
    return row


def write_outputs(output_dir: Path, report: dict[str, Any]) -> dict[str, str]:
    output_dir.mkdir(parents=False)
    analysis_path = output_dir / "analysis.json"
    observations_path = output_dir / "concurrency_observations.csv"
    summary_path = output_dir / "concurrency_summary.csv"
    phase_path = output_dir / "bank_phase_summary.csv"
    retained_path = output_dir / "retained_status_records.csv"
    analysis_path.write_text(
        json.dumps(
            json_ready(report), indent=2, sort_keys=True, allow_nan=False
        )
        + "\n",
        encoding="utf-8",
    )
    write_csv(observations_path, report["observations"])
    write_csv(
        summary_path,
        [flatten_summary(row) for row in report["scenario_summaries"]],
    )
    write_csv(
        phase_path,
        [flatten_summary(row) for row in report["bank_phase_summaries"]],
    )
    write_csv(retained_path, report["retained_input"]["records"])
    outputs = {
        path.name: sha256_file(path)
        for path in (
            analysis_path,
            observations_path,
            summary_path,
            phase_path,
            retained_path,
        )
    }
    manifest_path = output_dir / "artifact_manifest.json"
    manifest_path.write_text(
        json.dumps({
            "analysis_git_commit": report["analysis_provenance"]["git"]["commit"],
            "analysis_git_dirty": report["analysis_provenance"]["git"]["dirty"],
            "analysis_tool": {
                "path": report["analysis_provenance"]["tool_path"],
                "sha256": report["analysis_provenance"]["tool_sha256"],
                "python": report["analysis_provenance"]["python"],
            },
            "input_roots": report["input_evidence"]["roots"],
            "outputs": outputs,
        }, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    outputs[manifest_path.name] = sha256_file(manifest_path)
    return outputs


def validate_output_dir(output_dir: Path, repo_root: Path) -> Path:
    output = output_dir.resolve()
    repo = repo_root.resolve()
    try:
        output.relative_to(repo)
    except ValueError:
        pass
    else:
        raise AnalysisError("output directory must be outside the Git worktree")
    if not output.name.startswith("work-online-merge-"):
        raise AnalysisError(
            "output directory basename must start with work-online-merge-"
        )
    if output.exists():
        raise AnalysisError(f"output directory already exists: {output}")
    if not output.parent.is_dir():
        raise AnalysisError(f"output parent does not exist: {output.parent}")
    return output


def parse_coordinate(value: str) -> tuple[int, int]:
    try:
        n_text, d_text = value.split(",", maxsplit=1)
        coordinate = (int(n_text), int(d_text))
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError("expected N,D") from error
    if coordinate[0] <= 0 or coordinate[1] <= 0:
        raise argparse.ArgumentTypeError("N and D must be positive")
    return coordinate


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--result-root", type=Path, action="append", required=True
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--required-case",
        type=parse_coordinate,
        action="append",
        help="repeat as N,D; defaults to 16,64",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    required_cases = args.required_case or [(16, 64)]
    if len(set(required_cases)) != len(required_cases):
        raise AnalysisError("required cases must not repeat")
    output = validate_output_dir(args.output_dir, args.repo_root)
    report = analyze(
        args.repo_root,
        args.result_root,
        required_cases,
        Path(__file__),
    )
    outputs = write_outputs(output, report)
    print(json.dumps({
        "output_dir": str(output),
        "outputs": outputs,
        "all_acceptance_gates_pass": report["all_acceptance_gates_pass"],
    }, indent=2, sort_keys=True))
    return 0 if report["all_acceptance_gates_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
