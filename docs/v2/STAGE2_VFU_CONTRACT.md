# CFMA v2 阶段 2：Spatz VFU Dedicated CFMA 契约冻结

**日期**：2026-07-07  
**分支**：`feature/cfma-v2-datapath`  
**前置证据**：阶段 0 baseline、阶段 1 standalone `fpnew_complex_fma` directed matrix

## 1. 目标

阶段 2 冻结 `vfcmacc.vv` 从 Spatz VFU 到 dedicated CFMA block 的 request/result/writeback 契约。该文档是阶段 3-5 RTL 修改的约束，避免在接入六操作数读取和两拍写回时引入 partial architectural state。

本阶段不启用 dedicated writeback，也不改变公开 ISA encoding。`CfmaDedicatedWritebackEn` 必须继续默认 `1'b0`，直到阶段 5 dedicated-mode regression 完成。

## 2. 软件可见语义

`vfcmacc.vv vd, vs1, vs2` 的 paired register group 布局沿用 v1：

```text
vs1.real = vs1
vs1.imag = vs1 + LMUL
vs2.real = vs2
vs2.imag = vs2 + LMUL
vd.real  = vd
vd.imag  = vd + LMUL
```

每个 active element 的计算为：

```text
real = vd.real + vs1.real * vs2.real - vs1.imag * vs2.imag
imag = vd.imag + vs1.imag * vs2.real + vs1.real * vs2.imag
```

初始 v2 arithmetic order 与阶段 1 standalone block 一致：

| Phase | Real path | Imag path |
| --- | --- | --- |
| 1 | `real_acc = FMADD(vs1.real, vs2.real, vd.real)` | `imag_acc = FMADD(vs1.imag, vs2.real, vd.imag)` |
| 2 | `real = FNMSUB(vs1.imag, vs2.imag, real_acc)` | `imag = FMADD(vs1.real, vs2.imag, imag_acc)` |

## 3. Dedicated CFMA request bundle

VFU 在完成两拍 VRF 读取后，必须向 dedicated block 发送一个完整 request。request 只有在六个 operand、mask snapshot、element metadata 全部稳定后才允许 valid。

```systemverilog
typedef struct packed {
  logic [ELEN-1:0] a_real;
  logic [ELEN-1:0] a_imag;
  logic [ELEN-1:0] b_real;
  logic [ELEN-1:0] b_imag;
  logic [ELEN-1:0] c_real;
  logic [ELEN-1:0] c_imag;
  fpnew_pkg::roundmode_e rnd_mode;
  cfma_vfu_tag_t tag;
} cfma_req_t;
```

`tag` 必须携带 writeback 和 architectural completion 所需的信息，不得依赖发出 request 后仍会变化的 VFU 全局状态。

## 4. Tag 字段

推荐冻结为以下逻辑字段；实际 RTL 可复用/扩展 `vfu_tag_t`，但语义必须等价。

| 字段 | 用途 | 说明 |
| --- | --- | --- |
| `vd_real_addr` | real writeback address | 指向 `vd` 当前 element/word |
| `vd_imag_addr` | imag writeback address | 指向 `vd + LMUL` 当前 element/word |
| `word_idx` / `elem_idx` | mask/tail 与 debug 定位 | 用于 byte enable 和 trace |
| `vsew` | element width | e16/e32/e64 byte enable 选择 |
| `vlmul` / `lmul_words` | paired layout | 计算 imag group offset，debug range check |
| `vl` | active vector length | tail byte enable 判断 |
| `vm` | mask enable bit | `vm=1` 表示 unmasked |
| `mask_bits` | mask snapshot | request 发出时已锁存，不再读动态 mask |
| `is_last_word` / `is_last_elem` | completion | 两个 write beats 完成后才能 architectural complete |
| `insn_id` 或 ROB tag | flush/kill/debug | 如 VFU/ROB 已有等价 tag，可复用 |

