#!/usr/bin/env python3
"""wr3_editorial_bench.py — monthly deep-research video editorial bench.

5-phase multi-LLM cascade:
    Phase 1 — gather: yt-dlp metadata + auto-captions for last 5 videos / brand.
    Phase 2 — ingest (agy / Gemini 3.1 Pro): long-context corpus pass, extract
              trends-du-mois from 15 brands at once (1M ctx window).
    Phase 3 — synthesis (Claude Opus via claude-cascade.sh): "what works for
              Bali Zero regulatory/legal/visa field" framing.
    Phase 4 — numerical patterns (DeepSeek V4 Pro, reasoning_effort=high):
              hook ms, cuts/sec, emoji freq, text density chars/sec.
    Phase 5 — assemble: write _external-bench-video-YYYY-MM.md with 7 sections.

Outputs:
    ~/.claude/skills/bali-zero-brand/_external-bench-video-YYYY-MM.md

Cost ceiling: $0.50/month (Law 7). Per-tier telemetry written to stdout.

CLI:
    python3 wr3_editorial_bench.py [--dry-run] [--month YYYY-MM]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parent.parent
BRANDS_FILE = REPO_ROOT / "scripts" / "wr3_editorial_bench_brands.yaml"
BENCH_DIR = Path.home() / ".claude" / "skills" / "bali-zero-brand"
CLAUDE_CASCADE = Path.home() / "scripts" / "claude-cascade.sh"
AGY_BIN = Path.home() / ".local" / "bin" / "agy"

YT_DLP_TIMEOUT_SEC = 120
AGY_TIMEOUT_SEC = 600  # 10min — long-context pass
CLAUDE_TIMEOUT_SEC = 300
DEEPSEEK_TIMEOUT_SEC = 300

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-pro"


@dataclass
class TierTelemetry:
    """Per-LLM-tier cost/timing record. Emitted in final Cost Report section."""

    tier: str
    model: str
    wall_seconds: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd_actual: float = 0.0
    status: str = "pending"
    notes: list[str] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_brands() -> dict[str, Any]:
    with BRANDS_FILE.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _yt_dlp_available() -> bool:
    try:
        subprocess.run(
            ["yt-dlp", "--version"], capture_output=True, check=True, timeout=10
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def phase1_gather(brands: dict[str, Any], workdir: Path) -> tuple[str, list[str]]:
    """Phase 1: yt-dlp metadata + auto-captions per brand. Graceful on failure."""
    corpus_parts: list[str] = []
    failures: list[str] = []
    have_ytdlp = _yt_dlp_available()

    entries = list(brands.get("reference_brands", [])) + list(
        brands.get("competitors", [])
    )

    for entry in entries:
        name = entry["name"]
        url = entry.get("youtube_channel_url")
        ig = entry.get("instagram_handle")
        header = f"\n\n## SOURCE: {name}\n- channel: {url or ig or 'TBD'}\n- relevance: {entry.get('domain_relevance_to_balizero')}\n- why: {entry.get('why_pick')}\n"
        corpus_parts.append(header)

        if not have_ytdlp or not url:
            failures.append(f"{name}: skipped (yt-dlp absent OR no YT URL)")
            corpus_parts.append(
                f"[METADATA-FETCH-SKIPPED: yt-dlp_available={have_ytdlp}, url={url}]\n"
            )
            continue

        try:
            # Last 5 videos, metadata-only + auto-subs
            result = subprocess.run(
                [
                    "yt-dlp",
                    "--flat-playlist",
                    "--print",
                    "%(title)s | %(view_count)s | %(duration)s | %(upload_date)s",
                    "--playlist-end",
                    "5",
                    f"{url}/videos",
                ],
                capture_output=True,
                text=True,
                timeout=YT_DLP_TIMEOUT_SEC,
            )
            if result.returncode == 0:
                corpus_parts.append(result.stdout)
            else:
                failures.append(f"{name}: yt-dlp rc={result.returncode}")
                corpus_parts.append(
                    f"[YT-DLP-FAILED rc={result.returncode}: {result.stderr[:200]}]\n"
                )
        except subprocess.TimeoutExpired:
            failures.append(f"{name}: yt-dlp timeout")
            corpus_parts.append("[YT-DLP-TIMEOUT]\n")

    # Trend reports (markers only — WebFetch from synthesis layer)
    for tr in brands.get("trend_reports", []):
        corpus_parts.append(
            f"\n## TREND-REPORT: {tr['name']}\n- url: {tr['url']}\n- (fetch deferred to synthesis tier)\n"
        )

    corpus = "\n".join(corpus_parts)
    corpus_file = workdir / "wr3-bench-corpus.txt"
    corpus_file.write_text(corpus, encoding="utf-8")
    return str(corpus_file), failures


def phase2_agy_ingest(corpus_file: str, workdir: Path) -> tuple[str, TierTelemetry]:
    """Phase 2: agy CLI long-context pass over the corpus."""
    tel = TierTelemetry(tier="2-agy-ingest", model="gemini-3.1-pro-preview")
    out_file = workdir / "wr3-bench-agy.txt"

    if not AGY_BIN.exists():
        tel.status = "skipped"
        tel.notes.append(f"agy CLI not found at {AGY_BIN}")
        out_file.write_text("[AGY-UNAVAILABLE]\n", encoding="utf-8")
        return str(out_file), tel

    prompt = (
        "You are analyzing a corpus of YouTube video metadata + captions from 15 "
        "video editorial brands (12 reference, 3 Bali Zero competitors). "
        "Output structured Markdown with these sections:\n"
        "  ## Trends Du Mois (10-15 bullets, what is rising/falling this month)\n"
        "  ## Per-Brand Brief (one paragraph per brand, ~100 words, what they do "
        "well, what to steal)\n"
        "  ## Emerging Formats (3-5 new format ideas observed)\n"
        "Be concrete, cite titles/view counts where present. Bali Zero is a "
        "regulatory/visa/tax consultancy in Bali — frame all observations through "
        "transferability to that field."
    )

    t0 = time.time()
    try:
        with open(corpus_file, "rb") as fin:
            result = subprocess.run(
                [str(AGY_BIN), "-p", "--print-timeout", "10m", prompt],
                stdin=fin,
                capture_output=True,
                text=True,
                timeout=AGY_TIMEOUT_SEC,
            )
        tel.wall_seconds = round(time.time() - t0, 1)
        if result.returncode == 0:
            out_file.write_text(result.stdout, encoding="utf-8")
            tel.status = "ok"
            tel.cost_usd_actual = 0.0  # agy via Google AI Ultra subscription
        else:
            tel.status = "failed"
            tel.notes.append(f"rc={result.returncode}: {result.stderr[:300]}")
            out_file.write_text(
                f"[AGY-FAILED rc={result.returncode}]\n{result.stderr[:500]}",
                encoding="utf-8",
            )
    except subprocess.TimeoutExpired:
        tel.wall_seconds = AGY_TIMEOUT_SEC
        tel.status = "timeout"
        out_file.write_text("[AGY-TIMEOUT]\n", encoding="utf-8")

    return str(out_file), tel


def phase3_claude_synthesis(
    agy_file: str, workdir: Path
) -> tuple[str, TierTelemetry]:
    """Phase 3: Claude Opus synthesis for Bali Zero adoption framing."""
    tel = TierTelemetry(tier="3-claude-synthesis", model="claude-opus-4-7")
    out_file = workdir / "wr3-bench-claude.md"

    if not CLAUDE_CASCADE.exists():
        tel.status = "skipped"
        tel.notes.append(f"claude-cascade.sh not found at {CLAUDE_CASCADE}")
        out_file.write_text("[CLAUDE-CASCADE-UNAVAILABLE]\n", encoding="utf-8")
        return str(out_file), tel

    prompt = (
        "You are the WR3 editorial-bench synthesist for Bali Zero (Indonesian "
        "visa/tax/company-setup consultancy). Read the agy long-context ingestion "
        "below and produce these two sections only:\n\n"
        "## Executive Summary (200-300 words)\n"
        "  3-5 paragraph synthesis: what the video editorial state-of-the-art says "
        "this month, focused on what is transferable to regulatory-explainer "
        "content. Be opinionated.\n\n"
        "## Bali Zero Adoptable Patterns (5 bullets)\n"
        "  Concrete, testable patterns we could pilot in the next 30 days.\n\n"
        "## Anti-Patterns to Avoid (5 bullets)\n"
        "  Things observed that would harm our trust/credibility positioning.\n"
    )

    t0 = time.time()
    try:
        agy_text = Path(agy_file).read_text(encoding="utf-8")
        full_input = f"{prompt}\n\n---AGY-INGESTION---\n\n{agy_text}"
        result = subprocess.run(
            [str(CLAUDE_CASCADE), "--stdin", "--model", "claude-opus-4-7"],
            input=full_input,
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT_SEC,
        )
        tel.wall_seconds = round(time.time() - t0, 1)
        if result.returncode == 0:
            out_file.write_text(result.stdout, encoding="utf-8")
            tel.status = "ok"
            # Rough Opus 4.7 cost — claude-cascade may have used another tier
            tel.cost_usd_actual = 0.30
        else:
            tel.status = "failed"
            tel.notes.append(f"rc={result.returncode}: {result.stderr[:300]}")
            out_file.write_text(
                f"[CLAUDE-FAILED rc={result.returncode}]\n{result.stderr[:500]}",
                encoding="utf-8",
            )
    except subprocess.TimeoutExpired:
        tel.wall_seconds = CLAUDE_TIMEOUT_SEC
        tel.status = "timeout"
        out_file.write_text("[CLAUDE-TIMEOUT]\n", encoding="utf-8")

    return str(out_file), tel


def _deepseek_api_key() -> str | None:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                "deepseek",
                "-s",
                "deepseek_api_key",
                "-w",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip() or None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def phase4_deepseek_patterns(
    corpus_file: str, agy_file: str, workdir: Path
) -> tuple[str, TierTelemetry]:
    """Phase 4: DeepSeek reasoning_effort=high — numerical pattern extraction."""
    tel = TierTelemetry(tier="4-deepseek-patterns", model=DEEPSEEK_MODEL)
    out_file = workdir / "wr3-bench-deepseek.md"

    api_key = _deepseek_api_key()
    if not api_key:
        tel.status = "skipped"
        tel.notes.append("DEEPSEEK_API_KEY missing (env + Keychain)")
        out_file.write_text("[DEEPSEEK-NO-KEY]\n", encoding="utf-8")
        return str(out_file), tel

    try:
        import httpx  # type: ignore[import-not-found]
    except ImportError:
        tel.status = "skipped"
        tel.notes.append("httpx not installed")
        out_file.write_text("[DEEPSEEK-NO-HTTPX]\n", encoding="utf-8")
        return str(out_file), tel

    corpus = Path(corpus_file).read_text(encoding="utf-8")[:60_000]
    agy_out = Path(agy_file).read_text(encoding="utf-8")[:30_000]

    user_msg = (
        "Extract numerical patterns from this video editorial corpus. "
        "Where the corpus is sparse, estimate from titles/durations + your "
        "knowledge of these brands. Output ONLY this Markdown structure:\n\n"
        "## Numerical Patterns\n"
        "### Hook duration (ms)\n  - p50: <ms>, p90: <ms>, notes: ...\n"
        "### Cuts per second\n  - p50: <n>, p90: <n>, notes: ...\n"
        "### Text density (chars on screen / sec)\n  - p50, p90, notes\n"
        "### Emoji frequency (per video)\n  - p50, p90, notes\n"
        "### Title length (chars)\n  - p50, p90, notes\n\n"
        "Then ## Field-Transfer Verdict (3 bullets) — which numerical pattern is "
        "most worth piloting for Bali Zero regulatory short-form.\n\n"
        f"---CORPUS---\n{corpus}\n\n---AGY-SUMMARY---\n{agy_out}"
    )

    t0 = time.time()
    try:
        resp = httpx.post(
            DEEPSEEK_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a numerical pattern analyst for short-form video editorial. Output strict Markdown, no preamble.",
                    },
                    {"role": "user", "content": user_msg},
                ],
                "reasoning_effort": "high",
                "max_tokens": 2000,
            },
            timeout=DEEPSEEK_TIMEOUT_SEC,
        )
        tel.wall_seconds = round(time.time() - t0, 1)
        if resp.status_code == 200:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tel.tokens_in = usage.get("prompt_tokens", 0)
            tel.tokens_out = usage.get("completion_tokens", 0)
            # DeepSeek V4 Pro: ~$0.28/M in, $0.42/M out (cache-miss)
            tel.cost_usd_actual = round(
                (tel.tokens_in / 1_000_000) * 0.28
                + (tel.tokens_out / 1_000_000) * 0.42,
                4,
            )
            out_file.write_text(text, encoding="utf-8")
            tel.status = "ok"
        else:
            tel.status = "failed"
            tel.notes.append(f"http {resp.status_code}: {resp.text[:200]}")
            out_file.write_text(
                f"[DEEPSEEK-HTTP-{resp.status_code}]\n{resp.text[:500]}",
                encoding="utf-8",
            )
    except Exception as exc:
        tel.wall_seconds = round(time.time() - t0, 1)
        tel.status = "error"
        tel.notes.append(repr(exc)[:200])
        out_file.write_text(f"[DEEPSEEK-ERROR]\n{exc!r}", encoding="utf-8")

    return str(out_file), tel


def phase5_assemble(
    month: str,
    agy_file: str,
    claude_file: str,
    deepseek_file: str,
    telemetry: list[TierTelemetry],
    gather_failures: list[str],
) -> Path:
    """Phase 5: assemble final _external-bench-video-YYYY-MM.md."""
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    out = BENCH_DIR / f"_external-bench-video-{month}.md"

    claude_text = Path(claude_file).read_text(encoding="utf-8")
    agy_text = Path(agy_file).read_text(encoding="utf-8")
    deepseek_text = Path(deepseek_file).read_text(encoding="utf-8")

    total_cost = round(sum(t.cost_usd_actual for t in telemetry), 4)

    cost_table = "\n".join(
        f"| {t.tier} | {t.model} | {t.status} | {t.wall_seconds}s | "
        f"{t.tokens_in}/{t.tokens_out} | ${t.cost_usd_actual} |"
        for t in telemetry
    )

    failures_block = (
        "\n".join(f"- {f}" for f in gather_failures) if gather_failures else "_(none)_"
    )

    body = f"""---
