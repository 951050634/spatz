#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Build, run, and preserve online-merge experiment records."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import signal
import statistics
import struct
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

RESULT_PREFIX = "OM_RESULT "
FAILURE_PREFIX = "OM_FAILURE "
EXPECTED_IMPLEMENTATIONS = ("B1", "B2-R", "A1", "B3")
RVV_UPDATE_SYMBOL = "online_merge_rvv_update"
RVV_REQUIRED_MNEMONICS = (
    "vsetvli",
    "vle32.v",
    "vfmul.vf",
    "vfmacc.vf",
    "vse32.v",
)
RVV_REQUIRED_COUNTS = {"vle32.v": 2}
VALID_STATUSES = {
    "pass",
    "correctness_fail",
    "timeout",
    "capacity_skip",
    "unsupported",
    "tool_error",
}
CASE_KINDS = {
    "main",
    "equal-m",
    "delta-neg8",
    "delta-below-neg8",
    "l-old-zero",
    "l-tile-zero",
    "small-l",
    "signed-o",
    "both-zero-l",
}
UINT32_MAX = (1 << 32) - 1
TCDM_CAPACITY_BYTES = 128 * 1024
TCDM_LIMIT_BYTES = TCDM_CAPACITY_BYTES * 7 // 10
ALLOCATION_ALIGNMENT_BYTES = 256
REQUIRED_TARGET_FIELDS = {
    "implementation",
    "N",
    "D",
    "stride",
    "seed",
    "case_kind",
    "case_class",
    "repeat",
    "cycles_hi",
    "cycles_lo",
    "tcdm_accessed",
    "tcdm_congested",
    "max_abs_bits",
    "max_rel_numerator_bits",
    "max_rel_denominator_bits",
    "sum_sq_bits",
    "checked",
    "bit_equal",
    "nonfinite",
    "status",
}
REQUIRED_FIELDS = (
    "git_commit",
    "cfg_path",
    "cfg_hash",
    "tool_version",
    "implementation",
    "N",
    "D",
    "stride",
    "seed",
    "repeat",
    "cycles",
    "tcdm_accessed",
    "tcdm_congested",
    "max_abs",
    "max_rel",
    "rmse",
    "bit_equal_ratio",
    "status",
)
DERIVED_FIELDS = (
    "cycles_per_element",
    "elements_per_cycle",
    "congestion_ratio",
)
CMAKE_DEFINE_KEY_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
RESERVED_CMAKE_DEFINE_KEYS = frozenset(
    {
        "ONLINE_MERGE_N",
        "ONLINE_MERGE_D",
        "ONLINE_MERGE_SEED",
        "ONLINE_MERGE_CASE_KIND",
        "ONLINE_MERGE_REPEATS",
    }
)


@dataclass(frozen=True)
class Case:
    n: int
    d: int
    seed: int = 1
    case_kind: str = "main"
    repeats: int = 5
    timeout_seconds: int | None = None

    @property
    def slug(self) -> str:
        kind = self.case_kind.replace("-", "_")
        return (
            f"N{self.n}_D{self.d}_S{self.seed}_{kind}_R{self.repeats}"
        )


@dataclass
class CommandRecord:
    argv: list[str]
    command: str
    start_utc: str
    end_utc: str
    returncode: int | None
    status: str
    timeout_seconds: int
    log_path: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def layout_bytes(n: int, d: int) -> tuple[int, int]:
    footprint = n * (40 + 16 * d)
    allocation = (
        (footprint + ALLOCATION_ALIGNMENT_BYTES - 1)
        // ALLOCATION_ALIGNMENT_BYTES
        * ALLOCATION_ALIGNMENT_BYTES
    )
    return footprint, allocation


def capacity_fits(case: Case) -> bool:
    _, allocation = layout_bytes(case.n, case.d)
    return allocation <= TCDM_LIMIT_BYTES


def validate_case(case: Case) -> None:
    if case.n <= 0 or case.d <= 0:
        raise ValueError("N and D must be positive")
    if case.n > UINT32_MAX or case.d > UINT32_MAX:
        raise ValueError("N and D must fit in uint32_t")
    if not 0 <= case.seed <= UINT32_MAX:
        raise ValueError("seed must be in [0, 2^32-1]")
    if case.case_kind not in CASE_KINDS:
        raise ValueError(
            f"case_kind must be one of {sorted(CASE_KINDS)}"
        )
    if not 3 <= case.repeats <= 16:
        raise ValueError("repeats must be in [3, 16]")
    if case.timeout_seconds is not None and case.timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")


def parse_case(value: str, default_repeats: int) -> Case:
    parts = value.split(",")
    if not 2 <= len(parts) <= 5:
        raise argparse.ArgumentTypeError(
            "case must be N,D[,seed[,case-kind[,timeout-seconds]]]"
        )
    try:
        case = Case(
            n=int(parts[0]),
            d=int(parts[1]),
            seed=int(parts[2]) if len(parts) >= 3 else 1,
            case_kind=parts[3] if len(parts) >= 4 else "main",
            repeats=default_repeats,
            timeout_seconds=int(parts[4]) if len(parts) >= 5 else None,
        )
        validate_case(case)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    return case


