#!/usr/bin/env python3
"""Voyager-style curriculum — weekly underrepresented-topic detection.

Inspired by Voyager (Wang et al., 2023) automatic curriculum: agent decides what to attempt
next based on coverage of the skill space.

For Bali Zero: inspect last 30 carousels, identify domain×audience×register×layout combos
with zero coverage, propose ONE exploration variant for next production cycle.

Output: ~/Desktop/nuzantara/apps/war-room/output/exploration_proposal.json
The orchestrator picks this up at next carousel run and generates an extra exploration variant
alongside the requested production carousel.

CRITICAL — per Gemini FLAW MEDIUM "open-loop curriculum":
This script does NOT optimize against IG metrics yet (sessione 3 deferred). Curriculum signal
is COVERAGE-based (what hasn't been tried), not OUTCOME-based (what worked). Once 50+
published carousels have IG metrics ingested, switch to outcome-weighted curriculum.

Run: weekly LaunchAgent Sunday 02:00 WITA (low-load).
"""

import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path.home() / ".claude/projects/-Users-nuzantara/memory/wr2-episodic.db"
PROPOSAL_PATH = Path.home() / "Desktop/nuzantara/apps/war-room/output/exploration_proposal.json"

DOMAINS = ["visa", "tax", "property", "regulatory", "health"]
AUDIENCE_SEGMENTS = ["founder", "investor", "digital-nomad", "retiree", "mass-tourist"]
REGISTERS = ["rituale", "analitico", "ironico", "militante", "pedagogico", "poetico", "tecnico"]
LAYOUTS = ["cover-photo", "photo-headline-yellow-sub", "qa-dialogue",
           "timeline-pinboard", "dark-status-list", "statement-bomb"]


def load_recent_runs(n=30):
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("""
            SELECT cr.id, cr.topic_slug, cr.domain, cr.audience_segment, cr.layout_families_used,
                   cr.completed_at, cr.instagram_published_at,
                   ttl.tone_register_primary, ttl.layout_family_primary
              FROM carousel_runs cr
              LEFT JOIN topic_type_log ttl ON ttl.run_id = cr.id
             WHERE cr.completed_at IS NOT NULL
             ORDER BY cr.completed_at DESC
             LIMIT ?
        """, (n,)).fetchall()
        cols = ["id", "topic_slug", "domain", "audience_segment", "layout_families_used",
                "completed_at", "instagram_published_at", "tone_register_primary",
                "layout_family_primary"]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def coverage_analysis(runs):
    """Count occurrences of each (domain, register, layout_primary) combo."""
    combos = Counter()
    by_domain = Counter()
    by_register = Counter()
    by_layout = Counter()
    by_audience = Counter()

    for r in runs:
        d = r["domain"] or "unknown"
        a = r["audience_segment"] or "unknown"
        rg = r["tone_register_primary"] or "unknown"
        ly = r["layout_family_primary"] or "unknown"
        combos[(d, rg, ly)] += 1
        by_domain[d] += 1
        by_register[rg] += 1
        by_layout[ly] += 1
        by_audience[a] += 1

    return {
        "combos": dict(combos),
        "by_domain": dict(by_domain),
        "by_register": dict(by_register),
        "by_layout": dict(by_layout),
        "by_audience": dict(by_audience),
    }


def find_gaps(coverage, total_runs):
    """Identify underrepresented combos worth exploring."""
    gaps = []

    # 1) Domains with zero or very low coverage
    for d in DOMAINS:
        c = coverage["by_domain"].get(d, 0)
        if c == 0:
            gaps.append({
                "type": "domain-gap",
                "missing": {"domain": d},
                "current_count": 0,
                "priority": "high",
                "rationale": f"Domain '{d}' has zero carousels in last {total_runs} runs",
            })
        elif total_runs > 10 and c < total_runs * 0.05:
            gaps.append({
                "type": "domain-underrepresented",
                "missing": {"domain": d},
                "current_count": c,
                "priority": "medium",
                "rationale": f"Domain '{d}' is below 5% of last {total_runs} runs (count={c})",
            })

    # 2) Registers with zero coverage
    for rg in REGISTERS:
        c = coverage["by_register"].get(rg, 0)
        if c == 0:
            gaps.append({
                "type": "register-gap",
                "missing": {"register": rg},
                "current_count": 0,
                "priority": "medium",
                "rationale": f"Register '{rg}' has zero carousels in last {total_runs} runs",
            })

    # 3) Layout families with zero coverage as primary
    for ly in LAYOUTS:
        if ly in ("cover-photo", "statement-bomb"):
            continue  # always-present, not "primary" variation
        c = coverage["by_layout"].get(ly, 0)
        if c == 0:
            gaps.append({
                "type": "layout-gap",
                "missing": {"layout": ly},
                "current_count": 0,
                "priority": "low",
                "rationale": f"Layout '{ly}' never used as primary in last {total_runs} runs",
            })

    # 4) Audience segments
    for a in AUDIENCE_SEGMENTS:
        c = coverage["by_audience"].get(a, 0)
        if c == 0:
            gaps.append({
                "type": "audience-gap",
                "missing": {"audience_segment": a},
                "current_count": 0,
                "priority": "medium",
                "rationale": f"Audience segment '{a}' has zero carousels in last {total_runs} runs",
            })

    priority_order = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda g: (priority_order[g["priority"]], g["type"]))
    return gaps


def select_proposal(gaps):
    """Pick ONE exploration proposal from the highest-priority gap."""
    if not gaps:
        return None
    top = gaps[0]
    return {
        "exploration_id": f"explore_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "type": top["type"],
        "target": top["missing"],
        "priority": top["priority"],
        "rationale": top["rationale"],
        "instructions_for_orchestrator": (
            f"At next carousel run, after completing the user-requested production carousel, "
            f"generate ONE additional exploration carousel filling this gap: {top['missing']}. "
            "Tag the run with is_exploration=1 in topic_type_log. Do NOT auto-publish; route to "
            "human-review-queue with state=drafted as usual. Antonello reviews + decides whether "
            "to graduate it to production."
        ),
        "all_gaps_detected": gaps[:10],
        "coverage_snapshot_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    runs = load_recent_runs(n=30)
    if not runs:
        print("No completed carousels in DB; nothing to analyze.")
        sys.exit(0)

    coverage = coverage_analysis(runs)
    total = len(runs)
    gaps = find_gaps(coverage, total)

    proposal = select_proposal(gaps)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs_analyzed": total,
        "coverage": coverage,
        "gaps_count": len(gaps),
        "proposal": proposal,
    }

    PROPOSAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROPOSAL_PATH.write_text(json.dumps(output, indent=2))

    if proposal:
        print(f"Proposal: {proposal['type']} → target {proposal['target']}")
        print(f"Rationale: {proposal['rationale']}")
    else:
        print("No coverage gaps detected; curriculum has converged.")
    print(f"Output: {PROPOSAL_PATH}")


if __name__ == "__main__":
    main()
