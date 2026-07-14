#!/usr/bin/env python3
"""wr2_carousel_import.py — import externally-produced IG carousels into WR2.

Zero sometimes designs an Instagram carousel OUTSIDE the WR2 pipeline (by hand,
in another tool) and wants it to enter the exact same review→approve→publish
flow as pipeline-generated carousels (Law 5 — never auto-publish). This script
is the on-ramp: it accepts total input freedom (a single PDF where one page =
one slide, a folder of images, or N individual image files — mixed
png/jpg/jpeg/webp/heic), normalizes every slide to the IG portrait 4:5 canvas
(1080x1350), writes the same `slides/NN.png` + `manifest.json` layout the
pipeline uses under `apps/war-room/output/carousel/<slug>/`, and appends a
queue item in state `drafted` to `human-review-queue.json` — reusing
`wr2_queue_writer.py`'s lock + atomic-write primitives (STRATO 3) via the same
importlib-sibling-module pattern `wr2_ig_profile_harvester.py` uses, rather
than reimplementing queue I/O.

Contract (frozen — the review-queue app is being built against this CLI in
parallel; do not change the shape without updating that consumer too):

    python3 scripts/wr2_carousel_import.py <input>... [--slug SLUG]
        [--topic "TEXT"] [--fit contain|cover|native] [--queue PATH] [--dry-run]

`<input>...` is exactly one of:
  - one PDF path (page order preserved, one page -> one slide)
  - one directory path (natural-sorted image files inside)
  - N individual image file paths (natural-sorted by basename)

Output: a single JSON line on stdout —
    success: {"ok": true, "slug": ..., "carousel_dir": ..., "slide_count": N,
              "queue_id": ...}                                    exit 0
    failure: {"ok": false, "error": "..."}                         exit 2
Human-readable progress goes to stderr only, never stdout (the caller parses
stdout as JSON).

Normalization uses macOS `/usr/bin/sips` exclusively (no Pillow dependency):
  - contain (default): scale-to-fit + pad to exactly 1080x1350 with the brand
    antracite `373D42`.
  - cover: scale + center-crop to exactly 1080x1350.
  - native: format-convert to PNG only, no resize (still validates the image
    is readable — sips raises loudly on garbage input).

PDF splitting tries PyMuPDF (`import fitz`) first, falls back to `pdftoppm`
(poppler) if fitz isn't importable, and fails visibly with an install hint if
neither is available — it never silently drops pages.

Env `WR2_OUTPUT_ROOT` overrides the carousel output base (default
`~/Desktop/nuzantara/apps/war-room/output/carousel`) so tests/smokes never
write into the real pipeline output tree (scar W96 — redirectable-by-design).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Import STRATO 3 queue writer (sibling module, same pattern as
#    wr2_ig_profile_harvester.py) — reuse queue_lock + write_queue_atomic
#    instead of reimplementing queue I/O.  ─────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_WRITER_PATH = _THIS_DIR / "wr2_queue_writer.py"
_spec = importlib.util.spec_from_file_location("wr2_queue_writer", _WRITER_PATH)
_qw = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _qw
_spec.loader.exec_module(_qw)

# ── Constants ───────────────────────────────────────────────────────────────

SLIDE_W = 1080
SLIDE_H = 1350
BRAND_ANTRACITE = "373D42"
MIN_SLIDES = 1
MAX_SLIDES = 20  # Instagram carousel cap
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".heic"}
SIPS = "/usr/bin/sips"

DEFAULT_OUTPUT_ROOT = Path.home() / "Desktop/nuzantara/apps/war-room/output/carousel"


def _log(msg: str) -> None:
    print(f"[wr2-carousel-import] {msg}", file=sys.stderr)


# ── Pure helpers (no I/O beyond stat/iterdir — unit-tested with tmp_path) ──

_NUM_RE = re.compile(r"(\d+)")


def natural_sort_key(name: str) -> list:
    """Natural sort key so '2' sorts before '10' (string-vs-number chunking)."""
    return [int(tok) if tok.isdigit() else tok.lower() for tok in _NUM_RE.split(name)]


_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Lowercase, ASCII-ish, dash-separated slug. Never returns empty string."""
    s = _SLUG_STRIP_RE.sub("-", text.strip().lower()).strip("-")
    return s or "imported"


