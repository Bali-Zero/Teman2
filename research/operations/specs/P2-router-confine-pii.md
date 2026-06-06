---
date: 2026-06-06
pezzo: 2 di 9
nome: router con confine-PII + burst-cloud
ruolo: CRITICO-2 — sostrato di esecuzione. PREREQUISITO del Pezzo 1 (strato-4 ensemble-LLM)
status: SPEC (studio) — non implementata
metodo: deep-research (22 claim 3-0 / 3 refutati) + reuse-first interno + council 4-LLM pieno
council_pieno: SÌ (sovranità-PII = errore legale costoso)
dipendenze: Pezzo 1 strato-4 dipende da questo. Questo è indipendente (foundational).
---

# SPEC Pezzo 2 — router con confine-PII + burst-cloud

> Il sostrato che instrada ogni task a modello locale-vs-cloud garantendo (per quanto STRUTTURALMENTE
> possibile) che PII cliente non finisca al cloud. Errore = violazione legale UU PDP.

## 0. La domanda e la risposta (verificata 3-0)

**Domanda**: si può GARANTIRE che PII non finisca al cloud, o è strutturalmente best-effort?

**Risposta (deep-research, 22 claim 3-0)**: **NO. È STRUTTURALMENTE best-effort.**
- Il vendor stesso lo ammette (Presidio FAQ: "no guarantee... additional systems should be employed"). [3-0]
- Floor falsi-negativi non-zero OVUNQUE: Presidio recall 0.62-0.84 (~16% mancato), miglior LLM 2026
  (Gemini 3 Pro) ~24% mancato sugli span, miglior client-side (Casper ~1.5% miss). [3-0]
- Leak reali: 159 nomi mancati in un corpus; **LiteLLM bug #8359** (PII mascherata-nei-log arrivava
  NON-mascherata ad AWS Bedrock). [3-0]
- Presidio NON ha benchmark su PII INDONESIANE (KTP/NPWP/akta/nomi-lowercase-WA) → rischio PEGGIORE.

**CONSEGUENZA (3-0)**: l'unica postura difendibile = **DEFENSE-IN-DEPTH + AIR-GAP ARCHITETTURALE**:
NON "pulisci e manda", ma **decidi local-vs-cloud PRIMA**. Se task TOCCA PII → modelli SOLO-LOCALI, la
chiave cloud nemmeno raggiungibile su quel path. Il redactor è il SECONDO strato, mai il gate primario.

## 1. Cosa esiste GIÀ (reuse-first — componenti SCOLLEGATI dal path principale)

Nuzantara ha i mattoni ma scollegati:
- **`_redact_pii.py`** = redactor 4-pass fail-closed OTTIMO (NPWP/KTP/KITAS/passport + nomi-CRM-da-Postgres)
  MA wired SOLO evolver pipeline. ← IL GIOIELLO da cablare al path principale.
- `pii_scanner.py` (Presidio + recognizer-KTP/NPWP custom) = output-side (scruba risposte, non prompt-pre-cloud).
- `dlp.py` 3-layer (filename + regex + Ollama-classifier gemma4) = solo media-indexing.
- `multi_ai_adapter.py` ha map `PRIVACY_SENSITIVE→QWEN` MA richiede caller-sa-già (no auto-detect).
- `federation_orchestrator.py` classifica per DOMINIO via Qwen-locale (no sensibilità-PII). CLASSIFIER già Ollama!
- `claude-max-usage-watcher` monitora quota-5h ma ALERT-ONLY.
- `llm_cost_recorder` traccia costi (triple-write) ma ZERO budget-enforcement.

**FINDING GRAVE**: `federation_orchestrator.py:152` passa prompt RAW ai cloud agent SENZA filtro PII (il
commento "PII-safe" è solo per logging). → **Law 2 OGGI NON è enforced da codice nel path principale.**

## 2. I 5 GAP

