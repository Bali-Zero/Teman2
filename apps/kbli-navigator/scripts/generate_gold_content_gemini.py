#!/usr/bin/env python3
"""
KBLI Gold Content Generator — Gemini CLI backend
Same logic as generate_gold_content.py but uses `gemini -p` subprocess instead of Ollama.

Usage:
  # Process codes 601-1247 (complement to qwen run doing 0-600)
  python scripts/generate_gold_content_gemini.py --skip-existing --range-start 600

  # Test first
  python scripts/generate_gold_content_gemini.py --skip-existing --range-start 600 --limit 5 --dry-run

  # Full range
  python scripts/generate_gold_content_gemini.py --skip-existing --range-start 600 --range-end 1247
"""

import json
import sys
import re
import argparse
import subprocess
from pathlib import Path

# Reuse all helpers from the main script
sys.path.insert(0, str(Path(__file__).parent))
from generate_gold_content import (
    load_kbli,
    load_existing_codes,
    build_what_you_need,
    build_what_changed,
    build_youll_also_need,
    format_ts_entry,
    append_to_gold_ts,
    SYSTEM_PROMPT,
    FEW_SHOT,
    GOLD_TS,
)


def gemini_generate(prompt: str) -> str:
    """Call `gemini -p PROMPT` and return the response text."""
    full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
    result = subprocess.run(
        ["gemini", "-p", full_prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gemini CLI error: {result.stderr[:300]}")
    return result.stdout.strip()


def enrich_llm_fields_gemini(targets: list[dict], batch_size: int = 3) -> dict[str, dict]:
    """Returns {code: {whatItMeans, baliContext, zantaraOpener}} using Gemini CLI."""
    results: dict[str, dict] = {}
    total = len(targets)

    for i in range(0, total, batch_size):
        batch = targets[i : i + batch_size]

        batch_text = "\n\n".join(
            f"code: {c['kode_kbli_2025']}\n"
            f"judul: {c['judul']}\n"
            f"uraian: {c.get('uraian', '')[:600]}\n"
            f"pma_status: {c.get('pma_status', 'TERBUKA')} ({c.get('pma_max_asing', 100)}%)\n"
            f"sektor_id: {c.get('sektor_id', 'N/A')}"
            for c in batch
        )

        print(
            f"  Gemini batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}"
            f": {len(batch)} codes...",
            end="",
            flush=True,
        )

        raw = ""
        try:
            raw = gemini_generate(batch_text)

            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            parsed = json.loads(raw)

            for item in parsed.get("results", []):
                code_key = item.get("code")
                if code_key:
                    results[code_key] = {
                        "whatItMeans": item.get("whatItMeans", ""),
                        "baliContext": item.get("baliContext", ""),
                        "zantaraOpener": item.get("zantaraOpener", ""),
                    }

            print(f" ✓ ({min(i + batch_size, total)}/{total})")

        except (json.JSONDecodeError, KeyError) as e:
            print(f" ✗ Parse error: {e}")
            if raw:
                print(f"    Raw (first 300): {raw[:300]}")
        except subprocess.TimeoutExpired:
            print(" ✗ Timeout")
        except Exception as e:
            print(f" ✗ Error: {e}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate KBLIGoldContent entries using Gemini CLI"
    )
    parser.add_argument("--sector", help="Process only this sector ID")
    parser.add_argument("--limit", type=int, help="Max codes to process")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--batch-size", type=int, default=3, help="Gemini batch size (default: 3)")
    parser.add_argument("--range-start", type=int, default=0)
    parser.add_argument("--range-end", type=int, default=None)
    args = parser.parse_args()

    codes = load_kbli()
    existing = load_existing_codes()
    print(f"Loaded {len(codes)} KBLI codes. {len(existing)} already in gold-content.ts.")

    targets = codes
    if args.skip_existing:
        targets = [c for c in targets if c["kode_kbli_2025"] not in existing]
        print(f"After --skip-existing: {len(targets)} codes remaining.")
    if args.sector:
        targets = [c for c in targets if str(c.get("sektor_id") or "None") == args.sector]
        print(f"After --sector {args.sector}: {len(targets)} codes.")
    if args.limit:
        targets = targets[: args.limit]
        print(f"After --limit {args.limit}: {len(targets)} codes.")
    if args.range_start or args.range_end:
        end = args.range_end if args.range_end is not None else len(targets)
        targets = targets[args.range_start : end]
        print(f"After --range-start {args.range_start} --range-end {end}: {len(targets)} codes.")

    if not targets:
        print("Nothing to process.")
        return

    print(f"\nProcessing {len(targets)} codes via Gemini CLI...")

    # Phase 1: Deterministic fields
    print("\n[1/2] Building deterministic fields...")
    gold_data: dict[str, dict] = {}
    for c in targets:
        code = c["kode_kbli_2025"]
        gold_data[code] = {
            "whatYouNeed": build_what_you_need(c),
            "whatChanged": build_what_changed(c),
            "youllAlsoNeed": build_youll_also_need(c),
            "whatItMeans": "",
            "baliContext": "",
            "zantaraOpener": "",
        }
    print(f"  ✓ Deterministic fields built for {len(targets)} codes.")

    if args.skip_llm:
        print("[LLM skipped — --skip-llm flag set]")
    else:
        # Phase 2: Gemini LLM fields
        print(f"\n[2/2] LLM enrichment via Gemini CLI (batch_size={args.batch_size})...")
        llm_results = enrich_llm_fields_gemini(targets, batch_size=args.batch_size)

        for code, llm_fields in llm_results.items():
            if code in gold_data:
                gold_data[code].update(llm_fields)

        print(f"  ✓ LLM fields received for {len(llm_results)}/{len(targets)} codes.")

    entries = [(code, content) for code, content in gold_data.items()]
    entries.sort(key=lambda x: x[0])

    if args.dry_run:
        print(f"\n[DRY RUN] {len(entries)} entries ready. Sample output:")
        for code, content in entries[:2]:
            print(f"\n--- {code} ---")
            print(f"whatItMeans: {content.get('whatItMeans', '')[:150]}...")
            print(f"baliContext: {content.get('baliContext', '')[:150]}...")
            print(f"zantaraOpener: {content.get('zantaraOpener', '')[:100]}...")
        print(f"\n[DRY RUN] Run without --dry-run to write {len(entries)} entries.")
        return

    print(f"\nWriting {len(entries)} entries to kbli-gold-content.ts...")
    append_to_gold_ts(entries, dry_run=False)


if __name__ == "__main__":
    main()
