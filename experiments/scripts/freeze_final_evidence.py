#!/usr/bin/env python3
"""Freeze the small set of machine-readable final evidence records.

The script intentionally consumes only the Sol-reviewed M2 tables, the formal
P0-6 standalone area summary, the P7-R synchronous timing audit, and the P3
FSM breakdown.  It emits deterministic CSV/JSON records; no wall-clock time,
random value, or legacy P0-5/P7/P9-P11 result is read.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from decimal import Decimal
from typing import Any


HEAD = "7225d41ad2d1c63376a9fb1ea4e56b3b24a3e97f"
CONFIGS = ("B2R_RVV", "A1_SMU_SCALAR", "A2_SMU_FULL")
WORKLOAD_ORDER = ("BERT", "Mistral", "Qwen14B")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def source_record(repo_root: Path, relative: str) -> dict[str, str]:
    path = repo_root / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": relative, "sha256": sha256_file(path)}


def load_inputs(repo_root: Path) -> dict[str, Any]:
    m2_scaling_path = repo_root / "experiments/parsed/m2/m2_scaling.csv"
    m2_workloads_path = repo_root / "experiments/parsed/m2/m2_workloads.csv"
    p06_path = repo_root / "experiments/parsed/p0_6/p0_6_synthesis_summary.csv"
    p7r_summary_path = repo_root / "experiments/parsed/p7r_timing/p7r_path_summary.csv"
    p7r_details_path = repo_root / "experiments/parsed/p7r_timing/p7r_path_details.json"
    p3_path = repo_root / "experiments/parsed/p3_smu_latency_breakdown.csv"

    scaling = read_csv(m2_scaling_path)
    points = [
        row for row in scaling
        if row.get("kind") == "point" and row.get("config") in CONFIGS
    ]
    if len(points) != 69:
        raise ValueError(f"expected 69 M2 scaling points, found {len(points)}")
    if any(row.get("source_audit") for row in points):
        raise ValueError("unexpected non-M2 point schema")

    workloads = read_csv(m2_workloads_path)
    if [row["case_id"] for row in workloads] != [
        "model_bert_base_heads",
        "model_mistral_7b_heads",
        "model_qwen2_5_14b_heads",
    ]:
        raise ValueError("M2 workload order or membership changed")
    if any(row.get("disposition") != "MEASURED" or row.get("paper_eligible") != "YES"
           for row in workloads):
        raise ValueError("M2 workload eligibility gate failed")

    p06 = {row["config_id"]: row for row in read_csv(p06_path)}
    for config in ("C1_SCALAR", "C2_FULL"):
        if p06[config].get("paper_eligible") != "YES":
            raise ValueError(f"P0-6 area row is not paper eligible: {config}")

    p7r_summary = {
        (row["design"], row["category"]): row
        for row in read_csv(p7r_summary_path)
    }
    p7r_details = json.loads(p7r_details_path.read_text(encoding="utf-8"))
    if p7r_details.get("audit", {}).get("synchronous_fmax_policy") != "withdrawn":
        raise ValueError("P7-R synchronous-Fmax withdrawal policy is not active")
    for design in ("A1", "A2"):
        row = p7r_summary[(design, "reg→reg")]
        if row["status"] != "verified" or not row["longest_delay_ps"]:
            raise ValueError(f"missing P7-R reg→reg row: {design}")
    if not p3_path.is_file():
        raise FileNotFoundError(p3_path)

    return {
        "scaling": scaling,
        "points": points,
        "workloads": workloads,
        "p06": p06,
        "p7r_summary": p7r_summary,
        "p7r_details": p7r_details,
        "inputs": [
            source_record(repo_root, "experiments/parsed/m2/m2_scaling.csv"),
            source_record(repo_root, "experiments/parsed/m2/m2_workloads.csv"),
            source_record(repo_root, "experiments/parsed/p0_6/p0_6_synthesis_summary.csv"),
            source_record(repo_root, "experiments/parsed/p7r_timing/p7r_path_summary.csv"),
            source_record(repo_root, "experiments/parsed/p7r_timing/p7r_path_details.json"),
            source_record(repo_root, "experiments/parsed/p3_smu_latency_breakdown.csv"),
        ],
    }


def build_workload_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    speedups_a1 = []
    speedups_a2 = []
    for workload in data["workloads"]:
        name = {
            "model_bert_base_heads": "BERT",
            "model_mistral_7b_heads": "Mistral",
            "model_qwen2_5_14b_heads": "Qwen14B",
        }[workload["case_id"]]
        b2r = int(workload["B2R_RVV_cycles"])
        a1 = int(workload["A1_SMU_SCALAR_cycles"])
        a2 = int(workload["A2_SMU_FULL_cycles"])
        a1_speedup = b2r / a1
        a2_speedup = b2r / a2
        speedups_a1.append(a1_speedup)
        speedups_a2.append(a2_speedup)
        rows.append({
            "workload": name,
            "model_id": workload["model_id"],
            "N": workload["N"],
            "D": workload["D"],
            "B2R_RVV_cycles": b2r,
            "A1_SMU_SCALAR_cycles": a1,
            "A2_SMU_FULL_cycles": a2,
            "A1_speedup_over_B2R": f"{a1_speedup:.12f}",
            "A2_speedup_over_B2R": f"{a2_speedup:.12f}",
            "status": "VERIFIED_M2_MEASURED_CYCLES",
            "speedup_basis": "B2R cycles / design cycles; no frequency assumption",
        })
    rows.append({
        "workload": "geomean",
        "model_id": "",
        "N": "",
        "D": "",
        "B2R_RVV_cycles": "",
        "A1_SMU_SCALAR_cycles": "",
        "A2_SMU_FULL_cycles": "",
        "A1_speedup_over_B2R": f"{math.prod(speedups_a1) ** (1 / len(speedups_a1)):.12f}",
        "A2_speedup_over_B2R": f"{math.prod(speedups_a2) ** (1 / len(speedups_a2)):.12f}",
        "status": "DERIVED_FROM_M2_MEASURED_CYCLES",
        "speedup_basis": "geometric mean of the three workload cycle ratios",
    })
    return rows


def build_area_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    a1 = data["p06"]["C1_SCALAR"]
    a2 = data["p06"]["C2_FULL"]
    area_a1 = Decimal(a1["mapped_cell_area"])
    area_a2 = Decimal(a2["mapped_cell_area"])
    return [
        {
            "design": "A1",
            "role": "Proposed Scalar SMU + RVV",
            "mapped_cells": int(a1["mapped_cell_count"]),
            "liberty_area": f"{area_a1:.3f}",
            "area_units": "Nangate45 Liberty cell-area units",
            "relative_to_A1": "1.000000000000",
            "delta_vs_A1": "0.000",
            "delta_percent_vs_A1": "0.000000",
            "status": "VERIFIED_P0_6_STANDALONE",
        },
        {
            "design": "A2",
            "role": "Full-Offload ablation",
            "mapped_cells": int(a2["mapped_cell_count"]),
            "liberty_area": f"{area_a2:.3f}",
            "area_units": "Nangate45 Liberty cell-area units",
            "relative_to_A1": f"{area_a2 / area_a1:.12f}",
            "delta_vs_A1": f"{area_a2 - area_a1:.3f}",
            "delta_percent_vs_A1": f"{(area_a2 / area_a1 - 1) * 100:.6f}",
            "status": "VERIFIED_P0_6_STANDALONE",
        },
    ]


def build_timing_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    details = {row["id"]: row for row in data["p7r_details"]["designs"]}
    rows = []
    for design, role in (("A1", "Proposed Scalar SMU + RVV"),
                         ("A2", "Full-Offload ablation")):
        summary = data["p7r_summary"][(design, "reg→reg")]
        detail = details[design]
        delay_ps = float(summary["longest_delay_ps"])
        rows.append({
            "design": design,
            "role": role,
            "category": "reg→reg",
            "delay_ps": f"{delay_ps:.2f}",
            "delay_ns": f"{delay_ps / 1000:.5f}",
            "synchronous_fmax_mhz": "UNAVAILABLE",
            "status": "PARTIAL",
            "methodology": "pre-layout Nangate45/ABC stime reg→reg combinational-delay proxy; Outcome B",
            "startpoint": detail["ownership"]["start_q_signal_ownership"][0],
            "endpoint": next(
                name for name in detail["ownership"]["end_q_signal_ownership"]
                if "l_new_q" in name
            ),
        })
    return rows


def build_hardware_rows(area_rows: list[dict[str, Any]], timing_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    areas = {row["design"]: row for row in area_rows}
    timing = {row["design"]: row for row in timing_rows}
    return [
        {
            "design": design,
            "role": areas[design]["role"],
            "mapped_cells": areas[design]["mapped_cells"],
            "liberty_area": areas[design]["liberty_area"],
            "relative_area_to_A1": areas[design]["relative_to_A1"],
            "reg→reg_delay_proxy_ps": timing[design]["delay_ps"],
            "reg→reg_delay_proxy_ns": timing[design]["delay_ns"],
            "timing_status": "PARTIAL_ONLY",
        }
        for design in ("A1", "A2")
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze deterministic final evidence from M2/P0-6/P7-R/P3 inputs."
    )
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[2])
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    data = load_inputs(repo_root)
    out_dir = repo_root / "experiments/parsed"

    workload_fields = [
        "workload", "model_id", "N", "D", "B2R_RVV_cycles",
        "A1_SMU_SCALAR_cycles", "A2_SMU_FULL_cycles", "A1_speedup_over_B2R",
        "A2_speedup_over_B2R", "status", "speedup_basis",
    ]
    area_fields = [
        "design", "role", "mapped_cells", "liberty_area", "area_units",
        "relative_to_A1", "delta_vs_A1", "delta_percent_vs_A1", "status",
    ]
    timing_fields = [
        "design", "role", "category", "delay_ps", "delay_ns",
        "synchronous_fmax_mhz", "status", "methodology", "startpoint", "endpoint",
    ]
    hardware_fields = [
        "design", "role", "mapped_cells", "liberty_area", "relative_area_to_A1",
        "reg→reg_delay_proxy_ps", "reg→reg_delay_proxy_ns", "timing_status",
    ]
    outputs = {
        "experiments/parsed/final_workload_comparison.csv": (
            workload_fields, build_workload_rows(data)
        ),
        "experiments/parsed/final_area.csv": (area_fields, build_area_rows(data)),
        "experiments/parsed/final_timing.csv": (timing_fields, build_timing_rows(data)),
    }
    outputs["experiments/parsed/final_hardware_results.csv"] = (
        hardware_fields,
        build_hardware_rows(outputs["experiments/parsed/final_area.csv"][1],
                            outputs["experiments/parsed/final_timing.csv"][1]),
    )
    for relative, (fields, rows) in outputs.items():
        write_csv(repo_root / relative, fields, rows)

    active_csv = [
        "experiments/parsed/final_scaling_model.csv",
        *outputs.keys(),
    ]
    active_outputs = [
        {"path": relative, "sha256": sha256_file(repo_root / relative)}
        for relative in active_csv
    ]
    manifest = {
        "schema_version": "m3-final-evidence-freeze-v1",
        "analysis_head": HEAD,
        "expected_head": HEAD,
        "generation": {
            "deterministic": True,
            "timestamp": None,
            "workflow": [
                "python3 experiments/scripts/fit_final_scaling_model.py",
                "python3 experiments/scripts/freeze_final_evidence.py",
            ],
            "scripts": [
                source_record(repo_root, "experiments/scripts/fit_final_scaling_model.py"),
                source_record(repo_root, "experiments/scripts/freeze_final_evidence.py"),
            ],
        },
        "inputs": data["inputs"],
        "active_outputs": active_outputs,
        "manifest_self_hash": "excluded_to_avoid_self-referential_hash",
        "evidence_status": {
            "M2_matched_LUT": "VERIFIED_SOL_REVIEWED",
            "P0_6_standalone_area": "VERIFIED",
            "P3_scalar_SMU_breakdown": "VERIFIED",
            "P7R_timing": "PARTIAL_REG_TO_REG_PROXY_ONLY",
            "synchronous_Fmax": "UNAVAILABLE",
            "cluster_area_timing_power_energy": "UNAVAILABLE",
            "end_to_end_inference": "UNAVAILABLE",
        },
        "source_policy": {
            "proposed": "A1 Scalar SMU + existing RVV",
            "full": "A2 Full-Offload ablation only",
            "active_numbers_must_come_from": active_csv,
            "superseded_numbers_must_not_be_used": [
                "81.0186/75.7427 MHz",
                "old progressive baseline values",
                "old P0-5 workload/scaling values",
                "absolute latency/throughput derived from withdrawn Fmax",
            ],
        },
    }
    manifest_path = repo_root / "experiments/parsed/final_evidence_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("wrote deterministic M3 final evidence CSVs and manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
