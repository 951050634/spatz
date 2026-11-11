# Online Softmax Merge 加速器 RTL 设计讨论

## 1. 文档目的

本文记录当前 Spatz online softmax merge-update engine（下文简称 SMU）的
RTL 实现状态、已经完成的硬件设计改进、现有微架构瓶颈，以及下一阶段建议实施的
RTL 优化。

本文聚焦硬件设计本身，不将软件 benchmark、RTL-aligned reference 或
attention-like workload 的结果扩大为端到端 attention 性能结论。

记录基线：

- 分支：`feature/online-softmax-merge-engine`
- 检查日期：2026-07-13
- 检查时 HEAD：`136da62`
- 最后一次核心 datapath RTL 提交：
  `00ba358 [smu] Implement full mixed merge datapath`（2026-06-06）

截至本文记录时，工作区中没有未提交的 RTL 修改；最近的工作主要集中在 benchmark、
实验数据、论文材料和文档整理。因此，准确状态是：**RTL 已经有实质性改造，但当前
没有新的 RTL 优化正在工作区中进行。**

## 2. 总体结论

SMU 已经不是纯软件模型或孤立的 testbench，而是一个接入 Spatz cluster 的
cluster-local 硬件旁路引擎。当前实现已经包含：

- 独立的 online softmax merge-update engine；
- MMIO 配置、启动和状态接口；
- 独立的 TCDM master 访问路径；
- 完整 mixed-scalar online softmax merge 方程；
- 两个基于 LUT 的 exponential 近似单元；
- 一个基于 LUT 的 reciprocal 近似单元；
- Q-format 定点缩放、权重和向量 merge 数据通路；
- `busy`、`done`、`error` 控制状态；
- 地址对齐、维度和 FP32 输入范围检查；
- standalone 近似模块测试和系统级 Verilator benchmark。

不过，当前 RTL 更适合定位为“功能闭环的第一版微架构”。它还没有完成针对综合
频率、面积和最高 TCDM 吞吐量的系统优化。

## 3. RTL 修改范围

相对 SMU 分支的初始基线，硬件和系统集成主要涉及以下文件：

```text
Bender.yml
hw/ip/online_merge/src/online_merge_exp_approx.sv
hw/ip/online_merge/src/online_merge_fp32_helpers.sv
hw/ip/online_merge/src/online_merge_recip_approx.sv
hw/ip/online_merge/src/online_merge_update_engine.sv
hw/ip/online_merge/test/online_merge_approx_tb.sv
hw/system/spatz_cluster/src/spatz_cluster.sv
hw/system/spatz_cluster/src/spatz_cluster_peripheral/
  spatz_cluster_peripheral.sv
  spatz_cluster_peripheral_reg.hjson
  spatz_cluster_peripheral_reg_pkg.sv
  spatz_cluster_peripheral_reg_top.sv
```

主要 RTL 演进提交为：

```text
957667e  2026-05-25  [smu] Add online merge engine prototype
5495b4d  2026-05-25  [smu] Reject unsupported merge cases
0231695  2026-06-01  [smu] Add exp and reciprocal approximation units
00ba358  2026-06-06  [smu] Implement full mixed merge datapath
```

## 4. 当前硬件架构

### 4.1 控制方式

SMU 采用低侵入式旁路架构：

```text
CPU
  |
  | MMIO configuration/start/status
  v
Cluster peripheral registers
  |
  v
Online merge-update engine
  |
  | independent TCDM master
  v
TCDM interconnect and banks
```

当前实现不修改：

- Spatz ISA；
- decoder；
- controller；
- VFU；
- VRF；
- VLSU；
- 主向量指令 pipeline。

这降低了系统集成风险，但每个任务仍需要软件通过 MMIO 配置和启动。

### 4.2 MMIO 配置

当前软件可以配置：

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

状态包括：

```text
busy
done
error
```

外围寄存器集成位于：

