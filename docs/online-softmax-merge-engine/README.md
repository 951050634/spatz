# Online Softmax Merge-Update Engine

本目录用于记录在 Spatz 平台上新增 online softmax merge 硬件旁路引擎的工程计划、阶段成果和 Git 状态。

目标分支：

```text
feature/online-softmax-merge-engine
```

文档说明：

- [PLAN.md](PLAN.md)：完整实施流程、阶段节点、目标和验收标准。
- [PHASE_RESULTS.md](PHASE_RESULTS.md)：各阶段执行结果、证据和备注记录。
- [GIT_NOTES.md](GIT_NOTES.md)：分支状态、提交策略和 Git 操作记录。
- [COMPARISON_EXPERIMENT.md](COMPARISON_EXPERIMENT.md)：CPU scalar path 与
  merge engine path 的 A/B 对比实验、原始数据和评估结论。
- [PAPER_ROADMAP.md](PAPER_ROADMAP.md)：受限语义原型论文和完整
  online softmax/attention 加速论文的双路线规划。
- [PAPER_B_FULL_SYSTEM_PLAN.md](PAPER_B_FULL_SYSTEM_PLAN.md)：论文 B 完整
  旁路 SMU 系统实现计划和分阶段验收标准。

v1 的默认方向是在 cluster 内新增一个由 MMIO 寄存器控制、带 TCDM master 端口的 Streaming Merge-Update Engine。软件负责配置地址和维度并启动引擎，硬件直接在 TCDM 中流式读取和更新 online softmax merge 状态。

## 当前实现边界

截至 2026-06-06，本分支已经完成论文 A 受限语义 baseline，并在论文 B 最小闭环
中接入完整 mixed-scalar online softmax merge datapath。当前 RTL 保持现有
`MERGE_*` MMIO/TCDM 接口，不修改 Spatz ISA、decoder、controller、VFU、VRF、
VLSU 或指令 pipeline。

当前 SMU datapath 支持 finite normal FP32 输入以及受支持的 zero length 状态，
内部使用 256 段 Q1.23 `exp` LUT、256 段 Q1.23 reciprocal LUT 和 Q16.32 定点
缩放/加权累加。both-zero-`l`、非法配置、NaN/Inf/subnormal 等仍走 error 或
unsupported 边界。

`online-softmax-merge` benchmark 现在包含完整 mixed-scalar sweep、stride-zero
packed layout、invalid config、both-zero-`l` error path、受限语义回归和
attention-like SMU merge-chain fallback。`full-ref-probe` 已从 expected-error
切换为 correctness gate。当前证据记录见
[PHASE_RESULTS.md](PHASE_RESULTS.md) 和
[COMPARISON_EXPERIMENT.md](COMPARISON_EXPERIMENT.md)。
