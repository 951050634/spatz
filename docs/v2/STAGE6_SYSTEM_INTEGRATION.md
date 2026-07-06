# CFMA v2 阶段 6：系统层参数透传与 dedicated-mode 集成准备

**日期**：2026-07-07  
**分支**：`feature/cfma-v2-datapath`

## 1. 小阶段目标

阶段 5 已在 VFU 级 directed test 中证明 dedicated read/compute/writeback microflow。阶段 6 的第一步是让系统层具备显式构建 dedicated CFMA mode 的参数路径，同时默认继续关闭。

本小阶段只做参数透传，不切换默认路径。

## 2. RTL 修改

新增默认关闭参数透传链：

```text
spatz_cluster_wrapper
  -> spatz_cluster
    -> spatz_cc
      -> spatz
        -> spatz_vfu
```

涉及文件：

```text
hw/ip/spatz_cc/src/spatz_cc.sv
hw/system/spatz_cluster/src/spatz_cluster.sv
hw/system/spatz_cluster/src/generated/spatz_cluster_wrapper.sv
hw/system/spatz_cluster/src/spatz_cluster_wrapper.sv.tpl
```

新增参数：

```systemverilog
CfmaDedicatedReadCollectorEn
CfmaDedicatedWritebackEn
```

`spatz_cluster` 层使用 per-core bit vector，`spatz_cc/spatz/spatz_vfu` 使用 scalar bit。generated wrapper 和 template 中默认 localparam 都为 `'0`。

## 3. 验证

完整证据：

```text
docs/v2/evidence/stage6_system_param_passthrough_verification.txt
```

结果：

```text
git diff --check: PASS
pass-through grep check: PASS
system Verilator build default-off: PASS
ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$': PASS, 3/3
```

## 4. 剩余 gap

本小阶段只证明默认关闭的参数路径不会破坏系统 build/regression。后续仍需：

- 构建 dedicated-mode system/ISA regression 开关；
- dedicated-mode `vfcmacc` ISA test；
- fflags/mask/tail/e16/e32 closure；
- 决定是否、何时切换默认 architectural path。

## 5. 小阶段：`CFMA_DEDICATED_V2` dedicated-mode build switch

在系统参数透传之后，本小阶段新增一个显式编译期开关：

```systemverilog
`ifdef CFMA_DEDICATED_V2
  localparam bit [NumCores-1:0] CfmaDedicatedReadCollectorEn = '1;
  localparam bit [NumCores-1:0] CfmaDedicatedWritebackEn = '1;
`else
  localparam bit [NumCores-1:0] CfmaDedicatedReadCollectorEn = '0;
  localparam bit [NumCores-1:0] CfmaDedicatedWritebackEn = '0;
`endif
```

涉及：

```text
hw/system/spatz_cluster/src/generated/spatz_cluster_wrapper.sv
hw/system/spatz_cluster/src/spatz_cluster_wrapper.sv.tpl
```

该开关不改变默认 build；只有在 Verilator/Bender `DEFS=-DCFMA_DEDICATED_V2` 时，cluster 内每个 Spatz core 才启用 dedicated read collector 和 dedicated split writeback。

### Trace gating

首次 full `vfcmacc` dedicated-mode CTest 尝试长时间无结果。系统化排查后确认：smoke 可快速通过，但 full test 会执行大量 CFMA，默认 `$display` 每个 bundle/result 会严重拖慢仿真。因此本小阶段把以下 trace 改为显式 `CFMA_DEDICATED_V2_TRACE` 才启用：

```text
CFMA_READ_BUNDLE
CFMA_COMPUTE_RESULT
```

默认 dedicated-mode regression 不再打印 per-CFMA trace；需要调试时可额外传入：

```text
-DEFS="-DCFMA_DEDICATED_V2 -DCFMA_DEDICATED_V2_TRACE"
```

### 验证结果

完整证据：

```text
docs/v2/evidence/stage6_dedicated_mode_switch_attempt.txt
```

覆盖：

```text
git diff --check: PASS
CFMA_DEDICATED_V2 switch grep: PASS
dedicated-mode system Verilator build: PASS
vfcmacc_smoke direct run: PASS
full vfcmacc direct run: PASS
default-off system Verilator rebuild: PASS
default-off v1 fallback regression: PASS, 3/3
```

full dedicated-mode `vfcmacc` direct run 输出：

```text
[SUCCESS] Program finished successfully
```

### 剩余 gap

该小阶段首次证明 dedicated-mode system build 可以跑通 full `vfcmacc` ISA test。但完整 v2 closure 仍需要：

- dedicated-mode `vfcmacc_illegal`/mask-tail/fflags 细分验证；
- dedicated-mode `vfmacc/vfnmsac` 非 CFMA regression 旁路确认；
- benchmark/performance；
- 默认切换前的文档化决策。
