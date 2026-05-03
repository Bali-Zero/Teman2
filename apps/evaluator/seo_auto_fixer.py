#!/usr/bin/env python3
"""
SEO Auto-Fixer — consumes high_escalations from seo_observe_report and fixes them autonomously.

Supported fix types:
  - fix_meta_description_fallback: generates ai_summary via Haiku, patches DB

Called by OpenClaw job `seo-auto-fixer` after each seo-guardian-observe run.
"""
import asyncio
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

SHARED_MEMORY = Path.home() / ".openclaw" / "workspace" / "shared_memory"
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag",
)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_SEO_CHAT_ID", "1125336968")
BACKEND_URL = os.environ.get("BACKEND_URL", "https://nuzantara-rag.fly.dev")
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "internal-scraper-key")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def send_telegram(msg: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        log(f"[NO-TOKEN] {msg}")
        return
    try:
        payload = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log(f"Telegram error: {e}")


def load_observe_report() -> dict:
    path = SHARED_MEMORY / "seo_observe_report.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def save_fixer_report(report: dict) -> None:
    SHARED_MEMORY.mkdir(parents=True, exist_ok=True)
    path = SHARED_MEMORY / "seo_fixer_report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False))


def generate_meta_description(slug: str, title: str, body_excerpt: str) -> str:
    """Call Claude Haiku to generate a 155-char SEO meta description."""
    if not ANTHROPIC_API_KEY:
        # Fallback: clean title truncation
        return title[:155]

    prompt = (
        f"Write a compelling SEO meta description (max 155 characters) for this article.\n"
        f"Title: {title}\n"
        f"Excerpt: {body_excerpt[:500]}\n\n"
        f"Rules: factual, no clickbait, include Indonesia/Bali if relevant, end naturally.\n"
        f"Output ONLY the description, no quotes, no extra text."
    )
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
            return body["content"][0]["text"].strip()[:155]
    except Exception as e:
        log(f"Haiku error: {e}")
        return title[:155]


def fetch_article_from_backend(category: str, slug: str) -> dict:
    """Fetch article from backend API to get title + body content."""
    try:
        url = f"{BACKEND_URL}/api/intel/articles/{category}/{slug}"
        req = urllib.request.Request(url, headers={"X-API-Key": SCRAPER_API_KEY})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        pass
    # Try scraper endpoint
    try:
        url = f"{BACKEND_URL}/api/scraper/article/{category}/{slug}"
        req = urllib.request.Request(url, headers={"X-API-Key": SCRAPER_API_KEY})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        return {}


# ─── Fix handlers ─────────────────────────────────────────────────────────────

async def fix_meta_description(conn: asyncpg.Connection, escalation: dict) -> dict:
    """
    Fix: article has no ai_summary → generate one with Haiku and patch DB.
    Returns {status, slug, generated_description}
    """
    target_url = escalation.get("target", "")  # e.g. /business/2026-guide-...
    parts = target_url.strip("/").split("/")
    if len(parts) < 2:
        return {"status": "error", "reason": f"Cannot parse URL: {target_url}"}

    category, slug = parts[0], parts[1]
    log(f"  Fixing meta description for /{category}/{slug}")

    # Check current DB state
    row = await conn.fetchrow(
        "SELECT id, title, summary, ai_summary FROM news_items WHERE slug = $1",
        slug
    )
    if not row:
        return {"status": "skipped", "reason": f"Article not found in DB: {slug}"}

    if row["ai_summary"] and len(row["ai_summary"]) > 30:
        return {"status": "skipped", "reason": "ai_summary already populated"}

    title = row["title"] or slug.replace("-", " ").title()
    body_excerpt = row["summary"] or ""

    # If body_excerpt is empty, try to get from backend API
    if not body_excerpt:
        article_data = fetch_article_from_backend(category, slug)
        body_excerpt = (
            article_data.get("summary") or
            article_data.get("excerpt") or
            article_data.get("content", "")[:500] or
            ""
        )

    # Generate with Haiku
    description = generate_meta_description(slug, title, body_excerpt)
    log(f"  Generated: {repr(description[:80])}")

    # Patch DB
    await conn.execute(
        "UPDATE news_items SET ai_summary = $1 WHERE slug = $2",
        description, slug
    )

    return {
        "status": "fixed",
        "slug": slug,
        "category": category,
        "generated_description": description,
    }


# ─── Batch fixer ──────────────────────────────────────────────────────────────

async def fix_all_missing_meta_descriptions(conn: asyncpg.Connection, limit: int = 10) -> list[dict]:
    """
    Find all published articles missing ai_summary and fix them in batch.
    This runs regardless of escalations — proactive cleanup.
    """
    rows = await conn.fetch(
        """
        SELECT id, slug, title, summary, category
        FROM news_items
        WHERE (ai_summary IS NULL OR length(ai_summary) < 30)
          AND published_at IS NOT NULL
        ORDER BY published_at DESC
        LIMIT $1
        """,
        limit
    )
    if not rows:
        log("Batch fix: all articles already have ai_summary")
        return []

    log(f"Batch fix: found {len(rows)} articles missing ai_summary (showing up to {limit})")
    results = []
    for row in rows:
        slug = row["slug"]
        category = row["category"] or "business"
        title = row["title"] or slug.replace("-", " ").title()
        body_excerpt = row["summary"] or ""

        if not body_excerpt:
            article_data = fetch_article_from_backend(category, slug)
            body_excerpt = (
                article_data.get("summary") or
                article_data.get("excerpt") or
                article_data.get("content", "")[:500] or
                ""
            )

        description = generate_meta_description(slug, title, body_excerpt)
        log(f"  [{slug[:50]}] → {repr(description[:60])}")

        await conn.execute(
            "UPDATE news_items SET ai_summary = $1 WHERE slug = $2",
            description, slug
        )
        results.append({
            "status": "fixed",
            "slug": slug,
            "category": category,
            "generated_description": description,
            "source": "batch",
        })

    return results


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    log("=== SEO Auto-Fixer start ===")

    report = load_observe_report()
    escalations = report.get("high_escalations", [])

    try:
        conn = await asyncpg.connect(DB_URL)
    except Exception as e:
        log(f"DB connection failed: {e}")
        send_telegram(f"⚠️ SEO Auto-Fixer: DB connection failed\n`{e}`")
        sys.exit(1)

    results = []
    fixed = 0
    errors = 0

    # Process escalation-driven fixes
    if escalations:
        log(f"Found {len(escalations)} HIGH escalation(s)")
        for esc in escalations:
            fix_type = esc.get("type", "")
            log(f"Processing escalation: {fix_type} on {esc.get('target')}")

            try:
                if fix_type == "fix_meta_description_fallback":
                    result = await fix_meta_description(conn, esc)
                else:
                    result = {"status": "unsupported", "type": fix_type}

                results.append({**result, "escalation_id": esc.get("id")})

                if result["status"] == "fixed":
                    fixed += 1
                    log(f"  ✅ Fixed: {result.get('slug')}")
                elif result["status"] == "skipped":
                    log(f"  ⏭ Skipped: {result.get('reason')}")
                else:
                    errors += 1
                    log(f"  ❌ Error: {result.get('reason', result)}")

            except Exception as e:
                log(f"  ❌ Exception: {e}")
                results.append({"status": "error", "reason": str(e), "escalation_id": esc.get("id")})
                errors += 1
    else:
        log("No HIGH escalations")

    # Always run batch fix for articles missing ai_summary (proactive, max 10 per run)
    try:
        batch_results = await fix_all_missing_meta_descriptions(conn, limit=10)
        results.extend(batch_results)
        batch_fixed = len(batch_results)
        fixed += batch_fixed
        if batch_fixed:
            log(f"Batch: fixed {batch_fixed} articles missing ai_summary")
    except Exception as e:
        log(f"Batch fix error: {e}")
        errors += 1

    await conn.close()

    # Count remaining unfixed
    try:
        conn2 = await asyncpg.connect(DB_URL)
        remaining = await conn2.fetchval(
            "SELECT COUNT(*) FROM news_items WHERE (ai_summary IS NULL OR length(ai_summary) < 30) AND published_at IS NOT NULL"
        )
        await conn2.close()
    except Exception:
        remaining = -1

    # Save fixer report
    fixer_report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_number": report.get("run_number", 0),
        "fixed": fixed,
        "errors": errors,
        "skipped": len(escalations) - len([r for r in results if r.get("escalation_id")]),
        "remaining_without_ai_summary": remaining,
        "results": results,
    }
    save_fixer_report(fixer_report)

    # Telegram report
    if fixed > 0 or errors > 0:
        lines = ["🔧 *SEO Auto-Fixer*"]
        batch_count = len([r for r in results if r.get("source") == "batch"])
        esc_count = fixed - batch_count
        if esc_count > 0:
            lines.append(f"✅ Escalations fixed: {esc_count}")
        if batch_count > 0:
            lines.append(f"✅ Batch fixed: {batch_count} articles")
        if remaining >= 0:
            lines.append(f"📊 Still missing ai_summary: {remaining}")
        if errors > 0:
            lines.append(f"❌ Errors: {errors}")
        for r in results:
            if r["status"] == "fixed" and r.get("source") != "batch":
                lines.append(f"  • `{r.get('slug', '?')}`: {r.get('generated_description', '')[:80]}")
        send_telegram("\n".join(lines))

    log(f"=== Done: {fixed} fixed, {errors} errors, {remaining} remaining ===")


if __name__ == "__main__":
    asyncio.run(main())
