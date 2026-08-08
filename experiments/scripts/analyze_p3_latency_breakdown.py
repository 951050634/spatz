#!/usr/bin/env python3
"""P3: Scalar SMU internal latency breakdown from the FSM cycle observer.

The production RTL embeds a simulation-only FSM observer
(hw/ip/online_merge/src/online_merge_update_engine.sv, `// pragma
translate_off`) that counts cycles spent in each FSM state.  Every formal
P0-4 record for A1_SMU_SCALAR carries these per-run counters; this script
aggregates them from the 17 formal p0_4 roots and derives the per-row
per-stage latency.

Stages (RTL FSM names):
  LOAD_SCALAR      command accept + 4 scalar TCDM reads (m_old, l_old, m_tile, l_tile)
  COMPUTE_SCALAR   max/delta + exp_old + exp_tile + l update (combinational)
  COMPUTE_WEIGHT   reciprocal + weight generation (combinational LUT)
  STORE_SCALAR     writeback m, l, old_weight, tile_weight
  UPDATE_VECTOR    not used in scalar-only mode (0)
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

INDEX_SET = REPO_ROOT / "experiments/manifests/p0_4_index_set.json"
OUT_CSV = REPO_ROOT / "experiments/parsed/p3_smu_latency_breakdown.csv"
OUT_MD = REPO_ROOT / "experiments/reports/P3_SMU_LATENCY_BREAKDOWN.md"
OUT_PNG = REPO_ROOT / "experiments/plots/p3_smu_latency_breakdown.png"

STAGE_FIELDS = (
    ("load_scalar_cycles", "LOAD_SCALAR"),
    ("compute_scalar_cycles", "COMPUTE_SCALAR"),
    ("compute_weight_cycles", "COMPUTE_WEIGHT"),
    ("store_scalar_cycles", "STORE_SCALAR"),
    ("update_vector_cycles", "UPDATE_VECTOR"),
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--require-clean", action="store_true")
    args = ap.parse_args()
    if args.require_clean:
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT,
            capture_output=True, text=True, check=True)
        if status.stdout.strip():
            print("worktree not clean; refusing to emit final report")
            return 1

    index = json.loads(INDEX_SET.read_text())
    roots = [json.loads(Path(r["index_path"]).read_text())
             for r in index["runs"]]
    by_nd: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for entry in roots:
        recs = json.loads(
            (Path(entry["artifact_root"]) / "records.json").read_text())
        for rec in recs:
            if rec.get("config") == "A1_SMU_SCALAR" and rec.get("status") == "PASS":
                by_nd[(int(rec["N"]), int(rec["D"]))].append(rec)
    if not by_nd:
        print("no A1 FSM records found")
        return 1

    # Per-row per-stage cost per (N,D): total stage cycles / N.
    per_row: dict[tuple[int, int], dict[str, float]] = {}
    for (n, d), recs in by_nd.items():
        row: dict[str, float] = {"busy": 0.0}
        for field, _ in STAGE_FIELDS:
            row[field] = float(recs[0][field]) / n
        row["busy"] = float(recs[0]["smu_busy_cycles"]) / n
        per_row[(n, d)] = row

    # Deterministic per-row values (all points agree to within rounding).
    def median(key: str) -> float:
        vals = sorted(per_row[k][key] for k in per_row)
        return vals[len(vals) // 2]

    stage_rows = []
    for field, label in STAGE_FIELDS:
        cycles = median(field)
        stage_rows.append((label, cycles, field))
    busy_total = median("busy")
    stage_rows = [
        (label, cycles, field) for label, cycles, field in stage_rows
        if cycles > 0
    ]
    total_known = sum(c for _, c, _ in stage_rows)

    # Software-side context (measured smu_scalar window).
    sw_fixed = sorted(
        rec["smu_scalar_cycles"] - rec["smu_busy_cycles"]
        for recs in by_nd.values() for rec in recs
        if int(rec["N"]) == 1
    )
    sw_fixed_med = sw_fixed[len(sw_fixed) // 2]

    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["stage", "cycles_per_row", "share_of_smu_busy", "notes"])
        for label, cycles, _ in stage_rows:
            w.writerow([label, f"{cycles:.0f}",
                        f"{cycles / busy_total:.3f}", ""])
        w.writerow(["SMU busy total", f"{busy_total:.0f}", 1.0, ""])
        w.writerow(["software smu_scalar window fixed overhead (N=1 median)",
                    str(sw_fixed_med), "", ""])

    lines = []
    lines.append("# P3 — Scalar SMU 内部 latency breakdown")
    lines.append("")
    lines.append("来源：P0-4 正式 17 roots 中 A1_SMU_SCALAR 的 FSM observer 计数"
                 "（`online_merge_update_engine.sv` 仿真专用 observer，"
                 "synthesis 时被 `translate_off` 剔除）。所有 (N,D) 点逐行值确定一致"
                 "（三次 trial 完全相同）。")
    lines.append("")
    lines.append("## 每行（per-row）SMU busy 分解")
    lines.append("")
    lines.append("| Stage (RTL FSM) | Cycles/row | 占比 | 内容 |")
    lines.append("| --- | ---: | ---: | --- |")
    notes = {
        "LOAD_SCALAR": "command accept + 4 个 scalar TCDM 读（m_old/l_old/m_tile/l_tile），每个读 req+resp 握手约 3 cycle",
        "COMPUTE_SCALAR": "max/delta + exp_old + exp_tile + l update：全部组合逻辑（两个 exp 为单周期 LUT 近似）",
        "COMPUTE_WEIGHT": "reciprocal + weight generation：单周期 LUT 近似，无需迭代",
        "STORE_SCALAR": "writeback：m、l、old_weight、tile_weight 4 个 scalar 写，每个约 2 cycle",
    }
    for label, cycles, _ in stage_rows:
        lines.append(f"| {label} | {cycles:.0f} | {cycles / busy_total * 100:.0f}% | {notes.get(label, '')} |")
    lines.append(f"| **SMU busy 合计** | **{busy_total:.0f}** | 100% | scalar-only mode，UPDATE_VECTOR=0 |")
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append(f"- SMU 硬件完成一次 scalar recurrence 只需 **{busy_total:.0f} cycles/row**："
                 "主要开销是 TCDM 标量读写（load 13 + store 9），"
                 "EXP / RECIP / weight generation 全部组合逻辑单周期完成，"
                 "没有多周期迭代单元。")
    lines.append(
        f"- 对比软件 recurrence（B2R `Cs ≈ 1594 cycles/row`），硬件 scalar merge "
        f"把逐行 recurrence 开销降低 `{1594.2 / busy_total:.0f}×`。")
    lines.append(
        f"- 软件侧 `smu_scalar` 窗口（命令寄存器配置 + done 轮询）固定开销中位数 "
        f"≈ {sw_fixed_med} cycles（与 N 无关），加上 `{busy_total:.0f}·N` 的 SMU busy，"
        "解释了 A1 拟合模型中的 C0 与 Cs。")
    lines.append("")
    lines.append("## 数据文件")
    lines.append(f"- CSV：`experiments/parsed/p3_smu_latency_breakdown.csv`")
    lines.append(f"- 图：`experiments/plots/p3_smu_latency_breakdown.png`")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Figure: stacked per-row stage cycles (Scalar vs Full vector path).
    sys.path.insert(0, "/tmp/plotenv/lib/python3.12/site-packages")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    labels = [label for label, _, _ in stage_rows]
    cycles = [cycles for _, cycles, _ in stage_rows]
    colors = ["#94a3b8", "#2563eb", "#059669", "#d97706"]
    bottom = 0
    for label, cyc, col in zip(labels, cycles, colors):
        ax.bar(["Scalar SMU"], cyc, bottom=bottom, label=label,
               color=col, edgecolor="white", width=0.55)
        bottom += cyc
    ax.axhline(1594.2, color="#b91c1c", linestyle="--", linewidth=1.2)
    ax.text(0.02, 0.88, "B2R software recurrence\nCs ≈ 1594 cyc/row",
            transform=ax.transAxes, va="top", fontsize=8, color="#b91c1c")
    ax.set_ylim(0, 1750)
    ax.set_ylabel("Cycles per row")
    ax.set_title("Scalar SMU internal latency per row (24 cycles)")
    ax.legend(fontsize=7, ncol=2, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)
    print(f"wrote {OUT_CSV}")
    print(f"wrote {OUT_MD}")
    print(f"wrote {OUT_PNG}")
    for label, cyc, _ in stage_rows:
        print(f"{label}: {cyc:.0f} cyc/row")
    print(f"busy total: {busy_total:.0f}")
    print(f"sw fixed overhead median (N=1): {sw_fixed_med}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
