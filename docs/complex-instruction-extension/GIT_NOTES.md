# 复数指令扩展 Git 记录

本文件记录复数指令扩展工程的分支、阶段提交、验证命令和远端操作状态。

## 初始状态

记录时间：2026-06-08

工作树：

```text
/home/wxt/spatz-cfma
```

分支：

```text
feature/cfma-instruction-extension
```

初始状态：

```text
## feature/cfma-instruction-extension
?? docs/complex-instruction-extension/
```

复制 `.codexignore` 后的待提交状态：

```text
## feature/cfma-instruction-extension
?? .codexignore
?? docs/complex-instruction-extension/
```

说明：

- 当前工程在 linked worktree 中进行，避免与
  `feature/online-softmax-merge-engine` 的 accelerator 改动混合。
- `.codexignore` 已从 `/home/wxt/spatz/.codexignore` 复制到当前工作树根目录，
  用于过滤 toolchain、build output、仿真波形和二进制产物。

## 分支策略

主开发分支：

```text
feature/cfma-instruction-extension
```

推荐阶段提交：

```text
[cfma] Record complex instruction planning baseline
[cfma] Add complex register layout reference checks
[cfma] Add vfcmacc opcode pattern
[cfma] Decode vfcmacc in Snitch and Spatz
[cfma] Add vfcmacc e32 micro-op execution
[cfma] Add vfcmacc e64 and e16 behavior
[cfma] Cover vfcmacc mask and tail behavior
[cfma] Cover vfcmacc numerical corner cases
[cfma] Complete vfcmacc ISA behavior
[cfma] Add vfcmacc dp-cdotp benchmark path
[cfma] Add vfcmacc mnemonic support
[cfma] Record complex datapath v2 decision
```

## 每阶段提交模板

```text
日期：
Node：
计划提交：
实际提交：
修改范围：
验证命令：
结果摘要：
遗留风险：
远端 Git 操作：
```

## 2026-06-08 Node 0 计划记录

计划提交：

```text
[cfma] Record complex instruction planning baseline
```

范围：

```text
A  .codexignore
A  docs/complex-instruction-extension/GIT_NOTES.md
A  docs/complex-instruction-extension/PHASE_RESULTS.md
A  docs/complex-instruction-extension/PLAN.md
A  docs/complex-instruction-extension/README.md
```

目的：

- 建立隔离工作树下的复数指令扩展文档基线。
- 复制并追踪 `.codexignore`。
- 将计划重构为 node-by-node 工程流程。
- 明确测试标准、结果标准、阶段记录和 git 操作要求。

验证：

```text
git diff --check: PASS，退出码 0。
make -C hw/system/spatz_cluster help: PASS，退出码 0；成功打印 Makefile targets。
```

备注：

```text
make help 过程中提示 /home/wxt/spatz-cfma/install/bender/bender 不存在。
该提示属于当前工作树未 bootstrap pinned toolchain 的基线事实，不影响 help
目标退出码和目标列表打印。
```

远端 Git 操作：

```text
暂无。
```

## 2026-06-08 Plan hardening 记录

计划提交：

```text
[cfma] Harden complex instruction plan for goal execution
```

范围：

```text
M  docs/complex-instruction-extension/GIT_NOTES.md
M  docs/complex-instruction-extension/PHASE_RESULTS.md
M  docs/complex-instruction-extension/PLAN.md
```

目的：

- 冻结 goal 一次性执行的默认决策。
- 明确 `make update_opcodes` 是 Node 2 默认 opcode 生成入口。
- 将隐式 imag group hazard 策略固定为 conservative serialization fence。
- 拆分原 Node 5，并收紧 `dp-cdotp` benchmark 验收目标。

验证：

```text
git diff --check: PASS，退出码 0。
```

远端 Git 操作：

```text
暂无。
```

## 2026-06-08 Node 1 记录

日期：

```text
2026-06-08
```

Node：

```text
Node 1：Register Layout Reference 与 Encoding 决策
```

分支和状态：

```text
## feature/cfma-instruction-extension
?? docs/complex-instruction-extension/register_layout.md
?? docs/complex-instruction-extension/scripts/
```

计划提交：

```text
[cfma] Add complex register layout reference checks
```

修改范围：

```text
A  docs/complex-instruction-extension/register_layout.md
A  docs/complex-instruction-extension/scripts/cfma_register_layout.py
M  docs/complex-instruction-extension/PHASE_RESULTS.md
M  docs/complex-instruction-extension/GIT_NOTES.md
M  docs/complex-instruction-extension/README.md
```

目的：

- 生成 `LMUL=m1/m2/m4/m8`、`v0..v31` 的 paired register layout 全表。
- 冻结 v1 legal/illegal policy：`m1/m2/m4` 可在 alignment/range 合法时使用，
  `m8` 默认 illegal，`vd` pair 与任一 source pair overlap illegal。
- 冻结 `vfcmacc.vv` 的 OPFVV encoding：
  `32'b111010???????????001?????1010111`。

验证命令：

```text
python3 docs/complex-instruction-extension/scripts/cfma_register_layout.py: PASS，退出码 0。
python3 docs/complex-instruction-extension/scripts/cfma_register_layout.py --write-md docs/complex-instruction-extension/register_layout.md: PASS，退出码 0。
git diff --check: PASS，退出码 0。
```

结果摘要：

```text
脚本输出 128 行 layout 记录；`VFCMACC_VV` 与 `VFMACC_VV`、`VFNMSAC_VV`、
`VFWDOTP_VV`、`VFWDOTP_VF` 无 checked overlap。
```

实际提交：

```text
4d629877ceacdd47500640e6ff5f134cbd374a56
```

遗留风险：

```text
尚未更新 opcode source 或 generated `riscv_instr.sv`；Node 2 必须通过
`make update_opcodes` 完成，不允许只手改 generated file。
```

远端 Git 操作：

```text
暂无。
```

## 2026-06-08 Node 2 记录

日期：

```text
2026-06-08
```

Node：

```text
Node 2：Opcode 生成与 Snitch 识别
```

分支和状态：

```text
## feature/cfma-instruction-extension
 M hw/ip/snitch/src/riscv_instr.sv
 M hw/ip/snitch/src/snitch.sv
 M hw/system/spatz_cluster/src/generated/testharness.sv
 M hw/system/spatz_cluster/test/bootrom.elf
 M sw/riscvTests/CMakeLists.txt
?? .venv
?? sw/riscvTests/isa/rv64uv/vfcmacc_smoke.c
```

计划提交：

```text
[cfma] Add vfcmacc opcode pattern
```

修改范围：

