# CFMA v1 Git 记录摘要

本文件是 v1 归档后的 Git 记录摘要，不再保留完整逐行会话日志。若需要完整历史，请使用 `git log --stat`、`git show <commit>` 查看仓库历史。

## 1. 关键分支

| 分支 | 作用 |
| --- | --- |
| `feature/cfma-instruction-extension` | v1 四阶段 FPU 复用实现与归档 |
| `feature/cfma-v2-datapath` | v2 dedicated datapath 规划与后续开发 |

## 2. v1 关键提交

| 提交 | 说明 |
| --- | --- |
| `7be9e6a` | 刷新和精简复数指令扩展文档 |
| `7b5366b` | guard 未完成的 dedicated CFMA writeback path |
| `52352e8` | 补齐 v1 收尾文档和验证证据 |
| `d539c2c` | 将 v1 文档归档到 `docs/v1/`，删除 `docs/superpowers/` |

## 3. v2 起点提交

| 提交 | 说明 |
| --- | --- |
| `92308de` | 新建 `docs/v2/README.md`，记录 dedicated datapath 规划 |

## 4. v1 验证摘要

2026-07-06 记录：

```text
git diff --check: PASS
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt: PASS
make -C hw/system/spatz_cluster sw.vlt: PASS
ctest riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac): PASS, 3/3
```

benchmark probe：

```text
dp-caxpy_M256: PASS
dp-caxpy_vfcmacc_M256: PASS
dp-cdotp_old_M128: >17 min 未完成
dp-cdotp_vfcmacc_M128: 未执行到
```

## 5. 归档后的 Git 使用建议

查看 v1 最新归档：

```bash
git checkout feature/cfma-instruction-extension
```

查看 v2 工作：

```bash
git checkout feature/cfma-v2-datapath
```

查看最近历史：

```bash
git log --oneline --decorate -10
```
