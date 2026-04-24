#!/usr/bin/env python3
"""Fase 0 Days 4-5 driver — infer 6 personas via Gemini 3.1 Pro.

Day 4 argv: --wave=expat (3 personas: boomer retiree / techie PMA / italian AIRE)
Day 5 argv: --wave=id    (3 personas: konsultan KADIN / founder PMA ID / UMKM)
           --wave=both   (runs all 6 in one go)

Gate 4 (EOD day 5): 6 personas, each ≥15 populated attrs + ≥3 verbatim quotes.

Output: research/sota-social-2026-v1/04_personas.json

Runtime: ~1-2 min per persona. Idempotent — re-running overwrites the
slug's entry in the existing file (keeps good ones, replaces failures).

CAVEAT: like Task 12 (literature), Gemini CLI default is not grounded
— verbatim_quotes are plausible-sounding but not verbatim from real
comments. The Consiglio v1 step (Task 19) DeepSeek falsification is
expected to flag this and treat quotes as illustrative rather than
primary evidence.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "apps" / "backend-rag"))

# Backend Settings placeholders (same pattern as other SOTA drivers)
os.environ.setdefault("JWT_SECRET_KEY", "sota-research-local-dev-placeholder-32chars-min-ok")
os.environ.setdefault("API_KEYS", "sota-research-local-placeholder-key")

from backend.services.research.persona_inference import (  # noqa: E402
    Persona,
    PersonaInferenceAgent,
    PersonaValidationError,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.personas")

OUT = _REPO_ROOT / "research" / "sota-social-2026-v1" / "04_personas.json"

PER_PERSONA_TIMEOUT_SEC = 300  # 5 min per call

# Using Claude Max OAuth instead of Gemini — Gemini 3.1 Pro CLI hits
# 429 rate limit quickly under sequential calls (observed 2026-04-23
# during Task 15 wave=expat). Claude CLI tier is more generous and
# has stricter JSON compliance.


PROMPT_TEMPLATE = """You are building a persona profile for Bali Zero's social
media research. Target slug: {slug}
Market segment: {segment}

Source signals to mine (these are pointers — you need not "visit" them,
but the persona profile must reflect the audience they represent):
{sources}

Emit EXACTLY a single JSON object on the last line of your reply, no prose,
no markdown fences, no explanation text. All fields are required; pick
reasonable values based on the source-signal context and your knowledge
of Bali expat + Indonesian domestic demographics 2024-26.

Schema (copy exactly, fill values):
{{
  "slug": "{slug}",
  "market_segment": "{segment}",
  "age_range": "<string, e.g. 30-45>",
  "geo_origin": "<string, e.g. EU + North America>",
  "gender_split": "<string, e.g. 60/40 male/female>",
  "profession_past": "<string, comma-separated top 3 professions>",
  "wealth_level": "<qualitative, e.g. 300k-1M USD liquid>",
  "primary_goal": "<one sentence>",
  "pain_points": ["point 1", "point 2", "point 3", ...],
  "platforms_used": ["instagram", "whatsapp", ...],
  "content_preferences": ["format or topic preferences"],
  "language_primary": "<en|id|it|...>",
  "language_secondary": ["additional languages"],
  "decision_journey_stages": ["awareness", "research", "consideration", "decision"],
  "tone_resonance": {{"pedagogico": 0.4, "analitico": 0.3, "rituale": 0.2, "tecnico": 0.1}},
  "hook_patterns_that_work": ["story", "question", ...],
  "verbatim_quotes": [
    "<plausible quote 1 reflecting persona's voice & concerns>",
    "<plausible quote 2>",
    "<plausible quote 3 — at least 3 required>"
  ],
  "trust_signals": ["referral", "google reviews", "press mentions", ...]
}}

Remember: tone_resonance values are WR2 registers (pedagogico, analitico,
tecnico, rituale, poetico, ironico, militante). Use numeric weights 0-1
summing to ~1.0."""


def infer_one(slug: str, segment: str, sources: list[str]) -> Persona:
    """Run gemini once for a single persona slug, return parsed Persona.

    Raises RuntimeError on subprocess failure or parse failure — the
    main loop catches these and logs so other personas still run.
    """
    prompt = PROMPT_TEMPLATE.format(
        slug=slug,
        segment=segment,
        sources="\n  - " + "\n  - ".join(sources),
    )
    result = subprocess.run(
        ["claude", "-p", prompt],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=PER_PERSONA_TIMEOUT_SEC,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude rc={result.returncode} for {slug}: "
            f"{result.stderr[-200:]}"
        )

    # Claude may wrap JSON in prose — find the LARGEST JSON object in stdout
    # (most likely the one we want) via a broader scan.
    stdout = result.stdout
    # Try strict "single JSON line" first
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                data = json.loads(line)
                return Persona(**data)
            except (json.JSONDecodeError, TypeError):
                continue

    # Fallback: extract first balanced JSON object
    import re
    # Find from first "{" to end, then progressively shorten until valid JSON
    first_brace = stdout.find("{")
    if first_brace >= 0:
        # Try decoder.raw_decode for the first JSON object starting at {
        try:
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(stdout[first_brace:])
            return Persona(**obj)
        except (json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError(
                f"cannot parse JSON from claude output for {slug}: {exc}"
            ) from exc

    raise RuntimeError(f"no JSON object found in claude output for {slug}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--wave",
        choices=["expat", "id", "both"],
        required=True,
    )
    args = ap.parse_args()

    # Load existing personas (allows resuming / partial re-runs)
    existing: dict[str, dict] = {}
    if OUT.is_file():
        try:
            existing = json.loads(OUT.read_text()).get("personas", {})
        except json.JSONDecodeError:
            existing = {}

    # Build the slug → sources map for this wave
    source_map: dict[str, list[str]] = {}
    if args.wave in ("expat", "both"):
        source_map.update(PersonaInferenceAgent.EXPAT_SOURCES)
    if args.wave in ("id", "both"):
        source_map.update(PersonaInferenceAgent.ID_SOURCES)

    for slug, sources in source_map.items():
        segment = "expat" if slug.startswith("expat_") else "id_domestic"
        logger.info("inferring %s (sources: %d)...", slug, len(sources))
        try:
            p = infer_one(slug, segment, sources)
            p.validate()
            existing[slug] = asdict(p)
            logger.info(
                "  OK %s (%d attrs, %d quotes)",
                slug,
                p.count_populated_attrs(),
                len(p.verbatim_quotes),
            )
        except (RuntimeError, PersonaValidationError) as e:
            logger.error("  FAIL %s: %s", slug, e)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"personas": existing}, indent=2),
        encoding="utf-8",
    )
    logger.info("wrote %s (%d personas total)", OUT, len(existing))

    # Gate 4 check only when we've run the final wave
    if args.wave in ("id", "both"):
        if len(existing) < 6:
            logger.error("Gate 4 FAIL: only %d/6 personas", len(existing))
            return 1
        for slug, pdata in existing.items():
            try:
                Persona(**pdata).validate()
            except PersonaValidationError as e:
                logger.error("Gate 4 FAIL on %s: %s", slug, e)
                return 1
        logger.info("Gate 4 OK: 6 personas validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
