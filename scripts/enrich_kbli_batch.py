#!/usr/bin/env python3
"""
KBLI Base Enrichment Script
Populates intel_2026 fields for unenriched KBLI codes.
"""
import json
import sys
import argparse
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


def get_unenriched(codes: list, sector: str | None = None, limit: int | None = None) -> list:
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


def main():
    parser = argparse.ArgumentParser(description='KBLI Base Enrichment')
    parser.add_argument('--sector', help='Sector ID to process (e.g. I.E)')
    parser.add_argument('--limit', type=int, help='Max codes to process')
    parser.add_argument('--dry-run', action='store_true', help='Print output, do not write')
    parser.add_argument('--stats', action='store_true', help='Show enrichment stats and exit')
    parser.add_argument('--skip-llm', action='store_true', help='Only derive deterministic fields')
    args = parser.parse_args()

    data = load_json()
    codes = data['data']

    if args.stats:
        print_stats(codes)
        return

    targets = get_unenriched(codes, sector=args.sector, limit=args.limit)
    print(f"\nTargets: {len(targets)} codes to enrich"
          + (f" in sector {args.sector}" if args.sector else ""))

    if not targets:
        print("Nothing to do.")
        return

    # Phase 1: Deterministic fields
    for code in targets:
        code['intel_2026'] = {
            'whatItMeans': '',       # filled by LLM
            'whatYouNeed': derive_what_you_need(code),
            'whatChanged': derive_what_changed(code),
            'zantaraOpener': '',     # filled by LLM
            'baliContext': '',
            'youllAlsoNeed': '',
        }

    if args.dry_run:
        print("\n=== DRY RUN OUTPUT ===")
        for code in targets:
            print(f"\n--- {code['kode_kbli_2025']} | {code['judul']} ---")
            intel = code['intel_2026']
            print(f"whatYouNeed:\n{intel['whatYouNeed']}")
            print(f"whatChanged: {intel['whatChanged']}")
        print(f"\n[DRY RUN] Would write {len(targets)} codes. Use --write to save.")
        return

    if not args.skip_llm:
        enrich_with_llm(targets)

    # Write back
    # Update codes in-place by code key
    code_map = {c['kode_kbli_2025']: c for c in codes}
    for t in targets:
        code_map[t['kode_kbli_2025']]['intel_2026'] = t['intel_2026']

    save_json(data)
    print(f"\n✅ Wrote {len(targets)} enriched codes to {JSON_PATH}")


if __name__ == '__main__':
    main()
