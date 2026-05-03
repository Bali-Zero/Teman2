"""DB→NLM Markdown templates.

Converts raw SQL query results (list of dicts / asyncpg Records)
into narrative Markdown that NLM can reason about.

No Jinja2 dependency — pure f-strings.

Security: NEVER include PII (email, phone, passport, tax_id).
All references use client IDs or company names only.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def _fmt_idr(amount: Any) -> str:
    """Format IDR currency."""
    if amount is None:
        return "N/A"
    try:
        return f"IDR {int(amount):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(amount)


def _fmt_date(dt: Any) -> str:
    """Format a date/datetime to YYYY-MM-DD."""
    if dt is None:
        return "N/A"
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")
    return str(dt)[:10]


def _pct(part: int, total: int) -> str:
    """Safe percentage."""
    if total == 0:
        return "0%"
    return f"{part * 100 / total:.0f}%"


def _trend_arrow(current: int | float | None, previous: int | float | None, threshold_pct: float = 25.0) -> str:
    """Return trend indicator: ▲/▼/→ with delta percentage and anomaly flag."""
    if current is None or previous is None:
        return "→ N/A"
    if previous == 0:
        return f"▲ NEW ({current})" if current > 0 else "→ 0"
    delta_pct = (current - previous) / previous * 100
    if abs(delta_pct) < 5:
        arrow = "→"
    elif delta_pct > 0:
        arrow = "▲"
    else:
        arrow = "▼"
    anomaly = " ⚠️ ANOMALIA" if abs(delta_pct) >= threshold_pct else ""
    return f"{arrow} {delta_pct:+.0f}%{anomaly}"


def _delta_line(label: str, current: int | float | None, previous: int | float | None, fmt: str = "int") -> str:
    """Format a single metric with trend for use in templates."""
    curr_str = _fmt_idr(current) if fmt == "idr" else (str(int(current)) if current is not None else "N/A")
    trend = _trend_arrow(current, previous)
    return f"- **{label}**: {curr_str} (vs settimana scorsa: {trend})"


# ---------------------------------------------------------------------------
# NB-OPS: Bali Zero Ops Live
# ---------------------------------------------------------------------------

def render_portfolio_snapshot(
    stats: dict[str, Any],
    segments: list[dict[str, Any]],
    nationalities: list[dict[str, Any]],
    today: str,
    prev_stats: dict[str, Any] | None = None,
    at_risk_clients: list[dict[str, Any]] | None = None,
    upcoming_deadlines: list[dict[str, Any]] | None = None,
) -> str:
    """Source 1: Client portfolio overview with trend comparison."""
    active = stats.get("active", 0)
    total = stats.get("total", 0)
    new_7d = stats.get("new_7d", 0)
    new_30d = stats.get("new_30d", 0)
    prospect = stats.get("prospect", 0)

    seg_lines = []
    for s in segments[:10]:
        seg_lines.append(
            f"- **{s['category']}**: {s['clients']} clients, "
            f"{_pct(s['clients'], active)} of active, "
            f"pipeline value {_fmt_idr(s.get('pipeline_value', 0))}"
        )

    nat_lines = []
    for n in nationalities[:10]:
        nat_lines.append(f"- {n['nationality']}: {n['count']} clients")

    # Trend section (requires prev_stats)
    trend_section = ""
    if prev_stats:
        trend_lines = [
            _delta_line("Active clients", active, prev_stats.get("active")),
            _delta_line("New this week", new_7d, prev_stats.get("new_7d")),
            _delta_line("Prospects", prospect, prev_stats.get("prospect")),
        ]
        trend_section = f"""
## Confronto Settimana Precedente
{chr(10).join(trend_lines)}
"""

    # At-risk clients section
    risk_section = ""
    if at_risk_clients:
        risk_lines = []
        for c in at_risk_clients[:10]:
            risk_lines.append(
                f"- Client #{c.get('client_id', '?')} ({c.get('nationality', '?')}): "
                f"{c.get('open_practices', 0)} pratiche aperte, "
                f"ultima attività {_fmt_date(c.get('last_activity'))}"
            )
        risk_section = f"""
## Clienti con Pratiche in Ritardo ({len(at_risk_clients)} totali)
{chr(10).join(risk_lines)}
"""

    # Upcoming deadlines section
    deadline_section = ""
    if upcoming_deadlines:
        deadline_lines = []
        for d in upcoming_deadlines[:15]:
            deadline_lines.append(
                f"- Client #{d.get('client_id', '?')}: {d.get('practice_type', '?')} "
                f"scade {_fmt_date(d.get('deadline'))} "
                f"({d.get('days_remaining', '?')} giorni)"
            )
        deadline_section = f"""
