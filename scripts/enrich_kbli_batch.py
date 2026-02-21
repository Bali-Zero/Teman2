#!/usr/bin/env python3
"""
KBLI Base Enrichment Script
Populates intel_2026 fields for unenriched KBLI codes.
"""
import json
import sys
import argparse
import urllib.request
from pathlib import Path

JSON_PATH = Path(__file__).parent.parent / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

RISK_MAP = {
    'Rendah': ('Low risk', 'NIB only — issued automatically.'),
    'Menengah Rendah': ('Medium-Low risk', 'NIB + Standard Certificate — issued automatically.'),
    'Menengah Tinggi': ('Medium-High risk', 'NIB + Standard Certificate — issued within 7 working days.'),
    'Tinggi': ('High risk', 'NIB + Business License (Izin) — full review required.'),
}

SCALE_MAP = {
    'Mikro': 'Micro', 'Kecil': 'Small', 'Menengah': 'Medium', 'Besar': 'Large',
}

STATUS_MAP = {
    'MATCH_LANGSUNG': 'Unchanged from KBLI 2020 — direct match.',
    'CODICE_RINUMERATO': 'Renumbered/adjusted from KBLI 2020. OSS update may be required to register under the new code.',
    'MATCH_CON_AGGREGAZIONE': 'This code aggregates multiple KBLI 2020 activities. Verify your specific activity maps correctly.',
    'BPS_ONLY': 'New code in KBLI 2025 — no direct equivalent in KBLI 2020. Register fresh on OSS.',
}


def load_json() -> dict:
    with open(JSON_PATH) as f:
        return json.load(f)


def save_json(data: dict) -> None:
    with open(JSON_PATH, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def derive_what_you_need(code: dict) -> str:
    lines = []
    seen = set()
    for s in code.get('per_skala', []):
        scales = s.get('skala_usaha', [])
        risk = s.get('kategori_risiko', '')
        if risk not in RISK_MAP:
            continue
        scale_str = ' / '.join(SCALE_MAP.get(sc, sc) for sc in scales)
        risk_en, license_en = RISK_MAP[risk]
        key = (scale_str, risk_en)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"**{scale_str} scale**: {risk_en}. {license_en}")

    pma_status = code.get('pma_status', '')
    pma_max = code.get('pma_max_asing', 0)
    pma_kondisi = code.get('pma_kondisi') or ''
    pma_nota = code.get('pma_nota') or ''

    if pma_status == 'TERBUKA':
        pma_line = f"**PMA:** Fully open to PMA — {pma_max}% foreign ownership allowed."
    elif pma_status == 'TERTUTUP':
        pma_line = "**PMA:** Closed to foreign investment — domestic only."
    elif pma_status == 'TERBATAS':
        pma_line = f"**PMA:** Limited — max {pma_max}% foreign ownership."
    else:
        pma_line = ""

    if pma_kondisi:
        pma_line += f" Condition: {pma_kondisi}."
    if pma_nota and pma_nota not in pma_line:
        pma_line += f" Note: {pma_nota}."

    all_parts = lines + ([pma_line] if pma_line else [])
    return '\n\n'.join(all_parts)


def derive_what_changed(code: dict) -> str:
    mapping = code.get('status_mapping') or 'None'
    return STATUS_MAP.get(mapping, f'Status: {mapping}.')


def get_unenriched(codes: list, sector: str | None = None, limit: int | None = None,
                   refill_empty: bool = False) -> list:
    if refill_empty:
        # Include codes that have intel_2026 but missing LLM fields
        result = [c for c in codes if not c.get('intel_2026') or not c['intel_2026'].get('whatItMeans')]
    else:
        result = [c for c in codes if not c.get('intel_2026')]
    if sector:
        result = [c for c in result if str(c.get('sektor_id', 'None')) == sector]
    if limit:
        result = result[:limit]
    return result


def print_stats(codes: list) -> None:
    total = len(codes)
    enriched = sum(1 for c in codes if c.get('intel_2026'))
    print(f"\nTotal: {total} | Enriched: {enriched} | Missing: {total - enriched}")

    # By sector
    sectors = {}
    for c in codes:
        sid = str(c.get('sektor_id', 'None'))
        sectors.setdefault(sid, {'total': 0, 'enriched': 0})
        sectors[sid]['total'] += 1
        if c.get('intel_2026'):
            sectors[sid]['enriched'] += 1

    print("\nSector breakdown (missing ascending):")
    for sid, info in sorted(sectors.items(), key=lambda x: x[1]['total'] - x[1]['enriched']):
        missing = info['total'] - info['enriched']
        pct = info['enriched'] / info['total'] * 100
        print(f"  {sid:<10} {info['enriched']:>4}/{info['total']:<4} ({pct:>5.1f}%) missing={missing}")


