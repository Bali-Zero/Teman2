# KBLI Base Enrichment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Populate 4 intel_2026 fields (`whatItMeans`, `whatYouNeed`, `whatChanged`, `zantaraOpener`) for all 1,313 unenriched KBLI codes, starting from smallest sectors, with 0% error rate before scaling.

**Architecture:** Single Python script `scripts/enrich_kbli_batch.py` — 2 fields deterministic (from structured JSON data), 2 fields via Claude API (from `uraian` text). Runs sector by sector. Dry-run mode for testing. Writes directly to `source_documents/KBLI_2025_FINAL_CLEAN.json`.

**Tech Stack:** Python 3.11, `anthropic` SDK (Claude Haiku 4.5), JSON in/out, no DB.

---

## Context: Data Structure

**JSON path:** `source_documents/KBLI_2025_FINAL_CLEAN.json`
**Access:** `data['data']` → list of 1563 code objects
**Enriched check:** `code.get('intel_2026')` is truthy

**Each code object has:**

```python
{
  "kode_kbli_2025": "01131",       # 5-digit code
  "judul": "PERTANIAN SAYURAN DAUN", # Indonesian title
  "uraian": "Kelompok ini mencakup...", # Indonesian description (~438 chars avg)
  "per_skala": [                    # licensing by business scale
    {
      "skala_usaha": ["Mikro", "Kecil"],  # scale
      "kategori_risiko": "Rendah",         # risk level
      "perizinan": "NIB",                  # license type
      "persyaratan": ["..."]               # requirements list
    }
  ],
  "sektor_id": "I.B",              # sector (19 sectors)
  "status_mapping": "MATCH_LANGSUNG", # change status from KBLI 2020
  "pma_status": "TERBUKA",         # PMA access
  "pma_max_asing": 100,            # max foreign %
  "pma_kondisi": null,             # conditions (if any)
  "pma_nota": null,                # additional notes
  "intel_2026": { ... }            # TARGET FIELD (add this)
}
```

**Target `intel_2026` structure (4 fields for this phase):**

```python
{
  "whatItMeans": "Plain English, 1-3 sentences, ~200-280 chars",
  "whatYouNeed": "**Scale**: Risk. License.\n\n**PMA:** status.",
  "whatChanged": "One sentence about KBLI 2020→2025 change.",
  "zantaraOpener": "One conversational sentence for chatbot.",
  "baliContext": "",        # empty for now
  "youllAlsoNeed": ""       # empty for now
}
```

## Context: Sector Priority (fewest missing first)

| Sektor | Name                   | Missing | Done   |
| ------ | ---------------------- | ------- | ------ |
| I.E    | Nuclear & Radioactive  | 10      | 0/10   |
| I.C    | Forestry & Wood        | 15      | 0/15   |
| I.A    | Agriculture Crops      | 34      | 6/40   |
| I.F.c  | Wood/Paper/Publishing  | 41      | 1/42   |
| I.F.d  | Chemical/Pharma/Rubber | 49      | 0/49   |
| ...    | ...                    | ...     | ...    |
| None   | Utilities/Construction | 175     | 42/217 |

## Context: Derivation Rules

### whatYouNeed (deterministic)

```python
RISK_MAP = {
    'Rendah': ('Low risk', 'NIB only — issued automatically.'),
    'Menengah Rendah': ('Medium-Low risk', 'NIB + Standard Certificate — issued automatically.'),
    'Menengah Tinggi': ('Medium-High risk', 'NIB + Standard Certificate — issued within 7 working days.'),
    'Tinggi': ('High risk', 'NIB + Business License (Izin) — full review required.'),
}

SCALE_MAP = {
    'Mikro': 'Micro', 'Kecil': 'Small', 'Menengah': 'Medium', 'Besar': 'Large',
}
```

For each `per_skala` entry:

