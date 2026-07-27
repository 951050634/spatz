#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Analyze Full-SMU FSM cycles and the measured A0/A2 ablation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Sequence

FSM_PREFIX = "OM_FSM "
REQUIRED_CASES = ((1, 1), (8, 32), (16, 64))
IMPLEMENTATIONS = ("B2-R", "B3")
STATE_FIELDS = (
    "load_scalar_cycles",
    "compute_scalar_cycles",
    "compute_weight_cycles",
    "store_scalar_cycles",
    "update_vector_cycles",
)
SCALAR_STATE_FIELDS = STATE_FIELDS[:4]
EXPECTED_STATE_ENCODING = {
    "IDLE": 0,
    "LOAD_SCALAR": 1,
    "COMPUTE_SCALAR": 2,
    "COMPUTE_WEIGHT": 3,
    "STORE_SCALAR": 4,
    "UPDATE_VECTOR": 5,
    "DONE": 6,
    "ERROR": 7,
}
RTL_PATH = Path("hw/ip/online_merge/src/online_merge_update_engine.sv")
PROVENANCE_ONLY_RECORD_FIELDS = {"source_root", "git_commit"}
CORRECTNESS_FIELDS = (
    "max_abs",
    "max_rel",
    "rmse",
    "bit_equal_ratio",
)


