# P7 — Standalone SMU Timing 与 Fmax

来源：`experiments/scripts/run_p7_timing_synthesis.py`（`--collect-only` 从
`work-p7/p7runs/` 现有 run 重建 CSV）。flow 与 P0-6 完全相同（Nangate45 typical /
Yosys / ABC、同一 Liberty、同一 hierarchy policy），唯一差别是 P7 用 ABC 的
显式 timing-driven script（`strash; if -K 6; dretime; map -D <target>; &get -n;
&st; &dch; &nf; &put`）并以 ABC 的 post-map `stime` 提取 critical delay。

**口径（重要）**：`stime` 是 pre-layout、无 clock tree、无 routing、无 output
load 的 ABC 库延迟估计，不是 signoff STA。`work-p7/ieda_split.log` 记录 iEDA STA
无法读入 flatten 后的 Yosys netlist（parser/STA 缺陷，非本设计 netlist 问题），
因此这是固定工具链下能给出的最诚实 timing 来源。

## Standalone Timing

| Design | Cells | Mapped Area (此 flow) | Critical Delay | Fmax |
| --- | ---: | ---: | ---: | ---: |
| C1 — Scalar SMU | 59,910 | 66,264.058 | 12,342.85 ps (12.34 ns) | **81.02 MHz** |
| C2 — Full SMU | 91,361 | 101,978.548 | 13,202.60 ps (13.20 ns) | **75.74 MHz** |

critical path 均为 scalar control/datapath 逻辑：

- C1：`pi → AOI22_X1 → NAND3_X1 → OR3_X1 → NOR3_X1`
- C2：`pi → INV_X1 → NAND2_X1 → AOI22_X1 → AND2_X1`

## 专用算术模块的组合延迟（scope top，无寄存器 → 无 cycle time）

scope top 是纯组合（sequential_area = 0），`stime` 给出的是 input→output
组合延迟，不是 Fmax：

| Scope | Cells | Area | Combinational delay |
| --- | ---: | ---: | ---: |
| EXP LUT | 4,428 | 4,526.788 | 4,070.47 ps |
| Reciprocal LUT | 4,502 | 4,594.618 | 2,493.75 ps |
| Vector merge datapath | 44,114 | 46,019.596 | 6,930.62 ps |

## 面积口径说明

P7 的 timing-driven ABC script 得到的 mapped area（66.3k / 102.0k）低于 P0-6 的
`abc -fast` 面积 flow（77,103 / 114,713）。两个数字来自不同 ABC script，均合法。
**论文口径**：面积用 P0-6 的 3-trial 确定性结果（77,103 / 114,713），timing 用
P7 的 `stime`（12.34 ns / 13.20 ns）。

## 结论

- Scalar SMU standalone Fmax ≈ 81 MHz（pre-layout ABC），Full SMU ≈ 75.7 MHz；
  Full 的 vector datapath 使 critical delay 增加约 0.86 ns（+7.0%）。
- C1/C2 的 critical path 都落在 scalar control/datapath，不是 EXP/Recip LUT；
  EXP 4.07 ns、Recip 2.49 ns、vector merge 6.93 ns 均低于整体 critical path。
- 当前无需为 timing 做微架构优化：Exp/Recip 是单周期组合 LUT 且不在 critical
  path 上（P14 依据）。

## 数据文件
- CSV：`experiments/parsed/p7_timing/p7_timing.csv`
- 原始 run：`work-p7/p7runs/{C1_SCALAR,C2_FULL,SCOPE_*}_trial1/<target>ps/`
  （yosys.log、mapped-netlist.v、mapped-stat.json）
