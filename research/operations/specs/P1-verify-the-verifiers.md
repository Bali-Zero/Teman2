---
date: 2026-06-06
pezzo: 1 di 9
nome: verify-the-verifiers
ruolo: CRITICO-1 — il cardine del meta-dev-loop
status: SPEC (studio) — non implementata
metodo: deep-research (18 claim verificati 3-0 / 7 refutati) + reuse-first interno + council 4-LLM
council_pieno: SÌ (decisione fondante, errore costosissimo)
---

# SPEC Pezzo 1 — verify-the-verifiers

> Il gate di verifica che SOSTITUISCE la code-review di Antonello (non-dev, non revisiona codice).
> Se questo è fragile, l'intero meta-dev-loop crolla. È il cardine.

## 0. La domanda e la risposta (verificata)

**Domanda**: se un'AI genera codice più veloce di quanto un umano possa verificare, e la soluzione è
"fai verificare a un'altra AI", chi verifica il verificatore?

**Risposta (deep-research, 18 claim 3-0)**: il paradosso è **SPOSTABILE ma NON RISOLVIBILE** da arrangiamenti
all-AI. Prove:
- Errori LLM CORRELATI (~60% accordo quando sbagliano vs 33% random); correlazione AUMENTA con accuratezza +
  provider/architettura condivisi → verificatori "più forti/diversi" PEGGIORANO l'indipendenza. [arXiv 2506.07962]
- Agente che reward-hacka SABOTA i detector (12% delle volte, Anthropic arXiv 2511.18397) → self-verifica insicura.
- Solo barriere DETERMINISTICHE non condividono il bias. Mutation testing = discriminatore portante.
- FLOOR: Test Oracle Problem indecidibile → nemmeno il deterministico è infallibile. Gli agenti hardcodano
  input, cancellano test, fanno sys.exit(0) pre-assert.

