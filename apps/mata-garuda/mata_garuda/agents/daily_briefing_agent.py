"""
Mata Garuda — Daily Briefing Agent.

Every morning 07:00 WITA, aggregates the last 24h of enriched-stream items
by domain, picks top 5 per domain by relevance_score, generates a compact
Markdown briefing and sends it to Zero via Telegram.

Design:
  * Deterministic worker-style (no LLM reasoning for aggregation).
  * Optional per-item TL;DR via Claude CLI (briefing spec — max 2 lines).
    If Claude CLI unavailable / rate-limited, falls back to first 160 chars
    of content.
  * Reads from `garuda:enriched` via XREVRANGE with a 24h window filter
    (we parse `created_at`/`timestamp` field — enriched items carry a
    normalized timestamp via normalizer.py).
  * Also registers a Layer-4 Agent in the MG registry so it shows up in
    `get_agents_status`, but the operational path is the deterministic
    runner below.

Layer 4 Analista. Autonomy: L1 (send to Zero every morning).
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mata_garuda.config import (
    RELEVANCE_WEIGHTS,
    STREAM_DIGEST,
    STREAM_ENRICHED,
    TG_ZERO_CHAT_ID,
)
from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.tools.knowledge_tools import kb_search, kb_store
from mata_garuda.tools.stream_tools import stream_publish
from mata_garuda.tools.tg_tools import send_tg_alert
from mata_garuda.types import Agent
from mata_garuda.workers.base_worker import redis_cmd

logger = logging.getLogger("mata_garuda.agents.daily_briefing")

GENOME_FILE = str(Path(__file__).parent / "daily_briefing_agent_GENOME.md")

DOMAIN_LABELS = {
    "immigration_visa": "🛂 Immigration & Visa",
    "tax_fiscal": "💼 Tax & Fiscal",
    "investment_licensing": "📄 Investment & Licensing",
    "labor_manpower": "👷 Labor & Manpower",
    "provincial_bali": "🌴 Bali Provincial",
    "financial_banking": "🏦 Financial & Banking",
    "property": "🏠 Property",
    "environmental": "🌿 Environmental",
    "ai_research": "🧠 AI Research",
    "political_risk": "📰 Politics & Press",
    "procurement": "📦 Procurement",
    "other": "🔹 Other",
}


# ── low-level: enriched stream window read ────────────────────────────────


def _xrevrange(stream: str, count: int = 200) -> list[dict[str, Any]]:
    """Read up to ``count`` most-recent items from ``stream`` (XREVRANGE).

    Returns list of {id, data} dicts. Parses redis-cli flat output — same
    heuristic as workers.base_worker but scoped to XREVRANGE.
    """
    raw = redis_cmd("XREVRANGE", stream, "+", "-", "COUNT", str(count), timeout=15)
    if not raw or raw.startswith("[ERROR]"):
        return []

    items: list[dict[str, Any]] = []
    lines = [line for line in raw.split("\n") if line.strip()]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-" in line and line[0].isdigit():
            msg_id = line
            data: dict[str, str] = {}
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if "-" in nxt and nxt[0].isdigit():
                    break
                if j + 1 < len(lines):
                    key = nxt
                    val = lines[j + 1].strip()
                    data[key] = val
                    j += 2
                else:
                    break
            items.append({"id": msg_id, "data": data})
            i = j
        else:
            i += 1
    return items


def _parse_ts(data: dict[str, str]) -> datetime | None:
    """Pick a best-effort timestamp from an enriched stream row."""
    for key in ("normalized_at", "timestamp", "alert_time", "created_at"):
        v = data.get(key)
        if not v:
            continue
        try:
            # datetime.fromisoformat handles most variants incl. '+00:00'
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue
    return None


def _last_24h_by_domain(
    items: list[dict[str, Any]],
    now: datetime | None = None,
    top_n: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    """Group items by domain, filter last 24h, return top N per domain.

    Items without a parseable timestamp are INCLUDED (defensive — better to
    over-include than silently drop). Items are sorted by relevance_score
    desc (missing → 0).
    """
    now = now or datetime.now(timezone.utc)
    horizon = now - timedelta(hours=24)
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for it in items:
        data = it.get("data") or {}
        ts = _parse_ts(data)
        if ts is not None and ts < horizon:
            continue
        domain = (data.get("domain") or data.get("topic") or "other").strip() or "other"
        by_domain[domain].append(data)

    def _score(d: dict[str, str]) -> float:
        for k in ("relevance_score", "score", "weighted_score"):
            v = d.get(k)
            if v is None:
                continue
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
        return float(RELEVANCE_WEIGHTS.get(d.get("domain", ""), 0))

    return {
        domain: sorted(rows, key=_score, reverse=True)[:top_n]
        for domain, rows in by_domain.items()
    }


# ── per-item TL;DR via Claude CLI (optional) ─────────────────────────────


def _tldr_claude(title: str, content: str) -> str:
    """Call Claude CLI to produce a max-2-line TL;DR. Returns empty on any failure.

    Respects briefing rate limits by skipping if no OAUTH token is set or
    Claude is unavailable. Falls back silently.
    """
    if not content:
        return ""
    token_vars = [
        "CLAUDE_CODE_OAUTH_TOKEN_1",
        "CLAUDE_CODE_OAUTH_TOKEN_2",
        "CLAUDE_CODE_OAUTH_TOKEN_3",
        "CLAUDE_CODE_OAUTH_TOKEN",
    ]
    for var in token_vars:
        token = os.environ.get(var)
        if not token:
            continue
        env = os.environ.copy()
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
        prompt = (
            f"Riassumi in MAX 2 righe (italiano, tecnico) questo item:\n"
            f"Titolo: {title}\nContenuto: {content[:800]}\n"
            f"Output: solo il riassunto, niente prefissi."
        )
        try:
            result = subprocess.run(
                ["claude", "--print", "-p", prompt],
                capture_output=True, text=True, timeout=45, env=env,
            )
            out = (result.stdout or "").strip()
            if result.returncode == 0 and out:
                if out.startswith("[Pro]") or out.startswith("[Air]"):
                    out = out.split("\n", 1)[-1].strip()
                return out.splitlines()[0:2] and "\n".join(out.splitlines()[:2]) or out
            if "hit your limit" in (result.stderr + result.stdout).lower():
                continue
        except Exception:
            continue
    return ""


def _fallback_tldr(content: str, limit: int = 160) -> str:
    if not content:
        return ""
    first_line = content.strip().splitlines()[0] if content.strip() else ""
    return (first_line[:limit] + ("…" if len(first_line) > limit else ""))


# ── briefing assembly ─────────────────────────────────────────────────────


def build_briefing_md(
    grouped: dict[str, list[dict[str, Any]]],
    now: datetime | None = None,
    use_claude_tldr: bool = True,
) -> str:
    """Build the Markdown briefing body."""
    now = now or datetime.now(timezone.utc)
    header = f"# Daily Intelligence Briefing — {now.strftime('%Y-%m-%d')}"

    if not grouped:
        return (
            f"{header}\n\n📭 Giornata silenziosa — nessun item nell'enriched "
            f"stream nelle ultime 24h.\n\nMata Garuda · Daily Briefing"
        )

    lines = [header, ""]
    # Deterministic order: domains by weight desc, then alpha
    def _domain_sort_key(d: str) -> tuple[int, str]:
        return (-RELEVANCE_WEIGHTS.get(d, 0), d)

    for domain in sorted(grouped.keys(), key=_domain_sort_key):
        rows = grouped[domain]
        label = DOMAIN_LABELS.get(domain, f"🔹 {domain}")
        lines.append(f"## {label} ({len(rows)} items)")
        for r in rows:
            title = (r.get("title") or "(senza titolo)").strip()[:180]
            source = (r.get("source") or "").strip()
            url = (r.get("url") or "").strip()
            score_raw = r.get("relevance_score") or r.get("score") or "?"
            content = r.get("content") or ""
            tldr = _tldr_claude(title, content) if use_claude_tldr else ""
            if not tldr:
                tldr = _fallback_tldr(content)
            meta_bits = [b for b in [source, f"score {score_raw}"] if b]
            lines.append(f"- **{title}** — {' · '.join(meta_bits)}")
            if url:
                lines.append(f"  → {url}")
            if tldr:
                lines.append(f"  TL;DR: {tldr}")
        lines.append("")

    lines.append("_Mata Garuda · Daily Briefing · L4 Analista_")
    return "\n".join(lines)


# ── telegram delivery (with chunking) ────────────────────────────────────


TG_MAX_CHARS = 3800  # Telegram sendMessage hard limit 4096 — leave margin


def _send_telegram(text: str, dry_run: bool = False) -> bool:
    """Send text to Zero's TG. Chunks if > TG_MAX_CHARS. Returns overall ok."""
    if dry_run:
        logger.info(f"[DRY-RUN] would send TG ({len(text)} chars)")
        return True
    chunks = [text[i:i + TG_MAX_CHARS] for i in range(0, len(text), TG_MAX_CHARS)] or [""]
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("[daily_briefing] TELEGRAM_BOT_TOKEN not set")
        return False
    ok_all = True
    for chunk in chunks:
        try:
            result = subprocess.run(
                [
                    "curl", "-s",
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    "-d", f"chat_id={TG_ZERO_CHAT_ID}",
                    "--data-urlencode", f"text={chunk}",
                ],
                capture_output=True, text=True, timeout=15,
            )
            if '"ok":true' not in (result.stdout or ""):
                ok_all = False
                logger.error(f"[daily_briefing] TG send failed: {result.stdout[:200]}")
        except Exception as e:
            logger.error(f"[daily_briefing] TG send exception: {e}")
            ok_all = False
    return ok_all


