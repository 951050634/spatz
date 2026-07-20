# SMU 科研项目与论文完善总计划

## 1. 目标与管理方式

本文档是 Online Softmax Merge Unit（SMU）项目从创新性审计、实验补充到
IEEEtran 6 页 workshop 论文交付的唯一总计划。现有论文草稿仅作为已有结果和
主张的索引，不作为文章结构或措辞基线。

所有阶段使用以下状态：

- `pending`：尚未开始；
- `in_progress`：正在执行；
- `blocked_external`：缺少 PDK、工具或其他外部材料；
- `complete`：产物、验证和证据均已闭环；
- `rejected`：实验失败或主张不成立，不进入论文。

每个阶段必须记录输入、产物、验证命令、证据路径、Git commit、限制和下一步。
大体积仿真产物保留在外部 `work-online-merge-*` 目录，Git 内只保存结构化摘要、
哈希和可复现入口。

## 2. 固定研究定位

### 2.1 研究问题

当前研究问题为：

> 能否在不修改 Spatz ISA 和主向量流水线的条件下，通过 cluster-local、
> TCDM-connected SMU 高效执行 tile-boundary online-softmax merge？

候选论文身份为：

> 本文研究一种保持现有处理器接口的 online-softmax merge offload 粒度，并在
> Spatz 上实现和评估完整 mixed-scalar SMU。

### 2.2 候选贡献

1. 保持 MMIO/TCDM 接口且不修改 ISA、decoder、VRF 和主向量流水线的
   tile-boundary merge offload。
2. 覆盖 `max + exp + reciprocal + weighted vector update` 的完整
   mixed-scalar datapath。
3. 对软件逐行标量开销、SMU 启动开销、vector-streaming 瓶颈和 TCDM 并发
   干扰的实测分解。

“两阶段开发过程”不作为创新点。只有与 closest prior art 存在明确差异且有直接
实验支持的内容才能进入最终贡献列表。

### 2.3 主张边界

- 不宣称已经实现完整 attention accelerator 或 LLM 推理系统；
- 不将 scalar reference 的约 `37.89x` 加速作为 headline；
- 不宣称已证明所有 attention 输入上的全局数值误差界；
- 不把 Yosys generic cells 或零延迟 RTL toggles 写成物理 PPA；
- 不将模型预测点混入直接测量结果。

## 3. 阶段总览

| 阶段 | 内容 | 优先级 | 状态 | 完成门槛 |
| ---: | --- | --- | --- | --- |
| 1 | 研究问题与创新性审计 | P0 | `in_progress` | closest-prior-art 矩阵和稳定贡献列表 |
| 2 | 公平 baseline 审计 | P0 | `pending` | B2-R 计时与 RVV 证据闭环 |
| 3 | A0/A1/A2 关键消融 | P0 | `pending` | 三个 anchor 上分离 scalar/vector 收益 |
| 4 | blocked-attention 最小闭环 | P0 | `pending` | 总周期、merge 占比和输出误差 |
| 5 | 数值与 LUT 设计空间 | P0 | `pending` | FP64 oracle 和误差/复杂度取舍 |
| 6 | 论文架构与图表 | P0 | `pending` | claim-evidence 驱动的 6 页结构 |
| 7 | 完整论文重写 | P0 | `pending` | 可编译、可追溯的英文初稿 |
| 8 | 完整性与模拟审稿 | P0 | `pending` | 无未处理 CRITICAL/MAJOR 问题 |
| 9 | 投稿格式与 artifact 交付 | P0 | `pending` | 机械检查和可复现性检查全部通过 |
| 10 | ASIC PPA 和物理能耗 | P2 | `blocked_external` | 固定 PDK、PVT、约束和物理流程 |

## 4. 阶段一：创新性审计

### 4.1 检索范围

检索并交叉核验以下类别：

- online softmax 与 streaming normalization；
- FlashAttention、blockwise/tiled attention；
- softmax、exponential、reciprocal 硬件单元；
- attention accelerator 内的 normalization/merge datapath；
- RISC-V/vector-cluster auxiliary accelerator；
- scratchpad-coupled、MMIO-controlled offload；
- ISA extension 与非侵入式外围引擎的比较。

对每篇文献记录：目标操作、加速粒度、是否实现完整 merge recurrence、处理器接口、
存储层次、数值格式、非线性函数实现、baseline、端到端 workload、PPA、与 SMU
的重合点及差异。

### 4.2 创新性判定门槛

- 覆盖上述主要竞争类别；
- 每项候选贡献绑定至少一篇 closest prior art；
- 每个“首次”或“不同于已有工作”的表述都有可核验来源；
- 区分论文明确写出的事实、根据架构做出的推断和本项目建议；
- 若“无 ISA 修改”已经被充分覆盖，则将主线收紧为“tile-boundary merge 粒度、
  完整 recurrence 和实测 bottleneck transition”。

### 4.3 产物

- `NOVELTY_LANDSCAPE.md`：检索策略、竞争工作矩阵和创新性结论；
- `CLAIM_EVIDENCE_MATRIX.md`：主张、直接证据、closest prior art 和允许的措辞；
- 经 DOI 或出版社元数据核验的 BibTeX 条目。

## 5. 阶段二：公平 baseline

保留三个主要实现：

- B1：RTL-aligned scalar software reference；
- B2-R：同数值语义的 scalar weights 加 RVV vector update；
- B3：完整 SMU。

执行要求：

