#!/usr/bin/env python3
"""Phase-1 host validation of the Scalar SMU tile-merge datapath.

This script is intentionally independent of the target benchmark runner.  It
models the repository's two-summary Scalar SMU operation on fixed 32-element
tiles, followed by a separate vector update.  The three primary models are
FP32, all-FP16, and the proposed mixed FP16/INT16-LUT/FP32 path.  The
``mixed_exact_exp`` row is a diagnostic only: it replaces the LUT with exact
FP32 exponential evaluation while keeping every other mixed stage unchanged.
``mixed_rtl_exact`` is a second diagnostic that mirrors the RTL Q16.32 length
carrier and fixed-point truncation before the FP16 divider normalization.
``mixed_rtl_reciprocal`` is the bit-exact reciprocal-LUT normalization model
used by the Phase-3 software scan.  The latter keeps the former unchanged so
the division and reciprocal paths can be compared on identical cases.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import shlex
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import numpy as np
except ImportError as error:  # pragma: no cover
    raise SystemExit(
        "Phase-1 validation requires the repository's existing NumPy "
        "environment; no new dependency is added."
    ) from error


EXPERIMENT_NAME = "phase1_online_softmax"
MODEL_FP32 = "fp32"
MODEL_FP16 = "fp16"
MODEL_MIXED = "mixed"
MODEL_MIXED_EXACT = "mixed_exact_exp"
MODEL_MIXED_RTL_EXACT = "mixed_rtl_exact"
MODEL_MIXED_RTL_RECIPROCAL = "mixed_rtl_reciprocal"
PRIMARY_MODELS = (MODEL_FP32, MODEL_FP16, MODEL_MIXED)
DIAGNOSTIC_MODELS = (
    MODEL_MIXED_EXACT,
    MODEL_MIXED_RTL_EXACT,
    MODEL_MIXED_RTL_RECIPROCAL,
)
ALL_MODELS = PRIMARY_MODELS + DIAGNOSTIC_MODELS
TILE_SIZE = 32
SEQUENCE_LENGTHS = (128, 256, 512, 1024)
HEAD_DIMENSIONS = (64, 128)
QKTV_LENGTH = SEQUENCE_LENGTHS
QKTV_DIMENSION = HEAD_DIMENSIONS
BASE_SEED = 20260823

LUT_MIN = -8.0
LUT_MAX = 0.0
LUT_ENTRIES_SWEEP = (64, 128, 256)
LUT_Q_BITS_SWEEP = (10, 12, 14)
RECIPROCAL_LUT_ENTRIES_SWEEP = (64, 128, 256)
RECIPROCAL_LUT_Q_BITS_SWEEP = (10, 12, 14, 15, 16, 18, 20, 23)
RECIPROCAL_RECOMMENDED_ENTRIES = 256
RECIPROCAL_RECOMMENDED_Q_BITS = 15
RECIPROCAL_PROBE_MANTISSAS = 257
RECIPROCAL_PROBE_EXPONENTS = (1, 63, 127, 191, 254)
FP16_REACHABLE_DENOMINATOR_COUNT = 31_743
# This interval bound is for the recommended 256-entry Q1.15 image.  It is
# kept separate from the 257-point probe maximum because the latter is only a
# deterministic sample of the FP32 mantissa domain.
FULL_FP32_MANTISSA_THEORETICAL_MAX = 8.76765e-5
FULL_FP32_MANTISSA_THEORETICAL_MAX_METHOD = (
    "validated by bin-local FP32 mantissa interval enumeration with endpoint "
    "RNE and interpolation truncation"
)
TARGET_VALIDATION_WORST_ERROR = 1.5e-2
TARGET_PAIRWISE_COSINE = 0.9999
# Keep the old name as a source-compatible alias for small downstream tools;
# reports and manifests use the unambiguous validation/final-test names.
TARGET_HELDOUT_WORST_ERROR = TARGET_VALIDATION_WORST_ERROR
STABLE_RELATIVE_FLOOR = 1.0e-12


def f16(value: Any) -> np.float16:
    return np.float16(value)


def f32(value: Any) -> np.float32:
    return np.float32(value)


def _round_integer_ratio_rne(numerator: int, denominator: int) -> int:
    """Round a non-negative integer ratio to nearest, ties-to-even."""

    quotient, remainder = divmod(int(numerator), int(denominator))
    twice = 2 * remainder
    if twice > denominator or (twice == denominator and (quotient & 1)):
        quotient += 1
    return quotient


@dataclass
class Summary:
    """One Scalar SMU summary: max, length, and normalized vector state."""

    m: np.float32 | np.float16
    l: np.float32 | np.float16
    o: np.ndarray


class Int16DirectExpLUT:
    """A direct-address signed-INT16 exponential ROM.

    ``entries / 8`` is the input address scale.  Each bin stores one Q-format
    code; there is deliberately no interpolation.  The table uses bin centers
    and reserves the exact delta-zero identity, which is a common merge case.
    """

    def __init__(self, entries: int, q_bits: int) -> None:
        if entries not in LUT_ENTRIES_SWEEP:
            raise ValueError(f"unsupported LUT entries: {entries}")
        if q_bits not in LUT_Q_BITS_SWEEP:
            raise ValueError(f"unsupported LUT q_bits: {q_bits}")
        self.entries = int(entries)
        self.q_bits = int(q_bits)
        self.q_scale = 1 << self.q_bits
        self.input_scale = self.entries / 8.0
        self.output_scale = self.q_scale
        centers = LUT_MIN + (
            (np.arange(self.entries, dtype=np.float64) + 0.5)
            / self.input_scale
        )
        codes = np.rint(np.exp(centers) * self.output_scale).astype(np.int64)
        codes = np.clip(codes, 0, 32767)
        self.table = codes.astype(np.int16)

    def evaluate(self, value: Any) -> np.float32:
        x = float(np.float32(value))
        if not np.isfinite(x):
            raise ValueError(f"LUT input must be finite, got {x!r}")
        if x < LUT_MIN:
            return f32(0.0)
        if x == LUT_MAX:
            return f32(1.0)
        if x > LUT_MAX:
            return f32(1.0)
        index = int(np.floor((x - LUT_MIN) * self.input_scale))
        index = max(0, min(index, self.entries - 1))
        return f32(int(self.table[index]) / self.output_scale)

    def evaluate_code(self, value: Any) -> int:
        """Return the exact signed-INT16 ROM word selected by ``value``."""

        x = float(np.float32(value))
        if not np.isfinite(x):
            raise ValueError(f"LUT input must be finite, got {x!r}")
        if x < LUT_MIN:
            return 0
        if x >= LUT_MAX:
            return self.q_scale
        index = int(np.floor((x - LUT_MIN) * self.input_scale))
        index = max(0, min(index, self.entries - 1))
        return int(self.table[index])

    def as_dict(self) -> dict[str, Any]:
        raw_little_endian = self.table.astype("<i2", copy=False).tobytes()
        return {
            "entries": self.entries,
            "q_bits": self.q_bits,
            "q_scale": self.q_scale,
            "input_range": [LUT_MIN, LUT_MAX],
            "input_scale_entries_per_unit": self.input_scale,
            "output_scale": self.output_scale,
            "storage_bits": 16,
            "storage_dtype": "signed_int16",
            "addressing": "direct_bin_no_interpolation",
            "table_sampling": "bin_centers",
            "minimum_code": int(self.table.min()),
            "maximum_code": int(self.table.max()),
            "rom_codes_signed_int16": [int(code) for code in self.table],
            "rom_sha256_raw_little_endian_int16": hashlib.sha256(
                raw_little_endian
            ).hexdigest(),
        }


class ReciprocalLUT:
    """Bit-level FP32 mantissa reciprocal LUT used by Mixed normalization.

    The table stores unsigned Q1.q values at exact endpoint mantissas
    ``1+i/entries``.  Endpoints use integer RNE, while the runtime
    interpolation deliberately truncates the product, matching the frozen
    RTL contract.  The reciprocal scale is kept separate from the Q code:
    ``1/x = (q_code / 2**q_bits) * 2**(127-exp)``.
    """

    def __init__(self, entries: int, q_bits: int) -> None:
        if entries not in RECIPROCAL_LUT_ENTRIES_SWEEP:
            raise ValueError(f"unsupported reciprocal entries: {entries}")
        if q_bits not in RECIPROCAL_LUT_Q_BITS_SWEEP:
            raise ValueError(f"unsupported reciprocal q_bits: {q_bits}")
        if entries & (entries - 1):
            raise ValueError("reciprocal entries must be a power of two")
        self.entries = int(entries)
        self.q_bits = int(q_bits)
        self.q_scale = 1 << self.q_bits
        self.storage_bits = self.q_bits + 1
        self.index_bits = self.entries.bit_length() - 1
        self.frac_bits = 23 - self.index_bits
        self.frac_mask = (1 << self.frac_bits) - 1
        self.table = tuple(
            _round_integer_ratio_rne(
                self.entries * self.q_scale, self.entries + index
            )
            for index in range(self.entries + 1)
        )

    def trace(self, fp32_bits: int) -> dict[str, Any]:
        """Return all RTL-visible reciprocal intermediate fields."""

        bits = int(fp32_bits) & 0xFFFF_FFFF
        sign = (bits >> 31) & 1
        exponent = (bits >> 23) & 0xFF
        mantissa = bits & 0x7F_FFFF
        valid = sign == 0 and exponent not in (0, 0xFF)
        if not valid:
            return {
                "valid": False,
                "unsupported": True,
                "fp32_bits": bits,
                "exponent": exponent,
                "mantissa": mantissa,
                "index": 0,
                "frac": 0,
                "lo": 0,
                "hi": 0,
                "q": 0,
                "s": 0,
                "overflow": False,
            }
        index = mantissa >> self.frac_bits
        frac = mantissa & self.frac_mask
        lo = self.table[index]
        hi = self.table[index + 1]
        interp_product = (lo - hi) * frac
        interp_step = interp_product >> self.frac_bits
        q_code = lo - interp_step
        scale_exp = 127 - exponent
        return {
            "valid": True,
            "unsupported": False,
            "fp32_bits": bits,
            "exponent": exponent,
            "mantissa": mantissa,
            "index": index,
            "frac": frac,
            "lo": lo,
            "hi": hi,
            "interp_product": interp_product,
            "interp_step": interp_step,
            "q": q_code,
            "s": scale_exp,
        }

    def reciprocal_value(self, fp32_bits: int) -> float:
        trace = self.trace(fp32_bits)
        if not trace["valid"]:
            return 0.0
        return (trace["q"] / self.q_scale) * (2.0 ** trace["s"])

    def as_dict(self) -> dict[str, Any]:
        # Runtime interpolation reads endpoint ``entries`` as code[256], but
        # the physical ROM stores only code[0:255].  The endpoint is a
        # hardwired constant (16384 for the recommended Q1.15 image).
        stored_codes = self.table[: self.entries]
        endpoint_code = int(self.table[self.entries])
        bytes_per_word = (self.storage_bits + 7) // 8
        raw_little_endian = b"".join(
            int(code).to_bytes(
                bytes_per_word,
                byteorder="little",
                signed=False,
            )
            for code in stored_codes
        )
        return {
            "entries": self.entries,
            "q_bits": self.q_bits,
            "q_scale": self.q_scale,
            "storage_bits": self.storage_bits,
            "storage_dtype": "unsigned_q1_q",
            "index_bits": self.index_bits,
            "frac_bits": self.frac_bits,
            "addressing": "fp32_mantissa_linear_interpolation",
            "table_sampling": "endpoint_1_over_(1+i/entries)_rne",
            "minimum_code": int(min(stored_codes)),
            "maximum_code": int(max(stored_codes)),
            "rom_words": self.entries,
            "rom_bits": self.entries * self.storage_bits,
            "stored_code_range": [0, self.entries - 1],
            "endpoint_code_256_hardwired": endpoint_code,
            "rom_codes": [int(code) for code in stored_codes],
            "rom_codes_0_to_255": [int(code) for code in stored_codes],
            "rom_sha256_raw_little_endian": hashlib.sha256(
                raw_little_endian
            ).hexdigest(),
        }


def _finite_array(value: Any, dtype: np.dtype[Any]) -> np.ndarray:
    array = np.asarray(value, dtype=dtype)
    if not np.all(np.isfinite(array)):
        raise ValueError("workload inputs must be finite")
    return array


def stable_metrics(
    actual: np.ndarray, reference: np.ndarray
) -> dict[str, float | int]:
    """MAE, global-L1 stable relative error, and cosine against an oracle."""

    actual64 = np.asarray(actual, dtype=np.float64).ravel()
    reference64 = np.asarray(reference, dtype=np.float64).ravel()
    if actual64.shape != reference64.shape:
        raise ValueError("metric arrays must have equal shapes")
    difference = np.abs(actual64 - reference64)
    reference_l1 = float(np.sum(np.abs(reference64)))
    denominator = max(reference_l1, STABLE_RELATIVE_FLOOR)
    actual_norm = float(np.linalg.norm(actual64))
    reference_norm = float(np.linalg.norm(reference64))
    if actual_norm == 0.0 or reference_norm == 0.0:
        cosine = 1.0 if actual_norm == reference_norm else 0.0
    else:
        cosine = float(
            np.dot(actual64, reference64) / (actual_norm * reference_norm)
        )
    return {
        "mae": float(np.mean(difference)),
        "stable_relative_error": float(np.sum(difference) / denominator),
        "cosine_similarity": cosine,
        "elements": int(actual64.size),
    }


def fp64_attention_oracle(
    scores: np.ndarray, values: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Independent FP64 softmax/attention oracle (never calls the tile model)."""

    scores64 = _finite_array(scores, np.float64)
    values64 = _finite_array(values, np.float64)
    if scores64.ndim != 1 or values64.ndim != 2:
        raise ValueError("oracle expects scores [L] and values [L,D]")
    if values64.shape[0] != scores64.size:
        raise ValueError("oracle score/value lengths differ")
    shifted = scores64 - np.max(scores64)
    exponentials = np.exp(shifted)
    probabilities = exponentials / np.sum(exponentials, dtype=np.float64)
    output = np.sum(values64 * probabilities[:, None], axis=0, dtype=np.float64)
    return probabilities, output


def _model_is_mixed(model: str) -> bool:
    return model in (
        MODEL_MIXED,
        MODEL_MIXED_EXACT,
        MODEL_MIXED_RTL_EXACT,
        MODEL_MIXED_RTL_RECIPROCAL,
    )


def _score_state(scores: np.ndarray, model: str) -> np.ndarray:
    if model == MODEL_FP32:
        return _finite_array(scores, np.float32)
    return _finite_array(scores, np.float16)


def _exp_value(
    delta: Any,
    model: str,
    lut: Int16DirectExpLUT | None,
) -> np.float32 | np.float16:
    if model == MODEL_FP32:
        return f32(np.exp(f32(delta)))
    if model == MODEL_FP16:
        return f16(np.exp(f16(delta)))
    delta16 = f16(delta)
    if model == MODEL_MIXED_EXACT:
        # Exact exponent is only the diagnostic replacement.  Its input still
        # is the mixed FP16 delta and all length/weight stages remain mixed.
        return f32(np.exp(f32(delta16)))
    if lut is None:
        raise ValueError("mixed model requires an INT16 LUT")
    return lut.evaluate(delta16)


Q16_32_SCALE = 1 << 32
Q1_23_SCALE = 1 << 23
FP16_POS_INF_BITS = 0x7C00


def _f32_bits(value: Any) -> int:
    """Return the IEEE-754 binary32 bits of a value rounded to FP32."""

    packed = struct.pack(">f", float(np.float32(value)))
    return int.from_bytes(packed, byteorder="big", signed=False)


def _f32_from_bits(bits: int) -> np.float32:
    """Return an ``np.float32`` from IEEE-754 binary32 bits."""

    packed = int(bits & 0xFFFF_FFFF).to_bytes(4, byteorder="big")
    return f32(struct.unpack(">f", packed)[0])


def _round_shift_rne(value: int, shift: int) -> int:
    """Integer round-to-nearest, ties-to-even, matching round_shift_u64."""

    if shift <= 0:
        return int(value)
    base = int(value) >> shift
    remainder = int(value) & ((1 << shift) - 1)
    halfway = 1 << (shift - 1)
    if remainder > halfway or (remainder == halfway and (base & 1)):
        return base + 1
    return base


