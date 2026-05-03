"""ARCH-5 Layer A+B: Source Gap Detection & Coverage Matrix.

Layer A — Essential Questions (daily 05:30 WITA):
    Queries each notebook: "Quali sono le 5 domande più importanti su [dominio]
    a cui NON puoi rispondere?" → extracts gap topics → updates coverage_matrix.json.

Layer B — Coverage Matrix (weekly Sunday 03:00 WITA):
    For each notebook and topic checklist, queries freshness of key regulatory
    areas. Classifies: FRESH (<30d) / AGING (30-90d) / STALE (>90d) / GAP (no answer).
    Persists to coverage_matrix.json. Sends Telegram digest.

Usage:
    python -m apps.evaluator.nlm_deep_research.gap_scanner --layer-a
    python -m apps.evaluator.nlm_deep_research.gap_scanner --layer-b
    python -m apps.evaluator.nlm_deep_research.gap_scanner --layer-a --dry-run
    python -m apps.evaluator.nlm_deep_research.gap_scanner --status
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

_DIR = Path(__file__).parent
COVERAGE_MATRIX_FILE = _DIR / "coverage_matrix.json"
GAP_STATE_FILE = _DIR / "gap_scanner_state.json"

# ── Config ────────────────────────────────────────────────────────────────────

_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "")

NLM_QUERY_TIMEOUT = 120
LAYER_B_QUERY_TIMEOUT = 180  # PR-D1 (2026-04-30): NLM bridge slow under load — was 90s
GAP_QUERY_DELAY = 5  # seconds between queries — NLM rate limiting

# Freshness thresholds (days)
FRESH_DAYS = 30
AGING_DAYS = 90

# Per-domain topic checklists for Layer B coverage matrix
DOMAIN_TOPICS: dict[str, dict[str, list[str]]] = {
    "immigration": {
        "notebook_id": "cff93ab0-813a-42f2-a8de-36987e724271",
        "label": "Immigration & Visa",
        "topics": [
            "KITAS requirements and process 2025",
            "KITAP eligibility and conversion from KITAS",
            "B211A visa digital nomad Indonesia",
            "TKA (foreign worker permit) requirements",
            "KITAS renewal procedure and timeline",
            "Spouse/dependent KITAS (KITAS ikut suami/istri)",
            "Immigration fines and overstay penalties",
            "E-visa online application process",
        ],
    },
    "company": {
        "notebook_id": "933509f9-1561-403d-bd44-4a7a67a36df2",
        "label": "Company Setup & KBLI",
        "topics": [
            "PT PMA setup requirements 2025",
            "OSS-RBA online registration process",
            "NIB (Nomor Induk Berusaha) registration",
            "Daftar Negatif Investasi foreign ownership limits",
            "PT PMA minimum capital requirements",
            "Notaris process for PT establishment",
            "KBLI 2020 classification system",
            "Representative Office vs PT PMA",
        ],
    },
    "tax": {
        "notebook_id": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",
        "label": "Tax & Fiscal",
        "topics": [
            "PPh 21 rates and calculation for expats",
            "PPN (VAT) 11% registration and reporting",
            "CoreTax system migration 2025",
            "PPh 25 quarterly installment for PT PMA",
            "LKPM reporting requirements BKPM",
            "Transfer pricing documentation",
            "SPT Tahunan Badan filing deadline",
            "NPWP registration for foreigners",
        ],
    },
    "property": {
        "notebook_id": "d9438180-5e63-4e2a-a473-6061101f6a8d",
        "label": "Property & Real Estate",
        "topics": [
            "HGB title for foreigners in Indonesia",
            "Hak Pakai for foreign nationals",
            "Leasehold property structures Bali",
            "RTRW zoning regulations Bali 2024",
            "BPHTB property transfer tax",
            "KPR mortgage for foreigners Indonesia",
            "Nominee structure legality Indonesia",
            "AJB process and notaris requirements",
        ],
    },
    "operations": {
        "notebook_id": "85207af3-352f-4554-8d2a-18f42cc541ba",
        "label": "Operations & Compliance",
        "topics": [
            "UMR/UMK Bali minimum wage 2025",
            "BPJS Ketenagakerjaan rates 2025",
            "BPJS Kesehatan contribution rates",
            "PKWT vs PKWTT contract types",
            "UU Cipta Kerja employment law changes",
            "UU PDP data protection compliance",
            "TDUP license for tourism businesses",
            "Anti-money laundering PPATK obligations",
        ],
    },
    "editorial": {
        "notebook_id": "f51ab8a0-50d0-49f1-a64f-ebc131fed7b8",
        "label": "Editorial & Content",
        "topics": [
            "Google Helpful Content Update 2024",
            "E-E-A-T for legal and financial content",
            "YMYL content best practices",
            "Indonesia expat search intent analysis",
            "Core Web Vitals ranking factors",
            "Long-form guide structure for immigration topics",
            "Content gap analysis vs competitors",
            "AI content detection and avoidance",
        ],
    },
    "lifestyle": {
        "notebook_id": "4fd8cd0f-93f1-4e43-9c9e-86c0d581852c",
        "label": "Expat Life & Bali",
        "topics": [
            "International health insurance Bali 2025",
            "BIMC Siloam hospital services",
            "International schools Bali fees 2025",
            "Cost of living Canggu Seminyak 2025",
            "Opening bank account as foreigner Indonesia",
            "Driving license for foreigners in Bali",
            "Internet and phone plans Bali",
            "Pet import regulations Indonesia",
        ],
    },
}

# Layer A gap query template
GAP_QUERY_TEMPLATE = (
    "Quali sono le 5 domande più importanti su {domain_label} "
    "a cui NON riesci a rispondere basandoti sulle tue fonti attuali? "
    "Elenca solo le domande, una per riga, senza numeri o bullet points."
)

# Layer B freshness query template
FRESHNESS_QUERY_TEMPLATE = (
    "Qual è il regolamento o la procedura più recente riguardo a: {topic}? "
    "Indica l'anno o la data dell'informazione più aggiornata che hai nelle fonti. "
    "Se non hai informazioni su questo argomento, rispondi SOLO con la parola: GAP"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _query_notebook(notebook_id: str, query: str, timeout: int = NLM_QUERY_TIMEOUT) -> str | None:
    if not notebook_id:
        return None
    try:
        result = subprocess.run(
            ["nlm", "query", "notebook", notebook_id, query],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.error("nlm query failed for %s: %s", notebook_id, result.stderr.strip()[:200])
            return None
        return result.stdout.strip() or None
    except subprocess.TimeoutExpired:
        logger.warning("Query timeout for notebook %s", notebook_id)
        return None
    except Exception as exc:
        logger.error("Query error: %s", exc)
        return None


def _extract_gap_topics(response: str) -> list[str]:
    """Extract gap topic questions from NLM response.

    The NLM CLI sometimes returns a JSON envelope
    (``{"answer": "...", "conversation_id": "...", "sources_used": [], ...}``)
    instead of the bare model output. The older implementation split the
    whole response by newlines, so envelope keys like ``"conversation_id": ...``
    ended up in ``coverage_matrix.json`` as fake gap topics (35 corrupted
    entries observed in the 2026-04-03 run — see wave 1 triage report).

    Guard: if the response parses as JSON and contains an ``answer`` field,
    use that field as the text to split on. Otherwise fall back to the
    previous behaviour. Defensive filter also drops obvious JSON-key lines
    (``"foo": ...``, ``"foo":``) in case the CLI emits half-valid output.
    """
    if not response:
        return []

    text = response.strip()
    if text.startswith("{"):
        try:
            obj = json.loads(text)
            # Two known envelope shapes exist in the wild:
            #   {"answer": "...", "conversation_id": "...", ...}         (flat)
            #   {"value": {"answer": "...", "conversation_id": "..."}}   (wrapped)
            # The live `nlm query notebook` CLI as of 2026-04-22 emits the
            # wrapped variant; older mocks used the flat one. Support both.
            if isinstance(obj, dict):
                inner = obj.get("value") if isinstance(obj.get("value"), dict) else obj
                if isinstance(inner, dict) and isinstance(inner.get("answer"), str):
                    text = inner["answer"].strip()
        except (json.JSONDecodeError, ValueError):
            # Not a well-formed envelope — keep the raw text and rely on the
            # line-level filter below to drop leaking keys.
            pass

    lines = text.split("\n")
    gaps: list[str] = []
    for line in lines:
        clean = line.strip().lstrip("0123456789.-) *#").strip()
        if len(clean) <= 15:
            continue
        # Drop obvious JSON key-value leakage. Keys always start with a
        # double-quoted identifier immediately followed by ``:``. This is
        # cheap and catches the corruption even when json.loads bails.
        stripped = clean.rstrip(",").strip()
        if stripped.startswith('"') and '":' in stripped[:60]:
            # Only reject if the line looks like a bare JSON k/v — natural
            # prose containing a quoted phrase followed by a colon (rare) is
            # far less likely to start with a literal double-quote AND have
            # the colon within the first 60 chars.
            continue
        if "?" in clean:
            gaps.append(clean[:200])
        else:
            gaps.append(clean[:200])
    return gaps[:8]  # At most 8 gap topics


def _classify_freshness(response: str) -> str:
    """Classify response freshness: FRESH / AGING / STALE / GAP."""
    if not response:
        return "GAP"
    resp_upper = response.upper()
    if resp_upper.strip() == "GAP" or resp_upper.startswith("GAP"):
        return "GAP"
    if "NON HO" in resp_upper or "NON TROVO" in resp_upper or "NON DISPONIBILE" in resp_upper:
        return "GAP"

    now = datetime.now(timezone.utc)
    # Look for year references
    current_year = now.year
    years_found = []
    import re
    for y in re.findall(r'\b(20\d{2})\b', response):
        years_found.append(int(y))

    if not years_found:
        return "STALE"

    latest_year = max(years_found)
    age_years = current_year - latest_year

    if age_years == 0:
        return "FRESH"
    elif age_years == 1:
        # Check if mentions recent months
        recent_months = ["jan", "feb", "mar", "apr", "may", "jun",
                         "jul", "aug", "sep", "oct", "nov", "dec",
                         "jan", "feb", "mar", "apr", "mei", "jun",
                         "jul", "agu", "sep", "okt", "nov", "des"]
        resp_lower = response.lower()
        if any(m in resp_lower for m in recent_months):
            return "AGING"
        return "AGING"
    else:
        return "STALE"


def _send_telegram(msg: str) -> None:
    if not _BOT_TOKEN or not _CHAT_ID:
        return
    try:
        data = json.dumps({
            "chat_id": _CHAT_ID,
            "text": msg[:4096],
            "parse_mode": "HTML",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── State management ──────────────────────────────────────────────────────────

def _load_matrix() -> dict[str, Any]:
    if COVERAGE_MATRIX_FILE.exists():
        try:
            return json.loads(COVERAGE_MATRIX_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_matrix(matrix: dict[str, Any]) -> None:
    COVERAGE_MATRIX_FILE.write_text(json.dumps(matrix, indent=2, default=str))


def _load_gap_state() -> dict[str, Any]:
    if GAP_STATE_FILE.exists():
        try:
            return json.loads(GAP_STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_layer_a": None, "last_layer_b": None, "layer_a_runs": 0, "layer_b_runs": 0}


def _save_gap_state(state: dict[str, Any]) -> None:
    GAP_STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


# ── Layer A: Essential Questions (Gap Discovery) ───────────────────────────────

def run_layer_a(dry_run: bool = False) -> dict[str, Any]:
    """Layer A: Query each notebook for unanswerable questions → gap topics.

    Results stored in coverage_matrix.json under each domain's 'gaps' key.
    """
    result: dict[str, Any] = {
        "status": "ok",
        "domains_scanned": 0,
        "total_gaps": 0,
        "dry_run": dry_run,
        "errors": [],
    }

    matrix = _load_matrix()
    state = _load_gap_state()

    for domain, config in DOMAIN_TOPICS.items():
        nb_id = config["notebook_id"]
        label = config["label"]
        logger.info("Layer A — scanning gaps for %s (%s)", domain, nb_id[:8])

        if not dry_run:
            query = GAP_QUERY_TEMPLATE.format(domain_label=label)
            response = _query_notebook(nb_id, query)

            if response:
                gaps = _extract_gap_topics(response)
                logger.info("  Found %d gap topics for %s", len(gaps), domain)

                if domain not in matrix:
                    matrix[domain] = {}
                matrix[domain]["gaps"] = gaps
                matrix[domain]["gaps_updated"] = _now_iso()
                matrix[domain]["label"] = label
                result["total_gaps"] += len(gaps)
            else:
                logger.warning("  No response from %s", domain)
                result["errors"].append(f"{domain}: no response")

            result["domains_scanned"] += 1
            time.sleep(GAP_QUERY_DELAY)
        else:
            logger.info("  DRY RUN: would query %s for gaps", domain)
            result["domains_scanned"] += 1

    if not dry_run:
        _save_matrix(matrix)
        state["last_layer_a"] = _now_iso()
        state["layer_a_runs"] = state.get("layer_a_runs", 0) + 1
        _save_gap_state(state)

        # Telegram summary
        if result["total_gaps"] > 0:
            _send_telegram(
                f"📋 <b>Gap Scanner — Layer A</b>\n"
                f"Scansionati {result['domains_scanned']} notebook\n"
                f"Trovati {result['total_gaps']} gap topics\n"
                f"Report completo in coverage_matrix.json"
            )

    if result["errors"]:
        result["status"] = "partial"

    return result


# ── Layer B: Coverage Matrix (Freshness Assessment) ───────────────────────────

def run_layer_b(dry_run: bool = False) -> dict[str, Any]:
    """Layer B: Test freshness of each topic checklist per domain.

    Classifies each topic as FRESH/AGING/STALE/GAP.
    Results stored in coverage_matrix.json under each domain's 'topics' key.
    """
    result: dict[str, Any] = {
        "status": "ok",
        "domains_scanned": 0,
        "total_topics": 0,
        "fresh": 0,
        "aging": 0,
        "stale": 0,
        "gap": 0,
        "dry_run": dry_run,
        "errors": [],
    }

    matrix = _load_matrix()
    state = _load_gap_state()

    # Count query infrastructure failures separately so a total CLI
    # outage (e.g. `nlm` not in PATH) doesn't masquerade as a normal
    # 100% GAP result — which would leave heartbeat green and Zero
    # unaware. See scar: 2026-04-19 Layer B run silently reported "ok"
    # while 56/56 queries failed with Errno 2: 'nlm'.
    total_queries_attempted = 0
    total_queries_failed = 0

    for domain, config in DOMAIN_TOPICS.items():
        nb_id = config["notebook_id"]
        label = config["label"]
        topics = config["topics"]
        logger.info("Layer B — coverage matrix for %s (%d topics)", domain, len(topics))

        domain_results: dict[str, str] = {}

        for topic_idx, topic in enumerate(topics, 1):
            result["total_topics"] += 1

            if not dry_run:
                total_queries_attempted += 1
                query = FRESHNESS_QUERY_TEMPLATE.format(topic=topic)
                response = _query_notebook(nb_id, query, timeout=LAYER_B_QUERY_TIMEOUT)
                if response is None:
                    total_queries_failed += 1
                classification = _classify_freshness(response)
            else:
                classification = "FRESH"  # dry run stub

            domain_results[topic] = classification
            result[classification.lower()] += 1
            # PR-D1 (2026-04-30): per-topic progress so a kill mid-domain
            # leaves a breadcrumb in the log instead of silent gap.
            logger.info(
                "  [%s %d/%d] %s — %s",
                domain, topic_idx, len(topics), topic[:60], classification,
            )

            if not dry_run:
                time.sleep(GAP_QUERY_DELAY)

        if domain not in matrix:
            matrix[domain] = {}
        matrix[domain]["coverage"] = domain_results
        matrix[domain]["coverage_updated"] = _now_iso()
        matrix[domain]["label"] = config["label"]

        # Compute domain health score
        total = len(domain_results)
        if total > 0:
            fresh_pct = sum(1 for v in domain_results.values() if v == "FRESH") / total * 100
            gap_pct = sum(1 for v in domain_results.values() if v == "GAP") / total * 100
            matrix[domain]["health_pct"] = round(fresh_pct, 1)
            matrix[domain]["gap_pct"] = round(gap_pct, 1)
            logger.info("  %s: %.0f%% fresh, %.0f%% gap", domain, fresh_pct, gap_pct)

        result["domains_scanned"] += 1

    if not dry_run:
        _save_matrix(matrix)
        state["last_layer_b"] = _now_iso()
        state["layer_b_runs"] = state.get("layer_b_runs", 0) + 1
        _save_gap_state(state)

        # Build Telegram coverage report
        msg_lines = ["📊 <b>Coverage Matrix — Layer B</b>\n"]
        for domain, data in matrix.items():
            coverage = data.get("coverage", {})
            if not coverage:
                continue
            total = len(coverage)
            fresh = sum(1 for v in coverage.values() if v == "FRESH")
            aging = sum(1 for v in coverage.values() if v == "AGING")
            stale = sum(1 for v in coverage.values() if v == "STALE")
            gap = sum(1 for v in coverage.values() if v == "GAP")
            health = data.get("health_pct", 0)
            icon = "🟢" if health >= 70 else ("🟡" if health >= 40 else "🔴")
            msg_lines.append(
                f"{icon} <b>{data.get('label', domain)}</b>: "
                f"{fresh}✓ {aging}⏱ {stale}⚠️ {gap}❌ ({total} topics, {health:.0f}% fresh)"
            )

        stale_total = result["stale"] + result["gap"]
        if stale_total > 0:
            msg_lines.append(f"\n⚠️ {stale_total} topics stale/missing — freshness_monitor will trigger remediation")

        _send_telegram("\n".join(msg_lines))

    if result["errors"]:
        result["status"] = "partial"

    # Infrastructure-failure guard: if we attempted queries but every
    # single one failed, treat the whole run as failed so the bash
    # wrapper does NOT register a heartbeat and the cron alert fires.
    # A single successful query in the batch is enough to keep the run
    # alive — the legitimate per-topic GAPs will still show up in
    # coverage_matrix as GAP classifications.
    if (
        not dry_run
        and total_queries_attempted > 0
        and total_queries_failed == total_queries_attempted
    ):
        result["status"] = "failed"
        result["errors"].append(
            f"all {total_queries_failed}/{total_queries_attempted} NLM queries "
            f"failed — check that the `nlm` CLI is on PATH and OAuth token "
            f"is valid; heartbeat NOT recorded to avoid falso-OK "
            f"(cicatrix 2026-04-19)."
        )
        logger.error(
            "Layer B: infrastructure failure — %d/%d queries failed",
            total_queries_failed,
            total_queries_attempted,
        )

    return result


# ── Layer C: Gap Remediation Loop ────────────────────────────────────────────

# Max remediation targets per run (NLM rate limiting)
MAX_REMEDIATIONS_PER_RUN = 3

# Gemini search timeout
GEMINI_TIMEOUT = 120

# Delay between NLM source_add calls
REMEDIATION_DELAY = 15  # seconds


def _run_gemini_search(query: str) -> str | None:
    """Use Gemini CLI (built-in web search) to find content for a gap topic."""
    prompt = (
        f"Search the web for: {query}\n\n"
        "Provide a comprehensive 300-500 word summary of the most recent and authoritative "
        "information found. Include dates, regulation numbers, and official sources. "
        "Write in English. If you find nothing relevant, respond ONLY with: NO_RESULT"
    )
    try:
        result = subprocess.run(
            ["gemini", "-p", prompt, "--model", "gemini-3-flash-preview"],
            capture_output=True, text=True, timeout=GEMINI_TIMEOUT,
        )
        if result.returncode != 0:
            logger.warning("Gemini CLI error: %s", result.stderr.strip()[:200])
            return None
        output = result.stdout.strip()
        if not output or "NO_RESULT" in output.upper():
            return None
        return output
    except subprocess.TimeoutExpired:
        logger.warning("Gemini search timeout for: %s", query[:60])
        return None
    except FileNotFoundError:
        logger.error("gemini CLI not found in PATH")
        return None
    except Exception as exc:
        logger.error("Gemini search error: %s", exc)
        return None


def _add_source_to_notebook(notebook_id: str, title: str, content: str, timeout: int = 60) -> bool:
    """Add a text source to a NLM notebook via nlm CLI."""
    try:
        result = subprocess.run(
            ["nlm", "source", "add", notebook_id, "--text", content, "--title", title],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.error("nlm source add failed for %s: %s", notebook_id[:8], result.stderr.strip()[:200])
            return False
        logger.info("Added source '%s' to notebook %s", title[:50], notebook_id[:8])
        return True
    except subprocess.TimeoutExpired:
        logger.warning("nlm source add timeout for notebook %s", notebook_id[:8])
        return False
    except Exception as exc:
        logger.error("Source add error: %s", exc)
        return False


def run_remediation(dry_run: bool = False) -> dict[str, Any]:
    """Gap Remediation Loop: find GAP/STALE topics → Gemini search → nlm source add.

    This is the 'close the loop' step that was missing from the original ARCH-5.
    Instead of only detecting gaps, it actively fills them:
    1. Read coverage_matrix.json for GAP and STALE topics
    2. For each topic (up to MAX_REMEDIATIONS_PER_RUN): search via Gemini CLI
    3. Add the result as a new source directly to the notebook

    Priority: GAP topics first, then STALE.
    """
    result: dict[str, Any] = {
        "status": "ok",
        "gap_topics_found": 0,
        "stale_topics_found": 0,
        "sources_added": 0,
        "search_failed": 0,
        "dry_run": dry_run,
        "errors": [],
        "remediated": [],
    }

    if not COVERAGE_MATRIX_FILE.exists():
        logger.warning("coverage_matrix.json not found — run --layer-b first")
        result["status"] = "skipped"
        return result

    matrix = _load_matrix()

    # Collect targets sorted by priority: GAP first, then STALE
    targets: list[tuple[str, str, str, str]] = []  # (priority, domain, topic, nb_id)
    for domain, data in matrix.items():
        coverage = data.get("coverage", {})
        nb_id = DOMAIN_TOPICS.get(domain, {}).get("notebook_id", "")
        if not nb_id:
            continue
        for topic, classification in coverage.items():
            if classification == "GAP":
                result["gap_topics_found"] += 1
                targets.append(("1_gap", domain, topic, nb_id))
            elif classification == "STALE":
                result["stale_topics_found"] += 1
                targets.append(("2_stale", domain, topic, nb_id))

    targets.sort(key=lambda x: x[0])
    to_process = targets[:MAX_REMEDIATIONS_PER_RUN]

    logger.info(
        "Remediation: %d GAP + %d STALE topics found. Processing %d.",
        result["gap_topics_found"], result["stale_topics_found"], len(to_process),
    )

    for priority, domain, topic, nb_id in to_process:
        search_query = f"{topic} Indonesia 2025 2026 latest regulations official"
        label = DOMAIN_TOPICS.get(domain, {}).get("label", domain)
        logger.info("[%s] Remediating: %s — %s", priority.split("_")[1].upper(), label, topic[:60])

        if dry_run:
            logger.info("  DRY RUN: would search '%s' → add to %s", topic[:60], nb_id[:8])
            result["sources_added"] += 1
            result["remediated"].append({"domain": domain, "topic": topic, "status": "dry_run"})
            continue

        content = _run_gemini_search(search_query)
        if not content:
            logger.warning("  No content found for: %s", topic[:60])
            result["search_failed"] += 1
            result["errors"].append(f"{domain}/{topic[:40]}: no search result")
            continue

        # Title includes domain label and topic for easy identification
        source_title = f"[{label}] {topic[:80]} — {_now_iso()[:10]}"
        added = _add_source_to_notebook(nb_id, source_title, content)

        if added:
            result["sources_added"] += 1
            result["remediated"].append({
                "domain": domain,
                "topic": topic,
                "status": "added",
                "title": source_title,
            })
            # Update matrix: mark as FRESH since we just added content
            if domain in matrix and "coverage" in matrix[domain]:
                matrix[domain]["coverage"][topic] = "FRESH"
                matrix[domain]["coverage_updated"] = _now_iso()
            time.sleep(REMEDIATION_DELAY)
        else:
            result["errors"].append(f"{domain}/{topic[:40]}: source add failed")

    # Save updated matrix
    if not dry_run and result["sources_added"] > 0:
        _save_matrix(matrix)

        msg_lines = ["🔧 <b>Gap Remediation Loop</b>"]
        msg_lines.append(f"GAP trovati: {result['gap_topics_found']} | STALE: {result['stale_topics_found']}")
        msg_lines.append(f"✅ Fonti aggiunte: {result['sources_added']}")
        if result["search_failed"] > 0:
            msg_lines.append(f"⚠️ Ricerche fallite: {result['search_failed']}")
        for item in result["remediated"]:
            if item["status"] == "added":
                msg_lines.append(f"  • {item['domain']}: {item['topic'][:50]}")
        _send_telegram("\n".join(msg_lines))

    if result["errors"]:
        result["status"] = "partial"

    return result


# ── Status report ─────────────────────────────────────────────────────────────

def get_status() -> dict[str, Any]:
    """Return current gap scanner state and coverage matrix summary."""
    state = _load_gap_state()
    matrix = _load_matrix()

    summary: dict[str, Any] = {}
    for domain, data in matrix.items():
        coverage = data.get("coverage", {})
        total = len(coverage)
        if total == 0:
            continue
        summary[domain] = {
            "label": data.get("label", domain),
            "health_pct": data.get("health_pct", 0),
            "gap_pct": data.get("gap_pct", 0),
            "gaps_count": len(data.get("gaps", [])),
            "coverage_updated": data.get("coverage_updated"),
            "gaps_updated": data.get("gaps_updated"),
            "topics": {
                "FRESH": sum(1 for v in coverage.values() if v == "FRESH"),
                "AGING": sum(1 for v in coverage.values() if v == "AGING"),
                "STALE": sum(1 for v in coverage.values() if v == "STALE"),
                "GAP": sum(1 for v in coverage.values() if v == "GAP"),
                "TOTAL": total,
            },
        }

    return {
        "last_layer_a": state.get("last_layer_a"),
        "last_layer_b": state.get("last_layer_b"),
        "layer_a_runs": state.get("layer_a_runs", 0),
        "layer_b_runs": state.get("layer_b_runs", 0),
        "domains": summary,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [GapScanner] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Gap Scanner — ARCH-5 Layer A+B")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--layer-a", action="store_true",
                       help="Layer A: essential questions gap discovery (daily)")
    group.add_argument("--layer-b", action="store_true",
                       help="Layer B: coverage matrix freshness assessment (weekly)")
    group.add_argument("--remediate", action="store_true",
                       help="Gap remediation loop: Gemini search → nlm source add for GAP/STALE topics")
    group.add_argument("--status", action="store_true",
                       help="Show current coverage matrix status")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only, do not query NLM or update state")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.status:
        status = get_status()
        print(f"Last Layer A: {status['last_layer_a'] or 'never'}")
        print(f"Last Layer B: {status['last_layer_b'] or 'never'}")
        print(f"Runs: Layer A={status['layer_a_runs']}, Layer B={status['layer_b_runs']}")
        print()
        for domain, data in status["domains"].items():
            t = data["topics"]
            print(f"  {data['label']:35s} {data['health_pct']:5.1f}% fresh | "
                  f"F:{t['FRESH']} A:{t['AGING']} S:{t['STALE']} G:{t['GAP']} "
                  f"| {data['gaps_count']} gaps")
        return

    if args.layer_a:
        result = run_layer_a(dry_run=args.dry_run)
        print(f"\nLayer A: {result['status']}")
        print(f"  Domains scanned: {result['domains_scanned']}")
        print(f"  Total gaps found: {result['total_gaps']}")
        if result["errors"]:
            print(f"  Errors: {result['errors']}")
        sys.exit(0 if result["status"] == "ok" else 1)

    elif args.layer_b:
        result = run_layer_b(dry_run=args.dry_run)
        print(f"\nLayer B: {result['status']}")
        print(f"  Topics assessed: {result['total_topics']}")
        print(f"  FRESH: {result['fresh']} | AGING: {result['aging']} | STALE: {result['stale']} | GAP: {result['gap']}")
        if result["errors"]:
            print(f"  Errors: {result['errors']}")
        sys.exit(0 if result["status"] == "ok" else 1)

    elif args.remediate:
        result = run_remediation(dry_run=args.dry_run)
        print(f"\nRemediation: {result['status']}")
        print(f"  GAP topics found: {result['gap_topics_found']}")
        print(f"  STALE topics found: {result['stale_topics_found']}")
        print(f"  Sources added: {result['sources_added']}")
        print(f"  Search failed: {result['search_failed']}")
        if result["errors"]:
            print(f"  Errors: {result['errors']}")
        sys.exit(0 if result["status"] in ("ok", "partial") else 1)


if __name__ == "__main__":
    main()
