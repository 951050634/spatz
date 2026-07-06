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
