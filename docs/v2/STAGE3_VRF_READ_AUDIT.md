# CFMA v2 阶段 3 准备：六操作数 VRF 分拍读取现状审查

**日期**：2026-07-07  
**分支**：`feature/cfma-v2-datapath`  
**前置契约**：`docs/v2/STAGE2_VFU_CONTRACT.md`

## 1. 阶段 3 目标回顾

阶段 3 的目标是不增加 VRF 读端口，用现有 3 个读端口分两拍读取 dedicated CFMA 所需的 6 个 operand：

```text
R0: a.real, a.imag, b.real
R1: b.imag, c.real, c.imag
```

其中：

```text
a = vs1
b = vs2
c = vd accumulator
```

阶段 2 已冻结：request 只能在六 operand、mask snapshot、tag metadata 全部稳定后发出；request/result/writeback 不得依赖之后可能变化的 `spatz_req` 全局字段。

## 2. 当前 RTL 现状

当前 `hw/ip/spatz/src/spatz_vfu.sv` 已有 v1 四阶段 FPU fallback 和一个 dedicated prototype latch：

| 代码位置 | 现状 |
| --- | --- |
| `cfma_phase_e` (`Cfma_RR/II/RI/IR`) | v1 内部四阶段 FPU 复用状态 |
| `vreg_addr_proc` lines around 861 | 根据 `cfma_phase_q` 给 `vs2/vs1/vd` 加 LMUL offset |
| `operand_req_proc` | 仍按普通 VFU request 方式请求最多三个 read ports |
| `fpnew_complex_fma` instantiation | 已实例化，但 `CfmaDedicatedWritebackEn=1'b0` |
| operand latch around lines 1455-1509 | 从 v1 phase 中顺带收集 `a/b/c` operand |
| `cfma_op_valid` | 在 `Cfma_IR && word_issued` 时发出 dedicated op |

当前 prototype 的 phase mapping 为：

| v1 phase | 当前 latch 内容 |
| --- | --- |
| `Cfma_RR` | `operand2=a.real`, `operand1=b.real`, `operand3=c.real` |
| `Cfma_II` | `operand2=a.imag`, `operand1=b.imag` |
| `Cfma_RI` | `operand3=c.imag` |
| `Cfma_IR` | 不再 latch，认为六 operand 已齐 |

## 3. 与阶段 2 契约的差距

当前 prototype 能作为调试参考，但不能作为阶段 3 dedicated request 契约实现，原因如下：

1. **读取节奏不对**：当前依赖 v1 四个 FPU phase 收集 operand，而阶段 3 要求 dedicated path 在 R0/R1 两拍完成 6 operand 读取。
2. **operand 命名有历史混淆**：注释中 `operand2=vs2=a, operand1=vs1=b`，但 v2 契约冻结 `a=vs1, b=vs2`。后续 RTL 必须统一命名，避免 real/imag 乘法交换以外的 tag/layout 错误。
3. **tag 不完整**：当前 `cfma_tag_in = input_tag`，而 `input_tag` 不包含 frozen `vl/vm/mask_bits/lmul_words/vd_real_addr/vd_imag_addr` 全部语义。
4. **mask snapshot 未进入 tag**：当前 `cfma_active_wbe` 在 writeback 阶段仍使用 `spatz_req.vl/spatz_req.op_arith.vm/cfma_mask_q`。
5. **result/writeback 原子性未证明**：prototype writeback FSM 存在但默认禁用，且未证明 `W0/W1` no partial architectural completion。
6. **dynamic format 未实现**：dedicated block 当前在 VFU 中实例化为 `FpFormat=FP64`，不能作为 e16/e32 packed lane dedicated path。

## 4. 阶段 3 最小 RTL 切片建议

阶段 3 不应直接打开 dedicated writeback。推荐先实现一个 **dedicated read collector**，只完成 request bundle 形成和 debug/trace 可验证性：

```systemverilog
typedef enum logic [1:0] {
  CfmaReadIdle,
  CfmaReadR0,
  CfmaReadR1,
  CfmaReadReady
} cfma_read_state_e;
```

最小切片职责：

1. 在 `vfcmacc.vv` issue 且 dedicated collector enabled 时进入 `CfmaReadR0`；
2. `R0` 使用三个 VRF ports 读取：
   - port 0: `vs1.real` (`a.real`)
   - port 1: `vs1.imag` (`a.imag`)
   - port 2: `vs2.real` (`b.real`)
3. `R1` 使用三个 VRF ports 读取：
   - port 0: `vs2.imag` (`b.imag`)
   - port 1: `vd.real` (`c.real`)
   - port 2: `vd.imag` (`c.imag`)
