# Pro-2 — Opus 4.7 §7 Routing Audit + Cost Baselines (A breve 3-5h)

## Obiettivo

Completare §7 della migration Opus 4.7: audit routing multi-modello, tuning prompt caching, stabilire cost baselines misurabili.

## Contesto

- Macchina: Pro (cwd `/Users/nuzantara/Desktop/nuzantara`)
- Memory: "Opus 4.7 migration progress §1-§6 COMPLETI 2026-04-17"
- Plan: `~/.claude/plans/in-vista-di-questo-hashed-newell.md` (verificare path esatto)
- Baseline token già salvato in migration
- Vision pipeline live (cron 5 \* \* \* \*)

## Scope SÌ

- Audit `backend/llm/` e `backend/agents/` per routing decisions (quale modello per quale task)
- Misurare cache hit rate attuale prompt caching
- Stabilire baseline cost/query per 5 scenari tipici (pricing, KG, vision, CRM, council)
- Dashboard o script `scripts/cost_baseline.py` per monitoring continuo
- Ottimizzare eventuali routing miss (task semplice → Haiku invece di Opus)
- Branch `opus47-routing-audit` in worktree `.worktrees/opus47-routing`
- Report finale con raccomandazioni cost/performance

## Scope NO

- NON cambiare modelli default senza review umana
- NON toccare vision pipeline (già live)
- NON modificare cron schedule esistenti
- NON merge in main

## Deliverables attesi

1. `scripts/cost_baseline.py` runnable con output JSON
2. `docs/superpowers/sessions/2026-04-17-strategic-8/logs/pro-2-baseline.json` con baseline attuale
3. Routing audit report in `docs/opus47-routing-audit.md` con:
   - tabella modello × task × cost × latency
   - raccomandazioni (N cose da cambiare, priorità)
4. Branch con commit (se applicati fix low-risk — tipo typos, wrong model ID)
5. Log finale in `docs/superpowers/sessions/2026-04-17-strategic-8/logs/pro-2.log`

## Stop conditions

- Se non trovi il plan `in-vista-di-questo-hashed-newell.md` → cerca in `~/.claude/plans/` o documenti progetto, al massimo derivi le §1-6 dai memory e dal codice
- Tempo > 5h → checkpoint
- Discrepanze gravi con §1-6 → ferma e chiedi

## Skills

1. `superpowers:using-superpowers`
2. `superpowers:using-git-worktrees`
3. `claude-api` (per best practices prompt caching)
4. `superpowers:verification-before-completion`

## Prompt da incollare

```
Sessione Pro A breve 3-5h. Obiettivo: completare §7 migration Opus 4.7 (routing
audit + cost baselines).

Contesto: §1-6 completi (vedi MEMORY.md "Opus 4.7 migration progress"). Plan
candidato in ~/.claude/plans/in-vista-di-questo-hashed-newell.md.

Lavora in worktree .worktrees/opus47-routing branch opus47-routing-audit da main.

Deliverables:
1. scripts/cost_baseline.py (JSON output)
2. docs/opus47-routing-audit.md (tabella + raccomandazioni)
3. log in docs/superpowers/sessions/2026-04-17-strategic-8/logs/pro-2.log

NO push, NO merge. Stop 5h. Inizia.
```
