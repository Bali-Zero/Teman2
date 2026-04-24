#!/usr/bin/env python3
"""Fase 0 Day 6/9 driver — Consiglio v1 synthesizes playbook + wr2_weights.

Usage:
    --wave=preliminary   Day 6 draft → preliminary_playbook.md
    --wave=final         Day 9 final → 08_playbook.md + 09_wr2_weights.json

Pragmatic Consiglio composition for this first SOTA run:
  Primary:   Claude Opus 4.7 OAuth (always)
  Optional:  Gemini 3.1 Pro (if not rate-limited; 429 observed 2026-04-23)
  Deferred:  DeepSeek ($-audited, enable via CONSIGLIO_USE_DEEPSEEK=1)
  Deferred:  NotebookLM MCP (requires running bridge, enable via
             CONSIGLIO_USE_NLM=1)

Gate 6 (ideal): ≥3/4 LLMs agree on every claim. With Gemini rate-limited
and DeepSeek opt-in, real runs will typically reach 1-2 voters. The
playbook renders disputed claims with ⚠️ so Zero can judge visually.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "apps" / "backend-rag"))

os.environ.setdefault("JWT_SECRET_KEY", "sota-research-local-dev-placeholder-32chars-min-ok")
os.environ.setdefault("API_KEYS", "sota-research-local-placeholder-key")

from backend.services.research.consiglio_orchestrator import (  # noqa: E402
    ConsiglioV1,
    ConsiglioResult,
    ConsiglioClaim,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.consiglio")

RESEARCH = _REPO_ROOT / "research" / "sota-social-2026-v1"

# Context files fed to each LLM (truncated to 50KB each by orchestrator)
ARTIFACTS = [
    RESEARCH / "00_baseline.json",
    RESEARCH / "01_balizero_corpus.json",
    RESEARCH / "03_sota_literature.md",
    RESEARCH / "04_personas.json",
    RESEARCH / "05_format_matrix.json",
    RESEARCH / "06_cadence_engine.json",
    RESEARCH / "07_gap_analysis.md",
]

SYNTHESIS_PROMPT = """You are one voice in the Bali Zero Consiglio — a 4-LLM
deliberation producing the social media playbook for the next 90 days.

The Consiglio has read all Fase 0 artifacts (baseline, @balizero0 empirical
corpus of 25 posts, literature synthesis 4 topics, 6 personas, 294-cell
format matrix stub, cadence engine 14×3×24, gap analysis 16 gaps +
8 strengths).

CRITICAL OUTPUT DIRECTIVE: your entire reply is a single JSON object on
the LAST line of your response, no prose before or after, no markdown
fences. The first character of the last line MUST be "{".

JSON schema (copy and fill):

{"claims": [
  {"key": "<snake_case_stable_key>", "value": <scalar or object>, "confidence": <0-1>},
  ...
]}

Produce minimum 60 claims across these categories:

1. cadence_{channel}_posts_per_day — 14 channels (instagram, linkedin,
   tiktok, threads, x_twitter, youtube_long, youtube_shorts, telegram,
   whatsapp, newsletter, blog_seo, podcast, xiaohongshu_weibo,
   quora_reddit). Value: float 0-3 (posts/day target).

2. cadence_{channel}_optimal_hours_wita — 14 channels. Value: list[int]
   hours in WITA (0-23).

3. format_mix_{objective} — 3 objectives (lead, authority, audience).
   Value: object {format_name: weight_0_1, ...} summing to ~1.0.
   Reference 05_format_matrix.json for format taxonomy.

4. persona_weight_{slug} — 6 personas (expat_boomer_retiree,
   expat_techie_pma, expat_italian_aire, id_konsultan_kadin,
   id_founder_pma, id_umkm_digital). Value: float 0-1 summing to ~1.0
   across all 6 (targeting split).

5. hook_pattern_top_{persona_slug} — 6 personas. Value: list of top 3
   hook types that resonate (from: question, stat, story, contrarian,
   list).

6. tone_resonance_{persona_slug}_{register} — 6 personas × 7 registers
   (pedagogico, analitico, tecnico, rituale, poetico, ironico,
   militante) = 42 claims. Value: float 0-1.

7. pillar_kpi_target_{pillar} — 3 pillars (lead, authority, audience).
   Value: object with 90d-horizon numeric targets. Example for lead:
   {"leads_social_90d_target": 50, "cr_target_pct": 3.0}.
   Baseline today: leads_total_90d=324, leads_social_90d=5 (1.5%),
   @balizero0 followers=10,360.

8. channel_priority_top3 — single claim. Value: ordered list of 3
   channel names to activate first.

Base every claim on the provided context. If a claim requires a number
not in the context, set confidence to 0.3-0.5 (low). If it's well-grounded
in gap_analysis or literature, confidence can be 0.7-0.9.

