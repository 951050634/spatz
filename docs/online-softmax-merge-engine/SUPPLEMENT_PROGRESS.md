# Online Softmax Merge Engine Supplement Progress

This file is the small, version-controlled progress index for the experiments
specified by `需要补充的若干实验内容.md`.  Detailed raw artifacts must remain
outside Git under a `work-online-merge-*` directory and are referenced from
small manifests only.

## Fixed context

- Specification baseline: 2026-07-15
- Starting commit: `136da62cf3c8fed3ad7088b825661d71bd2b0b20`
- Working branch: `exp/online-softmax-supplement`
- Main CFG: `hw/system/spatz_cluster/cfg/spatz_cluster.default.dram.hjson`
- Main CFG SHA256:
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`
- Physical PPA/energy status: `blocked_external`
- Missing external inputs: target PDK, liberty/LEF, defined PVT/IO/clock
  constraints, and signoff synthesis/P&R/timing/power tools.
- Required next action for P2: provide the above inputs and a fixed physical
  flow; generic resources and RTL toggles must remain explicitly labelled as
  proxies.

## Stage index

| Order | Stage | Priority | Status | Checkpoint / evidence |
| ---: | --- | --- | --- | --- |
| 0 | Isolate worktree and import governing specification | setup | complete | this checkpoint |
| 1 | Compact buffers, unified timing/correctness, CSV/JSON, timeout runner | P0 | in_progress | pending |
| 2 | Fair B1/B2-R/B3 baselines and RVV disassembly gate | P0 | pending | pending |
| 3 | Anchors, RVV tails, mandatory size matrices | P0 | pending | pending |
| 4 | Break-even table and fitted scale model | P0 | pending | pending |
| 5 | Full-SMU FSM cycle breakdown and A0/A2 | P0 | pending | pending |
| 6 | C0/C1/C2/C3 concurrency and 16 bank phases | P0 | pending | pending |
| 7 | Yosys Slang generic-resource proxy | P0 | pending | pending |
| 8 | Representative RTL VCD toggle proxy | P0 | pending | pending |
| 9 | Target `expf` B0/B2-F | P1 | pending | pending |
| 10 | Scalar-only A1 | P1 | pending | pending |
| 11 | Trace gating / low-perturbation counter | P1 | pending | pending |
| 12 | Capacity probes and expanded numerical coverage | P1 | pending | pending |
| 13 | ASIC PPA and physical energy | P2 | blocked_external | see fixed context |

## Checkpoint log

### Setup checkpoint

- Objective: preserve unrelated user changes and establish an isolated,
  auditable experiment branch.
- Input: the untracked governing specification from the original worktree.
- Validation: `git status --short --branch`; inspect copied file and CFG hash.
- Result: dedicated worktree `/home/wxt/work-online-merge-supplement` on
  `exp/online-softmax-supplement`; no stash/reset/clean/overwrite was used.
- Known limitation: no experiment implementation or measurement is claimed by
  this checkpoint.
