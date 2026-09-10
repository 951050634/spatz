#!/usr/bin/env python3
"""Collect the two pre-selected Phase 6 Native Online Attention shapes.

The default invocation is plan-only.  Formal execution is explicit, requires
the clean approved snapshot, and runs only the two new shapes.  Phase 5
anchors are imported byte-for-byte from their archived formal CSV artifacts;
the Phase 6 output tables therefore have one auditable source for every
number without rerunning or modifying Phase 5.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
PHASE5_DIR = ROOT / "experiments/phase5_native_online_attention"
PHASE5_FORMAL = PHASE5_DIR / "formal"
SHAPE_MANIFEST = SCRIPT_DIR / "shape_manifest.csv"
NEW_SHAPES = ((24, 64), (16, 128))
ANCHORS = ((8, 32), (16, 64))
ALL_SHAPES = ANCHORS + NEW_SHAPES
REJECTED_PRE_RESULT_CANDIDATES = ({
    "n": 32,
    "d": 64,
    "seed": 1,
    "status": "rejected-pre-result-host-completion",
    "reason": "software exceeded the 900 s host smoke budget without PHASE5_RESULT; the interrupted SMU attempt emitted only OM_FSM invocations 0..2 without PHASE5_RESULT/output",
    "speedup_inspected": False,
},)
IMPLEMENTATIONS = ("software", "smu")
TARGETS = {
    "software": "test-spatzBenchmarks-native-online-attention-software",
    "smu": "test-spatzBenchmarks-native-online-attention-smu",
}
DEFAULT_SIMULATOR = Path(
    "/home/wxt/work-online-merge-supplement/work-artifacts/work-phase4-recip-sim/spatz_cluster.vlt"
)


def load_phase5_collector():
    spec = importlib.util.spec_from_file_location(
        "phase5_collect_formal", PHASE5_DIR / "collect_formal.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the frozen Phase 5 collector")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p5 = load_phase5_collector()


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_rows(path: Path) -> list[dict[str, str]]:
    require(path.is_file(), f"missing formal artifact: {path}")
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def shape_slug(n: int, d: int, seed: int) -> str:
    return f"N{n}_D{d}_S{seed}"


def shape_manifest_rows() -> list[dict[str, str]]:
    rows = read_rows(SHAPE_MANIFEST)
    selected = [row for row in rows if row.get("selected", "1") == "1"]
    require([(int(row["n"]), int(row["d"])) for row in selected] ==
            list(ALL_SHAPES),
            "selected shape manifest order/content changed from the approved four-shape plan")
    require(len(rows) == len(ALL_SHAPES),
            "formal shape manifest must contain exactly four selected shapes")
    for row in selected:
        require(int(row["tile_size"]) == 4, "shape manifest tile size is not 4")
        require(int(row["merge_count"]) > 0, "shape has no real online merge")
    return rows


def derive_smu_status(implementation: str,
                      smu_status: dict[str, Any]) -> str:
    """Derive a truthful run-details status from the result counters."""
    if implementation == "software":
        return "not-launched"
    if smu_status.get("errors", 0):
        return "error"
    if smu_status.get("timeouts", 0):
        return "timeout"
    commands = smu_status.get("commands", 0)
    done = smu_status.get("done", 0)
    if commands > 0 and done == commands:
        return "done"
    return "incomplete"


def collector_contract_self_test() -> None:
    """Keep SMU completion from regressing to the software label."""
    completed = {"commands": 3, "done": 3, "errors": 0, "timeouts": 0}
    require(derive_smu_status("smu", completed) == "done",
            "completed SMU run must be labelled done")
    require(derive_smu_status("software", {
        "commands": 0, "done": 0, "errors": 0, "timeouts": 0,
    }) == "not-launched", "software run must be labelled not-launched")
    require(derive_smu_status("smu", {
        "commands": 3, "done": 2, "errors": 0, "timeouts": 1,
    }) == "timeout", "timed-out SMU run must be labelled timeout")


def import_anchor_tables() -> tuple[list[dict[str, Any]], list[dict[str, Any]],
                                     list[dict[str, Any]], list[dict[str, Any]]]:
    performance = read_rows(PHASE5_FORMAL / "native_merge_performance.csv")
    summaries = read_rows(PHASE5_FORMAL / "native_merge_summary.csv")
    attention = read_rows(PHASE5_FORMAL / "native_attention_performance.csv")
    numerical = read_rows(PHASE5_FORMAL / "numerical_agreement.csv")
    for n, d in ANCHORS:
        slug = f"N{n}_D{d}_S1"
        require(sum(row["case"] == slug for row in performance) == 2,
                f"Phase 5 performance does not contain exactly two rows for {slug}")
        require(sum(row["case"] == slug for row in summaries) == 1,
                f"Phase 5 summary does not contain {slug}")
        require(sum(row["case"] == slug for row in attention) == 1,
                f"Phase 5 core table does not contain {slug}")
        require(sum(row["case"] == slug for row in numerical) == 1,
                f"Phase 5 numerical table does not contain {slug}")
    return performance, summaries, attention, numerical


def anchor_summary_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    performance, summaries, attention, numerical = import_anchor_tables()
    by_case: dict[str, dict[str, dict[str, str]]] = {}
    for row in performance:
        if row["case"] in {f"N{n}_D{d}_S1" for n, d in ANCHORS}:
            by_case.setdefault(row["case"], {})[row["implementation"]] = row
    core_by_case = {row["case"]: row for row in attention}
    num_by_case = {row["case"]: row for row in numerical}
    rows: list[dict[str, Any]] = []
    numerical_rows: list[dict[str, Any]] = []
    for summary in summaries:
        case = summary["case"]
        if case not in by_case:
            continue
        n, d = (int(part[1:]) for part in case.split("_")[:2])
        sw = by_case[case]["software"]
        smu = by_case[case]["smu"]
        core = core_by_case[case]
        rows.append({
            "source_phase": "phase5_formal",
            "case": case, "n": n, "d": d, "tile_size": sw["tile_keys"],
            "tile_count": sw["tile_count"], "merge_count": sw["merge_count"],
            "sw_recurrence_cycles": sw["recurrence_cycles"],
            "smu_recurrence_cycles": smu["recurrence_cycles"],
            "recurrence_speedup": summary["recurrence_speedup"],
            "sw_merge_cycles": summary["software_merge_total"],
            "smu_merge_cycles": summary["smu_merge_total"],
            "merge_speedup": summary["merge_speedup"],
            "sw_core_cycles": core["software_native_attention"],
            "smu_core_cycles": core["smu_native_attention"],
            "core_speedup": core["speedup"],
            "sw_status": "pass", "smu_status": "pass",
            "smu_commands": smu["smu_commands"],
            "smu_done": smu["smu_done"],
            "smu_errors": "0", "smu_timeouts": "0",
        })
        numerical_rows.append({
            "source_phase": "phase5_formal", "case": case, "n": n, "d": d,
            "output_mae": num_by_case[case]["output_mae"],
            "stable_relative_error": num_by_case[case]["stable_relative_error"],
            "cosine_similarity": num_by_case[case]["cosine_similarity"],
            "no_nan": "1", "smu_done": "1", "smu_error": "0",
            "timeout": "0",
        })
    require(len(rows) == len(ANCHORS), "failed to import both Phase 5 anchor summaries")
    return rows, numerical_rows


def run_new_shapes(args: argparse.Namespace, output: Path,
                   manifest: dict[str, Any]) -> tuple[list[dict[str, Any]],
                                                       list[dict[str, Any]],
                                                       list[dict[str, Any]]]:
    build_dirs = {
        shape_slug(n, d, args.seed): args.build_root / shape_slug(n, d, args.seed)
        for n, d in NEW_SHAPES
    }
    for slug, build_dir in build_dirs.items():
        require(not build_dir.exists() or not any(build_dir.iterdir()),
                f"refusing stale build directory: {build_dir}")
    output.mkdir(parents=True, exist_ok=True)
    raw_dir = output / "raw"
    outputs_dir = output / "outputs"
    raw_dir.mkdir()
    outputs_dir.mkdir()
    details: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    numerical: list[dict[str, Any]] = []
    for n, d in NEW_SHAPES:
        slug = shape_slug(n, d, args.seed)
        build_dir = build_dirs[slug]
        build_dir.mkdir(parents=True, exist_ok=True)
        configure = p5.cmake_configure_command(args, build_dir, n, d)
        build = [
            "cmake", "--build", str(build_dir), "--target",
            *(TARGETS[implementation] for implementation in IMPLEMENTATIONS),
            "--", f"-j{args.jobs}",
        ]
        configure_log = raw_dir / f"{slug}_configure.log"
        build_log = raw_dir / f"{slug}_build.log"
        configure_started_at = timestamp()
        configure_rc = p5.run_logged(configure, configure_log, args.timeout)
        configure_completed_at = timestamp()
        require(configure_rc == 0, f"CMake configure failed for {slug}")
        build_started_at = timestamp()
        build_rc = p5.run_logged(build, build_log, args.timeout)
        build_completed_at = timestamp()
        require(build_rc == 0, f"CMake build failed for {slug}")
        header = build_dir / "spatzBenchmarks" / "phase5_generated" / slug / "phase5_case_data.h"
        require(header.is_file(), f"generated case header missing for {slug}")
        manifest["builds"].append({
            "case": slug, "build_dir": str(build_dir),
            "configure_command": p5.command_text(configure),
            "build_command": p5.command_text(build),
            "configure_log": str(configure_log.relative_to(output)),
            "configure_log_sha256": p5.sha256_file(configure_log),
            "configure_started_at": configure_started_at,
            "configure_completed_at": configure_completed_at,
            "build_log": str(build_log.relative_to(output)),
            "build_log_sha256": p5.sha256_file(build_log),
            "build_started_at": build_started_at,
            "build_completed_at": build_completed_at,
            "header": str(header), "header_sha256": p5.sha256_file(header),
        })
        save_manifest(output, manifest)
        runs: dict[str, dict[str, Any]] = {}
        for implementation in IMPLEMENTATIONS:
            elf = build_dir / "spatzBenchmarks" / TARGETS[implementation]
            require(elf.is_file(), f"ELF missing for {slug}/{implementation}")
            log_path = raw_dir / f"{slug}_{implementation}.log"
            command = [str(args.simulator), str(elf)]
            run_started_at = timestamp()
            return_code = p5.run_logged(command, log_path, args.timeout)
            run_completed_at = timestamp()
            require(return_code == 0, f"simulator failed for {slug}/{implementation}")
            result_records = p5.parse_prefixed_json(log_path, "PHASE5_RESULT ")
            fsm_records = p5.parse_prefixed_json(log_path, "OM_FSM ")
            require(len(result_records) == 1,
                    f"expected one PHASE5_RESULT for {slug}/{implementation}")
            output_n, output_d, output_bits = p5.parse_output_bits(log_path)
            require(output_n == n and output_d == d,
                    f"output shape mismatch for {slug}/{implementation}")
            weight_cycles = p5.validate_run(
                result_records[0], fsm_records, implementation, n, d, output_bits
            )
            output_path = outputs_dir / f"{slug}_{implementation}_output_bits.json"
            output_path.write_text(json.dumps({
                "case": slug, "implementation": implementation,
                "n": n, "d": d, "bits": output_bits,
            }, separators=(",", ":")) + "\n", encoding="utf-8")
            run = {
                "case": slug, "implementation": implementation,
                "return_code": return_code, "command": p5.command_text(command),
                "run_started_at": run_started_at,
                "run_completed_at": run_completed_at,
                "raw_log": str(log_path.relative_to(output)),
                "raw_log_sha256": p5.sha256_file(log_path),
                "output_bits": str(output_path.relative_to(output)),
                "elf": str(elf), "elf_sha256": p5.sha256_file(elf),
                "result": result_records[0], "om_fsm": fsm_records,
                "compute_weight_cycles_sum": weight_cycles,
            }
            manifest["runs"].append(run)
            save_manifest(output, manifest)
            runs[implementation] = run
            cycles = result_records[0]["cycles"]
            smu_status = result_records[0]["smu"]
            recurrence_key = (
                "software_recurrence" if implementation == "software"
                else "smu_recurrence"
            )
            details.append({
                "source_phase": "phase6_formal", "case": slug, "n": n, "d": d,
                "implementation": implementation, "tile_size": 4,
                "tile_count": result_records[0]["tile_count"],
                "merge_count": result_records[0]["merge_count"],
                "recurrence_cycles": cycles[recurrence_key],
                "merge_window_cycles": cycles["merge_window"],
                "core_cycles": cycles["total"],
                "smu_status": derive_smu_status(implementation, smu_status),
                "smu_commands": smu_status.get("commands", 0),
                "smu_done": smu_status.get("done", 0),
                "smu_errors": smu_status.get("errors", 0),
                "smu_timeouts": smu_status.get("timeouts", 0),
                "output_nonfinite": result_records[0]["output_nonfinite"],
                "timeout": smu_status.get("timeouts", 0),
            })
        sw = runs["software"]["result"]
        smu = runs["smu"]["result"]
        sw_cycles = sw["cycles"]
        smu_cycles = smu["cycles"]
        summaries.append({
            "source_phase": "phase6_formal", "case": slug, "n": n, "d": d,
            "tile_size": 4, "tile_count": sw["tile_count"],
            "merge_count": sw["merge_count"],
            "sw_recurrence_cycles": sw_cycles["software_recurrence"],
            "smu_recurrence_cycles": smu_cycles["smu_recurrence"],
            "recurrence_speedup": sw_cycles["software_recurrence"] /
            smu_cycles["smu_recurrence"],
            "sw_merge_cycles": sw_cycles["merge_total"],
            "smu_merge_cycles": smu_cycles["merge_total"],
            "merge_speedup": sw_cycles["merge_total"] /
            smu_cycles["merge_total"],
            "sw_core_cycles": sw_cycles["total"],
            "smu_core_cycles": smu_cycles["total"],
            "core_speedup": sw_cycles["total"] / smu_cycles["total"],
            "sw_status": sw["status"], "smu_status": smu["status"],
            "smu_commands": smu["smu"]["commands"],
            "smu_done": smu["smu"]["done"],
            "smu_errors": smu["smu"]["errors"],
            "smu_timeouts": smu["smu"]["timeouts"],
        })
        software_bits = json.loads(
            (output / runs["software"]["output_bits"]).read_text(encoding="utf-8")
        )["bits"]
        smu_bits = json.loads(
            (output / runs["smu"]["output_bits"]).read_text(encoding="utf-8")
        )["bits"]
        metrics = p5.pairwise_metrics(software_bits, smu_bits)
        numerical.append({
            "source_phase": "phase6_formal", "case": slug, "n": n, "d": d,
            **metrics, "no_nan": 1, "smu_done": smu["smu"]["done"],
            "smu_error": smu["smu"]["errors"],
            "timeout": smu["smu"]["timeouts"],
        })
    return summaries, numerical, details


def save_manifest(output: Path, manifest: dict[str, Any]) -> None:
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-formal", action="store_true",
                        help="run the two new shape pairs from a clean snapshot")
    parser.add_argument("--output", type=Path, default=SCRIPT_DIR / "formal")
    parser.add_argument("--build-root", type=Path,
                        default=ROOT / "work-artifacts" / "work-phase6-native-formal")
    parser.add_argument("--simulator", type=Path, default=DEFAULT_SIMULATOR)
    parser.add_argument("--llvm-path", type=Path, default=ROOT / "install/llvm")
    parser.add_argument("--gcc-path", type=Path,
                        default=ROOT / "install/riscv-gcc")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()

    p5.collector_self_test()
    collector_contract_self_test()
    rows = shape_manifest_rows()
    print("collector_self_test: PASS (0x7fc00000 rejected)")
    print("run_details_contract_test: PASS (completed SMU => done)")
    print("shape_manifest: N24/D64 and N16/D128 selected before formal collection")
    audit = p5.worktree_audit()
    if not args.execute_formal:
        print("PLAN ONLY: no simulator or build command was executed")
        print(json.dumps({
            "git": audit, "new_shapes": [
                {"n": n, "d": d, "tile_size": 4, "seed": args.seed}
                for n, d in NEW_SHAPES
            ],
            "shape_manifest_sha256": p5.sha256_file(SHAPE_MANIFEST),
        }, indent=2, sort_keys=True))
        return 0

    require(audit["clean_before_run"], "refusing formal run from dirty worktree")
    require(args.simulator.is_file(), f"missing simulator: {args.simulator}")
    require(not args.output.exists() or not any(args.output.iterdir()),
            "refusing non-empty formal output directory")
    require(not args.build_root.exists() or not any(args.build_root.iterdir()),
            "refusing stale formal build root")
    for row in rows:
        if (row.get("selected", "1") == "1" and
                row["shape_status"] == "PROVISIONAL_NEW_SHAPE"):
            raise ValueError("new shape is still provisional; freeze after Gate 1")
    compiler = {
        "c_compiler": p5.executable_provenance(
            "C compiler", args.llvm_path / "bin/clang"),
        "cxx_compiler": p5.executable_provenance(
            "C++ compiler", args.llvm_path / "bin/clang++"),
        "gcc_toolchain": p5.executable_provenance(
            "GCC toolchain", args.gcc_path / "bin/riscv32-unknown-elf-gcc"),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "phase6-p0-2-native-online-attention-generality-formal",
        "status": "in_progress",
        "collection_started_at": timestamp(),
        "collection_completed_at": None,
        "formal_collection_started": True,
        "git": audit,
        "simulator": {"path": str(args.simulator),
                       "sha256": p5.sha256_file(args.simulator)},
        "config": {
            "all_shapes": [{"n": n, "d": d, "seed": args.seed}
                           for n, d in ALL_SHAPES],
            "new_shapes": [{"n": n, "d": d, "seed": args.seed}
                           for n, d in NEW_SHAPES],
            "rejected_pre_result_candidates": list(
                REJECTED_PRE_RESULT_CANDIDATES
            ),
            "tile_size": 4, "smu_mode": 3,
            "compiler_flags": "-DPRINTF_DISABLE_SUPPORT_FLOAT",
            "cmake_cluster_config": "spatz_cluster.default.dram.hjson",
            "shape_manifest_sha256": p5.sha256_file(SHAPE_MANIFEST),
        },
        "phase5_anchor_sources": {
            str(path.relative_to(PHASE5_FORMAL)): p5.sha256_file(path)
            for path in (
                PHASE5_FORMAL / "native_merge_performance.csv",
                PHASE5_FORMAL / "native_merge_summary.csv",
                PHASE5_FORMAL / "native_attention_performance.csv",
                PHASE5_FORMAL / "numerical_agreement.csv",
                PHASE5_FORMAL / "om_fsm_breakdown.csv",
            ) if path.is_file()
        },
        "toolchain": {
            "llvm_path": str(args.llvm_path), "gcc_path": str(args.gcc_path),
            "python": args.python, "compiler": compiler,
        },
        "run_policy": {"jobs": args.jobs, "timeout_seconds": args.timeout,
                        "formal_runs": 4, "phase5_anchor_reruns": 0},
        "builds": [], "runs": [],
    }
    save_manifest(args.output, manifest)
    try:
        new_summaries, new_numerical, details = run_new_shapes(
            args, args.output, manifest
        )
        anchor_summaries, anchor_numerical = anchor_summary_rows()
        performance = anchor_summaries + new_summaries
        numerical = anchor_numerical + new_numerical
        fields = list(performance[0].keys())
        write_csv(args.output / "performance.csv", fields, performance)
        write_csv(args.output / "numerical_agreement.csv",
                  list(numerical[0].keys()), numerical)
        write_csv(args.output / "run_details.csv", list(details[0].keys()), details)
        trend = [{
            "N": row["n"], "D": row["d"], "tile_size": row["tile_size"],
            "merge_count": row["merge_count"],
            "recurrence_speedup": row["recurrence_speedup"],
            "merge_speedup": row["merge_speedup"],
            "core_speedup": row["core_speedup"],
        } for row in performance]
        write_csv(args.output / "performance_trend.csv", list(trend[0].keys()), trend)
        write_csv(args.output / "shape_manifest.csv",
                  list(rows[0].keys()), rows)
        old_fsm = read_rows(PHASE5_FORMAL / "om_fsm_breakdown.csv")
        fsm_fields = ["source_phase", *[field for field in old_fsm[0]
                                         if field != "source_phase"]]
        fsm_rows = [{"source_phase": "phase5_formal", **row} for row in old_fsm]
        for run in manifest["runs"]:
            if run["implementation"] != "smu":
                continue
            for invocation, record in enumerate(run["om_fsm"]):
                fsm_rows.append({
                    "source_phase": "phase6_formal", "case": run["case"],
                    "implementation": "smu", "invocation": invocation, **record,
                })
        write_csv(args.output / "om_fsm_breakdown.csv", fsm_fields, fsm_rows)
        manifest["status"] = "complete"
        manifest["collection_completed_at"] = timestamp()
        manifest["artifacts"] = [
            "performance.csv", "performance_trend.csv",
            "numerical_agreement.csv", "run_details.csv", "shape_manifest.csv",
            "om_fsm_breakdown.csv", "manifest.json",
        ]
        save_manifest(args.output, manifest)
    except Exception:
        manifest["status"] = "failed"
        save_manifest(args.output, manifest)
        raise
    print(f"formal workload-generality collection complete: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
