"""Gold-coverage floor: every synthetic persona in the repository corpus must
still be SUPPORTED for its product by the highest signed PRODUCTION pack.

This is the armed twin of ``gold_coverage_replay.py``: the corpus under
``gold_coverage/personas/`` is data, and data without a reader is W81-dead.
The test runs the replay in-process and fails on the first persona whose
product drops out of the candidates — a pack sequence that silently
un-supports a product it used to support goes red here, before it is signed
into production.  An EMPTY corpus fails too (a floor that passes on zero
personas is the W84 green-but-dead shape).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.scripts.visa_engine import gold_coverage_replay as replay
from backend.scripts.visa_engine.gold_replay_driver import (
    PACKS_DIR,
    select_highest_repository_pack,
)

CORPUS_DIR = Path(__file__).resolve().parent / "gold_coverage" / "personas"

# PINNED to the highest signed pack's own `signed_at`, never the wall clock:
# the selected pack's source_records carry a freshness_policy
# (MAX_AGE_SINCE_VERIFIED_AT) with as little as a 604800s (7-day) window, so
# calling `replay.main` without `--as-of` evaluates at `datetime.now(UTC)` —
# a clock bomb guaranteed to go stale exactly 7 days after the newest
# source's verified_at, with zero code change. It took the ENTIRE merge
# queue down on 2026-08-30 (verified_at 2026-08-23T10:44:48Z + 604800s =
# 2026-08-30T10:44:48Z); at that instant the engine correctly started
# returning HUMAN_REVIEW_REQUIRED for every persona in this floor — the
# engine was right, the wall-clock evaluation was the bug. `signed_at` (not
# `payload.created_at`) because `--as-of` also drives `verify_rule_pack`'s
# `observed_at`, which rejects a signature dated AFTER the observation
# instant.
_, _HIGHEST_SIGNED_PACK = select_highest_repository_pack(PACKS_DIR)
_AS_OF = _HIGHEST_SIGNED_PACK["protected"]["signed_at"]


def _run_corpus(capsys: pytest.CaptureFixture[str]) -> tuple[int, dict]:
    rc = replay.main(["--corpus", str(CORPUS_DIR), "--as-of", _AS_OF])
    out = capsys.readouterr().out
    start = out.find("{")
    report = json.loads(out[start:]) if start >= 0 else {}
    return rc, report


def test_corpus_is_not_empty() -> None:
    files = sorted(CORPUS_DIR.glob("*.json"))
    assert files, f"gold-coverage corpus is empty: {CORPUS_DIR}"


def test_every_corpus_persona_is_supported_for_its_product(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, report = _run_corpus(capsys)
    failed = [p for p in report.get("personas", []) if not p.get("pass")]
    assert rc == 0 and not failed, "gold-coverage floor broken: " + "; ".join(
        f"{p.get('file')} ({p.get('product_code')}): state={p.get('actual', {}).get('state')} "
        f"missing={p.get('candidates_missing')}"
        for p in failed
    )
    assert report["summary"]["total"] == len(list(CORPUS_DIR.glob("*.json")))


def test_corpus_file_names_match_their_product_code() -> None:
    """``<CODE>.json`` must declare ``product_code == CODE`` — a renamed file
    that keeps another product's expectations would otherwise pass silently."""
    for path in sorted(CORPUS_DIR.glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert spec.get("product_code") == path.stem, path.name
        assert path.stem in (spec.get("expected_candidates") or []), path.name