def parse_cmake_defines(values: Sequence[str]) -> list[tuple[str, str]]:
    definitions: list[tuple[str, str]] = []
    seen: set[str] = set()
    for value in values:
        key, separator, definition_value = value.partition("=")
        if not separator:
            raise ValueError(
                f"--cmake-define must be KEY=VALUE, got {value!r}"
            )
        if CMAKE_DEFINE_KEY_PATTERN.fullmatch(key) is None:
            raise ValueError(
                "--cmake-define key must match "
                f"[A-Za-z_][A-Za-z0-9_]*, got {key!r}"
            )
        if not definition_value:
            raise ValueError(
                f"--cmake-define value must not be empty for {key}"
            )
        if any(not character.isprintable() for character in definition_value):
            raise ValueError(
                f"--cmake-define value contains a control character: {key}"
            )
        if key in RESERVED_CMAKE_DEFINE_KEYS:
            raise ValueError(
                f"--cmake-define {key} conflicts with per-case settings"
            )
        if key in seen:
            raise ValueError(f"duplicate --cmake-define key: {key}")
        seen.add(key)
        definitions.append((key, definition_value))
    return definitions


def cmake_define_arguments(
    definitions: Sequence[tuple[str, str]],
) -> list[str]:
    return [f"-D{key}={value}" for key, value in definitions]


def cmake_define_manifest(
    definitions: Sequence[tuple[str, str]],
) -> list[dict[str, str]]:
    return [
        {"key": key, "value": value, "argument": f"-D{key}={value}"}
        for key, value in definitions
    ]


def make_configure_argv(
    cmake_command: str,
    source_dir: Path,
    build_dir: Path,
    case: Case,
    definitions: Sequence[tuple[str, str]],
) -> list[str]:
    argv = [
        cmake_command,
        "-S",
        str(source_dir),
        "-B",
        str(build_dir),
        f"-DONLINE_MERGE_N={case.n}",
        f"-DONLINE_MERGE_D={case.d}",
        f"-DONLINE_MERGE_SEED={case.seed}",
        f"-DONLINE_MERGE_CASE_KIND={case.case_kind}",
        f"-DONLINE_MERGE_REPEATS={case.repeats}",
    ]
    argv.extend(cmake_define_arguments(definitions))
    return argv