```text
M  Makefile
M  hw/ip/snitch/src/riscv_instr.sv
M  hw/ip/snitch/src/snitch.sv
M  sw/riscvTests/CMakeLists.txt
A  sw/riscvTests/isa/rv64uv/vfcmacc_smoke.c
A  sw/toolchain-patches/riscv-opcodes/vfcmacc-vv.patch
M  docs/complex-instruction-extension/PHASE_RESULTS.md
M  docs/complex-instruction-extension/GIT_NOTES.md
```

目的：

- 增加 tracked opcode patch，在 pinned opcode source 中加入 `vfcmacc.vv`。
- 通过 `make update_opcodes` 生成 `riscv_instr::VFCMACC_VV`。
- 让 Snitch 在 RVV/RVF vector FP offload 分支识别该 pattern。
- 增加 compile-only inline assembly smoke test，先不执行。

验证命令：

```text
make update_opcodes: PASS，退出码 0。
make update_opcodes: PASS，退出码 0；幂等重跑显示 opcode patch already applied。
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt: PASS，退出码 0。
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt: PASS，退出码 0。
git diff --check: 提交前运行并记录。
```

结果摘要：

```text
tracked patch 将 `opcodes-rvv` 更新为包含
`vfcmacc.vv 31..26=0x3a ... 14..12=0x1 ... 6..0=0x57`；generated
`riscv_instr.sv` 包含
`VFCMACC_VV = 32'b111010???????????001?????1010111`；Snitch decode 只在
RVV/RVF vector FP offload case 中加入该指令，未加入 scalar FP source case。
```

实际提交：

```text
386e380a95ea9c102ded228e862d1e6958d5bc5e
```

遗留风险：

```text
Spatz decode、配置开关、非法 layout、serialization fence 和 VFU 执行尚未实现；
由 Node 3/4 继续处理。`sw/toolchain/riscv-opcodes` 是 ignored nested checkout，
父仓库不能直接提交其中单个源文件；本 node 用 tracked patch 保留 source 变更。
工作树中存在未 stage 的本地生成差异
`hw/system/spatz_cluster/src/generated/testharness.sv` 与
`hw/system/spatz_cluster/test/bootrom.elf`，本 node 不提交这些产物。
```

远端 Git 操作：

```text
暂无。
```

## 2026-06-08 Node 3 记录

日期：

```text
2026-06-08
```

Node：

```text
Node 3：Spatz Decode、配置开关与非法路径
```

分支和状态：

```text
## feature/cfma-instruction-extension
 M hw/ip/snitch/src/snitch.sv
 M hw/ip/spatz/src/generated/spatz_pkg.sv
 M hw/ip/spatz/src/spatz_controller.sv
 M hw/ip/spatz/src/spatz_decoder.sv
 M hw/ip/spatz/src/spatz_pkg.sv.tpl
 M hw/system/spatz_cluster/src/generated/testharness.sv
 M hw/system/spatz_cluster/test/bootrom.elf
 M sw/riscvTests/CMakeLists.txt
?? .venv
?? sw/riscvTests/isa/rv64uv/vfcmacc_illegal.c
```

计划提交：

```text
[cfma] Decode vfcmacc in Snitch and Spatz
```

修改范围：

```text
M  hw/ip/snitch/src/snitch.sv
M  hw/ip/spatz/src/generated/spatz_pkg.sv
M  hw/ip/spatz/src/spatz_controller.sv
M  hw/ip/spatz/src/spatz_decoder.sv
M  hw/ip/spatz/src/spatz_pkg.sv.tpl
M  sw/riscvTests/CMakeLists.txt
A  sw/riscvTests/isa/rv64uv/vfcmacc_illegal.c
M  docs/complex-instruction-extension/PHASE_RESULTS.md
M  docs/complex-instruction-extension/GIT_NOTES.md
```

目的：

- 增加 `RVV_EXT_XVFCOMPLEX` 配置开关和内部 op `VFCMADD`。
- 让 Spatz decoder 将 `VFCMACC_VV` 映射到 VFU request，保留 `vd_is_src`。
- 在 controller 中按当前 `vtype/vstart` 检查 paired register layout，并拒绝
  `m8`、misaligned base、越界 pair、`vd` 与 source pair overlap、unsupported SEW
  和 `vstart != 0`。
- 实现 v1 conservative serialization fence：`VFCMADD` 发射前等待旧非 `CON`
  指令完成，`VFCMADD` 完成前阻止新的 VFU/VLSU/VSLDU 指令发射。
- 让 Spatz issue response 的 exception 进入 Snitch illegal trap 路径。
- 增加 `vfcmacc_illegal` RTL regression。

验证命令：

```text
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt: PASS，退出码 0。
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt: PASS，退出码 0。
cd hw/system/spatz_cluster/sw/build && ctest -R vfcmacc_illegal --output-on-failure: PASS，退出码 0。
git diff --check: PASS，退出码 0。
```

结果摘要：

```text
`riscv_instr::VFCMACC_VV` 现在在 Spatz 解码为 `VFCMADD`；非法动态 layout 经
Spatz issue response exception 反馈给 Snitch 并以 illegal instruction trap
完成。`vfcmacc_illegal` 覆盖 m8、misaligned m2 vd、out-of-range m4 vd、vd/vs1
overlap、vd/vs2 overlap、e8 unsupported 和 reserved `.vf` encoding。

中间失败记录：初版 CTest 只看到 RTL `$display` illegal，测试未收到 trap；
修复 Snitch `acc_issue_exception` 后测试 trap handler 又因 caller-saved register
破坏而误读 cause 0/4；改为 pure assembly trap entry 后，发现 `vd=v24,m4` 不是
越界，最终改为 `vd=v28,m4`。
```

实际提交：

```text
5a4179efd06a359fea36e3724f2aac3900ac1e49
```

遗留风险：

```text
`vstart != 0` 当前按 Node 3 policy 定义为 illegal，Node 5b 重新评估最终 v1
行为。VFU 执行尚未实现，Node 4 继续处理。`RVV_EXT_XVFCOMPLEX=0` 有 RTL hook，
但本 node 未单独做 disabled-config build。工作树中仍存在未 stage 的本地生成差异
`hw/system/spatz_cluster/src/generated/testharness.sv` 与
`hw/system/spatz_cluster/test/bootrom.elf`，本 node 不提交这些产物。
```

远端 Git 操作：

```text
暂无。
```

## 2026-06-08 Node 4 记录

日期：

```text
2026-06-08
```

Node：

```text
Node 4：v1a Unmasked e32 多拍执行
```

分支和状态：

```text
## feature/cfma-instruction-extension
 M docs/complex-instruction-extension/PHASE_RESULTS.md
 M hw/ip/spatz/src/spatz_vfu.sv
 M hw/system/spatz_cluster/src/generated/testharness.sv
 M hw/system/spatz_cluster/test/bootrom.elf
 M sw/riscvTests/CMakeLists.txt
