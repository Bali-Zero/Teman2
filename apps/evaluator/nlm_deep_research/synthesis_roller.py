"""Rolling Synthesis Module for NLM Deep Research Pipeline.

Implements a 3-tier rolling synthesis strategy to prevent NotebookLM notebooks
from filling up (limit ~300-600 sources) by compressing accumulated intelligence
into progressively larger synthetic sources:

  Daily  → 1 synthetic source per day  (max 400 words)
  Weekly → 7 daily sources fused into 1 weekly source (max 600 words)
  Monthly → weekly sources fused into 1 monthly source (max 800 words)

Synthetic source title conventions (used to identify and manage them):
  [SYNTH-DAILY]  NB-X YYYY-MM-DD
  [SYNTH-WEEK]   NB-X YYYY-WXX
  [SYNTH-MONTH]  NB-X YYYY-MM

NLM CLI calls (sync, subprocess-based like nlm_bridge.py):
  nlm source add <notebook_id> --text <content> --title <title> --wait
  nlm source list <notebook_id>
  nlm source delete <notebook_id> <source_id>

Qwen synthesis calls use /api/chat (NOT /api/generate) with think:false top-level.

Usage:
    from apps.evaluator.nlm_deep_research.synthesis_roller import SynthesisRoller
    roller = SynthesisRoller(nb_id="933509f9-...", nb_name="NB-3: Company Setup")
    roller.run_daily_synthesis(claims=all_claims_today)
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NLM_CLI = "nlm"
NLM_TIMEOUT = 120  # seconds for nlm CLI calls

OLLAMA_URL = "http://localhost:11434/api/chat"
QWEN_MODEL = "qwen3.5:9b"
OLLAMA_TIMEOUT = 120  # seconds

# Word limits per synthesis type
MAX_WORDS_DAILY = 400
MAX_WORDS_WEEKLY = 600
MAX_WORDS_MONTHLY = 800

# Title prefix constants (used to identify synthetic sources in NLM)
PREFIX_DAILY = "[SYNTH-DAILY]"
PREFIX_WEEKLY = "[SYNTH-WEEK]"
PREFIX_MONTHLY = "[SYNTH-MONTH]"

# State file pattern: apps/evaluator/nlm_nbX_synthesis_state.json
STATE_DIR = Path("apps/evaluator")

# WITA = UTC+8
WITA_OFFSET = timedelta(hours=8)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_wita() -> datetime:
    """Return current datetime in WITA (UTC+8)."""
    return datetime.now(timezone.utc) + WITA_OFFSET


def _today_str() -> str:
    """Return today's date string in WITA: YYYY-MM-DD."""
    return _now_wita().strftime("%Y-%m-%d")


def _this_week_str() -> str:
    """Return current ISO week string in WITA: YYYY-WXX (e.g. 2026-W14)."""
    now = _now_wita()
    return now.strftime("%Y-W%W")


def _this_month_str() -> str:
    """Return current month string in WITA: YYYY-MM."""
    return _now_wita().strftime("%Y-%m")


def _is_monday() -> bool:
    """Return True if today (WITA) is Monday."""
    return _now_wita().weekday() == 0  # 0 = Monday


def _is_first_of_month() -> bool:
    """Return True if today (WITA) is the 1st of the month."""
    return _now_wita().day == 1


