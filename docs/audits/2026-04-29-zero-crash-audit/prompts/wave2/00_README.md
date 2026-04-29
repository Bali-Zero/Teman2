# Wave 2 — 3 sessioni, 9 fix concurrent

**Goal:** 9 fix in parallelo via agent teams. 3 sessioni totali (1 mia + 2 tue).

## Architettura

| Sessione | Macchina | Tipo | Agent del team | Fix |
|---|---|---|---|---|
| **Sessione 1** | Pro | Mia (questa) | A, B, C | P0-1, NB-A, P1-11 |
| **Sessione 2** | Pro | Tu apri | X, Y, Z | P0-2 fase 1, P1-8, NB-D |
| **Sessione 3** | Air | Tu apri | X, Y, Z | P0-5 fase 1, P1-7, P1-10 |

**Totale fix concurrent: 9.**

Tu apri solo 2 sessioni Claude Code Max (Opus 4.7 max effort). Una su Pro, una su Air. Per ognuna, copi il prompt e lo dai alla sessione.

## Comandi per te

### Sessione 2 (Pro)

In una nuova window/pane Pro:
```
claude
```
Poi nella sessione Claude:
```
leggi /Users/nuzantara/Desktop/nuzantara/docs/audits/2026-04-29-zero-crash-audit/prompts/wave2/wave2-team-pro.md ed esegui
```

### Sessione 3 (Air)

```
ssh air
cd ~/Projects/nuzantara
git fetch origin && git checkout main && git pull origin main
claude
```
Poi nella sessione Claude:
```
leggi /Users/antonellosiano/Projects/nuzantara/docs/audits/2026-04-29-zero-crash-audit/prompts/wave2/wave2-team-air.md ed esegui
```

## Cosa fa ogni agent dentro ogni team

Pattern uniforme (replicato da Wave 1):

1. **Brainstorm cross-LLM** (Codex GPT-5.5 + Gemini 3.1 Pro + DeepSeek v4-pro + NotebookLM NB-1) tramite `coord_brainstorm` — independent, no Opus opinion seeded
2. **Worktree isolato** in `../nuzantara-wt/<fix-id>/` (no `.git/` race)
3. **TDD**: tests prima, codice dopo
4. **Coord commit/push/deploy** con file lock `~/.claude/locks/git-{commit,push}.lock`
5. **Auto-merge** dopo CI verde
6. **MOS save** al merge

## Lock coordination

Tutti i 9 worker (3 nei miei team + 3 sessione 2 + 3 sessione 3) condividono i lock files in `~/.claude/locks/`. Quando uno commita, gli altri aspettano. Quando uno pusha, gli altri aspettano. Stessa infra di Wave 1.

## File index

- `00_README.md` — questo file
- `wave2-team-pro.md` — prompt per Sessione 2 (Pro)
- `wave2-team-air.md` — prompt per Sessione 3 (Air)
- `_coordination.sh` — symlink/copy da wave1 (riusiamo)

## Track C (dopo Track A merged)

I 3 fix dipendenti (P0-2 fase 2, P0-5 fase 2, P0-6) NON sono in questo batch. Partono dopo che P0-2 fase 1 e P0-1 sono in main. Se il primo batch finisce in ~1 giorno, Track C parte il giorno dopo con altre 2-3 sessioni.

Per ora: lanciamo 9 fix indipendenti. Track C lo schedulamo dopo.

## Track D (Zero handoff)

NB-E Brevo email fallback + P1-9 MCP partition: aspettano tua decisione architetturale. NON in nessun batch.