?? .venv
?? sw/riscvTests/isa/rv64uv/vfcmacc_e32.c
```

计划提交：

```text
[cfma] Add vfcmacc e32 micro-op execution
```

修改范围：

```text
M  hw/ip/spatz/src/spatz_vfu.sv
M  sw/riscvTests/CMakeLists.txt
A  sw/riscvTests/isa/rv64uv/vfcmacc_e32.c
M  docs/complex-instruction-extension/PHASE_RESULTS.md
M  docs/complex-instruction-extension/GIT_NOTES.md
```

目的：

- 在 VFU 中为 `VFCMADD` 增加 `Cfma_RR/Cfma_II/Cfma_RI/Cfma_IR` 四阶段执行。
- 按 paired layout 和 LMUL offset 选择 real/imag source 与 destination group。
- 将 `Cfma_II` 映射到 `FNMSUB`，其余阶段映射到 `FMADD`，复用现有 FPU/VRF 通路。
- 在内部 phase 最后写回后推进下一阶段，只在 final phase 产生 architectural
  completion。
- 累积四个内部 FPU status 并只在 final result response 那一拍暴露给 Snitch。
- 新增 `vfcmacc_e32` RTL regression，覆盖单条和 back-to-back same accumulator
  pair。

验证命令：

```text
TDD red: cd hw/system/spatz_cluster/sw/build && ctest -R vfcmacc_e32 --output-on-failure:
FAIL，退出码 8，关键输出 `real[0] Got 0, expected 1070386381`。
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt: PASS，退出码 0。
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt: PASS，退出码 0。
cd hw/system/spatz_cluster/sw/build && ctest -R vfcmacc_e32 --output-on-failure: PASS，退出码 0。
cd hw/system/spatz_cluster/sw/build && ctest -R "vfcmacc_e32|vfcmacc_illegal|vfmacc|vfnmsac" --output-on-failure: PASS，退出码 0。
git diff --check: PASS，退出码 0。
```

结果摘要：

```text
`vfcmacc.vv v8, v0, v2` 在 e32/m1/vm=1 下逐 bit 匹配四指令 reference sequence：
`vfmacc v16,v0,v2; vfnmsac v16,v1,v3; vfmacc v17,v0,v3; vfmacc v17,v1,v2`。
同一测试还覆盖连续两条 `vfcmacc.vv` 写同一 accumulator pair，未 deadlock 且结果
匹配两轮 reference sequence。VFU 对非 final internal phases 不发 architectural
response，final phase 才返回一次 completion；内部 FPU status 经 `cfma_status_q`
累积后在 final result response 送出。
```

实际提交：

```text
112aa25d9e1453024148c96b4f88b5b3d471caf0
```

遗留风险：

```text
本 node 是 v1a，只覆盖 e32、vm=1、合法 non-overlap paired layout。e64/e16 留给
Node 5a，mask/tail/vstart 留给 Node 5b，NaN/Inf/zero sign/rounding/精确 fflags 对比
留给 Node 5c，完整 real/imag serialization fence hazard regression 留给 Node 5d。
工作树中仍存在未 stage 的本地生成差异
`hw/system/spatz_cluster/src/generated/testharness.sv` 与
`hw/system/spatz_cluster/test/bootrom.elf`，本 node 不提交这些产物。
```

远端 Git 操作：

```text
暂无。
```

## 2026-06-08 Node 5a 记录

日期：

```text
2026-06-08
```

Node：

```text
Node 5a：e64/e16 Format 支持
```

分支和状态：

```text
## feature/cfma-instruction-extension
 M docs/complex-instruction-extension/PHASE_RESULTS.md
 M hw/ip/spatz/src/spatz_controller.sv
 M hw/system/spatz_cluster/src/generated/testharness.sv
 M hw/system/spatz_cluster/test/bootrom.elf
 M sw/riscvTests/CMakeLists.txt
 D sw/riscvTests/isa/rv64uv/vfcmacc_e32.c
 M sw/riscvTests/isa/rv64uv/vfcmacc_illegal.c
?? .venv
?? sw/riscvTests/isa/rv64uv/vfcmacc.c
```

计划提交：

```text
[cfma] Add vfcmacc e64 and e16 behavior
```

修改范围：

```text
M  hw/ip/spatz/src/spatz_controller.sv
M  sw/riscvTests/CMakeLists.txt
R  sw/riscvTests/isa/rv64uv/vfcmacc_e32.c -> sw/riscvTests/isa/rv64uv/vfcmacc.c
M  sw/riscvTests/isa/rv64uv/vfcmacc_illegal.c
M  docs/complex-instruction-extension/PHASE_RESULTS.md
M  docs/complex-instruction-extension/GIT_NOTES.md
```

目的：

- 将 Node 4 的 `vfcmacc_e32` regression 整理为统一 `vfcmacc` 目标。
- 保留 e32 single 和 back-to-back same accumulator cases。
- 新增 e64/e16 unmasked cases，均用
  `vfmacc/vfnmsac/vfmacc/vfmacc` 四指令 reference sequence 做逐 bit 对比。
- 拒绝 `fmode.src/dst != 0` 的 alternative FP format，使 `VFCMADD` 只使用 v1
  支持的 IEEE FP16/FP32/FP64 formats。
- 扩展 `vfcmacc_illegal`，覆盖 e16 alternative fmode trap。

验证命令：

```text
TDD red: cd hw/system/spatz_cluster/sw/build && ctest -R "vfcmacc$|vfcmacc_illegal" --output-on-failure:
FAIL，退出码 8，关键输出 `unsupported alternative fmode did not raise illegal instruction trap.`。
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt: PASS，退出码 0。
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt: PASS，退出码 0。
cd hw/system/spatz_cluster/sw/build && ctest -R "vfcmacc$|vfcmacc_illegal" --output-on-failure: PASS，退出码 0。
```

结果摘要：

```text
`vfcmacc` 覆盖 e32、e64、e16 unmasked behavior，并与四条现有 RVV FMA reference
sequence 逐 bit 匹配。e64 在默认 RVD/ELEN=64 build 中覆盖；e16 使用 IEEE FP16
format。新增 controller legality gate 拒绝 nonzero `fmode.src/dst`，`vfcmacc_illegal`
确认 alternative fmode 会触发 illegal instruction trap。
```

实际提交：

```text
0c9bf22a7a9f80f01956e0855db7b7707490a49f
```

遗留风险：

```text
mask、tail 和 vstart 行为留给 Node 5b；NaN/Inf/zero sign/rounding/精确 fflags
对比留给 Node 5c；serialization fence hazard regression 留给 Node 5d。工作树中仍
存在未 stage 的本地生成差异 `hw/system/spatz_cluster/src/generated/testharness.sv`
与 `hw/system/spatz_cluster/test/bootrom.elf`，本 node 不提交这些产物。
```

远端 Git 操作：

```text
暂无。
```

## 2026-06-08 Node 5b 记录

日期：

```text
2026-06-08
```

Node：

```text
Node 5b：Mask、Tail 与 vstart 行为
```

分支和状态：

```text
## feature/cfma-instruction-extension
 M docs/complex-instruction-extension/PHASE_RESULTS.md
 M hw/ip/spatz/src/spatz_vfu.sv
 M hw/system/spatz_cluster/src/generated/testharness.sv
 M hw/system/spatz_cluster/test/bootrom.elf
 M sw/riscvTests/isa/rv64uv/vfcmacc.c
 M sw/riscvTests/isa/rv64uv/vfcmacc_illegal.c