禁止 result/writeback 阶段重新读取 `spatz_req.vtype`、`spatz_req.vl`、`spatz_req.op_arith.vm` 来决定 architectural byte enable；这些字段必须在 request/tag 中冻结。

## 5. valid/ready 和 backpressure 契约

Dedicated CFMA unit 初始定义为 **blocking multi-cycle single-entry**：同一时刻只接受一个 request。未来可以 pipeline，但必须保持同样的 request/result ordering 或显式增加 reorder tag。

| Signal | Producer | Consumer | 契约 |
| --- | --- | --- | --- |
| `cfma_req_valid` | VFU | CFMA | 六 operand 和 tag 完整稳定后拉高 |
| `cfma_req_ready` | CFMA | VFU | CFMA idle 或可接收新 entry 时拉高 |
| `cfma_req_valid && cfma_req_ready` | both | both | request 被接受；VFU 可释放 operand latch |
| `cfma_rsp_valid` | CFMA | VFU | `{real, imag, status, tag}` 全部有效 |
| `cfma_rsp_ready` | VFU | CFMA | VFU 能捕获 result 或 writeback buffer 有空 |
| `cfma_rsp_valid && cfma_rsp_ready` | both | both | result ownership 交给 VFU |
| `cfma_busy` | CFMA | VFU/scoreboard | request accepted 到 result consumed 期间为 1 |

Backpressure 规则：

1. VFU 不能在 `cfma_req_ready=0` 时发出下一个 dedicated request。
2. 当 writeback buffer 或 VRF write port 无法保证接收 result 时，VFU 必须把 `cfma_rsp_ready=0`。
3. CFMA 在 `cfma_rsp_valid=1 && cfma_rsp_ready=0` 时必须保持 result/tag/status 稳定。
4. VFU issue 必须把 outstanding dedicated CFMA 视为占用 FPU/CFMA slot，直到 result 被 VFU 捕获。
5. 若 fallback v1 path 被选择，则 dedicated request signals 必须保持 idle，不得产生 side effect。

## 6. Timing tables

### 6.1 六操作数读取到 request

阶段 3 的 VRF 读取必须满足如下时序。`R0/R1` 可以是两个连续 cycle，也可以在 VRF backpressure 下插入 wait；但 request 只能在 `R1` 数据已锁存后发出。

| Cycle | VFU action | Captured fields | Architectural side effect |
| --- | --- | --- | --- |
| `I0` | decode/issue `vfcmacc.vv`，检查 layout/vstart | instruction metadata | none |
| `R0` | VRF read ports: `a.real`, `a.imag`, `b.real` | `a_real_q`, `a_imag_q`, `b_real_q` | none |
| `R1` | VRF read ports: `b.imag`, `c.real`, `c.imag`；mask snapshot | `b_imag_q`, `c_real_q`, `c_imag_q`, `mask_bits_q` | none |
| `Q` | drive `cfma_req_valid` | full `cfma_req_t` | none |
| `Q+` | if ready, request accepted | CFMA owns request | none |

### 6.2 Dedicated compute result

| Cycle | CFMA action | VFU action | Architectural side effect |
| --- | --- | --- | --- |
| `C0` | request accepted | marks dedicated op busy | none |
| `C1..Cn` | internal two-round FMA / pipeline | holds issue if single-entry busy | none |
| `Rn` | drives `cfma_rsp_valid` | if `cfma_rsp_ready=1`, captures result buffer | none |

### 6.3 两拍 writeback 与 completion

| Cycle | VFU action | VRF write | Completion |
| --- | --- | --- | --- |
| `W0` | write real beat | `result.real -> vd_real_addr` with frozen byte enable | no architectural completion |
| `W1` | write imag beat | `result.imag -> vd_imag_addr` with same active byte semantics | if this is last active element/word, instruction may complete |
| `DONE` | expose accumulated fflags | none | architectural completion after both beats visible |

