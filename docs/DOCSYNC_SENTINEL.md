# DocSentinel — Automated Documentation Stats Synchronizer

**Added:** 2026-03-24
**File:** `scripts/docs_sync.py`
**Cost:** $0 (deterministic, no LLM)

## What It Does

Extracts live metrics from the codebase. **Enumerations** (which app, which runbook, which skill, which workflow) are injected into markdown between `<!-- DOCSYNC:KEY_START -->` / `<!-- DOCSYNC:KEY_END -->` markers, so the atlas tables stay in sync with the tree. **Volume counts** (router count, service count, vector document count, …) are still computed but deliberately NOT written to any tracked page — they are served live by `--json` / `--coverage`. See the retirement note under "Markers in Docs".

## How It Works

```
Code Change → docs_sync.py extracts stats → Injects into marker regions → Docs updated
```

### Stats Extracted

| Stat               | Source                       | Method                        |
| ------------------ | ---------------------------- | ----------------------------- |
| Router count       | `router_registration.py`     | regex `api.include_router(`   |
| Service count      | `backend/services/**/*.py`   | file count (excl. `__init__`) |
| Test file count    | `backend/tests/**/test_*.py` | file count                    |
| App count          | `apps/*/`                    | directory count               |
| Version            | `package.json`               | JSON parse                    |
| Qdrant collections | `/health` endpoint           | HTTP GET with cache fallback  |
| Qdrant documents   | `/health` endpoint           | HTTP GET with cache fallback  |
| Embedding model    | `/health` endpoint           | HTTP GET with cache fallback  |
| Channel count      | `backend/channels/*/`        | directory count               |
| KG nodes/edges     | cached                       | hardcoded (changes rarely)    |

### Markers in Docs

| File                      | Markers                                            | Content                                   |
| ------------------------- | -------------------------------------------------- | ----------------------------------------- |
| `INDEX.md`                | `LIVING_ORGANS`, `WORKFLOWS_INDEX`, `SKILLS_INDEX` | Apps table, workflows table, skills table |
| `docs/runbooks/README.md` | `RUNBOOKS_INDEX`                                   | Runbooks table                            |

**Only enumerations are injected. Volume counts are not, and this is enforced.**
`TECH_STATS`, `QUICK_NUMBERS`, `AUTOMATION_COVERAGE`, `BACKEND_STATS`, `VECTOR_STATS`
and `EMBEDDING_FROZEN` were retired on 2026-08-16 (Merge-OS v3 step 4 / §C2,
`research/operations/2026-08-14-merge-os-v3-research-council.md`): a committed count
went stale on `main` on nearly every backend PR and handed the next innocent PR a red
required check (W86). They live in `RETIRED_COUNT_KEYS` in `scripts/docs_sync.py` and
`scripts/tests/test_docs_sync_atlas.py` fails if one comes back as a template or as a
marker in a tracked page. Read the numbers with `--json` (or `--coverage` for the
plists-vs-docs ratio) instead.

`README.md` and `docs/AI_ONBOARDING.md` stay in `TARGET_FILES` with zero markers, on
purpose: that is what keeps `--check` and the anti-regrowth corpus watching them.
(`FEATURE_FLAGS` in README.md was never a docs_sync marker — that table is
hand-maintained; its source of truth is `fly secrets list -a nuzantara-rag`.)
`CLAUDE.md` lost its markers in F44 and is deliberately not a target.

### Marker Format

```markdown
<!-- DOCSYNC:KEY_START -->

Content that gets auto-replaced

<!-- DOCSYNC:KEY_END -->
```

**Rule:** Never edit content between markers manually — it will be overwritten.

## Usage

```bash
# Update all markers in-place
python scripts/docs_sync.py

# Check if docs are stale (CI mode, exit 1 if stale)
python scripts/docs_sync.py --check

# Show what would change without writing
python scripts/docs_sync.py --diff

# Output raw stats as JSON — the channel for every volume count
python scripts/docs_sync.py --json

# Plists-vs-docs coverage, one line (also printed as a CI ::notice::)
python scripts/docs_sync.py --coverage

# Quiet mode (for hooks)
python scripts/docs_sync.py --quiet
```

## Triggers

| Trigger         | File                              | When                                                                                | Blocking             |
| --------------- | --------------------------------- | ----------------------------------------------------------------------------------- | -------------------- |
| **Manual**      | `python scripts/docs_sync.py`     | On demand                                                                           | —                    |
| **Post-commit** | `.husky/post-commit`              | After every git commit                                                              | No (background)      |
| **CI/CD**       | `.github/workflows/docs-sync.yml` | PRs touching a marker input (job-level relevance check; see the regex in that file) | Yes (fails if stale) |
| **Cron**        | `scripts/docs_sync_cron.sh`       | Daily at 03:17                                                                      | No (auto-commits)    |

### Setting Up Cron

```bash
# On Pro (development machine)
crontab -e
# Add:
17 3 * * * /Users/nuzantara/Projects/nuzantara/scripts/docs_sync_cron.sh

# On Air (server)
crontab -e
# Add:
17 3 * * * /Users/antonellosiano/Projects/nuzantara/scripts/docs_sync_cron.sh
```

## Graceful Degradation

- **Qdrant unreachable:** Uses cached values from `.docs_sync_cache.json`
- **Cache missing:** Falls back to last known hardcoded values
- **Post-commit fails:** Silent (background, non-blocking)
- **CI check fails:** PR blocked, developer runs `python scripts/docs_sync.py`

## Adding New Markers

First: **is it an enumeration or a count?** If the block would carry a number that moves
with code volume, stop — it does not belong in a marker at all, it belongs in `--json`
(see the retirement note above; `scripts/tests/test_docs_sync_atlas.py` fails the PR that
tries). Markers are for lists of organs a reader navigates by.

1. Add a template to `TEMPLATES` dict in `docs_sync.py`:

```python
TEMPLATES["MY_NEW_INDEX"] = lambda s: _render_rows(s["my_organs"])
```

2. Add markers to target .md file:

```markdown
<!-- DOCSYNC:MY_NEW_INDEX_START -->

placeholder

<!-- DOCSYNC:MY_NEW_INDEX_END -->
```

3. Add target file to `TARGET_FILES` list if not already there.

4. Run `python scripts/docs_sync.py` to verify.

## Architecture

```
scripts/docs_sync.py
├── Extractors (pure Python, no dependencies)
│   ├── count_routers()      → regex on router_registration.py
│   ├── count_services()     → glob on backend/services/
│   ├── count_test_files()   → glob on backend/tests/
│   ├── count_apps()         → listdir on apps/
│   ├── get_version()        → json.load on package.json
│   ├── get_qdrant_stats()   → HTTP GET /health + cache
│   ├── count_channels()     → listdir on backend/channels/
│   └── get_kg_stats()       → cached hardcoded values
├── Templates (string formatters per marker key)
├── inject_markers()         → regex replace between marker pairs
└── main()                   → CLI: --check, --diff, --json, --coverage, --quiet
```

No external dependencies. Uses only Python stdlib (`json`, `re`, `pathlib`, `urllib`).