?? .venv
```

计划提交：

```text
[cfma] Cover vfcmacc mask and tail behavior
```

修改范围：

```text
M  hw/ip/spatz/src/spatz_vfu.sv
M  sw/riscvTests/isa/rv64uv/vfcmacc.c
M  sw/riscvTests/isa/rv64uv/vfcmacc_illegal.c
M  docs/complex-instruction-extension/PHASE_RESULTS.md
M  docs/complex-instruction-extension/GIT_NOTES.md
```

目的：

- 为 `vfcmacc` regression 增加 e32/e64/e16 masked cases，masked-off lanes 必须
  保持原 accumulator。
- 为 e32/e64/e16 增加 short-`vl` tail-undisturbed cases，tail lanes 必须保持原
  accumulator。
- 将 `vstart != 0` 冻结为 v1 illegal policy，并在 `vfcmacc_illegal` 覆盖 trap。
- 在 VFU 内为 `VFCMADD` 预读 `v0` mask，并按 active element 生成 VRF byte-enable，
  让 masked-off/tail bytes 不写回。

验证命令：

```text
TDD red: cd hw/system/spatz_cluster/sw/build && ctest -R "vfcmacc$|vfcmacc_illegal" --output-on-failure:
FAIL，退出码 8；`vfcmacc_illegal` 通过，`vfcmacc` 在 TC5/6/7/8/9/10 masked/tail
cases 失败，证明 inactive lanes 被覆盖。
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt: PASS，退出码 0。
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt: PASS，退出码 0。
cd hw/system/spatz_cluster/sw/build && ctest -R "vfcmacc$|vfcmacc_illegal" --output-on-failure: PASS，退出码 0。
git diff --check: PASS，退出码 0。
git diff --cached --check: PASS，退出码 0。
```

结果摘要：

```text
`VFCMADD` 在 vm=0 时先通过现有 VFU vs2 read port 预读 v0 mask，后续四个
Cfma_RR/Cfma_II/Cfma_RI/Cfma_IR phases 仍复用原 FPU/VRF 通路；每个 result tag 携带
element base index，writeback 时只对 active element bytes 置位 `vrf_wbe_o`。
e32/e64/e16 masked 和 tail-undisturbed cases 全部通过。`vstart != 0` 仍按 v1 policy
illegal，由 `vfcmacc_illegal` 覆盖。
```

实际提交：

```text
4c50592b2ce1ef3ecbc606eb7face27b59aebd67
```

遗留风险：

```text
inactive lane 是否产生内部 FPU status 仍需 Node 5c 以精确 fflags/NaN coverage 验证。
工作树中仍存在未 stage 的本地生成差异
`hw/system/spatz_cluster/src/generated/testharness.sv` 与
`hw/system/spatz_cluster/test/bootrom.elf`，本 node 不提交这些产物。
```

远端 Git 操作：

```text
暂无。
```

## 2026-06-08 Node 5c 记录

日期：

```text
2026-06-08
```

Node：

```text
Node 5c：特殊数值、Rounding 与 FFLAGS
```

分支和状态：

```text
## feature/cfma-instruction-extension
 M docs/complex-instruction-extension/PHASE_RESULTS.md
 M hw/system/spatz_cluster/src/generated/testharness.sv
 M hw/system/spatz_cluster/test/bootrom.elf
 M sw/riscvTests/isa/rv64uv/vfcmacc.c
?? .venv
```

计划提交：

```text
[cfma] Cover vfcmacc numerical corner cases
```

修改范围：

```text
M  sw/riscvTests/isa/rv64uv/vfcmacc.c
M  docs/complex-instruction-extension/PHASE_RESULTS.md
M  docs/complex-instruction-extension/GIT_NOTES.md
```

目的：

- 在 `vfcmacc` regression 中增加 e32 special fixture，覆盖 signed zero、NaN、Inf、
  overflow、invalid 和 fractional rounding inputs。
- 对 RNE 与 RTZ rounding-mode 分别比较 `vfcmacc.vv` 和四指令 reference sequence
  的 result bits 与 `fflags`。
- 增加 masked signaling-NaN case，明确 `fflags` 必须 bit-identical 于当前四条
  masked FMA reference sequence。
- 运行现有 `vfmacc`、`vfnmsac` 和包含 `vfwdotp.vf` 的 sdotp proxy regression。

验证命令：

```text
TDD red: cd hw/system/spatz_cluster/sw/build && ctest -R "vfcmacc$" --output-on-failure:
FAIL，退出码 8；初版 TC13 错误地期望 masked-off sNaN lanes 不产生 flags，输出
`[TC 13] fflags FAILED. Got 0x10, expected 0x0.`。按 v1 reference 要求修正为比较
`vfcmacc.vv` 与四条 masked FMA sequence 的 flags。
cd hw/system/spatz_cluster/sw/build && ctest -R "vfcmacc$" --output-on-failure: PASS，退出码 0。
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt: PASS，退出码 0。
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt: PASS，退出码 0。
cd hw/system/spatz_cluster/sw/build && ctest -R "vfcmacc$" --output-on-failure: PASS，退出码 0。
cd hw/system/spatz_cluster/sw/build && ctest -R "vfmacc|vfnmsac|vfwdotp" --output-on-failure: PASS，退出码 0；当前只注册 vfmacc/vfnmsac 两个匹配目标。
cd hw/system/spatz_cluster/sw/build && ctest -R "sdotp-(hp|bp)-fmatmul_M64_N64_K64" --output-on-failure: PASS，退出码 0。
cd hw/system/spatz_cluster/sw/build && ctest -N -R "vfwdotp|dotp": PASS，退出码 0；无独立 vfwdotp ISA CTest。
git diff --check: PASS，退出码 0。
```

结果摘要：

```text
`vfcmacc` 新增 TC11/TC12/TC13，分别覆盖 special result bits + fflags、RTZ
rounding-mode result bits + fflags、masked signaling-NaN fflags reference
equivalence。当前 RTL 无需修改：`VFCMADD` 的 four-phase status OR/final-only
机制与四指令 reference sequence 对齐。
```

实际提交：

```text
47219ff873e0bc8f72f21a25e395a9aa576926f6
```

遗留风险：

```text
serialization fence 的 explicit real/imag hazard regression 仍留给 Node 5d。
工作树中仍存在未 stage 的本地生成差异
`hw/system/spatz_cluster/src/generated/testharness.sv` 与
`hw/system/spatz_cluster/test/bootrom.elf`，本 node 不提交这些产物。
```

远端 Git 操作：

```text
暂无。
```

## 2026-06-08 Node 5d 记录

日期：

```text
2026-06-08
```

Node：

```text
Node 5d：Serialization Fence 与 Hazard Regression
```

分支和状态：

```text
## feature/cfma-instruction-extension
 M docs/complex-instruction-extension/PHASE_RESULTS.md
 M hw/system/spatz_cluster/src/generated/testharness.sv
 M hw/system/spatz_cluster/test/bootrom.elf
 M sw/riscvTests/isa/rv64uv/vfcmacc.c
