#!/usr/bin/env python3
"""Validate and summarize formal P0-5 model-shape workloads."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import analyze_p0_4 as p0_4
import experiment_common as common
import run_performance_matrix as matrix


REVISION_PATTERN = re.compile(r"[0-9a-f]{40}")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
MODEL_MAPPING = "one_attention_position_all_query_heads"
MEASURED_STATUS = "PASS"
CAPACITY_STATUS = "SKIPPED_MEMORY_LIMIT"


def validate_model_catalog(
    raw_cases: Sequence[dict[str, Any]],
    cases: dict[str, matrix.Case],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Validate pinned source metadata and the exact N/D mapping."""
    issues: list[str] = []
    rows: list[dict[str, Any]] = []
    seen_models: set[str] = set()
    seen_cases: set[str] = set()
    for position, item in enumerate(raw_cases):
        if not isinstance(item, dict):
            issues.append(f"model case {position} is not an object")
            continue
        case_id = str(item.get("case_id"))
        model_id = str(item.get("model_id"))
        case = cases.get(case_id)
        if case is None:
            issues.append(f"model metadata has unknown case: {case_id}")
            continue
        if case_id in seen_cases:
            issues.append(f"duplicate model case metadata: {case_id}")
        if model_id in seen_models:
            issues.append(f"duplicate model source: {model_id}")
        if not model_id or model_id == "None" or "/" not in model_id:
            issues.append(f"{case_id} has an invalid model ID")
        seen_cases.add(case_id)
        seen_models.add(model_id)

        revision = item.get("model_revision")
        config_hash = item.get("model_config_sha256")
        config_url = item.get("model_config_url")
        hidden_size = item.get("hidden_size")
        heads = item.get("num_attention_heads")
        source_bytes = item.get("model_config_bytes")
        mapping = item.get("workload_mapping")
        if not isinstance(revision, str) or not REVISION_PATTERN.fullmatch(
            revision
        ):
            issues.append(f"{case_id} has an invalid model revision")
        if not isinstance(config_hash, str) or not SHA256_PATTERN.fullmatch(
            config_hash
        ):
            issues.append(f"{case_id} has an invalid config SHA256")
        if (
            not isinstance(config_url, str)
            or not config_url.startswith("https://huggingface.co/")
            or not isinstance(revision, str)
            or revision not in config_url
        ):
            issues.append(f"{case_id} has an unpinned config URL")
        if (
            not isinstance(hidden_size, int)
            or isinstance(hidden_size, bool)
            or hidden_size <= 0
            or not isinstance(heads, int)
            or isinstance(heads, bool)
            or heads <= 0
        ):
            issues.append(f"{case_id} has invalid model dimensions")
            head_dimension = None
        elif hidden_size % heads != 0:
            issues.append(f"{case_id} hidden size is not divisible by heads")
            head_dimension = None
        else:
            head_dimension = hidden_size // heads
            if case.n != heads or case.d != head_dimension:
                issues.append(f"{case_id} N/D mapping differs from source")
        if (
            not isinstance(source_bytes, int)
            or isinstance(source_bytes, bool)
            or source_bytes <= 0
        ):
            issues.append(f"{case_id} has an invalid source byte count")
        if mapping != MODEL_MAPPING:
            issues.append(f"{case_id} has an unsupported workload mapping")
        if case.evidence_class != "MODEL_WORKLOAD":
            issues.append(f"{case_id} is not MODEL_WORKLOAD evidence")

        rows.append(
            {
                "case_id": case_id,
                "model_id": model_id,
                "model_revision": revision,
                "model_config_url": config_url,
                "model_config_sha256": config_hash,
                "model_config_bytes": source_bytes,
                "model_config_retrieved_utc": item.get(
                    "model_config_retrieved_utc"
                ),
                "hidden_size": hidden_size,
                "num_attention_heads": heads,
                "num_key_value_heads": item.get("num_key_value_heads"),
                "N": case.n,
                "D": case.d,
                "derived_head_dimension": head_dimension,
                "workload_mapping": mapping,
                "input_pattern": case.case_kind,
                "source_audit": "PASS",
            }
        )
    if seen_cases != set(cases):
        issues.append(
            "model metadata coverage differs: missing="
            f"{sorted(set(cases) - seen_cases)}, extra="
            f"{sorted(seen_cases - set(cases))}"
        )
    if issues:
        for row in rows:
            row["source_audit"] = "FAIL"
    return issues, rows


