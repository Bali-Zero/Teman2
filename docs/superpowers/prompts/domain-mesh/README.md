# Domain Mesh — Phase Continuation Prompts

Prompt drop-in per continuare il **Domain Mesh autonomic system** (Bali Zero / Nuzantara) dopo l'implementazione iniziale del 2026-05-08.

## Stato corrente (snapshot 2026-05-08)

✅ **Implementato e merged in main**:

- Phase 0 (foundations, 8 moduli) — PR #523
- Phase 1 (B1 Setup Team, 9 moduli) — PR #534 + #536 + #540
- Design doc + 7 SOTA research reports — PR #518
- 9 bug fixed via 3 wave external review (PR #525, #526, #529)
- 106 test green
- Cron `com.balizero.setup-team.daily` LIVE su Pro

📦 **Pendente**:

| Fase | Dominio | Prompt | Stima |
|---|---|---|---|
| **Phase 2** | Setup Team extend (Property + Labor) | `01-phase2-setup-team-extend.md` | 5-7 giorni |
| **Phase 3** | B2 Tax Engine | `02-phase3-tax-engine.md` | 10-14 giorni |
| **Phase 4** | B3 Marketing Pulse | `03-phase4-marketing.md` | 7-10 giorni |
| **Phase 5** | B4 Antonello Lab | `04-phase5-antonello-lab.md` | 6-9 giorni |
| **Phase 6** | B5 Bali Macro | `05-phase6-bali-macro.md` | 5-8 giorni |
| **Phase 7** | B6 Nexus OSINT | `06-phase7-nexus-osint.md` | 7-10 giorni |
| **Phase 8** | Cross-domain federation | `07-phase8-cross-domain-federation.md` | 8-12 giorni |

Totale stima: **48-70 giorni solo-dev** per completamento full mesh.

## Come usare

1. **Apri nuova sessione Claude Code**.
2. **Decidi quale fase avanzare** (di solito sequenza naturale: 2 → 3 → 4 → 5 → 6 → 7 → 8).
3. **Copia il prompt corrispondente** dal file `.md` della fase.
4. **Incollalo come PRIMA riga** della sessione.
5. Claude leggerà spec + research + codebase, poi eseguirà brainstorm → plan → implementation con subagent-driven.

In alternativa: usa il **master orchestrator** (`00-MASTER-ORCHESTRATOR.md`) che si auto-orienta e ti chiede quale fase.

## Pattern condiviso da tutte le fasi

Tutte seguono questa pipeline:

1. Read spec + research + codebase
2. `superpowers:brainstorming` (conferma 5-fase lifecycle adattato al dominio)
3. `superpowers:writing-plans` → file in `docs/superpowers/plans/`
4. `superpowers:subagent-driven-development` (TDD per task, push dopo ogni commit)
5. External review wave (Codex GPT-5 + DeepSeek v4 + NotebookLM NB-1, optional Sonnet 4.6 + security-review skill)
6. Triage feedback indipendente, fix bug reali (non taste)
7. PR + auto-merge

## Regole non negoziabili (in ogni fase)

- **Niente Anthropic API key** — solo `claude --print` subprocess via OAuth Max
- **mata-garuda deps minimal** — `pydantic>=2` core, pesanti in `[project.optional-dependencies] foundations`
- **Lazy imports PEP 562** — per tutto ciò che tocca ML deps
- **Branch hijack scar protection** — `git push` dopo OGNI commit, branch verify pre-Edit
- **Cron LaunchAgent** — absolute venv python, atomic mv snapshot, kill switch env var, PATH includes `/Users/nuzantara/.local/bin`
- **TDD per task** — test fail → impl → test pass → commit + push
- **External review obbligatorio** prima del merge (qualità SOTA)

## Ordine consigliato (priorità business)

Se Antonello vuole massimo impatto business veloce:

1. **Phase 2** (Setup Team complete) — chiude il dominio già operativo
2. **Phase 3** (Tax Engine) — Veronika beneficia direttamente, alta utilizzazione clienti
3. **Phase 4** (Marketing) — content engine accelera dispatch
4. **Phase 6** (Bali Macro) — feeds altre fasi con cross-domain context
5. **Phase 7** (Nexus OSINT) — KYC due diligence + curiosità autorità
6. **Phase 5** (Antonello Lab) — personale, può aspettare
7. **Phase 8** (Federation) — chiusura sistema

Se Antonello vuole **systems thinking first** (federation power asap):

1. Phase 2 quick-win
2. Phase 8 SUBSET (cross-domain alert routing solo) — sblocca routing tra B1 + B6
3. Poi domini residui

## Reference

- **Master spec**: `docs/superpowers/specs/2026-05-08-domain-mesh-autonomic-design.md`
- **Phase 0 plan**: `docs/superpowers/plans/2026-05-08-domain-mesh-phase0-foundations.md`
- **Phase 1 plan**: `docs/superpowers/plans/2026-05-08-domain-mesh-phase1-setup-team.md`
- **R1-R7 research**: `docs/superpowers/specs/2026-05-08-domain-mesh-research/`
- **External reviews wave 1+2+3**: `docs/superpowers/specs/2026-05-08-domain-mesh-research/external-reviews*/`

## Quick start (master prompt)

In nuova sessione, incolla:

```
Continuiamo il Domain Mesh autonomic system. Leggi `docs/superpowers/prompts/domain-mesh/00-MASTER-ORCHESTRATOR.md` e dimmi quale fase posso avanzare.
```

Claude si orienta da solo e ti propone il prossimo step.
