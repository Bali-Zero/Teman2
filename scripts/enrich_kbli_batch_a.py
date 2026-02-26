#!/usr/bin/env python3
"""
KBLI Gold Content Batch A Enrichment (codes 1-200)
Generates intel_2026 content for KBLI codes that don't have it yet.

Uses the structured data from KBLI_2025_FINAL_CLEAN.json to produce:
- whatItMeans: plain-language explanation
- whatYouNeed: licensing requirements checklist
- whatChanged: transition from KBLI 2020
- zantaraOpener: conversational chatbot opener
- baliContext: Bali-specific context (where applicable)
- youllAlsoNeed: related codes (where applicable)

Output: source_documents/KBLI_GOLD_BATCH_A.json
"""

import json
import sys
from pathlib import Path
from typing import Optional

# Risk level translations
RISK_EN = {
    "Rendah": "Low",
    "Menengah Rendah": "Medium-Low",
    "Menengah Tinggi": "Medium-High",
    "Tinggi": "High",
}

# Scale translations
SCALE_EN = {
    "Mikro": "Micro",
    "Kecil": "Small",
    "Menengah": "Medium",
    "Besar": "Large",
}

# Authority translations
AUTH_EN = {
    "Bupati/Walikota": "District/City (Bupati/Walikota)",
    "Gubernur": "Provincial (Governor)",
    "Menteri": "National (Minister)",
    "Presiden": "Presidential",
}

# Mapping status translations
MAPPING_EN = {
    "MATCH_LANGSUNG": "Direct 1:1 match from KBLI 2020 — code and scope unchanged.",
    "CODICE_RINUMERATO": "Renumbered from KBLI 2020 — same activity, new code number.",
    "MATCH_CON_AGGREGAZIONE": "Merged from multiple KBLI 2020 codes into a single 2025 code.",
    "BPS_ONLY": "New code in KBLI 2025 — no direct equivalent in KBLI 2020.",
    "": "No mapping information available.",
}

# PMA status translations
PMA_EN = {
    "TERBUKA": "Open",
    "TERTUTUP": "Closed",
    "TERBATAS": "Restricted",
}

# Sector context for Bali (prefix-based)
BALI_SECTOR_CONTEXT = {
    "01": "Agriculture in Bali centers around rice (subak system), coffee (Kintamani highlands), and tropical fruits/vegetables. Foreign investment in agriculture is common for farm-to-table concepts, organic farming, and agritourism. Land use requires coordination with local subak (irrigation cooperative) and compliance with spatial planning (RTRW).",
    "02": "Bali's forestry sector is limited due to the island's small size, but protected forests in the central highlands (around Batukaru and Batur) are significant. Community-based forest management (Hutan Kemasyarakatan) is the primary model. Commercial forestry operations are rare on Bali.",
    "03": "Bali's fishing and aquaculture sector is centered around Jimbaran, Kedonganan, and the north coast (Singaraja area). Marine aquaculture — particularly seaweed, lobster, and ornamental fish — has foreign investment potential. Freshwater aquaculture thrives in Tabanan and Gianyar.",
    "05": "Coal mining does not exist in Bali. These codes are relevant only for operations in Kalimantan, Sumatra, and Sulawesi.",
    "06": "Oil and gas extraction does not occur in Bali. These codes apply to operations in East Java, Kalimantan, Papua, and offshore fields.",
    "07": "Metal ore mining is not present in Bali. Relevant for operations in Papua, Sulawesi, Kalimantan, and Nusa Tenggara.",
    "08": "Quarrying in Bali is limited to sand, stone, and marble extraction, primarily in Karangasem and parts of Gianyar. Environmental permits (AMDAL/UKL-UPL) are strictly enforced due to Bali's protected landscape status.",
    "09": "Mining support services apply primarily to operations outside Bali. Limited relevance on the island.",
    "10": "Food processing in Bali is a growing sector, particularly for: coconut products (VCO, coconut sugar), coffee processing (Kintamani), chocolate/cacao, and seafood processing. PT PMA food processing businesses typically locate in Badung or Gianyar industrial zones.",
}


