#!/usr/bin/env python3
"""Normalize a preserved P0 run and generate audit-ready CSV/reports."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import experiment_common as common

if str(common.REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(common.REPO_ROOT))

from util.online_softmax_merge import run_experiments as legacy


CONFIG_ORDER = (
    "B1_SCALAR",
    "B2R_RVV",
    "A1_SMU_SCALAR",
    "A2_SMU_FULL",
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    root = common.REPO_ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument(
        "--parsed-dir", type=Path, default=root / "experiments/parsed"
    )
    parser.add_argument(
        "--reports-dir", type=Path, default=root / "experiments/reports"
    )
    parser.add_argument(
        "--trace-audit",
        type=Path,
        action="append",
        default=[],
        help="dynamic trace audit JSON; repeat for multiple shapes/configs",
    )
    return parser.parse_args(argv)


def key(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record.get("config"),
        record.get("N"),
        record.get("D"),
        record.get("seed"),
        record.get("input_pattern"),
    )


def unique_or_none(records: list[dict[str, Any]], field: str) -> Any:
    values = {record.get(field) for record in records}
    values.discard(None)
    return next(iter(values)) if len(values) == 1 else None


def memory_groups(
    records: list[dict[str, Any]],
) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        if record.get("counter_profile") == "memory":
            groups.setdefault(key(record), []).append(record)
    return groups


def instruction_groups(
    records: list[dict[str, Any]],
) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        if record.get("counter_profile") == "instructions":
            groups.setdefault(key(record), []).append(record)
    return groups


def progressive_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    memory = memory_groups(records)
    instructions = instruction_groups(records)
    rows: list[dict[str, Any]] = []
    for group_key, group in memory.items():
        config, n, d, seed, pattern = group_key
        cycles = unique_or_none(group, "kernel_cycles")
        status = unique_or_none(group, "status")
        paper = unique_or_none(group, "paper_eligible")
        aux = instructions.get(group_key, [])
        row = {
            "config": config,
            "config_alias": unique_or_none(group, "config_alias"),
            "N": n,
            "D": d,
            "seed": seed,
            "input_pattern": pattern,
            "size_class": unique_or_none(group, "size_class"),
            "trials": len(group),
            "kernel_cycles": cycles,
            "status": status,
            "reproducible": unique_or_none(group, "reproducible"),
            "retired_instructions": unique_or_none(
                aux, "retired_instructions"
            ),
            "retired_accelerator_instructions": unique_or_none(
                aux, "retired_accelerator_instructions"
            ),
            "dynamic_vector_instructions": unique_or_none(
                group, "dynamic_vector_instructions"
            ),
            "scalar_instructions": unique_or_none(
                group, "scalar_instructions"
            ),
            "vector_instructions": unique_or_none(
                group, "vector_instructions"
            ),
            "smu_commands": unique_or_none(group, "smu_commands"),
            "tcdm_accessed": unique_or_none(group, "tcdm_accessed"),
            "tcdm_congested": unique_or_none(group, "tcdm_congested"),
            "memory_footprint_bytes": unique_or_none(
                group, "memory_footprint_bytes"
            ),
            "end_to_end_cycles": unique_or_none(
                group, "end_to_end_cycles"
            ),
            "smu_busy_cycles": unique_or_none(group, "smu_busy_cycles"),
            "smu_scalar_cycles": unique_or_none(group, "smu_scalar_cycles"),
            "rvv_vector_cycles": unique_or_none(group, "rvv_vector_cycles"),
            "command_and_sync_cycles": unique_or_none(
                group, "command_and_sync_cycles"
            ),
            "load_scalar_cycles": unique_or_none(
                group, "load_scalar_cycles"
            ),
            "compute_scalar_cycles": unique_or_none(
                group, "compute_scalar_cycles"
            ),
            "compute_weight_cycles": unique_or_none(
                group, "compute_weight_cycles"
            ),
            "store_scalar_cycles": unique_or_none(
                group, "store_scalar_cycles"
            ),
            "update_vector_cycles": unique_or_none(
                group, "update_vector_cycles"
            ),
            "trace_software_scalar_cycles": unique_or_none(
                group, "trace_software_scalar_cycles"
            ),
            "trace_rvv_cycles": unique_or_none(
                group, "trace_rvv_cycles"
            ),
            "trace_load_store_cycles": unique_or_none(
                group, "trace_load_store_cycles"
            ),
            "trace_loop_control_cycles": unique_or_none(
                group, "trace_loop_control_cycles"
            ),
            "trace_synchronization_cycles": unique_or_none(
                group, "trace_synchronization_cycles"
            ),
            "trace_other_cycles": unique_or_none(
                group, "trace_other_cycles"
            ),
            "trace_undecoded_cycles": unique_or_none(
                group, "trace_undecoded_cycles"
            ),
            "max_abs_error": max(
                (
                    value
                    for value in (
                        item.get("max_abs_error") for item in group
                    )
                    if value is not None
                ),
                default=None,
            ),
            "max_rel_error": max(
                (
                    value
                    for value in (
                        item.get("max_rel_error") for item in group
                    )
                    if value is not None
                ),
                default=None,
            ),
            "mean_abs_error": max(
                (
                    value
                    for value in (
                        item.get("mean_abs_error") for item in group
                    )
                    if value is not None
                ),
                default=None,
            ),
            "l2_relative_error": max(
                (
                    value
                    for value in (
                        item.get("l2_relative_error") for item in group
                    )
                    if value is not None
                ),
                default=None,
            ),
            "paper_eligible": paper,
            "paper_ineligible_reasons": unique_or_none(
                group, "paper_ineligible_reasons"
            ),
        }
        row["smu_utilization"] = (
            row["smu_busy_cycles"] / cycles
            if cycles and row["smu_busy_cycles"] is not None
            else None
        )
        row["command_overhead_ratio"] = (
            row["command_and_sync_cycles"] / cycles
            if cycles and row["command_and_sync_cycles"] is not None
            else None
        )
        rows.append(row)

    coordinate_groups: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = {}
    for row in rows:
        coordinate = (
            row["N"],
            row["D"],
            row["seed"],
            row["input_pattern"],
        )
        coordinate_groups.setdefault(coordinate, {})[str(row["config"])] = row
    for configs in coordinate_groups.values():
        b1 = configs.get("B1_SCALAR", {}).get("kernel_cycles")
        b2 = configs.get("B2R_RVV", {}).get("kernel_cycles")
        for config, row in configs.items():
            cycles = row.get("kernel_cycles")
            row["speedup_vs_B1"] = (
                b1 / cycles if b1 and cycles else None
            )
            row["speedup_vs_B2R"] = (
                b2 / cycles if b2 and cycles else None
            )
    order = {name: index for index, name in enumerate(CONFIG_ORDER)}
    return sorted(
        rows,
        key=lambda row: (
            int(row["N"]),
            int(row["D"]),
            order.get(str(row["config"]), 99),
        ),
    )


def breakdown_rows(progressive: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in progressive:
        config = str(source["config"])
        kernel = source.get("kernel_cycles")
        row = {
            "config": config,
            "N": source["N"],
            "D": source["D"],
            "kernel_cycles": kernel,
            "software_scalar_cycles": None,
            "rvv_cycles": None,
            "smu_scalar_compute_cycles": None,
            "smu_vector_compute_cycles": None,
            "memory_fsm_cycles": None,
            "command_and_sync_cycles": source.get(
                "command_and_sync_cycles"
            ),
            "loop_control_cycles": None,
            "other_cycles": None,
            "stall_or_other_cycles": None,
            "breakdown_complete": "NO",
            "breakdown_method": None,
        }
        if config in {"B1_SCALAR", "B2R_RVV"}:
            trace_values = {
                "software_scalar_cycles": source.get(
                    "trace_software_scalar_cycles"
                ),
                "rvv_cycles": source.get("trace_rvv_cycles"),
                "memory_fsm_cycles": source.get(
                    "trace_load_store_cycles"
                ),
                "command_and_sync_cycles": source.get(
                    "trace_synchronization_cycles"
                ),
                "loop_control_cycles": source.get(
                    "trace_loop_control_cycles"
                ),
                "other_cycles": source.get("trace_other_cycles"),
            }
            trace_total = sum(
                value for value in trace_values.values() if value is not None
            )
            if kernel is not None and trace_total > 0:
                scale = kernel / trace_total
                for field, value in trace_values.items():
                    row[field] = (value or 0) * scale
            row["breakdown_method"] = (
                "DASM_RETIRE_INTERVAL_SCALED_TO_KERNEL_WINDOW"
            )
        elif config == "A1_SMU_SCALAR":
            row["rvv_cycles"] = source.get("rvv_vector_cycles")
            load = source.get("load_scalar_cycles")
            store = source.get("store_scalar_cycles")
            compute = source.get("compute_scalar_cycles")
            weight = source.get("compute_weight_cycles")
            busy = source.get("smu_busy_cycles")
            scalar_path = source.get("smu_scalar_cycles")
            row["memory_fsm_cycles"] = (
                load + store if load is not None and store is not None else None
            )
            row["smu_scalar_compute_cycles"] = (
                compute + weight
                if compute is not None and weight is not None
                else None
            )
            row["command_and_sync_cycles"] = (
                scalar_path - busy
                if scalar_path is not None and busy is not None
                else None
            )
            row["breakdown_method"] = "FSM_AND_BOUNDARY_COUNTERS"
        elif config == "A2_SMU_FULL":
            load = source.get("load_scalar_cycles")
            store = source.get("store_scalar_cycles")
            compute = source.get("compute_scalar_cycles")
            weight = source.get("compute_weight_cycles")
            row["memory_fsm_cycles"] = (
                load + store if load is not None and store is not None else None
            )
            row["smu_scalar_compute_cycles"] = (
                compute + weight
                if compute is not None and weight is not None
                else None
            )
            row["smu_vector_compute_cycles"] = source.get(
                "update_vector_cycles"
            )
            row["breakdown_method"] = "FSM_AND_BOUNDARY_COUNTERS"
        known = [
            row[field]
            for field in (
                "software_scalar_cycles",
                "rvv_cycles",
                "smu_scalar_compute_cycles",
                "smu_vector_compute_cycles",
                "memory_fsm_cycles",
                "command_and_sync_cycles",
                "loop_control_cycles",
                "other_cycles",
            )
            if row[field] is not None
        ]
        if kernel is not None:
            residual = kernel - sum(known)
            nonnegative = residual >= -1.0e-6
            row["stall_or_other_cycles"] = (
                max(0.0, residual) if nonnegative else None
            )
            row["breakdown_complete"] = (
                "YES"
                if nonnegative
                and known
                and source.get("trace_undecoded_cycles") in (None, 0)
                else "NO"
            )
        rows.append(row)
    return rows


def instruction_mix_rows(
    raw_root: Path, records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for record in records:
        record_key = key(record)
        if record_key in seen:
            continue
        seen.add(record_key)
        config, n, d, seed, pattern = record_key
        matching = [item for item in records if key(item) == record_key]
        primary = [
            item
            for item in matching
            if item.get("counter_profile") == "memory"
        ]
        auxiliary = [
            item
            for item in matching
            if item.get("counter_profile") == "instructions"
        ]
        profile = (
            "instructions"
            if any(
                item.get("counter_profile") == "instructions"
                for item in matching
            )
            else "memory"
        )
        profile_dir = (
            raw_root
            / f"N{n}_D{d}_S{seed}_{str(pattern).replace('-', '_')}"
            / profile
            / str(config)
        )
        symbol = (
            "online_merge_rtl_reference"
            if config == "B1_SCALAR"
            else "online_merge_rvv_update"
        )
        snippet_path = profile_dir / f"{symbol}.disasm"
        text = (
            snippet_path.read_text(encoding="utf-8")
            if snippet_path.is_file()
            else ""
        )
        counts = Counter()
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.endswith(":"):
                continue
            pieces = stripped.split()
            if len(pieces) >= 2 and pieces[0].endswith(":"):
                counts[pieces[1]] += 1
        rows.append(
            {
                "config": config,
                "N": n,
                "D": d,
                "seed": seed,
                "input_pattern": pattern,
                "symbol": symbol,
                "static_instruction_count": sum(counts.values()),
                "static_vsetvli": counts["vsetvli"],
                "static_vector_loads": counts["vle32.v"],
                "static_vector_math": (
                    counts["vfmul.vf"] + counts["vfmacc.vf"]
                ),
                "static_vector_stores": counts["vse32.v"],
                "static_backedge": (
                    "YES" if text and legacy.has_local_backedge(text) else "NO"
                ),
                "retired_instructions": unique_or_none(
                    auxiliary, "retired_instructions"
                ),
                "retired_accelerator_instructions": unique_or_none(
                    auxiliary,
                    "retired_accelerator_instructions",
                ),
                "dynamic_rvv_trace_verified": unique_or_none(
                    primary or matching, "dynamic_trace_verified"
                ),
                "dynamic_retired_instructions": unique_or_none(
                    primary or matching, "dynamic_retired_instructions"
                ),
                "dynamic_vector_instructions": unique_or_none(
                    primary or matching, "dynamic_vector_instructions"
                ),
            }
        )
    return rows


def fmt(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def percent(value: Any, total: Any) -> str:
    if value is None or total in (None, 0):
        return "NA"
    return f"{100.0 * float(value) / float(total):.1f}%"


def apply_trace_audits(
    records: list[dict[str, Any]], audit_paths: list[Path]
) -> None:
    accepted: dict[tuple[str, int, int], dict[str, Any]] = {}
    for path in audit_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("dynamic_rvv_trace_verified") is not True:
            continue
        accepted[
            (
                str(payload["config"]),
                int(payload["N"]),
                int(payload["D"]),
            )
        ] = payload
    for record in records:
        audit_key = (
            str(record.get("config")),
            int(record.get("N", 0)),
            int(record.get("D", 0)),
        )
        payload = accepted.get(audit_key)
        if payload is None:
            continue
        record["dynamic_trace_verified"] = "YES"
        record["dynamic_retired_instructions"] = payload.get(
            "retired_instructions_in_envelope"
        )
        record["dynamic_vector_instructions"] = payload.get(
            "retired_rvv_instructions"
        )
        record["vector_instructions"] = record[
            "dynamic_vector_instructions"
        ]
        record["scalar_instructions"] = (
            record["dynamic_retired_instructions"]
            - record["dynamic_vector_instructions"]
            if record["dynamic_retired_instructions"] is not None
            and record["dynamic_vector_instructions"] is not None
            else None
        )
        record["instruction_mix_source"] = "DASM_MARKER_ENVELOPE"
        cycle_spans = payload.get("category_cycle_spans", {})
        for category_name in (
            "software_scalar",
            "rvv",
            "load_store",
            "loop_control",
            "synchronization",
            "other",
            "undecoded",
        ):
            record[f"trace_{category_name}_cycles"] = cycle_spans.get(
                category_name
            )
        reasons = [
            reason
            for reason in str(
                record.get("paper_ineligible_reasons") or ""
            ).split(";")
            if reason and reason != "DYNAMIC_RVV_TRACE_PENDING"
        ]
        record["paper_ineligible_reasons"] = (
            ";".join(reasons) if reasons else None
        )
        record["paper_eligible"] = "NO" if reasons else "YES"


def baseline_report(
    path: Path,
    progressive: list[dict[str, Any]],
    mix: list[dict[str, Any]],
    breakdown: list[dict[str, Any]],
) -> None:
    b1 = {(
        row["N"], row["D"]
    ): row for row in progressive if row["config"] == "B1_SCALAR"}
    b2 = {(
        row["N"], row["D"]
    ): row for row in progressive if row["config"] == "B2R_RVV"}
    lines = [
        "# Strong Software Baseline Audit",
        "",
        "## Evidence status",
        "",
        "Static disassembly and dynamic DASM evidence are retained; the "
        "auxiliary counter profile additionally records hardware retired "
        "events. A result is not promoted to paper-eligible B2-R evidence "
        "until the gated dynamic DASM audit records retired RVV "
        "instructions.",
        "",
        "## B1 versus B2-R",
        "",
        "| `(N,D)` | B1 cycles | B2-R cycles | B1/B2-R | Status |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for coordinate in sorted(set(b1) | set(b2)):
        b1_row = b1.get(coordinate, {})
        b2_row = b2.get(coordinate, {})
        b1_cycles = b1_row.get("kernel_cycles")
        b2_cycles = b2_row.get("kernel_cycles")
        speedup = (
            b1_cycles / b2_cycles if b1_cycles and b2_cycles else None
        )
        lines.append(
            f"| `{coordinate}` | {fmt(b1_cycles)} | {fmt(b2_cycles)} | "
            f"{fmt(speedup)} | {fmt(b2_row.get('status'))} |"
        )
    lines.extend(
        [
            "",
            "## Code-generation gates",
            "",
            "| Config | `(N,D)` | vsetvli | RVV loads | RVV math | "
            "RVV stores | Retired RVV | Dynamic trace |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in mix:
        if row["config"] not in {"B1_SCALAR", "B2R_RVV"}:
            continue
        lines.append(
            f"| {row['config']} | `({row['N']},{row['D']})` | "
            f"{row['static_vsetvli']} | {row['static_vector_loads']} | "
            f"{row['static_vector_math']} | "
            f"{row['static_vector_stores']} | "
            f"{fmt(row['dynamic_vector_instructions'])} | "
            f"{fmt(row['dynamic_rvv_trace_verified'])} |"
        )
    lines.extend(
        [
            "",
            "## Cycle attribution",
            "",
            "DASM retirement intervals are grouped by instruction category "
            "and proportionally scaled to the authoritative kernel-cycle "
            "window. These are attribution estimates, not independent "
            "per-block hardware counters.",
            "",
            "| Config | `(N,D)` | Scalar recurrence | RVV | Load/store | "
            "Loop/control | Synchronization | Other |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in breakdown:
        if row["config"] not in {"B1_SCALAR", "B2R_RVV"}:
            continue
        kernel = row.get("kernel_cycles")
        lines.append(
            f"| {row['config']} | `({row['N']},{row['D']})` | "
            f"{percent(row.get('software_scalar_cycles'), kernel)} | "
            f"{percent(row.get('rvv_cycles'), kernel)} | "
            f"{percent(row.get('memory_fsm_cycles'), kernel)} | "
            f"{percent(row.get('loop_control_cycles'), kernel)} | "
            f"{percent(row.get('command_and_sync_cycles'), kernel)} | "
            f"{percent(row.get('other_cycles'), kernel)} |"
        )
    lines.extend(["", "## Remaining B2-R bottleneck", ""])
    b2_breakdowns = [
        row for row in breakdown if row["config"] == "B2R_RVV"
    ]
    category_names = {
        "software_scalar_cycles": "scalar recurrence",
        "rvv_cycles": "RVV vector update",
        "memory_fsm_cycles": "load/store",
        "loop_control_cycles": "loop/control",
        "command_and_sync_cycles": "synchronization",
        "other_cycles": "other/unclassified software",
    }
    if not b2_breakdowns:
        lines.append("No B2-R cycle-attribution evidence is available.")
    for row in b2_breakdowns:
        available = {
            field: row.get(field)
            for field in category_names
            if row.get(field) is not None
        }
        if not available:
            lines.append(
                f"- `({row['N']},{row['D']})`: trace attribution is NA."
            )
            continue
        dominant = max(available, key=lambda field: float(available[field]))
        lines.append(
            f"- `({row['N']},{row['D']})`: the largest attributed "
            f"component is {category_names[dominant]} "
            f"({percent(available[dominant], row.get('kernel_cycles'))})."
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "- B1 must have zero RVV instructions in its measured scalar symbol.",
            "- B2-R must pass both static RVV and dynamic retired-RVV gates.",
            "- The current AVL cap of eight is a documented tail-correctness "
            "compatibility constraint, not a claimed optimum.",
            "- Missing dynamic trace evidence is reported as pending and never "
            "converted to a zero count.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def progressive_report(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Progressive Baseline Report",
        "",
        "`A0` is an alias of `B2R_RVV`; `B3` is the current raw label for "
        "`A2_SMU_FULL`.  Aliases are not duplicated below.",
        "",
        "| `(N,D)` | Config | Cycles | vs B1 | vs B2-R | Reproducible | "
        "Paper eligible |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `({row['N']},{row['D']})` | {row['config']} | "
            f"{fmt(row['kernel_cycles'])} | "
            f"{fmt(row.get('speedup_vs_B1'))} | "
            f"{fmt(row.get('speedup_vs_B2R'))} | "
            f"{fmt(row['reproducible'])} | "
            f"{fmt(row['paper_eligible'])} |"
        )
    lines.extend(
        [
            "",
            "## Per-stage contribution",
            "",
            "| `(N,D)` | B1 to B2-R | B2-R to A1 | A1 to A2 | "
            "B2-R to A2 | B1 to A2 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    by_coordinate: dict[
        tuple[Any, Any], dict[str, dict[str, Any]]
    ] = {}
    for row in rows:
        by_coordinate.setdefault((row["N"], row["D"]), {})[
            str(row["config"])
        ] = row
    transitions = (
        ("B1_SCALAR", "B2R_RVV"),
        ("B2R_RVV", "A1_SMU_SCALAR"),
        ("A1_SMU_SCALAR", "A2_SMU_FULL"),
        ("B2R_RVV", "A2_SMU_FULL"),
        ("B1_SCALAR", "A2_SMU_FULL"),
    )
    for coordinate, configs in sorted(by_coordinate.items()):
        values: list[Any] = []
        for source, target in transitions:
            source_cycles = configs.get(source, {}).get("kernel_cycles")
            target_cycles = configs.get(target, {}).get("kernel_cycles")
            values.append(
                source_cycles / target_cycles
                if source_cycles and target_cycles
                else None
            )
        lines.append(
            f"| `({coordinate[0]},{coordinate[1]})` | "
            + " | ".join(fmt(value) for value in values)
            + " |"
        )
    lines.extend(
        [
            "",
            "B1 to B2-R isolates the RVV software update; B2-R to A1 "
            "isolates scalar-recurrence offload; A1 to A2 isolates the "
            "SMU vector-update path. B2-R to A2 is the primary strong-"
            "baseline comparison.",
            "",
            "## Supporting counters",
            "",
            "| `(N,D)` | Config | Retired instructions | TCDM accesses | "
            "TCDM congestion | SMU utilization | Command/sync ratio |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            f"| `({row['N']},{row['D']})` | {row['config']} | "
            f"{fmt(row.get('retired_instructions'))} | "
            f"{fmt(row.get('tcdm_accessed'))} | "
            f"{fmt(row.get('tcdm_congested'))} | "
            f"{percent(row.get('smu_busy_cycles'), row.get('kernel_cycles'))} | "
            f"{percent(row.get('command_and_sync_cycles'), row.get('kernel_cycles'))} |"
        )
    lines.extend(
        [
            "",
            "## Measurement boundary",
            "",
            "Kernel cycles include software/RVV work, SMU MMIO command issue, "
            "busy polling, completion synchronization, and final output "
            "writeback. End-to-end cycles remain NA because this benchmark has "
            "no explicit DMA or transfer phase.",
            "",
            "Rows failing correctness, reproducibility, code-generation, FSM, "
            "or clean-provenance gates remain in the CSV with "
            "`paper_eligible=NO`.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    raw_root = args.raw_root.resolve()
    records_path = raw_root / "records.json"
    manifest_path = raw_root / "run_manifest.json"
    if not records_path.is_file() or not manifest_path.is_file():
        raise SystemExit("raw root lacks records.json or run_manifest.json")
    records = json.loads(records_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise SystemExit("records.json must contain an array")
    apply_trace_audits(
        records, [path.resolve() for path in args.trace_audit]
    )
    progressive = progressive_rows(records)
    breakdown = breakdown_rows(progressive)
    mix = instruction_mix_rows(raw_root, records)

    parsed_dir = args.parsed_dir.resolve()
    reports_dir = args.reports_dir.resolve()
    parsed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    common.write_csv(parsed_dir / "all_performance_results.csv", records)
    common.write_json(parsed_dir / "all_performance_results.json", records)
    common.write_csv(parsed_dir / "progressive_baseline.csv", progressive)
    common.write_csv(parsed_dir / "progressive_breakdown.csv", breakdown)
    common.write_csv(parsed_dir / "baseline_instruction_mix.csv", mix)
    baseline_report(
        reports_dir / "baseline_audit.md", progressive, mix, breakdown
    )
    progressive_report(
        reports_dir / "progressive_baseline.md", progressive
    )
    summary = {
        "raw_root": str(raw_root),
        "raw_records_sha256": common.sha256_file(records_path),
        "record_count": len(records),
        "progressive_row_count": len(progressive),
        "status_counts": dict(
            Counter(str(record.get("status")) for record in records)
        ),
        "paper_eligible_count": sum(
            record.get("paper_eligible") == "YES" for record in records
        ),
    }
    common.write_json(parsed_dir / "parse_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
