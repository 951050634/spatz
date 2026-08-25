#!/usr/bin/env python3
"""Run canonical online-merge configurations in independent simulators."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import jstyleson

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_instruction_trace as trace_audit
import experiment_common as common

if str(common.REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(common.REPO_ROOT))

from util.online_softmax_merge import run_experiments as legacy


STATUS_MAP = {
    "pass": "PASS",
    "correctness_fail": "INVALID_OUTPUT",
    "timeout": "TIMEOUT",
    "capacity_skip": "SKIPPED_MEMORY_LIMIT",
    "unsupported": "UNSUPPORTED_SHAPE",
    "tool_error": "TOOL_ERROR",
}

SIM_CONFIG_PREFIX = "OM_SIM_CONFIG "
CASE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}")
EVIDENCE_CLASSES = {
    "MAIN_PERFORMANCE",
    "FUNCTIONAL_BOUNDARY",
    "CAPACITY_PROBE",
    "MODEL_WORKLOAD",
    "OPTIONAL_DIAGNOSTIC",
}
SUPPORTING_ONLY_EVIDENCE = {
    "FUNCTIONAL_BOUNDARY": "FUNCTIONAL_BOUNDARY_ONLY",
    "CAPACITY_PROBE": "CAPACITY_PROBE_ONLY",
    "OPTIONAL_DIAGNOSTIC": "OPTIONAL_DIAGNOSTIC_ONLY",
}
TARGET_TIMING_FIELDS = {
    "cycles_hi",
    "cycles_lo",
    "kernel_cycles",
    "tcdm_accessed",
    "tcdm_congested",
    "cycles_per_element",
    "elements_per_cycle",
    "congestion_ratio",
}

SMU_EXPECTED_MODES = {
    "A1_SMU_SCALAR": 1,
    "A1_MIXED_SCALAR": 3,
    "A2_SMU_FULL": 0,
}


@dataclass(frozen=True)
class Case:
    n: int
    d: int
    seed: int
    case_kind: str
    case_id: str
    evidence_class: str
    size_class: str
    timeout_seconds: int
    max_kernel_cycles: int

    @property
    def slug(self) -> str:
        return self.case_id


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    root = common.REPO_ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument(
        "--case-file",
        type=Path,
        default=root / "experiments/configs/p0_anchor_cases.json",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=root / "experiments/configs/measurement_policy.json",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=root / "hw/system/spatz_cluster/sw",
    )
    parser.add_argument(
        "--cfg",
        type=Path,
        default=(
            root
            / "hw/system/spatz_cluster/cfg/"
            "spatz_cluster.default.dram.hjson"
        ),
    )
    parser.add_argument(
        "--simulator",
        type=Path,
        default=root / "hw/system/spatz_cluster/bin/spatz_cluster.vlt",
    )
    parser.add_argument(
        "--trace-witness-simulator",
        type=Path,
        help=(
            "independent DASM-enabled simulator used once per executable "
            "B2-R case; when set, the measurement simulator must identify "
            "itself as the low-perturbation profile"
        ),
    )
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--suite", default="p0")
    parser.add_argument(
        "--case-ids",
        default="",
        help="comma-separated case IDs selected from the case file",
    )
    parser.add_argument("--configs", default="")
    parser.add_argument("--profiles", default="memory,instructions")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--build-timeout-seconds", type=int, default=900)
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument("--no-index", action="store_true")
    return parser.parse_args(argv)


def load_cases(path: Path) -> list[Case]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("case file must contain a nonempty JSON array")
    cases: list[Case] = []
    case_ids: set[str] = set()
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"case {index} is not an object")
        n = int(item["N"])
        d = int(item["D"])
        seed = int(item.get("seed", 1))
        case_kind = str(item.get("case_kind", "main"))
        default_case_id = (
            f"N{n}_D{d}_S{seed}_{case_kind.replace('-', '_')}"
        )
        case = Case(
            n=n,
            d=d,
            seed=seed,
            case_kind=case_kind,
            case_id=str(item.get("case_id", default_case_id)),
            evidence_class=str(
                item.get("evidence_class", "MAIN_PERFORMANCE")
            ),
            size_class=str(item.get("size_class", "UNCLASSIFIED")),
            timeout_seconds=int(item.get("timeout_seconds", 1800)),
            max_kernel_cycles=int(
                item.get("max_kernel_cycles", 100_000_000)
            ),
        )
        if (
            case.n <= 0
            or case.d <= 0
            or case.timeout_seconds <= 0
            or case.max_kernel_cycles <= 0
        ):
            raise ValueError(f"case {index} has a nonpositive value")
        if CASE_ID_PATTERN.fullmatch(case.case_id) is None:
            raise ValueError(
                f"case {index} has an unsafe or invalid case_id"
            )
        if case.case_id in case_ids:
            raise ValueError(f"duplicate case_id: {case.case_id}")
        if case.evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(
                f"case {index} has unknown evidence_class: "
                f"{case.evidence_class}"
            )
        case_ids.add(case.case_id)
        cases.append(case)
    return cases


def selected_names(value: str, available: dict[str, Any]) -> list[str]:
    if not value:
        return list(available)
    names = [item.strip() for item in value.split(",") if item.strip()]
    unknown = sorted(set(names) - set(available))
    if unknown:
        raise ValueError(f"unknown configurations: {', '.join(unknown)}")
    return names


def selected_cases(value: str, cases: Sequence[Case]) -> list[Case]:
    if not value:
        return list(cases)
    names = [item.strip() for item in value.split(",") if item.strip()]
    if len(names) != len(set(names)):
        raise ValueError("case selection must not contain duplicate IDs")
    by_id = {case.case_id: case for case in cases}
    unknown = sorted(set(names) - set(by_id))
    if unknown:
        raise ValueError(f"unknown case IDs: {', '.join(unknown)}")
    return [by_id[name] for name in names]


def default_cmake_defines(
    repo_root: Path, cfg_path: Path, profile: str, case: Case
) -> list[str]:
    with cfg_path.open(encoding="utf-8") as stream:
        cfg = jstyleson.load(stream)
    cluster = cfg["cluster"]
    dram = cfg["dram"]
    isa = str(cluster["cores"][0].get("isa", "rv32"))
    values = {
        "BUILD_TESTS": "ON",
        "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
        "LLVM_PATH": str(repo_root / "install/llvm"),
        "GCC_PATH": str(repo_root / "install/riscv-gcc"),
        "ELEN": "64" if "d" in isa else "32",
        "MEM_DRAM_ORIGIN": str(dram["address"]),
        "MEM_DRAM_SIZE": str(dram["length"]),
        "SNRT_BASE_HARTID": str(cluster["cluster_base_hartid"]),
        "SNRT_CLUSTER_CORE_NUM": str(len(cluster["cores"])),
        "SNRT_CLUSTER_OFFSET": str(cluster["cluster_base_offset"]),
        "SNRT_NFPU_PER_CORE": str(cluster["n_fpu"]),
        "SNRT_TCDM_SIZE": str(cluster["tcdm"]["size"] * 1024),
        "SNRT_TCDM_START_ADDR": str(cluster["cluster_base_addr"]),
        "PLATFORM_SOURCE_FOLDER": "src/platforms/standalone",
        "SPATZ_CLUSTER_CFG": cfg_path.name,
        "ONLINE_MERGE_N": str(case.n),
        "ONLINE_MERGE_D": str(case.d),
        "ONLINE_MERGE_SEED": str(case.seed),
        "ONLINE_MERGE_CASE_KIND": case.case_kind,
        "ONLINE_MERGE_REPEATS": "1",
        "ONLINE_MERGE_COUNTER_PROFILE": profile,
    }
    return [f"-D{key}={value}" for key, value in values.items()]


def artifact(
    path: Path, artifact_root: Path, kind: str
) -> dict[str, Any]:
    return {
        "path": common.relative_or_absolute(path, artifact_root),
        "kind": kind,
        "bytes": path.stat().st_size,
        "sha256": common.sha256_file(path),
    }


def persist(
    root: Path,
    records: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    commands: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    common.write_json(root / "records.json", records)
    common.write_csv(root / "records.csv", records)
    common.write_json(root / "failures.json", failures)
    common.write_json(root / "commands.json", commands)
    common.write_json(root / "artifact_manifest.json", artifacts)
    common.write_json(root / "run_manifest.json", manifest)


def target_compile_commands(
    build_dir: Path, target: str
) -> list[dict[str, Any]]:
    path = build_dir / "compile_commands.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    marker = f"CMakeFiles/{target}.dir/"
    return [
        item
        for item in payload
        if marker
        in str(item.get("command") or " ".join(item.get("arguments", [])))
    ]


def main_compile_command(commands: list[dict[str, Any]]) -> str | None:
    for item in commands:
        if str(item.get("file", "")).endswith(
            "online-softmax-merge/main.c"
        ):
            return str(
                item.get("command") or " ".join(item.get("arguments", []))
            )
    return None


def compiler_fairness_hash(command: str | None) -> str | None:
    if command is None:
        return None
    normalized: list[str] = []
    skip_next = False
    for token in shlex.split(command):
        if skip_next:
            skip_next = False
            continue
        if token == "-o":
            skip_next = True
            continue
        if token.startswith("-DONLINE_MERGE_IMPLEMENTATION_SELECT="):
            continue
        normalized.append(token)
    return common.sha256_json(normalized)


def parse_simulator_configuration(
    output: str,
    expected_profile: str,
    expected_dasm: bool,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Parse and validate exactly one simulator instrumentation record."""
    records, errors = common.parse_prefixed_json(output, SIM_CONFIG_PREFIX)
    if len(records) != 1:
        errors.append(
            {
                "message": (
                    "expected exactly one OM_SIM_CONFIG record, got "
                    f"{len(records)}"
                )
            }
        )
        return None, errors
    record = records[0]
    expected = {
        "schema_version": 1,
        "profile": expected_profile,
        "dasm_trace_enabled": expected_dasm,
        "fsm_observer_enabled": True,
    }
    for field, value in expected.items():
        if record.get(field) != value:
            errors.append(
                {
                    "message": (
                        f"simulator configuration {field}="
                        f"{record.get(field)!r}, expected {value!r}"
                    )
                }
            )
    return record, errors


