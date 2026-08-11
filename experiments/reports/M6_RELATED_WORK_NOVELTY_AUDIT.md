# M6 Related Work and Novelty Audit

**Status:** PASS for the reviewed citation set, with the novelty statement
bounded to that set.

**Search date:** 2026-08-12.

**Scope:** This audit updates only the Related Work section and bibliography.
The title, abstract, introduction, architecture, evaluation, conclusion,
figures, active evidence, RTL, and software were not changed for M6.

## Retrieval and fallback record

The review used Crossref DOI metadata, OpenAlex work records, arXiv records,
and local author-paper full text where available. Local full text was available
only for Milakov, FlashAttention, Spatz, Softermax, SoftEx, VEXP, and
Titopoulos. TEA-S, Alexandridis, and Lai were checked only through Crossref and
OpenAlex metadata/abstract records. Fairoose was checked only through
Crossref/OpenAlex bibliographic metadata and its registered title; no Fairoose
full text or abstract was available. The web-search endpoint was also
attempted; `web__run` returned HTTP 404 (`Some("")`) before returning records.
The fallback therefore used direct Crossref REST and OpenAlex records, plus
the local full text listed above. No bibliographic fact below depends on the
failed endpoint.

The direct records identify Fairoose et al. as OpenAlex work `W7167843304` and
Lai et al. as OpenAlex work `W7136134282`. Crossref gives
`given=Shareefa Fairoose`, `family=P.`; OpenAlex display is
`Shareefa Fairoose P.`. BibTeX uses `Fairoose P., Shareefa and Mishra, Ashutosh` as a
deliberate rendering choice for IEEE output `S. Fairoose P.`; this does not
claim to reproduce the Crossref field split. Crossref confirms Fairoose DOI
`10.1109/TVLSI.2026.3706101`, pages 1--13, and registered title. Crossref
confirms Lai DOI `10.1109/JIOT.2026.3671312`, volume 13, issue 12, and pages
25890--25901.

## Citation verification

All 11 bibliographic identities are verified; claim-level verification uses the
source tiers listed below. The nine pre-existing entries retain their existing
keys; the last two are the M6 additions.

| Key | Work and venue record | Verification sources | Status |
|---|---|---|---|
| `milakov2018online` | Milakov and Gimelshein, *Online Normalizer Calculation for Softmax*, arXiv:1805.02867 (2018) | arXiv, OpenAlex, local full text | VERIFIED |
| `dao2022flashattention` | Dao et al., *FlashAttention*, NeurIPS 35, 16344--16359 (2022) | Crossref, OpenAlex, arXiv, local full text | VERIFIED |
| `spatz2023` | Perotti et al., *Spatz*, IEEE TCAD 44(7), 2488--2502 (2025), DOI 10.1109/TCAD.2025.3528349 | Crossref, OpenAlex, local full text | VERIFIED |
| `softermax2021` | Stevens et al., *Softermax*, DAC, 469--474 (2021), DOI 10.1109/DAC18074.2021.9586134 | Crossref, OpenAlex, local full text | VERIFIED |
| `teas2023` | Mei et al., *TEA-S*, IEEE TCAS-II 70(9), 3594--3598 (2023), DOI 10.1109/TCSII.2023.3265710 | Crossref, OpenAlex metadata/abstract | VERIFIED |
| `softex2025` | Belano et al., *A Flexible Template for Edge Generative AI*, IEEE JETCAS 15(2), 200--216 (2025), DOI 10.1109/JETCAS.2025.3562734 | Crossref, OpenAlex, local full text | VERIFIED |
| `alexandridis2025expmul` | Alexandridis et al., *Low-Cost FlashAttention with Fused Exponential and Multiplication Hardware Operators*, ISVLSI, 1--6 (2025), DOI 10.1109/ISVLSI65124.2025.11130263 | Crossref, OpenAlex metadata/abstract | VERIFIED |
| `vexp2025` | Wang et al., *VEXP*, ARITH, 37--44 (2025), DOI 10.1109/ARITH64983.2025.00016 | Crossref, OpenAlex, local full text | VERIFIED |
| `titopoulos2026vectorized` | Titopoulos et al., *Vectorized FlashAttention with Low-Cost Exponential Computation in RISC-V Vector Processors*, J. Supercomput. 82(4), Art. no. 189 (2026), DOI 10.1007/s11227-026-08322-x | Crossref, OpenAlex, Springer metadata, local full text | VERIFIED |
| `fairoose2026parallel` | Fairoose P. and Mishra, *A Custom Hardware Accelerator for Softmax Function With Parallel Online Normalization*, IEEE TVLSI, early access, 1--13 (2026), DOI 10.1109/TVLSI.2026.3706101 | Crossref, OpenAlex `W7167843304` metadata only | VERIFIED |
| `lai2026rvvsoftmax` | Lai et al., *RISC-V Vectorized Softmax Acceleration for IoT Edge Inference Systems*, IEEE IoT Journal 13(12), 25890--25901 (2026), DOI 10.1109/JIOT.2026.3671312 | Crossref, OpenAlex `W7136134282` metadata/abstract | VERIFIED |

