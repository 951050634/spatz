# 新主机上的工程启动流程（2026-11-12 核对）

本文记录在全新主机上从 GitHub 恢复本仓库并启动工程的步骤。以下命令已在
一份全新克隆中逐条验证：克隆、`make init`、`make generate` 均可通过。
重型工具链（LLVM/GCC/Spike/Verilator）的构建耗时以小时计，本次未重跑，
但四个版本指针均已确认在对应仓库中可达。

## 1. 克隆

仓库为私有/需认证，HTTPS 无凭据时请用 SSH：

```bash
git clone git@github.com:951050634/spatz.git spatz
cd spatz
git fetch origin 'refs/salvage/*:refs/salvage/*'   # 见第 5 节
```

## 2. 恢复三个工作树

`spatz`、`spatz-cfma`、`work-online-merge-supplement` 是同一仓库的三个
worktree，克隆后重新挂载：

```bash
git worktree add ../spatz-cfma feature/cfma-v2-datapath
git worktree add ../work-online-merge-supplement exp/online-softmax-supplement
```

## 3. 工具链引导（关键：riscv-opcodes 指针已失效）

`sw/toolchain/riscv-opcodes.version` 指向 `e46a55a1`，该提交已不在
`pulp-platform/riscv-opcodes` 的任何分支上（上游重写了历史），
`make init` / `make all` 的 `git checkout` 会报
`fatal: reference is not a tree`。GitHub 允许按 SHA 取对象，先手动补齐：

```bash
mkdir -p sw/toolchain && cd sw/toolchain
git clone https://github.com/pulp-platform/riscv-opcodes.git
cd riscv-opcodes
git fetch origin "$(cat ../riscv-opcodes.version)"
git checkout FETCH_HEAD
cd ../..
```

目录存在后 make 会跳过克隆，其余三个指针（LLVM `b494f2d`、GNU 工具链
`70acebe`、isa-sim `c663ea2`、Verilator `v5.034`）均可正常检出不需处理。

```bash
make init     # bender 0.29.1 + 重新生成 opcodes（生成结果与仓库内文件一致）
make all      # LLVM / GCC / Spike / Verilator，耗时数小时
```

`make all` 需要访问 github.com（bender 依赖 ~9 个 pulp-platform 仓库）。
国内网络下请先确认代理可用。

## 4. 构建与回归

```bash
cd hw/system/spatz_cluster
make generate                  # RTL 生成
make bin/spatz_cluster.vlt     # Verilator 仿真器
make sw.vlt                    # 编译软件
bin/spatz_cluster.vlt <elf>
ctest -R <test> --test-dir sw/build
```

## 5. 远端保留的孤儿提交

2026-11-12 清理时发现 13 个只存在于 reflog 的提交（P0-4/P0-5/P0-6 证据、
cfma 早期版本、论文重建版等），已以 `refs/salvage/2026-11-12/<short>` 形式
推到远端。查看或恢复：

```bash
git fetch origin 'refs/salvage/*:refs/salvage/*'
git log --all --oneline --decorate | grep salvage
git branch rescue-salvage <-某个 refs/salvage/...>
```

## 6. 不在 git 中的内容

以下目录被 `.gitignore` 有意排除，必须另行搬运，克隆不会带走：

| 路径 | 大小 | 内容 |
|---|---|---|
| `work-online-merge-supplement/experiments/` | 1.1 G | 实验脚本、配置与结果 |
| `work-online-merge-supplement/archive/` | 18 G | 论文交付包、日志、旧工程 |
| `~/spatz-archive/toolchain-src/` | 17 G | 独立目录，无版本控制 |

各工作树的 `build/`、`bin/`、`work-*/`、`install/`、`.bender/` 均为可重建产物，
无需迁移。
