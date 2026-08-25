#!/usr/bin/env python3
"""Small host model for the Phase 4 quantized attention path.

This module deliberately keeps the experiment self contained.  The frozen
Mixed SMU carrier, exp LUT and reciprocal LUT are imported from the Phase 1
model; no new softmax approximation is introduced here.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PHASE1 = ROOT / "experiments" / "phase1_online_softmax"
if str(PHASE1) not in sys.path:
    sys.path.insert(0, str(PHASE1))
import run_validation as phase1  # noqa: E402


SEED = 1
LUT_ENTRIES = 256
LUT_Q_BITS = 14
RECIP_ENTRIES = 256
RECIP_Q_BITS = 15
MODEL_MIXED = phase1.MODEL_MIXED_RTL_RECIPROCAL


def f32(value: Any) -> np.float32:
    return np.float32(value)


class XorShift32:
    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFF
        if self.state == 0:
            self.state = 0x6D2B79F5

    def next_u32(self) -> int:
        value = self.state
        value ^= (value << 13) & 0xFFFFFFFF
        value ^= value >> 17
        value ^= (value << 5) & 0xFFFFFFFF
        self.state = value & 0xFFFFFFFF
        return self.state

    def unit(self) -> float:
        return float(self.next_u32() >> 8) / float(1 << 24)

    def uniform(self, low: float, high: float) -> np.float32:
        return f32(low + (high - low) * self.unit())


def make_case(n: int, d: int, seed: int = SEED) -> dict[str, np.ndarray | float | int]:
    """Create deterministic, bounded X and static FP32 weight tensors."""

    rng = XorShift32(seed)
    x = np.asarray(
        [rng.uniform(-0.5, 0.5) for _ in range(n * d)], dtype=np.float32
    ).reshape(n, d)
    weights = []
    for _ in range(3):
        weights.append(
            np.asarray(
                [rng.uniform(-0.25, 0.25) for _ in range(d * d)],
                dtype=np.float32,
            ).reshape(d, d)
        )
    return {"n": n, "d": d, "seed": seed, "x": x, "weights": weights}


def _round_i8(value: np.ndarray | float) -> np.ndarray:
    return np.clip(np.rint(value), -127, 127).astype(np.int8)


def _scale_from_max(max_abs: float) -> float:
    # Zero tensors are not used by the anchors, but this convention keeps the
    # software and target paths defined without a large defensive framework.
    return max_abs / 127.0 if max_abs != 0.0 else 1.0


def quantize_weight(weight: np.ndarray) -> tuple[np.ndarray, float, float]:
    max_abs = float(np.max(np.abs(weight)))
    scale = _scale_from_max(max_abs)
    return _round_i8(weight / scale), scale, max_abs


def requant_acc(acc: np.ndarray, base_scale: float) -> tuple[np.ndarray, float, float]:
    max_abs = float(np.max(np.abs(acc)))
    if max_abs == 0.0:
        # q=0 and preserve the real-domain base scale.
        return np.zeros_like(acc, dtype=np.int8), float(base_scale), max_abs
    scale = float(base_scale) * max_abs / 127.0
    return _round_i8(acc.astype(np.float64) * (127.0 / max_abs)), scale, max_abs


def quantized_linear(case: dict[str, Any]) -> dict[str, Any]:
    x = np.asarray(case["x"], dtype=np.float32)
    weights = [np.asarray(w, dtype=np.float32) for w in case["weights"]]
    x_max = float(np.max(np.abs(x)))
    sx = _scale_from_max(x_max)
    xq = _round_i8(x / sx)
    wq: list[np.ndarray] = []
    sw: list[float] = []
    wmax: list[float] = []
    acc: list[np.ndarray] = []
    q: list[np.ndarray] = []
    s: list[float] = []
    qmax: list[float] = []
    base: list[float] = []
    for weight in weights:
        weight_q, weight_scale, weight_max = quantize_weight(weight)
        wq.append(weight_q)
        sw.append(weight_scale)
        wmax.append(weight_max)
        base_scale = sx * weight_scale
        base.append(base_scale)
        product = xq.astype(np.int32) @ weight_q.astype(np.int32)
        acc.append(product.astype(np.int32))
        output_q, output_scale, output_max = requant_acc(product, base_scale)
        q.append(output_q)
        s.append(output_scale)
        qmax.append(output_max)
    return {
        **case,
        "x_max": x_max,
        "sx": sx,
        "xq": xq,
        "wq": wq,
        "sw": sw,
        "wmax": wmax,
        "base": base,
        "acc": acc,
        "q": q,
        "s": s,
        "qmax": qmax,
    }


def score_fusion(qcase: dict[str, Any]) -> dict[str, Any]:
    q, k, v = [np.asarray(value) for value in qcase["q"]]
    n = int(qcase["n"])
    d = int(qcase["d"])
    score_acc = q.astype(np.int32) @ k.astype(np.int32).T
    # The system header uses key-major [key][query] score storage so one SMU
    # launch can consume a complete key column for all queries.
    score_key_major = score_acc.T.copy()
    s_q, s_k, s_v = [float(value) for value in qcase["s"]]
    score_scale = s_q * s_k / math.sqrt(float(d))
    score = score_acc.astype(np.float32) * f32(score_scale)
    score_staged = (
        (q.astype(np.float32) * f32(s_q))
        @ (k.astype(np.float32) * f32(s_k)).T
    ) / f32(math.sqrt(float(d)))
    x = np.asarray(qcase["x"], dtype=np.float32)
    weights = [np.asarray(w, dtype=np.float32) for w in qcase["weights"]]
    q_ref = x @ weights[0]
    k_ref = x @ weights[1]
    v_ref = x @ weights[2]
    score_ref = (q_ref @ k_ref.T) / f32(math.sqrt(float(d)))
    return {
        **qcase,
        "score_acc": score_acc,
        "score_key_major": score_key_major,
        "score": score,
        "score_staged": score_staged.astype(np.float32),
        "score_scale": score_scale,
        "s_v": s_v,
        "q_ref": q_ref,
        "k_ref": k_ref,
        "v_ref": v_ref,
        "score_ref": score_ref,
    }


def stable_softmax(scores: np.ndarray) -> np.ndarray:
    values = np.asarray(scores, dtype=np.float64)
    shifted = values - np.max(values, axis=-1, keepdims=True)
    result = np.exp(shifted)
    result /= np.sum(result, axis=-1, keepdims=True)
    return result.astype(np.float32)


def frozen_mixed_probability(scores: np.ndarray) -> np.ndarray:
    """Explicit P construction for row-major ``scores[query, key]``.

    The target-facing score buffer is key-major, but this host model keeps the
    ordinary row-major mathematical matrix.  Each query therefore consumes
    ``scores[query, key]``; using ``scores[key, query]`` here would silently
    construct softmax(S.T) and invalidate the Phase 4 accuracy result.
    """

    scores = np.asarray(scores, dtype=np.float32)
    n = scores.shape[0]
    lut = phase1.Int16DirectExpLUT(LUT_ENTRIES, LUT_Q_BITS)
    reciprocal = phase1.ReciprocalLUT(RECIP_ENTRIES, RECIP_Q_BITS)
    result = np.zeros((n, n), dtype=np.float32)
    basis = np.eye(n, dtype=np.float32)
    for query in range(n):
        old = phase1.Summary(
            f32(scores[query, 0]), f32(1.0), basis[0].copy(),
        )
        for key in range(1, n):
            tile = phase1.Summary(
                f32(scores[query, key]), f32(1.0), basis[key].copy(),
            )
            scalar = phase1.scalar_smu_merge(
                old, tile, MODEL_MIXED, lut, reciprocal
            )
            updated = phase1.rvv_equivalent_vector_update(
                old.o, tile.o, scalar["w_old"], scalar["w_tile"], MODEL_MIXED
            )
            old = phase1.Summary(
                scalar["m_new"], scalar["l_new"], updated
            )
        result[query, :] = np.asarray(old.o, dtype=np.float32)
    return result


def build_results(qcase: dict[str, Any]) -> dict[str, Any]:
    data = score_fusion(qcase)
    x = np.asarray(data["x"], dtype=np.float32)
    wq, wk, wv = [np.asarray(w, dtype=np.float32) for w in data["weights"]]
    q_fp = x @ wq
    k_fp = x @ wk
    v_fp = x @ wv
    score_fp = data["score_ref"]
    p_ref = stable_softmax(score_fp)
    o_ref = p_ref @ v_fp
    p_bq = stable_softmax(data["score"])
    vq = np.asarray(data["q"][2], dtype=np.float32)
    o_bq = (p_bq @ vq) * f32(data["s_v"])
    p_mixed = frozen_mixed_probability(data["score"])
    o_mixed = (p_mixed @ vq) * f32(data["s_v"])
    return {
        **data,
        "q_fp": q_fp,
        "k_fp": k_fp,
        "v_fp": v_fp,
        "p_ref": p_ref,
        "o_ref": o_ref.astype(np.float32),
        "p_bq": p_bq,
        "o_bq": o_bq.astype(np.float32),
        "p_mixed": p_mixed,
        "o_mixed": o_mixed.astype(np.float32),
    }


def metrics(actual: np.ndarray, reference: np.ndarray) -> dict[str, float | int]:
    actual64 = np.asarray(actual, dtype=np.float64)
    reference64 = np.asarray(reference, dtype=np.float64)
    difference = np.abs(actual64 - reference64)
    denom = max(float(np.sum(np.abs(reference64))), 1.0e-12)
    anorm = float(np.linalg.norm(actual64))
    rnorm = float(np.linalg.norm(reference64))
    cosine = (
        1.0 if anorm == 0.0 and rnorm == 0.0
        else 0.0 if anorm == 0.0 or rnorm == 0.0
        else float(np.sum(actual64 * reference64) / (anorm * rnorm))
    )
    return {
        "mae": float(np.mean(difference)),
        "stable_relative_error": float(np.sum(difference) / denom),
        "cosine_similarity": cosine,
        "elements": int(actual64.size),
    }


def saturation_ratio(values: np.ndarray) -> float:
    values = np.asarray(values)
    return float(np.mean((values <= -127) | (values >= 127)))


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    linear_rows = {}
    for index, (name, actual, reference) in enumerate((
        ("Q", data["q"][0] * data["s"][0], data["q_fp"]),
        ("K", data["q"][1] * data["s"][1], data["k_fp"]),
        ("V", data["q"][2] * data["s"][2], data["v_fp"]),
    )):
        linear_rows[name] = {
            **metrics(actual, reference),
            "saturation_ratio": saturation_ratio(data["q"][index]),
        }
    score_rows = {
        "quantized_vs_fp32": metrics(data["score"], data["score_ref"]),
        "fused_vs_staged": metrics(
            data["score"],
            data["score_staged"],
        ),
    }
    return {
        "n": int(data["n"]),
        "d": int(data["d"]),
        "seed": int(data["seed"]),
        "scales": {
            "sX": float(data["sx"]),
            "sWQ": float(data["sw"][0]),
            "sWK": float(data["sw"][1]),
            "sWV": float(data["sw"][2]),
            "sQ": float(data["s"][0]),
            "sK": float(data["s"][1]),
            "sV": float(data["s"][2]),
            "sScore": float(data["score_scale"]),
        },
        "linear": linear_rows,
        "score": score_rows,
        "probability": {
            "B-Q_vs_REF": metrics(data["p_bq"], data["p_ref"]),
            "P-QM_vs_REF": metrics(data["p_mixed"], data["p_ref"]),
        },
        "output": {
            "B-Q_vs_REF": metrics(data["o_bq"], data["o_ref"]),
            "P-QM_vs_REF": metrics(data["o_mixed"], data["o_ref"]),
        },
        "frozen_vectors": phase1.validate_rtl_exact_vectors(
            phase1.Int16DirectExpLUT(LUT_ENTRIES, LUT_Q_BITS)
        ),
    }


def jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def run_case(n: int, d: int, seed: int = SEED) -> dict[str, Any]:
    return build_results(quantized_linear(make_case(n, d, seed)))


def run_host_checkpoints(data: dict[str, Any]) -> None:
    """Fail fast on the Phase 4.1–4.3 correctness checkpoints."""

    if int(data["seed"]) != SEED:
        raise AssertionError("anchor seed must remain deterministic seed=1")
    if not np.array_equal(data["score_key_major"], data["score_acc"].T):
        raise AssertionError("score key-major transpose checkpoint failed")
    if not np.isfinite(np.asarray(data["score"])).all():
        raise AssertionError("fused score contains a non-finite value")
    fused = metrics(data["score"], data["score_staged"])
    if fused["cosine_similarity"] < 0.999999:
        raise AssertionError(f"fused/staged score checkpoint failed: {fused}")
    zero_q, zero_scale, zero_max = requant_acc(
        np.zeros((2, 2), dtype=np.int32), 0.25
    )
    if zero_max != 0.0 or zero_scale != 0.25 or np.any(zero_q != 0):
        raise AssertionError("zero maxabs requant convention failed")
    vectors = phase1.validate_rtl_exact_vectors(
        phase1.Int16DirectExpLUT(LUT_ENTRIES, LUT_Q_BITS)
    )
    if not all(row["matches"] for row in vectors):
        raise AssertionError("frozen Mixed scalar vectors failed")


def write_summary(path: Path, summaries: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(jsonable(summaries), indent=2) + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_summary(
        args.output,
        [run_case(8, 32), run_case(16, 64)],
    )
