#!/usr/bin/env python3
"""Cost baseline for the Opus 4.7 migration routing audit.

Estimates per-query token + USD cost for 5 representative Bali Zero scenarios
under the current routing (Gemini-first backend) and under two hypothetical
Opus 4.7 routings (all-Opus vs. Opus/Sonnet/Haiku tiered).

Usage:
    python scripts/cost_baseline.py
    python scripts/cost_baseline.py --out docs/superpowers/sessions/2026-04-17-strategic-8/logs/pro-2-baseline.json

No network calls — pricing tables are static and documented in the output.
Runs on stock Python 3.11+ (stdlib only).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


# ── Pricing tables (USD per 1M tokens) ──────────────────────────────────────
# Sources:
#   Gemini: https://ai.google.dev/pricing (verified 2026-04-17)
#   Anthropic: https://www.anthropic.com/pricing (Opus 4.7 release 2026-04-16)
# Current backend reality lives in
#   apps/backend-rag/backend/services/llm_clients/pricing.py:59
PRICING: dict[str, dict[str, float]] = {
    # Gemini — live in backend
    "gemini-3-flash-preview": {"input": 0.10, "output": 0.40},
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash-lite": {"input": 0.0375, "output": 0.15},
    # Anthropic — post-4.7 release
    "claude-opus-4-7": {"input": 5.00, "output": 25.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    # Legacy Claude still referenced in-repo
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    # Embedding
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
}


@dataclass
class Scenario:
    """One representative query pattern with typical token shape."""

    key: str
    label: str
    # Tokens observed in production-like traces (order of magnitude, conservative)
    system_prompt_tokens: int  # includes zantara_core + KB snippets
    user_tokens: int
    output_tokens: int
    calls_per_day: int
    notes: str


SCENARIOS: list[Scenario] = [
    Scenario(
        key="pricing",
        label="Pricing lookup (KBLI/visa → PricingTool)",
        system_prompt_tokens=4_500,
        user_tokens=80,
        output_tokens=300,
        calls_per_day=350,
        notes="Short Q, short A, cacheable system prompt.",
    ),
    Scenario(
        key="kg",
        label="Knowledge Graph reasoning (Company/Visa/Tax/Property)",
        system_prompt_tokens=6_000,
        user_tokens=250,
        output_tokens=900,
        calls_per_day=120,
        notes="LangGraph nodes, multi-hop. Currently OpenAI GPT-4o-mini "
        "(kg_langgraph_orchestrator.py:98) with Claude Sonnet 4.5 fallback.",
    ),
    Scenario(
        key="vision",
        label="Vision doc extractor (Permen / OSS / akta)",
        system_prompt_tokens=2_000,
        user_tokens=3_500,  # image tokens dominate
        output_tokens=1_200,
        calls_per_day=40,
        notes="New cron (§6 plan). HD 3.75MP needs Opus 4.7 — not cacheable "
        "because input images change every call.",
    ),
    Scenario(
        key="crm",
        label="CRM enrichment / translation (Gemini Flash)",
        system_prompt_tokens=1_200,
        user_tokens=400,
        output_tokens=600,
        calls_per_day=800,
        notes="High-volume, low-complexity. Best on Flash or Haiku tier.",
    ),
    Scenario(
        key="council",
        label="Council / fact-checker multi-agent",
        system_prompt_tokens=8_000,
        user_tokens=500,
        output_tokens=2_000,
        calls_per_day=60,
        notes="Multi-agent coordinator (multi_agent_coordinator.py). "
        "Critical quality — candidate for Opus 4.7 xhigh.",
    ),
]


def cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return USD cost for a single call. Raises on unknown model."""
    p = PRICING[model]
    return (input_tokens / 1_000_000) * p["input"] + (
        output_tokens / 1_000_000
    ) * p["output"]


def cost_with_cache(
    model: str,
    cacheable_input: int,
    fresh_input: int,
    output_tokens: int,
    cache_hit_rate: float = 0.7,
) -> float:
    """Return USD cost assuming Anthropic ephemeral cache pricing.

    Anthropic 5-min ephemeral cache: cache writes ≈ 1.25× input, cache reads ≈ 0.1× input.
    Gemini has no equivalent public discount model (treated as full price).
    """
    p = PRICING[model]
    is_anthropic = model.startswith("claude-")
    if is_anthropic:
        write_cost = (cacheable_input / 1_000_000) * p["input"] * 1.25
        read_cost = (cacheable_input / 1_000_000) * p["input"] * 0.10
        cached_input_cost = (
            (1 - cache_hit_rate) * write_cost + cache_hit_rate * read_cost
        )
    else:
        cached_input_cost = (cacheable_input / 1_000_000) * p["input"]
    fresh_cost = (fresh_input / 1_000_000) * p["input"]
    out_cost = (output_tokens / 1_000_000) * p["output"]
    return cached_input_cost + fresh_cost + out_cost


