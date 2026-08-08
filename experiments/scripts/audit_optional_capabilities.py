#!/usr/bin/env python3
"""Record optional experiment capabilities without installing tools."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import experiment_common as common


EXPECTED_NUMERICAL_PATTERNS = {
    "both-zero-l",
    "delta-below-neg8",
    "delta-neg8",
    "equal-m",
    "l-old-zero",
    "l-tile-zero",
    "signed-o",
    "small-l",
}
EXPECTED_RVV_TAILS = {1, 7, 15, 17, 31, 33, 63, 65, 127}
TOOL_VERSION_ARGUMENT = {
    "openroad": "-version",
    "sta": "-version",
    "vcd2saif": "--version",
    "yosys": "-V",
}
PYTHON_PACKAGES = ("matplotlib", "numpy", "pandas", "seaborn")


def load_json(path: Path, expected_type: type) -> Any:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, expected_type):
        raise ValueError(f"{path} must contain {expected_type.__name__}")
    return payload


def tool_state(
    name: str,
    which: Callable[[str], str | None] = shutil.which,
) -> dict[str, Any]:
    resolved = which(name)
    if not resolved:
        return {
            "name": name,
            "status": "NOT_FOUND",
            "path": None,
            "sha256": None,
            "version": None,
        }
    path = Path(resolved).resolve()
    version = common.command_version(
        [str(path), TOOL_VERSION_ARGUMENT.get(name, "--version")]
    )
    return {
        "name": name,
        "status": version.get("status", "TOOL_ERROR"),
        "path": str(path),
        "sha256": common.sha256_file(path) if path.is_file() else None,
        "version": version.get("version") or version.get("detail"),
    }


def package_state(
    name: str,
    find_spec: Callable[[str], Any] = importlib.util.find_spec,
) -> dict[str, Any]:
    available = find_spec(name) is not None
    return {
        "name": name,
        "status": "AVAILABLE" if available else "NOT_FOUND",
    }


def p0_4_acceptance(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "P0_4_ANALYSIS_NOT_FOUND"
    report = load_json(path, dict)
    acceptance = report.get("acceptance")
    if not isinstance(acceptance, dict) or not acceptance:
        return False, "P0_4_ACCEPTANCE_MISSING"
    failed = sorted(key for key, value in acceptance.items() if value is not True)
    if failed:
        return False, "P0_4_ACCEPTANCE_FAILED:" + ",".join(failed)
    return True, "P0_4_ACCEPTANCE_PASS"


def catalog_coverage(
    numerical_catalog: list[dict[str, Any]],
    tail_catalog: list[dict[str, Any]],
) -> tuple[bool, dict[str, Any]]:
    patterns = {str(row.get("case_kind")) for row in numerical_catalog}
    tails = {
        int(row["D"])
        for row in tail_catalog
        if isinstance(row.get("D"), int)
    }
    details = {
        "numerical_patterns": sorted(patterns),
        "expected_numerical_patterns": sorted(EXPECTED_NUMERICAL_PATTERNS),
        "rvv_tail_dimensions": sorted(tails),
        "expected_rvv_tail_dimensions": sorted(EXPECTED_RVV_TAILS),
    }
    return (
        patterns == EXPECTED_NUMERICAL_PATTERNS
        and tails == EXPECTED_RVV_TAILS,
        details,
    )


def capability_rows(
    policy: dict[str, Any],
    numerical_catalog: list[dict[str, Any]],
    tail_catalog: list[dict[str, Any]],
    p0_4_analysis: Path,
    tools: dict[str, dict[str, Any]],
    packages: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    configurations = policy.get("configurations", {})
    hardware = policy.get("hardware", {})
    p0_4_ok, p0_4_reason = p0_4_acceptance(p0_4_analysis)
    catalogs_ok, coverage = catalog_coverage(
        numerical_catalog, tail_catalog
    )

    exp_only_absent = "EXP_ONLY" not in configurations
    tile_size = hardware.get("tile_size")
    openroad_missing = tools["openroad"]["status"] == "NOT_FOUND"
    power_tools_missing = [
        name
        for name in ("openroad", "sta", "vcd2saif")
        if tools[name]["status"] == "NOT_FOUND"
    ]
    plot_packages_missing = [
        name
        for name in ("matplotlib", "numpy")
        if packages[name]["status"] == "NOT_FOUND"
    ]

    rows = [
        {
            "capability_id": "EXP_ONLY",
            "requested_scope": "target exponential-only baseline",
            "status": (
                "BLOCKED_NOT_IMPLEMENTED"
                if exp_only_absent
                else "READY_FOR_FORMAL_RUN"
            ),
            "paper_eligible": "NO",
            "reason": (
                "EXP_ONLY_NOT_IMPLEMENTED; software exp() and zero-cost "
                "substitutes are forbidden"
                if exp_only_absent
                else "EXP_ONLY_PRESENT_BUT_NOT_MEASURED"
            ),
            "evidence": "experiments/configs/measurement_policy.json",
        },
        {
            "capability_id": "TILE_SCAN",
            "requested_scope": "independent tile-size sweep",
            "status": (
                "NOT_APPLICABLE"
                if tile_size is None
                else "READY_FOR_FORMAL_RUN"
            ),
            "paper_eligible": "NO",
            "reason": (
                "NO_INDEPENDENT_TILE_PARAMETER"
                if tile_size is None
                else "TILE_PARAMETER_PRESENT_BUT_NOT_MEASURED"
            ),
            "evidence": "experiments/configs/measurement_policy.json",
        },
        {
            "capability_id": "INPUT_PATTERN",
            "requested_scope": "numerical patterns and RVV tail dimensions",
            "status": (
                "COMPLETE_SUPPORTING"
                if catalogs_ok and p0_4_ok
                else "PENDING_OR_BLOCKED"
            ),
            "paper_eligible": "NO",
            "reason": (
                "P0_4_BOUNDARY_COVERAGE_PASS"
                if catalogs_ok and p0_4_ok
                else (
                    "CATALOG_COVERAGE_MISMATCH"
                    if not catalogs_ok
                    else p0_4_reason
                )
            ),
            "evidence": (
                "experiments/configs/p0_numerical_boundary_cases.json;"
                "experiments/configs/p0_rvv_tail_cases.json;"
                f"{p0_4_analysis}"
            ),
            "details": coverage,
        },
        {
            "capability_id": "OPENROAD",
            "requested_scope": "placed-and-routed physical implementation",
            "status": (
                "BLOCKED_TOOLCHAIN"
                if openroad_missing
                else "BLOCKED_PHYSICAL_INPUTS"
            ),
            "paper_eligible": "NO",
            "reason": (
                "OPENROAD_NOT_FOUND"
                if openroad_missing
                else (
                    "NO_FIXED_FLOORPLAN_ROUTING_CLOCK_IO_AND_SIGNOFF_FLOW"
                )
            ),
            "evidence": tools["openroad"].get("path") or "NOT_FOUND",
        },
        {
            "capability_id": "WORKLOAD_POWER_ENERGY",
            "requested_scope": "workload-driven physical power and energy",
            "status": "BLOCKED_EXTERNAL",
            "paper_eligible": "NO",
            "reason": (
                "MISSING_TOOLS="
                + ",".join(power_tools_missing)
                + "; MISSING_GATE_OR_POSTLAYOUT_ACTIVITY_PARASITICS_"
                "CLOCK_TREE_AND_CHARACTERIZED_POWER_FLOW"
            ),
            "evidence": "experiments/power/README.md",
        },
        {
            "capability_id": "FIGURE_RENDERING",
            "requested_scope": "Python PDF/SVG/PNG figure bundle",
            "status": (
                "BLOCKED_PYTHON_PACKAGES"
                if plot_packages_missing
                else "READY"
            ),
            "paper_eligible": "NO",
            "reason": (
                "MISSING_PACKAGES=" + ",".join(plot_packages_missing)
                if plot_packages_missing
                else "PYTHON_PLOT_RUNTIME_AVAILABLE"
            ),
            "evidence": "experiments/scripts/make_plots.py",
        },
    ]
    return rows


def markdown_report(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Optional Experiment Capability Audit",
        "",
        "This audit records executable scope and blockers without installing "
        "or updating any tool, package, PDK, or submodule.",
        "",
        "| Capability | Status | Paper eligible | Reason |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['capability_id']}` | `{row['status']}` | "
            f"`{row['paper_eligible']}` | {row['reason']} |"
        )
    lines.extend(
        [
            "",
            "RTL toggle counts remain a zero-delay activity proxy. This audit "
            "does not convert them into mW, pJ, or physical energy.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=common.REPO_ROOT)
    parser.add_argument(
        "--policy",
        type=Path,
        default=common.REPO_ROOT
        / "experiments/configs/measurement_policy.json",
    )
    parser.add_argument(
        "--numerical-catalog",
        type=Path,
        default=common.REPO_ROOT
        / "experiments/configs/p0_numerical_boundary_cases.json",
    )
    parser.add_argument(
        "--tail-catalog",
        type=Path,
        default=common.REPO_ROOT
        / "experiments/configs/p0_rvv_tail_cases.json",
    )
    parser.add_argument(
        "--p0-4-analysis",
        type=Path,
        default=common.REPO_ROOT
        / "experiments/parsed/p0_4/p0_4_analysis.json",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--require-clean", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise SystemExit(f"refusing to overwrite output directory: {output_dir}")
    dirty = bool(common.git_output(repo_root, "status", "--porcelain"))
    if args.require_clean and dirty:
        raise SystemExit("--require-clean rejected a dirty Git worktree")

    input_paths = {
        "policy": args.policy.resolve(),
        "numerical_catalog": args.numerical_catalog.resolve(),
        "tail_catalog": args.tail_catalog.resolve(),
        "p0_4_analysis": args.p0_4_analysis.resolve(),
    }
    policy = load_json(input_paths["policy"], dict)
    numerical_catalog = load_json(input_paths["numerical_catalog"], list)
    tail_catalog = load_json(input_paths["tail_catalog"], list)
    tool_rows = {
        name: tool_state(name)
        for name in ("openroad", "sta", "vcd2saif", "yosys")
    }
    package_rows = {
        name: package_state(name) for name in PYTHON_PACKAGES
    }
    rows = capability_rows(
        policy,
        numerical_catalog,
        tail_catalog,
        input_paths["p0_4_analysis"],
        tool_rows,
        package_rows,
    )
    report = {
        "schema_version": 1,
        "audit_utc": common.utc_now(),
        "git": {
            "commit": common.git_output(repo_root, "rev-parse", "HEAD"),
            "branch": common.git_output(repo_root, "branch", "--show-current"),
            "dirty": dirty,
        },
        "no_install_or_update_performed": True,
        "proxy_claim_boundary": (
            "RTL toggles are not physical power or energy"
        ),
        "tools": tool_rows,
        "python_packages": package_rows,
        "capabilities": rows,
    }

    output_dir.mkdir(parents=True)
    json_path = output_dir / "optional_capability_audit.json"
    csv_path = output_dir / "optional_capability_audit.csv"
    report_path = output_dir / "OPTIONAL_EXPERIMENT_STATUS.md"
    common.write_json(json_path, report)
    common.write_csv(csv_path, rows)
    report_path.write_text(markdown_report(rows), encoding="utf-8")
    output_paths = [json_path, csv_path, report_path]
    manifest = {
        "schema_version": 1,
        "audit_tool": {
            "path": common.relative_or_absolute(
                Path(__file__).resolve(), repo_root
            ),
            "sha256": common.sha256_file(Path(__file__).resolve()),
            "python": sys.version.split()[0],
        },
        "inputs": [
            {
                "role": role,
                "path": common.relative_or_absolute(path, repo_root),
                "present": path.is_file(),
                "sha256": common.sha256_file(path) if path.is_file() else None,
            }
            for role, path in input_paths.items()
        ],
        "outputs": [
            {
                "path": common.relative_or_absolute(path, repo_root),
                "bytes": path.stat().st_size,
                "sha256": common.sha256_file(path),
            }
            for path in output_paths
        ],
    }
    manifest_path = output_dir / "optional_capability_manifest.json"
    common.write_json(manifest_path, manifest)
    print(f"output_dir={output_dir}")
    for row in rows:
        print(f"{row['capability_id']}={row['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
