# TCAS-II 后续工程任务规划：Online Softmax Merge

> 本文件把后续工程阶段冻结为一份总任务清单。目标不是继续证明"代码能够正确运行"，
> 而是围绕 **Proposed Scalar SMU** 补齐架构、性能、面积、时序和性能/面积效率证据。
> 执行时以本文件为唯一任务来源，按"最终执行顺序"推进。

## 0. 总体目标

回答 TCAS-II 审稿人最关心的四个问题：

1. 为什么 Online Softmax Merge 需要专用硬件？
2. Scalar SMU 到底解决了哪一个硬件瓶颈？
3. 为什么 Scalar SMU + RVV 比 Full SMU 更合理？
4. 为了这些性能收益，需要付出多少面积和时序代价？

核心证据链：

```text
RVV baseline
    │
    │ recurrence 软件开销大
    ↓
Scalar SMU
    │
    │ 显著降低 per-row cost
    ↓
Scalar SMU + RVV
    │
    │ 低 Cs + 低 Cv
    ↓
比 Full SMU 更快
    │
    │ 同时 Full SMU 增加 vector datapath
    ↓
更高面积 + 更差 scaling
    │
    ↓
Selective Offloading 是最佳执行边界
```

---

## P1. 冻结最终 Proposed Architecture

### P1-1 明确最终论文方案

从本阶段开始固定：

```text
Proposed Design = Scalar SMU + existing RVV
```

即现在的 `A1_SMU_SCALAR`。角色冻结：

| 名称 | 角色 |
| --- | --- |
| B1_SCALAR | Scalar Reference：SW recurrence + scalar vector update |
| B2R_RVV | RVV Software Baseline：SW recurrence + RVV vector update |
| PROPOSED / A1 | Scalar SMU + RVV：SMU recurrence + RVV vector update |
| FULL / A2 | Full-Offload Ablation：SMU recurrence + SMU vector update |

工程工作：不修改算法功能，只在论文分析层建立 A1 = proposed、A2 = full-offload
ablation 的对应关系。不要重新设计配置框架、不要大规模重构 runner、不要删除已有
A1/A2 名称导致历史结果失效。

### 验收

形成一份非常简单的最终配置说明。后续所有新实验默认围绕 B2R / PROPOSED / FULL
三者展开。

---

## P2. 补齐 Proposed A1 的 Scaling Model（最高优先级性能实验）

已有模型：

```text
B2R:  C(N,D) = 153.5 + 1594.2·N + 2.09·N·D
FULL: C(N,D) = 1285.6 + 19.3·N + 8.03·N·D
```

Proposed A1 还缺正式模型。

### P2-1 提取 A1 scaling 数据

从已完成 P0-4 scaling 数据中提取所有 `A1_SMU_SCALAR / paper-eligible / PASS /
scaling` 记录。三次 trial 完全一致，因此每个 `(N,D)` 只取一条确定 cycle value，
不把重复当多个拟合样本。

### P2-2 拟合模型

统一采用 `C(N,D) = C0 + Cs·N + Cv·N·D`，得到 A1 的 C0 / Cs / Cv / R²。

### P2-3 与 B2R / FULL 联合解释

| Design | C0 | Cs / row | Cv / element |
| --- | ---: | ---: | ---: |
| B2R | 153.5 | 1594.2 | 2.09 |
| Proposed A1 | 待测 | 待测 | 待测 |
| Full A2 | 1285.6 | 19.3 | 8.03 |

最期待看到：`Cs(A1) ≪ Cs(B2R)` 且 `Cv(A1) ≈ Cv(B2R)`，即

```text
A1 Cs ≈ SMU-like
A1 Cv ≈ RVV-like
```

### P2-4 重新计算 crossover

分别研究 B2R vs Proposed、Proposed vs FULL、B2R vs FULL，从拟合模型求
`C_X(N,D) = C_Y(N,D)` 的理论 crossover。重点确认 Proposed 与 FULL 的
crossover 是否存在、极小 D 时谁更好、从什么时候起 Proposed 更好。

### 输出

```text
experiments/reports/final_scaling_model.md
experiments/parsed/final_scaling_model.csv
```

### 验收

三个配置都有模型；R² 足够高；实测点和模型预测一致；能清楚解释 A1 为什么快。

