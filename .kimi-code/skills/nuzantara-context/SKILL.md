---
name: nuzantara-context
description: Deep-context map of the Nuzantara/Bali Zero system for Kimi working in this repo — where every truth lives, which rules are blood-bought, and what Kimi's role in the workflow is. Load whenever a task touches this repo beyond a single file.
---

# Nuzantara deep context (for Kimi)

You are working inside **Nuzantara**, the production AI-organism of **Bali Zero** (Indonesian
visa/company/tax/property agency). The root `AGENTS.md` gives you the operating contract
(machine map, external-agent rules, worktree discipline). This skill tells you **where the
truth lives** so you never guess.

## Your role in this team's workflow (decided 2026-07-19)

- **You build — a Claude session verifies.** Branches/diffs/artifacts only; never merge,
  never push `main`, never deploy, never publish (Legge 5). Your reviewer is adversarial by
  design (generator≠grader) — write for review, cite file:line for every claim.
- Your strong chairs here: **cross-family second opinion / refuter** (via `kimi` CLI),
  **agentic web research** (BrowseComp-class), **spreadsheet/data batch**, **frontend/UI
  and artifact drafts** (sites/slides/docs — brand surfaces still pass the WR2 constitution
  gates before any use).
- **Scope tightly.** K3's known failure mode is over-proactivity on ambiguous tasks: state
  your reading in one line, take the narrowest interpretation, never invent adjacent work.

## Where the truth lives (read, don't guess)

| Need                                                     | Authority                                                                                                |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Project rules, invariants, deploy                        | `CLAUDE.md` (repo root — Claude-oriented but authoritative for everyone)                                 |
| Ecosystem laws (PII, sovereignty, publish gate)          | `SYMBIOSIS.md`                                                                                           |
| Operative checklist before building anything             | `VADEMECUM.md`                                                                                           |
| Repo atlas (where every organ lives)                     | `INDEX.md`                                                                                               |
| Blood-bought failure patterns (10 families)              | `.claude/rules/cicatrix-superscar.md` — check BEFORE repeating a known mistake                           |
| WR2 editorial pipeline (carousels → Instagram)           | `.claude/skills/wr2/SKILL.md` (the corner: anatomy, live state, hard rules)                              |
| Master loop the Claude sessions run                      | `.claude/skills/modus/SKILL.md` · suspended-work ledger: `.claude/skills/modus/PENDING-ARMS.md`          |
| Backend specifics (Sentry PII hook, migrations, routers) | `apps/backend-rag/CLAUDE.md`                                                                             |
| Prices                                                   | `PricingTool` ONLY (`backend/data/bali_zero_official_prices_2026.json`) — never hardcode, never estimate |
| Project memory (decisions/discoveries)                   | `~/.claude/projects/*/memory/MEMORY.md` index (M5: `-Users-balizero-nuzantara`) — read-only for you      |

## Hard invariants you must never break

- **Embedding model FROZEN**: `text-embedding-3-small` (1536 dims). Changing it invalidates ~100k vectors.
- **KBLI payloads are FLAT** (no nesting) — fields per `CLAUDE.md` §9.
- **Evidence thresholds are 5 NAMED gates** (`backend/services/rag/agentic/_abstain_policy.py`) — never "tidy" them into one number.
- **Queue JSONs** (`apps/war-room/output/queue/*.json`) — canonical writers only, never hand-edit.
- **Migrations**: custom SQL in `backend/db/migrations_v2/NNN_*.sql` with `-- === ROLLBACK ===` marker (NOT Alembic).
- **Anthropic SDK banned** (`ANTHROPIC_API_KEY` never) — Claude is reached only via the `claude` CLI OAuth path.
- **No paid per-token APIs** without the owner's explicit authorization (your own Kimi access is flat-subscription — fine).

## Test & verify commands (run before handing work back)

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"   # import chain
PYTHONPATH=. pytest backend/tests/<relevant-path> -q                              # scoped tests
ruff check backend/                                                               # lint
```

Frontend: `cd apps/mouth && npm run lint && npm run test`.

## Communication

- Owner is **Zero** (Italian; real name private). Commits/PRs/docs in **English**,
  conventional format `feat|fix|chore|refactor|docs(scope): subject`.
- Your handoff = a branch + a 5-line summary: what changed, why, what you tested, what you
  did NOT verify, open risks. Honesty about untested parts is valued over polish.