# ── operational entrypoint ────────────────────────────────────────────────


def run_daily_briefing(
    kb: KnowledgeBase | None = None,
    *,
    now: datetime | None = None,
    use_claude_tldr: bool = True,
    dry_run: bool = False,
    max_stream_items: int = 200,
) -> dict:
    """Generate and deliver the daily briefing. Returns stats dict."""
    own_kb = False
    if kb is None:
        kb = KnowledgeBase()
        own_kb = True

    try:
        items = _xrevrange(STREAM_ENRICHED, count=max_stream_items)
        grouped = _last_24h_by_domain(items, now=now)
        briefing = build_briefing_md(grouped, now=now, use_claude_tldr=use_claude_tldr)

        tg_ok = _send_telegram(briefing, dry_run=dry_run)

        if not dry_run:
            # Publish to digest stream for observability + KB audit trail
            try:
                stream_publish(
                    title=f"Daily Briefing — {(now or datetime.now(timezone.utc)).strftime('%Y-%m-%d')}",
                    url="garuda:digest",
                    source="daily_briefing_agent",
                    content=briefing,
                    stream=STREAM_DIGEST,
                )
            except Exception as e:
                logger.warning(f"[daily_briefing] stream_publish failed: {e}")
            try:
                kb.store(
                    "daily_briefing_agent", "briefing",
                    briefing[:6000], "daily_run", 0.9,
                )
            except Exception as e:
                logger.warning(f"[daily_briefing] kb.store failed: {e}")

        n_items = sum(len(v) for v in grouped.values())
        n_domains = len(grouped)
        return {
            "domains": n_domains,
            "items": n_items,
            "chars": len(briefing),
            "tg_ok": tg_ok,
            "dry_run": dry_run,
        }
    finally:
        if own_kb:
            try:
                kb.close()
            except Exception:
                pass


# ── Agent registration (for registry visibility) ─────────────────────────


@register_agent(name="Daily Briefing Agent", func_name="get_daily_briefing_agent")
def get_daily_briefing_agent(model: str = "claude") -> Agent:
    """Returns the registered Agent stub. Operational work is
    ``run_daily_briefing()`` invoked from the cron script.
    """

    def instructions(context_variables: dict) -> str:  # pragma: no cover
        return (
            "You are the Daily Briefing Agent for Mata Garuda. Each morning "
            "at 07:00 WITA you aggregate last-24h enriched items by domain "
            "(top 5/domain by relevance_score), render a Markdown briefing, "
            "and send it to Zero via Telegram. Deterministic aggregation; "
            "optional Claude CLI TL;DR per item (max 2 lines)."
        )

    return Agent(
        name="Daily Briefing Agent",
        model=model,
        instructions=instructions,
        functions=[
            kb_search, kb_store, stream_publish,
            send_tg_alert, case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="analista",
    )
