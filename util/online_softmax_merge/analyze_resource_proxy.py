#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Analyze a captured Yosys generic-resource proxy run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence

REQUIRED_SCOPES = ("exp", "reciprocal", "full")
SCOPE_LABELS = {
    "exp": "exp approximation",
    "reciprocal": "reciprocal approximation",
    "vector": "vector arithmetic/data path",
    "full": "full SMU",
}
PRE_OPERATOR_TYPES = {
    "add_sub": ("$add", "$sub", "$neg"),
    "multiply": ("$mul",),
    "mux": ("$mux", "$pmux", "$bmux"),
    "compare": ("$eq", "$ne", "$lt", "$le", "$gt", "$ge"),
    "shift": ("$shl", "$shr", "$sshl", "$sshr"),
    "logic": (
        "$and", "$or", "$xor", "$xnor", "$not", "$logic_and",
        "$logic_or", "$logic_not", "$reduce_and", "$reduce_or",
        "$reduce_xor", "$reduce_xnor", "$reduce_bool",
    ),
}
FF_TYPE = re.compile(r"(?:^\$(?:a|s)?dff|^\$_DFF|^\$_SDFF|^\$_DFFE)")
MEMORY_TYPE = re.compile(r"^\$(?:mem|rom|lut)")
ANALYZER_PATH = Path("util/online_softmax_merge/analyze_resource_proxy.py")