**Conseguenza per il design**: NON un loop all-AI. Un **FUNNEL a strati**, dal deterministico (immune al bias)
al LLM-eterogeneo-calibrato, con **gate umano minimo** irriducibile in cima. E un **meta-verificatore
deterministico** che rende OSSERVABILE quando un gate è disarmato (non risolve l'indecidibilità — la rende visibile).

## 1. Cosa esiste GIÀ (reuse-first — NON ricostruire)

Nuzantara ha **~30 barriere deterministiche + 6 verificatori LLM** già pronti. Il livello "deterministico
pre-LLM" del funnel **esiste al 90%**:
- **Deterministici PRONTI**: `guardrails-static.py` (PreToolUse block), pre-commit husky 12-gate,
  `lint_asyncpg_except_completeness.py`, `lint_migration_numbers/rollback.py`, `lint_symbiosis_promises.py`,
  CODEOWNERS 2-tier, Bandit/Snyk/CodeQL/pip-audit (CI), `backend_stability_gate.py`, `_evidence_lint.py`, Squawk.
- **LLM PRONTI**: `codex-spalla.sh` (Codex 2nd-opinion), **`devils_advocate_runner.py`** (DeepSeek + NB
  ground-truth + override fail-closed ← IL GIOIELLO), `wr2-critic`/`wr3-critic` (Opus + rubriche modulari),
  gemini `security-reviewer.md`.
- **ROTTI (finding live, da riparare PRIMA di tutto)**:
  - `stop_verify.py` DISARMATO — settings.json ha `STOP_VERIFY_ALLOW_DIRTY=1` hardcoded nel comando.
  - `hot-zone-pr-gate.yml` in MONITOR-MODE — `continue-on-error: true`, Phase-2b mai implementata.

## 2. I 5 GAP reali (tutto il resto è riuso)

| # | Gap | Perché serve | Tool OSS candidato (Mac, no-paid-Anthropic) |
|---|---|---|---|
| 1 | **meta-verificatore** | nessuno verifica che i gate siano ARMATI (stop_verify disarmato lo dimostra) | deterministico custom (no tool) |
| 2 | **mutation testing** | coverage 55% non dice se i test scoprono regressioni | `mutmut` o `cosmic-ray` (Python) |
| 3 | **anti-reward-hacking detector** | niente blocca assert-True / mock-vuoti / sys.exit-pre-assert / test-deleted | Semgrep custom rules + AST linter |
| 4 | **ensemble-LLM su CODE-diff** | esiste per contenuti (WR2/WR3), manca per codice | estendere `devils_advocate_runner` |
| 5 | **property-based testing** | spezza l'hardcoding input/output degli agenti | `Hypothesis` (Python) |

## 3. ARCHITETTURA — il funnel (ordinato dal più economico/immune al più costoso)

```
PR/diff dell'agente
  │
  ▼ STRATO 0 — DETERMINISTICO ESISTENTE (immune al bias, costo ~0, già in casa)
  │  guardrails-static + pre-commit 12-gate + lint-suite + SAST/CodeQL/Snyk + backend-stability-gate
  │
  ▼ STRATO 1 — ANTI-REWARD-HACKING (NUOVO, deterministico — blocca il cheating sui test)
  │  AST/Semgrep: assert-True, asserzioni-tautologiche, mock-che-sostituisce-comportamento,
  │  sys.exit(0)-pre-assert, test-file-deleted, snapshot-aggiornata-senza-diff-logico
  │
  ▼ STRATO 2 — MUTATION TESTING INCREMENTALE (NUOVO — l'oracolo della qualità-test)
  │  mutmut/cosmic-ray SOLO su righe modificate (AST-diff, non tutto il codebase — Gemini #4).
  │  Operatori ad alto valore semantico (auth-check, calcolo billing), non log/formatting.
  │  Accettazione = check BOOLEANO rule-based mutant-KILL (pattern Meta ACH), NON parere LLM.
  │
  ▼ STRATO 3 — PROPERTY-BASED (NUOVO, mirato — solo moduli alto-rischio)
  │  Hypothesis su: parsing input esterni, billing/pricing, transizioni auth/RBAC. NON tutto (insostenibile).
  │
  ▼ STRATO 4 — ENSEMBLE LLM CROSS-LINEAGE (NUOVO — solo moduli critici, no ipertrofia)
  │  devils_advocate_runner esteso: DeepSeek + Gemini + Ollama-locale (NON Claude×N — correlazione errori).
  │  Ground-truth per il codice = output degli strati 0-3 (test che passano + mutant-KILL + property-hold),
  │  NON "il codice sembra giusto". Override fail-closed se ground-truth manca.
  │
  ▼ STRATO 5 — GATE UMANO MINIMO (irriducibile, Antonello)
     Domande BINARIE DETERMINISTICHE (non riassunti LLM che mentono — Gemini #3):
     UMANO obbligatorio: Auth/RBAC · Destructive-Delete (drop table/column) · Prod-Deploy
     Declassabile a policy deterministica: Secrets (TruffleHog) · PII-egress (taint analysis) ·
       Migration-non-distruttive (schema-diff statico)
```

## 4. Il meta-verificatore (la risposta pratica al paradosso per un non-dev)

**NON deve essere intelligente — deve essere DETERMINISTICO.** Un test schedulato (cron + CI) che:
1. Spara **input-noti-cattivi** a ogni gate e verifica che BLOCCHI (es: PR con `assert True` → strato-1 deve
   bloccare; migration senza rollback → lint deve bloccare; `rm -rf /` → guardrails deve bloccare).
2. Verifica che ogni gate sia **ARMATO** (es: `stop_verify` non ha `ALLOW_DIRTY=1`; `hot-zone-gate` non ha
   `continue-on-error: true`; i hook sono registrati in settings.json).
3. Emette un **report binario rosso/verde** dei gate ("12/14 gate armati, 2 DISARMATI: stop_verify, hot-zone").

Non risolve l'indecidibilità (impossibile). Rende **osservabile** quando un controllo è spento/bypassato.
Per un non-dev: il sistema gli dice quando fidarsi e quando no. È il GAP-1 che si auto-dimostra oggi.

> **Limite onesto (deep-research)**: il meta-verificatore è esso stesso codice deterministico → può avere bug.
> Ma a differenza degli LLM, è AUDITABILE una-volta-per-sempre (non probabilistico) e non condivide il bias
> del generatore. Lo si scrive con TDD + lo si congela. È il "trust the oracle writer" del net-answer.

## 5. DECISIONI (proposte)

- **D1 [PRIORITÀ ASSOLUTA]**: riparare `stop_verify.py` + `hot-zone-pr-gate.yml` PRIMA di costruire i 5 gap
  ("cassaforte su porta di cartone" — Gemini #5).
- **D2**: mutation testing INCREMENTALE (AST-diff), non full-codebase. Operatori semantici, non triviali.
- **D3**: ensemble-LLM cross-lineage (DeepSeek+Gemini+Ollama), MAI Claude×N. Solo moduli critici.
- **D4**: gate-umano ridotto a 3 categorie (Auth/Delete/Deploy) con segnale BINARIO deterministico,
  le altre 3 (secrets/PII/migration-additiva) → policy automatica. Anti-rubber-stamping.
- **D5**: ground-truth dell'ensemble-LLM = output deterministico degli strati 0-3, mai auto-giudizio LLM.

## 6. DA ATTACCARE / domande aperte (council in corso — §7)
- Mutation-score-non-decrescente crea ESSO un reward-hacking incentive (kill-test triviali)? → mitigazione
  Gemini: AST-linter sulle asserzioni + mutant-quality-filtering + mutanti generati da agente diverso.
- Property-based vale la candela? → Gemini: SÌ ma solo su parsing/billing/auth, insostenibile su tutto.
- VINCOLO-PII: l'ensemble-LLM manda il codice a Gemini/DeepSeek CLOUD. Il codice Nuzantara contiene logica
  business sensibile? → DeepSeek logico sta valutando. Mitigazione possibile: Ollama-locale per moduli PII-adiacenti.

## 7. COUNCIL 4-LLM — difetti
### 7.1 Gemini (red-team) — INTEGRATO (vedi §3-5, le sue risposte sono già nel design)
### 7.2 Codex GPT-5.5 (costruttivo) — INTEGRATO: sequenza + MVL + pilota 48h
> Tool OSS verificati con link. Convergente con Gemini su ripara-prima + mutation-incrementale + no-Claude×N.

**Sequenza di costruzione (valore incrementale, no big-bang):**
1. **Ripara i 2 rotti** (stop_verify riarmato + hot-zone flip a enforcement). "Senza gate armati,
   mutation/LLM sono teatro." Verifica config YAML/settings via Conftest/OPA.
2. **Meta-verificatore con canary negativi**: `verify_the_verifiers` spara canary cattivi (settings con
   override-dirty, workflow con continue-on-error, test con assert-True, PR-hot-zone-finta, migration-pericolosa)
   e verifica che ogni gate BLOCCHI. Tool: pytest + Conftest/OPA + `semgrep --test`.
3. **MVL "VerifyPack v0" (attivabile DOMANI)**: workflow manuale (input PR/branch) → output `verify-summary.md`
   + `.json`. Esegue i ~30 deterministici + hot-zone + evidence-lint + SAST esistenti, POI i 6 LLM **solo come
   "sospetto" non come pass/fail**. Antonello vede 3 blocchi: **PASS / BLOCK / HUMAN_ESCALATION**. Attiva con
   "Run workflow", legge solo la sintesi, zero review-codice.
4. **Anti-reward-hacking PRIMA dell'ensemble**: Semgrep custom rules per assert-True, `assert 1==1`,
   `pytest.raises(Exception)` generico, mock-vuoti, monkeypatch-no-op, sys.exit(0), test-cancellati,
   gate-config-indeboliti. + test delle regole stesse.
5. **Mutation mirato + ANTI-HACKING DEL MUTATION**: mutmut (1ª scelta Mac, incrementale) solo su file-toccati;
   soglia = "survivor-non-peggiorano + spiegazione-obbligatoria-dei-survivor". CHIAVE: **l'agente NON sceglie
   mutanti/operatori; il gate conserva seed/baseline e aggiunge CANARY MUTANTS NASCOSTI** → previene che l'agente
   bari sul mutation stesso (risolve la domanda aperta del deep-research).
6. **Property-based solo con oracolo vero**: Hypothesis su invarianti pure — RBAC-monotonicity, pricing-non-negativo-da-PricingTool,
   KBLI-payload-flat, migration-numbering/rollback-parser. Inutile su UX/logica-senza-proprietà.
7. **Gate umano sostenibile**: policy `requires_human` calcolata da diff+findings (NON firma-su-tutto). Batching
   giornaliero + diff-summary-leggibile + escalation-solo-su-sospetto. Declassa a policy-block: secrets + PII-egress.
   Tieni umano: delete-dati, migration-irreversibili, deploy-out-of-band, auth/RBAC/billing quando policy segnala risk.
8. **devils_advocate `--target code-diff`**: gli LLM ricevono SOLO ground-truth esterna (diff + test-log +
   Semgrep-findings + Conftest-verdict + mutation-survivors + coverage-delta + hot-zone-toccata). **Gli LLM trovano
   ipotesi/contraddizioni, ma il BLOCCO resta rule-based.** Riusa il runner esistente + DeepSeek/Gemini/Ollama, no Claude×N.
9. **PILOTA 48h**: su `scripts/lint_migration_numbers.py` + hot-zone workflow, con 3 canary PR
   (migration-cattiva, workflow-disarmato, test-reward-hacked). Successo = clean-passa + canary-bloccano +
   summary-leggibile + Antonello-interviene-solo-se-HUMAN_ESCALATION=true. Valida il Pezzo-1 in isolamento.

### 7.3 DeepSeek V4 Pro (logico) — INTEGRATO: 3 raffinamenti CRITICI che la spec dava per scontati
> Modello verificato: deepseek-v4-pro. Ha trovato buchi che Gemini+Codex hanno mancato.

1. **[NON-SEQUITUR RICORSIVO sul meta-verificatore] — il raffinamento più importante**: "quis custodiet
   ipsos custodes?" Il meta-verificatore è soggetto allo STESSO paradosso ricorsivamente. Rende osservabile
   SOLO se è esso stesso **immutabile/non-disarmabile dall'agente**. → FIX OBBLIGATORIO: meta-verificatore con
   **firma-hash + CI separato non-accessibile-all'agente** (es. GitHub Action su runner isolato, file con
   branch-protection CODEOWNERS-only). Senza questo, il meta-verificatore è solo un altro gate disarmabile.
2. **[PARADOSSO MUTATION] #5**: gli operatori di mutazione DEVONO essere **predefiniti standard
   (mutmut/cosmic-ray), MAI generati dall'agente** — altrimenti genera mutanti triviali (dead-code/commenti)
   che qualsiasi test uccide, gonfiando lo score. Separare generatore-mutanti da scrittore-test. (Converge con
   Codex #5 canary-mutants ma DeepSeek aggiunge: operatori FISSI, non agent-chosen.)
3. **[VINCOLO-PII VIOLATO] #6 — il difetto più grave**: l'ensemble cross-lineage manda il codice a DeepSeek/Gemini
   CLOUD. Ma il vincolo dice "solo Claude CLI per codice al cloud; PII locale assoluta Law 2". Se il diff contiene
   PII o logica-business-sensibile → VIOLA Law 2. → FIX OBBLIGATORIO: (a) sanitizer/taint-check sul diff PRIMA
   dell'invio cloud; (b) moduli PII-adiacenti → SOLO Ollama-locale (no cloud); (c) autorizzazione esplicita Zero
   per endpoint DeepSeek/Gemini con zero-retention, OPPURE ensemble degradato a Ollama-locale + Claude-CLI dove
   il codice è sensibile. Questo cambia il design: **l'ensemble cloud è condizionato al confine-PII (= Pezzo 2!)**.
4. **[ASSUNZIONE-NASCOSTA] #4+#8**: si assume che i ~30 deterministici esistenti siano CORRETTI/senza-falsi-negativi.
   Bandit/CodeQL hanno falsi-negativi noti. L'affermazione "chiude il 70% del gap" è SENZA derivazione. →
   l'anti-reward-hacking detector va inquadrato come **"euristico di primo livello facilmente aggirabile, da
   aggiornare continuamente"**, NON barriera affidabile. E serve misurare il tasso di falsi-negativi su un
   benchmark di codice-malevolo, non assumere efficacia.
5. **[TENSIONE LOGICA] #7**: "non-risolvibile all-AI" vs "ensemble-LLM come strato" → riconciliare:
   l'ensemble RIDUCE la correlazione errori ma non la azzera; è solo UNO strato del funnel PRE-UMANO, mai la
   soluzione. (Già coerente col design §3, ma da dire esplicitamente.)
6. **[CLAUDE NELL'ENSEMBLE] #10**: "no Claude×N" è giusto come "no ridondanza intra-lineage", ma Claude PUÒ
   essere UNO dei lineage (1 istanza) accoppiato ai cross-lineage — aggiunge segnale indipendente. La regola
   esatta è: **N=1 per lineage, privilegia diversità**, non "zero Claude".

### 7.4 CONVERGENZA + RAFFINAMENTI del council Pezzo 1
**Convergenza (3/3)**: ripara-i-2-rotti-PRIMA · mutation-incrementale-non-full · ensemble-no-ridondanza-intra-lineage
· gate-umano-binario-deterministico-non-LLM-summary.

**3 raffinamenti CRITICI di DeepSeek che correggono la spec**:
- **R1**: il meta-verificatore DEVE essere immutabile (firma-hash + CI isolato CODEOWNERS-only), altrimenti
  è ricorsivamente disarmabile. [§4 aggiornato]
- **R2**: operatori di mutazione FISSI standard (mutmut/cosmic-ray), mai generati dall'agente + canary nascosti. [§3 strato 2]
- **R3 (collega Pezzo 1 ↔ Pezzo 2)**: l'ensemble-LLM-cloud è CONDIZIONATO al confine-PII. Dove il codice è
  PII-adiacente → Ollama-locale only. **Questo rende il Pezzo 2 (router-con-confine-PII) un PREREQUISITO dello
  strato-4 del Pezzo 1**, non indipendente. Dipendenza scoperta dal council.

## 8bis. CORREZIONI alla spec post-council (cosa cambia)
- **§4 meta-verificatore**: aggiungere immutabilità (firma-hash + CI isolato). NON è "intelligente" NÉ
  "fidabile-per-sempre" — è auditabile-una-volta + protetto-da-modifica.
- **§3 strato 2**: operatori mutation FISSI + canary-mutants-nascosti (anti-gaming del mutation stesso).
- **§3 strato 1**: anti-reward-hacking = euristico-primo-livello aggiornabile, NON barriera affidabile.
- **§3 strato 4**: ensemble condizionato al confine-PII → DIPENDE dal Pezzo 2. Claude ammesso N=1 nel mix.
- **NUOVA DIPENDENZA**: Pezzo 1 (strato 4) → richiede Pezzo 2 (router-PII). Da tracciare nel finale-coerenza.
