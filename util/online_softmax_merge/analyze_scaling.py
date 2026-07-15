#!/usr/bin/env python3
# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Fit Online Softmax Merge scaling models and measured break-even rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Sequence

MODEL_IMPLEMENTATIONS = ("B2-R", "B3")
MODEL_FORMULA = "C(N,D) = C0 + Cs*N + Cv*N*D + Cstall"
PROVENANCE_ONLY_RECORD_FIELDS = {"source_root", "git_commit"}


class AnalysisError(ValueError):
    """Raised when input evidence cannot support the requested analysis."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_positive_ints(value: str) -> tuple[int, ...]:
    try:
        values = tuple(int(item) for item in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "expected a comma-separated integer list"
        ) from error
    if not values or any(item <= 0 for item in values):
        raise argparse.ArgumentTypeError("all values must be positive")
    if len(set(values)) != len(values):
        raise argparse.ArgumentTypeError("values must not repeat")
    return values


def as_fraction(value: int | float | Fraction) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnalysisError(f"expected a numeric value, got {value!r}")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AnalysisError(f"expected a finite value, got {value!r}")
        return Fraction(str(value))
    return Fraction(value)


def median_fraction(values: Iterable[int | float | Fraction]) -> Fraction:
    ordered = sorted(as_fraction(value) for value in values)
    if not ordered:
        raise AnalysisError("cannot take the median of an empty sequence")
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def fraction_json(value: Fraction) -> dict[str, Any]:
    return {
        "decimal": float(value),
        "numerator": value.numerator,
        "denominator": value.denominator,
    }


def solve_linear_system(
    matrix: Sequence[Sequence[Fraction]],
    vector: Sequence[Fraction],
) -> list[Fraction]:
    size = len(vector)
    if len(matrix) != size or any(len(row) != size for row in matrix):
        raise AnalysisError("linear system must be square")
    augmented = [
        list(row) + [vector[index]]
        for index, row in enumerate(matrix)
    ]
    for column in range(size):
        pivot = next(
            (row for row in range(column, size) if augmented[row][column]),
            None,
        )
        if pivot is None:
            raise AnalysisError("scale-model design matrix is singular")
        augmented[column], augmented[pivot] = (
            augmented[pivot],
            augmented[column],
        )
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                augmented[row] = [
                    left - factor * right
                    for left, right in zip(
                        augmented[row], augmented[column], strict=True
                    )
                ]
    return [augmented[row][-1] for row in range(size)]


def fit_model(points: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if len(points) < 3:
        raise AnalysisError("at least three points are required for a fit")
    rows = [
        (Fraction(1), Fraction(point["N"]), Fraction(point["N"] * point["D"]))
        for point in points
    ]
    measurements = [as_fraction(point["cycles_median"]) for point in points]
    normal = [
        [sum(row[i] * row[j] for row in rows) for j in range(3)]
        for i in range(3)
    ]
    rhs = [
        sum(
            row[i] * value
            for row, value in zip(rows, measurements, strict=True)
        )
        for i in range(3)
    ]
    c0, cs, cv = solve_linear_system(normal, rhs)
    mean = sum(measurements) / len(measurements)
    residuals = []
    sse = Fraction(0)
    sst = Fraction(0)
    for point, row, measured in zip(points, rows, measurements, strict=True):
        fitted = c0 * row[0] + cs * row[1] + cv * row[2]
        residual = measured - fitted
        sse += residual * residual
        centered = measured - mean
        sst += centered * centered
        residuals.append({
            **point,
            "fitted_cycles": fraction_json(fitted),
            "Cstall_cycles": fraction_json(residual),
        })
    if not sst:
        raise AnalysisError("R-squared is undefined for constant measurements")
    r_squared = Fraction(1) - sse / sst
    return {
        "formula": MODEL_FORMULA,
        "fit_point_count": len(points),
        "parameters_cycles": {
            "C0": fraction_json(c0),
            "Cs": fraction_json(cs),
            "Cv": fraction_json(cv),
        },
        "sum_squared_residuals": fraction_json(sse),
        "total_sum_squares": fraction_json(sst),
        "R_squared": fraction_json(r_squared),
        "residuals": residuals,
    }


def validate_result_root(root: Path) -> None:
    if not root.is_dir():
        raise AnalysisError(f"result root is not a directory: {root}")
    missing = [
        name
        for name in ("run_manifest.json", "records.json", "failures.json")
        if not (root / name).is_file()
    ]
    if missing:
        raise AnalysisError(f"result root {root} is missing {missing}")


def load_evidence(result_roots: Sequence[Path]) -> dict[str, Any]:
    if not result_roots:
        raise AnalysisError("at least one result root is required")
    roots = []
    records = []
    failures = []
    seen_roots = set()
    for raw_root in result_roots:
        root = raw_root.resolve()
        if root in seen_roots:
            raise AnalysisError(f"duplicate result root: {root}")
        seen_roots.add(root)
        validate_result_root(root)
        manifest_path = root / "run_manifest.json"
        records_path = root / "records.json"
        failures_path = root / "failures.json"
        manifest = json.loads(manifest_path.read_text())
        root_records = json.loads(records_path.read_text())
        root_failures = json.loads(failures_path.read_text())
        if (
            not isinstance(root_records, list)
            or not isinstance(root_failures, list)
        ):
            raise AnalysisError(f"records/failures must be lists in {root}")
        root_entry = {
            "root": str(root),
            "git_commit": manifest.get("git_commit"),
            "git_dirty": manifest.get("git_dirty"),
            "cfg_path": manifest.get("cfg_path"),
            "cfg_hash": manifest.get("cfg_hash"),
            "simulator_sha256": manifest.get("tool_versions", {})
            .get("simulator", {})
            .get("sha256"),
            "tool_versions": manifest.get("tool_versions"),
            "wall_clock_start_end": manifest.get("wall_clock_start_end"),
            "validation_result": manifest.get("validation_result"),
            "files": {
                "run_manifest.json": sha256_file(manifest_path),
                "records.json": sha256_file(records_path),
                "failures.json": sha256_file(failures_path),
            },
        }
        roots.append(root_entry)
        for record in root_records:
            if not isinstance(record, dict):
                raise AnalysisError(f"non-object record in {records_path}")
            records.append({"source_root": str(root), **record})
        for failure in root_failures:
            failures.append({"source_root": str(root), "failure": failure})
    return {"roots": roots, "records": records, "failures": failures}


def equivalent_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in PROVENANCE_ONLY_RECORD_FIELDS
    }


def prepare_points(evidence: dict[str, Any]) -> dict[str, Any]:
    status_counts = Counter(
        str(record.get("status")) for record in evidence["records"]
    )
    nonpass_records = []
    candidates: dict[
        tuple[int, int, str, int], list[dict[str, Any]]
    ] = defaultdict(list)
    for record in evidence["records"]:
        if record.get("status") != "pass":
            nonpass_records.append({
                "source_root": record["source_root"],
                "implementation": record.get("implementation"),
                "N": record.get("N"),
                "D": record.get("D"),
                "repeat": record.get("repeat"),
                "status": record.get("status"),
                "target_status": record.get("target_status"),
                "command_status": record.get("command_status"),
                "cycles": record.get("cycles"),
            })
            continue
        if record.get("implementation") not in MODEL_IMPLEMENTATIONS:
            continue
        if record.get("seed") != 1 or record.get("case_kind") != "main":
            continue
        if (
            record.get("command_status") != "pass"
            or record.get("command_returncode") != 0
            or record.get("nonfinite") != 0
        ):
            raise AnalysisError(
                "passing model record has invalid command/nonfinite fields: "
                f"{record['source_root']} {record.get('N')},{record.get('D')}"
            )
        cycles = record.get("cycles")
        if (
            isinstance(cycles, bool)
            or not isinstance(cycles, (int, float))
            or not math.isfinite(cycles)
            or cycles <= 0
        ):
            raise AnalysisError(
                f"invalid cycle count in {record['source_root']}"
            )
        key = (
            int(record["N"]),
            int(record["D"]),
            str(record["implementation"]),
            int(record["repeat"]),
        )
        candidates[key].append(record)

    unique_records = []
    equivalent_duplicates = []
    for key in sorted(candidates):
        group = candidates[key]
        canonical = group[0]
        if any(
            equivalent_record(item) != equivalent_record(canonical)
            for item in group[1:]
        ):
            raise AnalysisError(f"conflicting passing records for key {key}")
        unique_records.append(canonical)
        if len(group) > 1:
            equivalent_duplicates.append({
                "key": list(key),
                "source_roots": sorted(item["source_root"] for item in group),
                "record_count": len(group),
            })

    grouped: dict[
        tuple[int, int, str], list[dict[str, Any]]
    ] = defaultdict(list)
    for record in unique_records:
        key = (record["N"], record["D"], record["implementation"])
        grouped[key].append(record)
    points = []
    for key in sorted(grouped):
        rows = sorted(grouped[key], key=lambda item: item["repeat"])
        repeats = [row["repeat"] for row in rows]
        if len(rows) < 3 or repeats != list(range(len(rows))):
            raise AnalysisError(
                f"point {key} needs at least three contiguous repeats, "
                f"got {repeats}"
            )
        cycles_median = median_fraction(row["cycles"] for row in rows)
        element_count = Fraction(key[0] * key[1])
        points.append({
            "N": key[0],
            "D": key[1],
            "implementation": key[2],
            "measured_repeats": len(rows),
            "cycles_min": min(row["cycles"] for row in rows),
            "cycles_median": cycles_median,
            "cycles_max": max(row["cycles"] for row in rows),
            "cycles_per_element": cycles_median / element_count,
            "elements_per_cycle": element_count / cycles_median,
            "tcdm_accessed_median": median_fraction(
                row["tcdm_accessed"] for row in rows
            ),
            "tcdm_congested_median": median_fraction(
                row["tcdm_congested"] for row in rows
            ),
            "congestion_ratio_median": median_fraction(
                row["congestion_ratio"] for row in rows
            ),
            "footprint_bytes": rows[0]["footprint_bytes"],
            "allocation_bytes": rows[0]["allocation_bytes"],
            "tcdm_capacity_bytes": rows[0]["tcdm_capacity_bytes"],
            "source_roots": sorted({row["source_root"] for row in rows}),
        })
    rvv_cycles = {
        (point["N"], point["D"]): point["cycles_median"]
        for point in points
        if point["implementation"] == "B2-R"
    }
    for point in points:
        baseline = rvv_cycles.get((point["N"], point["D"]))
        point["speedup_vs_B2_R"] = (
            None if baseline is None else baseline / point["cycles_median"]
        )
    return {
        "status_counts": dict(sorted(status_counts.items())),
        "nonpass_records": sorted(
            nonpass_records,
            key=lambda item: (
                item["source_root"],
                item["N"] if item["N"] is not None else -1,
                item["D"] if item["D"] is not None else -1,
                str(item["implementation"]),
                item["repeat"] if item["repeat"] is not None else -1,
            ),
        ),
        "equivalent_duplicate_pass_records": equivalent_duplicates,
        "points": points,
    }


def point_for(
    point_index: dict[tuple[int, int, str], dict[str, Any]],
    n: int,
    d: int,
    implementation: str,
) -> dict[str, Any] | None:
    return point_index.get((n, d, implementation))


def break_even_table(
    points: Sequence[dict[str, Any]],
    n_values: Sequence[int],
    d_values: Sequence[int],
) -> dict[str, Any]:
    point_index = {
        (point["N"], point["D"], point["implementation"]): point
        for point in points
    }
    rows = []
    per_n = []
    missing = []
    for n in n_values:
        satisfying = []
        for d in d_values:
            rvv = point_for(point_index, n, d, "B2-R")
            smu = point_for(point_index, n, d, "B3")
            if rvv is None or smu is None:
                missing.append({"N": n, "D": d})
                rows.append({
                    "N": n,
                    "D": d,
                    "measurement_status": "missing",
                    "B2_R_cycles_median": None,
                    "B3_cycles_median": None,
                    "B3_le_B2_R": None,
                    "speedup_B3_vs_B2_R": None,
                })
                continue
            rvv_cycles = as_fraction(rvv["cycles_median"])
            smu_cycles = as_fraction(smu["cycles_median"])
            satisfies = smu_cycles <= rvv_cycles
            if satisfies:
                satisfying.append(d)
            rows.append({
                "N": n,
                "D": d,
                "measurement_status": "measured",
                "B2_R_cycles_median": fraction_json(rvv_cycles),
                "B3_cycles_median": fraction_json(smu_cycles),
                "B3_le_B2_R": satisfies,
                "speedup_B3_vs_B2_R": fraction_json(rvv_cycles / smu_cycles),
            })
        per_n.append({
            "N": n,
            "status": "measured" if not any(item["N"] == n for item in missing)
            else "incomplete_measurement",
            "minimum_measured_D": min(satisfying) if satisfying else None,
            "satisfying_measured_D": satisfying,
        })
    return {
        "definition": "C_smu(N,D) <= C_rvv(N,D)",
        "N_values": list(n_values),
        "D_values": list(d_values),
        "complete": not missing,
        "missing_points": missing,
        "rows": rows,
        "per_N": per_n,
        "model_predictions_mixed_with_measurements": False,
    }


def git_context(repo_root: Path) -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if commit.returncode or status.returncode:
        raise AnalysisError("failed to read Git provenance")
    return {
        "commit": commit.stdout.strip(),
        "dirty": bool(status.stdout.strip()),
        "status": status.stdout.splitlines(),
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, Fraction):
        return fraction_json(value)
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [json_ready(item) for item in value]
    return value


def write_outputs(
    output_dir: Path,
    report: dict[str, Any],
) -> dict[str, str]:
    output_dir.mkdir(parents=False, exist_ok=False)
    analysis_path = output_dir / "analysis.json"
    residuals_path = output_dir / "model_residuals.csv"
    break_even_path = output_dir / "break_even.csv"
    analysis_path.write_text(
        json.dumps(
            json_ready(report), indent=2, sort_keys=True, allow_nan=False
        )
        + "\n"
    )
    with residuals_path.open("w", newline="") as stream:
        fields = [
            "implementation", "N", "D", "measured_repeats",
            "cycles_min", "cycles_median", "cycles_max",
            "cycles_per_element", "elements_per_cycle",
            "speedup_vs_B2_R", "fitted_cycles", "Cstall_cycles",
            "tcdm_accessed_median",
            "tcdm_congested_median", "congestion_ratio_median",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for implementation in MODEL_IMPLEMENTATIONS:
            for row in report["models"][implementation]["residuals"]:
                writer.writerow({
                    "implementation": implementation,
                    "N": row["N"],
                    "D": row["D"],
                    "measured_repeats": row["measured_repeats"],
                    "cycles_min": row["cycles_min"],
                    "cycles_median": float(as_fraction(row["cycles_median"])),
                    "cycles_max": row["cycles_max"],
                    "cycles_per_element": float(
                        as_fraction(row["cycles_per_element"])
                    ),
                    "elements_per_cycle": float(
                        as_fraction(row["elements_per_cycle"])
                    ),
                    "speedup_vs_B2_R": (
                        "" if row["speedup_vs_B2_R"] is None
                        else float(as_fraction(row["speedup_vs_B2_R"]))
                    ),
                    "fitted_cycles": row["fitted_cycles"]["decimal"],
                    "Cstall_cycles": row["Cstall_cycles"]["decimal"],
                    "tcdm_accessed_median": float(
                        as_fraction(row["tcdm_accessed_median"])
                    ),
                    "tcdm_congested_median": float(
                        as_fraction(row["tcdm_congested_median"])
                    ),
                    "congestion_ratio_median": float(
                        as_fraction(row["congestion_ratio_median"])
                    ),
                })
    with break_even_path.open("w", newline="") as stream:
        fields = [
            "N", "D", "measurement_status", "B2_R_cycles_median",
            "B3_cycles_median", "B3_le_B2_R", "speedup_B3_vs_B2_R",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in report["break_even"]["rows"]:
            writer.writerow({
                "N": row["N"],
                "D": row["D"],
                "measurement_status": row["measurement_status"],
                "B2_R_cycles_median": (
                    "" if row["B2_R_cycles_median"] is None
                    else row["B2_R_cycles_median"]["decimal"]
                ),
                "B3_cycles_median": (
                    "" if row["B3_cycles_median"] is None
                    else row["B3_cycles_median"]["decimal"]
                ),
                "B3_le_B2_R": row["B3_le_B2_R"],
                "speedup_B3_vs_B2_R": (
                    "" if row["speedup_B3_vs_B2_R"] is None
                    else row["speedup_B3_vs_B2_R"]["decimal"]
                ),
            })
    outputs = {
        path.name: sha256_file(path)
        for path in (analysis_path, residuals_path, break_even_path)
    }
    manifest_path = output_dir / "artifact_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "analysis_git_commit": (
                    report["analysis_provenance"]["git"]["commit"]
                ),
                "analysis_git_dirty": (
                    report["analysis_provenance"]["git"]["dirty"]
                ),
                "analysis_tool": {
                    "path": report["analysis_provenance"]["tool_path"],
                    "sha256": report["analysis_provenance"]["tool_sha256"],
                    "python": report["analysis_provenance"]["python"],
                },
                "input_roots": report["input_evidence"]["roots"],
                "outputs": outputs,
            },
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )
    outputs[manifest_path.name] = sha256_file(manifest_path)
    return outputs


def analyze(
    repo_root: Path,
    result_roots: Sequence[Path],
    n_values: Sequence[int],
    d_values: Sequence[int],
    tool_path: Path,
) -> dict[str, Any]:
    evidence = load_evidence(result_roots)
    prepared = prepare_points(evidence)
    provenance = git_context(repo_root.resolve())
    models = {}
    for implementation in MODEL_IMPLEMENTATIONS:
        points = [
            point
            for point in prepared["points"]
            if point["implementation"] == implementation
        ]
        models[implementation] = fit_model(points)
    break_even = break_even_table(
        prepared["points"], n_values=n_values, d_values=d_values
    )
    return {
        "schema_version": 1,
        "objective": (
            "fit B2-R and B3 cycle models and report direct measured "
            "break-even points"
        ),
        "model_scope": (
            "all unique passing seed-1 main points supplied by the input "
            "result roots; each point uses the median retained cycle count"
        ),
        "analysis_provenance": {
            "git": provenance,
            "tool_path": str(tool_path.resolve()),
            "tool_sha256": sha256_file(tool_path.resolve()),
            "python": {
                "executable": sys.executable,
                "version": sys.version.split()[0],
            },
        },
        "input_evidence": {
            "roots": evidence["roots"],
            "record_status_counts": prepared["status_counts"],
            "nonpass_records": prepared["nonpass_records"],
            "failure_entries": evidence["failures"],
            "equivalent_duplicate_pass_records": (
                prepared["equivalent_duplicate_pass_records"]
            ),
        },
        "acceptance": {
            "break_even_grid_complete": break_even["complete"],
            "models_have_matching_coordinates": (
                {
                    (point["N"], point["D"])
                    for point in prepared["points"]
                    if point["implementation"] == "B2-R"
                }
                == {
                    (point["N"], point["D"])
                    for point in prepared["points"]
                    if point["implementation"] == "B3"
                }
            ),
            "analysis_git_clean": not provenance["dirty"],
            "input_roots_git_clean": all(
                root["git_dirty"] is False for root in evidence["roots"]
            ),
            "input_cfg_identity_complete_and_consistent": (
                len({root["cfg_hash"] for root in evidence["roots"]}) == 1
                and evidence["roots"][0]["cfg_hash"] is not None
            ),
            "input_simulator_identity_complete_and_consistent": (
                len({
                    root["simulator_sha256"] for root in evidence["roots"]
                }) == 1
                and evidence["roots"][0]["simulator_sha256"] is not None
            ),
            "input_measurement_windows_recorded": all(
                root["wall_clock_start_end"] is not None
                for root in evidence["roots"]
            ),
            "input_validation_results_recorded": all(
                root["validation_result"] is not None
                for root in evidence["roots"]
            ),
        },
        "models": models,
        "break_even": break_even,
    }


def validate_output_dir(output_dir: Path, repo_root: Path) -> Path:
    output = output_dir.resolve()
    repo = repo_root.resolve()
    try:
        output.relative_to(repo)
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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--result-root", type=Path, action="append", required=True,
        help="repeat for every preserved experiment result root",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--break-even-n", type=parse_positive_ints, default=(1, 2, 4, 8)
    )
    parser.add_argument(
        "--break-even-d", type=parse_positive_ints, default=(1, 8, 16, 32)
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    tool_path = Path(__file__)
    output = validate_output_dir(args.output_dir, args.repo_root)
    report = analyze(
        repo_root=args.repo_root,
        result_roots=args.result_root,
        n_values=args.break_even_n,
        d_values=args.break_even_d,
        tool_path=tool_path,
    )
    if not all(report["acceptance"].values()):
        raise AnalysisError(
            f"analysis acceptance failed: {report['acceptance']}"
        )
    outputs = write_outputs(output, report)
    print(json.dumps({
        "output_dir": str(output),
        "outputs": outputs,
        "acceptance": report["acceptance"],
        "break_even_per_N": report["break_even"]["per_N"],
        "models": {
            implementation: {
                "fit_point_count": (
                    report["models"][implementation]["fit_point_count"]
                ),
                "parameters_cycles": (
                    report["models"][implementation]["parameters_cycles"]
                ),
                "R_squared": report["models"][implementation]["R_squared"],
            }
            for implementation in MODEL_IMPLEMENTATIONS
        },
    }, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
