"""
Mata Garuda — NLM Expander Agent (L2 autonomy).

Weekly scan. If a domain has been producing >50 enriched items over the
last 30 days but isn't mapped to an NLM notebook in
`config.NLM_DOMAIN_ROUTING`, propose to Zero (via Telegram) that a new
NB-INTEL-{X} be created. Also flags mapped notebooks that appear stale
(no fed entries in KB for 30+ days).

Each proposal is enriched with the top public titles + URLs that compose
the domain (volume signal for Zero). ONLY public titles/URLs are surfaced
— NEVER raw OSINT body/content (Symbiosis Law 2).

AUTO-CREATE (L2+): when a domain crosses the HIGH threshold
(``AUTO_CREATE_THRESHOLD`` items/30d) the agent auto-creates an EMPTY NB
container via ``nlm notebook create`` (CLI subprocess), with a KB-backed
cooldown so the same domain is never auto-created twice. It NEVER feeds
sources into the new NB (auto-feed would push raw OSINT to the cloud —
forbidden by Law 2) and NEVER merges/deletes notebooks. Population is
manual / left to the feeder.

CRITICAL: below AUTO_CREATE_THRESHOLD this agent only PROPOSES — a human
(Zero) decides via Telegram reply. The auto-create container is empty by
design and still requires human/feeder population.

Layer 4 Analista.
"""
from __future__ import annotations

import logging
import re
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mata_garuda.agents.daily_briefing_agent import _send_telegram, _xrevrange
from mata_garuda.config import NLM_DOMAIN_ROUTING, NLM_NOTEBOOKS, STREAM_ENRICHED
from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.tools.knowledge_tools import kb_search, kb_store
from mata_garuda.tools.tg_tools import send_tg_alert
from mata_garuda.types import Agent

logger = logging.getLogger("mata_garuda.agents.nlm_expander")

GENOME_FILE = str(Path(__file__).parent / "nlm_expander_agent_GENOME.md")

DEFAULT_PROPOSAL_THRESHOLD = 50   # items in 30d → proposal-worthy
DEFAULT_STALE_DAYS = 30           # NB unused for this many days → stale flag
AUTO_CREATE_THRESHOLD = 100       # items in 30d → auto-create EMPTY NB container
TOP_ITEMS_PER_DOMAIN = 3          # public titles+URLs surfaced per proposal
NB_CREATE_STATUS = "nb_created"   # KB type used as auto-create cooldown marker
NB_CREATE_AGENT = "nlm_expander_agent"  # KB agent for cooldown lookups


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


def count_domains_last_30d(
    items: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, int]:
    """Count enriched items per domain over the last 30 days."""
    now = now or datetime.now(timezone.utc)
    horizon = now - timedelta(days=30)
    counts: Counter[str] = Counter()
    for it in items:
        data = it.get("data") or {}
        ts = _parse_ts(data)
        if ts is not None and ts < horizon:
            continue
        domain = (data.get("domain") or data.get("topic") or "").strip()
        if domain:
            counts[domain] += 1
    return dict(counts)


def find_proposal_candidates(
    counts: dict[str, int],
    threshold: int = DEFAULT_PROPOSAL_THRESHOLD,
) -> list[tuple[str, int]]:
    """Return (domain, count) pairs where count>=threshold AND domain is
    NOT already mapped in NLM_DOMAIN_ROUTING.
    """
    candidates = []
    for domain, n in counts.items():
        if n < threshold:
            continue
        if domain in NLM_DOMAIN_ROUTING:
            continue
        candidates.append((domain, n))
    # Highest volume first
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates


def find_stale_notebooks(
    kb: KnowledgeBase,
    now: datetime | None = None,
    stale_days: int = DEFAULT_STALE_DAYS,
) -> list[str]:
    """Return nb_key names whose `nlm_fed` KB entries have no activity in
    the last ``stale_days``. Ignores notebooks with empty IDs."""
    now = now or datetime.now(timezone.utc)
    horizon = now - timedelta(days=stale_days)
    stale: list[str] = []

    try:
        cursor = kb._conn.execute(
            "SELECT MAX(created_at) FROM knowledge "
            "WHERE agent = 'nlm_feeder' AND type = 'nlm_fed'"
        )
        row = cursor.fetchone()
    except Exception:
        return []

    # If there's NEVER been a fed entry, every configured NB is stale
    last_fed = None
    if row and row[0]:
        try:
            last_fed = datetime.fromisoformat(str(row[0]).replace(" ", "T"))
            if last_fed.tzinfo is None:
                last_fed = last_fed.replace(tzinfo=timezone.utc)
        except Exception:
            last_fed = None

    for nb_key, nb_id in NLM_NOTEBOOKS.items():
        if not nb_id:
            continue
        if last_fed is None or last_fed < horizon:
            stale.append(nb_key)
    return stale


