"""Wave 3 chunker performance benchmark.

Measures ``TextChunker.chunk_by_pages`` (wave 2 page-aware) vs the
``TextChunker.semantic_chunk`` baseline on production-representative PDFs.
Asserts the page-aware path stays within ≤ 3× baseline wall-clock (wave 2
contract in WAVE2_NOTES.md — "perf fallback ≤ 3× semantic_chunk baseline").

Usage:
    PYTHONPATH=apps/backend-rag python -m backend.core.benchmarks.wave3_chunker_benchmark [PDF_PATH ...]

Without arguments, runs on the built-in candidate list resolved from
common local fixture paths. Writes a Markdown table to
``apps/backend-rag/backend/core/PERF_BENCHMARK.md`` and exits non-zero if
any ratio exceeds the 3× threshold.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

# Make the repo tree importable when invoked as a script from repo root.
_REPO_ROOT = Path(__file__).resolve().parents[5]
if str(_REPO_ROOT / "apps/backend-rag") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "apps/backend-rag"))

from backend.core.chunker import TextChunker  # noqa: E402
from backend.core.parsers import extract_text_from_pdf  # noqa: E402

# Build candidates from known PDF locations on Pro. Fallback to passed-in
# paths when these are absent (CI, Air). Mix of sizes: small (KB-realistic
# client doc), medium (regulation PDF), large (PP28), very large (KUHP).
_DEFAULT_CANDIDATES: list[Path] = [
    Path(
        "/Users/nuzantara/Desktop/nuzantara/batch4_processing/"
        "965_Profil Perseroan.pdf",
    ),
    Path(
        "/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/data/assets/"
        "brochure_balizero_en.pdf",
    ),
    Path(
        "/Users/nuzantara/Desktop/nuzantara/data/kb_sources/"
        "UU Nomor 20 Tahun 2025.pdf",
    ),
    Path(
        "/Users/nuzantara/Desktop/nuzantara/data/kb_sources/"
        "PP Nomor 28 Tahun 2025.pdf",
    ),
    Path(
        "/Users/nuzantara/Desktop/nuzantara/data/kb_sources/2026_updates/"
        "UU_1_2023_KUHP_Baru.pdf",
    ),
]


RATIO_THRESHOLD = 3.0
REPEATS = 3  # per path, to reduce JIT/IO warm-up noise


def _time_ms(fn, *args, **kwargs) -> tuple[float, object]:
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    dur_ms = (time.perf_counter() - start) * 1000.0
    return dur_ms, result


def benchmark_pdf(path: Path) -> dict:
    """Run the benchmark for one PDF and return a row dict."""
    file_bytes = path.stat().st_size
    text, page_markers = extract_text_from_pdf(str(path), return_page_markers=True)
    text_len = len(text) if text else 0
    pages = len(page_markers) if page_markers else 0

    chunker = TextChunker(chunk_size=1000, chunk_overlap=100)

    # Warm-up to prime any lazy modules.
    _ = chunker.semantic_chunk(text)
    _ = chunker.chunk_by_pages(text, page_markers)

    baseline_ms = []
    page_aware_ms = []
    baseline_chunks = 0
    page_aware_chunks = 0
    for _ in range(REPEATS):
        t, res = _time_ms(chunker.semantic_chunk, text)
        baseline_ms.append(t)
        baseline_chunks = len(res) if res else 0

        t, res = _time_ms(chunker.chunk_by_pages, text, page_markers)
        page_aware_ms.append(t)
        page_aware_chunks = len(res) if res else 0

    base_med = statistics.median(baseline_ms)
    page_med = statistics.median(page_aware_ms)
    ratio = page_med / base_med if base_med > 0 else float("inf")
    return {
        "file": path.name,
        "bytes": file_bytes,
        "text_chars": text_len,
        "pages": pages,
        "baseline_ms": round(base_med, 2),
        "page_aware_ms": round(page_med, 2),
        "ratio": round(ratio, 2),
        "baseline_chunks": baseline_chunks,
        "page_aware_chunks": page_aware_chunks,
    }


def render_markdown(rows: list[dict], threshold: float) -> str:
    header = "# PDF Chunker Performance Benchmark (wave 3)\n\n"
    header += (
        f"Compares `TextChunker.chunk_by_pages` (wave 2 page-aware) against "
        f"`TextChunker.semantic_chunk` on real PDFs. Contract: ratio must "
        f"stay ≤ {threshold:.1f}× baseline. Methodology: {REPEATS} repeats "
        f"per file, median reported, ``chunk_size=1000`` / ``overlap=100``.\n\n"
    )
    table = (
        "| File | Size | Pages | Text chars | baseline median (ms) | "
        "page-aware median (ms) | ratio | baseline chunks | page-aware chunks |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    )
    for r in rows:
        table += (
            f"| `{r['file']}` | {r['bytes']:,} B | {r['pages']} | "
            f"{r['text_chars']:,} | {r['baseline_ms']:.2f} | "
            f"{r['page_aware_ms']:.2f} | {r['ratio']:.2f}× | "
            f"{r['baseline_chunks']} | {r['page_aware_chunks']} |\n"
        )
    summary = "\n## Summary\n\n"
    max_ratio = max((r["ratio"] for r in rows), default=0.0)
    pass_fail = "PASS" if max_ratio <= threshold else "FAIL"
    summary += (
        f"- Max observed ratio: **{max_ratio:.2f}×** (threshold {threshold:.1f}×)\n"
        f"- Verdict: **{pass_fail}**\n"
        f"- Files benchmarked: {len(rows)}\n"
        f"- Repeats per file (median reported): {REPEATS}\n"
    )
    return header + table + summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Wave 3 chunker benchmark")
    parser.add_argument("paths", nargs="*", type=Path, help="PDF paths to benchmark")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "PERF_BENCHMARK.md",
        help="Markdown report output",
    )
    parser.add_argument("--threshold", type=float, default=RATIO_THRESHOLD)
    args = parser.parse_args()

    paths = args.paths or [p for p in _DEFAULT_CANDIDATES if p.exists()]
    if not paths:
        print("ERROR: no PDF candidates available. Pass paths explicitly.")
        return 2

    print(f"Benchmarking {len(paths)} PDF(s)...")
    rows: list[dict] = []
    for p in paths:
        if not p.exists():
            print(f"  SKIP {p} (not found)")
            continue
        try:
            row = benchmark_pdf(p)
            rows.append(row)
            print(
                f"  {p.name}: baseline={row['baseline_ms']:.1f}ms "
                f"page-aware={row['page_aware_ms']:.1f}ms "
                f"ratio={row['ratio']:.2f}×",
            )
        except Exception as e:
            print(f"  ERROR {p.name}: {e}")

    if not rows:
        print("ERROR: no successful benchmark rows.")
        return 2

    args.output.write_text(render_markdown(rows, args.threshold), encoding="utf-8")
    print(f"\nReport written to: {args.output}")

    max_ratio = max(r["ratio"] for r in rows)
    if max_ratio > args.threshold:
        print(
            f"FAIL: max ratio {max_ratio:.2f}× exceeds threshold "
            f"{args.threshold:.1f}×",
        )
        return 1
    print(f"PASS: max ratio {max_ratio:.2f}× ≤ {args.threshold:.1f}×")
    return 0


if __name__ == "__main__":
    sys.exit(main())