- Format: `**{scales} scale**: {risk}. {license}.`
- Deduplicate identical (scale, risk) combos
- Append PMA line: `**PMA:** Fully open to PMA — {N}% foreign ownership allowed.`
- If `pma_status == 'TERTUTUP'`: `**PMA:** Closed to foreign investment — domestic only.`
- If `pma_status == 'TERBATAS'`: `**PMA:** Limited — max {N}% foreign ownership.`
- If `pma_kondisi`: append ` Condition: {pma_kondisi}.`
- If `pma_nota` AND it adds info: append ` Note: {pma_nota}.`

### whatChanged (deterministic)

```python
STATUS_MAP = {
    'MATCH_LANGSUNG': 'Unchanged from KBLI 2020 — direct match.',
    'CODICE_RINUMERATO': 'Renumbered/adjusted from KBLI 2020. OSS update may be required to register under the new code.',
    'MATCH_CON_AGGREGAZIONE': 'This code aggregates multiple KBLI 2020 activities. Verify your specific activity maps correctly.',
    'BPS_ONLY': 'New code in KBLI 2025 — no direct equivalent in KBLI 2020. Register fresh on OSS.',
}
```

### whatItMeans + zantaraOpener (LLM — Claude Haiku 4.5)

**Model:** `claude-haiku-4-5-20251001`
**Batch:** 10 codes per API call (structured JSON output)
**Prompt structure:** system + 3 few-shot examples + batch of codes

**System prompt:**

```
You are an expert on Indonesian business law writing for foreign investors in Bali.
Generate two fields for each KBLI 2025 business code:

1. whatItMeans: Plain English explanation, 1-3 sentences, ~200-280 chars.
   - Lead with the activity (e.g. "Growing leafy vegetables —")
   - Mention specific examples from the uraian
   - End with scope clarification if useful
   - NO Indonesian bureaucratic language

2. zantaraOpener: One conversational sentence for a chatbot. ~100-150 chars.
   - Start with context (e.g. "Planning a X in Bali?")
   - End with what Zantara will help with
   - Bali-specific when possible

Respond with a JSON object: {"results": [{"code": "01131", "whatItMeans": "...", "zantaraOpener": "..."}, ...]}
```

**Few-shot examples in prompt:**

```
EXAMPLE 1:
code: 01131
judul: PERTANIAN SAYURAN DAUN
uraian: Kelompok ini mencakup kegiatan pertanian sayuran yang daun, bunga atau batangnya dimakan sebagai sayur, seperti articok, petsai/sawi, asparagus, kubis/kol, kembang kol, brokoli, selada, seledri, daun bawang, bawang daun, bayam...
→ whatItMeans: "Growing leafy vegetables — spinach, kale, cabbage, lettuce, pak choi, kangkung, celery, leeks, and similar greens. This covers any farm activity where the leaf, stem, or flower of the plant is the edible product. It includes soil prep, planting, watering, and harvesting on the farm itself."
→ zantaraOpener: "Planning a leafy vegetable farm in Bali? Let me walk you through the licensing, land rules, and how to structure this as a PMA operation."

EXAMPLE 2:
code: 01138
judul: PERTANIAN CABAI
uraian: Kelompok ini mencakup kegiatan pertanian cabai (Capsicum spp), seperti cabai besar, cabai rawit, cabai keriting, dan paprika...
→ whatItMeans: "Farming chili peppers and similar hot or sweet pepper varieties (cabai merah, cabai rawit, paprika). This includes cultivation from seedling to harvest. One of Indonesia's most price-volatile agricultural commodities — chili prices can swing 300–400% within a single season."
→ zantaraOpener: "Growing chili in Bali? Let me explain the licensing requirements and how to navigate Subak water rights and the LP2B land restrictions."

EXAMPLE 3:
code: 43302
judul: PENGERJAAN LANTAI, DINDING, DAN PLAFON
uraian: Kelompok ini mencakup kegiatan pengerjaan lantai, dinding, dan plafon dalam rangka penyelesaian bangunan gedung hunian dan nonhunian...
→ whatItMeans: "Floor laying, wall covering, ceiling finishing — tiles, marble, wood flooring, plasterwork, stucco, painting preparation. If you're applying the final surfaces to floors, walls, and ceilings inside a building, this is the code."
→ zantaraOpener: "Doing luxury villa finishing in Bali? 43302 covers floor, wall, and ceiling work — but PMA access is restricted. Here are the structures that work."
```

