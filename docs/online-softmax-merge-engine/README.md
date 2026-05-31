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

截至 2026-06-01，本分支已经加入 MMIO 寄存器、cluster TCDM master 集成、
独立 engine RTL、受限语义 benchmark、A/B 对比实验、break-even sweep、稳定性
记录、绘图脚本和论文 A LaTeX 初稿。当前 RTL 是可集成的受限语义原型：它覆盖
TCDM 搬运、状态机、配置校验、零长度状态、`l_old=0`、`l_tile=0` 和
`m_old==m_tile && l_old==l_tile` 的等权重特例，但还没有完整实现 PLAN 中的
`exp()`、乘法缩放和除法归一化 datapath。

因此，当前 benchmark 的 reference 和输入 case 只验证该受限语义。合法但未支持
的 mixed-scalar 输入会返回 `MERGE_STATUS.error`，`full-ref-probe` 当前也是
expected-error 测试。

论文 A 相关内容现在视为阶段性完成。下一阶段按
[PAPER_B_FULL_SYSTEM_PLAN.md](PAPER_B_FULL_SYSTEM_PLAN.md) 推进：保持现有
MMIO/TCDM 旁路接口，不修改 Spatz ISA、decoder、controller、VFU、VRF、VLSU 或
指令 pipeline，在 SMU 内部实现 `ExpLUT + reciprocal` 的完整 online softmax
merge 近似 datapath，并重新生成完整 mixed-scalar 的 correctness、误差和性能
证据。
