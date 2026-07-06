#!/usr/bin/env python3
"""生成并检查 vfcmacc.vv v1 寄存器布局和编码参考。"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RISC_V_INSTR = REPO_ROOT / "hw/ip/snitch/src/riscv_instr.sv"

VFCMACC_PATTERN = "111010???????????001?????1010111"
CHECK_PATTERNS = {
    "VFMACC_VV",
    "VFNMSAC_VV",
    "VFWDOTP_VV",
    "VFWDOTP_VF",
}


@dataclass(frozen=True)
class LayoutRow:
    lmul: int
    base: int
    real_range: str
    imag_range: str
    alignment: str
    in_range: str
    legal: str
    reason: str


def group_range(base: int, lmul: int) -> tuple[int, int]:
    return base, base + lmul - 1


def fmt_range(first: int, last: int) -> str:
    return f"v{first}" if first == last else f"v{first}..v{last}"


def classify_layout(base: int, lmul: int) -> LayoutRow:
    real_first, real_last = group_range(base, lmul)
    imag_first, imag_last = group_range(base + lmul, lmul)
    aligned = base % lmul == 0
    ranged = imag_last < 32

    reasons: list[str] = []
    if lmul == 8:
        reasons.append("m8-disabled-v1")
    if not aligned:
        reasons.append("misaligned-base")
    if not ranged:
        reasons.append("imag-group-out-of-range")

    return LayoutRow(
        lmul=lmul,
        base=base,
        real_range=fmt_range(real_first, real_last),
        imag_range=fmt_range(imag_first, imag_last),
        alignment="pass" if aligned else "fail",
        in_range="pass" if ranged else "fail",
        legal="legal" if not reasons else "illegal",
        reason="-" if not reasons else ",".join(reasons),
    )


def all_layout_rows() -> list[LayoutRow]:
    return [classify_layout(base, lmul) for lmul in (1, 2, 4, 8) for base in range(32)]


def pattern_to_mask_value(pattern: str) -> tuple[int, int]:
    mask = 0
    value = 0
    for bit_index, char in enumerate(reversed(pattern)):
        if char == "?":
            continue
        if char not in {"0", "1"}:
            raise ValueError(f"Unsupported pattern character {char!r}: {pattern}")
        mask |= 1 << bit_index
        if char == "1":
            value |= 1 << bit_index
    return mask, value


def patterns_overlap(pattern_a: str, pattern_b: str) -> bool:
    mask_a, value_a = pattern_to_mask_value(pattern_a)
    mask_b, value_b = pattern_to_mask_value(pattern_b)
    shared_mask = mask_a & mask_b
    return (value_a & shared_mask) == (value_b & shared_mask)


def existing_patterns(instr_file: Path) -> dict[str, str]:
    pattern_re = re.compile(
        r"localparam\s+logic\s+\[31:0\]\s+([A-Z0-9_]+)\s*=\s*32'b([01?]{32});"
    )
    patterns: dict[str, str] = {}
    for line in instr_file.read_text(encoding="utf-8").splitlines():
        match = pattern_re.search(line)
        if match:
            patterns[match.group(1)] = match.group(2)
    return patterns


def check_encoding(instr_file: Path) -> list[str]:
    patterns = existing_patterns(instr_file)
    errors: list[str] = []
    for name in sorted(CHECK_PATTERNS):
        if name not in patterns:
            errors.append(f"缺少既有 opcode pattern: {name}")
            continue
        if patterns_overlap(VFCMACC_PATTERN, patterns[name]):
            errors.append(
                f"VFCMACC_VV 与 {name} 冲突: "
                f"{VFCMACC_PATTERN} vs {patterns[name]}"
            )
    return errors


def render_markdown(rows: list[LayoutRow], instr_file: Path) -> str:
    patterns = existing_patterns(instr_file)
    legal_by_lmul = {
        lmul: sum(1 for row in rows if row.lmul == lmul and row.legal == "legal")
        for lmul in (1, 2, 4, 8)
    }
    illegal_by_lmul = {
        lmul: sum(1 for row in rows if row.lmul == lmul and row.legal == "illegal")
        for lmul in (1, 2, 4, 8)
    }

    lines = [
        "# vfcmacc.vv 寄存器布局与编码参考",
        "",
        "本文件由 `scripts/cfma_register_layout.py` 生成。寄存器布局策略以该脚本为",
        "decoder 和 ISA test 的单一来源，避免 RTL 与测试各自解释。",
        "",
        "## v1 编码决策",
        "",
        "`vfcmacc.vv` 使用 32-bit RVV OPFVV 形式：",
        "",
        "```text",
        f"VFCMACC_VV = 32'b{VFCMACC_PATTERN}",
        "funct6     = 111010",
        "vm         = instr[25]",
        "vs2        = instr[24:20]",
        "vs1        = instr[19:15]",
        "funct3     = 001 (OPFVV)",
        "vd         = instr[11:7]",
        "opcode     = 1010111 (OP-V)",
        "```",
        "",
        "正式 mnemonic 支持完成前，bring-up 应使用以下 `.insn` 形式：",
        "",
        "```asm",
        ".insn r 0x57, 0x1, 0x75, vd, vs1, vs2  # vm=1",
        "```",
        "",
        "即时冲突检查会把该 pattern 与计划中列出的当前 Snitch 生成 pattern 对比：",
        "",
        "| 既有 pattern | Pattern | 是否冲突 |",
        "| --- | --- | --- |",
    ]
    for name in sorted(CHECK_PATTERNS):
        pattern = patterns.get(name, "missing")
        overlap = (
            "缺失" if pattern == "missing" else ("是" if patterns_overlap(VFCMACC_PATTERN, pattern) else "否")
        )
        lines.append(f"| `{name}` | `32'b{pattern}` | {overlap} |")

    lines.extend(
        [
            "",
            "## v1 布局策略",
            "",
            "- `LMUL=m1/m2/m4` 在所有 base register 对齐，且成对 real+imag group",
            "  均落在 `v0..v31` 内时合法。",
            "- `LMUL=m8` 在 v1 中非法。单个复数操作数会消耗全部 32 个 vector",
            "  registers，按 v1 策略无法再留下互不重叠的 destination/source pairs。",
            "- `base % LMUL != 0` 时非法。",
            "- `base + 2 * LMUL - 1 >= 32` 时非法。",
            "- `vd` pair 与任一 source pair 重叠时，在 v1 中非法。",
            "- `vs1` pair 可以与 `vs2` pair 重叠。",
            "",
            "## 汇总",
            "",
            "| LMUL | 合法 base 数 | 非法 base 数 |",
            "| --- | ---: | ---: |",
        ]
    )
    for lmul in (1, 2, 4, 8):
        lines.append(f"| m{lmul} | {legal_by_lmul[lmul]} | {illegal_by_lmul[lmul]} |")

    lines.extend(
        [
            "",
            "## 完整 Base 表",
            "",
            "| LMUL | base | real group 范围 | imag group 范围 | 对齐结果 | 范围结果 | v1 合法性 | 非法原因 |",
            "| --- | ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        alignment = "通过" if row.alignment == "pass" else "失败"
        in_range = "通过" if row.in_range == "pass" else "失败"
        legal = "合法" if row.legal == "legal" else "非法"
        lines.append(
            f"| m{row.lmul} | v{row.base} | {row.real_range} | {row.imag_range} | "
            f"{alignment} | {in_range} | {legal} | {row.reason} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_text(rows: list[LayoutRow]) -> str:
    header = (
        "LMUL base real-group-range imag-group-range alignment-result "
        "range-result v1-legality illegal-reason"
    )
    lines = [header]
    for row in rows:
        lines.append(
            f"m{row.lmul} v{row.base} {row.real_range} {row.imag_range} "
            f"{row.alignment} {row.in_range} {row.legal} {row.reason}"
        )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write-md",
        type=Path,
        help="Write generated Markdown table to the given path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    rows = all_layout_rows()

    errors = check_encoding(RISC_V_INSTR)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.write_md:
        args.write_md.write_text(render_markdown(rows, RISC_V_INSTR), encoding="utf-8")
    print(render_text(rows))
    print(f"Encoding VFCMACC_VV=32'b{VFCMACC_PATTERN} 未发现已检查的 pattern 冲突。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