---

## Task 1: Script skeleton + deterministic fields (Sector I.E — 10 codes)

**Files:**

- Create: `scripts/enrich_kbli_batch.py`

**Step 1: Create the script file**

```python
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
```

**Step 2: Verify it runs without error**

```bash
cd /Users/nuzantara/Desktop/nuzantara
python3 scripts/enrich_kbli_batch.py --stats
```

Expected: table showing 250/1563 enriched, sector breakdown

**Step 3: Dry-run on sector I.E (10 codes, deterministic only)**

```bash
python3 scripts/enrich_kbli_batch.py --sector I.E --dry-run --skip-llm
```

Expected: prints `whatYouNeed` and `whatChanged` for 10 nuclear/radioactive codes. No file written.

**Step 4: Manual quality check**

Visually verify the output for code `07210` (Uranium Mining):

- `whatYouNeed` should show: `**Large scale**: High risk. NIB + Business License (Izin) — full review required.` + PMA line
- `whatChanged` should show: `Unchanged from KBLI 2020 — direct match.`

**Step 5: Commit skeleton**

```bash
git add scripts/enrich_kbli_batch.py
git commit -m "feat(kbli): add base enrichment script with deterministic fields"
```

---

## Task 2: Add LLM enrichment (Claude Haiku 4.5)

**Files:**

- Modify: `scripts/enrich_kbli_batch.py` — add `enrich_with_llm()` function

**Step 1: Add LLM function to the script**

Add this function before `main()`:

```python
import os
import anthropic

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


def enrich_with_llm(targets: list, batch_size: int = 10) -> None:
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Use --skip-llm for deterministic-only mode.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Build index for fast lookup
    target_map = {c['kode_kbli_2025']: c for c in targets}

    total = len(targets)
    processed = 0

    for i in range(0, len(targets), batch_size):
        batch = targets[i:i + batch_size]

        # Build user message
        batch_text = "\n\n".join(
            f"code: {c['kode_kbli_2025']}\n"
            f"judul: {c['judul']}\n"
            f"uraian: {c.get('uraian', '')[:500]}"
            for c in batch
        )

        print(f"  LLM batch {i//batch_size + 1}: {len(batch)} codes...", end='', flush=True)

        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                messages=[{"role": "user", "content": batch_text}],
                system=SYSTEM_PROMPT,
            )

            raw = response.content[0].text.strip()
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
            print(f"  Raw response: {raw[:300]}")
            # Don't fail — deterministic fields already written, LLM fields stay empty
        except Exception as e:
            print(f" ✗ API error: {e}")
```

Also update `main()` — add `--write` flag and wire up LLM:

```python
# In main(), replace the "if args.dry_run" block with:
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
        print(f"\nRunning LLM enrichment ({len(targets)} codes in batches of 10)...")
        enrich_with_llm(targets)

    # Write back
    code_map = {c['kode_kbli_2025']: c for c in codes}
    for t in targets:
        code_map[t['kode_kbli_2025']]['intel_2026'] = t['intel_2026']

    save_json(data)
    print(f"\n✅ Enriched and saved {len(targets)} codes to {JSON_PATH.name}")

    # Summary
    enriched_after = sum(1 for c in codes if c.get('intel_2026'))
    print(f"   Progress: {enriched_after}/{len(codes)} ({enriched_after/len(codes)*100:.1f}%)")
```

**Step 2: Test LLM on 3 codes from I.E (dry-run first, then real)**