def translate_scales(scales: list[str]) -> str:
    """Translate scale list to English."""
    return ", ".join(SCALE_EN.get(s, s) for s in scales)


def format_timeframe(jangka_waktu: str) -> str:
    """Format timeframe in English."""
    if jangka_waktu == "Otomatis":
        return "Automatic (instant)"
    elif "Hari" in jangka_waktu:
        return f"{jangka_waktu.replace('Hari', 'working days').strip()}"
    return jangka_waktu


def generate_what_it_means(code: dict) -> str:
    """Generate plain-language explanation of the business activity."""
    judul = code["judul"]
    uraian = code["uraian"]

    # Clean up uraian — remove newlines, compress whitespace
    uraian_clean = " ".join(uraian.split())

    # Extract the key activity description
    # The uraian typically starts with "Kelompok ini mencakup..."
    activity = uraian_clean
    if len(activity) > 500:
        # Truncate intelligently at sentence boundary
        sentences = activity.split(". ")
        result = ""
        for s in sentences:
            if len(result) + len(s) > 450:
                break
            result += s + ". "
        activity = result.strip()

    return activity


def generate_what_you_need(code: dict) -> str:
    """Generate licensing requirements summary."""
    per_skala = code.get("per_skala", [])
    pma_status = code.get("pma_status", "")
    pma_max = code.get("pma_max_asing", 0)
    pma_kondisi = code.get("pma_kondisi")

    lines = []

    for entry in per_skala:
        scales = translate_scales(entry["skala_usaha"])
        risk = RISK_EN.get(entry["kategori_risiko"], entry["kategori_risiko"])
        license_type = entry["perizinan"]
        timeframe = format_timeframe(entry["jangka_waktu"])
        authority = AUTH_EN.get(entry["kewenangan"], entry["kewenangan"])

        line = f"**{scales}**: {risk} risk. {license_type}, issued {timeframe}. Authority: {authority}."

        # Add requirements if any
        if entry.get("persyaratan"):
            reqs = "; ".join(entry["persyaratan"][:3])
            if len(entry["persyaratan"]) > 3:
                reqs += f" (+{len(entry['persyaratan'])-3} more)"
            line += f"\n  Requirements: {reqs}"

        # Add key obligations if any
        if entry.get("kewajiban"):
            obls = entry["kewajiban"][:2]
            obl_text = "; ".join(o[:100] for o in obls)
            if len(entry["kewajiban"]) > 2:
                obl_text += f" (+{len(entry['kewajiban'])-2} more)"
            line += f"\n  Obligations: {obl_text}"

        lines.append(line)

    # PMA info
    pma_line = f"\n**PMA (Foreign Investment):** {PMA_EN.get(pma_status, pma_status)}"
    if pma_max > 0:
        pma_line += f" — up to {pma_max}% foreign ownership"
    if pma_kondisi:
        pma_line += f". Condition: {pma_kondisi}"
    pma_line += "."
    lines.append(pma_line)

    return "\n\n".join(lines)


def generate_what_changed(code: dict) -> str:
    """Generate transition info from KBLI 2020."""
    status = code.get("status_mapping", "")
    base = MAPPING_EN.get(status, "")

    notes = []
    if code.get("mapping_note"):
        notes.append(code["mapping_note"])
    if code.get("aggregation_note"):
        notes.append(f"Aggregation: {code['aggregation_note']}")
    if code.get("kbli_2020_source"):
        notes.append(f"Previous code(s): {code['kbli_2020_source']}")

    if notes:
        return f"{base} {' '.join(notes)}"
    return base


