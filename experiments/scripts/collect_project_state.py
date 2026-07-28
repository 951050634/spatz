#!/usr/bin/env python3
"""Collect the current repository and tool state without updating tools."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import experiment_common as common


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    root = common.REPO_ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def version(executable: Path | None, argument: str = "--version") -> str:
    if executable is None or not executable.is_file():
        return "NOT_FOUND"
    payload = common.command_version([str(executable), argument])
    return str(payload.get("version") or payload.get("detail") or "UNKNOWN")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.repo_root.resolve()
    output = (
        args.output.resolve()
        if args.output
        else root
        / "experiments/manifests"
        / f"project_state_{common.utc_run_stamp()}.md"
    )
    if output.exists():
        raise SystemExit(f"refusing to overwrite project state: {output}")
    cfg = (
        root
        / "hw/system/spatz_cluster/cfg/"
        "spatz_cluster.default.dram.hjson"
    )
    clang = root / "install/llvm/bin/clang"
    gcc = root / "install/riscv-gcc/bin/riscv32-unknown-elf-gcc"
    verilator = root / "install/verilator/bin/verilator"
    yosys_name = shutil.which("yosys")
    openroad_name = shutil.which("openroad")
    yosys = Path(yosys_name) if yosys_name else None
    openroad = Path(openroad_name) if openroad_name else None
    head = common.git_output(root, "rev-parse", "HEAD")
    branch = common.git_output(root, "branch", "--show-current")
    dirty = bool(common.git_output(root, "status", "--porcelain"))
    lines = [
        "# Project State",
        "",
        f"Collected at `{common.utc_now()}` without updating any tool, "
        "submodule, PDK, or library.",
        "",
        "| Item | Value |",
        "| --- | --- |",
        f"| Repository HEAD | `{head}` |",
        f"| Branch | `{branch}` |",
        f"| Worktree dirty | `{str(dirty).lower()}` |",
        "| Local Spatz base commit | "
        "`948985eaa4c88132f7786bbd9ce019a800e744d8` |",
        "| First SMU commit | "
        "`957667edb213cc748252d486554ff54b3b41fefe` |",
        f"| Default cluster CFG | `{cfg.relative_to(root)}` |",
        f"| CFG SHA256 | `{common.sha256_file(cfg)}` |",
        "| Cluster top | `spatz_cluster` |",
        "| SMU top | `online_merge_update_engine` |",
        "| Benchmark source | "
        "`sw/spatzBenchmarks/online-softmax-merge/` |",
        "| Legacy binary | "
        "`hw/system/spatz_cluster/sw/build/spatzBenchmarks/"
        "test-spatzBenchmarks-online-softmax-merge` |",
        f"| LLVM | {version(clang)} |",
        f"| RISC-V GCC | {version(gcc)} |",
        f"| Verilator | {version(verilator)} |",
        f"| Yosys | {version(yosys, '-V')} |",
        f"| OpenROAD / ORFS | {version(openroad)} |",
        "",
        "The repository has no configured official PULP upstream remote. "
        "The base commit above is therefore a local pre-SMU base, not a "
        "verified official release identity.",
        "",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
