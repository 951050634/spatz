# Paper B Full-System Plan

本文档是后续 `/goal` 实现论文 B 的执行蓝图。目标是把当前
cluster-local online softmax merge-update engine 从论文 A 的受限语义原型推进为
完整 online softmax merge 旁路硬件单元，并最终接入 attention-like / attention
workload 评估。

## 1. Baseline and Boundaries

### 当前基线

论文 A 已作为阶段性工作完成，内容包括：

- MMIO 控制寄存器和状态寄存器。
- cluster-local TCDM master 旁路硬件单元。
- 受限语义 RTL：`l_old=0`、`l_tile=0`、等权重特例。
- Verilator benchmark、invalid / unsupported path、zero-stride packed layout。
- CPU scalar path vs engine path A/B 实验。
- break-even sweep、三次稳定性运行、TCDM counter 记录。
- AttnRes/SMU 绘图脚本、CSV、论文 A LaTeX 初稿。

论文 A 的数据可以作为 baseline 和背景使用，但不能作为完整 online softmax merge
方程的性能证据。

### 论文 B 目标

实现完整 mixed-scalar online softmax merge 方程：

```text
m_new = max(m_old, m_tile)

l_new = l_old * exp(m_old - m_new)
      + l_tile * exp(m_tile - m_new)

O_new = O_old  * (l_old  * exp(m_old  - m_new) / l_new)
      + O_tile * (l_tile * exp(m_tile - m_new) / l_new)
```

论文 B 需要证明：

- 完整方程在硬件旁路 SMU 中可执行。
- 近似 `exp` 和 reciprocal 的误差可控。
- 完整 mixed-scalar 输入下，至少一个目标规模中 engine path 快于 CPU scalar
  reference path。
- attention-like workload 中有端到端 cycle/runtime proxy 或 traffic 改善证据。

### 固定设计边界

- 不修改 Spatz ISA、decoder、controller、VFU、VRF、VLSU 或指令 pipeline。
- SMU 仍是 cluster-local 旁路硬件单元。
- SMU 仍只访问 TCDM buffer，不直接访问 DRAM。
- 第一版保持现有 `MERGE_*` MMIO 寄存器和 TCDM layout 不变。
- 第一版不新增近似模式寄存器；近似参数先用 RTL `parameter` / `localparam`
  固定。
- 第一版只承诺 finite normal FP32 输入。NaN、Inf、subnormal 可以先作为
  unsupported 或 error path 处理。

## 2. Architecture Direction

### Datapath 选择

论文 B 第一版采用直接近似硬件 datapath：

- `exp`：LUT 或分段 LUT 近似。
- 除法：转换为 reciprocal 近似后乘法。
- `l_new`：两个 scaled `l` 相加。
- `O_new`：对每个 `O` 元素流式计算 old/tile 权重并加权累加。

优先级：

1. 先打通完整方程 correctness。
2. 再做近似参数 sweep。
3. 最后优化 latency、TCDM schedule 和资源。

### 接口策略

第一版保持现有接口：

```text
MERGE_SRC_M_OLD
MERGE_SRC_L_OLD
MERGE_SRC_O_OLD
MERGE_SRC_M_TILE
MERGE_SRC_L_TILE
MERGE_SRC_O_TILE
MERGE_DST_M
MERGE_DST_L
MERGE_DST_O
MERGE_N
MERGE_D
MERGE_STRIDE
MERGE_CTRL
MERGE_STATUS
```

保持现有 layout：

```text
m_old[N], l_old[N], O_old[N][D]
m_tile[N], l_tile[N], O_tile[N][D]
m_out[N], l_out[N], O_out[N][D]
```

如果后续需要 sweep 多种近似配置，再单独增加模式/参数寄存器；不要在第一版
datapath 未稳定前扩大 reggen、runtime 和文档改动面。

## 3. Execution Roadmap

### Phase B0：文档和状态冻结

目标：

- 将论文 A 标记为阶段完成。
- 固定论文 B 的旁路 SMU 路线。
- 明确不修改 Spatz pipeline。

产出：

- 本文档。
- `README.md`、`PHASE_RESULTS.md`、`PAPER_ROADMAP.md` 指向本文档。

验收：

- 后续 `/goal` 可以直接从 Phase B1 开始实现，不需要重新决定系统路线。

