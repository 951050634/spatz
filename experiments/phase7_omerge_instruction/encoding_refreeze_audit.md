# Phase 7A OMERGE Encoding Re-Freeze Audit

Audit scope is encoding selection only. No OMERGE RTL, decoder, adapter,
software, benchmark, existing ISA, or performance experiment was changed.
The audited repository revision is
40a679851a9e32e8a59793141a5be4bedccfd7c3.

## 1. Existing Decoder Pattern Inventory

The actual instruction decoder is the top-level unique casez at
hw/ip/snitch/src/snitch.sv:552, closed at line 2630. The checker
preprocesses this case for the current Spatz configuration, with
TARGET_SPATZ defined. It resolves each case label through
hw/ip/snitch/src/riscv_instr.sv and records both the generated pattern
location and the snitch decoder location.

The inventory contains 440 case-label occurrences and 440 unique
instruction names. All 440 labels resolve; unresolved labels = 0.
Top-level direct literal labels = 0. Comma/grouped labels are expanded to
one row per instruction name and retain their individual source line.

The active guard counts are always = 198 and ifdef TARGET_SPATZ = 242.
Nested field decoders at lines 776, 806, 835, 866, 901, 932, and 2731
are not additional instruction-pattern cases. The casez constructs for
next_pc and rd_select are likewise outside the instruction decoder.

decoder_pattern_inventory.csv contains:

~~~text
instruction_name, pattern, pattern_source_file,
pattern_source_location, decoder_location, guard,
generator_source_file, generator_source_location,
generator_generation_input
~~~

The generator join is name-based where a source definition exists; the
riscv_instr.sv pattern location and snitch.sv decoder location are retained
for every decoder row.

The current generated package contains 1062 localparam instruction
patterns. The current Spatz synthesis file list contains snitch.sv at
experiments/synthesis/p6-stop/cluster_bb.f:303 and explicitly selects
TARGET_SPATZ at line 17. The Bender target mechanics used by the
Spatz-cluster flow are Bender.yml:120 (target: spatz) and
util/Makefrag:73 (VLT_BENDER selects rtl, spatz, spatz_test, and
snitch_test). The actual Verilator entry is the VERILATE macro at
util/Makefrag:139, which emits the Bender file list and invokes Verilator
at lines 140--142. hw/system/spatz_cluster/Makefile:203 only generates
lint/tmp/files for lint/file-list use; it is not the Verilator build entry.
The generated synthesis file list provides the explicit TARGET_SPATZ
preprocessor define used for this audit.

## 2. Why custom-0 Is Invalid

The rejected family is:

~~~text
OMERGE rd: funct7=0000000, rs1=x0, rs2=x0, funct3=000,
          opcode=0001011 (0x0B)
pattern: 00000000000000000000?????0001011
~~~

The active FREP patterns are:

~~~text
FREP_I = ????????????????????????00001011
FREP_O = ????????????????????????10001011
~~~

The ternary intersection is nonempty with both patterns. Regression
witnesses are 0x0000000b for FREP_I and 0x0000008b for FREP_O. The
variable-rd family therefore has real overlap for both rd bit-7 values.
Case order or decode priority cannot make this encoding legal.

## 3. Collision-Checker Method

The read-only checker is
/tmp/phase7a_checker_step1.py with SHA256
fd04d0b743ecc584a2ec3ad2640f8932bcc59f0cd8198068b102d29d705fab3b.
It was invoked from the repository root as:

~~~sh
python3 /tmp/phase7a_checker_step1.py
~~~

The final CSV generation chain was:

~~~sh
python3 /tmp/phase7a_checker_step1.py
python3 /tmp/phase7a_augment.py
python3 /tmp/phase7a_augment_candidates.py
~~~

The three temporary scripts and hashes are:

~~~text
/tmp/phase7a_checker_step1.py
  fd04d0b743ecc584a2ec3ad2640f8932bcc59f0cd8198068b102d29d705fab3b
/tmp/phase7a_augment.py
  dc58b7bb6953cb21cd9777ba6da4e9786a243bac92e2ddd11623836f13b3ae58
/tmp/phase7a_augment_candidates.py
  5e659867b58be1a08a1bfe429681913eed6903818c2d78a101743db79cc1e31f
~~~

The primary checker wrote temporary decoder_inventory.csv,
generator_inventory.csv, encoding_candidates.csv,
collision_details.csv, all_rd_proof.csv, and audit_summary.json under
/tmp/phase7a_step1_outputs. phase7a_augment.py post-processed the raw
decoder inventory into decoder_pattern_inventory.csv, adding pattern
locations and generator-source joins. phase7a_augment_candidates.py
post-processed the candidate table into encoding_candidates.csv, adding
separate selected-generator and all-source columns. The final
encoding_audit_summary.json is a manually curated metadata summary made
from those outputs with apply_patch; it is not claimed to be direct
checker output or a fully automatic product.

For two 32-bit ternary patterns A and B, the intersection is nonempty iff
every bit position satisfies:

~~~text
A[i] == '?' or B[i] == '?' or A[i] == B[i]
~~~

