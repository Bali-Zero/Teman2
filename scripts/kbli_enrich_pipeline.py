#!/usr/bin/env python3
"""
KBLI Full-Spectrum Enrichment Pipeline
Orchestrates all 4 phases: Triage → Generate → Validate → Write

Usage:
  python scripts/kbli_enrich_pipeline.py                    # Full run
  python scripts/kbli_enrich_pipeline.py --phase 0          # Triage only
  python scripts/kbli_enrich_pipeline.py --phase 1          # Generate only (requires triage)
  python scripts/kbli_enrich_pipeline.py --phase 2          # Validate only
  python scripts/kbli_enrich_pipeline.py --phase 3          # Write only
  python scripts/kbli_enrich_pipeline.py --resume            # Resume from last checkpoint
  python scripts/kbli_enrich_pipeline.py --dry-run           # Don't write final output
  python scripts/kbli_enrich_pipeline.py --tier HIGH         # Process only HIGH tier
  python scripts/kbli_enrich_pipeline.py --limit 10          # Process max 10 codes
"""
import json
import sys
import argparse
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.kbli_enrich_db import (
    get_conn, init_codes, set_triage, set_state, set_nlm_context,
    set_generated, set_validated, set_failed, get_codes_by_state,
    get_codes_by_tier, get_stats, get_tier_stats, set_meta, get_meta,
)
from scripts.kbli_enrich_triage import run_triage
from scripts.kbli_enrich_deterministic import build_deterministic_fields
from scripts.kbli_enrich_generate import generate_high_tier, generate_medium_tier, generate_low_tier
from scripts.kbli_enrich_nlm import query_regulatory_intel
from scripts.kbli_enrich_validate import validate_batch
from scripts.kbli_enrich_write import merge_and_write, test_build

DATA_JSON = Path(__file__).parent.parent / "apps" / "kbli-navigator" / "data" / "kbli-2025.json"
GOLD_JSON = Path(__file__).parent.parent / "apps" / "mouth" / "data" / "kbli-gold-all.json"


def load_source_data() -> tuple[list[dict], dict[str, dict]]:
    """Load KBLI source data. Returns (list, {code: entry} lookup)."""
    with open(DATA_JSON) as f:
        data = json.load(f)
    entries = data["data"]
    lookup = {c["kode_kbli_2025"]: c for c in entries}
    return entries, lookup


def get_unenriched_codes(all_codes: list[dict]) -> list[dict]:
    """Filter to codes not already in kbli-gold-all.json."""
    existing = set()
    if GOLD_JSON.exists():
        with open(GOLD_JSON) as f:
            existing = set(json.load(f).keys())
    return [c for c in all_codes if c["kode_kbli_2025"] not in existing]


def phase_0_triage(conn, codes: list[dict]) -> None:
    """Phase 0: Classify codes into HIGH/MEDIUM/LOW via Gemini CLI."""
    print(f"\n{'='*60}")
    print(f"PHASE 0 — TRIAGE ({len(codes)} codes)")
    print(f"{'='*60}")

    already_triaged = get_codes_by_state(conn, "TRIAGED")
    if already_triaged:
        print(f"  {len(already_triaged)} codes already triaged, skipping...")
        triaged_codes = {r["code"] for r in already_triaged}
        codes = [c for c in codes if c["kode_kbli_2025"] not in triaged_codes]

    if not codes:
        print("  All codes already triaged.")
        return

    results = run_triage(codes)

    for r in results:
        set_triage(conn, r["code"], r.get("tier", "LOW"), r.get("score", 0), r.get("reasoning", ""))

    stats = get_tier_stats(conn)
    print(f"\n  Tier distribution: {stats}")
    set_meta(conn, "phase_0_completed", time.strftime("%Y-%m-%d %H:%M:%S"))


def phase_1_generate(conn, source_lookup: dict, tier_filter: str = None) -> None:
    """Phase 1: Generate content for all tiers."""
    print(f"\n{'='*60}")
    print(f"PHASE 1 — GENERATE")
    print(f"{'='*60}")

    for tier in (["HIGH", "MEDIUM", "LOW"] if not tier_filter else [tier_filter]):
        tier_codes = get_codes_by_tier(conn, tier)
        # Filter to only TRIAGED state (not already GENERATED/COMPLETED)
        pending = [c for c in tier_codes if c["state"] == "TRIAGED"]
        if not pending:
            print(f"\n  {tier}: No pending codes.")
            continue

        print(f"\n  {tier} TIER: {len(pending)} codes to process")

        # Get source data for these codes
        code_data = [source_lookup[c["code"]] for c in pending if c["code"] in source_lookup]

        if tier == "HIGH":
            # NLM enrichment first (pairs of 2)
            print("  Querying NLM for regulatory intel...")
            nlm_contexts = {}
            for i in range(0, len(code_data), 2):
                batch = code_data[i:i+2]
                try:
                    contexts = query_regulatory_intel(batch)
                    nlm_contexts.update(contexts)
                    for code in contexts:
                        set_nlm_context(conn, code, contexts[code])
                except Exception as e:
                    print(f"    NLM error: {e}")

            # DeepSeek generation
            print("  Generating with DeepSeek-R1:32b...")
            narrative = generate_high_tier(code_data, nlm_contexts, batch_size=2)

        elif tier == "MEDIUM":
            print("  Generating with Qwen3.5:9b...")
            narrative = generate_medium_tier(code_data, batch_size=5)

        else:  # LOW
            print("  Generating minimal content with Qwen3.5:9b...")
            narrative = generate_low_tier(code_data, batch_size=10)

        # Merge narrative + deterministic for each code
        for c in code_data:
            code = c["kode_kbli_2025"]
            set_state(conn, code, "GENERATING")

            # Deterministic fields (always generated)
            det = build_deterministic_fields(c)

            # Narrative fields (from LLM)
            narr = narrative.get(code, {})

            # Merge: narrative fields + deterministic fields
            merged = {
                "whatItMeans": narr.get("whatItMeans", ""),
                "whatYouNeed": det["whatYouNeed"],
                "whatChanged": det["whatChanged"],
                "baliContext": narr.get("baliContext", ""),
                "youllAlsoNeed": det["youllAlsoNeed"],
                "zantaraOpener": narr.get("zantaraOpener", ""),
            }

            set_generated(conn, code, merged)

    set_meta(conn, "phase_1_completed", time.strftime("%Y-%m-%d %H:%M:%S"))