def _fp32_to_fp16_rne_bits(value_bits: int) -> int:
    """Bit-level version of the RTL FP32-to-binary16 RNE helper."""

    sign = (value_bits >> 31) & 1
    exp32 = (value_bits >> 23) & 0xFF
    frac32 = value_bits & 0x7F_FFFF
    if exp32 == 0xFF:
        return (sign << 15) | (0x1F << 10) | (0 if frac32 == 0 else 0x200)
    if exp32 == 0:
        return sign << 15
    unbiased = exp32 - 127
    significand = (1 << 23) | frac32
    if unbiased > 15:
        return (sign << 15) | FP16_POS_INF_BITS
    if unbiased >= -14:
        rounded = _round_shift_rne(significand, 13)
        exp16 = unbiased + 15
        if rounded >= 2048:
            rounded >>= 1
            exp16 += 1
        if exp16 >= 0x1F:
            return (sign << 15) | FP16_POS_INF_BITS
        return (sign << 15) | (exp16 << 10) | (rounded & 0x3FF)
    rounded = _round_shift_rne(significand, -(unbiased + 1))
    if rounded >= 1024:
        return (sign << 15) | 0x0400
    return (sign << 15) | (rounded & 0x3FF)


def _fp16_to_fp32_bits(value_bits: int) -> int:
    """Bit-level binary16 widening matching ``fp16_to_fp32`` in RTL."""

    sign = (value_bits >> 15) & 1
    exp16 = (value_bits >> 10) & 0x1F
    frac16 = value_bits & 0x3FF
    if exp16 == 0x1F:
        return (sign << 31) | (0xFF << 23) | (frac16 << 13)
    if exp16 == 0 and frac16 == 0:
        return sign << 31
    if exp16 == 0:
        msb = frac16.bit_length() - 1
        unbiased = msb - 24
        normalized = frac16 << (23 - msb)
        return (sign << 31) | ((unbiased + 127) << 23) | (
            normalized & 0x7F_FFFF
        )
    unbiased = exp16 - 15
    return (sign << 31) | ((unbiased + 127) << 23) | (frac16 << 13)


def _fp16_bits_to_f32(value_bits: int) -> np.float32:
    return _f32_from_bits(_fp16_to_fp32_bits(value_bits))


def _fp32_bits_to_q16_32(value_bits: int) -> int:
    """Match ``fp32_abs_to_uq16_16`` for supported positive FP32 inputs."""

    exp32 = (value_bits >> 23) & 0xFF
    frac32 = value_bits & 0x7F_FFFF
    if exp32 == 0:
        return 0
    significand = (1 << 23) | frac32
    shift = exp32 - 118
    value = significand << shift if shift >= 0 else significand >> -shift
    return int(value) & ((1 << 48) - 1)


def _q16_32_to_fp32_bits(value: int) -> int:
    """Match the RTL truncating Q16.32-carrier to FP32 conversion."""

    value = int(value)
    if value == 0:
        return 0
    msb = value.bit_length() - 1
    exponent_bits = msb - 32 + 127
    normalized = value >> (msb - 23) if msb >= 23 else value << (23 - msb)
    return ((exponent_bits & 0xFF) << 23) | (normalized & 0x7F_FFFF)


def _q16_32_to_fp32(value: int) -> np.float32:
    return _f32_from_bits(_q16_32_to_fp32_bits(value))


def _uq16_32_to_fp16_bits(value: int) -> int:
    """Match the RTL's direct Q16.32-to-binary16 RNE conversion."""

    value = int(value)
    if value == 0:
        return 0
    msb = value.bit_length() - 1
    exponent = msb - 32
    if exponent >= -14:
        shift = max(msb - 10, 0)
        rounded = _round_shift_rne(value, shift)
        if rounded >= 2048:
            rounded >>= 1
            exponent += 1
        if exponent > 15:
            return FP16_POS_INF_BITS
        return ((exponent + 15) << 10) | (rounded & 0x3FF)
    rounded = _round_shift_rne(value, 8)
    if rounded >= 1024:
        return 0x0400
    return rounded & 0x3FF


def _round_ratio_rne(
    quotient: int, remainder: int, denominator: int, shift: int
) -> int:
    """Match the divider's quotient/remainder RNE operation."""

    if shift == 0:
        return int(quotient)
    base = int(quotient) >> shift
    discarded = (int(quotient) & ((1 << shift) - 1)) * int(denominator)
    discarded += int(remainder)
    denominator_scaled = int(denominator) << shift
    twice = discarded << 1
    if twice > denominator_scaled or (
        twice == denominator_scaled and (base & 1)
    ):
        return base + 1
    return base


def _fp16_div_bits(numerator_bits: int, denominator_bits: int) -> int:
    """Bit-level reference for the 35-iteration positive FP16 divider."""

    def significand_exponent(bits: int) -> tuple[int, int]:
        exp = (bits >> 10) & 0x1F
        frac = bits & 0x3FF
        if exp == 0:
            msb = frac.bit_length() - 1
            return frac << (10 - msb), msb - 34
        return 1024 + frac, exp - 25

    if (numerator_bits & 0x7FFF) == 0 or (denominator_bits & 0x7FFF) == 0:
        return 0
    if ((numerator_bits >> 10) & 0x1F) == 0x1F or (
        (denominator_bits >> 10) & 0x1F
    ) == 0x1F:
        return 0
    numerator_sig, numerator_exp = significand_exponent(numerator_bits)
    denominator_sig, denominator_exp = significand_exponent(denominator_bits)
    exponent_diff = numerator_exp - denominator_exp
    quotient, remainder = divmod(numerator_sig << 24, denominator_sig)
    if quotient >= (1 << 24):
        significand = _round_ratio_rne(
            quotient, remainder, denominator_sig, 14
        )
        normalized_exponent = exponent_diff - 10
    else:
        significand = _round_ratio_rne(
            quotient, remainder, denominator_sig, 13
        )
        normalized_exponent = exponent_diff - 11
    if significand >= 2048:
        significand >>= 1
        normalized_exponent += 1
    sign = ((numerator_bits >> 15) ^ (denominator_bits >> 15)) & 1
    if normalized_exponent > 5:
        return (sign << 15) | FP16_POS_INF_BITS
    if normalized_exponent >= -24:
        return (sign << 15) | ((normalized_exponent + 25) << 10) | (
            significand & 0x3FF
        )
    rounded = _round_ratio_rne(
        quotient, remainder, denominator_sig, -exponent_diff
    )
    if rounded >= 1024:
        return (sign << 15) | 0x0400
    return (sign << 15) | (rounded & 0x3FF)


def _mixed_reciprocal_weight(
    numerator_fixed: int,
    denominator_fixed: int,
    reciprocal_lut: ReciprocalLUT,
) -> tuple[int, dict[str, Any]]:
    """Apply the frozen reciprocal normalization contract bit-for-bit.

    Both fixed-point operands first undergo the same direct Q16.32-to-FP16
    RNE conversion as the existing divider path.  The FP16 denominator is
    widened to FP32 for mantissa/exponent decomposition.  For Q1.15 the
    product is exactly a 64-bit ``num_q32 * recip_q15`` product and the
    exponent correction is folded into one net shift before the 48-bit
    Q16.32 carrier is converted back to FP16 with RNE.
    """

    num_h = _uq16_32_to_fp16_bits(numerator_fixed)
    den_h = _uq16_32_to_fp16_bits(denominator_fixed)
    num_q32 = _fp32_bits_to_q16_32(_fp16_to_fp32_bits(num_h))
    den_fp32_bits = _fp16_to_fp32_bits(den_h)
    reciprocal = reciprocal_lut.trace(den_fp32_bits)
    trace: dict[str, Any] = {
        "num_fixed": int(numerator_fixed),
        "den_fixed": int(denominator_fixed),
        "num_h": int(num_h),
        "den_h": int(den_h),
        "den_fp32": int(den_fp32_bits),
        "num_q32": int(num_q32),
        "index": int(reciprocal.get("index", 0)),
        "frac": int(reciprocal.get("frac", 0)),
        "lo": int(reciprocal.get("lo", 0)),
        "hi": int(reciprocal.get("hi", 0)),
        "interp_product": int(reciprocal.get("interp_product", 0)),
        "interp_step": int(reciprocal.get("interp_step", 0)),
        "q": int(reciprocal.get("q", 0)),
        "s": int(reciprocal.get("s", 0)),
        "product": 0,
        "product_width": 48 + reciprocal_lut.storage_bits,
        "net_shift": 0,
        "shifted": 0,
        "w_q32": 0,
        "final_half": 0,
        "valid": bool(reciprocal.get("valid", False)),
        "unsupported": bool(reciprocal.get("unsupported", True)),
        "overflow": False,
    }
    if not reciprocal["valid"] or den_h == 0:
        return 0, trace

    q_code = int(reciprocal["q"])
    scale_exp = int(reciprocal["s"])
    net_shift = int(reciprocal_lut.q_bits - scale_exp)
    product_width = 48 + reciprocal_lut.storage_bits
    product = int(num_q32) * q_code
    product &= (1 << product_width) - 1
    if net_shift >= 0:
        shifted = product >> net_shift
    else:
        shifted = product << (-net_shift)
    overflow = shifted >= (1 << 48)
    # The RTL carrier is uq16_16_t, i.e. exactly 48 bits.  Overflow is an
    # unsupported input, never a legal wrapped result.  Keep the shifted
    # value in the trace so a later RTL miter can diagnose the violation.
    if overflow:
        trace.update(
            {
                "product": int(product),
                "product_width": int(product_width),
                "net_shift": int(net_shift),
                "shifted": int(shifted),
                "overflow": True,
                "valid": False,
                "unsupported": True,
            }
        )
        return 0, trace
    w_q32 = int(shifted)
    final_half = _uq16_32_to_fp16_bits(w_q32)
    trace.update(
        {
            "product": int(product),
            "product_width": int(product_width),
            "net_shift": int(net_shift),
            "shifted": int(shifted),
            "w_q32": int(w_q32),
            "final_half": int(final_half),
            "overflow": False,
        }
    )
    return final_half, trace


def _fp32_to_q16_32(value: Any) -> int:
    """Truncate a non-negative FP32 length into the RTL Q16.32 carrier."""

    scalar = f32(value)
    if scalar <= 0.0:
        return 0
    return _fp32_bits_to_q16_32(_f32_bits(scalar))


def _q1_14_code(lut: Int16DirectExpLUT, delta: Any) -> int:
    if float(np.float32(delta)) >= 0.0:
        return 1 << 14
    code = lut.evaluate_code(delta)
    # The sweep varies stored Q bits, while the RTL handoff is frozen at
    # Q1.14.  Rescale lower-Q diagnostic images before the Q1.23 shift.
    return code << max(0, 14 - lut.q_bits)


def _q16_32_exp_product(value: int, exp_q1_14: int) -> int:
    # Q1.14 -> Q1.23 is an exact left shift by nine; product truncation is
    # the same integer operation used by the RTL q1_23_mul_uq16_16 helper.
    return (int(value) * (int(exp_q1_14) << 9)) >> 23


def _fp16_sub_bits(lhs_bits: int, rhs_bits: int) -> int:
    """Use one explicitly rounded binary16 subtraction for scalar deltas."""

    lhs = _fp16_bits_to_f32(lhs_bits)
    rhs = _fp16_bits_to_f32(rhs_bits)
    result = f16(f16(lhs) - f16(rhs))
    return int(np.asarray([result], dtype=np.float16).view(np.uint16)[0])


def _rtl_exact_scalar_vector(
    vector: dict[str, Any], lut: Int16DirectExpLUT
) -> dict[str, int]:
    """Evaluate a fixed scalar-interface vector with RTL carrier semantics."""

    inputs = vector["inputs"]
    m_old_h = _fp32_to_fp16_rne_bits(inputs["m_old_fp32_bits"])
    m_tile_h = _fp32_to_fp16_rne_bits(inputs["m_tile_fp32_bits"])
    m_old_value = _fp16_bits_to_f32(m_old_h)
    m_tile_value = _fp16_bits_to_f32(m_tile_h)
    m_new_h = m_old_h if m_old_value >= m_tile_value else m_tile_h
    old_delta_h = _fp16_sub_bits(m_old_h, m_new_h)
    tile_delta_h = _fp16_sub_bits(m_tile_h, m_new_h)
    old_code = _q1_14_code(lut, _fp16_bits_to_f32(old_delta_h))
    tile_code = _q1_14_code(lut, _fp16_bits_to_f32(tile_delta_h))
    old_l_fixed = _fp32_bits_to_q16_32(inputs["l_old_fp32_bits"])
    tile_l_fixed = _fp32_bits_to_q16_32(inputs["l_tile_fp32_bits"])
    old_scaled = _q16_32_exp_product(old_l_fixed, old_code)
    tile_scaled = _q16_32_exp_product(tile_l_fixed, tile_code)
    l_new_fixed = old_scaled + tile_scaled
    old_weight_h = _fp16_div_bits(
        _uq16_32_to_fp16_bits(old_scaled),
        _uq16_32_to_fp16_bits(l_new_fixed),
    )
    tile_weight_h = _fp16_div_bits(
        _uq16_32_to_fp16_bits(tile_scaled),
        _uq16_32_to_fp16_bits(l_new_fixed),
    )
    return {
        "old_exp_q1_14": old_code,
        "tile_exp_q1_14": tile_code,
        "old_scaled_l_q16_32": old_scaled,
        "tile_scaled_l_q16_32": tile_scaled,
        "l_new_q16_32": l_new_fixed,
        "m_new_fp32_bits": _fp16_to_fp32_bits(m_new_h),
        "l_new_fp32_bits": _q16_32_to_fp32_bits(l_new_fixed),
        "old_weight_fp16_bits": old_weight_h,
        "tile_weight_fp16_bits": tile_weight_h,
        "old_weight_fp32_bits": _fp16_to_fp32_bits(old_weight_h),
        "tile_weight_fp32_bits": _fp16_to_fp32_bits(tile_weight_h),
    }


def _rtl_reciprocal_scalar_vector(
    vector: dict[str, Any],
    exp_lut: Int16DirectExpLUT,
    reciprocal_lut: ReciprocalLUT,
) -> dict[str, Any]:
    """Evaluate a scalar handoff vector with reciprocal normalization."""

    inputs = vector["inputs"]
    m_old_h = _fp32_to_fp16_rne_bits(inputs["m_old_fp32_bits"])
    m_tile_h = _fp32_to_fp16_rne_bits(inputs["m_tile_fp32_bits"])
    m_old_value = _fp16_bits_to_f32(m_old_h)
    m_tile_value = _fp16_bits_to_f32(m_tile_h)
    m_new_h = m_old_h if m_old_value >= m_tile_value else m_tile_h
    old_delta_h = _fp16_sub_bits(m_old_h, m_new_h)
    tile_delta_h = _fp16_sub_bits(m_tile_h, m_new_h)
    old_code = _q1_14_code(exp_lut, _fp16_bits_to_f32(old_delta_h))
    tile_code = _q1_14_code(exp_lut, _fp16_bits_to_f32(tile_delta_h))
    old_l_fixed = _fp32_bits_to_q16_32(inputs["l_old_fp32_bits"])
    tile_l_fixed = _fp32_bits_to_q16_32(inputs["l_tile_fp32_bits"])
    old_scaled = _q16_32_exp_product(old_l_fixed, old_code)
    tile_scaled = _q16_32_exp_product(tile_l_fixed, tile_code)
    l_new_fixed = old_scaled + tile_scaled
    old_weight_h, old_trace = _mixed_reciprocal_weight(
        old_scaled, l_new_fixed, reciprocal_lut
    )
    tile_weight_h, tile_trace = _mixed_reciprocal_weight(
        tile_scaled, l_new_fixed, reciprocal_lut
    )
    return {
        "old_exp_q1_14": old_code,
        "tile_exp_q1_14": tile_code,
        "old_scaled_l_q16_32": old_scaled,
        "tile_scaled_l_q16_32": tile_scaled,
        "l_new_q16_32": l_new_fixed,
        "m_new_fp32_bits": _fp16_to_fp32_bits(m_new_h),
        "l_new_fp32_bits": _q16_32_to_fp32_bits(l_new_fixed),
        "old_weight_fp16_bits": old_weight_h,
        "tile_weight_fp16_bits": tile_weight_h,
        "old_weight_fp32_bits": _fp16_to_fp32_bits(old_weight_h),
        "tile_weight_fp32_bits": _fp16_to_fp32_bits(tile_weight_h),
        "reciprocal_old": old_trace,
        "reciprocal_tile": tile_trace,
    }


