"""
Mata Garuda — Public Channel Publisher (Layer 5 Distribuzione).

Cura items da garuda:enriched e pubblica quelli esplicitamente marcati
public_safe=true sul canale Telegram pubblico Bali Zero (clienti).

Filtro: public_safe=true AND relevance_score >= 3 AND
domain in {immigration_visa, tax_fiscal, property} — i domini "educativi"
per clienti.

Rate limit: max 3 post/giorno.

Safe default: se TELEGRAM_PUBLIC_CHANNEL_ID non configurato → DRY-RUN
(logga invece di inviare). Zero deve creare il canale + configurare env
per abilitare pubblicazione reale.
"""
from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.stream_tools import stream_length, stream_read
from mata_garuda.tools.tg_public_tools import (
    is_public_channel_configured,
    send_tg_public_post,
)
from mata_garuda.types import Agent

logger = logging.getLogger("mata_garuda.agents.public_channel")

GENOME_FILE = str(Path(__file__).parent / "public_channel_publisher_GENOME.md")

# Filter config
ALLOWED_DOMAINS = {"immigration_visa", "tax_fiscal", "property"}
MIN_RELEVANCE_SCORE = 3
RATE_LIMIT_PER_DAY = 3
STATE_PATH = Path.home() / ".agent" / "decisions" / "public_channel_state.json"

WITA = timezone(timedelta(hours=8))


