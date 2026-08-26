#!/usr/bin/env python3
"""Build and run matched Software-Softmax and Mixed-SMU target paths."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.phase4_quantized_attention import run_system as phase4  # noqa: E402


ANCHORS = ((8, 32), (16, 64))
PERFORMANCE_BACKENDS = ("software", "mixed")
BACKENDS = PERFORMANCE_BACKENDS + ("device_compare",)
BUILD_ROOT = Path("/home/wxt/work-phase4-softmax-ablation-sw")
RESULTS = Path(__file__).resolve().parent / "results"
DEFAULT_SIMULATOR = phase4.DEFAULT_SIMULATOR


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def command_text(command: list[str]) -> str:
    return shlex.join(str(item) for item in command)


def case_tuple(text: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)x(\d+)", text)
    if match is None:
        raise argparse.ArgumentTypeError("case must be written as NxD, e.g. 8x32")
    return int(match.group(1)), int(match.group(2))


def reuse_map(values: list[str]) -> dict[tuple[str, str], Path]:
    """Parse backend:NxD=/path entries used for completed target logs."""

    result: dict[tuple[str, str], Path] = {}
    for value in values:
        if "=" not in value or ":" not in value.split("=", 1)[0]:
            raise ValueError(
                "--reuse-log expects backend:NxD=/path/to/log"
            )
        selector, path_text = value.split("=", 1)
        backend, case = selector.split(":", 1)
        if backend not in BACKENDS:
            raise ValueError(f"unknown reuse backend: {backend}")
        case_tuple(case)
        result[(backend, case)] = Path(path_text).resolve()
    return result


def build_case(
    n: int,
    d: int,
    backend: str,
    simulator: Path,
    commands: list[str],
    timeout: int,
) -> Path:
    build_dir = BUILD_ROOT / backend / f"N{n}_D{d}"
    cflags = "-DPRINTF_DISABLE_SUPPORT_FLOAT"
    if backend == "software":
        cflags += " -DPHASE4_SOFTWARE_SOFTMAX"
    elif backend == "device_compare":
        cflags += " -DPHASE4_DEVICE_COMPARE"
    cmake = [
        "cmake",
        "-S",
        str(phase4.SW_SOURCE),
        "-B",
        str(build_dir),
        f"-DLLVM_PATH={ROOT / 'install' / 'llvm'}",
        f"-DGCC_PATH={ROOT / 'install' / 'riscv-gcc'}",
        "-DPYTHON=python3",
        "-DBUILD_TESTS=ON",
        f"-DSNITCH_SIMULATOR={simulator}",
        f"-DSPATZ_CLUSTER_CFG={phase4.CFG_PATH.name}",
        "-DPHASE4_SEED=1",
        f"-DPHASE4_N={n}",
        f"-DPHASE4_D={d}",
        f"-DCMAKE_C_FLAGS={cflags}",
        *phase4.cluster_defines(),
    ]
    phase4.run(cmake, cwd=ROOT, timeout=timeout)
    commands.append(command_text(cmake))
    build = [
        "cmake",
        "--build",
        str(build_dir),
        "--target",
        "test-spatzBenchmarks-quantized-attention",
        "--",
        "-j8",
    ]
    phase4.run(build, cwd=ROOT, timeout=timeout)
    commands.append(command_text(build))
    elf = build_dir / "spatzBenchmarks" / (
        "test-spatzBenchmarks-quantized-attention"
    )
    if not elf.is_file():
        raise RuntimeError(f"missing built ELF: {elf}")
    return elf


def parse_log(path: Path) -> dict[str, Any]:
    p4: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    fsm: list[dict[str, Any]] = []
    p4_count = 0
    config_count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("P4_RESULT "):
            p4_count += 1
            p4 = json.loads(line.split(" ", 1)[1])
        elif line.startswith("OM_SIM_CONFIG "):
            config_count += 1
            config = json.loads(line.split(" ", 1)[1])
        elif line.startswith("OM_FSM "):
            fsm.append(json.loads(line.split(" ", 1)[1]))
    if p4 is None or config is None or p4_count != 1 or config_count != 1:
        raise RuntimeError(f"incomplete Phase 4 ablation log: {path}")
    return {
        "log": str(path),
        "p4_result": phase4.decode_bits(p4),
        "sim_config": config,
        "fsm": fsm,
    }


def attach_case_metadata(
    backend: str, key: str, parsed: dict[str, Any]
) -> None:
    """Attach runner metadata to a complete current ablation result."""

    p4 = parsed["p4_result"]
    if "backend" not in p4 or "softmax" not in p4.get("cycles", {}):
        raise RuntimeError(
            f"log is not a current Phase 4 ablation result: {parsed['log']}"
        )
    parsed["case"] = key
    parsed["backend"] = backend


def validate_case(backend: str, key: str, parsed: dict[str, Any]) -> None:
    p4 = parsed["p4_result"]
    expected_backend = {
        "software": "software_softmax",
        "mixed": "mixed_smu",
        "device_compare": "device_pair_compare",
    }[backend]
    if p4.get("backend") != expected_backend or p4.get("status") != "pass":
        raise RuntimeError(
            f"unexpected {backend} result for {key}: "
            f"backend={p4.get('backend')} status={p4.get('status')}"
        )
    n = p4["n"]
    if backend in ("mixed", "device_compare"):
        fsm = parsed["fsm"]
        if len(fsm) != n - 1 or any(item.get("mode") != 3 for item in fsm):
            raise RuntimeError(
                f"{backend} {key} must contain n-1 mode-3 SMU records; "
                f"got {len(fsm)} records"
            )
    if backend == "software" and parsed["fsm"]:
        raise RuntimeError(f"software {key} unexpectedly emitted SMU FSM records")


def validate_control_matrix(
    cases: dict[str, dict[str, dict[str, Any]]], selected: list[tuple[int, int]]
) -> None:
    """Require all non-softmax checkpoints/configuration to match per anchor."""

    invariant_fields = (
        "n", "d", "seed", "mode", "smu_d", "stride", "scales_bits",
        "maxabs_bits", "maxabs", "linear", "score", "tcdm",
    )
    for n, d in selected:
        key = f"{n}x{d}"
        reference = cases["software"][key]
        reference_p4 = reference["p4_result"]
        reference_config = reference["sim_config"]
        for backend in BACKENDS:
            candidate = cases[backend][key]
            if candidate["sim_config"] != reference_config:
                raise RuntimeError(
                    f"simulator configuration differs for {backend} {key}"
                )
            candidate_p4 = candidate["p4_result"]
            for field in invariant_fields:
                if candidate_p4.get(field) != reference_p4.get(field):
                    raise RuntimeError(
                        f"control mismatch {backend} {key}: field {field}"
                    )


def find_reused_elf(backend: str, n: int, d: int) -> Path | None:
    """Find a matching ELF for hash/evidence when a log is reused."""

    candidates = [
        BUILD_ROOT / backend / f"N{n}_D{d}" / "spatzBenchmarks" / (
            "test-spatzBenchmarks-quantized-attention"
        ),
        # N8 device-compare was built by the initial runner revision before
        # per-case build directories were introduced.
        BUILD_ROOT / backend / "spatzBenchmarks" / (
            "test-spatzBenchmarks-quantized-attention"
        ),
    ]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def cycle_row(backend: str, case: dict[str, Any]) -> dict[str, Any]:
    p4 = case["p4_result"]
    cycles = p4["cycles"]
    qkv_linear = sum(cycles[key] for key in ("q_linear", "k_linear", "v_linear"))
    attention_total = qkv_linear + cycles["qkt"] + cycles["score_rescale"]
    attention_total += cycles["softmax"] + cycles["pv"]
    return {
        "backend": backend,
        "case": f"N{p4['n']}_D{p4['d']}",
        "n": p4["n"],
        "d": p4["d"],
        "seed": p4["seed"],
        "qkv_linear": qkv_linear,
        "qkt": cycles["qkt"],
        "score_scaling": cycles["score_rescale"],
        "softmax": cycles["softmax"],
        "pv": cycles["pv"],
        "attention_total": attention_total,
        "raw_total": cycles["total"],
        "x_maxabs_scale": cycles["x_maxabs_scale"],
        "x_quant": cycles["x_quant"],
        "qkv_requant": sum(
            cycles[key] for key in ("q_requant", "k_requant", "v_requant")
        ),
        "output_rescale": cycles["output_rescale"],
        "smu_total": cycles["smu_total"],
        "smu_scalar_window": cycles["smu_scalar_window"],
        "smu_probability_update": cycles["smu_probability_update"],
        "smu_setup_orchestration": cycles["smu_setup_orchestration"],
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="anchor in NxD form; defaults to 8x32 and 16x64",
    )
    parser.add_argument("--simulator", type=Path, default=DEFAULT_SIMULATOR)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument(
        "--reuse-log",
        action="append",
        default=[],
        help="reuse completed log: backend:NxD=/path/to/log",
    )
    args = parser.parse_args()
    if args.seed != 1:
        raise SystemExit("Phase 4 anchors require seed=1")
    selected = [case_tuple(text) for text in (args.case or ["8x32", "16x64"])]
    if any(case not in ANCHORS for case in selected):
        raise SystemExit("only the N8_D32 and N16_D64 anchors are supported")
    simulator = args.simulator.resolve()
    if not simulator.is_file():
        raise SystemExit(f"simulator does not exist: {simulator}")
    try:
        reused = reuse_map(args.reuse_log)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    for (backend, key), path in reused.items():
        if case_tuple(key) not in selected:
            raise SystemExit(f"reuse log {backend}:{key} is not selected")
        n, d = case_tuple(key)
        expected_path = (
            RESULTS / "system_logs" / f"{backend}_N{n}_D{d}.log"
        ).resolve()
        if path.resolve() != expected_path:
            raise SystemExit(
                "reuse logs must be the current ablation logs under "
                f"{RESULTS / 'system_logs'}: {path}"
            )
        if not path.is_file():
            raise SystemExit(f"reused log does not exist: {path}")

    commands: list[str] = []
    cases: dict[str, dict[str, dict[str, Any]]] = {backend: {} for backend in BACKENDS}
    elf_hashes: dict[str, str | None] = {}
    elf_paths: dict[str, str | None] = {}
    # Each newly executed backend/case is a fresh simulator process. Reused
    # logs are explicit command-line inputs and are parsed/validated identically.
    for backend in BACKENDS:
        for n, d in selected:
            key = f"{n}x{d}"
            log_path = RESULTS / "system_logs" / f"{backend}_N{n}_D{d}.log"
            reuse_key = (backend, key)
            if reuse_key in reused:
                log_path = reused[reuse_key]
                parsed = parse_log(log_path)
                attach_case_metadata(backend, key, parsed)
                elf = find_reused_elf(backend, n, d)
                commands.append(
                    f"reuse-log {backend}:{key}={log_path} (cwd={ROOT})"
                )
            else:
                elf = build_case(n, d, backend, simulator, commands, args.timeout)
                phase4.objdump_gate(elf, commands, args.timeout)
                sim_command = [str(simulator), str(elf)]
                phase4.run(sim_command, cwd=ROOT, timeout=args.timeout,
                           output=log_path)
                commands.append(command_text(sim_command))
                parsed = parse_log(log_path)
                attach_case_metadata(backend, key, parsed)
            validate_case(backend, key, parsed)
            elf_paths[f"{backend}/{key}"] = str(elf) if elf else None
            elf_hashes[f"{backend}/{key}"] = sha256(elf) if elf else None
            parsed["elf"] = str(elf) if elf else None
            parsed["elf_sha256"] = elf_hashes[f"{backend}/{key}"]
            cases[backend][key] = parsed

    validate_control_matrix(cases, selected)
    RESULTS.mkdir(parents=True, exist_ok=True)
    all_rows = [
        cycle_row(backend, cases[backend][f"{n}x{d}"])
        for backend in PERFORMANCE_BACKENDS
        for n, d in selected
    ]
    write_csv(RESULTS / "cycles.csv", all_rows)
    direct_rows: list[dict[str, Any]] = []
    for n, d in selected:
        key = f"{n}x{d}"
        software = cases["software"][key]["p4_result"]
        mixed = cases["mixed"][key]["p4_result"]
        pair = cases["device_compare"][key]["p4_result"]
        probability = pair["device_pair_probability"]
        output = pair["device_pair_output"]
        direct_rows.append(
            {
                "case": f"N{n}_D{d}",
                "n": n,
                "d": d,
                "seed": args.seed,
                "probability_mae": probability["mae"],
                "probability_cosine_diagnostic": probability[
                    "cosine_similarity"
                ],
                "output_mae": output["mae"],
                "output_cosine_diagnostic": output["cosine_similarity"],
                "software_status": software["status"],
                "mixed_status": mixed["status"],
                "device_compare_status": pair["status"],
                "software_smu_commands": software["smu"]["commands"],
                "mixed_smu_commands": mixed["smu"]["commands"],
            }
        )
    write_csv(RESULTS / "device_numerical.csv", direct_rows)
    (RESULTS / "system_results.json").write_text(
        json.dumps(
            {
                "seed": args.seed,
                "simulator_path": str(simulator),
                "metric_authority": {
                    "device_mae": (
                        "direct device_pair_* MAE from the target run"
                    ),
                    "device_cosine": (
                        "diagnostic only; target sqrt/reciprocal approximation"
                    ),
                    "formal_cosine": (
                        "float64 host recomputation in results/numerical.csv"
                    ),
                },
                "backends": cases,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    git_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    manifest = {
        "seed": args.seed,
        "git_commit": git_commit,
        "git_dirty_after_outputs": bool(
            subprocess.run(
                ["git", "status", "--porcelain"], cwd=ROOT, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
        ),
        "simulator_path": str(simulator),
        "simulator_sha256": sha256(simulator),
        "config": str(phase4.CFG_PATH),
        "config_sha256": sha256(phase4.CFG_PATH),
        "elf_path": elf_paths,
        "elf_sha256": elf_hashes,
        "fresh_ablation_logs": {
            f"{backend}/{key}": str(path)
            for (backend, key), path in reused.items()
        },
        "fresh_ablation_logs_only": True,
        "metric_authority": {
            "device_mae": "direct device_pair_* MAE from target buffers",
            "device_cosine": (
                "diagnostic only; target sqrt/reciprocal approximation"
            ),
            "formal_cosine": (
                "float64 host recomputation in results/numerical.csv"
            ),
        },
        "backends": {
            "software": "-DPHASE4_SOFTWARE_SOFTMAX",
            "mixed": "default (frozen Mixed SMU path)",
            "device_compare": (
                "-DPHASE4_DEVICE_COMPARE; software P/O then frozen Mixed "
                "P/O on the same score/VQ buffers"
            ),
        },
        "command_provenance": (
            "The commands below are final aggregate/reparse inputs for the "
            "six completed fresh logs; original fresh log-generation command "
            "lines were not captured in this manifest."
        ),
        "commands": commands,
    }
    (RESULTS / "system_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    for row in all_rows:
        print(
            f"phase4-ablation-system {row['backend']} {row['case']} "
            f"softmax={row['softmax']} attention_total={row['attention_total']} "
            f"raw_total={row['raw_total']}"
        )
    for row in direct_rows:
        print(
            f"phase4-ablation-device {row['case']} "
            f"probability_cosine_diagnostic="
            f"{row['probability_cosine_diagnostic']:.9f} "
            f"output_cosine_diagnostic="
            f"{row['output_cosine_diagnostic']:.9f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
