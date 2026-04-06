#!/usr/bin/env python3
"""
KBLI Silver Validation — NB-3 Quality Gate
============================================
Validates silver-tier generated content against source data using
Gemini 3.1 Pro Preview as fact-checker (NB-3 equivalent).

Runs AFTER kbli_silver_parallel.py completes.

Validation checks:
  1. Structural: all 6 fields present, min length, no empty
  2. Factual: Gemini reviews whatItMeans + baliContext against raw uraian/PMA data
  3. Consistency: zantaraOpener aligns with whatItMeans
  4. Hallucination: flags invented permits, wrong PMA status, fake locations

Usage:
  python scripts/kbli_silver_validate.py                    # validate all
  python scripts/kbli_silver_validate.py --sample 50        # random 50
  python scripts/kbli_silver_validate.py --fix              # auto-fix failed codes

Zero API cost — uses Gemini CLI subscription.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent

DATA_JSON = REPO_ROOT / "apps" / "kbli-navigator" / "data" / "kbli-2025.json"
GOLD_JSON = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"
SILVER_OUTPUT_DIR = SCRIPT_DIR / "output" / "silver_workers"
VALIDATION_REPORT = SCRIPT_DIR / "output" / "silver_validation_report.json"

GEMINI_CLI = "gemini"
GEMINI_MODEL = "gemini-3.1-pro-preview"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validation prompts
# ---------------------------------------------------------------------------

VALIDATION_PROMPT = """You are a strict quality auditor for KBLI 2025 business classification content aimed at foreign investors in Bali.

I will give you:
- The RAW source data (official Indonesian government data: code, judul, uraian, PMA status, risk level)
- The GENERATED content (whatItMeans, baliContext, zantaraOpener)

Your job: verify the generated content is ACCURATE, USEFUL, and NOT HALLUCINATED.

Check each field:

1. whatItMeans:
   - Does it correctly describe the business activity from the uraian?
   - Are Indonesian terms properly translated?
   - Is the scope accurate (not too broad, not too narrow)?
   - Score: 1-10

2. baliContext:
   - Is the Bali-specific info plausible and useful?
   - Does it mention real permits/regulations (not invented ones)?
   - Is the PMA status consistent with source data?
   - Does it avoid mentioning farming/land terms (HGU/Subak/LP2B) unless the code is actually about farming?
   - Score: 1-10

3. zantaraOpener:
   - Is it specific to this business activity (not generic)?
   - Does it align with whatItMeans?
   - Score: 1-10

4. Hallucination check:
   - Any invented permit names, fake regulations, wrong percentages?
   - Any claim that contradicts the source PMA status?
   - hallucination_detected: true/false

Respond ONLY with valid JSON (no markdown, no extra text):
{"results": [{"code": "XXXXX", "whatItMeans_score": N, "baliContext_score": N, "zantaraOpener_score": N, "hallucination_detected": true/false, "issues": ["issue1", "issue2"], "overall_pass": true/false}]}

An entry PASSES if: all scores >= 6 AND hallucination_detected == false.

Codes to validate:
"""


REGEN_PROMPT = """You are an expert on Indonesian business law writing precise, useful content for foreign investors in Bali.

The previous content for this KBLI code was flagged as LOW QUALITY. Regenerate it with higher accuracy.

Issues found: {issues}

For this KBLI 2025 code, generate THREE fields:

1. whatItMeans: Plain English explanation, 3-4 sentences, ~250-400 chars.
   - Lead with the core activity using a dash
   - Name SPECIFIC examples from the uraian — translate them
   - Translate ALL Indonesian terms. No bureaucratic language.

2. baliContext: Bali-specific practical intelligence, 3-5 sentences, ~350-550 chars.
   - Include at least ONE of: price range (IDR), Bali location, enforcement reality, named permit
   - Include ONE insider tip or common mistake specific to THIS code
   - ONLY mention HGU/Subak/LP2B if this code is directly about farming on Bali land

3. zantaraOpener: One conversational chatbot sentence, ~100-160 chars.
   - Start with Bali context
   - Be specific to the business activity

Respond ONLY with valid JSON:
{{"results": [{{"code": "XXXXX", "whatItMeans": "...", "baliContext": "...", "zantaraOpener": "..."}}]}}
No extra text, no markdown fences.