def top_public_items_for_domain(
    items: list[dict[str, Any]],
    domain: str,
    now: datetime | None = None,
    limit: int = TOP_ITEMS_PER_DOMAIN,
) -> list[tuple[str, str]]:
    """Return up to ``limit`` (title, url) pairs for ``domain`` over the
    last 30 days.

    SYMBIOSIS Law 2: only PUBLIC fields (``title`` + ``url``) are read —
    NEVER ``content``/body or any raw OSINT field. ``items`` are the same
    {id, data} rows produced by ``_xrevrange`` (newest-first), so we keep
    that ordering as the "top" signal and de-duplicate on URL.
    """
    now = now or datetime.now(timezone.utc)
    horizon = now - timedelta(days=30)
    out: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for it in items:
        data = it.get("data") or {}
        ts = _parse_ts(data)
        if ts is not None and ts < horizon:
            continue
        item_domain = (data.get("domain") or data.get("topic") or "").strip()
        if item_domain != domain:
            continue
        # ONLY public fields — title + url. Never data.get("content").
        title = (data.get("title") or "(untitled)").strip()[:160]
        url = (data.get("url") or "").strip()
        dedup_key = url or title
        if dedup_key in seen_urls:
            continue
        seen_urls.add(dedup_key)
        out.append((title, url))
        if len(out) >= limit:
            break
    return out


def _domain_to_nb_title(domain: str) -> str:
    """Derive a stable, human-readable NB title from a domain slug."""
    pretty = re.sub(r"[_\-]+", " ", domain).strip().title()
    return f"NB-INTEL {pretty}"


def domain_recently_auto_created(
    kb: KnowledgeBase,
    domain: str,
    cooldown_days: int = 30,
    now: datetime | None = None,
) -> bool:
    """Return True if ``domain`` already has a recent auto-create / proposal
    marker in the KB (anti-spam cooldown).

    Matches any `nb_created` OR `proposal` entry whose ``source`` is the
    domain slug, created within ``cooldown_days``. Prevents auto-creating the
    same NB container twice. Best-effort: any DB error → treat as NOT recent
    (favour surfacing over silent skip, but never hard-fail the run)."""
    now = now or datetime.now(timezone.utc)
    try:
        cursor = kb._conn.execute(
            "SELECT 1 FROM knowledge "
            "WHERE agent = ? AND type IN (?, ?) AND source = ? "
            "AND created_at > datetime('now', ?) LIMIT 1",
            (
                NB_CREATE_AGENT,
                NB_CREATE_STATUS,
                "proposal",
                domain,
                f"-{cooldown_days} days",
            ),
        )
        return cursor.fetchone() is not None
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"[nlm_expander] cooldown lookup failed for {domain}: {e}")
        return False


