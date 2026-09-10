#!/usr/bin/env python3
"""Run non-formal Gate 1 smoke checks for the selected new shapes.

This script builds and executes both Phase 5 target variants for each new
shape with the archived reciprocal simulator.  It writes only smoke logs and
a compact summary under the Phase 6 experiment directory; it never writes a
formal CSV or invokes either formal collector's execution mode.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
PHASE6 = ROOT / "experiments/phase6_integrated_cost_generality"
P0_1_PLAN = PHASE6 / "p0_1_integrated_cost/run_matched_synthesis.py"
P0_2_PLAN = PHASE6 / "p0_2_workload_generality/collect_formal.py"
GENERATOR = ROOT / "experiments/phase5_native_online_attention/generate_case.py"
NEW_SHAPES = ((24, 64), (16, 128))
TARGETS = {
    "software": "test-spatzBenchmarks-native-online-attention-software",
    "smu": "test-spatzBenchmarks-native-online-attention-smu",
}
SIMULATOR = Path(
    "/home/wxt/work-online-merge-supplement/work-artifacts/work-phase4-recip-sim/spatz_cluster.vlt"
)


def run_logged(command: list[str], cwd: Path, log: Path,
               timeout: int | None = None) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        try:
            completed = subprocess.run(
                command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            return 124
    return completed.returncode


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def command_text(command: list[str]) -> str:
    import shlex
    return shlex.join(str(part) for part in command)


def parse_records(log: Path, prefix: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    records = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            value, _ = decoder.raw_decode(line[len(prefix):].lstrip())
            records.append(value)
    return records


def parse_output(log: Path, n: int, d: int) -> int:
    chunks = parse_records(log, "PHASE5_OUTPUT_CHUNK ")
    if chunks:
        ordered = sorted(chunks, key=lambda record: record["offset"])
        bits: list[int] = []
        for record in ordered:
            require(record["n"] == n and record["d"] == d,
                    f"chunk shape mismatch in {log}")
            require(record["offset"] == len(bits),
                    f"chunk offset gap in {log}")
            bits.extend(record["bits"])
        require(len(bits) == n * d,
                f"chunk bit count mismatch in {log}: {len(bits)}")
        require(all(isinstance(value, int) and 0 <= value <= 0xffffffff
                    for value in bits), f"invalid output bit in {log}")
        return len(bits)
    records = parse_records(log, "PHASE5_OUTPUT ")
    require(len(records) == 1, f"missing compact output record in {log}")
    record = records[0]
    require(record["n"] == n and record["d"] == d,
            f"output shape mismatch in {log}")
    bits = record["bits"]
    require(isinstance(bits, list) and len(bits) == n * d,
            f"output bit count mismatch in {log}: {len(bits)}")
    require(all(isinstance(value, int) and 0 <= value <= 0xffffffff
                for value in bits), f"invalid output bit in {log}")
    return len(bits)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-root", type=Path,
                        default=ROOT / "work-artifacts" / "work-phase6-native-smoke")
    parser.add_argument("--case-root", type=Path,
                        default=ROOT / "work-artifacts" / "work-phase6-native-smoke-cases")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--reuse-build", action="store_true",
                        help="reuse an already compiled external smoke build")
    parser.add_argument(
        "--shape", action="append", metavar="N,D",
        help="run only the listed new shape (repeatable); prior PASS rows are retained",
    )
    parser.add_argument("--plan-only", action="store_true",
                        help="run and archive both collector plan/self-checks only")
    args = parser.parse_args()

    shapes = list(NEW_SHAPES)
    if args.shape:
        shapes = []
        for value in args.shape:
            try:
                n_text, d_text = value.split(",", 1)
                shape = (int(n_text), int(d_text))
            except ValueError as error:
                raise RuntimeError(f"invalid --shape {value!r}; use N,D") from error
            require(shape in NEW_SHAPES,
                    f"--shape {value} is not a selected Phase 6 new shape")
            if shape not in shapes:
                shapes.append(shape)

    p0_1_log = PHASE6 / "p0_1_integrated_cost/logs/plan.log"
    p0_2_log = PHASE6 / "p0_2_workload_generality/logs/plan.log"
    require(run_logged([sys.executable, str(P0_1_PLAN)], ROOT, p0_1_log) == 0,
            "P0-1 plan-only check failed")
    require(run_logged([sys.executable, str(P0_2_PLAN)], ROOT, p0_2_log) == 0,
            "P0-2 plan-only/self-check failed")
    if args.plan_only:
        print("Gate 1 plan/self-check PASS")
        return 0
    require(SIMULATOR.is_file(), f"missing archived simulator: {SIMULATOR}")

    args.build_root.mkdir(parents=True, exist_ok=True)
    args.case_root.mkdir(parents=True, exist_ok=True)
    summary: list[dict[str, Any]] = []
    summary_path = PHASE6 / "p0_2_workload_generality/logs/smoke_summary.csv"
    if args.shape and summary_path.is_file():
        with summary_path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                prior_shape = (int(row["n"]), int(row["d"]))
                if (prior_shape in NEW_SHAPES and prior_shape not in shapes and
                        row.get("smoke_status") == "PASS"):
                    summary.append(row)
    for n, d in shapes:
        slug = f"N{n}_D{d}_S1"
        build_dir = args.build_root / slug
        case_header = args.case_root / slug / "phase5_case_data.h"
        if not args.reuse_build:
            require(not build_dir.exists() or not any(build_dir.iterdir()),
                    f"stale smoke build directory: {build_dir}")
        require(run_logged([
            sys.executable, str(GENERATOR), "--n", str(n), "--d", str(d),
            "--seed", "1", "--output", str(case_header),
        ], ROOT, PHASE6 / "p0_2_workload_generality/logs" /
           f"{slug}_generate.log") == 0, f"case generation failed for {slug}")
        configure = [
            "cmake", "-S", str(ROOT / "hw/system/spatz_cluster/sw"),
            "-B", str(build_dir), f"-DLLVM_PATH={ROOT / 'install/llvm'}",
            f"-DGCC_PATH={ROOT / 'install/riscv-gcc'}", f"-DPYTHON={sys.executable}",
            "-DBUILD_TESTS=ON", f"-DSNITCH_SIMULATOR={SIMULATOR}",
            "-DSPATZ_CLUSTER_CFG=spatz_cluster.default.dram.hjson",
            f"-DPHASE5_N={n}", f"-DPHASE5_D={d}", "-DPHASE5_SEED=1",
            "-DPHASE5_DUMP_OUTPUT=1", "-DCMAKE_C_FLAGS=-DPRINTF_DISABLE_SUPPORT_FLOAT",
            "-DMEM_DRAM_ORIGIN=2147483648", "-DMEM_DRAM_SIZE=2147483648",
            "-DSNRT_BASE_HARTID=0", "-DSNRT_CLUSTER_CORE_NUM=2",
            "-DSNRT_TCDM_START_ADDR=1048576", "-DSNRT_CLUSTER_OFFSET=0",
            "-DSNRT_TCDM_SIZE=131072", "-DSNRT_NFPU_PER_CORE=4", "-DELEN=64",
        ]
        configure_log = PHASE6 / "p0_2_workload_generality/logs" / f"{slug}_configure.log"
        require(run_logged(configure, ROOT, configure_log, args.timeout) == 0,
                f"CMake configure failed for {slug}")
        build = [
            "cmake", "--build", str(build_dir), "--target",
            TARGETS["software"], TARGETS["smu"], "--", f"-j{args.jobs}",
        ]
        build_log = PHASE6 / "p0_2_workload_generality/logs" / f"{slug}_build.log"
        require(run_logged(build, ROOT, build_log, args.timeout) == 0,
                f"CMake build failed for {slug}")
        for implementation, target in TARGETS.items():
            elf = build_dir / "spatzBenchmarks" / target
            require(elf.is_file(), f"missing {implementation} ELF for {slug}")
            log = PHASE6 / "p0_2_workload_generality/logs" / f"{slug}_{implementation}.log"
            command = [str(SIMULATOR), str(elf)]
            rc = run_logged(command, ROOT, log, args.timeout)
            if rc == 124:
                summary.append({
                    "case": slug, "implementation": implementation, "n": n,
                    "d": d, "tile_size": 4, "merge_count": n // 4 - 1,
                    "status": "timeout_deferred", "output_bits": 0,
                    "smu_commands": 0, "smu_done": 0, "smu_errors": 0,
                    "smu_timeouts": 0, "host_timeout": 1,
                    "smoke_status": "DEFERRED_HOST_TIMEOUT",
                    "command": command_text(command),
                })
                continue
            require(rc == 0, f"simulator return code {rc} for {slug}/{implementation}")
            result_records = parse_records(log, "PHASE5_RESULT ")
            require(len(result_records) == 1, f"missing result for {slug}/{implementation}")
            result = result_records[0]
            require(result.get("status") == "pass",
                    f"target status is not pass for {slug}/{implementation}")
            require(result.get("n") == n and result.get("d") == d,
                    f"result shape mismatch for {slug}/{implementation}")
            require(result.get("tile_keys") == 4 and
                    result.get("merge_count") == n // 4 - 1,
                    f"tile/merge contract mismatch for {slug}/{implementation}")
            require(result.get("output_nonfinite") == 0,
                    f"non-finite output for {slug}/{implementation}")
            bit_count = parse_output(log, n, d)
            smu = result["smu"]
            if implementation == "smu":
                require(smu["commands"] == n // 4 - 1 and
                        smu["done"] == n // 4 - 1 and
                        smu["errors"] == 0 and smu["timeouts"] == 0,
                        f"SMU completion contract mismatch for {slug}")
            summary.append({
                "case": slug, "implementation": implementation, "n": n,
                "d": d, "tile_size": 4, "merge_count": n // 4 - 1,
                "status": result["status"], "output_bits": bit_count,
                "smu_commands": smu["commands"], "smu_done": smu["done"],
                "smu_errors": smu["errors"], "smu_timeouts": smu["timeouts"],
                "host_timeout": 0, "smoke_status": "PASS",
                "command": command_text(command),
            })
    with summary_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)
    status = "PASS" if all(row["smoke_status"] == "PASS" for row in summary) else "PARTIAL"
    print(f"Gate 1 smoke {status}: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
