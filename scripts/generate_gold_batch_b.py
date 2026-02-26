#!/usr/bin/env python3
"""
KBLI Gold Content — Batch B Generator (codes 501-1000)
Generates enriched Gold content from KBLI_2025_FINAL_CLEAN.json source data.

Source: source_documents/KBLI_2025_FINAL_CLEAN.json
Output: apps/mouth/src/lib/kbli-gold-batch-b.ts

For codes WITH intel_2026 → uses that content directly
For codes WITHOUT intel_2026 → generates from per_skala, pma_*, uraian fields
"""

import json
import re
import textwrap
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
OUTPUT = ROOT / "apps" / "mouth" / "src" / "lib" / "kbli-gold-batch-b.ts"

# Existing gold codes (from kbli-gold-content.ts) — skip these
EXISTING_GOLD: set[str] = set()


def load_existing_gold() -> set[str]:
    """Extract codes already in kbli-gold-content.ts."""
    gold_file = ROOT / "apps" / "mouth" / "src" / "lib" / "kbli-gold-content.ts"
    content = gold_file.read_text()
    return set(re.findall(r'"(\d{5})":\s*\{', content))


# ─── PMA helpers ─────────────────────────────────────────────────────────────

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
    else:  # TERBUKA
        line = "**PMA: OPEN** — 100% foreign ownership allowed."
        if prioritas:
            line += " Priority sector — tax incentives and streamlined licensing may apply."
        return line


# ─── Risk / licensing helpers ────────────────────────────────────────────────

RISK_ORDER = {
    "Rendah": 1,
    "Menengah Rendah": 2,
    "Menengah Tinggi": 3,
    "Tinggi": 4,
}

RISK_EN = {
    "Rendah": "Low",
    "Menengah Rendah": "Medium-Low",
    "Menengah Tinggi": "Medium-High",
    "Tinggi": "High",
}

SCALE_EN = {
    "Mikro": "Micro",
    "Kecil": "Small",
    "Menengah": "Medium",
    "Besar": "Large",
}


def format_scales(scales: list[str]) -> str:
    return " / ".join(SCALE_EN.get(s, s) for s in scales)


def licensing_summary(per_skala: list[dict[str, Any]]) -> str:
    """Generate whatYouNeed from per_skala entries."""
    if not per_skala:
        return "Licensing details not yet available in PP28/2025 for this code."

    # Sort by risk level
    sorted_entries = sorted(per_skala, key=lambda e: RISK_ORDER.get(e.get("kategori_risiko", ""), 5))

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

        # Key requirements (top 3)
        reqs = entry.get("persyaratan", [])
        if reqs:
            top_reqs = reqs[:3]
            req_text = "\\n".join(f"- {r[:120]}{'...' if len(r) > 120 else ''}" for r in top_reqs)
            if len(reqs) > 3:
                req_text += f"\\n- ...and {len(reqs) - 3} more requirements"
            line += f"\\n\\nKey requirements:\\n{req_text}"

        # Key obligations (top 2)
        obligs = entry.get("kewajiban", [])
        if obligs:
            top_obligs = obligs[:2]
            oblig_text = "\\n".join(f"- {o[:120]}{'...' if len(o) > 120 else ''}" for o in top_obligs)
            line += f"\\n\\nObligations:\\n{oblig_text}"

        parts.append(line)

    return "\\n\\n".join(parts)


def mapping_summary(code: dict[str, Any]) -> str:
    """Generate whatChanged from mapping status."""
    status = code.get("status_mapping", "")
    note = code.get("mapping_note") or code.get("aggregation_note") or ""
    source_2020 = code.get("kbli_2020_source") or ""

    if status == "MATCH_LANGSUNG":
        base = "Direct match from KBLI 2020 — code and scope unchanged."
    elif status == "CODICE_RINUMERATO":
        base = "Code was renumbered from KBLI 2020 (same activity, new code number)."
    elif status == "MATCH_CON_AGGREGAZIONE":
        base = "This code was created by merging multiple KBLI 2020 codes into one."
    elif status == "BPS_ONLY":
        base = "New code in KBLI 2025 — not present in KBLI 2020. This is a newly classified business activity."
    else:
        base = "Mapping status from KBLI 2020 is pending verification."

    if note:
        base += f" {note}"
    if source_2020:
        base += f" (Previous: {source_2020})"

    return base


def generate_what_it_means(code: dict[str, Any]) -> str:
    """Generate whatItMeans from judul + uraian."""
    judul = code.get("judul", "")
    uraian = code.get("uraian", "")

    # Clean up uraian
    uraian_clean = re.sub(r'\s+', ' ', uraian).strip()

    # Extract the key description
    if uraian_clean:
        # Take first 2 sentences or 300 chars
        sentences = re.split(r'(?<=[.!?])\s+', uraian_clean)
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

    # Extract English title if available (in parentheses)
    en_match = re.search(r'\(([A-Z][^)]+)\)', judul)
    title_en = en_match.group(1).title() if en_match else judul.split("(")[0].strip().title()

    if pma == "TERTUTUP":
        return f"Interested in {title_en.lower()}? Code {kode} is closed to foreign investment — let me explain the local-ownership requirements."
    elif pma == "TERBATAS":
        max_pct = code.get("pma_max_asing", 0)
        return f"Looking at {title_en.lower()}? Code {kode} allows up to {max_pct}% foreign ownership — let me walk you through the requirements."
    else:
        return f"Setting up {title_en.lower()} in Indonesia? Code {kode} is fully open to foreign investment — here's what you need to know."


