#!/usr/bin/env python3
"""Verify the implemented frozen OMCFG decode without redoing Phase 8A."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


RAW_DIR = Path(__file__).resolve().parent
PHASE8B_DIR = RAW_DIR.parent
REPO_ROOT = PHASE8B_DIR.parents[1]
PHASE8A_CHECKER = (
    REPO_ROOT
    / "experiments/phase8a_omcfg_encoding_audit/raw/audit_instruction_space.py"
)
PKG_PATH = REPO_ROOT / "hw/ip/snitch/src/riscv_instr.sv"
SNITCH_PATH = REPO_ROOT / "hw/ip/snitch/src/snitch.sv"


def load_phase8a_checker():
    spec = importlib.util.spec_from_file_location(
        "phase8a_checker", PHASE8A_CHECKER
    )
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load the frozen Phase 8A parser")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    checker = load_phase8a_checker()
    package = checker.parse_package(PKG_PATH)
    _, _, labels = checker.extract_top_case_labels(
        SNITCH_PATH, r"inst_data_i", {"TARGET_SPATZ"}
    )

    omcfg = package["OMCFG"]
    omerge = package["OMERGE"]
    assert omcfg.bits == "?????????????????001000001011011"
    assert omcfg.match == 0x0000105B
    assert omcfg.mask == 0x00007FFF
    assert omerge.match == 0x0600005B
    assert omerge.mask == 0xFFFFF07F
    assert sum(label.name == "OMCFG" for label in labels) == 1
    assert sum(label.name == "OMERGE" for label in labels) == 1

    overlaps = []
    for label in labels:
        if label.name == "OMCFG":
            continue
        pattern = package[label.name]
        if checker.constraints_compatible(
            (omcfg.mask, omcfg.match), (pattern.mask, pattern.match)
        ):
            overlaps.append(label.name)
    assert not overlaps, f"OMCFG overlaps active decodes: {overlaps}"

    samples = (
        (0x0000105B, 0, 0),
        (0x0015105B, 1, 10),
        (0x002F905B, 2, 31),
        (0x00AF905B, 10, 31),
    )
    for word, cfg_id, rs1 in samples:
        assert checker.matches(word, omcfg)
        assert not checker.matches(word, omerge)
        assert word & 0x7F == 0x5B
        assert word >> 12 & 0x7 == 1
        assert word >> 7 & 0x1F == 0
        assert word >> 15 & 0x1F == rs1
        assert word >> 20 & 0xFFF == cfg_id

    print("PHASE8B_DECODE PASS")
    print(f"OMCFG match=0x{omcfg.match:08x} mask=0x{omcfg.mask:08x}")
    print(f"OMERGE match=0x{omerge.match:08x} mask=0x{omerge.mask:08x}")
    print(f"active_snitch_labels={len(labels)} symbolic_overlaps=0")
    for word, cfg_id, rs1 in samples:
        print(f"sample=0x{word:08x} cfg_id={cfg_id} rs1=x{rs1} rd=x0")


if __name__ == "__main__":
    main()
