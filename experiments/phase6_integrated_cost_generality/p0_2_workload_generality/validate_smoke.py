#!/usr/bin/env python3
"""Validate exact output coverage and numerical agreement in Gate 1 logs."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
LOG_ROOT = Path(__file__).resolve().parent / "logs"
PHASE5_COLLECTOR = ROOT / "experiments/phase5_native_online_attention/collect_formal.py"
CASES = ((16, 128), (24, 64))


def load_phase5_collector():
    spec = importlib.util.spec_from_file_location("phase5_collect_formal", PHASE5_COLLECTOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen Phase 5 collector")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    collector = load_phase5_collector()
    lines = [f"STARTED_AT {datetime.now(timezone.utc).isoformat()}"]
    for n, d in CASES:
        slug = f"N{n}_D{d}_S1"
        paths = {
            implementation: LOG_ROOT / f"{slug}_{implementation}.log"
            for implementation in ("software", "smu")
        }
        outputs = {}
        for implementation, path in paths.items():
            result_records = collector.parse_prefixed_json(path, "PHASE5_RESULT ")
            fsm_records = collector.parse_prefixed_json(path, "OM_FSM ")
            if len(result_records) != 1:
                raise RuntimeError(f"missing unique result in {path}")
            n_out, d_out, bits = collector.parse_output_bits(path)
            if (n_out, d_out) != (n, d):
                raise RuntimeError(f"shape mismatch in {path}")
            collector.validate_run(result_records[0], fsm_records,
                                   implementation, n, d, bits)
            outputs[implementation] = bits
            smu = result_records[0]["smu"]
            lines.append(
                f"RUN {slug} {implementation} status={result_records[0]['status']} "
                f"bits={len(bits)} output_nonfinite={result_records[0]['output_nonfinite']} "
                f"smu_done={smu['done']} smu_errors={smu['errors']} "
                f"smu_timeouts={smu['timeouts']}"
            )
        metrics = collector.pairwise_metrics(outputs["software"], outputs["smu"])
        lines.append(
            f"METRICS {slug} output_mae={metrics['output_mae']:.17g} "
            f"stable_relative_error={metrics['stable_relative_error']:.17g} "
            f"cosine_similarity={metrics['cosine_similarity']:.17g}"
        )
    lines.append(f"COMPLETED_AT {datetime.now(timezone.utc).isoformat()}")
    output = LOG_ROOT / "smoke_numerical_check.log"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Gate 1 smoke numerical check PASS: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