```text
hw/system/spatz_cluster/src/spatz_cluster_peripheral/
  spatz_cluster_peripheral.sv
  spatz_cluster_peripheral_reg.hjson
```

### 4.3 TCDM 集成

SMU 被作为非 core master 接入 cluster TCDM interconnect。相关例化位于：

```text
hw/system/spatz_cluster/src/spatz_cluster.sv
```

TCDM interconnect 输入包含：

```systemverilog
{axi_soc_req, merge_req, tcdm_req}
```

SMU 可以直接读取和写回：

```text
m_old, l_old, O_old
m_tile, l_tile, O_tile
m_new, l_new, O_new
```

因此 CPU 不需要逐元素执行输出状态 merge。

## 5. 已经完成的硬件算法升级

### 5.1 从受限原型升级为完整 merge

早期 prototype 主要处理：

- `l_tile == 0` 时选择 old state；
- `l_old == 0` 时选择 tile state；
- 两边均有效时使用简化的近似平均更新输出向量。

当前 RTL 已实现完整 mixed-scalar online softmax merge：

\[
m_{new}=\max(m_{old},m_{tile})
\]

\[
a=\exp(m_{old}-m_{new}),\qquad
b=\exp(m_{tile}-m_{new})
\]

\[
l_{new}=a l_{old}+b l_{tile}
\]

\[
w_{old}=\frac{a l_{old}}{l_{new}},\qquad
w_{tile}=\frac{b l_{tile}}{l_{new}}
\]

\[
O_{new}[j]=w_{old}O_{old}[j]+w_{tile}O_{tile}[j]
\]

核心实现位于：

```text
hw/ip/online_merge/src/online_merge_update_engine.sv
```

### 5.2 状态机

当前主要状态包括：

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

总体执行顺序为：

1. 依次读取一行的 `m_old/l_old/m_tile/l_tile`；
2. 计算 `m_new`、两个 exponential scale 和 `l_new`；
3. 计算 reciprocal 和 old/tile 权重；
4. 写回 `m_new/l_new`；
5. 逐元素读取 `O_old/O_tile`，计算并写回 `O_new`；
6. 处理下一行，或进入 `DONE`。

## 6. 数学近似数据通路

### 6.1 Exponential 近似

模块：

```text
hw/ip/online_merge/src/online_merge_exp_approx.sv
```

当前配置：

- 输入设计范围：`[-8, 0]`；
- 256 段 Q1.23 LUT；
- 相邻 LUT 项之间线性插值；
- `x > 0` 饱和到 1；
- `x < -8` 饱和到 0；
- NaN/Inf 返回 unsupported；
- engine 内部并行例化两个 exp 单元。

两个 exp 单元分别处理：

```text
m_old - m_new
m_tile - m_new
```

### 6.2 Reciprocal 近似

模块：

```text
hw/ip/online_merge/src/online_merge_recip_approx.sv
```

当前配置：

- 输入为正 finite normal FP32；
- 对 `[1, 2]` mantissa 使用 256 段 Q1.23 LUT；
- 相邻 LUT 项之间线性插值；
- 输出 reciprocal mantissa 和指数缩放；
- 当前没有 Newton-Raphson refinement。

### 6.3 内部定点格式

辅助包：

```text
hw/ip/online_merge/src/online_merge_fp32_helpers.sv
```

当前主要格式包括：

- Q1.23：exponential 和 reciprocal 结果；
- 48-bit、32 fractional bits：length、weight 和输出中间结果。

注意：当前类型名为：

```systemverilog
typedef logic [47:0] uq16_16_t;
typedef logic signed [47:0] sq16_16_t;
localparam int unsigned UQ_FRAC_BITS = 32;
```

从实际 fractional bits 看，它更接近 `UQ16.32/SQ16.32`。后续应考虑重命名，避免
文档、软件 reference 和 RTL 对 Q-format 的理解出现偏差。

## 7. 当前输入和错误检查

当前 RTL 已检查：

