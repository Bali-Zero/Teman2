# PDF Chunker Performance Benchmark (wave 3)

Compares `TextChunker.chunk_by_pages` (wave 2 page-aware) against `TextChunker.semantic_chunk` on real PDFs. Contract: ratio must stay ≤ 3.0× baseline. Methodology: 3 repeats per file, median reported, ``chunk_size=1000`` / ``overlap=100``.

| File | Size | Pages | Text chars | baseline median (ms) | page-aware median (ms) | ratio | baseline chunks | page-aware chunks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `965_Profil Perseroan.pdf` | 350,157 B | 7 | 11,769 | 0.14 | 0.14 | 1.04× | 14 | 14 |
| `brochure_balizero_en.pdf` | 1,265,014 B | 7 | 6,566 | 0.07 | 0.08 | 1.10× | 11 | 15 |
| `UU Nomor 20 Tahun 2025.pdf` | 13,630,882 B | 238 | 314,720 | 3.30 | 3.24 | 0.98× | 425 | 432 |
| `PP Nomor 28 Tahun 2025.pdf` | 20,861,755 B | 383 | 533,398 | 5.28 | 5.42 | 1.03× | 681 | 710 |
| `UU_1_2023_KUHP_Baru.pdf` | 24,793,845 B | 345 | 506,752 | 5.20 | 5.25 | 1.01× | 670 | 672 |

## Summary

- Max observed ratio: **1.10×** (threshold 3.0×)
- Verdict: **PASS**
- Files benchmarked: 5
- Repeats per file (median reported): 3