# ── Routing variants ────────────────────────────────────────────────────────
ROUTING_CURRENT: dict[str, str] = {
    "pricing": "gemini-3-flash-preview",
    "kg": "claude-sonnet-4-20250514",
    "vision": "gemini-3-flash-preview",  # no vision cron live yet
    "crm": "gemini-2.5-flash",
    "council": "claude-sonnet-4-20250514",
}

ROUTING_ALL_OPUS_47: dict[str, str] = dict.fromkeys(
    [s.key for s in SCENARIOS], "claude-opus-4-7"
)

ROUTING_TIERED_47: dict[str, str] = {
    "pricing": "claude-haiku-4-5",  # simple lookup
    "kg": "claude-sonnet-4-6",  # reasoning
    "vision": "claude-opus-4-7",  # HD vision exclusive
    "crm": "claude-haiku-4-5",  # high-volume cheap
    "council": "claude-opus-4-7",  # critical quality
}

ROUTING_HYBRID_RECOMMENDED: dict[str, str] = {
    "pricing": "gemini-3-flash-preview",  # cheapest per your traces
    "kg": "claude-sonnet-4-6",
    "vision": "claude-opus-4-7",
    "crm": "gemini-2.5-flash",
    "council": "claude-opus-4-7",
}


def evaluate(routing: dict[str, str], *, with_cache: bool) -> dict:
    """Compute cost per scenario and daily total for a given routing map."""
    rows = []
    total_day = 0.0
    for s in SCENARIOS:
        model = routing[s.key]
        input_total = s.system_prompt_tokens + s.user_tokens
        if with_cache:
            per_call = cost_with_cache(
                model,
                cacheable_input=s.system_prompt_tokens,
                fresh_input=s.user_tokens,
                output_tokens=s.output_tokens,
            )
        else:
            per_call = cost(model, input_total, s.output_tokens)
        per_day = per_call * s.calls_per_day
        total_day += per_day
        rows.append(
            {
                "scenario": s.key,
                "label": s.label,
                "model": model,
                "input_tokens": input_total,
                "output_tokens": s.output_tokens,
                "calls_per_day": s.calls_per_day,
                "cost_per_call_usd": round(per_call, 6),
                "cost_per_day_usd": round(per_day, 4),
            }
        )
    return {
        "rows": rows,
        "total_per_day_usd": round(total_day, 2),
        "total_per_month_usd": round(total_day * 30, 2),
        "with_cache": with_cache,
    }


def build_baseline() -> dict:
    """Return the full baseline report as a JSON-serializable dict."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "scenarios": [asdict(s) for s in SCENARIOS],
        "pricing_usd_per_1m_tokens": PRICING,
        "assumptions": {
            "cache_hit_rate": 0.7,
            "cache_write_multiplier": 1.25,
            "cache_read_multiplier": 0.10,
            "calls_per_day_horizon": "steady-state per scenarios[].calls_per_day",
            "note": (
                "Token shapes are order-of-magnitude estimates, not measured. "
                "Replace with real values from metrics.py once populated."
            ),
        },
        "variants": {
            "current_no_cache": evaluate(ROUTING_CURRENT, with_cache=False),
            "current_with_cache": evaluate(ROUTING_CURRENT, with_cache=True),
            "all_opus_4_7_no_cache": evaluate(ROUTING_ALL_OPUS_47, with_cache=False),
            "all_opus_4_7_with_cache": evaluate(ROUTING_ALL_OPUS_47, with_cache=True),
            "tiered_4_7_no_cache": evaluate(ROUTING_TIERED_47, with_cache=False),
            "tiered_4_7_with_cache": evaluate(ROUTING_TIERED_47, with_cache=True),
            "hybrid_recommended_no_cache": evaluate(
                ROUTING_HYBRID_RECOMMENDED, with_cache=False
            ),
            "hybrid_recommended_with_cache": evaluate(
                ROUTING_HYBRID_RECOMMENDED, with_cache=True
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=None,
        help="Optional JSON output path. Also prints a short summary to stdout.",
    )
    args = parser.parse_args()

    report = build_baseline()

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=False))
        print(f"wrote {args.out}")

    summary = [
        ("current_no_cache", "current Gemini+legacy Claude (no cache_control)"),
        ("current_with_cache", "current routing + hypothetical 70% cache hit"),
        ("all_opus_4_7_with_cache", "everything on Opus 4.7 + cache"),
        ("tiered_4_7_with_cache", "Opus/Sonnet/Haiku tiered + cache"),
        ("hybrid_recommended_with_cache", "Gemini hot path + Claude critical + cache"),
    ]
    print()
    print(f"{'variant':<40} {'$/day':>10} {'$/mo':>10}")
    print("-" * 62)
    for k, _label in summary:
        v = report["variants"][k]
        print(f"{k:<40} {v['total_per_day_usd']:>10.2f} {v['total_per_month_usd']:>10.2f}")
    print()
    print("Per-scenario breakdown — current_no_cache:")
    for r in report["variants"]["current_no_cache"]["rows"]:
        print(
            f"  {r['scenario']:<10} {r['model']:<35} "
            f"${r['cost_per_call_usd']:.6f}/call  ${r['cost_per_day_usd']:.2f}/day"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