The witness assigns a specified bit when available and assigns 0 when both
patterns are wildcards. Concrete matching compares all 32 bits of each
machine word with the same rule.

For each custom-2 and custom-3 family, the checker enumerates funct3 0..7,
funct7 0..127, rs1=x0, rs2=x0, and rd x0..x31. Thus it checks 1024
symbolic families and 32768 concrete words per opcode, 65536 words total.
The family rule and the concrete 32-word rule agree for every search row.

The checker parses every opcode source with:

~~~sh
sw/toolchain/riscv-opcodes/parse_opcodes -sverilog
~~~

The root Makefile passes the following seven names as MY_OPCODES to the
opcode-generator sub-Makefile:

~~~text
opcodes-rvv opcodes-rv32b_CUSTOM opcodes-ipu_CUSTOM
opcodes-frep_CUSTOM opcodes-dma_CUSTOM opcodes-ssr_CUSTOM
opcodes-smallfloat
~~~

Those seven additional generator inputs contain 642 definitions; they are
not the complete default ALL_OPCODES set of the sub-Makefile. A
conservative scan also parses all 46 opcodes-* files; 42 contain 1717
actual definitions after excluding @ pseudo/custom descriptors. Generic
@ lines and empty pseudo files are not instruction definitions.
The candidate shortlist below is drawn from the all-source-safe set.

## 4. Regression Validation

The custom-0 regression result is UNSAFE with overlap_count = 2:

~~~text
FREP_I: witness 0x0000000b
FREP_O: witness 0x0000008b
~~~

The custom-1 sanity family is:

~~~text
00000000000000000000?????0101011
~~~

It finds DMSRC with witness 0x0000002b. This confirms that the checker
detects an actual Xdma/custom-1 subspace rather than treating opcode names
as occupancy evidence.

Both regressions are the first rows in encoding_collision_details.csv.

## 5. custom-2 Search Results

custom-2 is opcode 1011011 (0x5B). All 1024 R-type-shaped families have
zero overlap with the active TARGET_SPATZ decoder. Generator/source results
are separated below:

| Pattern set | SAFE families | UNSAFE families | source-pattern intersection pairs |
|---|---:|---:|---:|
| Active TARGET_SPATZ decoder | 1024 | 0 | 0 |
| Seven current Makefile generator inputs | 851 | 173 | 176 |
| All opcodes-* definitions | 806 | 218 | 240 |

The current selected custom-2 definitions are the 62 IPU definitions in
opcodes-ipu_CUSTOM. The conservative scan adds two definitions from
opcodes-xpulpminmax_CUSTOM. The all-source result is used for acceptance,
so a future regeneration cannot silently consume a shortlisted family.

Concrete enumeration checked 32768 words for each of the three pattern
sets. The symbolic and concrete SAFE/UNSAFE classifications agree.

## 6. custom-3 Search Results

custom-3 is opcode 1111011 (0x7B). It has no active TARGET_SPATZ decoder
collision; its results are:

| Pattern set | SAFE families | UNSAFE families | source-pattern intersection pairs |
|---|---:|---:|---:|
| Active TARGET_SPATZ decoder | 1024 | 0 | 0 |
| Seven current Makefile generator inputs | 230 | 794 | 794 |
| All opcodes-* definitions | 0 | 1024 | 1435 |

The selected generator set contributes 20 IPU definitions. The conservative
all-source scan additionally includes six hardware-loop definitions from
opcodes-xpulphwloop_CUSTOM. Those six definitions do not cover funct3=6
or funct3=7, and the funct3=2 hardware-loop pattern covers only one
funct7 value. Together with the 20 IPU definitions, however, the combined
all-source set intersects every custom-3 R-type family for some rd.
Therefore custom-3 is not claimed to be decoder-colliding; it fails the
conservative generator-source acceptance criterion.

## 7. Other Encoding Formats

Not required. Safe custom-2 R-type families exist while preserving zero
dynamic source operands and a variable status destination. No standard,
reserved, floating-point, or vector opcode was considered, and no I-type
fallback is needed.

## 8. Safe Encoding Candidates

The table reports active decoder, current selected-generator, and
all-opcodes-source intersections independently. Each row checks all 32 rd
values. The status is based on the conservative all-source check.

| Candidate | Opcode | funct3 | funct7 | rs1 | rs2 | All 32 rd Safe? | Family Overlap | Verdict |
|---|---|---|---|---|---|---|---:|---|
| A | custom-2 / 0x5B | 000 | 0000011 (3) | x0 | x0 | Yes | 0 in all three sets | SAFE |
| B | custom-2 / 0x5B | 000 | 0000100 (4) | x0 | x0 | Yes | 0 in all three sets | SAFE |
| C | custom-2 / 0x5B | 000 | 0000110 (6) | x0 | x0 | Yes | 0 in all three sets | SAFE |

The complete 2048-family table is in encoding_candidates.csv. Its explicit
columns distinguish active_decoder_family_overlap_count,
selected_generator_family_overlap_count, and
all_source_generator_family_overlap_count.

## 9. Recommended Encoding

The recommended re-freeze is Candidate A:

~~~text
Instruction: OMERGE rd
Format:      R-type custom
opcode:      1011011
opcode hex:  0x5B
funct3:      000
funct7:      0000011
rs1:         x0
rs2:         x0
rd:          completion/status destination
~~~

Bit layout:

~~~text
31 ... 25   0000011   funct7
24 ... 20   00000     rs2=x0
19 ... 15   00000     rs1=x0
14 ... 12   000       funct3
11 ...  7   ?????     rd
 6 ...  0   1011011   custom-2 opcode
~~~

This candidate is proven safe against the active TARGET_SPATZ decoder and
against every actual instruction definition found in all opcodes-* source
files. It preserves the required zero-source-operand architectural
semantics.

## 10. Machine Words

The base word and variable-rd formula are:

~~~text
base = 0x0600005B
instruction = 0x0600005B | (rd << 7)
~~~

Concrete words:

| Assembly spelling | rd | Machine word |
|---|---:|---:|
| OMERGE x0 | 0 | 0x0600005B |
| OMERGE a0 | 10 | 0x0600055B |
| OMERGE a1 | 11 | 0x060005DB |
| OMERGE x31 | 31 | 0x06000FDB |

encoding_rd_proof.csv contains 96 rows (32 rows each for A, B, and C).
For every row, existing decoder matches = 0, generator matches = 0,
matches after adding OMERGE = 1, and unique_omerge_after_add = 1.

## 11. Suggested .insn Form

The GNU assembler form is:

~~~asm
.insn r 0x5b, 0, 3, rd, x0, x0
~~~

Assembler sanity command:

~~~sh
riscv64-unknown-elf-as -march=rv32imafdv -mabi=ilp32d \
  -o /tmp/phase7a_asm.o /tmp/phase7a_asm.S
riscv64-unknown-elf-objcopy -O binary -j .text \
  /tmp/phase7a_asm.o /tmp/phase7a_asm.bin
od -An -tx4 -v /tmp/phase7a_asm.bin
riscv64-unknown-elf-objdump -dr /tmp/phase7a_asm.o
~~~

Tool versions are GNU assembler 2.42-1ubuntu1+6 and GNU objdump
2.42-1ubuntu1+6. The emitted words are, in order,
0x0600005B, 0x0600055B, 0x060005DB, and 0x06000FDB. objdump prints each
as .insn 4 with the literal word because no OMERGE mnemonic has been added;
this is expected and is not the collision authority.

## 12. Collision Proof

The machine-readable proof artifacts are:

| Artifact | Data rows | Purpose |
|---|---:|---|
| decoder_pattern_inventory.csv | 440 | Active decoder labels and joined source locations |
| opcode_generator_inventory.csv | 1717 | All parsed opcode-source definitions |
| encoding_candidates.csv | 2048 | Complete custom-2/custom-3 family search |
| encoding_collision_details.csv | 1678 | Regression and every rejected-family witness |
| encoding_rd_proof.csv | 96 | Concrete all-rd proof for A/B/C |
| encoding_audit_summary.json | 1 object | Machine-readable audit summary |

The collision detail row breakdown is custom-0 regression = 2,
custom-1 sanity = 1, custom-2 all-source intersections = 240, and
custom-3 all-source intersections = 1435. Every rejected family has a
specific conflicting pattern and witness machine word. Candidate A, B, and
C each have zero family intersections in the active decoder, selected
generator set, and all-source generator set.

## 13. Remaining Risks

TARGET_SPATZ selection is evidenced by the generated synthesis file list
experiments/synthesis/p6-stop/cluster_bb.f:17. Bender.yml:120 selects the
spatz target, util/Makefrag:73 defines the VLT source targets, and
util/Makefrag:139 is the actual VERILATE macro entry. The command at
hw/system/spatz_cluster/Makefile:203 is only lint/file-list generation.
A different preprocessor target or a changed Bender/Verilator file list
requires rerunning the inventory.

The seven root-Makefile MY_OPCODES inputs contribute to the checked-in
riscv_instr.sv generation, but are not the complete default opcode list.
The all-source scan is intentionally stricter and includes currently
unselected opcode files to guard against future regeneration collisions.
This is why the reported current-generator and all-source SAFE counts differ.

No OMERGE implementation was started. No performance, timing, area, or
benchmark claim is made by this audit. The assembler accepts the encoding
as a raw custom instruction; the absence of an objdump mnemonic is expected.

## 14. Sol Review

Sol Max completed the unique final review with P0 = 0, P1 = 0, P2 = 3,
Verdict = PASS. The three P2 observations concerned artifact
pipeline/provenance precision, custom-3 coverage wording, and
generator/build-target wording. They were corrected in this report and
summary metadata.

Luna Max checks completed with no identified P0/P1 issue:

~~~text
pattern extraction completeness: PASS
ternary intersection and concrete enumeration: PASS
custom-0 regression: PASS
custom-1 sanity: PASS
custom-2/custom-3 exhaustive search: PASS
recommended candidate and machine-word formula: PASS
~~~

No second Sol Max invocation was made after these wording and provenance
corrections. This report authorizes no implementation work.
