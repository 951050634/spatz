# 复数指令扩展文档索引

本目录记录 Spatz 平台上新增复数浮点指令扩展的工程规划、实施证据和恢复上下文。
当前工作树位于 `/home/wxt/spatz-cfma`，分支为
`feature/cfma-instruction-extension`。

## 当前状态入口

- [RESUME_INFO.md](RESUME_INFO.md)：恢复工作时优先阅读。它反映当前 Git 状态、
  已完成步骤、未提交工作和下一步建议。
- [PHASE_RESULTS.md](PHASE_RESULTS.md)：按工程 node 记录验收证据、风险和验证结果。
- [GIT_NOTES.md](GIT_NOTES.md)：记录分支、提交、验证命令和 Git 操作。

## 设计与计划

- [PLAN.md](PLAN.md)：`vfcmacc.vv` 指令语义、实现边界、涉及文件、阶段计划、
  测试矩阵和工程规则。
- [complex_fma_hardware_design.md](complex_fma_hardware_design.md)：专用
  Complex FMA 硬件单元详细设计，包括 18 步实施计划。
- [register_layout.md](register_layout.md)：paired vector register layout 合法表、
  非法策略和编码决策。
- [dedicated_hardware_path.md](dedicated_hardware_path.md)：专用 datapath 的技术路径和
  投入产出分析。
- [toolchain_mnemonic_status.md](toolchain_mnemonic_status.md)：工具链 mnemonic 支持状态。

## 支撑资料

以下文件保留为设计或实现依据，不作为当前进度入口。当前进度以
`RESUME_INFO.md` 和 `PHASE_RESULTS.md` 为准。

- [fpnew_structure.md](fpnew_structure.md)

## 编译验证规则

本工程允许执行长时间编译工作来验证指令集修改的合理性。涉及 RTL、opcode、decode、
benchmark 或 ISA 行为的修改，可以运行完整 Verilator 构建、软件构建和目标 CTest；
编译耗时长不能作为跳过验证的理由。每次长时间验证都必须记录命令、开始/结束时间、
退出码和关键输出摘要。