def _redis_cmd(*args: str, timeout: int = 10) -> str:
    """Run redis-cli and return stdout (empty on error)."""
    try:
        result = subprocess.run(
            ["redis-cli", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            logger.warning("redis-cli failed: %s", result.stderr.strip())
            return ""
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("redis-cli error: %s", e)
        return ""


def _parse_xrange_output(raw: str) -> list[dict[str, str]]:
    """Parse redis-cli XRANGE/XREVRANGE plain output into list of dicts.

    redis-cli formats each entry as:
        1) 1) "<stream_id>"
           2) 1) "field1"
              2) "value1"
              ...
    We parse line by line: lines that are `"field"` alternate with `"value"`
    inside each entry block.
    """
    entries: list[dict[str, str]] = []
    current_id: str | None = None
    current_fields: dict[str, str] = {}
    pending_key: str | None = None

    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Strip `N)` list markers produced by redis-cli
        # e.g. '1) "1734567890-0"' → '"1734567890-0"'
        # Preserve the inner quoted token.
        if ")" in line and line[0].isdigit():
            line = line.split(")", 1)[1].strip()
        # Strip surrounding quotes if present
        if line.startswith('"') and line.endswith('"') and len(line) >= 2:
            line = line[1:-1]
        # Stream IDs look like "<ms>-<seq>"
        if current_id is None and "-" in line and line.replace("-", "").isdigit():
            current_id = line
            current_fields = {}
            pending_key = None
            continue
        if current_id is None:
            continue
        # Check if this line starts a new entry ID (new numbered block at top level).
        # Heuristic: if pending_key is None and line matches <digits>-<digits>,
        # treat as new id.
        if pending_key is None and "-" in line and line.replace("-", "").isdigit():
            # flush previous entry
            if current_fields:
                entries.append({"_id": current_id, **current_fields})
            current_id = line
            current_fields = {}
            continue
        # Otherwise alternating key/value
        if pending_key is None:
            pending_key = line
        else:
            current_fields[pending_key] = line
            pending_key = None

    if current_id and current_fields:
        entries.append({"_id": current_id, **current_fields})
    return entries


def _load_state() -> dict[str, Any]:
    """Load rate-limiting state from disk."""
    if not STATE_PATH.exists():
        return {"day": "", "count": 0, "last_post_id": ""}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:  # noqa: BLE001
        return {"day": "", "count": 0, "last_post_id": ""}


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def _today_wita() -> str:
    return datetime.now(WITA).date().isoformat()


def _reset_if_new_day(state: dict[str, Any]) -> dict[str, Any]:
    today = _today_wita()
    if state.get("day") != today:
        state = {"day": today, "count": 0, "last_post_id": state.get("last_post_id", "")}
    return state


def _is_public_safe(item: dict[str, str]) -> bool:
    """Check all filter conditions."""
    if item.get("public_safe", "").lower() not in {"true", "1", "yes"}:
        return False
    try:
        score = int(item.get("relevance_score", "0"))
    except ValueError:
        return False
    if score < MIN_RELEVANCE_SCORE:
        return False
    domain = item.get("domain", "").lower()
    if domain not in ALLOWED_DOMAINS:
        return False
    return True


def _format_post(item: dict[str, str]) -> str:
    """Format a stream item as a public TG post.

    Plain text, no Markdown quirks. Title + one-line summary + URL.
    """
    title = item.get("title", "Bali Zero Update").strip()
    summary = item.get("content", "").strip().splitlines()
    summary_line = summary[0] if summary else ""
    summary_line = summary_line[:280]
    url = item.get("url", "").strip()
    domain = item.get("domain", "").replace("_", " ")

    parts = [f"🇮🇩 *Bali Zero* — {domain}", "", title]
    if summary_line:
        parts.append(summary_line)
    if url:
        parts.append("")
        parts.append(url)
    return "\n".join(parts)


def fetch_candidate_items(count: int = 50) -> list[dict[str, str]]:
    """Fetch latest enriched items and keep only public-safe ones."""
    raw = _redis_cmd(
        "XREVRANGE", "garuda:enriched", "+", "-", "COUNT", str(count)
    )
    if not raw:
        return []
    entries = _parse_xrange_output(raw)
    return [e for e in entries if _is_public_safe(e)]


def run_public_channel_cycle(
    now: datetime | None = None,
    fetch_fn=None,
    send_fn=None,
    state_loader=None,
    state_saver=None,
) -> dict[str, Any]:
    """One cycle of the publisher. Pure-function hookable for tests."""
    fetch_fn = fetch_fn or fetch_candidate_items
    send_fn = send_fn or send_tg_public_post
    state_loader = state_loader or _load_state
    state_saver = state_saver or _save_state

    state = _reset_if_new_day(state_loader())
    dry_run = not is_public_channel_configured()

    if state["count"] >= RATE_LIMIT_PER_DAY:
        logger.info(
            "Rate limit reached for %s (%d/%d), skipping.",
            state["day"], state["count"], RATE_LIMIT_PER_DAY,
        )
        return {
            "status": "rate_limited",
            "dry_run": dry_run,
            "count": state["count"],
            "posted": 0,
        }

    candidates = fetch_fn()
    if not candidates:
        logger.info("No public-safe candidates found in garuda:enriched.")
        return {"status": "no_candidates", "dry_run": dry_run, "posted": 0}

    # Skip items we've already posted (last_post_id tracks redis stream id)
    last_id = state.get("last_post_id", "")
    fresh = [c for c in candidates if c.get("_id", "") > last_id]
    if not fresh:
        logger.info("No fresh items newer than last_post_id=%s", last_id)
        return {"status": "no_fresh", "dry_run": dry_run, "posted": 0}

    budget = RATE_LIMIT_PER_DAY - state["count"]
    to_post = fresh[:budget]
    posted = 0
    results = []
    for item in to_post:
        post_text = _format_post(item)
        status = send_fn(post_text)
        results.append({"id": item.get("_id", ""), "status": status})
        if status.startswith("[SUCCESS]") or status.startswith("[DRY-RUN]"):
            posted += 1
            state["count"] += 1
            state["last_post_id"] = item.get("_id", state["last_post_id"])

    state_saver(state)

    return {
        "status": "ok",
        "dry_run": dry_run,
        "posted": posted,
        "candidates_seen": len(candidates),
        "results": results,
    }


@register_agent(name="Public Channel Publisher", func_name="get_public_channel_publisher")
def get_public_channel_publisher(model: str = "claude") -> Agent:
    """Layer 5 agent: curates enriched stream → Bali Zero public TG channel."""

    def instructions(context_variables: dict) -> str:
        return """You are the Public Channel Publisher for Mata Garuda (Layer 5 — Distribuzione).

Mission: post at most 3 curated items/day to the Bali Zero public Telegram
channel. Only items flagged `public_safe=true` AND `relevance_score>=3` AND
`domain in {immigration_visa, tax_fiscal, property}` qualify — these are the
client-educational domains.

SAFETY:
- If TELEGRAM_PUBLIC_CHANNEL_ID is missing, run in DRY-RUN mode (log only).
- Never post OSINT, lhkpn, alerts, or internal items.
- Respect the 3/day rate limit.

WORKFLOW:
1. stream_read stream="garuda:enriched" count=50
2. Filter items matching all conditions above
3. For each qualifying fresh item (newer than last posted), call
   send_tg_public_post with a short formatted post (title + 1 line + URL)
4. Stop after 3 posts (or fewer if budget reached)
5. case_resolved

Output SOLO conferma dei post, nessun contenuto dei feed in output."""

    return Agent(
        name="Public Channel Publisher",
        model=model,
        instructions=instructions,
        functions=[
            stream_read, stream_length,
            send_tg_public_post,
            case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="distribuzione",
    )