def generate_zantara_opener(code: dict) -> str:
    """Generate conversational chatbot opener."""
    judul = code["judul"]
    kode = code["kode_kbli_2025"]
    pma_status = PMA_EN.get(code.get("pma_status", ""), "Unknown")

    # Get highest risk level
    risks = [e["kategori_risiko"] for e in code.get("per_skala", [])]
    highest_risk = "Unknown"
    risk_order = ["Tinggi", "Menengah Tinggi", "Menengah Rendah", "Rendah"]
    for r in risk_order:
        if r in risks:
            highest_risk = RISK_EN.get(r, r)
            break

    return f"Looking into {judul.title()} ({kode})? This is classified as {highest_risk} risk with PMA status: {pma_status}. Let me walk you through the requirements."


def generate_bali_context(code: dict) -> Optional[str]:
    """Generate Bali-specific context based on sector."""
    prefix = code["kode_kbli_2025"][:2]
    return BALI_SECTOR_CONTEXT.get(prefix)


def enrich_code(code: dict) -> dict:
    """Generate full intel_2026 content for a single KBLI code."""
    intel = {
        "whatItMeans": generate_what_it_means(code),
        "whatYouNeed": generate_what_you_need(code),
        "whatChanged": generate_what_changed(code),
        "zantaraOpener": generate_zantara_opener(code),
    }

    bali = generate_bali_context(code)
    if bali:
        intel["baliContext"] = bali

    return intel


def generate_summary(code: dict) -> dict:
    """Generate a summary record for the output JSON."""
    per_skala = code.get("per_skala", [])

    # Determine highest risk
    risk_order = ["Tinggi", "Menengah Tinggi", "Menengah Rendah", "Rendah"]
    highest_risk = "Unknown"
    for entry in per_skala:
        r = entry["kategori_risiko"]
        if risk_order.index(r) < risk_order.index(highest_risk) if highest_risk in risk_order else True:
            highest_risk = r

    return {
        "code": code["kode_kbli_2025"],
        "title": code["judul"],
        "pma_status": code.get("pma_status", ""),
        "pma_max_foreign": code.get("pma_max_asing", 0),
        "highest_risk": RISK_EN.get(highest_risk, highest_risk),
        "scale_count": len(per_skala),
        "mapping_status": code.get("status_mapping", ""),
    }


def main():
    source_path = Path("source_documents/KBLI_2025_FINAL_CLEAN.json")
    output_path = Path("source_documents/KBLI_GOLD_BATCH_A.json")

    print(f"Loading source data from {source_path}...")
    with open(source_path) as f:
        data = json.load(f)

    first_200 = data["data"][:200]
    needing = [c for c in first_200 if not c.get("intel_2026")]

    print(f"Total codes in range: {len(first_200)}")
    print(f"Already enriched: {len(first_200) - len(needing)}")
    print(f"Needing enrichment: {len(needing)}")
    print()

    results = []
    for code in needing:
        intel = enrich_code(code)
        summary = generate_summary(code)
        summary["intel_2026"] = intel
        results.append(summary)
        print(f"  ✓ {code['kode_kbli_2025']}: {code['judul'][:50]}")

    output = {
        "metadata": {
            "batch": "A",
            "description": "Gold content enrichment for KBLI codes 1-200 (positions in source data)",
            "source": "KBLI_2025_FINAL_CLEAN.json",
            "generated_date": "2026-02-26",
            "total_enriched": len(results),
            "code_range": f"{results[0]['code']}-{results[-1]['code']}" if results else "",
        },
        "data": results,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Generated {len(results)} enriched codes → {output_path}")

    # Also update the source file with intel_2026
    updated_count = 0
    code_map = {r["code"]: r["intel_2026"] for r in results}
    for code in data["data"]:
        if code["kode_kbli_2025"] in code_map and not code.get("intel_2026"):
            code["intel_2026"] = code_map[code["kode_kbli_2025"]]
            updated_count += 1

    with open(source_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Updated {updated_count} codes in {source_path}")

    # Verify
    with open(source_path) as f:
        verify = json.load(f)
    enriched_total = sum(1 for c in verify["data"][:200] if c.get("intel_2026"))
    print(f"✅ Verification: {enriched_total}/200 codes now have intel_2026")


if __name__ == "__main__":
    main()
