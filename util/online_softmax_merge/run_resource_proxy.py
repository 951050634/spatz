#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Capture versioned Yosys generic-resource proxy synthesis artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import run_experiments as common

SCHEMA_VERSION = 1
REQUIRED_SCOPES = ("exp", "reciprocal", "full")
DEFAULT_SCOPES = ("exp", "reciprocal", "vector", "full")
RAW_OUTPUTS = (
    "pre-stat.json",
    "pre-stat.txt",
    "pre-netlist.json",
    "post-stat.json",
    "post-stat.txt",
    "post-netlist.json",
)


@dataclass(frozen=True)
class ScopeDefinition:
    name: str
    top: str
    decomposition_label: str
    additive: bool


SCOPES = {
    "exp": ScopeDefinition(
        "exp",
        "online_merge_exp_resource_top",
        "exp approximation",
        False,
    ),
    "reciprocal": ScopeDefinition(
        "reciprocal",
        "online_merge_reciprocal_resource_top",
        "reciprocal approximation",
        False,
    ),
    "vector": ScopeDefinition(
        "vector",
        "online_merge_vector_resource_top",
        "vector arithmetic/data path",
        False,
    ),
    "full": ScopeDefinition(
        "full",
        "online_merge_full_resource_top",
        "full SMU",
        False,
    ),
}

INPUT_FILES = (
    (
        "capture_runner",
        "util/online_softmax_merge/run_resource_proxy.py",
    ),
    (
        "synthesis_wrapper",
        "hw/ip/online_merge/synth/online_merge_resource_wrapper.sv",
    ),
    (
        "yosys_pass_script",
        "hw/ip/online_merge/synth/generic_resource.ys",
    ),
    (
        "rtl_helper_package",
        "hw/ip/online_merge/src/online_merge_fp32_helpers.sv",
    ),
    (
        "rtl_exp_approximation",
        "hw/ip/online_merge/src/online_merge_exp_approx.sv",
    ),
    (
        "rtl_reciprocal_approximation",
        "hw/ip/online_merge/src/online_merge_recip_approx.sv",
    ),
    (
        "rtl_full_update_engine",
        "hw/ip/online_merge/src/online_merge_update_engine.sv",
    ),
    (
        "fixed_configuration_reference",
        "hw/system/spatz_cluster/cfg/spatz_cluster.default.dram.hjson",
    ),
)

SYNTHESIS_SOURCE_ROLES = {
    "synthesis_wrapper",
    "rtl_helper_package",
    "rtl_exp_approximation",
    "rtl_reciprocal_approximation",
    "rtl_full_update_engine",
}


def validate_output_root(work_dir: Path, repo_root: Path) -> None:
    if not work_dir.name.startswith("work-online-merge-"):
        raise ValueError(
            "work-dir basename must start with work-online-merge-"
        )
    if common.is_relative_to(work_dir, repo_root):
        raise ValueError("work-dir must be outside the Git worktree")
    if work_dir.exists() and any(work_dir.iterdir()):
        raise ValueError("work-dir already exists and is not empty")


def yosys_token(value: Path | str) -> str:
    text = str(value)
    if not re.fullmatch(r"[A-Za-z0-9_./:+@=,-]+", text):
        raise ValueError(
            "Yosys command paths must not contain whitespace or metacharacters"
        )
    return text


def synthesis_command(
    definition: ScopeDefinition,
    sources: Sequence[Path],
    script: Path,
) -> str:
    source_tokens = " ".join(yosys_token(path) for path in sources)
    return (
        f"read_slang --std 1800-2017 {source_tokens}; "
        f"hierarchy -check -top {definition.top}; "
        f"script {yosys_token(script)}"
    )


def command_mapping(
    command: common.CommandRecord,
    work_dir: Path,
) -> dict[str, Any]:
    result = asdict(command)
    result["log_path"] = common.display_path(
        Path(command.log_path), work_dir
    )
    return result


def input_manifest(repo_root: Path, git_commit: str) -> list[dict[str, Any]]:
    entries = []
    for role, relative_path in INPUT_FILES:
        path = repo_root / relative_path
        entries.append(
            {
                "role": role,
                "relative_or_external_path": relative_path,
                "exists": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else None,
                "sha256": (
                    common.sha256_file(path) if path.is_file() else None
                ),
                "git_commit": git_commit,
            }
        )
    return entries


