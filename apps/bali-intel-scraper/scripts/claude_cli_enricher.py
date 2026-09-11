#!/usr/bin/env python3
"""
CLAUDE CLI ENRICHER
Uses Claude Code CLI (subprocess) - Max quota, no browser automation
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any
import logging

import httpx

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


ENRICHMENT_PROMPT_TEMPLATE = """You are a senior editor at Bali Zero, a business consultancy for foreigners in Bali/Indonesia.

Enrich this article for our intelligence news room. Write in English, editorial style.

<notizia_scraped>
Title: {title}
Source: {source}
Category: {category}
Published: {published_date}
Content: {content}
</notizia_scraped>

AS OF: {as_of} — this is the current date/time; use it (together with
Published, and any dates mentioned in Content) to judge whether events are
"in the last ~48h" for the LIVENESS TIER section below.

<base_legale_certificata>
{nlm_legal_basis}
</base_legale_certificata>

<fonti_web_non_verificate>
{nlm_web_findings}
</fonti_web_non_verificate>

IMPORTANT: The <base_legale_certificata> section contains VERIFIED Indonesian law from our legal database.
The <fonti_web_non_verificate> section may contain errors — use with caution and always
prefer the certified legal basis. Never present web findings as verified law.
If both sections are empty, write based on the news article alone.

OUTPUT FORMAT (strict JSON only, no markdown):
{{
  "headline": "Punchy editorial headline (max 80 chars, no source name)",
  "thirty_second_brief": {{
    "what": "1 sentence: what happened",
    "why_it_matters": "1 sentence: why it matters to expats/investors in Bali",
    "who": "who is affected",
    "risk_level": "low|medium|high"
  }},
  "the_facts": "3-5 paragraphs of pure journalism. Facts only, no opinion. 400-500 words.",
  "bali_zero_take": "2-3 paragraphs: Bali Zero editorial perspective. What does this mean for our clients? 150-200 words.",
  "in_practice": "Practical implications for expats/investors in Bali. Bullet-point style converted to prose. 150-200 words.",
  "next_steps": "Concrete action items for readers. What should they do NOW? 100-150 words.",
  "faq": [
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}}
  ],
  "liveness_tier": "<breaking|developing|evergreen>",
  "live_news_reasons": [],
  "metadata": {{
    "suggested_slug": "url-friendly-slug-max-60-chars",
    "tags": ["tag1", "tag2", "tag3"],
    "priority": "high|medium|low",
    "reading_time_minutes": 3
  }}
}}

LIVENESS TIER (forced choice):
You MUST choose exactly one of: "breaking", "developing", "evergreen". Do not compute a
score — pick the tier directly from the signal definitions below. Judge "last ~48h" and
"near-term" relative to AS OF above (not to the calibrated anchors below, which are shape
references only, not date references).

- breaking — a concrete dated event/decision within the last ~48h of AS OF that changes
  what readers must do NOW: a new decree published with a date, a single enforcement
  action (arrest/deportation/raid) that concluded within that ~48h window with immediate
  effect, or a fee change effective immediately.
- developing — a dated, concrete story that is actively unfolding or has a near-term
  deadline/effect: an announced-but-not-yet-effective rule, dated arrests/raids reported as
  part of a broader enforcement pattern or policy story (not the initial <48h enforcement
  moment itself), official figures just released, imminent deadlines.
- evergreen — routine guides, how-tos, explainer content, undated or old news, recurring
  seasonal content.

CALIBRATED ANCHORS (real examples from our corpus; shape references, not date references):
- developing:
  * "15 WNA China dan Vietnam Ditangkap Usai Buka Lowongan Kerja" (dated arrests, part of
    an enforcement pattern, policy implication)
  * "Immigration Cuts Visa-Free Entry by 87.91%" (official figure just released)
  * "Empat Marketplace Besar Jadi Pemungut Pajak Mulai Agustus" (dated upcoming policy)
- breaking (illustrative shape — "effective now, published within 48h of AS OF"):
  * "Permenkumham 12/2026 diundangkan kemarin: syarat KITAS investor berubah efektif hari
    ini"
  * "Deportasi 8 WNA di Bandara Ngurah Rai hari ini usai razia overstay" (single enforcement
    action, immediate effect — not a pattern reported after the fact)
  * "PNBP visa D2 naik jadi IDR 6 juta, berlaku efektif hari ini"
- evergreen:
  * "How to apply for KITAS"
  * "The Complete Guide to PT PMA"
  * Undated lifestyle / cost-of-living explainer

