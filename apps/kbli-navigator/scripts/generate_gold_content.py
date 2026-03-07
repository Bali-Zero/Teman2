#!/usr/bin/env python3
"""
KBLI Gold Content Generator
Generates all 6 KBLIGoldContent fields for all 1563 KBLI 2025 codes.
Writes directly to kbli-gold-content.ts, preserving existing entries.

Usage:
  python scripts/generate_gold_content.py --limit 5 --dry-run
  python scripts/generate_gold_content.py --limit 10
  python scripts/generate_gold_content.py --sector I.I
  python scripts/generate_gold_content.py --skip-existing
  python scripts/generate_gold_content.py --skip-llm --skip-existing
  python scripts/generate_gold_content.py --ollama-host http://192.168.0.19:11434 --skip-existing
"""

import json
import sys
import re
import argparse
import urllib.request
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DATA_JSON = REPO_ROOT / "data" / "kbli-2025.json"
GOLD_TS = REPO_ROOT / "lib" / "kbli-gold-content.ts"

# ---------------------------------------------------------------------------
# Static maps
# ---------------------------------------------------------------------------
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

OLLAMA_MODEL = "qwen2.5-coder:32b"  # Override with --model flag; qwen2.5:32b also works if available

# ---------------------------------------------------------------------------
# Few-shot examples for LLM
# ---------------------------------------------------------------------------
FEW_SHOT = """
EXAMPLE 1:
code: 56101
judul: RESTORAN
uraian: Kelompok ini mencakup kegiatan usaha yang melayani penjualan makanan dan minuman untuk dikonsumsi di tempat usaha yang bangunannya bersifat tetap.
pma_status: TERBUKA (100%)
sektor_id: I.J-P
→ whatItMeans: "Running any food and beverage establishment in a permanent building — sit-down restaurants, warungs with fixed walls, food courts, and hotel dining. The key qualifier is 'permanent building': if customers come in, sit down, and eat food you cooked on-site, this is your code. Includes cafeterias, self-service spots, and hotel restaurants."
→ baliContext: "Bali's restaurant scene is the most competitive in Southeast Asia — Seminyak, Canggu, and Ubud are saturated, with premium spots running IDR 80–200M/year rent. TDUP (Dinas Pariwisata) and SLHS kitchen hygiene certificate are mandatory on top of the NIB — skipping either invites Satpol PP closure. If you serve alcohol, you'll need to add 56301 to your NIB; operating without it is the single most common enforcement trigger in Canggu."
→ zantaraOpener: "Opening a restaurant in Bali? 56101 is your main code — let me walk you through licensing, what changed in 2025, and how to structure a PMA operation correctly."

EXAMPLE 2:
code: 55203
judul: VILLA
uraian: Kelompok ini mencakup kegiatan penyediaan akomodasi jangka pendek oleh pengelola villa, dilengkapi dengan fasilitas hotel, kolam renang, dan dapur yang terpisah.
pma_status: TERBUKA (100%)
sektor_id: I.J-P
→ whatItMeans: "Short-term accommodation in a private villa — with hotel-grade facilities, private pool, and a separate kitchen. This is the standard code for Bali villa rentals. It covers both owner-managed and professionally managed villas open to paying guests, from boutique 1-bedroom villas to large estate properties."
→ baliContext: "The dominant PMA hospitality entry point in Bali. Beyond the NIB, you need TDUP from Dinas Pariwisata Kabupaten, PBG building permit (replaced IMB in 2022), and KKPR spatial conformity. Critical: villas in green zone agricultural land (LP2B) cannot be permitted regardless of ownership structure — check RDTR zoning before signing any land deal."
→ zantaraOpener: "Buying or building a villa in Bali? 55203 is the code — I can walk you through licensing, PMA structuring, zoning rules, and what's changed in 2025."

EXAMPLE 3:
code: 01131
judul: PERTANIAN SAYURAN DAUN
uraian: Kelompok ini mencakup kegiatan pertanian sayuran yang daun, bunga atau batangnya dimakan sebagai sayur, seperti articok, petsai/sawi, asparagus, kubis/kol, kembang kol, brokoli, selada, seledri, daun bawang, bayam, kangkung, dll.
pma_status: TERBUKA (100%)
sektor_id: I.B
→ whatItMeans: "Growing leafy vegetables commercially — spinach, kale, cabbage, lettuce, pak choi, kangkung, celery, leeks, broccoli, asparagus, and similar greens. Covers the full cycle: soil prep, planting, irrigation, pest management, and harvesting. The defining feature is that the leaf, stem, or flower of the plant is the edible product."
→ baliContext: "Organic premium produce for Bali's hotels and restaurants is the viable PMA niche — hotels in Ubud and Seminyak pay 2–4x market rate for certified organic local supply. The hard part is land: PMA cannot hold SHM (freehold) on agricultural land; HGU (cultivation rights) is the correct title, typically granted for 25–35 years. Subak water access is negotiated directly with the banjar, not through OSS — engage the local water council before signing any lease."
→ zantaraOpener: "Planning a leafy vegetable farm in Bali? Let me explain the licensing requirements, Subak water rules, and how to structure this as a PMA operation."

EXAMPLE 4:
code: 01113
judul: PERTANIAN KEDELAI
uraian: Kelompok ini mencakup kegiatan pertanian kedelai (Glycine max). Kelompok ini tidak mencakup pertanian kedelai sayur (edamame) atau kedelai rebus yang termasuk dalam kelompok 01116.
pma_status: TERBUKA (100%)
sektor_id: I.B
→ whatItMeans: "Commercial soybean cultivation (Glycine max) — covering the full cycle from land prep and planting to harvest and post-harvest handling. Important scope note: edamame and green soybeans for vegetable use fall under 01116, not this code. This is dry soybean for food processing, tempeh/tofu production, and export."
→ baliContext: "Soybean is a strategic food commodity in Indonesia — government intervention on prices and imports is common, which affects PMA business planning. In Bali, the main viable angle is supplying organic soy to artisan tempeh and tofu producers in Ubud and Denpasar. Land title rules apply: HGU required for PMA (not SHM). Unlike rice and corn, soybean has no Subak water dependency — dryland cultivation is common, which simplifies water rights."
→ zantaraOpener: "Planning a soybean farm in Bali? Let me walk you through licensing, the edamame vs. kedelai code distinction, and HGU land rights for PMA."
"""

