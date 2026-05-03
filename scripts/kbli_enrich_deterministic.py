#!/usr/bin/env python3
"""Deterministic field builders for KBLI enrichment.
Extracted from apps/kbli-navigator/scripts/generate_gold_content.py.
Generates whatYouNeed, whatChanged, youllAlsoNeed from raw JSON data — no LLM.
"""
import re

RISK_MAP = {
    "Rendah": ("Low risk", "NIB only — issued automatically."),
    "Menengah Rendah": ("Medium-Low risk", "NIB + Standard Certificate — issued automatically."),
    "Menengah Tinggi": ("Medium-High risk", "NIB + Standard Certificate — issued within 7 working days."),
    "Tinggi": ("High risk", "NIB + Business License (Izin) — full review required."),
}

SCALE_MAP = {
    "Mikro": "Micro",
    "Kecil": "Small",
    "Menengah": "Medium",
    "Besar": "Large",
}

STATUS_MAP = {
    "MATCH_LANGSUNG": "Unchanged from KBLI 2020 — direct match.",
    "CODICE_RINUMERATO": "Renumbered from KBLI 2020. Your OSS registration may need updating to the new code.",
    "MATCH_CON_AGGREGAZIONE": "This code consolidates multiple KBLI 2020 activities into one. Verify your specific activity maps correctly.",
    "BPS_ONLY": "New in KBLI 2025 — no equivalent in KBLI 2020. Register fresh on OSS.",
    "NUOVO": "New in KBLI 2025 — no equivalent in KBLI 2020. Register fresh on OSS.",
}

# Sector-level related codes map for youllAlsoNeed (semi-deterministic)
SECTOR_RELATED: dict[str, list[str]] = {
    "I.J-P": ["55101", "55201", "55203", "56101", "56301", "79110", "93199"],  # Accommodation/Tourism
    "I.I": ["49111", "49120", "52292", "77100", "79110"],                       # Transport/Storage
    "I.G": ["46100", "47111", "47719", "47999"],                                # Trade/Wholesale-Retail
    "I.F.a": ["10295", "10296", "46201", "47212"],                              # Food manufacturing
    "I.F.b": ["11040", "11059", "46332"],                                       # Beverage manufacturing
    "I.B": ["01111", "01310", "01401", "46201"],                                # Agriculture
    "I.A": ["03110", "46201", "10200"],                                         # Fishery
    "I.C": ["02101", "16101", "46319"],                                         # Forestry
    "I.D": ["06100", "06201", "46610"],                                         # Mining/Energy
    "I.H": ["41011", "41012", "68112", "68200"],                                # Construction/Real estate
    "I.Q-V": ["69100", "70209", "74909", "82990"],                              # Services
    "None": [],
}

# Common Indonesian obligation phrases → English translations
_KEWAJIBAN_TRANSLATIONS: list[tuple[str, str]] = [
    ("cara budi daya tanaman pangan yang baik", "Apply good agricultural practices (GAP)"),
    ("cara budi daya tanaman yang baik", "Apply good agricultural practices (GAP)"),
    ("budi daya tanaman pangan yang baik", "Apply good agricultural practices (GAP)"),
    ("budi daya tanaman yang baik", "Apply good agricultural practices (GAP)"),
    ("standar mutu benih", "Apply seed quality standards"),
    ("laporan perkembangan usaha", "Submit periodic business activity reports"),
    ("laporan perkembang", "Submit periodic business activity reports"),  # corrupted variant
    ("laporan berkala", "Submit periodic activity reports"),
    ("laporan kegiatan usaha", "Submit business activity reports"),
    ("menyampaikan laporan", "Submit periodic activity reports"),
    ("standar pelayanan minimal", "Comply with minimum service standards"),
    ("sistem manajemen keselamatan", "Implement safety management system"),
    ("penerapan standar", "Comply with applicable standards"),
    ("label higiene sanitasi pangan", "Obtain Food Hygiene & Sanitation label (HSP)"),
    ("higiene sanitasi", "Food hygiene and sanitation compliance"),
    ("bukti penguasaan lahan", "Proof of land tenure/control"),
    ("lokasi produksi benih bukan daerah endemis", "Production site must be free from endemic pests (certified)"),
    ("izin operasi", "Obtain operational permit within 2 years of business license"),
    ("memiliki sertifikat standar usaha", "Obtain Standard Business Certificate (SSU)"),
    ("sertifikat standar", "Standard Certificate (auto-issued)"),
    ("tanda daftar usaha pariwisata", "Register as a tourism business (TDUP)"),
    ("amdal", "Environmental Impact Assessment (AMDAL) required"),
    ("upaya pengelolaan lingkungan", "Environmental management compliance (UKL-UPL)"),
    ("pengelolaan limbah", "Waste management compliance"),
    ("sarana produksi dalam negeri", "Use domestic inputs/materials where locally available"),
    ("menggunakan sarana produksi", "Use domestic inputs/materials where locally available"),
    ("data industri", "Submit industrial data report every 6 months (Kemenperin)"),
    ("laporan data industri", "Submit industrial data report every 6 months (Kemenperin)"),
    ("wajib data industri", "Submit industrial data report every 6 months (Kemenperin)"),
    ("berbentuk badan hukum", "Must be a legal entity (PT/CV) — incorporate before applying"),
    ("badan hukum", "Must be a legal entity (PT/CV) — incorporate before applying"),
    ("lkpm", "Submit quarterly investment activity report (LKPM) via OSS"),
    ("menyampaikan lkpm", "Submit quarterly investment activity report (LKPM) via OSS"),
    ("keselamatan dan kesehatan kerja", "Implement occupational health & safety (K3) system"),
    ("k3", "Implement occupational health & safety (K3) system"),
    ("sertifikat laik sehat", "Obtain Laik Sehat (SLS) health-ready certificate"),
    ("laik sehat", "Obtain Laik Sehat (SLS) health-ready certificate"),
    ("sertifikat standar usaha", "Obtain Standard Business Certificate (SSU) from Dinas"),
    ("sertifikat standar pariwisata", "Obtain Tourism Standard Certificate from Dinas Pariwisata"),
    ("haccp", "Implement HACCP food safety management system"),
    ("izin edar", "Obtain product marketing/circulation permit (Izin Edar)"),
    ("bpom", "Obtain BPOM registration for products"),
    ("halal", "Obtain halal certification (MUI) if serving Muslim market"),
    ("nkv", "Obtain Nomor Kontrol Veteriner (NKV) for animal products"),
    ("nomor kontrol veteriner", "Obtain Nomor Kontrol Veteriner (NKV) for animal products"),
]