- `N != 0`；
- `D != 0`；
- source/destination 地址按 4 byte 对齐；
- stride 为 0 或按 4 byte 对齐；
- `stride == 0` 时使用 `D * 4`；
- `m_old/m_tile` 为 finite normal 或 zero；
- `l_old/l_tile` 为非负 finite normal 或 zero；
- both-zero-`l` 进入 error；
- NaN、Inf 和 subnormal 不在当前数值承诺范围内。

当前不足：

- 只有单一 `error` bit，没有具体 error code；
- 没有完整 TCDM 地址范围检查；
- 没有检查地址计算 overflow；
- 没有默认检查 `stride >= D * 4`；
- 定点转换和乘法缺少系统化 overflow/underflow 状态；
- exp saturation 信号已存在，但没有反馈给软件。

## 8. 当前性能证据及边界

当前 full mixed-scalar sweep 的记录为：

| N | D | CPU cycles | Engine cycles | Speedup |
|---:|---:|---:|---:|---:|
| 1 | 1 | 2327 | 1207 | 1.93x |
| 4 | 8 | 17490 | 1478 | 11.83x |
| 8 | 16 | 56103 | 2343 | 23.94x |
| 8 | 32 | 97554 | 3371 | 28.94x |
| 16 | 64 | 365620 | 9650 | 37.89x |

固定近似配置下记录的最差绝对误差约为：

```text
9.78e-6
```

这些结果可以说明：

- 完整 mixed-scalar 方程已经通过真实 SMU RTL path 执行；
- 固定 LUT/定点配置满足当前误差目标；
- 在当前评估 workload 中，engine path 快于 RTL-aligned software reference。

这些结果不能说明：

- 相比优化后的 vector softmax 有相同 speedup；
- 端到端 attention 或 LLM 有 37.89x speedup；
- 当前 RTL 已经完成面积、功耗和 Fmax 优化；
- attention-like merge chain 等同于完整 attention kernel。

## 9. 当前微架构瓶颈

### 9.1 单 outstanding TCDM 请求

当前请求控制主要依赖：

```systemverilog
logic read_pending_q;
op_e  op_q;
```

因此引擎只能安全地跟踪一个 outstanding read。每次 read request 被接受后，状态机
必须等待 response 返回，才能继续发送后续相关请求。

这使 TCDM latency 无法被多个并行请求隐藏。

### 9.2 Scalar load/store 串行

每一行 scalar 阶段包含：

```text
4 reads: m_old, l_old, m_tile, l_tile
2 writes: m_new, l_new
```

这些事务当前基本串行执行。

### 9.3 Vector 每个元素三个事务

每个 `O[j]` 当前需要：

```text
read O_old[j]
read O_tile[j]
write O_new[j]
```

每行 TCDM 操作数量大约为：

\[
6+3D
\]

当 `D=64` 时，一行约有 198 次 scalar/vector TCDM 操作。

### 9.4 64-bit 总线只处理一个 FP32

TCDM data width 为 64 bit，但当前通过地址 bit 选择其中一个 32-bit FP32 lane。
连续向量数据没有被默认打包成每次两个 FP32 处理，导致有效带宽利用率偏低。

### 9.5 算术路径没有系统流水化

当前组合逻辑包含：

- FP32 classification 和转换；
- variable shift；
- exponential LUT 和插值乘法；
- reciprocal LUT 和插值乘法；
- 48x24 bit 乘法；
- 48x48 bit weight 乘法；
- 定点累加；
- 定点到 FP32 normalization。

Verilator cycle 结果不能反映综合后的 critical path。当前尚无证据证明这条数据通路
能在目标频率下收敛。

### 9.6 地址重复使用变量乘法

当前向量地址形式为：

```text
base + row * stride + elem * 4
```

如果综合器不能有效优化，频繁的变量乘法地址计算可能带来额外面积或组合路径。
使用行基址和递增地址寄存器更适合流式硬件。

### 9.7 配置没有在 start 时完整快照

