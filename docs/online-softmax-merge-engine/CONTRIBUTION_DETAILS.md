# Online Softmax Merge Engine：贡献细化说明

本文档用于统一论文、组会、答辩和简历中的贡献表述。重点回答四个问题：

1. **解决了什么问题？**
2. **具体实现了什么？**
3. **有哪些可复现的验证证据？**
4. **当前结果能声称什么，不能声称什么？**

本文中的“本工作”指 Spatz 上的 cluster-local Streaming Merge-Update Engine，
下文简称 **SMU**。

---

## 1. 核心结论

### 1.1 一句话版本

本工作在不修改 Spatz ISA 和主指令流水线的前提下，设计并实现了一个由 MMIO
控制、通过 TCDM 访问数据的 cluster-local SMU，将 online softmax merge 中的
`m/l/O` 状态更新从软件 scalar/reference path 旁路到硬件，并通过完整
mixed-scalar datapath、LUT 数值近似、RTL-aligned reference、CTest benchmark
和 attention-like merge chain 建立了功能、数值和性能验证闭环。

### 1.2 最重要的贡献

| 贡献 | 具体内容 | 直接证据 |
|---|---|---|
| **问题抽象** | 将 block-wise attention 中的 online merge 从完整 attention kernel 中拆出，定义为可独立卸载、可单独验证的 `m/l/O` state update workload | `m/l/O` recurrence、microbenchmark、attention-like chain |
| **低侵入系统架构** | 采用 MMIO 控制寄存器 + TCDM master 旁路路径，不改 ISA、decoder、controller、VFU、VRF 和主 pipeline | cluster peripheral、top-level integration、TCDM 连接 |
| **完整硬件 datapath** | 在 SMU 内完成 `m_new`、双路指数缩放、`l_new`、reciprocal 归一化以及 `O` 向量更新 | `online_merge_update_engine.sv` 及辅助数值模块 |
| **硬件化数值实现** | 使用 `exp`/reciprocal LUT、线性插值和 Q-format 定点缩放，避免依赖完整浮点 `exp/div` | approximation modules、fixed-point helpers、numeric model |
| **系统验证闭环** | 建立软件 reference、近似单元 testbench、CTest benchmark、错误路径回归和性能/流量统计 | benchmark、CTest、CSV、plotting scripts |
| **量化结果** | 在当前 full mixed-scalar sweep 中最高达到 `37.89x` speedup，相比 RTL-aligned software reference 减少 `97.36%` cycles | `N=16,D=64` result；attention-like chain result |

### 1.3 论文定位

最稳妥的定位是：

```text
A low-intrusion architecture/system prototype for online softmax merge
offload on a RISC-V vector-cluster platform.
```

中文可表述为：

> 面向 RISC-V vector cluster 的低侵入式 online softmax merge 硬件卸载架构与
> 系统原型。

本工作的核心不是声称已经完成完整 attention accelerator，而是证明：

1. online softmax merge 可以被抽象成独立硬件 offload target；
2. 该 target 可以通过保守的 MMIO/TCDM 接口接入 Spatz；
3. 完整 mixed-scalar recurrence 可以在紧凑的 SMU datapath 中实现；
4. LUT 近似和定点累加在当前评估范围内具有足够小的观测误差；
5. 该路径在 microbenchmark 和 attention-like merge chain 中具有明显的 cycle
   benefit，并为后续端到端 attention 集成提供硬件基础。

---

## 2. 要解决的问题：为什么需要 online merge offload

在 block-wise attention 或 FlashAttention-style 算法中，每个 block 先产生局部
统计量，随后需要与历史状态合并。对于每一行，输入状态为：

- 历史状态：`m_old`、`l_old`、`O_old[D]`；
- 当前 tile 状态：`m_tile`、`l_tile`、`O_tile[D]`。

合并后的状态为：

```text
m_new = max(m_old, m_tile)

l_new = l_old  * exp(m_old  - m_new)
      + l_tile * exp(m_tile - m_new)

O_new = O_old * (l_old  * exp(m_old  - m_new) / l_new)
      + O_tile * (l_tile * exp(m_tile - m_new) / l_new)
```

这个计算不是普通的逐元素 softmax，原因在于：

