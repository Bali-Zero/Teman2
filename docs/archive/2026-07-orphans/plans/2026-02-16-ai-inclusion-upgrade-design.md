# Design: AI Inclusion Upgrade — Approccio B Stratificato

**Data:** 2026-02-16
**Status:** Implementato
**Scope:** Cursor + Windsurf full integration con MCP + rules stratificate per dominio

---

## Problema

Il sistema multi-AI (Claude, Kimi, Gemini, Cursor, Windsurf) aveva un'integrazione disomogenea:

- `.cursorrules` deprecato (sostituito da `.cursor/rules/*.mdc` in Cursor 0.45)
- Windsurf senza rules, senza MCP, senza Cascade memories
- Nessun `AGENTS.md` (file hub letto da Cursor + Augment + GitHub Copilot)
- MCP non configurato né in Cursor né in Windsurf

## Soluzione: Approccio B Stratificato

Ogni AI riceve solo il contesto rilevante al file che sta editando, grazie al glob-scoping.

## Architettura Implementata

```
.cursor/
  mcp.json                  ← MCP project-level (versioned)
  rules/
    00-always.mdc           ← alwaysApply: stack + golden rules + owner
    01-backend.mdc          ← globs: apps/backend-rag/**/*.py
    02-frontend.mdc         ← globs: apps/mouth/**/*.{ts,tsx,js,jsx}
    03-deploy.mdc           ← globs: **/fly.toml, **/Dockerfile
    04-kbli.mdc             ← globs: **/kbli*

.windsurf/
  rules/
    always.md               ← sempre attivo
    backend.md              ← Python/FastAPI
    frontend.md             ← Next.js/TypeScript
    deploy.md               ← Fly.io + Vercel
  cascade-memory-seed.md    ← seed per Cascade memories (prima apertura)

~/.codeium/windsurf/
  mcp_config.json           ← MCP globale Windsurf
  memories/
    global_rules.md         ← global rules Cascade (tutti i workspace)

AGENTS.md                   ← hub: Cursor + Augment + GitHub Copilot
```

## Completamento Stack Multi-AI

| AI       | Config                           | MCP                                      | Rules/Skill                   |
| -------- | -------------------------------- | ---------------------------------------- | ----------------------------- |
| Claude   | `CLAUDE.md` ✅                   | `.mcp.json` ✅                           | `skills/nuzantara-member/` ✅ |
| Kimi     | `.kimi/NUZANTARA_IDENTITY.md` ✅ | `~/.kimi/config.toml` ✅                 | `skills/kimi-nuzantara/` ✅   |
| Gemini   | `GEMINI.md` ✅                   | —                                        | —                             |
| Cursor   | `.cursor/rules/*.mdc` ✅         | `.cursor/mcp.json` ✅                    | —                             |
| Windsurf | `.windsurf/rules/*.md` ✅        | `~/.codeium/windsurf/mcp_config.json` ✅ | Cascade memories seeded ✅    |
| OpenClaw | `docs/OPENCLAW_SYSTEM.md` ✅     | eredita da modelli                       | —                             |

## Note Implementazione

- `.cursorrules` mantenuto per compatibilità backward ma `.cursor/rules/` ora è primario
- Cascade memories workspace-scoped non sono editabili direttamente — usare `cascade-memory-seed.md` come guida per la prima sessione
- Windsurf rules activation mode (Always/Glob/Model Decision) si configura dall'UI Windsurf, non dal file
- `AGENTS.md` è compatibile con OpenAI Codex, GitHub Copilot, Augment Code — un file per tutti

## Manutenzione

Quando cambia architettura, aggiornare in questo ordine:

1. `docs/AI_ONBOARDING.md` (fonte canonica)
2. `CLAUDE.md`
3. `AGENTS.md`
4. `GEMINI.md`
5. `.cursor/rules/00-always.mdc` + regola specifica
6. `.windsurf/rules/always.md` + regola specifica
7. `.kimi/NUZANTARA_IDENTITY.md`
8. `skills/nuzantara-member/SKILL.md`
