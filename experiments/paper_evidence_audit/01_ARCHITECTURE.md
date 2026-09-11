# Final Architecture Audit

## Frozen architectural position

**Proposed Design = Mixed-Precision Scalar SMU + existing RVV.** Full SMU / A2
仅用于消融。该定位由 `experiments/reports/P1_final_architecture_note.md`、Phase 7
`formal/instruction_manifest.json` 以及 Phase 8B implementation summary 一致支持。

## Platform

| Element | Frozen fact | Primary source |
|---|---|---|
| Scalar core | Snitch integer core | `hw/ip/spatz_cc/src/spatz_cc.sv` |
| Vector processor | Spatz vector unit attached to the core complex | `hw/ip/spatz_cc/src/spatz_cc.sv` |
| Cluster | `spatz_cluster`; default config has one DMA core and one compute core | `hw/system/spatz_cluster/cfg/spatz_cluster.default.dram.hjson` |
| Vector configuration | VLEN 512; 4 FPUs, 1 IPU, 4 ports in the default config | same HJSON |
| TCDM | base `0x00100000`, 128 KiB (`131072` B), 16 banks | same HJSON; `experiments/PROJECT_STATE.md` |
| SMU top | `online_merge_update_engine` | `experiments/PROJECT_STATE.md` |
| Cluster top | `spatz_cluster` | `experiments/PROJECT_STATE.md` |
| Integration | SMU requester joins the TCDM interconnect; one cluster issue arbiter records the owner and demultiplexes the asynchronous response | `hw/system/spatz_cluster/src/spatz_cluster.sv` |
| Core issue path | Snitch decode → `spatz_cc` accelerator demux → cluster arbiter → OMERGE adapter/SMU → owner-routed response | `hw/ip/snitch/src/snitch.sv`; `hw/ip/spatz_cc/src/spatz_cc.sv`; cluster RTL |

The default memory map also gives boot address `0x1000` and a 64 KiB cluster
peripheral region. These are platform facts, not performance claims.

## HW/SW partition

```text
state-dependent Online Merge recurrence
  m_new = max(m_old, m_tile)
  l_new = l_old*exp(m_old-m_new) + l_tile*exp(m_tile-m_new)
  old_weight, tile_weight
→ Scalar SMU

regular O[D] output update
  O_new[j] = old_weight*O_old[j] + tile_weight*O_tile[j]
→ existing RVV
```

The SMU scalar path reads/writes `m`, `l`, and the two weights through TCDM.
Software/RVV retains the dimension-dependent output loop. This avoids duplicating
the established vector machinery inside the accelerator.

### Explicitly unchanged

- Spatz RVV datapath;
- vector lanes and FPUs;
- vector register file (VRF);
- standard RVV semantics and instruction set behavior;
- mixed SMU arithmetic between the matched MMIO and OMERGE paths;
- RVV output-update routine between the compared paths.

The Phase 8B change adds configuration transport and shared-register write enables;
it does not create a second configuration bank or alter SMU arithmetic.

## Native Online Attention execution sequence

The implemented sequence in `sw/spatzBenchmarks/native-online-attention/main.c` is:

```text
Q/K/V and buffers prepared outside Native Core timer
→ workload-persistent SMU context configured and INIT committed
→ compute score tile
→ build tile-local (m_tile, l_tile, O_tile)
→ if first tile: copy tile state into running state; no OMERGE
→ otherwise: OMERGE
     adapter selects A/B source/destination
     SMU reads running and tile m/l through TCDM
     SMU computes recurrence and stores new m/l + two weights through TCDM
     completion/status returns to issuing scalar core
→ existing RVV reads weights and O buffers and performs O[D] update
→ software swaps running O pointers (and the legacy-visible m/l pointers)
→ hardware selector has toggled after successful accepted response
→ next tile
```

Tile size is four keys in all Phase 5–8 formal native runs. Thus N8 has two tiles
and one merge; N16 has four tiles and three merges. There is no final normalization
pass because each `O` state is normalized at every merge.

## Persistent configuration boundary

OMCFG/OMERGE v1 configures nine scalar-context fields: physical A/B `m/l` buffer
addresses, tile `m/l` addresses, two weight destinations, and N. The adapter fixes
Mixed Scalar mode 3, engine D=1, stride=0, and unused accelerator O addresses to
zero. Workload D and all `O[D]` addressing remain software/RVV concerns.

“Persistent” means that the context is established once per workload and then
consumed by every OMERGE. Writing any required field makes the context dirty until
a successful INIT. It does not mean that the hardware autonomously advances tile
addresses; the benchmark reuses fixed tile buffers.

## Ping-pong state and selector contract

| Property | Frozen behavior | Source |
|---|---|---|
| Physical state | A=`A_M/A_L`; B=`B_M/B_L` | adapter RTL; Phase 8 cfg mapping |
| Initial selector | `0` after reset; successful complete INIT also sets `0` | `online_merge_omerge_adapter.sv` |
| Selector 0 | A is source, B destination | same |
| Selector 1 | B is source, A destination | same |
| Toggle | only when a successful response is accepted by the core | same |
| Invalid/incomplete context | response status nonzero; engine is not started; no toggle | same; Phase 8B directed test |
| Engine error | nonzero response; no successful toggle | same |
| First tile | software initializes running A/O state; no OMERGE and no toggle | native benchmark |
| N8 trace | `0→1` / A→B | Phase 7 selector audit; Phase 8C manifest |
| N16 trace | `0→1→0→1` / A→B→A→B | same |

OMERGE success is status `0`; error is nonzero (bit 0 in the adapter response).
Completion is asynchronous at the accelerator interface but architecturally
consumed before the instruction returns its status. OMCFG itself is an accepted
configuration write and has no response/writeback result.

## Evidence boundary

The architecture above is supported by current RTL plus frozen Phase 7/8 reports.
`paper/online-merge-smu/main.tex` predates OMERGE/OMCFG and describes a legacy MMIO
and older precision story. It is retained as provenance but is **STALE for the final
architecture** and must not override this audit.