- `m/l` 是每行的 scalar state，`O[D]` 是对应的 vector state；
- `m_new` 会影响两路指数缩放；
- `l_new` 又会反过来决定 `O` 的归一化权重；
- scalar 更新和 vector 更新之间存在明确的数据依赖；
- 完全走软件路径时，需要承担循环、访存以及 `exp`/除法近似的成本。

因此，本工作的第一步不是直接优化完整 attention，而是把其中的 merge-update
步骤抽象成一个独立 workload。这个边界使硬件、软件和验证可以围绕同一组输入
输出收敛：输入和输出都是 `m/l/O` state tuple，而不是 `Q/K/V`。

---

## 3. 贡献一：低侵入式 cluster-local SMU 架构

### 3.1 架构目标

SMU 被设计为现有 Spatz cluster 旁边的 sidecar engine：软件通过寄存器配置任务，
硬件通过 TCDM master 端口读取输入并写回输出。该设计不重做 Spatz vector
pipeline，也不把 merge 运算塞入 core 的关键路径。

### 3.2 控制与数据接口

SMU 接口由三部分组成：输入/输出地址、形状与布局配置、控制与状态寄存器。

**输入地址：**

```text
MERGE_SRC_M_OLD
MERGE_SRC_L_OLD
MERGE_SRC_O_OLD
MERGE_SRC_M_TILE
MERGE_SRC_L_TILE
MERGE_SRC_O_TILE
```

**输出地址：**

```text
MERGE_DST_M
MERGE_DST_L
MERGE_DST_O
```

**形状和布局：**

```text
MERGE_N       # row 数
MERGE_D       # O 向量维度
MERGE_STRIDE  # O 的 row stride
```

**控制与状态：**

```text
MERGE_CTRL.start
MERGE_CTRL.clear_done
MERGE_STATUS.busy
MERGE_STATUS.done
MERGE_STATUS.error
```

软件侧的调用流程被收敛为四步：

1. 在 TCDM 中准备 `m_old/l_old/O_old` 和 `m_tile/l_tile/O_tile`；
2. 写入 source/destination base address、`N`、`D` 和 stride；
3. 写 `start` 启动 SMU；
4. 轮询 `busy/done/error`，再读取输出 buffer。

### 3.3 低侵入边界

该架构明确保持以下边界：

- 不修改 Spatz ISA；
- 不新增自定义 vector instruction；
- 不修改 decoder、controller、VFU、VRF、VLSU 或主指令 pipeline；
- 不要求 SMU 直接访问外部 DRAM；
- 不改变原有 core TCDM port 的基本使用方式。

因此，主要架构贡献不是“增加了一个独立 RTL 模块”，而是证明 merge update
可以作为 **cluster-local sidecar engine** 集成到真实 SoC cluster 中，同时尽量
降低对既有处理器微结构的侵入。

---

## 4. 贡献二：完整 mixed-scalar merge datapath

### 4.1 从 Phase A 到 Phase B

工作按两个阶段推进：

- **Phase A：受限语义原型。** 重点是打通 `MERGE_*` MMIO、TCDM master、状态寄存器
  和软件启动路径，验证“engine 能否安全接入 Spatz”。早期 case 包括
  `l_old=0`、`l_tile=0` 或构造出的等权特例。
- **Phase B：完整 mixed-scalar datapath。** 保留同一条 MMIO/TCDM 系统接口，将
  内部语义扩展为完整 online merge recurrence；generic mixed-scalar case 进入
  correctness gate，只有 both-zero-`l` 等不支持配置继续走 error path。

这种递进关系很重要：Phase A 是系统集成证据，Phase B 才是完整 online softmax
merge 语义的硬件实现证据，不能把早期 restricted prototype 直接描述成最终能力。

### 4.2 SMU 内部计算流程

当前状态机按 row 和 vector element 流式推进，主要状态为：

```text
IDLE
LOAD_SCALAR
COMPUTE_SCALAR
COMPUTE_WEIGHT
STORE_SCALAR
UPDATE_VECTOR
DONE
ERROR
```

每个 row 的主要流程如下：

