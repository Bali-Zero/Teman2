# imigrasi.go.id scoped mirror + diff-alert

**Scope: NOT a full-site copy.** ~124 pages that feed the Bali Zero visa
engine, versioned daily/weekly, with a Telegram alert when one of them
changes. The value is the repeated crawl + diff, not a one-off copy
(cicatrix W90: "anche il ground-truth invecchia" — a static snapshot goes
stale the moment Imigrasi edits a list; this exists to catch that edit).

## What it watches

| Category | Count | Tier | Examples |
|---|---|---|---|
| VoA/BVK/Calling subject lists + parent | 4 | daily | `/wna/daftar-negara-voa-bvk-calling-visa[/...]` |
| FAQ (documented for its OWN staleness, not trusted) | 1 | daily | `/faq/visa/negara-mana-saja...e-voa` |
| Visa catalog index | 1 | daily | `/wna/daftar-visa-indonesia` |
| News/announcement index (v2 — removals announced here first) | 1 | daily | `/berita` |
| Regional kanim mirrors (schema counter-proof) | 3 | daily | depok / bontang / ngurah rai |
| Per-visa-code detail pages | 114 | weekly | `/wna/daftar-visa-indonesia/{CODE}` |

The 114 codes are a **copy** of `apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py`,
not a live import (keeps this module free of the backend-rag app's
dependency chain so it can run standalone from cron). Re-check with:

```
scripts/imigrasi_mirror/run-mirror.sh --verify-codes
```

All 124 URLs in `urls.py` were verified live (200, real content) before being
committed — 123 on 2026-08-08, the `/berita` v2 index on 2026-08-09. `/berita`
was also extraction-stability probed (identical extract text across two fetches
3s apart) so the daily diff fires only on a genuinely new headline, never on
volatile page furniture. See the module docstring.

## Cadence (coded, NOT yet installed as cron)

```
run-mirror.sh --tier daily     # the 10 pages that "morde" — run this one daily
run-mirror.sh --tier weekly    # the 114 per-code pages — run this one weekly
run-mirror.sh --tier all       # everything in one pass
run-mirror.sh --select parent,voa,bvk,calling,faq-evoa   # ad-hoc subset
```

Both daily and weekly are armed as LaunchAgents on Mini
(`com.nuzantara.imigrasi-mirror.{daily,weekly}`).

## Self-health (does the mirror still RUN?)

The mirror alerts on content DIFFS — it is structurally blind to its own
death: an unloaded cron, a broken venv, a network outage or a site-wide 5xx
either never runs `run.py` or captures nothing, and in every case NO diff
fires, so the channel stays silent while the sentinel is dead (scar #2
"Esiste ≠ Armato").

Two independent parts close that gap (kept SEPARATE from the crawl so the
alarm never shares its failure mode — scar W108):

1. **Heartbeat** — every completed `run.py` writes
   `~/logs/imigrasi-mirror-heartbeat.json` (env `IMIGRASI_MIRROR_HEARTBEAT`),
   OUTSIDE the data git repo (so it never breaks the `nothing_to_commit`
   clean signal), recording tier / captured / failed / epoch.

