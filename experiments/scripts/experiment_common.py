#!/usr/bin/env python3
"""Shared, standard-library-only helpers for paper experiment scripts."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shlex
import signal
import struct
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_PREFIX = "OM_RESULT "
FSM_PREFIX = "OM_FSM "
UINT32_MAX = (1 << 32) - 1


@dataclass
class CommandResult:
    argv: list[str]
    command: str
    cwd: str
    start_utc: str
    end_utc: str
    timeout_seconds: int
    returncode: int | None
    status: str
    log_path: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def utc_run_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(payload: Any) -> str:
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for record in records:
        for field in record:
            if field not in fields:
                fields.append(field)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    key: "NA" if value is None else value
                    for key, value in record.items()
                }
            )
    temporary.replace(path)


def git_output(repo_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def worktree_snapshot(repo_root: Path) -> dict[str, Any]:
    commands = (
        [
            "git",
            "ls-files",
            "--modified",
            "--deleted",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        ["git", "diff", "--cached", "--name-only", "-z"],
    )
    paths: set[str] = set()
    for argv in commands:
        completed = subprocess.run(
            argv,
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                completed.stderr.decode("utf-8", errors="replace")
            )
        paths.update(
            item.decode("utf-8", errors="surrogateescape")
            for item in completed.stdout.split(b"\0")
            if item
        )
    entries: list[dict[str, Any]] = []
    for relative in sorted(paths):
        path = repo_root / relative
        entries.append(
            {
                "path": relative,
                "sha256": sha256_file(path) if path.is_file() else None,
                "state": "present" if path.exists() else "deleted",
            }
        )
    return {"sha256": sha256_json(entries), "entries": entries}


def command_version(argv: Sequence[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            list(argv),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"status": "TOOL_ERROR", "detail": str(error)}
    lines = [line.strip() for line in completed.stdout.splitlines() if line]
    return {
        "status": "PASS" if completed.returncode == 0 else "TOOL_ERROR",
        "returncode": completed.returncode,
        "version": " | ".join(lines[:3]),
    }


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
    cwd: Path,
    log_path: Path,
    timeout_seconds: int,
    environment: Mapping[str, str] | None = None,
) -> tuple[CommandResult, str]:
    start = utc_now()
    output = ""
    returncode: int | None = None
    status = "PASS"
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            list(argv),
            cwd=cwd,
            env={**os.environ, **environment} if environment else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        raw_output, _ = process.communicate(timeout=timeout_seconds)
        returncode = process.returncode
        output = raw_output.decode("utf-8", errors="replace")
        if returncode != 0:
            status = "TOOL_ERROR"
    except subprocess.TimeoutExpired as error:
        status = "TIMEOUT"
        partial = error.output or b""
        output = (
            partial.decode("utf-8", errors="replace")
            if isinstance(partial, bytes)
            else str(partial)
        )
        if process is not None:
            terminate_process_group(process)
            returncode = process.returncode
            if process.stdout is not None:
                output += process.stdout.read().decode(
                    "utf-8", errors="replace"
                )
                process.stdout.close()
        output += f"\nHOST_TIMEOUT seconds={timeout_seconds}\n"
    except OSError as error:
        status = "TOOL_ERROR"
        output = f"HOST_TOOL_ERROR {error}\n"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(output, encoding="utf-8")
    result = CommandResult(
        argv=list(argv),
        command=shlex.join(argv),
        cwd=str(cwd),
        start_utc=start,
        end_utc=utc_now(),
        timeout_seconds=timeout_seconds,
        returncode=returncode,
        status=status,
        log_path=str(log_path),
    )
    return result, output


def command_dict(command: CommandResult) -> dict[str, Any]:
    return asdict(command)


def parse_prefixed_json(output: str, prefix: str) -> tuple[list[dict], list]:
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for line_number, line in enumerate(output.splitlines(), 1):
        if not line.startswith(prefix):
            continue
        try:
            payload = json.loads(line[len(prefix) :])
        except json.JSONDecodeError as error:
            errors.append(
                {
                    "line_number": line_number,
                    "message": str(error),
                    "line": line[:512],
                }
            )
            continue
        if not isinstance(payload, dict):
            errors.append(
                {
                    "line_number": line_number,
                    "message": "structured record is not an object",
                }
            )
            continue
        records.append(payload)
    return records, errors


def float_from_bits(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", value & UINT32_MAX))[0]


def finite_or_none(value: float) -> float | None:
    return value if math.isfinite(value) else None


def enrich_target_record(raw: dict[str, Any]) -> dict[str, Any]:
    record = dict(raw)
    high = int(record.pop("cycles_hi", 0)) & UINT32_MAX
    low = int(record.pop("cycles_lo", 0)) & UINT32_MAX
    record["kernel_cycles"] = (high << 32) | low
    max_abs = float_from_bits(int(record.pop("max_abs_bits", 0)))
    numerator = float_from_bits(
        int(record.pop("max_rel_numerator_bits", 0))
    )
    denominator = float_from_bits(
        int(record.pop("max_rel_denominator_bits", 0))
    )
    sum_sq = float_from_bits(int(record.pop("sum_sq_bits", 0)))
    sum_abs = float_from_bits(int(record.pop("sum_abs_bits", 0)))
    sum_ref_sq = float_from_bits(int(record.pop("sum_ref_sq_bits", 0)))
    checked = int(record.get("checked", 0) or 0)
    bit_equal = int(record.get("bit_equal", 0) or 0)
    record["max_abs_error"] = finite_or_none(max_abs)
    record["max_rel_error"] = finite_or_none(
        numerator / denominator
        if denominator > 0.0 and math.isfinite(denominator)
        else math.nan
    )
    record["mean_abs_error"] = finite_or_none(
        sum_abs / checked if checked else math.nan
    )
    record["rmse"] = finite_or_none(
        math.sqrt(sum_sq / checked)
        if checked and sum_sq >= 0.0
        else math.nan
    )
    record["l2_relative_error"] = finite_or_none(
        math.sqrt(sum_sq / sum_ref_sq)
        if sum_sq >= 0.0 and sum_ref_sq > 0.0
        else math.nan
    )
    record["bit_equal_ratio"] = (
        bit_equal / checked if checked else None
    )
    record["inf_count"] = int(record.get("pos_inf_count", 0) or 0) + int(
        record.get("neg_inf_count", 0) or 0
    )
    return record


def require_fresh_external_root(path: Path, repo_root: Path) -> None:
    if not path.name.startswith("work-online-merge-"):
        raise ValueError(
            "artifact root basename must start with work-online-merge-"
        )
    try:
        path.relative_to(repo_root)
    except ValueError:
        pass
    else:
        raise ValueError("artifact root must be outside the Git worktree")
    if path.exists():
        raise ValueError(f"artifact root already exists: {path}")


def relative_or_absolute(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)