class AnalysisError(ValueError):
    """Raised when the supplied evidence cannot support this analysis."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_coordinate(value: str) -> tuple[int, int]:
    try:
        n_text, d_text = value.split(",", maxsplit=1)
        coordinate = (int(n_text), int(d_text))
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError("expected N,D") from error
    if coordinate[0] <= 0 or coordinate[1] <= 0:
        raise argparse.ArgumentTypeError("N and D must be positive")
    return coordinate


def fraction_json(value: Fraction) -> dict[str, int | float]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal": float(value),
    }


def median_fraction(values: Iterable[int | float]) -> Fraction:
    converted = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AnalysisError(f"invalid median value: {value!r}")
        if isinstance(value, float) and not math.isfinite(value):
            raise AnalysisError(f"non-finite median value: {value!r}")
        converted.append(Fraction(str(value)))
    if not converted:
        raise AnalysisError("cannot take the median of an empty sequence")
    converted.sort()
    middle = len(converted) // 2
    if len(converted) % 2:
        return converted[middle]
    return (converted[middle - 1] + converted[middle]) / 2


def require_int(
    record: dict[str, Any], field: str, *, minimum: int = 0
) -> int:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise AnalysisError(f"{field} must be an integer, got {value!r}")
    if value < minimum:
        raise AnalysisError(f"{field} must be >= {minimum}, got {value}")
    return value


def require_finite_number(
    record: dict[str, Any],
    field: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    value = record.get(field)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise AnalysisError(
            f"{field} must be a finite number, got {value!r}"
        )
    converted = float(value)
    if minimum is not None and converted < minimum:
        raise AnalysisError(
            f"{field} must be >= {minimum}, got {converted}"
        )
    if maximum is not None and converted > maximum:
        raise AnalysisError(
            f"{field} must be <= {maximum}, got {converted}"
        )
    return converted


def parse_fsm_text(
    text: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    observations = []
    errors = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.startswith(FSM_PREFIX):
            continue
        payload = line[len(FSM_PREFIX) :]
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as error:
            errors.append({
                "kind": "malformed_fsm_json",
                "line_number": line_number,
                "message": str(error),
                "line": line[:512],
            })
            continue
        if not isinstance(decoded, dict):
            errors.append({
                "kind": "non_object_fsm_record",
                "line_number": line_number,
                "line": line[:512],
            })
            continue
        decoded["line_number"] = line_number
        observations.append(decoded)
    return observations, errors


def inspect_state_encoding(repo_root: Path) -> dict[str, Any]:
    path = (repo_root / RTL_PATH).resolve()
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"typedef\s+enum\s+logic\s*\[2:0\]\s*\{(.*?)\}\s*state_e\s*;",
        text,
        flags=re.DOTALL,
    )
    if match is None:
        raise AnalysisError(f"cannot locate state_e declaration in {path}")
    names = []
    for item in match.group(1).split(","):
        name = item.strip().split()[0]
        if name:
            names.append(name)
    encoding = {name: index for index, name in enumerate(names)}
    busy_expression = (
        "assign busy_o = (state_q != IDLE) && (state_q != DONE) && "
        "(state_q != ERROR);"
    )
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "state_width_bits": 3,
        "declaration_order_encoding": encoding,
        "expected_encoding": EXPECTED_STATE_ENCODING,
        "encoding_matches": encoding == EXPECTED_STATE_ENCODING,
        "busy_expression": busy_expression,
        "busy_expression_matches": busy_expression in text,
        "mutually_exclusive_enum": True,
    }


def validate_result_root(root: Path) -> None:
    if not root.is_dir():
        raise AnalysisError(f"result root is not a directory: {root}")
    required = (
        "run_manifest.json",
        "records.json",
        "failures.json",
        "commands.json",
    )
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        raise AnalysisError(f"result root {root} is missing {missing}")


def load_json(path: Path, expected_type: type) -> Any:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, expected_type):
        raise AnalysisError(
            f"{path} must contain {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )
    return value


def load_evidence(result_roots: Sequence[Path]) -> dict[str, Any]:
    if not result_roots:
        raise AnalysisError("at least one result root is required")
    roots = []
    records = []
    failures = []
    commands = []
    seen = set()
    for raw_root in result_roots:
        root = raw_root.resolve()
        if root in seen:
            raise AnalysisError(f"duplicate result root: {root}")
        seen.add(root)
        validate_result_root(root)
        manifest_path = root / "run_manifest.json"
        records_path = root / "records.json"
        failures_path = root / "failures.json"
        commands_path = root / "commands.json"
        manifest = load_json(manifest_path, dict)
        root_records = load_json(records_path, list)
        root_failures = load_json(failures_path, list)
        root_commands = load_json(commands_path, list)
        root_entry = {
            "root": str(root),
            "git_commit": manifest.get("git_commit"),
            "git_dirty": manifest.get("git_dirty"),
            "cfg_path": manifest.get("cfg_path"),
            "cfg_hash": manifest.get("cfg_hash"),
            "simulator_sha256": manifest.get("tool_versions", {})
            .get("simulator", {})
            .get("sha256"),
            "tool_versions": manifest.get("tool_versions"),
            "wall_clock_start_end": manifest.get("wall_clock_start_end"),
            "validation_result": manifest.get("validation_result"),
            "cases": manifest.get("cases"),
            "files": {
                "run_manifest.json": sha256_file(manifest_path),
                "records.json": sha256_file(records_path),
                "failures.json": sha256_file(failures_path),
                "commands.json": sha256_file(commands_path),
            },
        }
        roots.append(root_entry)
        for record in root_records:
            if not isinstance(record, dict):
                raise AnalysisError(f"non-object record in {records_path}")
            records.append({**record, "source_root": str(root)})
        for failure in root_failures:
            failures.append({"source_root": str(root), "failure": failure})
        for command in root_commands:
            if not isinstance(command, dict):
                raise AnalysisError(f"non-object command in {commands_path}")
            commands.append({**command, "source_root": str(root)})
    return {
        "roots": roots,
        "records": records,
        "failures": failures,
        "commands": commands,
    }


def equivalent_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in PROVENANCE_ONLY_RECORD_FIELDS
    }


def validated_pass_records(
    evidence: dict[str, Any], required_cases: Sequence[tuple[int, int]]
) -> tuple[
    dict[tuple[int, int, str, int], dict[str, Any]], dict[str, Any]
]:
    required = set(required_cases)
    candidates: dict[tuple[int, int, str, int], list[dict[str, Any]]]
    candidates = defaultdict(list)
    nonpass = []
    for record in evidence["records"]:
        if record.get("status") != "pass":
            nonpass.append(dict(record))
            continue
        coordinate = (record.get("N"), record.get("D"))
        if coordinate not in required:
            continue
        if record.get("implementation") not in IMPLEMENTATIONS:
            continue
        if record.get("seed") != 1 or record.get("case_kind") != "main":
            continue
        command_returncode = record.get("command_returncode")
        nonfinite = record.get("nonfinite")
        if (
            record.get("target_status") != "pass"
            or record.get("command_status") != "pass"
            or isinstance(command_returncode, bool)
            or command_returncode != 0
            or isinstance(nonfinite, bool)
            or nonfinite != 0
        ):
            raise AnalysisError(
                "passing required record has invalid command/correctness "
                f"fields: {record['source_root']} {coordinate}"
            )
        cycles = record.get("cycles")
        if isinstance(cycles, bool) or not isinstance(cycles, int):
            raise AnalysisError(
                f"invalid cycle count in {record['source_root']}"
            )
        if cycles <= 0:
            raise AnalysisError(f"nonpositive cycle count: {cycles}")
        repeat = record.get("repeat")
        if isinstance(repeat, bool) or not isinstance(repeat, int):
            raise AnalysisError(f"invalid repeat: {repeat!r}")
        if repeat < 0:
            raise AnalysisError(f"negative pass repeat: {repeat}")
        tcdm_accessed = require_int(record, "tcdm_accessed")
        tcdm_congested = require_int(record, "tcdm_congested")
        if tcdm_congested > tcdm_accessed:
            raise AnalysisError(
                "tcdm_congested exceeds tcdm_accessed in "
                f"{record['source_root']} {coordinate}"
            )
        for field in CORRECTNESS_FIELDS[:3]:
            require_finite_number(record, field, minimum=0.0)
        require_finite_number(
            record, "bit_equal_ratio", minimum=0.0, maximum=1.0
        )
        key = (
            int(record["N"]),
            int(record["D"]),
            str(record["implementation"]),
            repeat,
        )
        candidates[key].append(record)

    unique = {}
    duplicates = []
    for key in sorted(candidates):
        group = candidates[key]
        canonical = group[0]
        if any(
            equivalent_record(item) != equivalent_record(canonical)
            for item in group[1:]
        ):
            raise AnalysisError(f"conflicting passing records for {key}")
        unique[key] = canonical
        if len(group) > 1:
            duplicates.append({
                "key": list(key),
                "source_roots": sorted(item["source_root"] for item in group),
                "record_count": len(group),
            })
    return unique, {
        "nonpass_records": sorted(
            nonpass,
            key=lambda row: (
                str(row["source_root"]),
                str(row["implementation"]),
                str(row["N"]),
                str(row["D"]),
                str(row["repeat"]),
            ),
        ),
        "equivalent_duplicate_pass_records": duplicates,
    }


def case_slug(n: int, d: int, repeats: int) -> str:
    return f"N{n}_D{d}_S1_main_R{repeats}"


def find_case_root_and_repeats(
    records: dict[tuple[int, int, str, int], dict[str, Any]],
    coordinate: tuple[int, int],
) -> tuple[Path, list[int]]:
    repeat_sets = []
    roots = set()
    for implementation in IMPLEMENTATIONS:
        rows = [
            record
            for key, record in records.items()
            if key[:3] == (*coordinate, implementation)
        ]
        repeats = sorted(int(row["repeat"]) for row in rows)
        if len(repeats) < 3 or repeats != list(range(len(repeats))):
            raise AnalysisError(
                f"{coordinate} {implementation} needs at least three "
                f"contiguous repeats, got {repeats}"
            )
        repeat_sets.append(repeats)
        roots.update(row["source_root"] for row in rows)
    if repeat_sets[0] != repeat_sets[1]:
        raise AnalysisError(
            f"A0/A2 repeat mismatch at {coordinate}: {repeat_sets}"
        )
    if len(roots) != 1:
        raise AnalysisError(
            f"required case {coordinate} spans multiple roots: {roots}"
        )
    return Path(roots.pop()), repeat_sets[0]


def matching_simulator_command(
    evidence: dict[str, Any], root: Path, log_path: Path
) -> dict[str, Any]:
    matches = []
    for command in evidence["commands"]:
        if Path(command["source_root"]) != root:
            continue
        command_log = command.get("log_path")
        if not isinstance(command_log, str):
            continue
        if Path(command_log).resolve() == log_path.resolve():
            matches.append(command)
    if len(matches) != 1:
        raise AnalysisError(
            f"expected one simulator command for {log_path}, got {len(matches)}"
        )
    command = matches[0]
    if command.get("status") != "pass" or command.get("returncode") != 0:
        raise AnalysisError(f"simulator command did not pass: {command}")
    return command


def validate_observations(
    observations: Sequence[dict[str, Any]],
    coordinate: tuple[int, int],
    repeats: Sequence[int],
) -> list[dict[str, Any]]:
    expected_invocations = list(range(len(repeats) + 1))
    selected_observations = list(observations)
    if len(selected_observations) == 2 * len(expected_invocations):
        # A1 scalar-only runs immediately before B3 and emits its own FSM
        # records. The Full-SMU analysis consumes the trailing B3 sequence.
        selected_observations = selected_observations[
            len(expected_invocations):
        ]
        selected_observations = [
            {**record, "source_invocation": record.get("invocation"),
             "invocation": invocation}
            for invocation, record in enumerate(selected_observations)
        ]
    if len(selected_observations) != len(expected_invocations):
        raise AnalysisError(
            f"{coordinate} expected {len(expected_invocations)} FSM records, "
            f"got {len(observations)}"
        )
    by_invocation = {}
    for raw in selected_observations:
        record = dict(raw)
        if require_int(record, "schema_version") != 1:
            raise AnalysisError("unsupported FSM schema version")
        invocation = require_int(record, "invocation")
        if invocation in by_invocation:
            raise AnalysisError(f"duplicate FSM invocation {invocation}")
        if (
            require_int(record, "N", minimum=1) != coordinate[0]
            or require_int(record, "D", minimum=1) != coordinate[1]
        ):
            raise AnalysisError(
                f"FSM coordinate mismatch in invocation {invocation}"
            )
        if record.get("terminal_state") != "DONE":
            raise AnalysisError(
                f"FSM invocation {invocation} ended in "
                f"{record.get('terminal_state')!r}"
            )
        state_total = sum(
            require_int(record, field, minimum=1) for field in STATE_FIELDS
        )
        busy = require_int(record, "busy_cycles", minimum=1)
        if state_total != busy:
            raise AnalysisError(
                f"FSM invocation {invocation} state sum {state_total} "
                f"does not match busy {busy}"
            )
        record["state_sum_cycles"] = state_total
        record["scalar_cycles"] = sum(
            int(record[field]) for field in SCALAR_STATE_FIELDS
        )
        record["vector_cycles"] = int(record["update_vector_cycles"])
        by_invocation[invocation] = record
    if sorted(by_invocation) != expected_invocations:
        raise AnalysisError(
            f"FSM invocations are not contiguous: {sorted(by_invocation)}"
        )
    return [by_invocation[index] for index in expected_invocations]


def safe_ratio(
    numerator: int | float, denominator: int | float
) -> float | None:
    if denominator == 0:
        return None
    return float(numerator) / float(denominator)


def build_case_rows(
    coordinate: tuple[int, int],
    repeats: Sequence[int],
    records: dict[tuple[int, int, str, int], dict[str, Any]],
    observations: Sequence[dict[str, Any]],
    source_root: Path,
    log_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    observation_rows = []
    for invocation, observation in enumerate(observations):
        row = {
            "source_root": str(source_root),
            "simulator_log": str(log_path),
            "N": coordinate[0],
            "D": coordinate[1],
            "invocation": invocation,
            "phase": "warmup" if invocation == 0 else "measured",
            "repeat": None if invocation == 0 else invocation - 1,
            **observation,
        }
        row["scalar_share_of_busy"] = safe_ratio(
            row["scalar_cycles"], row["busy_cycles"]
        )
        row["vector_share_of_busy"] = safe_ratio(
            row["vector_cycles"], row["busy_cycles"]
        )
        observation_rows.append(row)

    measured_rows = []
    for repeat in repeats:
        a0 = records[(*coordinate, "B2-R", repeat)]
        a2 = records[(*coordinate, "B3", repeat)]
        fsm = observations[repeat + 1]
        a2_cycles = int(a2["cycles"])
        busy = int(fsm["busy_cycles"])
        if busy > a2_cycles:
            raise AnalysisError(
                f"{coordinate} repeat {repeat}: busy {busy} exceeds "
                f"A2 end-to-end {a2_cycles}"
            )
        other = a2_cycles - busy
        row = {
            "source_root": str(source_root),
            "simulator_log": str(log_path),
            "N": coordinate[0],
            "D": coordinate[1],
            "seed": 1,
            "case_kind": "main",
            "repeat": repeat,
            "A0_implementation": "B2-R",
            "A2_implementation": "B3",
            "A0_cycles": int(a0["cycles"]),
            "A2_end_to_end_cycles": a2_cycles,
            "A2_speedup_vs_A0": safe_ratio(a0["cycles"], a2_cycles),
            **{field: int(fsm[field]) for field in STATE_FIELDS},
            "scalar_cycles": int(fsm["scalar_cycles"]),
            "vector_cycles": int(fsm["vector_cycles"]),
            "busy_cycles": busy,
            "state_sum_cycles": int(fsm["state_sum_cycles"]),
            "command_setup_wait_error_nonoverlap_cycles": other,
            "scalar_share_of_busy": safe_ratio(
                fsm["scalar_cycles"], busy
            ),
            "vector_share_of_busy": safe_ratio(
                fsm["vector_cycles"], busy
            ),
            "nonoverlap_share_of_A2_end_to_end": safe_ratio(
                other, a2_cycles
            ),
            "A0_tcdm_accessed": int(a0["tcdm_accessed"]),
            "A0_tcdm_congested": int(a0["tcdm_congested"]),
            "A0_congestion_ratio": safe_ratio(
                a0["tcdm_congested"], a0["tcdm_accessed"]
            ),
            "A2_tcdm_accessed": int(a2["tcdm_accessed"]),
            "A2_tcdm_congested": int(a2["tcdm_congested"]),
            "A2_congestion_ratio": safe_ratio(
                a2["tcdm_congested"], a2["tcdm_accessed"]
            ),
            "A0_max_abs": a0.get("max_abs"),
            "A0_max_rel": a0.get("max_rel"),
            "A0_rmse": a0.get("rmse"),
            "A2_max_abs": a2.get("max_abs"),
            "A2_max_rel": a2.get("max_rel"),
            "A2_rmse": a2.get("rmse"),
            "A0_bit_equal_ratio": a0.get("bit_equal_ratio"),
            "A2_bit_equal_ratio": a2.get("bit_equal_ratio"),
            "A0_status": a0.get("status"),
            "A2_status": a2.get("status"),
        }
        if row["state_sum_cycles"] != row["busy_cycles"]:
            raise AnalysisError("internal FSM reconciliation failure")
        if (
            row["busy_cycles"]
            + row["command_setup_wait_error_nonoverlap_cycles"]
            != row["A2_end_to_end_cycles"]
        ):
            raise AnalysisError("internal end-to-end reconciliation failure")
        measured_rows.append(row)
    return observation_rows, measured_rows


def maximum_finite_metric(
    rows: Sequence[dict[str, Any]], field: str
) -> float:
    values = [
        require_finite_number(row, field, minimum=0.0) for row in rows
    ]
    if not values:
        raise AnalysisError(f"cannot summarize missing metric {field}")
    return max(values)


def summarize_case(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise AnalysisError("cannot summarize an empty case")
    integer_fields = (
        "A0_cycles",
        "A2_end_to_end_cycles",
        *STATE_FIELDS,
        "scalar_cycles",
        "vector_cycles",
        "busy_cycles",
        "command_setup_wait_error_nonoverlap_cycles",
        "A0_tcdm_accessed",
        "A0_tcdm_congested",
        "A2_tcdm_accessed",
        "A2_tcdm_congested",
    )
    medians = {
        field: median_fraction(row[field] for row in rows)
        for field in integer_fields
    }
    busy = medians["busy_cycles"]
    a2_cycles = medians["A2_end_to_end_cycles"]
    return {
        "N": rows[0]["N"],
        "D": rows[0]["D"],
        "measured_repeats": len(rows),
        "median_cycles": {
            field: fraction_json(value) for field, value in medians.items()
        },
        "A2_speedup_vs_A0_median_cycles": fraction_json(
            medians["A0_cycles"] / a2_cycles
        ),
        "scalar_share_of_busy_from_medians": fraction_json(
            medians["scalar_cycles"] / busy
        ),
        "vector_share_of_busy_from_medians": fraction_json(
            medians["vector_cycles"] / busy
        ),
        "nonoverlap_share_of_A2_end_to_end_from_medians": fraction_json(
            medians["command_setup_wait_error_nonoverlap_cycles"]
            / a2_cycles
        ),
        "A0_congestion_ratio_from_medians": (
            None
            if medians["A0_tcdm_accessed"] == 0
            else fraction_json(
                medians["A0_tcdm_congested"]
                / medians["A0_tcdm_accessed"]
            )
        ),
        "A2_congestion_ratio_from_medians": (
            None
            if medians["A2_tcdm_accessed"] == 0
            else fraction_json(
                medians["A2_tcdm_congested"]
                / medians["A2_tcdm_accessed"]
            )
        ),
        "maximum_correctness_metrics": {
            field: maximum_finite_metric(rows, field)
            for field in (
                "A0_max_abs",
                "A0_max_rel",
                "A0_rmse",
                "A2_max_abs",
                "A2_max_rel",
                "A2_rmse",
            )
        },
    }


def git_context(repo_root: Path) -> dict[str, Any]:
    def command(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), *args], text=True
        ).strip()

    return {
        "commit": command("rev-parse", "HEAD"),
        "dirty": bool(command("status", "--porcelain")),
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, Fraction):
        return fraction_json(value)
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def analyze(
    repo_root: Path,
    result_roots: Sequence[Path],
    required_cases: Sequence[tuple[int, int]],
    tool_path: Path,
) -> dict[str, Any]:
    repo = repo_root.resolve()
    evidence = load_evidence(result_roots)
    records, retained = validated_pass_records(evidence, required_cases)
    state_encoding = inspect_state_encoding(repo)
    observations = []
    measured_rows = []
    log_entries = []
    case_summaries = []
    parse_errors = []

    for coordinate in required_cases:
        root, repeats = find_case_root_and_repeats(records, coordinate)
        log_path = root / case_slug(*coordinate, len(repeats)) / "simulator.log"
        if not log_path.is_file():
            raise AnalysisError(f"missing simulator log: {log_path}")
        command = matching_simulator_command(evidence, root, log_path)
        raw_observations, errors = parse_fsm_text(
            log_path.read_text(encoding="utf-8", errors="replace")
        )
        parse_errors.extend(
            {"simulator_log": str(log_path), **error} for error in errors
        )
        validated = validate_observations(
            raw_observations, coordinate, repeats
        )
        case_observations, case_rows = build_case_rows(
            coordinate,
            repeats,
            records,
            validated,
            root,
            log_path,
        )
        observations.extend(case_observations)
        measured_rows.extend(case_rows)
        case_summaries.append(summarize_case(case_rows))
        log_entries.append({
            "N": coordinate[0],
            "D": coordinate[1],
            "path": str(log_path),
            "sha256": sha256_file(log_path),
            "command": command.get("command"),
            "command_start_utc": command.get("start_utc"),
            "command_end_utc": command.get("end_utc"),
            "observation_count": len(validated),
            "measured_repeat_count": len(repeats),
        })

    provenance = git_context(repo)
    input_commits = {root["git_commit"] for root in evidence["roots"]}
    cfg_hashes = {root["cfg_hash"] for root in evidence["roots"]}
    simulator_hashes = {
        root["simulator_sha256"] for root in evidence["roots"]
    }
    status_counts = Counter(
        str(record.get("status")) for record in evidence["records"]
    )
    expected_rows = sum(
        summary["measured_repeats"] for summary in case_summaries
    )
    acceptance = {
        "required_cases_complete": (
            {tuple((row["N"], row["D"])) for row in case_summaries}
            == set(required_cases)
        ),
        "at_least_three_measured_repeats_per_case": all(
            row["measured_repeats"] >= 3 for row in case_summaries
        ),
        "all_required_A0_A2_records_pass": all(
            row["A0_status"] == "pass" and row["A2_status"] == "pass"
            for row in measured_rows
        ),
        "all_fsm_invocations_terminate_done": all(
            row["terminal_state"] == "DONE" for row in observations
        ),
        "all_fsm_state_sums_match_busy": all(
            row["state_sum_cycles"] == row["busy_cycles"]
            for row in observations
        ),
        "all_A2_end_to_end_reconciles": all(
            row["busy_cycles"]
            + row["command_setup_wait_error_nonoverlap_cycles"]
            == row["A2_end_to_end_cycles"]
            for row in measured_rows
        ),
        "measured_row_count_matches_repeats": (
            len(measured_rows) == expected_rows
        ),
        "observer_records_parse_cleanly": not parse_errors,
        "state_enum_encoding_confirmed": (
            state_encoding["encoding_matches"]
            and state_encoding["busy_expression_matches"]
        ),
        "analysis_git_clean": not provenance["dirty"],
        "input_roots_git_clean": all(
            root["git_dirty"] is False for root in evidence["roots"]
        ),
        "analysis_commit_matches_inputs": (
            input_commits == {provenance["commit"]}
        ),
        "input_cfg_identity_complete_and_consistent": (
            len(cfg_hashes) == 1 and None not in cfg_hashes
        ),
        "input_simulator_identity_complete_and_consistent": (
            len(simulator_hashes) == 1 and None not in simulator_hashes
        ),
        "input_measurement_windows_recorded": all(
            root["wall_clock_start_end"] is not None
            for root in evidence["roots"]
        ),
        "input_validation_results_recorded": all(
            root["validation_result"] is not None
            for root in evidence["roots"]
        ),
    }
    return {
        "schema_version": 1,
        "objective": (
            "measure Full-SMU per-state cycles and compare measured A0/B2-R "
            "against A2/B3 at the mandatory ablation coordinates"
        ),
        "measurement_semantics": {
            "A0": "B2-R scalar merge plus RVV O[D] update",
            "A2": "Full SMU scalar and vector merge",
            "fsm_observer": (
                "simulation-only counters increment one mutually exclusive "
                "state_q enum state per cluster clock"
            ),
            "state_groups": {
                "scalar": list(SCALAR_STATE_FIELDS),
                "vector": ["update_vector_cycles"],
                "other": (
                    "A2 end-to-end minus accelerator busy; aggregate "
                    "non-overlapped command/setup/completion-wait/error "
                    "boundary overhead"
                ),
            },
            "overlap_statement": (
                "FSM state counts do not overlap because state_q is one "
                "mutually exclusive enum. The core's high-frequency MMIO "
                "completion polling runs concurrently with SMU busy, so "
                "polling work is not added to FSM cycles. Only the measured "
                "end-to-end remainder is reported as non-overlapped control "
                "overhead."
            ),
            "busy_reconciliation": (
                "sum(LOAD_SCALAR, COMPUTE_SCALAR, COMPUTE_WEIGHT, "
                "STORE_SCALAR, UPDATE_VECTOR) == busy_cycles"
            ),
            "end_to_end_reconciliation": (
                "busy_cycles + command_setup_wait_error_nonoverlap_cycles "
                "== A2_end_to_end_cycles"
            ),
            "physical_units_excluded": (
                "These are Verilator cycle and generic TCDM counter "
                "measurements, not physical PPA or energy data."
            ),
        },
        "analysis_provenance": {
            "git": provenance,
            "tool_path": str(tool_path.resolve()),
            "tool_sha256": sha256_file(tool_path.resolve()),
            "python": {
                "executable": sys.executable,
                "version": sys.version.split()[0],
            },
            "rtl_state_source": state_encoding,
        },
        "input_evidence": {
            "roots": evidence["roots"],
            "simulator_logs": log_entries,
            "record_status_counts": dict(sorted(status_counts.items())),
            "nonpass_records": retained["nonpass_records"],
            "failure_entries": evidence["failures"],
            "equivalent_duplicate_pass_records": (
                retained["equivalent_duplicate_pass_records"]
            ),
            "observer_parse_errors": parse_errors,
        },
        "required_cases": [
            {"N": coordinate[0], "D": coordinate[1]}
            for coordinate in required_cases
        ],
        "acceptance": acceptance,
        "fsm_observations": observations,
        "per_repeat": measured_rows,
        "case_summaries": case_summaries,
    }


def csv_value(value: Any) -> Any:
    if isinstance(value, Fraction):
        return float(value)
    if isinstance(value, dict) and set(value) >= {
        "numerator",
        "denominator",
        "decimal",
    }:
        return value["decimal"]
    if value is None:
        return ""
    return value


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        raise AnalysisError(f"cannot write empty CSV {path.name}")
    fields = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: csv_value(value) for key, value in row.items()
            })


def summary_csv_row(summary: dict[str, Any]) -> dict[str, Any]:
    medians = summary["median_cycles"]
    row = {
        "N": summary["N"],
        "D": summary["D"],
        "measured_repeats": summary["measured_repeats"],
    }
    for field, value in medians.items():
        row[f"{field}_median"] = value["decimal"]
    for field in (
        "A2_speedup_vs_A0_median_cycles",
        "scalar_share_of_busy_from_medians",
        "vector_share_of_busy_from_medians",
        "nonoverlap_share_of_A2_end_to_end_from_medians",
        "A0_congestion_ratio_from_medians",
        "A2_congestion_ratio_from_medians",
    ):
        value = summary[field]
        row[field] = "" if value is None else value["decimal"]
    row.update(summary["maximum_correctness_metrics"])
    return row


def write_outputs(output_dir: Path, report: dict[str, Any]) -> dict[str, str]:
    output_dir.mkdir(parents=False)
    analysis_path = output_dir / "analysis.json"
    observations_path = output_dir / "fsm_observations.csv"
    breakdown_path = output_dir / "fsm_breakdown.csv"
    ablation_path = output_dir / "ablation_a0_a2.csv"
    analysis_path.write_text(
        json.dumps(
            json_ready(report), indent=2, sort_keys=True, allow_nan=False
        )
        + "\n",
        encoding="utf-8",
    )
    write_csv(observations_path, report["fsm_observations"])
    write_csv(breakdown_path, report["per_repeat"])
    write_csv(
        ablation_path,
        [summary_csv_row(row) for row in report["case_summaries"]],
    )
    outputs = {
        path.name: sha256_file(path)
        for path in (
            analysis_path,
            observations_path,
            breakdown_path,
            ablation_path,
        )
    }
    manifest_path = output_dir / "artifact_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "analysis_git_commit": report["analysis_provenance"]["git"][
                    "commit"
                ],
                "analysis_git_dirty": report["analysis_provenance"]["git"][
                    "dirty"
                ],
                "analysis_tool": {
                    "path": report["analysis_provenance"]["tool_path"],
                    "sha256": report["analysis_provenance"]["tool_sha256"],
                    "python": report["analysis_provenance"]["python"],
                },
                "rtl_state_source": report["analysis_provenance"][
                    "rtl_state_source"
                ],
                "input_roots": report["input_evidence"]["roots"],
                "simulator_logs": report["input_evidence"][
                    "simulator_logs"
                ],
                "outputs": outputs,
            },
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
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
        help="repeat as N,D; defaults to the three mandatory points",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    required_cases = args.required_case or list(REQUIRED_CASES)
    if len(set(required_cases)) != len(required_cases):
        raise AnalysisError("required cases must not repeat")
    output = validate_output_dir(args.output_dir, args.repo_root)
    report = analyze(
        repo_root=args.repo_root,
        result_roots=args.result_root,
        required_cases=required_cases,
        tool_path=Path(__file__),
    )
    outputs = write_outputs(output, report)
    print(json.dumps({
        "output_dir": str(output),
        "outputs": outputs,
        "acceptance": report["acceptance"],
        "case_summaries": report["case_summaries"],
    }, indent=2, sort_keys=True, allow_nan=False))
    if not all(report["acceptance"].values()):
        raise AnalysisError(
            f"FSM analysis acceptance failed: {report['acceptance']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