当前 engine 运行过程中会继续直接使用 MMIO 配置输入。如果软件在 `busy` 时修改
配置寄存器，正在运行的任务可能读取到混合配置。

建议 start 被接受时将全部配置锁存到 engine 内部寄存器，此后只使用配置快照。

## 10. 推荐的 RTL 模块拆分

当前主要逻辑集中在 `online_merge_update_engine.sv`。为了方便流水化、复用和验证，
建议逐步拆成以下模块。

### 10.1 `online_merge_engine.sv`

职责：

- command 接收；
- 配置锁存；
- row/block 控制；
- scalar/vector 阶段调度；
- `busy/done/error`；
- 异常状态汇总。

### 10.2 `online_merge_tcdm_frontend.sv`

职责：

- TCDM request FIFO；
- response metadata/tag FIFO；
- outstanding request 管理；
- packed FP32 load/store；
- backpressure；
- 可选的 response reorder。

推荐 metadata：

```systemverilog
typedef enum logic [2:0] {
  TAG_M_OLD,
  TAG_L_OLD,
  TAG_M_TILE,
  TAG_L_TILE,
  TAG_O_OLD,
  TAG_O_TILE,
  TAG_STORE
} merge_tag_e;
```

### 10.3 `online_merge_scalar_pipe.sv`

输入：

```text
m_old, l_old, m_tile, l_tile
```

输出：

```text
m_new, l_new, old_weight, tile_weight, status
```

推荐使用 valid/ready 接口，使 pipeline latency 与控制器解耦。

### 10.4 `online_merge_vector_pipe.sv`

输入：

```text
O_old lane(s)
O_tile lane(s)
old_weight
tile_weight
```

输出：

```text
O_new lane(s)
```

该模块可以参数化为单 lane 或双 lane。

### 10.5 `online_merge_addr_gen.sv`

职责：

- 行基址初始化；
- scalar 地址生成；
- vector 地址递增；
- stride 和 tail 管理；
- 地址范围/overflow 检查。

## 11. 第一优先级：健壮性改进

### 11.1 启动时锁存配置

建议增加内部配置寄存器：

```systemverilog
addr_t src_m_old_cfg_q;
addr_t src_l_old_cfg_q;
addr_t src_o_old_cfg_q;
addr_t src_m_tile_cfg_q;
addr_t src_l_tile_cfg_q;
addr_t src_o_tile_cfg_q;
addr_t dst_m_cfg_q;
addr_t dst_l_cfg_q;
addr_t dst_o_cfg_q;
logic [31:0] n_cfg_q;
logic [31:0] d_cfg_q;
logic [31:0] stride_cfg_q;
```

在 `IDLE` 接受 `start_i` 时一次性锁存，运行期间只使用 `_cfg_q`。

### 11.2 增加 error code

建议增加 `MERGE_ERROR_CODE`，例如：

```systemverilog
typedef enum logic [3:0] {
  MERGE_ERR_NONE,
  MERGE_ERR_N_ZERO,
  MERGE_ERR_D_ZERO,
  MERGE_ERR_ADDR_ALIGN,
  MERGE_ERR_STRIDE_ALIGN,
  MERGE_ERR_STRIDE_SMALL,
  MERGE_ERR_ADDR_RANGE,
  MERGE_ERR_INVALID_FP,
  MERGE_ERR_BOTH_ZERO_L,
  MERGE_ERR_FIXED_OVERFLOW,
  MERGE_ERR_START_WHILE_BUSY
} merge_error_e;
```

### 11.3 地址范围和 overflow 检查

建议检查：

\[
last\_addr=base+(N-1)\times stride+(D-1)\times4
\]

并验证最后一个 byte 仍在 TCDM 范围内。还应明确：

```text
stride == 0 || stride >= D * 4
```

对于明确允许 overlapping rows 的场景，可以增加配置位，而不是静默接受。

### 11.4 数值异常状态

建议增加 sticky status：

