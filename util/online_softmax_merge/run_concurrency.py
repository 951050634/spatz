#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Build, run, validate, and preserve the core--SMU concurrency sweep."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import statistics
import struct
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import run_experiments as common

RECORD_PREFIX = "OM_CONCURRENCY "
META_PREFIX = "OM_CONCURRENCY_META "
FSM_PREFIX = "OM_FSM "
PASS_BANNER = "online-softmax-merge-concurrency PASS"
TARGET_NAME = "test-spatzBenchmarks-online-softmax-merge-concurrency"
REGISTER_SYMBOL = "online_merge_register_workload"
STREAM_SYMBOL = "online_merge_concurrency_stream"
UINT32_MAX = (1 << 32) - 1
PHASES = tuple(range(0, 128, 8))
STREAM_ELEMENTS = 2049
STREAM_ARRAY_BYTES = STREAM_ELEMENTS * 4
STREAM_SPACING_BYTES = 8320
STREAM_BYTES = STREAM_ELEMENTS * 8
STREAM_AVL_CAP = 8
STREAM_TAIL_ELEMENTS = 1
POLL_BACKOFF_ITERATIONS = 64
TCDM_CAPACITY_BYTES = 128 * 1024
TCDM_LIMIT_BYTES = TCDM_CAPACITY_BYTES * 7 // 10
ALLOCATION_ALIGNMENT_BYTES = 256
VALID_STATUSES = {
    "pass",
    "correctness_fail",
    "timeout",
    "capacity_skip",
    "unsupported",
    "tool_error",
}
TERMINAL_ACCEPTED = {"capacity_skip", "unsupported"}
SMU_SCENARIOS = {"C0_SMU", "C1", "C2", "C3"}
CORE_SCENARIOS = {"C0_REG", "C0_STREAM", "C3_CORE"}
ALL_SCENARIOS = SMU_SCENARIOS | CORE_SCENARIOS | {"ALL"}
REQUIRED_RECORD_FIELDS = {
    "schema_version",
    "scenario",
    "repeat",
    "N",
    "D",
    "phase_bytes",
    "relative_phase_bytes",
    "destination_relative_phase_bytes",
    "smu_bank_phase",
    "core_source_bank_phase",
    "core_destination_bank_phase",
    "smu_invocation",
    "total_cycles_hi",
    "total_cycles_lo",
    "core_cycles_hi",
    "core_cycles_lo",
    "tcdm_accessed",
    "tcdm_congested",
    "status_after_core",
    "status_reads",
    "busy_status_reads",
    "poll_backoff_calls",
    "poll_backoff_iterations",
    "poll_checksum",
    "core_checksum",
    "status_reads_during_core",
    "counter_reads_inside_window",
    "register_iterations",
    "core_elements",
    "core_bytes",
    "stream_array_bytes",
    "stream_tail_elements",
    "merge_checked",
    "merge_mismatches",
    "merge_max_abs_bits",
    "core_checked",
    "core_mismatches",
    "failure_index",
    "expected_bits",
    "actual_bits",
    "status",
}
REQUIRED_META_FIELDS = {
    "schema_version",
    "N",
    "D",
    "repeats",
    "phase_count",
    "phase_step_bytes",
    "phase_period_bytes",
    "smu_phase_base_offset",
    "stream_elements",
    "stream_array_bytes",
    "stream_bytes_per_workload",
    "stream_source_destination_spacing",
    "stream_avl_cap",
    "stream_tail_elements",
    "register_iterations",
    "register_target_cycles_hi",
    "register_target_cycles_lo",
    "poll_backoff_iterations",
    "poll_backoff_cycles_hi",
    "poll_backoff_cycles_lo",
    "max_status_reads",
    "merge_footprint_bytes",
    "merge_allocation_bytes",
    "stream_allocation_bytes",
    "tcdm_capacity_bytes",
}
REQUIRED_FSM_FIELDS = {
    "schema_version",
    "invocation",
    "N",
    "D",
    "terminal_state",
    "load_scalar_cycles",
    "compute_scalar_cycles",
    "compute_weight_cycles",
    "store_scalar_cycles",
    "update_vector_cycles",
    "busy_cycles",
}
FSM_STATE_FIELDS = (
    "load_scalar_cycles",
    "compute_scalar_cycles",
    "compute_weight_cycles",
    "store_scalar_cycles",
    "update_vector_cycles",
)


def uint64_from_words(high: Any, low: Any) -> int:
    return ((int(high) & UINT32_MAX) << 32) | (int(low) & UINT32_MAX)


def float_from_bits(value: Any) -> float:
    return struct.unpack("<f", struct.pack("<I", int(value) & UINT32_MAX))[0]


def integer_or(value: Any, default: int) -> int:
    """Return an integer without letting malformed target output escape."""
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def layout_bytes(n: int, d: int) -> dict[str, int]:
    merge_footprint = n * (32 + 16 * d)
    merge_allocation = align_up(
        merge_footprint, ALLOCATION_ALIGNMENT_BYTES
    )
    stream_allocation = (
        ALLOCATION_ALIGNMENT_BYTES
        + STREAM_SPACING_BYTES
        + STREAM_ARRAY_BYTES
    )
    return {
        "merge_footprint_bytes": merge_footprint,
        "merge_allocation_bytes": merge_allocation,
        "stream_allocation_bytes": stream_allocation,
        "combined_allocation_bytes": merge_allocation + stream_allocation,
        "working_set_limit_bytes": TCDM_LIMIT_BYTES,
    }


def capacity_fits(case: common.Case) -> bool:
    return (
        layout_bytes(case.n, case.d)["combined_allocation_bytes"]
        <= TCDM_LIMIT_BYTES
    )


def expected_scenario_counts(repeats: int) -> dict[str, int]:
    per_series = repeats + 1
    return {
        "C0_SMU": per_series,
        "C0_REG": per_series,
        "C0_STREAM": per_series,
        "C1": per_series,
        "C2": per_series,
        "C3_CORE": len(PHASES) * per_series,
        "C3": len(PHASES) * per_series,
    }


