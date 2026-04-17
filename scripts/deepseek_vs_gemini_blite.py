"""B-lite shadow benchmark: DeepSeek V3.2 vs Gemini 3 Flash.

Same prompt, same system instructions, no RAG context. Measures:
- Latency (wall clock per call)
- Token I/O + estimated cost
- Response text (manual human eval later)
- Language adherence (Italian where requested)
- JSON validity (where the prompt asks for it)

Run locally on Pro (needs GEMINI_API_KEY + DEEPSEEK_API_KEY).

Output: JSON report in /tmp/bench_blite_<timestamp>.json + markdown
summary on stdout.
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GEMINI_MODEL = "gemini-3-flash-preview"
DEEPSEEK_MODEL = "deepseek-chat"

GEMINI_URL_TMPL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    "?key={key}"
)
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

# Pricing (USD per 1M tokens). Rough, as of 2026-04.
GEMINI_PRICING = {"input": 0.075, "output": 0.30}  # 3 Flash preview ≈ 2.5 Flash
DEEPSEEK_PRICING_MISS = {"input": 0.28, "output": 0.42}
DEEPSEEK_PRICING_HIT = {"input": 0.07, "output": 0.42}  # cache hit

SYSTEM_PROMPT = (
    "You are Zantara, the senior editor-advisor of Bali Zero, an Indonesian business-"
    "services firm helping expats and investors with visa, company setup, tax, and "
    "property in Bali. Answer professionally and concisely. If the user writes in "
    "Italian, reply in Italian. If the user writes in English, reply in English. "
    "When asked for a price, state that you must consult the PricingTool (do not "
    "invent prices). If the question is outside Indonesian business services, say so "
    "briefly and redirect."
)

# 12 queries: 10 canary (from scripts/rag_canary.py) + 2 zantara-style edge cases
QUERIES: list[dict[str, Any]] = [
    {
        "id": "Q01_kitas_docs",
        "lang": "en",
        "text": "What documents are needed for a KITAS work permit in Indonesia?",
    },
    {
        "id": "Q02_pma_cost",
        "lang": "en",
        "text": "How much does a PT PMA cost?",
        "wants_pricing_tool_refusal": True,
    },
    {
        "id": "Q03_kbli_restaurant",
        "lang": "en",
        "text": "What KBLI code should I use for a restaurant business in Bali?",
    },
    {
        "id": "Q04_kitap_extend",
        "lang": "en",
        "text": "What is the process to extend a KITAP?",
    },
    {
        "id": "Q05_pph21",
        "lang": "en",
        "text": "What is the PPh 21 tax rate for employees in Indonesia?",
    },
    {
        "id": "Q06_investor_visa",
        "lang": "en",
        "text": "What are the investor visa requirements and the minimum capital?",
    },
    {
        "id": "Q07_open_company",
        "lang": "en",
        "text": "How do I open a company in Bali as a foreign investor?",
    },
    {
        "id": "Q08_rptka",
        "lang": "en",
        "text": "What are the RPTKA requirements for hiring foreign workers?",
    },
    {
        "id": "Q09_property",
        "lang": "en",
        "text": "What are the property ownership rights for foreigners in Bali?",
    },
    {
        "id": "Q10_oss",
        "lang": "en",
        "text": "How does the OSS (online single submission) business licensing work?",
    },
    {
        "id": "Q11_italian_greeting",
        "lang": "it",
        "text": "Ciao, puoi dirmi quali documenti servono per il KITAS investor?",
        "wants_italian_reply": True,
    },
    {
        "id": "Q12_out_of_scope",
        "lang": "en",
        "text": "What's the best surfing spot in Australia in November?",
        "wants_scope_refusal": True,
    },
]


# ---------------------------------------------------------------------------
# Results container
# ---------------------------------------------------------------------------


@dataclass
class CallResult:
    provider: str
    model: str
    success: bool
    latency_s: float
    input_tokens: int
    output_tokens: int
    cache_hit_tokens: int
    cost_usd: float
    text: str
    error: str | None = None


@dataclass
class QueryResult:
    id: str
    lang: str
    query_text: str
    gemini: CallResult | None = None
    deepseek: CallResult | None = None
    flags: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


async def call_gemini(client: httpx.AsyncClient, prompt: str, api_key: str) -> CallResult:
    url = GEMINI_URL_TMPL.format(model=GEMINI_MODEL, key=api_key)
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024},
    }
    t0 = time.monotonic()
    try:
        resp = await client.post(url, json=payload, timeout=60.0)
        latency = time.monotonic() - t0
        if resp.status_code >= 400:
            return CallResult(
                provider="gemini",
                model=GEMINI_MODEL,
                success=False,
                latency_s=latency,
                input_tokens=0,
                output_tokens=0,
                cache_hit_tokens=0,
                cost_usd=0.0,
                text="",
                error=f"HTTP {resp.status_code}: {resp.text[:200]}",
            )
        data = resp.json()
        cand = (data.get("candidates") or [{}])[0]
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts).strip()
        usage = data.get("usageMetadata") or {}
        input_tokens = int(usage.get("promptTokenCount") or 0)
        output_tokens = int(usage.get("candidatesTokenCount") or 0)
        cost = (
            input_tokens * GEMINI_PRICING["input"] / 1_000_000
            + output_tokens * GEMINI_PRICING["output"] / 1_000_000
        )
        return CallResult(
            provider="gemini",
            model=GEMINI_MODEL,
            success=bool(text),
            latency_s=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_hit_tokens=0,
            cost_usd=cost,
            text=text,
        )
    except Exception as exc:  # noqa: BLE001
        return CallResult(
            provider="gemini",
            model=GEMINI_MODEL,
            success=False,
            latency_s=time.monotonic() - t0,
            input_tokens=0,
            output_tokens=0,
            cache_hit_tokens=0,
            cost_usd=0.0,
            text="",
            error=f"{type(exc).__name__}: {exc}",
        )


async def call_deepseek(client: httpx.AsyncClient, prompt: str, api_key: str) -> CallResult:
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
        "stream": False,
    }
    t0 = time.monotonic()
    try:
        resp = await client.post(
            DEEPSEEK_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
        latency = time.monotonic() - t0
        if resp.status_code >= 400:
            return CallResult(
                provider="deepseek",
                model=DEEPSEEK_MODEL,
                success=False,
                latency_s=latency,
                input_tokens=0,
                output_tokens=0,
                cache_hit_tokens=0,
                cost_usd=0.0,
                text="",
                error=f"HTTP {resp.status_code}: {resp.text[:200]}",
            )
        data = resp.json()
        choice0 = (data.get("choices") or [{}])[0]
        text = (choice0.get("message") or {}).get("content", "").strip()
        usage = data.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)
        cache_hit = int(usage.get("prompt_cache_hit_tokens") or 0)
        cache_miss = input_tokens - cache_hit
        cost = (
            cache_miss * DEEPSEEK_PRICING_MISS["input"] / 1_000_000
            + cache_hit * DEEPSEEK_PRICING_HIT["input"] / 1_000_000
            + output_tokens * DEEPSEEK_PRICING_MISS["output"] / 1_000_000
        )
        return CallResult(
            provider="deepseek",
            model=DEEPSEEK_MODEL,
            success=bool(text),
            latency_s=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_hit_tokens=cache_hit,
            cost_usd=cost,
            text=text,
        )
    except Exception as exc:  # noqa: BLE001
        return CallResult(
            provider="deepseek",
            model=DEEPSEEK_MODEL,
            success=False,
            latency_s=time.monotonic() - t0,
            input_tokens=0,
            output_tokens=0,
            cache_hit_tokens=0,
            cost_usd=0.0,
            text="",
            error=f"{type(exc).__name__}: {exc}",
        )


# ---------------------------------------------------------------------------
# Heuristic flags
# ---------------------------------------------------------------------------


def detect_italian(text: str) -> bool:
    """Very rough heuristic: presence of common Italian stopwords / endings."""
    if not text:
        return False
    lowered = text.lower()
    hits = sum(
        1
        for marker in (
            " che ",
            " per ",
            " sono ",
            " della ",
            " con ",
            " del ",
            " una ",
            " devi ",
            " serve ",
            " documenti",
        )
        if marker in lowered
    )
    return hits >= 2


def mentions_pricing_refusal(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    markers = ("pricingtool", "pricing tool", "consult", "verificare", "verify with")
    return any(marker in lowered for marker in markers)


def mentions_scope_refusal(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    markers = (
        "outside",
        "not related",
        "not about",
        "indonesia",
        "i focus",
        "redirect",
        "beyond",
    )
    return any(marker in lowered for marker in markers)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_benchmark() -> list[QueryResult]:
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not gemini_key:
        print("ERROR: GEMINI_API_KEY not set", file=sys.stderr)
        sys.exit(2)
    if not deepseek_key:
        print("ERROR: DEEPSEEK_API_KEY not set", file=sys.stderr)
        sys.exit(2)

    results: list[QueryResult] = []
    async with httpx.AsyncClient() as client:
        for idx, q in enumerate(QUERIES, start=1):
            print(f"[{idx:2d}/{len(QUERIES)}] {q['id']} …", end="", flush=True)
            # Run providers in parallel for speed; they don't share state.
            gemini_task = call_gemini(client, q["text"], gemini_key)
            deepseek_task = call_deepseek(client, q["text"], deepseek_key)
            gemini_res, deepseek_res = await asyncio.gather(gemini_task, deepseek_task)

            flags: dict[str, Any] = {}
            if q.get("wants_italian_reply"):
                flags["gemini_italian"] = detect_italian(gemini_res.text)
                flags["deepseek_italian"] = detect_italian(deepseek_res.text)
            if q.get("wants_pricing_tool_refusal"):
                flags["gemini_pricing_refusal"] = mentions_pricing_refusal(gemini_res.text)
                flags["deepseek_pricing_refusal"] = mentions_pricing_refusal(deepseek_res.text)
            if q.get("wants_scope_refusal"):
                flags["gemini_scope_refusal"] = mentions_scope_refusal(gemini_res.text)
                flags["deepseek_scope_refusal"] = mentions_scope_refusal(deepseek_res.text)

            qr = QueryResult(
                id=q["id"],
                lang=q["lang"],
                query_text=q["text"],
                gemini=gemini_res,
                deepseek=deepseek_res,
                flags=flags,
            )
            results.append(qr)
            print(
                f" gemini {gemini_res.latency_s:5.2f}s "
                f"deepseek {deepseek_res.latency_s:5.2f}s",
            )
    return results


def summarize(results: list[QueryResult]) -> str:
    gem_lats = [r.gemini.latency_s for r in results if r.gemini and r.gemini.success]
    ds_lats = [r.deepseek.latency_s for r in results if r.deepseek and r.deepseek.success]
    gem_cost = sum(r.gemini.cost_usd for r in results if r.gemini and r.gemini.success)
    ds_cost = sum(r.deepseek.cost_usd for r in results if r.deepseek and r.deepseek.success)
    gem_fail = sum(1 for r in results if r.gemini and not r.gemini.success)
    ds_fail = sum(1 for r in results if r.deepseek and not r.deepseek.success)

    def stats(xs: list[float]) -> str:
        if not xs:
            return "n/a"
        return f"mean={statistics.mean(xs):.2f}s p95={max(xs):.2f}s min={min(xs):.2f}s"

    lines = [
        "# B-lite Shadow Benchmark — Gemini vs DeepSeek",
        "",
        f"Queries: {len(results)}",
        f"Gemini failures: {gem_fail}  ·  DeepSeek failures: {ds_fail}",
        "",
        "## Latency",
        f"- Gemini 3 Flash: {stats(gem_lats)}",
        f"- DeepSeek Chat:  {stats(ds_lats)}",
        "",
        "## Cost (total for the 12-query run)",
        f"- Gemini:   ${gem_cost:.6f}",
        f"- DeepSeek: ${ds_cost:.6f}",
        "",
        "## Per-query latency (s)",
        "| ID | Gemini | DeepSeek | DS faster? |",
        "|---|---|---|---|",
    ]
    for r in results:
        g = r.gemini.latency_s if r.gemini else None
        d = r.deepseek.latency_s if r.deepseek else None
        faster = "✓" if g is not None and d is not None and d < g else ""
        lines.append(
            f"| {r.id} | {g:.2f} | {d:.2f} | {faster} |"
            if g is not None and d is not None
            else f"| {r.id} | n/a | n/a |  |",
        )

    lines += ["", "## Adherence flags"]
    for r in results:
        if r.flags:
            lines.append(f"- **{r.id}**: {r.flags}")

    return "\n".join(lines)


async def main() -> None:
    results = await run_benchmark()
    out_path = Path(f"/tmp/bench_blite_{int(time.time())}.json")
    serialized = [
        {
            "id": r.id,
            "lang": r.lang,
            "query_text": r.query_text,
            "gemini": asdict(r.gemini) if r.gemini else None,
            "deepseek": asdict(r.deepseek) if r.deepseek else None,
            "flags": r.flags,
        }
        for r in results
    ]
    out_path.write_text(json.dumps(serialized, indent=2, ensure_ascii=False))
    summary = summarize(results)
    print()
    print(summary)
    print()
    print(f"Full JSON report: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
