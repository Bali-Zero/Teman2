#!/usr/bin/env python3
"""Phase 0: Classify 1,241 KBLI codes into HIGH/MEDIUM/LOW Bali relevance using Gemini CLI.
Runs 6 parallel Gemini CLI processes (batches of ~200 codes each).
"""
import json
import subprocess
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

GEMINI_BIN = "/opt/homebrew/bin/gemini"

TRIAGE_PROMPT_TEMPLATE = """You are an expert on Indonesian business classification (KBLI 2025) and foreign investment in Bali.

Classify each KBLI code below into exactly one tier based on Bali relevance for foreign investors (PT PMA):

**HIGH** — Directly relevant to Bali's economy: tourism, hospitality, F&B, real estate, wellness/spa, tech/digital nomad services, creative industries, education (yoga/surf/beauty academies), healthcare (clinics/IV drips), sports facilities (padel/gyms), transport (rental/ride-hailing), professional services commonly used by expats (legal, consulting, architecture, photography).

**MEDIUM** — Indirectly relevant or general business: wholesale/retail trade, general manufacturing, logistics, financial services, HR/staffing, general education, telecoms, media production, environmental services. Could serve Bali market but not specifically Bali-centric.

**LOW** — Minimal Bali relevance: heavy industry, mining, oil/gas, large-scale agriculture (non-Bali crops), government services, military/defense, public utilities, highly restricted sectors, obscure niche manufacturing. Also includes BPS_ONLY codes with no PP28 licensing data.

For each code, respond with ONLY a JSON array. No extra text, no markdown fences:
[{{"code": "XXXXX", "tier": "HIGH|MEDIUM|LOW", "score": 0-100, "reasoning": "one sentence"}}]

Here are the codes to classify:

{codes_block}
"""


def format_code_block(codes: list[dict]) -> str:
    """Format codes for the Gemini prompt."""
    lines = []
    for c in codes:
        per_skala_summary = "none" if not c.get("per_skala") else f"{len(c['per_skala'])} scale(s)"
        lines.append(
            f"- {c['kode_kbli_2025']}: {c['judul']} | PMA: {c.get('pma_status', '?')} | "
            f"Mapping: {c.get('status_mapping', '?')} | Licensing: {per_skala_summary}"
        )
    return "\n".join(lines)


def run_gemini_batch(batch_id: int, codes: list[dict], output_dir: Path) -> Path:
    """Run a single Gemini CLI triage batch. Returns path to output JSON file."""
    codes_block = format_code_block(codes)
    prompt = TRIAGE_PROMPT_TEMPLATE.format(codes_block=codes_block)

    output_file = output_dir / f"triage_batch_{batch_id}.json"

    # Write prompt to temp file to avoid shell escaping issues
    prompt_file = output_dir / f"triage_prompt_{batch_id}.txt"
    prompt_file.write_text(prompt)

    try:
        result = subprocess.run(
            [GEMINI_BIN, "-p", prompt],
            capture_output=True, text=True, timeout=300,
            cwd=str(Path(__file__).parent.parent)
        )

        raw = result.stdout.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        parsed = json.loads(raw)
        output_file.write_text(json.dumps(parsed, indent=2, ensure_ascii=False))
        print(f"  Batch {batch_id}: {len(parsed)} codes classified ✓")
        return output_file

    except subprocess.TimeoutExpired:
        print(f"  Batch {batch_id}: TIMEOUT (300s)")
        return output_file
    except json.JSONDecodeError as e:
        print(f"  Batch {batch_id}: JSON parse error: {e}")
        # Save raw for debugging
        raw_out = result.stdout if result else ""
        (output_dir / f"triage_raw_{batch_id}.txt").write_text(raw_out)
        return output_file
    except Exception as e:
        print(f"  Batch {batch_id}: Error: {e}")
        return output_file


def run_triage(codes: list[dict], batch_size: int = 200, max_workers: int = 6) -> list[dict]:
    """Run Phase 0 triage: classify all codes in parallel Gemini CLI batches.
    Returns list of {code, tier, score, reasoning} dicts.
    """
    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(exist_ok=True)

    # Split into batches
    batches = [codes[i:i + batch_size] for i in range(0, len(codes), batch_size)]
    print(f"Phase 0 — Triage: {len(codes)} codes in {len(batches)} batches (max {max_workers} parallel)")

    all_results = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_gemini_batch, i, batch, output_dir): i
            for i, batch in enumerate(batches)
        }
        for future in as_completed(futures):
            batch_id = futures[future]
            try:
                output_file = future.result()
                if output_file.exists():
                    batch_results = json.loads(output_file.read_text())
                    all_results.extend(batch_results)
            except Exception as e:
                print(f"  Batch {batch_id} failed: {e}")

    # Save merged results
    merged_file = output_dir / "triage_results.json"
    merged_file.write_text(json.dumps(all_results, indent=2, ensure_ascii=False))
    print(f"  Total classified: {len(all_results)} codes → {merged_file}")

    return all_results