SYSTEM_PROMPT = (
    "You are an expert on Indonesian business law writing precise, useful content for foreign investors in Bali.\n\n"
    "For each KBLI 2025 business code provided, generate THREE fields:\n\n"
    "1. whatItMeans: Plain English explanation, 3-4 sentences, ~250-400 chars.\n"
    "   - Lead with the core activity using a dash (e.g. 'Growing leafy vegetables —')\n"
    "   - Name SPECIFIC examples mentioned in the uraian — translate them, don't skip\n"
    "   - Include scope clarifications (what IS and is NOT covered) when the uraian mentions them\n"
    "   - Translate ALL Indonesian terms. No bureaucratic language.\n\n"
    "2. baliContext: Bali-specific practical intelligence, 3-5 sentences, ~350-550 chars.\n"
    "   RULES (strictly enforce):\n"
    "   - ONLY mention HGU, Subak, or LP2B if this specific code is DIRECTLY about farming/agriculture on Bali land\n"
    "   - NEVER use these for non-agricultural businesses (restaurants, IT, finance, consulting, retail, etc.)\n"
    "   - For hospitality: mention TDUP, SLHS, KKPR, zoning specifics — not HGU\n"
    "   - For finance: mention OJK license, modal disetor, fit & proper — not Subak\n"
    "   - For tech: mention PP 71/2019 data localization, Kominfo registration — not HGU\n"
    "   - Include at least ONE of: price range (IDR), specific Bali location, enforcement reality, or named permit\n"
    "   - Include ONE insider tip or common mistake specific to THIS code (not generic advice)\n"
    "   - Write in English. No Indonesian sentences.\n\n"
    "3. zantaraOpener: One conversational sentence for a chatbot, ~100-160 chars.\n"
    "   - Start with Bali context (e.g. 'Opening a X in Bali?')\n"
    "   - End with what Zantara will help with\n"
    "   - Be specific to the business activity\n\n"
    "Study these examples:\n"
    + FEW_SHOT
    + "\nRespond ONLY with valid JSON:\n"
    '{"results": [{"code": "56101", "whatItMeans": "...", "baliContext": "...", "zantaraOpener": "..."}, ...]}\n'
    "No extra text, no markdown fences."
)


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_kbli() -> list[dict]:
    with open(DATA_JSON) as f:
        data = json.load(f)
    return data["data"]


