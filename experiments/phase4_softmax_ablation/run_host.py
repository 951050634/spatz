#!/usr/bin/env python3
"""Generate deterministic host evidence for the Phase 4 softmax ablation."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.phase4_quantized_attention.attention_model import (
    SEED,
    jsonable,
    metrics,
    run_case,
    run_host_checkpoints,
    summarize,
)


ANCHORS = ((8, 32), (16, 64))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def collect(output_dir: Path, seed: int = SEED) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    vectors: list[dict[str, Any]] = []
    for n, d in ANCHORS:
        data = run_case(n, d, seed)
        run_host_checkpoints(data)
        summary = summarize(data)
        probability_pair = metrics(data["p_bq"], data["p_mixed"])
        output_pair = metrics(data["o_bq"], data["o_mixed"])
        rows.append(
            {
                "n": n,
                "d": d,
                "seed": seed,
                "software_backend": (
                    "host stable max-subtract + exp + normalization "
                    "reference"
                ),
                "mixed_backend": "Frozen Mixed-Precision SMU model",
                "probability_mae": probability_pair["mae"],
                "probability_cosine": probability_pair["cosine_similarity"],
                "output_mae": output_pair["mae"],
                "output_cosine": output_pair["cosine_similarity"],
                "software_probability_vs_ref_mae": summary["probability"][
                    "B-Q_vs_REF"
                ]["mae"],
                "software_probability_vs_ref_cosine": summary["probability"][
                    "B-Q_vs_REF"
                ]["cosine_similarity"],
                "mixed_probability_vs_ref_mae": summary["probability"][
                    "P-QM_vs_REF"
                ]["mae"],
                "mixed_probability_vs_ref_cosine": summary["probability"][
                    "P-QM_vs_REF"
                ]["cosine_similarity"],
                "software_output_vs_ref_mae": summary["output"]["B-Q_vs_REF"][
                    "mae"
                ],
                "software_output_vs_ref_cosine": summary["output"]["B-Q_vs_REF"][
                    "cosine_similarity"
                ],
                "mixed_output_vs_ref_mae": summary["output"]["P-QM_vs_REF"][
                    "mae"
                ],
                "mixed_output_vs_ref_cosine": summary["output"]["P-QM_vs_REF"][
                    "cosine_similarity"
                ],
            }
        )
        vectors.append(
            {
                "n": n,
                "d": d,
                "seed": seed,
                "software_probability": jsonable(data["p_bq"]),
                "mixed_probability": jsonable(data["p_mixed"]),
                "software_output": jsonable(data["o_bq"]),
                "mixed_output": jsonable(data["o_mixed"]),
            }
        )
        summaries.append(summary)
    (output_dir / "host_results.json").write_text(
        json.dumps(
            {"seed": seed, "summaries": jsonable(summaries), "vectors": vectors},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_csv(output_dir / "numerical.csv", rows)
    return rows


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "results",
    )
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    if args.seed != SEED:
        raise SystemExit("Phase 4 anchors require deterministic seed=1")
    for row in collect(args.output_dir, args.seed):
        print(
            f"phase4-ablation-host N{row['n']}_D{row['d']} "
            f"probability_cosine={row['probability_cosine']:.9f} "
            f"output_cosine={row['output_cosine']:.9f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
