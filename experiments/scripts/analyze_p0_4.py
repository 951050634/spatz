#!/usr/bin/env python3
"""Validate, consolidate, and model the formal P0-4 experiment set."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import experiment_common as common
import index_external_runs as external_index
import run_performance_matrix as matrix

if str(common.REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(common.REPO_ROOT))

from util.online_softmax_merge import analyze_scaling as scaling_math


CONFIGS = (
    "B1_SCALAR",
    "B2R_RVV",
    "A1_SMU_SCALAR",
    "A2_SMU_FULL",
)
MODEL_CONFIGS = ("B2R_RVV", "A2_SMU_FULL")
PAPER_ELIGIBLE_EVIDENCE = {"MAIN_PERFORMANCE", "MODEL_WORKLOAD"}
STATUS_FROM_TARGET = {
    "pass": "PASS",
    "capacity_skip": "SKIPPED_MEMORY_LIMIT",
    "unsupported": "UNSUPPORTED_SHAPE",
}


def load_json(path: Path, expected_type: type) -> Any:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {path}: {error}") from error
    if not isinstance(payload, expected_type):
        raise ValueError(
            f"{path} must contain {expected_type.__name__}"
        )
    return payload


def resolve_repo_path(repo_root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"invalid repository path: {value!r}")
    path = Path(value)
    return path.resolve() if path.is_absolute() else (repo_root / path).resolve()


def verify_file_hash(path: Path, expected: Any, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    actual = common.sha256_file(path)
    if actual != expected:
        raise ValueError(
            f"{label} SHA256 mismatch: {actual} != {expected}: {path}"
        )


def load_indexed_runs(
    repo_root: Path, index_set_path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    index_set = load_json(index_set_path, dict)
    entries = index_set.get("runs")
    if not isinstance(entries, list) or not entries:
        raise ValueError("index set must contain a nonempty runs list")
    runs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"index-set run {position} is not an object")
        index_path = resolve_repo_path(repo_root, entry.get("index_path"))
        snapshot_path = resolve_repo_path(
            repo_root, entry.get("manifest_snapshot_path")
        )
        verify_file_hash(
            index_path, entry.get("index_sha256"), "run index"
        )
        verify_file_hash(
            snapshot_path,
            entry.get("manifest_snapshot_sha256"),
            "manifest snapshot",
        )
        index = load_json(index_path, dict)
        snapshot = load_json(snapshot_path, dict)
        root = Path(str(index.get("artifact_root"))).resolve()
        verified = external_index.verify_run(root)
        if verified.run_id != entry.get("run_id"):
            raise ValueError(f"run ID mismatch for {root}")
        if verified.run_id in seen_ids:
            raise ValueError(f"duplicate run ID: {verified.run_id}")
        seen_ids.add(verified.run_id)
        for key, value in verified.index.items():
            if index.get(key) != value:
                raise ValueError(
                    f"indexed field mismatch for {verified.run_id}: {key}"
                )
        if snapshot != verified.manifest:
            raise ValueError(
                f"manifest snapshot differs from external root: {root}"
            )
        records = load_json(root / "records.json", list)
        failures = load_json(root / "failures.json", list)
        runs.append(
            {
                "run_id": verified.run_id,
                "root": root,
                "index_path": index_path,
                "index": index,
                "manifest_path": snapshot_path,
                "manifest": snapshot,
                "records": records,
                "failures": failures,
            }
        )
    if index_set.get("run_count") != len(runs):
        raise ValueError("index-set run_count does not match its run list")
    return index_set, runs


def load_case_catalogs(
    repo_root: Path, plan: dict[str, Any]
) -> tuple[dict[str, matrix.Case], dict[str, Path]]:
    config_dir = repo_root / "experiments/configs"
    shards = plan.get("shards")
    if not isinstance(shards, list) or not shards:
        raise ValueError("P0-4 plan has no shards")
    names = {str(shard.get("case_file")) for shard in shards}
    cases: dict[str, matrix.Case] = {}
    paths: dict[str, Path] = {}
    for name in sorted(names):
        path = (config_dir / name).resolve()
        paths[name] = path
        for case in matrix.load_cases(path):
            if case.case_id in cases:
                raise ValueError(
                    f"case ID appears in multiple catalogs: {case.case_id}"
                )
            cases[case.case_id] = case
    return cases, paths


def suite_for_run(
    run_id: str, shards: Sequence[dict[str, Any]]
) -> dict[str, Any] | None:
    matches = [
        shard
        for shard in shards
        if run_id.endswith("_" + str(shard.get("suite")))
    ]
    return matches[0] if len(matches) == 1 else None


def audit_roots(
    repo_root: Path,
    plan: dict[str, Any],
    catalog_paths: dict[str, Path],
    runs: Sequence[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    issues: list[str] = []
    root_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    shards = plan["shards"]
    expected_suites = {str(shard["suite"]) for shard in shards}
    observed_suites: set[str] = set()
    commits = {run["manifest"].get("git_commit") for run in runs}
    cfg_hashes = {run["manifest"].get("cfg_sha256") for run in runs}
    simulator_hashes = {
        run["manifest"].get("simulator_sha256") for run in runs
    }
    witness_hashes = {
        run["manifest"].get("trace_witness_simulator_sha256")
        for run in runs
    }
    policy_hashes = {
        run["manifest"].get("policy_sha256") for run in runs
    }
    for label, values in (
        ("Git commit", commits),
        ("CFG hash", cfg_hashes),
        ("measurement simulator hash", simulator_hashes),
        ("trace-witness simulator hash", witness_hashes),
        ("measurement policy hash", policy_hashes),
    ):
        if len(values) != 1 or None in values:
            issues.append(f"{label} is incomplete or inconsistent: {values}")

    for run in runs:
        manifest = run["manifest"]
        shard = suite_for_run(run["run_id"], shards)
        if shard is None:
            issues.append(f"run does not match exactly one shard: {run['run_id']}")
            continue
        suite = str(shard["suite"])
        if suite in observed_suites:
            issues.append(f"duplicate suite evidence: {suite}")
        observed_suites.add(suite)
        expected_ids = list(shard["case_ids"])
        if manifest.get("selected_case_ids") != expected_ids:
            issues.append(f"selected case IDs differ for {suite}")
        if manifest.get("selected_case_count") != len(expected_ids):
            issues.append(f"selected case count differs for {suite}")
        case_file = str(shard["case_file"])
        case_path = catalog_paths[case_file]
        if Path(str(manifest.get("case_file"))).name != case_file:
            issues.append(f"case-file name differs for {suite}")
        if manifest.get("case_file_sha256") != common.sha256_file(case_path):
            issues.append(f"case-file hash differs for {suite}")
        if manifest.get("configurations") != list(CONFIGS):
            issues.append(f"configuration list differs for {suite}")
        if manifest.get("counter_profiles") != ["memory"]:
            issues.append(f"counter profile differs for {suite}")
        if manifest.get("trials") != 3:
            issues.append(f"trial count differs for {suite}")
        if manifest.get("git_dirty") is not False:
            issues.append(f"dirty-worktree evidence in {suite}")
        runner_argv = manifest.get("runner_argv")
        if not isinstance(runner_argv, list):
            issues.append(f"runner argv missing for {suite}")
        else:
            for required_flag in ("--require-clean", "--no-index"):
                if required_flag not in runner_argv:
                    issues.append(f"{required_flag} missing for {suite}")
        expected_records = len(expected_ids) * len(CONFIGS) * 3
        if manifest.get("record_count") != expected_records:
            issues.append(f"record count differs for {suite}")
        for failure in run["failures"]:
            failure_rows.append(
                {
                    "run_id": run["run_id"],
                    "suite": suite,
                    "artifact_root": str(run["root"]),
                    "failure": failure,
                }
            )
        root_rows.append(
            {
                "run_id": run["run_id"],
                "suite": suite,
                "artifact_root": str(run["root"]),
                "git_commit": manifest.get("git_commit"),
                "git_dirty": manifest.get("git_dirty"),
                "selected_case_ids": expected_ids,
                "record_count": manifest.get("record_count"),
                "failure_count": manifest.get("failure_count"),
                "cfg_sha256": manifest.get("cfg_sha256"),
                "simulator_sha256": manifest.get("simulator_sha256"),
                "trace_witness_simulator_sha256": manifest.get(
                    "trace_witness_simulator_sha256"
                ),
                "run_manifest_sha256": run["index"].get(
                    "run_manifest_sha256"
                ),
                "records_sha256": run["index"].get("records_sha256"),
                "artifact_manifest_sha256": run["index"].get(
                    "artifact_manifest_sha256"
                ),
                "artifact_verification": run["index"].get(
                    "artifact_verification"
                ),
            }
        )
    if observed_suites != expected_suites:
        issues.append(
            "suite coverage differs: missing="
            f"{sorted(expected_suites - observed_suites)}, extra="
            f"{sorted(observed_suites - expected_suites)}"
        )
    return issues, sorted(root_rows, key=lambda row: row["suite"]), failure_rows


def layout(case: matrix.Case, policy: dict[str, Any]) -> dict[str, int]:
    hardware = policy["hardware"]
    alignment = int(hardware["allocation_alignment_bytes"])
    footprint = case.n * (40 + 16 * case.d)
    allocation = (footprint + alignment - 1) // alignment * alignment
    runtime = int(hardware["runtime_reserved_bytes"])
    return {
        "footprint_bytes": footprint,
        "allocation_bytes": allocation,
        "runtime_reserved_bytes": runtime,
        "memory_footprint_bytes": allocation + runtime,
        "formal_total_footprint_limit_bytes": int(
            hardware["formal_total_footprint_limit_bytes"]
        ),
    }


def finite_max(values: Sequence[Any]) -> float | None:
    numeric = [
        float(value)
        for value in values
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ]
    return max(numeric) if numeric else None


def audit_records(
    plan: dict[str, Any],
    cases: dict[str, matrix.Case],
    policy: dict[str, Any],
    runs: Sequence[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    issues: list[str] = []
    records: list[dict[str, Any]] = []
    expected_keys: set[tuple[str, str, int]] = set()
    selected_by_run: dict[str, set[str]] = {}
    for run in runs:
        selected = set(run["manifest"].get("selected_case_ids", []))
        selected_by_run[run["run_id"]] = selected
        for case_id in selected:
            for config in CONFIGS:
                for trial in range(3):
                    expected_keys.add((case_id, config, trial))
        for raw in run["records"]:
            if not isinstance(raw, dict):
                issues.append(f"non-object record in {run['run_id']}")
                continue
            record = {
                "source_artifact_root": str(run["root"]),
                **raw,
            }
            records.append(record)

    grouped: dict[
        tuple[str, str, int], list[dict[str, Any]]
    ] = defaultdict(list)
    for record in records:
        case_id = str(record.get("case_id"))
        config = str(record.get("config"))
        trial = record.get("trial")
        if not isinstance(trial, int):
            issues.append(f"non-integer trial for {case_id}/{config}")
            continue
        key = (case_id, config, trial)
        grouped[key].append(record)
        case = cases.get(case_id)
        if case is None:
            issues.append(f"unknown case ID in records: {case_id}")
            continue
        run_id = str(record.get("run_id"))
        if case_id not in selected_by_run.get(run_id, set()):
            issues.append(f"case {case_id} is outside run selection {run_id}")
        expected_target = matrix.expected_case_status(case, policy)
        expected_status = STATUS_FROM_TARGET[expected_target]
        expected_layout = layout(case, policy)
        checks = {
            "N": case.n,
            "D": case.d,
            "seed": case.seed,
            "input_pattern": case.case_kind,
            "evidence_class": case.evidence_class,
            "counter_profile": "memory",
            "expected_target_status": expected_target,
            "target_status": expected_target,
            "status": expected_status,
            "git_dirty": False,
            "reproducible": "YES",
            "static_code_gate": "PASS",
            "fairness_gate": "PASS",
            "comparison_set_complete": "YES",
            "measurement_simulator_gate": "PASS",
            "logical_N": case.n,
            "logical_D": case.d,
            "padded_N": case.n,
            "padded_D": case.d,
            "padding_ratio": 1.0,
            "footprint_bytes": expected_layout["footprint_bytes"],
            "allocation_bytes": expected_layout["allocation_bytes"],
            "runtime_reserved_bytes": expected_layout[
                "runtime_reserved_bytes"
            ],
            "memory_footprint_bytes": expected_layout[
                "memory_footprint_bytes"
            ],
        }
        for field, expected in checks.items():
            if record.get(field) != expected:
                issues.append(
                    f"{case_id}/{config}/trial-{trial} {field}="
                    f"{record.get(field)!r}, expected {expected!r}"
                )
        expected_paper = (
            "YES"
            if case.evidence_class in PAPER_ELIGIBLE_EVIDENCE
            and expected_status == "PASS"
            else "NO"
        )
        if record.get("paper_eligible") != expected_paper:
            issues.append(
                f"{case_id}/{config}/trial-{trial} paper eligibility differs"
            )
        if expected_status == "PASS":
            cycles = record.get("kernel_cycles")
            if not isinstance(cycles, int) or isinstance(cycles, bool) or cycles <= 0:
                issues.append(
                    f"{case_id}/{config}/trial-{trial} has invalid cycles"
                )
            if record.get("nonfinite") != 0:
                issues.append(
                    f"{case_id}/{config}/trial-{trial} is nonfinite"
                )
            if record.get("nan_count") != 0 or record.get("inf_count") != 0:
                issues.append(
                    f"{case_id}/{config}/trial-{trial} has NaN/Inf"
                )
            if config in {"A1_SMU_SCALAR", "A2_SMU_FULL"}:
                if record.get("fsm_gate") != "PASS":
                    issues.append(
                        f"{case_id}/{config}/trial-{trial} FSM gate failed"
                    )
                state_cycles = [
                    record.get(field)
                    for field in (
                        "load_scalar_cycles",
                        "compute_scalar_cycles",
                        "compute_weight_cycles",
                        "store_scalar_cycles",
                        "update_vector_cycles",
                    )
                ]
                if all(isinstance(value, int) for value in state_cycles):
                    if sum(state_cycles) != record.get("smu_busy_cycles"):
                        issues.append(
                            f"{case_id}/{config}/trial-{trial} FSM sum differs"
                        )
                else:
                    issues.append(
                        f"{case_id}/{config}/trial-{trial} FSM states missing"
                    )
            elif record.get("fsm_gate") != "NA":
                issues.append(
                    f"{case_id}/{config}/trial-{trial} unexpected FSM gate"
                )
            if config == "B2R_RVV":
                witness_checks = {
                    "dynamic_trace_verified": "YES",
                    "trace_witness_gate": "PASS",
                    "trace_source": "INDEPENDENT_DASM_WITNESS",
                    "trace_target_equivalence_gate": "PASS",
                }
                for field, expected in witness_checks.items():
                    if record.get(field) != expected:
                        issues.append(
                            f"{case_id}/{config}/trial-{trial} {field} failed"
                        )
                if (
                    record.get("measurement_target_projection_hash")
                    != record.get("trace_witness_target_projection_hash")
                ):
                    issues.append(
                        f"{case_id}/{config}/trial-{trial} witness mismatch"
                    )
        else:
            if record.get("fsm_gate") != "NA":
                issues.append(
                    f"{case_id}/{config}/trial-{trial} terminal FSM is not NA"
                )
        if not record.get("target_result_hash"):
            issues.append(
                f"{case_id}/{config}/trial-{trial} target hash missing"
            )
        if not record.get("input_hash") or not record.get("binary_hash"):
            issues.append(
                f"{case_id}/{config}/trial-{trial} input/binary hash missing"
            )

    observed_keys = set(grouped)
    missing = sorted(expected_keys - observed_keys)
    extra = sorted(observed_keys - expected_keys)
    if missing:
        issues.append(f"missing record keys: {missing}")
    if extra:
        issues.append(f"unexpected record keys: {extra}")
    duplicates = sorted(key for key, rows in grouped.items() if len(rows) != 1)
    if duplicates:
        issues.append(f"duplicate record keys: {duplicates}")

    trial_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        trial_groups[(str(record.get("case_id")), str(record.get("config")))].append(
            record
        )
    summaries: list[dict[str, Any]] = []
    for (case_id, config), rows in sorted(trial_groups.items()):
        case = cases.get(case_id)
        if case is None:
            continue
        rows = sorted(
            rows,
            key=lambda row: (
                row.get("trial")
                if isinstance(row.get("trial"), int)
                else -1
            ),
        )
        statuses = {row.get("status") for row in rows}
        cycles = [row.get("kernel_cycles") for row in rows]
        numeric_cycles = [
            value
            for value in cycles
            if isinstance(value, int) and not isinstance(value, bool)
        ]
        target_hashes = {row.get("target_result_hash") for row in rows}
        if len(rows) != 3:
            issues.append(f"{case_id}/{config} does not contain three trials")
        if len(statuses) != 1:
            issues.append(f"{case_id}/{config} statuses are not stable")
        if len(set(cycles)) != 1:
            issues.append(f"{case_id}/{config} cycles are not exact")
        if len(target_hashes) != 1 or None in target_hashes:
            issues.append(f"{case_id}/{config} target hashes are not exact")
        paper_values = {row.get("paper_eligible") for row in rows}
        if len(paper_values) != 1:
            issues.append(f"{case_id}/{config} paper gate is not stable")
        cycle_value = (
            numeric_cycles[0]
            if len(numeric_cycles) == len(cycles)
            and len(set(numeric_cycles)) == 1
            else None
        )
        summaries.append(
            {
                "case_id": case_id,
                "evidence_class": case.evidence_class,
                "size_class": case.size_class,
                "case_kind": case.case_kind,
                "N": case.n,
                "D": case.d,
                "config": config,
                "trials": len(rows),
                "status": next(iter(statuses)) if len(statuses) == 1 else "MIXED",
                "kernel_cycles_min": (
                    min(numeric_cycles) if numeric_cycles else None
                ),
                "kernel_cycles_median": cycle_value,
                "kernel_cycles_max": (
                    max(numeric_cycles) if numeric_cycles else None
                ),
                "cycles_per_element": (
                    cycle_value / (case.n * case.d)
                    if cycle_value is not None
                    else None
                ),
                "elements_per_cycle": (
                    (case.n * case.d) / cycle_value
                    if cycle_value not in (None, 0)
                    else None
                ),
                "tcdm_accessed": rows[0].get("tcdm_accessed") if rows else None,
                "tcdm_congested": rows[0].get("tcdm_congested") if rows else None,
                "max_abs_error": finite_max(
                    [row.get("max_abs_error") for row in rows]
                ),
                "max_rel_error": finite_max(
                    [row.get("max_rel_error") for row in rows]
                ),
                "mean_abs_error": finite_max(
                    [row.get("mean_abs_error") for row in rows]
                ),
                "l2_relative_error": finite_max(
                    [row.get("l2_relative_error") for row in rows]
                ),
                "memory_footprint_bytes": rows[0].get(
                    "memory_footprint_bytes"
                ) if rows else None,
                "paper_eligible": (
                    next(iter(paper_values)) if len(paper_values) == 1 else "NO"
                ),
                "paper_ineligible_reasons": rows[0].get(
                    "paper_ineligible_reasons"
                ) if rows else None,
                "reproducible": (
                    "YES"
                    if rows
                    and all(row.get("reproducible") == "YES" for row in rows)
                    else "NO"
                ),
                "input_hash": rows[0].get("input_hash") if rows else None,
                "binary_hash": rows[0].get("binary_hash") if rows else None,
                "target_result_hash": (
                    next(iter(target_hashes))
                    if len(target_hashes) == 1
                    else None
                ),
                "trace_witness_gate": rows[0].get(
                    "trace_witness_gate"
                ) if rows else None,
                "trace_target_equivalence_gate": rows[0].get(
                    "trace_target_equivalence_gate"
                ) if rows else None,
                "fsm_gate": rows[0].get("fsm_gate") if rows else None,
            }
        )

    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in summaries:
        by_case[row["case_id"]].append(row)
    for case_id, rows in sorted(by_case.items()):
        input_hashes = {row.get("input_hash") for row in rows}
        if len(input_hashes) != 1 or None in input_hashes:
            issues.append(f"{case_id} cross-config input hashes differ")
        if {row.get("config") for row in rows} != set(CONFIGS):
            issues.append(f"{case_id} configuration set is incomplete")

    return issues, records, summaries


def fit_models(
    summaries: Sequence[dict[str, Any]], issues: list[str]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    models: dict[str, Any] = {}
    parameter_rows: list[dict[str, Any]] = []
    residual_rows: list[dict[str, Any]] = []
    for config in MODEL_CONFIGS:
        points = [
            {
                "case_id": row["case_id"],
                "N": row["N"],
                "D": row["D"],
                "cycles_median": row["kernel_cycles_median"],
            }
            for row in summaries
            if row["evidence_class"] == "MAIN_PERFORMANCE"
            and row["config"] == config
            and row["status"] == "PASS"
            and row["paper_eligible"] == "YES"
        ]
        if len(points) != 23:
            issues.append(
                f"{config} model has {len(points)} points instead of 23"
            )
            models[config] = None
            continue
        try:
            model = scaling_math.fit_model(points)
        except scaling_math.AnalysisError as error:
            issues.append(f"{config} model fit failed: {error}")
            models[config] = None
            continue
        models[config] = model
        parameters = model["parameters_cycles"]
        parameter_rows.append(
            {
                "config": config,
                "formula": model["formula"],
                "fit_point_count": model["fit_point_count"],
                "C0_cycles": parameters["C0"]["decimal"],
                "C0_numerator": parameters["C0"]["numerator"],
                "C0_denominator": parameters["C0"]["denominator"],
                "Cs_cycles_per_row": parameters["Cs"]["decimal"],
                "Cs_numerator": parameters["Cs"]["numerator"],
                "Cs_denominator": parameters["Cs"]["denominator"],
                "Cv_cycles_per_element": parameters["Cv"]["decimal"],
                "Cv_numerator": parameters["Cv"]["numerator"],
                "Cv_denominator": parameters["Cv"]["denominator"],
                "R_squared": model["R_squared"]["decimal"],
                "R_squared_numerator": model["R_squared"]["numerator"],
                "R_squared_denominator": model["R_squared"]["denominator"],
                "sum_squared_residuals": model[
                    "sum_squared_residuals"
                ]["decimal"],
            }
        )
        for residual in model["residuals"]:
            residual_rows.append(
                {
                    "config": config,
                    "case_id": residual["case_id"],
                    "N": residual["N"],
                    "D": residual["D"],
                    "measured_cycles": residual["cycles_median"],
                    "fitted_cycles": residual["fitted_cycles"]["decimal"],
                    "Cstall_residual_cycles": residual["Cstall_cycles"][
                        "decimal"
                    ],
                    "Cstall_numerator": residual["Cstall_cycles"][
                        "numerator"
                    ],
                    "Cstall_denominator": residual["Cstall_cycles"][
                        "denominator"
                    ],
                }
            )
    return models, parameter_rows, residual_rows


def measured_break_even(
    summaries: Sequence[dict[str, Any]], issues: list[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    index = {
        (row["N"], row["D"], row["config"]): row
        for row in summaries
        if row["evidence_class"] == "MAIN_PERFORMANCE"
    }
    rows: list[dict[str, Any]] = []
    per_n: list[dict[str, Any]] = []
    for n in (1, 2, 4, 8):
        satisfying: list[int] = []
        for d in (1, 8, 16, 32):
            rvv = index.get((n, d, "B2R_RVV"))
            smu = index.get((n, d, "A2_SMU_FULL"))
            if rvv is None or smu is None:
                issues.append(f"break-even point is missing: N={n}, D={d}")
                rows.append(
                    {
                        "N": n,
                        "D": d,
                        "measurement_status": "MISSING",
                        "B2R_RVV_cycles": None,
                        "A2_SMU_FULL_cycles": None,
                        "A2_le_B2R": None,
                        "speedup_A2_vs_B2R": None,
                    }
                )
                continue
            rvv_cycles = rvv["kernel_cycles_median"]
            smu_cycles = smu["kernel_cycles_median"]
            valid = (
                rvv["status"] == "PASS"
                and smu["status"] == "PASS"
                and isinstance(rvv_cycles, int)
                and isinstance(smu_cycles, int)
            )
            if not valid:
                issues.append(f"break-even point did not pass: N={n}, D={d}")
            satisfies = valid and smu_cycles <= rvv_cycles
            if satisfies:
                satisfying.append(d)
            rows.append(
                {
                    "N": n,
                    "D": d,
                    "measurement_status": "MEASURED" if valid else "FAILED",
                    "B2R_RVV_cycles": rvv_cycles,
                    "A2_SMU_FULL_cycles": smu_cycles,
                    "A2_le_B2R": satisfies if valid else None,
                    "speedup_A2_vs_B2R": (
                        rvv_cycles / smu_cycles
                        if valid and smu_cycles != 0
                        else None
                    ),
                }
            )
        per_n.append(
            {
                "N": n,
                "minimum_measured_D": min(satisfying) if satisfying else None,
                "satisfying_measured_D": satisfying,
            }
        )
    return rows, per_n


def markdown_report(report: dict[str, Any]) -> str:
    counts = report["counts"]
    lines = [
        "# P0-4 Scaling and Boundary Report",
        "",
        "This report contains only measured Verilator cycle proxies.  Boundary",
        "and capacity evidence is retained as supporting-only and is excluded",
        "from headline performance and model fits.",
        "",
        "## Validation",
        "",
        f"- Indexed roots: {counts['root_count']}",
        f"- Raw records: {counts['record_count']}",
        f"- Failure entries: {counts['failure_count']}",
        f"- Validation issues: {counts['validation_issue_count']}",
        f"- Paper-eligible raw rows: {counts['paper_eligible_record_count']}",
        "",
        "## Scaling model",
        "",
        "The exact least-squares form is `C = C0 + Cs*N + Cv*N*D`; the",
        "per-point residual is reported separately as `Cstall`.",
        "",
        "| Config | Points | C0 | Cs/row | Cv/element | R² |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["model_parameter_rows"]:
        lines.append(
            f"| {row['config']} | {row['fit_point_count']} | "
            f"{row['C0_cycles']:.6f} | {row['Cs_cycles_per_row']:.6f} | "
            f"{row['Cv_cycles_per_element']:.6f} | "
            f"{row['R_squared']:.9f} |"
        )
    lines.extend(
        [
            "",
            "## Directly measured break-even",
            "",
            "`A2_SMU_FULL <= B2R_RVV`; no fitted prediction is mixed into",
            "this table.",
            "",
            "| N | Minimum measured D | Satisfying measured D values |",
            "| ---: | ---: | --- |",
        ]
    )
    for row in report["break_even_per_N"]:
        minimum = (
            str(row["minimum_measured_D"])
            if row["minimum_measured_D"] is not None
            else "NA"
        )
        values = ", ".join(str(value) for value in row["satisfying_measured_D"])
        lines.append(f"| {row['N']} | {minimum} | {values or 'none'} |")
    lines.extend(
        [
            "",
            "## Boundary and capacity status",
            "",
            "| Evidence class | Summary rows | Status counts |",
            "| --- | ---: | --- |",
        ]
    )
    for evidence_class, payload in report["boundary_status"].items():
        counts_text = ", ".join(
            f"{key}={value}" for key, value in payload["status_counts"].items()
        )
        lines.append(
            f"| {evidence_class} | {payload['summary_rows']} | "
            f"{counts_text} |"
        )
    if report["validation_issues"]:
        lines.extend(["", "## Validation issues", ""])
        lines.extend(f"- {issue}" for issue in report["validation_issues"])
    if report["failure_entries"]:
        lines.extend(["", "## Preserved failure entries", ""])
        for failure in report["failure_entries"]:
            lines.append(
                f"- `{failure['suite']}`: "
                f"`{json.dumps(failure['failure'], sort_keys=True)}`"
            )
    return "\n".join(lines) + "\n"


def write_outputs(
    output_dir: Path,
    report: dict[str, Any],
    records: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    index_set_path: Path,
    plan_path: Path,
    policy_path: Path,
    catalog_paths: dict[str, Path],
    git_context: dict[str, Any],
) -> dict[str, Any]:
    if output_dir.exists():
        raise ValueError(f"refusing to overwrite output directory: {output_dir}")
    output_dir.mkdir(parents=True)
    scaling_rows = [
        row for row in summaries if row["evidence_class"] == "MAIN_PERFORMANCE"
    ]
    boundary_rows = [
        row for row in summaries if row["evidence_class"] != "MAIN_PERFORMANCE"
    ]
    capacity_rows = [
        row for row in summaries if row["evidence_class"] == "CAPACITY_PROBE"
    ]
    output_payloads: list[tuple[Path, Any, str]] = [
        (output_dir / "p0_4_analysis.json", report, "json"),
        (output_dir / "p0_4_all_records.json", records, "json"),
        (output_dir / "p0_4_all_records.csv", records, "csv"),
        (output_dir / "p0_4_trial_summary.csv", summaries, "csv"),
        (output_dir / "p0_4_scaling_points.csv", scaling_rows, "csv"),
        (output_dir / "p0_4_boundary_summary.csv", boundary_rows, "csv"),
        (output_dir / "p0_4_capacity_summary.csv", capacity_rows, "csv"),
        (
            output_dir / "p0_4_model_parameters.csv",
            report["model_parameter_rows"],
            "csv",
        ),
        (
            output_dir / "p0_4_model_residuals.csv",
            report["model_residual_rows"],
            "csv",
        ),
        (
            output_dir / "p0_4_break_even.csv",
            report["break_even_rows"],
            "csv",
        ),
    ]
    for path, payload, kind in output_payloads:
        if kind == "json":
            common.write_json(path, payload)
        else:
            common.write_csv(path, payload)
    report_path = output_dir / "P0_4_SCALING_AND_BOUNDARY_REPORT.md"
    report_path.write_text(markdown_report(report), encoding="utf-8")

    output_paths = [path for path, _, _ in output_payloads] + [report_path]
    manifest = {
        "schema_version": 1,
        "analysis_git": git_context,
        "analysis_tool": {
            "path": common.relative_or_absolute(
                Path(__file__).resolve(), common.REPO_ROOT
            ),
            "sha256": common.sha256_file(Path(__file__).resolve()),
            "python": sys.version.split()[0],
        },
        "inputs": {
            "index_set": {
                "path": common.relative_or_absolute(
                    index_set_path, common.REPO_ROOT
                ),
                "sha256": common.sha256_file(index_set_path),
            },
            "plan": {
                "path": common.relative_or_absolute(
                    plan_path, common.REPO_ROOT
                ),
                "sha256": common.sha256_file(plan_path),
            },
            "policy": {
                "path": common.relative_or_absolute(
                    policy_path, common.REPO_ROOT
                ),
                "sha256": common.sha256_file(policy_path),
            },
            "case_catalogs": [
                {
                    "path": common.relative_or_absolute(
                        path, common.REPO_ROOT
                    ),
                    "sha256": common.sha256_file(path),
                }
                for path in sorted(catalog_paths.values())
            ],
            "roots": report["root_evidence"],
        },
        "outputs": [
            {
                "path": common.relative_or_absolute(
                    path, common.REPO_ROOT
                ),
                "bytes": path.stat().st_size,
                "sha256": common.sha256_file(path),
            }
            for path in output_paths
        ],
    }
    manifest_path = output_dir / "p0_4_manifest.json"
    common.write_json(manifest_path, manifest)
    return manifest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=common.REPO_ROOT)
    parser.add_argument("--index-set", type=Path, required=True)
    parser.add_argument(
        "--plan",
        type=Path,
        default=common.REPO_ROOT / "experiments/configs/p0_4_shards.json",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=common.REPO_ROOT
        / "experiments/configs/measurement_policy.json",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--require-clean", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    index_set_path = args.index_set.resolve()
    plan_path = args.plan.resolve()
    policy_path = args.policy.resolve()
    output_dir = args.output_dir.resolve()
    git_context = {
        "commit": common.git_output(repo_root, "rev-parse", "HEAD"),
        "branch": common.git_output(repo_root, "branch", "--show-current"),
        "dirty": bool(common.git_output(repo_root, "status", "--porcelain")),
    }
    if args.require_clean and git_context["dirty"]:
        raise SystemExit("--require-clean rejected a dirty Git worktree")
    try:
        plan = load_json(plan_path, dict)
        policy = load_json(policy_path, dict)
        index_set, runs = load_indexed_runs(repo_root, index_set_path)
        cases, catalog_paths = load_case_catalogs(repo_root, plan)
        root_issues, root_rows, failure_entries = audit_roots(
            repo_root, plan, catalog_paths, runs
        )
        record_issues, records, summaries = audit_records(
            plan, cases, policy, runs
        )
        issues = root_issues + record_issues
        models, parameter_rows, residual_rows = fit_models(
            summaries, issues
        )
        break_even_rows, break_even_per_n = measured_break_even(
            summaries, issues
        )
        boundary_status: dict[str, Any] = {}
        for evidence_class in (
            "FUNCTIONAL_BOUNDARY",
            "CAPACITY_PROBE",
        ):
            selected = [
                row
                for row in summaries
                if row["evidence_class"] == evidence_class
            ]
            boundary_status[evidence_class] = {
                "summary_rows": len(selected),
                "status_counts": dict(
                    sorted(Counter(row["status"] for row in selected).items())
                ),
            }
        status_counts = dict(
            sorted(Counter(str(row.get("status")) for row in records).items())
        )
        paper_count = sum(
            row.get("paper_eligible") == "YES" for row in records
        )
        acceptance = {
            "index_set_complete": len(runs) == len(plan["shards"]) == 17,
            "all_external_artifacts_reverified": all(
                row["artifact_verification"] == "PASS" for row in root_rows
            ),
            "no_failure_entries": not failure_entries,
            "record_matrix_complete": len(records) == 49 * 4 * 3,
            "validation_issue_free": not issues,
            "scaling_coordinate_count": sum(
                row["evidence_class"] == "MAIN_PERFORMANCE"
                and row["config"] == "B1_SCALAR"
                for row in summaries
            )
            == 23,
            "models_complete": all(models.get(config) for config in MODEL_CONFIGS),
            "break_even_complete": all(
                row["measurement_status"] == "MEASURED"
                for row in break_even_rows
            ),
            "paper_eligible_scope_exact": paper_count == 23 * 4 * 3,
        }
        report = {
            "schema_version": 1,
            "objective": (
                "P0-4 N/D scaling, directly measured break-even, RVV tails, "
                "numerical boundaries, and TCDM capacity boundaries"
            ),
            "measurement_semantics": (
                "kernel cycles from low-perturbation Verilator processes; "
                "independent identical-ELF DASM witnesses for B2-R"
            ),
            "model_formula": scaling_math.MODEL_FORMULA,
            "Cstall_interpretation": (
                "per-point measured-minus-fitted residual, not an "
                "independently identifiable fourth regression coefficient"
            ),
            "index_set": index_set,
            "root_evidence": root_rows,
            "failure_entries": failure_entries,
            "validation_issues": issues,
            "acceptance": acceptance,
            "counts": {
                "root_count": len(runs),
                "case_count": len(cases),
                "record_count": len(records),
                "summary_row_count": len(summaries),
                "failure_count": len(failure_entries),
                "validation_issue_count": len(issues),
                "paper_eligible_record_count": paper_count,
                "status_counts": status_counts,
            },
            "models": models,
            "model_parameter_rows": parameter_rows,
            "model_residual_rows": residual_rows,
            "break_even_definition": "A2_SMU_FULL cycles <= B2R_RVV cycles",
            "break_even_rows": break_even_rows,
            "break_even_per_N": break_even_per_n,
            "model_predictions_mixed_with_break_even": False,
            "boundary_status": boundary_status,
        }
        write_outputs(
            output_dir,
            report,
            records,
            summaries,
            index_set_path,
            plan_path,
            policy_path,
            catalog_paths,
            git_context,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"P0-4 analysis failed: {error}") from error

    print(f"output_dir={output_dir}")
    print(
        f"roots={len(runs)} records={len(records)} "
        f"issues={len(issues)} failures={len(failure_entries)}"
    )
    print(f"acceptance={json.dumps(acceptance, sort_keys=True)}")
    return 0 if all(acceptance.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
