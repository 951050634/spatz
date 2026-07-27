# Online Softmax Merge 加速项目文档

本目录只讨论 Spatz 向量 cluster 中的 online softmax merge 加速。当前论文主线是：
SMU 卸载逐行 scalar recurrence，RVV 保留高吞吐 `O[D]` 更新。

截至 2026-07-20，A0/A1/A2 消融已经支持这一执行边界。A1 相对 A0 在三个 anchor
上加速 `1.38x` 至 `5.55x`，并在两个中大规模 anchor 上分别比 Full SMU 快
`1.37x` 和 `2.01x`。

## 文档结构

| 顺序 | 文档 | 内容 |
| ---: | --- | --- |
| 1 | [SMU设计与创新点.md](SMU设计与创新点.md) | 研究问题、SMU 结构、执行边界、创新性审计与主张范围 |
| 2 | [实验设计与结果.md](实验设计与结果.md) | A0/A1/A2、规模、FSM、并发、正确性和 proxy 结果 |
| 3 | [论文计划.md](论文计划.md) | 论文论点、章节、图表、剩余工作和完成标准 |
| 4 | [复现与证据索引.md](复现与证据索引.md) | 配置、命令、artifact、哈希和证据等级 |
| 5 | [A1标量卸载实验.md](A1标量卸载实验.md) | A1 三点验证的详细数据与 provenance |
| 6 | [补充实验进度.md](补充实验进度.md) | checkpoint、失败记录和完整审计日志 |

前四份文档构成当前主线。A1 明细和补充实验进度只提供复现与审计信息。

## 当前状态

| 工作 | 状态 | 结论或下一步 |
| --- | --- | --- |
| 公平 B2-R/B3 baseline | 完成 | 16 个实测点上 B3 均快于 B2-R |
| A0/A1/A2 消融 | 验证完成 | A1 在两个中大规模 anchor 上优于 A2 |
| A1 正式证据 | 待收口 | 在 clean commit 上复跑三个 anchor |
| FSM 与瓶颈分解 | 完成 | 中大规模由 SMU vector streaming 主导 |
| TCDM 并发 | 完成 | 当前单引擎场景可以有效重叠 |
| 数值正确性 | 支撑当前实现 | 不扩展为 LUT 设计空间研究 |
| closest prior art 全文核验 | 进行中 | 决定最终创新措辞 |
| 论文重写 | 待开始 | 围绕 scalar-SMU/RVV 执行边界组织 |

## 研究边界

- 不把完整 attention、QK/PV 或 LLM 端到端性能作为必须实验；
- 不做 LUT 段数和指数范围的大规模 sweep；
- 不把 generic cells 或 RTL toggles 写成物理 PPA、功耗或能效；
- 不把旧 scalar reference 的高加速比作为 headline；
- 不把开发阶段或历史论文路线写成贡献。