?? .venv
```

计划提交：

```text
[cfma] Complete vfcmacc ISA behavior
```

修改范围：

```text
M  sw/riscvTests/isa/rv64uv/vfcmacc.c
M  docs/complex-instruction-extension/PHASE_RESULTS.md
M  docs/complex-instruction-extension/GIT_NOTES.md
```

目的：

- 增加 `vfcmacc.vv` 后立即读取 `vd.real/vd.imag` 的普通 vector 指令 regression。
- 增加普通 VFU 写 `vs1.imag`、`vs2.imag` 后立即执行 `vfcmacc.vv` 的 regression。
- 增加 VLSU 写 `vs1.imag` 与 `vs2.imag` 后立即执行 `vfcmacc.vv` 的 hidden-imag
  dependency regression。
- 增加三连 `vfcmacc.vv` 写同一 accumulator pair 的 ordering/deadlock regression。
- 通过 `vfcmacc_illegal` 继续覆盖 overlap illegal 不进入执行状态。

验证命令：

```text
TDD red/mutation: 临时设置 spatz_controller.sv 中 cfma_fence_stall = 1'b0，
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt:
PASS，退出码 0。
cd hw/system/spatz_cluster/sw/build && ctest -R "vfcmacc$" --output-on-failure:
FAIL，退出码 8；输出 `ERROR: ... vfcmacc.c failed 6 tests!`，masked/tail cases
出现 stale/ordering failure，证明 conservative fence 必要。随后恢复 RTL。
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt:
PASS，退出码 0。
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt:
PASS，退出码 0。
cd hw/system/spatz_cluster/sw/build && ctest -R vfcmacc --output-on-failure:
PASS，退出码 0；`100% tests passed, 0 tests failed out of 2`。
cd hw/system/spatz_cluster/sw/build && ctest -R "vfmacc|vfnmsac|vfwdotp" --output-on-failure:
PASS，退出码 0；当前只注册 vfmacc/vfnmsac 两个匹配目标。
cd hw/system/spatz_cluster/sw/build && ctest -N -R "vfwdotp|dotp":
PASS，退出码 0；无独立 vfwdotp ISA CTest。
cd hw/system/spatz_cluster/sw/build && ctest -R "sdotp-(hp|bp)-fmatmul_M64_N64_K64" --output-on-failure:
PASS，退出码 0。
git diff --check: PASS，退出码 0。
```

结果摘要：

```text
`vfcmacc` 新增 TC14-TC18，覆盖 accumulator pair 后继读取、普通 VFU 写 hidden
imag source、VLSU 写 hidden imag source、以及 back-to-back accumulator ordering。
现有 RTL 无需修改；Node 3 的 conservative serialization fence 覆盖这些 hazards。
至此 v1 ISA 行为不再停留在 v1a：e32/e64/e16、mask/tail、vstart illegal、fflags、
NaN/zero sign 和 serialization fence regression 均已覆盖。
```

实际提交：

```text
4f6904a5a7b0ab81d33d342f5bb68a23eb61b6cc
```

遗留风险：

```text
更精细的 imag group scoreboard 未在 v1 实现，仍按计划保留 conservative fence。
工作树中仍存在未 stage 的本地生成差异
`hw/system/spatz_cluster/src/generated/testharness.sv` 与
`hw/system/spatz_cluster/test/bootrom.elf`，本 node 不提交这些产物。
```

远端 Git 操作：

```text
暂无。
```

## 2026-06-08 Node 6 记录

日期：

```text
2026-06-08
```

## 2026-06-08 Node 6 记录

日期:

```text
2026-06-08
```

Node:

```text
Node 6：Mnemonic 与工具链整理
```

分支和状态：

```text
## feature/cfma-instruction-extension
 M docs/complex-instruction-extension/GIT_NOTES.md
 M docs/complex-instruction-extension/PHASE_RESULTS.md
 M hw/system/spatz_cluster/src/generated/testharness.sv
 M hw/system/spatz_cluster/test/bootrom.elf