1. **配置检查**：检查 `N`、`D`、地址对齐和 stride 对齐；
2. **读取 scalar state**：加载 `m_old/l_old/m_tile/l_tile`；
3. **更新最大值**：计算 `m_new = max(m_old, m_tile)`；
4. **计算指数缩放**：得到 `m_old-m_new` 和 `m_tile-m_new`，分别计算两路 scale；
5. **更新归一化长度**：在定点域中缩放并累加两路 `l`，得到 `l_new`；
6. **计算 vector 权重**：对 `l_new` 做 reciprocal 近似，生成 old/tile 两路权重；
7. **写回 scalar state**：写回 `m_new/l_new`；
8. **流式更新向量**：逐元素读取 `O_old/O_tile`，计算并写回 `O_new`；
9. **推进或结束**：继续下一个 row，或置位 `done`；非法配置进入 `ERROR`。

这个 datapath 的关键点是：`m/l` scalar 更新与 `O[D]` vector 更新使用同一套
online merge 语义，而不是只实现 `max` 或简单的向量加法。

### 4.3 数据布局和 stride 语义

输入输出布局为：

```text
m_old[N],  l_old[N],  O_old[N][D]
m_tile[N], l_tile[N], O_tile[N][D]
m_out[N],  l_out[N],  O_out[N][D]
```

`O` 支持两种 stride：

- `stride == 0`：使用 packed layout，默认 row stride 为 `D * sizeof(float)`；
- `stride != 0`：使用软件显式指定的 row stride，且必须保持 4-byte 对齐。

这使同一 engine 既可以处理紧凑的 microbenchmark buffer，也可以处理带 padding
或更一般的 TCDM row layout。

---

## 5. 贡献三：面向硬件的数值近似 datapath

### 5.1 设计选择

当前原型不依赖完整浮点 `exp` 和除法，而是采用较紧凑的近似方案：

- `exp`：在 `[-8, 0]` 区间使用 256 段 Q1.23 LUT，并进行线性插值；
- reciprocal：在 `[1, 2]` mantissa 区间使用 256 段 Q1.23 LUT，并进行线性插值；
- scalar 和 vector 权重计算：使用 Q-format 定点缩放；
- 中间长度和加权累加：使用 Q16.32 表示。

### 5.2 配套 fixed-point 语义

为使软件 reference 与 RTL 逐位语义尽可能一致，建立了配套 helper 体系，包括：

- FP32 bit-level 分类；
- finite normal 输入检查；
- FP32 到 signed/unsigned Q-format 转换；
- Q1.23 与 Q16.32 乘法；
- 带 scale exponent 的 reciprocal 应用；
- 饱和、unsupported 和非法输入处理。

因此，数值贡献不仅是“调用一个 LUT”，而是把输入分类、格式转换、近似函数、
缩放、累加和边界处理组织成了可以被软件 reference 重现的完整 datapath 语义。

### 5.3 当前数值证据

在当前 benchmark 和 numeric model 覆盖的 finite normal FP32 输入上：

- host numeric model 的最大绝对误差约为 `9.78e-6`；
- 该结果满足当前 `1e-4` 级目标，并明显小于 benchmark 使用的 `1e-3` gate。

这些数据支持“在当前评估范围内误差较小”的表述，但不支持以下更强结论：

- 对所有 attention 输入分布均有全局误差证明；
- 对 NaN、Inf、subnormal 提供完整数值语义；
- 已完成 formal error bound 或大规模真实模型 trace 验证。

---

## 6. 贡献四：从 standalone RTL 到可运行的 Spatz cluster 路径

主要集成工作包括：

- 在 `Bender.yml` 中加入 online merge RTL source；
- 在 cluster peripheral HJSON 中加入 `MERGE_*` 寄存器；
- 重新生成 peripheral register package、top module 和 C header；
- 在 `spatz_cluster_peripheral.sv` 中导出 `reg2hw` 配置和 `hw2reg` 状态；
- 在 `spatz_cluster.sv` 中实例化 SMU；
- 新增 SMU 的 TCDM request/response 连接；
- 将 SMU 作为非 core master 接入 TCDM interconnect；
- 保持 perf counter、CLINT、barrier、icache prefetch 和 AXI-to-TCDM 路径可编译。

这一步把工作从“孤立 testbench 中能工作的 RTL”推进为“软件可以通过真实 MMIO
和 TCDM path 驱动的 cluster 组件”。这也是系统原型与单模块演示之间的主要区别。

---