def target_functional_projection(
    target_record: dict[str, Any],
) -> dict[str, Any]:
    """Return target output fields unaffected by tracing or counters."""
    return {
        key: target_record[key]
        for key in sorted(target_record)
        if key not in TARGET_TIMING_FIELDS
    }


def expected_case_status(
    case: Case, policy: dict[str, Any]
) -> str:
    """Predict only generator-declared terminal cases from policy values."""
    hardware = policy["hardware"]
    alignment = int(hardware["allocation_alignment_bytes"])
    footprint = case.n * (40 + 16 * case.d)
    allocation = (footprint + alignment - 1) // alignment * alignment
    total = allocation + int(hardware["runtime_reserved_bytes"])
    if total > int(hardware["formal_total_footprint_limit_bytes"]):
        return "capacity_skip"
    if case.case_kind == "both-zero-l":
        return "unsupported"
    return "pass"


def implementation_static_gate_reasons(
    output: str,
    snippet: str | None,
    config_name: str,
    expected_status: str,
) -> list[str]:
    """Inspect hot implementation code only for executable pass cases."""
    if expected_status != "pass":
        return []
    if config_name in {"B2R_RVV", "A1_SMU_SCALAR", "A1_MIXED_SCALAR"}:
        _, missing = legacy.inspect_rvv_disassembly(output)
        return list(missing)
    if config_name == "B1_SCALAR":
        if snippet is None:
            return ["missing scalar reference symbol"]
        if any(
            mnemonic in snippet
            for mnemonic in (
                "vsetvl",
                "vle32.v",
                "vse32.v",
                "vfmul",
                "vfmacc",
            )
        ):
            return ["B1 scalar symbol contains RVV"]
    return []


def make_failure_record(
    base: dict[str, Any], status: str, reason: str
) -> dict[str, Any]:
    record = dict(base)
    record.update(
        {
            "kernel_cycles": None,
            "status": status,
            "target_status": None,
            "failure_reason": reason,
            "paper_eligible": "NO",
            "paper_ineligible_reasons": reason,
            "reproducible": "NO",
        }
    )
    return record


def canonical_base(
    run_id: str,
    git_commit: str,
    git_dirty: bool,
    config_name: str,
    definition: dict[str, Any],
    profile: str,
    case: Case,
    trial: int,
    cfg_path: Path,
    cfg_hash: str,
    simulator: Path,
    simulator_hash: str | None,
    compiler: str,
    verilator_version: str,
    worktree_snapshot_hash: str,
) -> dict[str, Any]:
    aliases = definition.get("aliases", [])
    return {
        "run_id": run_id,
        "timestamp": common.utc_now(),
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "worktree_snapshot_hash": worktree_snapshot_hash,
        "config": config_name,
        "config_alias": ",".join(aliases) if aliases else None,
        "internal_implementation": definition["internal_implementation"],
        "counter_profile": profile,
        "trial": trial,
        "cluster_cfg": common.relative_or_absolute(
            cfg_path, common.REPO_ROOT
        ),
        "cfg_hash": cfg_hash,
        "simulator_path": str(simulator),
        "simulator_hash": simulator_hash,
        "compiler": compiler,
        "compiler_flags": None,
        "compiler_fairness_hash": None,
        "verilator_version": verilator_version,
        "binary_hash": None,
        "input_hash": None,
        "N": case.n,
        "D": case.d,
        "case_id": case.case_id,
        "evidence_class": case.evidence_class,
        "tile_size": None,
        "logical_N": case.n,
        "logical_D": case.d,
        "padded_N": case.n,
        "padded_D": case.d,
        "padding_ratio": 1.0,
        "seed": case.seed,
        "input_pattern": case.case_kind,
        "size_class": case.size_class,
        "max_kernel_cycles": case.max_kernel_cycles,
        "memory_footprint_bytes": None,
        "kernel_cycles": None,
        "end_to_end_cycles": None,
        "end_to_end_reason": "NO_EXPLICIT_TRANSFER_PHASE",
        "tcdm_read_bytes": None,
        "tcdm_write_bytes": None,
        "bank_conflicts": None,
        "retired_instructions": None,
        "retired_accelerator_instructions": None,
        "scalar_instructions": None,
        "vector_instructions": None,
        "smu_commands": None,
        "smu_busy_cycles": None,
        "smu_wait_cycles": None,
        "stall_cycles": None,
        "max_abs_error": None,
        "max_rel_error": None,
        "mean_abs_error": None,
        "l2_relative_error": None,
        "nan_count": None,
        "inf_count": None,
        "pos_inf_count": None,
        "neg_inf_count": None,
        "raw_log_path": None,
        "dynamic_trace_verified": "NO",
        "measurement_simulator_gate": "NA",
        "measurement_simulator_profile": None,
        "measurement_simulator_dasm_trace_enabled": None,
        "trace_source": None,
        "trace_witness_gate": "NA",
        "trace_witness_simulator_path": None,
        "trace_witness_simulator_hash": None,
        "trace_witness_target_projection_hash": None,
        "measurement_target_projection_hash": None,
        "trace_target_equivalence_gate": "NA",
    }