def generate_gold_entry(code: dict[str, Any]) -> dict[str, str]:
    """Generate a complete Gold content entry for a KBLI code."""
    intel = code.get("intel_2026")

    if intel and any(intel.values()):
        # Use existing intel_2026 content, fill gaps
        return {
            "whatItMeans": intel.get("whatItMeans") or generate_what_it_means(code),
            "whatYouNeed": intel.get("whatYouNeed") or licensing_summary(code.get("per_skala", [])),
            "whatChanged": intel.get("whatChanged") or mapping_summary(code),
            "baliContext": intel.get("baliContext") or "",
            "youllAlsoNeed": intel.get("youllAlsoNeed") or "",
            "zantaraOpener": intel.get("zantaraOpener") or generate_zantara_opener(code),
        }
    else:
        # Generate everything from structured data
        what_you_need = licensing_summary(code.get("per_skala", []))
        pma_text = pma_summary(code)

        return {
            "whatItMeans": generate_what_it_means(code),
            "whatYouNeed": f"{what_you_need}\\n\\n{pma_text}",
            "whatChanged": mapping_summary(code),
            "baliContext": "",
            "youllAlsoNeed": "",
            "zantaraOpener": generate_zantara_opener(code),
        }


def escape_for_backtick(s: str) -> str:
    """Escape a string for use inside TypeScript backtick template literal."""
    if not s:
        return ""
    s = s.replace("\\", "\\\\")
    s = s.replace("`", "\\`")
    s = s.replace("${", "\\${")
    # Preserve intentional \\n markers as actual newlines in TS
    s = s.replace("\\\\n", "\\n")
    return s


def format_ts_entry(kode: str, entry: dict[str, str]) -> str:
    """Format a Gold content entry as TypeScript.

    Always uses backtick template literals to safely handle newlines in content.
    """
    lines = [f'  "{kode}": {{']

    for key in ["whatItMeans", "whatYouNeed", "whatChanged", "baliContext", "youllAlsoNeed", "zantaraOpener"]:
        val = entry.get(key, "")
        escaped = escape_for_backtick(val)
        if not escaped:
            lines.append(f'    {key}: "",')
        else:
            lines.append(f'    {key}:')
            lines.append(f'      `{escaped}`,')

    lines.append("  },")
    return "\n".join(lines)


def main() -> None:
    # Load source data
    with open(SOURCE) as f:
        data = json.load(f)

    all_codes = data["data"]
    batch_b = all_codes[500:1000]

    # Load existing gold codes to skip
    existing = load_existing_gold()
    print(f"Existing gold codes: {len(existing)}")

    # Generate gold content for batch B
    entries: list[tuple[str, dict[str, str]]] = []
    stats = {"intel_2026": 0, "generated": 0, "skipped_existing": 0}

    for code in batch_b:
        kode = code["kode_kbli_2025"]

        if kode in existing:
            stats["skipped_existing"] += 1
            continue

        entry = generate_gold_entry(code)
        entries.append((kode, entry))

        if code.get("intel_2026") and any(code["intel_2026"].values()):
            stats["intel_2026"] += 1
        else:
            stats["generated"] += 1

    print(f"Batch B results:")
    print(f"  From intel_2026: {stats['intel_2026']}")
    print(f"  Generated from structured data: {stats['generated']}")
    print(f"  Skipped (existing gold): {stats['skipped_existing']}")
    print(f"  Total entries: {len(entries)}")

    # Generate TypeScript file
    ts_parts = [
        "// =============================================================================",
        "// KBLI 2025 Gold-Tier Content — Batch B (codes index 500-999)",
        "// Auto-generated from KBLI_2025_FINAL_CLEAN.json",
        "// Source: BPS 7/2025 + PP28/2025 structured data + intel_2026 enrichment",
        f"// Generated: {__import_date()}",
        f"// Total entries: {len(entries)}",
        "// =============================================================================",
        "",
        'import type { KBLIGoldContent } from "./kbli-types";',
        "",
        "export const KBLI_GOLD_BATCH_B: Record<string, KBLIGoldContent> = {",
    ]

    # Group by section prefix for readability
    current_prefix = ""
    for kode, entry in sorted(entries, key=lambda x: x[0]):
        prefix = kode[:2]
        if prefix != current_prefix:
            current_prefix = prefix
            ts_parts.append(f"\n  // --- Section {prefix}xxx ---")
        ts_parts.append(format_ts_entry(kode, entry))

    ts_parts.append("};")
    ts_parts.append("")

    # Write output
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(ts_parts))
    print(f"\nOutput written to: {OUTPUT}")
    print(f"File size: {OUTPUT.stat().st_size:,} bytes")

    # Also output a JSON version for backend use
    json_output = ROOT / "apps" / "mouth" / "src" / "lib" / "kbli-gold-batch-b.json"
    json_data = {kode: entry for kode, entry in entries}
    with open(json_output, "w") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print(f"JSON output: {json_output}")
    print(f"JSON size: {json_output.stat().st_size:,} bytes")


def __import_date() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")


if __name__ == "__main__":
    main()