| # | Gap | Tool/componente |
|---|---|---|
| G1 | PII-detector pre-cloud nel path principale | cablare `_redact_pii.py` (esiste) |
| G2 | router sensibilità-aware (classificatore PII→local/cloud) | estendere Qwen-classifier di federation |
| G3 | sanitizer REVERSIBILE (round-trip token→valore) | NUOVO layer su Redactor [valutare se serve] |
| G4 | quota-aware stop/resume automatico | far AGIRE il watcher + LiteLLM budget-hard |
| G5 | hook pre-dispatch in federation | nuovo middleware |

## 3. ARCHITETTURA — air-gap-first + defense-in-depth

```
Task in ingresso
  │
  ▼ STRATO A — CLASSIFICATORE SENSIBILITÀ (Qwen-LOCALE, default-DENY)
  │  Decide: PII-adiacente? → ramo LOCALE. Cloud-safe? → ramo CLOUD.
  │  DEFAULT-DENY: in dubbio → LOCALE. (best-effort, ma è il 1° filtro)
  │  WHITELIST esplicita di task-tipi-cloud-safe (non blacklist-PII) — più sicuro.
  │
  ├──────────────► RAMO LOCALE (Ollama) ◄── la chiave cloud NON è raggiungibile qui (air-gap reale)
  │                 task PII-adiacenti girano SOLO locale. Punto.
  │
  ▼ RAMO CLOUD (solo se classificato cloud-safe)
  │  ▼ STRATO B — REGEX BACKSTOP DETERMINISTICO (2° filtro, immune-da-classificatore-sbagliato)
  │  │  regex KTP(16-digit)/NPWP/passport/phone-+62 su prompt. Match → BLOCCA + reroute-locale.
  │  │  (cattura ciò che il classificatore-A ha mancato; deterministico, no falsi-positivi-LLM)
  │  │
  │  ▼ STRATO C — REDACTOR _redact_pii.py (3° filtro, fail-closed)
  │  │  4-pass + nomi-CRM-da-Postgres. Se output < min_chars → fail-closed (non manda nulla).
  │  │
  │  ▼ STRATO D — PRESIDIO pre_call guardrail (4° filtro, recognizer-indonesiani)
  │  │  Analyzer:5002 + Anonymizer:5001. BLOCK sui tipi più sensibili (non mask).
  │  │
  │  ▼ LiteLLM GATEWAY → cloud (Claude-CLI/Gemini/DeepSeek)
  │     routing + fallback-cascade (429-cooldown) + budget-HARD-fail-closed + cost-tracking.
  │     zero-retention enterprise terms come backstop contrattuale.
  │
  ▼ AUDIT: ogni decisione local/cloud + ogni BLOCK loggato (pii_violations esistente).
```

**Principio**: 4 filtri sovrapposti PRIMA del cloud (classificatore + regex-backstop + redactor + Presidio),
perché ognuno è best-effort ma la loro COMPOSIZIONE abbassa il floor. NESSUNO è il gate unico. L'air-gap
(ramo-locale senza chiave-cloud) è l'unico vero confine; il resto riduce il rischio sul ramo-cloud.

## 4. DECISIONI (proposte)

- **D1 [PRIORITÀ]**: cablare `_redact_pii.py` + regex-backstop al path principale (G1+G5+G2). Chiude il
  finding-grave (federation passa PII raw). Questo PRIMA di LiteLLM.
- **D2**: AIR-GAP-FIRST con WHITELIST cloud-safe (non blacklist-PII) + default-deny. Costa performance
  (più task vanno locale) ma è l'unica postura sicura.
- **D3**: LiteLLM come gateway — MA valutare costo-migrazione vs wrapper-minimale (council §6). Bug #8359
  → Presidio NON è il single-gate, è il 4° strato.
- **D4**: watcher AGISCE (G4) — su CRIT% → federation a Ollama-only + LiteLLM budget-hard backstop.
- **D5**: sanitizer-reversibile (G3) — valutare se serve (forse no per codice-non-PII; council §5).