def load_existing_codes() -> set[str]:
    """Extract KBLI codes already present in kbli-gold-content.ts."""
    if not GOLD_TS.exists():
        return set()
    content = GOLD_TS.read_text()
    # Match "55203": { patterns
    return set(re.findall(r'"(\d{5})":\s*\{', content))


# ---------------------------------------------------------------------------
# Deterministic field builders
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# LLM batch enrichment
# ---------------------------------------------------------------------------

def ollama_generate(prompt: str, ollama_url: str, model: str = OLLAMA_MODEL) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": f"{SYSTEM_PROMPT}\n\n{prompt}",
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 6144},
    }).encode()
    req = urllib.request.Request(
        f"{ollama_url}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=360) as resp:
        result = json.loads(resp.read())
        return result.get("response", "").strip()


def enrich_llm_fields(
    targets: list[dict],
    batch_size: int = 5,
    ollama_url: str = "http://localhost:11434",
    model: str = OLLAMA_MODEL,
) -> dict[str, dict]:
    """Returns {code: {whatItMeans, baliContext, zantaraOpener}} for all targets."""
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
            f"  LLM batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}"
            f": {len(batch)} codes...",
            end="",
            flush=True,
        )

        raw = ""
        try:
            raw = ollama_generate(batch_text, ollama_url, model=model)

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
        except Exception as e:
            print(f" ✗ Error: {e}")

    return results


# ---------------------------------------------------------------------------
# TypeScript output
# ---------------------------------------------------------------------------

def escape_ts(text: str) -> str:
    """Escape a string for TypeScript template literal or double-quoted string."""
    return text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def format_ts_entry(code: str, content: dict) -> str:
    """Format a single KBLIGoldContent entry as TypeScript."""
    what_it_means = escape_ts(content.get("whatItMeans", ""))
    what_you_need = escape_ts(content.get("whatYouNeed", ""))
    what_changed = escape_ts(content.get("whatChanged", ""))
    bali_context = escape_ts(content.get("baliContext", ""))
    youll_also_need = escape_ts(content.get("youllAlsoNeed", ""))
    zantara_opener = escape_ts(content.get("zantaraOpener", ""))

    return (
        f'  "{code}": {{\n'
        f"    whatItMeans:\n"
        f"      `{what_it_means}`,\n"
        f"    whatYouNeed:\n"
        f"      `{what_you_need}`,\n"
        f"    whatChanged:\n"
        f"      `{what_changed}`,\n"
        f"    baliContext:\n"
        f"      `{bali_context}`,\n"
        f"    youllAlsoNeed:\n"
        f"      `{youll_also_need}`,\n"
        f"    zantaraOpener:\n"
        f"      `{zantara_opener}`,\n"
        f"  }},\n"
    )


