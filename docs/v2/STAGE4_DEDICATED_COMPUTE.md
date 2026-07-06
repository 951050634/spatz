# CFMA v2 阶段 4：接入 dedicated compute path（不默认写回）

**日期**：2026-07-07  
**分支**：`feature/cfma-v2-datapath`  
**前置阶段**：阶段 3 已完成 VFU enable-mode read collector directed trace closure。

## 1. 阶段目标

阶段 4 的目标是把阶段 3 形成的 frozen six-operand bundle 接入 `fpnew_complex_fma`，证明 dedicated compute path 可以直接消费：

```text
a.real, a.imag, b.real, b.imag, c.real, c.imag
```

并产生：

```text
result.real, result.imag, fflags
```

本阶段仍不默认写回 VRF：

- `CfmaDedicatedReadCollectorEn` 默认关闭；
- `CfmaDedicatedWritebackEn` 默认关闭；
- architectural path 仍是 v1 fallback；
- dedicated result 只通过 testbench/hierarchical check 和 trace 观察。

## 2. 发现的问题

进入本阶段前，`spatz_vfu.sv` 中 `fpnew_complex_fma` 已实例化，但输入仍来自旧 v1 四阶段 latch：

```text
cfma_a_real_q/cfma_a_imag_q/...
```

`cfma_op_valid` 也仍在 `Cfma_IR && word_issued` 时发起。这意味着即使阶段 3 read collector 已能形成正确 bundle，dedicated compute 仍会消费旧四阶段路径中混合出来的 operand。

TDD 红灯使用：

```text
hw/ip/spatz/test/spatz_vfu_cfma_compute_bundle_tb.sv
```

该 test 在 `CfmaDedicatedReadCollectorEn=1`、`CfmaDedicatedWritebackEn=0` 下驱动：

```text
a = 1 + 2i
b = 3 + 4i
c = 5 + 6i
expected = 0 + 16i
```

红灯结果：

```text
CFMA_READ_BUNDLE ... a.real=0x3ff0000000000000 ... c.imag=0x4018000000000000 ...
CFMA real result mismatch: expected 0x0 got 0xc028000000000000
```

这证明 read bundle 正确，但 compute 未消费该 bundle。

## 3. RTL 修改

在 `CfmaDedicatedReadCollectorEn=1` 时：

- `cfma_operand_*` 改由 `cfma_read_*[ELEN-1:0]` 驱动；
- `cfma_op_valid` 改由 `cfma_read_bundle_valid` 驱动；
- `cfma_read_bundle_ready` 改接 `cfma_op_ready`，避免 compute 无法接收时丢失 bundle。

默认关闭时保留旧行为：

```systemverilog
assign cfma_op_valid = CfmaDedicatedReadCollectorEn ?
                       cfma_read_bundle_valid :
                       (cfma_insn && (cfma_phase_q == Cfma_IR) && word_issued);
```

该修改只影响显式 enable-mode，系统默认 build/regression 仍验证 v1 fallback。

## 4. Directed GREEN

修复后，同一 test 通过：

```text
CFMA_READ_BUNDLE elem=0 last=0 a.real.addr=0xa a.real=0x3ff0000000000000 a.imag.addr=0xc a.imag=0x4000000000000000 b.real.addr=0x12 b.real=0x4008000000000000 b.imag.addr=0x14 b.imag=0x4010000000000000 c.real.addr=0x1a c.real=0x4014000000000000 c.imag.addr=0x1c c.imag=0x4018000000000000 vd.real.addr=0x1a vd.imag.addr=0x1c
SPATZ_VFU_CFMA_COMPUTE_BUNDLE_TB_PASS result.real=0x0 result.imag=0x4030000000000000
```

`0x4030000000000000` 是 FP64 `16.0`，匹配 `(1+2i)*(3+4i)+(5+6i) = 0+16i`。

## 5. 验证结果

完整验证证据：

```text
docs/v2/evidence/stage4_vfu_compute_bundle_verification.txt
```

验证命令覆盖：

```text
git diff --check
/home/wxt/spatz/install/bender/bender script verilator -t spatz -t rtl
VFU compute-bundle directed build/run
VFU read-mux directed build/run
standalone fpnew_complex_fma matrix build/run
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$'
```

结果：

```text
git diff --check: PASS
VFU compute-bundle directed build/run: PASS
VFU read-mux directed build/run: PASS
standalone fpnew_complex_fma matrix: PASS
system Verilator build default-off: PASS
v1 fallback regression: PASS, 3/3
```

## 6. 阶段 4 closure 和剩余 gap

已完成：

- dedicated read bundle 可直接驱动 `fpnew_complex_fma`；
- read bundle ready 与 compute ready 对齐；
- directed FP64 finite case 证明 VFU enable-mode dedicated compute 输出正确；
- standalone complex FMA matrix 继续通过；
- 默认关闭系统 build/regression 未回归。

未完成，留给后续阶段：

- dedicated result tag 仍未完全冻结 mask/vl/lmul/fflags completion 语义；
- dedicated writeback 仍未启用；
- 尚未证明 real/imag 两拍写回原子性；
- e16/e32 packed lane 的 VFU dedicated compute 仍未作为 architectural path 验证；
- default path 仍保持 v1 fallback。
