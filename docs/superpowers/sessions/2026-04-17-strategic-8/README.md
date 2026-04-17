# 8 Sessioni Strategiche Parallele — 2026-04-17

**Modello:** Claude Opus 4.7 (1M context), xhigh effort preconfigurato nei terminali
**Pattern:** 8 filoni indipendenti (A), zero blocking, deliverable autonomi
**Asimmetria:** Pro A/A/C/D + Air A/C/C/D

## Mappa sessioni

| Slot | Macchina | Tipo | Filone | Prompt |
|------|----------|------|--------|--------|
| Pro-1 | Pro | A 3-5h | L2 Client App portal | [pro-1-l2-client-app.md](pro-1-l2-client-app.md) |
| Pro-2 | Pro | A 3-5h | Opus 4.7 §7 routing + cost | [pro-2-opus47-routing.md](pro-2-opus47-routing.md) |
| Pro-3 | Pro | C 12-24h | L3 Team Ops end-to-end | [pro-3-l3-team-ops.md](pro-3-l3-team-ops.md) |
| Pro-4 | Pro | D variabile | Bundle audit + QA regression | [pro-4-bundle-qa.md](pro-4-bundle-qa.md) |
| Air-1 | Air | A 3-5h | UU PDP coverage push | [air-1-pdp-coverage.md](air-1-pdp-coverage.md) |
| Air-2 | Air | C 12-24h | S09 Services solidification | [air-2-s09-services.md](air-2-s09-services.md) |
| Air-3 | Air | C 12-24h | GraphRAG 2.0 completion | [air-3-graphrag-completion.md](air-3-graphrag-completion.md) |
| Air-4 | Air | D variabile | S11/S12/S13 cherry-pick | [air-4-solidification-jolly.md](air-4-solidification-jolly.md) |

## Regole comuni per tutte le sessioni

1. **Lavora in worktree** (`.worktrees/<branch-name>`) — NON su main
2. **Piccoli commit frequenti** con messaggi `feat(x):`, `fix(x):`, `refactor(x):`
3. **Mai push** senza aver letto il diff finale — aspetta l'umano
4. **Mai merge in main** autonomo
5. **Log progressi** in `docs/superpowers/sessions/2026-04-17-strategic-8/logs/<slot>.log`
6. **Stop conditions**: se loop di errori > 3, fermarsi e scrivere report
7. **Memory non toccare**: scrivere memorie solo se feedback esplicito dall'umano
8. **Skills obbligatorie**: superpowers:brainstorming → superpowers:writing-plans → superpowers:executing-plans (o subagent-driven-development)

## Pattern di esecuzione

Ogni prompt è **self-contained**: può essere incollato in una sessione Claude Opus 4.7 fresca senza altro contesto. Include:
- Obiettivo
- Scope (cosa SÌ / cosa NO)
- Plan path o design path
- Deliverables attesi
- Stop conditions
- Checkpoint intermedi
