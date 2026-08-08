# 调用 goal 工具的提示词（新窗口使用）

> 在新窗口中直接粘贴下面整段即可。它会要求执行模型先创建 goal，再按规划执行。
> 不需要设置 token budget（除非你明确要求）。

---

请用 create_goal 工具创建一个 goal，然后立即开始执行。objective 如下：

**「按 docs/online-softmax-merge-engine/TCAS2后续工程任务规划.md 的 P1–P18 顺序，
量化和强化 Proposed Scalar SMU（= A1_SMU_SCALAR = Scalar SMU + existing RVV）：
拟合 A1 scaling model（C0/Cs/Cv + crossover）、做 Scalar SMU 内部 latency
breakdown、完成 Scalar/Full standalone 与 cluster-level 综合（area、area
overhead、timing/Fmax、critical path）、把 cycles 换算成真实 latency 并计算
throughput 与 area efficiency，最终生成 P16 硬件结果表和 P17 核心图表。Full SMU
（A2）仅作为 Full-Offload 消融对照，不继续作为主要架构开发方向。」**

执行要求：

1. 先通读 docs/online-softmax-merge-engine/TCAS2后续工程任务规划.md 全文，并
   阅读同目录 README.md、A1标量卸载实验.md 和 experiments/ 下已有 parsed /
   reports 结果，优先复用现有脚本、RTL 和结果格式。
2. 已有模型可直接使用：B2R: C=153.5+1594.2N+2.09ND；FULL: C=1285.6+19.3N+8.03ND。
   Proposed A1 需要从已有 P0-4 scaling 数据中提取并拟合 C0/Cs/Cv（三次 trial
   一致，每个 (N,D) 只取一条数据）。
3. Proposed Design 固定为 Scalar SMU + RVV；不修改算法功能，不重构 runner /
   配置框架，不删除历史 A1/A2 名称导致历史结果失效。
4. 不要过度防御性编程：每项任务先做最短可工作的实现，直接产出论文需要的性能、
   面积、时序或结构数据；除非直接阻塞目标实验，否则不要大规模重构、兼容性封装、
   异常处理扩展、额外 runner gate 或防御性检查。
5. 及时 git 同步：每个里程碑完成后立即提交（原子、rebase、无 merge commit，
   subject 用 imperative 且 ≤100 字符）。
6. 生成文件按规划：experiments/reports/final_scaling_model.md、
   experiments/parsed/final_scaling_model.csv，以及 P16/P17 的最终表与图。
7. 每完成一个 P 阶段，用简短中文汇报该阶段结论（数字 + 文件路径），不要冗长。

---

### 说明

- 该提示词对应本环境中的 goal 工具：`create_goal`（创建目标）+ `update_goal`
  （目标完成时标记 complete）。objective 已按 TCAS-II 四问（为何需要专用硬件 /
  解决哪个瓶颈 / 为何 Scalar+RVV 更合理 / 面积时序代价）组织。
- 新窗口工作目录应保持为 `/home/wxt/work-online-merge-supplement`，这样规划文档
  路径可直接解析。
- 如果新窗口不允许读取本文件，把上面提示词整段（含 objective）粘贴给执行模型即可，
  它不依赖本文件内容之外的上下文。