`refs.bib` contains 11 unique keys. The `{RISC-V}` title protection is
preserved, and the Titopoulos entry records `Art. no. 189` without duplicating
page information.

## Novelty matrix

The matrix uses the paper's three-property boundary. “No” for the RVV column
means no reuse of the existing RVV datapath for the regular $O[D]$ update; it
does not deny that a work may use another vector datapath.

| Candidate | Full/broad accelerator? | Scalar-recurrence-only specialization? | Reuses existing RVV for $O[D]$? | Cluster-local/TCDM handoff? | Notes/source ID |
|---|---|---|---|---|---|
| Softermax | YES | NO | NO | Not established | Broad hardware/software Softmax co-design; `softermax2021` |
| TEA-S | YES | NO | Not established | Not established | PLAC-based full Softmax; `teas2023` |
| ITA (screened) | YES | NO | NO | Not established | Screened DOI `10.1109/ISLPED58423.2023.10244348` |
| SoftEx | YES | NO | NO | YES | Cluster-local/shared-TCDM full Softmax/GELU HWPE; `softex2025` |
| Fairoose 2026 | YES | NO | Not established | Not established | Full Softmax accelerator with parallel online normalization; `fairoose2026parallel` |
| FuseMax (screened) | YES | NO | NO | Not established | Screened DOI `10.1109/MICRO61859.2024.00107` |
| Alexandridis 2025 | YES | NO | NO | Not established | Custom FlashAttention exponential/multiplication hardware; `alexandridis2025expmul` |
| VEXP | NO, ISA extension | NO | NO | NO | Core-local BF16 scalar/SIMD exponential ISA extension, not RVV and not a separate recurrence engine; `vexp2025` |
| Titopoulos 2026 | NO, programmable/vector | NO | YES | Not established | Standard RVV instructions and no custom instructions; `titopoulos2026vectorized` |
| Lai 2026 | NO, software vectorization | NO | YES | NO | Standard RVV intrinsics and explicitly no specialized accelerator; `lai2026rvvsoftmax` |
| Proposed | NO, selective engine | YES | YES | YES | Scalar SMU only for the state-dependent merge recurrence, TCDM-mediated handoff, existing RVV update; active M2/M4 evidence |

SoftEx is the cluster-local/TCDM “yes” among the full-Softmax rows, but it
still accelerates full Softmax/GELU and does not reuse the existing RVV update
path. Titopoulos and Lai reuse RVV, but neither supplies a dedicated scalar
recurrence engine. These distinctions drive the bounded wording in the
manuscript rather than an absolute first/only claim.

## Screened but not cited

The following records were screened and retained in the audit trail, but were
not inserted into the five-page manuscript because representative coverage and
deduplication were sufficient:

- ITA, DOI `10.1109/ISLPED58423.2023.10244348`.
- FuseMax, DOI `10.1109/MICRO61859.2024.00107`.
- FLASH-D, DOI `10.1109/ISLPED65674.2025.11261805`.
- *Hardware-Oriented Online Softmax*, DOI `10.1109/ICECS66544.2025.11270517`.
- VFA, arXiv:`2604.12798`.

Omission reflects the five-page limit and representative deduplication; it
does not indicate that these works are irrelevant.

## Final novelty judgment

**PASS for the reviewed set.** No reviewed source documents a design that
combines all three targeted properties: (i) a cluster-local engine only for the
state-dependent blockwise merge recurrence, (ii) a TCDM-mediated weight
handoff, and (iii) reuse of the existing RVV datapath for the regular $O[D]$
update. This judgment is bounded to the records and screening list above.

## Manuscript integration and QA

The Related Work section now has three paragraphs and 256 prose words. It
classifies dedicated/full Softmax, full-attention hardware, and
programmable/vector approaches, then uses the evidence-bounded three-property
sentence. Only those paragraphs and the bibliography were changed for M6.

The bibliography uses the default IEEEtran size. The resulting PDF has five
pages, all 11 citations resolve, and no
undefined references or citations are present. Existing underfull-box warnings
remain, but there are no overfull boxes. `pdffonts` reports every listed font
as embedded and subsetted. Figure assets and Figure 1--3 hashes were not
changed by M6.

Final M6 file hashes:

| File | SHA256 |
|---|---|
| `paper/online-merge-smu/main.tex` | `5765996db85946239299d1071cbff77f86d855ae37576fa15c938cbed5e58685` |
| `paper/online-merge-smu/refs.bib` | `6428df11545d5da7c478d0d751da9dea236973014a82a88da682bb188b9d625a` |
| `paper/online-merge-smu/main.pdf` | `0c991a67df517c04be2772d1486c9303eaaf711acab3564305de2ff9d1cba8fe` |

Validation command:

```text
cd paper/online-merge-smu
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

The M6 scope is complete; no M7 work was started.
