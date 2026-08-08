# P14 / P15 — 微架构优化与 Power 决策

## P14 — 简单微架构优化：**当前不实施**

依据（P7 standalone timing）：
- Scalar SMU critical path（12.34 ns）落在 scalar control/datapath 组合逻辑，
  不在 EXP（4.07 ns）/ Recip（2.49 ns）LUT 上；专用算术单元是单周期组合 LUT
  且远低于整体 critical path。
- 没有 cluster-level timing 证据表明 SMU 会进入系统 critical path（P8：cluster
  综合工具链不可行，无法实测）。

因此按规划"除非发现非常明显的问题，否则不要重新设计 SMU"，当前**不做** pipeline
插入 / 控制 mux 简化 / exp 两路并行等改动。若未来获得 cluster 综合显示 SMU 成为
critical path，再评估最小 reg 插入；不作为本阶段工作。

## P15 — Power / Energy：**暂缓**

依据：post-synthesis netlist + workload activity 的 power flow 需要额外
（iEDA power / PrimeTime 类）工具链与活动因子提取，当前固定工具链成本高；规划
P15 明确"若工具链成本很高直接停止"。cycles + area + timing + throughput 已足够
支撑 TCAS-II 证据链，power 不阻塞论文结论。

CSV：`experiments/parsed/p16/p16_hardware_results.csv`。