?? .venv
?? docs/complex-instruction-extension/toolchain_mnemonic_status.md
?? logs/
```

计划提交：

```text
[cfma] Add vfcmacc mnemonic support
```

修改范围：

```text
A  docs/complex-instruction-extension/toolchain_mnemonic_status.md
M  docs/complex-instruction-extension/PHASE_RESULTS.md
M  docs/complex-instruction-extension/GIT_NOTES.md
```

目的：

- 明确 `vfcmacc.vv` mnemonic 在当前 installed LLVM/binutils 下不可用。
- 记录 `riscv-opcodes` source patch 已存在，但 LLVM/GNU source tree 未展开。
- 记录 `.insn` bring-up 仍可汇编，objdump 仍显示 `<unknown>`。
- 保留 LLVM 自动 SelectionDAG lowering 为 v1 之外工作。

验证命令：

```text
find sw/toolchain -maxdepth 2 -type d: PASS；当前只展开 `sw/toolchain/riscv-opcodes`。
rg -n "vfcmacc|VFCMACC|vfwdotp|VFWDOTP" sw/toolchain sw/toolchain-patches install/llvm install/riscv-gcc -S:
PASS；`vfcmacc` 只出现在 riscv-opcodes source/patch 中，installed toolchain 无支持痕迹。
printf "... vfcmacc.vv v16, v0, v8" | install/llvm/bin/clang -x assembler ...:
FAIL，退出码 1；assembler 报 `unrecognized instruction mnemonic`。
printf "... .insn r 0x57, 0x1, 0x75, v16, v0, v8" | install/llvm/bin/clang -x assembler ...:
PASS，退出码 0；`llvm-objdump -d` 显示 `57 18 80 ea   <unknown>`。
install/llvm/bin/clang --version: PASS；LLVM 14.0.6，pulp-platform revision b494f2d8...
git diff --check: 提交前运行并记录。
```

结果摘要：

```text
Node 7 的正式 mnemonic replacement 未完成，原因是当前工作树没有
`sw/toolchain/llvm-project` 或 `sw/toolchain/riscv-gnu-toolchain` source tree，
installed LLVM 14.0.6 也不识别 `vfcmacc.vv`。v1 bring-up 继续使用 `.insn`
固定编码；正式 assembler/objdump support 需单独展开、patch 并重建 toolchain。
```

实际提交：

```text
e1a31554f63ed7931f68d83bab7fe63c8e6774dc
```

遗留风险：

```text
benchmark/ISA tests 仍不能使用正式 `vfcmacc.vv` mnemonic。Node 6 benchmark
runtime blocker 仍未解除，因此本 node 未运行 `ctest -R "vfcmacc|dp-cdotp"` 的完整
benchmark 部分。
```

远端 Git 操作：

```text
暂无。
```

## 2026-06-08 Node 8 记录

日期：

```text
2026-06-08
```

Node：

```text
Node 7：v2 Datapath 评审门
```

分支和状态：

```text
## feature/cfma-instruction-extension
 M docs/complex-instruction-extension/GIT_NOTES.md
 M docs/complex-instruction-extension/PHASE_RESULTS.md
 M hw/system/spatz_cluster/src/generated/testharness.sv
 M hw/system/spatz_cluster/test/bootrom.elf
?? .venv
?? docs/complex-instruction-extension/v2_datapath_review.md
?? logs/
```

计划提交：

```text
[cfma] Record complex datapath v2 decision
```

修改范围：

```text
A  docs/complex-instruction-extension/v2_datapath_review.md
M  docs/complex-instruction-extension/PHASE_RESULTS.md
M  docs/complex-instruction-extension/GIT_NOTES.md
```

目的：

- 基于当前 v1 ISA、benchmark 和 toolchain 证据评审是否启动专用 complex-FMA
  datapath。
- 明确 v2 no-go：当前分支不新增 fpnew operation、不新增 VRF port、不新增专用
  complex-FMA datapath。
- 记录重新打开 v2 的 entry criteria。

验证命令：

```text
git diff --check: 提交前运行并记录。
```

结果摘要：

```text
v1 ISA 行为已有 RTL regression 覆盖，但 Node 6 未取得 `dp-cdotp` old/new
benchmark 数据，Node 7 未取得正式 mnemonic/objdump support。当前没有足够数据证明
专用 datapath 优于继续优化 v1 sequencer/fence/scoreboard，因此 v2 决策为 no-go。
```

实际提交：

```text
5edfa4333f5d5399159c1e3621241a17b57a437f
```

遗留风险：

```text
如果后续 Node 6 benchmark blocker 和 Node 7 toolchain blocker 被解锁，需要重新打开
v2 评审并先冻结独立 numerical reference，不能直接开始 RTL。
```

远端 Git 操作：

```text
暂无。
```

## 2026-06-10 Node 6 续诊断记录

日期：

```text
2026-06-10
```

Node：

```text
Node 6：dp-cdotp 小规模验证约束与 runtime blocker 续诊断
```

分支和状态：

```text
## feature/cfma-instruction-extension
 M docs/complex-instruction-extension/GIT_NOTES.md
 M docs/complex-instruction-extension/PHASE_RESULTS.md
 M docs/complex-instruction-extension/PLAN.md
 M docs/complex-instruction-extension/README.md
 M docs/complex-instruction-extension/register_layout.md
 M docs/complex-instruction-extension/scripts/cfma_register_layout.py
 M docs/complex-instruction-extension/toolchain_mnemonic_status.md
 M docs/complex-instruction-extension/v2_datapath_review.md
 M sw/spatzBenchmarks/CMakeLists.txt
 M sw/spatzBenchmarks/dp-cdotp/kernel/cdotp.c
 M sw/spatzBenchmarks/dp-cdotp/main.c
```

计划提交：

```text
[cfma] Record dp-cdotp small-scale diagnostics
```

修改范围：

```text
M  docs/complex-instruction-extension/GIT_NOTES.md
M  docs/complex-instruction-extension/PHASE_RESULTS.md
M  docs/complex-instruction-extension/PLAN.md
M  docs/complex-instruction-extension/README.md
M  docs/complex-instruction-extension/register_layout.md
M  docs/complex-instruction-extension/scripts/cfma_register_layout.py
M  docs/complex-instruction-extension/toolchain_mnemonic_status.md
M  docs/complex-instruction-extension/v2_datapath_review.md
M  sw/spatzBenchmarks/CMakeLists.txt
M  sw/spatzBenchmarks/dp-cdotp/kernel/cdotp.c
M  sw/spatzBenchmarks/dp-cdotp/main.c
```

目的：

- 将 Node 6 bring-up、可行性验证和默认验收规模收敛为 `M <= 1024`，优先
  `M128`，不得再用 `M4096` 这类大数据作为可行性验证。
- 把 CFMA A/B 默认目标从 `M4096` 改为 `M1024`，保留 `M128` 作为最小
  bring-up 目标。
- 新增 `dp-cdotp_scalar_M128` 诊断目标，复用 `M128` 数据、DMA、barrier、
  `result` 写回和最终 correctness check，但绕开 `cdotp_v64b` 的 RVV/fused
  计算序列。
- 记录当前 blocker 收敛结论：非 fused scalar 诊断通过，old/new vector/fused
  `M128` 路径仍 timeout。

验证命令：

```text
cd hw/system/spatz_cluster/sw/build && ctest -N -R "dp-cdotp_(old|vfcmacc|scalar)_M(128|1024)$":
PASS，退出码 0；列出 5 个小规模目标。
cd hw/system/spatz_cluster/sw/build && timeout 120s ctest -V -R "dp-cdotp_scalar_M128$":
PASS，退出码 0；串口输出 `Verification: SUCCESS`，用时约 17.27 秒。
git diff --check: 提交前运行并记录。
```

结果摘要：

```text
`dp-cdotp_scalar_M128` 通过，说明 `M128` 数据、分块 DMA、barrier、
`result` 写回和最终 correctness check 主流程可收敛。`dp-cdotp_old_M128`
与 `dp-cdotp_vfcmacc_M128` 仍在小规模 timeout，无 benchmark 串口输出。
剩余 blocker 继续聚焦在 `cdotp_v64b` 的向量/fused 计算序列、其 result
写回前后交互，或 timeout trace 截断边界。
```

实际提交：

```text
b7ddd6ff00e0e7df59ab14857909f9e6ec3d16ae
```

遗留风险：

```text
尚未取得 `M <= 1024` old/new correctness 或 cycles，不得声称 benchmark
speedup。后续调试必须继续使用 `M128` 或最多 `M1024`，禁止用 `M4096`
作为可行性验证。
工作树中仍存在未 stage 的本地生成差异
`hw/system/spatz_cluster/src/generated/testharness.sv` 与
`hw/system/spatz_cluster/test/bootrom.elf`，本记录不提交这些产物。
```

补充记录：

```text
日期：2026-06-10
计划提交：[cfma] Extend dp-cdotp M128 runtime diagnostics
修改范围：
M  docs/complex-instruction-extension/GIT_NOTES.md
M  docs/complex-instruction-extension/PHASE_RESULTS.md
M  sw/spatzBenchmarks/CMakeLists.txt
M  sw/spatzBenchmarks/dp-cdotp/kernel/cdotp.c
M  sw/spatzBenchmarks/dp-cdotp/main.c
```

目的：

- 继续遵守小规模验证约束：可行性验证只用 `M128`，上限不超过 `M1024`，不使用
  `M4096`。
- 新增 `dp-cdotp_vec_*_M128` 分阶段诊断目标，把 `cdotp_v64b` 的 load、MAC、
  reduction、vector-to-FPR extract、collect、summary 和 print 边界拆开。
- 新增 `singlecore` 与 `direct_singlecore` 诊断目标，验证单核执行和直接赋值能否
  避开当前 timeout。

验证结果：

```text
通过：
- dp-cdotp_vec_load_M128
- dp-cdotp_vec_mac_M128
- dp-cdotp_vec_reduce_real_M128
- dp-cdotp_vec_reduce_imag_M128
- dp-cdotp_vec_reduce_noextract_M128
- dp-cdotp_vec_extract_nocollect_M128，约 1.90 秒
- dp-cdotp_vec_extract_nosummary_M128，约 1.87 秒

