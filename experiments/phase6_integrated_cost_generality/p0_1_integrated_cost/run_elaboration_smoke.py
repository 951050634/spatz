#!/usr/bin/env python3
"""Read/elaborate both matched P0-1 source configurations.

This is a Gate 1 compatibility smoke only.  It uses the exact Bender flist
construction and pre-SMU source overlay used by the formal runner, then runs
only Slang elaboration and ``hierarchy -check``.  No process, ABC, mapping, or
``stat`` command is issued and no formal result is produced.
"""

from __future__ import annotations

import csv
import importlib.util
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
SCRATCH = ROOT / "work-artifacts" / "work-phase6-integrated-elab-smoke"
LOG_ROOT = SCRIPT_DIR / "logs"
RUNNER = SCRIPT_DIR / "run_matched_synthesis.py"
TOP = "spatz_cluster_wrapper"
CONFIGS = (("baseline", "Spatz_Baseline"), ("smu", "Spatz_Mixed_SMU"))


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_runner():
    spec = importlib.util.spec_from_file_location("p0_1_runner", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load matched synthesis runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def command_text(command: list[str]) -> str:
    return shlex.join(str(part) for part in command)


def main() -> int:
    runner = load_runner()
    for path in (runner.BENDER, runner.YOSYS, runner.SLANG,
                 runner.SRAM_BLACKBOX):
        if not path.is_file():
            raise RuntimeError(f"required P0-1 smoke input is missing: {path}")
    if SCRATCH.exists() and any(SCRATCH.iterdir()):
        raise RuntimeError(f"refusing stale elaboration smoke directory: {SCRATCH}")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    overlay = runner.materialize_overlay(SCRATCH / "baseline_source_overlay")
    flists = {
        "baseline": runner.write_flist(SCRATCH / "baseline_cluster.f", True,
                                        overlay),
        "smu": runner.write_flist(SCRATCH / "smu_cluster.f", False, overlay),
    }
    rows = []
    for kind, name in CONFIGS:
        flist = Path(flists[kind]["path"])
        work_dir = SCRATCH / name
        work_dir.mkdir(parents=True, exist_ok=True)
        flow = work_dir / "elaboration.ys"
        flow.write_text(
            "\n".join((
                f"plugin -i {runner.SLANG}",
                f"read_slang --std 1800-2017 --single-unit --top {TOP} "
                f"--keep-hierarchy --no-proc -j 1 "
                f"-W no-implicit-port-type-mismatch -F {flist}",
                f"hierarchy -check -top {TOP}",
            )) + "\n", encoding="utf-8")
        command = [str(runner.YOSYS), "-Q", "-s", str(flow)]
        log = LOG_ROOT / f"elab_{kind}.log"
        started_at = timestamp()
        started = time.time()
        with log.open("w", encoding="utf-8") as stream:
            stream.write(f"COMMAND {command_text(command)}\n")
            stream.write(f"FLOW {flow}\n")
            stream.write(f"FLIST {flist}\n")
            stream.write(f"STARTED_AT {started_at}\n")
            stream.flush()
            completed = subprocess.run(
                command, cwd=work_dir, check=False, text=True,
                stdout=stream, stderr=subprocess.STDOUT,
            )
            completed_at = timestamp()
            stream.write(f"RETURN_CODE {completed.returncode}\n")
            stream.write(f"COMPLETED_AT {completed_at}\n")
            stream.write(f"ELAPSED_S {time.time() - started:.1f}\n")
        rows.append({
            "configuration": name,
            "flist": str(flist),
            "flow": str(flow),
            "command": command_text(command),
            "return_code": completed.returncode,
            "started_at": started_at,
            "completed_at": completed_at,
            "log": str(log),
        })
    summary = LOG_ROOT / "elab_smoke_summary.csv"
    with summary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if any(row["return_code"] != 0 for row in rows):
        raise RuntimeError(f"elaboration smoke failed; see {summary}")
    print(f"P0-1 elaboration smoke PASS: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
