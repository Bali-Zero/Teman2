# DocSentinel — Automated Documentation Stats Synchronizer

**Added:** 2026-03-24
**File:** `scripts/docs_sync.py`
**Cost:** $0 (deterministic, no LLM)

## What It Does

Extracts live metrics from the codebase and injects them into markdown files between `<!-- DOCSYNC:KEY_START -->` / `<!-- DOCSYNC:KEY_END -->` markers. Numbers like router count, service count, vector document count stay always in sync with the actual code.

## How It Works

```
Code Change → docs_sync.py extracts stats → Injects into marker regions → Docs updated
```

### Stats Extracted

| Stat | Source | Method |
|------|--------|--------|
| Router count | `router_registration.py` | regex `api.include_router(` |
| Service count | `backend/services/**/*.py` | file count (excl. `__init__`) |
| Test file count | `backend/tests/**/test_*.py` | file count |
| App count | `apps/*/` | directory count |
| Version | `package.json` | JSON parse |
| Qdrant collections | `/health` endpoint | HTTP GET with cache fallback |
| Qdrant documents | `/health` endpoint | HTTP GET with cache fallback |
| Embedding model | `/health` endpoint | HTTP GET with cache fallback |
| Channel count | `backend/channels/*/` | directory count |
| KG nodes/edges | cached | hardcoded (changes rarely) |

### Markers in Docs

| File | Markers | Content |
|------|---------|---------|
| `README.md` | `TECH_STATS`, `FEATURE_FLAGS` | Tech stack table, feature flags table |
| `CLAUDE.md` | `BACKEND_STATS`, `VECTOR_STATS`, `EMBEDDING_FROZEN` | Backend metrics, vector counts, frozen warning |
| `docs/AI_ONBOARDING.md` | `QUICK_NUMBERS` | One-line stats summary |

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

# Output raw stats as JSON
python scripts/docs_sync.py --json

# Quiet mode (for hooks)
python scripts/docs_sync.py --quiet
```

## Triggers

| Trigger | File | When | Blocking |
|---------|------|------|----------|
| **Manual** | `python scripts/docs_sync.py` | On demand | — |
| **Post-commit** | `.husky/post-commit` | After every git commit | No (background) |
| **CI/CD** | `.github/workflows/docs-sync.yml` | PRs touching `apps/` | Yes (fails if stale) |
| **Cron** | `scripts/docs_sync_cron.sh` | Daily at 03:17 | No (auto-commits) |

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

1. Add a template to `TEMPLATES` dict in `docs_sync.py`:
```python
TEMPLATES["MY_NEW_STAT"] = lambda s: f"My stat: {s['routers']} routers"
```

2. Add markers to target .md file:
```markdown
<!-- DOCSYNC:MY_NEW_STAT_START -->
placeholder
<!-- DOCSYNC:MY_NEW_STAT_END -->
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
└── main()                   → CLI: --check, --diff, --json, --quiet
```

No external dependencies. Uses only Python stdlib (`json`, `re`, `pathlib`, `urllib`).
