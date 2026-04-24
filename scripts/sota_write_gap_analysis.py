#!/usr/bin/env python3
"""Fase 0 Day 7 driver — gap analysis → 07_gap_analysis.md.

TWO-MODE SCRIPT:
  - FULL mode (when 02_competitor_corpus.json exists): Claude compares
    @balizero0 corpus vs 18 competitors, ≥15 gaps + ≥8 strengths.
  - PARTIAL mode (competitor corpus missing, Vino not done yet): Claude
    analyzes ONLY @balizero0 empirical corpus against literature-derived
    best practices. Produces a "pre-Vino" gap analysis. Re-run once
    competitor CSV arrives to upgrade to FULL mode.

Both modes require:
  - claude CLI in PATH (not gemini — see DISCOVERY 2026-04-23 re: 429)
  - research/sota-social-2026-v1/01_balizero_corpus.json
  - research/sota-social-2026-v1/03_sota_literature.md
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
RESEARCH = _REPO_ROOT / "research" / "sota-social-2026-v1"

OUT = RESEARCH / "07_gap_analysis.md"
EMPIRICAL = RESEARCH / "01_balizero_corpus.json"
BENCHMARK = RESEARCH / "02_competitor_corpus.json"
LITERATURE = RESEARCH / "03_sota_literature.md"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.day7.gap")

PER_CALL_TIMEOUT_SEC = 900  # 15 min


def _build_full_prompt(empirical: str, benchmark: str) -> str:
    return f"""You are the gap analyst for Bali Zero's social media research.

INPUTS:
- Empirical corpus (25 own @balizero0 posts classified hook/tone/topic/format):
<<<EMPIRICAL_START>>>
{empirical[:60000]}
<<<EMPIRICAL_END>>>

- Benchmark corpus (18 competitor accounts × 15 posts each):
<<<BENCHMARK_START>>>
{benchmark[:120000]}
<<<BENCHMARK_END>>>

PRODUCE a markdown document with these sections (use these exact headings):

## Gaps

At least 15 specific weaknesses of @balizero0 vs competition. Format each gap as:

### Gap N: <one-line observation>

<2-3 sentences explaining the gap, citing specific post IDs from the JSONs.>

**Action:** <concrete remedy in one sentence>

## Strengths

At least 8 areas where @balizero0 outperforms competitors, same format but with
**Double down:** <how to amplify> instead of Action.

## Top performer patterns

5-10 specific post patterns from the benchmark corpus that @balizero0 is NOT
using but should try. Each with the competitor handle + post_id that
demonstrates the pattern.

Cite post IDs (e.g. `p12` or `18100502363319462`) for every claim. No vague
"competitors do X better" — always point to a specific example."""


def _build_partial_prompt(empirical: str, literature: str) -> str:
    return f"""You are producing a gap analysis document for Bali Zero.

CRITICAL OUTPUT DIRECTIVE: Your reply is the markdown document itself.
Do NOT summarize what you would do, do NOT describe the document you
wrote to a file, do NOT use phrases like "Deliverable written to..." or
"Counts verified:". Just write the markdown content directly. The very
first line of your reply MUST be `## Gaps (vs literature best practices)`.

Competitor corpus is not yet available (team scraping in progress). Analyze
only the empirical @balizero0 corpus against best practices from the
literature synthesis.

INPUTS:
- Empirical corpus (25 own @balizero0 posts):
<<<EMPIRICAL_START>>>
{empirical[:60000]}
<<<EMPIRICAL_END>>>

- Literature synthesis (hook taxonomy, tone for B2B legal, cadence, format
  matrix — from Gemini Deep Research Day 3):
<<<LITERATURE_START>>>
{literature[:80000]}
<<<LITERATURE_END>>>

Required document structure (copy these heading levels exactly):

## Gaps (vs literature best practices)

### Gap 1: <one-line observation>

<2-3 sentences citing specific post IDs from the empirical JSON and the
literature finding it violates.>

**Action:** <concrete remedy>

### Gap 2: <observation>

...(continue until at least Gap 15)

## Strengths

### Strength 1: <observation>

<2-3 sentences with post ID citations>

**Double down:** <how to amplify>

...(continue until at least Strength 8)

## Open questions for Vino's competitor benchmark

### Q1: <question>

<one sentence on what the competitor corpus answer will enable>

...(5 to 8 questions total)

Cite post IDs for every empirical claim. No vague prose. Emit the
markdown directly; your entire reply IS the document."""


def main() -> int:
    if not EMPIRICAL.is_file():
        logger.error("empirical corpus missing: %s", EMPIRICAL)
        return 2

    empirical = EMPIRICAL.read_text(encoding="utf-8")

    if BENCHMARK.is_file():
        logger.info("FULL mode — both corpora present")
        benchmark = BENCHMARK.read_text(encoding="utf-8")
        prompt = _build_full_prompt(empirical, benchmark)
        mode = "full"
    elif LITERATURE.is_file():
        logger.info("PARTIAL mode — competitor corpus missing, using literature")
        literature = LITERATURE.read_text(encoding="utf-8")
        prompt = _build_partial_prompt(empirical, literature)
        mode = "partial"
    else:
        logger.error(
            "neither %s nor %s available — need at least one",
            BENCHMARK,
            LITERATURE,
        )
        return 2

    logger.info("calling claude -p (%d chars prompt, mode=%s)...", len(prompt), mode)
    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=PER_CALL_TIMEOUT_SEC,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.error("claude invocation failed: %s", exc)
        return 1

    if result.returncode != 0:
        logger.error(
            "claude rc=%s stderr=%s",
            result.returncode,
            result.stderr[-400:],
        )
        return 1

    body = result.stdout or ""
    header = (
        f"# SOTA Gap Analysis ({mode} mode)\n\n"
        f"> Auto-generated by `scripts/sota_write_gap_analysis.py` Day 7.\n"
        f"> Mode: **{mode.upper()}** — "
        + (
            "both empirical + benchmark corpora present."
            if mode == "full"
            else "competitor corpus missing (Vino still scraping), analysis based on empirical + literature only. Re-run this script after Vino delivers `02_competitor_corpus.json` to upgrade to FULL mode."
        )
        + "\n\n---\n\n"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(header + body, encoding="utf-8")
    logger.info("wrote %s (%d chars)", OUT, len(body))

    # Sanity count: ≥15 gaps + ≥8 strengths expected in FULL; lenient in PARTIAL
    gap_count = body.count("**Action:**")
    strength_count = body.count("**Double down:**")
    logger.info("gaps=%d strengths=%d", gap_count, strength_count)

    if mode == "full":
        if gap_count < 15 or strength_count < 8:
            logger.error(
                "Gap analysis insufficient (full mode): gaps=%d/15 strengths=%d/8",
                gap_count,
                strength_count,
            )
            return 1
    else:
        if gap_count < 10 or strength_count < 5:
            logger.warning(
                "Gap analysis thin (partial mode): gaps=%d/10 strengths=%d/5",
                gap_count,
                strength_count,
            )
            # PARTIAL mode is non-blocking — still exits 0, flagged in output.

    return 0


if __name__ == "__main__":
    sys.exit(main())
