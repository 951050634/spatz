#!/usr/bin/env python3
"""Build and run the two bounded Phase 4 system anchors.

This is intentionally a small experiment driver.  It keeps the software build
outside the repository, reuses an already captured log when requested, and
emits only the tables needed by the Phase 4 system comparison.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shlex
import struct
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SW_SOURCE = ROOT / "hw" / "system" / "spatz_cluster" / "sw"
CFG_PATH = ROOT / "hw" / "system" / "spatz_cluster" / "cfg" / (
    "spatz_cluster.default.dram.hjson"
)
BUILD_ROOT = Path("/home/wxt/work-phase4-sw")
DEFAULT_SIMULATOR = Path("/home/wxt/work-phase4-recip-sim/spatz_cluster.vlt")
RESULTS = Path(__file__).resolve().parent / "results"
ANCHORS = ((8, 32), (16, 64))


def run(command: list[str], *, cwd: Path | None = None,
        timeout: int = 7200, output: Path | None = None) -> str:
    if output is None:
        completed = subprocess.run(
            command, cwd=cwd, check=True, text=True,
            capture_output=True, timeout=timeout,
        )
        return completed.stdout
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        subprocess.run(
            command, cwd=cwd, check=True, stdout=stream,
            stderr=subprocess.STDOUT, timeout=timeout,
        )
    return output.read_text(encoding="utf-8")


def command_text(command: list[str]) -> str:
    return shlex.join(str(item) for item in command)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def float_bits(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", int(value)))[0]


def decode_bits(value: Any) -> Any:
    """Retain bit fields while adding decoded float fields beside them."""

    if isinstance(value, list):
        return [decode_bits(item) for item in value]
    if not isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for key, item in value.items():
        decoded = decode_bits(item)
        result[key] = decoded
        if key.endswith("_bits") and isinstance(item, int):
            if key[:-5] not in value:
                result[key[:-5]] = float_bits(item)
        elif key.endswith("_bits") and isinstance(item, dict):
            if key[:-5] not in value:
                result[key[:-5]] = {
                    subkey: float_bits(subvalue)
                    if isinstance(subvalue, int) else decode_bits(subvalue)
                    for subkey, subvalue in item.items()
                }
    return result


def parse_log(path: Path) -> dict[str, Any]:
    p4: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    fsm: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("P4_RESULT "):
            p4 = json.loads(line.split(" ", 1)[1])
        elif line.startswith("OM_SIM_CONFIG "):
            config = json.loads(line.split(" ", 1)[1])
        elif line.startswith("OM_FSM "):
            fsm.append(json.loads(line.split(" ", 1)[1]))
    if p4 is None or config is None or not fsm:
        raise RuntimeError(f"incomplete Phase 4 system log: {path}")
    return {
        "log": str(path),
        "p4_result": decode_bits(p4),
        "sim_config": config,
        "fsm": fsm,
    }


def case_tuple(text: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)x(\d+)", text)
    if match is None:
        raise argparse.ArgumentTypeError("case must be written as NxD, e.g. 8x32")
    return int(match.group(1)), int(match.group(2))


def reuse_map(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--reuse-log expects NxD=/path/to/log")
        case, path = value.split("=", 1)
        case_tuple(case)
        result[case] = Path(path).resolve()
    return result


def cluster_defines() -> list[str]:
    # Keep these values tied to the checked-in default cluster configuration.
    # They are the same explicit definitions used by the cluster Makefile.
    return [
        "-DMEM_DRAM_ORIGIN=2147483648",
        "-DMEM_DRAM_SIZE=2147483648",
        "-DSNRT_BASE_HARTID=0",
        "-DSNRT_CLUSTER_CORE_NUM=2",
        "-DSNRT_TCDM_START_ADDR=1048576",
        "-DSNRT_CLUSTER_OFFSET=0",
        "-DSNRT_TCDM_SIZE=131072",
        "-DSNRT_NFPU_PER_CORE=4",
        "-DELEN=64",
    ]


def build_case(n: int, d: int, simulator: Path, commands: list[str],
               timeout: int) -> Path:
    build_dir = BUILD_ROOT / f"N{n}_D{d}"
    cmake = [
        "cmake", "-S", str(SW_SOURCE), "-B", str(build_dir),
        f"-DLLVM_PATH={ROOT / 'install' / 'llvm'}",
        f"-DGCC_PATH={ROOT / 'install' / 'riscv-gcc'}",
        "-DPYTHON=python3", "-DBUILD_TESTS=ON",
        f"-DSNITCH_SIMULATOR={simulator}",
        f"-DSPATZ_CLUSTER_CFG={CFG_PATH.name}",
        "-DPHASE4_SEED=1", f"-DPHASE4_N={n}", f"-DPHASE4_D={d}",
        "-DCMAKE_C_FLAGS=-DPRINTF_DISABLE_SUPPORT_FLOAT",
        *cluster_defines(),
    ]
    run(cmake, cwd=ROOT, timeout=timeout)
    commands.append(command_text(cmake))

    build = [
        "cmake", "--build", str(build_dir),
        "--target", "test-spatzBenchmarks-quantized-attention", "--", "-j8",
    ]
    run(build, cwd=ROOT, timeout=timeout)
    commands.append(command_text(build))
    elf = build_dir / "spatzBenchmarks" / (
        "test-spatzBenchmarks-quantized-attention"
    )
    if not elf.is_file():
        raise RuntimeError(f"missing built ELF: {elf}")
    return elf


def objdump_gate(elf: Path, commands: list[str], timeout: int) -> None:
    objdump = ROOT / "install" / "llvm" / "bin" / "llvm-objdump"
    command = [
        str(objdump), "--mcpu=snitch", "--mattr=a", "--mattr=v",
        "--mattr=m", "--mattr=zfh", "-d", str(elf),
    ]
    disassembly = run(command, cwd=ROOT, timeout=timeout)
    commands.append(command_text(command))
    fdiv = re.findall(r"^\s*[0-9a-f]+:\s+.*\bfdiv(?:\.[sd])?\b",
                      disassembly, flags=re.MULTILINE)
    if fdiv:
        raise RuntimeError(f"objdump fdiv gate failed for {elf}: {fdiv[:3]}")


def host_cosines() -> dict[tuple[int, int], dict[str, float]]:
    path = RESULTS / "numerical.csv"
    values: dict[tuple[int, int], dict[str, float]] = {}
    if not path.is_file():
        return values
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row.get("baseline") != "P-QM":
                continue
            key = (int(row["n"]), int(row["d"]))
            values[key] = {
                "score": float(row["score_cosine"]),
                "probability": float(row["probability_cosine"]),
                "output": float(row["output_cosine"]),
            }
    return values


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def cycle_row(case: dict[str, Any]) -> dict[str, Any]:
    p4 = case["p4_result"]
    cycles = p4["cycles"]
    quantize_x = cycles["x_maxabs_scale"] + cycles["x_quant"]
    qkv_linear = sum(cycles[key] for key in ("q_linear", "k_linear", "v_linear"))
    qkv_requant = sum(
        cycles[key] for key in ("q_requant", "k_requant", "v_requant")
    )
    overhead = quantize_x + qkv_requant
    total = cycles["total"]
    fraction = overhead / total if total else 0.0
    return {
        "case": f"N{p4['n']}_D{p4['d']}",
        "n": p4["n"], "d": p4["d"], "seed": p4["seed"],
        "x_maxabs_scale": cycles["x_maxabs_scale"],
        "x_quant": cycles["x_quant"],
        "q_linear": cycles["q_linear"],
        "k_linear": cycles["k_linear"],
        "v_linear": cycles["v_linear"],
        "q_requant": cycles["q_requant"],
        "k_requant": cycles["k_requant"],
        "v_requant": cycles["v_requant"],
        "quantize_x": quantize_x, "qkv_linear": qkv_linear,
        "qkv_requant": qkv_requant, "qkt": cycles["qkt"],
        "score_rescale": cycles["score_rescale"],
        "smu_total": cycles["smu_total"],
        "smu_scalar_window": cycles["smu_scalar_window"],
        "smu_probability_update": cycles["smu_probability_update"],
        "smu_setup_orchestration": cycles["smu_setup_orchestration"],
        "pv": cycles["pv"], "output_rescale": cycles["output_rescale"],
        "total": total, "dynamic_quant_overhead": overhead,
        "dynamic_quant_overhead_fraction": fraction,
        "dynamic_quant_overhead_percent": 100.0 * fraction,
    }


def accuracy_rows(case: dict[str, Any], cosines: dict[tuple[int, int],
                                                       dict[str, float]]) -> list[dict[str, Any]]:
    p4 = case["p4_result"]
    n, d = p4["n"], p4["d"]
    host = cosines.get((n, d), {})
    rows: list[dict[str, Any]] = []
    metric_groups = (
        ("Q", "linear", "Q", "host_fp32", ""),
        ("K", "linear", "K", "host_fp32", ""),
        ("V", "linear", "V", "host_fp32", ""),
        ("score_vs_ref", "score", None, "host_fp32", host.get("score", "")),
        ("probability_vs_ref", "probability", "vs_ref", "host_ref", host.get("probability", "")),
        ("probability_vs_host_mixed", "probability", "integration_vs_host_mixed", "host_mixed", host.get("probability", "")),
        ("output_vs_ref", "output", "vs_ref", "host_fp32", host.get("output", "")),
        ("output_vs_host_mixed", "output", "integration_vs_host_mixed", "host_mixed", host.get("output", "")),
    )
    for stage, group, key, reference, host_cosine in metric_groups:
        metric = p4[group] if key is None else p4[group][key]
        stable = metric["stable_relative_error"]
        # Keep this CSV witness scoped to stable-relative error.  main.c also
        # enforces cosine >= 0.999 for the actual integration status; MAE is
        # reported but is not a gate predicate.
        rows.append({
            "case": f"N{n}_D{d}", "n": n, "d": d, "seed": p4["seed"],
            "stage": stage, "reference": reference,
            "target_mae": metric["mae"],
            "target_stable_relative_error": stable,
            "target_cosine_diagnostic": metric["cosine_similarity"],
            "host_cosine_from_numerical_csv": host_cosine,
            "integration_witness": (
                "PASS" if key == "integration_vs_host_mixed" and stable < 0.01
                else "N/A" if key != "integration_vs_host_mixed" else "FAIL"
            ),
        })
    return rows


def scale_row(case: dict[str, Any]) -> dict[str, Any]:
    p4 = case["p4_result"]
    scales = p4["scales"]
    maxabs = p4["maxabs"]
    return {
        "case": f"N{p4['n']}_D{p4['d']}", "n": p4["n"],
        "d": p4["d"], "seed": p4["seed"],
        **{key: scales[key] for key in
           ("sX", "sWQ", "sWK", "sWV", "sQ", "sK", "sV", "sScore")},
        "maxabs_X": float_bits(p4["maxabs_bits"]["X"]),
        "maxabs_Q": maxabs["Q"], "maxabs_K": maxabs["K"],
        "maxabs_V": maxabs["V"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", default=[],
                        help="anchor in NxD form; defaults to 8x32 and 16x64")
    parser.add_argument("--reuse-log", action="append", default=[],
                        help="reuse log as NxD=/path/to/log")
    parser.add_argument("--simulator", type=Path, default=DEFAULT_SIMULATOR)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=7200)
    args = parser.parse_args()
    if args.seed != 1:
        raise SystemExit("Phase 4 anchors require seed=1")

    selected = [case_tuple(text) for text in (args.case or ["8x32", "16x64"])]
    if any(case not in ANCHORS for case in selected):
        raise SystemExit("only the N8_D32 and N16_D64 anchors are supported")
    reuse = reuse_map(args.reuse_log)
    simulator = args.simulator.resolve()
    if not simulator.is_file():
        raise SystemExit(f"simulator does not exist: {simulator}")

    commands: list[str] = []
    cases: list[dict[str, Any]] = []
    elf_hashes: dict[str, str] = {}
    for n, d in selected:
        elf = build_case(n, d, simulator, commands, args.timeout)
        objdump_gate(elf, commands, args.timeout)
        case_name = f"{n}x{d}"
        elf_hashes[case_name] = sha256(elf)
        if case_name in reuse:
            log_path = reuse[case_name]
            commands.append(f"reuse-log {case_name}={log_path}")
        else:
            log_path = RESULTS / "system_logs" / f"N{n}_D{d}.log"
            sim_command = [str(simulator), str(elf)]
            run(sim_command, cwd=ROOT, timeout=args.timeout, output=log_path)
            commands.append(command_text(sim_command))
        parsed = parse_log(log_path)
        parsed["case"] = case_name
        parsed["elf"] = str(elf)
        parsed["elf_sha256"] = elf_hashes[case_name]
        cases.append(parsed)

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "system_results.json").write_text(
        json.dumps({"seed": args.seed, "cases": cases}, indent=2) + "\n",
        encoding="utf-8",
    )
    write_csv(RESULTS / "cycles.csv", [cycle_row(case) for case in cases])
    cosines = host_cosines()
    write_csv(
        RESULTS / "device_accuracy.csv",
        [row for case in cases for row in accuracy_rows(case, cosines)],
    )
    write_csv(RESULTS / "device_scales.csv", [scale_row(case) for case in cases])

    git_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    git_dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip())
    manifest = {
        "seed": args.seed,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "simulator_path": str(simulator),
        "simulator_sha256": sha256(simulator),
        "elf_sha256": elf_hashes,
        "commands": commands,
    }
    (RESULTS / "system_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8",
    )
    for row in [cycle_row(case) for case in cases]:
        print(
            f"phase4-system {row['case']} total={row['total']} "
            f"dynamic_quant_overhead={row['dynamic_quant_overhead']} "
            f"fraction={row['dynamic_quant_overhead_fraction']:.6g}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