def parse_one_result(
    output: str,
    expected_internal: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    raw_records, errors = common.parse_prefixed_json(
        output, common.RESULT_PREFIX
    )
    if len(raw_records) != 1:
        errors.append(
            {
                "message": (
                    "single-implementation run must emit exactly one "
                    f"OM_RESULT record, got {len(raw_records)}"
                )
            }
        )
        return None, errors
    raw = raw_records[0]
    if raw.get("implementation") != expected_internal:
        errors.append(
            {
                "message": (
                    f"implementation mismatch: {raw.get('implementation')} "
                    f"!= {expected_internal}"
                )
            }
        )
        return None, errors
    try:
        return common.enrich_target_record(raw), errors
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        errors.append({"message": f"record enrichment failed: {error}"})
        return None, errors


def measured_fsm(
    output: str, config_name: str
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    expected_mode = SMU_EXPECTED_MODES.get(config_name)
    if expected_mode is None:
        return None, []
    records, errors = common.parse_prefixed_json(output, common.FSM_PREFIX)
    if len(records) != 2:
        errors.append(
            {
                "message": (
                    "SMU run must emit exactly one warm-up and one measured "
                    f"FSM record, got {len(records)}"
                )
            }
        )
        return (records[-1] if records else None), errors
    measured = records[-1]
    if records[0].get("invocation") != 0 or measured.get("invocation") != 1:
        errors.append({"message": "SMU invocation sequence is not 0,1"})
    for phase, record in (("warm-up", records[0]), ("measured", measured)):
        if record.get("mode") != expected_mode:
            errors.append(
                {
                    "message": (
                        f"{phase} SMU FSM mode {record.get('mode')!r} != "
                        f"expected {expected_mode} for {config_name}"
                    )
                }
            )
    if measured.get("terminal_state") != "DONE":
        errors.append({"message": "measured SMU FSM did not reach DONE"})
    return measured, errors


def apply_reproducibility(
    records: list[dict[str, Any]], trials: int
) -> None:
    deterministic_terminal_statuses = {
        "PASS",
        "SKIPPED_MEMORY_LIMIT",
        "UNSUPPORTED_SHAPE",
    }
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        key = (
            record.get("config"),
            record.get("counter_profile"),
            record.get("case_id"),
            record.get("evidence_class"),
            record.get("N"),
            record.get("D"),
            record.get("seed"),
            record.get("input_pattern"),
        )
        groups.setdefault(key, []).append(record)
    for group in groups.values():
        accepted = [
            row
            for row in group
            if row.get("status") in deterministic_terminal_statuses
        ]
        statuses = {row.get("status") for row in accepted}
        cycles = {row.get("kernel_cycles") for row in accepted}
        result_hashes = {
            row.get("target_result_hash") for row in accepted
        }
        exact = (
            len(group) == trials
            and len(accepted) == trials
            and len(statuses) == 1
            and len(cycles) == 1
            and None not in result_hashes
            and len(result_hashes) == 1
        )
        for row in group:
            row["reproducible"] = "YES" if exact else "NO"
        unstable = (
            len(statuses) > 1
            or len(cycles) > 1
            or len(result_hashes) > 1
        )
        if len(group) == trials and len(accepted) == trials and unstable:
            for row in group:
                row["status"] = "NONDETERMINISTIC"
                row["failure_reason"] = (
                    "independent trials produced different cycles or target "
                    "results"
                )


def apply_cross_config_fairness(
    records: list[dict[str, Any]], required_configs: set[str]
) -> None:
    fields = (
        "cfg_hash",
        "simulator_hash",
        "worktree_snapshot_hash",
        "input_hash",
        "compiler_fairness_hash",
        "logical_N",
        "logical_D",
        "padded_N",
        "padded_D",
        "padding_ratio",
    )
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        coordinate = (
            record.get("counter_profile"),
            record.get("case_id"),
            record.get("evidence_class"),
            record.get("N"),
            record.get("D"),
            record.get("seed"),
            record.get("input_pattern"),
        )
        groups.setdefault(coordinate, []).append(record)
    for group in groups.values():
        configs = {str(record.get("config")) for record in group}
        mismatches = [
            field
            for field in fields
            if len({str(record.get(field)) for record in group}) != 1
        ]
        for record in group:
            record["fairness_gate"] = "PASS" if not mismatches else "FAIL"
            record["fairness_mismatches"] = (
                ";".join(mismatches) if mismatches else None
            )
            record["comparison_set_complete"] = (
                "YES" if configs == required_configs else "NO"
            )


def apply_paper_eligibility(records: list[dict[str, Any]]) -> None:
    for record in records:
        reasons: list[str] = []
        if record.get("status") != "PASS":
            reasons.append(str(record.get("status")))
        if record.get("git_dirty"):
            reasons.append("DIRTY_WORKTREE")
        if record.get("counter_profile") != "memory":
            reasons.append("AUXILIARY_COUNTER_PROFILE")
        if record.get("reproducible") != "YES":
            reasons.append("NOT_REPRODUCIBLE")
        if record.get("static_code_gate") != "PASS":
            reasons.append("STATIC_CODE_GATE_FAILED")
        if record.get("fairness_gate") != "PASS":
            reasons.append("CROSS_CONFIG_FAIRNESS_FAILED")
        if record.get("comparison_set_complete") != "YES":
            reasons.append("INCOMPLETE_CONFIG_SET")
        if record.get("config") in {
            "A1_SMU_SCALAR",
            "A1_MIXED_SCALAR",
            "A2_SMU_FULL",
        } and record.get("fsm_gate") != "PASS":
            reasons.append("SMU_FSM_GATE_FAILED")
        if record.get("config") == "B2R_RVV" and record.get(
            "dynamic_trace_verified"
        ) != "YES":
            reasons.append("DYNAMIC_RVV_TRACE_PENDING")
        evidence_class = record.get("evidence_class")
        if evidence_class in SUPPORTING_ONLY_EVIDENCE:
            reasons.append(SUPPORTING_ONLY_EVIDENCE[evidence_class])
        record["paper_eligible"] = "NO" if reasons else "YES"
        record["paper_ineligible_reasons"] = (
            ";".join(reasons) if reasons else None
        )


def main(argv: Sequence[str] | None = None) -> int:
    effective_argv = list(argv) if argv is not None else sys.argv[1:]
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    policy_path = args.policy.resolve()
    case_path = args.case_file.resolve()
    source_dir = args.source_dir.resolve()
    cfg_path = args.cfg.resolve()
    simulator = args.simulator.resolve()
    trace_witness_simulator = (
        args.trace_witness_simulator.resolve()
        if args.trace_witness_simulator
        else None
    )
    if args.trials < 1:
        raise SystemExit("--trials must be at least one")
    if args.jobs <= 0:
        raise SystemExit("--jobs must be positive")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    definitions = policy["configurations"]
    try:
        config_names = selected_names(args.configs, definitions)
        case_catalog = load_cases(case_path)
        cases = selected_cases(args.case_ids, case_catalog)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"invalid experiment configuration: {error}") from error
    profiles = [item.strip() for item in args.profiles.split(",") if item.strip()]
    if not profiles or set(profiles) - {"memory", "instructions"}:
        raise SystemExit("--profiles must contain memory and/or instructions")

    git_commit = common.git_output(repo_root, "rev-parse", "HEAD")
    git_dirty = bool(common.git_output(repo_root, "status", "--porcelain"))
    if args.require_clean and git_dirty:
        raise SystemExit("--require-clean rejected a dirty Git worktree")
    try:
        source_snapshot = common.worktree_snapshot(repo_root)
    except RuntimeError as error:
        raise SystemExit(f"cannot snapshot worktree: {error}") from error
    run_id = f"{common.utc_run_stamp()}_{git_commit[:8]}_{args.suite}"
    artifact_root = (
        args.artifact_root.resolve()
        if args.artifact_root
        else repo_root.parent / f"work-online-merge-{run_id}"
    )
    try:
        common.require_fresh_external_root(artifact_root, repo_root)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    artifact_root.mkdir(parents=True)
    build_dir = (
        args.build_dir.resolve()
        if args.build_dir
        else artifact_root / "build"
    )
    try:
        build_dir.relative_to(repo_root)
    except ValueError:
        pass
    else:
        raise SystemExit("build directory must be outside the Git worktree")
    if build_dir.exists():
        raise SystemExit(f"refusing to reuse build directory: {build_dir}")
    build_dir.mkdir(parents=True)

    cfg_hash = common.sha256_file(cfg_path)
    simulator_hash = (
        common.sha256_file(simulator) if simulator.is_file() else None
    )
    trace_witness_simulator_hash = (
        common.sha256_file(trace_witness_simulator)
        if trace_witness_simulator is not None
        and trace_witness_simulator.is_file()
        else None
    )
    objdump = repo_root / "install/llvm/bin/llvm-objdump"
    llvm_nm = repo_root / "install/llvm/bin/llvm-nm"
    llvm_size = repo_root / "install/llvm/bin/llvm-size"
    compiler_tool = common.command_version(
        [str(repo_root / "install/llvm/bin/clang"), "--version"]
    )
    verilator_tool = common.command_version(
        [str(repo_root / "install/verilator/bin/verilator"), "--version"]
    )
    compiler_identity = str(
        compiler_tool.get("version") or compiler_tool.get("detail")
    )
    verilator_identity = str(
        verilator_tool.get("version") or verilator_tool.get("detail")
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "runner_argv": [
            sys.executable,
            str(Path(__file__).resolve()),
            *effective_argv,
        ],
        "runner_sha256": common.sha256_file(Path(__file__).resolve()),
        "start_utc": common.utc_now(),
        "end_utc": None,
        "git_commit": git_commit,
        "git_branch": common.git_output(
            repo_root, "branch", "--show-current"
        ),
        "git_dirty": git_dirty,
        "worktree_snapshot": source_snapshot,
        "case_file": common.relative_or_absolute(case_path, repo_root),
        "case_file_sha256": common.sha256_file(case_path),
        "case_catalog_count": len(case_catalog),
        "selected_case_ids": [case.case_id for case in cases],
        "selected_case_count": len(cases),
        "policy": common.relative_or_absolute(policy_path, repo_root),
        "policy_sha256": common.sha256_file(policy_path),
        "cfg_path": common.relative_or_absolute(cfg_path, repo_root),
        "cfg_sha256": cfg_hash,
        "simulator": str(simulator),
        "simulator_sha256": simulator_hash,
        "trace_witness_simulator": (
            str(trace_witness_simulator)
            if trace_witness_simulator is not None
            else None
        ),
        "trace_witness_simulator_sha256": trace_witness_simulator_hash,
        "trace_witness_policy": (
            "one independent DASM-enabled B2-R execution per executable "
            "case/profile using the identical ELF and generated input"
            if trace_witness_simulator is not None
            else None
        ),
        "configurations": config_names,
        "counter_profiles": profiles,
        "trials": args.trials,
        "warmups_per_process": 1,
        "measured_samples_per_process": 1,
        "tool_versions": {
            "cmake": common.command_version([args.cmake, "--version"]),
            "compiler": compiler_tool,
            "verilator": verilator_tool,
            "objdump": common.command_version(
                [str(objdump), "--version"]
            ),
            "simulator": {
                "path": str(simulator),
                "sha256": simulator_hash,
            },
            "trace_witness_simulator": {
                "path": (
                    str(trace_witness_simulator)
                    if trace_witness_simulator is not None
                    else None
                ),
                "sha256": trace_witness_simulator_hash,
            },
        },
        "measurement_window": (
            "inputs resident in TCDM through final output completion; "
            "includes command, wait, RVV, and synchronization"
        ),
        "end_to_end_reason": "NO_EXPLICIT_TRANSFER_PHASE",
    }
    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = [
        artifact(
            Path(__file__).resolve(), artifact_root, "runner_script"
        ),
        artifact(cfg_path, artifact_root, "cluster_cfg"),
        artifact(case_path, artifact_root, "case_file"),
        artifact(policy_path, artifact_root, "measurement_policy"),
    ]
    if simulator.is_file():
        artifacts.append(artifact(simulator, artifact_root, "simulator"))
    if (
        trace_witness_simulator is not None
        and trace_witness_simulator.is_file()
    ):
        artifacts.append(
            artifact(
                trace_witness_simulator,
                artifact_root,
                "trace_witness_simulator",
            )
        )
    persist(
        artifact_root, records, failures, commands, artifacts, manifest
    )

    for case in cases:
        expected_status = expected_case_status(case, policy)
        for profile in profiles:
            profile_dir = artifact_root / case.slug / profile
            configure_log = profile_dir / "configure.log"
            configure_argv = [
                args.cmake,
                "-S",
                str(source_dir),
                "-B",
                str(build_dir),
                *default_cmake_defines(
                    repo_root, cfg_path, profile, case
                ),
            ]
            configure, _ = common.run_command(
                configure_argv,
                repo_root,
                configure_log,
                args.build_timeout_seconds,
            )
            commands.append(common.command_dict(configure))
            artifacts.append(
                artifact(configure_log, artifact_root, "configure_log")
            )
            if configure.status != "PASS":
                message = f"configure failed with {configure.status}"
                failures.append(
                    {
                        "case": case.slug,
                        "profile": profile,
                        "kind": "CONFIGURE_FAILURE",
                        "message": message,
                    }
                )
                for config_name in config_names:
                    definition = definitions[config_name]
                    for trial in range(args.trials):
                        base = canonical_base(
                            run_id,
                            git_commit,
                            git_dirty,
                            config_name,
                            definition,
                            profile,
                            case,
                            trial,
                            cfg_path,
                            cfg_hash,
                            simulator,
                            simulator_hash,
                            compiler_identity,
                            verilator_identity,
                            str(source_snapshot["sha256"]),
                        )
                        records.append(
                            make_failure_record(
                                base, configure.status, message
                            )
                        )
                persist(
                    artifact_root,
                    records,
                    failures,
                    commands,
                    artifacts,
                    manifest,
                )
                continue

            generated_header = (
                build_dir
                / "spatzBenchmarks/online_merge_generated/"
                f"N{case.n}_D{case.d}_S{case.seed}_"
                f"{case.case_kind}_R1/online_merge_case_data.h"
            )
            for config_name in config_names:
                definition = definitions[config_name]
                target = str(definition["build_target"])
                config_dir = profile_dir / config_name
                build_log = config_dir / "build.log"
                build, _ = common.run_command(
                    [
                        args.cmake,
                        "--build",
                        str(build_dir),
                        "--target",
                        target,
                        "--parallel",
                        str(args.jobs),
                    ],
                    repo_root,
                    build_log,
                    args.build_timeout_seconds,
                )
                commands.append(common.command_dict(build))
                artifacts.append(
                    artifact(build_log, artifact_root, "build_log")
                )
                elf_source = build_dir / "spatzBenchmarks" / target
                elf = config_dir / "online-softmax-merge.elf"
                static_gate = "PASS"
                gate_reasons: list[str] = []
                if build.status != "PASS" or not elf_source.is_file():
                    static_gate = "TOOL_ERROR"
                    gate_reasons.append(
                        f"build/ELF unavailable: {build.status}"
                    )
                else:
                    config_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(elf_source, elf)
                    artifacts.append(artifact(elf, artifact_root, "elf"))
                    if generated_header.is_file():
                        copied_header = config_dir / generated_header.name
                        shutil.copy2(generated_header, copied_header)
                        artifacts.append(
                            artifact(
                                copied_header,
                                artifact_root,
                                "generated_input_header",
                            )
                        )
                    for tool, suffix, kind in (
                        (objdump, "objdump.txt", "disassembly"),
                        (llvm_nm, "symbols.txt", "symbol_table"),
                        (llvm_size, "sections.txt", "section_sizes"),
                    ):
                        output_path = config_dir / suffix
                        tool_args = [str(tool)]
                        if tool == objdump:
                            tool_args.extend(
                                ["-d", "--no-show-raw-insn", "--mattr=+v"]
                            )
                        elif tool == llvm_nm:
                            tool_args.extend(["-n", "-S"])
                        else:
                            tool_args.extend(["-A", "-x"])
                        tool_args.append(str(elf))
                        command, output = common.run_command(
                            tool_args,
                            config_dir,
                            output_path,
                            args.build_timeout_seconds,
                        )
                        commands.append(common.command_dict(command))
                        artifacts.append(
                            artifact(output_path, artifact_root, kind)
                        )
                        if command.status != "PASS":
                            static_gate = "TOOL_ERROR"
                            gate_reasons.append(f"{kind} failed")
                        if tool == objdump and command.status == "PASS":
                            symbol = (
                                "online_merge_rtl_reference"
                                if config_name == "B1_SCALAR"
                                else "online_merge_rvv_update"
                            )
                            snippet = legacy.extract_symbol_disassembly(
                                output, symbol
                            )
                            if snippet is not None:
                                snippet_path = config_dir / f"{symbol}.disasm"
                                snippet_path.write_text(
                                    snippet, encoding="utf-8"
                                )
                                artifacts.append(
                                    artifact(
                                        snippet_path,
                                        artifact_root,
                                        "hot_symbol_disassembly",
                                    )
                                )
                            implementation_reasons = (
                                implementation_static_gate_reasons(
                                    output,
                                    snippet,
                                    config_name,
                                    expected_status,
                                )
                            )
                            if implementation_reasons:
                                static_gate = "TOOL_ERROR"
                                gate_reasons.extend(implementation_reasons)

                compile_records = target_compile_commands(build_dir, target)
                compile_line = main_compile_command(compile_records)
                if compile_records:
                    compile_path = config_dir / "compile_commands.json"
                    common.write_json(compile_path, compile_records)
                    artifacts.append(
                        artifact(
                            compile_path,
                            artifact_root,
                            "compile_commands",
                        )
                    )
                link_source = (
                    build_dir
                    / "spatzBenchmarks/CMakeFiles"
                    / f"{target}.dir/link.txt"
                )
                if link_source.is_file():
                    link_path = config_dir / "link_command.txt"
                    shutil.copy2(link_source, link_path)
                    artifacts.append(
                        artifact(link_path, artifact_root, "link_command")
                    )
                input_hash = (
                    common.sha256_file(generated_header)
                    if generated_header.is_file()
                    else None
                )
                elf_hash = common.sha256_file(elf) if elf.is_file() else None
                witness_gate = "NA"
                witness_sim_config: dict[str, Any] | None = None
                witness_trace_payload: dict[str, Any] | None = None
                witness_trace_audit_path: Path | None = None
                witness_target_projection_hash: str | None = None
                witness_target_result_hash: str | None = None
                if (
                    config_name == "B2R_RVV"
                    and trace_witness_simulator is not None
                ):
                    if expected_status != "pass":
                        witness_gate = "NOT_APPLICABLE_TERMINAL_CASE"
                    elif static_gate != "PASS" or not elf.is_file():
                        witness_gate = "BLOCKED_BY_STATIC_GATE"
                    else:
                        witness_dir = config_dir / "trace-witness"
                        witness_logs_dir = witness_dir / "logs"
                        witness_logs_dir.mkdir(
                            parents=True, exist_ok=False
                        )
                        witness_log = witness_dir / "simulator.log"
                        witness_errors: list[dict[str, Any]] = []
                        witness_command = None
                        witness_target: dict[str, Any] | None = None
                        if not trace_witness_simulator.is_file():
                            witness_errors.append(
                                {
                                    "message": (
                                        "trace witness simulator unavailable: "
                                        f"{trace_witness_simulator}"
                                    )
                                }
                            )
                        else:
                            witness_command, witness_output = (
                                common.run_command(
                                    [
                                        str(trace_witness_simulator),
                                        str(elf),
                                    ],
                                    witness_dir,
                                    witness_log,
                                    case.timeout_seconds,
                                )
                            )
                            commands.append(
                                common.command_dict(witness_command)
                            )
                            artifacts.append(
                                artifact(
                                    witness_log,
                                    artifact_root,
                                    "trace_witness_simulator_log",
                                )
                            )
                            if witness_command.status != "PASS":
                                witness_errors.append(
                                    {
                                        "message": (
                                            "trace witness command failed: "
                                            f"{witness_command.status}"
                                        )
                                    }
                                )
                            witness_sim_config, simulator_errors = (
                                parse_simulator_configuration(
                                    witness_output,
                                    expected_profile="default",
                                    expected_dasm=True,
                                )
                            )
                            witness_errors.extend(simulator_errors)
                            witness_target, target_errors = parse_one_result(
                                witness_output,
                                str(
                                    definition[
                                        "internal_implementation"
                                    ]
                                ),
                            )
                            witness_errors.extend(target_errors)
                            if witness_target is not None:
                                witness_target_result_hash = (
                                    common.sha256_json(witness_target)
                                )
                                witness_projection = (
                                    target_functional_projection(
                                        witness_target
                                    )
                                )
                                witness_target_projection_hash = (
                                    common.sha256_json(witness_projection)
                                )
                                projection_path = (
                                    witness_dir
                                    / "target_functional_projection.json"
                                )
                                common.write_json(
                                    projection_path, witness_projection
                                )
                                artifacts.append(
                                    artifact(
                                        projection_path,
                                        artifact_root,
                                        "trace_witness_target_projection",
                                    )
                                )
                                if witness_target.get("status") != "pass":
                                    witness_errors.append(
                                        {
                                            "message": (
                                                "trace witness target status "
                                                "is not pass"
                                            )
                                        }
                                    )
                            trace_path = (
                                witness_logs_dir
                                / "trace_hart_00000.dasm"
                            )
                            for dasm_path in sorted(
                                witness_logs_dir.glob(
                                    "trace_hart_*.dasm"
                                )
                            ):
                                artifacts.append(
                                    artifact(
                                        dasm_path,
                                        artifact_root,
                                        "trace_witness_dasm_trace",
                                    )
                                )
                            disassembly_path = config_dir / "objdump.txt"
                            if (
                                trace_path.is_file()
                                and disassembly_path.is_file()
                            ):
                                try:
                                    audited_trace = trace_audit.audit_trace(
                                        trace_path,
                                        disassembly_path,
                                        config_name,
                                        case.n,
                                        case.d,
                                    )
                                except (OSError, ValueError) as error:
                                    witness_errors.append(
                                        {"message": str(error)}
                                    )
                                else:
                                    witness_trace_audit_path = (
                                        witness_dir
                                        / "instruction_trace_audit.json"
                                    )
                                    common.write_json(
                                        witness_trace_audit_path,
                                        audited_trace,
                                    )
                                    artifacts.append(
                                        artifact(
                                            witness_trace_audit_path,
                                            artifact_root,
                                            "trace_witness_audit",
                                        )
                                    )
                                    if audited_trace["errors"]:
                                        witness_errors.extend(
                                            {"message": message}
                                            for message in audited_trace[
                                                "errors"
                                            ]
                                        )
                                    elif not audited_trace[
                                        "dynamic_rvv_trace_verified"
                                    ]:
                                        witness_errors.append(
                                            {
                                                "message": (
                                                    "trace witness did not "
                                                    "verify dynamic RVV"
                                                )
                                            }
                                        )
                                    else:
                                        witness_trace_payload = audited_trace
                            else:
                                witness_errors.append(
                                    {
                                        "message": (
                                            "trace witness hart-0 DASM or "
                                            "disassembly missing"
                                        )
                                    }
                                )

                        witness_gate = (
                            "FAIL" if witness_errors else "PASS"
                        )
                        witness_metadata = {
                            "schema_version": 1,
                            "case_id": case.case_id,
                            "config": config_name,
                            "counter_profile": profile,
                            "expected_target_status": expected_status,
                            "gate": witness_gate,
                            "errors": witness_errors,
                            "simulator": str(trace_witness_simulator),
                            "simulator_sha256": (
                                trace_witness_simulator_hash
                            ),
                            "simulator_configuration": witness_sim_config,
                            "binary_sha256": elf_hash,
                            "input_sha256": input_hash,
                            "target_result_sha256": (
                                witness_target_result_hash
                            ),
                            "target_functional_projection_sha256": (
                                witness_target_projection_hash
                            ),
                            "command": (
                                common.command_dict(witness_command)
                                if witness_command is not None
                                else None
                            ),
                        }
                        witness_metadata_path = (
                            witness_dir / "trace_witness_metadata.json"
                        )
                        common.write_json(
                            witness_metadata_path, witness_metadata
                        )
                        artifacts.append(
                            artifact(
                                witness_metadata_path,
                                artifact_root,
                                "trace_witness_metadata",
                            )
                        )
                        if witness_errors:
                            failures.append(
                                {
                                    "case": case.slug,
                                    "profile": profile,
                                    "config": config_name,
                                    "trial": "trace-witness",
                                    "kind": "TRACE_WITNESS_GATE",
                                    "message": ";".join(
                                        str(error.get("message"))
                                        for error in witness_errors
                                    ),
                                }
                            )
                for trial in range(args.trials):
                    base = canonical_base(
                        run_id,
                        git_commit,
                        git_dirty,
                        config_name,
                        definition,
                        profile,
                        case,
                        trial,
                        cfg_path,
                        cfg_hash,
                        simulator,
                        simulator_hash,
                        compiler_identity,
                        verilator_identity,
                        str(source_snapshot["sha256"]),
                    )
                    base.update(
                        {
                            "binary_hash": elf_hash,
                            "input_hash": input_hash,
                            "compiler_flags": compile_line,
                            "compiler_fairness_hash": (
                                compiler_fairness_hash(compile_line)
                            ),
                            "static_code_gate": static_gate,
                            "static_code_gate_reasons": (
                                ";".join(gate_reasons)
                                if gate_reasons
                                else None
                            ),
                            "expected_target_status": expected_status,
                            "trace_witness_gate": (
                                witness_gate
                                if config_name == "B2R_RVV"
                                else "NA"
                            ),
                            "trace_witness_simulator_path": (
                                str(trace_witness_simulator)
                                if config_name == "B2R_RVV"
                                and trace_witness_simulator is not None
                                else None
                            ),
                            "trace_witness_simulator_hash": (
                                trace_witness_simulator_hash
                                if config_name == "B2R_RVV"
                                else None
                            ),
                            "trace_witness_simulator_profile": (
                                witness_sim_config.get("profile")
                                if witness_sim_config is not None
                                else None
                            ),
                            "trace_witness_target_projection_hash": (
                                witness_target_projection_hash
                            ),
                        }
                    )
                    if static_gate != "PASS" or not simulator.is_file():
                        reason = (
                            ";".join(gate_reasons)
                            if gate_reasons
                            else f"simulator unavailable: {simulator}"
                        )
                        record = make_failure_record(
                            base, "TOOL_ERROR", reason
                        )
                        record["fsm_gate"] = "NA"
                        records.append(record)
                        failures.append(
                            {
                                "case": case.slug,
                                "profile": profile,
                                "config": config_name,
                                "trial": trial,
                                "kind": "STATIC_OR_SIMULATOR_GATE",
                                "message": reason,
                            }
                        )
                        persist(
                            artifact_root,
                            records,
                            failures,
                            commands,
                            artifacts,
                            manifest,
                        )
                        continue

                    trial_dir = config_dir / f"trial-{trial}"
                    trial_dir.mkdir(parents=True, exist_ok=False)
                    (trial_dir / "logs").mkdir(exist_ok=False)
                    log_path = trial_dir / "simulator.log"
                    command, output = common.run_command(
                        [str(simulator), str(elf)],
                        trial_dir,
                        log_path,
                        case.timeout_seconds,
                    )
                    commands.append(common.command_dict(command))
                    artifacts.append(
                        artifact(log_path, artifact_root, "simulator_log")
                    )
                    target_record, parse_errors = parse_one_result(
                        output, str(definition["internal_implementation"])
                    )
                    if target_record is not None and target_record.get(
                        "status"
                    ) in {"capacity_skip", "unsupported"}:
                        fsm, fsm_errors = None, []
                    else:
                        fsm, fsm_errors = measured_fsm(
                            output, config_name
                        )
                    simulator_config: dict[str, Any] | None = None
                    simulator_errors: list[dict[str, Any]] = []
                    if trace_witness_simulator is not None:
                        simulator_config, simulator_errors = (
                            parse_simulator_configuration(
                                output,
                                expected_profile="low_perturbation",
                                expected_dasm=False,
                            )
                        )
                    base.update(
                        {
                            "measurement_simulator_gate": (
                                "PASS"
                                if trace_witness_simulator is not None
                                and not simulator_errors
                                else (
                                    "FAIL"
                                    if trace_witness_simulator is not None
                                    else "NA"
                                )
                            ),
                            "measurement_simulator_profile": (
                                simulator_config.get("profile")
                                if simulator_config is not None
                                else None
                            ),
                            "measurement_simulator_dasm_trace_enabled": (
                                simulator_config.get(
                                    "dasm_trace_enabled"
                                )
                                if simulator_config is not None
                                else None
                            ),
                        }
                    )
                    errors = (
                        parse_errors + fsm_errors + simulator_errors
                    )
                    if (
                        target_record is not None
                        and target_record.get("status") != expected_status
                    ):
                        errors.append(
                            {
                                "message": (
                                    "target status does not match declared "
                                    f"case policy: {target_record.get('status')}"
                                    f" != {expected_status}"
                                )
                            }
                        )
                    measurement_projection_hash: str | None = None
                    trace_equivalence_gate = "NA"
                    if target_record is not None:
                        measurement_projection_hash = common.sha256_json(
                            target_functional_projection(target_record)
                        )
                    if config_name == "B2R_RVV" and witness_gate == "PASS":
                        if (
                            measurement_projection_hash
                            == witness_target_projection_hash
                        ):
                            trace_equivalence_gate = "PASS"
                        else:
                            trace_equivalence_gate = "FAIL"
                            errors.append(
                                {
                                    "message": (
                                        "measurement and trace-witness "
                                        "functional target projections differ"
                                    )
                                }
                            )
                    base.update(
                        {
                            "measurement_target_projection_hash": (
                                measurement_projection_hash
                            ),
                            "trace_target_equivalence_gate": (
                                trace_equivalence_gate
                            ),
                        }
                    )
                    trace_payload: dict[str, Any] | None = None
                    trace_source: str | None = None
                    trace_audit_record_path: Path | None = None
                    trace_path = (
                        trial_dir / "logs/trace_hart_00000.dasm"
                    )
                    disassembly_path = config_dir / "objdump.txt"
                    for dasm_path in sorted(
                        (trial_dir / "logs").glob("trace_hart_*.dasm")
                    ):
                        artifacts.append(
                            artifact(dasm_path, artifact_root, "dasm_trace")
                        )
                    if trace_path.is_file() and disassembly_path.is_file():
                        try:
                            trace_payload = trace_audit.audit_trace(
                                trace_path,
                                disassembly_path,
                                config_name,
                                case.n,
                                case.d,
                            )
                        except (OSError, ValueError) as error:
                            failures.append(
                                {
                                    "case": case.slug,
                                    "profile": profile,
                                    "config": config_name,
                                    "trial": trial,
                                    "kind": "TRACE_AUDIT_FAILURE",
                                    "message": str(error),
                                }
                            )
                        else:
                            trace_audit_path = (
                                trial_dir / "instruction_trace_audit.json"
                            )
                            trace_audit_record_path = trace_audit_path
                            trace_source = "MEASUREMENT_PROCESS_DASM"
                            common.write_json(
                                trace_audit_path, trace_payload
                            )
                            artifacts.append(
                                artifact(
                                    trace_audit_path,
                                    artifact_root,
                                    "instruction_trace_audit",
                                )
                            )
                            if trace_payload["errors"]:
                                failures.append(
                                    {
                                        "case": case.slug,
                                        "profile": profile,
                                        "config": config_name,
                                        "trial": trial,
                                        "kind": "TRACE_AUDIT_GATE",
                                        "message": ";".join(
                                            trace_payload["errors"]
                                        ),
                                    }
                                )
                    elif (
                        config_name == "B2R_RVV"
                        and witness_gate == "PASS"
                        and witness_trace_payload is not None
                    ):
                        trace_payload = witness_trace_payload
                        trace_audit_record_path = witness_trace_audit_path
                        trace_source = "INDEPENDENT_DASM_WITNESS"
                    elif (
                        config_name == "B2R_RVV"
                        and expected_status == "pass"
                        and trace_witness_simulator is None
                    ):
                        failures.append(
                            {
                                "case": case.slug,
                                "profile": profile,
                                "config": config_name,
                                "trial": trial,
                                "kind": "TRACE_AUDIT_UNAVAILABLE",
                                "message": (
                                    "hart-0 DASM trace or disassembly missing"
                                ),
                            }
                        )
                    if errors:
                        failures.extend(
                            {
                                "case": case.slug,
                                "profile": profile,
                                "config": config_name,
                                "trial": trial,
                                "kind": "TARGET_OUTPUT_GATE",
                                **error,
                            }
                            for error in errors
                        )
                    if target_record is None:
                        record = make_failure_record(
                            base,
                            "TIMEOUT"
                            if command.status == "TIMEOUT"
                            else "TOOL_ERROR",
                            "missing or malformed target result",
                        )
                        record["fsm_gate"] = "TOOL_ERROR"
                    else:
                        record = dict(base)
                        record.update(target_record)
                        record["target_result_hash"] = common.sha256_json(
                            target_record
                        )
                        target_status = str(target_record.get("status"))
                        status = STATUS_MAP.get(target_status, "TOOL_ERROR")
                        if command.status == "TIMEOUT":
                            status = "TIMEOUT"
                        elif command.status != "PASS" and status != (
                            "INVALID_OUTPUT"
                        ):
                            status = "TOOL_ERROR"
                        if errors:
                            status = "TOOL_ERROR"
                        if (
                            status == "PASS"
                            and int(target_record["kernel_cycles"])
                            > case.max_kernel_cycles
                        ):
                            status = "TIMEOUT"
                            failures.append(
                                {
                                    "case": case.slug,
                                    "profile": profile,
                                    "config": config_name,
                                    "trial": trial,
                                    "kind": "CYCLE_LIMIT_EXCEEDED",
                                    "message": (
                                        f"kernel cycles exceed "
                                        f"{case.max_kernel_cycles}"
                                    ),
                                }
                            )
                        record["target_status"] = target_status
                        record["status"] = status
                        record["dynamic_trace_verified"] = (
                            "YES"
                            if trace_payload
                            and trace_payload["dynamic_rvv_trace_verified"]
                            else "NO"
                        )
                        record["dynamic_retired_instructions"] = (
                            trace_payload.get(
                                "retired_instructions_in_envelope"
                            )
                            if trace_payload
                            else None
                        )
                        record["dynamic_vector_instructions"] = (
                            trace_payload.get("retired_rvv_instructions")
                            if trace_payload
                            else None
                        )
                        record["vector_instructions"] = record[
                            "dynamic_vector_instructions"
                        ]
                        record["scalar_instructions"] = (
                            record["dynamic_retired_instructions"]
                            - record["dynamic_vector_instructions"]
                            if record["dynamic_retired_instructions"]
                            is not None
                            and record["dynamic_vector_instructions"]
                            is not None
                            else None
                        )
                        record["instruction_mix_source"] = (
                            (
                                "DASM_MARKER_ENVELOPE_WITNESS"
                                if trace_source
                                == "INDEPENDENT_DASM_WITNESS"
                                else "DASM_MARKER_ENVELOPE"
                            )
                            if trace_payload
                            else None
                        )
                        record["trace_source"] = trace_source
                        trace_cycles = (
                            trace_payload.get("category_cycle_spans", {})
                            if trace_payload
                            else {}
                        )
                        for category_name in (
                            "software_scalar",
                            "rvv",
                            "load_store",
                            "loop_control",
                            "synchronization",
                            "other",
                            "undecoded",
                        ):
                            record[
                                f"trace_{category_name}_cycles"
                            ] = trace_cycles.get(category_name)
                        record["trace_audit_path"] = (
                            common.relative_or_absolute(
                                trace_audit_record_path,
                                artifact_root,
                            )
                            if trace_payload
                            and trace_audit_record_path is not None
                            else None
                        )
                        record["raw_log_path"] = common.relative_or_absolute(
                            log_path, artifact_root
                        )
                        record["memory_footprint_bytes"] = target_record.get(
                            "memory_footprint_bytes"
                        )
                        record["buffer_footprint_bytes"] = (
                            target_record.get("footprint_bytes")
                        )
                        record["buffer_allocation_bytes"] = (
                            target_record.get("allocation_bytes")
                        )
                        record["runtime_reserved_bytes"] = (
                            target_record.get("runtime_reserved_bytes")
                        )
                        record["logical_cycles_per_element"] = (
                            target_record["kernel_cycles"]
                            / (case.n * case.d)
                        )
                        record["physical_cycles_per_element"] = record[
                            "logical_cycles_per_element"
                        ]
                        record["smu_commands"] = (
                            1
                            if config_name
                            in {
                                "A1_SMU_SCALAR",
                                "A1_MIXED_SCALAR",
                                "A2_SMU_FULL",
                            }
                            else 0
                        )
                        if config_name not in {
                            "A1_SMU_SCALAR",
                            "A1_MIXED_SCALAR",
                        }:
                            record["smu_scalar_cycles"] = None
                            record["rvv_vector_cycles"] = None
                        if fsm is None:
                            record["fsm_gate"] = (
                                "TOOL_ERROR"
                                if target_status == "pass"
                                and config_name
                                in {
                                    "A1_SMU_SCALAR",
                                    "A1_MIXED_SCALAR",
                                    "A2_SMU_FULL",
                                }
                                else "NA"
                            )
                            record["smu_busy_cycles"] = None
                            record["command_and_sync_cycles"] = None
                        else:
                            busy = int(fsm.get("busy_cycles", -1))
                            kernel = int(record["kernel_cycles"])
                            update_cycles = int(
                                fsm.get("update_vector_cycles", -1)
                            )
                            vector_mode_valid = (
                                update_cycles == 0
                                if config_name
                                in {"A1_SMU_SCALAR", "A1_MIXED_SCALAR"}
                                else update_cycles > 0
                            )
                            valid_fsm = (
                                fsm.get("terminal_state") == "DONE"
                                and 0 <= busy <= kernel
                                and int(fsm.get("N", -1)) == case.n
                                and int(fsm.get("D", -1)) == case.d
                                and int(fsm.get("invocation", -1)) >= 1
                                and int(fsm.get("mode", -1))
                                == SMU_EXPECTED_MODES[config_name]
                                and vector_mode_valid
                            )
                            record["fsm_gate"] = (
                                "PASS" if valid_fsm else "TOOL_ERROR"
                            )
                            if not valid_fsm:
                                record["status"] = "TOOL_ERROR"
                                failures.append(
                                    {
                                        "case": case.slug,
                                        "profile": profile,
                                        "config": config_name,
                                        "trial": trial,
                                        "kind": "FSM_SEMANTIC_GATE",
                                        "message": (
                                            "measured FSM shape, mode, "
                                            "invocation, or busy interval "
                                            "is invalid"
                                        ),
                                    }
                                )
                            record["smu_busy_cycles"] = (
                                busy if valid_fsm else None
                            )
                            record["command_and_sync_cycles"] = (
                                kernel - busy if valid_fsm else None
                            )
                            record["smu_measured_invocation"] = fsm.get(
                                "invocation"
                            )
                            for key in (
                                "load_scalar_cycles",
                                "compute_scalar_cycles",
                                "compute_weight_cycles",
                                "store_scalar_cycles",
                                "update_vector_cycles",
                            ):
                                record[key] = fsm.get(key)
                        record["paper_eligible"] = "NO"
                        record["paper_ineligible_reasons"] = (
                            "REPRODUCIBILITY_NOT_CHECKED"
                        )
                    records.append(record)
                    persist(
                        artifact_root,
                        records,
                        failures,
                        commands,
                        artifacts,
                        manifest,
                    )

    apply_reproducibility(records, args.trials)
    nondeterministic_groups = {
        (
            record.get("config"),
            record.get("counter_profile"),
            record.get("case_id"),
            record.get("evidence_class"),
            record.get("N"),
            record.get("D"),
            record.get("seed"),
            record.get("input_pattern"),
        )
        for record in records
        if record.get("status") == "NONDETERMINISTIC"
    }
    failures.extend(
        {
            "kind": "NONDETERMINISTIC",
            "group": list(group),
            "message": "independent trials did not match exactly",
        }
        for group in sorted(nondeterministic_groups, key=str)
    )
    apply_cross_config_fairness(records, set(definitions))
    fairness_failures = {
        (
            record.get("counter_profile"),
            record.get("case_id"),
            record.get("evidence_class"),
            record.get("N"),
            record.get("D"),
            record.get("seed"),
            record.get("input_pattern"),
            record.get("fairness_mismatches"),
        )
        for record in records
        if record.get("fairness_gate") == "FAIL"
    }
    failures.extend(
        {
            "kind": "CROSS_CONFIG_FAIRNESS",
            "group": list(group[:-1]),
            "message": str(group[-1]),
        }
        for group in sorted(fairness_failures, key=str)
    )
    apply_paper_eligibility(records)
    manifest["end_utc"] = common.utc_now()
    manifest["record_count"] = len(records)
    manifest["failure_count"] = len(failures)
    manifest["all_trials_reproducible"] = all(
        record.get("reproducible") == "YES" for record in records
    )
    persist(artifact_root, records, failures, commands, artifacts, manifest)

    if not args.no_index:
        index_path = repo_root / "experiments/raw" / f"{run_id}.json"
        snapshot_path = (
            repo_root / "experiments/manifests" / f"{run_id}.json"
        )
        if index_path.exists() or snapshot_path.exists():
            raise SystemExit(
                "run index or manifest snapshot already exists for "
                f"{run_id}"
            )
        index = {
            "run_id": run_id,
            "artifact_root": str(artifact_root),
            "run_manifest_sha256": common.sha256_file(
                artifact_root / "run_manifest.json"
            ),
            "records_sha256": common.sha256_file(
                artifact_root / "records.json"
            ),
            "artifact_manifest_sha256": common.sha256_file(
                artifact_root / "artifact_manifest.json"
            ),
        }
        common.write_json(index_path, index)
        common.write_json(snapshot_path, manifest)

    failures_present = bool(failures)
    nondeterministic = any(
        record.get("status") == "NONDETERMINISTIC" for record in records
    )
    print(f"run_id={run_id}")
    print(f"artifact_root={artifact_root}")
    print(f"records={len(records)} failures={len(failures)}")
    return 1 if failures_present or nondeterministic else 0


if __name__ == "__main__":
    raise SystemExit(main())