## Scadenze Prossimi 30 Giorni ({len(upcoming_deadlines)} totali)
{chr(10).join(deadline_lines)}
"""

    return f"""# Client Portfolio Snapshot — {today}

## Summary
- **{active}** active clients (total: {total})
- **{new_7d}** new in last 7 days, **{new_30d}** in last 30 days
- **{prospect}** prospects (not yet converted)
{trend_section}
## Segments by Service Category
{chr(10).join(seg_lines) if seg_lines else '- No active practices'}

## Top Nationalities
{chr(10).join(nat_lines) if nat_lines else '- No data'}
{risk_section}{deadline_section}
---
*Auto-generated from Nuzantara CRM database. Updated {today}.*
"""


def render_practices_pipeline(
    by_status: list[dict[str, Any]],
    bottlenecks: list[dict[str, Any]],
    avg_duration: list[dict[str, Any]],
    today: str,
    prev_by_status: list[dict[str, Any]] | None = None,
) -> str:
    """Source 2: Practice pipeline status with trend comparison."""
    status_lines = []
    total_practices = 0
    status_map: dict[str, int] = {}
    for s in by_status:
        count = s.get("count", 0)
        total_practices += count
        status_map[s["status"]] = count
        status_lines.append(f"- **{s['status']}**: {count} practices")

    bottleneck_lines = []
    for b in bottlenecks[:10]:
        days = b.get("avg_days_in_status", 0)
        bottleneck_lines.append(
            f"- {b['practice_type']} stuck at **{b['status']}** "
            f"for avg **{days:.0f} days** ({b.get('count', 0)} practices)"
        )

    duration_lines = []
    for d in avg_duration[:10]:
        duration_lines.append(
            f"- {d['practice_type']}: avg **{d.get('avg_days', 0):.0f} days** "
            f"to complete ({d.get('completed', 0)} completed)"
        )

    # Trend section
    trend_section = ""
    if prev_by_status:
        prev_map: dict[str, int] = {s["status"]: s.get("count", 0) for s in prev_by_status}
        prev_total = sum(prev_map.values())
        trend_lines = [_delta_line("Total practices", total_practices, prev_total)]
        for status, count in status_map.items():
            trend_lines.append(_delta_line(f"  {status}", count, prev_map.get(status, 0)))
        # Anomaly summary
        anomalies = [l for l in trend_lines if "ANOMALIA" in l]
        trend_section = f"""
## Confronto Settimana Precedente
{chr(10).join(trend_lines)}
"""
        if anomalies:
            trend_section += f"\n⚠️ **{len(anomalies)} anomalie rilevate** — variazioni >25%\n"

    return f"""# Practices Pipeline — {today}

## Status Distribution ({total_practices} total)
{chr(10).join(status_lines)}
{trend_section}
## Bottlenecks (longest average wait)
{chr(10).join(bottleneck_lines) if bottleneck_lines else '- No bottlenecks detected'}

## Average Completion Time by Type
{chr(10).join(duration_lines) if duration_lines else '- No completed practices yet'}

---
*Auto-generated from Nuzantara CRM database. Updated {today}.*
"""


def render_compliance_radar(
    expiring_30: list[dict[str, Any]],
    expiring_60: list[dict[str, Any]],
    expiring_90: list[dict[str, Any]],
    missing_docs: list[dict[str, Any]],
    today: str,
) -> str:
    """Source 3: Compliance and expiry alerts."""

    def _alert_lines(items: list[dict[str, Any]], limit: int = 15) -> str:
        lines = []
        for item in items[:limit]:
            lines.append(
                f"- Client #{item.get('client_id', '?')} "
                f"({item.get('practice_type', 'unknown')}): "
                f"expires {_fmt_date(item.get('expiry_date'))} "
                f"({item.get('days_remaining', '?')} days)"
            )
        if len(items) > limit:
            lines.append(f"- ... and {len(items) - limit} more")
        return chr(10).join(lines) if lines else "- None"

    doc_lines = []
    for d in missing_docs[:15]:
        doc_lines.append(
            f"- Client #{d.get('client_id', '?')}: missing "
            f"**{d.get('missing_count', 0)}** required documents "
            f"for {d.get('practice_type', 'unknown')}"
        )

    return f"""# Compliance Radar — {today}

## Expiring Within 30 Days ({len(expiring_30)} practices)
{_alert_lines(expiring_30)}

