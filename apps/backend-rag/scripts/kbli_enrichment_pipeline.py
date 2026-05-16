#!/usr/bin/env python3
"""
KBLI Full-Spectrum Enrichment Pipeline
=======================================
Enriches unenriched KBLI codes with tiered editorial content using local Ollama models.

Phases:
  1. Discovery  — find codes not yet in kbli-gold-all.json
  2. Classify   — tier each code (gold/silver/bronze) using qwen3.5:9b
  3. Generate   — produce editorial content per tier via Ollama
  4. Upsert     — write to kbli-gold-all.json + update Qdrant text payload

Usage:
  python scripts/kbli_enrichment_pipeline.py --dry-run --limit 5
  python scripts/kbli_enrichment_pipeline.py --limit 50 --tier gold
  python scripts/kbli_enrichment_pipeline.py --resume
  python scripts/kbli_enrichment_pipeline.py --tier all

Flags:
  --dry-run         Classify only, no upsert/write
  --limit N         Max codes to process
  --tier            gold | silver | bronze | all  (default: all)
  --resume          Continue from checkpoint (skip already processed codes)
  --phase 1|2|3|4  Run only that phase

Golden Rules:
  - Ollama native /api/chat (NOT OpenAI-compat)
  - think: false for qwen3.5
  - NEVER change embedding model (text-embedding-3-small frozen)
  - Flat Qdrant payload upsert (update text field only, preserve metadata)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent  # .../nuzantara
BACKEND_RAG = SCRIPT_DIR.parent

DATA_JSON = REPO_ROOT / "apps" / "kbli-navigator" / "data" / "kbli-2025.json"
GOLD_JSON = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"
CHECKPOINT_FILE = SCRIPT_DIR / "output" / "kbli_enrichment_state.json"
OUTPUT_DIR = SCRIPT_DIR / "output"

QDRANT_URL = "http://localhost:6333"
QDRANT_COLLECTION = "kbli_2025_final_hybrid"
OLLAMA_URL = "http://localhost:11434"

MODEL_CLASSIFY = "qwen3.5:9b"
MODEL_GOLD = "gemma4:26b"
MODEL_SILVER = "qwen3.5:9b"
MODEL_BRONZE = "gemma4:26b"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static maps (from generate_gold_content.py — battle-tested)
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

SECTOR_RELATED: dict[str, list[str]] = {
    "I.J-P": ["55101", "55201", "55203", "56101", "56301", "79110", "93199"],
    "I.I": ["49111", "49120", "52292", "77100", "79110"],
    "I.G": ["46100", "47111", "47719", "47999"],
    "I.F.a": ["10295", "10296", "46201", "47212"],
    "I.F.b": ["11040", "11059", "46332"],
    "I.B": ["01111", "01310", "01401", "46201"],
    "I.A": ["03110", "46201", "10200"],
    "I.C": ["02101", "16101", "46319"],
    "I.D": ["06100", "06201", "46610"],
    "I.H": ["41011", "41012", "68112", "68200"],
    "I.Q-V": ["69100", "70209", "74909", "82990"],
    "None": [],
}

_KEWAJIBAN_TRANSLATIONS: list[tuple[str, str]] = [
    ("cara budi daya tanaman pangan yang baik", "Apply good agricultural practices (GAP)"),
    ("cara budi daya tanaman yang baik", "Apply good agricultural practices (GAP)"),
    ("budi daya tanaman pangan yang baik", "Apply good agricultural practices (GAP)"),
    ("budi daya tanaman yang baik", "Apply good agricultural practices (GAP)"),
    ("standar mutu benih", "Apply seed quality standards"),
    ("laporan perkembangan usaha", "Submit periodic business activity reports"),
    ("laporan perkembang", "Submit periodic business activity reports"),
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

# System prompt for LLM (gold/silver tiers): 3 narrative fields
SYSTEM_PROMPT_3FIELDS = """You are an expert on Indonesian business law writing precise, useful content for foreign investors in Bali.

For each KBLI 2025 business code provided, generate THREE fields:

1. whatItMeans: Plain English explanation, 3-4 sentences, ~250-400 chars.
   - Lead with the core activity using a dash
   - Name SPECIFIC examples from the uraian — translate them
   - Include scope clarifications when the uraian mentions them
   - Translate ALL Indonesian terms. No bureaucratic language.

2. baliContext: Bali-specific practical intelligence, 3-5 sentences, ~350-550 chars.
   - Include at least ONE of: price range (IDR), Bali location, enforcement reality, named permit
   - Include ONE insider tip or common mistake specific to THIS code
   - Write in English
   - ONLY mention HGU/Subak/LP2B if this code is directly about farming on Bali land
   - For hospitality: mention TDUP, SLHS, KKPR, zoning
   - For finance: mention OJK license, modal disetor
   - For tech: mention PP 71/2019 data localization