def _claims_to_text(claims: list[Any]) -> str:
    """Flatten a list of claim records into a plain text block for the prompt.

    Strips confidence scores — Qwen should not cite them in the synthesis.
    """
    lines = []
    for c in claims:
        if isinstance(c, dict):
            # claim_text is the field used by all nbX pipelines
            text = (
                c.get("claim_text")
                or c.get("claim")
                or c.get("text")
                or c.get("content")
                or str(c)
            )
        elif hasattr(c, "claim_text"):
            text = c.claim_text
        elif hasattr(c, "claim"):
            text = c.claim
        elif hasattr(c, "text"):
            text = c.text
        else:
            text = str(c)
        if text:
            lines.append(f"- {text.strip()}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Ollama Qwen synthesis
# ---------------------------------------------------------------------------


def _call_qwen(prompt: str, max_words: int) -> Optional[str]:
    """Call Qwen 3.5:9b via Ollama /api/chat for synthesis.

    Uses think:false top-level (not inside options) as required by CLAUDE.md.
    Returns the synthesized text, or None if Ollama is unavailable.
    """
    try:
        response = httpx.post(
            OLLAMA_URL,
            json={
                "model": QWEN_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "think": False,
                "stream": False,
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("message", {}).get("content", "").strip()
        if not text:
            logger.warning("Qwen returned empty content")
            return None
        return text
    except httpx.ConnectError:
        logger.warning("Ollama not reachable at %s — skipping synthesis", OLLAMA_URL)
        return None
    except httpx.TimeoutException:
        logger.warning("Ollama timeout (%ds) — skipping synthesis", OLLAMA_TIMEOUT)
        return None
    except Exception as e:
        logger.warning("Qwen synthesis error: %s — skipping synthesis", e)
        return None


def _synthesize_daily(nb_name: str, claims: list[Any]) -> Optional[str]:
    """Generate a daily synthesis from today's claims (max 400 words)."""
    claims_text = _claims_to_text(claims)
    if not claims_text:
        logger.info("No claims for daily synthesis — skipping")
        return None

    prompt = (
        f"Sei un analista senior specializzato in {nb_name}. "
        f"Scrivi una sintesi narrativa giornaliera in italiano delle seguenti informazioni intelligence. "
        f"Regole: narrativa fluida (non elenco puntato), max {MAX_WORDS_DAILY} parole, "
        f"evidenzia novità recenti e implicazioni pratiche, NON citare punteggi di confidenza numerici. "
        f"Inizia direttamente con il contenuto, senza intestazione o meta-commenti.\n\n"
        f"INFORMAZIONI:\n{claims_text}\n\n"
        f"SINTESI:"
    )
    return _call_qwen(prompt, MAX_WORDS_DAILY)


def _synthesize_weekly(
    nb_name: str, week_str: str, daily_texts: list[str]
) -> Optional[str]:
    """Fuse 7 daily syntheses into one weekly synthesis (max 600 words)."""
    combined = "\n\n---\n\n".join(daily_texts)
    if not combined.strip():
        return None

    prompt = (
        f"Sei un analista senior specializzato in {nb_name}. "
        f"Consolida le seguenti sintesi giornaliere della settimana {week_str} "
        f"in un'unica sintesi settimanale coerente in italiano. "
        f"Narrativa fluida, max {MAX_WORDS_WEEKLY} parole, evidenzia trend e sviluppi, "
        f"NON citare punteggi numerici, elimina ridondanze. Inizia direttamente.\n\n"
        f"SINTESI GIORNALIERE:\n{combined}\n\n"
        f"OUTPUT: Write the weekly synthesis as a structured briefing."
    )
    return _call_qwen(prompt, MAX_WORDS_WEEKLY)


def _synthesize_monthly(
    nb_name: str, month_str: str, weekly_texts: list[str]
) -> Optional[str]:
    """Fuse all weekly syntheses from the month into one monthly synthesis (max 800 words)."""
    combined = "\n\n---\n\n".join(weekly_texts)
    if not combined.strip():
        return None

    prompt = (
        f"Sei un analista senior specializzato in {nb_name}. "
        f"Consolida le seguenti sintesi settimanali del mese {month_str} "
        f"in un unico documento mensile di knowledge consolidata in italiano. "
        f"Narrativa fluida, max {MAX_WORDS_MONTHLY} parole, focus su insight duraturi e "
        f"cambiamenti normativi permanenti, NON citare punteggi numerici. Inizia direttamente.\n\n"
        f"SINTESI SETTIMANALI:\n{combined}\n\n"
        f"OUTPUT: Write the monthly synthesis as a structured knowledge document."
    )
    return _call_qwen(prompt, MAX_WORDS_MONTHLY)


# ---------------------------------------------------------------------------
# NLM CLI wrappers
# ---------------------------------------------------------------------------


def nlm_source_add(
    notebook_id: str, title: str, text: str, timeout: int = NLM_TIMEOUT
) -> Optional[str]:
    """Add a text source to NLM notebook via CLI.

    Returns the new source_id on success, None on failure.
    """
    cmd = [
        NLM_CLI, "source", "add", notebook_id,
        "--text", text,
        "--title", title,
        "--wait",
    ]
    logger.info("NLM source add: title=%s (notebook=%s)", title, notebook_id)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 30,
        )
        if result.returncode != 0:
            logger.error("nlm source add failed: %s", result.stderr[:300])
            return None

        # Try to parse source_id from JSON output
        output = result.stdout.strip()
        if output:
            try:
                data = json.loads(output)
                # Handle {"value": {"source_id": "..."}} or {"source_id": "..."}
                if "value" in data and isinstance(data["value"], dict):
                    data = data["value"]
                source_id = (
                    data.get("source_id")
                    or data.get("id")
                    or data.get("sourceId")
                )
                if source_id:
                    logger.info("NLM source added: id=%s", source_id)
                    return str(source_id)
            except json.JSONDecodeError:
                pass
        # No parseable source_id but command succeeded — return sentinel
        logger.info("NLM source add succeeded (no source_id in output)")
        return "ok"

    except subprocess.TimeoutExpired:
        logger.error("nlm source add timeout (%ds)", timeout)
        return None
    except FileNotFoundError:
        logger.error("nlm CLI not found")
        return None
    except Exception as e:
        logger.error("nlm source add error: %s", e)
        return None


def nlm_source_list(notebook_id: str, timeout: int = NLM_TIMEOUT) -> list[dict]:
    """List all sources in an NLM notebook.

    Returns list of dicts with at least: {id, title}.
    """
    cmd = [NLM_CLI, "source", "list", notebook_id]
    logger.debug("NLM source list: notebook=%s", notebook_id)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 30,
        )
        if result.returncode != 0:
            logger.error("nlm source list failed: %s", result.stderr[:300])
            return []

        output = result.stdout.strip()
        if not output:
            return []

        data = json.loads(output)
        # Handle {"value": [...]} or [...]
        if isinstance(data, dict) and "value" in data:
            data = data["value"]
        if isinstance(data, list):
            return data
        # Some CLIs return {"sources": [...]}
        if isinstance(data, dict) and "sources" in data:
            return data["sources"]
        return []

    except subprocess.TimeoutExpired:
        logger.error("nlm source list timeout (%ds)", timeout)
        return []
    except json.JSONDecodeError as e:
        logger.error("nlm source list JSON parse error: %s", e)
        return []
    except FileNotFoundError:
        logger.error("nlm CLI not found")
        return []
    except Exception as e:
        logger.error("nlm source list error: %s", e)
        return []


def nlm_source_delete(
    notebook_id: str, source_id: str, timeout: int = NLM_TIMEOUT
) -> bool:
    """Delete a source from an NLM notebook by source_id."""
    cmd = [NLM_CLI, "source", "delete", notebook_id, source_id]
    logger.info("NLM source delete: id=%s (notebook=%s)", source_id, notebook_id)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 30,
        )
        if result.returncode != 0:
            logger.error("nlm source delete failed: %s", result.stderr[:300])
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("nlm source delete timeout (%ds)", timeout)
        return False
    except FileNotFoundError:
        logger.error("nlm CLI not found")
        return False
    except Exception as e:
        logger.error("nlm source delete error: %s", e)
        return False