若 `W0` 已完成但 `W1` 尚未完成，VFU 必须禁止 flush/kill 后暴露 partial architectural state；见第 8 节。

## 7. fflags/status 契约

- Dedicated block 对每个 request 返回一个 `fpnew_pkg::status_t`。
- VFU 必须 OR-reduce 所有 active elements 的 status。
- Masked-off lane 和 tail lane 不得产生 architectural fflags。
- fflags 只在整条 `vfcmacc.vv` architectural completion 时暴露。
- 若 v2 dedicated path 与 v1 fallback 在 NaN payload 或 rounding order 上不 bit-identical，必须在阶段 6 closure 文档中列出差异，并由 dedicated regression 接受。

## 8. flush/kill/debug 与 partial progress

初始 v2 明确定义为 **non-resumable, no partial architectural completion**：

1. `vstart != 0` 继续沿用 v1 illegal 策略。
2. request 被 accepted 但尚未写回时，flush/kill 必须丢弃 result，不能写 VRF。
3. `W0` real beat 已写但 `W1` imag beat 未写时，不允许普通精确异常/kill 观察到该状态。实现上必须二选一：
   - 在允许 flush/kill 的点之前等待 `W0/W1` 原子 drain 完成；或
   - 使用 shadow writeback buffer，只在 `W0/W1` 都可提交时写 VRF。
4. debug trace 可以记录 internal progress，但不得把 dedicated partial progress 作为 architectural state。

阶段 5 实现两拍 writeback 时必须显式证明上述策略。若 RTL 选择“drain 完成后响应 kill”，应在 timing trace 中展示 kill 被延迟到 `W1` 后。

## 9. Illegal layout 和 mask/tail 契约

Dedicated path 只能在 v1 已允许的 layout 上运行：

- `LMUL=m1/m2/m4` 且 paired group alignment/range 合法；
- `LMUL=m8` illegal；
- `vstart == 0`；
- e16/e32/e64 format 被支持；
- mask/tail byte enable 基于 request/tag 中冻结的 `vl/vsew/vm/mask_bits/elem_idx`。

任何 illegal layout 必须在 dedicated request 发出前被拒绝；不得由 CFMA block 接收后再报错。

## 10. fallback 选择

RTL 必须保留 v1 fallback：

```text
if dedicated_enable && layout_supported && stage5_verified:
  use dedicated CFMA path
else:
  use v1 four-phase FPU fallback
```

在阶段 3/4 中，`dedicated_enable` 默认仍为 false。阶段 4 允许实例化 dedicated compute block 和收集 result，但不得让 result 覆盖 v1 architectural writeback。阶段 5 才允许在受控参数下打开 dedicated writeback。

## 11. 阶段 2 退出标准对照

| 要求 | 本文位置 | 状态 |
| --- | --- | --- |
| request valid/ready 时序 | 第 5、6.1 节 | 已冻结 |
| dedicated unit blocking/multi-cycle/pipelined 定义 | 第 5 节 | 初始冻结为 blocking multi-cycle single-entry |
| backpressure 如何作用于 VFU issue | 第 5 节 | 已冻结 |
| tag 携带 `vd/vd+LMUL/vsew/vl/mask/tail/element index` | 第 4 节 | 已冻结 |
| status/fflags architectural completion | 第 7 节 | 已冻结 |
| flush/kill/debug partial progress 策略 | 第 8 节 | 已冻结为 non-resumable/no partial completion |
| request/result/writeback timing table | 第 6 节 | 已冻结 |
| v1 fallback 仍可选择 | 第 10 节 | 已冻结 |

## 12. 阶段 3 前置约束

阶段 3 六操作数 VRF 分拍读取实现必须直接遵守：

- `R0: a.real, a.imag, b.real`；
- `R1: b.imag, c.real, c.imag`；
- mask snapshot 与 tag 在 `R1` 完成时冻结；
- request accepted 前无 architectural side effect；
- illegal layout 在 `I0/R0` 前拒绝。
