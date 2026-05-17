#!/usr/bin/env python3
"""
NLM Legal Context Step — Step 2.9 of Intel Pipeline

Queries NotebookLM core notebooks (read-only) for legal context,
and optionally runs Deep Research in a temporary notebook for web findings.

Architecture:
  Phase A: notebook_query on NB core → legal_basis + citations (read-only, ~5s)
  Phase B: If Phase A insufficient → research_start on temp NB → web findings (~30-60s)

Safety:
  - NB core (NB-2/3/4/5/6) are NEVER modified
  - Web findings go to temporary notebooks only
  - Pending sources saved for human approval before NB core import
  - 60s hard timeout per operation, graceful degradation on failure
  - Max 3 dossiers per run (budget protection)
"""

import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# NLM CLI binary
NLM_CLI = "nlm"

# Mapping: scraper category → NotebookLM notebook UUID
CATEGORY_NB_MAP: dict[str, str] = {
    "immigration": "cff93ab0-813a-42f2-a8de-36987e724271",       # NB-2
    "business": "933509f9-1561-403d-bd44-4a7a67a36df2",           # NB-3
    "tax": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",               # NB-4
    "tax-legal": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",         # NB-4
    "property": "d9438180-5e63-4e2a-a473-6061101f6a8d",           # NB-5
    "business_regulations": "85207af3-352f-4554-8d2a-18f42cc541ba",  # NB-6
    "legal": "85207af3-352f-4554-8d2a-18f42cc541ba",              # NB-6
    "compliance": "85207af3-352f-4554-8d2a-18f42cc541ba",         # NB-6
}

# Categories that qualify for NLM legal context
REGULATORY_CATEGORIES = set(CATEGORY_NB_MAP.keys())

# Limits
MAX_DOSSIERS_PER_RUN = 3
MIN_QUALITY_SCORE = 50
ALLOWED_TIERS = {"T1", "T2"}
QUERY_TIMEOUT = 60  # seconds per NLM operation
MIN_CITATIONS_FOR_PHASE_B = 2

# Pending sources directory
PENDING_DIR = Path(__file__).parent.parent / "data" / "pending_sources"

# Total step timeout (all dossiers combined) — prevents pipeline overrun
STEP_TIMEOUT = 300  # 5 minutes max for entire step 2.9


def _safe_cli_str(s: str) -> str:
    """Sanitize string for use as CLI argument value.

    Prevents flag injection (titles starting with --) and null bytes.
    """
    t = s.strip().replace("\x00", "")
    if t.startswith("-"):
        t = " " + t
    return t


def _nlm_cmd(args: list[str], timeout: int = QUERY_TIMEOUT) -> dict:
    """Run an nlm CLI command and parse JSON output."""
    cmd = [NLM_CLI] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 15,
        )
        if result.returncode != 0:
            error = result.stderr.strip() or f"exit code {result.returncode}"
            logger.warning("nlm CLI error: %s", error)
            return {"status": "error", "error": error}

        output = result.stdout.strip()
        if not output:
            return {"status": "error", "error": "empty response"}

        data = json.loads(output)
        if "value" in data and isinstance(data["value"], dict):
            data = data["value"]
        return data

    except subprocess.TimeoutExpired:
        logger.warning("nlm command timed out after %ds: %s", timeout, " ".join(args[:4]))
        return {"status": "error", "error": f"timeout {timeout}s"}
    except json.JSONDecodeError as e:
        logger.warning("nlm JSON parse error: %s", e)
        return {"status": "error", "error": f"json parse: {e}"}
    except FileNotFoundError:
        logger.error("nlm CLI not found")
        return {"status": "error", "error": "nlm not found"}
    except Exception as e:
        logger.error("nlm unexpected error: %s", e)
        return {"status": "error", "error": str(e)}