3. zantaraOpener: One conversational chatbot sentence, ~100-160 chars.
   - Start with Bali context (e.g. "Opening a X in Bali?")
   - Be specific to the business activity

Respond ONLY with valid JSON:
{"results": [{"code": "XXXXX", "whatItMeans": "...", "baliContext": "...", "zantaraOpener": "..."}]}
No extra text, no markdown fences."""

# System prompt for bronze tier: minimal whatItMeans only
SYSTEM_PROMPT_MINIMAL = """For each KBLI code, write a plain English explanation of what this business activity covers.
2-3 sentences, ~150-250 chars. Lead with the core activity. Translate all Indonesian terms.
Respond ONLY with valid JSON:
{"results": [{"code": "XXXXX", "whatItMeans": "..."}]}
No extra text, no markdown fences."""

# Classification prompt
CLASSIFY_PROMPT_TEMPLATE = """Classify each KBLI 2025 code below into exactly one tier for Bali foreign investor relevance:

gold: PMA-eligible, high-traffic Bali sectors — tourism, hospitality, F&B, tech/digital nomad, education (yoga/surf/beauty), healthcare (clinics/IV drips), sports (padel/gyms), transport rental, professional services (legal, consulting, architecture, photography), real estate, wellness/spa

silver: Common local business types indirectly relevant to Bali — wholesale/retail trade, general manufacturing, logistics, financial services, HR/staffing, general education, telecoms, media production, environmental services

bronze: Niche/specialized, minimal Bali relevance — heavy industry, mining, oil/gas, large-scale agriculture (non-Bali crops), government/military, public utilities, highly restricted sectors, obscure manufacturing

Respond ONLY with valid JSON array — no extra text, no markdown:
[{{"code": "XXXXX", "tier": "gold|silver|bronze", "reason": "one sentence"}}]

Codes to classify:
{codes_block}"""


# ---------------------------------------------------------------------------
# Deterministic field builders (copied verbatim from generate_gold_content.py)
# ---------------------------------------------------------------------------

def _translate_kewajiban(raw: str) -> str:
    """Translate a raw kewajiban string to English."""
    text = " ".join(raw.split())
    text = re.sub(r"(?<=[a-z])-\s+", "", text)
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    text = text.strip().rstrip(".,;")
    text_lower = text.lower()
    for phrase, translation in _KEWAJIBAN_TRANSLATIONS:
        if phrase in text_lower:
            return translation
    if len(text) > 8:
        return text[:100] + ("..." if len(text) > 100 else "")
    return ""


def build_what_you_need(code: dict) -> str:
    """Build whatYouNeed from per_skala data — 100% deterministic."""
    per_skala = code.get("per_skala", [])
    pma_status = code.get("pma_status", "")
    pma_max = code.get("pma_max_asing", 0)
    pma_kondisi = code.get("pma_kondisi") or ""
    pma_nota = code.get("pma_nota") or ""

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

    seen: set = set()
    scale_blocks: list = []

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

        translated_kew = [_translate_kewajiban(k) for k in kewajiban if k.strip()]
        translated_kew = [t for t in translated_kew if t]
        scale_blocks.append((scale_str, risk_en, perizinan, kewenangan, jangka_waktu, translated_kew))

    if not scale_blocks:
        base = "Licensing data not available in PP28/2025 for this code."
        return base + (f"\n\n{pma_line}" if pma_line else "")

    scale_blocks = scale_blocks[:4]

    all_kewajiban: list[str] = []
    seen_kew: set[str] = set()
    for (_, _, _, _, _, translated_kew) in scale_blocks:
        for kew in translated_kew:
            if kew not in seen_kew:
                seen_kew.add(kew)
                all_kewajiban.append(kew)

    steps: list[str] = []
    step_n = 1

    steps.append(f"{step_n}. **PT PMA incorporation** — notary deed, AHU registration, TDP (~2–4 weeks)")
    step_n += 1
    steps.append(f"{step_n}. **NIB via OSS** — register on oss.go.id, select this code, issued automatically (1–3 days)")
    step_n += 1

    _PERIZINAN_EN = {
        "NIB": "",
        "NIB dan Sertifikat Standar": "NIB + Standard Certificate",
        "Sertifikat Standar": "Standard Certificate",
        "NIB dan Izin": "NIB + Business License (Izin)",
        "Izin": "Business License (Izin)",
        "NIB, Sertifikat Standar, dan Izin": "NIB + Standard Certificate + Business License",
    }

    for (scale_str, risk_en, perizinan, kewenangan, jangka_waktu, _) in scale_blocks:
        license_desc = _PERIZINAN_EN.get(perizinan, perizinan) if perizinan else ""
        if license_desc:
            authority_note = f"Authority: {kewenangan}" if kewenangan else ""
            timing_note = jangka_waktu if jangka_waktu != "Otomatis" else "automatic"
            detail = " — ".join(filter(None, [authority_note, timing_note]))
            steps.append(f"{step_n}. **{license_desc}** ({scale_str}, {risk_en}) — {detail}")
            step_n += 1

    for kew in all_kewajiban[:3]:
        steps.append(f"{step_n}. **{kew}** — post-license obligation")
        step_n += 1

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
    """Build whatChanged from status_mapping — deterministic."""
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
# Checkpoint management
# ---------------------------------------------------------------------------

def load_checkpoint() -> dict:
    """Load state from checkpoint file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"processed": {}, "meta": {}}


