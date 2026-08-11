#!/usr/bin/env python3
"""Audit and compare the matched-LUT M2 measurement matrix."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import analyze_p0_4 as p0_4
import analyze_p0_5 as p0_5
import experiment_common as common
from util.online_softmax_merge import analyze_scaling as scaling_math


EXPECTED_CONFIGS = (
    "B2R_RVV",
    "A1_SMU_SCALAR",
    "A2_SMU_FULL",
)
SCALING_CASE_FILE = "p0_scaling_cases.json"
MODEL_CASE_FILE = "p0_model_workload_cases.json"
SCALING_POINT_COUNT = 23
MODEL_CASE_COUNT = 3
TRIAL_COUNT = 3
EXPECTED_COMMIT = "7225d41ad2d1c63376a9fb1ea4e56b3b24a3e97f"


def selected_case_ids(plan: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for shard in plan.get("shards", []):
        for case_id in shard.get("case_ids", []):
            case_id = str(case_id)
            if case_id in ids:
                raise ValueError(f"duplicate case ID in plan: {case_id}")
            ids.append(case_id)
    return ids


def validate_plan(plan: dict[str, Any]) -> tuple[str, ...]:
    configs = tuple(str(value) for value in plan.get("configurations", []))
    if configs != EXPECTED_CONFIGS:
        raise ValueError(
            "plan configurations must be "
            f"{list(EXPECTED_CONFIGS)}, got {configs}"
        )
    if plan.get("trials") != TRIAL_COUNT:
        raise ValueError("plan must use three trials")
    if plan.get("counter_profiles") != ["memory"]:
        raise ValueError("plan must use the memory profile")
    shards = plan.get("shards")
    if not isinstance(shards, list) or len(shards) != 9:
        raise ValueError("plan must contain nine shards")
    scale_count = 0
    model_count = 0
    for index, shard in enumerate(shards):
        case_file = str(shard.get("case_file"))
        case_ids = shard.get("case_ids")
        suite = str(shard.get("suite"))
        if not isinstance(case_ids, list) or not case_ids:
            raise ValueError(f"shard {index} has no case IDs")
        if index < 8:
            expected_suite = f"m2-matched-lut-scale-{index:02d}"
            if case_file != SCALING_CASE_FILE or suite != expected_suite:
                raise ValueError(f"invalid scaling shard {index}")
            scale_count += len(case_ids)
        else:
            if case_file != MODEL_CASE_FILE or suite != "m2-matched-lut-models":
                raise ValueError("invalid model shard")
            model_count += len(case_ids)
    if scale_count != SCALING_POINT_COUNT or model_count != MODEL_CASE_COUNT:
        raise ValueError(
            "plan case counts are "
            f"{scale_count} scaling and {model_count} models"
        )
    return configs


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def numeric(value: Any) -> float | None:
    if value is None or value == "" or value == "NA":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def fmt(value: Any, digits: int = 6) -> str:
    number = numeric(value)
    if number is None:
        return "NA"
    if float(number).is_integer() and digits == 0:
        return str(int(number))
    return f"{number:.{digits}f}"


def ratio(numerator: Any, denominator: Any) -> float | None:
    top = numeric(numerator)
    bottom = numeric(denominator)
    if top is None or bottom in (None, 0):
        return None
    return top / bottom


def geomean(values: Sequence[float | None]) -> float | None:
    if not values or any(value is None or value <= 0 for value in values):
        return None
    return math.prod(float(value) for value in values) ** (1.0 / len(values))


def record_correctness_pass(record: dict[str, Any]) -> bool:
    if record.get("status") != "PASS" or record.get("target_status") != "pass":
        return False
    if any(
        record.get(field) != 0
        for field in ("nonfinite", "nan_count", "inf_count")
    ):
        return False
    return all(
        numeric(record.get(field)) is not None
        for field in (
            "max_abs_error",
            "max_rel_error",
            "mean_abs_error",
            "l2_relative_error",
        )
    )


def gate_summary(
    records: Sequence[dict[str, Any]],
    summaries: Sequence[dict[str, Any]],
    root_rows: Sequence[dict[str, Any]],
    failure_entries: Sequence[dict[str, Any]],
    configs: Sequence[str],
    issues: list[str],
) -> dict[str, bool]:
    b2r = configs[0]
    smu_configs = set(configs[1:])
    correctness = bool(records) and all(
        record_correctness_pass(row) for row in records
    )
    status = bool(records) and all(
        row.get("status") == "PASS" and row.get("target_status") == "pass"
        for row in records
    )
    fairness = bool(records) and all(
        row.get("fairness_gate") == "PASS"
        and row.get("comparison_set_complete") == "YES"
        for row in records
    )
    fsm = bool(records) and all(
        row.get("fsm_gate") == "PASS"
        for row in records
        if row.get("config") in smu_configs
    ) and all(
        row.get("fsm_gate") == "NA"
        for row in records
        if row.get("config") == b2r
    )
    trace = bool(records) and all(
        row.get("dynamic_trace_verified") == "YES"
        and row.get("trace_witness_gate") == "PASS"
        and row.get("trace_target_equivalence_gate") == "PASS"
        for row in records
        if row.get("config") == b2r
    )
    reproducibility = bool(summaries) and all(
        row.get("trials") == TRIAL_COUNT and row.get("reproducible") == "YES"
        and row.get("kernel_cycles_min") == row.get("kernel_cycles_median")
        and row.get("kernel_cycles_median") == row.get("kernel_cycles_max")
        for row in summaries
    )
    roots = bool(root_rows) and all(
        row.get("artifact_verification") == "PASS" for row in root_rows
    )
    gates = {
        "correctness": correctness,
        "status": status,
        "fairness": fairness,
        "fsm": fsm,
        "trace": trace,
        "reproducibility": reproducibility,
        "root_artifacts": roots,
        "no_failure_entries": not failure_entries,
    }
    for name, passed in gates.items():
        if not passed:
            issues.append(f"{name} gate failed")
    return gates


def fit_scaling(
    summaries: Sequence[dict[str, Any]],
    configs: Sequence[str],
    issues: list[str],
) -> tuple[
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    models: dict[str, dict[str, Any]] = {}
    parameter_rows: list[dict[str, Any]] = []
    point_rows: list[dict[str, Any]] = []
    for config in configs:
        points = [
            {
                "case_id": row["case_id"],
                "N": row["N"],
                "D": row["D"],
                "cycles_median": row["kernel_cycles_median"],
            }
            for row in summaries
            if row.get("evidence_class") == "MAIN_PERFORMANCE"
            and row.get("config") == config
            and row.get("status") == "PASS"
            and row.get("paper_eligible") == "YES"
        ]
        if len(points) != SCALING_POINT_COUNT:
            issues.append(f"{config} scaling point count is {len(points)}")
            continue
        try:
            model = scaling_math.fit_model(points)
        except scaling_math.AnalysisError as error:
            issues.append(f"{config} scaling fit failed: {error}")
            continue
        models[config] = model
        parameters = model["parameters_cycles"]
        parameter_rows.append(
            {
                "kind": "parameter",
                "config": config,
                "case_id": "",
                "N": "",
                "D": "",
                "C0": parameters["C0"]["decimal"],
                "Cs": parameters["Cs"]["decimal"],
                "Cv": parameters["Cv"]["decimal"],
                "R_squared": model["R_squared"]["decimal"],
                "measured_cycles": "",
                "fitted_cycles": "",
                "Cstall_cycles": "",
                "fit_point_count": model["fit_point_count"],
            }
        )
        residuals = {row["case_id"]: row for row in model["residuals"]}
        ordered_points = sorted(
            points,
            key=lambda row: (row["N"], row["D"], row["case_id"]),
        )
        for point in ordered_points:
            residual = residuals[point["case_id"]]
            point_rows.append(
                {
                    "kind": "point",
                    "config": config,
                    "case_id": point["case_id"],
                    "N": point["N"],
                    "D": point["D"],
                    "C0": "",
                    "Cs": "",
                    "Cv": "",
                    "R_squared": "",
                    "measured_cycles": point["cycles_median"],
                    "fitted_cycles": residual["fitted_cycles"]["decimal"],
                    "Cstall_cycles": residual["Cstall_cycles"]["decimal"],
                    "fit_point_count": "",
                }
            )
    return models, parameter_rows, point_rows


def build_workloads(
    source_rows: Sequence[dict[str, Any]],
    summaries: Sequence[dict[str, Any]],
    configs: Sequence[str],
    issues: list[str],
) -> list[dict[str, Any]]:
    indexed = {
        (str(row.get("case_id")), str(row.get("config"))): row
        for row in summaries
    }
    rows: list[dict[str, Any]] = []
    for source in source_rows:
        case_id = str(source["case_id"])
        per_config = {
            config: indexed.get((case_id, config)) for config in configs
        }
        missing = [config for config, row in per_config.items() if row is None]
        if missing:
            issues.append(f"{case_id} missing configurations: {missing}")
        if any(
            row is None or row.get("status") != "PASS"
            for row in per_config.values()
        ):
            issues.append(
                f"{case_id} workload status is not PASS for all configurations"
            )
        row: dict[str, Any] = {
            "case_id": case_id,
            "model_id": source.get("model_id"),
            "N": source.get("N"),
            "D": source.get("D"),
            "source_audit": source.get("source_audit"),
            "disposition": "MEASURED",
        }
        cycles: dict[str, Any] = {}
        for config in configs:
            summary = per_config[config]
            value = summary.get("kernel_cycles_median") if summary else None
            cycles[config] = value
            row[f"{config}_cycles"] = value
            row[f"{config}_status"] = summary.get("status") if summary else None
            row[f"{config}_reproducible"] = (
                summary.get("reproducible") if summary else None
            )
        row["A1_vs_B2R_speedup"] = ratio(cycles[configs[0]], cycles[configs[1]])
        row["A2_vs_B2R_speedup"] = ratio(cycles[configs[0]], cycles[configs[2]])
        row["paper_eligible"] = "YES" if all(
            summary is not None and summary.get("paper_eligible") == "YES"
            for summary in per_config.values()
        ) else "NO"
        if row["paper_eligible"] != "YES":
            issues.append(f"{case_id} workload rows are not paper eligible")
        rows.append(row)
    return rows


def compare_value(
    metric: str,
    scope: str,
    config: str,
    workload: str,
    old: Any,
    new: Any,
) -> dict[str, Any]:
    old_number = numeric(old)
    new_number = numeric(new)
    delta = (
        new_number - old_number
        if old_number is not None and new_number is not None
        else None
    )
    delta_percent = (
        delta / old_number * 100.0
        if delta is not None and old_number not in (None, 0)
        else None
    )
    return {
        "metric": metric,
        "scope": scope,
        "config": config,
        "workload": workload,
        "old": old_number,
        "new": new_number,
        "delta": delta,
        "delta_percent": delta_percent,
    }


def load_old_values(
    old_scaling_path: Path,
    old_workload_path: Path,
    configs: Sequence[str],
    workload_ids: Sequence[str],
    issues: list[str],
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    old_scaling: dict[str, dict[str, float]] = {}
    for row in load_csv(old_scaling_path):
        if row.get("kind") != "parameter" or row.get("config") not in configs:
            continue
        old_scaling[row["config"]] = {
            key: numeric(row.get(key))
            for key in ("C0", "Cs", "Cv")
        }
    for config in configs:
        if config not in old_scaling or any(
            value is None for value in old_scaling[config].values()
        ):
            issues.append(f"old scaling anchor missing {config}")

    old_workloads: dict[str, dict[str, float]] = {}
    for row in load_csv(old_workload_path):
        case_id = row.get("case_id")
        if case_id not in workload_ids or row.get("disposition") != "MEASURED":
            continue
        values: dict[str, float] = {}
        for config in configs:
            cycles = numeric(row.get(f"{config}_cycles"))
            if cycles is None:
                issues.append(f"old workload anchor missing {case_id}/{config}")
            else:
                values[f"{config}_cycles"] = cycles
        for metric in ("A1_vs_B2R_speedup", "A2_vs_B2R_speedup"):
            value = numeric(row.get(metric))
            if value is None:
                issues.append(f"old workload anchor missing {case_id}/{metric}")
            else:
                values[metric] = value
        old_workloads[case_id] = values
    if set(old_workloads) != set(workload_ids):
        issues.append("old workload anchor coverage differs")
    return old_scaling, old_workloads


def build_comparison(
    models: dict[str, dict[str, Any]],
    workload_rows: Sequence[dict[str, Any]],
    old_scaling: dict[str, dict[str, float]],
    old_workloads: dict[str, dict[str, float]],
    configs: Sequence[str],
    issues: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in configs:
        model = models.get(config)
        if model is None:
            continue
        params = model["parameters_cycles"]
        for metric in ("C0", "Cs", "Cv"):
            new = params[metric]["decimal"]
            old = old_scaling.get(config, {}).get(metric)
            rows.append(compare_value(metric, "scaling", config, "", old, new))
    for workload in workload_rows:
        case_id = str(workload["case_id"])
        old = old_workloads.get(case_id, {})
        for config in configs:
            rows.append(
                compare_value(
                    "cycles",
                    "workload",
                    config,
                    case_id,
                    old.get(f"{config}_cycles"),
                    workload.get(f"{config}_cycles"),
                )
            )
        for metric, config in (
            ("A1_vs_B2R_speedup", configs[1]),
            ("A2_vs_B2R_speedup", configs[2]),
        ):
            rows.append(
                compare_value(
                    "speedup", "workload", config, case_id,
                    old.get(metric), workload.get(metric),
                )
            )
    for metric, config, field in (
        ("A1_geomean_speedup", configs[1], "A1_vs_B2R_speedup"),
        ("A2_geomean_speedup", configs[2], "A2_vs_B2R_speedup"),
    ):
        old_values = [
            old_workloads.get(row["case_id"], {}).get(field)
            for row in workload_rows
        ]
        new_values = [numeric(row.get(field)) for row in workload_rows]
        old_value = geomean(old_values)
        new_value = geomean(new_values)
        rows.append(
            compare_value(
                metric,
                "workload_geomean",
                config,
                "geomean",
                old_value,
                new_value,
            )
        )
    expected_count = (
        len(configs) * 3 + MODEL_CASE_COUNT * (len(configs) + 2) + 2
    )
    if len(rows) != expected_count:
        issues.append(f"comparison row count is {len(rows)}")
    return rows


def markdown_report(
    report: dict[str, Any],
    configs: Sequence[str],
) -> str:
    lines = [
        "# M2 Matched-LUT Revalidation",
        "",
        "## Acceptance",
        "",
    ]
    for name, passed in report["acceptance"].items():
        lines.append(f"- `{name}`: `{'PASS' if passed else 'FAIL'}`")
    lines.extend(["", "## Counts", ""])
    for name in (
        "root_count",
        "record_count",
        "failure_count",
        "validation_issue_count",
    ):
        lines.append(f"- `{name}`: `{report['counts'][name]}`")
    lines.extend(
        [
            "",
            "## Scaling old to new",
            "",
            "| Config | C0 | Cs | Cv |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for config in configs:
        values = {
            row["metric"]: row for row in report["comparison"]
            if row["scope"] == "scaling" and row["config"] == config
        }
        lines.append(
            f"| {config} | "
            f"{fmt(values['C0']['old'])}→{fmt(values['C0']['new'])} | "
            f"{fmt(values['Cs']['old'])}→{fmt(values['Cs']['new'])} | "
            f"{fmt(values['Cv']['old'])}→{fmt(values['Cv']['new'])} |"
        )
    lines.extend([
        "", "## Workload old to new", "",
        "| Workload | B2R cycles | A1 cycles | A2 cycles | A1 speedup | A2 speedup |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for workload in report["workloads"]:
        case_id = workload["case_id"]
        entries = [
            row
            for row in report["comparison"]
            if row["scope"] == "workload"
            and row["workload"] == case_id
        ]
        by_key = {(row["metric"], row["config"]): row for row in entries}
        lines.append(
            f"| {workload['model_id']} | "
            f"{fmt(by_key[('cycles', configs[0])]['old'], 0)}→"
            f"{fmt(by_key[('cycles', configs[0])]['new'], 0)} | "
            f"{fmt(by_key[('cycles', configs[1])]['old'], 0)}→"
            f"{fmt(by_key[('cycles', configs[1])]['new'], 0)} | "
            f"{fmt(by_key[('cycles', configs[2])]['old'], 0)}→"
            f"{fmt(by_key[('cycles', configs[2])]['new'], 0)} | "
            f"{fmt(by_key[('speedup', configs[1])]['old'])}→"
            f"{fmt(by_key[('speedup', configs[1])]['new'])} | "
            f"{fmt(by_key[('speedup', configs[2])]['old'])}→"
            f"{fmt(by_key[('speedup', configs[2])]['new'])} |"
        )
    lines.extend(["", "## Geomean old to new", ""])
    for config in configs[1:]:
        metric = (
            "A1_geomean_speedup"
            if config == configs[1]
            else "A2_geomean_speedup"
        )
        row = next(
            item
            for item in report["comparison"]
            if item["metric"] == metric
        )
        lines.append(f"- `{metric}`: `{fmt(row['old'])}→{fmt(row['new'])}`")
    lines.extend(["", "## Correctness and repeat consistency", ""])
    lines.append(
        f"- `correctness`: `{'PASS' if report['gates']['correctness'] else 'FAIL'}`"
    )
    lines.append(
        "- `repeat_consistency`: "
        f"`{'PASS' if report['gates']['reproducibility'] else 'FAIL'}`"
    )
    return "\n".join(lines) + "\n"


def write_outputs(
    output_dir: Path,
    report: dict[str, Any],
    records: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    plan_path: Path,
    policy_path: Path,
    index_set_path: Path,
    old_scaling_path: Path,
    old_workload_path: Path,
    catalog_paths: dict[str, Path],
    repo_root: Path,
) -> None:
    report_path = (
        repo_root / "experiments/reports/M2_MATCHED_LUT_REVALIDATION.md"
    )
    if output_dir.exists() or report_path.exists():
        raise ValueError("refusing to overwrite M2 output or report")
    output_dir.mkdir(parents=True)
    markdown = markdown_report(report, report["configs"])
    csv_payloads = {
        "m2_scaling.csv": report["scaling_rows"],
        "m2_workloads.csv": report["workloads"],
        "m2_comparison.csv": report["comparison"],
        "m2_all_records.csv": records,
        "m2_trial_summary.csv": summaries,
        "m2_root_audit.csv": report["root_evidence"],
        "m2_model_source_audit.csv": report["model_source_audit"],
        "m2_scaling_residuals.csv": report["scaling_residuals"],
    }
    json_payloads = {
        "m2_analysis.json": report,
        "m2_all_records.json": records,
        "m2_trial_summary.json": summaries,
        "m2_root_audit.json": report["root_evidence"],
        "m2_failure_entries.json": report["failure_entries"],
        "m2_model_source_audit.json": report["model_source_audit"],
    }
    for name, payload in csv_payloads.items():
        common.write_csv(output_dir / name, payload)
    for name, payload in json_payloads.items():
        common.write_json(output_dir / name, payload)
    common.write_json(output_dir / "m2_index_set.json", report["index_set"])
    (output_dir / "M2_MATCHED_LUT_REVALIDATION.md").write_text(
        markdown,
        encoding="utf-8",
    )
    report_path.write_text(markdown, encoding="utf-8")

    input_paths = [
        plan_path,
        policy_path,
        index_set_path,
        old_scaling_path,
        old_workload_path,
        *catalog_paths.values(),
    ]
    output_paths = [*output_dir.iterdir(), report_path]
    manifest = {
        "schema_version": 1,
        "analysis_git": report["git_context"],
        "analysis_tool": {
            "path": common.relative_or_absolute(
                Path(__file__).resolve(), repo_root
            ),
            "sha256": common.sha256_file(Path(__file__).resolve()),
            "python": sys.version.split()[0],
        },
        "inputs": [
            {
                "path": common.relative_or_absolute(path, repo_root),
                "sha256": common.sha256_file(path),
            }
            for path in input_paths
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
    common.write_json(output_dir / "m2_manifest.json", manifest)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=common.REPO_ROOT)
    parser.add_argument("--index-set", type=Path, required=True)
    parser.add_argument(
        "--plan",
        type=Path,
        default=common.REPO_ROOT
        / "experiments/configs/m2_matched_lut_shards.json",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=common.REPO_ROOT
        / "experiments/configs/m2_matched_lut_policy.json",
    )
    parser.add_argument(
        "--old-scaling",
        type=Path,
        default=common.REPO_ROOT
        / "experiments/parsed/final_scaling_model.csv",
    )
    parser.add_argument(
        "--old-workloads",
        type=Path,
        default=common.REPO_ROOT
        / "experiments/parsed/p0_5/p0_5_workload_comparison.csv",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--require-clean", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    plan_path = args.plan.resolve()
    policy_path = args.policy.resolve()
    index_set_path = args.index_set.resolve()
    old_scaling_path = args.old_scaling.resolve()
    old_workload_path = args.old_workloads.resolve()
    output_dir = args.output_dir.resolve()
    git_context = {
        "commit": common.git_output(repo_root, "rev-parse", "HEAD"),
        "branch": common.git_output(repo_root, "branch", "--show-current"),
        "dirty": bool(common.git_output(repo_root, "status", "--porcelain")),
    }
    initial_issues: list[str] = []
    if git_context["commit"] != EXPECTED_COMMIT:
        initial_issues.append(
            "analysis HEAD differs from expected M2 commit: "
            f"{git_context['commit']} != {EXPECTED_COMMIT}"
        )
    if args.require_clean and git_context["dirty"]:
        raise SystemExit("--require-clean rejected a dirty Git worktree")
    try:
        plan = p0_4.load_json(plan_path, dict)
        configs = validate_plan(plan)
        policy = p0_4.load_json(policy_path, dict)
        if list(policy.get("configurations", {})) != list(configs):
            raise ValueError("policy configuration order differs from plan")
        p0_4.CONFIGS = configs
        p0_4.MODEL_CONFIGS = configs
        index_set, runs = p0_4.load_indexed_runs(repo_root, index_set_path)
        policy_hash = common.sha256_file(policy_path)
        run_manifest_issues: list[str] = []
        for run in runs:
            manifest = run["manifest"]
            run_id = str(manifest.get("run_id"))
            if manifest.get("git_commit") != EXPECTED_COMMIT:
                run_manifest_issues.append(
                    f"{run_id} git_commit differs from expected M2 commit"
                )
            if manifest.get("git_dirty") is not False:
                run_manifest_issues.append(
                    f"{run_id} has dirty-worktree evidence"
                )
            if manifest.get("policy_sha256") != policy_hash:
                run_manifest_issues.append(
                    f"{run_id} policy hash differs from M2 policy"
                )
        cases, catalog_paths = p0_4.load_case_catalogs(repo_root, plan)
        selected_ids = selected_case_ids(plan)
        if len(selected_ids) != SCALING_POINT_COUNT + MODEL_CASE_COUNT:
            raise ValueError("selected case count is not 26")
        raw_model_cases = p0_4.load_json(catalog_paths[MODEL_CASE_FILE], list)
        model_ids = [
            case_id for case_id in selected_ids
            if cases[case_id].evidence_class == "MODEL_WORKLOAD"
        ]
        model_cases = {case_id: cases[case_id] for case_id in model_ids}
        selected_model_cases = [
            item
            for item in raw_model_cases
            if item.get("case_id") in model_ids
        ]
        model_source_issues, model_source_rows = p0_5.validate_model_catalog(
            selected_model_cases,
            model_cases,
        )
        root_issues, root_rows, failure_entries = p0_4.audit_roots(
            repo_root, plan, catalog_paths, runs
        )
        record_issues, records, summaries = p0_4.audit_records(
            plan, cases, policy, runs
        )
        issues = (
            initial_issues
            + run_manifest_issues
            + model_source_issues
            + root_issues
            + record_issues
        )
        gates = gate_summary(
            records,
            summaries,
            root_rows,
            failure_entries,
            configs,
            issues,
        )
        models, parameter_rows, point_rows = fit_scaling(
            summaries, configs, issues
        )
        workload_rows = build_workloads(
            model_source_rows, summaries, configs, issues
        )
        old_scaling, old_workloads = load_old_values(
            old_scaling_path, old_workload_path, configs, model_ids, issues
        )
        comparison = build_comparison(
            models,
            workload_rows,
            old_scaling,
            old_workloads,
            configs,
            issues,
        )
        scaling_rows = parameter_rows + point_rows
        paper_eligible_count = sum(
            row.get("paper_eligible") == "YES" for row in records
        )
        if paper_eligible_count != 234:
            issues.append(
                "paper-eligible record count is "
                f"{paper_eligible_count}, expected 234"
            )
        report = {
            "schema_version": 1,
            "objective": "M2 matched reciprocal-LUT revalidation",
            "configs": list(configs),
            "index_set": index_set,
            "git_context": git_context,
            "root_evidence": root_rows,
            "failure_entries": failure_entries,
            "run_manifest_issues": run_manifest_issues,
            "validation_issues": issues,
            "gates": gates,
            "acceptance": {
                "expected_analysis_head": (
                    git_context["commit"] == EXPECTED_COMMIT
                ),
                "index_set_complete": len(runs) == 9,
                "all_external_artifacts_reverified": gates["root_artifacts"],
                "no_failure_entries": gates["no_failure_entries"],
                "record_matrix_complete": len(records) == 234,
                "paper_eligible_matrix_complete": (
                    paper_eligible_count == 234
                ),
                "measurement_roots_clean_and_code_matched": (
                    len(runs) == 9 and not run_manifest_issues
                ),
                "validation_issue_free": not issues,
                "model_sources_complete": (
                    len(model_source_rows) == MODEL_CASE_COUNT
                    and not model_source_issues
                ),
                "scaling_models_complete": (
                    len(models) == len(configs)
                    and all(
                        len([
                            row
                            for row in point_rows
                            if row["config"] == config
                        ])
                        == SCALING_POINT_COUNT
                        for config in configs
                    )
                ),
                "workload_rows_complete": (
                    len(workload_rows) == MODEL_CASE_COUNT
                ),
                "correctness_gates_pass": gates["correctness"],
                "repeat_consistency_pass": gates["reproducibility"],
                "status_gates_pass": gates["status"],
                "fairness_gates_pass": gates["fairness"],
                "fsm_gates_pass": gates["fsm"],
                "trace_gates_pass": gates["trace"],
                "reproducibility_gates_pass": gates["reproducibility"],
            },
            "counts": {
                "root_count": len(runs),
                "case_count": len(selected_ids),
                "record_count": len(records),
                "summary_row_count": len(summaries),
                "failure_count": len(failure_entries),
                "validation_issue_count": len(issues),
                "paper_eligible_record_count": paper_eligible_count,
            },
            "model_source_audit": model_source_rows,
            "workloads": workload_rows,
            "scaling_rows": scaling_rows,
            "scaling_residuals": [row for row in point_rows],
            "comparison": comparison,
        }
        write_outputs(
            output_dir, report, records, summaries, plan_path, policy_path,
            index_set_path, old_scaling_path, old_workload_path, catalog_paths,
            repo_root,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"M2 analysis failed: {error}") from error
    print(f"output_dir={output_dir}")
    print(f"record_count={report['counts']['record_count']}")
    print(
        "validation_issue_count="
        + str(report["counts"]["validation_issue_count"])
    )
    return 0 if report["acceptance"]["validation_issue_free"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
