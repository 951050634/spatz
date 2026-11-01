本阶段目标是量化和强化 Scalar SMU 加速器本身，而不是继续扩展实验基础设施。优先复用现有脚本、RTL 和结果格式。除非直接阻塞目标实验，否则不要进行大规模重构、兼容性封装、异常处理扩展、额外 runner gate 或防御性检查。每项任务应首先完成最短可工作的实现，然后直接生成论文需要的性能、面积、时序或结构数据。Proposed Design 固定为 Scalar SMU + RVV，Full SMU 仅用于消融比较，不继续作为主要架构开发方向。

# Repository Guidelines

## Project Structure & Module Organization

`hw/` holds the RTL and system integration code, with the main top-level cluster in `hw/system/spatz_cluster/`. `sw/` contains the software stack: `snRuntime/` for runtime support, `riscvTests/` for ISA-style tests, and `spatzBenchmarks/` for benchmark programs. Shared build helpers live in `util/`, while generated or local build outputs should stay under `sw/build/`, `hw/system/spatz_cluster/bin/`, or `work-*` directories.

## Build, Test, and Development Commands

Use the root `Makefile` to bootstrap the toolchain and generated sources:

- `make all` installs the pinned toolchain pieces and updates opcodes.
- `make init` is the lighter setup path for IIS-managed environments.
- `make -C hw/system/spatz_cluster help` lists simulator and software targets.
- `make -C hw/system/spatz_cluster bin/spatz_cluster.vlt` builds the Verilator system binary.
- `make -C hw/system/spatz_cluster sw.vlt` configures and builds the software against the Verilator simulator.
- `make -C hw/system/spatz_cluster sw.test.vlt` runs the software test suite through CTest.

## Coding Style & Naming Conventions

Follow the existing `.editorconfig`: 2-space indentation by default, 4 spaces for Python, tabs for Makefiles, LF line endings, and 80-column wrapping unless a file type overrides it. SystemVerilog files may use up to 100 columns. Keep names descriptive and local to the domain: hardware under `hw/ip/<block>/`, software tests under `sw/riscvTests/isa/`, and benchmark directories grouped by kernel and precision. Prefer the repository’s current naming patterns for generated artifacts and Make targets.

## Testing Guidelines

The software test flow is CMake- and CTest-based. Add new ISA tests in `sw/riscvTests/CMakeLists.txt` using the existing `add_snitch_test(...)` pattern, and run the relevant subset with `ctest -R <name>` from `sw/build/`. For simulator-integrated validation, use `sw.test.vlt`, `sw.test.vsim`, or `sw.test.vcs` from `hw/system/spatz_cluster/`.

## Commit & Pull Request Guidelines

Keep commits atomic, rebased, and free of merge commits. Subject lines should be imperative, capitalized, under 100 characters, and may start with a scoped tag like `[uart]`. Reference related issues in the commit body or PR description when relevant. Pull requests should include a clear summary, the validation you ran, and screenshots or waveforms when the change affects hardware behavior.

## Configuration Notes

Cluster configuration comes from `hw/system/spatz_cluster/cfg/*.hjson`. When changing simulator behavior, prefer passing `CFG=...` on the make command line rather than editing the default file in place.

# Research and Validation Guidelines

## 1. Evidence-Based Acceptance

只有在 evidence 足够支持结论时，才能将结果标记为：

- `PASS`
- `VERIFIED`
- `FROZEN`

如果证据不足，应明确标记：

- `BLOCKED`
- `LIMITATION`
- `DEFERRED`
- `NOT MEASURED`

不得通过猜测补全缺失实验。

## 2. Review Policy

是否需要再次 review，应根据：

- 修改的重要程度；
- 是否改变 architecture；
- 是否改变实验方法；
- 是否改变 baseline；
- 是否改变 measurement scope；
- 是否影响正式 paper claim；

进行判断。

对于很小且明确的修正，不需要为了流程本身增加额外 review。

对于 architecture、ISA、numerical semantics、正式 experiment methodology 或 paper evidence 的重要修改，应优先进行独立 review。

## 3. Scope Discipline

所有 agent 都必须严格控制 scope。

除非用户明确要求，否则：

- 不主动增加新 feature；
- 不主动扩大 ISA；
- 不主动增加新的 accelerator mode；
- 不主动扩大 workload sweep；
- 不主动增加新的 quantization scheme；
- 不主动修改与当前任务无关的 RTL；
- 不进行大规模无关 refactor；
- 不因为“顺便可以优化”而修改稳定模块；
- 不为了获得更好的实验数字而改变 baseline、tile、timing window 或 evaluation methodology；
- 不删除或隐藏负结果；
- 不把未测量结果补全为推测值。

发现潜在后续方向时，可以记录为：

- `SUGGESTION`
- `DEFERRED`

但不要自动实施。

## 4. Minimal-Change Principle

优先选择能够回答当前研究问题的最小修改。

不要把科研 prototype 自动工程化为 production-quality general-purpose system。

避免：

- 过度 defensive programming；
- 与实际失败模式无关的大量保护逻辑；
- 无关 abstraction；
- 无必要的 framework 重构；
- 为理论上的未来扩展提前加入复杂接口；
- 为未要求的 corner case 大规模修改现有架构。

如果现有实现已经满足任务目标，应优先保留现有结构。

## 5. Experiment and Evidence Discipline

正式实验必须明确区分：

- workload setup；
- recurring control；
- engine execution；
- recurrence；
- vector update；
- merge；
- larger kernel/core scope；
- end-to-end scope。

不得把局部 speedup 表述成更大 scope 的 speedup。

例如：

- recurrence speedup 只能称 recurrence speedup；
- merge speedup 只能称 merge speedup；
- Native Core speedup 只能称 Native Core speedup；
- 没有 full-attention 或 full-model measurement 时，不得声称 full-attention / model speedup。

如果不同实验来自不同 implementation epoch、simulator epoch 或 evidence family：

- 不得直接使用绝对 cycle 构造跨 epoch 的 progressive speedup；
- 只能使用各自 matched baseline/design pair；
- 必须保留 provenance。

## 6. Negative Results

负结果是有效研究证据。

如果实验得到：

- negligible improvement；
- slowdown；
- no systematic benefit；
- blocked synthesis；
- unsupported claim；

必须如实保留。

不得：

- 换 workload 寻找更好结果；
- 删除不利结果；
- 更换 measurement window；
- 修改 baseline；
- 修改实现以单纯“救性能”，除非用户明确批准新的研究任务。

## 7. Priority Classification

review 中的问题优先使用：

### P0

会导致结果错误、功能错误、实验无效或核心 claim 不成立的问题。

### P1

会显著影响 architecture correctness、methodology、公平比较、reproducibility 或 paper claim 的问题。

### P2

非关键优化、代码风格、可选重构、未来扩展等。

P0/P1 应优先解决。

P2 默认不应扩大当前任务 scope，除非用户明确要求。

## 8. User Authority

用户的当前明确指令始终优先于本仓库规范。

本文件用于规定默认工作方式，而不是替用户做研究方向决策。

当用户明确要求：

- 改变 scope；
- 跳过某次 review；
- 仅做 analysis；
- 仅做 implementation；
- 停止实验；
- 冻结当前结果；

应遵循用户当前指令。

不要根据本文件自动创造用户没有要求的新任务。
