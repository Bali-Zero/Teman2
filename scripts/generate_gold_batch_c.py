#!/usr/bin/env python3
"""
KBLI Gold Content — Batch C Generator (all remaining codes)
Generates Gold content for the 843 codes not yet in kbli-gold-all.json.

Source: source_documents/KBLI_2025_FINAL_CLEAN.json
Merges with: apps/mouth/data/kbli-gold-all.json
Output: apps/mouth/data/kbli-gold-all.json (unified A+B+C)

For codes WITH intel_2026 → uses that content directly
For codes WITHOUT intel_2026 → generates from per_skala, pma_*, uraian fields
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
GOLD_ALL = ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"


# ─── Translation tables ─────────────────────────────────────────────────────

RISK_EN: dict[str, str] = {
    "Rendah": "Low",
    "Menengah Rendah": "Medium-Low",
    "Menengah Tinggi": "Medium-High",
    "Tinggi": "High",
}

SCALE_EN: dict[str, str] = {
    "Mikro": "Micro",
    "Kecil": "Small",
    "Menengah": "Medium",
    "Besar": "Large",
}

RISK_ORDER: dict[str, int] = {
    "Rendah": 1,
    "Menengah Rendah": 2,
    "Menengah Tinggi": 3,
    "Tinggi": 4,
}

# Sector context for Bali
BALI_SECTOR_CONTEXT: dict[str, str] = {
    "01": "Agriculture in Bali centers around rice (subak system), coffee (Kintamani highlands), and tropical fruits. Foreign investment is common for farm-to-table, organic farming, and agritourism.",
    "03": "Bali's fishing and aquaculture is centered around Jimbaran, Kedonganan, and north coast. Marine aquaculture (seaweed, lobster, ornamental fish) has foreign investment potential.",
    "10": "Food processing in Bali is growing: coconut products (VCO, coconut sugar), coffee processing (Kintamani), chocolate/cacao, and seafood processing. PT PMA typically locates in Badung or Gianyar.",
    "11": "Craft beverage production in Bali includes arak distilling (traditional), kombucha, and specialty coffee. The island's tourism market drives demand for premium local beverages.",
    "14": "Bali's garment industry serves both domestic retail and export. Seminyak and Canggu host numerous boutique fashion brands. Factory production concentrates in Denpasar industrial areas.",
    "16": "Bali is renowned for wood carving (Mas village), bamboo construction (Green School influence), and rattan furniture. Gianyar and Ubud are centers of traditional woodcraft.",
    "23": "Stone and marble crafting in Bali centers around Batubulan. Ornamental stone carving is a significant export industry.",
    "32": "Bali's jewelry industry (especially Celuk village in Gianyar) is globally recognized for silver and gold craftsmanship. Both traditional and contemporary designs for export.",
    "41": "Villa and hotel construction is a major industry in Bali. Building permits (IMB/PBG) require compliance with local height restrictions and Balinese architectural guidelines.",
    "43": "Specialized construction in Bali demands familiarity with tropical building standards, traditional Balinese architectural elements, and environmental regulations.",
    "46": "Wholesale trade in Bali serves the tourism and hospitality sector. Import distribution requires careful customs and BPOM (food safety) compliance.",
    "47": "Retail in Bali is driven by tourism. Popular categories: surfwear, handicrafts, organic products, and luxury goods. Mall and boutique retail both thrive.",
    "55": "Accommodation is Bali's core industry. From five-star resorts to budget homestays, this sector employs the most people on the island. Strict tourism regulations apply.",
    "56": "F&B is Bali's second-largest sector. Restaurants, cafes, and bars serve both tourists and expats. Alcohol licensing, halal certification, and health permits are key requirements.",
    "59": "Bali's creative scene supports film, video, and music production. The island attracts international productions and has a growing local indie scene.",
    "60": "Digital media and streaming platforms benefit from Bali's creative community and growing tech ecosystem.",
    "62": "Bali's tech startup scene is concentrated in Canggu, Seminyak, and Sanur. Digital nomad culture drives demand for software development, AI, and blockchain services.",
    "63": "Data processing and cloud services in Bali serve the growing digital economy. Co-working spaces and tech hubs are common.",
    "68": "Real estate in Bali is highly active: villa development, hotel management, and property management for foreign investors. Land use requires careful legal structuring (Hak Pakai/HGB).",
    "69": "Legal and accounting services in Bali serve the expat community and foreign investors. KITAS/work permit consulting is a major specialization.",
    "70": "Management consulting in Bali focuses on tourism, hospitality, and F&B sectors. Market entry consulting for foreign investors is a growth area.",
    "71": "Architecture in Bali blends traditional Balinese design with modern tropical architecture. International architects collaborate with local firms on resort and villa projects.",
    "73": "Marketing and advertising in Bali is driven by tourism and hospitality brands. Digital marketing and social media management are particularly active.",
    "74": "Design services in Bali span interior design (villas/resorts), graphic design, and photography. The island's aesthetic culture drives demand for creative professionals.",
    "77": "Rental businesses in Bali include motorbike/car rental, surfboard rental, and equipment hire for tourists. This sector has low barriers to entry.",
    "79": "Tour operators and travel agencies are fundamental to Bali's economy. Adventure tourism, cultural tours, and diving excursions are popular segments.",
    "82": "Business support services in Bali include event planning (weddings, conferences), virtual assistants, and co-working space management.",
    "85": "International schools and language centers serve Bali's expat community. Yoga teacher training and wellness education are unique Bali-specific offerings.",
    "86": "Healthcare in Bali serves both locals and medical tourists. Private clinics, dental practices, and wellness centers are common foreign investment targets.",
    "90": "Bali's arts scene includes visual arts (painting, sculpture), performing arts (traditional dance, gamelan), and contemporary gallery spaces.",
    "93": "Sports and recreation in Bali: surfing, diving, yoga, fitness, golf, and adventure activities. The island is a global wellness destination.",
    "96": "Spa and wellness services are iconic to Bali. Day spas, wellness retreats, and beauty salons serve both tourists and residents.",
}


# ─── Content generators ──────────────────────────────────────────────────────

def format_scales(scales: list[str]) -> str:
    return " / ".join(SCALE_EN.get(s, s) for s in scales)


def pma_summary(code: dict[str, Any]) -> str:
    """Generate PMA classification text."""
    status = code.get("pma_status", "")
    max_asing = code.get("pma_max_asing", 0)
    kondisi = code.get("pma_kondisi") or ""
    prioritas = code.get("pma_prioritas", False)

    if status == "TERTUTUP":
        return "**PMA: CLOSED** — This sector is closed to foreign investment. Only Indonesian-owned companies (PMDN) can operate."
    elif status == "TERBATAS":
        pct = f"{max_asing}%" if max_asing else "limited"
        line = f"**PMA: RESTRICTED** — Foreign ownership capped at {pct}."
        if kondisi:
            line += f" Condition: {kondisi}"
        if prioritas:
            line += " (Priority sector — investment incentives may apply.)"
        return line
    else:
        line = "**PMA: OPEN** — 100% foreign ownership allowed."
        if prioritas:
            line += " Priority sector — tax incentives and streamlined licensing may apply."
        return line


def licensing_summary(per_skala: list[dict[str, Any]]) -> str:
    """Generate whatYouNeed from per_skala entries."""
    if not per_skala:
        return "Licensing details not yet available in PP28/2025 for this code."

    sorted_entries = sorted(
        per_skala,
        key=lambda e: RISK_ORDER.get(e.get("kategori_risiko", ""), 5),
    )

    parts: list[str] = []
    for entry in sorted_entries:
        scales = format_scales(entry.get("skala_usaha", []))
        risk = entry.get("kategori_risiko", "")
        risk_en = RISK_EN.get(risk, risk)
        perizinan = entry.get("perizinan", "NIB")
        jangka = entry.get("jangka_waktu", "")
        auth = entry.get("kewenangan", "")

        line = f"**{scales} scale**: {risk_en} risk ({risk})."
        if perizinan:
            line += f" {perizinan}"
        if jangka:
            if jangka.lower() == "otomatis":
                line += " — issued **automatically**."
            else:
                line += f" — issued within **{jangka}**."
        else:
            line += "."
        if auth:
            line += f" Authority: **{auth}**."

        reqs = entry.get("persyaratan", [])
        if reqs:
            top_reqs = reqs[:3]
            req_text = "\n".join(
                f"- {r[:120]}{'...' if len(r) > 120 else ''}" for r in top_reqs
            )
            if len(reqs) > 3:
                req_text += f"\n- ...and {len(reqs) - 3} more requirements"
            line += f"\n\nKey requirements:\n{req_text}"

        obligs = entry.get("kewajiban", [])
        if obligs:
            top_obligs = obligs[:2]
            oblig_text = "\n".join(
                f"- {o[:120]}{'...' if len(o) > 120 else ''}" for o in top_obligs
            )
            line += f"\n\nObligations:\n{oblig_text}"

        parts.append(line)

    return "\n\n".join(parts)


def mapping_summary(code: dict[str, Any]) -> str:
    """Generate whatChanged from mapping status."""
    status = code.get("status_mapping", "")
    note = code.get("mapping_note") or code.get("aggregation_note") or ""
    source_2020 = code.get("kbli_2020_source") or ""

    mapping_text: dict[str, str] = {
        "MATCH_LANGSUNG": "Direct match from KBLI 2020 — code and scope unchanged.",
        "CODICE_RINUMERATO": "Code was renumbered from KBLI 2020 (same activity, new code number).",
        "MATCH_CON_AGGREGAZIONE": "This code was created by merging multiple KBLI 2020 codes into one.",
        "BPS_ONLY": "New code in KBLI 2025 — not present in KBLI 2020. This is a newly classified business activity.",
    }
    base = mapping_text.get(status, "Mapping status from KBLI 2020 is pending verification.")

    if note:
        base += f" {note}"
    if source_2020:
        base += f" (Previous: {source_2020})"
    return base


def generate_what_it_means(code: dict[str, Any]) -> str:
    """Generate whatItMeans from judul + uraian."""
    uraian = code.get("uraian", "")
    judul = code.get("judul", "")
    uraian_clean = re.sub(r"\s+", " ", uraian).strip()

    if uraian_clean:
        sentences = re.split(r"(?<=[.!?])\s+", uraian_clean)
        summary = " ".join(sentences[:2])
        if len(summary) > 400:
            summary = summary[:397] + "..."
        return summary

    return f"Business activity classified under {judul}."


def generate_zantara_opener(code: dict[str, Any]) -> str:
    """Generate a conversational opener for the chatbot."""
    kode = code.get("kode_kbli_2025", "")
    judul = code.get("judul", "")
    pma = code.get("pma_status", "")

    en_match = re.search(r"\(([A-Z][^)]+)\)", judul)
    title_en = (
        en_match.group(1).title()
        if en_match
        else judul.split("(")[0].strip().title()
    )

    if pma == "TERTUTUP":
        return f"Interested in {title_en.lower()}? Code {kode} is closed to foreign investment — let me explain the local-ownership requirements."
    elif pma == "TERBATAS":
        max_pct = code.get("pma_max_asing", 0)
        return f"Looking at {title_en.lower()}? Code {kode} allows up to {max_pct}% foreign ownership — let me walk you through the requirements."
    else:
        return f"Setting up {title_en.lower()} in Indonesia? Code {kode} is fully open to foreign investment — here's what you need to know."


def generate_bali_context(code: dict[str, Any]) -> str:
    """Generate Bali-specific context based on sector."""
    prefix = code["kode_kbli_2025"][:2]
    return BALI_SECTOR_CONTEXT.get(prefix, "")


def generate_gold_entry(code: dict[str, Any]) -> dict[str, str]:
    """Generate a complete Gold content entry for a KBLI code."""
    intel = code.get("intel_2026")

    if intel and any(intel.values()):
        return {
            "whatItMeans": intel.get("whatItMeans") or generate_what_it_means(code),
            "whatYouNeed": intel.get("whatYouNeed") or licensing_summary(code.get("per_skala", [])),
            "whatChanged": intel.get("whatChanged") or mapping_summary(code),
            "baliContext": intel.get("baliContext") or generate_bali_context(code),
            "youllAlsoNeed": intel.get("youllAlsoNeed") or "",
            "zantaraOpener": intel.get("zantaraOpener") or generate_zantara_opener(code),
        }
    else:
        what_you_need = licensing_summary(code.get("per_skala", []))
        pma_text = pma_summary(code)
        return {
            "whatItMeans": generate_what_it_means(code),
            "whatYouNeed": f"{what_you_need}\n\n{pma_text}",
            "whatChanged": mapping_summary(code),
            "baliContext": generate_bali_context(code),
            "youllAlsoNeed": "",
            "zantaraOpener": generate_zantara_opener(code),
        }


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    # Load source data
    print(f"Loading source from {SOURCE}...")
    with open(SOURCE) as f:
        source = json.load(f)
    all_codes = source["data"]
    print(f"  Total KBLI codes: {len(all_codes)}")

    # Load existing gold
    print(f"Loading existing gold from {GOLD_ALL}...")
    with open(GOLD_ALL) as f:
        gold_data = json.load(f)
    existing_gold: dict[str, Any] = gold_data["data"]
    print(f"  Existing gold codes: {len(existing_gold)}")

    # Generate Batch C for missing codes
    batch_c: dict[str, dict[str, str]] = {}
    stats = {"from_intel": 0, "generated": 0}

    for code in all_codes:
        kode = code["kode_kbli_2025"]
        if kode in existing_gold:
            continue

        entry = generate_gold_entry(code)
        batch_c[kode] = entry

        if code.get("intel_2026") and any(code["intel_2026"].values()):
            stats["from_intel"] += 1
        else:
            stats["generated"] += 1

    print(f"\nBatch C generated:")
    print(f"  From intel_2026: {stats['from_intel']}")
    print(f"  Generated from structured data: {stats['generated']}")
    print(f"  Total new entries: {len(batch_c)}")

    # Merge all batches
    merged = {**existing_gold, **batch_c}
    print(f"\nMerged total: {len(merged)} codes (all 1563)")

    # Write unified output
    output = {
        "metadata": {
            "description": "KBLI 2025 Gold-Tier Editorial Content (Batch A + B + C — Complete 1563 codes)",
            "generated": datetime.now(timezone.utc).isoformat(),
            "totalCodes": len(merged),
            "batchACodes": gold_data["metadata"].get("batchACodes", 304),
            "batchBCodes": gold_data["metadata"].get("batchBCodes", 416),
            "batchCCodes": len(batch_c),
            "note": "Batch A (hand-curated) > Batch B (semi-auto) > Batch C (auto-generated). Earlier batches take precedence.",
        },
        "data": dict(sorted(merged.items())),
    }

    with open(GOLD_ALL, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    file_size = GOLD_ALL.stat().st_size
    print(f"\n✅ Written to {GOLD_ALL}")
    print(f"   Size: {file_size:,} bytes ({file_size / 1024 / 1024:.1f} MB)")

    # Verify completeness
    all_kbli_codes = {c["kode_kbli_2025"] for c in all_codes}
    gold_codes_set = set(merged.keys())
    missing = all_kbli_codes - gold_codes_set
    if missing:
        print(f"\n⚠️  Still missing {len(missing)} codes: {sorted(missing)[:10]}...")
    else:
        print(f"\n✅ All {len(all_kbli_codes)} KBLI codes have gold content!")


if __name__ == "__main__":
    main()
