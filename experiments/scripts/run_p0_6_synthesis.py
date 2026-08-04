#!/usr/bin/env python3
"""Run failure-isolated P0-6 C0/C1/C2 mapped synthesis trials."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import experiment_common as common


SCHEMA_VERSION = 1
EXPECTED_CONFIG_IDS = ("C0_NONE", "C1_SCALAR", "C2_FULL")
FLOW_PLACEHOLDER = "@LIBERTY@"
RAW_OUTPUTS = (
    "mapped-stat.json",
    "mapped-stat.txt",
    "mapped-netlist.json",
    "mapped-netlist.v",
)
REPO_INPUTS = (
    ("runner", "experiments/scripts/run_p0_6_synthesis.py"),
    ("catalog", "experiments/configs/p0_6_synthesis.json"),
    (
        "flow_template",
        "hw/ip/online_merge/synth/nangate45_area.ys.in",
    ),
    (
        "mapped_wrapper",
        "hw/ip/online_merge/synth/online_merge_mapped_wrapper.sv",
    ),
    (
        "resource_wrapper",
        "hw/ip/online_merge/synth/online_merge_resource_wrapper.sv",
    ),
    (
        "fp32_helpers",
        "hw/ip/online_merge/src/online_merge_fp32_helpers.sv",
    ),
    (
        "exp_approximation",
        "hw/ip/online_merge/src/online_merge_exp_approx.sv",
    ),
    (
        "reciprocal_approximation",
        "hw/ip/online_merge/src/online_merge_recip_approx.sv",
    ),
    (
        "update_engine",
        "hw/ip/online_merge/src/online_merge_update_engine.sv",
    ),
    (
        "fixed_configuration_reference",
        "hw/system/spatz_cluster/cfg/spatz_cluster.default.dram.hjson",
    ),
)
SYNTHESIS_SOURCE_ROLES = (
    "fp32_helpers",
    "exp_approximation",
    "reciprocal_approximation",
    "update_engine",
    "resource_wrapper",
    "mapped_wrapper",
)
SAFE_YOSYS_TOKEN = re.compile(r"[A-Za-z0-9_./:+@=,-]+")
LIBERTY_CELL = re.compile(
    r"^\s*cell\s*\(\s*([A-Za-z_][A-Za-z0-9_$]*)\s*\)"
)


class SynthesisError(ValueError):
    """Raised when a request or captured output violates the P0-6 contract."""


def load_json(path: Path, expected_type: type) -> Any:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SynthesisError(f"cannot read {path}: {error}") from error
    if not isinstance(payload, expected_type):
        raise SynthesisError(
            f"{path} must contain {expected_type.__name__}"
        )
    return payload


def validate_catalog(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise SynthesisError("unsupported P0-6 catalog schema")
    if payload.get("trials") != 3:
        raise SynthesisError("P0-6 catalog must require exactly three trials")
    configurations = payload.get("configurations")
    if not isinstance(configurations, list):
        raise SynthesisError("P0-6 configurations must be a list")
    ids = [row.get("config_id") for row in configurations]
    if tuple(ids) != EXPECTED_CONFIG_IDS:
        raise SynthesisError(
            "P0-6 configurations must be ordered C0_NONE/C1_SCALAR/C2_FULL"
        )
    tops: set[str] = set()
    for row in configurations:
        if not isinstance(row, dict):
            raise SynthesisError("P0-6 configuration is not an object")
        top = row.get("top")
        if not isinstance(top, str) or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_$]*", top
        ):
            raise SynthesisError(f"invalid synthesis top: {top!r}")
        if top in tops:
            raise SynthesisError(f"duplicate synthesis top: {top}")
        tops.add(top)
    expected_modes = {
        "C0_NONE": (False, None),
        "C1_SCALAR": (True, 1),
        "C2_FULL": (True, 0),
    }
    for row in configurations:
        expected = expected_modes[str(row["config_id"])]
        observed = (row.get("engine_present"), row.get("fixed_mode"))
        if observed != expected:
            raise SynthesisError(
                f"invalid C0/C1/C2 semantics for {row['config_id']}"
            )
    return configurations


def yosys_token(value: Path | str) -> str:
    text = str(value)
    if SAFE_YOSYS_TOKEN.fullmatch(text) is None:
        raise SynthesisError(
            "Yosys paths must not contain whitespace or metacharacters"
        )
    return text


def render_flow(template: str, liberty: Path) -> str:
    if FLOW_PLACEHOLDER not in template:
        raise SynthesisError("flow template lacks @LIBERTY@")
    rendered = template.replace(FLOW_PLACEHOLDER, yosys_token(liberty))
    if re.search(r"@[A-Z][A-Z0-9_]*@", rendered):
        raise SynthesisError("flow template retains an unresolved placeholder")
    return rendered


def liberty_cell_names(path: Path) -> set[str]:
    names: set[str] = set()
    try:
        with path.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                match = LIBERTY_CELL.match(line)
                if match:
                    names.add(match.group(1))
    except OSError as error:
        raise SynthesisError(f"cannot read Liberty cells: {error}") from error
    if not names:
        raise SynthesisError("Liberty contains no cell definitions")
    return names


def numeric(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SynthesisError(f"{field} is not numeric")
    converted = float(value)
    if not math.isfinite(converted) or converted < 0.0:
        raise SynthesisError(f"{field} is not finite and nonnegative")
    return converted


def validate_stat_payload(
    payload: dict[str, Any], expected_top: str, cells: set[str]
) -> dict[str, Any]:
    creator = payload.get("creator")
    modules = payload.get("modules")
    design = payload.get("design")
    if not isinstance(creator, str) or not creator:
        raise SynthesisError("mapped stat lacks creator")
    if not isinstance(modules, dict) or not isinstance(design, dict):
        raise SynthesisError("mapped stat lacks modules/design objects")
    normalized = {str(name).lstrip("\\") for name in modules}
    if expected_top not in normalized:
        raise SynthesisError(f"mapped stat lacks expected top {expected_top}")
    count = design.get("num_cells")
    counts = design.get("num_cells_by_type")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise SynthesisError("mapped stat has invalid num_cells")
    if not isinstance(counts, dict):
        raise SynthesisError("mapped stat cell types are not an object")
    normalized_counts: dict[str, int] = {}
    for cell_type, cell_count in counts.items():
        if (
            isinstance(cell_count, bool)
            or not isinstance(cell_count, int)
            or cell_count < 0
        ):
            raise SynthesisError(f"invalid count for {cell_type}")
        normalized_counts[str(cell_type).lstrip("\\")] = cell_count
    if sum(normalized_counts.values()) != count:
        raise SynthesisError("mapped stat cell-type sum mismatch")
    unknown = sorted(set(normalized_counts).difference(cells))
    if unknown:
        raise SynthesisError(
            f"mapped stat contains non-Liberty cells: {unknown}"
        )
    if count:
        area = numeric(design.get("area"), "mapped area")
        sequential_area = numeric(
            design.get("sequential_area", 0.0), "sequential area"
        )
    else:
        area = numeric(design.get("area", 0.0), "mapped area")
        sequential_area = numeric(
            design.get("sequential_area", 0.0), "sequential area"
        )
    if sequential_area > area:
        raise SynthesisError("sequential area exceeds total mapped area")
    return {
        "creator": creator,
        "mapped_cell_count": count,
        "mapped_cell_area": area,
        "sequential_cell_area": sequential_area,
        "combinational_cell_area": area - sequential_area,
        "cell_types": dict(sorted(normalized_counts.items())),
    }


def validate_trial_outputs(
    trial_dir: Path, expected_top: str, cells: set[str]
) -> tuple[dict[str, Any] | None, list[str], dict[str, str]]:
    errors: list[str] = []
    hashes: dict[str, str] = {}
    for name in RAW_OUTPUTS:
        path = trial_dir / name
        if not path.is_file():
            errors.append(f"missing output: {name}")
        elif path.stat().st_size == 0:
            errors.append(f"empty output: {name}")
        else:
            hashes[name] = common.sha256_file(path)
    summary = None
    stat_path = trial_dir / "mapped-stat.json"
    if stat_path.is_file() and stat_path.stat().st_size:
        try:
            summary = validate_stat_payload(
                load_json(stat_path, dict), expected_top, cells
            )
        except SynthesisError as error:
            errors.append(str(error))
    return summary, errors, hashes


def companion_paths(yosys: Path) -> tuple[Path, Path]:
    suite_root = yosys.parent.parent
    return (
        suite_root / "libexec/yosys",
        suite_root / "share/yosys/plugins/slang.so",
    )


def file_entry(
    role: str,
    path: Path,
    repo_root: Path,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    exists = path.is_file()
    actual = common.sha256_file(path) if exists else None
    return {
        "role": role,
        "path": common.relative_or_absolute(path, repo_root),
        "exists": exists,
        "bytes": path.stat().st_size if exists else None,
        "sha256": actual,
        "expected_sha256": expected_sha256,
        "expected_sha256_matches": (
            actual == expected_sha256 if expected_sha256 is not None else None
        ),
    }


def build_input_manifest(
    repo_root: Path,
    catalog_path: Path,
    catalog: dict[str, Any],
    yosys: Path,
    liberty: Path,
) -> list[dict[str, Any]]:
    entries = []
    for role, relative in REPO_INPUTS:
        path = catalog_path if role == "catalog" else repo_root / relative
        entries.append(file_entry(role, path.resolve(), repo_root))
    executable, plugin = companion_paths(yosys)
    library = catalog["library"]
    tool = catalog["tool"]
    pdk_readme = liberty.parent.parent / "README.md"
    entries.extend(
        (
            file_entry(
                "liberty",
                liberty,
                repo_root,
                str(library["liberty_sha256"]),
            ),
            file_entry(
                "library_readme",
                pdk_readme,
                repo_root,
                str(library["readme_sha256"]),
            ),
            file_entry(
                "yosys_launcher",
                yosys,
                repo_root,
                str(tool["launcher_sha256"]),
            ),
            file_entry(
                "yosys_executable",
                executable,
                repo_root,
                str(tool["executable_sha256"]),
            ),
            file_entry(
                "slang_plugin",
                plugin,
                repo_root,
                str(tool["slang_plugin_sha256"]),
            ),
        )
    )
    return entries


def artifact_entry(
    path: Path,
    root: Path,
    kind: str,
    config_id: str | None = None,
    trial: int | None = None,
) -> dict[str, Any]:
    return {
        "path": common.relative_or_absolute(path, root),
        "kind": kind,
        "config_id": config_id,
        "trial": trial,
        "bytes": path.stat().st_size,
        "sha256": common.sha256_file(path),
    }


def command_for_trial(
    yosys: Path,
    liberty: Path,
    sources: Sequence[Path],
    top: str,
) -> list[str]:
    source_tokens = " ".join(yosys_token(path) for path in sources)
    invocation = (
        f"read_liberty -lib {yosys_token(liberty)}; "
        f"read_slang --std 1800-2017 {source_tokens}; "
        f"hierarchy -check -top {top}; script flow.ys"
    )
    return [str(yosys), "-Q", "-m", "slang", "-p", invocation]


def output_signature(record: dict[str, Any]) -> str | None:
    if record.get("status") != "pass":
        return None
    fields = {
        "mapped_cell_count": record.get("mapped_cell_count"),
        "mapped_cell_area": record.get("mapped_cell_area"),
        "sequential_cell_area": record.get("sequential_cell_area"),
        "combinational_cell_area": record.get("combinational_cell_area"),
        "cell_types_sha256": record.get("cell_types_sha256"),
        "mapped_stat_sha256": record.get("mapped_stat_sha256"),
        "mapped_netlist_json_sha256": record.get(
            "mapped_netlist_json_sha256"
        ),
        "mapped_netlist_verilog_sha256": record.get(
            "mapped_netlist_verilog_sha256"
        ),
        "rendered_flow_sha256": record.get("rendered_flow_sha256"),
    }
    return common.sha256_json(fields)


def reproducibility_by_config(
    records: Sequence[dict[str, Any]], expected_trials: int
) -> dict[str, bool]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("config_id"))].append(record)
    result = {}
    for config_id in EXPECTED_CONFIG_IDS:
        rows = grouped.get(config_id, [])
        signatures = [output_signature(row) for row in rows]
        result[config_id] = bool(
            len(rows) == expected_trials
            and all(signature is not None for signature in signatures)
            and len(set(signatures)) == 1
        )
    return result


def persist(
    root: Path,
    manifest: dict[str, Any],
    records: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    commands: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    inputs: list[dict[str, Any]],
) -> None:
    manifest["record_count"] = len(records)
    manifest["failure_count"] = len(failures)
    common.write_json(root / "run_manifest.json", manifest)
    common.write_json(root / "records.json", records)
    common.write_csv(root / "records.csv", records)
    common.write_json(root / "failures.json", failures)
    common.write_json(root / "commands.json", commands)
    common.write_json(root / "artifact_manifest.json", artifacts)
    common.write_json(root / "input_manifest.json", inputs)


def parse_version(output: str) -> str | None:
    for line in output.splitlines():
        if line.strip().startswith("Yosys "):
            return line.strip()
    return None


def terminal_record(
    run_id: str,
    git_commit: str,
    git_dirty: bool,
    catalog_sha256: str,
    config: dict[str, Any],
    trial: int,
    status: str,
    reason: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "stage": "P0-6",
        "config_id": config["config_id"],
        "top": config["top"],
        "engine_present": config["engine_present"],
        "fixed_mode": config["fixed_mode"],
        "trial": trial,
        "status": status,
        "failure_reason": reason,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "catalog_sha256": catalog_sha256,
        "mapped_cell_count": None,
        "mapped_cell_area": None,
        "sequential_cell_area": None,
        "combinational_cell_area": None,
        "cell_types_sha256": None,
        "mapped_stat_sha256": None,
        "mapped_netlist_json_sha256": None,
        "mapped_netlist_verilog_sha256": None,
        "rendered_flow_sha256": None,
        "all_cells_in_liberty": False,
        "exact_reproducible": False,
        "paper_eligible": "NO",
        "paper_ineligibility_reason": reason or "run not finalized",
        "physical_ppa_evidence": "NO",
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=common.REPO_ROOT)
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("experiments/configs/p0_6_synthesis.json"),
    )
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--yosys", type=Path)
    parser.add_argument("--liberty", type=Path)
    parser.add_argument(
        "--config-id", action="append", choices=EXPECTED_CONFIG_IDS
    )
    parser.add_argument("--trials", type=int)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--probe-timeout-seconds", type=int, default=60)
    parser.add_argument("--require-clean", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    catalog_path = args.catalog
    if not catalog_path.is_absolute():
        catalog_path = repo_root / catalog_path
    catalog_path = catalog_path.resolve()
    catalog = load_json(catalog_path, dict)
    configurations = validate_catalog(catalog)
    config_by_id = {row["config_id"]: row for row in configurations}
    requested_ids = tuple(args.config_id or EXPECTED_CONFIG_IDS)
    if len(set(requested_ids)) != len(requested_ids):
        raise SystemExit("duplicate --config-id values are not allowed")
    trial_count = args.trials if args.trials is not None else catalog["trials"]
    if not 1 <= trial_count <= int(catalog["trials"]):
        raise SystemExit("--trials must be between one and three")
    if args.timeout_seconds <= 0 or args.probe_timeout_seconds <= 0:
        raise SystemExit("timeouts must be positive")

    git_commit = common.git_output(repo_root, "rev-parse", "HEAD")
    git_dirty = bool(common.git_output(repo_root, "status", "--porcelain"))
    if args.require_clean and git_dirty:
        raise SystemExit("formal P0-6 synthesis requires a clean worktree")
    run_id = f"{common.utc_run_stamp()}_{git_commit[:8]}_p0-6-synthesis"
    artifact_root = (
        args.artifact_root.resolve()
        if args.artifact_root
        else (repo_root.parent / f"work-online-merge-{run_id}").resolve()
    )
    try:
        common.require_fresh_external_root(artifact_root, repo_root)
    except ValueError as error:
        raise SystemExit(f"invalid artifact root: {error}") from error

    library = catalog["library"]
    tool = catalog["tool"]
    yosys = Path(
        args.yosys or str(tool["default_yosys_path"])
    ).resolve()
    liberty = Path(
        args.liberty or str(library["default_liberty_path"])
    ).resolve()
    try:
        yosys_token(yosys)
        yosys_token(liberty)
    except SynthesisError as error:
        raise SystemExit(f"invalid tool path: {error}") from error

    inputs = build_input_manifest(
        repo_root, catalog_path, catalog, yosys, liberty
    )
    input_by_role = {entry["role"]: entry for entry in inputs}
    missing_inputs = [
        entry["role"] for entry in inputs if not entry["exists"]
    ]
    pinned_mismatches = [
        entry["role"]
        for entry in inputs
        if entry["expected_sha256_matches"] is False
    ]
    catalog_sha256 = common.sha256_file(catalog_path)
    worktree = common.worktree_snapshot(repo_root)
    artifact_root.mkdir(parents=True)

    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "title": catalog["title"],
        "stage": "P0-6",
        "status": "in_progress",
        "start_utc": common.utc_now(),
        "end_utc": None,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "worktree_snapshot_sha256": worktree["sha256"],
        "catalog_path": common.relative_or_absolute(
            catalog_path, repo_root
        ),
        "catalog_sha256": catalog_sha256,
        "requested_config_ids": list(requested_ids),
        "required_config_ids": list(EXPECTED_CONFIG_IDS),
        "trials": trial_count,
        "required_trials": 3,
        "yosys_path": str(yosys),
        "yosys_version": None,
        "liberty_path": str(liberty),
        "liberty_sha256": input_by_role["liberty"]["sha256"],
        "library": library,
        "mapping": catalog["mapping"],
        "tool_identity_pass": False,
        "input_identity_pass": False,
        "exact_reproducibility_by_config": {},
        "formal_acceptance_gates": {},
        "paper_eligible": False,
        "physical_ppa_evidence": False,
        "claim_boundary": (
            "Unconstrained pre-layout Nangate45 Liberty cell-area mapping "
            "for the fixed SMU-only scope; no physical/timing/power claim."
        ),
    }
    persist(
        artifact_root,
        manifest,
        records,
        failures,
        commands,
        artifacts,
        inputs,
    )
    artifacts.append(
        artifact_entry(
            artifact_root / "input_manifest.json",
            artifact_root,
            "input_manifest",
        )
    )
    persist(
        artifact_root,
        manifest,
        records,
        failures,
        commands,
        artifacts,
        inputs,
    )

    early_reasons = []
    if missing_inputs:
        early_reasons.append("missing inputs: " + ", ".join(missing_inputs))
    if pinned_mismatches:
        early_reasons.append(
            "pinned SHA256 mismatch: " + ", ".join(pinned_mismatches)
        )

    yosys_version = None
    if yosys.is_file():
        version_command, version_output = common.run_command(
            [str(yosys), "-V"],
            artifact_root,
            artifact_root / "yosys-version.log",
            args.probe_timeout_seconds,
        )
        commands.append(common.command_dict(version_command))
        artifacts.append(
            artifact_entry(
                artifact_root / "yosys-version.log",
                artifact_root,
                "yosys_version_log",
            )
        )
        yosys_version = parse_version(version_output)
        manifest["yosys_version"] = yosys_version
        if version_command.status != "PASS":
            early_reasons.append("Yosys version probe failed")
        elif yosys_version != tool["yosys_version"]:
            early_reasons.append("Yosys version does not match catalog")

        plugin_command, _ = common.run_command(
            [str(yosys), "-Q", "-m", "slang", "-p", "help read_slang"],
            artifact_root,
            artifact_root / "slang-probe.log",
            args.probe_timeout_seconds,
        )
        commands.append(common.command_dict(plugin_command))
        artifacts.append(
            artifact_entry(
                artifact_root / "slang-probe.log",
                artifact_root,
                "slang_probe_log",
            )
        )
        if plugin_command.status != "PASS":
            early_reasons.append("Yosys Slang plugin probe failed")

    liberty_cells: set[str] = set()
    if liberty.is_file():
        try:
            liberty_cells = liberty_cell_names(liberty)
        except SynthesisError as error:
            early_reasons.append(str(error))

    flow_template_path = repo_root / str(
        next(
            relative
            for role, relative in REPO_INPUTS
            if role == "flow_template"
        )
    )
    flow_template = ""
    if flow_template_path.is_file():
        try:
            flow_template = flow_template_path.read_text(encoding="utf-8")
            render_flow(flow_template, liberty)
        except (OSError, UnicodeError, SynthesisError) as error:
            early_reasons.append(f"invalid flow template: {error}")

    manifest["input_identity_pass"] = not (
        missing_inputs or pinned_mismatches
    )
    manifest["tool_identity_pass"] = bool(
        not early_reasons
        and yosys_version == tool["yosys_version"]
        and liberty_cells
    )
    sources = [
        repo_root / str(input_by_role[role]["path"])
        for role in SYNTHESIS_SOURCE_ROLES
    ]

    if early_reasons:
        reason = "; ".join(dict.fromkeys(early_reasons))
        for config_id in requested_ids:
            config = config_by_id[config_id]
            for trial in range(1, trial_count + 1):
                records.append(
                    terminal_record(
                        run_id,
                        git_commit,
                        git_dirty,
                        catalog_sha256,
                        config,
                        trial,
                        "tool_error",
                        reason,
                    )
                )
                failures.append(
                    {
                        "kind": "early_tool_error",
                        "config_id": config_id,
                        "trial": trial,
                        "status": "tool_error",
                        "reason": reason,
                    }
                )
    else:
        for config_id in requested_ids:
            config = config_by_id[config_id]
            for trial in range(1, trial_count + 1):
                trial_dir = artifact_root / config_id / f"trial-{trial}"
                trial_dir.mkdir(parents=True)
                rendered_flow = render_flow(flow_template, liberty)
                flow_path = trial_dir / "flow.ys"
                flow_path.write_text(rendered_flow, encoding="utf-8")
                artifacts.append(
                    artifact_entry(
                        flow_path,
                        artifact_root,
                        "rendered_flow",
                        config_id,
                        trial,
                    )
                )
                command, _ = common.run_command(
                    command_for_trial(
                        yosys,
                        liberty,
                        sources,
                        str(config["top"]),
                    ),
                    trial_dir,
                    trial_dir / "yosys.log",
                    args.timeout_seconds,
                )
                command_index = len(commands)
                commands.append(common.command_dict(command))
                artifacts.append(
                    artifact_entry(
                        trial_dir / "yosys.log",
                        artifact_root,
                        "yosys_log",
                        config_id,
                        trial,
                    )
                )
                summary, output_errors, hashes = validate_trial_outputs(
                    trial_dir, str(config["top"]), liberty_cells
                )
                for name in RAW_OUTPUTS:
                    path = trial_dir / name
                    if path.is_file():
                        artifacts.append(
                            artifact_entry(
                                path,
                                artifact_root,
                                name.replace(".", "_"),
                                config_id,
                                trial,
                            )
                        )
                status = command.status.lower()
                reasons = []
                if command.status != "PASS":
                    reasons.append(
                        f"Yosys command ended with {command.status}"
                    )
                reasons.extend(output_errors)
                if reasons and status == "pass":
                    status = "tool_error"
                reason = "; ".join(reasons) or None
                record = terminal_record(
                    run_id,
                    git_commit,
                    git_dirty,
                    catalog_sha256,
                    config,
                    trial,
                    status,
                    reason,
                )
                record.update(
                    {
                        "command_index": command_index,
                        "yosys_version": yosys_version,
                        "liberty_sha256": input_by_role["liberty"][
                            "sha256"
                        ],
                        "rendered_flow_sha256": common.sha256_file(
                            flow_path
                        ),
                        "mapped_stat_sha256": hashes.get(
                            "mapped-stat.json"
                        ),
                        "mapped_netlist_json_sha256": hashes.get(
                            "mapped-netlist.json"
                        ),
                        "mapped_netlist_verilog_sha256": hashes.get(
                            "mapped-netlist.v"
                        ),
                        "all_cells_in_liberty": summary is not None,
                    }
                )
                if summary is not None:
                    record.update(
                        {
                            key: value
                            for key, value in summary.items()
                            if key != "cell_types"
                        }
                    )
                    record["cell_types_sha256"] = common.sha256_json(
                        summary["cell_types"]
                    )
                records.append(record)
                if status != "pass":
                    failures.append(
                        {
                            "kind": "synthesis_trial_failure",
                            "config_id": config_id,
                            "trial": trial,
                            "status": status,
                            "reason": reason,
                            "command_index": command_index,
                            "partial_outputs": sorted(hashes),
                        }
                    )
                manifest["end_utc"] = common.utc_now()
                persist(
                    artifact_root,
                    manifest,
                    records,
                    failures,
                    commands,
                    artifacts,
                    inputs,
                )

    reproducibility = reproducibility_by_config(
        records, int(catalog["trials"])
    )
    c0_rows = [row for row in records if row["config_id"] == "C0_NONE"]
    c0_zero = bool(
        len(c0_rows) == trial_count
        and all(
            row.get("status") == "pass"
            and row.get("mapped_cell_count") == 0
            and row.get("mapped_cell_area") == 0.0
            for row in c0_rows
        )
    )
    gates = {
        "git_clean": not git_dirty,
        "all_configurations_requested": requested_ids == EXPECTED_CONFIG_IDS,
        "exactly_three_trials": trial_count == 3,
        "input_identity_pass": manifest["input_identity_pass"],
        "tool_identity_pass": manifest["tool_identity_pass"],
        "all_trials_pass": bool(records)
        and all(row["status"] == "pass" for row in records),
        "all_cells_in_liberty": bool(records)
        and all(row["all_cells_in_liberty"] for row in records),
        "all_configurations_exact": all(reproducibility.values()),
        "c0_is_zero_cell_baseline": c0_zero,
        "failures_empty": not failures,
    }
    formal_acceptance = all(gates.values())
    failed_gate_names = [name for name, passed in gates.items() if not passed]
    reason = (
        "PASS"
        if formal_acceptance
        else "failed gates: " + ", ".join(failed_gate_names)
    )
    for record in records:
        record["exact_reproducible"] = reproducibility.get(
            str(record["config_id"]), False
        )
        record["paper_eligible"] = "YES" if formal_acceptance else "NO"
        record["paper_ineligibility_reason"] = (
            None if formal_acceptance else reason
        )

    manifest["exact_reproducibility_by_config"] = reproducibility
    manifest["formal_acceptance_gates"] = gates
    manifest["paper_eligible"] = formal_acceptance
    manifest["status"] = (
        "pass"
        if records and all(row["status"] == "pass" for row in records)
        else (
            "timeout"
            if any(row["status"] == "timeout" for row in records)
            else "tool_error"
        )
    )
    manifest["end_utc"] = common.utc_now()
    persist(
        artifact_root,
        manifest,
        records,
        failures,
        commands,
        artifacts,
        inputs,
    )
    print(f"run_id={run_id}")
    print(f"artifact_root={artifact_root}")
    print(f"records={len(records)} failures={len(failures)}")
    print(f"paper_eligible={'YES' if formal_acceptance else 'NO'}")
    return 0 if manifest["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
