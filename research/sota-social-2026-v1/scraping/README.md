# Competitor scrape Vino — 2026-04-23

**Source:** delivered by Vino (Bali Zero IG research) via claude-in-chrome scraping session on 2026-04-23.
**Archived from:** `~/Downloads/Senza nome 3.rtf`.
**Format:** pipe-separated, schema per `reference_claude_in_chrome_ig_scraping.md` (prompt v3 with `catatan` column for provenance).

## Counts

- Accounts: **18**
- Unique post URLs: **210**
- Target window: last ~60 days per account (Feb → Apr 2026)

## Accounts (18)

Business / immigration / legal (Bali Zero competitor set):
1. emerhub.bali
2. incorp_id
3. celerity.click
4. indobizcorner.id
5. indolegality
6. balibusinessconsulting
7. spun.global
8. nomadsembassy (originale: `nomaaadsembassy` nell'header — handle reale `nomadsembassy`)
9. digital.nomad.info

Bali lifestyle / expat / news:
10. lawakbalinew (comedy Bali)
11. balitransitsolutions (rental + visa services)
12. thebalibible
13. indonesiaexpat
14. radar.bali
15. canggucommunity (originale: `canggucomunity` header)
16. expatroasters (F&B, benchmark non-competitor)
17. balibuda (originale: `balibudha` header; handle reale `balibuda`)
18. gnfi (Good News From Indonesia, pan-Indonesia reach)

## Known caveats documented by Vino in `catatan`

- **Hidden likes** concentrate on 3 Bali Zero direct competitors: `incorp_id` 100%, `celerity.click` ~87%, `emerhub.bali` ~60%. Other 15 accounts show public like counts.
- **Pinned posts** inflate oldest rows (e.g. `digital.nomad.info` 82.9K likes from Jan 2026 pinned reel). Flagged in `catatan` with `pinned post (YYYY-MM-DD, lama)`.
- **video_views_count** empty for most reels — IG hides view count for non-authenticated sessions.
- **9 viral outliers** already annotated in `catatan` field (>3× account average).
- **fonte=dom** vs **fonte=json** — audit trail of scrape method. DOM = scroll grid visible count; JSON = SSR hydration payload.

## Downstream usage

This dump is the **input corpus for Fase 1 Task 13** (`scripts/sota_ingest_competitors.py`, still TODO).
Once Task 13 ships, this file becomes the training data for:
- **M13 monthly retrain** (`scripts/m13_monthly_retrain.py`) — competitor baseline for Consiglio v1 deliberation.
- **M13 weekly report** (`scripts/m13_weekly_report.py`) — benchmark column "Bali Zero vs competitor avg" per pillar.
- **Cadence engine** (`06_cadence_engine.json`) — validation of optimal posting hours WITA against 18-account distribution.

## Immutability

Do not edit `.txt` or `.rtf` in place. This is a frozen research snapshot.
Normalized CSV (future Task 13 output) will live at `../competitors/vino_2026-04-23.csv`.