## 7. 贡献五：软件接口、benchmark 与验证闭环

### 7.1 软件和 benchmark

主要实现位于：

```text
sw/spatzBenchmarks/online-softmax-merge/main.c
sw/spatzBenchmarks/CMakeLists.txt
```

benchmark 完成以下工作：

- 准备 TCDM 输入输出 buffer；
- 写入 `MERGE_*` 寄存器并启动 SMU；
- 轮询 `busy/done/error`；
- 统计 CPU/reference path 和 engine path cycles；
- 统计 TCDM accessed/congested counter；
- 比较输出正确性；
- 验证非法配置和 unsupported case；
- 执行 attention-like multi-row、multi-block merge chain。

### 7.2 覆盖的测试矩阵

| 类别 | 覆盖内容 | 目的 |
|---|---|---|
| 基础功能 | `N=1,D=1` | 验证最小任务和基本启动路径 |
| 尺寸扩展 | `N=4,D=8` 至 `N=16,D=64` | 观察 row/vector 规模变化下的性能 |
| 布局 | `stride==0` packed layout | 验证默认布局语义 |
| 配置错误 | `N=0`、`D=0` | 验证零尺寸检查 |
| 地址错误 | misaligned address | 验证 TCDM 地址对齐检查 |
| stride 错误 | misaligned stride | 验证布局参数检查 |
| 不支持输入 | both-zero-`l` | 验证显式 `error` 路径 |
| 完整语义 | full-reference probe | 验证 generic mixed-scalar correctness gate |
| 链式 workload | `rows=8, blocks=4, D=32` | 验证多 row、多 block 的连续 merge |

### 7.3 正确性分层

为了避免把不同问题混在一起，验证分为三层：

1. **近似单元层**：
   `hw/ip/online_merge/test/online_merge_approx_tb.sv` 单独验证 `exp` 和 reciprocal
   approximate unit 的基本行为。
2. **RTL-aligned reference 层**：
   软件 reference 重现 RTL 的 bit-level 近似和定点语义，用来区分“硬件实现错误”
   与“近似方案本身带来的误差”。
3. **系统 workload 层**：
   CTest/Verilator benchmark 验证 MMIO 启动、TCDM 读写、状态寄存器、输出结果、
   错误路径、TCDM counter 和性能结果。

`full-ref-probe` 已由 expected-error 转为 correctness gate，说明 generic
mixed-scalar case 已进入完整正确性验证路径；当前仅保留明确不支持的
both-zero-`l` 等配置作为 error path。

---

## 8. 实验证据：性能、数值和系统行为

### 8.1 Full mixed-scalar sweep

以下 CPU path 是 **RTL-aligned fixed-point software reference**，不是高度优化的
vectorized attention baseline。

| N | D | CPU cycles | Engine cycles | Speedup | TCDM accessed | TCDM congested |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 2327 | 1207 | 1.93x | 327 | 0 |
| 4 | 8 | 17490 | 1478 | 11.83x | 495 | 2 |
| 8 | 16 | 56103 | 2343 | 23.94x | 985 | 4 |
| 8 | 32 | 97554 | 3371 | 28.94x | 1583 | 9 |
| 16 | 64 | 365620 | 9650 | 37.89x | 5229 | 27 |

最大数据点为：

```text
N=16, D=64
speedup = 37.89x
cycle reduction = 97.36%
```

该表支持的结论是：在当前评估 workload 上，SMU path 相比 RTL-aligned software
reference path 具有明显 cycle benefit，且随着 `N` 和 `D` 增大，软件路径的循环
和近似计算成本增长更快。

该表不支持“SMU 已经击败高度优化 attention kernel”或“端到端 attention 获得
37.89x 加速”等表述。

### 8.2 Attention-like merge chain

当前 workload 为：

```text
rows=8, blocks=4, D=32
cpu=388826 cycles
engine=13432 cycles
tcdm_accessed=6188
tcdm_congested=32
state_bytes=4352
saw_busy=1
```

该测试真实调用 SMU hardware path，模拟多 row、多 block 和多 hidden dimension
的 `m/l/O` 连续合并。它比单次 microbenchmark 更接近 online merge 的使用方式，
但仍然不是端到端 attention，因为不包含完整的 QK、mask、PV、runtime 和 DRAM
调度。