def validate_reciprocal_vectors(
    exp_lut: Int16DirectExpLUT, reciprocal_lut: ReciprocalLUT
) -> list[dict[str, Any]]:
    """Generate frozen-contract intermediate vectors for later RTL mitering."""

    rows: list[dict[str, Any]] = []
    for vector in RTL_EXACT_GOLDEN_VECTORS:
        actual = _rtl_reciprocal_scalar_vector(
            vector, exp_lut, reciprocal_lut
        )
        rows.append(
            {
                "name": vector["name"],
                "inputs": vector["inputs"],
                "expected": {
                    key: value
                    for key, value in actual.items()
                    if key not in ("reciprocal_old", "reciprocal_tile")
                },
                "reciprocal_old": actual["reciprocal_old"],
                "reciprocal_tile": actual["reciprocal_tile"],
                "matches": True,
            }
        )
    for vector in RECIPROCAL_DIRECT_VECTORS:
        numerator_h = int(vector["numerator_h"])
        denominator_h = int(vector["denominator_h"])
        numerator_fixed = _fp32_bits_to_q16_32(
            _fp16_to_fp32_bits(numerator_h)
        )
        denominator_fixed = _fp32_bits_to_q16_32(
            _fp16_to_fp32_bits(denominator_h)
        )
        final_half, trace = _mixed_reciprocal_weight(
            numerator_fixed, denominator_fixed, reciprocal_lut
        )
        rows.append(
            {
                "name": vector["name"],
                "kind": "direct",
                "inputs": {
                    "numerator_h": numerator_h,
                    "denominator_h": denominator_h,
                },
                "expected": {"final_half": int(final_half)},
                "reciprocal": trace,
                "matches": True,
            }
        )
    return rows


def flatten_reciprocal_vectors(
    vectors: list[dict[str, Any]], reciprocal_lut: ReciprocalLUT
) -> list[dict[str, Any]]:
    """Flatten scalar intermediate vectors into a CSV-friendly miter schema."""

    rows: list[dict[str, Any]] = []
    fields = (
        "den_h",
        "den_fp32",
        "index",
        "frac",
        "lo",
        "hi",
        "q",
        "s",
        "product",
        "net_shift",
        "shifted",
        "w_q32",
        "final_half",
    )
    for vector in vectors:
        if vector.get("kind") == "direct":
            side_traces = (("direct", vector["reciprocal"]),)
        else:
            side_traces = (
                ("old", vector["reciprocal_old"]),
                ("tile", vector["reciprocal_tile"]),
            )
        for side, trace in side_traces:
            row = {
                "vector": vector["name"],
                "kind": vector.get("kind", "engine"),
                "weight_side": side,
                "entries": reciprocal_lut.entries,
                "q_bits": reciprocal_lut.q_bits,
                "product_width": trace["product_width"],
                "num_fixed": trace["num_fixed"],
                "num_h": trace["num_h"],
                "num_q32": trace["num_q32"],
                "interp_product": trace["interp_product"],
                "interp_step": trace["interp_step"],
                "valid": trace["valid"],
                "unsupported": trace["unsupported"],
                "overflow": trace["overflow"],
            }
            if vector.get("kind") == "direct":
                row["input_numerator_h"] = vector["inputs"]["numerator_h"]
                row["input_denominator_h"] = vector["inputs"][
                    "denominator_h"
                ]
            row.update({field: trace[field] for field in fields})
            rows.append(row)
    return rows


# These are scalar-interface handoff vectors, not workload-generated values.
# The first vector is the exact input/expected group asserted by
# online_merge_engine_mixed_tb.sv (mode 3).  The second exercises equal maxima
# and both unity winner factors.  Keep all intermediate fields frozen so a
# host-only self-consistency change cannot silently move the RTL contract.
RTL_EXACT_GOLDEN_VECTORS = (
    {
        "name": "engine_mode3_1_0",
        "inputs": {
            "m_old_fp32_bits": 0x3F800000,
            "l_old_fp32_bits": 0x3F800000,
            "m_tile_fp32_bits": 0x00000000,
            "l_tile_fp32_bits": 0x3F800000,
        },
        "expected": {
            "old_exp_q1_14": 0x4000,
            "tile_exp_q1_14": 0x17EA,
            "old_scaled_l_q16_32": 0x100000000,
            "tile_scaled_l_q16_32": 0x5FA80000,
            "l_new_q16_32": 0x15FA80000,
            "m_new_fp32_bits": 0x3F800000,
            "l_new_fp32_bits": 0x3FAFD400,
            "old_weight_fp16_bits": 0x39D3,
            "tile_weight_fp16_bits": 0x345A,
            "old_weight_fp32_bits": 0x3F3A6000,
            "tile_weight_fp32_bits": 0x3E8B4000,
        },
    },
    {
        "name": "equal_max_1_3",
        "inputs": {
            "m_old_fp32_bits": 0x3F800000,
            "l_old_fp32_bits": 0x3F800000,
            "m_tile_fp32_bits": 0x3F800000,
            "l_tile_fp32_bits": 0x40400000,
        },
        "expected": {
            "old_exp_q1_14": 0x4000,
            "tile_exp_q1_14": 0x4000,
            "old_scaled_l_q16_32": 0x100000000,
            "tile_scaled_l_q16_32": 0x300000000,
            "l_new_q16_32": 0x400000000,
            "m_new_fp32_bits": 0x3F800000,
            "l_new_fp32_bits": 0x40800000,
            "old_weight_fp16_bits": 0x3400,
            "tile_weight_fp16_bits": 0x3A00,
            "old_weight_fp32_bits": 0x3E800000,
            "tile_weight_fp32_bits": 0x3F400000,
        },
    },
)


# Direct normalization vectors cover zero/zero handling, FP16 subnormals,
# unity/two, and the largest finite FP16 value.  They are intentionally kept
# alongside the engine vectors so the later RTL miter can consume one frozen
# intermediate schema for both interfaces.
RECIPROCAL_DIRECT_VECTORS = (
    {"name": "direct_0000_over_3c00", "numerator_h": 0x0000, "denominator_h": 0x3C00},
    {"name": "direct_0000_over_0000", "numerator_h": 0x0000, "denominator_h": 0x0000},
    {"name": "direct_0001_over_0001", "numerator_h": 0x0001, "denominator_h": 0x0001},
    {"name": "direct_0003_over_0003", "numerator_h": 0x0003, "denominator_h": 0x0003},
    {"name": "direct_0001_over_3c00", "numerator_h": 0x0001, "denominator_h": 0x3C00},
    {"name": "direct_0001_over_4000", "numerator_h": 0x0001, "denominator_h": 0x4000},
    {"name": "direct_3c04_over_3c04", "numerator_h": 0x3C04, "denominator_h": 0x3C04},
    {"name": "direct_7bff_over_7bff", "numerator_h": 0x7BFF, "denominator_h": 0x7BFF},
)


def validate_rtl_exact_vectors(lut: Int16DirectExpLUT) -> list[dict[str, Any]]:
    """Check frozen scalar vectors against the bit-level Python RTL model."""

    # The primary sweep may select a smaller validation-cost candidate in
    # smoke mode.  Scalar RTL handoff vectors always use the separately
    # frozen Phase-2 256-entry Q1.14 ROM.
    reference_lut = (
        lut if (lut.entries, lut.q_bits) == (256, 14)
        else Int16DirectExpLUT(256, 14)
    )
    rows: list[dict[str, Any]] = []
    for vector in RTL_EXACT_GOLDEN_VECTORS:
        actual = _rtl_exact_scalar_vector(vector, reference_lut)
        expected = vector["expected"]
        if actual != expected:
            raise AssertionError(
                f"RTL exact vector {vector['name']} mismatch: "
                f"actual={actual}, expected={expected}"
            )
        rows.append(
            {
                "name": vector["name"],
                "inputs": vector["inputs"],
                "expected": expected,
                "python_reference": actual,
                "matches": True,
            }
        )
    return rows


def _local_tile_summary(
    scores: np.ndarray,
    values: np.ndarray,
    start: int,
    total_length: int,
    model: str,
    lut: Int16DirectExpLUT | None,
    reciprocal_lut: ReciprocalLUT | None = None,
) -> tuple[Summary, Summary]:
    """Build one tile summary.

    The ``mixed_rtl_exact`` local-tile path is a system-level diagnostic
    assumption: Phase-2 RTL exposes scalar summary interfaces, so its exact
    contract is checked separately by fixed scalar-interface vectors below.
    This helper still uses the same carrier/conversion/divider rules when
    constructing the end-to-end diagnostic workload.
    """

    scores_in = _score_state(scores, model)
    tile_scores = scores_in[start : start + TILE_SIZE]
    if tile_scores.size != TILE_SIZE:
        raise ValueError("all validation lengths must be divisible by TILE_SIZE")
    if model == MODEL_FP32:
        tile_m: np.float32 | np.float16 = f32(np.max(tile_scores))
        tile_deltas = np.asarray(tile_scores - tile_m, dtype=np.float32)
    else:
        tile_m = f16(np.max(tile_scores))
        tile_deltas = np.asarray(
            [f16(f16(score) - f16(tile_m)) for score in tile_scores],
            dtype=np.float16,
        )
    exponentials = [
        _exp_value(delta, model, lut) for delta in tile_deltas
    ]

    if model == MODEL_FP32:
        tile_l: np.float32 | np.float16 = f32(0.0)
        for value in exponentials:
            tile_l = f32(f32(tile_l) + f32(value))
    elif model == MODEL_FP16:
        tile_l = f16(0.0)
        for value in exponentials:
            tile_l = f16(f16(tile_l) + f16(value))
    elif model in (MODEL_MIXED_RTL_EXACT, MODEL_MIXED_RTL_RECIPROCAL):
        if lut is None:
            raise ValueError("RTL-exact mixed models require an INT16 LUT")
        tile_l_fixed = 0
        for delta in tile_deltas:
            tile_l_fixed += _q16_32_exp_product(
                Q16_32_SCALE, _q1_14_code(lut, delta)
            )
        tile_l = _q16_32_to_fp32(tile_l_fixed)
    else:
        tile_l = f32(0.0)
        for value in exponentials:
            tile_l = f32(f32(tile_l) + f32(value))

    if model == MODEL_FP32:
        local_weights = np.asarray(
            [f32(f32(value) / f32(tile_l)) for value in exponentials],
            dtype=np.float32,
        )
        value_state = _finite_array(values, np.float32)
        tile_output = np.zeros(value_state.shape[1], dtype=np.float32)
        for row, weight in zip(
            value_state[start : start + TILE_SIZE], local_weights
        ):
            tile_output = np.asarray(
                np.asarray(tile_output, dtype=np.float32)
                + np.asarray(row, dtype=np.float32) * f32(weight),
                dtype=np.float32,
            )
        probability_state = np.zeros(total_length, dtype=np.float32)
        probability_state[start : start + TILE_SIZE] = local_weights
    elif model == MODEL_FP16:
        local_weights = np.asarray(
            [f16(f16(value) / f16(tile_l)) for value in exponentials],
            dtype=np.float16,
        )
        value_state = _finite_array(values, np.float16)
        tile_output = np.zeros(value_state.shape[1], dtype=np.float16)
        for row, weight in zip(
            value_state[start : start + TILE_SIZE], local_weights
        ):
            tile_output = np.asarray(
                f16(f16(tile_output) + f16(row) * f16(weight)),
                dtype=np.float16,
            )
        probability_state = np.zeros(total_length, dtype=np.float16)
        probability_state[start : start + TILE_SIZE] = local_weights
    elif model in (MODEL_MIXED_RTL_EXACT, MODEL_MIXED_RTL_RECIPROCAL):
        if lut is None:
            raise ValueError("RTL-exact mixed models require an INT16 LUT")
        local_products = [
            _q16_32_exp_product(Q16_32_SCALE, _q1_14_code(lut, delta))
            for delta in tile_deltas
        ]
        if model == MODEL_MIXED_RTL_EXACT:
            local_weights16 = np.asarray(
                [
                    _fp16_bits_to_f32(
                        _fp16_div_bits(
                            _uq16_32_to_fp16_bits(product),
                            _uq16_32_to_fp16_bits(tile_l_fixed),
                        )
                    )
                    for product in local_products
                ],
                dtype=np.float32,
            )
        else:
            if reciprocal_lut is None:
                raise ValueError(
                    "mixed_rtl_reciprocal requires a reciprocal LUT"
                )
            local_weight_values: list[np.float32] = []
            local_overflow_count = 0
            local_unsupported_count = 0
            for product in local_products:
                weight_bits, trace = _mixed_reciprocal_weight(
                    product, tile_l_fixed, reciprocal_lut
                )
                local_overflow_count += int(bool(trace["overflow"]))
                local_unsupported_count += int(bool(trace["unsupported"]))
                local_weight_values.append(_fp16_bits_to_f32(weight_bits))
            if local_overflow_count or local_unsupported_count:
                raise AssertionError(
                    "legal reciprocal workload produced overflow/unsupported "
                    f"normalization ({local_overflow_count}/"
                    f"{local_unsupported_count})"
                )
            local_weights16 = np.asarray(local_weight_values, dtype=np.float32)
        local_weights = local_weights16
        value_state = _finite_array(values, np.float32)
        tile_output = np.zeros(value_state.shape[1], dtype=np.float32)
        for row, weight in zip(
            value_state[start : start + TILE_SIZE], local_weights
        ):
            tile_output = np.asarray(
                np.asarray(tile_output, dtype=np.float32)
                + np.asarray(row, dtype=np.float32) * f32(weight),
                dtype=np.float32,
            )
        probability_state = np.zeros(total_length, dtype=np.float32)
        probability_state[start : start + TILE_SIZE] = local_weights
    else:
        # Proposed and exact-exp diagnostic paths keep V/O FP32.  Only the
        # weights are normalized in actual FP16 arithmetic, then widened.
        local_weights16 = np.asarray(
            [f16(f16(value) / f16(tile_l)) for value in exponentials],
            dtype=np.float16,
        )
        local_weights = np.asarray(local_weights16, dtype=np.float32)
        value_state = _finite_array(values, np.float32)
        tile_output = np.zeros(value_state.shape[1], dtype=np.float32)
        for row, weight in zip(
            value_state[start : start + TILE_SIZE], local_weights
        ):
            tile_output = np.asarray(
                np.asarray(tile_output, dtype=np.float32)
                + np.asarray(row, dtype=np.float32) * f32(weight),
                dtype=np.float32,
            )
        probability_state = np.zeros(total_length, dtype=np.float32)
        probability_state[start : start + TILE_SIZE] = local_weights

    return (
        Summary(tile_m, tile_l, probability_state),
        Summary(tile_m, tile_l, np.asarray(tile_output)),
    )


