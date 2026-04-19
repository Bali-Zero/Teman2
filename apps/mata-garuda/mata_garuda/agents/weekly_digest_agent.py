"""
Mata Garuda — Weekly Digest Agent.

Every Sunday 08:00 WITA, aggregates the last 7 days of enriched-stream
items, asks Claude CLI for a cross-domain strategic digest (top trends,
risks, opportunities), and sends the result to Zero via Telegram.

Layer 4 Analista. Autonomy L1.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mata_garuda.agents.daily_briefing_agent import _send_telegram, _xrevrange
from mata_garuda.config import RELEVANCE_WEIGHTS, STREAM_DIGEST, STREAM_ENRICHED
from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.tools.knowledge_tools import kb_search, kb_store
from mata_garuda.tools.stream_tools import stream_publish
from mata_garuda.tools.tg_tools import send_tg_alert
from mata_garuda.types import Agent
from mata_garuda.workers.base_worker import redis_cmd  # noqa: F401 — re-used by _xrevrange

logger = logging.getLogger("mata_garuda.agents.weekly_digest")

GENOME_FILE = str(Path(__file__).parent / "weekly_digest_agent_GENOME.md")


def _parse_ts(data: dict[str, str]) -> datetime | None:
    for key in ("normalized_at", "timestamp", "alert_time", "created_at"):
        v = data.get(key)
        if not v:
            continue
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue
    return None


def _score(data: dict[str, str]) -> float:
    for k in ("relevance_score", "score", "weighted_score"):
        v = data.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return float(RELEVANCE_WEIGHTS.get(data.get("domain", ""), 0))


def filter_last_7_days(
    items: list[dict[str, Any]],
    now: datetime | None = None,
    top_n: int = 80,
) -> list[dict[str, str]]:
    """Return up to ``top_n`` items from the last 7 days, ordered by score desc."""
    now = now or datetime.now(timezone.utc)
    horizon = now - timedelta(days=7)
    rows: list[dict[str, str]] = []
    for it in items:
        data = it.get("data") or {}
        ts = _parse_ts(data)
        if ts is not None and ts < horizon:
            continue
        rows.append(data)
    rows.sort(key=_score, reverse=True)
    return rows[:top_n]


def build_analysis_prompt(rows: list[dict[str, str]], now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    week_label = now.strftime("%Y-W%V")
    corpus_lines: list[str] = []
    for r in rows:
        title = (r.get("title") or "").strip()[:160]
        domain = (r.get("domain") or r.get("topic") or "").strip()
        src = (r.get("source") or "").strip()
        url = (r.get("url") or "").strip()
        score = _score(r)
        body = (r.get("content") or "").strip().replace("\n", " ")[:300]
        corpus_lines.append(
            f"- [{domain} | score {score:.1f}] {title} — {src}\n  {body}\n  {url}"
        )
    corpus = "\n".join(corpus_lines) if corpus_lines else "(nessun dato)"
    return (
        f"Sei l'analista strategico di Mata Garuda. Settimana {week_label}.\n"
        f"Questi sono i {len(rows)} item più rilevanti dello stream enriched:\n\n"
        f"{corpus}\n\n"
        "Compito: analizza questa settimana in ambito compliance/business indonesiano.\n"
        "Identifica:\n"
        "- Top 3 TRENDS (con evidenza testuale dai titoli sopra)\n"
        "- Top 3 RISKS\n"
        "- Top 3 OPPORTUNITIES\n"
        "MAX 500 parole totali. Markdown. Italiano tecnico.\n"
        "Cita titoli ESATTI dai dati, mai inventare."
    )


def call_claude(prompt: str, timeout: int = 120) -> str:
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
        try:
            result = subprocess.run(
                ["claude", "--print", "-p", prompt],
                capture_output=True, text=True, timeout=timeout, env=env,
            )
            out = (result.stdout or "").strip()
            if result.returncode == 0 and out:
                if out.startswith("[Pro]") or out.startswith("[Air]"):
                    out = out.split("\n", 1)[-1].strip()
                return out
            if "hit your limit" in (result.stderr + result.stdout).lower():
                continue
        except Exception:
            continue
    return ""


def fallback_digest(rows: list[dict[str, str]], now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    header = f"# Weekly Digest — {now.strftime('%Y-W%V')}  (Claude CLI non disponibile)"
    if not rows:
        return f"{header}\n\n📭 Settimana silenziosa — nessun item."
    lines = [header, "", "## Top 10 item per rilevanza"]
    for r in rows[:10]:
        title = (r.get("title") or "").strip()[:120]
        domain = (r.get("domain") or r.get("topic") or "").strip()
        score = _score(r)
        url = (r.get("url") or "").strip()
        lines.append(f"- [{domain} | {score:.1f}] {title}")
        if url:
            lines.append(f"  → {url}")
    return "\n".join(lines)


def run_weekly_digest(
    kb: KnowledgeBase | None = None,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
    max_stream_items: int = 1000,
    use_claude: bool = True,
) -> dict:
    """Generate and deliver the weekly digest. Returns stats."""
    now = now or datetime.now(timezone.utc)
    own_kb = False
    if kb is None:
        kb = KnowledgeBase()
        own_kb = True

    try:
        raw = _xrevrange(STREAM_ENRICHED, count=max_stream_items)
        rows = filter_last_7_days(raw, now=now)

        digest = ""
        if use_claude and rows:
            prompt = build_analysis_prompt(rows, now=now)
            digest = call_claude(prompt)

        if not digest:
            digest = fallback_digest(rows, now=now)

        # Prepend header for TG clarity
        header = f"📅 WEEKLY DIGEST — {now.strftime('%Y-%m-%d')} (W{now.strftime('%V')})\n\n"
        body = header + digest

        tg_ok = _send_telegram(body, dry_run=dry_run)

        if not dry_run:
            try:
                stream_publish(
                    title=f"Weekly Digest — {now.strftime('%Y-W%V')}",
                    url="garuda:digest",
                    source="weekly_digest_agent",
                    content=body,
                    stream=STREAM_DIGEST,
                )
            except Exception as e:
                logger.warning(f"[weekly_digest] stream_publish failed: {e}")
            try:
                kb.store(
                    "weekly_digest_agent", "weekly_digest",
                    body[:6000], "weekly_run", 0.9,
                )
            except Exception as e:
                logger.warning(f"[weekly_digest] kb.store failed: {e}")

        return {
            "items": len(rows),
            "chars": len(body),
            "tg_ok": tg_ok,
            "dry_run": dry_run,
            "used_claude": bool(digest and not digest.startswith("# Weekly Digest")),
        }
    finally:
        if own_kb:
            try:
                kb.close()
            except Exception:
                pass


@register_agent(name="Weekly Digest Agent", func_name="get_weekly_digest_agent")
def get_weekly_digest_agent(model: str = "claude") -> Agent:
    def instructions(context_variables: dict) -> str:  # pragma: no cover
        return (
            "You are the Weekly Digest Agent for Mata Garuda. Every Sunday "
            "at 08:00 WITA you aggregate the last-7-days enriched stream "
            "(top 80 items by relevance), ask Claude CLI for a strategic "
            "analysis (top 3 trends/risks/opportunities, ≤500 words), and "
            "send the Markdown digest to Zero via Telegram. Falls back to "
            "top-10 raw list if Claude CLI unavailable."
        )

    return Agent(
        name="Weekly Digest Agent",
        model=model,
        instructions=instructions,
        functions=[
            kb_search, kb_store, stream_publish,
            send_tg_alert, case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="analista",
    )
