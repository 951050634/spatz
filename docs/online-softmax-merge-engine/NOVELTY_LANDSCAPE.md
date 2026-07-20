# SMU 创新性检索与竞争工作矩阵

## 1. 文档状态

- 当前状态：`in_progress`；
- 检索日期：2026-07-20；
- 当前轮次：第一轮元数据发现与候选筛选；
- 证据等级：标题、摘要和 DOI 元数据，尚未完成全部全文精读；
- 当前结论均为待全文核验的工作假设，不支持“首次”或“唯一”表述。

本轮的目标不是罗列所有 Transformer accelerator，而是识别最可能覆盖以下三条
候选贡献的 closest prior art：

1. tile-boundary online-softmax merge 作为独立硬件 offload 粒度；
2. 不修改 Spatz ISA 和主向量流水线的 cluster-local MMIO/TCDM 集成；
3. 完整 mixed-scalar merge recurrence 的硬件实现与瓶颈分解。

## 2. 检索方法

### 2.1 数据源和降级记录

计划使用 Crossref、arXiv、Semantic Scholar 和出版社页面。当前会话中的内置学术
检索和网页检索端点返回 HTTP 404，因此第一轮按 `nature-academic-search` 的降级
规则使用 OpenAlex 公共元数据接口。后续必须用 arXiv 开放全文、作者 manuscript
或出版社页面核验关键架构细节。

### 2.2 第一轮查询

- `online softmax hardware accelerator attention`
- `softmax accelerator exponential reciprocal attention hardware`
- `FlashAttention hardware accelerator online softmax`
- `RISC-V vector attention accelerator scratchpad softmax`
- `attention accelerator online softmax`
- `streaming softmax accelerator transformer`
- `softmax hardware RISC-V accelerator`
- `scratchpad coupled accelerator RISC-V cluster`
- `Softermax hardware software co-design`
- `ITA energy efficient attention softmax accelerator`
- `FuseMax attention accelerator`
- `SpAtten sparse attention architecture`
- `Energon dynamic sparse attention accelerator`

### 2.3 纳入原则

优先纳入直接处理 softmax/online-softmax、明确实现 attention datapath、展示非线性
函数硬件或与 RISC-V cluster 紧耦合的工作。纯模型压缩、通用 DNN survey 和与
Transformer softmax 无关的结果不进入核心矩阵。

## 3. 第一轮候选矩阵

| 工作 | 类别 | 初步重合点 | 必须核验的问题 | 风险 |
| --- | --- | --- | --- | --- |
| Online Normalizer Calculation for Softmax | 算法 | 在线最大值与归一化状态 | 是否包含可组合 merge 形式 | 背景 |
| FlashAttention / FlashAttention-2 | 算法和 GPU kernel | blockwise online softmax 与状态重标定 | 精确状态定义、merge 粒度和接口 | 高 |
| Softermax | softmax HW/SW co-design | exponential/division 近似和硬件友好 softmax | 是否支持在线或分块状态合并 | 高 |
| ITA | attention/softmax accelerator | 量化 attention 与 softmax 专用硬件 | softmax 单元粒度、存储接口和数据流 | 高 |
| FuseMax | 完整 attention accelerator | operator fusion、online softmax 和片上状态 | 是否已显式实现同一 merge recurrence | 极高 |
| Flexible Template for Edge GenAI | PULP 非线性加速 | Softmax/GELU 单元、RISC-V/PULP 生态 | 集成接口、共享 scratchpad 和 ISA 关系 | 极高 |
| Hardware-Efficient SoftMax Architecture | softmax 电路 | exponentiation 和 reciprocal 硬件 | 数值方法、吞吐和是否支持 streaming | 中高 |
| SpAtten | sparse-attention accelerator | attention softmax 与专用数据流 | softmax 是否在线、是否与剪枝绑定 | 中 |
| Energon | sparse-attention accelerator | attention 数据流与 softmax | 是否存在独立状态更新或 merge engine | 中 |
| Spatz | 基础平台 | RISC-V vector cluster、TCDM 和可扩展计算 | 原论文是否已有外围 accelerator 模式 | 平台 |
| OpenGeMM | 紧耦合 RISC-V accelerator | lightweight RISC-V control 和 memory coupling | 控制/存储接口与本项目的共性 | 集成背景 |

## 4. 关键元数据

以下条目已获得 DOI 或 arXiv 标识，仍需全文核验：

1. Stevens et al., “Softermax: Hardware/Software Co-Design of an Efficient
   Softmax for Transformers,” DAC 2021,
   <https://doi.org/10.1109/DAC18074.2021.9586134>.
2. Islamoglu et al., “ITA: An Energy-Efficient Attention and Softmax
   Accelerator for Quantized Transformers,” ISLPED 2023,
   <https://doi.org/10.1109/ISLPED58423.2023.10244348>.