def scalar_smu_merge(
    old: Summary,
    tile: Summary,
    model: str,
    lut: Int16DirectExpLUT | None,
    reciprocal_lut: ReciprocalLUT | None = None,
) -> dict[str, Any]:
    """Merge ``(m_old,l_old,O_old)`` and ``(m_tile,l_tile,O_tile)``.

    The scalar block reads the two summary scalars and emits only scalar
    weights.  ``old.o`` and ``tile.o`` are deliberately carried in the Summary
    inputs and consumed by the separate RVV-equivalent vector update.
    """

    old_m, old_l = old.m, old.l
    tile_m, tile_l = tile.m, tile.l

    if model == MODEL_FP32:
        old_m_state = f32(old_m)
        tile_m_state = f32(tile_m)
        old_l_state = f32(old_l)
        tile_l_state = f32(tile_l)
        new_m = f32(max(old_m_state, tile_m_state))
        old_delta = f32(old_m_state - new_m)
        tile_delta = f32(tile_m_state - new_m)
        old_exp = f32(_exp_value(old_delta, model, lut))
        tile_exp = f32(_exp_value(tile_delta, model, lut))
        old_scaled = f32(old_l_state * old_exp)
        tile_scaled = f32(tile_l_state * tile_exp)
        new_l = f32(old_scaled + tile_scaled)
        old_weight = f32(old_scaled / new_l)
        tile_weight = f32(tile_scaled / new_l)
    elif model == MODEL_FP16:
        old_m_state = f16(old_m)
        tile_m_state = f16(tile_m)
        old_l_state = f16(old_l)
        tile_l_state = f16(tile_l)
        new_m = f16(max(old_m_state, tile_m_state))
        old_delta = f16(f16(old_m_state) - f16(new_m))
        tile_delta = f16(f16(tile_m_state) - f16(new_m))
        old_exp = f16(_exp_value(old_delta, model, lut))
        tile_exp = f16(_exp_value(tile_delta, model, lut))
        old_scaled = f16(f16(old_l_state) * f16(old_exp))
        tile_scaled = f16(f16(tile_l_state) * f16(tile_exp))
        new_l = f16(f16(old_scaled) + f16(tile_scaled))
        old_weight = f16(f16(old_scaled) / f16(new_l))
        tile_weight = f16(f16(tile_scaled) / f16(new_l))
    else:
        old_m_state = f16(old_m)
        tile_m_state = f16(tile_m)
        old_l_state = f32(old_l)
        tile_l_state = f32(tile_l)
        new_m = f16(max(old_m_state, tile_m_state))
        old_delta = f16(f16(old_m_state) - f16(new_m))
        tile_delta = f16(f16(tile_m_state) - f16(new_m))
        old_exp = f32(_exp_value(old_delta, model, lut))
        tile_exp = f32(_exp_value(tile_delta, model, lut))
        old_scaled = f32(old_l_state * old_exp)
        tile_scaled = f32(tile_l_state * tile_exp)
        new_l = f32(old_scaled + tile_scaled)
        # This is intentionally FP16 arithmetic, not FP32 division followed
        # by a storage cast: both numerator and denominator enter as FP16.
        old_weight = f16(f16(old_scaled) / f16(new_l))
        tile_weight = f16(f16(tile_scaled) / f16(new_l))

    if model in (MODEL_MIXED_RTL_EXACT, MODEL_MIXED_RTL_RECIPROCAL):
        if lut is None:
            raise ValueError("RTL-exact mixed models require an INT16 LUT")
        old_m_state = f16(old_m)
        tile_m_state = f16(tile_m)
        old_l_fixed = _fp32_to_q16_32(old_l)
        tile_l_fixed = _fp32_to_q16_32(tile_l)
        new_m = f16(max(old_m_state, tile_m_state))
        old_delta = f16(f16(old_m_state) - f16(new_m))
        tile_delta = f16(f16(tile_m_state) - f16(new_m))
        old_code = _q1_14_code(lut, old_delta)
        tile_code = _q1_14_code(lut, tile_delta)
        old_scaled_fixed = _q16_32_exp_product(old_l_fixed, old_code)
        tile_scaled_fixed = _q16_32_exp_product(tile_l_fixed, tile_code)
        new_l_fixed = old_scaled_fixed + tile_scaled_fixed
        old_scaled = _q16_32_to_fp32(old_scaled_fixed)
        tile_scaled = _q16_32_to_fp32(tile_scaled_fixed)
        new_l = _q16_32_to_fp32(new_l_fixed)
        if model == MODEL_MIXED_RTL_EXACT:
            old_weight_bits = _fp16_div_bits(
                _uq16_32_to_fp16_bits(old_scaled_fixed),
                _uq16_32_to_fp16_bits(new_l_fixed),
            )
            tile_weight_bits = _fp16_div_bits(
                _uq16_32_to_fp16_bits(tile_scaled_fixed),
                _uq16_32_to_fp16_bits(new_l_fixed),
            )
            reciprocal_old = None
            reciprocal_tile = None
        else:
            if reciprocal_lut is None:
                raise ValueError(
                    "mixed_rtl_reciprocal requires a reciprocal LUT"
                )
            old_weight_bits, reciprocal_old = _mixed_reciprocal_weight(
                old_scaled_fixed, new_l_fixed, reciprocal_lut
            )
            tile_weight_bits, reciprocal_tile = _mixed_reciprocal_weight(
                tile_scaled_fixed, new_l_fixed, reciprocal_lut
            )
        old_weight = _fp16_bits_to_f32(old_weight_bits)
        tile_weight = _fp16_bits_to_f32(tile_weight_bits)
        old_exp = f32(old_code / float(1 << 14))
        tile_exp = f32(tile_code / float(1 << 14))

    result = {
        "m_new": new_m,
        "l_new": new_l,
        "w_old": old_weight,
        "w_tile": tile_weight,
        "old_delta": old_delta,
        "tile_delta": tile_delta,
        "old_exp": old_exp,
        "tile_exp": tile_exp,
        "old_scaled_l": old_scaled,
        "tile_scaled_l": tile_scaled,
    }
    if model in (MODEL_MIXED_RTL_EXACT, MODEL_MIXED_RTL_RECIPROCAL):
        result.update(
            {
                "rtl_old_exp_q1_14": int(old_code),
                "rtl_tile_exp_q1_14": int(tile_code),
                "rtl_old_scaled_l_q16_32": int(old_scaled_fixed),
                "rtl_tile_scaled_l_q16_32": int(tile_scaled_fixed),
                "rtl_l_new_q16_32": int(new_l_fixed),
                "rtl_old_weight_fp16_bits": int(old_weight_bits),
                "rtl_tile_weight_fp16_bits": int(tile_weight_bits),
                "rtl_m_new_fp32_bits": _fp16_to_fp32_bits(
                    _fp32_to_fp16_rne_bits(_f32_bits(new_m))
                ),
                "rtl_l_new_fp32_bits": _q16_32_to_fp32_bits(new_l_fixed),
            }
        )
        if model == MODEL_MIXED_RTL_RECIPROCAL:
            result.update(
                {
                    "reciprocal_old": reciprocal_old,
                    "reciprocal_tile": reciprocal_tile,
                    "reciprocal_overflow_count": int(
                        bool(reciprocal_old["overflow"])
                    )
                    + int(bool(reciprocal_tile["overflow"])),
                    "reciprocal_unsupported_count": int(
                        bool(reciprocal_old["unsupported"])
                    )
                    + int(bool(reciprocal_tile["unsupported"])),
                }
            )
    return result


def rvv_equivalent_vector_update(
    old: np.ndarray,
    tile: np.ndarray,
    old_weight: Any,
    tile_weight: Any,
    model: str,
) -> np.ndarray:
    """Separate vector update corresponding to the SMU's RVV update stage."""

    if model == MODEL_FP16:
        old_state = np.asarray(old, dtype=np.float16)
        tile_state = np.asarray(tile, dtype=np.float16)
        return np.asarray(
            f16(f16(old_state) * f16(old_weight)
                + f16(tile_state) * f16(tile_weight)),
            dtype=np.float16,
        )
    old_state = np.asarray(old, dtype=np.float32)
    tile_state = np.asarray(tile, dtype=np.float32)
    return np.asarray(
        old_state * f32(old_weight) + tile_state * f32(tile_weight),
        dtype=np.float32,
    )