def synthesis_sources(
    repo_root: Path,
    inputs: Sequence[dict[str, Any]],
) -> list[Path]:
    return [
        repo_root / str(entry["relative_or_external_path"])
        for entry in inputs
        if entry["role"] in SYNTHESIS_SOURCE_ROLES
    ]


def find_input(
    inputs: Sequence[dict[str, Any]], role: str
) -> dict[str, Any]:
    return next(entry for entry in inputs if entry["role"] == role)


def parse_yosys_version(output: str) -> str | None:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("Yosys "):
            return stripped
    return None


def validate_stat_payload(
    path: Path, expected_top: str
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return None, [f"{path.name}: invalid JSON: {error}"]
    if not isinstance(payload, dict):
        return None, [f"{path.name}: root is not an object"]

    modules = payload.get("modules")
    if not isinstance(modules, dict):
        errors.append(f"{path.name}: modules is not an object")
    else:
        normalized = {str(name).lstrip("\\") for name in modules}
        if expected_top not in normalized:
            errors.append(
                f"{path.name}: missing expected top {expected_top}"
            )

    design = payload.get("design")
    if not isinstance(design, dict):
        errors.append(f"{path.name}: design is not an object")
    else:
        cells = design.get("num_cells")
        if not isinstance(cells, int) or cells < 0:
            errors.append(f"{path.name}: invalid design num_cells")
    if not isinstance(payload.get("creator"), str):
        errors.append(f"{path.name}: missing creator")
    return payload, errors


def validate_scope_outputs(
    scope_dir: Path, expected_top: str
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    errors = []
    stat_payloads: dict[str, dict[str, Any]] = {}
    for name in RAW_OUTPUTS:
        path = scope_dir / name
        if not path.is_file():
            errors.append(f"missing output: {name}")
        elif path.stat().st_size == 0:
            errors.append(f"empty output: {name}")
    for phase in ("pre", "post"):
        path = scope_dir / f"{phase}-stat.json"
        if not path.is_file() or path.stat().st_size == 0:
            continue
        payload, payload_errors = validate_stat_payload(path, expected_top)
        errors.extend(payload_errors)
        if payload is not None:
            stat_payloads[phase] = payload
    return errors, stat_payloads


def artifact_entry(
    path: Path,
    work_dir: Path,
    git_commit: str,
    tool_version: str | None,
    scope: str | None,
    role: str,
) -> dict[str, Any]:
    return {
        "relative_or_external_path": common.display_path(path, work_dir),
        "sha256": common.sha256_file(path),
        "bytes": path.stat().st_size,
        "git_commit": git_commit,
        "cfg_hash": None,
        "tool_version": tool_version,
        "synthesis_scope": scope,
        "role": role,
    }


def scope_result(
    definition: ScopeDefinition,
    status: str,
    reason: str | None,
    command_index: int | None,
    stat_payloads: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payloads = stat_payloads or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": definition.name,
        "top": definition.top,
        "decomposition_label": definition.decomposition_label,
        "independent_scope_is_additive": definition.additive,
        "status": status,
        "failure_reason": reason,
        "command_index": command_index,
        "pre_num_cells": (
            payloads.get("pre", {}).get("design", {}).get("num_cells")
        ),
        "post_num_cells": (
            payloads.get("post", {}).get("design", {}).get("num_cells")
        ),
    }


def write_scope_csv(
    path: Path, results: Sequence[dict[str, Any]]
) -> None:
    fields = (
        "schema_version",
        "scope",
        "top",
        "decomposition_label",
        "independent_scope_is_additive",
        "status",
        "failure_reason",
        "command_index",
        "pre_num_cells",
        "post_num_cells",
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    temporary.replace(path)


def persist(
    work_dir: Path,
    run_manifest: dict[str, Any],
    inputs: Sequence[dict[str, Any]],
    results: Sequence[dict[str, Any]],
    failures: Sequence[dict[str, Any]],
    commands: Sequence[dict[str, Any]],
    artifacts: Sequence[dict[str, Any]],
) -> None:
    common.write_json(work_dir / "run_manifest.json", run_manifest)
    common.write_json(work_dir / "input_manifest.json", list(inputs))
    common.write_json(work_dir / "scope_results.json", list(results))
    write_scope_csv(work_dir / "scope_results.csv", results)
    common.write_json(work_dir / "failures.json", list(failures))
    common.write_json(work_dir / "commands.json", list(commands))
    common.write_json(work_dir / "artifact_manifest.json", list(artifacts))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_root = script.parents[2]
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    default_yosys = shutil.which("yosys") or "yosys"
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=(
            default_root.parent
            / f"work-online-merge-resource-proxy-{timestamp}"
        ),
    )
    parser.add_argument("--yosys", type=Path, default=Path(default_yosys))
    parser.add_argument(
        "--scope",
        action="append",
        choices=tuple(SCOPES),
        default=[],
        help="synthesis scope; repeat as needed (default: all scopes)",
    )
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--probe-timeout-seconds", type=int, default=60)
    parser.add_argument("--require-clean", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    work_dir = args.work_dir.resolve()
    yosys = args.yosys.resolve()
    requested_scopes = tuple(args.scope or DEFAULT_SCOPES)
    if len(set(requested_scopes)) != len(requested_scopes):
        raise SystemExit("duplicate --scope values are not allowed")
    if args.timeout_seconds <= 0 or args.probe_timeout_seconds <= 0:
        raise SystemExit("timeouts must be positive")
    try:
        validate_output_root(work_dir, repo_root)
    except ValueError as error:
        raise SystemExit(f"invalid resource-proxy request: {error}") from error

    start_utc = common.utc_now()
    git_commit = common.git_output(repo_root, "rev-parse", "HEAD")
    git_dirty = bool(common.git_output(repo_root, "status", "--porcelain"))
    if args.require_clean and git_dirty:
        raise SystemExit(
            "formal generic-resource proxy run requires a clean worktree"
        )
    work_dir.mkdir(parents=True, exist_ok=True)

    inputs = input_manifest(repo_root, git_commit)
    missing_inputs = [
        str(entry["relative_or_external_path"])
        for entry in inputs
        if not entry["exists"]
    ]
    sources = synthesis_sources(repo_root, inputs)
    script_entry = find_input(inputs, "yosys_pass_script")
    script_path = repo_root / str(script_entry["relative_or_external_path"])
    cfg_entry = find_input(inputs, "fixed_configuration_reference")

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    tool_version: str | None = None
    run_manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "title": "Online Softmax Merge Engine generic resource proxy",
        "status": "in_progress",
        "start_utc": start_utc,
        "end_utc": None,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "resource_proxy_evidence": False,
        "physical_ppa_evidence": False,
        "claim_boundary": (
            "Version-specific Yosys generic logic complexity only; no "
            "liberty, PDK, physical constraints, timing, power, or energy."
        ),
        "requested_scopes": list(requested_scopes),
        "required_acceptance_scopes": list(REQUIRED_SCOPES),
        "yosys_path": str(yosys),
        "yosys_version": None,
        "slang_probe_status": None,
        "wrapper_sha256": find_input(inputs, "synthesis_wrapper")[
            "sha256"
        ],
        "script_sha256": script_entry["sha256"],
        "configuration_reference_path": cfg_entry[
            "relative_or_external_path"
        ],
        "configuration_reference_sha256": cfg_entry["sha256"],
        "fixed_type_parameters": {
            "tcdm_address_width_bits": 17,
            "tcdm_data_width_bits": 64,
            "tcdm_strobe_width_bits": 8,
            "tcdm_user_width_bits": 4,
        },
    }
    persist(
        work_dir,
        run_manifest,
        inputs,
        results,
        failures,
        commands,
        artifacts,
    )

    version_command, version_output = common.run_command(
        [str(yosys), "-V"],
        work_dir / "yosys-version.log",
        args.probe_timeout_seconds,
        work_dir,
    )
    commands.append(command_mapping(version_command, work_dir))
    tool_version = parse_yosys_version(version_output)
    run_manifest["yosys_version"] = tool_version
    artifacts.append(
        artifact_entry(
            work_dir / "yosys-version.log",
            work_dir,
            git_commit,
            tool_version,
            None,
            "tool_version_log",
        )
    )

    probe_command, _ = common.run_command(
        [str(yosys), "-m", "slang", "-Q", "-p", "help read_slang"],
        work_dir / "slang-probe.log",
        args.probe_timeout_seconds,
        work_dir,
    )
    commands.append(command_mapping(probe_command, work_dir))
    run_manifest["slang_probe_status"] = probe_command.status
    artifacts.append(
        artifact_entry(
            work_dir / "slang-probe.log",
            work_dir,
            git_commit,
            tool_version,
            None,
            "slang_plugin_probe_log",
        )
    )

    early_status = "tool_error"
    early_reason = None
    if missing_inputs:
        early_reason = "missing input files: " + ", ".join(missing_inputs)
    elif version_command.status != "pass":
        early_status = version_command.status
        early_reason = "Yosys version command failed"
    elif tool_version is None:
        early_reason = "Yosys version output was not recognized"
    elif probe_command.status != "pass":
        early_status = probe_command.status
        early_reason = "Yosys Slang plugin probe failed"

    if early_reason is not None:
        for scope in requested_scopes:
            definition = SCOPES[scope]
            results.append(
                scope_result(definition, early_status, early_reason, None)
            )
            failures.append(
                {
                    "kind": "early_tool_error",
                    "scope": scope,
                    "status": early_status,
                    "reason": early_reason,
                }
            )
    else:
        for scope in requested_scopes:
            definition = SCOPES[scope]
            scope_dir = work_dir / scope
            scope_dir.mkdir()
            invocation = synthesis_command(
                definition, sources, script_path
            )
            command, _ = common.run_command(
                [
                    str(yosys),
                    "-m",
                    "slang",
                    "-Q",
                    "-p",
                    invocation,
                ],
                scope_dir / "yosys.log",
                args.timeout_seconds,
                scope_dir,
            )
            command_index = len(commands)
            commands.append(command_mapping(command, work_dir))
            artifacts.append(
                artifact_entry(
                    scope_dir / "yosys.log",
                    work_dir,
                    git_commit,
                    tool_version,
                    scope,
                    "yosys_log",
                )
            )

            output_errors, stat_payloads = validate_scope_outputs(
                scope_dir, definition.top
            )
            for name in RAW_OUTPUTS:
                path = scope_dir / name
                if path.is_file():
                    artifacts.append(
                        artifact_entry(
                            path,
                            work_dir,
                            git_commit,
                            tool_version,
                            scope,
                            name.replace("-", "_").replace(".", "_"),
                        )
                    )

            status = command.status
            reasons = []
            if status != "pass":
                reasons.append(
                    f"Yosys command ended with status {command.status}"
                )
            if output_errors:
                status = "tool_error" if status == "pass" else status
                reasons.extend(output_errors)
            reason = "; ".join(reasons) or None
            results.append(
                scope_result(
                    definition,
                    status,
                    reason,
                    command_index,
                    stat_payloads,
                )
            )
            if status != "pass":
                failures.append(
                    {
                        "kind": "scope_synthesis_failure",
                        "scope": scope,
                        "status": status,
                        "reason": reason,
                        "command_index": command_index,
                        "partial_outputs": [
                            name
                            for name in RAW_OUTPUTS
                            if (scope_dir / name).is_file()
                        ],
                    }
                )
            run_manifest["end_utc"] = common.utc_now()
            persist(
                work_dir,
                run_manifest,
                inputs,
                results,
                failures,
                commands,
                artifacts,
            )

    all_pass = (
        len(results) == len(requested_scopes)
        and all(result["status"] == "pass" for result in results)
    )
    required_present = set(REQUIRED_SCOPES).issubset(requested_scopes)
    if all_pass:
        run_manifest["status"] = "pass"
    elif any(result["status"] == "timeout" for result in results):
        run_manifest["status"] = "timeout"
    else:
        run_manifest["status"] = "tool_error"
    run_manifest["end_utc"] = common.utc_now()
    run_manifest["resource_proxy_evidence"] = bool(
        all_pass and required_present and not git_dirty
    )
    persist(
        work_dir,
        run_manifest,
        inputs,
        results,
        failures,
        commands,
        artifacts,
    )
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
