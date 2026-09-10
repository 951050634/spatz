#!/usr/bin/env python3
"""Plan or collect the matched Phase 6 Spatz integration synthesis.

The default invocation is deliberately plan-only.  ``--execute-formal`` is
the only path that creates synthesis outputs, and it refuses a dirty
worktree.  The baseline is built from a synthesis-only overlay of the direct
pre-SMU cluster commit, while the SMU configuration uses the current source
tree and the frozen reciprocal Mixed define.  No repository RTL is modified
to construct the baseline.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
BENDER = ROOT / "install" / "bender" / "bender"
YOSYS = Path("/home/wxt/yosys-sta/oss-cad-suite/bin/yosys")
LIBERTY = Path(
    "/home/wxt/yosys-sta/pdk/nangate45/lib/Nangate45_typ.lib"
)
SLANG = Path(
    "/home/wxt/yosys-sta/oss-cad-suite/share/yosys/plugins/slang.so"
)
SRAM_BLACKBOX = ROOT / "experiments/synthesis/compat/tc_sram_blackbox.sv"
BASELINE_REF = "957667e^"
TOP = "spatz_cluster_wrapper"
SMU_MODULE = "spatz_cluster$spatz_cluster_wrapper.i_cluster"
TIMING_TARGET_PS = 50000

BASELINE_OVERRIDES = (
    "hw/system/spatz_cluster/src/spatz_cluster.sv",
    "hw/system/spatz_cluster/src/spatz_cluster_peripheral/spatz_cluster_peripheral.sv",
    "hw/system/spatz_cluster/src/spatz_cluster_peripheral/spatz_cluster_peripheral_reg.hjson",
    "hw/system/spatz_cluster/src/spatz_cluster_peripheral/spatz_cluster_peripheral_reg_pkg.sv",
    "hw/system/spatz_cluster/src/spatz_cluster_peripheral/spatz_cluster_peripheral_reg_top.sv",
)

CONFIGS = (
    ("Spatz_Baseline", "baseline"),
    ("Spatz_Mixed_SMU", "smu"),
)

PROC_PASSES = """\
proc_clean
proc_prune
proc_init
proc_arst
proc_rom
proc_mux
proc_dlatch
proc_dff
proc_memwr
proc_clean
opt_expr -keepdc
"""

ABC_TIMING_SCRIPT = (
    "+strash; if -K 6; dretime; map -D {target}; "
    "&get -n; &st; &dch; &nf; &put; stime -p 5; print_stats -m"
)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_text(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def command_text(command: list[str]) -> str:
    return shlex.join(str(part) for part in command)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def worktree_audit() -> dict[str, Any]:
    status = git_text("status", "--short")
    return {
        "clean": not bool(status),
        "status_short": status.splitlines() if status else [],
        "commit": git_text("rev-parse", "HEAD"),
        "baseline_reference": git_text("rev-parse", BASELINE_REF),
    }


def bender_flist() -> list[str]:
    command = [
        str(BENDER), "script", "flist-plus", "-t", "rtl", "-t", "spatz",
        "-D", "COMMON_CELLS_ASSERTS_OFF", "-D", "BUF_FPU", "-D",
        "TARGET_SYNTHESIS", "-D", "ONLINE_MERGE_MIXED_RECIPROCAL",
    ]
    completed = subprocess.run(
        command, cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    lines = [line.strip() for line in completed.stdout.splitlines()]
    lines = [
        line for line in lines
        if line.startswith("+incdir+") or line.startswith("+define+") or
        (line.startswith("/") and line.endswith((".sv", ".v", ".vhd")))
    ]
    require(lines, "Bender produced an empty synthesis file list")
    if "+define+TARGET_FLIST" not in lines:
        lines.insert(0, "+define+TARGET_FLIST")
    return lines


def materialize_overlay(overlay_root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for relative in BASELINE_OVERRIDES:
        destination = overlay_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        contents = subprocess.run(
            ["git", "show", f"{BASELINE_REF}:{relative}"], cwd=ROOT,
            check=True, stdout=subprocess.PIPE,
        ).stdout
        # The first SMU integration commit also carried forward this
        # unrelated request-ID tieoff in the core TCDM adapter.  Restore the
        # current value in the historical baseline overlay so the matched
        # comparison differs only in the SMU integration boundary.
        if relative == "hw/system/spatz_cluster/src/spatz_cluster.sv":
            old_line = (
                "        tcdm_req[TcdmPortsOffs+j].q.user.is_core = 1;\n"
            )
            new_line = old_line + (
                "        tcdm_req[TcdmPortsOffs+j].q.user.req_id  = '0;\n"
            )
            require(contents.count(old_line.encode()) == 1,
                    "pre-SMU overlay request-ID tieoff context is not unique")
            contents = contents.replace(old_line.encode(), new_line.encode(), 1)
        destination.write_bytes(contents)
        result[relative] = destination
    return result


def write_flist(path: Path, baseline: bool, overlay: dict[str, Path]) -> dict[str, Any]:
    lines = bender_flist()
    if baseline:
        replacements = {
            str(ROOT / relative): str(overlay[relative])
            for relative in BASELINE_OVERRIDES
            if relative.endswith(".sv")
        }
        lines = [replacements.get(line, line) for line in lines]
    else:
        replacements = {}
    original_sram = next(
        (line for line in lines
         if line.endswith("/tech_cells_generic-8293603d34b176db/src/rtl/tc_sram.sv")
         or line.endswith("/src/rtl/tc_sram.sv")),
        None,
    )
    require(original_sram is not None, "Bender flist has no tc_sram.sv")
    lines = [str(SRAM_BLACKBOX) if line == original_sram else line for line in lines]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "baseline_overlay": baseline,
        "baseline_file_replacements": replacements,
        "sram_original": original_sram,
        "sram_replacement": str(SRAM_BLACKBOX),
        "line_count": len(lines),
    }


def render_flow(path: Path, flist: Path, config: str, kind: str) -> None:
    tieoffs = ""
    if kind == "baseline":
        # These names are retained for auditability; the baseline overlay does
        # not contain these nets.  The historical boundary removes them.
        tieoffs = "# Baseline source overlay has no merge_* nets or SMU instance.\n"
    if config == "area":
        map_command = f"abc -fast -liberty {LIBERTY}"
    else:
        abc = ABC_TIMING_SCRIPT.format(target=TIMING_TARGET_PS)
        map_command = (
            f'abc -D {TIMING_TARGET_PS} -script "{abc}" -liberty {LIBERTY}'
        )
    flow = f"""\
