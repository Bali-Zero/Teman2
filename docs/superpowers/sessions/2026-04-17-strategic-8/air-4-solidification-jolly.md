# Air-4 — S11/S12/S13 Solidification Jolly (D variabile)

## Obiettivo

Jolly Air: estendere il ciclo solidification su 3 layer candidati (Agents / LLM / Middleware) con priorità a scelta runtime basata su audit rapido.

## Contesto

- Macchina: Air (cwd `/Users/antonellosiano/Projects/nuzantara`)
- Pattern solidification come Air-2 S09, ma scope più ristretto (jolly)
- 3 layer candidati in `apps/backend-rag/backend/`:
  - **S11 Agents** (`backend/agents/`) — federation v3.1, agent routing
  - **S12 LLM** (`backend/llm/`) — Ollama client, routing, fallback
  - **S13 Middleware** (`backend/middleware/`) — auth, CORS, logging, rate limit

## Scope SÌ

### Fase 0: Audit rapido (1-2h, obbligatorio)

- Per ciascuno dei 3 layer: LOC, TODO, test coverage, last modified
- Scegli **1 layer** su cui focalizzare (criterio: peggiore coverage + più TODO + criticità)

### Fase 1: Fix concentrato sul layer scelto (4-8h)

- 3-5 fix atomici
- Pattern solidification (no refactor architetturale)
- Test TDD

### Fase 2: Report (1h)

- `docs/superpowers/solidification-reports/S1N-<layer>.md`

## Scope NO

- NON fare tutti e 3 (sono troppi per jolly, stai in 1 solo)
- NON overlap con Air-2 S09 Services
- NON toccare backend/core/ (foundational, rischio alto)
- NON merge main, NON deploy

## Deliverables attesi

1. Audit JSON dei 3 layer in `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-4-audit-layers.json`
2. Decisione motivata su layer scelto in log
3. Branch `solidification/s1N-<layer>` con 3-5 commit
4. Report `S1N-<layer>.md`
5. Log finale `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-4.log`

## Stop conditions

- Durata scelta in base al layer (3-10h)
- Se audit rivela layer molto complesso (>200 TODO) → ferma, scegli altro o scrivi solo audit
- Overlap detected con altri branch → stop e chiedi

## Skills

1. `superpowers:using-superpowers`
2. `superpowers:using-git-worktrees`
3. `superpowers:systematic-debugging`
4. `superpowers:test-driven-development`
5. `simplify`

## Prompt da incollare (Air via tmux)

```
Sessione Air D jolly variabile. Obiettivo: estendere solidification a 1 layer tra
S11 Agents, S12 LLM, S13 Middleware.

Fase 0 (obbligatoria): audit rapido 3 layer (LOC, TODO, coverage). Scegli il
peggiore. Motiva nel log.

Fase 1: 3-5 fix atomici sul layer scelto (pattern solidification, no refactor).

Fase 2: report docs/superpowers/solidification-reports/S1N-<layer>.md

Worktree .worktrees/s1N-<layer> branch solidification/s1N-<layer> da main.

Stop variabile 3-10h. NO merge main. NO overlap con Air-2 S09 Services.

Log: docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-4.log

Usa superpowers:systematic-debugging + TDD + simplify. Inizia dall'audit.
```
