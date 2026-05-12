---
date: 2026-05-12
wave: 5
producer: bali_intel_scraper
status: implemented
---

# Wave 5 — Bali Intel Scraper → Intel Lake

## Scope

`apps/bali-intel-scraper/scripts/run_intel_pipeline.py` (cron 03:00 WITA, Pro-local via OpenClaw) is the highest-volume producer with 5 native destinations:

1. Qdrant `intel_articles` collection (vector search)
2. Fly `/api/intel/scraper/submit` → News Room staging (Postgres + filesystem)
3. Fly `/api/intel/staging/<type>/<id>/cover` (cover image upload)
4. Telegram notification (bilingual)
5. `data/published_articles.json` history dedup

Wave 5 adds a 6th hook: enqueue to local SQLite outbox at the moment of successful staging submission, so the Intel Lake observation table captures every news/visa article — alongside intel_radar (Wave 1), mata-garuda nlm_feeder (Wave 6), and the rest.

## Patch applied

Inside `_push()` async helper of the publish step (the function that POSTs to `/api/intel/scraper/submit`), after `r.status_code in (200, 201)` and `item_id` extraction, call `intel_lake_outbox.enqueue` with:

- `producer_name=bali_intel_scraper`
- `canonical_url=art.url || f"bali-intel-scraper://item/{item_id}"` (fallback for missing URL)
- `content_hash=sha256(title + " " + url)[:32]`
- `source_domain=parsed_netloc || "bali-intel-scraper"`
- `language=art.language || "id"`
- `jurisdiction="ID-bali" if intel_type=='news' else "ID-national"`
- `topic_tags=[intel_type, "news-room", category]`
- `raw_payload={intel_type, staging_item_id, tier, source}`

Best-effort: failure to import or enqueue is logged as WARN and swallowed — MUST NOT break the existing staging submission.

## Verification

- `ast.parse` clean on patched file
- Outbox module already smoke-tested in Wave 1 + Wave 3

## Volume estimate

Bali Intel Scraper is the highest-volume producer:

- 609 URL fixed sources × variable scrape success rate × dedup
- Empirical: ~40-100 articles published per daily run (post-dedup, post-scoring)
- Combined with Wave 1/2/3/4 producers: total observation rate to outbox now ~100-200/day

Drain worker (60s tick, batch=100) is well within capacity. Backend `/api/intel/lake/observations:batch` rate-limit assumed at 1 batch/s = 100k/day theoretical ceiling, several orders of magnitude above current need.

## Multi-destination invariant

The 5 native destinations stay untouched. Wave 5 adds a 6th observation channel (SQLite outbox) without touching the existing flow. If the lake outbox or backend is unavailable, the scraper still:

- Pushes to Qdrant (RAG)
- Submits to News Room staging (blog pipeline)
- Sends Telegram
- Updates `published_articles.json`

This is the "additive observability" pattern; failure isolation by design.

## Stop-loss

Same as previous waves: `~/.intel-lake-wave2-blocked` file pauses Wave 6 if shadow-validate detects >15% divergence.

## Next: Wave 6 (Mata Garuda)

24 harvester agents share a common `base_worker.py`. Single patch point: add enqueue inside `stream_publish_redis` so every Mata Garuda producer (arxiv, reddit, twitter, youtube, github, imigrasi_harvester, kemkumham_harvester, bkpm_harvester, ...) becomes a lake producer in one shot.