def float_from_bits(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", value & UINT32_MAX))[0]


def parse_target_output(
    output: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for line_number, line in enumerate(output.splitlines(), 1):
        destination: list[dict[str, Any]] | None = None
        payload = ""
        kind = ""
        if line.startswith(RESULT_PREFIX):
            destination = records
            payload = line[len(RESULT_PREFIX) :]
            kind = "result"
        elif line.startswith(FAILURE_PREFIX):
            destination = failures
            payload = line[len(FAILURE_PREFIX) :]
            kind = "failure"
        if destination is None:
            continue
        try:
            decoded = json.loads(payload)
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
            continue
        if not isinstance(decoded, dict):
            errors.append(
                {
                    "kind": "non_object_structured_record",
                    "record_kind": kind,
                    "line_number": line_number,
                    "line": line[:512],
                }
            )
            continue
        destination.append(decoded)
    return records, failures, errors


def safe_metric(value: float) -> float | None:
    return value if math.isfinite(value) else None


def enrich_record(
    record: dict[str, Any], metadata: dict[str, Any]
) -> dict[str, Any]:
    enriched = dict(metadata)
    enriched.update(record)
    if "cycles" not in enriched:
        cycles_hi = int(enriched.pop("cycles_hi", 0)) & UINT32_MAX
        cycles_lo = int(enriched.pop("cycles_lo", 0)) & UINT32_MAX
        enriched["cycles"] = (cycles_hi << 32) | cycles_lo

    max_abs = float_from_bits(int(enriched.pop("max_abs_bits", 0)))
    if "max_rel_bits" in enriched:
        max_rel = float_from_bits(int(enriched.pop("max_rel_bits")))
    else:
        numerator = float_from_bits(
            int(enriched.pop("max_rel_numerator_bits", 0))
        )
        denominator = float_from_bits(
            int(enriched.pop("max_rel_denominator_bits", 0))
        )
        max_rel = (
            numerator / denominator
            if math.isfinite(numerator)
            and math.isfinite(denominator)
            and denominator > 0.0
            else math.nan
        )
    sum_sq = float_from_bits(int(enriched.pop("sum_sq_bits", 0)))
    checked = int(enriched.get("checked", 0) or 0)
    bit_equal = int(enriched.get("bit_equal", 0) or 0)
    cycles = enriched.get("cycles")
    accessed = enriched.get("tcdm_accessed")
    congested = enriched.get("tcdm_congested")
    elements = int(enriched.get("N", 0)) * int(enriched.get("D", 0))

    if int(enriched.get("repeat", -1)) < 0:
        cycles = None
        accessed = None
        congested = None
        enriched["cycles"] = None
        enriched["tcdm_accessed"] = None
        enriched["tcdm_congested"] = None
    enriched["max_abs"] = safe_metric(max_abs)
    enriched["max_rel"] = safe_metric(max_rel)
    enriched["rmse"] = (
        math.sqrt(sum_sq / checked)
        if checked and math.isfinite(sum_sq) and sum_sq >= 0.0
        else None
    )
    enriched["bit_equal_ratio"] = (
        bit_equal / checked if checked else None
    )
    enriched["cycles_per_element"] = (
        float(cycles) / elements if cycles is not None and elements else None
    )
    enriched["elements_per_cycle"] = (
        elements / float(cycles) if cycles not in (None, 0) else None
    )
    enriched["congestion_ratio"] = (
        float(congested) / float(accessed)
        if accessed not in (None, 0) and congested is not None
        else None
    )
    return enriched


def synthetic_records(
    case: Case, status: str, reason: str | None = None
) -> list[dict[str, Any]]:
    footprint, allocation = layout_bytes(case.n, case.d)
    records = []
    for implementation in EXPECTED_IMPLEMENTATIONS:
        record: dict[str, Any] = {
            "implementation": implementation,
            "N": case.n,
            "D": case.d,
            "stride": 4 * case.d,
            "seed": case.seed,
            "case_kind": case.case_kind,
            "case_class": (
                "capacity"
                if status == "capacity_skip"
                else (
                    "unsupported"
                    if case.case_kind == "both-zero-l"
                    else "main" if case.case_kind == "main" else "boundary"
                )
            ),
            "repeat": -1,
            "cycles": None,
            "tcdm_accessed": None,
            "tcdm_congested": None,
            "max_abs": None,
            "max_rel": None,
            "rmse": None,
            "bit_equal_ratio": None,
            "cycles_per_element": None,
            "elements_per_cycle": None,
            "congestion_ratio": None,
            "footprint_bytes": footprint,
            "allocation_bytes": allocation,
            "tcdm_capacity_bytes": TCDM_CAPACITY_BYTES,
            "status": status,
        }
        if reason is not None:
            record["failure_reason"] = reason
        records.append(record)
    return records


def terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    process.wait()


def run_command(
    argv: Sequence[str],
    log_path: Path,
    timeout_seconds: int,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
) -> tuple[CommandRecord, str]:
    start = utc_now()
    status = "pass"
    returncode: int | None = None
    output = ""
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            list(argv),
            cwd=cwd,
            env=(
                {**os.environ, **environment}
                if environment is not None
                else None
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        raw, _ = process.communicate(timeout=timeout_seconds)
        returncode = process.returncode
        output = raw.decode("utf-8", errors="replace")
        if returncode != 0:
            status = "tool_error"
    except subprocess.TimeoutExpired as error:
        status = "timeout"
        raw = error.output or b""
        output = (
            raw.decode("utf-8", errors="replace")
            if isinstance(raw, bytes)
            else str(raw)
        )
        if process is not None:
            terminate_process_group(process)
            returncode = process.returncode
            if process.stdout is not None:
                remainder = process.stdout.read()
                process.stdout.close()
            else:
                remainder = b""
            output += remainder.decode("utf-8", errors="replace")
        output += f"\nHOST_TIMEOUT seconds={timeout_seconds}\n"
    except OSError as error:
        status = "tool_error"
        output = f"HOST_TOOL_ERROR {error}\n"
    end = utc_now()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(output, encoding="utf-8")
    record = CommandRecord(
        argv=list(argv),
        command=shlex.join(argv),
        start_utc=start,
        end_utc=end,
        returncode=returncode,
        status=status,
        timeout_seconds=timeout_seconds,
        log_path=str(log_path),
    )
    return record, output


def extract_symbol_disassembly(disassembly: str, symbol: str) -> str | None:
    lines = disassembly.splitlines()
    symbol_header = re.compile(r"^[0-9a-fA-F]+ <([^>]+)>:$")
    start: int | None = None
    for index, line in enumerate(lines):
        match = symbol_header.match(line)
        if match and match.group(1) == symbol:
            start = index
            break
    if start is None:
        return None

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if symbol_header.match(lines[index]):
            end = index
            break
    return "\n".join(lines[start:end]).rstrip() + "\n"


def has_local_backedge(disassembly: str) -> bool:
    instruction = re.compile(
        r"^\s*([0-9a-fA-F]+):\s+([a-zA-Z0-9_.]+)(?:\s+(.*))?$"
    )
    parsed: list[tuple[int, str, str]] = []
    for line in disassembly.splitlines():
        match = instruction.match(line)
        if match:
            parsed.append(
                (
                    int(match.group(1), 16),
                    match.group(2),
                    match.group(3) or "",
                )
            )
    if not parsed:
        return False

    first_address = min(address for address, _, _ in parsed)
    last_address = max(address for address, _, _ in parsed)
    for address, mnemonic, operands in parsed:
        if not (mnemonic.startswith("b") or mnemonic.startswith("j")):
            continue
        targets = re.findall(r"0x([0-9a-fA-F]+)", operands)
        if any(
            first_address <= int(target, 16) < address <= last_address
            for target in targets
        ):
            return True
    return False


def inspect_rvv_disassembly(disassembly: str) -> tuple[str | None, list[str]]:
    snippet = extract_symbol_disassembly(disassembly, RVV_UPDATE_SYMBOL)
    if snippet is None:
        return None, [f"missing symbol {RVV_UPDATE_SYMBOL}"]
    missing = [
        mnemonic
        for mnemonic in RVV_REQUIRED_MNEMONICS
        if mnemonic not in snippet
    ]
    for mnemonic, required_count in RVV_REQUIRED_COUNTS.items():
        if snippet.count(mnemonic) < required_count:
            missing.append(f"{required_count} {mnemonic} instructions")
    if not has_local_backedge(snippet):
        missing.append("strip-mining back-edge")
    if "<unknown>" in snippet:
        missing.append("decoded RVV instructions")
    return snippet, missing


def run_rvv_disassembly_gate(
    objdump: Path,
    elf: Path,
    log_path: Path,
    snippet_path: Path,
    timeout_seconds: int,
    cwd: Path,
) -> tuple[CommandRecord, str | None]:
    command, output = run_command(
        [
            str(objdump),
            "-d",
            "--no-show-raw-insn",
            "--mattr=+v",
            str(elf),
        ],
        log_path,
        timeout_seconds,
        cwd,
    )
    reason: str | None = None
    snippet: str | None = None
    if command.status == "pass":
        snippet, missing = inspect_rvv_disassembly(output)
        if missing:
            command.status = "tool_error"
            reason = "missing RVV gate evidence: " + ", ".join(missing)
    else:
        reason = f"objdump command status={command.status}"

    if snippet is not None:
        snippet_path.write_text(snippet, encoding="utf-8")
    gate_status = "pass" if reason is None else "tool_error"
    gate_summary = (
        f"\nRVV_DISASSEMBLY_GATE status={gate_status} "
        f"symbol={RVV_UPDATE_SYMBOL}"
    )
    if reason is not None:
        gate_summary += f" reason={reason}"
    log_path.write_text(output + gate_summary + "\n", encoding="utf-8")
    return command, reason


def git_output(repo_root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=repo_root, text=True
    ).strip()


def command_version(argv: Sequence[str]) -> dict[str, Any]:
    executable = (
        shutil.which(argv[0]) if not Path(argv[0]).is_file() else argv[0]
    )
    if not executable:
        return {"path": argv[0], "status": "missing"}
    try:
        completed = subprocess.run(
            [str(executable), *argv[1:]],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "path": str(executable),
            "status": "tool_error",
            "detail": str(error),
        }
    lines = [line.strip() for line in completed.stdout.splitlines() if line]
    return {
        "path": str(Path(executable).resolve()),
        "status": "pass" if completed.returncode == 0 else "tool_error",
        "returncode": completed.returncode,
        "version": " | ".join(lines[:3]),
    }


def configured_compiler(build_dir: Path, repo_root: Path) -> Path | None:
    cmake_files = sorted(
        build_dir.glob("CMakeFiles/*/CMakeCCompiler.cmake"), reverse=True
    )
    pattern = re.compile(r'^set\(CMAKE_C_COMPILER "([^"]+)"\)')
    for cmake_file in cmake_files:
        for line in cmake_file.read_text(encoding="utf-8").splitlines():
            match = pattern.match(line)
            if match:
                compiler = Path(match.group(1))
                if compiler.is_file():
                    return compiler
    candidates = (
        repo_root / "install/llvm/bin/clang",
        Path(shutil.which("clang") or ""),
    )
    for candidate in candidates:
        if str(candidate) and candidate.is_file():
            return candidate
    return None


def detect_tool_versions(
    repo_root: Path,
    simulator: Path,
    build_dir: Path,
    cmake_command: str,
    objdump: Path | None = None,
) -> dict[str, Any]:
    simulator_info: dict[str, Any] = {
        "path": str(simulator),
        "status": "present" if simulator.is_file() else "missing",
    }
    if simulator.is_file():
        simulator_info["sha256"] = sha256_file(simulator)

    verilator_candidates = (
        repo_root / "install/verilator/bin/verilator",
        Path(shutil.which("verilator") or ""),
    )
    verilator_info: dict[str, Any] = {"status": "missing"}
    for candidate in verilator_candidates:
        if str(candidate) and candidate.is_file():
            verilator_info = command_version([str(candidate), "--version"])
            break

    compiler = configured_compiler(build_dir, repo_root)
    compiler_info = (
        command_version([str(compiler), "--version"])
        if compiler is not None
        else {"status": "missing"}
    )
    if objdump is None:
        objdump = repo_root / "install/llvm/bin/llvm-objdump"
    objdump_info = command_version([str(objdump), "--version"])
    return {
        "simulator": simulator_info,
        "verilator": verilator_info,
        "cmake": command_version([cmake_command, "--version"]),
        "compiler": compiler_info,
        "objdump": objdump_info,
        "python": {
            "path": os.sys.executable,
            "version": os.sys.version.split()[0],
            "status": "pass",
        },
    }


def artifact_entry(
    path: Path,
    repo_root: Path,
    git_commit: str,
    cfg_hash: str,
    tool_version: str,
    workload: str,
    window: str,
) -> dict[str, Any]:
    return {
        "relative_or_external_path": display_path(path, repo_root),
        "sha256": sha256_file(path),
        "git_commit": git_commit,
        "cfg_hash": cfg_hash,
        "tool_version": tool_version,
        "workload": workload,
        "window": window,
    }


def generated_simulator_artifacts(
    case_dir: Path,
    repo_root: Path,
    git_commit: str,
    cfg_hash: str,
    tool_version: str,
    workload: str,
) -> list[dict[str, Any]]:
    logs_dir = case_dir / "logs"
    if not logs_dir.is_dir():
        return []
    entries = []
    for path in sorted(logs_dir.iterdir()):
        if path.is_file():
            entries.append(
                artifact_entry(
                    path,
                    repo_root,
                    git_commit,
                    cfg_hash,
                    tool_version,
                    workload,
                    "simulator-generated execution trace or metadata",
                )
            )
    return entries


def summarize(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        key = (
            record.get("implementation"),
            record.get("N"),
            record.get("D"),
            record.get("seed"),
            record.get("case_kind"),
        )
        groups.setdefault(key, []).append(record)

    summaries = []
    for key, group in sorted(groups.items(), key=lambda item: str(item[0])):
        passing_cycles = [
            int(record["cycles"])
            for record in group
            if record.get("status") == "pass"
            and record.get("cycles") is not None
        ]
        passing_smu_scalar_cycles = [
            int(record["smu_scalar_cycles"])
            for record in group
            if record.get("status") == "pass"
            and record.get("smu_scalar_cycles") is not None
            and int(record["smu_scalar_cycles"]) > 0
        ]
        passing_rvv_vector_cycles = [
            int(record["rvv_vector_cycles"])
            for record in group
            if record.get("status") == "pass"
            and record.get("rvv_vector_cycles") is not None
            and int(record["rvv_vector_cycles"]) > 0
        ]
        statuses: dict[str, int] = {}
        for record in group:
            status = str(record.get("status", "tool_error"))
            statuses[status] = statuses.get(status, 0) + 1
        summaries.append(
            {
                "implementation": key[0],
                "N": key[1],
                "D": key[2],
                "seed": key[3],
                "case_kind": key[4],
                "statuses": statuses,
                "measured_repeats": len(passing_cycles),
                "cycles_min": min(passing_cycles) if passing_cycles else None,
                "cycles_median": (
                    statistics.median(passing_cycles)
                    if passing_cycles
                    else None
                ),
                "cycles_max": max(passing_cycles) if passing_cycles else None,
                "smu_scalar_cycles_median": (
                    statistics.median(passing_smu_scalar_cycles)
                    if passing_smu_scalar_cycles
                    else None
                ),
                "rvv_vector_cycles_median": (
                    statistics.median(passing_rvv_vector_cycles)
                    if passing_rvv_vector_cycles
                    else None
                ),
            }
        )
    return summaries


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def csv_fields(records: Sequence[dict[str, Any]]) -> list[str]:
    fields = list(REQUIRED_FIELDS + DERIVED_FIELDS)
    for record in records:
        for field in record:
            if field not in fields:
                fields.append(field)
    return fields


def write_csv(path: Path, records: Sequence[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=csv_fields(records))
        writer.writeheader()
        writer.writerows(records)
    temporary.replace(path)


def case_from_mapping(item: Any, default_repeats: int) -> Case:
    if not isinstance(item, dict):
        raise ValueError("each case-file entry must be an object")
    missing = [key for key in ("N", "D") if key not in item]
    if missing:
        raise ValueError(
            "missing required field(s): " + ", ".join(missing)
        )
    try:
        case = Case(
            n=int(item["N"]),
            d=int(item["D"]),
            seed=int(item.get("seed", 1)),
            case_kind=str(item.get("case_kind", "main")),
            repeats=int(item.get("repeats", default_repeats)),
            timeout_seconds=(
                int(item["timeout_seconds"])
                if item.get("timeout_seconds") is not None
                else None
            ),
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid field value: {error}") from error
    validate_case(case)
    return case


def validate_run_options(args: argparse.Namespace) -> None:
    positive_options = (
        ("timeout_seconds", "--timeout-seconds"),
        ("large_timeout_seconds", "--large-timeout-seconds"),
        ("build_timeout_seconds", "--build-timeout-seconds"),
        ("jobs", "--jobs"),
    )
    for attribute, option in positive_options:
        if getattr(args, attribute) <= 0:
            raise ValueError(f"{option} must be positive")


def load_cases(args: argparse.Namespace) -> list[Case]:
    validate_run_options(args)
    if not 3 <= args.repeats <= 16:
        raise ValueError("repeats must be in [3, 16]")
    cases = [parse_case(value, args.repeats) for value in args.case]
    if args.case_file:
        payload = json.loads(args.case_file.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("case file must contain a JSON array")
        for index, item in enumerate(payload):
            try:
                cases.append(case_from_mapping(item, args.repeats))
            except ValueError as error:
                raise ValueError(
                    f"case-file entry {index}: {error}"
                ) from error
    default = Case(1, 1, repeats=args.repeats)
    validate_case(default)
    return cases or [default]


def validate_work_dir(work_dir: Path, repo_root: Path) -> None:
    if not work_dir.name.startswith("work-online-merge-"):
        raise ValueError("work-dir basename must start with work-online-merge-")
    if is_relative_to(work_dir, repo_root):
        raise ValueError("work-dir must be outside the Git worktree")


def validate_raw_record(record: dict[str, Any], case: Case) -> list[str]:
    errors = []
    missing = sorted(REQUIRED_TARGET_FIELDS - record.keys())
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
    implementation = record.get("implementation")
    if implementation not in EXPECTED_IMPLEMENTATIONS:
        errors.append(f"unexpected implementation: {implementation!r}")
    if record.get("status") not in VALID_STATUSES:
        errors.append(f"invalid status: {record.get('status')!r}")
    expected_values = {
        "N": case.n,
        "D": case.d,
        "stride": 4 * case.d,
        "seed": case.seed,
        "case_kind": case.case_kind,
    }
    for key, expected in expected_values.items():
        if record.get(key) != expected:
            errors.append(
                f"{key} mismatch: got {record.get(key)!r}, "
                f"expected {expected!r}"
            )
    try:
        repeat = int(record.get("repeat"))
    except (TypeError, ValueError):
        errors.append("repeat is not an integer")
    else:
        if repeat < -1 or repeat >= case.repeats:
            errors.append(f"repeat out of range: {repeat}")
    try:
        nonfinite = int(record.get("nonfinite", 0))
    except (TypeError, ValueError):
        errors.append("nonfinite is not an integer")
    else:
        if nonfinite and record.get("status") == "pass":
            errors.append("nonfinite output cannot have pass status")
    return errors


def validate_record_set(
    records: list[dict[str, Any]], case: Case
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for index, record in enumerate(records):
        for message in validate_raw_record(record, case):
            errors.append(
                {
                    "kind": "invalid_target_record",
                    "record_index": index,
                    "message": message,
                }
            )
        key = (record.get("implementation"), record.get("repeat"))
        if key in seen:
            errors.append(
                {
                    "kind": "duplicate_target_record",
                    "record_index": index,
                    "message": f"duplicate implementation/repeat {key!r}",
                }
            )
        seen.add(key)

    for implementation in EXPECTED_IMPLEMENTATIONS:
        implementation_records = [
            record
            for record in records
            if record.get("implementation") == implementation
        ]
        if not implementation_records:
            errors.append(
                {
                    "kind": "missing_implementation",
                    "implementation": implementation,
                }
            )
            continue
        statuses = {record.get("status") for record in implementation_records}
        repeats = {record.get("repeat") for record in implementation_records}
        has_runtime_terminal = bool(statuses & {"timeout", "tool_error"})
        has_case_terminal = bool(statuses & {"capacity_skip", "unsupported"})
        if has_case_terminal:
            if repeats != {-1} or len(implementation_records) != 1:
                errors.append(
                    {
                        "kind": "invalid_terminal_record_set",
                        "implementation": implementation,
                    }
                )
        elif not has_runtime_terminal:
            expected_repeats = set(range(case.repeats))
            if repeats != expected_repeats or len(implementation_records) != (
                case.repeats
            ):
                errors.append(
                    {
                        "kind": "incomplete_repeat_set",
                        "implementation": implementation,
                        "got": sorted(repeats),
                        "expected": sorted(expected_repeats),
                    }
                )
    return errors


def normalize_target_records(
    raw_records: list[dict[str, Any]],
    case: Case,
    metadata: dict[str, Any],
    command: CommandRecord,
    parse_errors: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    validation_errors = list(parse_errors)
    validation_errors.extend(validate_record_set(raw_records, case))
    enriched: list[dict[str, Any]] = []
    for index, raw_record in enumerate(raw_records):
        try:
            record = enrich_record(raw_record, metadata)
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            validation_errors.append(
                {
                    "kind": "record_enrichment_error",
                    "record_index": index,
                    "message": str(error),
                }
            )
            continue
        record["target_status"] = record.get("status")
        record["command_status"] = command.status
        record["command_returncode"] = command.returncode
        enriched.append(record)

    target_statuses = {
        str(record.get("target_status")) for record in enriched
    }
    command_failure_explained = bool(
        target_statuses & {"correctness_fail", "timeout", "tool_error"}
    )
    force_tool_error = bool(validation_errors)
    if command.status == "tool_error" and not command_failure_explained:
        force_tool_error = True
    if force_tool_error:
        for record in enriched:
            record["status"] = "tool_error"
    if command.status == "timeout":
        for record in enriched:
            record["status"] = "timeout"
            record["failure_reason"] = (
                f"host wall-clock timeout after {command.timeout_seconds} "
                "seconds"
            )

    present = {record.get("implementation") for record in enriched}
    missing_status = (
        "timeout" if command.status == "timeout" else "tool_error"
    )
    for synthetic in synthetic_records(
        case,
        missing_status,
        "missing or malformed target records",
    ):
        if synthetic["implementation"] in present:
            continue
        synthetic.update(metadata)
        synthetic["target_status"] = None
        synthetic["command_status"] = command.status
        synthetic["command_returncode"] = command.returncode
        enriched.append(synthetic)
    if not enriched:
        enriched = synthetic_records(case, missing_status, "no target records")
        for record in enriched:
            record.update(metadata)
            record["target_status"] = None
            record["command_status"] = command.status
            record["command_returncode"] = command.returncode
    return enriched, validation_errors


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_root = script.parents[2]
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
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
        default=default_root.parent / f"work-online-merge-run-{timestamp}",
    )
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--case-file", type=Path)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--large-timeout-seconds", type=int, default=3600)
    parser.add_argument("--build-timeout-seconds", type=int, default=900)
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument(
        "--cmake-define",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "repeatable non-case CMake cache definition; per-case "
            "ONLINE_MERGE_* keys are reserved"
        ),
    )
    parser.add_argument(
        "--objdump",
        type=Path,
        default=default_root / "install/llvm/bin/llvm-objdump",
    )
    parser.add_argument(
        "--build-target",
        default="test-spatzBenchmarks-online-softmax-merge",
    )
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--no-configure", action="store_true")
    parser.add_argument("--no-build", action="store_true")
    return parser.parse_args(argv)


def add_common_metadata(
    records: list[dict[str, Any]], metadata: dict[str, Any]
) -> None:
    for record in records:
        for key, value in metadata.items():
            record.setdefault(key, value)


def persist_incremental(
    work_dir: Path,
    records: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    commands: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> None:
    write_json(work_dir / "records.json", records)
    write_csv(work_dir / "records.csv", records)
    write_json(work_dir / "failures.json", failures)
    write_json(work_dir / "summary.json", summarize(records))
    write_json(work_dir / "commands.json", commands)
    write_json(work_dir / "artifact_manifest.json", artifacts)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    source_dir = args.source_dir.resolve()
    build_dir = args.build_dir.resolve()
    simulator = args.simulator.resolve()
    objdump = args.objdump.resolve()
    cfg = args.cfg.resolve()
    work_dir = args.work_dir.resolve()

    try:
        cases = load_cases(args)
        cmake_defines = parse_cmake_defines(args.cmake_define)
        validate_work_dir(work_dir, repo_root)
    except (
        ValueError,
        argparse.ArgumentTypeError,
        json.JSONDecodeError,
    ) as error:
        raise SystemExit(f"invalid experiment request: {error}") from error
    if not cfg.is_file():
        raise SystemExit(f"CFG does not exist: {cfg}")
    work_dir.mkdir(parents=True, exist_ok=True)

    git_commit = git_output(repo_root, "rev-parse", "HEAD")
    git_dirty = bool(git_output(repo_root, "status", "--porcelain"))
    cfg_hash = sha256_file(cfg)
    tool_versions = detect_tool_versions(
        repo_root, simulator, build_dir, args.cmake, objdump
    )
    tool_version = json.dumps(
        tool_versions, sort_keys=True, separators=(",", ":")
    )
    metadata = {
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "cfg_path": display_path(cfg, repo_root),
        "cfg_hash": cfg_hash,
        "tool_version": tool_version,
        "tool_versions": tool_versions,
    }

    all_records: list[dict[str, Any]] = []
    all_failures: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    elf = (
        build_dir
        / "spatzBenchmarks/test-spatzBenchmarks-online-softmax-merge"
    )

    artifacts.append(
        artifact_entry(
            cfg,
            repo_root,
            git_commit,
            cfg_hash,
            tool_version,
            "all",
            "fixed cluster configuration",
        )
    )
    if simulator.is_file():
        artifacts.append(
            artifact_entry(
                simulator,
                repo_root,
                git_commit,
                cfg_hash,
                tool_version,
                "all",
                "Verilator simulator executable",
            )
        )

    for case in cases:
        case_dir = work_dir / case.slug
        case_dir.mkdir(parents=True, exist_ok=True)
        failures: list[dict[str, Any]] = []

        if not capacity_fits(case):
            case_records = synthetic_records(
                case,
                "capacity_skip",
                "allocator-rounded footprint exceeds 70% TCDM limit",
            )
            for record in case_records:
                record["host_capacity_precheck"] = True
            add_common_metadata(case_records, metadata)
            all_records.extend(case_records)
            persist_incremental(
                work_dir,
                all_records,
                all_failures,
                commands,
                artifacts,
            )
            continue

        if not simulator.is_file():
            case_records = synthetic_records(
                case, "tool_error", f"simulator does not exist: {simulator}"
            )
            add_common_metadata(case_records, metadata)
            all_records.extend(case_records)
            persist_incremental(
                work_dir,
                all_records,
                all_failures,
                commands,
                artifacts,
            )
            continue

        case_status = "pass"
        failure_reason: str | None = None
        if not args.no_configure:
            configure_argv = make_configure_argv(
                args.cmake,
                source_dir,
                build_dir,
                case,
                cmake_defines,
            )
            command, _ = run_command(
                configure_argv,
                case_dir / "configure.log",
                args.build_timeout_seconds,
                repo_root,
            )
            commands.append(asdict(command))
            artifacts.append(
                artifact_entry(
                    case_dir / "configure.log",
                    repo_root,
                    git_commit,
                    cfg_hash,
                    tool_version,
                    case.slug,
                    "host build configuration",
                )
            )
            case_status = command.status
            failure_reason = (
                None
                if case_status == "pass"
                else f"configure command status={case_status}"
            )

        if case_status == "pass" and not args.no_build:
            build_argv = [
                args.cmake,
                "--build",
                str(build_dir),
                "--target",
                args.build_target,
                "--parallel",
                str(args.jobs),
            ]
            command, _ = run_command(
                build_argv,
                case_dir / "build.log",
                args.build_timeout_seconds,
                repo_root,
            )
            commands.append(asdict(command))
            artifacts.append(
                artifact_entry(
                    case_dir / "build.log",
                    repo_root,
                    git_commit,
                    cfg_hash,
                    tool_version,
                    case.slug,
                    "host target build",
                )
            )
            case_status = command.status
            failure_reason = (
                None
                if case_status == "pass"
                else f"build command status={case_status}"
            )

        case_elf = case_dir / "online-softmax-merge.elf"
        if case_status == "pass":
            if not elf.is_file():
                case_status = "tool_error"
                failure_reason = f"target ELF does not exist: {elf}"
            else:
                shutil.copy2(elf, case_elf)
                artifacts.append(
                    artifact_entry(
                        case_elf,
                        repo_root,
                        git_commit,
                        cfg_hash,
                        tool_version,
                        case.slug,
                        "exact target ELF executed for this case",
                    )
                )

        if case_status == "pass":
            disassembly_log = case_dir / "rvv_objdump.log"
            disassembly_snippet = case_dir / "online_merge_rvv_update.disasm"
            command, gate_reason = run_rvv_disassembly_gate(
                objdump,
                case_elf,
                disassembly_log,
                disassembly_snippet,
                args.build_timeout_seconds,
                case_dir,
            )
            commands.append(asdict(command))
            artifacts.append(
                artifact_entry(
                    disassembly_log,
                    repo_root,
                    git_commit,
                    cfg_hash,
                    tool_version,
                    case.slug,
                    "RVV target disassembly gate and full objdump",
                )
            )
            if disassembly_snippet.is_file():
                artifacts.append(
                    artifact_entry(
                        disassembly_snippet,
                        repo_root,
                        git_commit,
                        cfg_hash,
                        tool_version,
                        case.slug,
                        "online_merge_rvv_update target instruction snippet",
                    )
                )
            if gate_reason is not None:
                case_status = "tool_error"
                failure_reason = gate_reason
                failures.append(
                    {
                        "kind": "rvv_disassembly_gate",
                        "message": gate_reason,
                    }
                )

        if case_status != "pass":
            case_records = synthetic_records(
                case,
                case_status,
                failure_reason or "host build/setup failure",
            )
        else:
            timeout = case.timeout_seconds
            if timeout is None:
                timeout = (
                    args.large_timeout_seconds
                    if case.n * case.d >= 1024
                    else args.timeout_seconds
                )
            (case_dir / "logs").mkdir(parents=True, exist_ok=True)
            command, output = run_command(
                [str(simulator), str(case_elf)],
                case_dir / "simulator.log",
                timeout,
                case_dir,
            )
            commands.append(asdict(command))
            artifacts.append(
                artifact_entry(
                    case_dir / "simulator.log",
                    repo_root,
                    git_commit,
                    cfg_hash,
                    tool_version,
                    case.slug,
                    "SPATZ_STATUS marker; cycle window inside marker",
                )
            )
            artifacts.extend(
                generated_simulator_artifacts(
                    case_dir,
                    repo_root,
                    git_commit,
                    cfg_hash,
                    tool_version,
                    case.slug,
                )
            )
            raw_records, failures, parse_errors = parse_target_output(output)
            if command.status == "timeout" and not raw_records:
                case_records = synthetic_records(
                    case,
                    "timeout",
                    f"host wall-clock timeout after {timeout} seconds",
                )
                for record in case_records:
                    record["command_status"] = command.status
                    record["command_returncode"] = command.returncode
                failures.extend(parse_errors)
            else:
                case_records, validation_errors = normalize_target_records(
                    raw_records,
                    case,
                    metadata,
                    command,
                    parse_errors,
                )
                failures.extend(validation_errors)

        add_common_metadata(case_records, metadata)
        all_records.extend(case_records)
        for failure in failures:
            failure.update(metadata)
            failure["workload"] = case.slug
            all_failures.append(failure)
        persist_incremental(
            work_dir,
            all_records,
            all_failures,
            commands,
            artifacts,
        )

    run_manifest = {
        **metadata,
        "objective": (
            "compact-buffer B1/B2-R/A1/B3 timing, correctness, RVV gate, "
            "timeout, and structured-result framework"
        ),
        "wall_clock_start_end": {
            "first_command_start": (
                commands[0]["start_utc"] if commands else None
            ),
            "last_command_end": commands[-1]["end_utc"] if commands else None,
        },
        "cases": [asdict(case) for case in cases],
        "cmake_definitions": cmake_define_manifest(cmake_defines),
        "capacity_protocol": {
            "tcdm_capacity_bytes": TCDM_CAPACITY_BYTES,
            "working_set_limit_bytes": TCDM_LIMIT_BYTES,
            "allocation_alignment_bytes": ALLOCATION_ALIGNMENT_BYTES,
            "footprint_formula": "N * (40 + 16D)",
        },
        "known_limitations": [
            "Verilator cycles are a same-configuration runtime proxy.",
            "Generic counters and correctness metrics are not physical PPA.",
            "A dirty run is validation-only and must not be published as a "
            "formal checkpoint.",
        ],
        "validation_result": {
            "statuses": sorted(
                {str(record.get("status")) for record in all_records}
            ),
            "record_count": len(all_records),
            "failure_count": len(all_failures),
        },
        "artifact_index": "artifact_manifest.json",
        "exact_commands": "commands.json",
    }
    write_json(work_dir / "run_manifest.json", run_manifest)

    failed = any(
        record.get("status")
        not in ("pass", "capacity_skip", "unsupported")
        for record in all_records
    )
    print(f"results={work_dir}")
    print(f"records={len(all_records)} failed={int(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