---

## P3. Scalar SMU 微架构性能分解

### P3-1 内部 latency 分解

记录一次典型 recurrence 的内部阶段（名称以 RTL FSM 为准）：

```text
command accept → max/delta → exp_old → exp_tile → l update →
reciprocal → weight generation → writeback → done
```

### P3-2 记录每阶段 cycle

| Stage | Cycles |
| --- | ---: |
| command/decode | x |
| max/delta | x |
| exponential | x |
| l update | x |
| reciprocal | x |
| weight generation | x |
| writeback | x |
| total | x |

不要求每阶段独立占一个 FSM state，可根据 FSM、valid/ready、internal counter 计算。

### P3-3 找内部真正 bottleneck

回答：SMU 内部哪部分最耗周期（EXP / RECIPROCAL / WRITEBACK，或整个 recurrence
已经很短）。如果 exp + reciprocal 只占几十周期而 software recurrence 是上千周期，
论文结论非常清晰：specialized arithmetic + tightly coupled control 消除了软件指令
序列开销。

### P3-4 不要过度优化

本阶段目的是解释现有设计。除非发现非常明显的问题（例如一个完全不必要的 10-cycle
wait），否则不要重新设计 SMU；尤其不要重写 exp / reciprocal、大规模 pipeline、
为省几周期破坏现有验证结果。

### 验收

给出一张简洁的 Scalar SMU latency breakdown 图或表。

---

## P4. Standalone SMU 综合

定义三个硬件综合配置：

| Config | 内容 |
| --- | --- |
| H0 | No SMU（概念 reference，可无实际逻辑） |
| H1 — Proposed Scalar SMU | command/control、scalar recurrence datapath、exp、reciprocal、weight generation、scalar writeback；不含 Full vector update datapath |
| H2 — Full SMU | H1 + vector update datapath |

---

## P5. 统一综合 Area

### P5-1 固定同一 synthesis flow

继续采用已有 Nangate45 / Yosys / ABC。三个配置必须：相同 Liberty、相同 synthesis
options、相同 hierarchy policy、相同 ABC flow。不要换库。

### P5-2 输出 standalone SMU area

| Config | Cells | Mapped Area |
| --- | ---: | ---: |
| Scalar SMU | ... | ... |
| Full SMU | ... | ... |

已有参考值：Scalar ≈ 77,103；Full ≈ 114,713（继续确认即可）。

### P5-3 输出模块面积分解

按 RTL hierarchy 分模块（control/FSM、exp、reciprocal、scalar arithmetic、
registers、interface；Full 额外 vector datapath），形成：

| Module | Area | % |
| --- | ---: | ---: |
| EXP | ... | ... |
| Reciprocal | ... | ... |
| Scalar control | ... | ... |
| Vector path | ... | ... |

目的：解释为什么 Full SMU 面积更高，而不是只给 "+49%"。

### P5-4 不要求非常细

如果 Yosys hierarchy 已被 flatten、无法轻松得到精确模块面积，不要为此重构 RTL，
可用 scope synthesis proxy 辅助说明。重点仍是 Scalar vs Full。

---

## P6. Cluster-Level Area Overhead（TCAS-II 值得补的关键表）

| Step | 配置 | 产出 |
| --- | --- | --- |
| P6-1 | C0_CLUSTER：Spatz cluster without SMU | A_base |
| P6-2 | C1_CLUSTER_SCALAR_SMU：Spatz + Scalar SMU | A_scalar，Overhead_scalar = (A_scalar − A_base) / A_base |
| P6-3 | C2_CLUSTER_FULL_SMU | A_full，Overhead_full = (A_full − A_base) / A_base |

同一 memory setup、同一 core/vector configuration。

最终核心表：

| Design | Cluster Area | Overhead |
| --- | ---: | ---: |
| Baseline Spatz | A0 | – |
| + Scalar SMU | A1 | +x% |
| + Full SMU | A2 | +y% |

这张表比 standalone 77k / 115k 更重要。

---

## P7. Timing 与 Fmax

### P7-1 standalone SMU timing

对 Scalar SMU / Full SMU，相同 library 和 corner，提取 critical path delay，
`Fmax = 1 / T_critical`。

