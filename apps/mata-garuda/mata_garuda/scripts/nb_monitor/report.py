"""Weekly markdown report generator for nb_monitor.

Output path: ~/Desktop/nuzantara/research/nb-monitor/report-YYYY-Www.md
Renderer is pure -- takes entries + timestamp, returns markdown string. The
caller writes to disk.

Spec §7.3 (banner content), §6 (alert format reference for footer link).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import StringIO

from mata_garuda.scripts.nb_monitor.tier import Tier


@dataclass(frozen=True)
class ReportEntry:
    rank: int
    uuid: str
    name: str
    tier: Tier
    read_freq_7d: int | None
    read_freq_30d: int | None
    delta_7d_vs_lastweek: int | None
    age_days: int
    skill_derivation_count: int | None
    downstream_cite_rate: float | None
    source_freshness_age_days: int | None
    push_success_rate: float | None
    instrumentation_status: str


BASELINE_BANNER = """\
> **Baseline period — first 14 days post-deploy. Score reliability degraded:**
> - `read_freq_7d/30d`: live (Claude Code JSONL scraper).
> - `source_freshness_age`: best-effort (nlm cookie 5min TTL).
> - `push_success_rate`: live (matagaruda-nlm-feeder-stream.log; **GLOBAL** — same value applied per active_routing UUID).
> - `skill_derivation_count`: **N/A pending FASE 1 merge**.
> - `downstream_cite_rate`: **N/A pending FASE 4 merge**.
"""


def iso_year_week(dt: datetime) -> str:
    iy, iw, _ = dt.isocalendar()
    return f"{iy}-W{iw:02d}"


def render_weekly_report(
    entries: list[ReportEntry],
    generated_at: datetime,
    baseline_window: bool,
) -> str:
    week = iso_year_week(generated_at)
    out = StringIO()
    out.write(f"# NB Mitochondrial Value Monitor — {week}\n\n")
    out.write(f"_Generated at {generated_at.isoformat()}_\n\n")
    if baseline_window:
        out.write(BASELINE_BANNER)
        out.write("\n")

    if not entries:
        out.write("_No entries (0 NB recorded). Check cron + bootstrap registry._\n")
        return out.getvalue()

    out.write("## Ranking\n\n")
    out.write("| rank | name | tier | rf7 | rf30 | Δ vs lastweek | age (d) |\n")
    out.write("|---:|---|:---:|---:|---:|---:|---:|\n")
    for e in entries:
        out.write(
            f"| {e.rank} | `{e.name}` | {e.tier.value} | "
            f"{_fmt_int(e.read_freq_7d)} | {_fmt_int(e.read_freq_30d)} | "
            f"{_fmt_delta(e.delta_7d_vs_lastweek)} | {e.age_days} |\n"
        )

    out.write("\n<details>\n")
    out.write(
        "<summary>Diagnostic columns "
        "(skill_derivation_count, downstream_cite_rate, freshness, push_success, "
        "instrumentation_status)</summary>\n\n"
    )
    out.write(
        "| name | skill_derivation_count | downstream_cite_rate | "
        "source_freshness_age_days | push_success_rate | instrumentation_status |\n"
    )
    out.write("|---|---:|---:|---:|---:|:---|\n")
    for e in entries:
        out.write(
            f"| `{e.name}` | {_fmt_int(e.skill_derivation_count)} | "
            f"{_fmt_rate(e.downstream_cite_rate)} | {_fmt_int(e.source_freshness_age_days)} | "
            f"{_fmt_rate(e.push_success_rate)} | {e.instrumentation_status} |\n"
        )
    out.write("\n</details>\n")
    return out.getvalue()


def _fmt_int(v: int | None) -> str:
    return "N/A" if v is None else str(v)


def _fmt_rate(v: float | None) -> str:
    return "N/A" if v is None else f"{v:.2f}"


def _fmt_delta(v: int | None) -> str:
    if v is None:
        return "N/A"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v}"