```text
invalid_fp
overflow
underflow
exp_saturated
recip_unsupported
```

## 12. 第二优先级：64-bit 双 FP32 lane

### 12.1 基本方案

对于连续且 8-byte 对齐的向量，一次读取两个 FP32：

```systemverilog
o_old_lane0_q <= tcdm_rsp_i.p.data[31:0];
o_old_lane1_q <= tcdm_rsp_i.p.data[63:32];
```

计算后完整写回：

```systemverilog
req_wdata_q <= {o_new_lane1, o_new_lane0};
req_strb_q  <= 8'hff;
```

理论上 vector transaction 数量可以从：

\[
3D
\]

降低为：

\[
3\lceil D/2\rceil
\]

### 12.2 边界情况

必须覆盖：

- `D` 为奇数；
- 起始地址只有 4-byte 对齐；
- 最后一个 lane 的 byte strobe；
- old/tile/destination 地址 lane alignment 不一致。

建议实现：

```text
8-byte aligned: dual-lane fast path
4-byte aligned: single-lane fallback
```

## 13. 第三优先级：地址递增器

建议在进入每行时计算一次行基址：

```text
old_row_base
tile_row_base
dst_row_base
```

处理每个单 lane 时地址加 4，处理每个双 lane 时地址加 8。每完成一行后，三个行
基址分别加 stride。

这样可以用加法器替代 vector loop 中反复出现的：

```text
row * stride + elem * 4
```

## 14. 第四优先级：算术流水化

建议至少拆为以下流水级。

### Stage A：max 和 delta

```text
m_new
delta_old = m_old - m_new
delta_tile = m_tile - m_new
```

### Stage B：exponential

```text
exp_old
exp_tile
```

### Stage C：length merge

```text
scaled_l_old
scaled_l_tile
l_new
```

### Stage D：reciprocal 和 weight

```text
1 / l_new
old_weight
tile_weight
```

### Stage E：输出向量乘法

```text
O_old * old_weight
O_tile * tile_weight
```

### Stage F：输出累加和转换

```text
fixed-point add
fixed-to-FP32
pack/store
```

具体流水级数量应由综合 critical path 决定，而不是只根据 RTL 代码结构决定。

## 15. 第五优先级：multiple outstanding TCDM

### 15.1 Metadata FIFO

请求被接受时，将 tag、元素索引和 lane 信息写入 metadata FIFO。response 返回时，
从 FIFO 取出对应信息。

如果 TCDM 保证 response 按请求顺序返回，则无需复杂 reorder buffer。

### 15.2 Load/compute/store 重叠

目标调度示例：

| Cycle | TCDM request | Compute | Store |
|---:|---|---|---|
| 0 | old pair 0 | - | - |
| 1 | tile pair 0 | - | - |
| 2 | old pair 1 | pair 0 | - |
| 3 | tile pair 1 | - | pair 0 |
| 4 | old pair 2 | pair 1 | - |
| 5 | tile pair 2 | - | pair 1 |

实际吞吐量受 TCDM backpressure、bank conflict、memory latency 和 arithmetic
pipeline latency 限制。

## 16. 数值实现改进

### 16.1 Q-format 命名

将：

```text
uq16_16_t/sq16_16_t
```

改为与 32 fractional bits 一致的名称，例如：

```text
uq16_32_t/sq16_32_t
```

### 16.2 舍入

当前大量右移操作采用截断。后续可以比较：

- truncation；
- round-half-up；
- round-to-nearest-even。

任何舍入规则修改都必须同步更新：

```text
RTL helper package
RTL-aligned C reference
host numeric model
golden data
```

### 16.3 定点饱和和 overflow

建议转换和乘法返回 value 与 status，例如：

```systemverilog
typedef struct packed {
  sq16_32_t value;
  logic     overflow;
  logic     underflow;
  logic     invalid;
} fixed_conv_t;
```

### 16.4 Reciprocal 设计空间

当前方案：