### Phase B1：软件数值模型

目标：

- 建立完整方程 reference。
- 建立 `ExpLUT + reciprocal` 近似模型。
- 定义误差统计和输入范围。

实现要点：

- 在 benchmark 或数据处理脚本中实现完整 FP32 reference。
- 单独实现与 RTL 计划一致的近似模型，避免 RTL 完成后才发现误差不可控。
- 覆盖 `m_old > m_tile`、`m_old < m_tile`、`m_old == m_tile`、`l_old != l_tile`、
  small `l`、mixed signed `O`。

验收：

- 生成固定 full-reference probe golden values。
- 输出 max absolute error、guarded max relative error、mean absolute error。
- 初始近似目标达到 `<= 1e-3`；记录是否可逼近 `<= 1e-4`。

### Phase B2：近似 RTL 模块

目标：

- 实现 SMU 内部可复用的近似数学模块。

建议模块：

```text
hw/ip/online_merge/src/online_merge_exp_approx.sv
hw/ip/online_merge/src/online_merge_recip_approx.sv
hw/ip/online_merge/src/online_merge_fp32_helpers.sv
```

实现要点：

- `exp_approx(x)` 的输入主要是 `m_old - m_new` 或 `m_tile - m_new`，理论上
  `x <= 0`。
- 对超出设计范围的输入输出饱和值或 error，行为必须与软件近似模型一致。
- reciprocal 只需要覆盖正 finite normal `l_new`。
- 先采用清晰、可调试的 pipeline；后续再压 latency。

验收：

- 近似模块可单独编译。
- 模块级 testbench 或集成 benchmark 能证明近似输出与软件模型一致。

### Phase B3：完整 SMU datapath

目标：

- 替换当前受限语义 datapath，支持完整 mixed-scalar merge。

实现要点：

- 保留现有 MMIO、配置校验、TCDM load/store、`busy/done/error` 协议。
- 移除或收窄 `supported_scalar_merge()` 的受限语义检查。
- 新增完整 scalar stage：
  - 计算 `m_new`。
  - 计算 `old_exp = exp(m_old - m_new)`。
  - 计算 `tile_exp = exp(m_tile - m_new)`。
  - 计算 `old_scaled_l`、`tile_scaled_l` 和 `l_new`。
  - 计算 `old_weight = old_scaled_l * recip(l_new)`。
  - 计算 `tile_weight = tile_scaled_l * recip(l_new)`。
- vector stage 对每个元素计算：
  - `O_new[j] = O_old[j] * old_weight + O_tile[j] * tile_weight`。

验收：

- `make -C hw/system/spatz_cluster bin/spatz_cluster.vlt` 通过。
- `make -C hw/system/spatz_cluster sw.vlt` 通过。

### Phase B4：Full Microbenchmark Gate

目标：

- 把 `online-softmax-merge` benchmark 从受限语义验证升级为完整方程验证。

实现要点：

- `run_full_reference_probe_case()` 不再 expected-error，改为输出比对 PASS gate。
- 保留 invalid config error path。
- 保留受限 case 作为回归 case，但不再作为主要论文 B 证据。
- 增加完整 mixed-scalar sweep：
  - `N=1,D=1`
  - `N=4,D=8`
  - `N=8,D=16`
  - `N=8,D=32`
  - `N=16,D=64`
  - stride-zero packed layout

验收：

- `ctest -R online-softmax-merge -V` 通过。
- 完整 mixed-scalar cases 误差达到 `<= 1e-3`。
- 至少一个完整 mixed-scalar case 中 engine path 快于 CPU scalar reference path。
- stdout 记录 `cpu_cycles`、`engine_cycles`、`tcdm_accessed`、`tcdm_congested`。

### Phase B5：近似参数 sweep 和图表

目标：

- 形成论文 B 的 numeric design 证据。

实现要点：

- sweep `exp` LUT 精度、分段数量或 reciprocal 精度。
- 每个配置记录误差、cycles、TCDM counters、资源 proxy。
- 更新 CSV 和绘图脚本，新增完整方程图表。

验收：

- 生成误差-性能折中图。
- 说明为什么选择最终近似配置。
- 尝试逼近 `<= 1e-4`，如果不能达到，记录原因和论文 caveat。

### Phase B6：Attention-Like 合成 workload

目标：