def _translate_kewajiban(raw: str) -> str:
    """Translate a raw kewajiban string to English. Returns empty string if unrecognizable."""
    # Clean artifacts first
    text = " ".join(raw.split())               # collapse whitespace/newlines
    text = re.sub(r"(?<=[a-z])-\s+", "", text) # rejoin mid-word hyphens
    text = re.sub(r"\s+([.,;:])", r"\1", text) # remove space before punctuation
    text = text.strip().rstrip(".,;")

    text_lower = text.lower()

    for phrase, translation in _KEWAJIBAN_TRANSLATIONS:
        if phrase in text_lower:
            return translation

    # Generic fallback: clean and cap at 100 chars
    if len(text) > 8:  # skip very short garbage strings
        return text[:100] + ("..." if len(text) > 100 else "")
    return ""


def build_what_you_need(code: dict) -> str:
    """Build whatYouNeed from per_skala data — 100% deterministic, numbered steps."""
    per_skala = code.get("per_skala", [])
    pma_status = code.get("pma_status", "")
    pma_max = code.get("pma_max_asing", 0)
    pma_kondisi = code.get("pma_kondisi") or ""
    pma_nota = code.get("pma_nota") or ""

    # PMA line
    if pma_status == "TERBUKA":
        pma_line = f"**PMA:** Fully open — {pma_max}% foreign ownership allowed."
    elif pma_status == "TERTUTUP":
        pma_line = "**PMA:** Closed to foreign investment — domestic entities only."
    elif pma_status == "TERBATAS":
        pma_line = f"**PMA:** Restricted — max {pma_max}% foreign ownership."
    else:
        pma_line = ""
    if pma_kondisi:
        pma_line += f" Condition: {pma_kondisi}."
    if pma_nota and pma_nota not in pma_line:
        pma_line += f" Note: {pma_nota}."

    if not per_skala:
        base = "Licensing data not available in PP28/2025 for this code. Register NIB via OSS and monitor for updates."
        return base + (f"\n\n{pma_line}" if pma_line else "")

    # Build numbered steps from the first (most representative) scale
    # Then add scale variations below
    seen: set = set()
    scale_blocks: list[str] = []

    for s in per_skala:
        scales = s.get("skala_usaha", [])
        risk = s.get("kategori_risiko", "")
        if risk not in RISK_MAP:
            continue
        scale_str = " / ".join(SCALE_MAP.get(sc, sc) for sc in scales)
        risk_en, _ = RISK_MAP[risk]
        key = (scale_str, risk_en)
        if key in seen:
            continue
        seen.add(key)

        kewenangan = s.get("kewenangan", "")
        jangka_waktu = s.get("jangka_waktu", "") or "Otomatis"
        perizinan = s.get("perizinan", "") or "NIB"
        kewajiban = s.get("kewajiban", [])

        # Translate kewajiban
        translated_kew = [_translate_kewajiban(k) for k in kewajiban if k.strip()]
        translated_kew = [t for t in translated_kew if t]

        scale_blocks.append((scale_str, risk_en, perizinan, kewenangan, jangka_waktu, translated_kew))

    if not scale_blocks:
        base = "Licensing data not available in PP28/2025 for this code."
        return base + (f"\n\n{pma_line}" if pma_line else "")

    # Cap at 4 most distinct scale blocks to avoid bloat
    scale_blocks = scale_blocks[:4]

    # Collect all unique kewajiban across all scales (deduplicated)
    all_kewajiban: list[str] = []
    seen_kew: set[str] = set()
    for (_, _, _, _, _, translated_kew) in scale_blocks:
        for kew in translated_kew:
            if kew not in seen_kew:
                seen_kew.add(kew)
                all_kewajiban.append(kew)

    # Numbered steps: always start with PT PMA + NIB, then per-scale requirements
    steps: list[str] = []
    step_n = 1

    steps.append(f"{step_n}. **PT PMA incorporation** — notary deed, AHU registration, TDP (~2–4 weeks)")
    step_n += 1

    steps.append(f"{step_n}. **NIB via OSS** — register on oss.go.id, select this code, issued automatically (1–3 days)")
    step_n += 1

    # Translate common perizinan values to English
    _PERIZINAN_EN = {
        "NIB": "",  # already covered in step 2
        "NIB dan Sertifikat Standar": "NIB + Standard Certificate",
        "Sertifikat Standar": "Standard Certificate",
        "NIB dan Izin": "NIB + Business License (Izin)",
        "Izin": "Business License (Izin)",
        "NIB, Sertifikat Standar, dan Izin": "NIB + Standard Certificate + Business License",
    }

    # Per-scale licensing steps (license type only, no per-scale kewajiban)
    for (scale_str, risk_en, perizinan, kewenangan, jangka_waktu, _) in scale_blocks:
        license_desc = _PERIZINAN_EN.get(perizinan, perizinan) if perizinan else ""
        if license_desc:
            authority_note = f"Authority: {kewenangan}" if kewenangan else ""
            timing_note = jangka_waktu if jangka_waktu != "Otomatis" else "automatic"
            detail = " — ".join(filter(None, [authority_note, timing_note]))
            steps.append(f"{step_n}. **{license_desc}** ({scale_str}, {risk_en}) — {detail}")
            step_n += 1

    # Deduplicated post-license obligations (max 3)
    for kew in all_kewajiban[:3]:
        steps.append(f"{step_n}. **{kew}** — post-license obligation")
        step_n += 1

    # Scale summary note
    if len(scale_blocks) > 1:
        scale_summary_parts = []
        for (scale_str, risk_en, _, kewenangan, jangka_waktu, _) in scale_blocks:
            authority = kewenangan or "OSS"
            scale_summary_parts.append(f"{scale_str}: **{authority}** ({jangka_waktu})")
        scale_summary = "\n\n**Authority by scale:**\n" + " · ".join(scale_summary_parts)
    else:
        sc = scale_blocks[0]
        authority = sc[3] or "OSS / BKPM"
        scale_summary = f"\n\n**Authority:** {authority} · Processing: {sc[4]}"

    result = "\n".join(steps) + scale_summary
    if pma_line:
        result += f"\n\n{pma_line}"
    return result


