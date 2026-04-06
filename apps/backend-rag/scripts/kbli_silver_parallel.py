#!/usr/bin/env python3
"""
KBLI Silver Tier — Parallel 3-Worker Generator
================================================
Splits 830 silver codes into 3 slices, runs Gemini 3.1 Pro Preview CLI
in parallel (3 subprocesses), merges results into kbli-gold-all.json.

Fallback chain per batch: Gemini CLI → Ollama gemma4:26b

Usage:
  python scripts/kbli_silver_parallel.py                    # full run
  python scripts/kbli_silver_parallel.py --dry-run          # show plan only
  python scripts/kbli_silver_parallel.py --workers 2        # 2 workers
  python scripts/kbli_silver_parallel.py --resume           # skip already enriched

Zero API cost — uses CLI subscriptions only.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent
BACKEND_RAG = SCRIPT_DIR.parent

DATA_JSON = REPO_ROOT / "apps" / "kbli-navigator" / "data" / "kbli-2025.json"
GOLD_JSON = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"
CHECKPOINT_FILE = SCRIPT_DIR / "output" / "kbli_enrichment_state.json"
SILVER_OUTPUT_DIR = SCRIPT_DIR / "output" / "silver_workers"
OUTPUT_DIR = SCRIPT_DIR / "output"

OLLAMA_URL = "http://localhost:11434"
MODEL_FALLBACK = "gemma4:26b"

GEMINI_CLI = "gemini"
GEMINI_MODEL = "gemini-3.1-pro-preview"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [W%(process)d] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts (same as main pipeline — high quality for silver)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_SILVER = """You are an expert on Indonesian business law writing precise, useful content for foreign investors in Bali.

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
   - Start with Bali context (e.g. "Setting up a X in Bali?")
   - Be specific to the business activity