## Expiring Within 60 Days ({len(expiring_60)} practices)
{_alert_lines(expiring_60)}

## Expiring Within 90 Days ({len(expiring_90)} practices)
{_alert_lines(expiring_90)}

## Missing Required Documents ({len(missing_docs)} practices)
{chr(10).join(doc_lines) if doc_lines else '- All documents complete'}

---
*Auto-generated from Nuzantara CRM database. Updated {today}.*
"""


def render_team_activity(
    interactions_by_member: list[dict[str, Any]],
    interactions_by_channel: list[dict[str, Any]],
    sentiment_dist: list[dict[str, Any]],
    today: str,
) -> str:
    """Source 4: Team activity and interactions."""
    member_lines = []
    for m in interactions_by_member[:10]:
        member_lines.append(
            f"- **{m.get('team_member', 'unassigned')}**: "
            f"{m.get('count', 0)} interactions (last 30 days)"
        )

    channel_lines = []
    for c in interactions_by_channel:
        channel_lines.append(
            f"- {c.get('channel', 'unknown')}: {c.get('count', 0)}"
        )

    sentiment_lines = []
    for s in sentiment_dist:
        sentiment_lines.append(
            f"- {s.get('sentiment', 'unknown')}: {s.get('count', 0)}"
        )

    return f"""# Team Activity Report — {today}

## Interactions by Team Member (last 30 days)
{chr(10).join(member_lines) if member_lines else '- No interactions recorded'}

## Interactions by Channel
{chr(10).join(channel_lines) if channel_lines else '- No data'}

## Sentiment Distribution
{chr(10).join(sentiment_lines) if sentiment_lines else '- No sentiment data'}

---
*Auto-generated from Nuzantara CRM database. Updated {today}.*
"""


def render_recent_changes(
    new_clients: list[dict[str, Any]],
    completed_practices: list[dict[str, Any]],
    new_practices: list[dict[str, Any]],
    today: str,
) -> str:
    """Source 5: Recent changes (7 days)."""
    nc_lines = []
    for c in new_clients[:15]:
        nc_lines.append(
            f"- Client #{c.get('id', '?')} — "
            f"{c.get('nationality', 'unknown')}, "
            f"registered {_fmt_date(c.get('created_at'))}"
        )

    cp_lines = []
    for p in completed_practices[:15]:
        cp_lines.append(
            f"- Practice #{p.get('id', '?')} ({p.get('practice_type', '?')}): "
            f"completed {_fmt_date(p.get('completion_date'))}, "
            f"revenue {_fmt_idr(p.get('actual_price'))}"
        )

    np_lines = []
    for p in new_practices[:15]:
        np_lines.append(
            f"- Practice #{p.get('id', '?')} ({p.get('practice_type', '?')}): "
            f"client #{p.get('client_id', '?')}, "
            f"quoted {_fmt_idr(p.get('quoted_price'))}"
        )

    return f"""# Recent Changes — Last 7 Days (as of {today})

## New Clients ({len(new_clients)})
{chr(10).join(nc_lines) if nc_lines else '- None'}

## Completed Practices ({len(completed_practices)})
{chr(10).join(cp_lines) if cp_lines else '- None'}

## New Practices Opened ({len(new_practices)})
{chr(10).join(np_lines) if np_lines else '- None'}

---
*Auto-generated from Nuzantara CRM database. Updated {today}.*
"""


# ---------------------------------------------------------------------------
# NB-INTEL: Bali Zero Business Intelligence
# ---------------------------------------------------------------------------

def render_revenue_dashboard(
    monthly_revenue: list[dict[str, Any]],
    unpaid_aging: list[dict[str, Any]],
    top_services: list[dict[str, Any]],
    today: str,
    prev_monthly_revenue: list[dict[str, Any]] | None = None,
) -> str:
    """Source 6: Revenue and billing overview with trend comparison."""
    rev_lines = []
    current_month_rev = 0
    prev_month_rev = 0

    for i, m in enumerate(monthly_revenue[:12]):
        rev = m.get("revenue") or 0
        rev_lines.append(
            f"- **{m.get('month', '?')}**: revenue {_fmt_idr(rev)}, "
            f"{m.get('practices_completed', 0)} practices completed"
        )
        if i == 0:
            current_month_rev = int(rev)
        if i == 1:
            prev_month_rev = int(rev)

    aging_lines = []
    total_outstanding = 0
    for a in unpaid_aging:
        outstanding = int(a.get("total_outstanding") or 0)
        total_outstanding += outstanding
        aging_lines.append(
            f"- **{a.get('bucket', '?')}**: {a.get('count', 0)} practices, "
            f"total {_fmt_idr(outstanding)}"
        )

    svc_lines = []
    for s in top_services[:10]:
        svc_lines.append(
            f"- **{s.get('practice_type', '?')}**: "
            f"{_fmt_idr(s.get('total_revenue'))}, "
            f"{s.get('count', 0)} practices, "
            f"avg {_fmt_idr(s.get('avg_price'))}"
        )

    # Trend vs previous month
    trend_section = ""
    if current_month_rev > 0 or prev_month_rev > 0:
        rev_trend = _trend_arrow(current_month_rev, prev_month_rev)
        trend_section = f"""
