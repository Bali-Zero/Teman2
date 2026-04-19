# Kita Feed Generator — GENOME

## Mission
Produce `apps/mata-garuda/data/kita_feed.json` with up to 20 top enriched
items for future consumption by `kita.balizero.com/newsroom`.
Layer 5 — Distribuzione.

## Inputs
- Redis stream `garuda:enriched` (read-only)

## Output
- File `apps/mata-garuda/data/kita_feed.json` with schema:
  ```
  {
    "generated_at": ISO timestamp,
    "version": 1,
    "count": int,
    "items": [
      {
        "id": str,
        "title": str,
        "summary": str (max 400 chars),
        "url": str,
        "domain": str,
        "relevance_score": int,
        "source": str,
        "timestamp": str
      }
    ]
  }
  ```

## Filter
- `public_safe == true`
- `relevance_score >= 3`
- non-empty `title`
- Any business domain allowed (newsroom is broader than TG channel)

## Ordering
- `relevance_score` DESC, then `timestamp` DESC

## Success criteria
- Feed written atomically (tmp + rename)
- ≤ 20 items
- No frontend change in this PR — the file is the handoff contract

## Known gotchas
- No delete of old feed; overwrite is the update strategy (daily cron).
- Frontend wiring is deferred — future work is to have
  `kita.balizero.com/newsroom` fetch this file (copied to its public dir
  by a separate deploy step).

## Mutations history
_(empty at creation)_