# ---------------------------------------------------------------------------
# Synthesis State
# ---------------------------------------------------------------------------


class SynthesisState:
    """Persists synthesis metadata for a notebook.

    State file: apps/evaluator/nlm_nbX_synthesis_state.json
    Tracks which synthetic sources exist in NLM (title → source_id mapping),
    plus content of daily/weekly syntheses for fusion operations.
    """

    def __init__(self, nb_id: str, nb_name: str) -> None:
        # Derive a short key from nb_name: "NB-3" → "nb3"
        nb_slug = nb_name.split(":")[0].strip().lower().replace("-", "")
        self.path = STATE_DIR / f"nlm_{nb_slug}_synthesis_state.json"
        self.nb_id = nb_id
        self.nb_name = nb_name
        self._data: dict = {}

    def load(self) -> None:
        """Load state from disk, or initialize empty state."""
        if self.path.exists():
            with open(self.path) as f:
                self._data = json.load(f)
            logger.debug("Loaded synthesis state from %s", self.path)
        else:
            self._data = self._default_state()
            logger.info("Initialized empty synthesis state for %s", self.nb_name)

    def save(self) -> None:
        """Persist state to disk."""
        self._data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        logger.debug("Saved synthesis state to %s", self.path)

    def _default_state(self) -> dict:
        return {
            "schema_version": 1,
            "notebook_id": self.nb_id,
            "notebook_name": self.nb_name,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            # title → source_id: tracks live synthetic sources in NLM
            "daily_sources": {},    # "2026-03-31" → source_id
            "weekly_sources": {},   # "2026-W13" → source_id
            "monthly_sources": {},  # "2026-03" → source_id
            # content cache for fusion
            "daily_texts": {},      # "2026-03-31" → synthesis text
            "weekly_texts": {},     # "2026-W13" → synthesis text
        }

    # --- Accessors ---

    @property
    def daily_sources(self) -> dict[str, str]:
        return self._data.setdefault("daily_sources", {})

    @property
    def weekly_sources(self) -> dict[str, str]:
        return self._data.setdefault("weekly_sources", {})

    @property
    def monthly_sources(self) -> dict[str, str]:
        return self._data.setdefault("monthly_sources", {})

    @property
    def daily_texts(self) -> dict[str, str]:
        return self._data.setdefault("daily_texts", {})

    @property
    def weekly_texts(self) -> dict[str, str]:
        return self._data.setdefault("weekly_texts", {})

    def count_daily(self) -> int:
        return len(self.daily_sources)

    def count_weekly(self) -> int:
        return len(self.weekly_sources)

    def count_monthly(self) -> int:
        return len(self.monthly_sources)

    def total_synthetic_count(self) -> int:
        return self.count_daily() + self.count_weekly() + self.count_monthly()

    def record_daily(self, date_str: str, source_id: str, text: str) -> None:
        self.daily_sources[date_str] = source_id
        self.daily_texts[date_str] = text

    def record_weekly(self, week_str: str, source_id: str, text: str) -> None:
        self.weekly_sources[week_str] = source_id
        self.weekly_texts[week_str] = text

    def record_monthly(self, month_str: str, source_id: str) -> None:
        self.monthly_sources[month_str] = source_id

    def remove_daily(self, date_str: str) -> None:
        self.daily_sources.pop(date_str, None)
        self.daily_texts.pop(date_str, None)

    def remove_weekly(self, week_str: str) -> None:
        self.weekly_sources.pop(week_str, None)
        self.weekly_texts.pop(week_str, None)

    def get_daily_for_week(self, week_str: str) -> dict[str, dict]:
        """Return {date_str: {source_id, text}} for all daily entries in week_str."""
        result = {}
        # Calculate which dates belong to this ISO week
        week_dates = _dates_in_iso_week(week_str)
        for date_str in week_dates:
            sid = self.daily_sources.get(date_str)
            text = self.daily_texts.get(date_str, "")
            if sid:
                result[date_str] = {"source_id": sid, "text": text}
        return result

    def get_weeklies_for_month(self, month_str: str) -> dict[str, dict]:
        """Return {week_str: {source_id, text}} for all weekly entries in month_str."""
        result = {}
        for week_str, sid in self.weekly_sources.items():
            if _week_belongs_to_month(week_str, month_str):
                result[week_str] = {
                    "source_id": sid,
                    "text": self.weekly_texts.get(week_str, ""),
                }
        return result