def append_to_gold_ts(entries: list[tuple[str, dict]], dry_run: bool = False) -> None:
    """Append new entries to kbli-gold-content.ts, before the closing }."""
    if not entries:
        print("No entries to write.")
        return

    new_block = "\n".join(
        f"  // AUTO-GENERATED: {code}\n" + format_ts_entry(code, content)
        for code, content in entries
    )

    if dry_run:
        print("\n=== DRY RUN: TypeScript output ===")
        print(new_block[:3000])
        if len(new_block) > 3000:
            print(f"  ... [{len(new_block) - 3000} more chars] ...")
        return

    content = GOLD_TS.read_text()

    # Find the insertion point: before the closing }; of the record
    # The file ends with:   };\n\nexport function hasGoldContent...
    # We insert before the closing "}" of KBLI_GOLD_CONTENT
    marker = "\n};"
    idx = content.rfind(marker)
    if idx == -1:
        print("ERROR: Could not find closing '}' in kbli-gold-content.ts")
        sys.exit(1)

    new_content = content[:idx] + "\n" + new_block + content[idx:]
    GOLD_TS.write_text(new_content)
    print(f"  ✅ Wrote {len(entries)} entries to {GOLD_TS.name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate KBLIGoldContent entries for kbli-gold-content.ts"
    )
    parser.add_argument("--sector", help="Process only this sector ID (e.g. I.I)")
    parser.add_argument("--limit", type=int, help="Max codes to process")
    parser.add_argument("--dry-run", action="store_true", help="Print output, do not write")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip codes already present in kbli-gold-content.ts",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Only generate deterministic fields (no Ollama)",
    )
    parser.add_argument(
        "--ollama-host",
        default="http://localhost:11434",
        help="Ollama URL (default: http://localhost:11434). Use http://192.168.0.19:11434 for Mac Air.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="LLM batch size (default: 5)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override Ollama model (default: qwen2.5-coder:32b). Use qwen2.5:32b if available.",
    )
    parser.add_argument(
        "--range-start",
        type=int,
        default=0,
        help="Start index (0-based) in the filtered target list. Use with --range-end to split work.",
    )
    parser.add_argument(
        "--range-end",
        type=int,
        default=None,
        help="End index (exclusive) in the filtered target list. Default: process to end.",
    )
    args = parser.parse_args()

    # Load data
    codes = load_kbli()
    existing = load_existing_codes()
    print(f"Loaded {len(codes)} KBLI codes. {len(existing)} already in gold-content.ts.")

    # Filter targets
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

    print(f"\nProcessing {len(targets)} codes...")

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

    active_model = args.model or OLLAMA_MODEL

    if args.skip_llm:
        print("[LLM skipped — --skip-llm flag set]")
    else:
        # Phase 2: LLM fields
        print(f"\n[2/2] LLM enrichment via {active_model} @ {args.ollama_host}...")
        llm_results = enrich_llm_fields(
            targets, batch_size=args.batch_size, ollama_url=args.ollama_host, model=active_model
        )

        for code, llm_fields in llm_results.items():
            if code in gold_data:
                gold_data[code].update(llm_fields)

        print(f"  ✓ LLM fields received for {len(llm_results)}/{len(targets)} codes.")

    # Phase 3: Output
    entries = [(code, content) for code, content in gold_data.items()]
    entries.sort(key=lambda x: x[0])  # Sort by code

    if args.dry_run:
        print(f"\n[DRY RUN] {len(entries)} entries ready. Sample output:")
        # Show first 2 entries
        for code, content in entries[:2]:
            print(f"\n--- {code} ---")
            print(f"whatItMeans: {content.get('whatItMeans', '')[:150]}...")
            print(f"whatYouNeed: {content.get('whatYouNeed', '')[:150]}...")
            print(f"whatChanged: {content.get('whatChanged', '')[:100]}")
            print(f"baliContext: {content.get('baliContext', '')[:150]}...")
            print(f"youllAlsoNeed: {content.get('youllAlsoNeed', '')[:100]}...")
            print(f"zantaraOpener: {content.get('zantaraOpener', '')[:100]}...")
        append_to_gold_ts(entries[:2], dry_run=True)
        print(f"\n[DRY RUN] Run without --dry-run to write {len(entries)} entries.")
        return

    print(f"\nWriting {len(entries)} entries to kbli-gold-content.ts...")
    append_to_gold_ts(entries, dry_run=False)

    print(f"\n✅ Done. {len(entries)} gold content entries written.")
    new_total = len(existing) + len(entries)
    print(f"   Total in gold-content.ts: ~{new_total} / 1563 codes")


if __name__ == "__main__":
    main()