live_news_reasons: list of max 3 short strings (≤80 chars each) that explain WHY you
assigned the tier. Format examples:
- "BKPM Reg 5/2026 published 2026-04-23"
- "Deportation of 12 nationals at Ngurah Rai 2026-04-25"
- "PNBP fee for D2 visa raised to IDR 5.5M (effective 2026-04-20)"
If liveness_tier is "evergreen", return an empty list.

RULES:
- headline: never include the source name, make it punchy and specific
- the_facts: journalism only, no Bali Zero branding, no "our clients"
- bali_zero_take: this is where we add our expert spin
- liveness_tier: if unsure between two tiers, pick the LOWER one. But note: routine guides
  are evergreen BY SHAPE — a dated, concrete story is NOT routine just because it's about a
  familiar topic (visa, tax, KITAS).
- live_news_reasons: only cite signals you can quote from the source content. Do not invent.
- Output ONLY valid JSON, no explanations or markdown code blocks
"""


_TIER_TO_SCORE = {"breaking": 90, "developing": 60, "evergreen": 0}

# F5 (Codex red-team, 2026-07-18): buffer above the prompt's ≤80-char
# instruction for live_news_reasons, so minor model overshoot doesn't get
# truncated mid-thought — but bounded well below the old 200, which let a
# reason balloon into a near-paragraph.
_REASON_MAX_CHARS = 120


def _claude_provider_ids() -> list[str]:
    """Return configured OAuth seats once each, without exposing token values."""

    # Seat 3 is assigned to this batch; 4-6 are the immediate quota fallback.
    candidates = [
        *(f"CLAUDE_CODE_OAUTH_TOKEN_{seat}" for seat in (3, 4, 5, 6, 1, 2)),
        "CLAUDE_CODE_OAUTH_TOKEN",
    ]
    providers: list[str] = []
    seen_tokens: set[str] = set()
    for env_name in candidates:
        token = os.environ.get(env_name, "").strip()
        if not token or token in seen_tokens:
            continue
        seen_tokens.add(token)
        suffix = env_name.removeprefix("CLAUDE_CODE_OAUTH_TOKEN")
        providers.append(f"claude{suffix.lower()}")
    # Interactive sessions may authenticate through Claude's config without
    # exporting a token, so retain that sanctioned path when no seat is set.
    return providers or ["claude"]


def _provider_attempts(prompt: str) -> list[tuple[str, list[str], str | None, int]]:
    """Return the subscription-first text-generation cascade.

    Scraped text is untrusted. Claude therefore runs with no tools and no
    session persistence. The only fallback is local Ollama, which has no tool
    surface or cloud credential. Agentic CLIs with filesystem tools are not
    eligible for this stage.
    """

    claude_bin = shutil.which("claude") or "/Users/nuzantara/.local/bin/claude"
    ollama_bin = shutil.which("ollama") or "/opt/homebrew/bin/ollama"
    claude_command = [
        claude_bin,
        "--print",
        "--model",
        "claude-sonnet-4-6",
        "--tools",
        "",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--safe-mode",
    ]
    attempts = [
        (provider, list(claude_command), prompt, 150)
        for provider in _claude_provider_ids()
    ]
    attempts.append(
        (
            "ollama",
            [ollama_bin, "run", "qwen3.5:9b"],
            prompt,
            120,
        )
    )
    return attempts


def _provider_env(provider: str) -> dict[str, str]:
    """Return the smallest environment needed by one subscription/local seat."""

    allowed = {"HOME", "LANG", "LC_ALL", "PATH", "TMPDIR"}
    if provider.startswith("claude"):
        allowed.update(
            {
                "CLAUDE_CONFIG_DIR",
                "CLAUDE_CODE_OAUTH_TOKEN",
                "ANTHROPIC_AUTH_TOKEN",
            }
        )
    elif provider == "ollama":
        allowed.add("OLLAMA_HOST")
    env = {key: value for key, value in os.environ.items() if key in allowed}
    path_prefix = "/Users/nuzantara/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
    env["PATH"] = f"{path_prefix}:{env.get('PATH', '')}"
    if provider.startswith("claude"):
        suffix = provider.removeprefix("claude")
        source_name = f"CLAUDE_CODE_OAUTH_TOKEN{suffix.upper()}"
        seat_token = os.environ.get(source_name, "").strip()
        if seat_token:
            # Forward one selected seat under the canonical child-process name.
            env["CLAUDE_CODE_OAUTH_TOKEN"] = seat_token
    if provider == "ollama":
        env["OLLAMA_NOHISTORY"] = "1"
    return env


def _run_ollama_generation(
    prompt: str,
    *,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    """Generate bounded JSON through local Ollama with reasoning disabled."""

    response = httpx.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": "qwen3.5:9b",
            "prompt": prompt,
            "stream": False,
            "think": False,
            "format": "json",
            "keep_alive": "5m",
            "options": {"temperature": 0, "num_predict": 2300},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    output = payload.get("response") if isinstance(payload, dict) else None
    if not isinstance(output, str) or not output.strip():
        raise ValueError("Ollama returned no JSON response")
    return subprocess.CompletedProcess(
        args=["ollama-http", "qwen3.5:9b"],
        returncode=0,
        stdout=output,
        stderr="",
    )


def _run_generation_cascade(
    prompt: str,
    *,
    circuit_open: set[str] | None = None,
) -> tuple[dict[str, Any] | None, str | None, str, list[str]]:
    """Return the first valid JSON completion plus raw text, provider and safe errors."""

    batch_circuit = circuit_open if circuit_open is not None else set()
    errors: list[str] = []

    for provider, command, stdin_text, timeout in _provider_attempts(prompt):
        if provider in batch_circuit:
            continue
        logger.info("Calling %s enrichment provider...", provider)
        try:
            if provider == "ollama":
                result = _run_ollama_generation(prompt, timeout=timeout)
            else:
                result = subprocess.run(
                    command,
                    input=stdin_text,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                    env=_provider_env(provider),
                    cwd="/tmp",
                )
        except (
            FileNotFoundError,
            subprocess.TimeoutExpired,
            httpx.HTTPError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            batch_circuit.add(provider)
            errors.append(f"{provider}:{type(exc).__name__}")
            logger.warning(
                "%s enrichment provider unavailable; opening batch circuit", provider
            )
            continue

        if result.returncode != 0:
            batch_circuit.add(provider)
            errors.append(f"{provider}:rc={result.returncode}")
            logger.warning(
                "%s enrichment provider returned rc=%s; opening batch circuit",
                provider,
                result.returncode,
            )
            continue
        output = (result.stdout or "").strip()
        if output:
            try:
                return _parse_enrichment_output(output), output, provider, errors
            except (json.JSONDecodeError, ValueError):
                batch_circuit.add(provider)
                errors.append(f"{provider}:invalid_json")
                logger.warning(
                    "%s enrichment provider returned invalid output; opening batch circuit",
                    provider,
                )
                continue
        batch_circuit.add(provider)
        errors.append(f"{provider}:empty")

    return None, None, "", errors


def _parse_enrichment_output(output: str) -> dict[str, Any]:
    """Extract and normalize the JSON object returned by any cascade seat."""

    cleaned = output.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()
    json_start = cleaned.find("{")
    json_end = cleaned.rfind("}") + 1
    if json_start < 0 or json_end <= json_start:
        raise ValueError("No valid JSON in response")
    payload = json.loads(cleaned[json_start:json_end])
    if not isinstance(payload, dict):
        raise ValueError("Enrichment response must be an object")
    _validate_enrichment_contract(payload)
    return _normalize_live_news_fields(payload)


def _validate_enrichment_contract(payload: dict[str, Any]) -> None:
    """Reject error envelopes and partial JSON before it can look truthy downstream."""

    if "error" in payload:
        raise ValueError("Enrichment response is an error envelope")
    for field in ("headline", "the_facts", "bali_zero_take", "in_practice", "next_steps"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Enrichment field {field} is missing or invalid")

    brief = payload.get("thirty_second_brief")
    if not isinstance(brief, dict):
        raise ValueError("Enrichment brief is missing or invalid")
    for field in ("what", "why_it_matters", "who"):
        value = brief.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Enrichment brief field {field} is missing or invalid")
    if brief.get("risk_level") not in {"low", "medium", "high"}:
        raise ValueError("Enrichment risk level is invalid")

    faq = payload.get("faq")
    if not isinstance(faq, list) or not faq:
        raise ValueError("Enrichment FAQ is missing or invalid")
    for item in faq:
        if not isinstance(item, dict) or not all(
            isinstance(item.get(field), str) and item[field].strip()
            for field in ("question", "answer")
        ):
            raise ValueError("Enrichment FAQ item is invalid")

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Enrichment metadata is missing or invalid")
    if metadata.get("priority") not in {"high", "medium", "low"}:
        raise ValueError("Enrichment priority is invalid")
    if not isinstance(metadata.get("tags"), list):
        raise ValueError("Enrichment tags are invalid")
    if payload.get("liveness_tier") not in _TIER_TO_SCORE:
        raise ValueError("Enrichment liveness tier is invalid")


def _derive_tier_from_score(raw_score: Any) -> str:
    """F2 (Codex red-team, 2026-07-18): legacy/truncated-output fallback.

    #2631's persistence contract still tolerates a `live_news_score`-only
    payload with no `liveness_tier` (e.g. a truncated JSON parse, or an
    older enrichment run). Rather than silently discarding that signal and
    collapsing to evergreen, best-effort derive a tier from the score using
    the pre-B2 80/40 buckets — with the same defensive float coercion and
    clamping the old additive-rubric normalizer used. Garbage,
    out-of-range, or absent scores fall back to evergreen (no signal),
    never raise.
    """
    try:
        score = int(round(float(raw_score)))
    except (TypeError, ValueError):
        return "evergreen"
    score = max(0, min(100, score))
    if score >= 80:
        return "breaking"
    elif score >= 40:
        return "developing"
    return "evergreen"


def _normalize_live_news_fields(enriched: dict[str, Any]) -> dict[str, Any]:
    """Trust the validated TIER, derive live_news_score deterministically.

    Growth-loop sprint B2 (2026-07-18): trust direction is INVERTED from the
    pre-B2 module. The old additive 0-100 rubric structurally amplified
    central-tendency bias (real distribution: 124/135 items scored exactly 0,
    the rest capped at 30, nothing above — the live pool was permanently
    empty). The prompt now forces the model to pick one of
    breaking/developing/evergreen directly; `live_news_score` is a DERIVED
    compatibility value for the selector's `>=40` filter and #2631's
    persistence contract, NOT a measurement — never trust a model-provided
    score over a VALID tier, even if present (stray field / prompt drift
    tolerated but ignored — see test_score_only_fallback_never_fires_when_
    tier_is_valid).

    F1 (Codex red-team, 2026-07-18): raw_tier is normalized (str + strip +
    lower) BEFORE the membership check — the pre-fix code did
    `raw_tier in _TIER_TO_SCORE` directly, which raises TypeError for a
    non-str, unhashable value (list/dict) and silently mis-evergreens a
    differently-cased/whitespace-padded valid tier ("Developing").

    F2 (Codex red-team, 2026-07-18): if the (normalized) tier is not one of
    the three valid values — missing, garbage, or a non-str type — fall
    back to deriving it from a legacy/truncated `live_news_score` if one was
    still sent (see `_derive_tier_from_score`), instead of discarding the
    signal outright.

    Either way the strict invariant downstream WR2 selector code relies on
    still holds: `tier == bucket(score)` under the existing 80/40 buckets
    (90->breaking, 60->developing, 0->evergreen).

    Mutates and returns the same dict. Missing fields are filled with
    safe defaults (tier="evergreen", score=0, reasons=[]) so downstream
    code never has to handle KeyError.
    """
    raw_tier = enriched.get("liveness_tier")
    tier_candidate = raw_tier.strip().lower() if isinstance(raw_tier, str) else ""
    if tier_candidate in _TIER_TO_SCORE:
        tier = tier_candidate
    else:
        tier = _derive_tier_from_score(enriched.get("live_news_score"))
    score = _TIER_TO_SCORE[tier]

    raw_reasons = enriched.get("live_news_reasons", [])
    if not isinstance(raw_reasons, list):
        raw_reasons = []
    reasons: list[str] = []
    for r in raw_reasons[:3]:
        if isinstance(r, str) and r.strip():
            reasons.append(r.strip()[:_REASON_MAX_CHARS])
    if tier == "evergreen":
        reasons = []

    enriched["live_news_score"] = score
    enriched["liveness_tier"] = tier
    enriched["live_news_reasons"] = reasons
    return enriched


def enrich_article_claude_cli(
    article: dict[str, Any],
    *,
    circuit_open: set[str] | None = None,
) -> dict[str, Any]:
    """
    Enrich article using Claude Code CLI (subprocess call).
    Uses Claude Max subscription quota.

    Args:
        article: Dict with keys: title, source, category, published_date, content

    Returns:
        Dict with enrichment data
    """
    logger.info(f"Enriching: {article.get('title', 'Unknown')[:50]}...")

    # Extract NLM context if available (from step 2.9)
    nlm_ctx = article.get("nlm_context") or {}
    nlm_legal = nlm_ctx.get("legal_basis", "")
    nlm_web = nlm_ctx.get("web_findings", "")
    # nlm_legal and nlm_web default to '' from .get() above — no extra guard needed

    def _escape_for_prompt(s: str) -> str:
        """Escape curly braces (for str.format) and XML tag chars (prevent tag injection)."""
        return (
            s.replace("{", "{{")
            .replace("}", "}}")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    # Escape NLM output and article content for safe prompt injection
    nlm_legal = _escape_for_prompt(str(nlm_legal or "")[:3000])
    nlm_web = _escape_for_prompt(str(nlm_web or "")[:2000])

    # F4 (Codex red-team, 2026-07-18): AS OF anchors the LIVENESS TIER "last
    # ~48h" judgment to the real current date instead of nothing — system
    # generated, not user/article input, so no _escape_for_prompt needed.
    as_of = datetime.now(timezone.utc).isoformat()

    # Build prompt — ALL article fields escaped to prevent XML tag spoofing
    prompt = ENRICHMENT_PROMPT_TEMPLATE.format(
        title=_escape_for_prompt(str(article.get("title") or "Unknown")[:300]),
        source=_escape_for_prompt(
            article.get("source_name", article.get("source", "Unknown"))
        ),
        category=_escape_for_prompt(
            article.get("qwen_category", article.get("category", "general"))
        ),
        published_date=_escape_for_prompt(
            str(
                article.get("published_date")
                or article.get("published")
                or "Unknown"
            )
        ),
        content=_escape_for_prompt(
            str(
                article.get("content")
                or article.get("text")
                or article.get("summary")
                or ""
            )[:4000]
        ),
        nlm_legal_basis=nlm_legal,
        nlm_web_findings=nlm_web,
        as_of=as_of,
    )

    try:
        enriched, output, provider, errors = _run_generation_cascade(
            prompt,
            circuit_open=circuit_open,
        )
        if enriched is None or output is None:
            return {
                "success": False,
                "error": "No enrichment provider available: " + ", ".join(errors),
            }
        logger.info("Enrichment successful via %s", provider)
        return {
            "success": True,
            "enrichment": enriched,
            "provider": provider,
            "raw_response": output,
        }
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"JSON parse error: {e}")
        return {
            "success": False,
            "error": f"Invalid JSON: {e}",
            "raw_response": output if "output" in locals() else None,
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"success": False, "error": str(e)}


def batch_enrich_articles(
    articles: list[dict[str, Any]], max_articles: int = None
) -> list[dict[str, Any]]:
    """
    Batch enrich multiple articles.

    Args:
        articles: List of article dicts
        max_articles: Limit number of articles (for testing)

    Returns:
        List of enriched articles
    """
    if max_articles:
        articles = articles[:max_articles]

    logger.info(f"Batch enriching {len(articles)} articles...")

    enriched_articles = []
    success_count = 0
    error_count = 0
    batch_circuit: set[str] = set()

    for i, article in enumerate(articles, 1):
        logger.info(
            f"\n[{i}/{len(articles)}] Processing: {article.get('title', 'Unknown')[:50]}"
        )

        result = enrich_article_claude_cli(article, circuit_open=batch_circuit)

        if result["success"]:
            success_count += 1
            enriched_articles.append(
                {
                    **article,
                    "enrichment": result["enrichment"],
                    "enrichment_provider": result["provider"],
                }
            )
        else:
            error_count += 1
            logger.error(f"Failed: {result.get('error')}")
            enriched_articles.append(
                {**article, "enrichment_error": result.get("error")}
            )

    logger.info(f"\n{'=' * 60}")
    logger.info("BATCH COMPLETE")
    logger.info(f"  Success: {success_count}/{len(articles)}")
    logger.info(f"  Errors:  {error_count}/{len(articles)}")
    logger.info(f"{'=' * 60}")

    return enriched_articles


if __name__ == "__main__":
    # Test with sample article
    test_article = {
        "title": "Indonesia Extends Digital Nomad Visa to 5 Years",
        "source": "Jakarta Post",
        "category": "immigration",
        "published_date": "2026-02-20",
        "content": """The Indonesian government announced today that the B211A digital nomad visa
        will be extended from 1 year to 5 years validity, effective March 2026. This makes Indonesia
        one of the most attractive destinations for remote workers in Southeast Asia. The visa allows
        foreigners to live and work remotely from Indonesia while earning income from abroad.
        Immigration officials stated this change aims to attract high-skilled foreign talent and 
        boost the digital economy.""",
    }

    print("=" * 60)
    print("TEST: Claude CLI Enricher")
    print("=" * 60)
    print()

    result = enrich_article_claude_cli(test_article)

    print("\n" + "=" * 60)
    print("RESULT:")
    print("=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result["success"]:
        print("\n🎉 TEST PASSED")
        sys.exit(0)
    else:
        print("\n💥 TEST FAILED")
        sys.exit(1)