def save_checkpoint(state: dict) -> None:
    """Persist state to checkpoint file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Source data loading
# ---------------------------------------------------------------------------

def load_source_data() -> tuple[list[dict], dict[str, dict]]:
    """Load KBLI 2025 source JSON. Returns (list, {code: entry} lookup)."""
    with open(DATA_JSON) as f:
        data = json.load(f)
    entries = data["data"]
    lookup = {c["kode_kbli_2025"]: c for c in entries}
    return entries, lookup


def find_unenriched(all_codes: list[dict]) -> list[dict]:
    """
    Return codes not in kbli-gold-all.json OR with content < 500 chars in any field.
    Skips codes already in gold with sufficient content.
    """
    existing: dict = {}
    if GOLD_JSON.exists():
        with open(GOLD_JSON) as f:
            existing = json.load(f)

    unenriched = []
    for code in all_codes:
        kode = code["kode_kbli_2025"]
        if kode not in existing:
            unenriched.append(code)
            continue
        entry = existing[kode]
        # Skip codes with >= 500 chars of whatItMeans (already richly enriched)
        what_it_means = entry.get("whatItMeans", "")
        if len(what_it_means) >= 500:
            continue
        unenriched.append(code)

    return unenriched


# ---------------------------------------------------------------------------
# Ollama API (native /api/chat — NOT OpenAI-compat)
# ---------------------------------------------------------------------------

def call_ollama(model: str, system: str, user_prompt: str, timeout: int = 180) -> str:
    """
    Call Ollama /api/chat with think:false for qwen3.5 models.
    Returns the assistant message content.
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 8192,
        },
    }
    # think:false is critical for qwen3.5 to avoid output stripping
    if "qwen3.5" in model or "qwen" in model.lower():
        payload["options"]["think"] = False

    encoded = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=encoded,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())
        return result["message"]["content"].strip()


def parse_llm_json(raw: str) -> list[dict]:
    """Parse LLM JSON response. Handles markdown fences and <think> tags."""
    text = raw
    # Strip <think>...</think> (DeepSeek-R1)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip markdown fences
    if "```" in text:
        if "```json" in text:
            text = text.split("```json", 1)[1].rsplit("```", 1)[0]
        else:
            text = text.split("```", 1)[1].rsplit("```", 1)[0]
    text = text.strip()
    parsed = json.loads(text)
    if isinstance(parsed, list):
        return parsed
    return parsed.get("results", [])


# ---------------------------------------------------------------------------
# Anthropic API — fast classify via claude-haiku-4-5
# ---------------------------------------------------------------------------