### 8.3 数值和流量证据

当前数值/系统证据包括：

- numeric model 最大绝对误差约 `9.78e-6`；
- 当前 benchmark 使用 `1e-3` correctness gate；
- TCDM accessed/congested counter 可观测；
- attention-like chain 能观测到 `saw_busy=1`，证明确实经过硬件 busy path；
- full-reference probe 作为 correctness gate 运行，而不是仅返回 expected-error。

---

## 9. 可复现证据链

### 9.1 RTL 与集成文件

```text
hw/ip/online_merge/src/online_merge_update_engine.sv
hw/ip/online_merge/src/online_merge_fp32_helpers.sv
hw/ip/online_merge/src/online_merge_exp_approx.sv
hw/ip/online_merge/src/online_merge_recip_approx.sv
hw/ip/online_merge/test/online_merge_approx_tb.sv
```

### 9.2 软件与数据处理文件

```text
sw/spatzBenchmarks/online-softmax-merge/main.c
sw/spatzBenchmarks/CMakeLists.txt

data_process/attnres/code/full_merge_numeric_model.py
data_process/attnres/code/plot_attnres_results.py
data_process/attnres/code/plot_paper_b_svg.py

data_process/attnres/data/online_softmax_full_mixed_bypass.csv
data_process/attnres/data/online_softmax_full_merge_numeric.csv
data_process/attnres/data/online_softmax_attention_like_smu.csv
```

### 9.3 文档证据

```text
docs/online-softmax-merge-engine/PLAN.md
docs/online-softmax-merge-engine/PHASE_RESULTS.md
docs/online-softmax-merge-engine/COMPARISON_EXPERIMENT.md
docs/online-softmax-merge-engine/PAPER_ROADMAP.md
docs/online-softmax-merge-engine/PAPER_B_FULL_SYSTEM_PLAN.md
docs/online-softmax-merge-engine/PAPER_AB_ARTICLE_POSITIONING.md
```

这些文件共同形成从 RTL、系统集成、软件调用、测试输出、数值分析到论文图表的
证据链。数据处理工作的重要价值是把 raw benchmark output 转换成可复用的 CSV、
numeric error 结果和论文 SVG，而不是只保留终端日志。

---

## 10. 适合论文 introduction 的贡献表述

可以压缩为以下五点：

### 贡献点 1：低侵入式 offload 架构

本文提出并实现了一个 cluster-local online softmax merge offload 架构，通过
MMIO 控制寄存器和 TCDM master 接口接入 Spatz cluster，在不修改 ISA、decoder、
controller、VFU、VRF 和主指令流水线的前提下，为 `m/l/O` state update 提供专用
硬件执行路径。

### 贡献点 2：完整 mixed-scalar merge datapath

本文实现了完整的 online merge recurrence，在 SMU 内完成 `m_new`、双路指数缩放、
`l_new`、reciprocal-based normalization 以及 `O[D]` 逐元素加权更新，支持 scalar
state 和 vector state 的一致更新。

### 贡献点 3：硬件友好的数值近似与对齐验证

本文采用 exp/reciprocal LUT、线性插值和 Q-format 定点累加构建紧凑 datapath，并
建立 RTL-aligned software reference、host numeric model 和 standalone approximation
testbench，从而能够分别评估实现正确性和近似误差。

### 贡献点 4：可运行的系统 benchmark 和错误回归

本文构建覆盖 full mixed-scalar sweep、stride-zero layout、invalid configuration、
unsupported case、full-reference probe 和 attention-like merge chain 的 benchmark
体系，并通过 CTest/Verilator 验证 MMIO、TCDM、状态寄存器、输出结果和 error path。

### 贡献点 5：性能与系统行为量化

在当前评估范围内，SMU path 相比 RTL-aligned software reference path 最高达到
`37.89x` speedup，对应 `97.36%` cycle reduction；同时记录 TCDM accessed/congested
counter 和 attention-like chain 结果，为后续 datapath 扩展和完整 attention 集成
提供量化依据。

---

## 11. 论文、答辩和简历版本

### 11.1 英文长版本

