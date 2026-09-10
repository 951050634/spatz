#!/usr/bin/env python3
"""Build, run, and validate the frozen Phase 8C matched pair."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shlex
import struct
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).resolve().parent
RAW = OUTPUT / "raw"
CLUSTER = ROOT / "hw/system/spatz_cluster"
BUILD_ROOT = CLUSTER / "work-phase8c-formal"
SIMULATOR = CLUSTER / "work-phase8c/spatz_cluster.vlt"
LLVM = ROOT / "install/llvm"
GCC = ROOT / "install/riscv-gcc"
FREEZE_COMMIT = "7786820821102d34e32e9517a7630b028693f25a"
SEED = 1
TARGETS = {
    "mmio": "test-spatzBenchmarks-native-online-attention-omerge-mmio",
    "omcfg": "test-spatzBenchmarks-native-online-attention-omerge-omcfg",
}
RUN_ORDER = (
    ("n8", 8, 32, "mmio"),
    ("n8", 8, 32, "omcfg"),
    ("n16", 16, 64, "mmio"),
    ("n16", 16, 64, "omcfg"),
)
CONFIG_FIELDS = (
    "A_M", "A_L", "B_M", "B_L", "TILE_M", "TILE_L",
    "WEIGHT_OLD", "WEIGHT_TILE", "N",
)
EXPECTED_TRACKED_DIFF = {
    "sw/spatzBenchmarks/CMakeLists.txt",
    "sw/spatzBenchmarks/native-online-attention/main.c",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_output(*args: str, binary: bool = False) -> str | bytes:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True,
        text=not binary, stdout=subprocess.PIPE,
    ).stdout


def command_text(command: list[str]) -> str:
    return shlex.join(command)


def parse_prefixed_json(text: str, prefix: str) -> list[dict[str, Any]]:
    records = []
    decoder = json.JSONDecoder()
    for line in text.splitlines():
        if line.startswith(prefix):
            record, _ = decoder.raw_decode(line[len(prefix):].lstrip())
            records.append(record)
    return records


def output_bits(text: str, n: int, d: int) -> list[int]:
    chunks = parse_prefixed_json(text, "PHASE5_OUTPUT_CHUNK ")
    require(bool(chunks), "missing PHASE5_OUTPUT_CHUNK")
    bits: list[int] = []
    for record in sorted(chunks, key=lambda item: item["offset"]):
        require(record["n"] == n and record["d"] == d,
                "output chunk shape mismatch")
        require(record["offset"] == len(bits),
                "output chunks are missing or out of order")
        bits.extend(record["bits"])
    require(len(bits) == n * d, "output word count mismatch")
    require(all(isinstance(value, int) and 0 <= value <= 0xffffffff
                for value in bits), "invalid uint32 output word")
    return bits


def bits_to_float64(bits: list[int]) -> list[float]:
    values = [float(struct.unpack("<f", struct.pack("<I", word))[0])
              for word in bits]
    require(all(math.isfinite(value) for value in values),
            "non-finite decoded output")
    return values


def pairwise_metrics(lhs_bits: list[int], rhs_bits: list[int]) -> dict[str, Any]:
    require(len(lhs_bits) == len(rhs_bits) and lhs_bits,
            "invalid matched output lengths")
    lhs = bits_to_float64(lhs_bits)
    rhs = bits_to_float64(rhs_bits)
    differences = [abs(a - b) for a, b in zip(lhs, rhs)]
    mae = sum(differences) / len(differences)
    stable = sum(differences) / max(sum(abs(value) for value in lhs), 1.0e-12)
    word_for_word_equal = lhs_bits == rhs_bits
    dot = sum(a * b for a, b in zip(lhs, rhs))
    lhs_norm = math.sqrt(sum(value * value for value in lhs))
    rhs_norm = math.sqrt(sum(value * value for value in rhs))
    # Exact bit identity proves mathematical identity.  Returning the exact
    # value avoids host float64 dot/norm rounding such as 1.0000000000000002.
    if word_for_word_equal:
        cosine = 1.0
    elif lhs_norm == 0.0 and rhs_norm == 0.0:
        cosine = 1.0
    elif lhs_norm == 0.0 or rhs_norm == 0.0:
        cosine = 0.0
    else:
        cosine = dot / (lhs_norm * rhs_norm)
    return {
        "word_for_word_equal": word_for_word_equal,
        "pairwise_mae": mae,
        "stable_rel": stable,
        "cosine": cosine,
        "nonfinite": sum(not math.isfinite(value) for value in lhs + rhs),
    }


def fnv1a_words(bits: list[int]) -> int:
    digest = 2166136261
    for word in bits:
        digest ^= word
        digest = (digest * 16777619) & 0xffffffff
    return digest


def text_sha256(elf: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="phase8c-text-") as directory:
        section = Path(directory) / "text.bin"
        copied = Path(directory) / "copy.elf"
        subprocess.run([
            str(LLVM / "bin/llvm-objcopy"),
            "--dump-section", f".text={section}", str(elf), str(copied),
        ], cwd=ROOT, check=True, stdout=subprocess.PIPE,
           stderr=subprocess.PIPE)
        return sha256_file(section)


def configure_command(build_dir: Path, n: int, d: int) -> list[str]:
    return [
        "cmake", "-S", str(CLUSTER / "sw"), "-B", str(build_dir),
        f"-DLLVM_PATH={LLVM}", f"-DGCC_PATH={GCC}",
        f"-DPYTHON={sys.executable}", "-DBUILD_TESTS=ON",
        f"-DSNITCH_SIMULATOR={SIMULATOR}",
        "-DSPATZ_CLUSTER_CFG=spatz_cluster.default.dram.hjson",
        f"-DPHASE5_N={n}", f"-DPHASE5_D={d}",
        f"-DPHASE5_SEED={SEED}", "-DPHASE5_DUMP_OUTPUT=1",
        "-DCMAKE_C_FLAGS=-DPRINTF_DISABLE_SUPPORT_FLOAT",
        "-DMEM_DRAM_ORIGIN=2147483648",
        "-DMEM_DRAM_SIZE=2147483648",
        "-DSNRT_BASE_HARTID=0", "-DSNRT_CLUSTER_CORE_NUM=2",
        "-DSNRT_TCDM_START_ADDR=1048576", "-DSNRT_CLUSTER_OFFSET=0",
        "-DSNRT_TCDM_SIZE=131072", "-DSNRT_NFPU_PER_CORE=4",
        "-DELEN=64",
    ]


def run_to_file(command: list[str], path: Path, timeout: int) -> int:
    with path.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(
            command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
            timeout=timeout, check=False,
        )
    return completed.returncode


def run_simulator(command: list[str], path: Path, provenance: dict[str, Any],
                  timeout: int) -> tuple[int, bool]:
    timed_out = False
    return_code = 124
    with path.open("w", encoding="utf-8") as stream:
        stream.write("PHASE8C_RUN_PROVENANCE " +
                     json.dumps(provenance, sort_keys=True) + "\n")
        stream.flush()
        try:
            completed = subprocess.run(
                command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            )
            return_code = completed.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
        stream.write("PHASE8C_RUN_EXIT " + json.dumps({
            "exit_code": return_code,
            "timed_out": timed_out,
            "finished_at": datetime.now().astimezone().isoformat(),
        }, sort_keys=True) + "\n")
    return return_code, timed_out


def parse_selector_transitions(text: str) -> list[tuple[int, int]]:
    pattern = re.compile(
        r"^OMERGE_ADAPTER_RESPONSE error=(\d+) selector_before=(\d+) "
        r"selector_after=(\d+)$", re.MULTILINE)
    transitions = []
    for error, before, after in pattern.findall(text):
        require(error == "0", "OMERGE response reported an error")
        transitions.append((int(before), int(after)))
    return transitions


def validate_run(log_path: Path, case: str, n: int, d: int,
                 path: str, return_code: int, timed_out: bool) -> dict[str, Any]:
    text = log_path.read_text(encoding="utf-8")
    require(return_code == 0 and not timed_out,
            f"{case}/{path} simulator failure")
    require("[SUCCESS] Program finished successfully" in text,
            f"{case}/{path} missing simulator success marker")
    results = parse_prefixed_json(text, "PHASE5_RESULT ")
    states = parse_prefixed_json(text, "PHASE8C_CONFIG_STATE ")
    simulator_configs = parse_prefixed_json(text, "OM_SIM_CONFIG ")
    provenances = parse_prefixed_json(text, "PHASE8C_RUN_PROVENANCE ")
    exits = parse_prefixed_json(text, "PHASE8C_RUN_EXIT ")
    fsm = parse_prefixed_json(text, "OM_FSM ")
    require(len(results) == len(states) == len(simulator_configs) ==
            len(provenances) == len(exits) == 1,
            f"{case}/{path} missing or duplicate structured record")
    result = results[0]
    state = states[0]
    sim_config = simulator_configs[0]
    provenance = provenances[0]
    exit_record = exits[0]
    merge_count = n // 4 - 1
    order_index = RUN_ORDER.index((case, n, d, path)) + 1
    require(provenance["formal_order_index"] == order_index and
            provenance["implementation_freeze_commit"] == FREEZE_COMMIT and
            provenance["simulator_build_id"] == sha256_file(SIMULATOR),
            f"{case}/{path} provenance mismatch")
    require(exit_record["exit_code"] == return_code and
            exit_record["timed_out"] is timed_out,
            f"{case}/{path} exit record mismatch")
    require(result["status"] == "pass", f"{case}/{path} target failed")
    require(result["n"] == n and result["d"] == d and
            result["seed"] == SEED, f"{case}/{path} workload mismatch")
    require(result["merge_count"] == merge_count,
            f"{case}/{path} merge count mismatch")
    require(state["path"] == path and state["N"] == n and
            state["workload_D"] == d, f"{case}/{path} config-state mismatch")
    require(sim_config["dasm_trace_enabled"] is False and
            sim_config["fsm_observer_enabled"] is True,
            f"{case}/{path} simulator observer profile mismatch")

    configuration = result["configuration"]
    require(configuration["path"] == path and
            configuration["field_writes"] == 9 and
            configuration["init_count"] == 1,
            f"{case}/{path} configuration count mismatch")
    expected_mmio = 9 if path == "mmio" else 0
    expected_omcfg = 10 if path == "omcfg" else 0
    require(configuration["mmio_writes"] == expected_mmio and
            configuration["omcfg_instructions"] == expected_omcfg,
            f"{case}/{path} access-mechanism count mismatch")

    smu = result["smu"]
    require(smu["commands"] == smu["done"] == merge_count and
            smu["errors"] == smu["timeouts"] == 0,
            f"{case}/{path} SMU count/error mismatch")
    markers = {
        "omerge_accept": text.count("OMERGE_ADAPTER_ACCEPT "),
        "smu_start": text.count("OMERGE_ADAPTER_START "),
        "smu_done": text.count("OMERGE_ADAPTER_DONE "),
        "omcfg_field_writes": text.count("OMCFG_ADAPTER_WRITE "),
        "mmio_field_writes": text.count("OMCFG_ADAPTER_MMIO_WRITE "),
        "omcfg_init": text.count("OMCFG_ADAPTER_INIT "),
        "mmio_init": text.count("OMCFG_ADAPTER_MMIO_INIT "),
    }
    require(markers["omerge_accept"] == markers["smu_start"] ==
            markers["smu_done"] == merge_count,
            f"{case}/{path} adapter event count mismatch")
    require(markers["omcfg_field_writes"] ==
            (9 if path == "omcfg" else 0) and
            markers["mmio_field_writes"] ==
            (9 if path == "mmio" else 0),
            f"{case}/{path} observed field-write count mismatch")
    require(markers["omcfg_init"] == (1 if path == "omcfg" else 0) and
            markers["mmio_init"] == (1 if path == "mmio" else 0),
            f"{case}/{path} observed INIT count mismatch")

    init_pattern = (
        r"OMCFG_ADAPTER_INIT .*complete=1 cfg_valid_after=1 selector_after=0"
        if path == "omcfg" else
        r"OMCFG_ADAPTER_MMIO_INIT .*cfg_valid_after=1 selector_after=0"
    )
    require(re.search(init_pattern, text) is not None,
            f"{case}/{path} cfg_valid/selector INIT evidence missing")
    transitions = parse_selector_transitions(text)
    expected_transitions = [
        (index & 1, (index + 1) & 1) for index in range(merge_count)
    ]
    require(transitions == expected_transitions,
            f"{case}/{path} selector sequence mismatch")

    require(len(fsm) == merge_count, f"{case}/{path} OM_FSM count mismatch")
    for invocation, record in enumerate(fsm):
        require(record["invocation"] == invocation and record["N"] == n and
                record["D"] == 1 and record["mode"] == 3 and
                record["terminal_state"] == "DONE" and
                record["update_vector_cycles"] == 0,
                f"{case}/{path} OM_FSM record mismatch")

    cycles = result["cycles"]
    require(cycles["merge_window"] == cycles["smu_recurrence"] +
            cycles["rvv_output_update"] + cycles["merge_orchestration"],
            f"{case}/{path} merge-cycle decomposition mismatch")
    require(cycles["total"] == cycles["score_compute"] +
            cycles["tile_local_state"] + cycles["merge_window"] +
            cycles["core_residual"] + cycles["output_copy"],
            f"{case}/{path} core-cycle decomposition mismatch")

    bits = output_bits(text, n, d)
    require(result["output_nonfinite"] == 0,
            f"{case}/{path} target non-finite output")
    require(fnv1a_words(bits) == result["output_hash"],
            f"{case}/{path} output hash mismatch")
    canonical_state = {field: state[field] for field in CONFIG_FIELDS}
    canonical_state.update({"cfg_valid": 1, "selector_after_init": 0})
    state_hash = sha256_bytes(
        json.dumps(canonical_state, sort_keys=True,
                   separators=(",", ":")).encode()
    )
    return {
        "case": case,
        "config_path": path,
        "result": result,
        "config_state": canonical_state,
        "config_state_hash": state_hash,
        "output_bits": bits,
        "markers": markers,
        "selector_transitions": transitions,
        "om_fsm": fsm,
        "raw_log": str(log_path.relative_to(OUTPUT)),
        "raw_log_sha256": sha256_file(log_path),
        "exit_code": return_code,
        "timed_out": timed_out,
    }


def write_csv(rows: list[dict[str, Any]], metrics: dict[str, dict[str, Any]]) -> None:
    fieldnames = [
        "case", "config_path", "setup_cycles", "omerge_count",
        "smu_start", "smu_done", "selector_toggle", "mmio_writes",
        "omcfg_instructions", "init_count", "rvv_update_cycles",
        "merge_cycles", "native_core_cycles", "setup_inclusive_cycles",
        "output_words", "output_hash", "pairwise_mae", "stable_rel",
        "cosine", "nonfinite", "config_state_hash", "errors", "timeouts",
        "exit_code",
    ]
    output_rows = []
    for run in rows:
        result = run["result"]
        cycles = result["cycles"]
        config = result["configuration"]
        pair = metrics[run["case"]]
        output_rows.append({
            "case": run["case"],
            "config_path": run["config_path"],
            "setup_cycles": cycles["workload_setup"],
            "omerge_count": run["markers"]["omerge_accept"],
            "smu_start": run["markers"]["smu_start"],
            "smu_done": run["markers"]["smu_done"],
            "selector_toggle": len(run["selector_transitions"]),
            "mmio_writes": config["mmio_writes"],
            "omcfg_instructions": config["omcfg_instructions"],
            "init_count": config["init_count"],
            "rvv_update_cycles": cycles["rvv_output_update"],
            "merge_cycles": cycles["merge_total"],
            "native_core_cycles": cycles["total"],
            "setup_inclusive_cycles":
                cycles["workload_setup"] + cycles["total"],
            "output_words": len(run["output_bits"]),
            "output_hash": result["output_hash"],
            "pairwise_mae": pair["pairwise_mae"],
            "stable_rel": pair["stable_rel"],
            "cosine": pair["cosine"],
            "nonfinite": result["output_nonfinite"],
            "config_state_hash": run["config_state_hash"],
            "errors": result["smu"]["errors"],
            "timeouts": result["smu"]["timeouts"],
            "exit_code": run["exit_code"],
        })
    with (OUTPUT / "matched_results.csv").open(
            "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)


def tool_version(path: Path) -> str:
    completed = subprocess.run(
        [str(path), "--version"], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10,
    )
    return completed.stdout.strip()


def pair_evidence(mmio: dict[str, Any], omcfg: dict[str, Any],
                  case: str) -> dict[str, Any]:
    pair = pairwise_metrics(mmio["output_bits"], omcfg["output_bits"])
    pair["config_state_equal"] = (
        mmio["config_state"] == omcfg["config_state"])
    pair["output_hash_equal"] = (
        mmio["result"]["output_hash"] == omcfg["result"]["output_hash"])
    require(pair["word_for_word_equal"] and
            pair["pairwise_mae"] == 0.0 and
            pair["stable_rel"] == 0.0 and
            pair["cosine"] == 1.0 and
            pair["nonfinite"] == 0 and
            pair["config_state_equal"] and
            pair["output_hash_equal"],
            f"{case} MMIO/OMCFG equivalence failed")
    return pair


def summarized_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in run.items()
        if key not in {"output_bits", "result", "om_fsm"}
    } | {
        "result": run["result"],
        "om_fsm": run["om_fsm"],
        "output_words": len(run["output_bits"]),
        "output_hash": run["result"]["output_hash"],
        "output_bits_sha256": sha256_bytes(b"".join(
            struct.pack("<I", word) for word in run["output_bits"])),
    }


def analyze_existing(manifest: dict[str, Any], audit: dict[str, Any]) -> None:
    """Re-run strict parsing only; never execute or alter a formal raw log."""
    require(manifest.get("kind") ==
            "phase8c-omcfg-runtime-matched-validation",
            "unexpected existing manifest")
    previous_runs = {
        (run["case"], run["config_path"]): run
        for run in manifest.get("runs", [])
    }
    require(len(previous_runs) == 4, "expected four completed formal runs")
    rows: list[dict[str, Any]] = []
    by_case: dict[str, dict[str, dict[str, Any]]] = {}
    metrics: dict[str, dict[str, Any]] = {}
    for case, n, d, path in RUN_ORDER:
        log_path = RAW / f"{case}_{path}.log"
        require(log_path.is_file(), f"missing formal log: {log_path}")
        require(sha256_file(log_path) ==
                previous_runs[(case, path)]["raw_log_sha256"],
                f"formal raw log changed: {case}/{path}")
        text = log_path.read_text(encoding="utf-8")
        exits = parse_prefixed_json(text, "PHASE8C_RUN_EXIT ")
        require(len(exits) == 1, f"missing exit record: {case}/{path}")
        run = validate_run(
            log_path, case, n, d, path,
            int(exits[0]["exit_code"]), bool(exits[0]["timed_out"]),
        )
        rows.append(run)
        by_case.setdefault(case, {})[path] = run
        if path == "omcfg":
            metrics[case] = pair_evidence(
                by_case[case]["mmio"], run, case)

    prior_correction = manifest.get("postprocessing_correction", {})
    original_failure = prior_correction.get(
        "original_failure", manifest.get("failure"))
    original_finished_at = prior_correction.get(
        "original_finished_at", manifest.get("finished_at"))
    require({path: sha256_file(ROOT / path)
             for path in audit["sources"]} == audit["sources"],
            "formal benchmark source changed after execution")
    require(not str(git_output(
        "diff", "--name-only", FREEZE_COMMIT, "--", "hw")).strip(),
        "RTL changed after formal execution")
    write_csv(rows, metrics)
    manifest["runs"] = [summarized_run(run) for run in rows]
    manifest["matched_pairs"] = metrics
    manifest["status"] = "complete"
    manifest.pop("failure", None)
    manifest["finished_at"] = datetime.now().astimezone().isoformat()
    manifest["source_snapshot_unchanged"] = True
    manifest["postprocessing_correction"] = {
        "formal_cases_rerun": False,
        "raw_logs_modified": False,
        "original_status": prior_correction.get("original_status", "failed"),
        "original_failure": original_failure,
        "original_finished_at": original_finished_at,
        "reason": (
            "Exact N16 bit-vector identity produced host float64 cosine "
            "1.0000000000000002; exact identity is now mapped to cosine 1.0."
        ),
        "raw_log_sha256_unchanged": {
            f"{case}_{path}": previous_runs[(case, path)]["raw_log_sha256"]
            for case, _, _, path in RUN_ORDER
        },
    }
    manifest["artifacts"] = [
        "matched_results.csv", "manifest.json",
        *[f"raw/{case}_{path}.log" for case, _, _, path in RUN_ORDER],
    ]
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-formal", action="store_true")
    parser.add_argument("--analyze-existing", action="store_true")
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    head = str(git_output("rev-parse", "HEAD")).strip()
    freeze = str(git_output("rev-parse", FREEZE_COMMIT)).strip()
    require(freeze == FREEZE_COMMIT, "Phase 8B freeze commit mismatch")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", FREEZE_COMMIT, "HEAD"],
        cwd=ROOT, check=True,
    )
    tracked = set(filter(None, str(git_output(
        "diff", "--name-only", FREEZE_COMMIT)).splitlines()))
    require(tracked == EXPECTED_TRACKED_DIFF,
            f"unexpected tracked diff from freeze: {sorted(tracked)}")
    rtl_diff = str(git_output(
        "diff", "--name-only", FREEZE_COMMIT, "--", "hw")).strip()
    require(not rtl_diff, "RTL changed after Phase 8B freeze")
    require(SIMULATOR.is_file(), f"missing simulator: {SIMULATOR}")
    status = str(git_output("status", "--short", "--untracked-files=all"))
    source_diff = git_output(
        "diff", "--binary", FREEZE_COMMIT, "--",
        *sorted(EXPECTED_TRACKED_DIFF), binary=True,
    )
    audit = {
        "implementation_freeze_commit": FREEZE_COMMIT,
        "formal_head": head,
        "git_status_before": status.splitlines(),
        "tracked_diff_from_freeze": sorted(tracked),
        "tracked_diff_sha256": sha256_bytes(source_diff),
        "rtl_diff_from_freeze": [],
        "simulator": {
            "path": str(SIMULATOR),
            "sha256": sha256_file(SIMULATOR),
        },
        "sources": {
            path: sha256_file(ROOT / path) for path in sorted(tracked)
        },
        "run_order": [
            {"index": index, "case": case, "n": n, "d": d, "path": path}
            for index, (case, n, d, path) in enumerate(RUN_ORDER, 1)
        ],
    }
    print(json.dumps(audit, indent=2), flush=True)
    require(not (args.execute_formal and args.analyze_existing),
            "choose either --execute-formal or --analyze-existing")
    if args.analyze_existing:
        manifest_path = OUTPUT / "manifest.json"
        require(manifest_path.is_file(), "missing existing formal manifest")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        analyze_existing(manifest, manifest["audit"])
        print("PHASE 8C EXISTING-LOG ANALYSIS: PASS", flush=True)
        return 0
    if not args.execute_formal:
        print("PLAN ONLY: formal build/run not executed", flush=True)
        return 0

    required_logs = [RAW / f"{case}_{path}.log"
                     for case, _, _, path in RUN_ORDER]
    require(not any(path.exists() for path in required_logs),
            "formal raw log already exists")
    require(not BUILD_ROOT.exists() or not any(BUILD_ROOT.iterdir()),
            f"formal build root is not empty: {BUILD_ROOT}")
    RAW.mkdir(parents=True, exist_ok=True)
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "phase8c-omcfg-runtime-matched-validation",
        "status": "in_progress",
        "audit": audit,
        "policy": {
            "seed": SEED,
            "tile_keys": 4,
            "timeout_seconds": args.timeout,
            "jobs": args.jobs,
            "formal_order_fixed": True,
            "dasm_trace_enabled": False,
            "fsm_observer_enabled": True,
        },
        "toolchain": {
            "clang": tool_version(LLVM / "bin/clang"),
            "riscv_gcc": tool_version(GCC / "bin/riscv32-unknown-elf-gcc"),
            "verilator": tool_version(ROOT / "install/verilator/bin/verilator"),
            "python": sys.version,
        },
        "builds": [],
        "runs": [],
        "matched_pairs": {},
    }

    def save_manifest() -> None:
        (OUTPUT / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    save_manifest()
    builds: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    by_case: dict[str, dict[str, dict[str, Any]]] = {}
    metrics: dict[str, dict[str, Any]] = {}
    try:
        for case, n, d in (("n8", 8, 32), ("n16", 16, 64)):
            build_dir = BUILD_ROOT / f"N{n}_D{d}_S{SEED}"
            configure = configure_command(build_dir, n, d)
            build = [
                "cmake", "--build", str(build_dir), "--target",
                TARGETS["mmio"], TARGETS["omcfg"], "--", f"-j{args.jobs}",
            ]
            configure_log = RAW / f"{case}_configure.log"
            build_log = RAW / f"{case}_build.log"
            print(f"BUILD {case}: configure", flush=True)
            require(run_to_file(configure, configure_log, args.timeout) == 0,
                    f"{case} configure failed")
            print(f"BUILD {case}: compile matched targets", flush=True)
            require(run_to_file(build, build_log, args.timeout) == 0,
                    f"{case} build failed")
            header = (build_dir / "spatzBenchmarks/phase5_generated" /
                      f"N{n}_D{d}_S{SEED}/phase5_case_data.h")
            require(header.is_file(), f"{case} generated input is missing")
            elfs = {
                path: build_dir / "spatzBenchmarks" / target
                for path, target in TARGETS.items()
            }
            require(all(elf.is_file() for elf in elfs.values()),
                    f"{case} ELF is missing")
            text_hashes = {path: text_sha256(elf)
                           for path, elf in elfs.items()}
            require(text_hashes["mmio"] == text_hashes["omcfg"],
                    f"{case} matched ELF .text sections differ")
            build_record = {
                "case": case,
                "n": n,
                "d": d,
                "build_dir": str(build_dir),
                "configure_command": command_text(configure),
                "build_command": command_text(build),
                "configure_log": str(configure_log.relative_to(OUTPUT)),
                "configure_log_sha256": sha256_file(configure_log),
                "build_log": str(build_log.relative_to(OUTPUT)),
                "build_log_sha256": sha256_file(build_log),
                "generated_input": str(header),
                "generated_input_sha256": sha256_file(header),
                "elfs": {
                    path: {
                        "path": str(elf),
                        "sha256": sha256_file(elf),
                        "text_sha256": text_hashes[path],
                    } for path, elf in elfs.items()
                },
                "matched_text_identical": True,
            }
            builds[case] = build_record
            manifest["builds"].append(build_record)
            save_manifest()

        for order_index, (case, n, d, path) in enumerate(RUN_ORDER, 1):
            elf_record = builds[case]["elfs"][path]
            elf = Path(elf_record["path"])
            log_path = RAW / f"{case}_{path}.log"
            command = [str(SIMULATOR), str(elf)]
            provenance = {
                "schema_version": 1,
                "implementation_freeze_commit": FREEZE_COMMIT,
                "formal_head": head,
                "tracked_diff_sha256": audit["tracked_diff_sha256"],
                "rtl_diff_from_freeze": [],
                "formal_order_index": order_index,
                "case": case,
                "workload": {"N": n, "D": d, "seed": SEED},
                "config_path": path,
                "cfg_ids": list(range(10)),
                "simulator_path": str(SIMULATOR),
                "simulator_build_id": audit["simulator"]["sha256"],
                "elf_path": str(elf),
                "elf_sha256": elf_record["sha256"],
                "elf_text_sha256": elf_record["text_sha256"],
                "generated_input_sha256":
                    builds[case]["generated_input_sha256"],
                "command": command_text(command),
                "started_at": datetime.now().astimezone().isoformat(),
            }
            print(f"FORMAL {order_index}/4: {case} {path}", flush=True)
            return_code, timed_out = run_simulator(
                command, log_path, provenance, args.timeout)
            run = validate_run(
                log_path, case, n, d, path, return_code, timed_out)
            rows.append(run)
            by_case.setdefault(case, {})[path] = run
            manifest["runs"].append(summarized_run(run))
            save_manifest()
            print(f"PASS {case} {path}", flush=True)
            if path == "omcfg":
                mmio = by_case[case]["mmio"]
                pair = pair_evidence(mmio, run, case)
                metrics[case] = pair
                manifest["matched_pairs"][case] = pair
                save_manifest()
                print(f"MATCHED PAIR PASS: {case}", flush=True)

        current_sources = {
            path: sha256_file(ROOT / path) for path in sorted(tracked)
        }
        require(current_sources == audit["sources"],
                "Phase 8C source changed during formal execution")
        require(not str(git_output(
            "diff", "--name-only", FREEZE_COMMIT, "--", "hw")).strip(),
            "RTL changed during formal execution")
        write_csv(rows, metrics)
        manifest["status"] = "complete"
        manifest["finished_at"] = datetime.now().astimezone().isoformat()
        manifest["source_snapshot_unchanged"] = True
        manifest["artifacts"] = [
            "matched_results.csv", "manifest.json",
            *[str(path.relative_to(OUTPUT)) for path in required_logs],
        ]
        save_manifest()
    except Exception as error:
        manifest["status"] = "failed"
        manifest["failure"] = str(error)
        manifest["finished_at"] = datetime.now().astimezone().isoformat()
        save_manifest()
        raise

    print("PHASE 8C FORMAL VALIDATION: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
