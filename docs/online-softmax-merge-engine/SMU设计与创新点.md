# SMU 设计、研究定位与创新点

## 1. 研究定位

本文研究 online softmax merge 在 Spatz 向量 cluster 中的执行边界。SMU 负责
逐行 scalar recurrence，RVV 负责规则的 `O[D]` 更新。该划分保留现有 ISA 和主
向量流水线，并利用两个执行单元各自更适合的工作类型。

核心结论是：专用硬件消除了跨状态依赖和非线性计算造成的逐行开销；RVV 在中大
规模上提供了更低的向量更新成本。

## 2. Online softmax merge 的计算划分

Tile-boundary merge 对每一行执行：

```text
m_new  = max(m_old, m_tile)
alpha  = exp(m_old  - m_new)
beta   = exp(m_tile - m_new)
l_new  = alpha * l_old + beta * l_tile
w_old  = alpha * l_old  / l_new
w_tile = beta  * l_tile / l_new
O_new[d] = w_old * O_old[d] + w_tile * O_tile[d]
```

`m/l/weight` 构成逐行 scalar recurrence。`O[D]` 更新是规则的逐元素乘加。两部分
具有不同的依赖关系和并行度，因此执行位置直接影响性能。

研究问题可表述为：

> 对共享 TCDM 的 RISC-V vector cluster，哪一种 online softmax merge 卸载粒度
> 能降低逐行开销，并保留 RVV 的向量吞吐？

## 3. SMU 的系统结构

SMU 通过现有 cluster peripheral 接收 MMIO 命令，并以 TCDM master 身份访问共享
scratchpad。软件配置源地址、目标地址、`N`、`D`、stride 和执行模式。SMU 从
TCDM 读取每行状态，执行 recurrence，再把结果写回 TCDM。

该集成方式不修改 Spatz ISA、decoder、controller、VFU、VRF、VLSU 或主向量
流水线。软件仍可使用 RVV 执行普通向量工作，并通过共享 TCDM 与 SMU 交换状态。

当前 RTL 提供两种模式：

| 模式 | SMU 输出 | 后续执行 |
| --- | --- | --- |
| Full | `m_new`、`l_new`、`O_new[D]` | 无 |
| Scalar-only | `m_new`、`l_new`、`w_old`、`w_tile` | RVV 更新 `O[D]` |

状态机依次执行 scalar load、recurrence、weight 计算和 scalar store。Full 模式
随后进入 vector update。Scalar-only 模式写回权重后结束。默认模式保持 Full，
因此新增消融接口不会破坏原有软件行为。

## 4. 数值与接口边界

被测 datapath 接受 finite normal FP32 和受支持的 zero-length 状态。内部使用固定
256 段 Q1.23 exponential/reciprocal LUT 与 Q16.32 计算。非法 mode、未对齐地址、
零维度、NaN、Inf、subnormal 和 both-zero-`l` 进入显式 error 或 unsupported 路径。

Scalar-only 模式增加两个 FP32 权重目标地址。SMU 写回权重后，RVV 使用同一组
权重完成逐元素乘加。该接口把有状态 recurrence 与规则向量计算分开，也使 A1 能
直接测量 scalar offload 的收益。

## 5. 三种执行方案

| 模式 | Scalar recurrence | `O[D]` 更新 | 研究作用 |
| --- | --- | --- | --- |
| A0 / B2-R | 软件 | RVV | 公平优化软件基线 |
| A1 | SMU | RVV | 隔离 scalar offload 收益 |
| A2 / B3 | SMU | SMU | 完整硬件卸载对照 |

A1 组合 SMU 的逐行低成本与 RVV 的低每元素成本。A2 保留完整 SMU 路径，用于
测量把向量更新继续放入专用数据通路的代价。

## 6. 设计结论的证据链

1. B2-R 反汇编门槛证明软件基线执行 RVV load、浮点向量运算和 store。
2. 16 点 B2-R/B3 数据显示，Full SMU 把每行成本从约 `1538` 降到 `22` cycles，
   同时把每元素成本从约 `2.06` 提高到 `8.00` cycles。
3. FSM 分解显示，中大规模的 vector streaming 占 SMU busy time 的 `92.80%` 至
   `96.25%`，scalar path 保持约 `20 cycles/row`。
4. A1 在 `(8,32)` 和 `(16,64)` 上分别比 A2 快 `1.37x` 和 `2.01x`，直接验证
   RVV 在这些规模上更适合执行向量更新。
