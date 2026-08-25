#!/usr/bin/env python3
"""Run the two bounded Phase 4 host anchors and write paper-facing artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from attention_model import (
    SEED,
    jsonable,
    run_case,
    run_host_checkpoints,
    summarize,
)
from generate_case import generate_header


ANCHORS = ((8, 32), (16, 64))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def collect(output_dir: Path, seed: int) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    scale_rows: list[dict[str, Any]] = []
    linear_rows: list[dict[str, Any]] = []
    numerical_rows: list[dict[str, Any]] = []
    fusion_rows: list[dict[str, Any]] = []
    for n, d in ANCHORS:
        data = run_case(n, d, seed)
        run_host_checkpoints(data)
        summary = summarize(data)
        summaries.append(summary)
        scales = summary["scales"]
        scale_rows.append({"n": n, "d": d, "seed": seed, **scales})
        for name, values in summary["linear"].items():
            linear_rows.append({"n": n, "d": d, "stage": name, **values})
        fusion_rows.append(
            {
                "n": n,
                "d": d,
                "checkpoint": "fused_score_vs_staged_dequant",
                **summary["score"]["fused_vs_staged"],
            }
        )
        for baseline in ("REF", "B-Q", "P-QM"):
            if baseline == "REF":
                score = {"mae": 0.0, "stable_relative_error": 0.0, "cosine_similarity": 1.0}
                probability = score
                output = score
            elif baseline == "B-Q":
                score = summary["score"]["quantized_vs_fp32"]
                probability = summary["probability"]["B-Q_vs_REF"]
                output = summary["output"]["B-Q_vs_REF"]
            else:
                score = summary["score"]["quantized_vs_fp32"]
                probability = summary["probability"]["P-QM_vs_REF"]
                output = summary["output"]["P-QM_vs_REF"]
            numerical_rows.append(
                {
                    "n": n,
                    "d": d,
                    "seed": seed,
                    "baseline": baseline,
                    "score_mae": score["mae"],
                    "score_stable_relative_error": score["stable_relative_error"],
                    "score_cosine": score["cosine_similarity"],
                    "probability_mae": probability["mae"],
                    "probability_stable_relative_error": probability["stable_relative_error"],
                    "probability_cosine": probability["cosine_similarity"],
                    "output_mae": output["mae"],
                    "output_stable_relative_error": output["stable_relative_error"],
                    "output_cosine": output["cosine_similarity"],
                }
            )
        header_path = output_dir / f"phase4_case_N{n}_D{d}_S{seed}.h"
        header_path.write_text(generate_header(n, d, seed), encoding="utf-8")
    (output_dir / "host_results.json").write_text(
        json.dumps(jsonable(summaries), indent=2) + "\n", encoding="utf-8"
    )
    write_csv(output_dir / "scales.csv", scale_rows)
    write_csv(output_dir / "linear.csv", linear_rows)
    write_csv(output_dir / "numerical.csv", numerical_rows)
    write_csv(output_dir / "fused_score.csv", fusion_rows)
    return summaries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "results")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    summaries = collect(args.output_dir, args.seed)
    for summary in summaries:
        output = summary["output"]["P-QM_vs_REF"]
        print(
            f"phase4-host N={summary['n']} D={summary['d']} seed={summary['seed']} "
            f"output_cosine={output['cosine_similarity']:.9f} "
            f"output_stable_rel={output['stable_relative_error']:.6g}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