## Confronto Mese Precedente
- **Revenue mese corrente**: {_fmt_idr(current_month_rev)} (vs mese precedente: {rev_trend})
- **Crediti insoluti totali**: {_fmt_idr(total_outstanding)}
"""

    return f"""# Revenue Dashboard — {today}

## Monthly Revenue (last 12 months)
{chr(10).join(rev_lines) if rev_lines else '- No revenue data'}
{trend_section}
## Unpaid Practices by Age
{chr(10).join(aging_lines) if aging_lines else '- All paid'}

## Top Services by Revenue
{chr(10).join(svc_lines) if svc_lines else '- No data'}

---
*Auto-generated from Nuzantara CRM database. Updated {today}.*
"""


def render_client_segments(
    by_nationality: list[dict[str, Any]],
    by_type: list[dict[str, Any]],
    by_status: list[dict[str, Any]],
    today: str,
) -> str:
    """Source 7: Client segmentation."""
    nat_lines = []
    for n in by_nationality[:15]:
        nat_lines.append(
            f"- **{n.get('nationality', '?')}**: {n.get('count', 0)} clients, "
            f"avg practices {n.get('avg_practices', 0):.1f}, "
            f"avg revenue {_fmt_idr(n.get('avg_revenue'))}"
        )

    type_lines = []
    for t in by_type:
        type_lines.append(
            f"- **{t.get('client_type', '?')}**: {t.get('count', 0)} clients"
        )

    status_lines = []
    for s in by_status:
        status_lines.append(
            f"- **{s.get('status', '?')}**: {s.get('count', 0)} clients"
        )

    return f"""# Client Segments — {today}

## By Nationality
{chr(10).join(nat_lines) if nat_lines else '- No data'}

## By Client Type
{chr(10).join(type_lines) if type_lines else '- No data'}

## By Status
{chr(10).join(status_lines) if status_lines else '- No data'}

---
*Auto-generated from Nuzantara CRM database. Updated {today}.*
"""


def render_company_overview(
    by_type: list[dict[str, Any]],
    by_status: list[dict[str, Any]],
    top_kbli: list[dict[str, Any]],
    today: str,
) -> str:
    """Source 8: Company portfolio overview."""
    type_lines = []
    for t in by_type:
        type_lines.append(
            f"- **{t.get('company_type', '?')}**: {t.get('count', 0)} companies"
        )

    status_lines = []
    for s in by_status:
        status_lines.append(
            f"- **{s.get('status', '?')}**: {s.get('count', 0)} companies"
        )

    kbli_lines = []
    for k in top_kbli[:15]:
        kbli_lines.append(
            f"- **{k.get('kbli_code', '?')}** ({k.get('kbli_description', '')[:60]}): "
            f"{k.get('count', 0)} companies"
        )

    return f"""# Company Portfolio — {today}

## By Company Type
{chr(10).join(type_lines) if type_lines else '- No data'}

## By Status
{chr(10).join(status_lines) if status_lines else '- No data'}

## Top KBLI Codes (most registered)
{chr(10).join(kbli_lines) if kbli_lines else '- No KBLI data'}

---
*Auto-generated from Nuzantara CRM database. Updated {today}.*
"""


# ---------------------------------------------------------------------------
# NB-TELEMETRY: Bali Zero System Telemetry
# ---------------------------------------------------------------------------

def render_system_health(
    db_stats: dict[str, Any],
    qdrant_stats: dict[str, Any],
    today: str,
    redis_stats: dict[str, Any] | None = None,
    api_stats: dict[str, Any] | None = None,
    cron_stats: dict[str, Any] | None = None,
) -> str:
    """Source 9: System health overview — enriched with Redis, API, cron stats."""
    # Redis section
    redis_section = ""
    if redis_stats:
        redis_section = f"""