| Design | Critical Delay | Fmax |
| --- | ---: | ---: |
| Scalar SMU | ... ns | ... MHz |
| Full SMU | ... ns | ... MHz |

### P7-2 记录 critical path 内容

至少保存 startpoint、endpoint、logic path、delay，并分类：Scalar 可能落在
EXP / RECIP / weight arithmetic / control；Full 可能落在 vector arithmetic /
vector address / memory interface。

---

## P8. Cluster-Level Timing（比 standalone Fmax 更重要）

- P8-1：Baseline cluster → T_base、F_base、critical path；
- P8-2：Scalar SMU cluster → T_scalar、F_scalar，判断加入 SMU 后 Fmax 是否下降；
- P8-3：Full SMU cluster → T_full、F_full；
- P8-4：分析三种结果。

最理想：Baseline 与 Scalar 的 critical path 都是 existing Spatz path，即 Scalar
SMU 不进入系统 critical path。若 Scalar SMU 自身成为 critical path 也直接报告，
此时才考虑简单插入一级 pipeline，且仅当 timing penalty 明显且修复非常简单时修改。
不要为追求漂亮 Fmax 大规模重构。

---

## P9. 将 Cycle 转换成真实 Hardware Latency

`Latency = C / f`。优先使用 cluster-level achievable frequency（Proposed 用
f_scalar-cluster，Full 用 f_full-cluster），不要用 standalone SMU frequency。

典型 workload 只选正文需要的点：

```text
(8,32)
(16,64)
BERT
Mistral
Qwen2.5-14B
```

| Workload | Design | Cycles | Freq | Latency |
| --- | --- | ---: | ---: | ---: |
| BERT | B2R / Proposed / Full | ... | ... | ... |
| Mistral | B2R / Proposed / Full | ... | ... | ... |
| Qwen14B | B2R / Proposed / Full | ... | ... | ... |

---

## P10. Accelerator Throughput

统一吞吐指标：`Throughput = N·D / Latency = N·D·f / Cycles`（Merge Elements/s，
MElements/s）。不用 GOPS：Online Softmax Merge 不只是 MAC（max、exp、
reciprocal、normalization、FMA），换算 GOPS 会模糊。

---

## P11. Area Efficiency

`AreaEfficiency = Throughput / Area`，统一归一化到 MElements/s / normalized area。
Liberty area 不可靠换算 mm² 时，直接使用 throughput per mapped area，不叫
GOPS/mm²。

关键比较：AE(Proposed) vs AE(Full)。Proposed 更小 + 更快，area efficiency 应
明显更高——这是 TCAS-II 很欢迎的结果。

---

## P12. Hardware Performance–Area Trade-off

整合成论文核心图：横轴 Normalized mapped area（以 Proposed 或 baseline cluster
为 1），纵轴 Speedup over RVV 或 Throughput。比较 B2R / Proposed / Full，
B2R 使用 baseline cluster area。理想情况 Proposed 更左、更高。

---

## P13. Full-Offload Ablation 收尾

Full SMU 不再大规模开发，只回答三个问题：

1. Full 是否降低 recurrence cost？——是。
2. Full vector path 是否比 RVV vector path 高效？——当前结果显示不是。
3. Full vector path 需要多少额外硬件？——约 +49% standalone mapped area，并补
   cluster-level overhead。

完成后冻结 Full，它只是 ablation reference。

---

## P14. Proposed Scalar SMU 的简单微架构优化（可选）

只有 timing/area 结果出来后决定。检查 obvious bottleneck（exp path、reciprocal
path、weight generation、writeback、command handoff），寻找明显冗余 mux、
不必要长 combinational path、明显可并行的 independent operation。

允许的小优化：exp 两路并行、简化控制 mux、reciprocal 输入寄存、简单 pipeline
register、去掉 unused Full-only logic。

不做的优化：重新设计全新 EXP 单元、新增复杂 multi-stage scheduler、修改 RVV、
修改 ISA、大规模修改 TCDM、加入 multi-SMU、重写 entire FSM。卖点是 small
accelerator, good partitioning，不是 highly optimized giant accelerator。

---

## P15. Power / Energy（第二优先级）