```bash
# First see deterministic output
python3 scripts/enrich_kbli_batch.py --sector I.E --limit 3 --dry-run

# Then run full (needs ANTHROPIC_API_KEY)
ANTHROPIC_API_KEY=sk-ant-... python3 scripts/enrich_kbli_batch.py --sector I.E --limit 3 --skip-llm
# Check JSON was written:
python3 -c "
import json
d = json.load(open('source_documents/KBLI_2025_FINAL_CLEAN.json'))
codes = d['data']
enriched = [c for c in codes if c.get('intel_2026') and c.get('sektor_id') == 'I.E']
for c in enriched[:3]:
    print(c['kode_kbli_2025'], c['intel_2026'].get('whatYouNeed','')[:80])
"
```

**Step 3: Quality check checklist**

For each enriched code verify:

- [ ] `whatYouNeed` has correct scale labels in English
- [ ] `whatYouNeed` has correct PMA line
- [ ] `whatChanged` matches the `status_mapping` value
- [ ] `whatItMeans` is 1-3 sentences in plain English (no Indonesian bureaucratic words)
- [ ] `zantaraOpener` is one sentence starting with Bali context
- [ ] No field is empty (except `baliContext` and `youllAlsoNeed`)
- [ ] JSON file is still valid after write

**Step 4: Run full LLM on sector I.E (10 codes)**

```bash
ANTHROPIC_API_KEY=sk-ant-... python3 scripts/enrich_kbli_batch.py --sector I.E
```

Expected output:

```
Targets: 10 codes to enrich in sector I.E
Running LLM enrichment (10 codes in batches of 10)...
  LLM batch 1: 10 codes... ✓ (10/10)
✅ Enriched and saved 10 codes to KBLI_2025_FINAL_CLEAN.json
   Progress: 260/1563 (16.6%)
```

**Step 5: Commit**

```bash
git add scripts/enrich_kbli_batch.py source_documents/KBLI_2025_FINAL_CLEAN.json
git commit -m "feat(kbli): enrich Sector I.E — Nuclear/Radioactive (260/1563, 16.6%)"
```

---

## Task 3: Validation experiment on Sector I.C (15 codes)

This is the **go/no-go gate**. If this passes with 0 errors, we can parallelise.

**Step 1: Run enrichment on sector I.C**

```bash
ANTHROPIC_API_KEY=sk-ant-... python3 scripts/enrich_kbli_batch.py --sector I.C
```

**Step 2: Validate all 15 codes**

```bash
python3 << 'EOF'
import json

with open('source_documents/KBLI_2025_FINAL_CLEAN.json') as f:
    d = json.load(f)

codes = d['data']
sector_codes = [c for c in codes if str(c.get('sektor_id','')) == 'I.C']

errors = []
for c in sector_codes:
    intel = c.get('intel_2026', {})
    code_id = c['kode_kbli_2025']

    if not intel:
        errors.append(f"{code_id}: MISSING intel_2026")
        continue

    for field in ['whatItMeans', 'whatYouNeed', 'whatChanged', 'zantaraOpener']:
        if not intel.get(field, '').strip():
            errors.append(f"{code_id}: EMPTY {field}")

    # whatYouNeed must contain "**" (has markdown scale labels)
    if intel.get('whatYouNeed') and '**' not in intel['whatYouNeed']:
        errors.append(f"{code_id}: whatYouNeed missing markdown formatting")

    # whatChanged must end with period
    wc = intel.get('whatChanged', '')
    if wc and not wc.endswith('.'):
        errors.append(f"{code_id}: whatChanged doesn't end with period")

    # Length checks
    wim = intel.get('whatItMeans', '')
    if len(wim) > 400:
        errors.append(f"{code_id}: whatItMeans too long ({len(wim)} chars)")
    if len(wim) < 50:
        errors.append(f"{code_id}: whatItMeans too short ({len(wim)} chars)")

if errors:
    print(f"❌ {len(errors)} errors found:")
    for e in errors:
        print(f"  {e}")
else:
    print(f"✅ All {len(sector_codes)} codes in I.C passed validation")

EOF
```

Expected: `✅ All 15 codes in I.C passed validation`

**Step 3: If errors → fix script and re-run**

Common issues to fix:

- Empty `whatItMeans`: LLM parse failed → check JSON format in response
- Missing `**` in `whatYouNeed`: `per_skala` was empty → add fallback
- `whatChanged` missing period: fix STATUS_MAP values