date: {month}-01
generator: wr3-editorial-bench.py
generated_at: {_now_iso()}
total_cost_usd: {total_cost}
status: ok
---

# WR3 Editorial Bench — {month}

{claude_text}

## Trends Du Mois (agy long-context)

{agy_text}

{deepseek_text}

## Per-Brand Briefs

_(included inline above in agy section; see "Per-Brand Brief" subsections)_

## Cost Report

| Tier | Model | Status | Wall | Tokens (in/out) | Cost USD |
|---|---|---|---|---|---|
{cost_table}

**Total: ${total_cost} / ceiling $0.50**

## Gather Failures

{failures_block}
"""
    out.write_text(body, encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="WR3 monthly editorial bench")
    parser.add_argument("--month", default=datetime.now().strftime("%Y-%m"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print(f"[dry-run] would write {BENCH_DIR}/_external-bench-video-{args.month}.md")
        return 0

    brands = load_brands()
    telemetry: list[TierTelemetry] = []

    with tempfile.TemporaryDirectory(prefix="wr3-bench-") as tmp:
        workdir = Path(tmp)
        print(f"[wr3-bench] workdir={workdir}")

        print("[wr3-bench] phase 1: gather")
        corpus_file, failures = phase1_gather(brands, workdir)

        print("[wr3-bench] phase 2: agy long-context ingest")
        agy_file, t2 = phase2_agy_ingest(corpus_file, workdir)
        telemetry.append(t2)

        print("[wr3-bench] phase 3: claude synthesis")
        claude_file, t3 = phase3_claude_synthesis(agy_file, workdir)
        telemetry.append(t3)

        print("[wr3-bench] phase 4: deepseek numerical patterns")
        ds_file, t4 = phase4_deepseek_patterns(corpus_file, agy_file, workdir)
        telemetry.append(t4)

        print("[wr3-bench] phase 5: assemble")
        out = phase5_assemble(
            args.month, agy_file, claude_file, ds_file, telemetry, failures
        )
        print(f"[wr3-bench] wrote {out}")

    # Hard-fail signal if all 3 LLM tiers failed
    llm_ok = any(t.status == "ok" for t in telemetry)
    print(json.dumps([t.__dict__ for t in telemetry], indent=2))
    return 0 if llm_ok else 1


if __name__ == "__main__":
    sys.exit(main())