Area / Timing / Latency / Throughput 全部完成后再判断。若工具链容易完成：
post-synthesis netlist + workload activity + Liberty power，输出 average power、
energy/merge、energy/element；workload 只做 BERT / Mistral / Qwen14B，不跑全
scaling matrix。若工具链成本很高直接停止，不为 power 大规模安装环境、修改 RTL
或重构 simulation flow。对当前论文 cycles + area + timing + throughput 比 power
更重要。

---

## P16. 最终 Hardware Result Table

所有工程结束后必须生成：

| Metric | Baseline Spatz | Proposed Scalar SMU | Full SMU |
| --- | ---: | ---: | ---: |
| Mapped cells | | | |
| Mapped area | | | |
| Cluster area overhead | – | | |
| Critical delay | | | |
| Fmax | | | |
| BERT latency | | | |
| Mistral latency | | | |
| Qwen14B latency | | | |
| Throughput | | | |
| Area efficiency | | | |

若做 power 再加 Power、Energy/merge。

---

## P17. 最终 Evaluation 图表

TCAS-II 正文最后只留 3–4 张真正有价值的结果图/表：

1. **Figure 1 — Proposed Architecture**：Software/Core → command → Scalar SMU
   （max / exp / l update / reciprocal / weight generation）→ weights → existing
   RVV → O[D] update。这是最重要的图。
2. **Figure 2 — Scaling Mechanism**：B2R / Proposed / Full 的 Cs、Cv 或 scaling
   curves。核心说明：B2R high Cs / low Cv；Full low Cs / high Cv；Proposed
   low Cs / low Cv。
3. **Table 1 — Model-Derived Performance**：只放 BERT / Mistral / Qwen，比较
   B2R / Proposed / Full，B1 弱化。
4. **Table/Figure 3 — Hardware Implementation**：area、area overhead、Fmax、
   throughput、performance/area，成为真正的 TCAS-II 硬件结果。

---

## P18. 论文结论支撑

最终不写"We designed a Softmax accelerator that achieves large speedup"，
而写：Online Softmax Merge 中真正值得专用化的是 state-dependent scalar
recurrence。证据：

- 软件分析：B2R 的 Cs ≈ 1594；
- 硬件分析：Scalar SMU 把 Cs 降到几十 cycles；
- vector 分析：RVV 的 Cv ≈ 2，Full 的 Cv ≈ 8；
- 性能：Proposed 在 model-derived workloads 上约 4.6–5× over RVV；
- 硬件：Proposed 只增加有限 cluster area overhead 并保持合理 Fmax；
- Full ablation：vector datapath 增加显著面积且性能低于 Proposed。

结论：Selective scalar offloading > Full kernel offloading。

---

## 最终执行顺序

```text
P1   冻结 Proposed = Scalar SMU + RVV
P2   拟合 Proposed A1 scaling model，得到 C0 / Cs / Cv
P3   Scalar SMU 内部 latency breakdown
P4–P5  整理 Scalar / Full standalone synthesis，面积 + 模块组成
P6   综合 baseline Spatz / Spatz+Scalar / Spatz+Full，得到 cluster-level area overhead
P7   Standalone SMU timing
P8   Cluster-level timing / Fmax / critical path
P9   cycles → real latency
P10  计算 throughput
P11  计算 throughput / area
P12  形成 performance-area trade-off
P13  冻结 Full-Offload ablation
P14  如 timing 显示明显问题，仅做轻量微架构优化
P15  有余力再做 Power / Energy
P16  生成最终 hardware result table
P17  生成 TCAS-II 核心图表
P18  进入正式论文写作
```

## 给执行模型的总原则

> 本阶段目标是量化和强化 Scalar SMU 加速器本身，而不是继续扩展实验基础设施。
> 优先复用现有脚本、RTL 和结果格式。除非直接阻塞目标实验，否则不要进行大规模
> 重构、兼容性封装、异常处理扩展、额外 runner gate 或防御性检查。每项任务应首先
> 完成最短可工作的实现，然后直接生成论文需要的性能、面积、时序或结构数据。
> Proposed Design 固定为 Scalar SMU + RVV，Full SMU 仅用于消融比较，不继续作为
> 主要架构开发方向。

## 配套文件

- 调用 goal 工具的提示词见 [GOAL_PROMPT.md](GOAL_PROMPT.md)。
- A1 三点 anchor 明细见 [A1标量卸载实验.md](A1标量卸载实验.md)。