def build_what_changed(code: dict) -> str:
    """Build whatChanged from status_mapping — deterministic with template."""
    mapping = code.get("status_mapping") or ""
    pp28 = code.get("pp28_sources", [])
    sources_str = ", ".join(pp28[:3]) if pp28 else ""

    base = STATUS_MAP.get(mapping, f"Mapping status: {mapping}.")

    if mapping == "MATCH_CON_AGGREGAZIONE" and sources_str:
        base += f" Previous KBLI 2020 sources: {sources_str}."
    elif mapping == "CODICE_RINUMERATO" and sources_str:
        base += f" Previous code(s): {sources_str}."

    return base


def build_youll_also_need(code: dict) -> str:
    """Build youllAlsoNeed — semi-deterministic from sektor_id."""
    sektor = str(code.get("sektor_id") or "None")
    current_code = code.get("kode_kbli_2025", "")

    related = [c for c in SECTOR_RELATED.get(sektor, []) if c != current_code]

    if not related:
        return (
            "Review related codes in the same sector for complementary activities. "
            "Use the KBLI Navigator search to find codes that commonly pair with this one."
        )

    return (
        "Common codes that pair with this activity:\n"
        + "\n".join(f"- **{c}**" for c in related[:5])
        + "\n\nSearch the KBLI Navigator for sector-specific pairings."
    )


def build_deterministic_fields(code: dict) -> dict:
    """Build all 3 deterministic fields for a KBLI code entry."""
    return {
        "whatYouNeed": build_what_you_need(code),
        "whatChanged": build_what_changed(code),
        "youllAlsoNeed": build_youll_also_need(code),
    }