plugin -i {SLANG}
read_liberty -lib {LIBERTY}
read_slang --std 1800-2017 --single-unit --top {TOP} --keep-hierarchy --no-proc -j 1 -W no-implicit-port-type-mismatch -F {flist}
hierarchy -check -top {TOP}
{PROC_PASSES}
{tieoffs}opt
memory_collect
opt_clean
setattr -set fsm_encoding "auto" w:*state_q
fsm
opt
techmap
opt
dfflibmap -liberty {LIBERTY}
{map_command}
clean
check -assert
tee -q -o mapped-stat.json stat -json -liberty {LIBERTY}
tee -q -o mapped-hier-stat.json stat -top {TOP} -hierarchy -json -liberty {LIBERTY}
tee -o mapped-stat.txt stat -liberty {LIBERTY}
write_verilog -noattr -noexpr mapped-netlist.v
"""
    path.write_text(flow, encoding="utf-8")


def run_yosys(flow: Path, work_dir: Path, timeout: int) -> dict[str, Any]:
    command = [str(YOSYS), "-Q", "-s", str(flow)]
    started_at = timestamp()
    started = time.time()
    completed = subprocess.run(
        command, cwd=work_dir, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout,
    )
    elapsed = round(time.time() - started, 1)
    completed_at = timestamp()
    log_path = work_dir / "yosys.log"
    log_path.write_text(completed.stdout, encoding="utf-8")
    stat_path = work_dir / "mapped-stat.json"
    hier_stat_path = work_dir / "mapped-hier-stat.json"
    hierarchical_stat: dict[str, Any] = {}
    hierarchical_top: dict[str, Any] = {}
    if hier_stat_path.is_file():
        hierarchical_stat = json.loads(
            hier_stat_path.read_text(encoding="utf-8")
        )
        modules = hierarchical_stat.get("modules", {})
        hierarchical_top = modules.get(f"\\{TOP}", {})
        require(hierarchical_top,
                f"hierarchical stat has no top module {TOP}")

    def stat_metric(field: str, metric: str) -> Any:
        value = hierarchical_top.get(field, {})
        if not isinstance(value, dict):
            return None
        return value.get(metric)

    delay_matches = [
        float(value) for value in re.findall(
            r"Delay =\s*([\d.]+) ps", completed.stdout
        )
    ]
    target_failures = re.findall(
        r"Cannot meet the target required times \(([\d.]+)\)",
        completed.stdout,
    )
    return {
        "command": command_text(command),
        "return_code": completed.returncode,
        "run_started_at": started_at,
        "run_completed_at": completed_at,
        "elapsed_s": elapsed,
        "log": str(log_path),
        "log_sha256": sha256_file(log_path),
        "mapped_stat": str(stat_path),
        "mapped_stat_sha256": sha256_file(stat_path) if stat_path.is_file() else None,
        "mapped_hier_stat": str(hier_stat_path),
        "mapped_hier_stat_sha256": sha256_file(hier_stat_path)
        if hier_stat_path.is_file() else None,
        "hierarchical_stat_schema": hierarchical_stat.get("invocation"),
        "hierarchical_top_cell_count": stat_metric("num_cells", "count"),
        "hierarchical_top_cell_area": stat_metric("num_cells", "area"),
        "hierarchical_top_sequential_area": stat_metric(
            "sequential_area", "area"
        ),
        # Preserved hierarchy can make ABC print one stime result per mapped
        # module.  Use the worst reported local delay, not an assumed last
        # line and not a cross-hierarchy STA path.
        "critical_delay_ps": max(delay_matches) if delay_matches else None,
        "timing_delay_samples_ps": delay_matches,
        "abc_target_failure_ps": float(target_failures[-1]) if target_failures else None,
    }


def tool_provenance() -> dict[str, Any]:
    return {
        "yosys": {
            "path": str(YOSYS), "sha256": sha256_file(YOSYS),
            "version": subprocess.run(
                [str(YOSYS), "-V"], check=True, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            ).stdout.strip(),
        },
        "slang_plugin": {"path": str(SLANG), "sha256": sha256_file(SLANG)},
        "liberty": {"path": str(LIBERTY), "sha256": sha256_file(LIBERTY)},
        "bender": {
            "path": str(BENDER), "sha256": sha256_file(BENDER),
            "version": subprocess.run(
                [str(BENDER), "--version"], check=True, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            ).stdout.strip(),
        },
    }


def parse_required_stat(record: dict[str, Any], label: str) -> None:
    require(record["return_code"] == 0, f"{label}: Yosys failed")
    require(record["hierarchical_top_cell_count"] is not None,
            f"{label}: hierarchical top cell count missing")
    require(record["hierarchical_top_cell_area"] is not None,
            f"{label}: hierarchical top area missing")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-formal", action="store_true",
                        help="run the two matched synthesis configurations")
    parser.add_argument(
        "--output", type=Path,
        default=SCRIPT_DIR / "formal",
    )
    parser.add_argument(
        "--log-root", type=Path,
        default=SCRIPT_DIR / "logs",
    )
    parser.add_argument(
        "--work-root", type=Path,
        default=ROOT / "work-artifacts" / "work-phase6-integrated-synth",
    )
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()

    audit = worktree_audit()
    plan = {
        "top": TOP,
        "configs": [
            {"name": name, "kind": kind, "baseline_reference": BASELINE_REF}
            for name, kind in CONFIGS
        ],
        "bender_command": command_text([
            str(BENDER), "script", "flist-plus", "-t", "rtl", "-t", "spatz",
            "-D", "COMMON_CELLS_ASSERTS_OFF", "-D", "BUF_FPU", "-D",
            "TARGET_SYNTHESIS", "-D", "ONLINE_MERGE_MIXED_RECIPROCAL",
        ]),
        "yosys": str(YOSYS),
        "slang_plugin": str(SLANG),
        "liberty": str(LIBERTY),
        "timing_target_ps": TIMING_TARGET_PS,
        "clock_constraint": "none; ABC -D target is a mapping target, not an SDC clock",
        "audit": audit,
    }
    if not args.execute_formal:
        print("PLAN ONLY: no synthesis process or formal output was created")
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    require(audit["clean"], "refusing formal synthesis from dirty worktree")
    require(BENDER.is_file(), f"missing Bender: {BENDER}")
    require(YOSYS.is_file(), f"missing Yosys: {YOSYS}")
    require(SLANG.is_file(), f"missing Slang plugin: {SLANG}")
    require(LIBERTY.is_file(), f"missing Liberty: {LIBERTY}")
    require(SRAM_BLACKBOX.is_file(), f"missing SRAM blackbox: {SRAM_BLACKBOX}")
    require(not args.output.exists() or not any(args.output.iterdir()),
            "refusing non-empty formal output directory")
    formal_labels = {
        f"{name}_{flow_kind}"
        for name, _kind in CONFIGS
        for flow_kind in ("area", "timing")
    }
    for label in formal_labels:
        stale_log_dir = args.log_root / label
        require(not stale_log_dir.exists() or
                not any(stale_log_dir.iterdir()),
                f"refusing stale synthesis log directory: {stale_log_dir}")
    require(not args.work_root.exists() or not any(args.work_root.iterdir()),
            "refusing stale synthesis work directory")

    args.output.mkdir(parents=True, exist_ok=True)
    args.log_root.mkdir(parents=True, exist_ok=True)
    args.work_root.mkdir(parents=True, exist_ok=True)
    overlay = materialize_overlay(args.output / "baseline_source_overlay")
    smu_flist_meta = write_flist(args.output / "smu_cluster.f", False, overlay)
    baseline_flist_meta = write_flist(
        args.output / "baseline_cluster.f", True, overlay
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "phase6-p0-1-integrated-spatz-cost-formal",
        "status": "in_progress",
        "collection_started_at": timestamp(),
        "collection_completed_at": None,
        "area_unit": "um^2",
        "area_definition": "instance-weighted hierarchical top mapped Nangate45 standard-cell Liberty area rooted at spatz_cluster_wrapper; blackboxed SRAM macro area excluded",
        "git": audit,
        "top": TOP,
        "cluster_module": "spatz_cluster",
        "cluster_instance": "spatz_cluster_wrapper.i_cluster",
        "smu_instance": f"{SMU_MODULE}.i_online_merge_update_engine",
        "baseline_reference": BASELINE_REF,
        "baseline_overlay_files": list(BASELINE_OVERRIDES),
        "matched_non_smu_carry_forward": {
            "file": "hw/system/spatz_cluster/src/spatz_cluster.sv",
            "line_semantics": "tcdm_req[TcdmPortsOffs+j].q.user.req_id = '0",
            "reason": "957667e introduced this unrelated core TCDM request-ID tieoff in the same commit; the baseline overlay restores the current value so only SMU integration differs",
        },
        "flists": {
            "baseline": baseline_flist_meta,
            "smu": smu_flist_meta,
        },
        "toolchain": tool_provenance(),
        "flow": {
            "read_slang": "--std 1800-2017 --single-unit --keep-hierarchy --no-proc -j 1",
            "slang_load": f"plugin -i {SLANG}",
            "proc_passes": PROC_PASSES.splitlines(),
            "area_map": "abc -fast -liberty Nangate45_typ.lib",
            "area_stat": "stat -top spatz_cluster_wrapper -hierarchy -json -liberty Nangate45_typ.lib; top num_cells.area is instance-weighted across retained hierarchy",
            "timing_map": {
                "target_ps": TIMING_TARGET_PS,
                "script": ABC_TIMING_SCRIPT.format(target=TIMING_TARGET_PS),
            "proxy": "maximum local ABC stime post-map delay across reported mapped modules; no clock/IO constraints or cross-hierarchy STA",
            },
            "sram_assumption": str(SRAM_BLACKBOX),
            "hierarchy_policy": "keep hierarchy; no full-cluster flatten",
        },
        "runs": [],
    }

    def save_manifest() -> None:
        (args.output / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    save_manifest()
    results: dict[str, dict[str, Any]] = {}
    try:
        for name, kind in CONFIGS:
            flist = (
                args.output / "baseline_cluster.f"
                if kind == "baseline" else args.output / "smu_cluster.f"
            )
            for flow_kind in ("area", "timing"):
                label = f"{name}_{flow_kind}"
                run_dir = args.work_root / label
                log_dir = args.log_root / label
                run_dir.mkdir(parents=True, exist_ok=True)
                log_dir.mkdir(parents=True, exist_ok=True)
                flow_path = run_dir / "flow.ys"
                render_flow(flow_path, flist, flow_kind, kind)
                record = run_yosys(flow_path, run_dir, args.timeout)
                # Keep a copy in the experiment directory for direct log
                # provenance without making the runner rely on symlinks.
                log_copy = log_dir / "yosys.log"
                log_copy.write_bytes((run_dir / "yosys.log").read_bytes())
                hier_stat_copy = log_dir / "mapped-hier-stat.json"
                hier_stat_copy.write_bytes(
                    (run_dir / "mapped-hier-stat.json").read_bytes()
                )
                record.update({
                    "name": name,
                    "kind": kind,
                    "flow_kind": flow_kind,
                    "flow": str(flow_path),
                    "flow_sha256": sha256_file(flow_path),
                    "log_copy": str(log_copy),
                    "log_copy_sha256": sha256_file(log_copy),
                    "hier_stat_copy": str(hier_stat_copy),
                    "hier_stat_copy_sha256": sha256_file(hier_stat_copy),
                })
                manifest["runs"].append(record)
                save_manifest()
                parse_required_stat(record, label)
                results[label] = record

        rows = []
        baseline_area = float(
            results["Spatz_Baseline_area"]["hierarchical_top_cell_area"]
        )
        smu_area = float(
            results["Spatz_Mixed_SMU_area"]["hierarchical_top_cell_area"]
        )
        baseline_timing = results["Spatz_Baseline_timing"]["critical_delay_ps"]
        smu_timing = results["Spatz_Mixed_SMU_timing"]["critical_delay_ps"]
        require(baseline_timing is not None and smu_timing is not None,
                "ABC timing proxy did not emit a critical delay for both cases")
        for name, area, timing in (
            ("Spatz Baseline", baseline_area, float(baseline_timing)),
            ("Spatz + Mixed SMU", smu_area, float(smu_timing)),
        ):
            incremental = "" if name == "Spatz Baseline" else smu_area - baseline_area
            overhead = "" if name == "Spatz Baseline" else (
                (smu_area - baseline_area) / baseline_area * 100.0
            )
            timing_change = "" if name == "Spatz Baseline" else (
                (smu_timing - baseline_timing) / baseline_timing * 100.0
            )
            rows.append({
                "configuration": name,
                "area": area,
                "area_unit": "um^2",
                "area_stat_scope": "instance-weighted hierarchical top rooted at spatz_cluster_wrapper",
                "incremental_area": incremental,
                "area_overhead_percent": overhead,
                "timing_proxy_ps": timing,
                "timing_change_percent": timing_change,
                "area_flow": "abc -fast",
                "timing_flow": f"abc -D {TIMING_TARGET_PS} + stime",
            })
        with (args.output / "synthesis_comparison.csv").open(
            "w", newline="", encoding="utf-8"
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        manifest["status"] = "complete"
        manifest["collection_completed_at"] = timestamp()
        manifest["artifacts"] = ["synthesis_comparison.csv", "manifest.json"]
        manifest["comparison"] = rows
        save_manifest()
    except Exception:
        manifest["status"] = "failed"
        save_manifest()
        raise
    print(f"formal integrated synthesis complete: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