- 从 microbenchmark 过渡到更接近 attention 的计算分布。

“合成”的含义：

- 输入仍由仓库脚本生成，而不是接完整模型推理栈。
- 数据形态模拟 attention 中的 online softmax state merge：多层、多 block、
  多 query row、多 hidden dimension。
- 重点验证 `m/l/O` merge 计算链，而不是完整 LLM runtime。

实现要点：

- 复用或扩展 `attnres-baselines` 的数据生成和验证链。
- 让硬件 path 真正调用完整 SMU，而不是只展示软件 traffic。
- 记录 correctness、误差、cycles/runtime proxy、traffic。

验收：

- 至少一个 attention-like workload 输出在误差阈值内。
- 至少一个配置展示 engine path 相比 CPU/software baseline 的 cycle 或 runtime
  proxy 改善。

### Phase B7：真实 attention 尝试

目标：

- 尝试接完整 attention kernel，提升论文 B 的终极说服力。

“真实”的含义：

- 不只生成 `m/l/O` state，而是从 Q/K/V 或等价 attention 输入出发。
- 包含 QK、online softmax/merge、PV/output 的端到端计算路径。
- SMU 作为完整 attention 流中的旁路硬件调用点。

验收：

- 如果能接通：记录端到端 correctness、cycles、traffic 和 speedup。
- 如果成本过高：明确降级为完整 SMU + attention-like workload + numeric/traffic
  analysis，不再声称真实 attention 端到端加速。

## 4. Test and Evidence Plan

### 构建命令

```bash
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
make -C hw/system/spatz_cluster sw.vlt
```

### 功能测试

```bash
cd hw/system/spatz_cluster/sw/build
ctest -R online-softmax-merge -V
```

必须保留的测试：

- invalid `N=0`
- invalid `D=0`
- misaligned address
- misaligned stride
- stride-zero packed layout
- mixed-scalar full-reference probe

### 精度指标

必须记录：

- max absolute error
- guarded max relative error
- mean absolute error

阈值：

- 第一 gate：`<= 1e-3`
- 第二 gate：尝试逼近 `<= 1e-4`

### 性能指标

必须记录：

- CPU scalar cycles
- engine cycles
- speedup
- cycle reduction
- TCDM accessed
- TCDM congested

论文 B 的完整方程性能必须重跑，不能沿用论文 A 受限语义 speedup。

## 5. Documentation Updates During Implementation

每完成一个 Phase，应同步更新：

- [PHASE_RESULTS.md](PHASE_RESULTS.md)
- [COMPARISON_EXPERIMENT.md](COMPARISON_EXPERIMENT.md)
- `data_process/attnres/README.md`
- 相关 CSV 和图表脚本
- 论文 B LaTeX 草稿

新增图表建议：

- 完整 datapath block diagram。
- `exp` / reciprocal 近似误差图。
- 完整 mixed-scalar CPU vs engine cycles。
- 完整 mixed-scalar speedup。
- attention-like workload runtime proxy。
- TCDM accessed/congested vs workload size。

## 6. Risks and Fallbacks

| Risk | Impact | Fallback |
|---|---|---|
| 近似误差达不到 `1e-3` | 无法通过 correctness gate | 增加 LUT 精度或收窄输入范围 |
| reciprocal 误差放大 | `O_new` 误差超限 | 使用一次 Newton refinement |
| 完整 datapath 太慢 | speedup 不成立 | 聚焦 larger `N*D` 和 latency 分析 |
| RTL 复杂度过高 | 验证周期失控 | 先固定有限输入范围和单 outstanding TCDM |
| attention-like 接不上硬件 path | 论文 B 证据不足 | 保留完整 microbenchmark + numeric design 论文路线 |
| 真实 attention 接入过重 | 终极系统延期 | 降级为 future work，不写端到端真实 attention speedup |

## 7. Commit Structure

建议按以下顺序拆提交：

```text
[docs] Mark restricted merge paper phase complete
[smu] Add full merge numeric reference model
[smu] Add exp and reciprocal approximation units
[smu] Implement full online merge datapath
[bench] Convert full-reference probe to correctness gate
[bench] Add full mixed-scalar sweep and error metrics
[eval] Record full merge comparison experiment
[attn] Add attention-like merge workload
[paper] Update paper B figures and draft
```