3. Nayak et al., “FuseMax: Leveraging Extended Einsums to Optimize Attention
   Accelerator Design,” MICRO 2024,
   <https://doi.org/10.1109/MICRO61859.2024.00107>;
   OA preprint: <https://doi.org/10.48550/arXiv.2406.10491>.
4. Belano et al., “A Flexible Template for Edge Generative AI With
   High-Accuracy Accelerated Softmax and GELU,” JETCAS 2025,
   <https://doi.org/10.1109/JETCAS.2025.3562734>;
   OA preprint: <https://doi.org/10.48550/arXiv.2412.06321>.
5. Kim et al., “Hardware-Efficient SoftMax Architecture With Bit-Wise
   Exponentiation and Reciprocal Calculation,” TCAS-I 2024,
   <https://doi.org/10.1109/TCSI.2024.3443270>.
6. Wang et al., “SpAtten: Efficient Sparse Attention Architecture With Cascade
   Token and Head Pruning,” HPCA 2021,
   <https://doi.org/10.1109/HPCA51647.2021.00018>;
   OA preprint: <https://doi.org/10.48550/arXiv.2012.09852>.
7. Zhou et al., “Energon: Toward Efficient Acceleration of Transformers Using
   Dynamic Sparse Attention,” TCAD 2022,
   <https://doi.org/10.1109/TCAD.2022.3170848>;
   OA preprint: <https://doi.org/10.48550/arXiv.2110.09310>.
8. Dao, “FlashAttention-2: Faster Attention With Better Parallelism and Work
   Partitioning,” 2023, <https://doi.org/10.48550/arXiv.2307.08691>.
9. Perotti et al., “Spatz: Clustering Compact RISC-V-Based Vector Units to
   Maximize Computing Efficiency,” TCAD 2025,
   <https://doi.org/10.1109/TCAD.2025.3528349>.
10. Yi et al., “OpenGeMM: A Highly-Efficient GeMM Accelerator Generator With
    Lightweight RISC-V Control and Tight Memory Coupling,” 2025,
    <https://doi.org/10.1145/3658617.3697652>.

## 5. 当前创新判断

### 5.1 已被否定的宽泛主张

- “首次用硬件加速 softmax”明显不成立；
- “首次为 attention 加入专用 softmax 单元”明显不成立；
- “使用 LUT/近似 exponential 和 reciprocal”本身不构成充分创新；
- “不修改 ISA 的专用 accelerator”很可能是常见系统集成模式，不能单独作为
  novelty claim。

### 5.2 仍可能成立的窄主张

以下内容尚未被第一轮元数据直接覆盖，但必须通过全文证明：

1. 将完整 blockwise online-softmax 的 `(m,l,O)` merge recurrence 作为独立、
   tile-boundary、cluster-local offload，而不是完整 softmax 或完整 attention
   pipeline 的一个内部阶段；
2. 让现有 RISC-V vector cluster 继续执行 QK/PV 和通用向量工作，只通过现有
   MMIO/TCDM 边界旁路逐行 merge，不修改 ISA 和向量流水线；
3. 用 A0/A1/A2 实测证明收益来自消除逐行 scalar recurrence，并揭示瓶颈随后
   转移到 vector streaming，而不是仅报告整体 speedup。

第三条更适合作为解释性实验贡献，不能替代架构创新。

### 5.3 最高风险近邻

1. **FuseMax**：最可能已实现相同在线状态合并，但其系统粒度可能是完整 attention
   accelerator，而非可复用的 cluster-local auxiliary engine。
2. **Flexible Template for Edge GenAI**：与 Spatz 同属 PULP/Benini 生态，可能
   已采用共享 scratchpad 和外围非线性加速器，是“集成方式”主张的直接威胁。
3. **ITA**：可能同时覆盖 attention、softmax 和量化非线性 datapath，是完整功能
   与 PPA 对比的主要基线。
4. **Softermax**：直接威胁 LUT/近似算法的独立创新，但未必覆盖 online merge。

## 6. 下一轮全文核验表

| 优先级 | 工作 | 核验内容 | 状态 |
| ---: | --- | --- | --- |
| 1 | FuseMax | online state 方程、硬件边界、buffer 和数据流 | `pending_fulltext` |
| 2 | Flexible Template | RISC-V/PULP 接口、scratchpad coupling、ISA 改动 | `pending_fulltext` |
| 3 | ITA | softmax 单元、量化格式、端到端范围和 PPA | `pending_fulltext` |
| 4 | Softermax | 近似方法、online/blockwise 支持和 HW/SW 接口 | `pending_fulltext` |
| 5 | FlashAttention-2 | merge recurrence、状态和工作划分 | `pending_fulltext` |
| 6 | Hardware-Efficient SoftMax | exp/reciprocal 结构和设计空间 | `pending_fulltext` |
| 7 | SpAtten/Energon | softmax 数据流及其与完整 accelerator 的关系 | `pending_fulltext` |

全文核验完成前，不冻结最终标题、摘要或贡献列表。
