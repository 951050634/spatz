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