def call_anthropic_classify(codes_block: str) -> str:
    """
    Classify a batch of KBLI codes via Anthropic API (claude-haiku-4-5-20251001).
    Raises RuntimeError if ANTHROPIC_API_KEY not set.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    prompt = CLASSIFY_PROMPT_TEMPLATE.format(codes_block=codes_block)
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    encoded = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=encoded,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        return result["content"][0]["text"].strip()


# ---------------------------------------------------------------------------
# Gemini CLI — gemini-3.1-pro-preview for content generation
# ---------------------------------------------------------------------------

GEMINI_CLI = "gemini"
GEMINI_MODEL = "gemini-3.1-pro-preview"

def call_gemini_cli(system: str, user_prompt: str, timeout: int = 120) -> str:
    """
    Call gemini CLI (subscription, zero API cost) with gemini-3.1-pro-preview.
    Passes system+user as a single prompt. Returns raw text output.
    """
    full_prompt = f"{system}\n\n---\n\n{user_prompt}"
    result = subprocess.run(
        [GEMINI_CLI, "--model", GEMINI_MODEL, "--prompt", full_prompt],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gemini CLI error (rc={result.returncode}): {result.stderr[:300]}")
    # Strip CLI noise lines (Keychain errors, MCP logs) — keep only JSON
    lines = result.stdout.splitlines()
    clean = "\n".join(
        line for line in lines
        if not line.startswith("Keychain") and not line.startswith("Using") and
           not line.startswith("Loaded") and not line.startswith("Server") and
           not line.startswith("Scheduling") and not line.startswith("Executing") and
           not line.startswith("MCP")
    ).strip()
    return clean


# ---------------------------------------------------------------------------
# Phase 2: Tier Classification
# ---------------------------------------------------------------------------

def classify_tiers(codes: list[dict], state: dict, dry_run: bool = False) -> dict[str, str]:
    """
    Classify codes into gold/silver/bronze.
    Primary:  claude-haiku-4-5 via Anthropic API — batch 20, ~3-5s each.
    Fallback: qwen3.5:9b via Ollama — batch 2, ~90s each.
    Saves results to state["processed"][code]["tier"].
    Returns {code: tier} mapping.
    """
    use_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY", ""))
    classifier = "claude-haiku-4-5 (Anthropic API)" if use_anthropic else f"{MODEL_CLASSIFY} (Ollama)"
    logger.info(f"Phase 2 — Classify: {len(codes)} codes using {classifier}")
    tier_map: dict[str, str] = {}

    # Skip already classified
    to_classify = []
    for c in codes:
        kode = c["kode_kbli_2025"]
        existing = state["processed"].get(kode, {})
        if "tier" in existing:
            tier_map[kode] = existing["tier"]
        else:
            to_classify.append(c)

    logger.info(f"  Already classified: {len(tier_map)}, remaining: {len(to_classify)}")

    batch_size = 20 if use_anthropic else 2
    timeout_s = 30 if use_anthropic else 360

    n_batches = (len(to_classify) + batch_size - 1) // batch_size
    for i in range(0, len(to_classify), batch_size):
        batch = to_classify[i : i + batch_size]
        codes_block = "\n".join(
            f"- {c['kode_kbli_2025']}: {c['judul']} | PMA: {c.get('pma_status', '?')} | sector: {c.get('sektor_id', '?')}"
            for c in batch
        )

        logger.info(
            f"  Classify batch {i // batch_size + 1}/{n_batches}"
            f" ({len(batch)} codes)..."
        )
        try:
            if use_anthropic:
                raw = call_anthropic_classify(codes_block)
            else:
                prompt = CLASSIFY_PROMPT_TEMPLATE.format(codes_block=codes_block)
                raw = call_ollama(MODEL_CLASSIFY, "", prompt, timeout=timeout_s)

            parsed = parse_llm_json(raw)
            for item in parsed:
                kode = item.get("code", "")
                tier = item.get("tier", "bronze").lower()
                if tier not in ("gold", "silver", "bronze"):
                    tier = "bronze"
                tier_map[kode] = tier
                if not dry_run:
                    if kode not in state["processed"]:
                        state["processed"][kode] = {}
                    state["processed"][kode]["tier"] = tier
                    state["processed"][kode]["reason"] = item.get("reason", "")
            save_checkpoint(state)
            logger.info(f"    -> {len(parsed)} classified")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"  Parse error in classify batch: {e}")
            for c in batch:
                tier_map[c["kode_kbli_2025"]] = "silver"
        except Exception as e:
            logger.error(f"  Classify batch failed: {e}")
            for c in batch:
                tier_map[c["kode_kbli_2025"]] = "silver"

    # Print tier summary
    counts: dict[str, int] = {"gold": 0, "silver": 0, "bronze": 0}
    for t in tier_map.values():
        counts[t] = counts.get(t, 0) + 1
    logger.info(f"  Tier distribution: gold={counts['gold']}, silver={counts['silver']}, bronze={counts['bronze']}")

    return tier_map


# ---------------------------------------------------------------------------
# Phase 3: Content Generation
# ---------------------------------------------------------------------------

def generate_content_gold(codes: list[dict], batch_size: int = 5) -> dict[str, dict]:
    """
    Generate 3 narrative fields for gold-tier codes.
    Primary: gemini-3.1-pro-preview CLI (subscription). Fallback: gemma4:26b Ollama.
    Gold: PMA-eligible, high-traffic — 800-1000 words guide.
    Fallback: qwen3.5:27b via Ollama.
    """
    results: dict[str, dict] = {}
    total = len(codes)
    for i in range(0, total, batch_size):
        batch = codes[i : i + batch_size]
        user_prompt = "\n\n".join(
            f"code: {c['kode_kbli_2025']}\n"
            f"judul: {c['judul']}\n"
            f"uraian: {c.get('uraian', '')[:700]}\n"
            f"pma_status: {c.get('pma_status', 'TERBUKA')} ({c.get('pma_max_asing', 100)}%)\n"
            f"sektor_id: {c.get('sektor_id', 'N/A')}"
            for c in batch
        )
        logger.info(
            f"  [gold] Batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}"
            f": {[c['kode_kbli_2025'] for c in batch]}"
        )
        try:
            raw = call_gemini_cli(SYSTEM_PROMPT_3FIELDS, user_prompt, timeout=120)
            parsed = parse_llm_json(raw)
            for item in parsed:
                kode = item.get("code", "")
                if kode:
                    results[kode] = {
                        "whatItMeans": item.get("whatItMeans", ""),
                        "baliContext": item.get("baliContext", ""),
                        "zantaraOpener": item.get("zantaraOpener", ""),
                    }
            logger.info(f"    -> OK via gemini-3.1-pro-preview ({len(parsed)} results)")
        except Exception as e:
            logger.warning(f"    -> gemini failed ({e}), fallback Ollama...")
            try:
                raw = call_ollama(MODEL_GOLD, SYSTEM_PROMPT_3FIELDS, user_prompt, timeout=600)
                parsed = parse_llm_json(raw)
                for item in parsed:
                    kode = item.get("code", "")
                    if kode:
                        results[kode] = {
                            "whatItMeans": item.get("whatItMeans", ""),
                            "baliContext": item.get("baliContext", ""),
                            "zantaraOpener": item.get("zantaraOpener", ""),
                        }
                logger.info(f"    -> OK via Ollama fallback ({len(parsed)} results)")
            except Exception as e2:
                logger.warning(f"    -> FAILED both: {e2}")
    return results


def generate_content_silver(codes: list[dict], batch_size: int = 8) -> dict[str, dict]:
    """
    Generate 3 narrative fields for silver-tier codes using gemini-3.1-pro-preview (CLI).
    Silver: 300-500 word summary.
    Fallback: qwen3.5:9b via Ollama.
    """
    results: dict[str, dict] = {}
    total = len(codes)
    for i in range(0, total, batch_size):
        batch = codes[i : i + batch_size]
        user_prompt = "\n\n".join(
            f"code: {c['kode_kbli_2025']}\n"
            f"judul: {c['judul']}\n"
            f"uraian: {c.get('uraian', '')[:500]}\n"
            f"pma_status: {c.get('pma_status', 'TERBUKA')} ({c.get('pma_max_asing', 100)}%)\n"
            f"sektor_id: {c.get('sektor_id', 'N/A')}"
            for c in batch
        )
        logger.info(
            f"  [silver] Batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}"
            f": {[c['kode_kbli_2025'] for c in batch]}"
        )
        try:
            raw = call_gemini_cli(SYSTEM_PROMPT_3FIELDS, user_prompt, timeout=120)
            parsed = parse_llm_json(raw)
            for item in parsed:
                kode = item.get("code", "")
                if kode:
                    results[kode] = {
                        "whatItMeans": item.get("whatItMeans", ""),
                        "baliContext": item.get("baliContext", ""),
                        "zantaraOpener": item.get("zantaraOpener", ""),
                    }
            logger.info(f"    -> OK via gemini-3.1-pro-preview ({len(parsed)} results)")
        except Exception as e:
            logger.warning(f"    -> gemini failed ({e}), fallback Ollama...")
            try:
                raw = call_ollama(MODEL_SILVER, SYSTEM_PROMPT_3FIELDS, user_prompt, timeout=360)
                parsed = parse_llm_json(raw)
                for item in parsed:
                    kode = item.get("code", "")
                    if kode:
                        results[kode] = {
                            "whatItMeans": item.get("whatItMeans", ""),
                            "baliContext": item.get("baliContext", ""),
                            "zantaraOpener": item.get("zantaraOpener", ""),
                        }
                logger.info(f"    -> OK via Ollama fallback ({len(parsed)} results)")
            except Exception as e2:
                logger.warning(f"    -> FAILED both: {e2}")
    return results


def generate_content_bronze(codes: list[dict], batch_size: int = 10) -> dict[str, dict]:
    """
    Generate minimal content (whatItMeans only) for bronze-tier codes.
    Primary: gemini-3.1-pro-preview CLI (subscription). Fallback: gemma4:26b Ollama.
    Bronze: 100-200 word basic description.
    Fallback: gemma3:12b via Ollama.
    """
    results: dict[str, dict] = {}
    total = len(codes)
    for i in range(0, total, batch_size):
        batch = codes[i : i + batch_size]
        user_prompt = "\n\n".join(
            f"code: {c['kode_kbli_2025']}\n"
            f"judul: {c['judul']}\n"
            f"uraian: {c.get('uraian', '')[:400]}"
            for c in batch
        )
        logger.info(
            f"  [bronze] Batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}"
            f": {[c['kode_kbli_2025'] for c in batch]}"
        )
        try:
            raw = call_gemini_cli(SYSTEM_PROMPT_MINIMAL, user_prompt, timeout=120)
            parsed = parse_llm_json(raw)
            for item in parsed:
                kode = item.get("code", "")
                if kode:
                    results[kode] = {"whatItMeans": item.get("whatItMeans", "")}
            logger.info(f"    -> OK via gemini-3.1-pro-preview ({len(parsed)} results)")
        except Exception as e:
            logger.warning(f"    -> gemini failed ({e}), fallback Ollama...")
            try:
                raw = call_ollama(MODEL_BRONZE, SYSTEM_PROMPT_MINIMAL, user_prompt, timeout=240)
                parsed = parse_llm_json(raw)
                for item in parsed:
                    kode = item.get("code", "")
                    if kode:
                        results[kode] = {"whatItMeans": item.get("whatItMeans", "")}
                logger.info(f"    -> OK via Ollama fallback ({len(parsed)} results)")
            except Exception as e2:
                logger.warning(f"    -> FAILED both: {e2}")
    return results


def build_full_entry(code: dict, narrative: dict) -> dict:
    """
    Merge LLM narrative fields + deterministic fields into a complete gold-all entry.
    All 6 standard fields always populated.
    """
    det_what_you_need = build_what_you_need(code)
    det_what_changed = build_what_changed(code)
    det_youll_also_need = build_youll_also_need(code)

    return {
        "whatItMeans": narrative.get("whatItMeans", ""),
        "whatYouNeed": det_what_you_need,
        "whatChanged": det_what_changed,
        "baliContext": narrative.get("baliContext", ""),
        "youllAlsoNeed": det_youll_also_need,
        "zantaraOpener": narrative.get("zantaraOpener", ""),
    }


# ---------------------------------------------------------------------------
# Phase 4: Upsert
# ---------------------------------------------------------------------------

def upsert_to_gold_json(entries: dict[str, dict], dry_run: bool = False) -> int:
    """
    Merge new entries into kbli-gold-all.json.
    Preserves existing tkaInfo. Overwrites content fields.
    Returns count of entries written.
    """
    existing: dict = {}
    if GOLD_JSON.exists():
        with open(GOLD_JSON) as f:
            existing = json.load(f)

    for code, content in entries.items():
        tka_info = existing.get(code, {}).get("tkaInfo")
        if code in existing:
            existing[code].update(content)
        else:
            existing[code] = content
        if tka_info:
            existing[code]["tkaInfo"] = tka_info

    if dry_run:
        logger.info(f"  DRY RUN: Would write {len(entries)} entries to {GOLD_JSON} (total: {len(existing)})")
        return len(entries)

    with open(GOLD_JSON, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False, sort_keys=True)

    logger.info(f"  Wrote {len(entries)} entries to {GOLD_JSON} (total: {len(existing)})")
    return len(entries)


def upsert_to_qdrant(code_str: str, judul: str, content: dict, dry_run: bool = False) -> bool:
    """
    Update the Qdrant point's text payload with enriched content.
    Finds the point by kode_kbli in metadata, then patches its text field.
    Preserves existing metadata. Uses flat payload update.
    """
    if dry_run:
        return True

    # Build enriched text block to append/replace
    enriched_text = (
        f"\n\n--- ENRICHED CONTENT ---\n"
        f"whatItMeans: {content.get('whatItMeans', '')}\n\n"
        f"baliContext: {content.get('baliContext', '')}\n\n"
        f"zantaraOpener: {content.get('zantaraOpener', '')}\n"
    )

    # Scroll to find the point(s) for this code
    try:
        scroll_payload = json.dumps({
            "filter": {
                "must": [
                    {"key": "kode_kbli", "match": {"value": code_str}}
                ]
            },
            "limit": 10,
            "with_payload": True,
            "with_vector": False,
        }).encode()
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/scroll",
            data=scroll_payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        points = result.get("result", {}).get("points", [])
    except Exception as e:
        logger.warning(f"    Qdrant scroll failed for {code_str}: {e}")
        return False

    if not points:
        logger.debug(f"    No Qdrant points found for {code_str}")
        return False

    # Update each point's text field (flat payload patch)
    updated = 0
    for point in points:
        point_id = point["id"]
        existing_text = point.get("payload", {}).get("text", "")

        # Strip any previous enrichment block, append new
        if "--- ENRICHED CONTENT ---" in existing_text:
            existing_text = existing_text.split("--- ENRICHED CONTENT ---")[0].rstrip()

        new_text = existing_text + enriched_text

        patch_payload = json.dumps({
            "points": [{"id": point_id, "payload": {"text": new_text}}]
        }).encode()
        try:
            req = urllib.request.Request(
                f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/payload",
                data=patch_payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
            updated += 1
        except Exception as e:
            logger.warning(f"    Qdrant patch failed for point {point_id} ({code_str}): {e}")

    return updated > 0


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(
    args: argparse.Namespace,
    all_codes: list[dict],
    source_lookup: dict[str, dict],
) -> None:
    state = load_checkpoint()
    if "processed" not in state:
        state["processed"] = {}
    if "meta" not in state:
        state["meta"] = {}

    # Phase 1: Discovery
    if args.phase is None or args.phase == 1:
        logger.info("=" * 60)
        logger.info("PHASE 1 — DISCOVERY")
        unenriched = find_unenriched(all_codes)
        if args.tier != "all":
            # Filter by tier if already classified (resume scenario)
            unenriched = [
                c for c in unenriched
                if state["processed"].get(c["kode_kbli_2025"], {}).get("tier", args.tier) == args.tier
            ]
        if args.limit:
            unenriched = unenriched[: args.limit]
        logger.info(f"  Unenriched codes to process: {len(unenriched)}")
        state["meta"]["discovery_count"] = len(unenriched)
        state["meta"]["discovery_ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_checkpoint(state)
    else:
        # Load from checkpoint when running specific phase
        unenriched = [
            source_lookup[kode]
            for kode in state["processed"]
            if kode in source_lookup
        ]
        if args.limit:
            unenriched = unenriched[: args.limit]

    if not unenriched:
        logger.info("No codes to process — all already enriched or limit=0.")
        return

    # Phase 2: Classification
    if args.phase is None or args.phase == 2:
        logger.info("=" * 60)
        logger.info("PHASE 2 — CLASSIFY")
        tier_map = classify_tiers(unenriched, state, dry_run=args.dry_run)
    else:
        tier_map = {
            c["kode_kbli_2025"]: state["processed"].get(c["kode_kbli_2025"], {}).get("tier", "silver")
            for c in unenriched
        }

    if args.dry_run:
        logger.info("DRY RUN — stopping after classification (no content generation or upsert).")
        # Print sample classification results
        tier_counts: dict[str, int] = {"gold": 0, "silver": 0, "bronze": 0}
        for tier in tier_map.values():
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        logger.info(f"  Classification summary: {tier_counts}")
        sample = list(tier_map.items())[:10]
        for kode, tier in sample:
            entry = source_lookup.get(kode, {})
            logger.info(f"  {kode} ({entry.get('judul', '')[:40]}): {tier}")
        return

    # Phase 3: Content Generation
    if args.phase is None or args.phase == 3:
        logger.info("=" * 60)
        logger.info("PHASE 3 — GENERATE")

        # Split by tier
        gold_codes = [
            source_lookup[k] for k, t in tier_map.items()
            if t == "gold" and k in source_lookup
            and not state["processed"].get(k, {}).get("generated")
        ]
        silver_codes = [
            source_lookup[k] for k, t in tier_map.items()
            if t == "silver" and k in source_lookup
            and not state["processed"].get(k, {}).get("generated")
        ]
        bronze_codes = [
            source_lookup[k] for k, t in tier_map.items()
            if t == "bronze" and k in source_lookup
            and not state["processed"].get(k, {}).get("generated")
        ]

        # Apply tier filter from CLI
        if args.tier == "gold":
            silver_codes = []
            bronze_codes = []
        elif args.tier == "silver":
            gold_codes = []
            bronze_codes = []
        elif args.tier == "bronze":
            gold_codes = []
            silver_codes = []

        logger.info(f"  gold: {len(gold_codes)}, silver: {len(silver_codes)}, bronze: {len(bronze_codes)}")

        # Generate per tier
        all_narrative: dict[str, dict] = {}

        if gold_codes:
            logger.info(f"  Generating gold ({MODEL_GOLD})...")
            gold_narrative = generate_content_gold(gold_codes)
            all_narrative.update(gold_narrative)

        if silver_codes:
            logger.info(f"  Generating silver ({MODEL_SILVER})...")
            silver_narrative = generate_content_silver(silver_codes)
            all_narrative.update(silver_narrative)

        if bronze_codes:
            logger.info(f"  Generating bronze ({MODEL_BRONZE})...")
            bronze_narrative = generate_content_bronze(bronze_codes)
            all_narrative.update(bronze_narrative)

        # Merge narrative + deterministic fields
        all_entries: dict[str, dict] = {}
        for code_obj in unenriched:
            kode = code_obj["kode_kbli_2025"]
            if kode not in all_narrative:
                continue
            full_entry = build_full_entry(code_obj, all_narrative[kode])
            all_entries[kode] = full_entry
            state["processed"][kode]["generated"] = True
            state["processed"][kode]["tier"] = tier_map.get(kode, "silver")

        save_checkpoint(state)
        logger.info(f"  Generated {len(all_entries)} entries total")

    # Phase 4: Upsert
    if args.phase is None or args.phase == 4:
        logger.info("=" * 60)
        logger.info("PHASE 4 — UPSERT")

        if args.phase == 4:
            # Reconstruct all_entries from checkpoint when running phase 4 standalone
            # (requires generated content to be saved; simplified: re-generate from state)
            logger.warning("  Phase 4 standalone requires all_entries from phase 3. Re-run without --phase or from phase 3.")
            return

        # If no new entries generated (resume scenario), rebuild from kbli-gold-all.json
        if not all_entries:
            logger.info("  No new entries generated — rebuilding all_entries from kbli-gold-all.json for Qdrant upsert...")
            try:
                with open(GOLD_JSON) as f:
                    existing_gold = json.load(f)
                for kode, content in existing_gold.items():
                    if kode in {c["kode_kbli_2025"] for c in unenriched}:
                        all_entries[kode] = content
                logger.info(f"  Rebuilt {len(all_entries)} entries from JSON for Qdrant upsert")
            except Exception as e:
                logger.error(f"  Failed to rebuild entries: {e}")
                return

        if not all_entries:
            logger.info("  No entries to upsert.")
            return

        # Write to kbli-gold-all.json
        upsert_to_gold_json(all_entries, dry_run=False)

        # Update Qdrant points
        qdrant_ok = 0
        qdrant_fail = 0
        for kode, content in all_entries.items():
            code_obj = source_lookup.get(kode, {})
            judul = code_obj.get("judul", "")
            ok = upsert_to_qdrant(kode, judul, content, dry_run=False)
            if ok:
                qdrant_ok += 1
                state["processed"][kode]["qdrant_updated"] = True
            else:
                qdrant_fail += 1

        save_checkpoint(state)
        logger.info(f"  Qdrant updates: {qdrant_ok} OK, {qdrant_fail} skipped/failed")

    # Final summary
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    total_processed = sum(
        1 for v in state["processed"].values() if v.get("generated")
    )
    logger.info(f"  Total in checkpoint: {len(state['processed'])}")
    logger.info(f"  Total generated: {total_processed}")
    logger.info(f"  Checkpoint: {CHECKPOINT_FILE}")
    if GOLD_JSON.exists():
        with open(GOLD_JSON) as f:
            gold_count = len(json.load(f))
        logger.info(f"  kbli-gold-all.json entries: {gold_count}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="KBLI Full-Spectrum Enrichment Pipeline — enrich unenriched KBLI codes with tiered editorial content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/kbli_enrichment_pipeline.py --dry-run --limit 5
  python scripts/kbli_enrichment_pipeline.py --limit 50 --tier gold
  python scripts/kbli_enrichment_pipeline.py --resume
  python scripts/kbli_enrichment_pipeline.py --tier all
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify only, no content generation or upsert",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of codes to process",
    )
    parser.add_argument(
        "--tier",
        choices=["gold", "silver", "bronze", "all"],
        default="all",
        help="Process only this tier (default: all)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint (skip already classified/generated codes)",
    )
    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2, 3, 4],
        default=None,
        help="Run only this phase: 1=discover, 2=classify, 3=generate, 4=upsert",
    )

    args = parser.parse_args()

    logger.info("KBLI Full-Spectrum Enrichment Pipeline")
    logger.info(f"  dry-run: {args.dry_run} | limit: {args.limit} | tier: {args.tier}")
    logger.info(f"  resume: {args.resume} | phase: {args.phase or 'ALL'}")

    # Verify Ollama is reachable
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
        logger.info(f"  Ollama: OK ({OLLAMA_URL})")
    except Exception:
        logger.error(f"  Ollama not reachable at {OLLAMA_URL} — is it running?")
        sys.exit(1)

    # Verify Qdrant is reachable
    try:
        req = urllib.request.Request(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
        logger.info(f"  Qdrant: OK ({QDRANT_URL}/{QDRANT_COLLECTION})")
    except Exception:
        logger.warning(f"  Qdrant not reachable at {QDRANT_URL} — Qdrant upsert will be skipped")

    # Load source data
    all_codes, source_lookup = load_source_data()
    logger.info(f"  Source data: {len(all_codes)} KBLI 2025 codes")

    # Handle --resume: load existing checkpoint and skip processed codes
    if args.resume:
        state = load_checkpoint()
        processed_codes = {k for k, v in state["processed"].items() if v.get("generated")}
        logger.info(f"  Resuming: {len(processed_codes)} already generated in checkpoint")
        all_codes = [c for c in all_codes if c["kode_kbli_2025"] not in processed_codes]

    run_pipeline(args, all_codes, source_lookup)


if __name__ == "__main__":
    main()