class AnalysisError(ValueError):
    """Raised when captured evidence cannot support the proxy report."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path, expected_type: type) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AnalysisError(f"cannot read {path}: {error}") from error
    if not isinstance(value, expected_type):
        raise AnalysisError(
            f"{path} must contain {expected_type.__name__}"
        )
    return value


def git_context(repo_root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return completed.stdout.strip()

    return {
        "commit": run("rev-parse", "HEAD"),
        "dirty": bool(run("status", "--porcelain")),
    }


def decode_parameter(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise AnalysisError(f"{field} is boolean, expected an integer")
    if isinstance(value, int):
        return value
    if not isinstance(value, str) or not value:
        raise AnalysisError(f"{field} is not an encoded integer: {value!r}")
    if re.fullmatch(r"[01]+", value):
        return int(value, 2)
    if re.fullmatch(r"[0-9]+", value):
        return int(value, 10)
    raise AnalysisError(f"{field} has unsupported encoding: {value!r}")


def normalize_cell_counts(value: Any, context: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise AnalysisError(f"{context} cell counts are not an object")
    result = {}
    for cell_type, count in value.items():
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise AnalysisError(f"invalid count for {cell_type} in {context}")
        result[str(cell_type)] = count
    return dict(sorted(result.items()))


def validate_stat(
    payload: dict[str, Any], top: str, stage: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    modules = payload.get("modules")
    design = payload.get("design")
    if not isinstance(modules, dict) or not isinstance(design, dict):
        raise AnalysisError(f"{stage} stat lacks modules/design objects")
    normalized = {str(name).lstrip("\\"): data for name, data in modules.items()}
    if top not in normalized:
        raise AnalysisError(f"{stage} stat lacks expected top {top}")

    module_rows = []
    module_cell_sum = 0
    for module_name in sorted(normalized):
        data = normalized[module_name]
        if not isinstance(data, dict):
            raise AnalysisError(f"invalid module stat for {module_name}")
        num_cells = data.get("num_cells")
        if isinstance(num_cells, bool) or not isinstance(num_cells, int):
            raise AnalysisError(f"invalid num_cells for {module_name}")
        counts = normalize_cell_counts(
            data.get("num_cells_by_type", {}), module_name
        )
        if sum(counts.values()) != num_cells:
            raise AnalysisError(f"cell-type sum mismatch for {module_name}")
        module_cell_sum += num_cells
        module_rows.append({
            "module": module_name,
            "stage": stage,
            "num_cells": num_cells,
            "num_wire_bits": data.get("num_wire_bits", 0),
            "num_memory_bits": data.get("num_memory_bits", 0),
            "cell_types": counts,
        })

    design_cells = design.get("num_cells")
    if design_cells != module_cell_sum:
        raise AnalysisError(
            f"{stage} design/module cell sum mismatch: "
            f"{design_cells} != {module_cell_sum}"
        )
    counts = normalize_cell_counts(
        design.get("num_cells_by_type", {}), f"{stage} design"
    )
    if sum(counts.values()) != design_cells:
        raise AnalysisError(f"{stage} design cell-type sum mismatch")
    summary = {
        "creator": payload.get("creator"),
        "num_cells": design_cells,
        "num_wire_bits": design.get("num_wire_bits", 0),
        "num_memories": design.get("num_memories", 0),
        "num_memory_bits": design.get("num_memory_bits", 0),
        "cell_types": counts,
    }
    return summary, module_rows


def iter_cells(netlist: dict[str, Any]) -> Iterable[tuple[str, str, dict[str, Any]]]:
    modules = netlist.get("modules")
    if not isinstance(modules, dict):
        raise AnalysisError("netlist lacks modules object")
    for module_name in sorted(modules):
        module = modules[module_name]
        if not isinstance(module, dict) or not isinstance(module.get("cells"), dict):
            raise AnalysisError(f"invalid cells object in {module_name}")
        for cell_name in sorted(module["cells"]):
            cell = module["cells"][cell_name]
            if not isinstance(cell, dict) or not isinstance(cell.get("type"), str):
                raise AnalysisError(f"invalid cell {module_name}/{cell_name}")
            yield str(module_name).lstrip("\\"), str(cell_name), cell


def inspect_pre_netlist(netlist: dict[str, Any]) -> dict[str, Any]:
    multipliers = []
    register_bits = 0
    register_cells = 0
    memory_like_cells = 0
    memory_like_types: Counter[str] = Counter()
    for module, cell_name, cell in iter_cells(netlist):
        cell_type = cell["type"]
        parameters = cell.get("parameters", {})
        if not isinstance(parameters, dict):
            raise AnalysisError(f"invalid parameters for {module}/{cell_name}")
        if cell_type == "$mul":
            multipliers.append({
                "module": module,
                "cell": cell_name,
                "A_WIDTH": decode_parameter(parameters.get("A_WIDTH"), "A_WIDTH"),
                "B_WIDTH": decode_parameter(parameters.get("B_WIDTH"), "B_WIDTH"),
                "Y_WIDTH": decode_parameter(parameters.get("Y_WIDTH"), "Y_WIDTH"),
                "A_SIGNED": decode_parameter(parameters.get("A_SIGNED"), "A_SIGNED"),
                "B_SIGNED": decode_parameter(parameters.get("B_SIGNED"), "B_SIGNED"),
            })
        if FF_TYPE.match(cell_type):
            register_cells += 1
            register_bits += decode_parameter(parameters.get("WIDTH"), "WIDTH")
        if MEMORY_TYPE.match(cell_type):
            memory_like_cells += 1
            memory_like_types[cell_type] += 1
    return {
        "multipliers": multipliers,
        "register_cells": register_cells,
        "register_bits": register_bits,
        "memory_like_cells": memory_like_cells,
        "memory_like_types": dict(sorted(memory_like_types.items())),
    }


def categorized_operators(counts: dict[str, int]) -> dict[str, int]:
    return {
        category: sum(counts.get(cell_type, 0) for cell_type in types)
        for category, types in PRE_OPERATOR_TYPES.items()
    }


def validate_input_hashes(
    repo_root: Path, entries: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    checked = []
    for entry in entries:
        relative = entry.get("relative_or_external_path")
        expected = entry.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise AnalysisError("input manifest entry lacks path/hash")
        path = (repo_root / relative).resolve()
        actual = sha256_file(path) if path.is_file() else None
        checked.append({
            "role": entry.get("role"),
            "path": relative,
            "expected_sha256": expected,
            "actual_sha256": actual,
            "matches": actual == expected,
        })
    return checked


def validate_artifact_hashes(
    root: Path, entries: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    checked = []
    for entry in entries:
        relative = entry.get("relative_or_external_path")
        expected = entry.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise AnalysisError("artifact manifest entry lacks path/hash")
        raw_path = Path(relative)
        path = raw_path if raw_path.is_absolute() else root / raw_path
        actual = sha256_file(path) if path.is_file() else None
        checked.append({
            "role": entry.get("role"),
            "scope": entry.get("synthesis_scope"),
            "path": relative,
            "expected_sha256": expected,
            "actual_sha256": actual,
            "matches": actual == expected,
        })
    return checked


def analyze(repo_root: Path, result_root: Path) -> dict[str, Any]:
    root = result_root.resolve()
    required_files = (
        "run_manifest.json", "scope_results.json", "failures.json",
        "commands.json", "artifact_manifest.json", "input_manifest.json",
    )
    missing = [name for name in required_files if not (root / name).is_file()]
    if missing:
        raise AnalysisError(f"capture root is missing {missing}")
    manifest = load_json(root / "run_manifest.json", dict)
    results = load_json(root / "scope_results.json", list)
    failures = load_json(root / "failures.json", list)
    commands = load_json(root / "commands.json", list)
    artifacts = load_json(root / "artifact_manifest.json", list)
    inputs = load_json(root / "input_manifest.json", list)
    result_by_scope = {row.get("scope"): row for row in results}
    if len(result_by_scope) != len(results):
        raise AnalysisError("scope results contain duplicate scope names")

    scopes = []
    multiplier_rows = []
    cell_type_rows = []
    module_rows = []
    for scope in manifest.get("requested_scopes", []):
        result = result_by_scope.get(scope)
        if not isinstance(result, dict) or result.get("status") != "pass":
            continue
        top = result.get("top")
        if not isinstance(top, str):
            raise AnalysisError(f"scope {scope} lacks top name")
        pre_payload = load_json(root / scope / "pre-stat.json", dict)
        post_payload = load_json(root / scope / "post-stat.json", dict)
        pre, pre_modules = validate_stat(pre_payload, top, "pre_techmap")
        post, post_modules = validate_stat(post_payload, top, "post_techmap")
        netlist = load_json(root / scope / "pre-netlist.json", dict)
        structural = inspect_pre_netlist(netlist)
        if len(structural["multipliers"]) != pre["cell_types"].get("$mul", 0):
            raise AnalysisError(f"scope {scope} multiplier count mismatch")
        operators = categorized_operators(pre["cell_types"])
        scope_row = {
            "scope": scope,
            "decomposition_label": SCOPE_LABELS.get(scope, scope),
            "independent_scope_is_additive": False,
            "pre": pre,
            "post": post,
            "operators": operators,
            **{key: value for key, value in structural.items()
               if key != "multipliers"},
        }
        scopes.append(scope_row)
        multiplier_rows.extend(
            {"scope": scope, **row} for row in structural["multipliers"]
        )
        for stage, summary in (("pre_techmap", pre), ("post_techmap", post)):
            cell_type_rows.extend({
                "scope": scope, "stage": stage,
                "cell_type": cell_type, "count": count,
            } for cell_type, count in summary["cell_types"].items())
        module_rows.extend(
            {"scope": scope, **row} for row in pre_modules + post_modules
        )

    provenance = git_context(repo_root)
    input_checks = validate_input_hashes(repo_root, inputs)
    artifact_checks = validate_artifact_hashes(root, artifacts)
    scope_names = {row["scope"] for row in scopes}
    gates = {
        "capture_manifest_pass": manifest.get("status") == "pass",
        "capture_marked_resource_proxy_evidence": (
            manifest.get("resource_proxy_evidence") is True
        ),
        "capture_git_clean": manifest.get("git_dirty") is False,
        "analysis_git_clean": not provenance["dirty"],
        "required_scopes_present": set(REQUIRED_SCOPES).issubset(scope_names),
        "all_requested_scopes_pass": len(scopes) == len(results),
        "capture_failures_empty": not failures,
        "capture_commands_pass": bool(commands) and all(
            row.get("status") == "pass" for row in commands
        ),
        "current_inputs_match_capture": bool(input_checks) and all(
            row["matches"] for row in input_checks
        ),
        "captured_artifact_hashes_match": bool(artifact_checks) and all(
            row["matches"] for row in artifact_checks
        ),
        "pre_post_artifacts_indexed": all(
            any(
                row.get("synthesis_scope") == scope
                and row.get("role") == role
                for row in artifacts
            )
            for scope in scope_names
            for role in ("pre_stat_json", "pre_netlist_json",
                         "post_stat_json", "post_netlist_json")
        ),
    }
    return {
        "schema_version": 1,
        "title": "Online Softmax Merge Engine generic resource proxy",
        "status": "pass" if all(gates.values()) else "tool_error",
        "resource_proxy_evidence": all(gates.values()),
        "physical_ppa_evidence": False,
        "claim_boundary": (
            "Version-specific Yosys generic logic complexity proxy only; "
            "independent scopes are non-additive."
        ),
        "scope_decomposition": {
            "available": [SCOPE_LABELS.get(name, name) for name in sorted(scope_names)],
            "scalar_fsm_control": {
                "status": "unsupported",
                "reason": (
                    "No independent scalar/FSM/control synthesis top exists; "
                    "subtraction of independently optimized scopes is invalid."
                ),
            },
        },
        "scopes": scopes,
        "multipliers": multiplier_rows,
        "cell_types": cell_type_rows,
        "module_resources": module_rows,
        "acceptance_gates": gates,
        "all_acceptance_gates_pass": all(gates.values()),
        "capture": {
            "root": str(root),
            "manifest": manifest,
            "scope_results": results,
            "failures": failures,
            "commands": commands,
            "artifact_manifest_sha256": sha256_file(root / "artifact_manifest.json"),
        },
        "input_hash_checks": input_checks,
        "artifact_hash_checks": artifact_checks,
        "analysis_provenance": {
            "git": provenance,
            "python": sys.version.split()[0],
            "tool_path": str((repo_root / ANALYZER_PATH).resolve()),
            "tool_sha256": sha256_file((repo_root / ANALYZER_PATH).resolve()),
        },
        "physical_ppa_blocker": {
            "status": "blocked_external",
            "missing": [
                "target PDK", "liberty/LEF", "defined PVT corner",
                "clock/IO/load constraints", "floorplan/routing constraints",
                "signoff synthesis/P&R/timing/power tools",
            ],
            "required_next_action": (
                "Provide fixed external technology inputs and a reproducible "
                "physical implementation/signoff flow."
            ),
        },
        "forbidden_claims": [
            "ASIC area (um^2)", "frequency or Fmax", "critical path",
            "power (mW)", "energy (pJ)", "physical efficiency",
        ],
    }


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    fields = sorted({field for row in rows for field in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(value) for key, value in row.items()})


def resource_summary_rows(scopes: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for scope in scopes:
        row = {
            "scope": scope["scope"],
            "decomposition_label": scope["decomposition_label"],
            "independent_scope_is_additive": False,
            "pre_num_cells": scope["pre"]["num_cells"],
            "post_num_cells": scope["post"]["num_cells"],
            "register_cells": scope["register_cells"],
            "register_bits": scope["register_bits"],
            "memory_like_cells": scope["memory_like_cells"],
            "memory_bits": scope["pre"]["num_memory_bits"],
        }
        row.update({f"operator_{key}": value
                    for key, value in scope["operators"].items()})
        rows.append(row)
    return rows


def validate_output_dir(output_dir: Path, repo_root: Path) -> Path:
    output = output_dir.resolve()
    try:
        output.relative_to(repo_root.resolve())
    except ValueError:
        pass
    else:
        raise AnalysisError("output directory must be outside the Git worktree")
    if not output.name.startswith("work-online-merge-"):
        raise AnalysisError(
            "output directory basename must start with work-online-merge-"
        )
    if output.exists():
        raise AnalysisError(f"output directory already exists: {output}")
    if not output.parent.is_dir():
        raise AnalysisError(f"output parent does not exist: {output.parent}")
    return output


def write_outputs(output: Path, report: dict[str, Any]) -> dict[str, str]:
    output.mkdir()
    analysis_path = output / "analysis.json"
    analysis_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    csv_outputs = {
        "resource_summary.csv": resource_summary_rows(report["scopes"]),
        "multiplier_widths.csv": report["multipliers"],
        "cell_types.csv": report["cell_types"],
        "module_resources.csv": report["module_resources"],
    }
    for name, rows in csv_outputs.items():
        write_csv(output / name, rows)
    paths = [analysis_path, *(output / name for name in csv_outputs)]
    hashes = {path.name: sha256_file(path) for path in paths}
    manifest = {
        "analysis_git_commit": report["analysis_provenance"]["git"]["commit"],
        "analysis_git_dirty": report["analysis_provenance"]["git"]["dirty"],
        "analysis_tool": report["analysis_provenance"],
        "capture_root": report["capture"]["root"],
        "capture_artifact_manifest_sha256": (
            report["capture"]["artifact_manifest_sha256"]
        ),
        "outputs": hashes,
    }
    manifest_path = output / "artifact_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    hashes[manifest_path.name] = sha256_file(manifest_path)
    return hashes


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--result-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output = validate_output_dir(args.output_dir, args.repo_root)
    report = analyze(args.repo_root.resolve(), args.result_root)
    hashes = write_outputs(output, report)
    print(json.dumps({
        "output_dir": str(output),
        "outputs": hashes,
        "all_acceptance_gates_pass": report["all_acceptance_gates_pass"],
    }, indent=2, sort_keys=True))
    return 0 if report["all_acceptance_gates_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