def ratio(numerator: Any, denominator: Any) -> float | None:
    if (
        isinstance(numerator, (int, float))
        and not isinstance(numerator, bool)
        and isinstance(denominator, (int, float))
        and not isinstance(denominator, bool)
        and denominator > 0
    ):
        return float(numerator) / float(denominator)
    return None


def build_workload_comparisons(
    source_rows: Sequence[dict[str, Any]],
    summaries: Sequence[dict[str, Any]],
    issues: list[str],
) -> list[dict[str, Any]]:
    """Join one exact three-trial summary per model/configuration."""
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for summary in summaries:
        key = (str(summary.get("case_id")), str(summary.get("config")))
        if key in indexed:
            issues.append(f"duplicate workload summary: {key}")
        indexed[key] = summary

    rows: list[dict[str, Any]] = []
    for source in source_rows:
        case_id = str(source["case_id"])
        per_config = {
            config: indexed.get((case_id, config))
            for config in p0_4.CONFIGS
        }
        missing = [
            config for config, summary in per_config.items() if summary is None
        ]
        if missing:
            issues.append(f"{case_id} lacks summaries for {missing}")
        statuses = {
            summary.get("status")
            for summary in per_config.values()
            if summary is not None
        }
        if statuses == {MEASURED_STATUS}:
            disposition = "MEASURED"
        elif statuses == {CAPACITY_STATUS}:
            disposition = "EXPLICIT_CAPACITY_SKIP"
        else:
            disposition = "INVALID_MIXED_STATUS"
            display_statuses = sorted(str(status) for status in statuses)
            issues.append(
                f"{case_id} has mixed statuses: {display_statuses}"
            )

        cycles = {
            config: (
                per_config[config].get("kernel_cycles_median")
                if per_config[config] is not None
                else None
            )
            for config in p0_4.CONFIGS
        }
        if disposition == "MEASURED":
            if any(value is None for value in cycles.values()):
                issues.append(f"{case_id} measured cycles are incomplete")
            if any(
                summary is None
                or summary.get("paper_eligible") != "YES"
                for summary in per_config.values()
            ):
                issues.append(f"{case_id} measured rows are paper-ineligible")
        elif disposition == "EXPLICIT_CAPACITY_SKIP":
            if any(value not in (None, 0) for value in cycles.values()):
                issues.append(f"{case_id} capacity skip reports cycles")
            if any(
                summary is None
                or summary.get("paper_eligible") != "NO"
                for summary in per_config.values()
            ):
                issues.append(f"{case_id} capacity skip paper gate differs")

        rows.append(
            {
                **source,
                "disposition": disposition,
                "B1_SCALAR_status": (
                    per_config["B1_SCALAR"].get("status")
                    if per_config["B1_SCALAR"] is not None
                    else None
                ),
                "B2R_RVV_status": (
                    per_config["B2R_RVV"].get("status")
                    if per_config["B2R_RVV"] is not None
                    else None
                ),
                "A1_SMU_SCALAR_status": (
                    per_config["A1_SMU_SCALAR"].get("status")
                    if per_config["A1_SMU_SCALAR"] is not None
                    else None
                ),
                "A2_SMU_FULL_status": (
                    per_config["A2_SMU_FULL"].get("status")
                    if per_config["A2_SMU_FULL"] is not None
                    else None
                ),
                "B1_SCALAR_cycles": cycles["B1_SCALAR"],
                "B2R_RVV_cycles": cycles["B2R_RVV"],
                "A1_SMU_SCALAR_cycles": cycles["A1_SMU_SCALAR"],
                "A2_SMU_FULL_cycles": cycles["A2_SMU_FULL"],
                "A2_vs_B1_speedup": ratio(
                    cycles["B1_SCALAR"], cycles["A2_SMU_FULL"]
                ),
                "A2_vs_B2R_speedup": ratio(
                    cycles["B2R_RVV"], cycles["A2_SMU_FULL"]
                ),
                "A1_vs_B2R_speedup": ratio(
                    cycles["B2R_RVV"], cycles["A1_SMU_SCALAR"]
                ),
                "memory_footprint_bytes": next(
                    (
                        summary.get("memory_footprint_bytes")
                        for summary in per_config.values()
                        if summary is not None
                    ),
                    None,
                ),
                "paper_eligible": (
                    "YES" if disposition == "MEASURED" else "NO"
                ),
            }
        )
    return rows