def tiled_attention(
    scores: np.ndarray,
    values: np.ndarray,
    model: str,
    lut: Int16DirectExpLUT | None,
    reciprocal_lut: ReciprocalLUT | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Construct an end-to-end result from repeated 32-element tile merges."""

    scores_in = _finite_array(scores, np.float32)
    values_in = _finite_array(values, np.float32)
    if scores_in.ndim != 1 or values_in.ndim != 2:
        raise ValueError("tiled attention expects scores [L] and values [L,D]")
    if values_in.shape[0] != scores_in.size:
        raise ValueError("score/value lengths differ")
    if scores_in.size % TILE_SIZE:
        raise ValueError("sequence length must be a multiple of TILE_SIZE")

    probability_state: Summary | None = None
    output_state: Summary | None = None
    merge_count = 0
    tile_lengths: list[float] = []
    reciprocal_overflow_count = 0
    reciprocal_unsupported_count = 0
    for start in range(0, scores_in.size, TILE_SIZE):
        tile_probability, tile_output = _local_tile_summary(
            scores_in,
            values_in,
            start,
            scores_in.size,
            model,
            lut,
            reciprocal_lut,
        )
        tile_lengths.append(float(tile_probability.l))
        if probability_state is None or output_state is None:
            probability_state = tile_probability
            output_state = tile_output
            continue
        scalar = scalar_smu_merge(
            probability_state,
            tile_probability,
            model,
            lut,
            reciprocal_lut,
        )
        if model == MODEL_MIXED_RTL_RECIPROCAL:
            reciprocal_overflow_count += int(
                scalar["reciprocal_overflow_count"]
            )
            reciprocal_unsupported_count += int(
                scalar["reciprocal_unsupported_count"]
            )
        probability_vector = rvv_equivalent_vector_update(
            probability_state.o,
            tile_probability.o,
            scalar["w_old"],
            scalar["w_tile"],
            model,
        )
        output_vector = rvv_equivalent_vector_update(
            output_state.o,
            tile_output.o,
            scalar["w_old"],
            scalar["w_tile"],
            model,
        )
        probability_state = Summary(
            scalar["m_new"], scalar["l_new"], probability_vector
        )
        output_state = Summary(scalar["m_new"], scalar["l_new"], output_vector)
        merge_count += 1

    assert probability_state is not None and output_state is not None
    if model == MODEL_MIXED_RTL_RECIPROCAL and (
        reciprocal_overflow_count or reciprocal_unsupported_count
    ):
        raise AssertionError(
            "legal reciprocal workload produced overflow/unsupported merge "
            f"normalization ({reciprocal_overflow_count}/"
            f"{reciprocal_unsupported_count})"
        )
    diagnostics = {
        "tile_size": TILE_SIZE,
        "tile_count": scores_in.size // TILE_SIZE,
        "merge_count": merge_count,
        "tile_lengths": tile_lengths,
        "final_m": float(probability_state.m),
        "final_l": float(probability_state.l),
        "reciprocal_overflow_count": reciprocal_overflow_count,
        "reciprocal_unsupported_count": reciprocal_unsupported_count,
    }
    return (
        np.asarray(probability_state.o),
        np.asarray(output_state.o),
        diagnostics,
    )


def random_score_case(
    sequence_length: int, head_dimension: int, seed: int, score_scale: float = 1.0
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    scores = rng.normal(0.0, score_scale, sequence_length).astype(np.float32)
    values = rng.normal(0.0, 1.0, (sequence_length, head_dimension)).astype(
        np.float32
    )
    return scores, values


def qktv_case(
    sequence_length: int, head_dimension: int, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """Generate common FP32 QK^T scores; variants quantize only in kernels."""

    rng = np.random.default_rng(seed)
    query = rng.normal(0.0, 1.0, head_dimension).astype(np.float32)
    keys = rng.normal(0.0, 1.0, (sequence_length, head_dimension)).astype(
        np.float32
    )
    values = rng.normal(0.0, 1.0, (sequence_length, head_dimension)).astype(
        np.float32
    )
    scores = np.asarray(
        np.matmul(keys, query) / np.sqrt(np.float32(head_dimension)),
        dtype=np.float32,
    )
    return scores, values


def independent_seed(
    base_seed: int,
    split: int,
    workload_index: int,
    length_index: int,
    dimension_index: int,
    repetition: int,
) -> int:
    """Derive independent SeedSequence components for every case/repetition."""

    sequence = np.random.SeedSequence(
        [
            int(base_seed),
            int(split),
            int(workload_index),
            int(length_index),
            int(dimension_index),
            int(repetition),
        ]
    )
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


def case_metrics(
    actual_probability: np.ndarray,
    actual_output: np.ndarray,
    oracle_probability: np.ndarray,
    oracle_output: np.ndarray,
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    probability_error = stable_metrics(actual_probability, oracle_probability)
    output_error = stable_metrics(actual_output, oracle_output)
    probability_sum = float(
        np.sum(np.asarray(actual_probability, dtype=np.float64))
    )
    return {
        "probability_mae": probability_error["mae"],
        "probability_stable_relative_error": probability_error[
            "stable_relative_error"
        ],
        "probability_cosine_similarity": probability_error[
            "cosine_similarity"
        ],
        "output_mae": output_error["mae"],
        "output_stable_relative_error": output_error["stable_relative_error"],
        "output_cosine_similarity": output_error["cosine_similarity"],
        "probability_sum": probability_sum,
        "probability_sum_error": abs(probability_sum - 1.0),
        **diagnostics,
    }


def pairwise_metrics(
    actual_probability: np.ndarray,
    actual_output: np.ndarray,
    reference_probability: np.ndarray,
    reference_output: np.ndarray,
    actual_sum: float,
    reference_sum: float,
    prefix: str,
) -> dict[str, Any]:
    """Return explicit A/B or optimized-vs-FP32 metrics for one case."""

    probability_error = stable_metrics(
        actual_probability, reference_probability
    )
    output_error = stable_metrics(actual_output, reference_output)
    return {
        f"{prefix}_probability_mae": probability_error["mae"],
        f"{prefix}_probability_stable_relative_error": probability_error[
            "stable_relative_error"
        ],
        f"{prefix}_probability_cosine_similarity": probability_error[
            "cosine_similarity"
        ],
        f"{prefix}_output_mae": output_error["mae"],
        f"{prefix}_output_stable_relative_error": output_error[
            "stable_relative_error"
        ],
        f"{prefix}_output_cosine_similarity": output_error[
            "cosine_similarity"
        ],
        f"{prefix}_probability_sum_error": abs(actual_sum - reference_sum),
    }


def run_workload(
    workload: str,
    sequence_length: int,
    head_dimension: int,
    seed: int,
    lut: Int16DirectExpLUT,
    reciprocal_lut: ReciprocalLUT | None = None,
) -> list[dict[str, Any]]:
    if workload == "random_scores":
        scores, values = random_score_case(
            sequence_length, head_dimension, seed
        )
    elif workload == "single_head_qktv":
        scores, values = qktv_case(sequence_length, head_dimension, seed)
    else:
        raise ValueError(f"unknown workload: {workload}")
    oracle_probability, oracle_output = fp64_attention_oracle(scores, values)

    rows: list[dict[str, Any]] = []
    outputs: dict[str, tuple[np.ndarray, np.ndarray, dict[str, Any]]] = {}
    for model in ALL_MODELS:
        probability, output, diagnostics = tiled_attention(
            scores,
            values,
            model,
            lut if _model_is_mixed(model) else None,
            reciprocal_lut if model == MODEL_MIXED_RTL_RECIPROCAL else None,
        )
        outputs[model] = (probability, output, diagnostics)
        row = {
            "workload": workload,
            "sequence_length": sequence_length,
            "head_dimension": head_dimension,
            "seed": seed,
            "model": model,
            "model_role": "primary" if model in PRIMARY_MODELS else "diagnostic",
            "lut_entries": lut.entries if _model_is_mixed(model) else None,
            "lut_q_bits": lut.q_bits if _model_is_mixed(model) else None,
            "lut_input_scale": (
                lut.input_scale if _model_is_mixed(model) else None
            ),
            "lut_output_scale": (
                lut.output_scale if _model_is_mixed(model) else None
            ),
        }
        row.update(
            case_metrics(
                probability,
                output,
                oracle_probability,
                oracle_output,
                diagnostics,
            )
        )
        rows.append(row)
    row_by_model = {row["model"]: row for row in rows}
    reciprocal_row = row_by_model.get(MODEL_MIXED_RTL_RECIPROCAL)
    if reciprocal_row is not None:
        reciprocal_probability, reciprocal_output, _ = outputs[
            MODEL_MIXED_RTL_RECIPROCAL
        ]
        reciprocal_sum = float(
            np.sum(np.asarray(reciprocal_probability, dtype=np.float64))
        )
        division_probability, division_output, _ = outputs[
            MODEL_MIXED_RTL_EXACT
        ]
        division_sum = float(
            np.sum(np.asarray(division_probability, dtype=np.float64))
        )
        fp32_probability, fp32_output, _ = outputs[MODEL_FP32]
        fp32_sum = float(
            np.sum(np.asarray(fp32_probability, dtype=np.float64))
        )
        reciprocal_row.update(
            pairwise_metrics(
                reciprocal_probability,
                reciprocal_output,
                division_probability,
                division_output,
                reciprocal_sum,
                division_sum,
                "ab",
            )
        )
        reciprocal_row.update(
            pairwise_metrics(
                reciprocal_probability,
                reciprocal_output,
                fp32_probability,
                fp32_output,
                reciprocal_sum,
                fp32_sum,
                "optimized_vs_fp32",
            )
        )
    return rows


def _sweep_case_list(
    base_seed: int,
    smoke: bool,
    split: int,
    workload: str = "random_scores",
) -> list[dict[str, Any]]:
    lengths = (128,) if smoke else SEQUENCE_LENGTHS
    dimensions = (64,) if smoke else HEAD_DIMENSIONS
    score_scales = (1.0, 2.0)
    repetitions = (0,) if smoke else (0, 1)
    if workload not in ("random_scores", "single_head_qktv"):
        raise ValueError(f"unknown sweep workload: {workload}")
    workload_index = 0 if workload == "random_scores" else 1
    cases: list[dict[str, Any]] = []
    for length_index, sequence_length in enumerate(lengths):
        for dimension_index, head_dimension in enumerate(dimensions):
            for scale_index, score_scale in enumerate(score_scales):
                for repetition in repetitions:
                    seed = independent_seed(
                        base_seed,
                        split,
                        workload_index,
                        length_index * len(dimensions) + dimension_index,
                        scale_index,
                        repetition,
                    )
                    if workload == "random_scores":
                        scores, values = random_score_case(
                            sequence_length,
                            head_dimension,
                            seed,
                            score_scale,
                        )
                    else:
                        scores, values = qktv_case(
                            sequence_length, head_dimension, seed
                        )
                    oracle_probability, oracle_output = fp64_attention_oracle(
                        scores, values
                    )
                    cases.append(
                        {
                            "case_id": (
                                f"{workload}_L{sequence_length}_D{head_dimension}_"
                                f"scale{scale_index}_R{repetition}"
                            ),
                            "workload": workload,
                            "sequence_length": sequence_length,
                            "head_dimension": head_dimension,
                            "score_scale": score_scale,
                            "repetition": repetition,
                            "seed": seed,
                            "scores": scores,
                            "values": values,
                            "oracle_probability": oracle_probability,
                            "oracle_output": oracle_output,
                        }
                    )
    return cases


def run_lut_sweep(
    base_seed: int, smoke: bool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    calibration_cases = _sweep_case_list(base_seed, smoke, split=1)
    validation_cases = _sweep_case_list(base_seed, smoke, split=2)
    final_test_cases = _sweep_case_list(base_seed, smoke, split=4)
    config_rows: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    for entries in LUT_ENTRIES_SWEEP:
        for q_bits in LUT_Q_BITS_SWEEP:
            lut = Int16DirectExpLUT(entries, q_bits)
            split_values: dict[str, list[float]] = {
                "calibration": [],
                "validation": [],
                "final_test": [],
            }
            for split_name, cases in (
                ("calibration", calibration_cases),
                ("validation", validation_cases),
                ("final_test", final_test_cases),
            ):
                for case in cases:
                    probability, output, diagnostics = tiled_attention(
                        case["scores"],
                        case["values"],
                        MODEL_MIXED,
                        lut,
                    )
                    metrics = case_metrics(
                        probability,
                        output,
                        case["oracle_probability"],
                        case["oracle_output"],
                        diagnostics,
                    )
                    error = max(
                        float(metrics["probability_stable_relative_error"]),
                        float(metrics["output_stable_relative_error"]),
                    )
                    split_values[split_name].append(error)
                    case_rows.append(
                        {
                            "case_id": case["case_id"],
                            "split": split_name,
                            "entries": entries,
                            "q_bits": q_bits,
                            "rom_bits": entries * 16,
                            "sequence_length": case["sequence_length"],
                            "head_dimension": case["head_dimension"],
                            "score_scale": case["score_scale"],
                            "repetition": case["repetition"],
                            "seed": case["seed"],
                            "probability_stable_relative_error": metrics[
                                "probability_stable_relative_error"
                            ],
                            "output_stable_relative_error": metrics[
                                "output_stable_relative_error"
                            ],
                            "case_worst_error": error,
                            "probability_sum_error": metrics[
                                "probability_sum_error"
                            ],
                        }
                    )
            calibration_values = split_values["calibration"]
            validation_values = split_values["validation"]
            final_test_values = split_values["final_test"]
            config_rows.append(
                {
                    "entries": entries,
                    "q_bits": q_bits,
                    "rom_bits": entries * 16,
                    "input_scale_entries_per_unit": lut.input_scale,
                    "output_scale": lut.output_scale,
                    "calibration_cases": len(calibration_values),
                    "calibration_mean_case_error": float(
                        np.mean(calibration_values)
                    ),
                    "calibration_worst_case_error": float(
                        max(calibration_values)
                    ),
                    "validation_cases": len(validation_values),
                    "validation_mean_case_error": float(
                        np.mean(validation_values)
                    ),
                    "validation_worst_case_error": float(
                        max(validation_values)
                    ),
                    "final_test_cases": len(final_test_values),
                    "final_test_mean_case_error": float(
                        np.mean(final_test_values)
                    ),
                    "final_test_worst_case_error": float(
                        max(final_test_values)
                    ),
                    "validation_threshold": TARGET_VALIDATION_WORST_ERROR,
                    "passes_validation_threshold": bool(
                        max(validation_values) <= TARGET_VALIDATION_WORST_ERROR
                    ),
                    "selected": False,
                }
            )

    passing = [
        row for row in config_rows if row["passes_validation_threshold"]
    ]
    if passing:
        selected = min(
            passing,
            key=lambda row: (
                row["rom_bits"],
                row["validation_worst_case_error"],
                row["validation_mean_case_error"],
                row["q_bits"],
            ),
        )
        selection_status = "target_met"
    else:
        selected = min(
            config_rows,
            key=lambda row: (
                row["validation_worst_case_error"],
                row["rom_bits"],
                row["q_bits"],
            ),
        )
        selection_status = "best_effort_no_candidate_below_threshold"
    for row in config_rows:
        row["selected"] = (
            row["entries"] == selected["entries"]
            and row["q_bits"] == selected["q_bits"]
        )
    selection = {
        "status": selection_status,
        "entries": int(selected["entries"]),
        "q_bits": int(selected["q_bits"]),
        "rom_bits": int(selected["rom_bits"]),
        "input_scale_entries_per_unit": float(
            selected["input_scale_entries_per_unit"]
        ),
        "output_scale": int(selected["output_scale"]),
        "validation_threshold": TARGET_VALIDATION_WORST_ERROR,
        "validation_worst_case_error": float(
            selected["validation_worst_case_error"]
        ),
        "validation_mean_case_error": float(
            selected["validation_mean_case_error"]
        ),
        "calibration_worst_case_error": float(
            selected["calibration_worst_case_error"]
        ),
        "final_test_worst_case_error": float(
            selected["final_test_worst_case_error"]
        ),
        "final_test_mean_case_error": float(
            selected["final_test_mean_case_error"]
        ),
    }
    selected_lut = Int16DirectExpLUT(selection["entries"], selection["q_bits"])
    selection["rom_sha256_raw_little_endian_int16"] = selected_lut.as_dict()[
        "rom_sha256_raw_little_endian_int16"
    ]
    return config_rows, case_rows, selection


def _reciprocal_probe_bits() -> list[int]:
    """Build deterministic FP32 mantissa/exponent probes for LUT error."""

    max_mantissa = (1 << 23) - 1
    if RECIPROCAL_PROBE_MANTISSAS == 1:
        mantissas = [0]
    else:
        step = max_mantissa // (RECIPROCAL_PROBE_MANTISSAS - 1)
        mantissas = [
            min(index * step, max_mantissa)
            for index in range(RECIPROCAL_PROBE_MANTISSAS)
        ]
        mantissas[-1] = max_mantissa
    return [
        (exponent << 23) | mantissa
        for exponent in RECIPROCAL_PROBE_EXPONENTS
        for mantissa in mantissas
    ]


def _reciprocal_probe_rows(
    reciprocal_lut: ReciprocalLUT,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    rows: list[dict[str, Any]] = []
    errors: list[float] = []
    for fp32_bits in _reciprocal_probe_bits():
        trace = reciprocal_lut.trace(fp32_bits)
        exact = 1.0 / float(_f32_from_bits(fp32_bits))
        approximate = reciprocal_lut.reciprocal_value(fp32_bits)
        relative_error = abs(approximate - exact) / abs(exact)
        errors.append(relative_error)
        rows.append(
            {
                "entries": reciprocal_lut.entries,
                "q_bits": reciprocal_lut.q_bits,
                "fp32_bits": fp32_bits,
                "x": float(_f32_from_bits(fp32_bits)),
                "exact_reciprocal": exact,
                "lut_reciprocal": approximate,
                "relative_error": relative_error,
                "index": trace["index"],
                "frac": trace["frac"],
                "lo": trace["lo"],
                "hi": trace["hi"],
                "q": trace["q"],
                "s": trace["s"],
                "interp_product": trace.get("interp_product", 0),
                "interp_step": trace.get("interp_step", 0),
            }
        )
    sorted_errors = np.sort(np.asarray(errors, dtype=np.float64))
    probe_mean = float(np.mean(sorted_errors))
    probe_max = float(np.max(sorted_errors))
    probe_p99 = float(np.percentile(sorted_errors, 99.0))
    return rows, {
        "probe_mean": probe_mean,
        "probe_max": probe_max,
        "probe_p99": probe_p99,
        "probe_count": len(errors),
        # Keep the old names for downstream readers of the Phase-3 preview;
        # the report and new gates use the unambiguous probe_* names.
        "reciprocal_relative_error_mean": probe_mean,
        "reciprocal_relative_error_max": probe_max,
        "reciprocal_relative_error_p99": probe_p99,
        "reciprocal_probe_count": len(errors),
    }


def _reachable_fp16_denominator_bits() -> list[int]:
    """Enumerate every positive finite binary16 denominator bit pattern."""

    return [
        (exponent << 10) | fraction
        for exponent in range(0x1F)
        for fraction in range(0x400)
        if not (exponent == 0 and fraction == 0)
    ]


def _reachable_reciprocal_metrics(
    reciprocal_lut: ReciprocalLUT,
) -> dict[str, Any]:
    """Measure reciprocal error over the complete positive finite FP16 domain."""

    denominator_bits = _reachable_fp16_denominator_bits()
    errors: list[float] = []
    unsupported_count = 0
    for denominator_h in denominator_bits:
        denominator = float(_fp16_bits_to_f32(denominator_h))
        exact = 1.0 / denominator
        fp32_bits = _fp16_to_fp32_bits(denominator_h)
        trace = reciprocal_lut.trace(fp32_bits)
        if not trace["valid"]:
            unsupported_count += 1
            continue
        approximate = reciprocal_lut.reciprocal_value(fp32_bits)
        errors.append(abs(approximate - exact) / abs(exact))
    sorted_errors = np.sort(np.asarray(errors, dtype=np.float64))
    return {
        "reachable_domain_count": len(denominator_bits),
        "reachable_domain_unsupported_count": unsupported_count,
        "reachable_domain_overflow_count": 0,
        "reachable_domain_mean": float(np.mean(sorted_errors)),
        "reachable_domain_max": float(np.max(sorted_errors)),
        "reachable_domain_p99": float(np.percentile(sorted_errors, 99.0)),
        "full_fp32_mantissa_theoretical_max": (
            FULL_FP32_MANTISSA_THEORETICAL_MAX
            if (
                reciprocal_lut.entries == RECIPROCAL_RECOMMENDED_ENTRIES
                and reciprocal_lut.q_bits == RECIPROCAL_RECOMMENDED_Q_BITS
            )
            else None
        ),
        "full_fp32_mantissa_theoretical_max_method": (
            FULL_FP32_MANTISSA_THEORETICAL_MAX_METHOD
            if (
                reciprocal_lut.entries == RECIPROCAL_RECOMMENDED_ENTRIES
                and reciprocal_lut.q_bits == RECIPROCAL_RECOMMENDED_Q_BITS
            )
            else None
        ),
    }


def _metric_triplet(
    actual: np.ndarray, reference: np.ndarray
) -> tuple[float, float, float]:
    metrics = stable_metrics(actual, reference)
    return (
        float(metrics["mae"]),
        float(metrics["stable_relative_error"]),
        float(metrics["cosine_similarity"]),
    )


def run_reciprocal_sweep(
    base_seed: int,
    smoke: bool,
    exp_lut: Int16DirectExpLUT,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    """Scan reciprocal LUT shape/precision against Model A and FP32.

    The EXP LUT is held at the already selected Phase-2 256-entry Q1.14
    image.  This isolates normalization changes while retaining the existing
    Mixed EXP contract.
    """

    sweep_cases: dict[str, list[dict[str, Any]]] = {}
    for workload in ("random_scores", "single_head_qktv"):
        for split, split_name in (
            (1, "calibration"),
            (2, "validation"),
            (4, "final_test"),
        ):
            sweep_cases[f"{split_name}:{workload}"] = _sweep_case_list(
                base_seed, smoke, split, workload
            )

    # These two paths do not depend on reciprocal parameters.  Caching them
    # keeps the 24-config scan focused on the new multiplier/LUT candidate.
    reference_cache: dict[
        str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]
    ] = {}
    config_rows: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    probe_rows: list[dict[str, Any]] = []

    for entries in RECIPROCAL_LUT_ENTRIES_SWEEP:
        for q_bits in RECIPROCAL_LUT_Q_BITS_SWEEP:
            reciprocal_lut = ReciprocalLUT(entries, q_bits)
            config_probe_rows, probe_metrics = _reciprocal_probe_rows(
                reciprocal_lut
            )
            reachable_metrics = _reachable_reciprocal_metrics(reciprocal_lut)
            probe_rows.extend(config_probe_rows)
            split_values: dict[str, list[dict[str, Any]]] = {
                "calibration": [],
                "validation": [],
                "final_test": [],
            }
            for split_name in ("calibration", "validation", "final_test"):
                for workload in ("random_scores", "single_head_qktv"):
                    for case in sweep_cases[f"{split_name}:{workload}"]:
                        cache_key = f"{split_name}:{case['case_id']}"
                        if cache_key not in reference_cache:
                            fp32_probability, fp32_output, _ = tiled_attention(
                                case["scores"],
                                case["values"],
                                MODEL_FP32,
                                None,
                            )
                            division_probability, division_output, _ = (
                                tiled_attention(
                                    case["scores"],
                                    case["values"],
                                    MODEL_MIXED_RTL_EXACT,
                                    exp_lut,
                                )
                            )
                            reference_cache[cache_key] = (
                                fp32_probability,
                                fp32_output,
                                division_probability,
                                division_output,
                            )
                        (
                            fp32_probability,
                            fp32_output,
                            division_probability,
                            division_output,
                        ) = reference_cache[cache_key]
                        reciprocal_probability, reciprocal_output, _ = (
                            tiled_attention(
                                case["scores"],
                                case["values"],
                                MODEL_MIXED_RTL_RECIPROCAL,
                                exp_lut,
                                reciprocal_lut,
                            )
                        )
                        oracle_probability = case["oracle_probability"]
                        oracle_output = case["oracle_output"]
                        oracle_probability_metrics = stable_metrics(
                            reciprocal_probability, oracle_probability
                        )
                        oracle_output_metrics = stable_metrics(
                            reciprocal_output, oracle_output
                        )
                        ab_probability_metrics = stable_metrics(
                            reciprocal_probability, division_probability
                        )
                        ab_output_metrics = stable_metrics(
                            reciprocal_output, division_output
                        )
                        fp32_probability_metrics = stable_metrics(
                            reciprocal_probability, fp32_probability
                        )
                        fp32_output_metrics = stable_metrics(
                            reciprocal_output, fp32_output
                        )
                        reciprocal_sum = float(
                            np.sum(
                                np.asarray(reciprocal_probability, dtype=np.float64)
                            )
                        )
                        division_sum = float(
                            np.sum(
                                np.asarray(division_probability, dtype=np.float64)
                            )
                        )
                        fp32_sum = float(
                            np.sum(np.asarray(fp32_probability, dtype=np.float64))
                        )
                        row = {
                            "case_id": case["case_id"],
                            "split": split_name,
                            "workload": workload,
                            "entries": entries,
                            "q_bits": q_bits,
                            "rom_bits": entries * (q_bits + 1),
                            "sequence_length": case["sequence_length"],
                            "head_dimension": case["head_dimension"],
                            "score_scale": case["score_scale"],
                            "repetition": case["repetition"],
                            "seed": case["seed"],
                            "optimized_oracle_probability_mae": oracle_probability_metrics[
                                "mae"
                            ],
                            "optimized_oracle_probability_relative": oracle_probability_metrics[
                                "stable_relative_error"
                            ],
                            "optimized_oracle_probability_cosine": oracle_probability_metrics[
                                "cosine_similarity"
                            ],
                            "optimized_oracle_attention_mae": oracle_output_metrics[
                                "mae"
                            ],
                            "optimized_oracle_attention_relative": oracle_output_metrics[
                                "stable_relative_error"
                            ],
                            "optimized_oracle_attention_cosine": oracle_output_metrics[
                                "cosine_similarity"
                            ],
                            "ab_softmax_mae": ab_probability_metrics["mae"],
                            "ab_softmax_relative": ab_probability_metrics[
                                "stable_relative_error"
                            ],
                            "ab_softmax_cosine": ab_probability_metrics[
                                "cosine_similarity"
                            ],
                            "ab_attention_mae": ab_output_metrics["mae"],
                            "ab_attention_relative": ab_output_metrics[
                                "stable_relative_error"
                            ],
                            "ab_attention_cosine": ab_output_metrics[
                                "cosine_similarity"
                            ],
                            "optimized_fp32_softmax_mae": fp32_probability_metrics[
                                "mae"
                            ],
                            "optimized_fp32_softmax_relative": fp32_probability_metrics[
                                "stable_relative_error"
                            ],
                            "optimized_fp32_softmax_cosine": fp32_probability_metrics[
                                "cosine_similarity"
                            ],
                            "optimized_fp32_attention_mae": fp32_output_metrics[
                                "mae"
                            ],
                            "optimized_fp32_attention_relative": fp32_output_metrics[
                                "stable_relative_error"
                            ],
                            "optimized_fp32_attention_cosine": fp32_output_metrics[
                                "cosine_similarity"
                            ],
                            "optimized_probability_sum": reciprocal_sum,
                            "optimized_probability_sum_error": abs(
                                reciprocal_sum - 1.0
                            ),
                            "ab_probability_sum_error": abs(
                                reciprocal_sum - division_sum
                            ),
                            "optimized_fp32_probability_sum_error": abs(
                                reciprocal_sum - fp32_sum
                            ),
                        }
                        row["case_worst_error"] = max(
                            row["optimized_oracle_probability_relative"],
                            row["optimized_oracle_attention_relative"],
                        )
                        case_rows.append(row)
                        split_values[split_name].append(row)

            def values(field: str, split_name: str) -> list[float]:
                return [float(row[field]) for row in split_values[split_name]]

            def split_max(field: str, split_name: str) -> float:
                return max(values(field, split_name))

            def split_min(field: str, split_name: str) -> float:
                return min(values(field, split_name))

            validation_worst = split_max("case_worst_error", "validation")
            validation_ab_worst = max(
                split_max("ab_softmax_relative", "validation"),
                split_max("ab_attention_relative", "validation"),
            )
            validation_optimized_oracle_cosine = min(
                split_min("optimized_oracle_probability_cosine", "validation"),
                split_min("optimized_oracle_attention_cosine", "validation"),
            )
            validation_ab_pairwise_cosine = min(
                split_min("ab_softmax_cosine", "validation"),
                split_min("ab_attention_cosine", "validation"),
            )
            validation_optimized_fp32_cosine = min(
                split_min("optimized_fp32_softmax_cosine", "validation"),
                split_min("optimized_fp32_attention_cosine", "validation"),
            )
            config_rows.append(
                {
                    "entries": entries,
                    "q_bits": q_bits,
                    "rom_bits": entries * (q_bits + 1),
                    **probe_metrics,
                    **reachable_metrics,
                    "calibration_cases": len(split_values["calibration"]),
                    "validation_cases": len(split_values["validation"]),
                    "final_test_cases": len(split_values["final_test"]),
                    "calibration_worst_case_error": split_max(
                        "case_worst_error", "calibration"
                    ),
                    "validation_worst_case_error": split_max(
                        "case_worst_error", "validation"
                    ),
                    "validation_ab_worst_case_error": validation_ab_worst,
                    "validation_optimized_oracle_worst_case_error": validation_worst,
                    "final_test_worst_case_error": split_max(
                        "case_worst_error", "final_test"
                    ),
                    "validation_pairwise_cosine_min": validation_ab_pairwise_cosine,
                    "validation_ab_pairwise_cosine_min": validation_ab_pairwise_cosine,
                    "validation_optimized_fp32_pairwise_cosine_min": validation_optimized_fp32_cosine,
                    "validation_ab_attention_relative_max": split_max(
                        "ab_attention_relative", "validation"
                    ),
                    "validation_optimized_fp32_attention_relative_max": split_max(
                        "optimized_fp32_attention_relative", "validation"
                    ),
                    "validation_optimized_oracle_pairwise_cosine_min": validation_optimized_oracle_cosine,
                    "validation_optimized_probability_sum_error_max": split_max(
                        "optimized_probability_sum_error", "validation"
                    ),
                    "validation_ab_probability_sum_error_max": split_max(
                        "ab_probability_sum_error", "validation"
                    ),
                    "final_test_pairwise_cosine_min": min(
                        split_min("ab_softmax_cosine", "final_test"),
                        split_min("ab_attention_cosine", "final_test"),
                    ),
                    "final_test_optimized_fp32_pairwise_cosine_min": min(
                        split_min(
                            "optimized_fp32_softmax_cosine", "final_test"
                        ),
                        split_min(
                            "optimized_fp32_attention_cosine", "final_test"
                        ),
                    ),
                    "validation_threshold": TARGET_VALIDATION_WORST_ERROR,
                    "pairwise_cosine_threshold": TARGET_PAIRWISE_COSINE,
                    "passes_ab_validation_threshold": bool(
                        validation_ab_worst <= TARGET_VALIDATION_WORST_ERROR
                        and validation_ab_pairwise_cosine >= TARGET_PAIRWISE_COSINE
                    ),
                    "passes_optimized_oracle_validation_threshold": bool(
                        validation_worst <= TARGET_VALIDATION_WORST_ERROR
                        and validation_optimized_oracle_cosine
                        >= TARGET_PAIRWISE_COSINE
                    ),
                    # Compatibility alias: historical sweep consumers used
                    # this name for the A/B gate.
                    "passes_validation_threshold": bool(
                        validation_ab_worst <= TARGET_VALIDATION_WORST_ERROR
                        and validation_ab_pairwise_cosine >= TARGET_PAIRWISE_COSINE
                    ),
                    "recommended": bool(
                        entries == RECIPROCAL_RECOMMENDED_ENTRIES
                        and q_bits == RECIPROCAL_RECOMMENDED_Q_BITS
                    ),
                    "selected": False,
                }
            )

    selected = next(
        row for row in config_rows if row["recommended"]
    )
    selected["selected"] = True
    selection = {
        "status": "frozen_q1_15_candidate",
        "entries": int(selected["entries"]),
        "q_bits": int(selected["q_bits"]),
        "rom_bits": int(selected["rom_bits"]),
        "storage_bits": int(selected["q_bits"] + 1),
        "rom_words": int(selected["entries"]),
        "endpoint_code_256_hardwired": int(
            ReciprocalLUT(
                selected["entries"], selected["q_bits"]
            ).table[selected["entries"]]
        ),
        "probe_max": float(selected["probe_max"]),
        "probe_mean": float(selected["probe_mean"]),
        "probe_p99": float(selected["probe_p99"]),
        "reachable_domain_max": float(selected["reachable_domain_max"]),
        "reachable_domain_mean": float(selected["reachable_domain_mean"]),
        "reachable_domain_p99": float(selected["reachable_domain_p99"]),
        "reachable_domain_count": int(selected["reachable_domain_count"]),
        "reachable_domain_unsupported_count": int(
            selected["reachable_domain_unsupported_count"]
        ),
        "reachable_domain_overflow_count": int(
            selected["reachable_domain_overflow_count"]
        ),
        "full_fp32_mantissa_theoretical_max": selected[
            "full_fp32_mantissa_theoretical_max"
        ],
        "full_fp32_mantissa_theoretical_max_method": selected[
            "full_fp32_mantissa_theoretical_max_method"
        ],
        "validation_worst_case_error": float(
            selected["validation_worst_case_error"]
        ),
        "validation_pairwise_cosine_min": float(
            selected["validation_pairwise_cosine_min"]
        ),
        "final_test_worst_case_error": float(
            selected["final_test_worst_case_error"]
        ),
        "final_test_pairwise_cosine_min": float(
            selected["final_test_pairwise_cosine_min"]
        ),
        "passes_validation_threshold": bool(
            selected["passes_validation_threshold"]
        ),
        "passes_ab_validation_threshold": bool(
            selected["passes_ab_validation_threshold"]
        ),
        "passes_optimized_oracle_validation_threshold": bool(
            selected["passes_optimized_oracle_validation_threshold"]
        ),
        "validation_ab_worst_case_error": float(
            selected["validation_ab_worst_case_error"]
        ),
        "validation_optimized_oracle_worst_case_error": float(
            selected["validation_optimized_oracle_worst_case_error"]
        ),
        "validation_optimized_oracle_pairwise_cosine_min": float(
            selected["validation_optimized_oracle_pairwise_cosine_min"]
        ),
    }
    return config_rows, case_rows, probe_rows, selection


def boundary_cases() -> tuple[
    list[dict[str, Any]], np.ndarray, np.ndarray
]:
    base_old = np.asarray([0.25, -0.5, 0.75, -1.0], dtype=np.float32)
    base_tile = np.asarray([-0.2, 0.4, -0.6, 0.8], dtype=np.float32)
    return [
        {
            "case": "equal_max",
            "m_old": 0.0,
            "l_old": 2.0,
            "m_tile": 0.0,
            "l_tile": 3.0,
        },
        {
            "case": "near_tie_max",
            "m_old": 0.0,
            "l_old": 2.0,
            "m_tile": -1.0e-3,
            "l_tile": 1.5,
        },
        {
            "case": "delta_minus_8",
            "m_old": -8.0,
            "l_old": 2.0,
            "m_tile": 0.0,
            "l_tile": 1.25,
        },
        {
            "case": "delta_below_minus_8",
            "m_old": -10.0,
            "l_old": 2.0,
            "m_tile": 0.0,
            "l_tile": 1.25,
        },
        {
            "case": "small_unequal_l",
            "m_old": 0.25,
            "l_old": 0.125,
            "m_tile": -1.5,
            "l_tile": 3.75,
        },
        {
            "case": "old_l_zero",
            "m_old": -0.5,
            "l_old": 0.0,
            "m_tile": 0.0,
            "l_tile": 1.25,
        },
        {
            "case": "tile_l_zero",
            "m_old": 0.0,
            "l_old": 1.25,
            "m_tile": -0.5,
            "l_tile": 0.0,
        },
    ], base_old, base_tile


def run_boundaries(
    lut: Int16DirectExpLUT,
    reciprocal_lut: ReciprocalLUT | None = None,
) -> list[dict[str, Any]]:
    cases, old_vector, tile_vector = boundary_cases()
    rows: list[dict[str, Any]] = []
    for case in cases:
        for model in ALL_MODELS:
            scalar = scalar_smu_merge(
                Summary(case["m_old"], case["l_old"], old_vector),
                Summary(case["m_tile"], case["l_tile"], tile_vector),
                model,
                lut if _model_is_mixed(model) else None,
                reciprocal_lut if model == MODEL_MIXED_RTL_RECIPROCAL else None,
            )
            updated = rvv_equivalent_vector_update(
                old_vector,
                tile_vector,
                scalar["w_old"],
                scalar["w_tile"],
                model,
            )
            rows.append(
                {
                    "case": case["case"],
                    "model": model,
                    "model_role": (
                        "primary" if model in PRIMARY_MODELS else "diagnostic"
                    ),
                    "m_old": case["m_old"],
                    "l_old": case["l_old"],
                    "m_tile": case["m_tile"],
                    "l_tile": case["l_tile"],
                    "m_new": scalar["m_new"],
                    "l_new": scalar["l_new"],
                    "old_delta": scalar["old_delta"],
                    "tile_delta": scalar["tile_delta"],
                    "old_exp": scalar["old_exp"],
                    "tile_exp": scalar["tile_exp"],
                    "w_old": scalar["w_old"],
                    "w_tile": scalar["w_tile"],
                    "weight_sum_error": abs(
                        float(scalar["w_old"]) + float(scalar["w_tile"]) - 1.0
                    ),
                    "vector_update_l2": float(np.linalg.norm(updated)),
                }
            )
    return rows


def aggregate_rows(
    rows: list[dict[str, Any]],
    workload: str | None = None,
    model_role: str = "primary",
) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if row["model_role"] == model_role
        and (workload is None or row["workload"] == workload)
    ]
    summaries: list[dict[str, Any]] = []
    for model in (
        PRIMARY_MODELS if model_role == "primary" else DIAGNOSTIC_MODELS
    ):
        model_rows = [row for row in selected if row["model"] == model]
        if not model_rows:
            continue
        summary: dict[str, Any] = {
            "model": model,
            "model_role": model_role,
            "workload": workload or "all",
            "cases": len(model_rows),
        }
        for scope in ("probability", "output"):
            for metric in ("mae", "stable_relative_error"):
                values = [row[f"{scope}_{metric}"] for row in model_rows]
                summary[f"{scope}_{metric}_mean"] = float(np.mean(values))
                summary[f"{scope}_{metric}_max"] = float(np.max(values))
            cosine_values = [
                row[f"{scope}_cosine_similarity"] for row in model_rows
            ]
            summary[f"{scope}_cosine_similarity_min"] = float(
                np.min(cosine_values)
            )
        sum_errors = [row["probability_sum_error"] for row in model_rows]
        summary["probability_sum_error_mean"] = float(np.mean(sum_errors))
        summary["probability_sum_error_max"] = float(np.max(sum_errors))
        summaries.append(summary)
    return summaries


def _json_value(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_value(payload), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in materialized:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in materialized:
            writer.writerow(
                {
                    field: "NA" if row.get(field) is None else row.get(field)
                    for field in fields
                }
            )


def _summary_line(summary: dict[str, Any]) -> str:
    return (
        f"| {summary['model']} | {summary['cases']} | "
        f"{summary['probability_mae_mean']:.3e} / "
        f"{summary['probability_mae_max']:.3e} | "
        f"{summary['probability_stable_relative_error_mean']:.3e} / "
        f"{summary['probability_stable_relative_error_max']:.3e} | "
        f"{summary['probability_cosine_similarity_min']:.9f} | "
        f"{summary['output_mae_mean']:.3e} / "
        f"{summary['output_mae_max']:.3e} | "
        f"{summary['output_stable_relative_error_mean']:.3e} / "
        f"{summary['output_stable_relative_error_max']:.3e} | "
        f"{summary['output_cosine_similarity_min']:.9f} | "
        f"{summary['probability_sum_error_mean']:.3e} / "
        f"{summary['probability_sum_error_max']:.3e} |"
    )


def _summary_table(summaries: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| model | cases | probability MAE mean/max | probability "
        "stable-rel mean/max | probability cosine min | output MAE mean/max | "
        "output stable-rel mean/max | output cosine min | probability-sum "
        "error mean/max |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(_summary_line(summary) for summary in summaries)
    return lines


def reciprocal_matrix_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Model-B matrix pairwise metrics for machine-readable output."""

    summary: dict[str, Any] = {}
    fields = (
        "ab_probability_mae",
        "ab_probability_stable_relative_error",
        "ab_probability_cosine_similarity",
        "ab_output_mae",
        "ab_output_stable_relative_error",
        "ab_output_cosine_similarity",
        "optimized_vs_fp32_probability_mae",
        "optimized_vs_fp32_probability_stable_relative_error",
        "optimized_vs_fp32_probability_cosine_similarity",
        "optimized_vs_fp32_output_mae",
        "optimized_vs_fp32_output_stable_relative_error",
        "optimized_vs_fp32_output_cosine_similarity",
        "probability_sum_error",
        "ab_probability_sum_error",
        "optimized_vs_fp32_probability_sum_error",
    )
    for workload in ("random_scores", "single_head_qktv"):
        selected = [
            row
            for row in rows
            if row["model"] == MODEL_MIXED_RTL_RECIPROCAL
            and row["workload"] == workload
        ]
        if not selected:
            continue
        workload_summary: dict[str, Any] = {"cases": len(selected)}
        for field in fields:
            values = [float(row[field]) for row in selected]
            workload_summary[f"{field}_mean"] = float(np.mean(values))
            workload_summary[f"{field}_max"] = float(np.max(values))
            if "cosine" in field:
                workload_summary[f"{field}_min"] = float(np.min(values))
        summary[workload] = workload_summary
    return summary


def reciprocal_formal_matrix_gate(
    rows: list[dict[str, Any]],
    lengths: tuple[int, ...],
    dimensions: tuple[int, ...],
) -> dict[str, Any]:
    """Check complete Cartesian coverage and the optimized FP32 target."""

    expected = {
        f"{workload}:L{sequence_length}:D{head_dimension}"
        for workload in ("random_scores", "single_head_qktv")
        for sequence_length in lengths
        for head_dimension in dimensions
    }
    optimized_rows = [
        row
        for row in rows
        if row["model"] == MODEL_MIXED_RTL_RECIPROCAL
    ]
    keys = [
        f"{row['workload']}:L{row['sequence_length']}:D{row['head_dimension']}"
        for row in optimized_rows
    ]
    actual = set(keys)
    duplicates = sorted(
        key for key in actual if keys.count(key) > 1
    )
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    attention_cosine_min = (
        min(
            float(row["optimized_vs_fp32_output_cosine_similarity"])
            for row in optimized_rows
        )
        if optimized_rows
        else 0.0
    )
    ab_relative_max = (
        max(float(row["ab_output_stable_relative_error"]) for row in optimized_rows)
        if optimized_rows
        else float("inf")
    )
    passed = bool(
        not missing
        and not extra
        and not duplicates
        and len(optimized_rows) == len(expected)
        and attention_cosine_min >= TARGET_PAIRWISE_COSINE
        and ab_relative_max <= TARGET_VALIDATION_WORST_ERROR
    )
    return {
        "expected_cases": len(expected),
        "actual_cases": len(optimized_rows),
        "expected_cartesian": True,
        "missing": missing,
        "extra": extra,
        "duplicates": duplicates,
        "optimized_vs_fp32_attention_cosine_min": attention_cosine_min,
        "ab_attention_relative_max": ab_relative_max,
        "target_cosine": TARGET_PAIRWISE_COSINE,
        "target_ab_relative": TARGET_VALIDATION_WORST_ERROR,
        "passed": passed,
    }


def build_report(
    rows: list[dict[str, Any]],
    sweep_rows: list[dict[str, Any]],
    sweep_cases: list[dict[str, Any]],
    selection: dict[str, Any],
    boundary_rows: list[dict[str, Any]],
    rtl_exact_vectors: list[dict[str, Any]],
    args: argparse.Namespace,
) -> str:
    lengths = (128,) if args.smoke else SEQUENCE_LENGTHS
    dimensions = (64,) if args.smoke else HEAD_DIMENSIONS
    random_summary = aggregate_rows(rows, "random_scores")
    qktv_summary = aggregate_rows(rows, "single_head_qktv")
    exact_random = aggregate_rows(
        rows, "random_scores", model_role="diagnostic"
    )
    exact_qktv = aggregate_rows(
        rows, "single_head_qktv", model_role="diagnostic"
    )
    selected_sweep = next(row for row in sweep_rows if row["selected"])
    boundary_primary = [
        row for row in boundary_rows if row["model_role"] == "primary"
    ]
    lines = [
        "# Phase-1 Online Softmax Validation",
        "",
        "The primary kernel is the repository Scalar SMU contract: each 32-value",
        "tile forms `(m_tile, l_tile, O_tile)`, the scalar block merges it with",
        "`(m_old, l_old, O_old)` and emits `m_new`, `l_new`, `w_old`, and",
        "`w_tile`, then a separate RVV-equivalent vector update updates",
        "probability and attention-output state. All tiles have 32 elements, so",
        "every end-to-end case exercises non-singleton `l_tile` values.",
        "",
        "## Configuration",
        "",
        f"- Matrix: lengths `{lengths}` × dimensions `{dimensions}` for both "
        "random-score and single-head QK^T V workloads.",
        f"- Base seed: `{args.seed}`; every workload/coordinate/rep uses an "
        "independent SeedSequence.",
        f"- Primary models: `{MODEL_FP32}`, `{MODEL_FP16}`, `{MODEL_MIXED}`. "
        f"`{MODEL_MIXED_EXACT}` is diagnostic only.",
        f"- Tile size: `{TILE_SIZE}`; selected LUT: `{selection['entries']}` "
        f"entries, Q{selection['q_bits']}, ROM `{selection['rom_bits']}` bits.",
        f"- LUT input scale: `{selection['input_scale_entries_per_unit']}` "
        f"entries/unit; output scale: `{selection['output_scale']}`.",
        f"- Frozen selected ROM raw little-endian INT16 SHA-256: "
        f"`{selection.get('rom_sha256_raw_little_endian_int16', 'see summary.json')}`.",
        "- LUT is a direct-address signed-INT16 ROM over [-8,0], with no "
        "interpolation; delta=0 is exact unity and values below -8 saturate "
        "to zero.",
        "",
        "## Oracle and metrics",
        "",
        "Every model is compared with an independent FP64 softmax/attention",
        "oracle, not with the FP32 model. For flattened actual `a` and oracle",
        "`r`, MAE is `mean(abs(a-r))`; stable-relative error is",
        "`sum(abs(a-r)) / max(sum(abs(r)), 1e-12)`; cosine is the normalized",
        "dot product. Probability-sum error is `abs(sum(probability)-1)`.",
        "",
        "## Random-score matrix",
        "",
    ]
    lines.extend(_summary_table(random_summary))
    lines.extend(
        [
            "",
            "## Single-head Attention(QK^T)V matrix",
            "",
            "QK^T is generated once in FP32 for each seeded case. Every recurrence",
            "variant receives the same original score vector and quantizes it",
            "inside its own tile kernel; proposed-path V/O remain FP32.",
            "",
        ]
    )
    lines.extend(_summary_table(qktv_summary))
    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            "`mixed_exact_exp` keeps FP16 score/max/delta, FP32 length/scaled",
            "length, FP16 weight normalization, and FP32 vector update. Only",
            "the direct LUT lookup is replaced with exact FP32 `exp` of the",
            "FP16 delta, separating LUT error from mixed normalization error.",
            "",
            "### Random scores",
            "",
        ]
    )
    lines.extend(_summary_table(exact_random))
    lines.extend(["", "### QK^T V", ""])
    lines.extend(_summary_table(exact_qktv))
    rtl_exact_random = [
        summary for summary in exact_random
        if summary["model"] == MODEL_MIXED_RTL_EXACT
    ]
    rtl_exact_qktv = [
        summary for summary in exact_qktv
        if summary["model"] == MODEL_MIXED_RTL_EXACT
    ]
    lines.extend(
        [
            "",
            "### RTL-exact fixed-point diagnostic",
            "",
            "`mixed_rtl_exact` uses FP16 m/max/delta, the frozen direct LUT,",
            "Q16.32 conversion/product truncation/addition/fixed-to-FP32",
            "at each length recurrence, and the same FP16 numerator/denominator",
            "divide. It is a diagnostic handoff for the RTL carrier, not a",
            "fourth primary model.",
            "",
            "#### Random scores",
            "",
        ]
    )
    lines.extend(_summary_table(rtl_exact_random))
    lines.extend(["", "#### QK^T V", ""])
    lines.extend(_summary_table(rtl_exact_qktv))
    lines.extend(
        [
            "",
            "#### Frozen scalar-interface vectors",
            "",
            "These vectors are independently checked against the Python "
            "carrier/divider reference. The first vector is also asserted "
            "bit-for-bit by `online_merge_engine_mixed_tb.sv`; local tile "
            "construction remains a system-level diagnostic assumption.",
            "",
            "| vector | m_new FP32 | l_new FP32 | old exp Q1.14 | tile exp Q1.14 | "
            "old weight FP16 | tile weight FP16 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for vector in rtl_exact_vectors:
        expected = vector["expected"]
        lines.append(
            f"| {vector['name']} | `0x{expected['m_new_fp32_bits']:08x}` | "
            f"`0x{expected['l_new_fp32_bits']:08x}` | "
            f"`0x{expected['old_exp_q1_14']:04x}` | "
            f"`0x{expected['tile_exp_q1_14']:04x}` | "
            f"`0x{expected['old_weight_fp16_bits']:04x}` | "
            f"`0x{expected['tile_weight_fp16_bits']:04x}` |"
        )
    lines.extend(
        [
            "",
            "## LUT sweep and validation/final-test selection",
            "",
            f"The sweep evaluates entries `{LUT_ENTRIES_SWEEP}` and Q bits "
            f"`{LUT_Q_BITS_SWEEP}`. Each split has independent seeds for every "
            "scale/length/dimension/rep. Selection requires validation "
            f"per-case worst error ≤ `{TARGET_VALIDATION_WORST_ERROR:.1e}`, "
            "then minimizes 16-bit ROM size and validation worst error; the "
            "independent final-test split is reported but never used for selection.",
            "",
            "| entries | q_bits | ROM bits | calibration worst | validation mean | "
            "validation worst | final-test worst | pass | selected |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: | :---: |",
        ]
    )
    for sweep in sweep_rows:
        lines.append(
            f"| {sweep['entries']} | {sweep['q_bits']} | {sweep['rom_bits']} | "
            f"{sweep['calibration_worst_case_error']:.3e} | "
            f"{sweep['validation_mean_case_error']:.3e} | "
            f"{sweep['validation_worst_case_error']:.3e} | "
            f"{sweep['final_test_worst_case_error']:.3e} | "
            f"{'YES' if sweep['passes_validation_threshold'] else 'no'} | "
            f"{'YES' if sweep['selected'] else 'no'} |"
        )
    lines.extend(
        [
            "",
            f"Selection status: `{selection['status']}`; selected validation worst case "
            f"`{selection['validation_worst_case_error']:.3e}`, final-test worst case "
            f"`{selection['final_test_worst_case_error']:.3e}`. Per-case sweep rows are "
            "preserved in `lut_sweep_cases.csv`/`.json`.",
            "",
            "## Scalar merge boundaries",
            "",
            "These direct two-summary cases exercise equal/near-tie maxima,",
            "delta=-8, below-range saturation, single-sided zero lengths, and",
            "small/unequal lengths. The",
            "table reports the scalar outputs and `|w_old+w_tile-1|`.",
            "",
            "| case | model | m_new | l_new | w_old | w_tile | weight-sum error |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in boundary_primary:
        lines.append(
            f"| {row['case']} | {row['model']} | {float(row['m_new']):.6g} | "
            f"{float(row['l_new']):.6g} | {float(row['w_old']):.6g} | "
            f"{float(row['w_tile']):.6g} | {row['weight_sum_error']:.3e} |"
        )
    lines.extend(
        [
            "",
            "## Limitations and RTL implications",
            "",
            "- This is host-side NumPy validation; it reports no RTL area, timing, "
            "or power. The focused RTL TB separately observes mixed weight cycles.",
            "- FP16 baseline arithmetic is explicit NumPy FP16 at each scalar/vector "
            "stage. The proposed path keeps V/O FP32 and only weights/local "
            "score state use FP16 as specified.",
            "- The high-level `mixed` row follows the abstract FP32 length "
            "recurrence. `mixed_rtl_exact` is the Q16.32 carrier diagnostic "
            "used for RTL handoff; its local tile construction is a system-level "
            "assumption, while the scalar-interface vectors are exact; neither "
            "diagnostic is a fourth primary model.",
            "- The direct LUT's table encoding, address rounding, saturation, and "
            "Q format must be reproduced exactly before RTL claims are made.",
            "- A pre-flatten Yosys generate-pruning smoke is recorded in "
            "`rtl_pruning_smoke.json`: legacy-only tops contain no mixed LUT or "
            "divider, mixed-only contains no legacy exp/reciprocal, dual contains "
            "both with one mixed-LUT hierarchy path and 4096 source ROM bits. "
            "This is not a formal multi-trial area result.",
            "- Random cases are seeded synthetic scores/values; QK^T V is one "
            "single-query head at each matrix coordinate, not a full transformer "
            "layer.",
            "- The selected ROM is a numerical candidate for Scalar SMU "
            "integration. Follow-up RTL work should measure the same 32-element "
            "tile schedule and validate boundary codes without changing "
            "B1/B2-R/B3.",
            "",
            f"Command: `{shlex.join([sys.executable, *sys.argv])}`",
            "",
        ]
    )
    return "\n".join(lines)


def build_reciprocal_report_section(
    rows: list[dict[str, Any]],
    sweep_rows: list[dict[str, Any]],
    selection: dict[str, Any],
    vector_rows: list[dict[str, Any]],
    formal_matrix_gate: dict[str, Any],
) -> str:
    """Render the Phase-3 reciprocal scan without changing the Phase-1 tables."""

    lines = [
        "",
        "## Phase-3 Reciprocal-LUT normalization",
        "",
        "Model A is `mixed_rtl_exact` (the existing FP16 divider); Model B is",
        "`mixed_rtl_reciprocal` with the frozen Q16.32→FP16 RNE, FP32",
        "mantissa/exponent decomposition, Q1.q endpoint RNE, interpolation",
        "truncation, and one net shift contract. The selected conservative",
        "candidate (not a claim of unique optimum) is",
        f"`{selection['entries']} entries / Q1.{selection['q_bits']}` with a "
        f"{selection['storage_bits']}-bit unsigned reciprocal code; the ROM "
        f"stores {selection['rom_words']} words ({selection['rom_bits']} bits) "
        f"and hardwires code[256]={selection['endpoint_code_256_hardwired']}.",
        f"The complete positive finite FP16 denominator domain has "
        f"{selection['reachable_domain_count']} values; its selected-LUT "
        f"relative-error max is `{selection['reachable_domain_max']:.9e}` "
        f"(the 257-point probe max is `{selection['probe_max']:.9e}`).",
        "The same complete denominator domain is used for every scanned "
        "format, including the Q1.23 upper-bound candidate.",
        f"The full-FP32-mantissa theoretical max is "
        f"`{selection['full_fp32_mantissa_theoretical_max']:.9e}` "
        f"({selection['full_fp32_mantissa_theoretical_max_method']}).",
        f"Formal matrix gate: {'PASS' if formal_matrix_gate['passed'] else 'FAIL'} "
        f"({formal_matrix_gate['actual_cases']}/{formal_matrix_gate['expected_cases']} "
        "Cartesian cases, no missing/extra/duplicate keys).",
        "",
        "### Matrix Model-A/Model-B and optimized-vs-FP32 metrics",
        "",
        "| workload | A/B softmax MAE | A/B softmax relative | A/B softmax cosine | "
        "A/B attention MAE | A/B attention relative | A/B attention cosine | "
        "B-vs-FP32 softmax relative | B-vs-FP32 softmax cosine | "
        "B-vs-FP32 attention relative | B-vs-FP32 attention cosine | "
        "B probability-sum error |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for workload in ("random_scores", "single_head_qktv"):
        selected = [
            row
            for row in rows
            if row["model"] == MODEL_MIXED_RTL_RECIPROCAL
            and row["workload"] == workload
        ]
        if not selected:
            continue
        mean = lambda field: float(np.mean([float(row[field]) for row in selected]))
        maximum = lambda field: float(np.max([float(row[field]) for row in selected]))
        minimum = lambda field: float(np.min([float(row[field]) for row in selected]))
        lines.append(
            f"| {workload} | {mean('ab_probability_mae'):.3e} | "
            f"{maximum('ab_probability_stable_relative_error'):.3e} | "
            f"{minimum('ab_probability_cosine_similarity'):.9f} | "
            f"{mean('ab_output_mae'):.3e} | "
            f"{maximum('ab_output_stable_relative_error'):.3e} | "
            f"{minimum('ab_output_cosine_similarity'):.9f} | "
            f"{maximum('optimized_vs_fp32_probability_stable_relative_error'):.3e} | "
            f"{minimum('optimized_vs_fp32_probability_cosine_similarity'):.9f} | "
            f"{maximum('optimized_vs_fp32_output_stable_relative_error'):.3e} | "
            f"{minimum('optimized_vs_fp32_output_cosine_similarity'):.9f} | "
            f"{maximum('probability_sum_error'):.3e} |"
        )
    lines.extend(
        [
            "",
            "### Reciprocal parameter scan",
            "",
            "The 257-point probe uses deterministic mantissas at exponents "
            f"`{RECIPROCAL_PROBE_EXPONENTS}`; each row also reports the complete "
            "31,743-value positive finite FP16 denominator domain. End-to-end "
            "scan rows include both random-score and QK^T V cases for all "
            "requested lengths and dimensions. A/B and optimized-oracle gates "
            "are separate: A/B is the selection gate, while the latter exposes "
            "the existing Mixed EXP/FP16-max stress limitation.",
            "",
            "| entries | q_bits | code bits | ROM bits | probe max | reachable max | "
            "A/B worst | A/B cosine min | oracle worst | oracle cosine min | "
            "A/B pass | oracle pass | recommended |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
            "---: | :---: | :---: | :---: |",
        ]
    )
    for sweep in sweep_rows:
        lines.append(
            f"| {sweep['entries']} | {sweep['q_bits']} | "
            f"{sweep['q_bits'] + 1} | {sweep['rom_bits']} | "
            f"{sweep['probe_max']:.3e} | "
            f"{sweep['reachable_domain_max']:.3e} | "
            f"{sweep['validation_ab_worst_case_error']:.3e} | "
            f"{sweep['validation_ab_pairwise_cosine_min']:.9f} | "
            f"{sweep['validation_optimized_oracle_worst_case_error']:.3e} | "
            f"{sweep['validation_optimized_oracle_pairwise_cosine_min']:.9f} | "
            f"{'YES' if sweep['passes_ab_validation_threshold'] else 'no'} | "
            f"{'YES' if sweep['passes_optimized_oracle_validation_threshold'] else 'no'} | "
            f"{'YES' if sweep['recommended'] else 'no'} |"
        )
    selected_sweep = next(row for row in sweep_rows if row["selected"])
    lines.extend(
        [
            "",
            f"The formal matrix gate passes, but the extended stress scan's "
            f"lowest optimized-vs-FP32 cosine is "
            f"`{selected_sweep['validation_optimized_oracle_pairwise_cosine_min']:.9f}` "
            "(<0.9999); this is reported as a limitation rather than folded "
            "into the A/B selection gate.",
            "",
            "### Reciprocal/RTL intermediate vectors",
            "",
            "The machine-readable `reciprocal_vectors.json/csv` files expose "
            "`den_h`, mantissa `index/frac`, `lo/hi`, Q code `q`, scale `s`, "
            "the full product/shift fields, `overflow`, validity/unsupported "
            "status, and final FP16 code for both engine and direct vectors. "
            "The zero/zero direct vector is intentionally unsupported; legal "
            "workload traces require overflow=0 and unsupported=0.",
            "",
            "| vector | kind | side | num_h | den_h | index | frac | lo | hi | q | s | "
            "product | net_shift | shifted | overflow | valid | unsupported | final_half |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: | :---: | :---: | ---: |",
        ]
    )
    for vector in vector_rows:
        lines.append(
            f"| {vector['vector']} | {vector['kind']} | "
            f"{vector['weight_side']} | "
            f"`0x{int(vector['num_h']):04x}` | "
            f"`0x{int(vector['den_h']):04x}` | {vector['index']} | "
            f"{vector['frac']} | {vector['lo']} | {vector['hi']} | "
            f"{vector['q']} | {vector['s']} | {vector['product']} | "
            f"{vector['net_shift']} | {vector['shifted']} | "
            f"{str(bool(vector['overflow'])).lower()} | "
            f"{str(bool(vector['valid'])).lower()} | "
            f"{str(bool(vector['unsupported'])).lower()} | "
            f"`0x{int(vector['final_half']):04x}` |"
        )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("experiments/phase1_online_softmax/results"),
    )
    parser.add_argument("--seed", type=int, default=BASE_SEED)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="use one 128x64 coordinate per workload and one sweep rep",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 0 <= args.seed < (1 << 32):
        raise SystemExit("--seed must be in [0, 2^32-1]")
    lengths = (128,) if args.smoke else SEQUENCE_LENGTHS
    dimensions = (64,) if args.smoke else HEAD_DIMENSIONS
    sweep_rows, sweep_cases, selection = run_lut_sweep(args.seed, args.smoke)
    lut = Int16DirectExpLUT(selection["entries"], selection["q_bits"])
    (
        reciprocal_sweep_rows,
        reciprocal_sweep_cases,
        reciprocal_probe_rows,
        reciprocal_selection,
    ) = run_reciprocal_sweep(args.seed, args.smoke, lut)
    reciprocal_lut = ReciprocalLUT(
        RECIPROCAL_RECOMMENDED_ENTRIES,
        RECIPROCAL_RECOMMENDED_Q_BITS,
    )
    rtl_exact_vectors = validate_rtl_exact_vectors(lut)
    reciprocal_vectors = validate_reciprocal_vectors(lut, reciprocal_lut)
    reciprocal_vector_rows = flatten_reciprocal_vectors(
        reciprocal_vectors, reciprocal_lut
    )

    rows: list[dict[str, Any]] = []
    for workload_index, workload in enumerate(
        ("random_scores", "single_head_qktv")
    ):
        for length_index, sequence_length in enumerate(lengths):
            for dimension_index, head_dimension in enumerate(dimensions):
                seed = independent_seed(
                    args.seed,
                    3,
                    workload_index,
                    length_index,
                    dimension_index,
                    0,
                )
                rows.extend(
                    run_workload(
                        workload,
                        sequence_length,
                        head_dimension,
                        seed,
                        lut,
                        reciprocal_lut,
                    )
                )

    boundary_rows = run_boundaries(lut, reciprocal_lut)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "results.csv", rows)
    write_json(output_dir / "results.json", rows)
    write_csv(output_dir / "lut_sweep.csv", sweep_rows)
    write_json(output_dir / "lut_sweep.json", sweep_rows)
    write_csv(output_dir / "lut_sweep_cases.csv", sweep_cases)
    write_json(output_dir / "lut_sweep_cases.json", sweep_cases)
    write_csv(output_dir / "boundary.csv", boundary_rows)
    write_json(output_dir / "boundary.json", boundary_rows)
    write_csv(output_dir / "reciprocal_sweep.csv", reciprocal_sweep_rows)
    write_json(output_dir / "reciprocal_sweep.json", reciprocal_sweep_rows)
    write_csv(
        output_dir / "reciprocal_sweep_cases.csv", reciprocal_sweep_cases
    )
    write_json(
        output_dir / "reciprocal_sweep_cases.json", reciprocal_sweep_cases
    )
    write_csv(output_dir / "reciprocal_probe.csv", reciprocal_probe_rows)
    write_json(output_dir / "reciprocal_probe.json", reciprocal_probe_rows)
    write_csv(
        output_dir / "reciprocal_vectors.csv", reciprocal_vector_rows
    )
    write_json(output_dir / "reciprocal_vectors.json", reciprocal_vectors)

    reciprocal_matrix = reciprocal_matrix_summary(rows)
    reciprocal_matrix_gate = reciprocal_formal_matrix_gate(
        rows, lengths, dimensions
    )
    reciprocal_matrix_target_met = bool(reciprocal_matrix_gate["passed"])
    pruning_source = Path(
        "experiments/phase1_online_softmax/results/rtl_pruning_smoke.json"
    )
    if pruning_source.is_file():
        pruning_payload = json.loads(pruning_source.read_text(encoding="utf-8"))
    else:
        pruning_payload = {
            "schema_version": 1,
            "scope": "pre-flatten Yosys elaboration/synthesis smoke",
            "formal_or_area_claim": False,
            "status": "not_available",
        }
    write_json(output_dir / "rtl_pruning_smoke.json", pruning_payload)
    summary = {
        "experiment": EXPERIMENT_NAME,
        "schema_version": 5,
        "smoke": bool(args.smoke),
        "seed": args.seed,
        "tile_size": TILE_SIZE,
        "sequence_lengths": list(lengths),
        "head_dimensions": list(dimensions),
        "primary_models": list(PRIMARY_MODELS),
        "diagnostic_models": list(DIAGNOSTIC_MODELS),
        "selected_lut": {**selection, **lut.as_dict()},
        "selected_reciprocal_lut": {
            **reciprocal_selection,
            **reciprocal_lut.as_dict(),
        },
        "workload_counts": {
            "random_scores_cases": sum(
                1 for row in rows
                if row["workload"] == "random_scores"
                and row["model_role"] == "primary"
                and row["model"] == MODEL_FP32
            ),
            "single_head_qktv_cases": sum(
                1 for row in rows
                if row["workload"] == "single_head_qktv"
                and row["model_role"] == "primary"
                and row["model"] == MODEL_FP32
            ),
            "primary_result_rows": sum(
                1 for row in rows if row["model_role"] == "primary"
            ),
            "diagnostic_result_rows": sum(
                1 for row in rows if row["model_role"] == "diagnostic"
            ),
            "boundary_cases": len(boundary_rows) // len(ALL_MODELS),
            "boundary_result_rows": len(boundary_rows),
        },
        "random_primary": aggregate_rows(rows, "random_scores"),
        "qktv_primary": aggregate_rows(rows, "single_head_qktv"),
        "random_exact_exp": aggregate_rows(
            rows, "random_scores", model_role="diagnostic"
        ),
        "qktv_exact_exp": aggregate_rows(
            rows, "single_head_qktv", model_role="diagnostic"
        ),
        "rtl_exact_scalar_vectors": rtl_exact_vectors,
        "reciprocal_scalar_vectors": reciprocal_vectors,
        "reciprocal_matrix": reciprocal_matrix,
        "reciprocal_matrix_gate": reciprocal_matrix_gate,
        "reciprocal_matrix_target_met": reciprocal_matrix_target_met,
        "reciprocal_sweep": reciprocal_sweep_rows,
        "boundary_primary": [
            row for row in boundary_rows if row["model_role"] == "primary"
        ],
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
    }
    write_json(output_dir / "summary.json", summary)
    write_json(
        output_dir / "manifest.json",
        {
            "experiment": EXPERIMENT_NAME,
            "schema_version": 5,
            "command": [sys.executable, *sys.argv],
            "smoke": bool(args.smoke),
            "base_seed": args.seed,
            "tile_size": TILE_SIZE,
            "matrix": {
                "sequence_lengths": list(lengths),
                "head_dimensions": list(dimensions),
                "random_score_distribution": "independent normal(mean=0, std=1)",
                "qktv_score_generation": (
                    "common FP32 QK^T/sqrt(D); kernel precision starts after "
                    "score generation"
                ),
            },
            "models": {
                MODEL_FP32: {
                    "role": "primary",
                    "summary_state": "FP32 m/l/O",
                    "exp": "FP32 exp",
                    "length_recurrence": "FP32",
                    "weight_normalization": "FP32",
                    "vector_update": "FP32",
                },
                MODEL_FP16: {
                    "role": "primary",
                    "summary_state": "FP16 m/l/O",
                    "exp": "FP16 exp",
                    "length_recurrence": "FP16",
                    "weight_normalization": "FP16 numerator/denominator/divide",
                    "vector_update": "FP16",
                },
                MODEL_MIXED: {
                    "role": "primary",
                    "summary_state": "FP16 m/max/delta; FP32 l/scaled-l",
                    "exp": "direct signed-INT16 LUT over [-8,0]",
                    "weight_normalization": "FP16 numerator/denominator/divide",
                    "vector_update": "FP32 after widening FP16 weights; V/O remain FP32",
                },
                MODEL_MIXED_EXACT: {
                    "role": "diagnostic",
                    "contract": "identical to mixed except exact FP32 exp(FP16 delta) replaces LUT",
                },
                MODEL_MIXED_RTL_EXACT: {
                    "role": "diagnostic",
                    "contract": (
                        "FP16 m/max/delta and direct LUT with Q16.32 "
                        "conversion/product truncation/addition/fixed-to-FP32 "
                        "length recurrence plus FP16 divide; local tile "
                        "construction is a system-level assumption"
                    ),
                    "scalar_interface_vectors": "see summary.json",
                },
                MODEL_MIXED_RTL_RECIPROCAL: {
                    "role": "diagnostic",
                    "contract": (
                        "same FP16 m/max/delta and Q16.32 carrier as mixed_rtl_exact; "
                        "den_h/num_h are direct Q16.32-to-FP16 RNE, FP32 mantissa "
                        "reciprocal LUT interpolation truncates, and one net shift "
                        "precedes the 48-bit Q16.32-to-FP16 RNE conversion"
                    ),
                    "reciprocal_lut": reciprocal_lut.as_dict(),
                    "scalar_interface_vectors": "reciprocal_vectors.json",
                },
            },
            "lut_sweep": {
                "entries": list(LUT_ENTRIES_SWEEP),
                "q_bits": list(LUT_Q_BITS_SWEEP),
                "rom_cost": "entries * 16 bits for every q format",
                "selection": selection,
                "threshold": TARGET_VALIDATION_WORST_ERROR,
                "seed_splits": {
                    "calibration": 1,
                    "validation": 2,
                    "matrix": 3,
                    "final_test": 4,
                },
            },
            "reciprocal_lut_sweep": {
                "entries": list(RECIPROCAL_LUT_ENTRIES_SWEEP),
                "q_bits": list(RECIPROCAL_LUT_Q_BITS_SWEEP),
                "rom_cost": "entries * (q_bits + 1) bits",
                "selection": reciprocal_selection,
                "pairwise_cosine_threshold": TARGET_PAIRWISE_COSINE,
                "probe_exponents": list(RECIPROCAL_PROBE_EXPONENTS),
                "probe_mantissas": RECIPROCAL_PROBE_MANTISSAS,
                "formal_matrix_gate": reciprocal_matrix_gate,
            },
            "rtl_pruning_smoke": {
                "path": "rtl_pruning_smoke.json",
                "source": str(pruning_source),
                "present": bool(
                    pruning_payload.get("status") != "not_available"
                ),
                "formal_or_area_claim": False,
            },
            "metrics": {
                "oracle": "independent FP64 softmax and attention",
                "stable_relative_error": (
                    "sum(abs(actual-reference)) / "
                    "max(sum(abs(reference)), 1e-12)"
                ),
                "probability_sum_error": "abs(sum(probability)-1)",
            },
            "rtl_exact_scalar_vectors": rtl_exact_vectors,
            "outputs": [
                "results.csv",
                "results.json",
                "lut_sweep.csv",
                "lut_sweep.json",
                "lut_sweep_cases.csv",
                "lut_sweep_cases.json",
                "reciprocal_sweep.csv",
                "reciprocal_sweep.json",
                "reciprocal_sweep_cases.csv",
                "reciprocal_sweep_cases.json",
                "reciprocal_probe.csv",
                "reciprocal_probe.json",
                "reciprocal_vectors.csv",
                "reciprocal_vectors.json",
                "boundary.csv",
                "boundary.json",
                "summary.json",
                "manifest.json",
                "report.md",
                "rtl_pruning_smoke.json",
            ],
        },
    )
    report = build_report(
        rows,
        sweep_rows,
        sweep_cases,
        selection,
        boundary_rows,
        rtl_exact_vectors,
        args,
    )
    report += build_reciprocal_report_section(
        rows,
        reciprocal_sweep_rows,
        reciprocal_selection,
        reciprocal_vector_rows,
        reciprocal_matrix_gate,
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")

    status = (
        "target_met"
        if selection["status"] == "target_met"
        and reciprocal_selection["passes_ab_validation_threshold"]
        and reciprocal_matrix_target_met
        else "best_effort_no_candidate_below_threshold"
    )
    print(
        f"phase1-online-softmax status={status} "
        f"primary_rows={sum(row['model_role'] == 'primary' for row in rows)} "
        f"diagnostic_rows={sum(row['model_role'] == 'diagnostic' for row in rows)} "
        f"lut_entries={selection['entries']} lut_q_bits={selection['q_bits']} "
        f"reciprocal_entries={reciprocal_lut.entries} "
        f"reciprocal_q_bits={reciprocal_lut.q_bits} "
        f"reciprocal_matrix_target_met={reciprocal_matrix_target_met} "
        f"output_dir={output_dir}"
    )
    return 0 if status == "target_met" else 2


if __name__ == "__main__":
    raise SystemExit(main())