FEW_SHOT_EXAMPLES = """
EXAMPLE 1:
code: 01131
judul: PERTANIAN SAYURAN DAUN
uraian: Kelompok ini mencakup kegiatan pertanian sayuran yang daun, bunga atau batangnya dimakan sebagai sayur, seperti articok, petsai/sawi, asparagus, kubis/kol, kembang kol, brokoli, selada, seledri, daun bawang, bawang daun, bayam, kangkung, dll.
→ whatItMeans: "Growing leafy vegetables — spinach, kale, cabbage, lettuce, pak choi, kangkung, celery, leeks, and similar greens. This covers any farm activity where the leaf, stem, or flower of the plant is the edible product. It includes soil prep, planting, watering, and harvesting on the farm itself."
→ zantaraOpener: "Planning a leafy vegetable farm in Bali? Let me walk you through the licensing, land rules, and how to structure this as a PMA operation."

EXAMPLE 2:
code: 01138
judul: PERTANIAN CABAI
uraian: Kelompok ini mencakup kegiatan pertanian cabai (Capsicum spp), seperti cabai besar, cabai rawit, cabai keriting, dan paprika. Pertanian cabai yang dimaksud mencakup kegiatan pengolahan lahan, penyemaian, penanaman, pemeliharaan, pemanenan, dan kegiatan pascapanen.
→ whatItMeans: "Farming chili peppers and similar hot or sweet pepper varieties (cabai merah, cabai rawit, paprika). This includes cultivation from seedling to harvest. One of Indonesia's most price-volatile agricultural commodities — chili prices can swing 300–400% within a single season."
→ zantaraOpener: "Growing chili in Bali? Let me explain the licensing requirements and how to navigate Subak water rights and the LP2B land restrictions."

EXAMPLE 3:
code: 43302
judul: PENGERJAAN LANTAI, DINDING, DAN PLAFON
uraian: Kelompok ini mencakup kegiatan pengerjaan lantai, dinding, dan plafon dalam rangka penyelesaian bangunan gedung hunian dan nonhunian serta bangunan sipil. Kelompok ini mencakup pelapisan interior atau eksterior bangunan gedung dan bangunan sipil.
→ whatItMeans: "Floor laying, wall covering, ceiling finishing — tiles, marble, wood flooring, plasterwork, stucco, painting preparation. If you're applying the final surfaces to floors, walls, and ceilings inside a building, this is the code."
→ zantaraOpener: "Doing luxury villa finishing in Bali? 43302 covers floor, wall, and ceiling work — but PMA access is restricted. Here are the structures that work."
"""

SYSTEM_PROMPT = """You are an expert on Indonesian business law writing for foreign investors in Bali.

Generate two fields for each KBLI 2025 business code provided:

1. whatItMeans: Plain English explanation, 1-3 sentences, ~200-280 chars.
   - Lead with the activity (e.g. "Growing leafy vegetables —")
   - Mention specific examples from the uraian (Indonesian description)
   - End with scope clarification if useful
   - NO Indonesian bureaucratic language. Translate Indonesian terms.

2. zantaraOpener: One conversational sentence for a chatbot. ~100-150 chars.
   - Start with Bali context (e.g. "Planning a X in Bali?")
   - End with what Zantara will help with
   - Be specific to the business activity

Study these examples carefully:
""" + FEW_SHOT_EXAMPLES + """
Respond ONLY with valid JSON: {"results": [{"code": "01131", "whatItMeans": "...", "zantaraOpener": "..."}, ...]}
No extra text, no markdown fences."""


OLLAMA_MODEL = "qwen2.5-coder:32b"


