# CFMA v2 阶段 1 小阶段：`fpnew_complex_fma` directed standalone 验证

**日期**：2026-07-07  
**分支**：`feature/cfma-v2-datapath`  
**基线提交**：`2564708` (`[cfma-v2] Record stage 0 baseline verification`)

## 1. 本小阶段目标

阶段 1 的完整目标是建立 `fpnew_complex_fma` 独立 reference/testbench，并冻结 arithmetic、rounding 和 fflags 行为。本次完成其中的第一个可验证切片：

- 建立 standalone Verilator testbench：`hw/ip/spatz/test/fpnew_complex_fma_tb.sv`；
- 对 FP64/FP32/FP16 三个参数化实例分别检查 exact-bit directed case；
- 使用 TDD 红绿流程证明测试能捕获当前 prototype 的算术错误；
- 修正 `hw/ip/spatz/src/fpnew_complex_fma.sv` 中把两个部分积再次相乘的错误；
- 确认修正后 standalone directed test 通过，且默认 v1 fallback regression 未受影响。

## 2. 独立算术契约

本小阶段冻结的 directed arithmetic contract 与 v1 四阶段语义一致：

```text
real = c.real + a.real * b.real - a.imag * b.imag
imag = c.imag + a.imag * b.real + a.real * b.imag
```

为了与 v1 初始 correctness baseline 对齐，当前 dedicated block 采用两轮 `fpnew_fma` 累加顺序：

| Phase | Real path | Imag path |
| --- | --- | --- |
| 1 | `real_acc = FMADD(a.real, b.real, c.real)` | `imag_acc = FMADD(a.imag, b.real, c.imag)` |
| 2 | `real = FNMSUB(a.imag, b.imag, real_acc)` | `imag = FMADD(a.real, b.imag, imag_acc)` |

这不是最终性能优化形态；它是阶段 1 独立 correctness baseline，用于先把 arithmetic/data-contract 固化。

## 3. TDD 红灯证据

在修复前运行 standalone testbench，build 成功、run 失败：

```text
build_status=0 run_status=134
[95000] %Fatal: fpnew_complex_fma_tb.sv:178: Assertion failed in fpnew_complex_fma_tb.run_fp64_directed: FP64 real mismatch: actual=0xc03f000000000000 expected=0x3ff8000000000000
```

根因：旧实现 final real 阶段执行了 `FNMSUB(prod_rr, prod_ii, c.real)`，即 `-(4.5 * 8) + 5 = -31`，而不是 `5 + 4.5 - 8 = 1.5`。旧 imag 阶段也把 partial products 相乘，而不是执行第二次累加。

证据文件：

- `docs/v2/evidence/stage1_fpnew_complex_fma_tb_red_build.txt`
- `docs/v2/evidence/stage1_fpnew_complex_fma_tb_red_run.txt`
- `docs/v2/evidence/stage1_fpnew_complex_fma_tb_red_status.txt`

## 4. 修正内容

`hw/ip/spatz/src/fpnew_complex_fma.sv` 已重写为独立 handshaked sequential block：

- 输入 handshake 后锁存 6 个 operand 和 tag；
- 使用 `PHASE1_ISSUE/WAIT` 与 `PHASE2_ISSUE/WAIT` 两轮驱动两个 `fpnew_fma` 实例；
- 在两轮结果返回时累计 `NV/DZ/OF/UF/NX` flags；
- `RESULT` 状态保持 `{result_real, result_imag, status, tag}` 到 `result_ready_i`；
- `flush_i` 会清空内部状态并回到 `IDLE`。

## 5. 绿灯与集成验证

修复后 fresh verification：

```text
git diff --check: PASS
fpnew_complex_fma_tb build: PASS
fpnew_complex_fma_tb run: PASS
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt: PASS
ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$': PASS (3/3)
```

CTest 时间：

```text
vfmacc : 21.83 s
vfcmacc: 116.33 s
vfnmsac: 22.14 s
Total : 160.31 s
```

证据文件：

- `docs/v2/evidence/stage1_fpnew_complex_fma_tb_green_build.txt`
- `docs/v2/evidence/stage1_fpnew_complex_fma_tb_green_run.txt`
- `docs/v2/evidence/stage1_fpnew_complex_fma_tb_green_status.txt`
- `docs/v2/evidence/stage1_verification.txt`

## 6. 已覆盖与未覆盖

已覆盖：

- standalone testbench 能独立实例化 `fpnew_complex_fma`；
- FP64/FP32/FP16 三种 `FpFormat` 参数化实例；
- RNE 下 exact directed finite operand；
- tag pass-through；
- exact case 下 fflags 全 0；
- 当前 Spatz 默认 build 可编译；
- dedicated writeback 仍默认禁用，v1 fallback regression 通过。

尚未覆盖，仍属于阶段 1 后续工作：

- NaN/Inf/signed zero directed cases；
- 非 exact rounding cases 与 RTZ/RDN/RUP/RMM rounding modes；
- 随机 operand tuple；
- 以软件/SoftFloat 或 fpnew reference driver 自动生成 expected bits/fflags；
- VFU 侧 dynamic FP format selection；
- packed e16/e32 lane semantics；
- default dedicated writeback 或 ISA-level dedicated-mode regression。

## 7. 下一步

阶段 1 下一小阶段建议：把 standalone testbench 从 directed exact cases 扩展为 reference-driven matrix，优先覆盖 signed zero、NaN/Inf、rounding mode 和 fflags，再进入阶段 2 request/response 契约冻结。