Emit the JSON directly on the last line. Nothing after it."""


def render_playbook_md(result: ConsiglioResult, wave: str) -> str:
    """Group claims by prefix, flag disputed with ⚠️."""
    lines = [
        f"# Bali Zero Social Playbook (Consiglio v1, wave={wave})",
        "",
        f"> Generated {len(result.claims)} claims across "
        f"{result.meta.get('active_llms', 0)} active LLM(s).",
        f"> Gate 6 (≥3/4 agreement): {'✅ PASS' if result.gate_6_passes() else '⚠️ SOFT FAIL — disputed claims flagged'}",
        f"> Members queried: {result.meta.get('members_queried', [])}",
        f"> Answer counts: {result.meta.get('llm_answer_counts', {})}",
        "",
        "---",
    ]

    sections: dict[str, list[ConsiglioClaim]] = {}
    for c in result.claims:
        prefix = c.key.split("_")[0]
        sections.setdefault(prefix, []).append(c)

    for prefix, claims in sorted(sections.items()):
        lines.append(f"\n## {prefix}\n")
        for c in sorted(claims, key=lambda x: x.key):
            disp = " ⚠️ DISPUTED" if c.is_disputed() else ""
            # Truncate large values for readability
            val_repr = repr(c.value) if not isinstance(c.value, dict) else json.dumps(c.value)
            if len(val_repr) > 200:
                val_repr = val_repr[:200] + "..."
            lines.append(
                f"- **{c.key}**: `{val_repr}` "
                f"(agreement {c.agreement_count()}/{len(c.votes)}){disp}"
            )
    return "\n".join(lines)


def render_wr2_weights(result: ConsiglioResult) -> dict:
    """Extract WR2-consumable config from non-disputed claims.

    Threshold adapts to ``active_llms``: with 1 voter the minimum quorum
    drops to 1 (no "dispute" possible). With 4 voters the default 3/4
    applies. This keeps the WR2 config populated even when only Claude
    responded (Gemini rate-limited, DeepSeek opt-in off).

    Explicit safety: every channel's publisher_enabled starts FALSE.
    Zero approves go-live per channel manually (spec §Risk #7 default).
    """
    active = max(1, int(result.meta.get("active_llms", 1)))
    # Quorum: 3/4 ideal, 2/3 if 3 voters, 2/2 if 2 voters, 1/1 if alone
    quorum = min(3, max(1, active - (1 if active >= 2 else 0)))

    def accepts(c: ConsiglioClaim) -> bool:
        return not c.is_disputed(min_agreement=quorum)

    weights: dict = {
        "persona_weight": {},
        "tone_resonance": {},
        "cadence_by_channel": {},
        "format_mix_by_objective": {},
        "hook_pattern_top_by_persona": {},
        "pillar_kpi_targets": {},
        "channel_priority_top3": [],
        "publisher_enabled_by_channel": {},
    }
    for c in result.claims:
        if not accepts(c):
            continue
        key = c.key
        v = c.value

        if key.startswith("persona_weight_"):
            weights["persona_weight"][key[len("persona_weight_"):]] = v
        elif key.startswith("tone_resonance_"):
            rest = key[len("tone_resonance_"):]
            pslug, _, register = rest.rpartition("_")
            weights["tone_resonance"].setdefault(pslug, {})[register] = v
        elif key.startswith("cadence_") and "posts_per_day" in key:
            ch = key[len("cadence_"):-len("_posts_per_day")]
            weights["cadence_by_channel"].setdefault(ch, {})["posts_per_day"] = v
        elif key.startswith("cadence_") and "optimal_hours_wita" in key:
            ch = key[len("cadence_"):-len("_optimal_hours_wita")]
            weights["cadence_by_channel"].setdefault(ch, {})["optimal_hours_wita"] = v
        elif key.startswith("format_mix_"):
            weights["format_mix_by_objective"][key[len("format_mix_"):]] = v
        elif key.startswith("hook_pattern_top_"):
            weights["hook_pattern_top_by_persona"][key[len("hook_pattern_top_"):]] = v
        elif key.startswith("pillar_kpi_target_"):
            weights["pillar_kpi_targets"][key[len("pillar_kpi_target_"):]] = v
        elif key == "channel_priority_top3":
            weights["channel_priority_top3"] = v

    # Safety: explicit publisher disabled for canary 7 days
    for ch in [
        "instagram", "linkedin", "tiktok", "threads", "x_twitter",
        "youtube_long", "youtube_shorts", "telegram", "whatsapp",
        "newsletter", "blog_seo", "podcast", "xiaohongshu_weibo",
        "quora_reddit",
    ]:
        weights["publisher_enabled_by_channel"][ch] = False

    return weights


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", choices=["preliminary", "final"], required=True)
    args = ap.parse_args()

    # Resolve active members — start with just claude (most reliable),
    # add optional members via env flags.
    members: list[str] = ["claude"]
    if os.environ.get("CONSIGLIO_USE_GEMINI") == "1":
        members.append("gemini")
    if os.environ.get("CONSIGLIO_USE_DEEPSEEK") == "1":
        members.append("deepseek")
    if os.environ.get("CONSIGLIO_USE_NLM") == "1":
        members.append("notebooklm")
    logger.info("Consiglio members for this run: %s", members)

    council = ConsiglioV1(timeout_sec=900)
    context_files = [str(f) for f in ARTIFACTS if f.exists()]
    logger.info("feeding %d context files", len(context_files))

    result = council.deliberate(
        SYNTHESIS_PROMPT,
        context_files=context_files,
        members=tuple(members),
    )
    logger.info(
        "deliberation done: claims=%d active_llms=%d disputed=%d",
        len(result.claims),
        result.meta.get("active_llms", 0),
        len(result.disputed_keys()),
    )

    if args.wave == "preliminary":
        path = RESEARCH / "preliminary_playbook.md"
        path.write_text(render_playbook_md(result, "preliminary"), encoding="utf-8")
        logger.info("wrote %s", path)
        return 0

    # wave=final
    playbook_path = RESEARCH / "08_playbook.md"
    weights_path = RESEARCH / "09_wr2_weights.json"
    playbook_path.write_text(render_playbook_md(result, "final"), encoding="utf-8")
    weights_path.write_text(
        json.dumps(render_wr2_weights(result), indent=2),
        encoding="utf-8",
    )
    logger.info("wrote %s + %s", playbook_path, weights_path)

    if not result.gate_6_passes():
        logger.warning(
            "Gate 6 SOFT FAIL: %d disputed claims flagged in playbook "
            "(NOT blocking — Zero decides per claim)",
            len(result.disputed_keys()),
        )
    else:
        logger.info("Gate 6 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