2. **`healthcheck.py`** — pure stdlib (no venv, no network to the mirrored
   site), on its OWN LaunchAgent (`com.nuzantara.imigrasi-mirror.healthcheck`,
   08:30 WITA — after the 06:30 daily run + buffer). Reads the heartbeat and
   fires a Telegram `🚑 SELF-HEALTH` alert when it is:
   - **ABSENT / malformed** → CRITICAL (never ran, or logs wiped)
   - **STALE** > `--max-age-hours` (default 26h) → CRITICAL (cron unloaded / machine off)
   - **captured 0** of N → CRITICAL (network/proxy dead, site 5xx)
   - **failed** > `--max-failed` (default 0) → WARN (ran but stumbled)

   Healthy → silent, exit 0. Unhealthy → alert + exit 1. The decision is a
   pure function (`evaluate_health`) covered by `healthcheck.py --selftest`
   (no network) with guilt+innocence pairs. Dedup key is
   `(severity, date)` — one send per severity per day (a persistent outage
   doesn't spam; a new day re-alerts).

## Where the data lives

A **separate git repo**, not this monorepo (avoids repo bloat from daily
snapshot commits):

```
~/nuzantara-imigrasi-mirror/
  snapshots/
    2026-08-08/
      voa-subjects.txt
      bvk-subjects.txt
      ...
```

Each run writes `snapshots/<date>/<slug>.txt` and commits. **Git history IS
the version log** — no separate versioning mechanism. Override the path
with `--data-root` or `IMIGRASI_MIRROR_DATA_ROOT` (used by `--selftest`'s
hermetic fixtures, never the real path).

## How the diff+alert works

1. For each page, extract clean readable text (`extract.py` strips
   nav/header/footer/script/style, tries a priority list of CMS
   content-selectors, falls back to `<body>` — the goal is diffing what a
   human reader sees, not markup churn).
2. Find the most recent **prior** snapshot for that page's slug (searches
   back through however many days it takes — a weekly-tier page's
   "previous" may be ~7 days old, not just yesterday).
3. If content differs, build a unified-diff excerpt (capped at 25 lines,
   **always states `N of M` when truncated** — W97: no silent caps) and
   send ONE Telegram alert per changed page.

## Telegram: routed through `tg_notify.py`, not a direct call

This module shells out to `scripts/tg_notify.py` (repo's ONE Telegram
gateway, born 2026-07-06 after ~240 files each got secret-handling wrong in
its own way) instead of calling the Bot API directly. Concretely this
avoids re-introducing:

- **W104** — judging `redis-cli`-style bare exit codes instead of the reply.
  `tg_notify` already does the HTTP+JSON handling correctly.
- **W115** — passing message content on argv, readable by any `ps` on the
  box. This module pipes the message over **stdin**.
- **W55** — a single-attempt send that drops silently on failure. `tg_notify`
  spools unsendable P0s (`p0_unsent`) instead of losing them.

Tier used: `p0` (a country added/removed from VoA/BVK/Calling is a real,
actionable change for the visa engine — not routine noise). Dedup key is an
**explicit content hash of the new snapshot**, not `tg_notify`'s default
text-derived identity — the default strips numbers, which would treat two
genuinely different diffs on the same page as "the same condition" and mute
the second one. A content-hash key means: identical repeat send → deduped
correctly; different diff → never falsely muted.

## Guardrails actually enforced in code

- Async `httpx`, never `requests` (Golden Rule #4).
- Honest User-Agent: `BaliZero-visa-mirror/1.0 (+https://balizero.com; contact: zero@balizero.com)`.
- Global rate limit ≥2s between request **dispatches**, on top of (not
  instead of) a `--concurrency` cap (default 4 in flight).
- Bounded retries (default 3, exponential backoff) on transient errors only
  (timeout/5xx/429) — a 404/403 is not retried.
- **Overall wall-clock deadline** per run (tier-scaled: 600s daily / 1800s
  weekly / 2400s all) — never an unbounded crawl loop (the `fs_usage`
  firehose lesson). Anything not reached by the deadline is reported as
  `skipped_deadline`, never silently dropped.
- `robots.txt` honored per host, cached once per run, **fail-open** on a
  fetch/parse error (a robots.txt hiccup must not black out a public
  government list page — verified live 2026-08-08: `imigrasi.go.id/robots.txt`
  is `Allow: /` anyway).

## Tests

```
scripts/imigrasi_mirror/run-mirror.sh --selftest    # no network
scripts/imigrasi_mirror/run-mirror.sh --verify-codes
```

`--selftest` covers `extract_text` (guilt: script/nav stripped; innocence:
real content survives, including the body-fallback path when no CMS
selector matches), `compute_diff` (counts, and that a large diff DOES
truncate with an explicit `N of M` note), and `find_previous_snapshot`
(finds the most recent prior date, searches past simple d-1 gaps, and
returns `None` — not a false diff — on a genuinely first capture).