**Step 4: Commit if passing**

```bash
git add source_documents/KBLI_2025_FINAL_CLEAN.json
git commit -m "feat(kbli): enrich Sector I.C — Forestry/Wood (275/1563, 17.6%)"
```

---

## Task 4: Scale to all remaining sectors (if Task 3 passes)

**Step 1: Run stats to see current state**

```bash
python3 scripts/enrich_kbli_batch.py --stats
```

**Step 2: Run each sector in order**

```bash
for SECTOR in "I.A" "I.F.c" "I.F.d" "I.F.b" "I.F.e" "I.H" "I.F.g" "I.F.f" "I.D" "I.F.h" "I.F.a" "I.I" "I.J-P" "I.Q-V" "I.B" "I.G" "None"; do
  echo "=== Processing $SECTOR ==="
  ANTHROPIC_API_KEY=sk-ant-... python3 scripts/enrich_kbli_batch.py --sector "$SECTOR"
done
```

**Step 3: Final validation (all codes)**

```bash
python3 << 'EOF'
import json

with open('source_documents/KBLI_2025_FINAL_CLEAN.json') as f:
    d = json.load(f)

codes = d['data']
unenriched = [c for c in codes if not c.get('intel_2026')]
empty_fields = []

for c in codes:
    intel = c.get('intel_2026', {})
    if not intel:
        continue
    for field in ['whatItMeans', 'whatYouNeed', 'whatChanged', 'zantaraOpener']:
        if not intel.get(field, '').strip():
            empty_fields.append(f"{c['kode_kbli_2025']}: EMPTY {field}")

print(f"Unenriched: {len(unenriched)}")
print(f"Empty fields: {len(empty_fields)}")
if empty_fields[:10]:
    for e in empty_fields[:10]:
        print(f"  {e}")
EOF
```

Expected: `Unenriched: 0` and `Empty fields: 0`

**Step 4: Commit final state**

```bash
git add source_documents/KBLI_2025_FINAL_CLEAN.json
git commit -m "feat(kbli): complete base enrichment for all 1563 codes (1563/1563, 100%)"
```

---

## Parallelisation Protocol (after Task 3 passes)

Once the script is validated with 0 errors on 2 sectors, multiple AI agents can run it in parallel **on different sectors** without conflicts, because:

1. Each AI works on a different `--sector` value
2. Each AI writes to the same JSON file but touches different array entries (no overlap)
3. **ONE AI WRITES AT A TIME** — coordinate so only one is writing at any moment

**Parallel assignment:**

```
AI 1: sectors I.A, I.F.c, I.F.d  (124 codes)
AI 2: sectors I.F.b, I.F.e, I.H  (165 codes)
AI 3: sectors I.F.g, I.F.f, I.D  (192 codes)
AI 4: sectors I.F.h, I.F.a, I.I  (237 codes)
AI 5: sectors I.J-P, I.Q-V       (241 codes)
AI 6: sectors I.B, I.G, None     (354 codes)
```

Each AI:

1. Runs: `python3 scripts/enrich_kbli_batch.py --sector X`
2. Validates output with the validation script from Task 3
3. Commits: `git commit -m "feat(kbli): enrich Sector X — Name (N/1563, X%)"`
4. Pushes

**IMPORTANT:** Git pull before each sector to avoid conflicts on the JSON file.

---

## Environment Setup

```bash
# Required
export ANTHROPIC_API_KEY=sk-ant-...  # Already in env usually

# Optional: check it works
python3 -c "import anthropic; print('anthropic SDK ok')"
```

If `anthropic` not installed:

```bash
pip install anthropic
```

---

## Cost Estimate

- **Model:** Claude Haiku 4.5 — $0.80/MTok input, $4.00/MTok output
- **Per code:** ~600 tokens input (system + examples + uraian), ~150 tokens output
- **1,313 codes:** ~788K input tokens + ~197K output tokens
- **Total cost:** ~$0.63 + $0.79 = **~$1.42 total**
