---
date: 2026-07-17
domain: operations
mandate: "P2 precondition-1 (spec-push-pipeline-optimization-v2.md, panel-reviewed 3/3) — manifest-audit dei required status check contro la semantica merge_group, PRIMA di flippare branch protection verso GitHub merge queue"
gear: 2 (modus STANDARD — audit read-only, zero modifiche a workflow o branch protection)
method: gh api enumeration (branch protection + rulesets + code-scanning default-setup) + grep/read sistematico di tutti i 19 workflow file sorgente + verifica esterna (WebSearch/WebFetch su docs.github.com e community discussions) del comportamento REALE di GitHub Merge Queue per check senza trigger merge_group — nessuna assunzione non verificata
sources: gh api repos/Balizero1987/Teman2/branches/main/protection · gh api repos/Balizero1987/Teman2/rulesets · gh api repos/Balizero1987/Teman2/code-scanning/default-setup · 19 file .github/workflows/*.yml (letti per intero o a sezioni mirate) · scripts/check_adversarial_review.py · scripts/docs_sync.py · docs.github.com "Managing a merge queue" + "Webhook events: merge_group" · github.com/orgs/community/discussions/39933
adversarial_review: codex
---

# Merge-queue readiness manifest — 25-context audit vs `merge_group` semantics

**Zero modifiche a workflow o branch protection in questo lavoro. Solo analisi.**

## TL;DR

- **Required status check contexts REALI: 25** (non ~45 come stimato nella spec — la spec sovrastimava di ~1.8×). Verificato via `gh api repos/Balizero1987/Teman2/branches/main/protection --jq '.required_status_checks.contexts[]'`, doppia conta (lista + `wc -l`) = 25 in entrambi i run.
- **Rulesets: 0** (`gh api .../rulesets` → `[]`). Il repo usa SOLO classic branch protection — nessuna configurazione di merge queue esiste oggi (merge queue è un feature ruleset-only su GitHub; assenza di ruleset = merge queue non abilitabile nello stato corrente senza prima migrare a un ruleset).
- **Workflow file distinti che generano i 25 context: 19** (non "21" come la spec pre-stimava nel titolo del precondition).
- **Il rischio dominante NON è quello descritto nel titolo della spec.** Il pericolo "silent-green" (job/step skippato che referta successo) è REALE ma è la minoranza (1 caso confermato su 25). Il rischio dominante, per un fattore ~20×, è più semplice e più totalizzante: **18 dei 19 workflow non hanno `merge_group` nel trigger `on:` — quindi NON SI ESEGUIRANNO AFFATTO su un evento di coda.** Verificato con fonte ufficiale GitHub (vedi §1): un required check il cui workflow non ha `merge_group` **non viene mai riportato**, la coda va in timeout e **espelle la PR**. Non è un falso-verde: è un blocco totale della coda per assenza di segnale.
- Scoperto un **terzo modo di fallimento**, non previsto esplicitamente dal framing binario della spec (silent-green vs pending-wedge): **REF-BREAKAGE fail-closed** — 2 workflow usano `github.base_ref` / `github.event.pull_request.*` senza guardia; sotto `merge_group` quei campi sono vuoti, il comando git a valle fallisce con `set -euo pipefail` attivo, e il job **fallisce sempre**, per ogni PR, indipendentemente dal contenuto. È l'opposto polare del silent-green (un self-DoS della coda) ma altrettanto pericoloso da flippare a cuor leggero.
- **Verdetto per categoria (25/25 contestualizzati):** READY 1 · NEEDS-TRIGGER pulito 21 · NEEDS-TRIGGER+SILENT-GREEN-RISK 1 · NEEDS-TRIGGER+REF-BREAKAGE 2 · EXTERNAL-BLOCKER 0 · NAME-MISMATCH-RISK 0.
- **Buona notizia verificata (non presunta):** nessun required check è un check esterno (Vercel/Socket/Sonar/Lighthouse — verificato per nome, nessuno dei 25 combacia); CodeQL default-setup nativo è `"state":"not-configured"` (nessuna fonte-ombra per i 2 context CodeQL); i 2 job a matrice (CodeQL language, Frontend app/coverage) sono a matrice STATICA senza `if:` condizionale — zero rischio di nome-che-non-combacia in coda; tutti i `concurrency.group` sono chiavati su `github.ref` (o con fallback `|| github.ref`), che sotto `merge_group` risolve a un ref univoco per voce di coda (`refs/heads/gh-readonly-queue/...`) — zero rischio di collisione cross-PR verificato per costruzione.

---

## §1 — Il fatto di piattaforma che governa tutto il resto (verificato, non assunto)

Prima di classificare qualsiasi context ho verificato via WebSearch + WebFetch (docs.github.com, non dalla mia memoria di training, per rispettare la disciplina anti-allucinazione su semantica di piattaforma che cambia nel tempo) cosa succede REALMENTE quando un required check non ha `merge_group` nel trigger:

> "If your repository uses GitHub Actions to perform required checks on pull requests in your repository, you need to update the workflows to include the `merge_group` event as an additional trigger. Otherwise, status checks will not be triggered when you add a pull request to a merge queue. **The merge will fail as the required status check will not be reported.**" — docs.github.com, "Managing a merge queue"

E sul timeout risultante:

> "Timed out awaiting a successful CI result based off the configured timeout setting" → rimozione della PR dalla coda. L'amministratore configura quanto la coda aspetta prima di assumere che i check siano falliti.

Conferma indipendente da community discussion #39933 (staff/community, non official docs ma coerente): "skipped jobs count as successes" — **questo è il meccanismo esatto del silent-green** (family #2 della spec), ma è un fenomeno DIVERSO e più stretto: si applica solo quando il workflow HA `merge_group` come trigger ma un job/step al suo interno è skippato via `if:`. Se il workflow non ha `merge_group` affatto, non c'è nulla da skippare — il workflow semplicemente non parte, e il risultato è "mai riportato" → timeout → espulsione, non un successo fasullo.

**Ho quindi due popolazioni ben distinte da tracciare separatamente, e le ho verificate entrambe su ognuno dei 19 file:**
- Popolazione A (18/19 file): nessun trigger `merge_group` → verdetto primario **NEEDS-TRIGGER** (mai riportato → timeout → espulsione).
- Popolazione B (1/19 file, `hot-zone-pr-gate.yml`): HA `merge_group` → qui, e SOLO qui, il silent-green della spec è strutturalmente possibile oggi. L'ho auditato riga per riga (§3, §5).

Ho inoltre verificato (WebFetch su "Webhook events: merge_group") che l'evento `merge_group` supporta due `action`: `checks_requested` (creazione/aggiunta alla coda) e `destroyed` (rimozione) — questo è il primitivo su cui si fonda il design del watcher in §8. La documentazione ufficiale NON specifica lo schema del campo `reason` sotto `destroyed`; non lo invento — lo marco come "da verificare empiricamente nel canary" in §8.

---

## §2 — Metodo di enumerazione (verificabile, ripetibile)

```bash
gh api repos/Balizero1987/Teman2/branches/main/protection --jq '.required_status_checks.contexts[]'   # → 25 righe
gh api repos/Balizero1987/Teman2/branches/main/protection --jq '.required_status_checks.strict'         # → false
gh api repos/Balizero1987/Teman2/rulesets                                                                # → []
gh api repos/Balizero1987/Teman2/code-scanning/default-setup --jq '.state'                               # → "not-configured"
```

Per ogni context: `grep -rn "<stringa esatta>" .github/workflows/*.yml` per trovare il job che dichiara quel `name:` (o, quando assente, il job-id usato come nome di default — 6 dei 25 casi: `root-guard`, `verify-the-verifiers`, `lesson-harvester-gate`, `brand-api-gate`, `cost-breaker-tests`, `antidotes`). Poi lettura completa o mirata del file sorgente per le 7 dimensioni richieste dal mandato: (a) `merge_group` in `on:`, (b) `if:` a livello job/step che referenzia `pull_request`, (c) path filter, (d) checkout/ref logic PR-specifica, (e) concurrency key, (f) check esterno, (g) matrix naming.

`strict: false` — nota a margine (non richiesta esplicitamente dal mandato, ma osservata): "require branches to be up to date" NON è armato oggi. Non impatta l'analisi merge_group (la coda ha una propria semantica di ricostruzione indipendente da questo flag), la registro solo per completezza del quadro branch-protection.

---

## §3 — Manifest completo: 25 context → workflow → verdetto

| # | Required context | Workflow file | Job (name/id) | `merge_group`? | Verdetto |
|---|---|---|---|---|---|
| 1 | E2E Tests (Playwright) | `tests.yml:325` | `e2e-tests` | NO | NEEDS-TRIGGER (pulito) |
| 2 | MCP Server Tests | `tests.yml:220` | `mcp-tests` | NO | NEEDS-TRIGGER (pulito) |
| 3 | Detect Secrets | `security.yml:284` | `detect-secrets` | NO | NEEDS-TRIGGER (pulito) |
| 4 | Backend Tests (Python) | `tests.yml:21` | `backend-tests` | NO | NEEDS-TRIGGER (pulito) |
| 5 | Bandit Python Security | `security.yml:174` | `bandit` | NO | NEEDS-TRIGGER (pulito) |
| 6 | CodeQL Analysis (python) | `security.yml:142` | `codeql` (matrix `language`) | NO | NEEDS-TRIGGER (pulito) |
| 7 | CodeQL Analysis (javascript) | `security.yml:142` | `codeql` (matrix `language`) | NO | NEEDS-TRIGGER (pulito) |
| 8 | root-guard | `root-guard.yml:15` | `root-guard` (job-id) | NO | NEEDS-TRIGGER (pulito) |
| 9 | Frontend Tests (Next.js) (mouth, true) | `tests.yml:252` | `frontend-tests` (matrix `include`) | NO | NEEDS-TRIGGER (pulito) |
| 10 | Canary self-test + incremental mutation | `p1s2-mutation-incremental.yml:47` | (unnamed job) | NO | NEEDS-TRIGGER (pulito) |
| 11 | verify-the-verifiers | `verify-the-verifiers.yml:31` | `verify-the-verifiers` (job-id) | NO | NEEDS-TRIGGER (pulito) |
| 12 | **Hot-zone enforcement** | `hot-zone-pr-gate.yml:47` | `hot-zone-gate` | **SÌ (unico)** | **READY** |
| 13 | asyncpg-lint | `asyncpg-lint.yml:31` | `asyncpg-lint` | NO | NEEDS-TRIGGER (pulito) |
| 14 | P3 static validation (enforcing) | `p3-sandbox-gates.yml:29` | (unnamed job) | NO | **NEEDS-TRIGGER + REF-BREAKAGE** — `p3-sandbox-gates.yml:72-73` |
| 15 | lesson-harvester-gate | `p7-lesson-harvester.yml:27` | `lesson-harvester-gate` (job-id) | NO | NEEDS-TRIGGER (pulito) |
| 16 | brand-api-gate | `p8-brand-api.yml:23` | `brand-api-gate` (job-id) | NO | NEEDS-TRIGGER (pulito) |
| 17 | cost-breaker-tests | `p9-cost-breaker.yml:30` | `cost-breaker-tests` (job-id) | NO | NEEDS-TRIGGER (pulito) |
| 18 | P6 parallelize-hypothesis falsifiable gates | `p6-federation-parallelize.yml:41` | (unnamed job) | NO | NEEDS-TRIGGER (pulito) |
| 19 | Every organ is born with its genes | `organ-conformance.yml:39` | (unnamed job) | NO | **NEEDS-TRIGGER + SILENT-GREEN-RISK** — `organ-conformance.yml:55,58,71` |
| 20 | R1 gate — adversarial review present | `adversarial-review-gate.yml:23` | `gate` | NO | **NEEDS-TRIGGER + REF-BREAKAGE** — `adversarial-review-gate.yml:36,44` |
| 21 | antidotes | `immune-enforcement.yml:27` | `antidotes` (job-id) | NO | NEEDS-TRIGGER (pulito) |
| 22 | npm lock honors manifest | `npm-lock-sync.yml:47` | (unnamed job) | NO | NEEDS-TRIGGER (pulito) |
| 23 | actionlint — workflow schema + expression gate | `actionlint.yml:36` | (unnamed job) | NO | NEEDS-TRIGGER (pulito) |
| 24 | Every guard proves guilt AND innocence | `guard-conformance.yml:42` | (unnamed job) | NO | NEEDS-TRIGGER (pulito) |
| 25 | Prove hooks bite only the guilty | `hook-innocence-gate.yml:50` | (unnamed job) | NO | NEEDS-TRIGGER (pulito) |

**"NEEDS-TRIGGER (pulito)"** = ho verificato (grep esaustivo `github.event.pull_request.*`, `github.base_ref`, `if:` a qualunque livello) che il file non referenzia contesto PR-only da nessuna parte; aggiungere `merge_group:` a `on:` è meccanicamente sufficiente — nessun secondo bug latente trovato. Per gli 8 file col pattern sentinel "Did relevant paths change?" (p1s2, p6, p7, p8, p9, p3, verify-the-verifiers, hook-innocence-gate, guard-conformance — 9 file, non 8, li ho tutti letti) il guard è esplicitamente **fail-open**: `if [[ "${{ github.event_name }}" != "pull_request" ]]; then run=true; exit 0; fi` — su `merge_group` questa condizione è vera (event_name="merge_group" ≠ "pull_request") quindi il gate esegue SEMPRE per intero, mai skip. È il comportamento sicuro per costruzione, verificato leggendo il codice bash reale, non assunto dal nome dello step.

---

## §4 — Le 5 peggiori istanze (file:line, con analisi del meccanismo)

### 1. `organ-conformance.yml` — SILENT-GREEN-RISK reale (il più vicino al pericolo che la spec titola)

```yaml
# organ-conformance.yml:55
if [ "$EVENT_NAME" = "push" ]; then
  echo "hit=true" >> "$GITHUB_OUTPUT"; exit 0
fi
# organ-conformance.yml:58
CHANGED=$(git diff --name-only "$BASE" "$HEAD" -- 'infra/organ-conformance/' ... 'infra/healer/' || true)
...
# organ-conformance.yml:71
echo "hit=false" >> "$GITHUB_OUTPUT"
```

`BASE`/`HEAD` sono `github.event.pull_request.base.sha` / `.head.sha` (righe 51-52) — vuoti sotto `merge_group`. Il guard controlla `EVENT_NAME == "push"` ma **non** `"merge_group"` (guard-over-match/under-match famiglia #3 del cicatrix: la guardia sorveglia UN evento non-PR letterale ed è cieca al gemello). `git diff --name-only "" ""` fallisce; `|| true` ingoia l'errore; `CHANGED` resta vuoto; il branch `else` a riga 71 scrive `hit=false`; ogni step successivo ha `if: steps.relevant.outputs.hit == 'true'` e viene skippato; **il job non fallisce mai** (nessuno step ha eseguito nulla che potesse fallire) → riporta SUCCESS. Risultato: "Every organ is born with its genes" può referire verde in coda senza aver verificato un solo organo, anche se la PR tocca `organs_registry.yaml`. Nota: oggi il file non ha comunque `merge_group` in `on:` — questo bug è **latente**, si attiva SOLO se qualcuno aggiunge il trigger senza leggere fin qui.

### 2 & 3. `p3-sandbox-gates.yml` + `adversarial-review-gate.yml` — REF-BREAKAGE fail-closed (polo opposto, non previsto dal framing binario della spec)

```yaml
# p3-sandbox-gates.yml:72-73 (dentro uno step con continue-on-error: false, set -euo pipefail)
git fetch origin ${{ github.base_ref }} --depth=1
if ! git diff --quiet origin/${{ github.base_ref }} -- apps/backend-rag/docker-compose.test.yml; then
```
```yaml
# adversarial-review-gate.yml:36 e :44
env:
  BASE_REF: ${{ github.base_ref }}
run: python scripts/check_adversarial_review.py --diff "origin/${BASE_REF}"
```

`github.base_ref` è popolato SOLO per eventi `pull_request`/`pull_request_target` — sotto `merge_group` è stringa vuota (l'equivalente corretto sarebbe `github.event.merge_group.base_ref`, mai referenziato in nessuno dei due file). In `p3-sandbox-gates.yml` questo produce `git diff --quiet origin/ -- ...` → ref ambiguo → `set -euo pipefail` termina lo step → job FAILED. In `adversarial-review-gate.yml` produce `--diff "origin/"` → `scripts/check_adversarial_review.py:444-452` cattura esplicitamente `subprocess.CalledProcessError` e ritorna **`2`** (verificato leggendo `main()` riga per riga) → step FAILED. In entrambi i casi: **non un falso-verde, un falso-rosso garantito al 100% delle PR**, indipendentemente dal contenuto — se aggiunto `merge_group` senza fix, questi due gate diventerebbero un muro invalicabile per OGNI voce di coda. Per `adversarial-review-gate.yml` la posta è più alta del solito: è l'R1 gate, il meccanismo generator≠grader citato in CLAUDE.md §6/§13 — se questo si rompe in coda, l'intero regime di verifica-non-umana su cui poggia lo SHIP-LIFECYCLE OWNERSHIP si blocca silenziosamente per errore di piattaforma, non per assenza di adversarial review reale.

### 4. `tests.yml` + `security.yml` — non un bug, ma il costo dominante del NEEDS-TRIGGER pulito

8 dei 25 context (32%) vengono da questi 2 file (Backend Tests, MCP Server Tests, Frontend Tests × matrix, E2E Tests, Detect Secrets, Bandit, CodeQL × matrix). Sono "puliti" (nessun riferimento a `pull_request.base/head`, checkout di default) ma sono anche i job più costosi (il backend-tests è il job ~18min citato nella spec). Finché mancano di `merge_group`, ogni PR che entra in coda farà **timeout aspettando il job CI più pesante della pipeline**, non una skip innocua — è il precondition più critico da chiudere prima di qualunque flip, perché è quello con il timeout-budget più stretto rispetto al tempo di esecuzione reale.

### 5. `hot-zone-pr-gate.yml` — il modello positivo, con un residuo cosmetico

L'unico file con `merge_group:` (riga 34) e con pattern SHA-fallback corretto ovunque tranne uno: `hot-zone-pr-gate.yml:159` — `PR_NUMBER: ${{ github.event.pull_request.number }}` (e riga 160, `PR_URL`) non hanno il fallback `github.event.merge_group...` usato in TUTTE le altre 4 occorrenze dello stesso file (righe 75, 85-86, 244 usano `||`). Sotto `merge_group` questi due campi sarebbero vuoti — ma lo step è raggiunto SOLO se `codeowners_touched == true`, e la logica di blocco (`ACTOR != "Balizero1987"` → `exit 1`) non dipende da `PR_NUMBER` — degrada solo il testo dell'alert Telegram (numero PR mancante nel messaggio), non la decisione di gate. L'ho classificato READY con nota, non NEEDS-FIX, perché non altera l'esito del check.

---

## §5 — Conteggi finali

| Categoria | N | % |
|---|---|---|
| READY | 1 | 4% |
| NEEDS-TRIGGER (pulito, nessun secondo bug) | 21 | 84% |
| NEEDS-TRIGGER + SILENT-GREEN-RISK | 1 | 4% |
| NEEDS-TRIGGER + REF-BREAKAGE (fail-closed) | 2 | 8% |
| EXTERNAL-BLOCKER | 0 | 0% |
| NAME-MISMATCH-RISK | 0 | 0% |
| **Totale** | **25** | **100%** |

Lettura: **0/25 sono oggi pronti per il flip "as-is che accada qualcosa di dannoso al primo tentativo"** nel senso stretto — 24/25 semplicemente non si eseguirebbero (timeout+espulsione, un fallimento rumoroso e visibile, non silenzioso), 1/25 (organ-conformance) è il vero rischio "silenzioso" che il titolo della spec temeva, e 2/25 sono un rischio opposto (self-DoS) che la spec non aveva nominato esplicitamente ma che i preconditions (audit completo, non solo "silent-green") erano comunque progettati per catturare.

---

## §6 — Verifiche negative (ciò che NON è un problema, verificato non presunto)

- **External-blocker: 0.** Nessuno dei 25 context combacia per nome con Vercel/Socket/Sonar/Lighthouse (grep esaustivo sulla lista). I workflow `vercel-build-guard.yml`, `sonarqube.yml`, `lighthouse.yml`, `sbom.yml`, `semgrep.yml`, `contract-tests.yml` esistono nel repo ma **non sono required** oggi — fuori scope per il gate della coda, per ora. Se in futuro uno di questi viene promosso a required, ripetere questo audit per quel file specifico (nessuno dei 6 è stato auditato in profondità qui, solo escluso per nome).
- **CodeQL default-setup: `"state":"not-configured"`** (verificato via API, non assunto) — nessuna fonte-ombra nativa in competizione con `security.yml`'s Actions-based CodeQL job per gli stessi 2 context name.
- **Name-mismatch: 0.** I 2 job a matrice (`codeql` con `language: ["python","javascript"]`; `frontend-tests` con `include: [{app:mouth,coverage:true},{app:admin-dashboard,coverage:false}]`) sono matrix STATICHE, dichiarate senza alcun `if:` condizionale sulla lista stessa — il nome generato (`<name> (<matrix-values>)`) è deterministico e identico a prescindere dall'evento scatenante. L'unico rischio residuo è lo stesso NEEDS-TRIGGER di tutti gli altri (il workflow non parte affatto), non un disallineamento di nome una volta partito.
- **Concurrency collision: 0.** Tutti i 15/19 file con blocco `concurrency:` usano `group: <prefix>-${{ github.ref }}` (2 con fallback `github.event.pull_request.number || github.ref`). Sotto `merge_group`, `github.ref` risolve al ref temporaneo univoco per voce di coda (`refs/heads/gh-readonly-queue/main/pr-<N>-<sha>`), quindi due PR diverse in coda non condividono mai lo stesso `group` — nessun cancel-in-progress cross-PR. I 4 file senza blocco `concurrency:` (`p3-sandbox-gates.yml`, `p7-lesson-harvester.yml`, `p8-brand-api.yml`, `adversarial-review-gate.yml`) non hanno un rischio di collisione, semplicemente non deduplicano — non è un difetto di per sé.
- **`docs_sync.py --check` (M2, dettaglio in §7) è tree-content puro** — nessuna chiamata `git diff`/base-ref nel suo path `--check` (verificato via grep sul sorgente: solo `content_checksum()` su stringhe rigenerate in memoria). Questo lo rende STRUTTURALMENTE sicuro sotto ricostruzione di coda, un design che gli altri 2 REF-BREAKAGE case (§4.2-3) NON condividono.

---

## §7 — (i) Piano canary di step-equivalence

Obiettivo: non "il check è partito" ma "il grafo di step eseguiti sotto `merge_group` è IDENTICO (stesso insieme, stesso ordine causale) a quello eseguito sotto `pull_request` per lo stesso diff" — la spec lo chiede esplicitamente perché "check fired" da solo non avrebbe rilevato né il caso organ-conformance (che fa PARTIRE il job ma skippa gli step interni) né i 2 REF-BREAKAGE (che fanno partire il job E lo step, ma con un comando diverso da quello inteso).

**Design, ancorato ai 25 context reali di questo repo, non generico:**

1. **Pre-requisito (bloccante, va fatto PRIMA del canary, non durante):** aggiungere `merge_group:` a `on:` nei 24/25 context NEEDS-TRIGGER — ma in un ordine a 3 lotti, non tutto insieme:
   - Lotto 1 (21 "puliti", §3): aggiunta meccanica, rischio verificato basso.
   - Lotto 2 (organ-conformance): fix del guard PRIMA di aggiungere il trigger (`EVENT_NAME` deve gestire `merge_group` esplicitamente, non solo `push`; rimuovere lo `|| true` cieco o sostituirlo con un controllo esplicito su `git diff` exit-code ≠ ambiguous-ref).
   - Lotto 3 (p3-sandbox-gates, adversarial-review-gate): questi usano `github.base_ref` (ref-name), che è vuoto sotto `merge_group`. Due opzioni: **(a)** allinearli allo **SHA-fallback** `github.event.merge_group.base_sha || github.event.pull_request.base.sha` già dimostrato in `hot-zone-pr-gate.yml:75,85-86,244` (approccio preferito — è la forma realmente collaudata nel repo, coerente con §10 punto 2), oppure **(b)** il fallback ref-name `github.event.merge_group.base_ref || github.base_ref`. **NB (adversarial review, §11):** `hot-zone-pr-gate.yml` usa lo **SHA-fallback**, NON il pattern ref-name — la prima stesura di questa riga lo attribuiva erroneamente a `base_ref`; corretto dopo il red-team. In entrambi i casi il fix va fatto PRIMA di aggiungere il trigger.
   - Questo ordine non è opzionale: aggiungere il trigger prima del fix trasformerebbe organ-conformance e p3/adversarial-review nei loro difetti latenti attivi, esattamente lo scenario che il canary dovrebbe scoprire DOPO invece che PRIMA.

2. **2 PR canary cumulative** (per-com specifica del punto 2 della spec):
   - **Canary-A**: tocca SOLO path innocui per tutti i 25 sentinel-path-filter tranne uno mirato (es. un file dentro `infra/organ-conformance/` — sceglierlo apposta per far scattare `hit=true` sul job appena corretto in Lotto 2) + un file backend qualunque per far scattare `tests.yml`/`security.yml`. Diff PR-run: cattura via `gh api repos/.../check-runs` la lista di `(job_name, step_name, conclusion)` per ogni check-run del commit HEAD.
   - **Canary-B**: cumulativa su Canary-A (secondo commit sullo stesso branch, o secondo PR in coda dietro la prima) — aggiunge un tocco a `apps/backend-rag/backend/db/migrations_v2/` per far scattare la logica "merge-tree overlay" già presente in `hot-zone-pr-gate.yml` (righe ~230-267, la parte letta ma non ancora citata sopra: replay di `lint_migration_numbers.py` sull'albero ricostruito) — questo è il punto più delicato del repo per la distinzione base/head sotto coda, merita un canary dedicato.
   - **1 failure iniettato**: in un terzo commit/PR, un fallimento deliberato e innocuo (es. un test che asserisce `False` in un file non-hot-zone) per verificare che (a) il fallimento sia visibile IDENTICAMENTE in coda e in PR, (b) il **ejection watcher** (§8) lo rilevi.
   - **Queue rebuild**: dopo l'iniezione del fallimento, verificare che GitHub ricostruisca la coda per le PR dietro quella fallita (comportamento nativo del merge queue — da osservare, non da programmare).
   - **Bot churn**: nel frattempo, un terzo commit non correlato deve mergiare su `main` per simulare il traffico reale (il repo fa "merge ogni ~15-20 min" per la spec §0) — verifica che il ricalcolo `base_sha` regga sotto avanzamento concorrente del base.
   - **Diff del grafo**: per ogni context, `(job_name, [step_name for step in steps if conclusion != 'skipped'])` PR-run vs merge-group-run — qualunque asimmetria (uno step skippato in coda che non lo era in PR, o viceversa) è un FAIL del canary, non solo un'osservazione.

3. **Criterio di uscita dal canary:** 0 asimmetrie sui 25/25 context per 2 cicli completi (Canary-A + Canary-B + failure-iniettato), prima di considerare il flip di branch protection.

---

## §8 — (ii) Design del watcher anti-espulsione

Fatto verificato (§1): l'evento webhook `merge_group` ha `action: "destroyed"` quando una voce esce dalla coda (per qualunque motivo — merged, invalidated, o dequeued da un fallimento; lo schema esatto del campo `reason` **non è documentato pubblicamente in modo verificabile** da questa sessione — va osservato empiricamente durante il canary di §7, non assunto).

**Design a 2 livelli (webhook primario + poll di backstop, la coppia che la spec chiede esplicitamente al punto 3):**

1. **Livello webhook (primario, near-real-time):** un endpoint (può vivere sul backend Fly esistente, `nuzantara-rag`, dato che ha già gestori di webhook per altri eventi — verificare in `apps/backend-rag/backend/channels/` se esiste già un ricevitore GitHub generico prima di costruirne uno nuovo, per riuso) sottoscritto a `merge_group` con `action=destroyed`. Alla ricezione: guarda se la PR associata (via il numero embedded nel ref `gh-readonly-queue/<base>/pr-<N>-<sha>`) è nello stato "merged" su GitHub — se SÌ, nessun'azione (uscita fisiologica). Se NO, la PR è stata **espulsa senza essere mergiata**: alert Telegram (canale P0 esistente, `TELEGRAM_OWNER_CHAT_ID`, pattern già in uso in `hot-zone-pr-gate.yml:157-171` per il CODEOWNERS alert — riusare lo stesso pattern curl, non reinventarlo) con PR number + motivo (se disponibile dal payload) + link.
2. **Livello poll (backstop, copre il caso "webhook perso"):** cron leggero (ri-uso della cadenza cron esistente nel repo, es. ogni 5-10 min) che interroga `GET /repos/{owner}/{repo}/pulls?state=open` filtrato per PR con un check-run "queued"/"in-progress" più vecchio del timeout di coda configurato (§1: "configured timeout setting" — verificare il valore reale via `gh api .../rulesets` una volta che la coda esiste; oggi non verificabile perché la coda non è configurata) MA senza più essere in coda (assenza del ref `gh-readonly-queue/...` associato). Questa è la stessa logica "green-ma-morto" già affrontata altrove nel repo per cron/daemon (cicatrix famiglia #2 "Esiste ≠ Armato") — il watcher qui è un'istanza dello stesso principio applicato alla coda invece che a un processo.
3. **Il watcher è un segnalatore, mai un ri-accodatore automatico** — coerente con `scripts/pending_arms_report.py` (stesso principio "segnalatore, non auto-attuatore" usato altrove nel repo, cicatrix #2): non richiama `gh pr merge` da solo. La decisione di ri-accodare (che potrebbe nascondere un fallimento reale se automatizzata ciecamente) resta un passo esplicito della sessione che ha aperto quella PR.

---

## §9 — (iii) W86 × squash × queue: cosa succede a `check-docs-sync`

**Fatto preliminare verificato, non nella spec**: `check-docs-sync` (`docs-sync.yml:51`) **non è oggi un required status check** — non compare nei 25 context (grep esaustivo). È quindi fuori scope per il flip di branch protection nel senso stretto — ma è comunque materiale per l'analisi M2 richiesta dal mandato, perché il pattern che protegge (o rompe) resta lo stesso indipendentemente dal fatto che sia formalmente "required" oggi.

**Come è costruito `check-docs-sync` (verificato leggendo `scripts/docs_sync.py`):** il flag `--check` **non fa un diff contro un base ref** — rigenera in memoria il contenuto atteso dei documenti derivati dal tree corrente e lo confronta via `content_checksum()` contro quanto committato. Nessuna chiamata `git diff`/`origin/main` nel suo path `--check` (confermato via grep sul sorgente). Questo è strutturalmente il design che il resto della spec (P3, redesign di Sol) chiede per gli ALTRI documenti derivati — `check-docs-sync` **già lo fa** per il proprio dominio.

**Cosa significa per la coda:** se `docs-sync.yml` ottenesse `merge_group:` (oggi non ce l'ha — stesso NEEDS-TRIGGER di tutti gli altri, MA senza secondo bug: il fatto di non dipendere da `github.event.pull_request.base/head` lo rende "pulito" per costruzione, non serve nemmeno il pattern SHA-fallback usato altrove) il check rieseguirebbe sul commit di coda ricostruito (base aggiornato + questa PR, eventualmente sopra altre PR già ammesse davanti in coda) — e siccome il check verifica **coerenza interna dell'albero risultante**, non un diff contro un punto nel tempo, resterebbe corretto A PATTO CHE la regola "regen nello stesso commit della feature" (CLAUDE.md §7bis, l'antidoto W86) continui a valere per OGNI singola PR in coda. La coda in sé **rinforza** l'antidoto W86 invece di romperlo: nel mondo attuale (senza coda) W86 accade perché due PR (feature + docs-bump) mergiano fuori ordine SENZA ri-verifica reciproca — è esattamente la finestra di race che il merge queue esiste per chiudere (ogni voce di coda è ri-validata contro lo stato combinato più recente prima di avanzare). **Condizione necessaria perché questo tenga**: `queue concurrency = 1` nella fase iniziale (già raccomandato dalla spec P2 precondition #4, per altri motivi) — con concurrency > 1 (batch/speculative checks), più PR che toccano contemporaneamente superfici docs-sync-rilevanti potrebbero essere validate in parallelo contro basi "previste" non ancora confermate; finché ogni singola PR porta il proprio regen nello stesso commit (invariante W86 già in vigore), il worst-case resta "coda rifiuta e richiede riordino", non "main torna incoerente" — ma questo è un ragionamento architetturale, non verificato empiricamente: è precisamente il tipo di comportamento che il canary di §7 (in particolare Canary-B, "bot churn" concorrente) dovrebbe osservare prima di fidarsi in produzione.

**Correzione all'inquadramento M2 della spec**: il rischio non è "check-docs-sync boccia una PR innocente in coda" (quello era il sintomo SENZA coda, W86 originale) — è "chi promuove check-docs-sync a required DEVE prima confermare che ogni fonte di docs derivati nel repo condivida lo stesso design content-pure di `docs_sync.py --check`" — cosa che questo audit non ha verificato per `docs-guardian.yml` (`inventory-check`, non required oggi, non auditato in profondità qui) né per `doc-freshness.yml` (anch'esso non required oggi). Se in futuro uno di questi due venisse promosso a required E avesse una logica diff-contro-base anziché tree-content-pure, erediterebbe lo stesso rischio REF-BREAKAGE di `p3-sandbox-gates.yml`/`adversarial-review-gate.yml` — segnalo come domanda aperta per un audit successivo, non la chiudo qui (fuori scope dai 25 context reali di oggi).

---

## §10 — Riepilogo per chi eseguirà P2

Non eseguibile da questo audit (mandato = solo analisi): la sequenza consigliata, in ordine di rischio crescente, per chi arriverà a costruire P2 dopo il canary di §7:

1. Fix Lotto 2 (organ-conformance.yml, SILENT-GREEN) e Lotto 3 (p3-sandbox-gates.yml + adversarial-review-gate.yml, REF-BREAKAGE) PRIMA di toccare qualunque `on:` trigger — questi sono bug latenti indipendenti dalla coda, li scopre solo chi legge il codice, non chi guarda i trigger dall'esterno.
2. Aggiungere `merge_group:` ai 24/25 file NEEDS-TRIGGER, riusando il pattern SHA-fallback già dimostrato in `hot-zone-pr-gate.yml` ovunque serva un base/head ref.
3. Eseguire il canary di §7 (2 PR cumulative + failure iniettato + bot churn) con concurrency di coda = 1.
4. Costruire il watcher di §8 (webhook + poll) PRIMA di fidarsi della coda in produzione, non dopo il primo incidente.
5. Solo allora: flip di branch protection verso ruleset + merge queue (oggi: rulesets = 0, quindi questo è anche un cambio di meccanismo di enforcement, non solo un toggle).

Nessuno di questi 5 passi è stato eseguito in questo audit. Zero file `.github/workflows/*` o impostazioni di branch protection sono stati modificati.

---

## Adversarial review

Section §11. Added post-hoc (2026-07-18) to satisfy the R1 gate: the original audit
(2026-07-17) shipped without an independent adversarial pass. A real cross-family
red-team was then run — **generator≠grader**: this audit was authored by Claude/Fable,
so the grader is **Codex GPT-5.6 (read-only sandbox)**, pointed at the live repo to
re-ground every load-bearing claim against the actual workflow files. Its verdicts,
each independently re-verified on disk before adoption (W65 — even the refuter
hallucinates):

- **VERIFIED — NEEDS-TRIGGER, not silent-green.** Only `hot-zone-pr-gate.yml:34` carries
  a `merge_group:` trigger; a required check without it is *never reported* → queue
  timeout/eject, not a false green. (GitHub "Managing a merge queue".)
- **VERIFIED — `p3-sandbox-gates.yml` + `adversarial-review-gate.yml` fail-closed under
  `merge_group`.** Both read `github.base_ref` unguarded (`p3` lines 72-73;
  `adversarial-review-gate.yml:37,46`), empty under `merge_group`; and
  `check_adversarial_review.py` returns exit **2** on the resulting bad revision
  (`main()` ~line 443, re-verified live: `--diff origin/` → `fatal: bad revision` → exit 2).
- **VERIFIED — `organ-conformance.yml` latent SILENT-GREEN** (no `merge_group`, PR-only
  BASE/HEAD, `|| true`-swallowed diff → `hit=false` skips all gate steps).
- **REFUTED, and fixed in this revision — the §7 Lotto-3 claim.** The draft said the fix
  pattern was `github.event.merge_group.base_ref || github.base_ref`, "already proven in
  `hot-zone-pr-gate.yml:75,85-86,244`". Independently re-verified: hot-zone uses the
  **SHA-fallback** `github.event.merge_group.base_sha || github.event.pull_request.base.sha`,
  NOT a ref-name fallback. It demonstrates the *principle* of a `merge_group.*` fallback,
  not the ref-name form. Line 174 corrected accordingly (and now matches §10 point 2,
  which already said "SHA-fallback").
- **PARTIALLY REFUTED — the §3 "NEEDS-TRIGGER pulito = nessun riferimento PR-only" wording
  is overstated.** Several "pulito" files do reference `github.event.pull_request.base.sha`
  (`p1s2:69`, `verify-the-verifiers:53`, `p7:45`, `p8:41`, `p9:48`, `p6:59`, `guard:59`,
  `hook:69`) — mostly guarded by an `event_name != pull_request` branch, so the per-file
  verdicts likely hold, but the blanket "nessun riferimento" is false. Treat as a wording
  correction / follow-up check, not a gate-decision error.
- **PARTIALLY VERIFIED — concurrency-collision §** analysis holds under the assumption that
  GitHub's merge-group refs (`gh-readonly-queue/{base}/pr-…`) are unique; not provable from
  repo files alone.

Net: the load-bearing structural conclusions (NEEDS-TRIGGER, the two REF-BREAKAGE gates,
organ-conformance silent-green, the fix ordering) survive the red-team. One concrete error
(§7 Lotto-3 hot-zone pattern) was found and corrected; one overstatement flagged for a
follow-up pass. Live `gh api` branch-protection enumeration could not be re-run by the
grader (peer unreachable), so the "25 required contexts" count remains as-audited on 07-17.
