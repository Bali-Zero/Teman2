# Domain Mesh — Master Orchestrator Prompt

> **Cosa fa**: prompt da incollare in nuova sessione Claude Code per **continuare** il domain-mesh autonomic system. Si auto-orienta leggendo lo stato.
>
> **Quando usare**: ogni volta che vuoi avanzare il sistema senza ripartire da zero.

---

## PROMPT (copia-incolla nella prima riga della nuova sessione)

Sei in continuazione di un progetto in corso: il **Domain Mesh autonomic system** di Bali Zero / Nuzantara. Prima di fare qualsiasi cosa:

1. Leggi `docs/superpowers/specs/2026-05-08-domain-mesh-autonomic-design.md` (il design master, 14 sezioni)
2. Leggi `docs/superpowers/plans/2026-05-08-domain-mesh-phase0-foundations.md` (Phase 0 plan, già implementato)
3. Leggi `docs/superpowers/plans/2026-05-08-domain-mesh-phase1-setup-team.md` (Phase 1 plan, già implementato)
4. Verifica stato implementazione attuale:
   ```bash
   ls apps/mata-garuda/mata_garuda/foundations/  # 8 moduli Phase 0
   ls apps/mata-garuda/mata_garuda/domains/     # B1 setup_team in Phase 1; verifica quali altri ci sono
   ```
5. Verifica cron attivi:
   ```bash
   launchctl list | grep balizero
   ```

Una volta orientato, chiedimi quale fase devo avanzare. Le fasi pendenti sono:

- **Phase 2**: Setup Team estensione (NB-INTEL-Property + NB-INTEL-Labor) — vedi `docs/superpowers/prompts/domain-mesh/01-phase2-setup-team-extend.md`
- **Phase 3 / B2**: Tax Engine — vedi `docs/superpowers/prompts/domain-mesh/02-phase3-tax-engine.md`
- **Phase 4 / B3**: Marketing Pulse — vedi `docs/superpowers/prompts/domain-mesh/03-phase4-marketing.md`
- **Phase 5 / B4**: Antonello Lab — vedi `docs/superpowers/prompts/domain-mesh/04-phase5-antonello-lab.md`
- **Phase 6 / B5**: Bali Macro — vedi `docs/superpowers/prompts/domain-mesh/05-phase6-bali-macro.md`
- **Phase 7 / B6**: Nexus OSINT — vedi `docs/superpowers/prompts/domain-mesh/06-phase7-nexus-osint.md`
- **Phase 8**: Cross-domain layer (federation graph + alert dispatcher + skill graduation)

**Regole non negoziabili** (controlla `apps/mata-garuda/CLAUDE.md` + root `CLAUDE.md`):

- Niente Anthropic API key. Solo `claude --print` subprocess via OAuth Max.
- mata-garuda: deps core SOLO `pydantic>=2`, deps test SOLO `pytest`. Cose pesanti in `[project.optional-dependencies] foundations`.
- Lazy imports (PEP 562) per tutto ciò che tocca ML deps.
- Branch hijack scar: `git push` dopo OGNI commit. Branch verify prima di Edit/Write.
- TDD per task (test fail → impl → test pass → commit + push).
- Cron LaunchAgent: absolute venv python, atomic mv snapshot, `*_CRON_ENABLED=false` kill switch, PATH includes `/Users/nuzantara/.local/bin` per `claude`.

**Pattern da seguire (Phase 0/1 hanno mostrato)**:

1. Brainstorm domain (skill `superpowers:brainstorming`) → conferma 5-fase lifecycle (nasce/cresce/auto-correct/cosciente/canalizza)
2. Spec doc → `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
3. Plan → `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`
4. Subagent-driven implementation (skill `superpowers:subagent-driven-development`)
5. External review wave (Codex GPT-5 + DeepSeek v4 + NotebookLM NB-1 minimum, Sonnet 4.6 + security-review skill optional)
6. Triage feedback indipendente, fix bug reali (non taste)
7. PR + auto-merge

Aspetta che io ti dica quale fase avanzare prima di partire.