def phase_2_validate(conn, source_lookup: dict) -> None:
    """Phase 2: Validate all GENERATED entries."""
    print(f"\n{'='*60}")
    print(f"PHASE 2 — VALIDATE")
    print(f"{'='*60}")

    generated = get_codes_by_state(conn, "GENERATED")
    if not generated:
        print("  No entries to validate.")
        return

    print(f"  Validating {len(generated)} entries...")

    entries = {}
    for row in generated:
        code = row["code"]
        content = json.loads(row["generated_content"]) if row["generated_content"] else {}
        entries[code] = content

    errors = validate_batch(entries, source_lookup)

    passed = 0
    failed = 0
    for code in entries:
        code_errors = errors.get(code, [])
        if code_errors:
            set_failed(conn, code, code_errors)
            failed += 1
        else:
            set_validated(conn, code)
            passed += 1

    print(f"  Passed: {passed}, Failed: {failed}")
    if failed > 0:
        print(f"  Run with --phase 1 to retry failed codes")

    set_meta(conn, "phase_2_completed", time.strftime("%Y-%m-%d %H:%M:%S"))


def phase_3_write(conn, dry_run: bool = False) -> None:
    """Phase 3: Write all COMPLETED entries to kbli-gold-all.json."""
    print(f"\n{'='*60}")
    print(f"PHASE 3 — WRITE")
    print(f"{'='*60}")

    completed = get_codes_by_state(conn, "COMPLETED")
    if not completed:
        print("  No completed entries to write.")
        return

    entries = {}
    for row in completed:
        content = json.loads(row["generated_content"]) if row["generated_content"] else {}
        entries[row["code"]] = content

    count = merge_and_write(entries, dry_run=dry_run)

    if not dry_run and count > 0:
        print("\n  Running build test...")
        if test_build():
            set_meta(conn, "phase_3_completed", time.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            print("  WARNING: Build failed! Check output manually.")


def main():
    parser = argparse.ArgumentParser(description="KBLI Full-Spectrum Enrichment Pipeline")
    parser.add_argument("--phase", type=int, choices=[0, 1, 2, 3], help="Run specific phase only")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--dry-run", action="store_true", help="Don't write final output")
    parser.add_argument("--tier", choices=["HIGH", "MEDIUM", "LOW"], help="Process only this tier")
    parser.add_argument("--limit", type=int, help="Max codes to process")
    args = parser.parse_args()

    all_codes, source_lookup = load_source_data()
    unenriched = get_unenriched_codes(all_codes)

    if args.limit:
        unenriched = unenriched[:args.limit]

    print(f"KBLI Enrichment Pipeline")
    print(f"  Total codes: {len(all_codes)}")
    print(f"  Unenriched: {len(unenriched)}")
    print(f"  Phase: {'ALL' if args.phase is None else args.phase}")

    conn = get_conn()
    init_codes(conn, unenriched)

    if args.resume:
        stats = get_stats(conn)
        print(f"  Resuming from checkpoint: {stats}")

    if args.phase is None or args.phase == 0:
        pending = get_codes_by_state(conn, "PENDING")
        pending_data = [source_lookup[c["code"]] for c in pending if c["code"] in source_lookup]
        if pending_data:
            phase_0_triage(conn, pending_data)

    if args.phase is None or args.phase == 1:
        phase_1_generate(conn, source_lookup, tier_filter=args.tier)

    if args.phase is None or args.phase == 2:
        phase_2_validate(conn, source_lookup)

    if args.phase is None or args.phase == 3:
        phase_3_write(conn, dry_run=args.dry_run)

    # Final stats
    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE")
    print(f"{'='*60}")
    stats = get_stats(conn)
    print(f"  State distribution: {stats}")
    tier_stats = get_tier_stats(conn)
    print(f"  Tier distribution: {tier_stats}")
    conn.close()


if __name__ == "__main__":
    main()