Respond ONLY with valid JSON:
{"results": [{"code": "XXXXX", "whatItMeans": "...", "baliContext": "...", "zantaraOpener": "..."}]}
No extra text, no markdown fences."""

# ---------------------------------------------------------------------------
# Static maps (from main pipeline)
# ---------------------------------------------------------------------------
RISK_MAP = {
    "Rendah": ("Low risk", "NIB only — issued automatically."),
    "Menengah Rendah": ("Medium-Low risk", "NIB + Standard Certificate — issued automatically."),
    "Menengah Tinggi": ("Medium-High risk", "NIB + Standard Certificate — issued within 7 working days."),
    "Tinggi": ("High risk", "NIB + Business License (Izin) — full review required."),
}

SCALE_MAP = {"Mikro": "Micro", "Kecil": "Small", "Menengah": "Medium", "Besar": "Large"}

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


# ---------------------------------------------------------------------------
# Deterministic field builders
# ---------------------------------------------------------------------------

def _translate_kewajiban(raw: str) -> str:
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
    steps.append(f"{step_n}. **PT PMA incorporation** — notary deed, AHU registration, TDP (~2-4 weeks)")
    step_n += 1
    steps.append(f"{step_n}. **NIB via OSS** — register on oss.go.id, select this code, issued automatically (1-3 days)")
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


def build_full_entry(code: dict, narrative: dict) -> dict:
    return {
        "whatItMeans": narrative.get("whatItMeans", ""),
        "whatYouNeed": build_what_you_need(code),
        "whatChanged": build_what_changed(code),
        "baliContext": narrative.get("baliContext", ""),
        "youllAlsoNeed": build_youll_also_need(code),
        "zantaraOpener": narrative.get("zantaraOpener", ""),
    }


# ---------------------------------------------------------------------------
# LLM callers
# ---------------------------------------------------------------------------

def call_gemini_cli(system: str, user_prompt: str, timeout: int = 120) -> str:
    full_prompt = f"{system}\n\n---\n\n{user_prompt}"
    result = subprocess.run(
        [GEMINI_CLI, "--model", GEMINI_MODEL, "--prompt", full_prompt],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Gemini CLI error (rc={result.returncode}): {result.stderr[:300]}")
    lines = result.stdout.splitlines()
    clean = "\n".join(
        line for line in lines
        if not line.startswith("Keychain") and not line.startswith("Using") and
           not line.startswith("Loaded") and not line.startswith("Server") and
           not line.startswith("Scheduling") and not line.startswith("Executing") and
           not line.startswith("MCP")
    ).strip()
    return clean


def call_ollama(model: str, system: str, user_prompt: str, timeout: int = 300) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 8192},
    }
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
    text = raw
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
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
# Worker function (runs in subprocess)
# ---------------------------------------------------------------------------

def worker_generate(
    worker_id: int,
    codes_slice: list[dict],
    batch_size: int = 5,
) -> dict[str, dict]:
    """
    Generate silver content for a slice of codes.
    Gemini CLI primary → Ollama gemma4:26b fallback.
    Returns {code: {whatItMeans, baliContext, zantaraOpener, ...full entry}}.
    """
    results: dict[str, dict] = {}
    total = len(codes_slice)
    n_batches = (total + batch_size - 1) // batch_size

    # Per-worker output file for crash recovery
    worker_file = SILVER_OUTPUT_DIR / f"worker_{worker_id}.json"
    if worker_file.exists():
        with open(worker_file) as f:
            results = json.load(f)
        logger.info(f"Worker {worker_id}: resumed {len(results)} from checkpoint")

    for i in range(0, total, batch_size):
        batch = codes_slice[i : i + batch_size]

        # Skip already done
        batch_codes = [c["kode_kbli_2025"] for c in batch]
        if all(c in results for c in batch_codes):
            logger.info(f"W{worker_id} batch {i // batch_size + 1}/{n_batches}: skip (all done)")
            continue

        user_prompt = "\n\n".join(
            f"code: {c['kode_kbli_2025']}\n"
            f"judul: {c['judul']}\n"
            f"uraian: {c.get('uraian', '')[:500]}\n"
            f"pma_status: {c.get('pma_status', 'TERBUKA')} ({c.get('pma_max_asing', 100)}%)\n"
            f"sektor_id: {c.get('sektor_id', 'N/A')}"
            for c in batch
        )

        logger.info(f"W{worker_id} batch {i // batch_size + 1}/{n_batches}: {batch_codes}")

        # Try Gemini CLI
        parsed = []
        provider = "none"
        try:
            raw = call_gemini_cli(SYSTEM_PROMPT_SILVER, user_prompt, timeout=120)
            parsed = parse_llm_json(raw)
            provider = "gemini"
            logger.info(f"  W{worker_id} -> Gemini OK ({len(parsed)} results)")
        except Exception as e:
            logger.warning(f"  W{worker_id} -> Gemini failed: {e}")
            # Fallback: Ollama
            try:
                raw = call_ollama(MODEL_FALLBACK, SYSTEM_PROMPT_SILVER, user_prompt, timeout=360)
                parsed = parse_llm_json(raw)
                provider = "ollama"
                logger.info(f"  W{worker_id} -> Ollama OK ({len(parsed)} results)")
            except Exception as e2:
                logger.error(f"  W{worker_id} -> BOTH FAILED: {e2}")

        # Build full entries
        for item in parsed:
            kode = item.get("code", "")
            if not kode:
                continue
            code_obj = next((c for c in batch if c["kode_kbli_2025"] == kode), None)
            if not code_obj:
                continue
            narrative = {
                "whatItMeans": item.get("whatItMeans", ""),
                "baliContext": item.get("baliContext", ""),
                "zantaraOpener": item.get("zantaraOpener", ""),
            }
            results[kode] = build_full_entry(code_obj, narrative)
            results[kode]["_provider"] = provider

        # Save worker checkpoint after each batch
        SILVER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(worker_file, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        # Gentle delay between batches to avoid rate limits
        time.sleep(2)

    logger.info(f"Worker {worker_id}: DONE — {len(results)}/{total} codes")
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="KBLI Silver Tier — Parallel Generator")
    parser.add_argument("--workers", type=int, default=3, help="Number of parallel workers (default: 3)")
    parser.add_argument("--batch-size", type=int, default=5, help="Codes per LLM call (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Show plan only, no generation")
    parser.add_argument("--resume", action="store_true", help="Skip codes already in kbli-gold-all.json")
    parser.add_argument("--limit", type=int, default=0, help="Max codes to process (0 = all)")
    args = parser.parse_args()

    logger.info("KBLI Silver Tier — Parallel Generator")
    logger.info(f"  workers: {args.workers} | batch: {args.batch_size} | dry-run: {args.dry_run}")

    # Load source data
    with open(DATA_JSON) as f:
        data = json.load(f)
    all_codes = data["data"]
    source_lookup = {c["kode_kbli_2025"]: c for c in all_codes}
    logger.info(f"  Source: {len(all_codes)} KBLI codes")

    # Load checkpoint to get silver tier codes
    if not CHECKPOINT_FILE.exists():
        logger.error(f"No checkpoint at {CHECKPOINT_FILE} — run main pipeline --tier silver first to classify")
        sys.exit(1)

    with open(CHECKPOINT_FILE) as f:
        state = json.load(f)

    silver_codes_list = [
        kode for kode, info in state.get("processed", {}).items()
        if isinstance(info, dict) and info.get("tier") == "silver"
    ]
    logger.info(f"  Silver codes in checkpoint: {len(silver_codes_list)}")

    # Filter out already enriched if --resume
    if args.resume:
        existing: dict = {}
        if GOLD_JSON.exists():
            with open(GOLD_JSON) as f:
                existing = json.load(f)
        before = len(silver_codes_list)
        silver_codes_list = [
            k for k in silver_codes_list
            if k not in existing or len(existing.get(k, {}).get("whatItMeans", "")) < 50
        ]
        logger.info(f"  Resume: {before} -> {len(silver_codes_list)} (skipped {before - len(silver_codes_list)} already enriched)")

    # Also check worker checkpoints for already-done codes
    SILVER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    already_done: set[str] = set()
    for wf in SILVER_OUTPUT_DIR.glob("worker_*.json"):
        with open(wf) as f:
            done = json.load(f)
        already_done.update(done.keys())
    if already_done:
        before = len(silver_codes_list)
        silver_codes_list = [k for k in silver_codes_list if k not in already_done]
        logger.info(f"  Worker checkpoints: skipped {before - len(silver_codes_list)} already done")

    # Resolve to full code objects
    silver_codes = [source_lookup[k] for k in silver_codes_list if k in source_lookup]

    if args.limit > 0:
        silver_codes = silver_codes[:args.limit]

    logger.info(f"  Codes to generate: {len(silver_codes)}")

    if not silver_codes:
        logger.info("Nothing to do!")
        # Merge existing worker outputs
        _merge_and_upsert(args.dry_run)
        return

    if args.dry_run:
        logger.info("DRY RUN — plan:")
        n_workers = min(args.workers, len(silver_codes))
        slice_size = (len(silver_codes) + n_workers - 1) // n_workers
        for w in range(n_workers):
            start = w * slice_size
            end = min(start + slice_size, len(silver_codes))
            codes_in_slice = silver_codes[start:end]
            n_batches = (len(codes_in_slice) + args.batch_size - 1) // args.batch_size
            est_time = n_batches * 50  # ~50s per batch including overhead
            logger.info(f"  Worker {w}: {len(codes_in_slice)} codes, ~{n_batches} batches, ~{est_time // 60}min")
        logger.info(f"  Estimated total: ~{(slice_size // args.batch_size * 50) // 60}min parallel")
        return

    # Split into slices
    n_workers = min(args.workers, len(silver_codes))
    slice_size = (len(silver_codes) + n_workers - 1) // n_workers
    slices = []
    for w in range(n_workers):
        start = w * slice_size
        end = min(start + slice_size, len(silver_codes))
        slices.append(silver_codes[start:end])

    logger.info(f"  Launching {n_workers} workers: {[len(s) for s in slices]} codes each")
    logger.info("=" * 60)

    t0 = time.time()

    # Launch parallel workers
    all_results: dict[str, dict] = {}
    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = {
            executor.submit(worker_generate, w, slices[w], args.batch_size): w
            for w in range(n_workers)
        }
        for future in as_completed(futures):
            worker_id = futures[future]
            try:
                worker_results = future.result()
                all_results.update(worker_results)
                logger.info(f"Worker {worker_id} returned {len(worker_results)} entries")
            except Exception as e:
                logger.error(f"Worker {worker_id} CRASHED: {e}")

    elapsed = time.time() - t0
    logger.info("=" * 60)
    logger.info(f"Generation complete: {len(all_results)} entries in {elapsed:.0f}s ({elapsed / 60:.1f}min)")

    # Merge and write
    _merge_and_upsert(dry_run=False)


def _merge_and_upsert(dry_run: bool = False) -> None:
    """Merge all worker outputs into kbli-gold-all.json."""
    SILVER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_results: dict[str, dict] = {}
    for wf in sorted(SILVER_OUTPUT_DIR.glob("worker_*.json")):
        with open(wf) as f:
            data = json.load(f)
        all_results.update(data)
        logger.info(f"  Loaded {len(data)} entries from {wf.name}")

    if not all_results:
        logger.info("  No worker outputs to merge.")
        return

    # Strip internal metadata
    for kode in all_results:
        all_results[kode].pop("_provider", None)

    # Count providers
    logger.info(f"  Total silver entries to merge: {len(all_results)}")

    if dry_run:
        logger.info("  DRY RUN — would merge into kbli-gold-all.json")
        return

    # Load existing
    existing: dict = {}
    if GOLD_JSON.exists():
        with open(GOLD_JSON) as f:
            existing = json.load(f)

    before = len(existing)
    for kode, content in all_results.items():
        tka_info = existing.get(kode, {}).get("tkaInfo")
        if kode in existing:
            existing[kode].update(content)
        else:
            existing[kode] = content
        if tka_info:
            existing[kode]["tkaInfo"] = tka_info

    with open(GOLD_JSON, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False, sort_keys=True)

    logger.info(f"  Merged: {before} -> {len(existing)} entries in kbli-gold-all.json (+{len(existing) - before} new)")


if __name__ == "__main__":
    main()