def ollama_generate(prompt: str, ollama_url: str) -> str:
    """Call Ollama API and return raw response text."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": f"{SYSTEM_PROMPT}\n\n{prompt}",
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 4096},
    }).encode()
    req = urllib.request.Request(
        f"{ollama_url}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())
        return result.get("response", "").strip()


def enrich_with_llm(targets: list, batch_size: int = 5, ollama_url: str = "http://localhost:11434") -> None:
    target_map = {c['kode_kbli_2025']: c for c in targets}
    total = len(targets)
    processed = 0

    for i in range(0, len(targets), batch_size):
        batch = targets[i:i + batch_size]

        batch_text = "\n\n".join(
            f"code: {c['kode_kbli_2025']}\n"
            f"judul: {c['judul']}\n"
            f"uraian: {c.get('uraian', '')[:500]}"
            for c in batch
        )

        print(f"  LLM batch {i//batch_size + 1}: {len(batch)} codes...", end='', flush=True)

        raw = ''
        try:
            raw = ollama_generate(batch_text, ollama_url)
            # Strip markdown fences if model wraps in ```json
            if raw.startswith('```'):
                raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()

            result = json.loads(raw)

            for item in result.get('results', []):
                code_key = item.get('code')
                if code_key in target_map:
                    target_map[code_key]['intel_2026']['whatItMeans'] = item.get('whatItMeans', '')
                    target_map[code_key]['intel_2026']['zantaraOpener'] = item.get('zantaraOpener', '')

            processed += len(batch)
            print(f" ✓ ({processed}/{total})")

        except (json.JSONDecodeError, KeyError) as e:
            print(f" ✗ Parse error: {e}")
            if raw:
                print(f"  Raw response (first 400 chars): {raw[:400]}")
        except Exception as e:
            print(f" ✗ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description='KBLI Base Enrichment')
    parser.add_argument('--sector', help='Sector ID to process (e.g. I.E)')
    parser.add_argument('--limit', type=int, help='Max codes to process')
    parser.add_argument('--dry-run', action='store_true', help='Print output, do not write')
    parser.add_argument('--stats', action='store_true', help='Show enrichment stats and exit')
    parser.add_argument('--skip-llm', action='store_true', help='Only derive deterministic fields')
    parser.add_argument('--refill-empty', action='store_true',
                        help='Re-process codes that have intel_2026 but empty whatItMeans/zantaraOpener')
    parser.add_argument('--ollama-host', default='http://localhost:11434',
                        help='Ollama host URL (default: http://localhost:11434). '
                             'Use http://192.168.0.19:11434 for Mac Air.')
    args = parser.parse_args()

    data = load_json()
    codes = data['data']

    if args.stats:
        print_stats(codes)
        return

    targets = get_unenriched(codes, sector=args.sector, limit=args.limit, refill_empty=args.refill_empty)
    print(f"\nTargets: {len(targets)} codes to enrich"
          + (f" in sector {args.sector}" if args.sector else ""))

    if not targets:
        print("Nothing to do.")
        return

    # Phase 1: Deterministic fields (skip if already populated by --refill-empty)
    for code in targets:
        existing = code.get('intel_2026') or {}
        code['intel_2026'] = {
            'whatItMeans': existing.get('whatItMeans', ''),
            'whatYouNeed': existing.get('whatYouNeed') or derive_what_you_need(code),
            'whatChanged': existing.get('whatChanged') or derive_what_changed(code),
            'zantaraOpener': existing.get('zantaraOpener', ''),
            'baliContext': existing.get('baliContext', ''),
            'youllAlsoNeed': existing.get('youllAlsoNeed', ''),
        }

    if args.dry_run:
        print("\n=== DRY RUN OUTPUT (deterministic fields) ===")
        for code in targets:
            print(f"\n--- {code['kode_kbli_2025']} | {code['judul']} ---")
            intel = code['intel_2026']
            print(f"whatYouNeed:\n{intel['whatYouNeed']}")
            print(f"whatChanged: {intel['whatChanged']}")
        print(f"\n[DRY RUN] {len(targets)} codes ready. Run without --dry-run to enrich with LLM + write.")
        return

    if not args.skip_llm:
        print(f"\nRunning LLM enrichment via Qwen 2.5:32b @ {args.ollama_host} ({len(targets)} codes in batches of 10)...")
        enrich_with_llm(targets, ollama_url=args.ollama_host)

    # Write back
    code_map = {c['kode_kbli_2025']: c for c in codes}
    for t in targets:
        code_map[t['kode_kbli_2025']]['intel_2026'] = t['intel_2026']

    save_json(data)
    print(f"\n✅ Enriched and saved {len(targets)} codes to {JSON_PATH.name}")

    # Summary
    enriched_after = sum(1 for c in codes if c.get('intel_2026'))
    print(f"   Progress: {enriched_after}/{len(codes)} ({enriched_after/len(codes)*100:.1f}%)")


if __name__ == '__main__':
    main()
