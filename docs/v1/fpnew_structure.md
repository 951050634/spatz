# FPnew 结构备忘

本文件用于记录 CFMA 工作中与 FPnew 相关的最小上下文。

## 1. v1 使用方式

v1 不修改 FPnew 为专用 complex-FMA datapath。`vfcmacc.vv` 在 Spatz VFU 中拆成四个普通 FPU phase，复用已有 FPnew FMA/FNMSUB 能力。

## 2. v2 可能需要的 FPnew 工作

若 v2 选择在 FPnew 内部实现 dedicated complex-FMA block，需要明确：

- 新 operation 是否进入 `fpnew_pkg`；
- 是否复用现有 FMA pipeline；
- 是否新增 `fpnew_complex_fma` 独立模块；
- e16/e32/e64 format 如何选择；
- rounding mode 和 fflags 如何定义；
- NaN/Inf/signed zero 行为是否与 v1 四操作序列 bit-identical；
- latency/throughput/backpressure contract。

## 3. v2 前置条件

在接入 Spatz VFU 前，必须先有独立 reference/testbench 证明 complex arithmetic、rounding 和 flags 行为。
