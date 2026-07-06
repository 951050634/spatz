# CFMA v2 专用数据通路规划

**日期**：2026-07-07
**基线**：CFMA v1 四阶段 FPU 复用实现
**分支**：`feature/cfma-v2-datapath`

## 1. v2 目标

v2 的目标是把 `vfcmacc.vv` 从“软件可见的一条复数指令、硬件内部四阶段复用 FPU”的 v1 实现，推进为真正的 dedicated complex-FMA datapath。

v2 需要证明：

- dedicated datapath 的复数算术正确；
- e16/e32/e64、mask/tail、fflags、rounding 行为有明确 reference；
- Spatz VFU 中的 request/response、backpressure、writeback 和 completion timing 安全；
- dedicated path 可以通过 ISA regression；
- 性能结论来自完整 benchmark，而不是设计假设。

## 2. v1 基线

v1 的架构语义继续作为 v2 correctness baseline：

```text
vd.real += vs1.real * vs2.real - vs1.imag * vs2.imag
vd.imag += vs1.real * vs2.imag + vs1.imag * vs2.real
```

v1 已冻结的设计边界：

- `vfcmacc.vv` encoding 和 decode 行为保持不变；
- paired register group 布局保持不变：
  - `vs1.real = vs1`，`vs1.imag = vs1 + LMUL`；
  - `vs2.real = vs2`，`vs2.imag = vs2 + LMUL`；
  - `vd.real = vd`，`vd.imag = vd + LMUL`；
- `LMUL=m1/m2/m4` 在 alignment/range 合法时可用，`m8` illegal；
- mask/tail 语义保持；
- fflags 语义必须重新明确：v2 若不与 v1 bit-identical，必须写入文档并由测试接受；
- `vstart != 0` 默认沿用 v1 illegal 策略，除非 v2 明确设计 resumable partial progress。

## 3. 第一阶段不做什么

v2 第一阶段应聚焦 dedicated datapath correctness，不应同时扩大 ISA 或工具链范围。

暂不做：

- `vfcmacc.vf`；
- conjugate、negated、rotation、butterfly 等复数变体；
- LLVM 自动向量化或完整 register allocator 支持；
- 面积/功耗优化；
- 改变公开 `vfcmacc.vv` encoding；
- 在没有独立 reference/testbench 前默认启用现有 guarded writeback prototype。

## 4. 专用数据通路架构目标

目标计算：

```text
real_out = c.real + a.real * b.real - a.imag * b.imag
imag_out = c.imag + a.real * b.imag + a.imag * b.real
```

其中：

```text
a = vs1
b = vs2
c = vd accumulator
```

每个 vector word 需要读取 6 组操作数：

```text
a.real, a.imag, b.real, b.imag, c.real, c.imag
```

需要写回 2 组结果：

```text
result.real -> vd
result.imag -> vd + LMUL
```

推荐初始微架构：

1. 使用现有三读端口 VRF，分两拍读取 6 个操作数；
2. 把六个操作数锁存为 dedicated CFMA request bundle；
3. 输入独立验证过的 `fpnew_complex_fma` 或等价模块；
4. 捕获 `{real, imag, status, tag}` 结果；
5. 使用两拍 writeback 写回 real 和 imag；
6. 在 dedicated path 完成验证前，保留 v1 四阶段 fallback。

## 5. 实施阶段

### 阶段 0：恢复干净基线

目标：确认 v2 从 v1 归档状态出发，而不是从脏工作区或未验证 prototype 出发。

任务：

- 确认 `docs/v1/IMPLEMENTATION_SUMMARY.md` 记录 v1 closure；
- 确认当前 dedicated writeback guard 默认禁用；
- 运行 baseline verification；
- 记录任何 pre-existing failure。

退出标准：

- Git 工作区干净；
- v1 baseline regression 可复现，或失败原因已记录。

### 阶段 1：建立 `fpnew_complex_fma` 独立参考模型和测试台

目标：先证明 complex arithmetic block 自身正确，再接入 Spatz VFU。

必须覆盖：

- e16/e32/e64 format selection；
- 普通有限数；
- signed zero；
- NaN/Inf；
- rounding modes；
- fflags；
- 随机 operand tuple；
- 与软件/reference model 对比。

退出标准：

- testbench 能输出 operand、format、rounding、expected、actual、flags；
- failure 可定位；
- 该阶段不要求修改 Spatz 默认 datapath。

### 阶段 2：冻结 Spatz VFU 请求/响应契约

目标：明确一条 `vfcmacc.vv` 如何转化为 dedicated CFMA request，以及 result 如何回到 VFU。