失败或超时：
- timeout 120s ctest -V -R "dp-cdotp_vec_extract_drop_M128$"：退出码 124
- timeout 120s ctest -V -R "dp-cdotp_vec_extract_noprint_M128$"：退出码 124
- timeout 120s ctest -V -R "dp-cdotp_old_singlecore_M128$"：退出码 124
- timeout 120s ctest -V -R "dp-cdotp_old_direct_singlecore_M128$"：退出码 124
```

当前结论：

```text
`M128` 数据、DMA、barrier、`result` 写回和 scalar-only correctness 主流程可收敛。
两次 `vfredusum.vs` 本身可以 retire；两次 `vfredusum.vs` 加两次 `vfmv.f.s`
也可以在跳过 collect/summary 时退出。最新 blocker 收敛到两次 vector-to-FPR
抽取之后进入 hart0 `result[]` 标量 `fld/fadd/fsd` 汇总或等价标量 FPU 收尾路径。

`SPATZ_CDOTP_SINGLE_CORE` 和 `SPATZ_CDOTP_DIRECT_ACC_ASSIGN` 均未解除 timeout，
不得把单核或 direct assign 作为修复结论，也不得声称 old/new benchmark 已修复。
```

遗留风险：

```text
本补充记录仍只是诊断节点。尚未取得 old/new `M128` correctness 或 cycles；
后续应继续在 `M128` 或更小目标上构造最小复现，优先隔离 `vfmv.f.s` 之后的
scalar FPU `fld/fadd/fsd` 状态交互。
```

远端 Git 操作：

```text
暂无。
```

补充记录二：

```text
日期：2026-06-10
计划提交：[cfma] Tighten dp-cdotp M128 failure diagnostics
修改范围：
M  sw/cmake/SnitchUtilities.cmake
M  sw/spatzBenchmarks/CMakeLists.txt
M  sw/spatzBenchmarks/dp-cdotp/kernel/cdotp.c
M  docs/complex-instruction-extension/PHASE_RESULTS.md
M  docs/complex-instruction-extension/GIT_NOTES.md
```

目的：

- 记录并执行用户新增约束：可行性验证禁止使用 `M4096` 等大数据，允许上限为
  `M1024`；本轮实际只运行 `M128`。
- 保留 `vec_store_scalar_M128` 证据，并新增 `vec_store_scalar_m1_M128` 诊断，
  验证 `vse64.v` 从 reduction result 取 scalar 时切换 `LMUL=m1` 是否改变结果。
- 将普通路径恢复为原始 `vfmv.f.s` 收尾，避免提交会导致新 timeout 的
  “store all lanes + scalar sum” 临时实验。
- 修复 CTest 对 RTL 串口失败的误判，新增 `FAILED` 和 `Error:` 失败匹配。

验证记录：

```text
cmake -S hw/system/spatz_cluster/sw -B hw/system/spatz_cluster/sw/build:
PASS，退出码 0；新目标 `dp-cdotp_vec_store_scalar_m1_M128` 已加入。

cmake --build hw/system/spatz_cluster/sw/build --target
test-spatzBenchmarks-dp-cdotp_vec_store_scalar_m1_M128 &&
cd hw/system/spatz_cluster/sw/build &&
timeout 60s ctest -V -R "dp-cdotp_vec_store_scalar_m1_M128$":
旧验证配置下退出码 0，但串口明确输出 `Error:` 和 `*** FAILED ***`。
结果为 `(13.568879, 0.000000)`，Golden 为 `(30.655098, 14.343171)`。
本条作为 CTest 误判证据；随后已把该诊断目标改回 `SPATZ_CDOTP_SKIP_VERIFY=1`。

git diff --check:
PASS，退出码 0。

cmake --build hw/system/spatz_cluster/sw/build --target
test-spatzBenchmarks-dp-cdotp_scalar_M128
test-spatzBenchmarks-dp-cdotp_vec_store_scalar_M128
test-spatzBenchmarks-dp-cdotp_vec_store_scalar_m1_M128:
PASS，退出码 0。