def derive_slug(explicit_slug: Optional[str], topic: Optional[str], now: datetime) -> str:
    """--slug wins; else slugified --topic; else `imported-<YYYYMMDD-HHMMSS>`."""
    if explicit_slug:
        return slugify(explicit_slug)
    if topic:
        return slugify(topic)
    return f"imported-{now.strftime('%Y%m%d-%H%M%S')}"


def humanize_slug(slug: str) -> str:
    """Default --topic when none given: the slug, title-cased word by word."""
    return " ".join(w.capitalize() for w in slug.split("-") if w)


def iso_z(dt: datetime) -> str:
    """UTC ISO-8601 with a literal `Z` suffix (no microseconds) — matches the
    existing queue's `id`/`drafted_at` convention (e.g. 'carousel_2026-07-08T05:16:22Z_...')."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_tilde_path(path: Path, home: Optional[Path] = None) -> str:
    """Rewrite an absolute path under $HOME to a literal `~/...` prefix.

    Machine-agnostic on purpose (scar #1 HOME-fork / path-drift): the queue is
    read on M5 and Pro under different usernames, so a hardcoded
    `/Users/<user>/...` prefix baked in by one machine is dead on the other.
    Paths outside $HOME are returned unchanged (best-effort, not expected in
    normal operation).
    """
    home = home or Path.home()
    home_s = str(home)
    s = str(path)
    if s == home_s:
        return "~"
    if s.startswith(home_s + os.sep):
        return "~" + s[len(home_s):]
    return s


def classify_inputs(raw_args: list[str]) -> tuple[str, list[Path]]:
    """Classify the CLI inputs and return (kind, naturally-sorted source files).

    kind is one of "pdf" | "dir" | "images". Raises ValueError with a clear,
    user-facing message on any invalid/ambiguous input — never silently
    drops or reorders slides.
    """
    if not raw_args:
        raise ValueError("no input given")
    paths = [Path(a).expanduser() for a in raw_args]

    if len(paths) == 1 and paths[0].is_dir():
        d = paths[0]
        found = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
        if not found:
            raise ValueError(
                f"directory {d} contains no supported images "
                f"({', '.join(sorted(IMAGE_EXTS))})"
            )
        found.sort(key=lambda p: natural_sort_key(p.name))
        return "dir", found

    if len(paths) == 1 and paths[0].suffix.lower() == ".pdf":
        p = paths[0]
        if not p.is_file():
            raise ValueError(f"PDF not found: {p}")
        return "pdf", [p]

    # N individual image files.
    for p in paths:
        if not p.is_file():
            raise ValueError(f"input path not found: {p}")
        if p.suffix.lower() not in IMAGE_EXTS:
            raise ValueError(
                f"unsupported file type: {p} — expected one of "
                f"{', '.join(sorted(IMAGE_EXTS))}, or a single .pdf, or a single directory"
            )
    sorted_paths = sorted(paths, key=lambda p: natural_sort_key(p.name))
    return "images", sorted_paths


def build_manifest(
    topic: str,
    png_paths: list[str],
    fit_mode: str,
    import_source: str,
    pdf_path: Optional[str],
) -> dict[str, Any]:
    """Mirror the pipeline's manifest.json shape, flagged as an external import."""
    n = len(png_paths)
    return {
        "topic": topic,
        "total_slides": n,
        "families": ["external-import"],
        "heroes_expected": 0,
        "heroes_placed": 0,
        "slides_rendered": n,
        "ok": True,
        "failures": [],
        "png_paths": png_paths,
        "pdf_path": pdf_path,
        "imported": True,
        "import_source": import_source,
        "fit_mode": fit_mode,
    }


def build_queue_item(
    slug: str,
    topic: str,
    slide_count: int,
    carousel_dir: Path,
    now: datetime,
    home: Optional[Path] = None,
) -> dict[str, Any]:
    """Build a `drafted`-state queue item shaped like the pipeline's, so
    review->approve->publish applies unchanged (Law 5)."""
    ts = iso_z(now)
    item_id = f"carousel_{ts}_{slug}"
    carousel_path = to_tilde_path(carousel_dir, home=home) + "/"
    slides_dir = to_tilde_path(carousel_dir / "slides", home=home) + "/"
    return {
        "id": item_id,
        "draft_id": str(uuid.uuid4()),
        "topic_slug": slug,
        "topic": topic,
        "drafted_at": ts,
        "carousel_path": carousel_path,
        "slides_dir": slides_dir,
        "drive_url": None,
        "media_type": "carousel",
        "slide_count": slide_count,
        "critic_overall_verdict": "external",
        "critic_summary": "imported — not critic-gated",
        "fact_check_status": "external",
        "state": "drafted",
        "state_history": [
            {"state": "drafted", "at": ts, "by": "wr2-carousel-import"}
        ],
        "instagram_post_url": None,
        "instagram_published_at": None,
        "engagement_metrics": None,
        "source": "external-import",
    }


def import_source_label(raw_args: list[str]) -> str:
    """Human-readable `<basename(s)>` for manifest.import_source."""
    return ",".join(Path(a).name for a in raw_args)


# ── PDF splitting (I/O) ─────────────────────────────────────────────────────


def render_pdf_pymupdf(pdf_path: Path, out_dir: Path) -> list[Path]:
    import fitz  # type: ignore

    doc = fitz.open(str(pdf_path))
    try:
        if doc.page_count == 0:
            raise RuntimeError(f"PDF has 0 pages: {pdf_path}")
        mat = fitz.Matrix(2.0, 2.0)  # 2x render scale for crisp downscale
        out_paths: list[Path] = []
        for i in range(doc.page_count):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=mat)
            raw_path = out_dir / f"_raw_{i + 1:03d}.png"
            pix.save(str(raw_path))
            out_paths.append(raw_path)
        return out_paths
    finally:
        doc.close()


