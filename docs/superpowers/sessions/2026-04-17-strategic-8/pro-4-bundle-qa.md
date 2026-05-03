# Pro-4 — Bundle Audit + QA Regression Jolly (D variabile)

## Obiettivo

Jolly variabile: triage + fix tech debt ad alta priorità che richiede Pro (browser + deploy Vercel).

## Contesto

- Macchina: Pro (cwd `/Users/nuzantara/Desktop/nuzantara`)
- Memory project attivo: "Bundle audit next session — ERR_INSUFFICIENT_RESOURCES portal: ~35 chunk paralleli"
- Ticket aperto: bundle portal troppo frammentato, browser fallisce fetch
- Design redesign attivo: `project_redesign_next` (balizero.com unify nav)

## Scope SÌ (in priorità)

1. **Bundle audit portal** (priorità 1):
   - Analisi chunk splitting `apps/mouth` build output
   - Identificare top 10 chunk per size e importance
   - Ridurre paralleli da ~35 a <15 via `next.config` tuning (lazy, dynamic import, chunks merge)
   - Verificare che ERR_INSUFFICIENT_RESOURCES sparisca su Chrome + Safari
2. **QA regression v2 funnel** (priorità 2):
   - Screenshot 4 funnel (visa/tax/property/kbli) post merge c194d83bf
   - Verificare analytics funnel-view event fire (11 eventi)
   - Test NavShell + WA CTA allineati
3. **Redesign audit** (priorità 3 se tempo avanza):
   - Audit 5 nav corrente balizero.com
   - Gap analysis vs target design coerente day/night

## Scope NO

- NON iniziare il redesign completo (è roadmap, non jolly)
- NON toccare produzione senza QA pass
- NON merge in main
- NON toccare filoni di altre sessioni

## Deliverables attesi (variabile — almeno 1 dei 3)

1. **Se bundle audit**: branch `fix/portal-bundle-audit` + report `docs/portal-bundle-audit.md` + screenshot before/after
2. **Se QA regression**: report `docs/superpowers/sessions/2026-04-17-strategic-8/logs/pro-4-qa.md` con tabella OK/KO + screenshot
3. **Se redesign audit**: `docs/redesign-audit.md` con gap analysis
4. Log finale `docs/superpowers/sessions/2026-04-17-strategic-8/logs/pro-4.log`

## Stop conditions

- Durata scelta da te in base a quanto prendi (3-10h)
- Se bundle audit non migliora dopo 3 iterazioni → stop, report negativo comunque utile
- Se Chrome non parte → stop immediato (sessione richiede browser)

## Skills

1. `superpowers:using-superpowers`
2. `superpowers:systematic-debugging` (per bundle)
3. `superpowers:using-git-worktrees`
4. `superpowers:verification-before-completion`

## Prompt da incollare

```
Sessione Pro D jolly variabile. Obiettivo: priority queue di 3 task.

Priorità 1: Bundle audit portal (ERR_INSUFFICIENT_RESOURCES, ~35 chunk → <15)
Priorità 2: QA regression 4 funnel v2 (post c194d83bf) + screenshot
Priorità 3 (se tempo): Redesign audit balizero.com 5 nav

Scegli tu cosa iniziare basandoti su quanto tempo hai (decidi 3-10h).

Worktree dedicato per fix bundle. Log in
docs/superpowers/sessions/2026-04-17-strategic-8/logs/pro-4.log

NO merge, NO deploy prod. Usa superpowers:systematic-debugging. Inizia.
```
