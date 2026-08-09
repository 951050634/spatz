# P13 — Full-Offload Ablation 收尾（Full SMU 冻结为 ablation reference）

回答规划 P13 的三个问题（数据来自 P2 scaling model、P4/P5 面积、P9–P11）：

1. **Full 是否降低 recurrence cost？——是。**
   Full 的 Cs = 19.32 cycles/row，远低于 B2R 的 1594.23（软件 recurrence）；
   与 Proposed 的 90.28 相比，Full 把 per-row recurrence 再降约 4.7×。

2. **Full vector path 是否比 RVV vector path 高效？——当前结果显示不是。**
   Full 的 Cv = 8.03 cycles/element，高于 RVV（B2R/Proposed）的 2.09/2.13。
   Full-Offload 用自建 vector datapath 替换 RVV 时，每 element 的更新代价反而
   上升约 3.8×。结果：Full 在三个 workload 上 derived throughput（9.05
   MElements/s geomean）低于 Proposed（21.72），仅约 2.0× over B2R，而
   Proposed 为 4.81×（exact geomean 4.806510911×）。

3. **Full vector path 需要多少额外硬件？——约 +48.8% standalone mapped area。**
   Full 相对 Scalar 的增量 = 114,713.3 − 77,103.3 = 37,610.0 Liberty units
   （P4/P5，模块分解见 `P4_P5_STANDALONE_AREA.md`；cluster-level area unavailable，见 P6）。

**结论**：Full-Offload 是合理的 ablation 对照——它证明"全核 offload"的瓶颈不在
recurrence（Cs 已极低）而在 vector update datapath（Cv 高）与额外面积；而
Selective scalar offloading（Proposed = Scalar SMU + existing RVV）同时拿到
低 Cs（90.28）与低 Cv（2.13），面积最小。Full SMU 冻结，不再作为主要架构方向。
