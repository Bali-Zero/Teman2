# CLAUDE.md — research/ specialist rules

> Loaded natively by Claude Code when working under `research/`. Moved verbatim out of the
> repo-root `CLAUDE.md` on 2026-09-04 (context-diet, root-CLAUDE.md-becomes-index).

---

## 15. Research Capture Convention

Ricerche sostanziose (≥400 parole + ≥3 fonti + checklist + dominio in {property, visa, tax, hr, compliance} + client-case) → `~/nuzantara/research/<domain>/YYYY-MM-DD-slug.md`.

**Frontmatter obbligatorio**: `date`/`domain`/`client_case`/`sources`.

**Proposta save**: *"Questa mi sembra da salvare in `research/<domain>/` — procedo? (y/n)"*

Su y: write file + append 1-line to `~/.claude/projects/-Users-nuzantara/memory/MEMORY.md` under `## Research Captures`. Solo se `domain=property`: push body as NB-5 text source (`d9438180-5e63-4e2a-a473-6061101f6a8d`) via `mcp__notebooklm-mcp__source_add`. Altri domini: non toccare NB curati.

**NEVER auto-promote** to `apps/backend-rag/backend/kb/` (that's curated). Research stays ad-hoc auditable.