## 5. DIPENDENZA col Pezzo 1 (scoperta dal council P1)
Il Pezzo 1 strato-4 (ensemble-LLM su code-diff con DeepSeek+Gemini) USA questo router. Conseguenza:
**se il codice può contenere PII (fixtures/seed/stringhe), l'ensemble del Pezzo 1 VIOLA Law 2** a meno
che passi per gli strati B-C-D di questo router. → i due pezzi sono accoppiati QUI. Da risolvere nel finale.

## 6. DA ATTACCARE (council in corso — §7)
- Air-gap sposta il rischio sul classificatore (anch'esso best-effort)? Default-deny paralizza il burst?
- Codice "sanificato" contiene davvero zero PII (fixtures/seed/connection-string/nomi-tabella)?
- LiteLLM single-point-of-failure vs wrapper-minimale?
- Presidio su PII indonesiane: recognizer esistenti bastano?

## 7. COUNCIL 4-LLM — difetti
### 7.1 Gemini (red-team) — INTEGRATO: 3 BUG REALI nel codice (non ipotesi) + leak ineluttabile
> Gemini ha LETTO il codice reale. Trovati 3 difetti CRITICI in `_redact_pii.py` (il "gioiello").

**3 BUG REALI azionabili OGGI (verificati nel codice):**
1. **[CRITICO — FAIL-OPEN su DB down]** `_redact_pii.py:196-235` `_load_pg_names()`: se Postgres irraggiungibile
   → ritorna `[]` + log-warning + **PROSEGUE senza eccezione** = nomi-CRM NON redatti, codice continua come
   no-op. È un **fail-OPEN mascherato da fail-closed**. → FIX: se DB-down → fail-CLOSED (blocca l'invio cloud),
   NON proseguire con lista-vuota. Il "fail-closed" della spec era FALSO per Pass-4.
2. **[CRITICO — case-sensitivity]** `_redact_pii.py:191`: regex nomi-CRM compilata SENZA `re.IGNORECASE`
   (presente invece in Pass1/Pass2). → "budi santoso" lowercase (tipico WhatsApp) BYPASSA il filtro. → FIX:
   aggiungere `re.IGNORECASE`. One-liner.
3. **[CRITICO — leak via repo-exploration]** anche se il PROMPT è sanificato, `gemini-explore`/`claude-redteam`
   leggono **i FILE del repo direttamente** (test_remediator.sqlite, logs/, fixtures, .env-locali) → leak massivo
   FUORI dal prompt. → la sanificazione-del-prompt è INSUFFICIENTE; serve sandbox/filesystem-isolation.

**Altri difetti (ALTO/MEDIO):**
4. [ALTO] Classificatore Qwen-9B fallibile su input atipici (`const user = "B-u-d-i"`, PII-spacing-strano) +
   fallback-keyword (riga 274) NON garantisce detection → manda comunque al cloud.
5. [ALTO] Tensione default-deny vs produttività: se tutto va locale, dev usa bypass (`--no-confirm` riga 524)
   → invalida il router. (Converge con la domanda del brief.)
6. [ALTO] LiteLLM single-point + log-leakage: bug #8359 + log-non-crittografati-a-riposo = bersaglio PII-storiche.
7. [MEDIO] Diminutivi/storpiature WhatsApp ("bpk budi", "pak wawan") — Pass-4 controlla solo match-esatti CRM → mancati.
8. [MEDIO] Reversibilità (G3): redazione one-way → codice cloud con `[NPWP-REDACTED]` non-compilabile → dev tentato di mettere PII reale nel prompt.
9. [MEDIO] Telemetria Langfuse/LangSmith: stack-trace con variabili-locali-non-sanificate → PII a server cloud telemetria.

**SINGOLO PUNTO DI LEAK INELUTTABILE (collega al Pezzo 3)**: assenza di **sandbox di isolamento**. L'agente
locale legge il sorgente in chiaro E ha canale-rete-aperto verso le API → qualsiasi prompt-injection o libreria
compromessa esfiltra PII dalla memoria/file-temp via HTTPS **bypassando LiteLLM**. → **il confine-PII (Pezzo 2)
RICHIEDE il sandbox (Pezzo 3)**. Nuova dipendenza scoperta: P2 → P3.

### 7.2 Codex (costruttivo) — [in attesa]
### 7.2 Codex GPT-5.5 (costruttivo) — INTEGRATO: MVL + scoperta R3-KILLED + whitelist-positiva
> Codex ha LETTO il codice + scoperto che LiteLLM è GIÀ stato killato. Riuso-first che paga.

1. **MVL `privacy_preflight()`**: hook prima di ogni `run_dispatch()` in federation_orchestrator:
   policy-default-deny → Qwen-sensitivity → regex/denylist → `_redact_pii` → Presidio-rescan → quota → dispatch.
   `PrivacyDecision = CLOUD_ALLOWED | LOCAL_ONLY | BLOCKED`. Se redactor fallisce/modifica → cloud-vietato.
   Trigger LOCAL_ONLY: prompt contiene crm/client/ktp/passport/npwp/akta/wa/osint/data/. **Chiude il buco
   raw-prompt SENZA migrare stack.**
2. **SCOPERTA: `R3-KILLED-litellm-gateway.md` ESISTE** (verificato da me): LiteLLM è stato **KILLED il 2026-05-21**
   da panel DeepSeek per **rischio billing-Anthropic-accidentale** (il LiteLLM-Anthropic-backend è pay-per-token,
   BANNATO). → **CORREGGE la D3 della spec**: NON migrare a LiteLLM. Wrapper-minimale attorno a `ai-dispatch.sh`.
   (Converge con DeepSeek #6.) Se mai LiteLLM in futuro: self-host + logging-raw-off + test-automatico-no-Anthropic-billing.
3. **Whitelist POSITIVA (non blacklist-PII)**: `PUBLIC_CODE_REPO | PUBLIC_DOCS_RESEARCH | SYNTHETIC_TEST |
   ARCHITECTURE_META` → tutto il resto LOCALE. Se task misto → SPLIT: cloud riceve solo subtask-pubblico-sintetizzato,
   pezzo-cliente resta locale. → **risolve Gemini #5 (default-deny vs produttività): non blocchi tutto, abiliti il sicuro.**
4. **Presidio indonesiano**: sposta recognizer KTP/NPWP/passport/phone da `pii_scanner.py` nel gate-pre-cloud +
   context-words (nik/ktp/npwp/paspor/akta/rekening/wa/kitas) + denylist-CRM + test-recall su corpus-sintetico+reale.
5. **Quota-aware**: watcher scrive `quota_state.json` → orchestrator legge `normal|cloud_paused|local_only`.
   Soglia critica → stop-cron-Claude + queue-cloud-safe + local-only-resto + resume-su-finestra. Evita che il
   fallback-quota AGGIRI il confine-PII (insight chiave).
6. **Sanitizer reversibile**: NO di default — meglio fixture-sintetica. Reversibile solo per round-trip controllati,
   TokenVault-locale (SQLite/Keychain) TTL-breve MAI-loggato (reversibilità aumenta blast-radius). → risolve G3.
7. **PILOTA isolato**: 2 test pytest subprocess-mock. Caso-A "fix CRM cliente con KTP/NPWP" → ZERO chiamate-cloud +
   audit LOCAL_ONLY. Caso-B "analizza routing senza dati-cliente" → passa cloud. Assert: niente-prompt-raw-in-audit
   (solo hash); se Presidio/redactor fallisce → blocco.

### 7.3 DeepSeek V4 Pro (logico) — INTEGRATO: errori fattuali + tensioni logiche
> Modello verificato: deepseek-v4-pro. Ha trovato 2 errori fattuali nella mia spec + tensioni profonde.

1. **[NUMERO CORRETTO — il floor era SBAGLIATO]**: ho scritto "Presidio ~16% mancato" ma recall 0.62-0.84 →
   floor reale fino al **38% mancato** (caso PEGGIORE), non 16% (caso migliore). **Ho riportato il best-case
   come floor.** → CORREZIONE: floor = "16-38% mancato a seconda del corpus", e su PII INDONESIANE (no-benchmark)
   potenzialmente PEGGIORE.
2. **[PARADOSSO RICORSIVO + NON-SEQUITUR — "garanzia" è ingannevole]**: l'air-gap si basa sul classificatore
   che è ESSO best-effort → "garanzia" è falso. Stesso loop del Pezzo 1 (chi-classifica-il-classificatore).
   → CORREZIONE: "air-gap = la contromisura PIÙ ROBUSTA disponibile, ma resta probabilistica per via della
   classificazione iniziale". Non "garanzia". Onestà.
3. **[VINCOLO-VIOLATO LiteLLM↔Claude-CLI]** (converge con R3-KILLED): LiteLLM si integra con l'API-Anthropic
   pay-per-token (BANNATA), NON con Claude-CLI-OAuth. Architettura contraddittoria. → già corretto da §7.2.2.
4. **[VINCOLO-VIOLATO Presidio ARM64]**: spaCy/transformer potrebbero richiedere build-x86 → su M-series
   emulazione/crash. → DA VERIFICARE empiricamente prima di adottare (spike). Possibile fallback: recognizer
   regex-puri (no-transformer) che girano nativi.
5. **[ASSUNZIONE codice≠PII]** (converge con Gemini #3): il codice CONTIENE PII (fixtures/seed/stringhe/commenti).
   La dicotomia "codice→cloud / PII→locale" è FALSA. → CORREZIONE: il burst-cloud richiede SCAN (non solo
   redaction) anche del codice, + Codex #6 SPLIT (solo subtask-pubblico-sintetizzato va al cloud).
6. **[CONTRADDIZIONE Pezzo1↔Pezzo2]**: se P2 non sigilla, l'ensemble-LLM-cloud del P1 riceve PII → viola Law 2.
   Coerenti solo assumendo protezione-non-dimostrata. → de-risking esplicito: confinare l'ensemble-P1 a
   LOCALE (Ollama) finché il falso-negativo non è accettabilmente basso; cloud-ensemble solo su codice-passato-da-split.
7. **NOTA su DeepSeek #NUMERO "Gemini 3 Pro non esiste (2024)"**: DeepSeek SBAGLIA qui — siamo nel 2026, Gemini
   3 Pro esiste (è `agy` nel nostro stack). Training-cutoff di DeepSeek. MA il sotto-punto (numero ~24% non
   trasferibile a PII-indonesiane) è valido. Esempio del perché si verificano i panelisti, non si fidano ciecamente.

## 8. CORREZIONI alla spec post-council (cosa cambia)
- **D3 RIMOSSA**: NO LiteLLM-gateway (già KILLED 2026-05-21, rischio billing-Anthropic). → wrapper-minimale su ai-dispatch.sh.
- **§3 architettura**: "air-gap = garanzia" → "contromisura più robusta, probabilistica". Whitelist-POSITIVA (Codex #3),
  non blacklist-PII. SPLIT task-misti (solo subtask-pubblico al cloud).
- **§0 numeri**: floor Presidio = 16-38% (non 16%); PII-indonesiane no-benchmark → peggiore.
- **BUG REALI da fixare PRIMA** (Gemini): `_redact_pii.py` fail-OPEN-su-DB-down → fail-closed; + `re.IGNORECASE` nomi-CRM.
- **NUOVE DIPENDENZE**: P2→P3 (confine-PII richiede sandbox per leak-via-repo-read). P1-ensemble confinato locale finché FN-alto.
- **DA VERIFICARE (spike)**: Presidio su ARM64 (possibile fallback regex-puri).

## 9. STATO Pezzo 2
Council pieno completato (3/3, convergenza tripla). 3 BUG REALI nel codice scoperti (azionabili oggi).
1 decisione corretta (LiteLLM già killato). 2 errori fattuali miei corretti (floor-recall, "garanzia").
Dipendenze: P2→P3 (sandbox), P1↔P2 (ensemble confinato). Postura onesta: confine-PII = best-effort multi-strato,
mai garanzia. MVL = `privacy_preflight()` + fix-2-bug + whitelist-positiva, attivabile senza migrare stack.
