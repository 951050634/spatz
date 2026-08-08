# P8 — Cluster-Level Timing（工具链受限，standalone Fmax 口径）

## 目标与约束

P8-1/2/3 需要 Baseline / Scalar / Full 的 cluster-level `T_critical` / Fmax。
与 P6 相同，完整 `spatz_cluster` 无法用固定工具链（Yosys + `read_slang` +
Nangate45）读入（AXI / register_interface 的 `parameter type` 成员访问在
standalone elaboration 下报错，见 `work-p6/elab_cluster.log`），因此
**cluster-level timing 无法实测**。

## 采用的频率口径（P9–P11 依据）

- Proposed（Scalar SMU cluster）可达到频率估计：**81.02 MHz**（standalone SMU
  Fmax，pre-layout ABC `stime`，P7）。
- Full（Full SMU cluster）：**75.74 MHz**（P7）。
- Baseline Spatz cluster 频率：仓库无 cluster 综合，**未测量**；P9–P11 主表采用
  iso-frequency 口径（三设计同用 81.02 MHz），使 latency 差异只反映 cycle
  差异（架构效果），与 Fmax 差异分开报告。Full 若按其自身 75.74 MHz 运行，
  latency 会比 iso-freq 表再高约 6.97%（= 81.02/75.74 − 1）。

## 结论

- 无法声称"Scalar SMU 不进入 cluster critical path"（需要真实 cluster 综合）；
  只能报告 standalone SMU critical path 在 scalar control/datapath、不在
  EXP/RECIP LUT（P7），以及 SMU 自身 Fmax ≈ 81 MHz 高于 Full 的 75.7 MHz。
- 论文口径建议：报告 standalone Fmax 作为 SMU 可达到频率上界，并明确标注
  pre-layout、无 clock tree/routing 的 ABC 估计性质。