必须冻结：

- request valid/ready 时序；
- dedicated unit 是 blocking、multi-cycle 还是 pipelined；
- backpressure 如何作用于 VFU issue；
- tag 如何携带 `vd`、`vd+LMUL`、`vsew`、`vl`、mask/tail、element index；
- status/fflags 如何等到 architectural completion 时暴露；
- flush/kill/debug 场景是否允许 partial progress。

退出标准：

- 文档中有 request/result/writeback timing table；
- v1 fallback 仍可选择。

### 阶段 3：实现六操作数 VRF 分拍读取

目标：不增加 VRF 读端口，使用两拍读取六个操作数。

建议读取顺序：

```text
Cycle R0: a.real, a.imag, b.real
Cycle R1: b.imag, c.real, c.imag
```

必须保证：

- LMUL offset 与 v1 paired layout 一致；
- mask 数据在 byte enable 计算前已捕获；
- illegal layout 在执行前被拒绝；
- 不暴露 partial architectural state。

退出标准：

- RTL build 通过；
- directed trace/test 能证明六个操作数来自正确 register group。

### 阶段 4：接入专用计算路径，但不默认写回

目标：把 dedicated compute block 接入 RTL，同时避免未验证结果覆盖 v1 正确路径。

必须保证：

- dynamic FP format 选择正确；
- status flags 随 result 返回；
- result tag 足够支持 real/imag writeback；
- v1 fallback regression 仍通过。

退出标准：

- dedicated compute block 实例化后 RTL build 通过；
- standalone CFMA block test 通过；
- v1 fallback regression 通过。

### 阶段 5：实现并验证实部/虚部分拍写回

目标：在受控参数下启用 dedicated writeback，证明两拍写回正确。

必须保证：

- `result.real` 写入 `vd`；
- `result.imag` 写入 `vd + LMUL`；
- e16/e32/e64 byte enable 正确；
- mask/tail 对 real 和 imag 都正确；
- 与普通 FPU writeback 仲裁安全；
- 两个 write beat 完成前不发出 architectural completion。

退出标准：

- dedicated-mode `vfcmacc` ISA regression 通过；
- `vfmacc`/`vfnmsac` 邻近回归通过；
- masked-off lane 和 tail lane 覆盖 real/imag destination group。

### 阶段 6：切换默认路径

目标：只有 correctness closure 后，才把 dedicated datapath 设为默认 `vfcmacc.vv` 实现。

必须保证：

- 默认 build 使用 dedicated path；
- fallback path 可保留用于 debug；
- 若 v2 与 v1 不 bit-identical，必须明确 rounding/fflags 差异。

退出标准：

- 默认模式 `vfcmacc` ISA regression 通过；
- v1 fallback 对比样例存在；
- 差异行为被文档和测试接受。

### 阶段 7：性能测试和性能闭环

目标：在 correctness 之后，再比较三种方案：

1. 不使用复数指令；
2. v1 四阶段 `vfcmacc.vv`；
3. v2 dedicated datapath `vfcmacc.vv`。

必须记录：

- `dp-cdotp` small-size correctness；
- cycle count；
- instruction-count proxy；
- frontend/offload stall counter，如可用；
- timeout 或 slowdown 原因。

退出标准：

- 表格记录三种方案；
- speedup 只基于完成的 benchmark run 声明。

## 6. 预期效率目标

以下是 v2 目标，不是当前结果：

| 方案 | 角色 | 预期效率 |
| --- | --- | ---: |
| 不使用复数指令 | baseline | 1.0x |
| v1 四阶段 `vfcmacc.vv` | 降低指令数和前端压力 | cycle 约 1.0-1.2x；软件指令数降低 4x |
| v2 dedicated datapath | 真正降低计算串行度 | 保守 2x+；理想 3-4x |

## 7. 最小验证矩阵

任何 v2 completion claim 前至少运行：

```bash
git diff --check
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt
cd hw/system/spatz_cluster/sw/build
PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" \
  ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure
```

Dedicated-mode 完成还必须增加：

- `fpnew_complex_fma` standalone/reference test；
- dedicated-mode `vfcmacc` regression；
- benchmark correctness；
- benchmark speedup 数据。

## 8. 第一个具体任务

v2 的第一个实现任务应是：

```text
为 fpnew_complex_fma 建立独立 reference/testbench，冻结 arithmetic、rounding 和 fflags 行为。
```

不要把第一步设为“直接打开 `CfmaDedicatedWritebackEn`”。现有 guarded writeback prototype 只能作为参考，不能作为默认启用基础。