```text
256-entry LUT + interpolation + zero Newton iteration
```

可比较：

```text
64/128-entry LUT + interpolation + one Newton iteration
```

最终应基于误差、面积、DSP/multiplier 数量、延迟和 Fmax 决定。

### 16.5 Exponential 资源共享

当前并行例化两个 exp 单元。后续应比较：

- 双 exp：低 scalar latency、面积较大；
- 单 exp 时分复用：面积较小、scalar latency 增加；
- 双 lane vector 启用后，scalar latency是否仍是关键瓶颈。

## 17. 控制语义建议

### 17.1 Sticky completion

建议定义：

```text
busy: 任务正在运行
done: 成功完成，直到 clear
error: 失败完成，直到 clear
```

并保证：

```text
done && error 永不成立
```

### 17.2 Start while busy

当前软件不容易区分 busy 期间的 start 是被忽略还是接受。建议：

- 直接报告 `MERGE_ERR_START_WHILE_BUSY`；或
- 增加单项 command pending；或
- 后续增加 command queue。

### 17.3 配置写保护

可选方案：

- busy 时 peripheral 拒绝配置写入；
- 允许写入下一任务 shadow registers；
- engine 始终只使用 start 时的配置快照。

至少应实现第三项。

## 18. 建议增加的性能计数器

Cluster 总体 TCDM counter 不能完整解释 SMU 内部瓶颈。建议增加：

```text
MERGE_PERF_CYCLES
MERGE_PERF_SCALAR_CYCLES
MERGE_PERF_VECTOR_CYCLES
MERGE_PERF_READ_REQ
MERGE_PERF_WRITE_REQ
MERGE_PERF_STALL_CYCLES
MERGE_PERF_ELEMENTS
MERGE_PERF_EXP_SATURATION
```

由此可以计算：

\[
cycles\ per\ element =
\frac{vector\ cycles}{N\times D}
\]

\[
stall\ ratio =
\frac{TCDM\ stall\ cycles}{total\ cycles}
\]

这些指标比单独报告 CPU/engine speedup 更能反映 RTL 优化效果。

## 19. 验证计划

### 19.1 数学模块测试

建议新增：

```text
online_merge_scalar_pipe_tb.sv
online_merge_vector_pipe_tb.sv
```

Scalar coverage：

- `m_old > m_tile`；
- `m_old < m_tile`；
- `m_old == m_tile`；
- `l_old == 0`；
- `l_tile == 0`；
- both-zero；
- delta 接近 0；
- delta 接近 -8；
- delta 小于 -8；
- length 范围边界；
- fixed-point overflow。

Vector coverage：

- 正/负输入组合；
- weight 接近 0 或 1；
- `weight_old + weight_tile` 误差；
- 单 lane/双 lane；
- odd `D` tail；
- 定点最大/最小范围。

### 19.2 TCDM 协议测试

随机化：

```text
q_ready
p_valid latency
bank conflict pattern
```

验证：

- backpressure 下请求不会丢失或重复；
- response tag 正确；
- write 不会重复提交；
- DONE/ERROR 时不存在未处理 transaction；
- reset/clear 行为明确。

### 19.3 Assertions

建议加入：

```systemverilog
assert property (!(done_o && error_o));
assert property (state_q == DONE  |-> !req_valid_q && !read_pending_q);
assert property (state_q == ERROR |-> !req_valid_q);
assert property (busy_o |-> row_q < n_cfg_q);
assert property (busy_o |-> elem_q <= d_cfg_q);
```

multiple outstanding 版本还应检查 FIFO overflow/underflow 和 request/response 数量
守恒。

### 19.4 回归命令

模块级近似测试：

```bash
verilator --binary --timing \
  hw/ip/online_merge/src/online_merge_fp32_helpers.sv \
  hw/ip/online_merge/src/online_merge_exp_approx.sv \
  hw/ip/online_merge/src/online_merge_recip_approx.sv \
  hw/ip/online_merge/test/online_merge_approx_tb.sv \
  --top-module online_merge_approx_tb
./obj_dir/Vonline_merge_approx_tb
```

