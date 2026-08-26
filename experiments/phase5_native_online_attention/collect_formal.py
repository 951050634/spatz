#!/usr/bin/env python3
"""Collect the four clean-snapshot Phase 5 runs.

The collector is plan-only unless ``--execute-formal`` is supplied.  Execution
refuses a dirty worktree and a non-empty output directory, so an existing
Phase 4 experiment cannot be overwritten accidentally.  It archives the
complete raw logs and final FP32 output bits before computing direct
software-to-SMU numerical metrics in host float64 arithmetic.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shlex
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIMULATOR = Path("/home/wxt/work-phase4-recip-sim/spatz_cluster.vlt")
DEFAULT_LLVM = ROOT / "install" / "llvm"
DEFAULT_GCC = ROOT / "install" / "riscv-gcc"
ANCHORS = ((8, 32), (16, 64))
IMPLEMENTATIONS = ("software", "smu")
TARGETS = {
    "software": "test-spatzBenchmarks-native-online-attention-software",
    "smu": "test-spatzBenchmarks-native-online-attention-smu",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_text(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def worktree_audit() -> dict[str, Any]:
    status = git_text("status", "--short")
    return {
        "clean_before_run": not bool(status),
        "status_short": status.splitlines() if status else [],
        "diff_stat": git_text("diff", "--stat"),
        "phase4_dirty_entries": [
            line for line in status.splitlines()
            if "phase4" in line.lower() or "quantized-attention" in line
        ],
        "commit": git_text("rev-parse", "HEAD"),
    }


def command_text(command: Iterable[str]) -> str:
    return shlex.join(str(part) for part in command)


def run_logged(command: list[str], log_path: Path, timeout: int | None) -> int:
    with log_path.open("w", encoding="utf-8") as stream:
        try:
            completed = subprocess.run(
                command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            return 124
    return completed.returncode


def parse_prefixed_json(log_path: Path, prefix: str) -> list[dict[str, Any]]:
    records = []
    decoder = json.JSONDecoder()
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            payload = line[len(prefix):].lstrip()
            record, _ = decoder.raw_decode(payload)
            records.append(record)
    return records


def parse_output_bits(log_path: Path) -> tuple[int, int, list[int]]:
    chunks = parse_prefixed_json(log_path, "PHASE5_OUTPUT_CHUNK ")
    if chunks:
        n = chunks[0]["n"]
        d = chunks[0]["d"]
        ordered = sorted(chunks, key=lambda record: record["offset"])
        bits: list[int] = []
        for record in ordered:
            require(record["n"] == n and record["d"] == d,
                    "output chunk shape mismatch")
            require(record["offset"] == len(bits),
                    "output chunks are missing or out of order")
            bits.extend(record["bits"])
        require(len(bits) == n * d, "output chunks do not cover N x D")
        validate_bit_vector(bits)
        return n, d, bits

    # Parse the compact one-line diagnostic emitted by current formal builds.
    # Keep the chunk parser above so older smoke logs remain inspectable.
    records = parse_prefixed_json(log_path, "PHASE5_OUTPUT ")
    require(len(records) == 1, "expected output bits")
    record = records[0]
    bits = record["bits"]
    validate_bit_vector(bits)
    return record["n"], record["d"], bits


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_bit_vector(bits: list[int]) -> None:
    require(isinstance(bits, list), "output bits are not a list")
    for index, value in enumerate(bits):
        require(isinstance(value, int) and not isinstance(value, bool),
                f"output bit {index} is not an integer")
        require(0 <= value <= 0xffffffff,
                f"output bit {index} is outside uint32 range")


def validate_run(
    result: dict[str, Any], fsm: list[dict[str, Any]],
    implementation: str, n: int, d: int, output_bits: list[int],
) -> int:
    merge_count = n // 4 - 1
    require(result.get("status") == "pass", "target did not report pass")
    require(result.get("n") == n and result.get("d") == d,
            "result shape does not match requested anchor")
    require(result.get("tile_keys") == 4, "unexpected tile width")
    require(result.get("merge_count") == merge_count,
            "result merge_count does not match anchor")
    require(result.get("output_nonfinite") == 0, "non-finite target output")
    require(len(output_bits) == n * d, "final output bit count mismatch")

    smu_status = result["smu"]
    cycles = result["cycles"]
    require(cycles["merge_total"] == cycles["merge_window"],
            "merge_total is not the outer per-merge window")
    recurrence_key = (
        "software_recurrence" if implementation == "software"
        else "smu_recurrence"
    )
    recurrence = cycles[recurrence_key]
    require(
        cycles["merge_window"] ==
        recurrence + cycles["rvv_output_update"] +
        cycles["merge_orchestration"],
        "merge window does not equal recurrence + RVV + orchestration",
    )
    require(
        cycles["total"] == cycles["score_compute"] +
        cycles["tile_local_state"] + cycles["merge_window"] +
        cycles["core_residual"] + cycles["output_copy"],
        "core cycle breakdown does not add to total",
    )

    if implementation == "software":
        require(cycles["software_recurrence_calls"] == merge_count,
                "software recurrence call count mismatch")
        require(smu_status["commands"] == 0 and smu_status["done"] == 0,
                "software path unexpectedly launched SMU")
    else:
        require(smu_status["commands"] == merge_count and
                smu_status["done"] == merge_count,
                "SMU command/done count mismatch")
        require(smu_status["errors"] == 0 and smu_status["timeouts"] == 0,
                "SMU error or timeout reported")
        require(len(fsm) == merge_count,
                "OM_FSM record count does not equal merge_count")
        for invocation, record in enumerate(fsm):
            for field in (
                "schema_version", "invocation", "N", "D", "mode",
                "terminal_state", "load_scalar_cycles",
                "compute_scalar_cycles", "compute_weight_cycles",
                "store_scalar_cycles", "update_vector_cycles", "busy_cycles",
            ):
                require(field in record,
                        f"OM_FSM record is missing {field}")
            require(record["N"] == n and record["D"] == d,
                    "OM_FSM shape does not match anchor")
            require(record["invocation"] == invocation,
                    "OM_FSM invocation sequence is not 0..merge_count-1")
            require(record["mode"] == 3 and record["terminal_state"] == "DONE",
                    "OM_FSM mode/state mismatch")
            require(record["update_vector_cycles"] == 0,
                    "mode 3 unexpectedly entered vector update")

    if implementation == "smu":
        require(cycles["smu_recurrence"] == cycles["smu_breakdown_sum"],
                "SMU recurrence does not equal setup + wait")
        require(cycles["smu_breakdown_delta"] == 0 and
                cycles["smu_breakdown_exact"] == 1,
                "SMU timing additivity flag is not exact")
    else:
        require(cycles["smu_setup"] == 0 and cycles["smu_wait"] == 0 and
                cycles["smu_breakdown_sum"] == 0 and
                cycles["smu_breakdown_delta"] == 0,
                "software path has non-zero SMU timing fields")
    return sum(record["compute_weight_cycles"] for record in fsm)


def bits_to_float64(bits: list[int]) -> list[float]:
    validate_bit_vector(bits)
    values = []
    for index, value in enumerate(bits):
        decoded = float(struct.unpack("<f", struct.pack("<I", value))[0])
        require(math.isfinite(decoded),
                f"decoded output bit {index} is not finite")
        values.append(decoded)
    return values


def pairwise_metrics(software_bits: list[int], smu_bits: list[int]) -> dict[str, float]:
    require(len(software_bits) == len(smu_bits),
            "software/SMU output lengths differ")
    require(len(software_bits) > 0, "empty output vectors")
    software = bits_to_float64(software_bits)
    smu = bits_to_float64(smu_bits)
    differences = [abs(lhs - rhs) for lhs, rhs in zip(software, smu)]
    mae = sum(differences) / float(len(differences))
    denominator = max(sum(abs(value) for value in software), 1.0e-12)
    stable_relative_error = sum(differences) / denominator
    dot = sum(lhs * rhs for lhs, rhs in zip(software, smu))
    software_norm = math.sqrt(sum(value * value for value in software))
    smu_norm = math.sqrt(sum(value * value for value in smu))
    cosine = 1.0 if software_norm == 0.0 and smu_norm == 0.0 else (
        dot / (software_norm * smu_norm)
        if software_norm != 0.0 and smu_norm != 0.0 else 0.0
    )
    metrics = {
        "output_mae": mae,
        "stable_relative_error": stable_relative_error,
        "cosine_similarity": cosine,
    }
    for name, value in metrics.items():
        require(math.isfinite(value), f"{name} is not finite")
    return metrics


def collector_self_test() -> None:
    """Reject an injected quiet-NaN FP32 encoding before any collection."""
    try:
        pairwise_metrics([0x7fc00000], [0x3f800000])
    except ValueError:
        return
    raise RuntimeError("collector self-test accepted 0x7fc00000")


def executable_provenance(label: str, path: Path) -> dict[str, str]:
    resolved = path.resolve()
    require(resolved.is_file(), f"{label} executable does not exist: {resolved}")
    version_command = [str(resolved), "--version"]
    completed = subprocess.run(
        version_command, cwd=ROOT, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10,
    )
    require(completed.returncode == 0,
            f"{label} --version failed with {completed.returncode}")
    return {
        "path": str(resolved),
        "version_command": command_text(version_command),
        "version": completed.stdout.rstrip(),
        "sha256": sha256_file(resolved),
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def cmake_configure_command(args: argparse.Namespace, build_dir: Path,
                            n: int, d: int) -> list[str]:
    return [
        "cmake", "-S", str(ROOT / "hw/system/spatz_cluster/sw"),
        "-B", str(build_dir),
        f"-DLLVM_PATH={args.llvm_path}", f"-DGCC_PATH={args.gcc_path}",
        f"-DPYTHON={args.python}", "-DBUILD_TESTS=ON",
        f"-DSNITCH_SIMULATOR={args.simulator}",
        "-DSPATZ_CLUSTER_CFG=spatz_cluster.default.dram.hjson",
        f"-DPHASE5_N={n}", f"-DPHASE5_D={d}",
        f"-DPHASE5_SEED={args.seed}", "-DPHASE5_DUMP_OUTPUT=1",
        "-DCMAKE_C_FLAGS=-DPRINTF_DISABLE_SUPPORT_FLOAT",
        "-DMEM_DRAM_ORIGIN=2147483648", "-DMEM_DRAM_SIZE=2147483648",
        "-DSNRT_BASE_HARTID=0", "-DSNRT_CLUSTER_CORE_NUM=2",
        "-DSNRT_TCDM_START_ADDR=1048576", "-DSNRT_CLUSTER_OFFSET=0",
        "-DSNRT_TCDM_SIZE=131072", "-DSNRT_NFPU_PER_CORE=4", "-DELEN=64",
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-formal", action="store_true",
                        help="run only from a clean approved snapshot")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "experiments/phase5_native_online_attention/formal")
    parser.add_argument("--build-root", type=Path,
                        default=ROOT.parent / "work-phase5-formal")
    parser.add_argument("--simulator", type=Path, default=DEFAULT_SIMULATOR)
    parser.add_argument("--llvm-path", type=Path, default=DEFAULT_LLVM)
    parser.add_argument("--gcc-path", type=Path, default=DEFAULT_GCC)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    collector_self_test()
    print("collector_self_test: PASS (0x7fc00000 rejected)")
    audit = worktree_audit()
    if not args.execute_formal:
        print("PLAN ONLY: no simulator or build command was executed")
        print(json.dumps({"git": audit, "anchors": ANCHORS}, indent=2))
        return 0

    require(audit["clean_before_run"],
            "refusing formal run: worktree is dirty; audit Phase 4 first")
    require(args.simulator.is_file(), "simulator does not exist")
    require(not args.output.exists() or not any(args.output.iterdir()),
            "refusing formal run: output directory is not empty")
    build_dirs = {
        f"N{n}_D{d}_S{args.seed}": args.build_root / f"N{n}_D{d}_S{args.seed}"
        for n, d in ANCHORS
    }
    for slug, build_dir in build_dirs.items():
        require(not build_dir.exists() or not any(build_dir.iterdir()),
                f"refusing stale build directory: {build_dir}")
    compiler = {
        "c_compiler": executable_provenance(
            "C compiler", args.llvm_path / "bin" / "clang"),
        "cxx_compiler": executable_provenance(
            "C++ compiler", args.llvm_path / "bin" / "clang++"),
        "gcc_toolchain": executable_provenance(
            "GCC toolchain", args.gcc_path / "bin" /
            "riscv32-unknown-elf-gcc"),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "raw").mkdir()
    (args.output / "outputs").mkdir()
    simulator_hash = sha256_file(args.simulator)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "phase5-native-online-attention-formal",
        "status": "in_progress",
        "git": audit,
        "simulator": {"path": str(args.simulator),
                       "sha256": simulator_hash},
        "config": {
            "anchors": [{"n": n, "d": d, "seed": args.seed}
                        for n, d in ANCHORS],
            "tile_keys": 4,
            "compiler_flags": "-DPRINTF_DISABLE_SUPPORT_FLOAT",
            "cmake_cluster_config": "spatz_cluster.default.dram.hjson",
        },
        "toolchain": {
            "llvm_path": str(args.llvm_path),
            "gcc_path": str(args.gcc_path),
            "python": args.python,
        },
        "compiler": compiler,
        "run_policy": {"jobs": args.jobs, "timeout_seconds": args.timeout},
        "builds": [],
        "runs": [],
    }

    def save_manifest() -> None:
        (args.output / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    save_manifest()
    by_case: dict[str, dict[str, dict[str, Any]]] = {}
    fsm_rows: list[dict[str, Any]] = []
    try:
        for n, d in ANCHORS:
            slug = f"N{n}_D{d}_S{args.seed}"
            build_dir = build_dirs[slug]
            build_dir.mkdir(parents=True, exist_ok=True)
            configure = cmake_configure_command(args, build_dir, n, d)
            build = [
                "cmake", "--build", str(build_dir),
                "--target", *(TARGETS[implementation]
                               for implementation in IMPLEMENTATIONS),
                "--", f"-j{args.jobs}",
            ]
            configure_log = args.output / "raw" / f"{slug}_configure.log"
            build_log = args.output / "raw" / f"{slug}_build.log"
            configure_rc = run_logged(configure, configure_log, args.timeout)
            require(configure_rc == 0, "CMake configure failed")
            build_rc = run_logged(build, build_log, args.timeout)
            require(build_rc == 0, "CMake build failed")
            manifest["builds"].append({
                "case": slug,
                "build_dir": str(build_dir),
                "configure_command": command_text(configure),
                "build_command": command_text(build),
                "configure_log": str(configure_log.relative_to(args.output)),
                "configure_log_sha256": sha256_file(configure_log),
                "build_log": str(build_log.relative_to(args.output)),
                "build_log_sha256": sha256_file(build_log),
            })
            save_manifest()

            header = build_dir / "spatzBenchmarks" / "phase5_generated" / slug / "phase5_case_data.h"
            require(header.is_file(), "generated Phase 5 header is missing")
            case_results: dict[str, dict[str, Any]] = {}
            for implementation in IMPLEMENTATIONS:
                elf = build_dir / "spatzBenchmarks" / TARGETS[implementation]
                require(elf.is_file(), f"ELF missing: {elf}")
                log_path = args.output / "raw" / f"{slug}_{implementation}.log"
                run_command = [str(args.simulator), str(elf)]
                return_code = run_logged(run_command, log_path, args.timeout)
                require(return_code == 0,
                        f"simulator failed for {slug}/{implementation}")
                result_records = parse_prefixed_json(log_path, "PHASE5_RESULT ")
                fsm_records = parse_prefixed_json(log_path, "OM_FSM ")
                require(len(result_records) == 1,
                        "expected exactly one PHASE5_RESULT")
                output_n, output_d, output_bits = parse_output_bits(log_path)
                require(output_n == n and output_d == d,
                        "output bit header does not match anchor")
                weight_cycles = validate_run(
                    result_records[0], fsm_records, implementation,
                    n, d, output_bits,
                )
                output_path = args.output / "outputs" / f"{slug}_{implementation}_output_bits.json"
                output_path.write_text(
                    json.dumps({"case": slug, "implementation": implementation,
                                "n": n, "d": d, "bits": output_bits},
                               separators=(",", ":")) + "\n",
                    encoding="utf-8",
                )
                run_record = {
                    "case": slug,
                    "implementation": implementation,
                    "return_code": return_code,
                    "command": command_text(run_command),
                    "raw_log": str(log_path.relative_to(args.output)),
                    "raw_log_sha256": sha256_file(log_path),
                    "output_bits": str(output_path.relative_to(args.output)),
                    "elf": str(elf),
                    "elf_sha256": sha256_file(elf),
                    "header": str(header),
                    "header_sha256": sha256_file(header),
                    "result": result_records[0],
                    "om_fsm": fsm_records,
                    "compute_weight_cycles_sum": weight_cycles,
                }
                manifest["runs"].append(run_record)
                case_results[implementation] = run_record
                for invocation, record in enumerate(fsm_records):
                    fsm_rows.append({"case": slug, "implementation": implementation,
                                     "invocation": invocation, **record})
                save_manifest()
            by_case[slug] = case_results

        performance_fields = [
            "case", "implementation", "n", "d", "tile_keys", "tile_count",
            "merge_count", "score_compute_cycles", "tile_local_state_cycles",
            "recurrence_cycles", "rvv_output_update_cycles",
            "merge_orchestration_cycles", "merge_window_cycles",
            "core_residual_cycles", "output_copy_cycles", "merge_total_cycles",
            "total_cycles", "smu_setup_cycles", "smu_wait_cycles",
            "smu_breakdown_sum_cycles", "smu_breakdown_delta_cycles",
            "software_recurrence_calls", "smu_commands", "smu_done",
            "smu_compute_weight_cycles",
        ]
        performance_rows = []
        summary_rows = []
        attention_rows = []
        numerical_rows = []
        for slug, implementations in by_case.items():
            n, d = (int(part[1:]) for part in slug.split("_")[:2])
            values = {}
            for implementation, run_record in implementations.items():
                result = run_record["result"]
                cycles = result["cycles"]
                recurrence_key = (
                    "software_recurrence" if implementation == "software"
                    else "smu_recurrence"
                )
                values[implementation] = cycles
                performance_rows.append({
                    "case": slug, "implementation": implementation, "n": n,
                    "d": d, "tile_keys": result["tile_keys"],
                    "tile_count": result["tile_count"],
                    "merge_count": result["merge_count"],
                    "score_compute_cycles": cycles["score_compute"],
                    "tile_local_state_cycles": cycles["tile_local_state"],
                    "recurrence_cycles": cycles[recurrence_key],
                    "rvv_output_update_cycles": cycles["rvv_output_update"],
                    "merge_orchestration_cycles": cycles["merge_orchestration"],
                    "merge_window_cycles": cycles["merge_window"],
                    "core_residual_cycles": cycles["core_residual"],
                    "output_copy_cycles": cycles["output_copy"],
                    "merge_total_cycles": cycles["merge_total"],
                    "total_cycles": cycles["total"],
                    "smu_setup_cycles": cycles["smu_setup"],
                    "smu_wait_cycles": cycles["smu_wait"],
                    "smu_breakdown_sum_cycles": cycles["smu_breakdown_sum"],
                    "smu_breakdown_delta_cycles": cycles["smu_breakdown_delta"],
                    "software_recurrence_calls": cycles["software_recurrence_calls"],
                    "smu_commands": cycles["smu_commands"],
                    "smu_done": result["smu"]["done"],
                    "smu_compute_weight_cycles": run_record["compute_weight_cycles_sum"],
                })
            software = values["software"]
            smu = values["smu"]
            summary_rows.append({
                "case": slug,
                "software_recurrence": software["software_recurrence"],
                "smu_recurrence": smu["smu_recurrence"],
                "recurrence_speedup": software["software_recurrence"] /
                smu["smu_recurrence"],
                "software_merge_total": software["merge_total"],
                "smu_merge_total": smu["merge_total"],
                "merge_speedup": software["merge_total"] /
                smu["merge_total"],
            })
            attention_rows.append({
                "case": slug,
                "software_native_attention": software["total"],
                "smu_native_attention": smu["total"],
                "speedup": software["total"] / smu["total"],
            })
            software_bits = json.loads(
                (args.output / implementations["software"]["output_bits"])
                .read_text(encoding="utf-8")
            )["bits"]
            smu_bits = json.loads(
                (args.output / implementations["smu"]["output_bits"])
                .read_text(encoding="utf-8")
            )["bits"]
            numerical_rows.append({"case": slug, **pairwise_metrics(
                software_bits, smu_bits,
            )})

        write_csv(args.output / "native_merge_performance.csv",
                  performance_fields, performance_rows)
        write_csv(
            args.output / "native_merge_summary.csv",
            ["case", "software_recurrence", "smu_recurrence",
             "recurrence_speedup", "software_merge_total", "smu_merge_total",
             "merge_speedup"], summary_rows,
        )
        write_csv(args.output / "native_attention_performance.csv", [
            "case", "software_native_attention", "smu_native_attention",
            "speedup",
        ], attention_rows)
        write_csv(args.output / "numerical_agreement.csv", [
            "case", "output_mae", "stable_relative_error",
            "cosine_similarity",
        ], numerical_rows)
        write_csv(args.output / "om_fsm_breakdown.csv", [
            "case", "implementation", "invocation", "schema_version", "N",
            "D", "mode", "terminal_state", "load_scalar_cycles",
            "compute_scalar_cycles", "compute_weight_cycles",
            "store_scalar_cycles", "update_vector_cycles", "busy_cycles",
        ], fsm_rows)
        manifest["status"] = "complete"
        manifest["artifacts"] = [
            "native_merge_performance.csv", "native_merge_summary.csv",
            "native_attention_performance.csv", "numerical_agreement.csv",
            "om_fsm_breakdown.csv",
        ]
        save_manifest()
    except Exception:
        manifest["status"] = "failed"
        save_manifest()
        raise
    print(f"formal collection complete: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
