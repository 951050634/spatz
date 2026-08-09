# P6 cluster STOP evidence

This directory preserves the smallest reviewable evidence set from the final
`work-p6b` attempt.  It is diagnostic evidence only: cluster PPA is
unavailable and no synthesis should be rerun from this directory.

`cluster_bb.f` is the exact Bender file-list capture.  It contains absolute
host paths from `/home/wxt/work-online-merge-supplement` and is intentionally
documented as host-path-specific rather than a portable build input.

The elaboration capture (`elab_bb3.ys`, `elab_bb3.log`, `elab-stat.json`) shows
full SV elaboration PASS.  The synthesis script/time capture is under
`synth-c1/`; it reaches proc/opt/memory_collect and then flatten, where the
attempt exits 137.  `flatten_oom_evidence.txt` records the relevant sequence,
hashes, and the SHA-256 of the omitted raw 108 MB log.