def format_value(value: Any, digits: int = 3) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# P0-5 Model-Shape Workload Report",
        "",
        "This stage maps pinned model configuration shapes onto one logical",
        "attention position: `N` is the query-head count and `D` is the",
        "derived head dimension. Inputs remain deterministic generated merge",
        "states; this is not end-to-end inference or captured activation data.",
        "",
        "## Acceptance",
        "",
    ]
    for gate, passed in report["acceptance"].items():
        lines.append(f"- `{gate}`: `{'PASS' if passed else 'FAIL'}`")
    lines.extend(
        [
            "",
            "## Workloads",
            "",
            "| Model | N | D | Disposition | B1 | B2-R | A1 | A2 | "
            "A2 vs B2-R |",
            "| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | "
            "---: |",
        ]
    )
    for row in report["workload_comparisons"]:
        lines.append(
            f"| {row['model_id']} | {row['N']} | {row['D']} | "
            f"{row['disposition']} | "
            f"{format_value(row['B1_SCALAR_cycles'], 0)} | "
            f"{format_value(row['B2R_RVV_cycles'], 0)} | "
            f"{format_value(row['A1_SMU_SCALAR_cycles'], 0)} | "
            f"{format_value(row['A2_SMU_FULL_cycles'], 0)} | "
            f"{format_value(row['A2_vs_B2R_speedup'])} |"
        )
    if report["validation_issues"]:
        lines.extend(["", "## Validation issues", ""])
        lines.extend(f"- {issue}" for issue in report["validation_issues"])
    if report["failure_entries"]:
        lines.extend(["", "## Preserved failure entries", ""])
        for failure in report["failure_entries"]:
            lines.append(
                f"- `{failure['suite']}`: "
                f"`{json.dumps(failure['failure'], sort_keys=True)}`"
            )
    return "\n".join(lines) + "\n"


