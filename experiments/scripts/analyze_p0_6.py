#!/usr/bin/env python3
"""Independently validate and summarize formal P0-6 mapped synthesis."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import analyze_p0_4 as indexed_evidence
import experiment_common as common


SCHEMA_VERSION = 1
CONFIG_IDS = ("C0_NONE", "C1_SCALAR", "C2_FULL")
RAW_OUTPUTS = (
    "mapped-stat.json",
    "mapped-stat.txt",
    "mapped-netlist.json",
    "mapped-netlist.v",
    "flow.ys",
    "yosys.log",
)
LIBERTY_CELL = re.compile(
    r"^\s*cell\s*\(\s*([A-Za-z_][A-Za-z0-9_$]*)\s*\)"
)
SHA256 = re.compile(r"[0-9a-f]{64}")


class AnalysisError(ValueError):
    """Raised when indexed evidence cannot be safely interpreted."""


def load_json(path: Path, expected_type: type) -> Any:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AnalysisError(f"cannot read {path}: {error}") from error
    if not isinstance(payload, expected_type):
        raise AnalysisError(
            f"{path} must contain {expected_type.__name__}"
        )
    return payload


def resolve_path(value: Any, base: Path) -> Path:
    if not isinstance(value, str) or not value:
        raise AnalysisError("manifest path must be a nonempty string")
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def validate_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise AnalysisError(f"{label} is not a SHA256")
    return value


def verify_hash(path: Path, expected: Any, label: str) -> str:
    expected_hash = validate_sha(expected, label)
    if not path.is_file():
        raise AnalysisError(f"{label} is missing: {path}")
    actual = common.sha256_file(path)
    if actual != expected_hash:
        raise AnalysisError(
            f"{label} hash mismatch: {actual} != {expected_hash}"
        )
    return actual


def validate_catalog(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if catalog.get("schema_version") != SCHEMA_VERSION:
        raise AnalysisError("unsupported P0-6 catalog schema")
    if catalog.get("trials") != 3:
        raise AnalysisError("P0-6 catalog does not require three trials")
    rows = catalog.get("configurations")
    if not isinstance(rows, list):
        raise AnalysisError("catalog configurations are not a list")
    ids = tuple(row.get("config_id") for row in rows if isinstance(row, dict))
    if ids != CONFIG_IDS:
        raise AnalysisError("catalog C0/C1/C2 ordering differs")
    expected = {
        "C0_NONE": (False, None),
        "C1_SCALAR": (True, 1),
        "C2_FULL": (True, 0),
    }
    result = {}
    for row in rows:
        config_id = str(row["config_id"])
        if (row.get("engine_present"), row.get("fixed_mode")) != expected[
            config_id
        ]:
            raise AnalysisError(f"catalog semantics differ for {config_id}")
        top = row.get("top")
        if not isinstance(top, str) or not top:
            raise AnalysisError(f"catalog top missing for {config_id}")
        result[config_id] = row
    return result


def liberty_cell_names(path: Path) -> set[str]:
    names: set[str] = set()
    try:
        with path.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                match = LIBERTY_CELL.match(line)
                if match:
                    names.add(match.group(1))
    except OSError as error:
        raise AnalysisError(f"cannot read Liberty: {error}") from error
    if not names:
        raise AnalysisError("Liberty contains no cell definitions")
    return names


def numeric(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnalysisError(f"{label} is not numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise AnalysisError(f"{label} is not finite and nonnegative")
    return result


def parse_mapped_stat(
    path: Path, expected_top: str, liberty_cells: set[str]
) -> dict[str, Any]:
    payload = load_json(path, dict)
    modules = payload.get("modules")
    design = payload.get("design")
    if not isinstance(payload.get("creator"), str):
        raise AnalysisError(f"{path} lacks a creator")
    if not isinstance(modules, dict) or not isinstance(design, dict):
        raise AnalysisError(f"{path} lacks modules/design")
    names = {str(name).lstrip("\\") for name in modules}
    if expected_top not in names:
        raise AnalysisError(f"{path} lacks expected top {expected_top}")
    count = design.get("num_cells")
    raw_types = design.get("num_cells_by_type")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise AnalysisError(f"{path} has invalid num_cells")
    if not isinstance(raw_types, dict):
        raise AnalysisError(f"{path} lacks cell-type counts")
    cell_types: dict[str, int] = {}
    for cell_type, cell_count in raw_types.items():
        if (
            isinstance(cell_count, bool)
            or not isinstance(cell_count, int)
            or cell_count < 0
        ):
            raise AnalysisError(f"{path} has an invalid cell count")
        cell_types[str(cell_type).lstrip("\\")] = cell_count
    if sum(cell_types.values()) != count:
        raise AnalysisError(f"{path} cell-type sum differs")
    unknown = sorted(set(cell_types).difference(liberty_cells))
    if unknown:
        raise AnalysisError(f"{path} contains non-Liberty cells: {unknown}")
    area = numeric(design.get("area", 0.0), f"{path} total area")
    sequential = numeric(
        design.get("sequential_area", 0.0), f"{path} sequential area"
    )
    if count and "area" not in design:
        raise AnalysisError(f"{path} omits nonzero mapped area")
    if sequential > area:
        raise AnalysisError(f"{path} sequential area exceeds total")
    return {
        "mapped_cell_count": count,
        "mapped_cell_area": area,
        "sequential_cell_area": sequential,
        "combinational_cell_area": area - sequential,
        "cell_types": dict(sorted(cell_types.items())),
    }


def verify_input_manifest(
    repo_root: Path, root: Path
) -> tuple[list[dict[str, Any]], list[str]]:
    entries = load_json(root / "input_manifest.json", list)
    checks: list[dict[str, Any]] = []
    issues: list[str] = []
    seen: set[str] = set()
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            issues.append(f"input entry {position} is not an object")
            continue
        role = str(entry.get("role"))
        if role in seen:
            issues.append(f"duplicate input role: {role}")
        seen.add(role)
        try:
            path = resolve_path(entry.get("path"), repo_root)
            expected = validate_sha(entry.get("sha256"), f"{role} hash")
            actual = common.sha256_file(path) if path.is_file() else None
        except AnalysisError as error:
            issues.append(str(error))
            continue
        matches = actual == expected
        expected_pinned = entry.get("expected_sha256")
        pinned_matches = entry.get("expected_sha256_matches")
        if expected_pinned is not None:
            if expected_pinned != expected or pinned_matches is not True:
                issues.append(f"pinned identity differs for {role}")
        if not matches:
            issues.append(f"current input differs for {role}")
        checks.append(
            {
                "role": role,
                "path": str(path),
                "captured_sha256": expected,
                "current_sha256": actual,
                "matches": matches,
                "pinned": expected_pinned is not None,
            }
        )
    required = {
        "runner",
        "catalog",
        "flow_template",
        "mapped_wrapper",
        "resource_wrapper",
        "fp32_helpers",
        "exp_approximation",
        "reciprocal_approximation",
        "update_engine",
        "fixed_configuration_reference",
        "liberty",
        "library_readme",
        "yosys_launcher",
        "yosys_executable",
        "slang_plugin",
    }
    if seen != required:
        issues.append(
            "input roles differ: missing="
            f"{sorted(required - seen)}, extra={sorted(seen - required)}"
        )
    return checks, issues


def record_identity(record: dict[str, Any]) -> tuple[str, int]:
    config_id = str(record.get("config_id"))
    trial = record.get("trial")
    if config_id not in CONFIG_IDS:
        raise AnalysisError(f"unknown configuration: {config_id}")
    if isinstance(trial, bool) or not isinstance(trial, int):
        raise AnalysisError(f"invalid trial for {config_id}: {trial}")
    return config_id, trial


def compare_value(
    issues: list[str], label: str, observed: Any, expected: Any
) -> None:
    if observed != expected:
        issues.append(f"{label} differs: {observed!r} != {expected!r}")


def audit_records(
    root: Path,
    records: Sequence[dict[str, Any]],
    manifest: dict[str, Any],
    configs: dict[str, dict[str, Any]],
    liberty_cells: set[str],
) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, int]],
    list[str],
    dict[str, bool],
]:
    issues: list[str] = []
    rows: list[dict[str, Any]] = []
    cell_maps: dict[str, dict[str, int]] = {}
    seen: set[tuple[str, int]] = set()
    signatures: dict[str, list[str]] = defaultdict(list)
    capture_commit = manifest.get("git_commit")
    catalog_hash = manifest.get("catalog_sha256")
    liberty_hash = manifest.get("liberty_sha256")
    for position, record in enumerate(records):
        if not isinstance(record, dict):
            issues.append(f"record {position} is not an object")
            continue
        try:
            config_id, trial = record_identity(record)
        except AnalysisError as error:
            issues.append(str(error))
            continue
        key = (config_id, trial)
        if key in seen:
            issues.append(f"duplicate synthesis record: {key}")
            continue
        seen.add(key)
        config = configs[config_id]
        compare_value(issues, f"{key} top", record.get("top"), config["top"])
        compare_value(
            issues,
            f"{key} engine presence",
            record.get("engine_present"),
            config["engine_present"],
        )
        compare_value(
            issues,
            f"{key} fixed mode",
            record.get("fixed_mode"),
            config["fixed_mode"],
        )
        compare_value(
            issues,
            f"{key} Git commit",
            record.get("git_commit"),
            capture_commit,
        )
        compare_value(
            issues,
            f"{key} catalog hash",
            record.get("catalog_sha256"),
            catalog_hash,
        )
        compare_value(
            issues,
            f"{key} Liberty hash",
            record.get("liberty_sha256"),
            liberty_hash,
        )
        if record.get("status") != "pass":
            issues.append(f"{key} is not a passing synthesis trial")
            rows.append({**record, "raw_reverification": "NOT_PASS"})
            continue
        if record.get("paper_eligible") != "YES":
            issues.append(f"{key} is not paper-eligible")
        if record.get("git_dirty") is not False:
            issues.append(f"{key} was captured from a dirty worktree")
        if record.get("failure_reason") is not None:
            issues.append(f"{key} retains a failure reason on a passing row")
        if record.get("all_cells_in_liberty") is not True:
            issues.append(f"{key} did not pass its Liberty-cell gate")
        if record.get("exact_reproducible") is not True:
            issues.append(f"{key} was not marked exactly reproducible")
        if record.get("physical_ppa_evidence") != "NO":
            issues.append(f"{key} incorrectly claims physical PPA")
        trial_dir = root / config_id / f"trial-{trial}"
        for name in RAW_OUTPUTS:
            if not (trial_dir / name).is_file():
                issues.append(f"{key} lacks raw output {name}")
        try:
            actual_hashes = {
                name: common.sha256_file(trial_dir / name)
                for name in RAW_OUTPUTS
                if (trial_dir / name).is_file()
            }
            hash_fields = {
                "mapped-stat.json": "mapped_stat_sha256",
                "mapped-netlist.json": "mapped_netlist_json_sha256",
                "mapped-netlist.v": "mapped_netlist_verilog_sha256",
                "flow.ys": "rendered_flow_sha256",
            }
            for name, field in hash_fields.items():
                compare_value(
                    issues,
                    f"{key} {name} hash",
                    record.get(field),
                    actual_hashes.get(name),
                )
            parsed = parse_mapped_stat(
                trial_dir / "mapped-stat.json",
                str(config["top"]),
                liberty_cells,
            )
        except (OSError, AnalysisError) as error:
            issues.append(f"{key} raw validation failed: {error}")
            rows.append({**record, "raw_reverification": "FAIL"})
            continue
        for field in (
            "mapped_cell_count",
            "mapped_cell_area",
            "sequential_cell_area",
            "combinational_cell_area",
        ):
            compare_value(
                issues,
                f"{key} {field}",
                record.get(field),
                parsed[field],
            )
        compare_value(
            issues,
            f"{key} cell-type hash",
            record.get("cell_types_sha256"),
            common.sha256_json(parsed["cell_types"]),
        )
        if (
            config_id in cell_maps
            and cell_maps[config_id] != parsed["cell_types"]
        ):
            issues.append(f"{config_id} cell types differ across trials")
        cell_maps[config_id] = parsed["cell_types"]
        signature = common.sha256_json(
            {
                "mapped_stat": actual_hashes.get("mapped-stat.json"),
                "mapped_stat_text": actual_hashes.get("mapped-stat.txt"),
                "mapped_netlist_json": actual_hashes.get(
                    "mapped-netlist.json"
                ),
                "mapped_netlist_v": actual_hashes.get("mapped-netlist.v"),
                "flow": actual_hashes.get("flow.ys"),
                "parsed": parsed,
            }
        )
        signatures[config_id].append(signature)
        rows.append({**record, "raw_reverification": "PASS"})

    expected = {
        (config_id, trial)
        for config_id in CONFIG_IDS
        for trial in range(1, 4)
    }
    if seen != expected:
        issues.append(
            "record matrix differs: missing="
            f"{sorted(expected - seen)}, extra={sorted(seen - expected)}"
        )
    exact = {
        config_id: len(signatures.get(config_id, [])) == 3
        and len(set(signatures[config_id])) == 1
        for config_id in CONFIG_IDS
    }
    for config_id, passed in exact.items():
        if not passed:
            issues.append(
                f"{config_id} raw outputs are not exactly reproducible"
            )
    return rows, cell_maps, issues, exact


def summarize_trials(
    trial_rows: Sequence[dict[str, Any]],
    exact: dict[str, bool],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trial_rows:
        grouped[str(row.get("config_id"))].append(row)
    summaries = []
    for config_id in CONFIG_IDS:
        rows = sorted(grouped.get(config_id, []), key=lambda row: row["trial"])
        pass_rows = [row for row in rows if row.get("status") == "pass"]
        exemplar = pass_rows[0] if pass_rows else {}
        summaries.append(
            {
                "config_id": config_id,
                "trial_count": len(rows),
                "pass_count": len(pass_rows),
                "exact_reproducible": exact.get(config_id, False),
                "mapped_cell_count": exemplar.get("mapped_cell_count"),
                "mapped_cell_area": exemplar.get("mapped_cell_area"),
                "sequential_cell_area": exemplar.get(
                    "sequential_cell_area"
                ),
                "combinational_cell_area": exemplar.get(
                    "combinational_cell_area"
                ),
                "delta_area_from_C0": None,
                "normalized_area_to_C1": None,
                "paper_eligible": (
                    "YES"
                    if len(pass_rows) == 3
                    and exact.get(config_id, False)
                    and all(row.get("paper_eligible") == "YES" for row in rows)
                    else "NO"
                ),
            }
        )
    indexed = {row["config_id"]: row for row in summaries}
    c0_area = indexed["C0_NONE"]["mapped_cell_area"]
    c1_area = indexed["C1_SCALAR"]["mapped_cell_area"]
    if isinstance(c0_area, (int, float)):
        for row in summaries:
            area = row["mapped_cell_area"]
            if isinstance(area, (int, float)):
                row["delta_area_from_C0"] = area - c0_area
    if isinstance(c1_area, (int, float)) and c1_area > 0:
        for row in summaries:
            area = row["mapped_cell_area"]
            if isinstance(area, (int, float)):
                row["normalized_area_to_C1"] = area / c1_area
    return summaries


def cell_type_rows(
    cell_maps: dict[str, dict[str, int]]
) -> list[dict[str, Any]]:
    return [
        {
            "config_id": config_id,
            "cell_type": cell_type,
            "count": count,
        }
        for config_id in CONFIG_IDS
        for cell_type, count in sorted(cell_maps.get(config_id, {}).items())
    ]


def format_area(value: Any) -> str:
    return "NA" if value is None else f"{float(value):.3f}"


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# P0-6 C0/C1/C2 Mapped Synthesis Report",
        "",
        "This report covers an SMU-only contribution scope mapped to the",
        "research-only, non-manufacturable Nangate45 typical Liberty. The",
        "flow is unconstrained and pre-layout; areas are Liberty cell-area",
        "units, not complete-cluster or physical-layout area.",
        "",
        "## Acceptance",
        "",
    ]
    for gate, passed in report["acceptance"].items():
        lines.append(f"- `{gate}`: `{'PASS' if passed else 'FAIL'}`")
    lines.extend(
        [
            "",
            "## Fixed configurations",
            "",
            "| Configuration | Trials | Cells | Total area | Sequential | "
            "Normalized to C1 | Eligible |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in report["synthesis_summary"]:
        normalized = row["normalized_area_to_C1"]
        cell_count = (
            row["mapped_cell_count"]
            if row["mapped_cell_count"] is not None
            else "NA"
        )
        lines.append(
            f"| {row['config_id']} | {row['pass_count']}/3 | "
            f"{cell_count} | "
            f"{format_area(row['mapped_cell_area'])} | "
            f"{format_area(row['sequential_cell_area'])} | "
            f"{format_area(normalized)} | {row['paper_eligible']} |"
        )
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "The accepted claim is limited to deterministic pre-layout mapped",
            "cell area for these fixed SMU-only tops. No complete-cluster",
            "area, physical area, Fmax, critical path, timing closure, power,",
            "or energy result is inferred.",
        ]
    )
    if report["validation_issues"]:
        lines.extend(["", "## Validation issues", ""])
        lines.extend(f"- {issue}" for issue in report["validation_issues"])
    if report["failure_entries"]:
        lines.extend(["", "## Preserved failure entries", ""])
        lines.extend(
            f"- `{json.dumps(entry, sort_keys=True)}`"
            for entry in report["failure_entries"]
        )
    return "\n".join(lines) + "\n"


def write_outputs(
    output_dir: Path,
    report: dict[str, Any],
    trial_rows: list[dict[str, Any]],
    cell_rows: list[dict[str, Any]],
    index_set_path: Path,
    catalog_path: Path,
    git_context: dict[str, Any],
    repo_root: Path,
) -> None:
    if output_dir.exists():
        raise AnalysisError(f"refusing to overwrite {output_dir}")
    output_dir.mkdir(parents=True)
    analysis_path = output_dir / "p0_6_analysis.json"
    trial_path = output_dir / "p0_6_synthesis_trials.csv"
    summary_path = output_dir / "p0_6_synthesis_summary.csv"
    cells_path = output_dir / "p0_6_cell_types.csv"
    report_path = output_dir / "P0_6_SYNTHESIS_REPORT.md"
    common.write_json(analysis_path, report)
    common.write_csv(trial_path, trial_rows)
    common.write_csv(summary_path, report["synthesis_summary"])
    common.write_csv(cells_path, cell_rows)
    report_path.write_text(markdown_report(report), encoding="utf-8")
    output_paths = (
        analysis_path,
        trial_path,
        summary_path,
        cells_path,
        report_path,
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "analysis_git": git_context,
        "analysis_tool": {
            "path": common.relative_or_absolute(
                Path(__file__).resolve(), repo_root
            ),
            "sha256": common.sha256_file(Path(__file__).resolve()),
            "python": sys.version.split()[0],
        },
        "inputs": {
            "index_set": {
                "path": common.relative_or_absolute(
                    index_set_path, repo_root
                ),
                "sha256": common.sha256_file(index_set_path),
            },
            "catalog": {
                "path": common.relative_or_absolute(catalog_path, repo_root),
                "sha256": common.sha256_file(catalog_path),
            },
            "root_evidence": report["root_evidence"],
        },
        "outputs": [
            {
                "path": common.relative_or_absolute(path, repo_root),
                "bytes": path.stat().st_size,
                "sha256": common.sha256_file(path),
            }
            for path in output_paths
        ],
    }
    common.write_json(output_dir / "p0_6_manifest.json", manifest)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=common.REPO_ROOT)
    parser.add_argument("--index-set", type=Path, required=True)
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("experiments/configs/p0_6_synthesis.json"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--require-clean", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    index_set_path = args.index_set
    if not index_set_path.is_absolute():
        index_set_path = repo_root / index_set_path
    index_set_path = index_set_path.resolve()
    catalog_path = args.catalog
    if not catalog_path.is_absolute():
        catalog_path = repo_root / catalog_path
    catalog_path = catalog_path.resolve()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    output_dir = output_dir.resolve()
    git_context = {
        "commit": common.git_output(repo_root, "rev-parse", "HEAD"),
        "branch": common.git_output(repo_root, "branch", "--show-current"),
        "dirty": bool(common.git_output(repo_root, "status", "--porcelain")),
    }
    if args.require_clean and git_context["dirty"]:
        raise SystemExit("--require-clean rejected a dirty Git worktree")
    try:
        catalog = load_json(catalog_path, dict)
        configs = validate_catalog(catalog)
        index_set, runs = indexed_evidence.load_indexed_runs(
            repo_root, index_set_path
        )
        if len(runs) != 1:
            raise AnalysisError("P0-6 requires exactly one indexed run root")
        run = runs[0]
        root = run["root"]
        manifest = run["manifest"]
        input_checks, input_issues = verify_input_manifest(
            repo_root, root
        )
        liberty_path = resolve_path(manifest.get("liberty_path"), repo_root)
        verify_hash(
            liberty_path, manifest.get("liberty_sha256"), "Liberty"
        )
        liberty_cells = liberty_cell_names(liberty_path)
        trial_rows, cell_maps, record_issues, exact = audit_records(
            root,
            run["records"],
            manifest,
            configs,
            liberty_cells,
        )
        issues = input_issues + record_issues
        summaries = summarize_trials(trial_rows, exact)
        summary_by_id = {row["config_id"]: row for row in summaries}
        c0_area = summary_by_id["C0_NONE"]["mapped_cell_area"]
        c1_area = summary_by_id["C1_SCALAR"]["mapped_cell_area"]
        c2_area = summary_by_id["C2_FULL"]["mapped_cell_area"]
        area_ordering = bool(
            c0_area == 0.0
            and isinstance(c1_area, (int, float))
            and isinstance(c2_area, (int, float))
            and 0.0 < c1_area < c2_area
        )
        if not area_ordering:
            issues.append("expected C0 == 0 < C1 < C2 area ordering failed")
        failures = list(run["failures"])
        commands = load_json(root / "commands.json", list)
        synthesis_commands = commands[2:] if len(commands) >= 2 else []
        command_timeouts = {
            row.get("timeout_seconds")
            for row in synthesis_commands
            if isinstance(row, dict)
        }
        all_commands_pass = bool(commands) and all(
            isinstance(row, dict)
            and row.get("status") == "PASS"
            and row.get("returncode") == 0
            for row in commands
        )
        timeout_uniform = bool(
            len(command_timeouts) == 1
            and all(
                isinstance(value, int)
                and not isinstance(value, bool)
                and value > 0
                for value in command_timeouts
            )
        )
        capture_gates = manifest.get("formal_acceptance_gates")
        capture_gates_pass = bool(
            isinstance(capture_gates, dict)
            and capture_gates
            and all(value is True for value in capture_gates.values())
        )
        claim_boundary_pass = bool(
            catalog["library"].get("research_only") is True
            and catalog["library"].get("manufacturable") is False
            and catalog["mapping"].get("timing_constraints") == "none"
            and catalog["mapping"].get("area_unit")
            == "Liberty cell-area unit"
        )
        acceptance = {
            "analysis_git_clean": not git_context["dirty"],
            "one_indexed_formal_root": len(runs) == 1,
            "index_set_named_p0_6": index_set.get("set_name") == "p0_6",
            "capture_git_clean": manifest.get("git_dirty") is False,
            "capture_status_pass": manifest.get("status") == "pass",
            "capture_paper_eligible": manifest.get("paper_eligible") is True,
            "capture_acceptance_gates_pass": capture_gates_pass,
            "capture_physical_ppa_false": (
                manifest.get("physical_ppa_evidence") is False
            ),
            "catalog_hash_matches": manifest.get("catalog_sha256")
            == common.sha256_file(catalog_path),
            "requested_matrix_exact": manifest.get("requested_config_ids")
            == list(CONFIG_IDS)
            and manifest.get("trials") == 3,
            "input_hashes_reverified": bool(input_checks)
            and all(row["matches"] for row in input_checks),
            "tool_and_library_identity_pass": (
                manifest.get("tool_identity_pass") is True
                and manifest.get("input_identity_pass") is True
            ),
            "all_commands_pass": all_commands_pass,
            "command_schedule_exact": (
                len(commands) == 11 and len(synthesis_commands) == 9
            ),
            "synthesis_timeout_uniform": timeout_uniform,
            "record_matrix_complete": len(trial_rows) == 9,
            "all_raw_outputs_reverified": bool(trial_rows)
            and all(
                row.get("raw_reverification") == "PASS"
                for row in trial_rows
            ),
            "three_exact_processes_per_config": all(exact.values()),
            "c0_c1_c2_area_ordering": area_ordering,
            "claim_boundary_explicit": claim_boundary_pass,
            "failure_entries_empty": not failures,
            "validation_issue_free": not issues,
        }
        root_evidence = {
            "run_id": run["run_id"],
            "artifact_root": str(root),
            "git_commit": manifest.get("git_commit"),
            "run_manifest_sha256": run["index"].get(
                "run_manifest_sha256"
            ),
            "records_sha256": run["index"].get("records_sha256"),
            "artifact_manifest_sha256": run["index"].get(
                "artifact_manifest_sha256"
            ),
            "artifact_count": run["index"].get("artifact_count"),
            "artifact_bytes": run["index"].get("artifact_bytes"),
            "artifact_verification": run["index"].get(
                "artifact_verification"
            ),
        }
        report = {
            "schema_version": SCHEMA_VERSION,
            "objective": "P0-6 C0/C1/C2 mapped synthesis",
            "scope": catalog["comparison_scope"],
            "library": catalog["library"],
            "mapping": catalog["mapping"],
            "claim_boundary": manifest.get("claim_boundary"),
            "physical_ppa_evidence": False,
            "index_set": index_set,
            "root_evidence": root_evidence,
            "input_checks": input_checks,
            "failure_entries": failures,
            "validation_issues": issues,
            "acceptance": acceptance,
            "counts": {
                "record_count": len(trial_rows),
                "failure_count": len(failures),
                "validation_issue_count": len(issues),
                "command_count": len(commands),
                "cell_type_row_count": sum(
                    len(cell_map) for cell_map in cell_maps.values()
                ),
                "status_counts": dict(
                    sorted(
                        Counter(
                            str(row.get("status")) for row in trial_rows
                        ).items()
                    )
                ),
            },
            "exact_reproducibility_by_config": exact,
            "synthesis_summary": summaries,
        }
        cells = cell_type_rows(cell_maps)
        write_outputs(
            output_dir,
            report,
            trial_rows,
            cells,
            index_set_path,
            catalog_path,
            git_context,
            repo_root,
        )
    except (OSError, AnalysisError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"P0-6 analysis failed: {error}") from error

    print(f"output_dir={output_dir}")
    print(
        f"records={len(trial_rows)} issues={len(issues)} "
        f"failures={len(failures)}"
    )
    print(f"acceptance={json.dumps(acceptance, sort_keys=True)}")
    return 0 if all(acceptance.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
