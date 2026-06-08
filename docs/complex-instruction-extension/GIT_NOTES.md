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