def expected_record_keys(repeats: int) -> set[tuple[str, int, int]]:
    repeats_with_warmup = range(-1, repeats)
    keys: set[tuple[str, int, int]] = set()
    for scenario in ("C0_SMU", "C0_REG", "C0_STREAM", "C1", "C2"):
        keys.update((scenario, 0, repeat) for repeat in repeats_with_warmup)
    for phase in PHASES:
        for scenario in ("C3_CORE", "C3"):
            keys.update(
                (scenario, phase, repeat)
                for repeat in repeats_with_warmup
            )
    return keys


def expected_smu_invocations(repeats: int) -> int:
    return (3 + len(PHASES)) * (repeats + 1)


def parse_prefixed_json(
    output: str,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    records: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    fsm_records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    prefixes = (
        (RECORD_PREFIX, "concurrency", records),
        (META_PREFIX, "metadata", metadata),
        (FSM_PREFIX, "fsm", fsm_records),
    )
    for line_number, line in enumerate(output.splitlines(), 1):
        for prefix, kind, destination in prefixes:
            if not line.startswith(prefix):
                continue
            payload = line[len(prefix) :]
            try:
                value = json.loads(payload)
            except json.JSONDecodeError as error:
                errors.append(
                    {
                        "kind": "malformed_structured_json",
                        "record_kind": kind,
                        "line_number": line_number,
                        "message": str(error),
                        "line": line[:512],
                    }
                )
                break
            if not isinstance(value, dict):
                errors.append(
                    {
                        "kind": "non_object_structured_record",
                        "record_kind": kind,
                        "line_number": line_number,
                        "line": line[:512],
                    }
                )
                break
            destination.append(value)
            break
    return records, metadata, fsm_records, errors


def enrich_record(record: dict[str, Any]) -> dict[str, Any]:
    result = dict(record)
    result["total_cycles"] = uint64_from_words(
        result.pop("total_cycles_hi"), result.pop("total_cycles_lo")
    )
    result["core_cycles"] = uint64_from_words(
        result.pop("core_cycles_hi"), result.pop("core_cycles_lo")
    )
    max_abs = float_from_bits(result.pop("merge_max_abs_bits"))
    result["merge_max_abs"] = max_abs if math.isfinite(max_abs) else None
    accessed = int(result.get("tcdm_accessed", 0))
    congested = int(result.get("tcdm_congested", 0))
    core_cycles = int(result.get("core_cycles", 0))
    core_bytes = int(result.get("core_bytes", 0))
    result["congestion_ratio"] = (
        congested / accessed if accessed > 0 else None
    )
    result["core_bytes_per_cycle"] = (
        core_bytes / core_cycles if core_cycles > 0 and core_bytes > 0 else None
    )
    result["measured"] = int(result.get("repeat", -1)) >= 0
    return result


def enrich_meta(meta: dict[str, Any]) -> dict[str, Any]:
    result = dict(meta)
    result["register_target_cycles"] = uint64_from_words(
        result.pop("register_target_cycles_hi"),
        result.pop("register_target_cycles_lo"),
    )
    result["poll_backoff_cycles"] = uint64_from_words(
        result.pop("poll_backoff_cycles_hi"),
        result.pop("poll_backoff_cycles_lo"),
    )
    return result


def synthetic_record(
    case: common.Case, status: str, reason: str
) -> dict[str, Any]:
    layout = layout_bytes(case.n, case.d)
    return {
        "schema_version": 1,
        "scenario": "ALL",
        "repeat": -1,
        "N": case.n,
        "D": case.d,
        "phase_bytes": UINT32_MAX,
        "relative_phase_bytes": UINT32_MAX,
        "destination_relative_phase_bytes": UINT32_MAX,
        "smu_bank_phase": UINT32_MAX,
        "core_source_bank_phase": UINT32_MAX,
        "core_destination_bank_phase": UINT32_MAX,
        "smu_invocation": -1,
        "total_cycles": None,
        "core_cycles": None,
        "tcdm_accessed": None,
        "tcdm_congested": None,
        "status_after_core": 0,
        "status_reads": 0,
        "busy_status_reads": 0,
        "poll_backoff_calls": 0,
        "poll_backoff_iterations": POLL_BACKOFF_ITERATIONS,
        "poll_checksum": 0,
        "core_checksum": 0,
        "status_reads_during_core": 0,
        "counter_reads_inside_window": 0,
        "register_iterations": 0,
        "core_elements": 0,
        "core_bytes": 0,
        "stream_array_bytes": 0,
        "stream_tail_elements": 0,
        "merge_checked": 0,
        "merge_mismatches": 0,
        "merge_max_abs": 0.0,
        "core_checked": 0,
        "core_mismatches": 0,
        "failure_index": 0,
        "expected_bits": 0,
        "actual_bits": 0,
        "status": status,
        "target_status": None,
        "failure_reason": reason,
        "congestion_ratio": None,
        "core_bytes_per_cycle": None,
        "measured": False,
        **layout,
    }


def _error(kind: str, message: str, **values: Any) -> dict[str, Any]:
    return {"kind": kind, "message": message, **values}


def validate_meta(meta: dict[str, Any], case: common.Case) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    missing = sorted(REQUIRED_META_FIELDS - meta.keys())
    if missing:
        errors.append(
            _error("invalid_metadata", f"missing fields: {', '.join(missing)}")
        )
        return errors
    expected = {
        "schema_version": 1,
        "N": case.n,
        "D": case.d,
        "repeats": case.repeats,
        "phase_count": len(PHASES),
        "phase_step_bytes": 8,
        "phase_period_bytes": 128,
        "stream_elements": STREAM_ELEMENTS,
        "stream_array_bytes": STREAM_ARRAY_BYTES,
        "stream_bytes_per_workload": STREAM_BYTES,
        "stream_source_destination_spacing": STREAM_SPACING_BYTES,
        "stream_avl_cap": STREAM_AVL_CAP,
        "stream_tail_elements": STREAM_TAIL_ELEMENTS,
        "poll_backoff_iterations": POLL_BACKOFF_ITERATIONS,
        "tcdm_capacity_bytes": TCDM_CAPACITY_BYTES,
    }
    expected.update(
        {
            key: value
            for key, value in layout_bytes(case.n, case.d).items()
            if key in {
                "merge_footprint_bytes",
                "merge_allocation_bytes",
                "stream_allocation_bytes",
            }
        }
    )
    for key, value in expected.items():
        if meta.get(key) != value:
            errors.append(
                _error(
                    "invalid_metadata",
                    f"{key} mismatch: got {meta.get(key)!r}, "
                    f"expected {value!r}",
                    field=key,
                )
            )
    for field in ("register_iterations", "max_status_reads"):
        try:
            value = int(meta[field])
        except (TypeError, ValueError, OverflowError):
            value = 0
        if value <= 0:
            errors.append(
                _error("invalid_metadata", f"{field} must be positive")
            )
    return errors


def validate_record(
    record: dict[str, Any], case: common.Case
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    missing = sorted(REQUIRED_RECORD_FIELDS - record.keys())
    if missing:
        return [
            _error(
                "invalid_target_record",
                f"missing fields: {', '.join(missing)}",
            )
        ]
    scenario = record.get("scenario")
    if scenario not in ALL_SCENARIOS:
        errors.append(
            _error(
                "invalid_target_record",
                f"unexpected scenario: {scenario!r}",
            )
        )
    if record.get("schema_version") != 1:
        errors.append(
            _error("invalid_target_record", "schema_version must be 1")
        )
    for key, expected in (("N", case.n), ("D", case.d)):
        if record.get(key) != expected:
            errors.append(
                _error(
                    "invalid_target_record",
                    f"{key} mismatch: got {record.get(key)!r}, "
                    f"expected {expected}",
                )
            )
    status = record.get("status")
    if status not in VALID_STATUSES:
        errors.append(
            _error("invalid_target_record", f"invalid status: {status!r}")
        )
    try:
        repeat = int(record.get("repeat"))
    except (TypeError, ValueError, OverflowError):
        errors.append(_error("invalid_target_record", "repeat is not integer"))
        repeat = -2
    if repeat < -1 or repeat >= case.repeats:
        errors.append(
            _error("invalid_target_record", f"repeat out of range: {repeat}")
        )
    for field in (
        "status_reads_during_core",
        "counter_reads_inside_window",
    ):
        if record.get(field) != 0:
            errors.append(
                _error(
                    "polling_window_violation",
                    f"{field} must be zero",
                    scenario=scenario,
                    repeat=repeat,
                )
            )
    if record.get("poll_backoff_iterations") != POLL_BACKOFF_ITERATIONS:
        errors.append(
            _error(
                "polling_protocol_violation",
                "unexpected poll backoff iteration count",
            )
        )
    if scenario == "ALL":
        return errors

    phase = integer_or(record.get("phase_bytes"), -1)
    if scenario in {"C3", "C3_CORE"}:
        if phase not in PHASES:
            errors.append(
                _error("invalid_phase", f"unexpected C3 phase: {phase}")
            )
    elif phase != 0:
        errors.append(
            _error(
                "invalid_phase",
                f"non-C3 scenario has phase {phase}, expected 0",
            )
        )

    has_stream = scenario in {"C0_STREAM", "C2", "C3_CORE", "C3"}
    has_register = scenario in {"C0_REG", "C1"}
    is_smu = scenario in SMU_SCENARIOS
    expected_relative = phase if has_stream else UINT32_MAX
    for field in (
        "relative_phase_bytes",
        "destination_relative_phase_bytes",
    ):
        if record.get(field) != expected_relative:
            errors.append(
                _error(
                    "invalid_phase",
                    f"{field} mismatch: got {record.get(field)!r}, "
                    f"expected {expected_relative}",
                )
            )
    if has_stream:
        for field, expected in (
            ("core_elements", STREAM_ELEMENTS),
            ("core_bytes", STREAM_BYTES),
            ("stream_array_bytes", STREAM_ARRAY_BYTES),
            ("stream_tail_elements", STREAM_TAIL_ELEMENTS),
        ):
            if record.get(field) != expected:
                errors.append(
                    _error(
                        "invalid_stream_shape",
                        f"{field} mismatch: got {record.get(field)!r}, "
                        f"expected {expected}",
                    )
                )
        try:
            bank_difference = (
                int(record["core_source_bank_phase"])
                - int(record["smu_bank_phase"])
            ) % 16
            destination_difference = (
                int(record["core_destination_bank_phase"])
                - int(record["smu_bank_phase"])
            ) % 16
        except (KeyError, TypeError, ValueError, OverflowError):
            bank_difference = destination_difference = -1
        expected_bank_difference = phase // 8
        if (
            bank_difference != expected_bank_difference
            or destination_difference != expected_bank_difference
        ):
            errors.append(
                _error(
                    "invalid_bank_phase",
                    "bank phase does not match relative byte phase",
                )
            )
    else:
        for field in (
            "core_elements",
            "core_bytes",
            "stream_array_bytes",
            "stream_tail_elements",
        ):
            if record.get(field) != 0:
                errors.append(
                    _error(
                        "invalid_stream_shape",
                        f"non-stream {field} must be zero",
                    )
                )
        for field in (
            "core_source_bank_phase",
            "core_destination_bank_phase",
        ):
            if record.get(field) != UINT32_MAX:
                errors.append(
                    _error(
                        "invalid_bank_phase",
                        f"non-stream {field} must be UINT32_MAX",
                    )
                )

    if has_register and integer_or(record.get("register_iterations"), 0) <= 0:
        errors.append(
            _error(
                "invalid_register_workload",
                "register_iterations must be positive",
            )
        )
    if not has_register and record.get("register_iterations") != 0:
        errors.append(
            _error(
                "invalid_register_workload",
                "non-register sample has register iterations",
            )
        )

    expected_merge_checked = case.n * (case.d + 2) if is_smu else 0
    if record.get("merge_checked") != expected_merge_checked:
        errors.append(
            _error(
                "invalid_correctness_count",
                "merge_checked mismatch",
                expected=expected_merge_checked,
                actual=record.get("merge_checked"),
            )
        )
    expected_core_checked = (
        STREAM_ELEMENTS if has_stream else 1 if has_register else 0
    )
    if record.get("core_checked") != expected_core_checked:
        errors.append(
            _error(
                "invalid_correctness_count",
                "core_checked mismatch",
                expected=expected_core_checked,
                actual=record.get("core_checked"),
            )
        )
    if status == "pass" and (
        record.get("merge_mismatches") != 0
        or record.get("core_mismatches") != 0
    ):
        errors.append(
            _error(
                "invalid_correctness_status",
                "pass record contains correctness mismatches",
            )
        )

    invocation = integer_or(record.get("smu_invocation"), -2)
    if is_smu and invocation < 0:
        errors.append(
            _error("invalid_smu_invocation", "SMU sample lacks invocation")
        )
    if not is_smu and invocation != -1:
        errors.append(
            _error(
                "invalid_smu_invocation",
                "core-only sample must use invocation -1",
            )
        )
    status_reads = integer_or(record.get("status_reads"), -1)
    poll_calls = integer_or(record.get("poll_backoff_calls"), -1)
    busy_reads = integer_or(record.get("busy_status_reads"), -1)
    if is_smu:
        if status_reads < 1 or poll_calls != status_reads - 1:
            errors.append(
                _error(
                    "polling_protocol_violation",
                    "SMU status_reads/poll_backoff_calls mismatch",
                )
            )
        if busy_reads < 0 or busy_reads > status_reads:
            errors.append(
                _error(
                    "polling_protocol_violation",
                    "busy_status_reads outside status read count",
                )
            )
    elif status_reads != 0 or poll_calls != 0 or busy_reads != 0:
        errors.append(
            _error(
                "polling_protocol_violation",
                "core-only sample unexpectedly polls status",
            )
        )
    return errors


def validate_fsm(
    fsm: dict[str, Any], case: common.Case
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    missing = sorted(REQUIRED_FSM_FIELDS - fsm.keys())
    if missing:
        return [
            _error("invalid_fsm_record", f"missing fields: {', '.join(missing)}")
        ]
    expected = {
        "schema_version": 1,
        "N": case.n,
        "D": case.d,
        "terminal_state": "DONE",
    }
    for key, value in expected.items():
        if fsm.get(key) != value:
            errors.append(
                _error(
                    "invalid_fsm_record",
                    f"{key} mismatch: got {fsm.get(key)!r}, "
                    f"expected {value!r}",
                )
            )
    try:
        state_sum = sum(int(fsm[field]) for field in FSM_STATE_FIELDS)
        busy = int(fsm["busy_cycles"])
    except (KeyError, TypeError, ValueError, OverflowError):
        errors.append(
            _error("invalid_fsm_record", "FSM cycle fields must be integers")
        )
    else:
        if state_sum != busy:
            errors.append(
                _error(
                    "invalid_fsm_record",
                    f"state sum {state_sum} != busy_cycles {busy}",
                )
            )
        if busy <= 0:
            errors.append(
                _error("invalid_fsm_record", "busy_cycles must be positive")
            )
    return errors


def validate_complete_schedule(
    records: Sequence[dict[str, Any]],
    metadata: Sequence[dict[str, Any]],
    fsm_records: Sequence[dict[str, Any]],
    case: common.Case,
    output: str,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if len(metadata) != 1:
        errors.append(
            _error(
                "metadata_count",
                f"expected one metadata record, got {len(metadata)}",
            )
        )
    else:
        errors.extend(validate_meta(metadata[0], case))

    keys: set[tuple[str, int, int]] = set()
    for index, record in enumerate(records):
        for error in validate_record(record, case):
            error.setdefault("record_index", index)
            errors.append(error)
        if record.get("scenario") == "ALL":
            continue
        try:
            key = (
                str(record["scenario"]),
                int(record["phase_bytes"]),
                int(record["repeat"]),
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if key in keys:
            errors.append(
                _error("duplicate_target_record", f"duplicate key {key!r}")
            )
        keys.add(key)
    expected_keys = expected_record_keys(case.repeats)
    if keys != expected_keys:
        errors.append(
            _error(
                "incomplete_schedule",
                "scenario/phase/repeat schedule is incomplete",
                missing=[list(key) for key in sorted(expected_keys - keys)],
                unexpected=[list(key) for key in sorted(keys - expected_keys)],
            )
        )
    nonterminal_records = [
        record for record in records if record.get("scenario") != "ALL"
    ]
    expected_count = sum(expected_scenario_counts(case.repeats).values())
    if len(nonterminal_records) != expected_count:
        errors.append(
            _error(
                "record_count",
                f"expected {expected_count} records, "
                f"got {len(nonterminal_records)}",
            )
        )
    if any(record.get("status") != "pass" for record in nonterminal_records):
        errors.append(
            _error("nonpassing_target_record", "full schedule has non-pass status")
        )

    invocations: dict[int, dict[str, Any]] = {}
    for index, fsm in enumerate(fsm_records):
        for error in validate_fsm(fsm, case):
            error.setdefault("fsm_record_index", index)
            errors.append(error)
        try:
            invocation = int(fsm["invocation"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if invocation in invocations:
            errors.append(
                _error(
                    "duplicate_fsm_invocation",
                    f"duplicate FSM invocation {invocation}",
                )
            )
        invocations[invocation] = fsm
    expected_invocations = set(range(expected_smu_invocations(case.repeats)))
    if set(invocations) != expected_invocations:
        errors.append(
            _error(
                "incomplete_fsm_schedule",
                "FSM invocation set is incomplete",
                missing=sorted(expected_invocations - set(invocations)),
                unexpected=sorted(set(invocations) - expected_invocations),
            )
        )
    smu_records = [
        record for record in nonterminal_records if record.get("scenario") in SMU_SCENARIOS
    ]
    target_invocations = [
        integer_or(record.get("smu_invocation"), -1)
        for record in smu_records
    ]
    if len(target_invocations) != len(set(target_invocations)):
        errors.append(
            _error("duplicate_smu_invocation", "duplicate target invocation")
        )
    if set(target_invocations) != expected_invocations:
        errors.append(
            _error(
                "incomplete_target_invocations",
                "target SMU invocation set is incomplete",
                missing=sorted(expected_invocations - set(target_invocations)),
                unexpected=sorted(set(target_invocations) - expected_invocations),
            )
        )
    if PASS_BANNER not in output.splitlines():
        errors.append(_error("missing_pass_banner", "PASS banner is missing"))

    measured_c0_smu = [
        uint64_from_words(record["total_cycles_hi"], record["total_cycles_lo"])
        for record in records
        if record.get("scenario") == "C0_SMU"
        and integer_or(record.get("repeat"), -1) >= 0
        and record.get("status") == "pass"
        and integer_or(record.get("total_cycles_hi"), -1) >= 0
        and integer_or(record.get("total_cycles_lo"), -1) >= 0
    ]
    measured_c0_reg = [
        uint64_from_words(record["core_cycles_hi"], record["core_cycles_lo"])
        for record in records
        if record.get("scenario") == "C0_REG"
        and integer_or(record.get("repeat"), -1) >= 0
        and record.get("status") == "pass"
        and integer_or(record.get("core_cycles_hi"), -1) >= 0
        and integer_or(record.get("core_cycles_lo"), -1) >= 0
    ]
    if measured_c0_smu and measured_c0_reg:
        ratio = statistics.median(measured_c0_reg) / statistics.median(
            measured_c0_smu
        )
        if not 0.8 <= ratio <= 1.2:
            errors.append(
                _error(
                    "register_calibration",
                    f"C0 register/SMU median ratio {ratio:.6f} outside "
                    "[0.8, 1.2]",
                )
            )
    return errors


def validate_terminal_schedule(
    records: Sequence[dict[str, Any]],
    case: common.Case,
    status: str,
) -> list[dict[str, Any]]:
    """Validate an explicit whole-run capacity/unsupported target result."""
    errors: list[dict[str, Any]] = []
    if len(records) != 1:
        errors.append(
            _error(
                "terminal_record_count",
                f"expected one {status} terminal record, got {len(records)}",
            )
        )
    for index, record in enumerate(records):
        for error in validate_record(record, case):
            error.setdefault("record_index", index)
            errors.append(error)
        if record.get("scenario") != "ALL" or record.get("status") != status:
            errors.append(
                _error(
                    "invalid_terminal_record",
                    "terminal record must use scenario ALL and matching status",
                    record_index=index,
                )
            )
    return errors


def terminal_status(records: Sequence[dict[str, Any]]) -> str | None:
    statuses = {str(record.get("status")) for record in records}
    for status in ("timeout", "tool_error", "correctness_fail"):
        if status in statuses:
            return status
    terminal_records = [
        record for record in records if record.get("scenario") == "ALL"
    ]
    for status in ("capacity_skip", "unsupported"):
        if any(record.get("status") == status for record in terminal_records):
            return status
    return None


def normalize_run(
    raw_records: list[dict[str, Any]],
    raw_metadata: list[dict[str, Any]],
    raw_fsm: list[dict[str, Any]],
    case: common.Case,
    command: common.CommandRecord,
    output: str,
    parse_errors: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    errors = list(parse_errors)
    target_terminal = terminal_status(raw_records)
    if target_terminal in TERMINAL_ACCEPTED:
        errors.extend(validate_terminal_schedule(raw_records, case, target_terminal))
        if raw_metadata:
            errors.append(
                _error(
                    "terminal_metadata",
                    "terminal capacity/unsupported run must not emit metadata",
                )
            )
        if raw_fsm:
            errors.append(
                _error(
                    "terminal_fsm_records",
                    "terminal capacity/unsupported run must not emit FSM records",
                )
            )
    else:
        errors.extend(
            validate_complete_schedule(
                raw_records, raw_metadata, raw_fsm, case, output
            )
        )

    enriched_records: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_records):
        try:
            record = enrich_record(raw)
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            errors.append(
                _error(
                    "record_enrichment_error",
                    str(error),
                    record_index=index,
                )
            )
            continue
        record["target_status"] = record.get("status")
        record["command_status"] = command.status
        record["command_returncode"] = command.returncode
        enriched_records.append(record)

    final_status: str | None = None
    reason: str | None = None
    if command.status == "timeout":
        final_status = "timeout"
        reason = (
            f"host wall-clock timeout after {command.timeout_seconds} seconds"
        )
    elif command.status == "tool_error":
        final_status = "tool_error"
        reason = f"simulator return code {command.returncode}"
    elif target_terminal in TERMINAL_ACCEPTED and errors:
        final_status = "tool_error"
        reason = "target terminal status failed validation"
    elif target_terminal is not None:
        final_status = target_terminal
        reason = "target emitted terminal status"
    elif errors:
        final_status = "tool_error"
        reason = "structured output failed completeness or validation gates"

    if final_status is not None and final_status != "pass":
        for record in enriched_records:
            record["status"] = final_status
            record.setdefault("failure_reason", reason)

    terminal_accepted = final_status in TERMINAL_ACCEPTED
    if final_status is not None and not terminal_accepted:
        if not any(record.get("scenario") == "ALL" for record in enriched_records):
            synthetic = synthetic_record(case, final_status, reason or final_status)
            synthetic["command_status"] = command.status
            synthetic["command_returncode"] = command.returncode
            enriched_records.append(synthetic)
    if not enriched_records:
        status = final_status or "tool_error"
        enriched_records.append(
            synthetic_record(case, status, reason or "no target records")
        )

    enriched_meta: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_metadata):
        try:
            enriched_meta.append(enrich_meta(raw))
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            errors.append(
                _error(
                    "metadata_enrichment_error",
                    str(error),
                    metadata_index=index,
                )
            )
    enriched_fsm = [dict(record) for record in raw_fsm]
    return enriched_records, enriched_meta, enriched_fsm, errors


def extract_symbol(disassembly: str, symbol: str) -> str | None:
    return common.extract_symbol_disassembly(disassembly, symbol)


def instruction_mnemonics(disassembly: str) -> list[str]:
    pattern = re.compile(
        r"^\s*[0-9a-fA-F]+:\s+(?:[0-9a-fA-F]{2,16}\s+)*"
        r"([A-Za-z0-9_.]+)"
    )
    result = []
    for line in disassembly.splitlines():
        match = pattern.match(line)
        if match:
            result.append(match.group(1).lower())
    return result


def has_local_backedge(disassembly: str) -> bool:
    instruction = re.compile(
        r"^\s*([0-9a-fA-F]+):\s+(?:[0-9a-fA-F]{2,16}\s+)*"
        r"([A-Za-z0-9_.]+)(?:\s+(.*))?$"
    )
    parsed: list[tuple[int, str, str]] = []
    for line in disassembly.splitlines():
        match = instruction.match(line)
        if match:
            parsed.append(
                (
                    int(match.group(1), 16),
                    match.group(2).lower(),
                    match.group(3) or "",
                )
            )
    if not parsed:
        return False
    first = min(address for address, _, _ in parsed)
    last = max(address for address, _, _ in parsed)
    target_pattern = re.compile(r"(?:0x)?([0-9a-fA-F]+)\s*<")
    for address, mnemonic, operands in parsed:
        if not (mnemonic.startswith("b") or mnemonic.startswith("j")):
            continue
        for target in target_pattern.findall(operands):
            target_address = int(target, 16)
            if first <= target_address < address <= last:
                return True
    return False


def is_memory_mnemonic(mnemonic: str) -> bool:
    scalar = {
        "lb",
        "lbu",
        "lh",
        "lhu",
        "lw",
        "lwu",
        "ld",
        "sb",
        "sh",
        "sw",
        "sd",
        "flh",
        "flw",
        "fld",
        "flq",
        "fsh",
        "fsw",
        "fsd",
        "fsq",
    }
    return mnemonic in scalar or mnemonic.startswith(("vl", "vs"))


def inspect_concurrency_disassembly(
    disassembly: str,
) -> tuple[dict[str, str], list[str]]:
    snippets: dict[str, str] = {}
    errors: list[str] = []
    register = extract_symbol(disassembly, REGISTER_SYMBOL)
    stream = extract_symbol(disassembly, STREAM_SYMBOL)
    if register is None:
        errors.append(f"missing symbol {REGISTER_SYMBOL}")
    else:
        snippets[REGISTER_SYMBOL] = register
        mnemonics = instruction_mnemonics(register)
        memory = sorted({item for item in mnemonics if is_memory_mnemonic(item)})
        if memory:
            errors.append(
                f"{REGISTER_SYMBOL} contains memory instructions: "
                + ", ".join(memory)
            )
        if re.search(r"\bsp\b", register):
            errors.append(f"{REGISTER_SYMBOL} references stack pointer")
        if not has_local_backedge(register):
            errors.append(f"{REGISTER_SYMBOL} lacks loop back-edge")
        if "<unknown>" in register:
            errors.append(f"{REGISTER_SYMBOL} contains undecoded instructions")
    if stream is None:
        errors.append(f"missing symbol {STREAM_SYMBOL}")
    else:
        snippets[STREAM_SYMBOL] = stream
        for mnemonic in ("vsetvli", "vle32.v", "vse32.v"):
            if mnemonic not in stream:
                errors.append(f"{STREAM_SYMBOL} lacks {mnemonic}")
        if not has_local_backedge(stream):
            errors.append(f"{STREAM_SYMBOL} lacks strip-mining back-edge")
        if "<unknown>" in stream:
            errors.append(f"{STREAM_SYMBOL} contains undecoded instructions")
    return snippets, errors


def objdump_argv(objdump: Path, elf: Path) -> list[str]:
    argv = [str(objdump), "-d", "--no-show-raw-insn"]
    if "llvm-objdump" in objdump.name:
        argv.append("--mattr=+v")
    argv.append(str(elf))
    return argv


def run_disassembly_gate(
    objdump: Path,
    elf: Path,
    output_dir: Path,
    timeout_seconds: int,
) -> tuple[common.CommandRecord, list[str], list[Path]]:
    log = output_dir / "concurrency_objdump.log"
    command, output = common.run_command(
        objdump_argv(objdump, elf), log, timeout_seconds, output_dir
    )
    snippets, errors = inspect_concurrency_disassembly(output)
    if command.status != "pass":
        errors.insert(0, f"objdump command status={command.status}")
    paths = [log]
    for symbol, snippet in snippets.items():
        path = output_dir / f"{symbol}.disasm"
        path.write_text(snippet, encoding="utf-8")
        paths.append(path)
    status = "pass" if not errors else "tool_error"
    summary = {
        "schema_version": 1,
        "status": status,
        "symbols": sorted(snippets),
        "errors": errors,
    }
    summary_path = output_dir / "disassembly_gate.json"
    common.write_json(summary_path, summary)
    paths.append(summary_path)
    return command, errors, paths


def csv_fields(records: Sequence[dict[str, Any]]) -> list[str]:
    preferred = [
        "git_commit",
        "git_dirty",
        "cfg_path",
        "cfg_hash",
        "scenario",
        "phase_bytes",
        "repeat",
        "measured",
        "N",
        "D",
        "smu_invocation",
        "total_cycles",
        "core_cycles",
        "tcdm_accessed",
        "tcdm_congested",
        "congestion_ratio",
        "core_elements",
        "core_bytes",
        "core_bytes_per_cycle",
        "status_reads",
        "busy_status_reads",
        "poll_backoff_calls",
        "merge_checked",
        "merge_mismatches",
        "merge_max_abs",
        "core_checked",
        "core_mismatches",
        "target_status",
        "command_status",
        "command_returncode",
        "status",
        "failure_reason",
    ]
    keys = {key for record in records for key in record}
    return [key for key in preferred if key in keys] + sorted(
        keys - set(preferred)
    )


def write_csv(path: Path, records: Sequence[dict[str, Any]]) -> None:
    fields = csv_fields(records)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    key: (
                        json.dumps(value, sort_keys=True)
                        if isinstance(value, (dict, list))
                        else value
                    )
                    for key, value in record.items()
                }
            )


def add_metadata(
    values: Iterable[dict[str, Any]], metadata: dict[str, Any]
) -> None:
    for value in values:
        for key, item in metadata.items():
            value.setdefault(key, item)


def persist(
    root: Path,
    records: Sequence[dict[str, Any]],
    metadata: Sequence[dict[str, Any]],
    fsm_records: Sequence[dict[str, Any]],
    failures: Sequence[dict[str, Any]],
    commands: Sequence[dict[str, Any]],
    artifacts: Sequence[dict[str, Any]],
) -> None:
    common.write_json(root / "concurrency_records.json", list(records))
    write_csv(root / "concurrency_records.csv", records)
    common.write_json(root / "concurrency_metadata.json", list(metadata))
    common.write_json(root / "fsm_records.json", list(fsm_records))
    write_csv(root / "fsm_records.csv", fsm_records)
    common.write_json(root / "failures.json", list(failures))
    common.write_json(root / "commands.json", list(commands))
    common.write_json(root / "artifact_manifest.json", list(artifacts))


def git_context(path: Path) -> dict[str, Any]:
    try:
        commit = common.git_output(path, "rev-parse", "HEAD")
        dirty = bool(common.git_output(path, "status", "--porcelain"))
    except Exception as error:  # pragma: no cover - platform failure detail
        return {"path": str(path), "status": "tool_error", "detail": str(error)}
    return {
        "path": str(path),
        "status": "pass",
        "commit": commit,
        "dirty": dirty,
    }


def validate_output_root(root: Path, repo_root: Path) -> None:
    common.validate_work_dir(root, repo_root)
    if root.exists() and any(root.iterdir()):
        raise ValueError("work-dir must not already contain files")


def make_case(args: argparse.Namespace) -> common.Case:
    case = common.Case(
        n=args.n,
        d=args.d,
        seed=args.seed,
        case_kind=args.case_kind,
        repeats=args.repeats,
        timeout_seconds=args.timeout_seconds,
    )
    common.validate_case(case)
    return case


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_root = script.parents[2]
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    system_objdump = Path(
        shutil.which("riscv64-unknown-elf-objdump")
        or default_root / "install/llvm/bin/llvm-objdump"
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=default_root / "hw/system/spatz_cluster/sw",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=default_root / "hw/system/spatz_cluster/sw/build",
    )
    parser.add_argument(
        "--simulator",
        type=Path,
        default=default_root / "hw/system/spatz_cluster/bin/spatz_cluster.vlt",
    )
    parser.add_argument("--simulator-source-dir", type=Path)
    parser.add_argument(
        "--simulator-arg",
        action="append",
        default=[],
        help="argument placed before the target ELF; repeat as needed",
    )
    parser.add_argument(
        "--cfg",
        type=Path,
        default=(
            default_root
            / "hw/system/spatz_cluster/cfg/spatz_cluster.default.dram.hjson"
        ),
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=default_root.parent
        / f"work-online-merge-concurrency-{timestamp}",
    )
    parser.add_argument("--n", type=int, default=16)
    parser.add_argument("--d", type=int, default=64)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--case-kind", default="main")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--configure-timeout-seconds", type=int, default=900)
    parser.add_argument("--build-timeout-seconds", type=int, default=900)
    parser.add_argument("--disassembly-timeout-seconds", type=int, default=120)
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument(
        "--cmake-define",
        action="append",
        default=[],
        metavar="KEY=VALUE",
    )
    parser.add_argument("--objdump", type=Path, default=system_objdump)
    parser.add_argument("--build-target", default=TARGET_NAME)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--no-configure", action="store_true")
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--require-clean", action="store_true")
    return parser.parse_args(argv)


def validate_options(args: argparse.Namespace) -> None:
    for field in (
        "timeout_seconds",
        "configure_timeout_seconds",
        "build_timeout_seconds",
        "disassembly_timeout_seconds",
        "jobs",
    ):
        if int(getattr(args, field)) <= 0:
            raise ValueError(f"{field.replace('_', '-')} must be positive")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    source_dir = args.source_dir.resolve()
    build_dir = args.build_dir.resolve()
    simulator = args.simulator.resolve()
    cfg = args.cfg.resolve()
    objdump = args.objdump.resolve()
    work_dir = args.work_dir.resolve()
    simulator_source = (
        args.simulator_source_dir.resolve()
        if args.simulator_source_dir is not None
        else repo_root
    )
    try:
        validate_options(args)
        case = make_case(args)
        cmake_defines = common.parse_cmake_defines(args.cmake_define)
        validate_output_root(work_dir, repo_root)
    except (ValueError, argparse.ArgumentTypeError) as error:
        raise SystemExit(f"invalid concurrency request: {error}") from error
    if not cfg.is_file():
        raise SystemExit(f"CFG does not exist: {cfg}")
    work_dir.mkdir(parents=True, exist_ok=True)

    git_commit = common.git_output(repo_root, "rev-parse", "HEAD")
    git_dirty = bool(common.git_output(repo_root, "status", "--porcelain"))
    if args.require_clean and git_dirty:
        raise SystemExit("formal concurrency run requires a clean worktree")
    cfg_hash = common.sha256_file(cfg)
    tool_versions = common.detect_tool_versions(
        repo_root, simulator, build_dir, args.cmake, objdump
    )
    tool_version = json.dumps(
        tool_versions, sort_keys=True, separators=(",", ":")
    )
    common_metadata = {
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "cfg_path": common.display_path(cfg, repo_root),
        "cfg_hash": cfg_hash,
        "tool_version": tool_version,
    }
    simulator_context = git_context(simulator_source)

    records: list[dict[str, Any]] = []
    target_metadata: list[dict[str, Any]] = []
    fsm_records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    layout = layout_bytes(case.n, case.d)

    artifacts.append(
        common.artifact_entry(
            cfg,
            repo_root,
            git_commit,
            cfg_hash,
            tool_version,
            case.slug,
            "fixed cluster configuration",
        )
    )
    if simulator.is_file():
        artifacts.append(
            common.artifact_entry(
                simulator,
                repo_root,
                git_commit,
                cfg_hash,
                tool_version,
                case.slug,
                "exact Verilator simulator executable",
            )
        )

    early_status: str | None = None
    early_reason: str | None = None
    if not capacity_fits(case):
        early_status = "capacity_skip"
        early_reason = (
            "combined merge and stream allocation exceeds 70% TCDM limit"
        )
    elif case.case_kind == "both-zero-l":
        early_status = "unsupported"
        early_reason = "case kind is outside the supported scalar domain"
    elif not simulator.is_file():
        early_status = "tool_error"
        early_reason = f"simulator does not exist: {simulator}"
    elif args.require_clean and simulator_context.get("dirty"):
        early_status = "tool_error"
        early_reason = "simulator source tree is dirty"

    elf = build_dir / f"spatzBenchmarks/{TARGET_NAME}"
    if early_status is None:
        status = "pass"
        if not args.no_configure:
            configure = common.make_configure_argv(
                args.cmake,
                source_dir,
                build_dir,
                case,
                cmake_defines,
            )
            command, _ = common.run_command(
                configure,
                work_dir / "configure.log",
                args.configure_timeout_seconds,
                repo_root,
            )
            commands.append(asdict(command))
            artifacts.append(
                common.artifact_entry(
                    work_dir / "configure.log",
                    repo_root,
                    git_commit,
                    cfg_hash,
                    tool_version,
                    case.slug,
                    "host CMake configuration",
                )
            )
            status = command.status
            if status != "pass":
                early_reason = f"configure command status={status}"
        if status == "pass" and not args.no_build:
            command, _ = common.run_command(
                [
                    args.cmake,
                    "--build",
                    str(build_dir),
                    "--target",
                    args.build_target,
                    "--parallel",
                    str(args.jobs),
                ],
                work_dir / "build.log",
                args.build_timeout_seconds,
                repo_root,
            )
            commands.append(asdict(command))
            artifacts.append(
                common.artifact_entry(
                    work_dir / "build.log",
                    repo_root,
                    git_commit,
                    cfg_hash,
                    tool_version,
                    case.slug,
                    "host target build",
                )
            )
            status = command.status
            if status != "pass":
                early_reason = f"build command status={status}"
        if status != "pass":
            early_status = status

    exact_elf = work_dir / "online-softmax-merge-concurrency.elf"
    if early_status is None:
        if not elf.is_file():
            early_status = "tool_error"
            early_reason = f"target ELF does not exist: {elf}"
        else:
            shutil.copy2(elf, exact_elf)
            artifacts.append(
                common.artifact_entry(
                    exact_elf,
                    repo_root,
                    git_commit,
                    cfg_hash,
                    tool_version,
                    case.slug,
                    "exact target ELF executed",
                )
            )

    if early_status is None:
        command, gate_errors, paths = run_disassembly_gate(
            objdump,
            exact_elf,
            work_dir,
            args.disassembly_timeout_seconds,
        )
        commands.append(asdict(command))
        for path in paths:
            artifacts.append(
                common.artifact_entry(
                    path,
                    repo_root,
                    git_commit,
                    cfg_hash,
                    tool_version,
                    case.slug,
                    "register-only and RVV stream disassembly gate",
                )
        )
        if gate_errors:
            early_status = (
                "timeout" if command.status == "timeout" else "tool_error"
            )
            early_reason = "; ".join(gate_errors)
            failures.append(
                _error(
                    "disassembly_gate",
                    early_reason,
                    status=early_status,
                )
            )

    if early_status is not None:
        reason = early_reason or early_status
        failures.append(
            _error(
                "early_terminal_status",
                reason,
                status=early_status,
            )
        )
        records = [synthetic_record(case, early_status, reason)]
    else:
        logs_dir = work_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        simulator_argv = [
            str(simulator),
            *args.simulator_arg,
            str(exact_elf),
        ]
        command, output = common.run_command(
            simulator_argv,
            work_dir / "simulator.log",
            args.timeout_seconds,
            work_dir,
        )
        commands.append(asdict(command))
        artifacts.append(
            common.artifact_entry(
                work_dir / "simulator.log",
                repo_root,
                git_commit,
                cfg_hash,
                tool_version,
                case.slug,
                "target mcycle windows plus simulation-only OM_FSM observer",
            )
        )
        artifacts.extend(
            common.generated_simulator_artifacts(
                work_dir,
                repo_root,
                git_commit,
                cfg_hash,
                tool_version,
                case.slug,
            )
        )
        raw_records, raw_meta, raw_fsm, parse_errors = parse_prefixed_json(
            output
        )
        records, target_metadata, fsm_records, validation_errors = normalize_run(
            raw_records,
            raw_meta,
            raw_fsm,
            case,
            command,
            output,
            parse_errors,
        )
        failures.extend(validation_errors)

    add_metadata(records, common_metadata)
    add_metadata(target_metadata, common_metadata)
    add_metadata(fsm_records, common_metadata)
    add_metadata(failures, common_metadata)
    persist(
        work_dir,
        records,
        target_metadata,
        fsm_records,
        failures,
        commands,
        artifacts,
    )

    statuses = sorted({str(record.get("status")) for record in records})
    manifest = {
        "schema_version": 1,
        **common_metadata,
        "objective": (
            "C0/C1/C2/C3 core--SMU overlap, TCDM contention, and all "
            "16 relative addr[6:3] phases"
        ),
        "case": asdict(case),
        "layout": layout,
        "expected_schedule": {
            "scenario_counts": expected_scenario_counts(case.repeats),
            "record_count": sum(
                expected_scenario_counts(case.repeats).values()
            ),
            "smu_invocation_count": expected_smu_invocations(case.repeats),
            "phases_bytes": list(PHASES),
        },
        "cmake_definitions": common.cmake_define_manifest(cmake_defines),
        "simulator_arguments": list(args.simulator_arg),
        "simulator_source": simulator_context,
        "tool_versions": tool_versions,
        "wall_clock_start_end": {
            "first_command_start": commands[0]["start_utc"] if commands else None,
            "last_command_end": commands[-1]["end_utc"] if commands else None,
        },
        "measurement_protocol": {
            "warmup_repeat": -1,
            "measured_repeats": list(range(case.repeats)),
            "status_reads_during_core": 0,
            "counter_reads_inside_window": 0,
            "poll_backoff_iterations": POLL_BACKOFF_ITERATIONS,
            "smu_duration_source": "simulation-only OM_FSM busy_cycles",
            "total_and_core_duration_source": "target 64-bit mcycle",
            "tcdm_counter_window": "start before launch/work; stop after completion",
        },
        "validation_result": {
            "statuses": statuses,
            "record_count": len(records),
            "metadata_count": len(target_metadata),
            "fsm_record_count": len(fsm_records),
            "failure_count": len(failures),
        },
        "known_limitations": [
            "Verilator cycles are a same-configuration runtime proxy.",
            "OM_FSM counters are simulation-only and do not feed functional RTL.",
            "No physical area, frequency, power, energy, or critical-path claim is made.",
            "Always-on per-instruction DASM tracing may dominate host wall-clock time.",
        ],
        "artifact_index": "artifact_manifest.json",
        "exact_commands": "commands.json",
    }
    common.write_json(work_dir / "run_manifest.json", manifest)

    failed = any(status not in TERMINAL_ACCEPTED | {"pass"} for status in statuses)
    print(f"results={work_dir}")
    print(
        f"records={len(records)} fsm={len(fsm_records)} "
        f"failures={len(failures)} failed={int(failed)}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