def _query_nb_core(notebook_id: str, title: str) -> dict:
    """Phase A: Query NB core for legal context (read-only)."""
    title = str(title or '')[:300]  # Canonical truncation for CLI safety
    query = (
        f"What existing Indonesian laws, regulations, government circulars, "
        f"and official rules relate to this news: '{title}'? "
        f"Cite specific regulation numbers (PP, UU, Permen, SE, Perda). "
        f"Be concise — bullet points with regulation references."
    )
    result = _nlm_cmd([
        "query", "notebook", notebook_id, query,
        "--timeout", str(QUERY_TIMEOUT),
    ])

    if result.get("status") == "error":
        return {"legal_basis": "", "citations": [], "status": "error"}

    answer = result.get("answer", "")
    citations = result.get("citations", {})
    sources_used = result.get("sources_used", [])

    # Count meaningful citations (non-empty)
    citation_count = len([c for c in citations.values() if c]) if isinstance(citations, dict) else 0
    if not citation_count:
        citation_count = len(sources_used)

    return {
        "legal_basis": answer,
        "citations": citations,
        "sources_used": sources_used,
        "citation_count": citation_count,
        "status": "ok",
    }


def _deep_research_temp_nb(title: str, category: str) -> dict:
    """Phase B: Create temp NB, run fast Deep Research, query for web findings."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    temp_title = f"Scraper Temp {date_str} — {_safe_cli_str(title[:50])}"

    # 1. Create temporary notebook
    create_result = _nlm_cmd(["notebook", "create", "--title", temp_title])
    if create_result.get("status") == "error":
        return {"web_findings": "", "temp_nb_id": None, "status": "error"}

    temp_nb_id = create_result.get("notebook_id") or create_result.get("id", "")
    if not temp_nb_id:
        # Try nested
        nb = create_result.get("notebook", {})
        temp_nb_id = nb.get("id", "")

    if not temp_nb_id:
        logger.warning("Could not create temp NB for: %s", title[:50])
        return {"web_findings": "", "temp_nb_id": None, "status": "error"}

    logger.info("Created temp NB %s for: %s", temp_nb_id[:8], title[:50])

    # 2. Run fast Deep Research
    research_query = f"{_safe_cli_str(title)} Indonesian regulation law 2026"
    research_result = _nlm_cmd([
        "research", "start",
        "--notebook", temp_nb_id,
        "--query", research_query,
        "--mode", "fast",
    ])

    task_id = research_result.get("task_id", "")

    # 3. Poll for completion (max 60s) using task_id, not notebook_id
    research_completed = False
    if task_id:
        start = time.time()
        while time.time() - start < QUERY_TIMEOUT:
            status = _nlm_cmd([
                "research", "status", task_id,
                "--max-wait", "10",
            ], timeout=15)  # 15s subprocess timeout (no +15 padding for polls)
            if status.get("status") == "completed":
                sources_found = status.get("sources_found", 0)
                logger.info("Deep Research complete: %d sources found", sources_found)
                research_completed = True
                break
            if status.get("status") == "error":
                logger.warning("Deep Research returned error")
                break
            # Check elapsed AFTER the blocking call, BEFORE sleeping
            if time.time() - start >= QUERY_TIMEOUT:
                break
            time.sleep(5)
        if not research_completed:
            logger.warning("Deep Research did not complete within %ds — skipping Phase B web query", QUERY_TIMEOUT)

    # 4. Query the temp NB for web context (only if research completed)
    web_findings = ""
    if research_completed:
        web_query = (
            f"Based on the web sources found, what are the key regulatory facts about: {title}? "
            f"Cite the source URLs."
        )
        web_result = _nlm_cmd([
            "query", "notebook", temp_nb_id, web_query,
            "--timeout", str(QUERY_TIMEOUT),
        ])
        web_findings = web_result.get("answer", "")

    # 5. Save pending sources for human approval
    _save_pending_sources(temp_nb_id, category, title)

    return {
        "web_findings": web_findings,
        "temp_nb_id": temp_nb_id,
        "status": "ok",
    }


def _cleanup_stale_temp_notebooks(max_age_days: int = 7) -> int:
    """Delete temp notebooks older than max_age_days from pending_sources.

    Reads JSONL files, deletes old temp NB via nlm CLI, marks as auto_deleted.
    Returns count of notebooks deleted.
    """
    from datetime import timedelta
    cutoff = datetime.now() - timedelta(days=max_age_days)
    deleted = 0

    if not PENDING_DIR.exists():
        return 0

    for jsonl_path in PENDING_DIR.glob("*.jsonl"):
        lines = jsonl_path.read_text().splitlines()
        updated = []
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if (
                    entry.get("status") == "pending_review"
                    and entry.get("temp_nb_id")
                    and entry.get("created_at")
                ):
                    created = datetime.fromisoformat(entry["created_at"])
                    if created < cutoff:
                        result = _nlm_cmd(
                            ["notebook", "delete", entry["temp_nb_id"], "--confirm"],
                            timeout=15,
                        )
                        if result.get("status") != "error":
                            entry["status"] = "auto_deleted"
                            deleted += 1
                            logger.info("Deleted stale temp NB %s", entry["temp_nb_id"][:8])
                        else:
                            logger.warning("Failed to delete temp NB %s", entry["temp_nb_id"][:8])
            except (json.JSONDecodeError, ValueError, KeyError):
                pass
            updated.append(json.dumps(entry) if isinstance(entry, dict) else line)

        # Rewrite file with updated statuses
        jsonl_path.write_text("\n".join(updated) + "\n")

    if deleted:
        logger.info("Cleaned up %d stale temp notebooks (older than %d days)", deleted, max_age_days)
    return deleted


def _save_pending_sources(temp_nb_id: str, category: str, title: str) -> None:
    """Save temp NB info for human review and potential NB core import.

    Uses JSONL (one JSON object per line) for atomic append — safe even
    if two pipeline runs overlap. Filesystem errors are caught and logged
    without propagating (saving metadata should never kill Phase B results).
    """
    try:
        # Guard: only whitelisted categories can write files (prevents path traversal)
        if category not in REGULATORY_CATEGORIES:
            logger.warning("Unexpected category for pending source: %r — skipping", category)
            return

        PENDING_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_str}_{category}.jsonl"
        filepath = PENDING_DIR / filename

        entry = {
            "date": date_str,
            "category": category,
            "title": title,
            "temp_nb_id": temp_nb_id,
            "status": "pending_review",
            "created_at": datetime.now().isoformat(),
        }

        with open(filepath, "a") as f:
            f.write(json.dumps(entry) + "\n")

        logger.info("Saved pending source for review: %s", filepath.name)
    except OSError as e:
        logger.warning("Could not save pending source to %s: %s", PENDING_DIR, e)


def select_dossiers_for_nlm(articles: list[dict]) -> list[dict]:
    """Select top regulatory dossiers eligible for NLM legal context."""
    eligible = [
        a for a in articles
        if (a.get("dossier") or {}).get("is_primary", False)
        and a.get("qwen_category", a.get("category", "")) in REGULATORY_CATEGORIES
        and a.get("tier", "T3") in ALLOWED_TIERS
        and int(a.get("quality_score", 0) or 0) >= MIN_QUALITY_SCORE
    ]

    # Sort by quality_score desc, T1 first
    tier_order = {"T1": 0, "T2": 1}
    eligible.sort(key=lambda a: (tier_order.get(a.get("tier", "T2"), 1), -int(a.get("quality_score", 0) or 0)))

    selected = eligible[:MAX_DOSSIERS_PER_RUN]
    logger.info(
        "NLM eligible: %d/%d articles, selected: %d",
        len(eligible), len(articles), len(selected),
    )
    return selected


def enrich_with_nlm_context(article: dict) -> dict:
    """Add NLM legal context to a single article.

    Phase A: Query NB core (read-only)
    Phase B: If insufficient → Deep Research in temp NB

    Returns article with 'nlm_context' field added.
    """
    category = article.get("qwen_category", article.get("category", ""))
    title = article.get("title", "")
    nb_id = CATEGORY_NB_MAP.get(category)

    if not nb_id:
        logger.warning("No NB mapping for category: %s", category)
        article["nlm_context"] = {"status": "skipped", "reason": "no_nb_mapping"}
        return article

    # Phase A: Query NB Core
    logger.info("Phase A — querying NB core for: %s", title[:60])
    core_result = _query_nb_core(nb_id, title)
    article["nlm_context"] = {
        "legal_basis": core_result.get("legal_basis", ""),
        "citations": core_result.get("citations", {}),
        "sources_used": core_result.get("sources_used", []),
        "phase_a_status": core_result.get("status", "error"),
    }

    # Phase B: Deep Research if Phase A didn't find enough
    citation_count = core_result.get("citation_count", 0)
    if citation_count < MIN_CITATIONS_FOR_PHASE_B and core_result.get("status") == "ok":
        logger.info(
            "Phase B — only %d citations, running Deep Research for: %s",
            citation_count, title[:60],
        )
        web_result = _deep_research_temp_nb(title, category)
        article["nlm_context"]["web_findings"] = web_result.get("web_findings", "")
        article["nlm_context"]["temp_nb_id"] = web_result.get("temp_nb_id")
        article["nlm_context"]["phase_b_status"] = web_result.get("status", "error")
    else:
        article["nlm_context"]["phase_b_status"] = "skipped"

    return article


def run_nlm_legal_context(articles: list[dict], log_fn=None) -> list[dict]:
    """Main entry point for Step 2.9.

    Selects eligible dossiers, enriches with NLM context, returns all articles.
    Non-eligible articles are returned unchanged.

    Args:
        articles: List of article dicts from pipeline
        log_fn: Optional logging function (uses logger.info if not provided)

    Returns:
        Updated articles list with nlm_context added to eligible ones.
    """
    _log = log_fn or logger.info

    # Check NLM CLI availability
    try:
        subprocess.run([NLM_CLI, "--version"], capture_output=True, timeout=10, check=True)
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        _log("NLM CLI not available — skipping step 2.9")
        return articles

    selected = select_dossiers_for_nlm(articles)
    if not selected:
        _log("No eligible dossiers for NLM legal context")
        return articles

    # Cleanup stale temp notebooks before creating new ones (prevents 100-NB limit breach)
    try:
        cleaned = _cleanup_stale_temp_notebooks(max_age_days=7)
        if cleaned:
            _log(f"  Cleaned {cleaned} stale temp notebooks")
    except Exception as e:
        _log(f"  Temp NB cleanup failed (non-fatal): {e}")

    _log(f"Step 2.9: Processing {len(selected)} dossiers with NLM (max {STEP_TIMEOUT}s)...")

    step_start = time.time()
    for i, article in enumerate(selected, 1):
        # Enforce total step timeout across all dossiers
        if time.time() - step_start >= STEP_TIMEOUT:
            _log(f"  Step timeout ({STEP_TIMEOUT}s) reached after {i-1} dossiers — skipping remaining")
            break

        title = article.get("title", "")[:60]
        _log(f"  [{i}/{len(selected)}] {title}")

        try:
            enrich_with_nlm_context(article)
            status_a = article.get("nlm_context", {}).get("phase_a_status", "?")
            status_b = article.get("nlm_context", {}).get("phase_b_status", "?")
            _log(f"    Phase A: {status_a}, Phase B: {status_b}")
        except Exception as e:
            _log(f"    ERROR: {e}")
            article["nlm_context"] = {"status": "error", "error": str(e)}

    # Count results
    ok_count = sum(
        1 for a in articles
        if a.get("nlm_context", {}).get("phase_a_status") == "ok"
    )
    _log(f"Step 2.9 complete: {ok_count}/{len(selected)} enriched with legal context")

    return articles
