#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Capture bounded B2-R/B3 RTL VCD activity windows."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import run_experiments as common

WINDOW_PATTERN = re.compile(
    r"^SNITCH_TRACE_WINDOW index=(\d+) event=(start|end) time=(\d+)$",
    re.MULTILINE,
)
IMPLEMENTATIONS = ("B2-R", "B3")
MANDATORY_CASES = ((1, 1), (8, 32), (16, 64))
TRACE_DEFINITION = ("ONLINE_MERGE_TRACE_PROXY", "1")
UINT32_MASK = (1 << 32) - 1


def uint64_from_words(high: Any, low: Any) -> int:
    return ((int(high) & UINT32_MASK) << 32) | (int(low) & UINT32_MASK)


def parse_case(value: str) -> common.Case:
    parts = value.split(",")
    if not 2 <= len(parts) <= 3:
        raise argparse.ArgumentTypeError("case must be N,D[,timeout-seconds]")
    try:
        case = common.Case(
            n=int(parts[0]),
            d=int(parts[1]),
            seed=1,
            case_kind="main",
            repeats=3,
            timeout_seconds=int(parts[2]) if len(parts) == 3 else None,
        )
        common.validate_case(case)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    return case


def parse_trace_windows(output: str) -> tuple[list[dict[str, Any]], list[str]]:
    events = [
        {"index": int(index), "event": event, "time": int(time)}
        for index, event, time in WINDOW_PATTERN.findall(output)
    ]
    errors: list[str] = []
    expected = [
        {"index": 0, "event": "start"},
        {"index": 0, "event": "end"},
        {"index": 1, "event": "start"},
        {"index": 1, "event": "end"},
    ]
    if [
        {"index": event["index"], "event": event["event"]}
        for event in events
    ] != expected:
        errors.append("expected exactly two ordered start/end trace windows")
        return [], errors

    windows = []
    for index, implementation in enumerate(IMPLEMENTATIONS):
        start = events[2 * index]["time"]
        end = events[2 * index + 1]["time"]
        if end <= start:
            errors.append(f"trace window {index} has non-positive span")
        windows.append(
            {
                "index": index,
                "implementation": implementation,
                "repeat": 0,
                "start_time": start,
                "end_time": end,
                "marker_span_half_cycles": end - start,
            }
        )
    if len(windows) == 2 and windows[1]["start_time"] <= windows[0]["end_time"]:
        errors.append("trace windows overlap or are not strictly ordered")
    return windows, errors