```text
I designed and implemented a low-intrusion, cluster-local online softmax
merge offload engine for Spatz. The engine is controlled through MMIO and
accesses merge states through a TCDM master path without modifying the Spatz
ISA or the main vector pipeline. It implements the full mixed-scalar online
merge recurrence, including max update, exponential rescaling, reciprocal-
based normalization, and element-wise O-state update, using LUT-based exp /
reciprocal approximations and fixed-point accumulation. I also built an
RTL-aligned software reference, standalone approximation tests, CTest
microbenchmarks, error-path regression, and attention-like merge-chain
workloads. On the evaluated full mixed-scalar cases, the prototype achieves
up to 37.89x speedup over the RTL-aligned software reference.
```

### 11.2 中文答辩版本

> 我设计并实现了 Spatz 上的 cluster-local online softmax merge 旁路引擎。该
> 引擎通过 MMIO + TCDM master 接口接入系统，不修改 ISA 和主向量流水线；在硬件
> 内完成完整的 `m/l/O` mixed-scalar online merge，包括 `m` 更新、双路指数缩放、
> `l` 归一化、reciprocal 近似以及 `O` 向量逐元素更新。围绕该引擎，我还建立了
> RTL-aligned software reference、LUT 近似测试、CTest benchmark、错误路径回归和
> attention-like merge-chain workload。在当前评估的 full mixed-scalar case 中，
> 相比 RTL-aligned software reference 最高获得 `37.89x` speedup。

### 11.3 简历短版本

```text
Designed and implemented a cluster-local online softmax merge offload engine
for Spatz with MMIO/TCDM integration, full mixed-scalar merge datapath,
LUT-based exp/reciprocal approximations, fixed-point accumulation, and
RTL-aligned validation. Achieved up to 37.89x speedup over the evaluated
RTL-aligned software reference.
```

---

## 12. 不能过度声称的边界

论文和汇报中应主动说明：

- 当前结果是 Spatz prototype evidence，不是所有平台上的通用性能结论；
- 当前 benchmark 不是端到端 LLM attention benchmark；
- attention-like chain 不包含完整 QK、mask、PV、runtime/DRAM 调度；
- CPU baseline 是 RTL-aligned software reference，不是高度优化的 attention baseline；
- 当前没有面积、功耗、频率或综合后资源数据；
- 当前 numeric validation 是 representative validation，不是全输入空间数学证明；
- 当前最大 full mixed-scalar sweep 规模为 `N=16,D=64`；
- 当前是单个 compact SMU engine，没有展示多 engine、多 head 或大 sequence 的
  端到端 scaling；
- `37.89x` 只适用于当前评估点和当前 baseline，不应写成端到端 attention speedup。

推荐使用“在当前评估范围内”“相比 RTL-aligned software reference”“attention-like
merge chain”这些限定语，避免把系统原型的结果扩大为通用硬件结论。

---

## 13. 后续工作

当前贡献自然导向以下扩展：

1. 将 SMU 接入完整 attention kernel，而不仅是 attention-like merge chain；
2. 增加 vector-lane parallelism 或复制 SMU，提高 `O[D]` update 吞吐；
3. 评估不同 LUT 大小和 interpolation 策略的误差、面积、延迟 trade-off；
4. 加入真实 attention trace 和随机 stress suite，扩大数值验证覆盖；
5. 进行综合、面积、功耗和频率评估；
6. 研究更低开销的启动机制，降低 MMIO launch overhead；
7. 分析 TCDM bandwidth/congestion 对更大 workload 的影响。

---

## 14. 最终表述

如果只能保留一段话，建议使用：

> 本工作针对 block-wise attention 中的 online softmax merge，设计并实现了一个
> 低侵入式 cluster-local SMU。该引擎通过 MMIO 控制和 TCDM master 访问状态，在
> 不修改 Spatz ISA 和主流水线的前提下，实现完整 `m/l/O` mixed-scalar merge
> recurrence，并采用 LUT-based exp/reciprocal 近似和定点累加构建面向硬件的
> datapath。通过 RTL-aligned reference、CTest benchmark、错误路径回归、数值模型
> 和 attention-like merge chain，建立了从功能正确性到系统性能的验证闭环；在当前
> full mixed-scalar 评估中，相比 RTL-aligned software reference 最高达到 `37.89x`
> speedup。该结果应定位为 Spatz 上的 architecture/system prototype evidence，
> 而不是端到端 attention accelerator 的最终性能结论。
