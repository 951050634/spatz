# work-online-merge 运行产物归档

本目录集中存放 online-softmax-merge 实验各批次的**运行产物**（artifact-root 输出）。
源码仓库与活跃工作区见下方说明。

| 目录 | 大小 | 套件 | run_id | 提交 | 开始(UTC) | 结束(UTC) | 说明 |
|---|---|---|---|---|---|---|---|
| work-online-merge-m1-matched-lut-20260810 | 53M | m1-matched-lut | 20260809T211249Z_05547a1b | 05547a1b | 2026-08-09 21:12 | 2026-08-09 21:28 | 已完结 |
| work-online-merge-m2-7225d41-models | 361M | m2-matched-lut-models | 20260810T061231Z_7225d41a | 7225d41a | 2026-08-10 06:12 | — | 疑为被 complete 取代的早期运行 |
| work-online-merge-m2-7225d41-scaling | 1.1G | m2-matched-lut-scaling | 20260809T214129Z_7225d41a | 7225d41a | 2026-08-09 21:41 | 2026-08-10 06:10 | 已完结 |
| work-online-merge-m2-complete-7225d41-models | 681M | m2-matched-lut-models | 20260810T110532Z_7225d41a | 7225d41a | 2026-08-10 11:05 | — | "complete" 版（含 run.log） |

> 注：`m2-7225d41-models` 与 `m2-complete-7225d41-models` 是同一套件（models）的两次运行，
> 后者为完整版，前者如需节省空间可考虑删除（已确认无脚本引用）。

## 相关位置
- 源码工作树：`/home/wxt/work-online-merge-supplement`（spatz 仓库的 git worktree，保留原位置）
- 当前活跃工作区：`/home/wxt/m1-matched-lut.7wqexi`（repo/ + artifacts/）
- 各运行明细见各目录内 `run_manifest.json` / `records.json`
