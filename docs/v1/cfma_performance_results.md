# CFMA v1 性能与测试证据

**记录日期**：2026-07-06
**整理日期**：2026-07-07
**范围**：v1 四阶段 FPU 复用实现

## 1. 结论

v1 不声明完整 benchmark correctness，也不声明 speedup。

当前可以说明的是：

- `vfcmacc.vv` 将软件可见复数 MAC 指令序列从 4 条折叠为 1 条；
- 该折叠降低 fetch/decode/offload/issue queue 压力；
- 当前硬件内部仍执行 4 个 FPU phase，因此不应期待原始 FPU 吞吐的大幅提升；
- dedicated datapath 默认禁用，不能作为性能结果来源。

## 2. 已记录命令与结果

### 基础检查

```bash
git diff --check
```

结果：PASS。

### RTL 仿真器构建

```bash
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
```

结果：PASS，目标已是最新或构建完成。

### 软件构建

```bash
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt
```

结果：PASS，CTest 注册了 `vfcmacc_illegal` 和 `vfcmacc`。

### ISA RTL 回归

```bash
cd hw/system/spatz_cluster/sw/build
PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" \
  ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure
```

结果：PASS，3/3 通过。

```text
vfmacc:  27.18 s
vfcmacc: 137.46 s
vfnmsac: 21.69 s
Total:   186.35 s
```

### 性能测试探针

```bash
cd hw/system/spatz_cluster/sw/build
PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" \
  ctest -R 'spatzBenchmarks-rtl-spatzBenchmarks-rtl-(dp-cdotp_old_M128|dp-cdotp_vfcmacc_M128|dp-caxpy_M256|dp-caxpy_vfcmacc_M256)$' --output-on-failure
```

结果：该轮被中断，退出码 130。已观察到：

| Target | 结果 | 时间 | 结论 |
| --- | --- | ---: | --- |
| `dp-caxpy_M256` | PASS | 1.59 s | 小规模 baseline probe 可完成 |
| `dp-caxpy_vfcmacc_M256` | PASS | 1.51 s | 小规模 vfcmacc probe 可完成 |
| `dp-cdotp_old_M128` | 未完成 | >17 min | performance closure blocked |
| `dp-cdotp_vfcmacc_M128` | 未执行到 | n/a | 无结论 |

## 3. 不作出的声明

v1 不声明：

- dedicated CFMA hardware correctness；
- full benchmark correctness；
- speedup；
- Step 12 dedicated writeback completion；
- 旧目标 `>2x` 或 `3.5x` 已达成。

## 4. 三种方案的预期效率边界

| 方案 | 软件指令数 | 内部计算 | 预期效率 |
| --- | ---: | --- | --- |
| 不使用复数指令 | 4 条 | 4 次普通 FPU op | baseline 1.0x |
| v1 `vfcmacc.vv` | 1 条 | 4 个内部 FPU phase | cycle 约 1.0-1.2x；指令数 4x 降低 |
| v2 dedicated datapath | 1 条 | dedicated complex-FMA | 目标 2x+，理想 3-4x；尚未证明 |

## 5. 后续工作

性能闭环应放到 v2 或独立 benchmark closure 分支中进行。完成前不得把 probe 数据当成正式 speedup 证据。