4. 在 `R1` valid 后锁存：
   - six operands；
   - `rnd_mode`；
   - `vd_real_addr` / `vd_imag_addr`；
   - `vsew/vlmul/vl/vm/mask_bits/elem_idx/is_last`；
5. 输出 `cfma_read_bundle_valid` 供阶段 4 dedicated compute path 使用；
6. 默认仍走 v1 fallback，不改变 architectural writeback。

## 5. 建议验证方法

阶段 3 退出标准需要 directed trace/test 证明六个 operand 来自正确 register group。推荐两层验证：

### 5.1 RTL build gate

```bash
git diff --check
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
```

### 5.2 Directed operand collector trace

新增受控 debug 开关，例如：

```systemverilog
localparam bit CfmaDedicatedReadCollectorTraceEn = 1'b0;
```

在 non-synthesis / verilator guard 下，当 collector bundle formed 时打印：

```text
CFMA_READ_BUNDLE elem=<idx> vsew=<...> lmul=<...>
  a.real addr=<vs1> data=<...>
  a.imag addr=<vs1+lmul> data=<...>
  b.real addr=<vs2> data=<...>
  b.imag addr=<vs2+lmul> data=<...>
  c.real addr=<vd> data=<...>
  c.imag addr=<vd+lmul> data=<...>
```

然后新增一个小型 ISA/RTL test 或临时 debug run，初始化 `vs1/vs1+LMUL/vs2/vs2+LMUL/vd/vd+LMUL` 为不同 sentinel pattern，检查 trace 中六个 data/address 与预期一致。

## 6. 阶段 3 不做什么

为了保持阶段边界清晰，本阶段暂不做：

- 不启用 `CfmaDedicatedWritebackEn`；
- 不让 dedicated result 覆盖 v1 fallback writeback；
- 不宣称 dedicated-mode ISA regression 通过；
- 不改变公开 `vfcmacc.vv` encoding；
- 不支持 `vfcmacc.vf` 或额外复数变体。

## 7. 下一步实现检查清单

- [ ] 增加 dedicated read collector state/regs，但默认不影响 v1 fallback。
- [ ] 统一 `a=vs1, b=vs2, c=vd` 命名。
- [ ] 冻结 request/tag 字段，避免 result/writeback 依赖动态 `spatz_req`。
- [ ] 增加 directed trace 或 testbench 证明 R0/R1 六 operand 来源。
- [ ] `make bin/spatz_cluster.vlt` 通过。
- [ ] v1 fallback `vfcmacc|vfmacc|vfnmsac` regression 仍通过。

## 8. 已完成小阶段：standalone read collector RTL

本小阶段新增了 standalone RTL helper：

```text
hw/ip/spatz/src/spatz_cfma_read_collector.sv
hw/ip/spatz/test/spatz_cfma_read_collector_tb.sv
```

该 helper 已实现并验证阶段 3 冻结的 R0/R1 mapping：

| Beat | Port 0 | Port 1 | Port 2 |
| --- | --- | --- | --- |
| R0 | `a.real` | `a.imag` | `b.real` |
| R1 | `b.imag` | `c.real` | `c.imag` |

已验证行为：

- `start_valid/start_ready` 只在 idle 接受一次 request；
- R0 在三个 `vrf_rvalid_i` 全部有效前保持地址和 read enable；
- R1 在三个 `vrf_rvalid_i` 全部有效前保持地址和 read enable；
- bundle valid 后冻结六个 operand、`vd_real_addr`、`vd_imag_addr`、`elem_idx`、`last`；
- `bundle_ready_i=0` 时 bundle 保持稳定并 backpressure 新 start；
- bundle handshake 后回到 idle。

TDD 红灯：

```text
stage3_read_collector_red_build.txt: Cannot find file containing module: 'spatz_cfma_read_collector'
```

最终验证证据：

```text
docs/v2/evidence/stage3_read_collector_final_verification.txt
```

最终验证命令包括：

```bash
git diff --check
install/verilator/bin/verilator_bin --binary --timing -Wno-TIMESCALEMOD \
  hw/ip/spatz/src/spatz_cfma_read_collector.sv \
  hw/ip/spatz/test/spatz_cfma_read_collector_tb.sv \
  --top-module spatz_cfma_read_collector_tb
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
cd hw/system/spatz_cluster/sw/build && \
  PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" \
  ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure
```

结果：standalone collector test PASS；system Verilator build PASS；v1 fallback regression PASS，3/3。

注意：该 helper 已加入 `Bender.yml`，但尚未接入 `spatz_vfu.sv` 的 architectural datapath。下一小阶段应把 helper 接入 VFU dedicated path 的 gated/scaffold flow，并产生真实 `cfma_read_bundle_valid`，仍不启用 dedicated writeback。