Source data:
code: {code}
judul: {judul}
uraian: {uraian}
pma_status: {pma_status} ({pma_max}%)
sektor_id: {sektor_id}"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def call_gemini_cli(prompt: str, timeout: int = 120) -> str:
    result = subprocess.run(
        [GEMINI_CLI, "--model", GEMINI_MODEL, "--prompt", prompt],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Gemini CLI error (rc={result.returncode}): {result.stderr[:300]}")
    lines = result.stdout.splitlines()
    clean = "\n".join(
        line for line in lines
        if not line.startswith("Keychain") and not line.startswith("Using") and
           not line.startswith("Loaded") and not line.startswith("Server") and
           not line.startswith("Scheduling") and not line.startswith("Executing") and
           not line.startswith("MCP")
    ).strip()
    return clean


def parse_llm_json(raw: str) -> list[dict]:
    text = raw
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    if "```" in text:
        if "```json" in text:
            text = text.split("```json", 1)[1].rsplit("```", 1)[0]
        else:
            text = text.split("```", 1)[1].rsplit("```", 1)[0]
    text = text.strip()
    parsed = json.loads(text)
    if isinstance(parsed, list):
        return parsed
    return parsed.get("results", [])


# ---------------------------------------------------------------------------
# Phase 1: Structural validation (no LLM needed)
# ---------------------------------------------------------------------------

def validate_structural(entries: dict[str, dict]) -> dict[str, list[str]]:
    """Check all entries have required fields with minimum content."""
    issues: dict[str, list[str]] = {}
    required_fields = ["whatItMeans", "whatYouNeed", "whatChanged", "baliContext", "youllAlsoNeed", "zantaraOpener"]
    min_lengths = {
        "whatItMeans": 80,
        "baliContext": 80,
        "zantaraOpener": 30,
        "whatYouNeed": 20,
        "whatChanged": 10,
    }

    for kode, entry in entries.items():
        code_issues = []
        for field in required_fields:
            if field not in entry:
                code_issues.append(f"MISSING field: {field}")
            elif not entry[field] or not entry[field].strip():
                code_issues.append(f"EMPTY field: {field}")
            elif field in min_lengths and len(entry[field]) < min_lengths[field]:
                code_issues.append(f"TOO SHORT: {field} ({len(entry[field])} chars, min {min_lengths[field]})")

        if code_issues:
            issues[kode] = code_issues

    return issues


# ---------------------------------------------------------------------------
# Phase 2: Factual validation via Gemini (NB-3 quality gate)
# ---------------------------------------------------------------------------

def validate_factual(
    sample_codes: list[str],
    entries: dict[str, dict],
    source_lookup: dict[str, dict],
    batch_size: int = 5,
) -> list[dict]:
    """
    Validate a sample of entries against source data using Gemini as fact-checker.
    Returns list of validation results.
    """
    all_results: list[dict] = []
    total = len(sample_codes)
    n_batches = (total + batch_size - 1) // batch_size

    for i in range(0, total, batch_size):
        batch_codes = sample_codes[i : i + batch_size]
        logger.info(f"  Validating batch {i // batch_size + 1}/{n_batches}: {batch_codes}")

        # Build validation prompt with source + generated data
        code_blocks = []
        for kode in batch_codes:
            src = source_lookup.get(kode, {})
            gen = entries.get(kode, {})
            block = (
                f"--- CODE: {kode} ---\n"
                f"SOURCE DATA:\n"
                f"  judul: {src.get('judul', 'N/A')}\n"
                f"  uraian: {src.get('uraian', 'N/A')[:500]}\n"
                f"  pma_status: {src.get('pma_status', 'N/A')} ({src.get('pma_max_asing', 'N/A')}%)\n"
                f"  sektor_id: {src.get('sektor_id', 'N/A')}\n"
                f"  kategori_risiko: {src.get('kategori_risiko', 'N/A')}\n\n"
                f"GENERATED CONTENT:\n"
                f"  whatItMeans: {gen.get('whatItMeans', 'MISSING')}\n"
                f"  baliContext: {gen.get('baliContext', 'MISSING')}\n"
                f"  zantaraOpener: {gen.get('zantaraOpener', 'MISSING')}\n"
            )
            code_blocks.append(block)

        full_prompt = VALIDATION_PROMPT + "\n\n".join(code_blocks)

        try:
            raw = call_gemini_cli(full_prompt, timeout=120)
            parsed = parse_llm_json(raw)
            all_results.extend(parsed)
            passed = sum(1 for r in parsed if r.get("overall_pass"))
            logger.info(f"    -> {len(parsed)} validated, {passed} passed")
        except Exception as e:
            logger.error(f"    -> Validation failed: {e}")
            # Mark batch as unvalidated
            for kode in batch_codes:
                all_results.append({
                    "code": kode,
                    "whatItMeans_score": 0,
                    "baliContext_score": 0,
                    "zantaraOpener_score": 0,
                    "hallucination_detected": False,
                    "issues": [f"Validation error: {str(e)[:100]}"],
                    "overall_pass": False,
                })

        time.sleep(2)  # Rate limit courtesy

    return all_results


# ---------------------------------------------------------------------------
# Phase 3: Auto-fix failed entries
# ---------------------------------------------------------------------------

def regenerate_failed(
    failed_codes: list[str],
    source_lookup: dict[str, dict],
    validation_results: list[dict],
) -> dict[str, dict]:
    """Regenerate entries that failed validation."""
    issues_map = {r["code"]: r.get("issues", []) for r in validation_results}
    regenerated: dict[str, dict] = {}

    for kode in failed_codes:
        src = source_lookup.get(kode, {})
        issues_str = "; ".join(issues_map.get(kode, ["low quality"]))

        prompt = REGEN_PROMPT.format(
            issues=issues_str,
            code=kode,
            judul=src.get("judul", ""),
            uraian=src.get("uraian", "")[:600],
            pma_status=src.get("pma_status", "TERBUKA"),
            pma_max=src.get("pma_max_asing", 100),
            sektor_id=src.get("sektor_id", "N/A"),
        )

        logger.info(f"  Regenerating {kode} (issues: {issues_str[:80]})")
        try:
            raw = call_gemini_cli(prompt, timeout=120)
            parsed = parse_llm_json(raw)
            if parsed:
                item = parsed[0]
                regenerated[kode] = {
                    "whatItMeans": item.get("whatItMeans", ""),
                    "baliContext": item.get("baliContext", ""),
                    "zantaraOpener": item.get("zantaraOpener", ""),
                }
                logger.info(f"    -> Regenerated OK")
        except Exception as e:
            logger.error(f"    -> Regen failed: {e}")

        time.sleep(2)

    return regenerated


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="KBLI Silver Validation — NB-3 Quality Gate")
    parser.add_argument("--sample", type=int, default=30, help="Number of random codes to validate factually (default: 30)")
    parser.add_argument("--fix", action="store_true", help="Auto-regenerate entries that fail validation")
    parser.add_argument("--structural-only", action="store_true", help="Only run structural checks, skip Gemini")
    args = parser.parse_args()

    logger.info("KBLI Silver Validation — NB-3 Quality Gate")

    # Load source data
    with open(DATA_JSON) as f:
        data = json.load(f)
    source_lookup = {c["kode_kbli_2025"]: c for c in data["data"]}

    # Load silver worker outputs
    silver_entries: dict[str, dict] = {}
    for wf in sorted(SILVER_OUTPUT_DIR.glob("worker_*.json")):
        with open(wf) as f:
            worker_data = json.load(f)
        # Strip internal metadata
        for kode in worker_data:
            worker_data[kode].pop("_provider", None)
        silver_entries.update(worker_data)
    logger.info(f"  Loaded {len(silver_entries)} silver entries from worker outputs")

    if not silver_entries:
        logger.error("No silver entries found — run kbli_silver_parallel.py first")
        sys.exit(1)

    # ── Phase 1: Structural validation ──
    logger.info("=" * 60)
    logger.info("PHASE 1 — STRUCTURAL VALIDATION")
    structural_issues = validate_structural(silver_entries)
    structural_fail = len(structural_issues)
    structural_pass = len(silver_entries) - structural_fail
    logger.info(f"  PASS: {structural_pass} | FAIL: {structural_fail}")
    if structural_issues:
        for kode, issues in list(structural_issues.items())[:5]:
            logger.warning(f"    {kode}: {issues}")
        if structural_fail > 5:
            logger.warning(f"    ... and {structural_fail - 5} more")

    if args.structural_only:
        _save_report(structural_issues, [], silver_entries)
        return

    # ── Phase 2: Factual validation via Gemini (NB-3 gate) ──
    logger.info("=" * 60)
    logger.info("PHASE 2 — FACTUAL VALIDATION (NB-3 Quality Gate)")

    # Sample: include all structural failures + random sample of passing
    structural_fail_codes = list(structural_issues.keys())
    passing_codes = [k for k in silver_entries if k not in structural_issues]
    random_sample_size = min(args.sample, len(passing_codes))
    random_sample = random.sample(passing_codes, random_sample_size)
    sample_codes = structural_fail_codes[:20] + random_sample  # Cap structural at 20

    logger.info(f"  Sample size: {len(sample_codes)} ({len(structural_fail_codes[:20])} structural fails + {len(random_sample)} random)")

    factual_results = validate_factual(sample_codes, silver_entries, source_lookup)

    # Analyze results
    passed = [r for r in factual_results if r.get("overall_pass")]
    failed = [r for r in factual_results if not r.get("overall_pass")]
    hallucinations = [r for r in factual_results if r.get("hallucination_detected")]

    avg_scores = {
        "whatItMeans": sum(r.get("whatItMeans_score", 0) for r in factual_results) / max(len(factual_results), 1),
        "baliContext": sum(r.get("baliContext_score", 0) for r in factual_results) / max(len(factual_results), 1),
        "zantaraOpener": sum(r.get("zantaraOpener_score", 0) for r in factual_results) / max(len(factual_results), 1),
    }

    logger.info(f"  RESULTS:")
    logger.info(f"    Passed:         {len(passed)}/{len(factual_results)} ({len(passed)/max(len(factual_results),1)*100:.0f}%)")
    logger.info(f"    Failed:         {len(failed)}")
    logger.info(f"    Hallucinations: {len(hallucinations)}")
    logger.info(f"    Avg whatItMeans:   {avg_scores['whatItMeans']:.1f}/10")
    logger.info(f"    Avg baliContext:   {avg_scores['baliContext']:.1f}/10")
    logger.info(f"    Avg zantaraOpener: {avg_scores['zantaraOpener']:.1f}/10")

    if failed:
        logger.info("  Failed codes:")
        for r in failed[:10]:
            logger.info(f"    {r['code']}: scores={r.get('whatItMeans_score',0)}/{r.get('baliContext_score',0)}/{r.get('zantaraOpener_score',0)} issues={r.get('issues', [])}")

    # ── Phase 3: Auto-fix (optional) ──
    if args.fix and failed:
        logger.info("=" * 60)
        logger.info("PHASE 3 — AUTO-FIX")
        failed_codes = [r["code"] for r in failed if r["code"] in source_lookup]
        logger.info(f"  Regenerating {len(failed_codes)} failed entries...")

        regenerated = regenerate_failed(failed_codes, source_lookup, factual_results)
        logger.info(f"  Regenerated: {len(regenerated)}/{len(failed_codes)}")

        # Update worker outputs with regenerated content
        if regenerated:
            # Write to a separate regen file
            regen_file = SILVER_OUTPUT_DIR / "worker_regen.json"
            existing_regen: dict = {}
            if regen_file.exists():
                with open(regen_file) as f:
                    existing_regen = json.load(f)

            # Merge with deterministic fields from source
            from kbli_silver_parallel import build_full_entry
            for kode, narrative in regenerated.items():
                code_obj = source_lookup[kode]
                existing_regen[kode] = build_full_entry(code_obj, narrative)

            with open(regen_file, "w") as f:
                json.dump(existing_regen, f, indent=2, ensure_ascii=False)
            logger.info(f"  Saved regenerated entries to {regen_file.name}")

    # ── Save report ──
    _save_report(structural_issues, factual_results, silver_entries)

    # ── Final verdict ──
    pass_rate = len(passed) / max(len(factual_results), 1) * 100
    if pass_rate >= 85:
        logger.info(f"\n  VERDICT: PASS ({pass_rate:.0f}% pass rate) — ready for merge")
    elif pass_rate >= 70:
        logger.info(f"\n  VERDICT: CONDITIONAL PASS ({pass_rate:.0f}%) — run with --fix to improve")
    else:
        logger.info(f"\n  VERDICT: FAIL ({pass_rate:.0f}%) — significant quality issues, review needed")