def write_outputs(
    output_dir: Path,
    report: dict[str, Any],
    records: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    index_set_path: Path,
    plan_path: Path,
    policy_path: Path,
    catalog_path: Path,
    git_context: dict[str, Any],
    repo_root: Path,
) -> None:
    if output_dir.exists():
        raise ValueError(f"refusing to overwrite output directory: {output_dir}")
    output_dir.mkdir(parents=True)
    payloads: list[tuple[Path, Any, str]] = [
        (output_dir / "p0_5_analysis.json", report, "json"),
        (output_dir / "p0_5_all_records.json", records, "json"),
        (output_dir / "p0_5_all_records.csv", records, "csv"),
        (output_dir / "p0_5_trial_summary.csv", summaries, "csv"),
        (
            output_dir / "p0_5_model_source_audit.csv",
            report["model_source_audit"],
            "csv",
        ),
        (
            output_dir / "p0_5_workload_comparison.csv",
            report["workload_comparisons"],
            "csv",
        ),
    ]
    for path, payload, kind in payloads:
        if kind == "json":
            common.write_json(path, payload)
        else:
            common.write_csv(path, payload)
    report_path = output_dir / "P0_5_MODEL_WORKLOAD_REPORT.md"
    report_path.write_text(markdown_report(report), encoding="utf-8")
    output_paths = [path for path, _, _ in payloads] + [report_path]
    manifest = {
        "schema_version": 1,
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
                "path": common.relative_or_absolute(index_set_path, repo_root),
                "sha256": common.sha256_file(index_set_path),
            },
            "plan": {
                "path": common.relative_or_absolute(plan_path, repo_root),
                "sha256": common.sha256_file(plan_path),
            },
            "policy": {
                "path": common.relative_or_absolute(policy_path, repo_root),
                "sha256": common.sha256_file(policy_path),
            },
            "model_catalog": {
                "path": common.relative_or_absolute(catalog_path, repo_root),
                "sha256": common.sha256_file(catalog_path),
            },
            "roots": report["root_evidence"],
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
    common.write_json(output_dir / "p0_5_manifest.json", manifest)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=common.REPO_ROOT)
    parser.add_argument("--index-set", type=Path, required=True)
    parser.add_argument(
        "--plan",
        type=Path,
        default=common.REPO_ROOT / "experiments/configs/p0_5_shards.json",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=common.REPO_ROOT
        / "experiments/configs/measurement_policy.json",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--require-clean", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    index_set_path = args.index_set.resolve()
    plan_path = args.plan.resolve()
    policy_path = args.policy.resolve()
    output_dir = args.output_dir.resolve()
    git_context = {
        "commit": common.git_output(repo_root, "rev-parse", "HEAD"),
        "branch": common.git_output(repo_root, "branch", "--show-current"),
        "dirty": bool(common.git_output(repo_root, "status", "--porcelain")),
    }
    if args.require_clean and git_context["dirty"]:
        raise SystemExit("--require-clean rejected a dirty Git worktree")
    try:
        plan = p0_4.load_json(plan_path, dict)
        policy = p0_4.load_json(policy_path, dict)
        index_set, runs = p0_4.load_indexed_runs(
            repo_root, index_set_path
        )
        cases, catalog_paths = p0_4.load_case_catalogs(repo_root, plan)
        if len(catalog_paths) != 1:
            raise ValueError("P0-5 requires exactly one model catalog")
        catalog_path = next(iter(catalog_paths.values()))
        raw_cases = p0_4.load_json(catalog_path, list)
        source_issues, source_rows = validate_model_catalog(raw_cases, cases)
        root_issues, root_rows, failure_entries = p0_4.audit_roots(
            repo_root, plan, catalog_paths, runs
        )
        record_issues, records, summaries = p0_4.audit_records(
            plan, cases, policy, runs
        )
        issues = source_issues + root_issues + record_issues
        comparison_rows = build_workload_comparisons(
            source_rows, summaries, issues
        )
        status_counts = dict(
            sorted(Counter(str(row.get("status")) for row in records).items())
        )
        disposition_counts = Counter(
            row["disposition"] for row in comparison_rows
        )
        paper_count = sum(
            row.get("paper_eligible") == "YES" for row in records
        )
        acceptance = {
            "index_set_complete": len(runs) == len(plan["shards"]) == 2,
            "all_external_artifacts_reverified": all(
                row["artifact_verification"] == "PASS" for row in root_rows
            ),
            "no_failure_entries": not failure_entries,
            "record_matrix_complete": len(records) == 4 * 4 * 3,
            "validation_issue_free": not issues,
            "pinned_model_sources_complete": (
                len(source_rows) == 4
                and all(row["source_audit"] == "PASS" for row in source_rows)
            ),
            "workload_dispositions_exact": disposition_counts
            == Counter({"MEASURED": 3, "EXPLICIT_CAPACITY_SKIP": 1}),
            "paper_eligible_scope_exact": paper_count == 3 * 4 * 3,
        }
        report = {
            "schema_version": 1,
            "objective": "P0-5 pinned real-model shape workloads",
            "scope": (
                "one logical attention position across all query heads; "
                "deterministic generated merge states, not full inference"
            ),
            "mapping": {
                "N": "num_attention_heads",
                "D": "hidden_size / num_attention_heads",
                "padding": "none",
                "automatic_tiling": False,
            },
            "index_set": index_set,
            "root_evidence": root_rows,
            "failure_entries": failure_entries,
            "validation_issues": issues,
            "acceptance": acceptance,
            "counts": {
                "root_count": len(runs),
                "case_count": len(cases),
                "record_count": len(records),
                "summary_row_count": len(summaries),
                "failure_count": len(failure_entries),
                "validation_issue_count": len(issues),
                "paper_eligible_record_count": paper_count,
                "status_counts": status_counts,
                "disposition_counts": dict(sorted(disposition_counts.items())),
            },
            "model_source_audit": source_rows,
            "workload_comparisons": comparison_rows,
        }
        write_outputs(
            output_dir,
            report,
            records,
            summaries,
            index_set_path,
            plan_path,
            policy_path,
            catalog_path,
            git_context,
            repo_root,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"P0-5 analysis failed: {error}") from error

    print(f"output_dir={output_dir}")
    print(
        f"roots={len(runs)} records={len(records)} "
        f"issues={len(issues)} failures={len(failure_entries)}"
    )
    print(f"acceptance={json.dumps(acceptance, sort_keys=True)}")
    return 0 if all(acceptance.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