cd hw/system/spatz_cluster/sw/build &&
timeout 90s ctest -V -R
"dp-cdotp_(scalar|vec_store_scalar|vec_store_scalar_m1)_M128$":
PASS，退出码 0；3/3 通过。`dp-cdotp_scalar_M128` 串口输出
`Verification: SUCCESS`；两个 store 诊断目标跳过 verify，仅用于证明
runtime 边界可退出。
```

遗留风险：

```text
尚未解决 `dp-cdotp_old_M128` / `dp-cdotp_vfcmacc_M128` runtime/correctness。
`vec_store_scalar` 解除 timeout 但不证明数值正确；`vec_store_scalar_m1` 排除了
简单 LMUL 切换修复。后续验证仍必须限制在 `M128` 或至多 `M1024`。
```

## 网络相关 Git 操作记录

如果后续执行依赖网络的 Git 操作失败，在这里记录即可。该工程不要求把修复网络
配置作为阶段任务。

记录模板：

```text
日期：
命令：
结果：
错误摘要：
后续处理：
```

当前记录：

```text
暂无。
```

## 文档重构：同步当前状态和长时间编译规则

日期：2026-07-06

本轮分支和状态：

```text
## feature/cfma-instruction-extension
 M docs/complex-instruction-extension/GIT_NOTES.md
 M docs/complex-instruction-extension/PHASE_RESULTS.md
 M docs/complex-instruction-extension/RESUME_INFO.md
 M docs/complex-instruction-extension/complex_fma_hardware_design.md
 M hw/ip/spatz/src/spatz_vfu.sv
```

计划提交名：

```text
[cfma] Refresh complex instruction extension docs
```

修改范围：

```text
M docs/complex-instruction-extension/README.md
M docs/complex-instruction-extension/RESUME_INFO.md
M docs/complex-instruction-extension/PLAN.md
M docs/complex-instruction-extension/complex_fma_hardware_design.md
M docs/complex-instruction-extension/PHASE_RESULTS.md
M docs/complex-instruction-extension/GIT_NOTES.md
D docs/complex-instruction-extension/FINAL_STATUS.md
D docs/complex-instruction-extension/SESSION_SUMMARY.md
D docs/complex-instruction-extension/PROGRESS_REPORT.md
D docs/complex-instruction-extension/step10_15_summary.md
D docs/complex-instruction-extension/step9_verification_report.md
```

内容摘要：

```text
- 将 README 改为当前文档导航入口。
- 重写 RESUME_INFO，记录最新提交 0de3f7f、Step 11 已完成、Step 12 有未提交写回草稿。
- 删除重复且容易过期的历史状态报告，保留 `RESUME_INFO.md` 和 `PHASE_RESULTS.md` 作为当前状态入口。
- 在 PLAN 和 complex_fma_hardware_design 中加入长时间编译验证许可和记录要求。
- 明确本轮不验证当前 RTL 草稿，不得声明 Step 12 已完成。
```

验证记录：

```text
git diff --check: PASS，退出码 0。

rg -n "当前任务\*\*: 步骤 11|下次会话中继续步骤 11|最后 Commit\*\*: bb47b77|建议\*\*: 在下次会话中继续步骤 11|立即行动（步骤 11）|⏳ \*\*实现 VRF 读取逻辑\*\*" docs/complex-instruction-extension/README.md docs/complex-instruction-extension/RESUME_INFO.md docs/complex-instruction-extension/PHASE_RESULTS.md docs/complex-instruction-extension/GIT_NOTES.md:
PASS，无匹配结果。

未运行 `make -C hw/system/spatz_cluster bin/spatz_cluster.vlt`，因为本轮提交范围是文档重构；当前未提交 RTL 草稿仍需后续单独编译验证。
```

实际提交：

```text
提交后由 `git log -1 --oneline` 确认。
```

补充：删除过期状态报告

```text
日期：2026-07-06
目的：按当前状态精简 docs，删除重复、过期且容易误导的状态总结文件。
删除：
- docs/complex-instruction-extension/FINAL_STATUS.md
- docs/complex-instruction-extension/SESSION_SUMMARY.md
- docs/complex-instruction-extension/PROGRESS_REPORT.md
- docs/complex-instruction-extension/step10_15_summary.md
- docs/complex-instruction-extension/step9_verification_report.md
保留：README、RESUME_INFO、PLAN、complex_fma_hardware_design、PHASE_RESULTS、GIT_NOTES 和设计支撑资料。

验证：
- git diff --check: PASS，退出码 0。
- 已检查当前 docs 中没有指向已删除文件的 Markdown 链接或恢复命令。
- 已检查当前状态入口不再包含 “当前任务是步骤 11” 等过期指引；GIT_NOTES 中保留的旧检查命令属于审计记录。
```

## Step 12 回归审查和验证记录

日期：2026-07-06

本轮分支和状态：

```text
## feature/cfma-instruction-extension
 M hw/ip/spatz/src/spatz_vfu.sv
```

计划提交名：

```text
[cfma] Guard incomplete dedicated CFMA writeback path
```

修改范围：

```text
M hw/ip/spatz/src/spatz_vfu.sv
M docs/complex-instruction-extension/RESUME_INFO.md
M docs/complex-instruction-extension/complex_fma_hardware_design.md
M docs/complex-instruction-extension/PHASE_RESULTS.md
M docs/complex-instruction-extension/GIT_NOTES.md
```

内容摘要：

```text
- Step 12 split VRF write-back 草稿保留在 RTL 中，但通过
  CfmaDedicatedWritebackEn = 1'b0 默认禁用。
- 默认功能路径恢复为已验证的四阶段 FPU CFMA 路径。
- 记录 dedicated hardware path 尚未满足动态 FP format、packed e16/e32 lane、
  complex arithmetic/status flags、mask/tail byte enable 和 response timing 要求。
- Step 12 不标记完成；下一步转入 Step 13 架构决策。
```

验证记录：

```text
git diff --check:
PASS，退出码 0。

PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt:
PASS，退出码 0。执行 fresh Verilator build；输出包含既有 Bender `description`
字段告警和 Verilator LATCH warnings；最终 Verilator report 显示 Walltime
124.447 s，并生成 `bin/spatz_cluster.vlt`。

PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt:
PASS，退出码 0。命令重建 `hw/system/spatz_cluster/sw/build`，CMake 重新加入
`vfcmacc_illegal`、`vfcmacc` 等 ISA/RTL 软件测试目标，并完成软件目标编译。
输出包含既有 runtime/benchmark warnings 和 DWARF address range diagnostic。

cd hw/system/spatz_cluster/sw/build &&
PATH="$PWD/.venv/bin:$PATH" ctest -R
'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure:
PASS，退出码 0。3/3 tests passed；总用时 162.86 s。
vfmacc 22.11 s，vfcmacc 118.53 s，vfnmsac 22.22 s。
```

遗留风险：

```text
专用 CFMA 硬件路径仍不可作为默认实现启用；不能声称 dedicated hardware
correctness、benchmark correctness 或 speedup。Step 13 必须先决定保留 v1
四阶段路径，或补齐并重新验证完整 dedicated path。
```
