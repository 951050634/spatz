# 复数指令扩展

本目录用于记录在 Spatz 平台上新增复数浮点指令扩展的工程规划。

初始目标是把当前一次复数乘加所需的四条向量浮点乘加指令，折叠成
一条软件可见的架构指令。第一版优先跑通 ISA、译码、RTL、软件和
benchmark 的完整闭环；后续版本再评估是否加入专用复数 FMA 数据通路。

文档说明：

- [PLAN.md](PLAN.md)：指令语义、实现边界、涉及文件、阶段计划、
  测试矩阵、结果标准和 v2 评审门。
- [PHASE_RESULTS.md](PHASE_RESULTS.md)：每个实施节点的状态、证据、
  验收结果和风险记录。
- [GIT_NOTES.md](GIT_NOTES.md)：分支、提交、验证命令和远端 Git 操作记录。
- [register_layout.md](register_layout.md)：`vfcmacc.vv` v1 寄存器布局合法表、
  非法策略和编码决策。
- [toolchain_mnemonic_status.md](toolchain_mnemonic_status.md)：工具链助记符支持状态。
- [dedicated_hardware_path.md](dedicated_hardware_path.md)：实现专用 Complex FMA
  硬件的技术路径和投入产出分析。
- [complex_fma_hardware_design.md](complex_fma_hardware_design.md)：专用 Complex FMA
  硬件单元详细设计方案，包括架构、模块设计、18 步详细实施步骤（每步可量化验收）、
  性能分析和验收标准。**推荐作为实施的主要指导文档。**