def validate_target_records(
    output: str, case: common.Case
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records, target_failures, parse_errors = common.parse_target_output(output)
    errors = list(parse_errors)
    errors.extend(common.validate_record_set(records, case))
    if target_failures:
        errors.extend(
            {"kind": "target_failure", "record": record}
            for record in target_failures
        )
    if any(record.get("status") != "pass" for record in records):
        errors.append({"kind": "non_passing_target_record"})
    return records, errors


def vcd_header_valid(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    with path.open("rb") as stream:
        while stream.tell() < 64 * 1024 * 1024:
            line = stream.readline()
            if not line:
                return False
            if line.lstrip().startswith(b"$enddefinitions"):
                return True
    return False


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    script = Path(__file__).resolve()
    root = script.parents[2]
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument(
        "--source-dir", type=Path, default=root / "hw/system/spatz_cluster/sw"
    )
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--simulator", type=Path, required=True)
    parser.add_argument("--simulator-source-dir", type=Path, default=root)
    parser.add_argument(
        "--cfg",
        type=Path,
        default=root
        / "hw/system/spatz_cluster/cfg/spatz_cluster.default.dram.hjson",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=root.parent / f"work-online-merge-toggle-{timestamp}",
    )
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--build-timeout-seconds", type=int, default=900)
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--cmake-define", action="append", default=[])
    parser.add_argument(
        "--objdump",
        type=Path,
        default=root / "install/llvm/bin/llvm-objdump",
    )
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--require-clean", action="store_true")
    return parser.parse_args(argv)


def source_identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "git_commit": common.git_output(path, "rev-parse", "HEAD"),
        "git_dirty": bool(common.git_output(path, "status", "--porcelain")),
    }


def persist(
    work_dir: Path,
    captures: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    commands: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> None:
    common.write_json(work_dir / "capture_records.json", captures)
    common.write_json(work_dir / "failures.json", failures)
    common.write_json(work_dir / "commands.json", commands)
    common.write_json(work_dir / "artifact_manifest.json", artifacts)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    source_dir = args.source_dir.resolve()
    build_dir = args.build_dir.resolve()
    simulator = args.simulator.resolve()
    simulator_source = args.simulator_source_dir.resolve()
    cfg = args.cfg.resolve()
    work_dir = args.work_dir.resolve()
    objdump = args.objdump.resolve()

    try:
        common.validate_work_dir(work_dir, repo_root)
        definitions = common.parse_cmake_defines(args.cmake_define)
        if any(key == TRACE_DEFINITION[0] for key, _ in definitions):
            raise ValueError("ONLINE_MERGE_TRACE_PROXY is owned by this runner")
        definitions.append(TRACE_DEFINITION)
        cases = [parse_case(value) for value in args.case]
        if not cases:
            cases = [common.Case(n, d, repeats=3) for n, d in MANDATORY_CASES]
        if len({(case.n, case.d) for case in cases}) != len(cases):
            raise ValueError("duplicate cases are not allowed")
        if args.timeout_seconds <= 0 or args.build_timeout_seconds <= 0:
            raise ValueError("timeouts must be positive")
        if args.jobs <= 0:
            raise ValueError("jobs must be positive")
    except (ValueError, argparse.ArgumentTypeError) as error:
        raise SystemExit(f"invalid toggle capture request: {error}") from error

    if not cfg.is_file() or not simulator.is_file():
        raise SystemExit("CFG and simulator must both exist")
    repo_identity = source_identity(repo_root)
    simulator_identity = source_identity(simulator_source)
    if args.require_clean and (
        repo_identity["git_dirty"] or simulator_identity["git_dirty"]
    ):
        raise SystemExit("formal toggle capture requires clean source trees")
    if repo_identity["git_commit"] != simulator_identity["git_commit"]:
        raise SystemExit(
            "simulator source commit does not match capture source"
        )

    work_dir.mkdir(parents=True, exist_ok=False)
    git_commit = str(repo_identity["git_commit"])
    cfg_hash = common.sha256_file(cfg)
    tool_versions = common.detect_tool_versions(
        repo_root, simulator, build_dir, args.cmake, objdump
    )
    tool_version = json.dumps(
        tool_versions, sort_keys=True, separators=(",", ":")
    )
    metadata = {
        "git_commit": git_commit,
        "git_dirty": bool(repo_identity["git_dirty"]),
        "cfg_path": common.display_path(cfg, repo_root),
        "cfg_hash": cfg_hash,
        "tool_version": tool_version,
    }
    captures: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    for source, workload, window in (
        (cfg, "all", "fixed cluster configuration"),
        (simulator, "all", "trace-capable Verilator simulator"),
    ):
        artifacts.append(
            common.artifact_entry(
                source,
                repo_root,
                git_commit,
                cfg_hash,
                tool_version,
                workload,
                window,
            )
        )

    elf = (
        build_dir
        / "spatzBenchmarks/test-spatzBenchmarks-online-softmax-merge"
    )
    for case in cases:
        case_dir = work_dir / case.slug
        case_dir.mkdir(parents=True)
        status = "pass"
        case_failures: list[dict[str, Any]] = []
        configure = common.make_configure_argv(
            args.cmake, source_dir, build_dir, case, definitions
        )
        command, _ = common.run_command(
            configure,
            case_dir / "configure.log",
            args.build_timeout_seconds,
            repo_root,
        )
        commands.append(asdict(command))
        status = command.status
        if status != "pass":
            case_failures.append(
                {
                    "kind": "configure_command",
                    "status": status,
                    "returncode": command.returncode,
                }
            )
        if status == "pass":
            command, _ = common.run_command(
                [
                    args.cmake,
                    "--build",
                    str(build_dir),
                    "--target",
                    "test-spatzBenchmarks-online-softmax-merge",
                    "--parallel",
                    str(args.jobs),
                ],
                case_dir / "build.log",
                args.build_timeout_seconds,
                repo_root,
            )
            commands.append(asdict(command))
            status = command.status
            if status != "pass":
                case_failures.append(
                    {
                        "kind": "build_command",
                        "status": status,
                        "returncode": command.returncode,
                    }
                )

        case_elf = case_dir / "online-softmax-merge.elf"
        if status == "pass" and elf.is_file():
            shutil.copy2(elf, case_elf)
            command, gate_error = common.run_rvv_disassembly_gate(
                objdump,
                case_elf,
                case_dir / "rvv_objdump.log",
                case_dir / "online_merge_rvv_update.disasm",
                args.build_timeout_seconds,
                case_dir,
            )
            commands.append(asdict(command))
            if gate_error is not None:
                status = "tool_error"
                case_failures.append(
                    {"kind": "rvv_disassembly_gate", "message": gate_error}
                )
        elif status == "pass":
            status = "tool_error"
            case_failures.append(
                {"kind": "missing_target_elf", "path": str(elf)}
            )

        vcd = case_dir / "activity.vcd"
        target_records: list[dict[str, Any]] = []
        windows: list[dict[str, Any]] = []
        if status == "pass":
            timeout = case.timeout_seconds or args.timeout_seconds
            environment = {
                "SNITCH_TRACE": "1",
                "SNITCH_TRACE_GATE": "1",
                "SNITCH_TRACE_FILE": str(vcd),
            }
            command, output = common.run_command(
                [str(simulator), str(case_elf)],
                case_dir / "simulator.log",
                timeout,
                case_dir,
                environment,
            )
            command_record = asdict(command)
            command_record["environment"] = environment
            commands.append(command_record)
            status = command.status
            if status != "pass":
                case_failures.append(
                    {
                        "kind": "simulator_command",
                        "status": status,
                        "returncode": command.returncode,
                        "timeout_seconds": timeout,
                    }
                )
            target_records, record_errors = validate_target_records(
                output, case
            )
            windows, window_errors = parse_trace_windows(output)
            case_failures.extend(record_errors)
            case_failures.extend(
                {"kind": "trace_window_gate", "message": error}
                for error in window_errors
            )
            if not vcd_header_valid(vcd):
                case_failures.append({"kind": "missing_or_invalid_vcd"})
            if status == "pass" and case_failures:
                status = "tool_error"

        cycles = {
            str(record.get("implementation")): uint64_from_words(
                record.get("cycles_hi", 0), record.get("cycles_lo", 0)
            )
            for record in target_records
            if record.get("repeat") == 0
            and record.get("implementation") in IMPLEMENTATIONS
        }
        for window in windows:
            window["target_cycles"] = cycles.get(window["implementation"])
        capture = {
            **metadata,
            "N": case.n,
            "D": case.d,
            "seed": case.seed,
            "repeats": case.repeats,
            "elements": case.n * case.d,
            "status": status,
            "target_record_count": len(target_records),
            "windows": windows,
            "vcd_path": str(vcd),
            "vcd_size_bytes": vcd.stat().st_size if vcd.is_file() else None,
            "vcd_sha256": common.sha256_file(vcd) if vcd.is_file() else None,
            "elf_path": str(case_elf),
            "elf_sha256": (
                common.sha256_file(case_elf) if case_elf.is_file() else None
            ),
        }
        captures.append(capture)
        for failure in case_failures:
            failure.update(metadata)
            failure.update({"N": case.n, "D": case.d})
            failures.append(failure)
        for path, label in (
            (case_dir / "configure.log", "target configure log"),
            (case_dir / "build.log", "target build log"),
            (case_dir / "rvv_objdump.log", "RVV disassembly gate"),
            (
                case_dir / "online_merge_rvv_update.disasm",
                "RVV instruction snippet",
            ),
            (case_dir / "simulator.log", "simulator output and trace markers"),
            (case_elf, "exact target ELF"),
            (vcd, "probe-gated RTL VCD"),
        ):
            if path.is_file():
                artifacts.append(
                    common.artifact_entry(
                        path,
                        repo_root,
                        git_commit,
                        cfg_hash,
                        tool_version,
                        case.slug,
                        label,
                    )
                )
        persist(work_dir, captures, failures, commands, artifacts)

    observed_cases = {(row["N"], row["D"]) for row in captures}
    complete = (
        observed_cases == set(MANDATORY_CASES)
        and all(row["status"] == "pass" for row in captures)
        and not failures
        and not repo_identity["git_dirty"]
        and not simulator_identity["git_dirty"]
    )
    manifest = {
        **metadata,
        "objective": "bounded representative RTL VCD toggle-proxy capture",
        "simulator_source": simulator_identity,
        "tool_versions": tool_versions,
        "cases": [asdict(case) for case in cases],
        "mandatory_cases": [list(case) for case in MANDATORY_CASES],
        "cmake_definitions": common.cmake_define_manifest(definitions),
        "capture_protocol": {
            "windows": ["B2-R repeat 0", "B3 repeat 0"],
            "trace_gate": "cluster_probe_o",
            "vcd_initial_values_are_not_toggles": True,
            "host_process_group_timeout": True,
        },
        "toggle_proxy_evidence": complete,
        "physical_power_energy_supported": False,
        "claim_boundary": (
            "zero-delay RTL bit-toggle proxy; no glitch, cell-internal, "
            "parasitic, clock-tree, leakage, voltage, or physical PPA model"
        ),
        "validation_result": {
            "statuses": sorted({row["status"] for row in captures}),
            "capture_count": len(captures),
            "failure_count": len(failures),
        },
        "artifact_index": "artifact_manifest.json",
        "exact_commands": "commands.json",
    }
    common.write_json(work_dir / "run_manifest.json", manifest)
    return 0 if all(row["status"] == "pass" for row in captures) else 1


if __name__ == "__main__":
    raise SystemExit(main())