# ---------------------------------------------------------------------------
# Date utilities
# ---------------------------------------------------------------------------


def _dates_in_iso_week(week_str: str) -> list[str]:
    """Return list of YYYY-MM-DD strings for all 7 days of the given ISO week.

    week_str format: YYYY-WXX (e.g. "2026-W13")
    Uses %Y-W%W-%w strptime convention (week 0 = week with Jan 1, Monday start).
    """
    try:
        year_str, week_part = week_str.split("-W")
        year = int(year_str)
        week_num = int(week_part)
        # %W = week number with Monday as first day of week (00-53)
        # %w = weekday (0=Sunday, 1=Monday)
        # Use day 1 (Monday) to get the start of the week
        monday = datetime.strptime(f"{year}-W{week_num:02d}-1", "%Y-W%W-%w")
        return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    except (ValueError, AttributeError):
        return []


def _week_belongs_to_month(week_str: str, month_str: str) -> bool:
    """Return True if the Thursday of week_str falls in month_str.

    Using ISO convention: a week belongs to the month that contains its Thursday.
    """
    dates = _dates_in_iso_week(week_str)
    if len(dates) < 4:
        return False
    thursday = dates[3]  # index 3 = Thursday (Mon=0)
    return thursday.startswith(month_str)


# ---------------------------------------------------------------------------
# Main SynthesisRoller
# ---------------------------------------------------------------------------


