# CFMA v2 阶段 5：dedicated real/imag 两拍 writeback

**日期**：2026-07-07  
**分支**：`feature/cfma-v2-datapath`  
**前置阶段**：阶段 4 已证明 read bundle 可直接驱动 dedicated compute。

## 1. 阶段目标

阶段 5 目标是在显式 enable-mode 下验证 dedicated CFMA result 可以通过单 VRF write port 分两拍写回：

```text
W0: result.real -> vd
W1: result.imag -> vd + LMUL
```

本阶段仍保持默认关闭：

- `CfmaDedicatedReadCollectorEn = 1'b0`；
- `CfmaDedicatedWritebackEn = 1'b0`；
- 默认系统 build/regression 仍走 v1 fallback。

## 2. Directed test

新增：

```text
hw/ip/spatz/test/spatz_vfu_cfma_writeback_tb.sv
```

配置：

```systemverilog
spatz_vfu #(
  .CfmaDedicatedReadCollectorEn(1'b1),
  .CfmaDedicatedWritebackEn(1'b1)
)
```

输入仍使用阶段 4 的 FP64 case：

```text
a = 1 + 2i
b = 3 + 4i
c = 5 + 6i
expected = 0 + 16i
```

验证点：

- read collector bundle 地址/数据正确；
- compute result 正确；
- `vrf_wvalid_i=0` 时 real write beat 保持稳定；
- 释放 backpressure 后 real beat 被接受，下一拍写 imag；
- imag beat 后 dedicated pending 清空；
- 写回地址分别为 `vd` 与 `vd+LMUL`；
- low 8 byte enable bits set（当前 directed SEW=64, VL=1, mask enabled）。

GREEN trace：

```text
CFMA_READ_BUNDLE elem=0 last=0 ... vd.real.addr=0x1a vd.imag.addr=0x1c
CFMA_COMPUTE_RESULT real=0x0 imag=0x4030000000000000 fflags=0x0
SPATZ_VFU_CFMA_WRITEBACK_TB_PASS real.addr=0x1a imag.addr=0x1c
```

## 3. 红灯与修复

### 3.1 写回地址未冻结

红灯：

```text
real hold under backpressure: expected addr 0x1a got 0x19
```

原因：旧 writeback FSM 通过 `cfma_tag_out.vd_addr - LMUL` 推导 real address，假设 tag 中保存 imag address。但 enable-mode 的 tag 尚未与 read bundle 对齐。

修复：在 `CfmaDedicatedReadCollectorEn=1` 时直接使用 collector 冻结地址：

```systemverilog
cfma_wb_real_addr_d = cfma_read_vd_real_addr;
cfma_wb_imag_addr_d = cfma_read_vd_imag_addr;
```

### 3.2 byte enable 为 0

红灯：

```text
real hold under backpressure: expected low 8 byte-enable bits set got 0x0
```

原因：`cfma_active_wbe()` 使用的 result tag 仍来自动态 `input_tag`，`elem_idx/vd_addr/last` 未按 read bundle 冻结。

修复：新增 `cfma_tag_bundle`，enable-mode 下覆盖：

```systemverilog
vd_addr        = cfma_read_vd_imag_addr;
elem_idx       = cfma_read_elem_idx;
last           = cfma_read_last;
cfma_step_last = cfma_read_last;
```

### 3.3 regular v1 FPU path 重复写回

红灯：

```text
dedicated writeback did not drain after imag beat
```

原因：即使 dedicated writeback enable，regular fpnew lane 仍会对同一 `VFCMADD` 发射 v1 四阶段 FPU ops，导致 dedicated imag beat 后又出现 fallback 写回。

修复：在 dedicated writeback mode 下禁止 regular fpnew lane 对 `cfma_insn` 发射：

```systemverilog
!(CfmaDedicatedReadCollectorEn && CfmaDedicatedWritebackEn && cfma_insn)
```

该 gating 只影响显式 dedicated writeback enable-mode；默认关闭路径不变。

## 4. 验证结果

完整证据：

```text
docs/v2/evidence/stage5_vfu_writeback_verification.txt
```

验证覆盖：

```text
git diff --check
VFU writeback directed build/run
VFU compute-bundle directed build/run
VFU read-mux directed build/run
system Verilator build default-off
ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$'
```

结果：

```text
git diff --check: PASS
VFU writeback directed build/run: PASS
VFU compute-bundle directed build/run: PASS
VFU read-mux directed build/run: PASS
system Verilator build default-off: PASS
v1 fallback regression: PASS, 3/3
```

## 5. 剩余 gap

阶段 5 只证明了单元素 FP64 directed writeback microflow。完整 dedicated architectural path 仍需后续阶段完成：

- fflags architectural completion/OR-reduction；
- mask/tail 多元素 byte enable matrix；
- e16/e32 packed lanes；
- full ISA regression with dedicated mode enabled；
- performance benchmark；
- 默认路径切换策略。
