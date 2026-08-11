#!/usr/bin/env python3
"""Audit P7 timing paths against sequential ownership and clock evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


EXPECTED_HEAD = "7225d41ad2d1c63376a9fb1ea4e56b3b24a3e97f"
LIBERTY = Path("/home/wxt/yosys-sta/pdk/nangate45/lib/Nangate45_typ.lib")
YOSYS = Path("/home/wxt/yosys-sta/oss-cad-suite/bin/yosys")
P7_TARGETS_PS = (1000, 1500, 3000, 5000)

SOURCES = (
    "hw/ip/online_merge/src/online_merge_fp32_helpers.sv",
    "hw/ip/online_merge/src/online_merge_exp_approx.sv",
    "hw/ip/online_merge/src/online_merge_recip_approx.sv",
    "hw/ip/online_merge/src/online_merge_update_engine.sv",
    "hw/ip/online_merge/synth/online_merge_resource_wrapper.sv",
    "hw/ip/online_merge/synth/online_merge_mapped_wrapper.sv",
)

DESIGNS = (
    {
        "id": "A1",
        "label": "C1_SCALAR/trial1",
        "top": "online_merge_c1_scalar_mapped_top",
        "p7_dir": "C1_SCALAR_trial1",
        "preabc": "C1_SCALAR",
        "start_kind": "net",
        "start_net": "$auto$dfflibmap.cc:539:dfflibmap$334459",
        "end_kind": "net",
        "end_net": "$auto$rtlil.cc:3501:MuxGate$333741",
        "expected_start_signal": "i_variant.gen_engine.i_engine.m_tile_q[22]",
        "expected_end_signal": "i_variant.gen_engine.i_engine.l_new_q[12]",
        "old_delay_ps": 12342.85,
        "old_fmax_mhz": 81.01856540426239,
    },
    {
        "id": "A2",
        "label": "C2_FULL/trial1",
        "top": "online_merge_c2_full_mapped_top",
        "p7_dir": "C2_FULL_trial1",
        "preabc": "C2_FULL",
        "start_kind": "signal",
        "start_signal": "i_variant.gen_engine.i_engine.m_old_q",
        "start_index": 31,
        "end_kind": "net",
        "end_net": "$auto$rtlil.cc:3501:MuxGate$476330",
        "expected_start_signal": "i_variant.gen_engine.i_engine.m_old_q[31]",
        "expected_end_signal": "i_variant.gen_engine.i_engine.l_new_q[1]",
        "old_delay_ps": 13202.60,
        "old_fmax_mhz": 75.74265674942814,
    },
)

PATH_RE = re.compile(
    r"ABC: Path\s*(\d+) --\s+(\d+)\s*:\s*(\d+)\s+(\d+)\s+"
    r"([A-Za-z0-9_]+)\s+A =\s*([\d.]+)\s+Df =\s*([\d.]+)\s+"
    r"([-\d.]+) ps\s+S =\s*([-\d.]+) ps\s+Cin =\s*([\d.]+) ff\s+"
    r"Cout =\s*([\d.]+) ff\s+Cmax =\s*([\d.]+) ff"
)

P7_CSV = Path("experiments/parsed/p7_timing/p7_timing.csv")
DELAY_RE = re.compile(r"Delay =\s*([\d.]+) ps")
START_END_RE = re.compile(
    r"ABC: Start-point = (?P<start>\S+) \((?P<start_name>.+?)\)\.\s+"
    r"End-point = (?P<end>\S+) \((?P<end_name>.+?)\)\."
)
TARGET_FAIL_RE = re.compile(
    r"ABC: Cannot meet the target required times \((?P<target>[\d.]+)\)"
)
ABC_NETLIST_RE = re.compile(
    r"ABC: netlist\s+: i/o =\s*(?P<inputs>\d+)/\s*(?P<outputs>\d+)\s+"
    r"lat =\s*(?P<lat>\d+)\s+nd =\s*(?P<nd>\d+)\s+edge =\s*(?P<edge>\d+)\s+"
    r"area =(?P<area>[\d.]+)\s+delay =(?P<delay>[\d.]+)\s+lev =\s*(?P<lev>\d+)"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def git_blob_sha(repo_root: Path, relative: str) -> str:
    data = subprocess.run(
        ["git", "show", f"{EXPECTED_HEAD}:{relative}"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    ).stdout
    return hashlib.sha256(data).hexdigest()


def yosys_version() -> str:
    result = subprocess.run(
        [str(YOSYS), "-V"], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def source_audit(repo_root: Path) -> dict[str, Any]:
    rows = []
    for relative in SOURCES:
        current = repo_root / relative
        current_sha = sha256_file(current)
        head_sha = git_blob_sha(repo_root, relative)
        rows.append(
            {
                "path": relative,
                "current_sha256": current_sha,
                "head_blob_sha256": head_sha,
                "byte_identical_to_head": current_sha == head_sha,
            }
        )
    return {
        "analysis_head": git_head(repo_root),
        "expected_head": EXPECTED_HEAD,
        "all_sources_byte_identical_to_head": all(
            row["byte_identical_to_head"] for row in rows
        ),
        "sources": rows,
        "liberty": str(LIBERTY),
        "liberty_sha256": sha256_file(LIBERTY),
        "yosys": str(YOSYS),
        "yosys_sha256": sha256_file(YOSYS),
        "yosys_version": yosys_version(),
    }


def parse_flow(flow_path: Path) -> dict[str, Any]:
    text = flow_path.read_text(encoding="utf-8")
    abc_line = next(
        (line.strip() for line in text.splitlines() if line.strip().startswith("abc ")),
        "",
    )
    constraint_tokens = (
        "create_clock",
        "set_clock",
        "set_input_delay",
        "set_output_delay",
        "set_driving_cell",
        "set_load",
        "-constr",
    )
    has_constraints = any(token in text for token in constraint_tokens)
    return {
        "path": str(flow_path),
        "abc_command": abc_line,
        "has_explicit_clock_or_io_constraints": has_constraints,
        "abc_delay_target_ps": int(re.search(r"abc -D (\d+)", abc_line).group(1))
        if re.search(r"abc -D (\d+)", abc_line)
        else None,
        "abc_script_has_buffer": "buffer" in abc_line,
        "abc_script_has_upsize": "upsize" in abc_line,
        "abc_script_has_dnsize": "dnsize" in abc_line,
        "abc_uses_stime": "stime" in abc_line,
        "abc_uses_dretime": "dretime" in abc_line,
        "clock_constraint_audit": (
            "No create_clock, set_clock, input/output delay, driver, or load "
            "constraint appears in flow.ys."
            if not has_constraints
            else "One or more timing constraint tokens appear in flow.ys."
        ),
    }


def liberty_sequential_audit() -> dict[str, Any]:
    """Record the sequential arcs present in the selected Liberty file.

    This is deliberately a small textual audit.  The P7 result is not STA;
    the important distinction is between arcs declared by Liberty and arcs
    consumed by the ABC ``stime`` flow.
    """

    text = LIBERTY.read_text(encoding="utf-8")
    cells: dict[str, Any] = {}
    for cell_name in ("DFFR_X1", "DFFS_X1"):
        match = re.search(
            rf"^  cell \({cell_name}\) \{{(?P<body>.*?)(?=^  cell \(|\Z)",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        if not match:
            cells[cell_name] = {"found": False}
            continue
        body = match.group("body")
        ff_match = re.search(
            r"ff \(\"(?P<iq>[^\"]+)\"\s*,\s*\"(?P<iqn>[^\"]+)\"\)\s*\{(?P<body>.*?)\n\s*\}",
            body,
            flags=re.DOTALL,
        )
        ff = {}
        if ff_match:
            ff = {
                key: value
                for key, value in re.findall(
                    r"^\s*(next_state|clocked_on|clear|preset)\s*:\s*\"([^\"]+)\"",
                    ff_match.group("body"),
                    flags=re.MULTILINE,
                )
            }
            ff["outputs"] = [ff_match.group("iq"), ff_match.group("iqn")]
        d_pin_match = re.search(
            r"pin \(D\).*?(?=^\s*pin \(|\Z)",
            body,
            flags=re.MULTILINE | re.DOTALL,
        )
        d_pin_body = d_pin_match.group(0) if d_pin_match else ""
        cells[cell_name] = {
            "found": True,
            "ff": ff,
            "D_timing_types": sorted(
                set(re.findall(r"timing_type\s*:\s*([A-Za-z0-9_]+)", d_pin_body))
            ),
            "D_related_clock_arcs": sorted(
                set(
                    re.findall(
                        r"related_pin\s*:\s*\"CK\";\s*timing_type\s*:\s*([A-Za-z0-9_]+)",
                        d_pin_body,
                    )
                )
            ),
            "Q_clock_to_q_arc_present": bool(
                re.search(
                    r"pin \(Q\).*?related_pin\s*:\s*\"CK\";\s*timing_type\s*:\s*rising_edge",
                    body,
                    flags=re.MULTILINE | re.DOTALL,
                )
            ),
        }
    return {
        "liberty_path": str(LIBERTY),
        "liberty_sha256": sha256_file(LIBERTY),
        "cells": cells,
        "declared_arcs": {
            "FF_function": "next_state D, clocked_on CK",
            "setup_hold": "D pin related_pin CK (setup_rising and hold_rising)",
            "clock_to_q": "Q/QN pin related_pin CK (rising_edge)",
            "clock_skew": "not a Liberty cell arc; requires clock-tree/STA constraints",
        },
    }


def frontend_flow_text(preabc_path: Path) -> str:
    source_tokens = " ".join(str(Path(__file__).parents[2] / source) for source in SOURCES)
    return "\n".join(
        [
            f"read_liberty -lib {LIBERTY}",
            f"read_slang --std 1800-2017 {source_tokens}",
            "hierarchy -check -top {top}",
            "proc",
            "opt",
            "memory_collect",
            "opt_clean",
            "flatten",
            'setattr -set fsm_encoding "auto" w:*state_q',
            "fsm",
            "opt",
            "techmap",
            "opt",
            f"dfflibmap -liberty {LIBERTY}",
            f"write_json {preabc_path}",
            "",
        ]
    )


def ensure_preabc(
    repo_root: Path,
    preabc_root: Path,
    spec: dict[str, Any],
    reuse: bool = False,
) -> dict[str, Any]:
    """Run (or reuse) the exact P7 front-end through dfflibmap.

    The generated JSON and log are intentionally under work-p7r, which is
    ignored.  A checked-in flow script makes regeneration direct and
    reproducible; callers may opt into reusing an existing JSON for a fast
    parse-only rerun.
    """

    design_root = preabc_root / spec["preabc"]
    design_root.mkdir(parents=True, exist_ok=True)
    preabc_path = design_root / "preabc.json"
    flow_path = design_root / "frontend.ys"
    log_path = design_root / "frontend.log"
    flow_text = frontend_flow_text(preabc_path).format(top=spec["top"])
    flow_path.write_text(flow_text, encoding="utf-8")
    generated = False
    if not preabc_path.exists() or not reuse:
        generated = True
        command = [
            str(YOSYS),
            "-Q",
            "-m",
            "slang",
            "-p",
            f"script {flow_path}",
        ]
        result = subprocess.run(
            command,
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=3600,
        )
        log_path.write_text(result.stdout, encoding="utf-8")
    return {
        "preabc_json": str(preabc_path),
        "preabc_json_sha256": sha256_file(preabc_path),
        "frontend_flow": str(flow_path),
        "frontend_flow_sha256": sha256_file(flow_path),
        "frontend_log": str(log_path) if log_path.exists() else None,
        "frontend_log_sha256": sha256_file(log_path) if log_path.exists() else None,
        "generated_in_this_run": generated,
        "command": [str(YOSYS), "-Q", "-m", "slang", "-p", f"script {flow_path}"],
        "stops_after": "dfflibmap; write_json",
    }


def parse_path_log(log_path: Path) -> dict[str, Any]:
    text = log_path.read_text(encoding="utf-8")
    path_rows: list[dict[str, Any]] = []
    for match in PATH_RE.finditer(text):
        (
            path_index,
            node,
            level,
            fanin,
            cell,
            area,
            df,
            slew,
            signal,
            cin,
            cout,
            cmax,
        ) = match.groups()
        path_rows.append(
            {
                "path_index": int(path_index),
                "abc_node": int(node),
                "logic_level": int(level),
                "fanin": int(fanin),
                "cell": cell,
                "area": float(area),
                "delay_fall_ps": float(df),
                "slew_ps": float(slew),
                "signal_ps": float(signal),
                "cin_ff": float(cin),
                "cout_ff": float(cout),
                "cmax_ff": float(cmax),
            }
        )
    start_end = START_END_RE.search(text)
    target_fail = TARGET_FAIL_RE.search(text)
    netlist = ABC_NETLIST_RE.search(text)
    delay = DELAY_RE.findall(text)
    violations = [row for row in path_rows if row["cout_ff"] > row["cmax_ff"]]
    gate_rows = [row for row in path_rows if row["cell"] not in {"pi", "po"}]
    max_cout = max(path_rows, key=lambda row: row["cout_ff"])
    max_gate_cout = max(gate_rows, key=lambda row: row["cout_ff"])
    return {
        "log_path": str(log_path),
        "log_sha256": sha256_file(log_path),
        "critical_delay_ps": float(delay[-1]) if delay else None,
        "startpoint_label": start_end.group("start") if start_end else None,
        "startpoint_name": start_end.group("start_name") if start_end else None,
        "endpoint_label": start_end.group("end") if start_end else None,
        "endpoint_name": start_end.group("end_name") if start_end else None,
        "target_met": target_fail is None,
        "target_failure_ps": (
            float(target_fail.group("target")) if target_fail else None
        ),
        "target_failure_count": len(TARGET_FAIL_RE.findall(text)),
        "abc_netlist": netlist.groupdict() if netlist else None,
        "path_rows": path_rows,
        "path_row_count": len(path_rows),
        "fanout_violation_count": len(violations),
        "gate_fanout_violation_count": sum(
            row["cout_ff"] > row["cmax_ff"] for row in gate_rows
        ),
        "boundary_row_violation_count": len(violations) - sum(
            row["cout_ff"] > row["cmax_ff"] for row in gate_rows
        ),
        "max_cout_row": max_cout,
        "max_gate_cout_row": max_gate_cout,
    }


def parse_p7_csv(repo_root: Path) -> dict[tuple[str, int], dict[str, Any]]:
    """Load the existing P7 collection without recomputing its metrics."""

    csv_path = repo_root / P7_CSV
    rows: dict[tuple[str, int], dict[str, Any]] = {}
    with csv_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            label = row["label"]
            target = int(row["delay_target_ps"])
            row["critical_delay_ps"] = float(row["critical_delay_ps"])
            row["fmax_mhz"] = float(row["fmax_mhz"])
            row["target_met"] = row["target_met"].strip().lower() == "true"
            rows[(label, target)] = row
    return rows


def timing_semantics_audit(flow: dict[str, Any], path: dict[str, Any]) -> dict[str, Any]:
    """State what the P7 ABC log does and does not time."""

    netlist = path["abc_netlist"] or {}
    return {
        "target_met": path["target_met"],
        "target_failure_ps": path["target_failure_ps"],
        "target_failure_count": path["target_failure_count"],
        "abc_lat": int(netlist["lat"]) if netlist.get("lat") is not None else None,
        "ff_arcs": "not evaluated by stime; DFFs are sequential boundaries",
        "clock_to_q": "excluded; ABC path starts at pi/registered boundary",
        "setup": "excluded; no required-time check against capture DFF setup arc",
        "hold": "excluded; only max-delay path printed",
        "clock_skew": "excluded; no clock tree or skew constraint",
        "io_constraints": "excluded; no input/output delay, driver, or load",
        "buffer": flow["abc_script_has_buffer"],
        "upsize": flow["abc_script_has_upsize"],
        "dnsize": flow["abc_script_has_dnsize"],
        "cap_fanout": {
            "gate_violation_count": path["gate_fanout_violation_count"],
            "boundary_row_violation_count": path["boundary_row_violation_count"],
            "max_gate_cout_ff": path["max_gate_cout_row"]["cout_ff"],
            "max_gate_cmax_ff": path["max_gate_cout_row"]["cmax_ff"],
            "max_gate_row": path["max_gate_cout_row"]["path_index"],
        },
    }


def top_module(preabc_path: Path, top: str) -> dict[str, Any]:
    payload = json.loads(preabc_path.read_text(encoding="utf-8"))
    module = payload["modules"][top]
    return module


def names_for_bit(module: dict[str, Any], bit: int) -> list[dict[str, Any]]:
    names = []
    for name, entry in module.get("netnames", {}).items():
        bits = entry.get("bits", [])
        indices = [index for index, value in enumerate(bits) if value == bit]
        if indices:
            names.append({"name": name, "indices": indices})
    return names


def semantic_names(module: dict[str, Any], bit: int) -> list[str]:
    names = []
    for item in names_for_bit(module, bit):
        name = item["name"]
        if name.startswith("i_variant."):
            for index in item["indices"]:
                names.append(f"{name}[{index}]")
    return names


def cell_hits(module: dict[str, Any], bit: int) -> list[dict[str, Any]]:
    hits = []
    for name, cell in module.get("cells", {}).items():
        for pin, bits in cell.get("connections", {}).items():
            if bit in bits:
                hits.append(
                    {
                        "cell": name,
                        "type": cell.get("type"),
                        "pin": pin,
                        "source": cell.get("attributes", {}).get("src"),
                    }
                )
    return hits


def dff_for_pin(module: dict[str, Any], bit: int, pins: set[str]) -> dict[str, Any]:
    matches = []
    for name, cell in module.get("cells", {}).items():
        if not str(cell.get("type", "")).startswith("DFF"):
            continue
        for pin in pins:
            if bit in cell.get("connections", {}).get(pin, []):
                matches.append(
                    {
                        "cell": name,
                        "type": cell.get("type"),
                        "pin": pin,
                        "connections": cell.get("connections", {}),
                        "source": cell.get("attributes", {}).get("src"),
                    }
                )
    if len(matches) != 1:
        raise RuntimeError(f"expected one DFF for bit {bit}, got {len(matches)}")
    return matches[0]


def resolve_bit(module: dict[str, Any], spec: dict[str, Any], prefix: str) -> dict[str, Any]:
    if spec[f"{prefix}_kind"] == "net":
        name = spec[f"{prefix}_net"]
        bits = module["netnames"][name]["bits"]
        if len(bits) != 1:
            raise RuntimeError(f"{name} is not a one-bit netname")
        return {"name": name, "index": None, "bit": bits[0]}
    name = spec[f"{prefix}_signal"]
    index = spec[f"{prefix}_index"]
    bits = module["netnames"][name]["bits"]
    return {"name": name, "index": index, "bit": bits[index]}


def ownership_audit(
    module: dict[str, Any], spec: dict[str, Any], path: dict[str, Any]
) -> dict[str, Any]:
    clock_port = "clk_i"
    clock_bits = module["ports"][clock_port]["bits"]
    start_net = resolve_bit(module, spec, "start")
    end_net = resolve_bit(module, spec, "end")
    start_dff = dff_for_pin(module, start_net["bit"], {"Q", "QN"})
    end_dff = dff_for_pin(module, end_net["bit"], {"D"})
    start_q_bit = start_dff["connections"]["Q"][0]
    end_q_bit = end_dff["connections"]["Q"][0]
    start_clock = start_dff["connections"].get("CK", [])
    end_clock = end_dff["connections"].get("CK", [])
    same_clock = start_clock == clock_bits and end_clock == clock_bits
    category = "reg→reg" if same_clock else "unclassified"
    return {
        "recognized_clock_port": clock_port,
        "recognized_clock_bits": clock_bits,
        "start_net": start_net,
        "start_net_names": names_for_bit(module, start_net["bit"]),
        "start_cell": start_dff,
        "start_q_bit": start_q_bit,
        "start_q_signal_ownership": semantic_names(module, start_q_bit),
        "end_net": end_net,
        "end_net_names": names_for_bit(module, end_net["bit"]),
        "end_cell": end_dff,
        "end_q_bit": end_q_bit,
        "end_q_signal_ownership": semantic_names(module, end_q_bit),
        "start_clock_bits": start_clock,
        "end_clock_bits": end_clock,
        "start_clock_matches_port": start_clock == clock_bits,
        "end_clock_matches_port": end_clock == clock_bits,
        "same_clock_domain": same_clock,
        "category": category,
        "category_evidence": (
            "ABC start/end names resolve to a DFF Q/QN and a DFF D; both "
            "DFF CK pins resolve to clk_i."
        ),
        "path_delay_ps": path["critical_delay_ps"],
        "ordered_cell_chain": path["path_rows"],
        "startpoint": path["startpoint_name"],
        "endpoint": path["endpoint_name"],
        "module_ownership": {
            "top": spec["top"],
            "start_register": f"{spec['top']} / i_variant.gen_engine.i_engine",
            "capture_register": f"{spec['top']} / i_variant.gen_engine.i_engine",
            "start_source": start_dff["source"],
            "capture_source": end_dff["source"],
        },
    }


def sequential_audit(module: dict[str, Any]) -> dict[str, Any]:
    types = Counter(
        cell.get("type")
        for cell in module.get("cells", {}).values()
        if str(cell.get("type", "")).startswith("DFF")
    )
    clock_bits = module["ports"]["clk_i"]["bits"]
    ck_values = Counter()
    all_ck_match = True
    for cell in module.get("cells", {}).values():
        if not str(cell.get("type", "")).startswith("DFF"):
            continue
        ck = tuple(cell.get("connections", {}).get("CK", []))
        ck_values[ck] += 1
        all_ck_match &= list(ck) == clock_bits
    return {
        "sequential_cell_count": sum(types.values()),
        "sequential_cell_types": dict(sorted(types.items())),
        "clock_port": "clk_i",
        "clock_bits": clock_bits,
        "all_sequential_ck_pins_match_clock_port": all_ck_match,
        "sequential_ck_bit_sets": {
            ",".join(str(bit) for bit in bits): count
            for bits, count in ck_values.items()
        },
    }


def audit_design(
    repo_root: Path,
    p7_root: Path,
    preabc_root: Path,
    spec: dict[str, Any],
    p7_csv_rows: dict[tuple[str, int], dict[str, Any]],
    preabc_info: dict[str, Any],
) -> dict[str, Any]:
    run_dir = p7_root / spec["p7_dir"] / "1000ps"
    log_path = run_dir / "yosys.log"
    flow_path = run_dir / "flow.ys"
    netlist_path = run_dir / "mapped-netlist.v"
    stat_path = run_dir / "mapped-stat.json"
    preabc_path = Path(preabc_info["preabc_json"])
    path = parse_path_log(log_path)
    flow = parse_flow(flow_path)
    module = top_module(preabc_path, spec["top"])
    path["mapped_netlist_sha256"] = sha256_file(netlist_path)
    path["mapped_stat_sha256"] = sha256_file(stat_path)
    path["flow_sha256"] = sha256_file(flow_path)
    ownership = ownership_audit(module, spec, path)
    sequential = sequential_audit(module)
    target_audit = []
    flow_audit = {}
    for target_ps in P7_TARGETS_PS:
        target_dir = p7_root / spec["p7_dir"] / f"{target_ps}ps"
        target_log = target_dir / "yosys.log"
        target_flow_path = target_dir / "flow.ys"
        target_path = parse_path_log(target_log)
        target_flow = parse_flow(target_flow_path)
        csv_row = p7_csv_rows[(spec["label"], target_ps)]
        target_audit.append(
            {
                "target_ps": target_ps,
                "log_path": str(target_log),
                "flow_path": str(target_flow_path),
                "critical_delay_ps": target_path["critical_delay_ps"],
                "csv_critical_delay_ps": csv_row["critical_delay_ps"],
                "csv_fmax_mhz": csv_row["fmax_mhz"],
                "target_met_log": target_path["target_met"],
                "target_met_csv": csv_row["target_met"],
                "target_failure_ps": target_path["target_failure_ps"],
                "target_failure_count": target_path["target_failure_count"],
                "startpoint_name": target_path["startpoint_name"],
                "endpoint_name": target_path["endpoint_name"],
                "delay_matches_csv": abs(
                    target_path["critical_delay_ps"]
                    - csv_row["critical_delay_ps"]
                )
                < 0.01,
            }
        )
        flow_audit[str(target_ps)] = {
            "flow_sha256": sha256_file(target_flow_path),
            "abc_delay_target_ps": target_flow["abc_delay_target_ps"],
            "has_explicit_clock_or_io_constraints": target_flow[
                "has_explicit_clock_or_io_constraints"
            ],
            "abc_script_has_buffer": target_flow["abc_script_has_buffer"],
            "abc_script_has_upsize": target_flow["abc_script_has_upsize"],
            "abc_script_has_dnsize": target_flow["abc_script_has_dnsize"],
            "abc_uses_stime": target_flow["abc_uses_stime"],
            "abc_uses_dretime": target_flow["abc_uses_dretime"],
        }
    path["critical_delay_matches_csv"] = abs(
        path["critical_delay_ps"]
        - p7_csv_rows[(spec["label"], 1000)]["critical_delay_ps"]
    ) < 0.01
    semantics = timing_semantics_audit(flow, path)
    return {
        "id": spec["id"],
        "label": spec["label"],
        "top": spec["top"],
        "preabc": preabc_info,
        "flow": flow,
        "flow_audit_by_target": flow_audit,
        "sequential": sequential,
        "path": path,
        "timing_semantics": semantics,
        "ownership": ownership,
        "target_audit": target_audit,
        "all_targets_unmet": all(
            not row["target_met_log"] and not row["target_met_csv"]
            for row in target_audit
        ),
        "legacy_inverse_delay_fmax_mhz": spec["old_fmax_mhz"],
        "synchronous_fmax_mhz": None,
        "outcome": "B",
        "outcome_wording": (
            "Verified reg→reg combinational boundary path near 12 ns, but "
            "no synchronous Fmax is reported because clock/setup/skew and "
            "cell timing arcs are not constrained by this flow."
        ),
    }


def csv_rows(designs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    categories = (
        ("reg→reg", "verified"),
        ("PI→reg", "unavailable"),
        ("reg→PO", "unavailable"),
        ("PI→PO", "unavailable"),
    )
    for design in designs:
        for category, status in categories:
            path = design["path"]
            rows.append(
                {
                    "design": design["id"],
                    "category": category,
                    "status": status,
                    "longest_delay_ps": (
                        path["critical_delay_ps"] if status == "verified" else ""
                    ),
                    "fmax_mhz": "",
                    "startpoint": (
                        path["startpoint_name"] if status == "verified" else ""
                    ),
                    "endpoint": path["endpoint_name"] if status == "verified" else "",
                    "reason": (
                        "ABC stime critical path resolves to DFF Q/QN→D."
                        if status == "verified"
                        else "P7 stime output does not enumerate this category."
                    ),
                }
            )
    return rows


def chain_text(design: dict[str, Any]) -> str:
    chain = " -> ".join(
        f"{row['path_index']}:{row['cell']}"
        for row in design["path"]["path_rows"]
    )
    endpoint = design["path"]["endpoint_label"] or "po"
    return f"{chain} -> {endpoint}"


def markdown_report(
    source: dict[str, Any], designs: list[dict[str, Any]], output_dir: Path
) -> str:
    lines = [
        "# P7-R Synchronous Timing Methodology Audit",
        "",
        "Status: **Outcome B** for both standalone designs.",
        "",
        "The existing ABC `stime` paths are reproducibly reg→reg boundary "
        "paths after ownership recovery. They remain library-delay proxies; "
        "this audit does not report synchronous Fmax.",
        "",
        "## Scope and reproducibility",
        "",
        f"- Analysis HEAD: `{source['analysis_head']}`.",
        f"- Expected HEAD: `{source['expected_head']}`.",
        f"- Liberty: `{source['liberty']}` "
        f"(SHA256 `{source['liberty_sha256']}`).",
        f"- Yosys: `{source['yosys']}` (`{source['yosys_version']}`, "
        f"SHA256 `{source['yosys_sha256']}`).",
        "- P7 front-end: `read_liberty; read_slang; hierarchy -check; proc; "
        "opt; memory_collect; opt_clean; flatten; setattr; fsm; opt; "
        "techmap; opt; dfflibmap`; P7 back-end then runs `abc -D <target> "
        "... stime -p 5; clean; check -assert`.",
        "- The exact front-end script is regenerated under `work-p7r/` and "
        "stops at `dfflibmap; write_json`; source bytes match the expected "
        "HEAD.",
        "",
        "P7 RTL input SHA256 audit:",
        "",
        "| Input | SHA256 | Byte-identical to expected HEAD |",
        "| --- | --- | --- |",
        *(
            f"| `{row['path']}` | `{row['current_sha256']}` | "
            f"`{row['byte_identical_to_head']}` |"
            for row in source["sources"]
        ),
        "",
        f"All six inputs are byte-identical to `{source['expected_head']}`: "
        f"`{source['all_sources_byte_identical_to_head']}`.",
        "- Full source and artifact hashes are in "
        f"`{output_dir / 'p7r_path_details.json'}`.",
        "",
        "## Clock and timing-constraint audit",
        "",
        "Both `flow.ys` files have top-level `clk_i` and asynchronous `rst_ni` "
        "connections, and every mapped DFF CK pin resolves to `clk_i`. "
        "Neither flow contains `create_clock`, `set_clock`, input/output "
        "delay, driver, load, or `-constr` constraints. The `-D` value is an "
        "ABC mapping target, not a clock period.",
        "",
        "The ABC script uses `dretime; map -D ...; ...; stime -p 5`, but does "
        "not use `buffer`, `upsize`, or `dnsize`. ABC reports `lat = 0`, so "
        "clock-to-Q, setup/hold, and clock skew are not represented. No input "
        "driver or output load is supplied; the `-D` target is not a clock "
        "period constraint.",
        "",
        "The selected Liberty declares DFFR/DFFS `next_state=D`, "
        "`clocked_on=CK`, D-pin setup/hold arcs, and Q/QN clock-to-Q arcs. "
        "Those declarations do not make this ABC `stime` run synchronous STA: "
        "the printed path consists of combinational gates between ABC `pi`/`po` "
        "boundaries, with no capture required time or clock network.",
        "",
        "## Path-category results",
        "",
        "| Design | Category | Longest delay (ps) | Status |",
        "| --- | --- | ---: | --- |",
    ]
    for design in designs:
        for row in csv_rows([design]):
            delay = (
                f"{row['longest_delay_ps']:.2f}"
                if row["longest_delay_ps"] != ""
                else "N/A"
            )
            lines.append(
                f"| {row['design']} | {row['category']} | {delay} | "
                f"{row['status']} |"
            )
    lines.extend(
        [
            "",
            "The reg→reg row is the longest path emitted by `stime`; its ABC "
            "`pi`/`po` labels are not treated as physical primary ports. The "
            "other rows are N/A because this P7 flow emits no category-specific "
            "path enumeration.",
            "",
            "## Design evidence",
        ]
    )
    for design in designs:
        path = design["path"]
        own = design["ownership"]
        seq = design["sequential"]
        flow = design["flow"]
        max_cout = path["max_gate_cout_row"]
        semantics = design["timing_semantics"]
        target_text = ", ".join(
            f"{row['target_ps']} ps: {'met' if row['target_met_log'] else 'unmet'}"
            for row in design["target_audit"]
        )
        lines.extend(
            [
                "",
                f"### {design['id']} ({design['top']})",
                "",
                f"- Pre-ABC JSON: `{design['preabc']['preabc_json']}` "
                f"(SHA256 `{design['preabc']['preabc_json_sha256']}`); "
                f"front-end script: `{design['preabc']['frontend_flow']}`.",
                f"- Sequential cells: {seq['sequential_cell_count']} "
                f"({seq['sequential_cell_types']}); recognized clock: "
                f"`{seq['clock_port']}`; all CK matches: "
                f"`{seq['all_sequential_ck_pins_match_clock_port']}`.",
                f"- All P7 targets: {target_text}; each log and CSV row is "
                f"unmet (`all_targets_unmet={design['all_targets_unmet']}`).",
                f"- Path: `{path['startpoint_label']} ({path['startpoint_name']})` "
                f"→ `{path['endpoint_label']} ({path['endpoint_name']})`; "
                f"delay `{path['critical_delay_ps']:.2f} ps`; category "
                f"`{own['category']}`.",
                f"- Launch ownership: `{own['start_q_signal_ownership']}` in "
                f"`{own['module_ownership']['start_register']}` via "
                f"`{own['start_cell']['type']} {own['start_cell']['pin']}`; "
                f"capture ownership: `{own['end_q_signal_ownership']}` in "
                f"`{own['module_ownership']['capture_register']}` via "
                f"`{own['end_cell']['type']} {own['end_cell']['pin']}`; "
                f"both CK pins resolve to `{own['recognized_clock_port']}` "
                f"bits `{own['start_clock_bits']}`/`{own['end_clock_bits']}`; "
                f"source `{own['module_ownership']['start_source']}` → "
                f"`{own['module_ownership']['capture_source']}`.",
                f"- Maximum path Cout: `{max_cout['cout_ff']:.1f} ff` versus "
                f"Cmax `{max_cout['cmax_ff']:.1f} ff` at "
                f"`{max_cout['cell']}` (path {max_cout['path_index']}); "
                f"gate Cout>Cmax rows: `{semantics['cap_fanout']['gate_violation_count']}` "
                f"(ABC boundary row adds "
                f"`{semantics['cap_fanout']['boundary_row_violation_count']}`).",
                f"- Timing semantics: target_met `{semantics['target_met']}` "
                f"(failure `{semantics['target_failure_ps']} ps`); FF arcs "
                f"`{semantics['ff_arcs']}`; clk→Q `{semantics['clock_to_q']}`; "
                f"setup `{semantics['setup']}`; skew `{semantics['clock_skew']}`; "
                f"I/O `{semantics['io_constraints']}`; buffer/upsize/dnsize "
                f"=`{semantics['buffer']}/{semantics['upsize']}/{semantics['dnsize']}`.",
                "- Ordered ABC chain (the complete machine-readable chain is "
                "also in `p7r_path_details.json`):",
                "",
                "```text",
                chain_text(design),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Classification of the old P7 numbers",
            "",
            "The old `pi`/`po` labels are ABC's sequential boundary abstraction. "
            "A1's start net resolves to the `DFFR_X1` QN associated with "
            "`m_tile_q[22]` in the scalar mapped top, and its endpoint net is "
            "the D input of the `DFFR_X1` whose Q is `l_new_q[12]`. A2 "
            "resolves analogously from `m_old_q[31]` Q to the D input of the "
            "register whose Q is `l_new_q[1]`. Thus both old paths are "
            "reg→reg combinational boundary delays, not PI→PO paths.",
            "",
            "The old inverses, 81.0186 MHz (A1) and 75.7427 MHz (A2), are "
            "withdrawn as synchronous Fmax. They must not be described as "
            "cluster Fmax, signoff frequency, or achievable frequency. The "
            "12.34285 ns and 13.20260 ns values may only be called pre-layout "
            "Nangate45/ABC reg→reg combinational delay proxies under this "
            "unconstrained flow.",
            "",
            "## Final outcome",
            "",
            "**Outcome B.** The recovered longest paths are real reg→reg paths "
            "and remain near 12–13 ns, but the flow lacks the timing "
            "constraints and sequential timing terms required for a defensible "
            "synchronous Fmax. All four category rows, clock assumptions, and "
            "limitations are encoded in the JSON/CSV outputs.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit P7 ABC paths against sequential ownership."
    )
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[2])
    parser.add_argument(
        "--p7-root", type=Path, default=Path("work-p7/p7runs")
    )
    parser.add_argument(
        "--preabc-root", type=Path, default=Path("work-p7r/preabc")
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("experiments/parsed/p7r_timing")
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("experiments/reports/P7R_SYNCHRONOUS_TIMING_AUDIT.md"),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace existing parsed/report outputs",
    )
    parser.add_argument(
        "--reuse-preabc",
        action="store_true",
        help="reuse work-p7r pre-ABC JSON instead of rerunning dfflibmap",
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    p7_root = (repo_root / args.p7_root).resolve()
    preabc_root = (repo_root / args.preabc_root).resolve()
    output_dir = (repo_root / args.output_dir).resolve()
    report_path = (repo_root / args.report).resolve()
    if (output_dir.exists() or report_path.exists()) and not args.overwrite:
        raise SystemExit("refusing to overwrite existing M2 audit outputs")

    source = source_audit(repo_root)
    if source["analysis_head"] != EXPECTED_HEAD:
        raise SystemExit("analysis HEAD does not match expected P7 HEAD")
    if not source["all_sources_byte_identical_to_head"]:
        raise SystemExit("P7 source bytes differ from expected HEAD")

    p7_csv_rows = parse_p7_csv(repo_root)
    preabc_infos = {
        spec["id"]: ensure_preabc(
            repo_root, preabc_root, spec, reuse=args.reuse_preabc
        )
        for spec in DESIGNS
    }
    designs = [
        audit_design(
            repo_root,
            p7_root,
            preabc_root,
            spec,
            p7_csv_rows,
            preabc_infos[spec["id"]],
        )
        for spec in DESIGNS
    ]
    for design in designs:
        if not design["path"]["critical_delay_matches_csv"]:
            raise SystemExit(f"{design['id']}: log and P7 CSV delay mismatch")
        if design["ownership"]["category"] != "reg→reg":
            raise SystemExit(f"{design['id']}: failed reg→reg ownership audit")
        if not design["all_targets_unmet"]:
            raise SystemExit(f"{design['id']}: at least one P7 target is met")
        if not all(row["delay_matches_csv"] for row in design["target_audit"]):
            raise SystemExit(f"{design['id']}: target log and P7 CSV mismatch")

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "p7r_path_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "design",
            "category",
            "status",
            "longest_delay_ps",
            "fmax_mhz",
            "startpoint",
            "endpoint",
            "reason",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(csv_rows(designs))

    details = {
        "audit": {
            "expected_head": EXPECTED_HEAD,
            "analysis_head": source["analysis_head"],
            "outcome": "B",
            "synchronous_fmax_policy": "withdrawn",
            "category_policy": {
                "reg→reg": "verified boundary-delay proxy",
                "PI→reg": "unavailable",
                "reg→PO": "unavailable",
                "PI→PO": "unavailable",
            },
        },
        "source_audit": source,
        "liberty_sequential_audit": liberty_sequential_audit(),
        "p7_csv": str(repo_root / P7_CSV),
        "designs": designs,
    }
    details_path = output_dir / "p7r_path_details.json"
    details_path.write_text(
        json.dumps(details, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        markdown_report(source, designs, output_dir), encoding="utf-8"
    )
    print(f"wrote {summary_path}")
    print(f"wrote {details_path}")
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