## Redis
- Connected clients: {redis_stats.get('connected_clients', 'N/A')}
- Memory used: {redis_stats.get('used_memory_human', 'N/A')}
- Keys total: {redis_stats.get('total_keys', 'N/A')}
- Hit rate: {redis_stats.get('hit_rate_pct', 'N/A')}%
"""

    # API performance section
    api_section = ""
    if api_stats:
        p95 = api_stats.get("p95_ms", "N/A")
        error_rate = api_stats.get("error_rate_pct", "N/A")
        anomaly = " ⚠️ CRITICO" if (isinstance(error_rate, (int, float)) and error_rate > 5) else ""
        api_section = f"""
## API Performance (last 24h)
- Requests: {api_stats.get('total_requests', 'N/A')}
- Error rate: {error_rate}%{anomaly}
- p95 latency: {p95}ms
- Cold start (Fly.io): {api_stats.get('cold_start_pct', 'N/A')}% of requests
"""

    # Cron jobs section
    cron_section = ""
    if cron_stats:
        cron_lines = []
        for job_name, job_data in cron_stats.items():
            status = job_data.get("status", "unknown")
            last_run = _fmt_date(job_data.get("last_run"))
            icon = "✅" if status == "ok" else ("⚠️" if status == "warning" else "❌")
            cron_lines.append(f"- {icon} **{job_name}**: {status} (last: {last_run})")
        cron_section = f"""
## Cron Jobs Status (last 7 days)
{chr(10).join(cron_lines) if cron_lines else '- No cron data'}
"""

    return f"""# System Health — {today}

## PostgreSQL
- Active connections: {db_stats.get('active_connections', 'N/A')}
- Database size: {db_stats.get('db_size', 'N/A')}
- Longest running query: {db_stats.get('longest_query_seconds', 'N/A')}s
- Dead tuples (top tables): {db_stats.get('dead_tuples_summary', 'N/A')}

## Qdrant
- Total collections: {qdrant_stats.get('total_collections', 'N/A')}
- Total vectors: {qdrant_stats.get('total_vectors', 'N/A')}
- RAM usage estimate: {qdrant_stats.get('ram_usage', 'N/A')}
{redis_section}{api_section}{cron_section}
---
*Auto-generated from system diagnostics. Updated {today}.*
"""


def render_tax_compliance(
    by_status: list[dict[str, Any]],
    upcoming_filings: list[dict[str, Any]],
    today: str,
) -> str:
    """Source 10: Tax compliance overview."""
    status_lines = []
    for s in by_status:
        status_lines.append(
            f"- **{s.get('compliance_status', '?')}**: "
            f"{s.get('count', 0)} entities"
        )

    filing_lines = []
    for f in upcoming_filings[:15]:
        filing_lines.append(
            f"- {f.get('entity_type', '?')} #{f.get('entity_id', '?')}: "
            f"{f.get('tax_type', '?')} due {_fmt_date(f.get('next_filing_date'))}"
        )

    return f"""# Tax Compliance Overview — {today}

## Status Distribution
{chr(10).join(status_lines) if status_lines else '- No tax records'}

## Upcoming Filing Deadlines (next 60 days)
{chr(10).join(filing_lines) if filing_lines else '- No upcoming filings'}

---
*Auto-generated from Nuzantara CRM database. Updated {today}.*
"""


# ---------------------------------------------------------------------------
# ARCH-10: Executive Briefing (weekly NB-11 + NB-12 intelligence query output)
# ---------------------------------------------------------------------------

def render_ops_briefing(
    week_label: str,
    ops_response: str,
    intel_response: str,
    anomalies: list[str] | None = None,
    top_risks: list[str] | None = None,
) -> str:
    """Render weekly executive ops briefing from NB-11 and NB-12 query responses.

    This template formats the output of weekly intelligence queries into a
    structured Telegram-ready briefing. Called by ops_intelligence.py.
    """
    anomaly_section = ""
    if anomalies:
        lines = [f"- {a}" for a in anomalies]
        anomaly_section = f"""
## ⚠️ Anomalie Rilevate
{chr(10).join(lines)}
"""

    risk_section = ""
    if top_risks:
        lines = [f"- {r}" for r in top_risks[:5]]
        risk_section = f"""
## 🔴 Top Rischi Operativi
{chr(10).join(lines)}
"""

    return f"""# Executive Ops Briefing — {week_label}

## 📊 Situation Report (NB-11: Ops Live)
{ops_response.strip()}

## 💰 Business Intelligence (NB-12)
{intel_response.strip()}
{anomaly_section}{risk_section}
---
*Generato automaticamente da Nuzantara Ops Intelligence. {week_label}*
"""