def _create_empty_notebook(title: str, dry_run: bool = False) -> tuple[bool, str]:
    """Create an EMPTY NB container via the `nlm notebook create` CLI.

    CLI-only (mata-garuda never imports the NLM SDK). Returns
    ``(ok, uuid_or_message)``. In ``dry_run`` no subprocess is invoked.

    Does NOT feed any source (auto-feed would leak raw OSINT to cloud —
    Law 2) and does NOT merge/delete notebooks.
    """
    if dry_run:
        logger.info(f"[nlm_expander] dry_run: would create empty NB '{title}'")
        return True, "(dry-run)"
    try:
        result = subprocess.run(
            ["nlm", "notebook", "create", title],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            out = (result.stdout or "").strip()
            # Best-effort UUID extraction from CLI stdout.
            m = re.search(
                r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                out,
            )
            uuid = m.group(0) if m else (out[:80] or "(unknown-uuid)")
            return True, uuid
        return False, (result.stderr or "")[:200]
    except FileNotFoundError:
        return False, "nlm CLI not found"
    except subprocess.TimeoutExpired:
        return False, "nlm notebook create timeout (60s)"
    except Exception as e:  # pragma: no cover - defensive
        return False, f"nlm notebook create failed: {e}"


def build_proposal_message(
    candidates: list[tuple[str, int]],
    stale: list[str],
    now: datetime | None = None,
    *,
    items: list[dict[str, Any]] | None = None,
    auto_created: list[dict[str, str]] | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    items = items or []
    auto_created = auto_created or []
    lines = [
        f"🧭 NLM EXPANDER — {now.strftime('%Y-%m-%d')}",
        "",
    ]
    if candidates:
        lines.append("**Propongo nuovi notebook:**")
        for domain, n in candidates:
            lines.append(f"• `{domain}` — {n} item/30gg (non mappato)")
            # Volume signal: ONLY public titles + URLs (Law 2 — no body).
            top = top_public_items_for_domain(items, domain, now=now)
            for title, url in top:
                if url:
                    lines.append(f"    – {title} — {url}")
                else:
                    lines.append(f"    – {title}")
        lines.append("")
        lines.append("Rispondi `y <domain>` per approvare la creazione, `n <domain>` per ignorare.")
    if auto_created:
        lines.append("")
        for nb in auto_created:
            lines.append(
                f"✅ Auto-creato NB vuoto: {nb.get('title', '?')} "
                f"({nb.get('uuid', '?')}) — va popolato manualmente / dal feeder"
            )
    if stale:
        lines.append("")
        lines.append(f"**NB stali (>{DEFAULT_STALE_DAYS}gg senza feed):** {', '.join(stale)}")
    if not candidates and not stale and not auto_created:
        lines.append("Niente da proporre — coverage stabile, feed attivo.")
    lines.append("")
    lines.append(
        "_L2 autonomy: proposte + auto-create solo contenitore vuoto "
        "(>=100 item/30gg). Mai feed/merge/delete. NB creati vanno popolati._"
    )
    return "\n".join(lines)


def run_nlm_expander(
    kb: KnowledgeBase | None = None,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
    max_stream_items: int = 2000,
    proposal_threshold: int = DEFAULT_PROPOSAL_THRESHOLD,
    auto_create_threshold: int = AUTO_CREATE_THRESHOLD,
) -> dict:
    """Scan enriched stream for unmapped high-volume domains and stale NBs.

    For domains over ``proposal_threshold`` → propose (with top public
    titles+URLs). For domains over ``auto_create_threshold`` AND not under
    cooldown → auto-create an EMPTY NB container via `nlm notebook create`.

    Returns stats: {domains_seen, candidates, stale, auto_created, tg_ok,
    dry_run, sent}. NEVER feeds sources, NEVER merges/deletes notebooks.
    """
    now = now or datetime.now(timezone.utc)
    own_kb = False
    if kb is None:
        kb = KnowledgeBase()
        own_kb = True

    try:
        items = _xrevrange(STREAM_ENRICHED, count=max_stream_items)
        counts = count_domains_last_30d(items, now=now)
        candidates = find_proposal_candidates(counts, threshold=proposal_threshold)
        stale = find_stale_notebooks(kb, now=now)

        # B) Auto-create EMPTY NB container for very-high-volume domains,
        # gated by cooldown so the same domain is never created twice.
        auto_created: list[dict[str, str]] = []
        for domain, n in candidates:
            if n < auto_create_threshold:
                continue
            if domain_recently_auto_created(kb, domain, now=now):
                logger.info(
                    f"[nlm_expander] skip auto-create '{domain}' "
                    f"({n} item) — cooldown active"
                )
                continue
            title = _domain_to_nb_title(domain)
            ok, uuid = _create_empty_notebook(title, dry_run=dry_run)
            if not ok:
                logger.warning(
                    f"[nlm_expander] auto-create failed for '{domain}': {uuid}"
                )
                continue
            auto_created.append({"domain": domain, "title": title, "uuid": uuid})
            logger.info(
                f"[nlm_expander] auto-created empty NB '{title}' ({uuid}) "
                f"for domain '{domain}' ({n} item/30gg, dry_run={dry_run})"
            )
            # Log to KB as cooldown marker (source = domain slug for lookup).
            if not dry_run:
                try:
                    kb.store(
                        NB_CREATE_AGENT, NB_CREATE_STATUS,
                        f"auto-created empty NB '{title}' ({uuid}) for "
                        f"domain '{domain}' ({n} item/30gg)",
                        domain, 0.8,
                    )
                except Exception as e:
                    logger.warning(f"[nlm_expander] kb.store(nb_created) failed: {e}")

        should_send = bool(candidates or stale or auto_created)
        tg_ok = True
        if should_send:
            msg = build_proposal_message(
                candidates, stale, now=now,
                items=items, auto_created=auto_created,
            )
            tg_ok = _send_telegram(msg, dry_run=dry_run)
            if not dry_run:
                try:
                    kb.store(
                        "nlm_expander_agent", "proposal",
                        msg[:4000], "weekly_scan", 0.7,
                    )
                except Exception as e:
                    logger.warning(f"[nlm_expander] kb.store failed: {e}")

        return {
            "domains_seen": len(counts),
            "candidates": [{"domain": d, "count": n} for d, n in candidates],
            "stale": stale,
            "auto_created": auto_created,
            "tg_ok": tg_ok,
            "dry_run": dry_run,
            "sent": should_send,
        }
    finally:
        if own_kb:
            try:
                kb.close()
            except Exception:
                pass


@register_agent(name="NLM Expander Agent (L2)", func_name="get_nlm_expander_agent")
def get_nlm_expander_agent(model: str = "claude") -> Agent:
    def instructions(context_variables: dict) -> str:  # pragma: no cover
        return (
            "You are the NLM Expander Agent (L2 autonomy) for Mata Garuda. "
            "Weekly, scan the enriched stream for domains with >50 items/30d "
            "that aren't already mapped in NLM_DOMAIN_ROUTING, and flag "
            "notebooks that haven't been fed in 30+ days. PROPOSE to Zero "
            "via Telegram — DO NOT create notebooks autonomously. Zero "
            "approves by TG reply."
        )

    return Agent(
        name="NLM Expander Agent (L2)",
        model=model,
        instructions=instructions,
        functions=[
            kb_search, kb_store,
            send_tg_alert, case_resolved, case_not_resolved,
        ],
        genome_path=GENOME_FILE,
        layer="analista",
    )