系统构建和软件测试：

```bash
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
make -C hw/system/spatz_cluster sw.vlt
make -C hw/system/spatz_cluster sw.test.vlt
```

## 20. 综合评估计划

下一阶段必须补充：

- 总面积；
- LUT/ROM/SRAM inference；
- multiplier/DSP 数量；
- critical path；
- Fmax；
- clock gating 后动态功耗；
- SMU 对 cluster 面积和功耗的增量；
- 单 exp/双 exp；
- 单 lane/双 lane；
- 不同 LUT 大小；
- 不同 pipeline depth。

特别需要确认两个 257-entry exp LUT 和一个 257-entry reciprocal LUT 最终被实现为：

- ROM/SRAM；还是
- 大型组合 mux network。

Verilator 功能仿真不能替代以上评估。

## 21. 推荐实施顺序

### Phase R0：状态和基线冻结

- 保存当前 cycles、TCDM counter 和 numeric error；
- 固定 golden cases；
- 记录当前 RTL 面积/Fmax 基线，如果综合环境可用。

### Phase R1：健壮性

- 配置快照；
- error code；
- 地址范围检查；
- fixed-point overflow 状态；
- assertions。

### Phase R2：流式地址生成

- 行基址寄存器；
- 单 lane 地址递增；
- 移除 vector loop 中重复变量乘法。

### Phase R3：64-bit 双 lane

- packed load/store；
- dual-lane vector datapath；
- odd tail；
- alignment fallback；
- cycles/element 对比。

### Phase R4：算术流水化

- scalar valid/ready pipeline；
- vector multiply-add pipeline；
- 根据综合 timing 调整 pipeline depth。

### Phase R5：Multiple outstanding

- metadata FIFO；
- 2 至 4 outstanding reads；
- load/compute/store overlap；
- randomized TCDM backpressure 验证。

### Phase R6：Attention 数据流融合

- tile state stream；
- ping-pong state；
- command queue；
- 避免 tile state 写回后再次读取；
- 与 QK/PV producer 的 valid/ready 接口。

## 22. 论文和答辩表述边界

推荐表述：

> 本设计实现了一个通过 MMIO 控制、作为独立 TCDM master 接入 Spatz cluster 的
> online softmax merge-update engine。该引擎在不修改 Spatz ISA 和主向量流水线的
> 前提下，在 RTL 中实现 max-rescaling、LUT-based exponential、LUT-based
> reciprocal、fixed-point normalization 和逐元素输出状态更新，并通过
> RTL-aligned reference、standalone approximation test 和系统级 Verilator
> benchmark 验证功能闭环。

当前不宜表述：

- 已实现最高性能 softmax 硬件；
- 已证明端到端 LLM attention speedup；
- 37.89x 是相对最优 CPU/vector baseline；
- 当前设计已经完成面积、功耗和频率优化；
- attention-like merge chain 等同于完整 attention kernel。

## 23. 最终判断

针对当前 softmax merge 加速器，可以明确确认：

1. RTL 已经有核心功能改造，而不是只修改软件；
2. 已经实现完整 mixed-scalar merge 数据通路；
3. 已经增加 exp/reciprocal 专用近似硬件；
4. 已经接入真实 MMIO 和 TCDM 系统路径；
5. 当前版本属于功能闭环 RTL 原型；
6. 最后一次核心 datapath RTL 修改发生在 2026-06-06；
7. 截至 2026-07-13，当前工作区没有新的 RTL 修改；
8. 下一阶段最有价值的工作是配置锁存、双 FP32 lane、流式地址生成、算术流水化、
   multiple outstanding TCDM 和综合评估。

因此，当前项目状态应概括为：

> **完整功能 RTL 原型和系统集成已经完成；面向综合频率、面积和最大吞吐量的第二轮
> 微架构优化尚待实施。**