5. A1 和并发实验记录的 TCDM congestion 很低。执行单元的每行和每元素成本解释
   了主要性能趋势。

这些证据支持 Scalar-only SMU 作为当前主设计。Full SMU 继续作为小规模可选模式
和实验对照。

## 7. 创新性审计

### 7.1 已排除的宽泛表述

- “首次用硬件加速 softmax”不成立；
- “首次为 attention 加入 softmax 单元”不成立；
- LUT exponential/reciprocal 本身不构成创新；
- 不修改 ISA 的 accelerator 集成方式不能单独支撑创新性；
- A0/A1/A2 性能结果属于实验证据，不等于架构首创。

### 7.2 需要全文核验的架构主张

当前候选架构主张是：SMU 把 tile-boundary online-softmax scalar recurrence 作为
独立的 cluster-local offload，并让现有 RVV 保留 `O[D]` 更新。该粒度不同于完整
softmax 单元和完整 attention accelerator。最终措辞取决于 closest prior art 的
全文证据。

| 工作 | 直接重合点 | 需要核验的问题 | 风险 |
| --- | --- | --- | --- |
| FlashAttention / FlashAttention-2 | blockwise online softmax | recurrence 与状态划分 | 高 |
| Softermax | exp/div 近似与硬件 softmax | 是否支持在线状态合并 | 高 |
| ITA | attention 与 softmax 专用硬件 | softmax 粒度和存储接口 | 高 |
| FuseMax | online softmax 与片上状态 | 是否实现相同 merge recurrence | 极高 |
| Flexible Template for Edge GenAI | PULP 非线性加速 | scratchpad、MMIO 与 ISA 边界 | 极高 |
| Hardware-Efficient SoftMax | exp/reciprocal 电路 | 是否支持 streaming merge | 中高 |
| Spatz | RISC-V vector cluster | 原平台已有的外围集成模式 | 平台基线 |

全文核验的最高优先级是 FuseMax、Flexible Template、ITA 和 Softermax。在核验完成
前，论文只陈述本原型的集成方式和执行划分，不使用“首次”或“唯一”。

### 7.3 主张与证据状态

| ID | 候选主张 | 本地证据 | 状态 |
| --- | --- | --- | --- |
| C1 | cluster-local scalar merge offload 保持现有 ISA 和主向量流水线 | RTL、MMIO、TCDM 与 benchmark | 候选，待全文核验 |
| C2 | A0/A1/A2 揭示 scalar-SMU/RVV 执行边界 | 三点消融、规模模型与 FSM | 本地证据成立 |
| C3 | 当前 Full SMU 的瓶颈转向 vector streaming | FSM 与 A1/A2 对比 | 结果成立 |
| C4 | 当前单引擎可与 core stream 共享 TCDM | 16-phase concurrency | 限定场景结果 |
| C5 | 固定 256 段 LUT 满足被测输入正确性 | host model 与 RTL gate | 实现结果，非创新 |
| C6 | SMU 具有物理 PPA 或能效优势 | 缺少 PDK、PVT 与物理流程 | 不得主张 |

C2 是当前最强贡献。若全文核验支持 C1，论文可将 C1 写成架构贡献，并把 C2、C3
写成实证贡献。若最近邻已经覆盖 C1，论文仍可围绕 C2 组织：完整卸载没有组合两个
执行单元的优势，Scalar-only SMU 与 RVV 构成当前更有效的执行方案。

## 8. 研究与写作边界

| 纳入本文 | 排除在主线之外 |
| --- | --- |
| 完整 `(m,l,O)` merge recurrence | 完整 attention 或 LLM 系统 |
| A0/A1/A2 执行边界 | QK、PV、mask 和全流程调度 |
| RVV 公平 baseline 与反汇编证据 | 自然 `expf` 的宽泛算法比较 |
| 周期、FSM、TCDM 与正确性 | LUT 段数和指数范围 sweep |
| generic resource / RTL toggle 的代理边界 | 无物理流程的 PPA、功耗和能效 |

固定 256 段 LUT 只是一项实现选择。正确性数据表明当前实现满足被测输入范围，
无法证明该配置全局最优。

论文可以报告 A1 相对 A0 的 `1.38x` 至 `5.55x` 加速，也可以报告 A1 在两个中大
规模 anchor 上相对 A2 的 `1.37x` 和 `2.01x` 加速。论文必须同时说明 `(1,1)`
上 A2 仍快约 `1.06x`，并把所有结论限制在被测规模和功能仿真环境内。
