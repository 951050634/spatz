# Updated experiment results

Validated configurations: **9 total**, including **8 of the 10 requested sweep configurations** and the extra N8/D32 baseline. Two original shapes remain capacity-BLOCKED. There are no unresolved Native simulation or timing failures.

N24/D64/B4 and N16/D128/B4 previously used pre-fix ELF files without the dependent ADD despite the source having been updated. Both were explicitly recompiled from the existing 9b8adb6b source and executed again. stdbuf line buffering changes host logging only. The matched software ELF images and inputs are unchanged, so their existing measurements remain valid; the prior PT_LOAD equivalence evidence is retained.

N32/D64/B4 returned zero and printed SUCCESS, seven successful commands and a complete output dump. Its PHASE5_RESULT began inside a buffered OM_FSM line. Exact JSON records and the split hardware record were recovered into a separately marked derived log, without modifying the raw source or cycle values. See N32_D64_B4-recovery.json and raw_log_sha256.

| N | D | B | Recurrence speedup | Merge speedup | Core speedup incl. setup |
|---:|---:|---:|---:|---:|---:|
|8|32|4|51.971|11.953|1.1896|
|8|64|4|52.245|8.258|1.0869|
|16|32|4|52.637|12.084|1.2383|
|16|64|4|52.454|8.182|1.1327|
|16|128|4|51.539|5.144|1.0698|
|24|64|4|51.614|8.245|1.1475|
|32|64|4|51.770|8.213|1.1526|
|32|64|8|52.031|7.876|1.0679|
|32|64|16|52.658|7.965|1.0238|

## Baseline 52x recurrence verification

| N/D | SW recurrence | ISA recurrence | engine busy | recurring control | once setup | raw speedup | speedup incl. setup |
|---|---:|---:|---:|---:|---:|---:|---:|
|8/32|12369|238|208|30|664|51.9706|13.7129|
|16/64|68610|1308|1248|60|636|52.4541|35.2932|

The roughly 52x figures include complete engine execution and returned-status consumption. They exclude once-only OMCFG/INIT, as do the original raw window definitions. Additive setup-inclusive metrics charge that cost and do not represent a newly measured contiguous interval. Neither number is an end-to-end/full-model speedup.

## Scaling interpretation

Scalar engine work is N*(N/B-1) row recurrences, and OMERGE count is N/B-1. Vector work is N*D*(N/B-1); the retained AVL cap of eight requires ceil(D/8) vector groups per row. Increasing D leaves scalar row work fixed while growing vector work and Q/K dot products, reducing Core speedup. Increasing square N grows row count and tile count together, while score/local work grows approximately with N^2*D. Larger B reduces merges and RVV updates, reducing the share of work that scalar recurrence acceleration can save. All measured common-stage differences are retained.

The existing D sets both dk and dv; this is a joint head/output dimension sweep. Nq and Nk also increase together. These data do not isolate dv at fixed dk or query count at fixed Nk.

ISA/MMIO pairs have word-for-word identical outputs. Software and Scalar SMU intentionally use different recurrence precision; their MAE/relative error/cosine metrics are reported without inventing an additional acceptance threshold. All formal outputs are finite, target execution passes, complete output digests agree, and all ISA handshake/static timing checks pass.

Full SMU remains an independent, matched **MMIO vs MMIO** ablation; it is not part of the formal ISA-controlled comparison. See full_smu_bottleneck.md.