def render_pdf_poppler(pdf_path: Path, out_dir: Path) -> list[Path]:
    prefix = out_dir / "_raw"
    proc = subprocess.run(
        ["pdftoppm", "-png", "-r", "150", str(pdf_path), str(prefix)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pdftoppm failed on {pdf_path}: {proc.stderr.strip()}")
    pages = sorted(out_dir.glob("_raw-*.png"), key=lambda p: natural_sort_key(p.name))
    if not pages:
        raise RuntimeError(f"pdftoppm produced no pages for {pdf_path}")
    return pages


def render_pdf_pages(pdf_path: Path, out_dir: Path) -> list[Path]:
    """Split a PDF into page images, page order preserved. Never silently
    skips pages — raises with a clear install hint if no backend is available."""
    try:
        import fitz  # noqa: F401
    except ImportError:
        fitz = None  # type: ignore
    if fitz is not None:
        _log(f"splitting PDF via PyMuPDF: {pdf_path}")
        return render_pdf_pymupdf(pdf_path, out_dir)
    if shutil.which("pdftoppm"):
        _log(f"PyMuPDF unavailable — splitting PDF via pdftoppm: {pdf_path}")
        return render_pdf_poppler(pdf_path, out_dir)
    raise RuntimeError(
        "cannot split PDF: PyMuPDF is not importable and `pdftoppm` is not on "
        "PATH. Install one of: `pip install pymupdf` (inside "
        "apps/backend-rag/.venv) or `brew install poppler`."
    )


# ── sips normalization (I/O) ────────────────────────────────────────────────


def _run_sips(args: list[str]) -> None:
    proc = subprocess.run([SIPS] + args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"sips failed ({' '.join(args)}): {proc.stderr.strip()}")


def get_pixel_dims(path: Path) -> tuple[int, int]:
    """Return (height, width) of an image via `sips -g`."""
    proc = subprocess.run(
        [SIPS, "-g", "pixelHeight", "-g", "pixelWidth", str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"sips could not read {path}: {proc.stderr.strip()}")
    h = w = None
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("pixelHeight:"):
            h = int(line.split(":", 1)[1].strip())
        elif line.startswith("pixelWidth:"):
            w = int(line.split(":", 1)[1].strip())
    if h is None or w is None:
        raise RuntimeError(f"could not parse pixel dimensions of {path}")
    return h, w


def normalize_image(src: Path, dst: Path, fit: str) -> None:
    """Normalize one slide image to the 1080x1350 canvas (or just PNG-convert
    for `native`), writing to `dst`. Raises loudly on any sips failure — a
    garbage/unreadable input is a hard error, never a silent skip."""
    dst.parent.mkdir(parents=True, exist_ok=True)

    if fit == "native":
        _run_sips(["-s", "format", "png", str(src), "--out", str(dst)])
    elif fit == "contain":
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "resampled.png"
            _run_sips(
                ["--resampleHeightWidthMax", str(max(SLIDE_W, SLIDE_H)),
                 "-s", "format", "png", str(src), "--out", str(tmp)]
            )
            _run_sips(
                ["-p", str(SLIDE_H), str(SLIDE_W), "--padColor", BRAND_ANTRACITE,
                 "-s", "format", "png", str(tmp), "--out", str(dst)]
            )
    elif fit == "cover":
        h, w = get_pixel_dims(src)
        scale = max(SLIDE_H / h, SLIDE_W / w)
        new_h = max(SLIDE_H, round(h * scale))
        new_w = max(SLIDE_W, round(w * scale))
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "resampled.png"
            _run_sips(
                ["--resampleHeightWidth", str(new_h), str(new_w),
                 "-s", "format", "png", str(src), "--out", str(tmp)]
            )
            _run_sips(
                ["-c", str(SLIDE_H), str(SLIDE_W),
                 "-s", "format", "png", str(tmp), "--out", str(dst)]
            )
    else:
        raise ValueError(f"unknown --fit mode: {fit}")

    if not dst.is_file():
        raise RuntimeError(f"sips did not produce output file {dst}")


# ── Env resolution ──────────────────────────────────────────────────────────


def resolve_output_root() -> Path:
    env = os.environ.get("WR2_OUTPUT_ROOT")
    return Path(env).expanduser() if env else DEFAULT_OUTPUT_ROOT


def resolve_queue_path(arg: Optional[str]) -> Path:
    if arg:
        return Path(arg).expanduser()
    env = os.environ.get("WR2_QUEUE_PATH")
    if env:
        return Path(env).expanduser()
    return _qw.DEFAULT_QUEUE_PATH


# ── Orchestration ───────────────────────────────────────────────────────────


def process_import(
    raw_inputs: list[str],
    slug_arg: Optional[str],
    topic_arg: Optional[str],
    fit: str,
    queue_path: Path,
    dry_run: bool,
    output_root: Path,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)

    kind, sources = classify_inputs(raw_inputs)
    _log(f"classified input as '{kind}' ({len(sources)} source file(s))")

    final_slug = derive_slug(slug_arg, topic_arg, now)
    final_topic = topic_arg or humanize_slug(final_slug)

    carousel_dir = output_root / final_slug
    slides_dir = carousel_dir / "slides"
    existing_slides = list(slides_dir.glob("*.png")) if slides_dir.is_dir() else []
    if existing_slides or (carousel_dir / "manifest.json").is_file():
        return {
            "ok": False,
            "error": (
                f"carousel dir already exists with content: {carousel_dir} — "
                "pass --slug to choose a different name (no silent overwrite)"
            ),
        }

    slides_dir.mkdir(parents=True, exist_ok=True)

    pdf_path_out: Optional[str] = None
    try:
        with tempfile.TemporaryDirectory() as raw_td:
            raw_dir = Path(raw_td)
            if kind == "pdf":
                raw_pages = render_pdf_pages(sources[0], raw_dir)
                pdf_path_out = str(sources[0])
            else:
                raw_pages = sources

            n = len(raw_pages)
            if not (MIN_SLIDES <= n <= MAX_SLIDES):
                shutil.rmtree(carousel_dir, ignore_errors=True)
                return {
                    "ok": False,
                    "error": (
                        f"slide count {n} outside allowed range "
                        f"[{MIN_SLIDES}, {MAX_SLIDES}] (Instagram carousel cap)"
                    ),
                }

            png_paths: list[str] = []
            failures: list[dict[str, str]] = []
            for i, src in enumerate(raw_pages, start=1):
                dst = slides_dir / f"{i:02d}.png"
                _log(f"normalizing slide {i}/{n} ({fit}): {src.name} -> {dst.name}")
                try:
                    normalize_image(src, dst, fit)
                    png_paths.append(str(dst))
                except Exception as e:  # noqa: BLE001 — surfaced in the JSON error
                    failures.append({"index": str(i), "source": str(src), "error": str(e)})
    except Exception:
        shutil.rmtree(carousel_dir, ignore_errors=True)
        raise

    if failures:
        shutil.rmtree(carousel_dir, ignore_errors=True)
        return {
            "ok": False,
            "error": f"failed to normalize {len(failures)}/{n} slide(s): {failures}",
        }

    manifest = build_manifest(
        topic=final_topic,
        png_paths=png_paths,
        fit_mode=fit,
        import_source=import_source_label(raw_inputs),
        pdf_path=pdf_path_out,
    )
    (carousel_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    _log(f"wrote manifest.json ({len(png_paths)} slides) -> {carousel_dir}")

    queue_id: Optional[str] = None
    if not dry_run:
        item = build_queue_item(
            slug=final_slug,
            topic=final_topic,
            slide_count=len(png_paths),
            carousel_dir=carousel_dir,
            now=now,
        )
        with _qw.queue_lock(queue_path):
            try:
                items = _qw.load_queue(queue_path)
            except FileNotFoundError:
                items = []
            items.append(item)
            _qw.write_queue_atomic(queue_path, items)
        queue_id = item["id"]
        _log(f"appended queue item {queue_id} (state=drafted) -> {queue_path}")
    else:
        _log("dry-run: skipping queue write")

    result: dict[str, Any] = {
        "ok": True,
        "slug": final_slug,
        "carousel_dir": str(carousel_dir),
        "slide_count": len(png_paths),
        "queue_id": queue_id,
    }
    if dry_run:
        result["dry_run"] = True
    return result


# ── CLI ──────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Import an externally-produced IG carousel (PDF/images) into the WR2 review queue"
    )
    p.add_argument(
        "inputs", nargs="+",
        help="one PDF path, OR one directory, OR N individual image files (png/jpg/jpeg/webp/heic)",
    )
    p.add_argument("--slug", help="carousel slug (default: derived from --topic or a timestamp)")
    p.add_argument("--topic", help="topic text for the queue item (default: humanized slug)")
    p.add_argument(
        "--fit", choices=["contain", "cover", "native"], default="contain",
        help="normalization mode to the 1080x1350 canvas (default: contain)",
    )
    p.add_argument("--queue", help="path to human-review-queue.json (default: env WR2_QUEUE_PATH or standard)")
    p.add_argument(
        "--dry-run", action="store_true",
        help="render slides + manifest but skip the queue write",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = process_import(
            raw_inputs=args.inputs,
            slug_arg=args.slug,
            topic_arg=args.topic,
            fit=args.fit,
            queue_path=resolve_queue_path(args.queue),
            dry_run=args.dry_run,
            output_root=resolve_output_root(),
        )
    except Exception as e:  # noqa: BLE001 — top-level fail-visible boundary
        result = {"ok": False, "error": str(e)}

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
