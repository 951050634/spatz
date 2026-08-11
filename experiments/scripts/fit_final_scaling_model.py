#!/usr/bin/env python3
"""Fit the frozen M2 scaling model and joint B2R/A1/Full crossovers.

Reuses the exact least-squares fit_model from
util/online_softmax_merge/analyze_scaling.py on the Sol-reviewed M2
matched-LUT scaling points.  Outputs the historical CSV schema consumed by
the existing Figure 2/3 scripts:

  experiments/parsed/final_scaling_model.csv
  experiments/reports/final_scaling_model.md
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from util.online_softmax_merge import analyze_scaling as scaling_math

CONFIGS = ("B2R_RVV", "A1_SMU_SCALAR", "A2_SMU_FULL")
SCALING_CSV = REPO_ROOT / "experiments/parsed/m2/m2_scaling.csv"
WORKLOAD_CSV = REPO_ROOT / "experiments/parsed/m2/m2_workloads.csv"
OUT_CSV = REPO_ROOT / "experiments/parsed/final_scaling_model.csv"
OUT_MD = REPO_ROOT / "experiments/reports/final_scaling_model.md"

WORKLOADS = (
    ("BERT", "model_bert_base_heads", 12, 64),
    ("Mistral", "model_mistral_7b_heads", 32, 128),
    ("Qwen14B", "model_qwen2_5_14b_heads", 40, 128),
)


def load_points(path: Path) -> dict[str, list[dict]]:
    points: dict[str, list[dict]] = {c: [] for c in CONFIGS}
    seen: set[tuple[str, int, int]] = set()
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            cfg = row["config"]
            if cfg not in CONFIGS:
                continue
            if row["kind"] != "point":
                continue
            n, d = int(row["N"]), int(row["D"])
            key = (cfg, n, d)
            if key in seen:
                continue
            seen.add(key)
            points[cfg].append({
                "case_id": row["case_id"],
                "N": n,
                "D": d,
                "cycles_median": int(float(row["measured_cycles"])),
            })
    for cfg in CONFIGS:
        points[cfg].sort(key=lambda p: (p["N"], p["D"]))
    return points


def fit_all(points: dict[str, list[dict]]) -> dict[str, dict]:
    return {cfg: scaling_math.fit_model(pts) for cfg, pts in points.items()}


def predicted(fit: dict, n: int, d: int) -> float:
    p = fit["parameters_cycles"]
    return p["C0"]["decimal"] + p["Cs"]["decimal"] * n + p["Cv"]["decimal"] * n * d


def crossover(a: dict, b: dict, n: int) -> float | None:
    """D such that C_a(N,D) == C_b(N,D); None when parallel or identical."""
    pa, pb = a["parameters_cycles"], b["parameters_cycles"]
    denom = (pa["Cv"]["decimal"] - pb["Cv"]["decimal"]) * n
    if denom == 0:
        return None
    value = -(pa["C0"]["decimal"] - pb["C0"]["decimal"]
              + (pa["Cs"]["decimal"] - pb["Cs"]["decimal"]) * n) / denom
    return value


def load_measured_workload(path: Path) -> dict[str, dict]:
    measured: dict[str, dict] = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            if row.get("disposition") != "MEASURED" or row.get("paper_eligible") != "YES":
                continue
            key = row["case_id"]
            measured[key] = {
                cfg: int(float(row[f"{cfg}_cycles"]))
                for cfg in CONFIGS
            }
    return measured


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--require-clean", action="store_true")
    args = ap.parse_args()

    if args.require_clean:
        import subprocess
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        if status.stdout.strip():
            print("worktree not clean; refusing to emit final model")
            return 1

    points = load_points(SCALING_CSV)
    fits = fit_all(points)
    measured_workloads = load_measured_workload(WORKLOAD_CSV)

    pairs = (
        ("B2R_RVV", "A1_SMU_SCALAR"),
        ("A1_SMU_SCALAR", "A2_SMU_FULL"),
        ("B2R_RVV", "A2_SMU_FULL"),
    )
    crossover_rows = []
    for n in (1, 2, 4, 8, 16, 32):
        for x, y in pairs:
            d = crossover(fits[x], fits[y], n)
            crossover_rows.append({
                "x": x, "y": y, "N": n,
                "D_crossover": None if d is None or d <= 0 else d,
            })

    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["kind", "config", "N", "D", "C0", "Cs", "Cv", "R_squared",
                    "measured_cycles", "fitted_cycles", "Cstall_cycles",
                    "crossover_pair", "crossover_D", "workload", "note"])
        for cfg in CONFIGS:
            fit = fits[cfg]
            p = fit["parameters_cycles"]
            w.writerow(["parameter", cfg, "", "",
                        f"{p['C0']['decimal']:.17g}",
                        f"{p['Cs']['decimal']:.17g}",
                        f"{p['Cv']['decimal']:.17g}",
                        f"{fit['R_squared']['decimal']:.12f}",
                        "", "", "", "", "", "", ""])
        for cfg in CONFIGS:
            fit = fits[cfg]
            for pt in points[cfg]:
                res = next(
                    r for r in fit["residuals"]
                    if r["N"] == pt["N"] and r["D"] == pt["D"])
                w.writerow(["point", cfg, pt["N"], pt["D"],
                            "", "", "", "",
                            pt["cycles_median"],
                            f"{res['fitted_cycles']['decimal']:.6f}",
                            f"{res['Cstall_cycles']['decimal']:.6f}",
                            "", "", "", ""])
        for row in crossover_rows:
            w.writerow(["crossover", "", row["N"], "", "", "", "", "",
                        "", "", "", f"{row['x']} vs {row['y']}",
                        "" if row["D_crossover"] is None
                        else f"{row['D_crossover']:.3f}", "", ""])
        for name, key, n, d in WORKLOADS:
            if key not in measured_workloads:
                continue
            for cfg in CONFIGS:
                pred = predicted(fits[cfg], n, d)
                meas = measured_workloads[key][cfg]
                w.writerow(["workload", cfg, n, d, "", "", "", "",
                            meas, f"{pred:.1f}", f"{meas - pred:.1f}",
                            "", "", name, ""])

    lines = []
    lines.append("# Final Scaling Model (M3 frozen M2 evidence)")
    lines.append("")
    lines.append("来源：Sol 审查通过的 M2 matched-LUT 正式数据 "
                 "（`experiments/parsed/m2/m2_scaling.csv`、"
                 "`experiments/parsed/m2/m2_workloads.csv`）。每条 `(N,D)` 使用 M2 "
                 "正式 measured cycle row；拟合形式 `C(N,D) = C0 + Cs·N + Cv·N·D`，"
                 "复用 `analyze_scaling.fit_model`（精确最小二乘）。")
    lines.append("")
    lines.append("## 拟合参数")
    lines.append("")
    lines.append("| Design | Points | C0 | Cs / row | Cv / element | R² |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for cfg in CONFIGS:
        fit = fits[cfg]
        p = fit["parameters_cycles"]
        lines.append(
            f"| {cfg} | {fit['fit_point_count']} | {p['C0']['decimal']:.2f} | "
            f"{p['Cs']['decimal']:.2f} | {p['Cv']['decimal']:.3f} | "
            f"{fit['R_squared']['decimal']:.9f} |")
    lines.append("")
    lines.append("## 解释")
    lines.append("")
    a1 = fits["A1_SMU_SCALAR"]["parameters_cycles"]
    b2r = fits["B2R_RVV"]["parameters_cycles"]
    full = fits["A2_SMU_FULL"]["parameters_cycles"]
    lines.append(
        f"- Proposed A1：`Cs = {a1['Cs']['decimal']:.6f}` cycles/row，"
        f"相对 B2R 的 `{b2r['Cs']['decimal']:.6f}` 降低 "
        f"`{b2r['Cs']['decimal'] / a1['Cs']['decimal']:.6f}×`（SMU-like）。")
    lines.append(
        f"- Proposed A1：`Cv = {a1['Cv']['decimal']:.6f}` cycles/element，"
        f"与 B2R 的 `{b2r['Cv']['decimal']:.6f}` 基本一致（RVV-like），"
        f"而 Full 的 `{full['Cv']['decimal']:.6f}` 更高。")
    lines.append(
        f"- 即 `Cs(A1) ≈ SMU-like` 且 `Cv(A1) ≈ RVV-like`，验证了 "
        "Selective scalar offloading 的执行边界。")
    lines.append("")
    lines.append("## Crossover（拟合模型求解 C_X = C_Y）")
    lines.append("")
    lines.append("| Pair | N | D_crossover |")
    lines.append("| --- | ---: | ---: |")
    for n in (1, 2, 4, 8, 16, 32):
        for x, y in pairs:
            row = next(r for r in crossover_rows
                       if r["x"] == x and r["y"] == y and r["N"] == n)
            d = row["D_crossover"]
            lines.append(f"| {x} vs {y} | {n} | "
                         + ("—" if d is None else f"{d:.1f}") + " |")
    lines.append("")
    lines.append("## Model-derived workload 预测 vs 实测（M2）")
    lines.append("")
    lines.append("| Workload | N | D | Config | 实测 cycles | 模型预测 | 残差 |")
    lines.append("| --- | ---: | ---: | --- | ---: | ---: | ---: |")
    for name, key, n, d in WORKLOADS:
        if key not in measured_workloads:
            continue
        for cfg in CONFIGS:
            pred = predicted(fits[cfg], n, d)
            meas = measured_workloads[key][cfg]
            lines.append(f"| {name} | {n} | {d} | {cfg} | {meas} | "
                         f"{pred:.0f} | {meas - pred:+.0f} |")
    lines.append("")
    lines.append("## 数据文件")
    lines.append("")
    lines.append("- CSV：`experiments/parsed/final_scaling_model.csv`")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT_CSV}")
    print(f"wrote {OUT_MD}")
    for cfg in CONFIGS:
        p = fits[cfg]["parameters_cycles"]
        print(f"{cfg}: C0={p['C0']['decimal']:.2f} Cs={p['Cs']['decimal']:.2f} "
              f"Cv={p['Cv']['decimal']:.3f} R2={fits[cfg]['R_squared']['decimal']:.9f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
