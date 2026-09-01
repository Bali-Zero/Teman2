"""Offline corpus replay for gold-coverage personas (2026-08-28).

Loads every persona JSON file in a corpus directory — one file per product,
each shaped exactly like ``gold_coverage_eval.py``'s single-persona
``--persona`` input (``{"label", "product_code", "expected_state",
"expected_candidates", "overrides"}``) — and evaluates each through the
SAME path ``gold_coverage_eval.py`` uses for one persona at a time:
``gold_coverage_eval._evaluate`` (verify -> compile -> highest signed
PRODUCTION pack in ``contracts/packs`` -> ``evaluator.evaluate`` ->
``apply_public_policy_adapters``). This module never re-implements that
path; it only calls it once per persona file, so the two CLIs can never
silently drift on what "evaluate a persona" means.

Like ``gold_coverage_eval.py`` and the ``--offline`` mode of
``gold_replay_driver.py``, this proves what the checked-out repository
artifact does, not what is currently ACTIVE in production — it never
queries a live database or the public evaluate endpoint, and it never
claims the selected pack is the one actually serving traffic.

A persona PASSES iff its actual decision state equals its declared
``expected_state`` AND every one of its ``expected_candidates`` appears in
the actual candidate set. This is a coverage FLOOR, not a full-fidelity
replay: unlike ``gold_replay_driver.py`` it does not compare missing_facts,
review reason codes, no-path reason codes, or notice codes — only state
plus the named candidate subset.

An EMPTY corpus is a FAILURE, never a vacuous pass. Exit code is 0 only
when at least one persona was evaluated AND every evaluated persona
passed; an empty directory exits 1 with an explanation on stderr. A
coverage gate that reports green because nobody fed it anything is the
"exists != armed" cron-theater shape (cicatrix family #2) this script is
built specifically never to reproduce.

Usage::

    cd apps/backend-rag && PYTHONPATH=. python -m backend.scripts.visa_engine.gold_coverage_replay \
        --corpus backend/tests/services/visa_engine/gold_coverage/personas \
        --out /tmp/gold-coverage-report.json
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.scripts.visa_engine.gold_coverage_eval import _evaluate
from backend.scripts.visa_engine.gold_replay_driver import _parse_utc

logger = logging.getLogger(__name__)

#: Bump on any incompatible change to the report shape below.
REPORT_SCHEMA_VERSION = "1.0.0"


def _load_persona_specs(corpus: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Load every ``*.json`` persona file directly under ``corpus``, sorted
    by filename for a deterministic report row order. A missing or empty
    directory yields an empty list — the caller (``build_report``) is the
    one place that turns "no personas" into a failure, so this loader stays
    a pure, side-effect-free read.
    """
    specs: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(corpus.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: persona file must contain a JSON object")
        specs.append((path, raw))
    return specs


def _evaluate_persona(
    path: Path, spec: dict[str, Any], *, as_of: datetime | None = None
) -> dict[str, Any]:
    """Evaluate one persona spec via ``gold_coverage_eval._evaluate`` and
    grade it against its own declared ``expected_state``/``expected_candidates``.

    Returns a row dict plus an internal ``"_pack"`` entry (popped by the
    caller) carrying that evaluation's ``{file, sequence, version}`` — every
    persona is evaluated against the same on-disk highest signed PRODUCTION
    pack, so any caller may take the first row's pack info as the report's
    top-level pack identity.

    ``as_of`` is forwarded verbatim to ``gold_coverage_eval._evaluate`` — see
    that function's docstring for why a fixed-wall-clock evaluation against a
    pack's freshness-windowed source_records is a clock bomb, not a stable
    baseline. Defaults to None so production behaviour (evaluate at the real
    wall clock) is unchanged.
    """
    overrides = spec.get("overrides") or {}
    if not isinstance(overrides, dict):
        raise ValueError(f"{path}: 'overrides' must be an object keyed by dotted FactPath")
    label = str(spec.get("label", path.stem))

    result = _evaluate(overrides, label, as_of=as_of)
    actual = result["actual"]
    actual_candidates = set(actual.get("candidates") or actual.get("candidate_products") or [])

    expected_state = spec.get("expected_state")
    expected_candidates = list(spec.get("expected_candidates") or [])
    candidates_missing = sorted(c for c in expected_candidates if c not in actual_candidates)
    state_matches = actual.get("state") == expected_state
    passed = state_matches and not candidates_missing

    return {
        "file": path.name,
        "label": label,
        "product_code": spec.get("product_code"),
        "expected_state": expected_state,
        "expected_candidates": expected_candidates,
        "actual": actual,
        "state_matches": state_matches,
        "candidates_missing": candidates_missing,
        "pass": passed,
        "_pack": result["pack"],
    }


def build_report(corpus: Path, *, as_of: datetime | None = None) -> dict[str, Any]:
    """Evaluate every persona in ``corpus`` and return the full report dict.

    Raises ``ValueError`` when the corpus contains zero persona files — the
    caller (``main``) turns that into the documented exit-1 + stderr
    explanation. Building an empty-but-"passing" report is deliberately not
    a reachable code path: total==0 can only ever arrive here as a raised
    exception, never as a returned summary a caller could mistake for green.

    ``as_of`` defaults to None (real wall clock, unchanged production
    behaviour) and is forwarded to every persona's evaluation — see
    ``_evaluate_persona``/``gold_coverage_eval._evaluate`` for why evaluating
    at ``datetime.now(UTC)`` against a pack's freshness-windowed
    ``source_records`` is a clock bomb, not a stable default for a pinned
    test.
    """
    entries = _load_persona_specs(corpus)
    if not entries:
        raise ValueError(f"corpus is empty: no *.json persona files found under {corpus}")

    rows: list[dict[str, Any]] = []
    pack_info: dict[str, Any] = {}
    for path, spec in entries:
        row = _evaluate_persona(path, spec, as_of=as_of)
        pack_info = row.pop("_pack")
        rows.append(row)
        logger.info("%s: label=%s pass=%s", path.name, row["label"], row["pass"])

    passed_rows = [row for row in rows if row["pass"]]
    products_covered = sorted({row["product_code"] for row in passed_rows if row["product_code"]})

    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "pack": pack_info,
        "personas": rows,
        "summary": {
            "total": len(rows),
            "passed": len(passed_rows),
            "failed": len(rows) - len(passed_rows),
            "products_covered": products_covered,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        required=True,
        help="directory of persona *.json files (gold_coverage_eval.py --persona shape)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="optional path to also write the report JSON (always printed to stdout)",
    )
    parser.add_argument(
        "--as-of",
        type=_parse_utc,
        default=None,
        help=(
            "pin the evaluation/verification instant to this timezone-aware "
            "UTC ISO-8601 timestamp instead of the real wall clock (e.g. "
            "'2026-08-29T05:00:00Z'). Defaults to now — production behaviour "
            "is unchanged; this exists so a test can pin the instant to a "
            "pack's own created_at and avoid a freshness-window clock bomb."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", force=True
    )
    args = _parser().parse_args(argv)

    try:
        report = build_report(args.corpus, as_of=args.as_of)
    except ValueError as exc:
        logger.error("gold coverage replay cannot run: %s", exc)
        return 1

    payload = json.dumps(report, indent=2, sort_keys=True)
    print(payload)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
        logger.info("report written to %s", args.out)

    summary = report["summary"]
    if summary["total"] > 0 and summary["failed"] == 0:
        return 0
    logger.error(
        "gold coverage replay FAILED: %d/%d personas passed (%d failed)",
        summary["passed"],
        summary["total"],
        summary["failed"],
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
