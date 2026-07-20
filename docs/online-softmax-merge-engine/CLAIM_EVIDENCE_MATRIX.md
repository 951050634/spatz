# SMU Claim–Evidence Matrix

## 1. 使用规则

本文档将候选论文主张映射到仓库证据和 closest prior art。状态含义：

- `candidate`：有本地证据，但创新性尚未闭环；
- `supported`：本地证据与 prior-art 差异均已核验；
- `result_only`：可作为实验结果，不作为创新；
- `blocked`：当前缺少必要证据；
- `rejected`：不得进入论文。

任何 headline claim 必须达到 `supported`。模型、RTL measurement、proxy 和推断必须
在正文中明确区分。

## 2. 主张矩阵

| ID | 候选主张 | 本地证据 | Prior-art 风险 | 状态 |
| --- | --- | --- | --- | --- |
| C1 | SMU 通过现有 MMIO/TCDM 边界集成，不修改 Spatz ISA 和主向量流水线 | RTL、寄存器、cluster integration、软件 benchmark | PULP 非线性 accelerator 和通用紧耦合 accelerator 可能已有相同模式 | `candidate` |
| C2 | SMU 独立执行完整 `(m,l,O)` mixed-scalar merge recurrence | full-reference gate、mixed sweep、FSM 和 approximation RTL | FuseMax、ITA 和 FlashAttention hardware 可能覆盖相同方程 | `candidate` |
| C3 | B3 在 16 个直接测量点均优于 B2-R | formal scaling artifacts 和结构化分析 | 这是结果，不是架构创新 | `result_only` |
| C4 | SMU 消除逐行 scalar bottleneck，随后暴露 vector-streaming bottleneck | 拟合模型和三个 FSM anchors | 需要 A1 才能严格分离 scalar 与 vector 贡献 | `blocked` |
| C5 | SMU 与 core stream 在共享 TCDM 上可以重叠执行 | 16 bank-phase concurrency artifacts | 仅对一个 engine、一个 core stream 和一个规模成立 | `result_only` |
| C6 | 256 段 LUT 在评测输入上保持较小误差 | host model 和 RTL correctness | Softermax 等已有近似；当前没有参数设计空间 | `candidate` |
| C7 | SMU 改善完整 attention kernel 的运行时间 | 当前只有 attention-like merge chain | 缺少共享 QK/PV 的 end-to-end 对比 | `blocked` |
| C8 | SMU 具有面积、频率、功耗或能效优势 | generic cells 和 RTL toggles | 缺少物理库、PVT、时序和功耗流程 | `rejected` |

## 3. 当前允许的措辞

### C1

允许：

> The prototype attaches an SMU through the existing cluster peripheral and
> TCDM interfaces and leaves the Spatz ISA and main vector pipeline unchanged.

禁止：

> This is the first ISA-preserving accelerator integration for RISC-V vector
> clusters.

### C2

允许：

> The SMU implements the evaluated mixed-scalar online merge recurrence,
> including maximum tracking, exponential rescaling, reciprocal-based
> normalization, and the weighted output update.

禁止：

> The SMU is the first hardware implementation of online softmax merge.

### C3 和 C4

允许：

> Across the 16 directly measured coordinates, B3 is faster than the
> RTL-aligned B2-R baseline. FSM measurements show that vector streaming
> dominates SMU busy time at the larger anchors.

在 A1 完成前禁止：

> The ablation proves the independent benefit of scalar offload and vector
> offload.

### C6

允许：

> The recorded cases bound the observed error of the selected 256-segment
> configuration.

禁止：

> The approximation guarantees bounded error for all attention inputs.

### C7

当前只允许：

> The merge-chain workload exercises repeated SMU state updates but excludes
> QK, PV, masking, and complete attention scheduling.

blocked-attention 实验闭环后才能讨论完整 kernel cycles。

## 4. 证据补全顺序

1. 精读 FuseMax、Flexible Template、ITA 和 Softermax，决定 C1/C2 是否能够升级；
2. 实现 scalar-only A1，将 C4 从 `blocked` 推进到可验证；
3. 完成 blocked-attention benchmark，将 C7 从 `blocked` 推进到直接测量结果；
4. 完成 LUT 参数 sweep，为 C6 增加设计选择依据；
5. 不投入无 PDK 条件下的物理 PPA 伪量化，C8 保持 `rejected`。
