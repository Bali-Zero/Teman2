# W0 — Visa Oracle: motivazioni e contratto degli esiti

## 1. Mandate

`SHWEB-20260911 / W0-ORACLE-REASONS` · BLUE default · Gear 2 minimo · Mini.
Attivazione: scelta M include Oracle e ownership topic 3 concordata. Worktree nuovo
`mouth-shweb-w0-oracle-20260911`, task-id `shweb-w0-oracle-20260911`; SHA da main
aggiornato, nessuna ripresa della branch audit. Successo: ogni ragione conosciuta
ha spiegazione specifica EN/ID nel vero esito, senza perdere prudenza/integrità.

## 2. Owned perimeter

Dentro `apps/mouth/src/app/(visa-oracle)/visa-oracle/`:
`_lib/engine-adapter.ts`, `engine-adapter.test.ts` nella stessa directory `_lib`,
`_lib/outcome-fallbacks.ts` e relativo test se necessari alla distinzione tecnica;
`_components/OutcomeSheet.tsx` solo contenuto/fallback e relativo test.
Corpus/replay: `research/visa/2026-09-11-review-reason-audit/` da fonte congelata;
`apps/backend-rag/backend/tests/services/visa_engine/test_interview_walk_census.py`
e nuovo test inventario adiacente; nuovo script read-only di estrazione inventario
sotto `apps/backend-rag/backend/scripts/visa_engine/` con nome fissato nel brief.
Corner visaoracle e ledger soltanto per esiti misurati. Nuovi path in contract-lock.

Read-only: emitter `evaluate_path.py`, evaluator, models/OpenAPI, pack, prezzi,
engine rules, `oracle.css`, layout/theme, domande e storage/consensi. Nessun cambio
backend di produzione; frontend/backend test writer è W0. Nessun lock/manifest.
Un difetto oltre copy/inventario diventa scope delta separato, non un'estensione
silenziosa per dichiarare “motore finito”.

## 3. Sibling contract

Fonte: snapshot locale `evidence/oracle-audit/README.md`, con driver/census/prove
e hash nel manifest; originale nel worktree `mouth-visa-review-reason-audit-20260911`.
I driver importano source dalla struttura repository originale: per riprodurli,
collocarli nel path `research/visa/2026-09-11-review-reason-audit/` del nuovo worktree,
registrando i path nel contract-lock; non eseguirli dalla directory dello snapshot.
Baseline auditata da
quella sessione, da riprodurre: 67 cammini con flag completi, 29 review; inventario
strutturale 38 codici (9 copy dedicate, 29 mancanti). **Non tutti i 38 sono provati
raggiungibili**; il corpus è campione e non tutte le combinazioni del prodotto.

`Decision` e codici restano compatibili. Scoprire codici da tutti gli stage con
`on_unknown=HUMAN_REVIEW`, review rules ed emitter/adattatori reali; non una seconda
lista manuale del solo stage HUMAN_REVIEW. Congelare pack effettivamente usato,
hash/firma, clock e fixture. Non inferire ACTIVE dal filename con sequenza maggiore.
Le disclosure non normative non acquisiscono citazioni legali inventate.

## 4. Acceptance

- Inventario derivato riproducibile, zero omissioni note nella copy EN/ID; codice
  backend o pack nuovo rende rosso il controllo, chiave stale rilevata. Distinguere
  sconosciuto da escluso: `on_unknown` non può diventare “non sei idoneo”.
- Render adapter→OutcomeSheet veri: incertezza dichiarata, sponsor ambiguo,
  bridging unknown e altri codici conosciuti spiegati in entrambe le lingue.
  Future code sconosciuto mantiene fallback prudente; una risposta non verificabile
  comunica problema tecnico, non attribuisce al cliente una causa normativa.
- Nessun target artificiale sulla percentuale di review/supportati. Stessi input
  completi danno stessi stati/candidati/pricing/source refs prima/dopo. Ogni stato
  NEEDS_INPUT emesso ha domanda raggiungibile. In REVIEW `missing_facts` resta
  assente: `models.py` lo vieta; non aggirare l'adattatore per gonfiare il risultato.
- Suite inventario/replay + `engine-adapter`, `OutcomeSheet`, `OracleShell`,
  `outcome-fallbacks`, walk determinism e E2E v2; TSC/lint/build. Baseline storiche
  non contano come test nuovi. I Python girano dalla root backend in venv, PYTHONPATH=.
- Integrazione browser EN/ID con API reale solo tramite driver sintetico già
  autorizzato/configurato, mai `traffic_source=real`; evidenza ridotta senza PII.
  Verificare separatamente configurazione handoff esistente: niente destinatario
  inventato o link/QR prima del consenso. Config mancante resta impedimento esplicito,
  non si chiude l'handoff con una fixture positiva. Nessun invio di lead.
- Osservazione live dopo rilascio autorizzato: commit servito, pack dichiarato,
  payload sintetico e testo DOM specifico. Mancata prova reale = PENDING, non PASS.

## 5. Team

Ruoli da army-map §1bis; topic 3 indica owner, Dux e worktree attuale prima di BUILD.
Nessuna seconda window sul suo stesso perimetro. Reviewer di famiglia diversa dal
builder, gate fresco fuori contribution chain; registrare modelli/effort/thread.

## 6. Appetite and stop-loss

Proposta 5h, deadline UTC al lancio, rinnovo Zero/staff room; nessun budget token o
API nuovo. Cap comuni README, massimo due window totali. Se emerge necessità di
alterare schema/regole o fonte legale incerta, checkpoint con casi e nuovo mandato
proposto; non indebolire il gate. Oracle occupa lo slot motori.

## 7. Evidence and release

Manifest pack/emitter/fixture, inventario atteso, matrice codice→EN/ID→semantica,
log test/exit, browser e prova live distinta. **Bites:** il visitatore vede il motivo
concreto della review. W0 è indipendente da W2/W7 perché Oracle resta graficamente
congelato. Release solo con nomina/autorizzazione e gate sul HEAD corrente; nessun
flip ENFORCE/SHADOW, firma/attivazione pack o deploy da parte della staff room.
Rollback se cambia un esito, cala integrità/consenso o la copy converte UNKNOWN in NO.