def _save_report(
    structural_issues: dict[str, list[str]],
    factual_results: list[dict],
    silver_entries: dict[str, dict],
) -> None:
    """Save validation report to JSON."""
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_entries": len(silver_entries),
        "structural": {
            "pass": len(silver_entries) - len(structural_issues),
            "fail": len(structural_issues),
            "issues": {k: v for k, v in list(structural_issues.items())[:50]},
        },
        "factual": {
            "sample_size": len(factual_results),
            "pass": sum(1 for r in factual_results if r.get("overall_pass")),
            "fail": sum(1 for r in factual_results if not r.get("overall_pass")),
            "hallucinations": sum(1 for r in factual_results if r.get("hallucination_detected")),
            "avg_scores": {
                "whatItMeans": round(sum(r.get("whatItMeans_score", 0) for r in factual_results) / max(len(factual_results), 1), 2),
                "baliContext": round(sum(r.get("baliContext_score", 0) for r in factual_results) / max(len(factual_results), 1), 2),
                "zantaraOpener": round(sum(r.get("zantaraOpener_score", 0) for r in factual_results) / max(len(factual_results), 1), 2),
            },
            "results": factual_results,
        },
    }

    VALIDATION_REPORT.parent.mkdir(parents=True, exist_ok=True)
    with open(VALIDATION_REPORT, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info(f"  Report saved to {VALIDATION_REPORT}")


if __name__ == "__main__":
    main()
