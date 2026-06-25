#!/usr/bin/env python3
"""Capture intake OCR-provider output into JSONL for quality scoring.

Input manifest JSONL rows:
  {
    "id": "sample-id",
    "image_path": "sample.png",
    "expected_doc_type": "passport|kitas|...",
    "expected_fields": {"field": "expected value"}
  }

The output is compatible with scripts/intake_ocr_quality_eval.py. Gemini is
opt-in and still requires the backend cloud-vision gate.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

ProviderSample = dict[str, Any]
ProviderRow = dict[str, Any]


class PageImage:
    """Minimal page object accepted by backend.services.intake.classify.ocr_pages."""

    def __init__(self, *, index: int, png_bytes: bytes, enhanced: bool = False) -> None:
        self.index = index
        self.png_bytes = png_bytes
        self.enhanced = enhanced


OcrPagesFn = Callable[[list[PageImage]], Awaitable[list[dict[str, Any]]]]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no}: row must be a JSON object")
            rows.append(row)
    return rows


def load_manifest(path: Path) -> list[ProviderSample]:
    """Load a benchmark manifest and resolve image paths relative to the file."""
    samples: list[ProviderSample] = []
    for index, row in enumerate(_load_jsonl(path), start=1):
        missing = [
            field
            for field in ("id", "image_path", "expected_doc_type", "expected_fields")
            if field not in row
        ]
        if missing:
            raise ValueError(f"sample #{index} missing required fields: {', '.join(missing)}")
        if not isinstance(row["expected_fields"], dict):
            raise ValueError(f"sample #{index} expected_fields must be an object")

        image_path = Path(str(row["image_path"]))
        if not image_path.is_absolute():
            image_path = path.parent / image_path

        samples.append(
            {
                "id": str(row["id"]),
                "image_path": image_path,
                "expected_doc_type": str(row["expected_doc_type"]),
                "expected_fields": row["expected_fields"],
            }
        )
    return samples


def _unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value)
        if text not in seen:
            seen.add(text)
            ordered.append(text)
    return ordered


def _row_from_pages(
    sample: ProviderSample,
    *,
    provider: str,
    pages: list[dict[str, Any]],
    error: str | None,
) -> ProviderRow:
    ocr_text = "\n\n".join(str(page.get("text", "")) for page in pages if page.get("text"))
    return {
        "id": sample["id"],
        "provider": provider,
        "ocr_text": ocr_text,
        "expected_doc_type": sample["expected_doc_type"],
        "expected_fields": sample["expected_fields"],
        "chars": len(ocr_text),
        "page_count": len(pages),
        "models": _unique([page.get("model") for page in pages]),
        "vias": _unique([page.get("via") for page in pages]),
        "error": error,
    }


async def _default_ocr_pages(pages: list[PageImage]) -> list[dict[str, Any]]:
    from backend.services.intake.classify import ocr_pages

    return await ocr_pages(pages)


async def capture_samples(
    samples: list[ProviderSample],
    *,
    provider: str,
    output_path: Path,
    ocr_pages_fn: OcrPagesFn | None = None,
) -> list[ProviderRow]:
    """Run OCR for each sample and write quality-evaluator JSONL rows."""
    provider = provider.strip().lower()
    ocr_fn = ocr_pages_fn or _default_ocr_pages
    results: list[ProviderRow] = []
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as fh:
        for sample in samples:
            started = time.perf_counter()
            error: str | None = None
            pages: list[dict[str, Any]] = []
            try:
                image_bytes = Path(sample["image_path"]).read_bytes()
                pages = await ocr_fn([PageImage(index=0, png_bytes=image_bytes)])
            except Exception as exc:  # keep benchmark rows comparable across failures
                error = f"{type(exc).__name__}: {exc}"

            elapsed = time.perf_counter() - started
            row = _row_from_pages(sample, provider=provider, pages=pages, error=error)
            output_row = dict(row)
            output_row["seconds"] = round(elapsed, 3)
            fh.write(json.dumps(output_row, ensure_ascii=False, sort_keys=True) + "\n")
            results.append(row)

    return results


def _configure_provider(provider: str, *, allow_cloud_vision: bool) -> None:
    if provider == "ollama":
        os.environ["INTAKE_OCR_PROVIDER"] = "ollama"
        return
    if provider != "gemini":
        raise ValueError(f"unsupported provider: {provider}")
    if not allow_cloud_vision:
        raise ValueError("provider gemini requires --allow-cloud-vision")
    os.environ["INTAKE_OCR_PROVIDER"] = "gemini"
    os.environ["OCR_ALLOW_CLOUD_VISION"] = "true"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help="JSONL manifest with local image paths and expected fields.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="JSONL output consumed by scripts/intake_ocr_quality_eval.py.",
    )
    parser.add_argument(
        "--provider",
        choices=("ollama", "gemini"),
        default="ollama",
        help="OCR provider to benchmark. Gemini additionally requires --allow-cloud-vision.",
    )
    parser.add_argument(
        "--allow-cloud-vision",
        action="store_true",
        help="Permit Gemini cloud OCR for explicitly authorized non-PII samples.",
    )
    return parser


async def _amain(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _configure_provider(args.provider, allow_cloud_vision=args.allow_cloud_vision)
    samples = load_manifest(args.manifest)
    await capture_samples(samples, provider=args.provider, output_path=args.output)
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return asyncio.run(_amain(argv))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