1. 审计 B2-R 计时窗口，排除输入准备、reference、日志和正确性检查；
2. 用反汇编证明 RVV load、multiply/FMA、store 和 strip-mining back edge；
3. 保证 B2-R 与 B3 使用相同输入和数值语义；
4. 尝试 B2-F，即自然 `expf` 加 RVV update；若目标运行时不能可靠支持，保留失败
   证据且不纳入正式 headline；
5. 正式结论以 B3/B2-R 为主，B1 只描述 scalar software 上界。

每个正式性能点执行一次 warm-up 和三次测量，报告 median、min 和 max，并固定
commit、CFG、simulator、工具版本和输入身份。

## 6. 阶段三：A0/A1/A2 消融

### 6.1 接口与行为

为 SMU 增加向后兼容的执行模式：

- `full`：保持当前完整 SMU 行为；
- `scalar-only`：计算新 `m/l` 和 old/tile weights，不执行向量更新。

接口增加 mode 控制字段以及 old-weight、tile-weight 输出地址。默认 mode 保持现有
full 行为。非法 mode、未对齐地址和无效配置必须进入显式 error path。

### 6.2 消融定义

- A0：software scalar 加 RVV；
- A1：SMU scalar 加 RVV；
- A2：SMU scalar 加 SMU vector。

在 `(1,1)`、`(8,32)`、`(16,64)` 三个 anchor 上报告 end-to-end、scalar、
vector、command/wait cycles、TCDM accessed/congested，以及 A1/A0、A2/A1、
A2/A0 比值。

## 7. 阶段四：blocked-attention 最小闭环

新增真实调用 SMU 的 blocked-attention benchmark。软件与 SMU 路径共享相同 QK、
PV、输入、mask、tiling 和调度，唯一差异是 merge recurrence 的执行位置。

固定测试点：

- `(rows,D,blocks)=(8,32,2)`；
- `(8,32,4)`；
- `(16,64,4)`。

报告完整 kernel cycles、merge cycles、merge 占比、software/SMU 总周期差异、最终
attention output 的绝对与相对误差，以及 TCDM traffic/congestion。容量不足时输出
`capacity_skip` 并保留记录，不静默缩小规模。

论文中将其称为 Spatz blocked-attention RTL workload，不外推为 LLM 端到端结果。

## 8. 阶段五：数值和 LUT 设计空间

以 FP64 为 oracle，覆盖：

- 随机 mixed-scalar 输入；
- logit delta 的 `[-8,0]` 区间、端点和饱和区；
- 极端 `l_old/l_tile` 比例；
- zero-length 和 both-zero-`l`；
- 1、2、4、8、16 次连续 merge；
- 多 seed、多 `N/D` 和不同 block 顺序。

比较 64、128、256、512 段 exponential/reciprocal LUT，报告最大绝对误差、guarded
relative error、均值、P95、P99、failure count 和 generic-cell proxy。根据误差与
复杂度取舍解释最终 LUT 配置。

## 9. 阶段六至七：论文重建

首先生成不提交 Git 的 `project_context.md`，锁定一句话身份、最终贡献、closest
prior art、claim-evidence map、禁止主张、术语表、目标页数和图表预算。

采用以下写作顺序：

1. Draft-0 Introduction；
2. Evaluation；
3. Design；
4. Background and Related Work；
5. Final Introduction；
6. Abstract；
7. 全文集成和压缩。

IEEEtran 6 页正文预算：

| 部分 | 页数 |
| --- | ---: |
| Introduction | 0.75 |
| Background and Related Work | 0.75 |
| SMU Design | 1.25 |
| Methodology | 0.75 |
| Evaluation | 2.00 |
| Limitations and Conclusion | 0.50 |

核心图表：

1. Spatz cluster、SMU 和 tile-boundary merge 数据流；
2. B2-R/A1/B3 scaling、break-even 与 FSM 瓶颈迁移组合图；
3. blocked-attention 总周期、merge 占比和数值误差组合图；
4. 版面允许时增加 LUT 误差与复杂度小表。

所有数据图从版本化 CSV/JSON 生成 SVG/PDF，不使用 AI 图像生成数据图。

## 10. 阶段八至九：完整性、审稿和交付

1. 逐条核验作者、题名、年份、venue、页码和 DOI；
2. 审查重复次数、误差统计、seed、异常值和图表表达；
3. 生成三份独立模拟审稿意见：体系结构与创新性、实验与 baseline 公平性、数值与
   外推边界；
4. 修复或降级所有 CRITICAL/MAJOR 问题；
5. 完成术语一致性、claim-first、压缩和去 AI 化审查；
6. 编写 Data/Artifact Availability，区分 Git 内数据和外部大型 artifact。

最终验收：

- 每项贡献均有 closest prior art、直接差异和实验支撑；
- A0/A1/A2、B2-R/B3 和 blocked-attention 实验闭环；
- 正文不超过 6 页；
- 无 undefined references/citations；
- 所有字体嵌入，数据图使用矢量格式；
- 所有结果可追溯到固定 commit、配置、命令和 artifact；
- 三轮模拟审稿后不存在未处理的 CRITICAL/MAJOR 问题。

## 11. 当前下一步

1. 完成多源检索策略和第一轮候选文献集合；
2. 建立 `NOVELTY_LANDSCAPE.md` 的竞争工作矩阵；
3. 对三项候选贡献分别寻找 closest prior art；
4. 完成创新性门槛后再冻结 A1 和 blocked-attention 的实现规格，避免为错误主张
   设计实验。