class SynthesisRoller:
    """Rolling synthesis engine for a single NLM notebook.

    Instantiate once per pipeline run; call run_daily_synthesis() after
    the pipeline's CONSOLIDATE phase.

    Args:
        nb_id: NotebookLM notebook UUID.
        nb_name: Human-readable notebook name (e.g. "NB-3: Company Setup").
        dry_run: If True, skips actual NLM/Qwen calls and logs what would happen.
    """

    def __init__(self, nb_id: str, nb_name: str, dry_run: bool = False) -> None:
        self.nb_id = nb_id
        self.nb_name = nb_name
        self.dry_run = dry_run
        self.state = SynthesisState(nb_id=nb_id, nb_name=nb_name)

    def run_daily_synthesis(self, claims: list[Any]) -> dict:
        """Entry point called by nbX_pipeline.py after CONSOLIDATE phase.

        Performs, in order:
          1. Daily synthesis of today's claims → adds 1 source to NLM
          2. (Monday only) Weekly roll-up of 7 daily sources → replaces them with 1
          3. (1st of month only) Monthly roll-up of weekly sources → replaces them with 1

        Returns a summary dict with keys: daily, weekly, monthly, total_synthetic.
        """
        self.state.load()
        today = _today_str()
        week = _this_week_str()
        month = _this_month_str()

        summary: dict = {
            "notebook": self.nb_name,
            "date": today,
            "dry_run": self.dry_run,
            "daily": None,
            "weekly": None,
            "monthly": None,
            "total_synthetic": self.state.total_synthetic_count(),
        }

        # ----------------------------------------------------------------
        # Step 1: Daily synthesis
        # ----------------------------------------------------------------
        daily_result = self._run_daily(today, claims)
        summary["daily"] = daily_result

        # ----------------------------------------------------------------
        # Step 2: Weekly roll-up (Mondays only)
        # ----------------------------------------------------------------
        if _is_monday():
            weekly_result = self._run_weekly(week)
            summary["weekly"] = weekly_result
        else:
            logger.debug("Not Monday — skipping weekly roll-up (today: %s)", today)

        # ----------------------------------------------------------------
        # Step 3: Monthly roll-up (1st of month only)
        # ----------------------------------------------------------------
        if _is_first_of_month():
            monthly_result = self._run_monthly(month)
            summary["monthly"] = monthly_result
        else:
            logger.debug("Not 1st of month — skipping monthly roll-up (today: %s)", today)

        summary["total_synthetic"] = self.state.total_synthetic_count()
        self.state.save()

        logger.info(
            "SynthesisRoller done for %s: daily=%s weekly=%s monthly=%s total_synth=%d",
            self.nb_name,
            daily_result.get("status") if daily_result else "skipped",
            summary["weekly"].get("status") if summary["weekly"] else "skipped",
            summary["monthly"].get("status") if summary["monthly"] else "skipped",
            summary["total_synthetic"],
        )
        return summary

    # ----------------------------------------------------------------
    # Daily phase
    # ----------------------------------------------------------------

    def _run_daily(self, today: str, claims: list[Any]) -> dict:
        """Generate and upload today's daily synthesis source."""
        title = f"{PREFIX_DAILY} {self.nb_name.split(':')[0].strip()} {today}"

        # Check if already done today (idempotent)
        if today in self.state.daily_sources:
            logger.info("Daily synthesis for %s already exists — skipping", today)
            return {
                "status": "already_done",
                "date": today,
                "source_id": self.state.daily_sources[today],
            }

        if not claims:
            logger.info("No claims for daily synthesis on %s — skipping", today)
            return {"status": "skipped_no_claims", "date": today}

        logger.info("Generating daily synthesis for %s (%d claims)...", today, len(claims))

        if self.dry_run:
            text = f"[DRY-RUN] Daily synthesis for {today} — {len(claims)} claims"
            logger.info("[DRY-RUN] Would add NLM source: %s", title)
            self.state.record_daily(today, "dry-run-id", text)
            return {"status": "dry_run", "date": today, "title": title}

        text = _synthesize_daily(self.nb_name, claims)
        if text is None:
            return {"status": "skipped_ollama_unavailable", "date": today}

        source_id = nlm_source_add(self.nb_id, title=title, text=text)
        if source_id is None:
            logger.error("Failed to add daily synthesis to NLM for %s", today)
            return {"status": "error_nlm_add", "date": today}

        self.state.record_daily(today, source_id, text)
        logger.info("Daily synthesis added: %s → source_id=%s", title, source_id)
        return {
            "status": "ok",
            "date": today,
            "title": title,
            "source_id": source_id,
            "word_count": len(text.split()),
        }

    # ----------------------------------------------------------------
    # Weekly roll-up phase
    # ----------------------------------------------------------------

    def _run_weekly(self, week_str: str) -> dict:
        """Fuse 7 daily syntheses into 1 weekly synthesis.

        On completion: deletes the 7 daily NLM sources, uploads 1 weekly source.
        """
        title = f"{PREFIX_WEEKLY} {self.nb_name.split(':')[0].strip()} {week_str}"

        # Idempotency check
        if week_str in self.state.weekly_sources:
            logger.info("Weekly synthesis for %s already exists — skipping", week_str)
            return {
                "status": "already_done",
                "week": week_str,
                "source_id": self.state.weekly_sources[week_str],
            }

        daily_entries = self.state.get_daily_for_week(week_str)
        if not daily_entries:
            logger.info("No daily syntheses found for week %s — skipping weekly roll-up", week_str)
            return {"status": "skipped_no_daily", "week": week_str}

        daily_texts = [entry["text"] for entry in daily_entries.values() if entry.get("text")]
        if not daily_texts:
            logger.info("Daily syntheses have no text for week %s — skipping", week_str)
            return {"status": "skipped_empty_texts", "week": week_str}

        logger.info(
            "Generating weekly synthesis for %s (%d daily entries)...",
            week_str, len(daily_texts)
        )

        if self.dry_run:
            text = f"[DRY-RUN] Weekly synthesis for {week_str} — {len(daily_texts)} dailies"
            logger.info("[DRY-RUN] Would add NLM source: %s", title)
            logger.info("[DRY-RUN] Would delete %d daily sources", len(daily_entries))
            self.state.record_weekly(week_str, "dry-run-weekly-id", text)
            for date_str in list(daily_entries.keys()):
                self.state.remove_daily(date_str)
            return {"status": "dry_run", "week": week_str, "fused": len(daily_texts)}

        weekly_text = _synthesize_weekly(self.nb_name, week_str, daily_texts)
        if weekly_text is None:
            return {"status": "skipped_ollama_unavailable", "week": week_str}

        # Upload weekly source first (fail-safe: add before deleting)
        source_id = nlm_source_add(self.nb_id, title=title, text=weekly_text)
        if source_id is None:
            logger.error("Failed to add weekly synthesis — NOT deleting daily sources")
            return {"status": "error_nlm_add", "week": week_str}

        self.state.record_weekly(week_str, source_id, weekly_text)

        # Delete the individual daily sources from NLM
        deleted = []
        failed_deletes = []
        for date_str, entry in daily_entries.items():
            sid = entry.get("source_id", "")
            if sid and sid not in ("dry-run-id", "ok"):
                ok = nlm_source_delete(self.nb_id, sid)
                if ok:
                    deleted.append(date_str)
                else:
                    failed_deletes.append(date_str)
                    logger.warning("Failed to delete daily source %s (%s)", sid, date_str)
            else:
                deleted.append(date_str)  # Already gone or sentinel — remove from state

            self.state.remove_daily(date_str)

        logger.info(
            "Weekly roll-up done for %s: source_id=%s deleted=%d failed=%d",
            week_str, source_id, len(deleted), len(failed_deletes)
        )
        return {
            "status": "ok",
            "week": week_str,
            "title": title,
            "source_id": source_id,
            "fused": len(daily_texts),
            "deleted_daily": deleted,
            "failed_deletes": failed_deletes,
            "word_count": len(weekly_text.split()),
        }

    # ----------------------------------------------------------------
    # Monthly roll-up phase
    # ----------------------------------------------------------------

    def _run_monthly(self, month_str: str) -> dict:
        """Fuse all weekly syntheses from this month into 1 monthly source.

        On completion: deletes the weekly NLM sources, uploads 1 monthly source.
        """
        title = f"{PREFIX_MONTHLY} {self.nb_name.split(':')[0].strip()} {month_str}"

        # Idempotency check
        if month_str in self.state.monthly_sources:
            logger.info("Monthly synthesis for %s already exists — skipping", month_str)
            return {
                "status": "already_done",
                "month": month_str,
                "source_id": self.state.monthly_sources[month_str],
            }

        weekly_entries = self.state.get_weeklies_for_month(month_str)
        if not weekly_entries:
            logger.info("No weekly syntheses for month %s — skipping monthly roll-up", month_str)
            return {"status": "skipped_no_weekly", "month": month_str}

        weekly_texts = [entry["text"] for entry in weekly_entries.values() if entry.get("text")]
        if not weekly_texts:
            logger.info("Weekly syntheses have no text for month %s — skipping", month_str)
            return {"status": "skipped_empty_texts", "month": month_str}

        logger.info(
            "Generating monthly synthesis for %s (%d weekly entries)...",
            month_str, len(weekly_texts)
        )

        if self.dry_run:
            text = f"[DRY-RUN] Monthly synthesis for {month_str} — {len(weekly_texts)} weeklies"
            logger.info("[DRY-RUN] Would add NLM source: %s", title)
            logger.info("[DRY-RUN] Would delete %d weekly sources", len(weekly_entries))
            self.state.record_monthly(month_str, "dry-run-monthly-id")
            for week_str in list(weekly_entries.keys()):
                self.state.remove_weekly(week_str)
            return {"status": "dry_run", "month": month_str, "fused": len(weekly_texts)}

        monthly_text = _synthesize_monthly(self.nb_name, month_str, weekly_texts)
        if monthly_text is None:
            return {"status": "skipped_ollama_unavailable", "month": month_str}

        # Upload monthly source first (fail-safe)
        source_id = nlm_source_add(self.nb_id, title=title, text=monthly_text)
        if source_id is None:
            logger.error("Failed to add monthly synthesis — NOT deleting weekly sources")
            return {"status": "error_nlm_add", "month": month_str}

        self.state.record_monthly(month_str, source_id)

        # Delete weekly sources from NLM
        deleted = []
        failed_deletes = []
        for week_str, entry in weekly_entries.items():
            sid = entry.get("source_id", "")
            if sid and sid not in ("dry-run-weekly-id", "ok"):
                ok = nlm_source_delete(self.nb_id, sid)
                if ok:
                    deleted.append(week_str)
                else:
                    failed_deletes.append(week_str)
                    logger.warning("Failed to delete weekly source %s (%s)", sid, week_str)
            else:
                deleted.append(week_str)

            self.state.remove_weekly(week_str)

        logger.info(
            "Monthly roll-up done for %s: source_id=%s deleted=%d failed=%d",
            month_str, source_id, len(deleted), len(failed_deletes)
        )
        return {
            "status": "ok",
            "month": month_str,
            "title": title,
            "source_id": source_id,
            "fused": len(weekly_texts),
            "deleted_weekly": deleted,
            "failed_deletes": failed_deletes,
            "word_count": len(monthly_text.split()),
        }


# ---------------------------------------------------------------------------
# Convenience factory — used by pipelines
# ---------------------------------------------------------------------------


def run_daily_synthesis(
    nb_id: str,
    nb_name: str,
    claims: list[Any],
    dry_run: bool = False,
) -> dict:
    """Convenience function to be called by nbX_pipeline.py after CONSOLIDATE.

    Example usage in nb3_pipeline.py:
        from .synthesis_roller import run_daily_synthesis
        roller_summary = run_daily_synthesis(
            nb_id=NB3_NOTEBOOK_ID,
            nb_name="NB-3: Company Setup Indonesia",
            claims=all_claims,
            dry_run=self.dry_run,
        )
        summary["phases"]["synthesis"] = roller_summary

    Args:
        nb_id: NotebookLM notebook UUID.
        nb_name: Human-readable notebook name.
        claims: List of ClaimRecord objects or dicts from today's pipeline run.
        dry_run: If True, no actual NLM/Qwen calls are made.

    Returns:
        Summary dict from SynthesisRoller.run_daily_synthesis().
    """
    roller = SynthesisRoller(nb_id=nb_id, nb_name=nb_name, dry_run=dry_run)
    return roller.run_daily_synthesis(claims=claims)
