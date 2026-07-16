---
name: skill-catalog
description: Use when a user request does NOT match any currently-loaded skill — BEFORE answering "I don't have a skill for that". The full Claude Code skill ecosystem (Tier 2/3 + hundreds of community skills) is NOT all installed; their descriptions are catalogued in the MOS, not in context. This skill tells you to query the MOS catalog and install the right skill on-demand.
---

> **CANON**: repo `.claude/` (vendored 2026-07-17, PR process-toolkit SSOT) — shadows the `~/.claude/` HOME copy. Edit HERE, never in `$HOME`. Pro/Mini shadow it on `git pull`.

# Skill Catalog — on-demand skill discovery

**The problem this solves**: Claude Code loads ALL installed skill descriptions into context at session start. To avoid context bloat (the orchestration-decay 8→0 regression), only Tier-1 skills + a curated few are installed. Everything else lives in the **MOS catalog** — searchable, zero context cost until queried.

## When to use

- A request doesn't match any loaded skill in your list.
- Before saying "no skill for that" or improvising.
- When the user asks about a domain you suspect has a dedicated skill (deploy checklist, incident response, RAG tuning, document generation, marketing, etc.).

## How (the on-demand cascade)

1. **Query the MOS catalog** (two verified paths — the prefix string `SKILL-CATALOG` itself breaks FTS5 because of the hyphen, so query by DOMAIN not by prefix):

   ```bash
   # a) by domain/intent — FTS5 keyword (e.g. "sandbox", "python", "video", "security", "trailofbits")
   ~/.claude/scripts/mem query "<domain keyword>"

   # b) full catalog dump — deterministic LIKE (use when "show me everything available")
   sqlite3 -header -column ~/.claude/memory.db \
     "SELECT id, importance, content FROM memories WHERE content LIKE 'SKILL-CATALOG%' ORDER BY importance DESC;"
   ```

   Catalog entries are `pattern`-type, prefixed `SKILL-CATALOG:` (or `SKILL-CATALOG-WARN:` for ones that should NOT be installed) with name + 1-line + install command.

2. **If a match is found** → install it at the moment of need:

   ```
   /plugin install <plugin>@<marketplace>      # for plugin-hosted skills
   # or for repo-hosted: git clone <repo> /tmp/x && audit SKILL.md && cp to ~/.claude/skills/
   ```

   Then `/reload-plugins`. The skill is now loaded and triggers.

3. **If no catalog match** → it's genuinely uncatalogued. Say so honestly, and optionally propose researching + cataloguing it.

## Discipline (anti-sprawl, the whole point)

- **NEVER pre-install Tier 2/3 in bulk** — that re-creates the context bloat this skill exists to prevent.
- **Install on-demand, use, then consider disabling** if it was a one-off (`/plugin` disable keeps it catalogued but out of context).
- The MOS catalog is the source of truth for "what skills EXIST but aren't loaded". Keep it current: when you research a new skill worth knowing, `mem save pattern "SKILL-CATALOG: <name> — <1-line> — install: <cmd>" <importance>`.

## Tiering (loaded vs catalogued)

- **Tier 1 (installed, always loaded)**: security (trailofbits static-analysis/differential-review/second-opinion, security-guidance), qdrant, claude-md-management, + the Nuzantara custom DIR skills.
- **Tier 2 (installed selectively)**: engineering@knowledge-work-plugins (incident-response, deploy-checklist, etc.).
- **Tier 3+ (catalogued in MOS, NOT installed)**: everything else — query the catalog to find + install on-demand.

Reference: `research/operations/2026-05-31-global-claude-skills-study.md`, lesson `feedback_orchestration_first.md` (the decay this prevents).
