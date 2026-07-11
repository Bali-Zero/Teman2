#!/usr/bin/env python3
"""Evaluate OCR-provider output quality from a JSONL sample file.

Input JSONL rows:
  {
    "id": "sample-id",
    "provider": "ollama|gemini|...",
    "ocr_text": "...",
    "expected_doc_type": "passport|kitas|...",
    "expected_fields": {"field": "expected value"}
  }

Default mode is offline: the script never calls OCR or extraction LLMs. It
scores provider-produced text through deterministic intake paths where possible.
Use --allow-model-calls only for an explicitly authorized local/prod run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


async def _offline_empty_model(_model: str, _prompt: str) -> str:
    return "{}"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
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
            samples.append(row)
    return samples


def _require_sample_fields(sample: dict[str, Any], index: int) -> None:
    required = ("provider", "ocr_text", "expected_doc_type", "expected_fields")
    missing = [field for field in required if field not in sample]
    if missing:
        raise ValueError(f"sample #{index} missing required fields: {', '.join(missing)}")
    if not isinstance(sample["expected_fields"], dict):
        raise ValueError(f"sample #{index} expected_fields must be an object")


async def evaluate_samples(
    samples: list[dict[str, Any]],
    *,
    allow_model_calls: bool = False,
) -> dict[str, Any]:
    from backend.services.intake import ocr_quality

    generate_fn = None if allow_model_calls else _offline_empty_model
    results: list[dict[str, Any]] = []
    for index, sample in enumerate(samples, start=1):
        _require_sample_fields(sample, index)
        result = await ocr_quality.evaluate_ocr_text(
            provider=str(sample["provider"]),
            ocr_text=str(sample["ocr_text"]),
            expected_doc_type=str(sample["expected_doc_type"]),
            expected_fields=sample["expected_fields"],
            generate_fn=generate_fn,
        )
        for key in ("id", "seconds", "elapsed_s", "error", "chars"):
            if sample.get(key) is not None:
                result[key] = sample[key]
        results.append(result)
    return ocr_quality.summarize_evaluations(results)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="JSONL file with provider OCR text and expected fields.",
    )
    parser.add_argument(
        "--allow-model-calls",
        action="store_true",
        help="Allow extraction LLM calls for doc types without deterministic extractors.",
    )
    return parser


async def _amain(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    samples = _load_jsonl(args.input)
    summary = await evaluate_samples(samples, allow_model_calls=args.allow_model_calls)
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return asyncio.run(_amain(argv))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
