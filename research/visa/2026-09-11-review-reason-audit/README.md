---
adversarial_review: kimi-k3
date: 2026-09-11
domain: visa
client_case: none
sources:
  - /Users/nuzantara/nuzantara/.worktrees/mouth-visa-review-reason-audit-20260911/research/visa/2026-09-11-review-reason-audit/README.md
---

# Visa Oracle — verifica delle motivazioni, 11 settembre 2026

**Verdetto: il meccanismo è user-facing e funzionante, ma la copertura richiesta NON è raggiunta.**
Audit sul commit `be45266252f4e1ccbaf19d2b81c73f03af676e05`, Mini; Pro raggiungibile e sullo stesso SHA.
Branch `agent/mini-pro2/mouth/visa-review-reason-audit-20260911`. Perimetro: verifica e prove;
nessuna modifica a regole, copy di prodotto, modalità o infrastruttura; nessun deploy.
Gli unici effetti live sono le valutazioni sintetiche esplicitamente etichettate.

## Risposta alle due domande

1. **`review_reasons` è visibile.** Il percorso è `Decision.review_reasons` →
   `buildEngineOutcome` → `reviewReasons` → `OutcomeSheet.ReasonList` → testo EN/ID e fonti.
   Riferimenti al commit auditato: `engine-adapter.ts:897`, `OutcomeSheet.tsx:134` e `:555`,
   sotto `apps/mouth/src/app/(visa-oracle)/visa-oracle/`. Il test di rendering ha esercitato
   l'adattatore e il componente veri, con decisioni generate dal vero evaluator; non solo log.
2. **La copertura non è esaustiva.** `engine-adapter.ts:416` ha **9 voci**; il test
   `engine-adapter.test.ts:782` ammette **25 codici senza copy**. Tra questi c'è
   `DISCLOSED_UNCERTAINTY_REVIEW`: in ENGINE passa dal fallback `GENERIC_REVIEW_REASON`
   (`engine-adapter.ts:465–480`). La frase specifica “You marked one answer as ‘not sure’…”
   esiste solo nel baseline PREVIEW (`preview-adapter.ts:58`), non nella mappa pubblica.

**Prova live, non dedotta dal merge:** Chromium su `https://balizero.com/visa-oracle`,
11 settembre 2026 ~01:29 WITA, HTTP 200, `mode=ENGINE`, seq-20 v2026.9.6,
`review_reasons=[DISCLOSED_UNCERTAINTY_REVIEW]`. Il DOM e lo screenshot mostrano:
“Some of your answers need a person's judgment before we can confirm a path.”
Il motivo concreto — la risposta incerta — non viene comunicato.
[DOM e risposta sintetica ridotta](live-browser.json) · [screenshot](live-uncertainty.png).
La navigazione usa un resume sintetico; l'API è vera, senza response mock. Tutti i POST sono
marcati `synthetic_driver`, mai `real`. Un primo probe CLI con `request_category=tourism`
è stato rifiutato HTTP 400 (valore non ammesso); il probe corretto omette quel parametro.

## Censimento fresco

Il denominatore attuale è **67**, dopo #5855 e #5918; 21/43 è un dato storico, non l'ultimo stato.
Il driver rigenera i percorsi dal vero `computeNextNode` e `mapOracleFactsToApplicantFacts`.
Il replay usa il pack firmato seq-20 verificato crittograficamente, al suo `signed_at` e
all'orologio corrente. I due orologi danno lo stesso risultato in questa sessione.

| Misura su 67 percorsi | SUPPORTED | NO_SUPPORTED_PATH | NEEDS_INPUT | HUMAN_REVIEW |
| --- | ---: | ---: | ---: | ---: |
| Censimento esistente, senza disclosure flag | 55 | 10 | 2 | 0 |
| Richiesta completa prodotta dal frontend, con flag reali | **31** | **7** | **0** | **29** |

Il secondo rigo è un **replay offline del comportamento pubblico**, non un campione di 67
utenti reali né un censimento di traffico in produzione. Tutti i 67 percorsi e 5 casi limite
sono in [census.json](census.json), con stato, flag e codici, senza identità/fingerprint.

Delle 29 review, **13/29 (44,8%)** hanno una voce specifica visibile nella mappa:
`DISCLOSED_ACTIVITY_BOUNDARY_REVIEW`. **16/29 (55,2%)** mostrano il fallback:
`DISCLOSED_AMBIGUOUS_SPONSOR_REVIEW`, sui rami family/diaspora con sponsor straniero
(7 relazioni offshore per categoria, più i 2 rami onshore).
La presenza di una voce misura la copertura nominale; non certifica da sola la qualità del testo.

I due `NEEDS_INPUT` del censimento vecchio sono `offshore/retirement/property/age64` e
`offshore/retirement/undecided/age64`, entrambi su `family.sponsor_confirmed`.
Con i flag reali diventano **review per ACTIVITY_BOUNDARY**: non si può dedurre dalla scomparsa
di NEEDS_INPUT che il funnel abbia raccolto il dato. Il follow-up introdotto da #5855 esiste
(`OracleShell.tsx:519`, `engine-adapter.ts:698`), ma in questi due casi non viene offerto perché
l'adattatore backend ha già cambiato lo stato e svuotato `missing_facts`.

Limiti: campione di scenari, prima opzione per domanda, sottorami onshore non enumerati
completamente; non copre tutte le combinazioni di risposte. I 5 casi limite restano fuori dal 67.
Nessuna conclusione sulla legittimità di tutte le 29 review o sulla correttezza legale del pack.

## Il buco che il test di esaustività non vede

`engine-adapter.test.ts:727` raccoglie solo regole con `stage === HUMAN_REVIEW`.
Il vero evaluator costruisce una review anche da HARD_FILTER/ELIGIBILITY con
`on_unknown=HUMAN_REVIEW` (`evaluator.py:359`, `:383`, `:741`, `:878`).
Il pack corrente dichiara quattro ulteriori codici fuori sia dalla mappa sia dall'allowlist:

| Codice | Evidenza nel replay di questa sessione |
| --- | --- |
| `BRIDGING_ONSHORE_ONLY` | Emesso su `edge/bridging/unknown-location` |
| `BRIDGING_FROM_VISIT_ITK_PROHIBITED` | Emesso su `edge/bridging/unknown-status` |
| `BRIDGING_TO_BRIDGING_PROHIBITED` | Emesso sullo stesso caso con status sconosciuto |
| `VOA_NATIONALITY_ONLY` | Presente sul filtro con `on_unknown=HUMAN_REVIEW`; non emesso dal probe di nazionalità sconosciuta, preceduto dalle review globali |

I tre `BRIDGING_*` sono stati prodotti dal vero evaluator e renderizzati in EN/ID:
ognuno cade sul fallback. Sono casi sintetici aggiuntivi, non 3 dei 67 percorsi standard.
**Inventario strutturale: 38 codici = 20 del pack + 18 degli adattatori; 9 mappati, 29 non mappati.**
Dei 29 non mappati: 25 sono lacune già dichiarate, 3 ulteriori sono effettivamente emessi,
1 resta un candidato strutturale non dimostrato raggiungibile. Non presentare “38” come prova
che tutti i codici siano raggiungibili dal funnel attuale.

La lista dei 18 codici degli adattatori è corretta oggi, verificata contro la mappa backend e
le chiamate `Reason(code=...)` nel suo AST; il test frontend la ricopia a mano e quindi non
scopre automaticamente una futura emissione backend. Nessuna chiave della mappa attuale è stale.

Ulteriore limite semantico: il probe di nazionalità sconosciuta produce
`CALLING_VISA_REVIEW` e `CITIZENSHIP_LIST_DIVERGENCE`, che hanno copy ma descrivono rispettivamente
appartenenza alla lista e risposte discordanti. Una verifica di sola presenza della chiave
non distingue TRUE da UNKNOWN. Non riciclare il testo di esclusione per i `BRIDGING_*` in review:
il trigger riprodotto è un dato sconosciuto, non una violazione accertata.

Esiste anche una review **creata dal client**, distinta dai 38 codici backend:
`CLIENT_UNABLE_TO_VERIFY_DETAIL` (`outcome-fallbacks.ts:100–133`). Quando il browser non
può validare una risposta già riconosciuta come review, `OracleShell.tsx:264–298` sostituisce
i dettagli respinti con questa spiegazione locale. Ha testo EN/ID dedicato e visibile,
ma non una voce in `REVIEW_REASON_COPY`. Anche questo percorso è stato renderizzato nel probe.
Il bar deve prevedere esplicitamente tale eccezione tecnica, senza esporre dettagli non validati.

## Bar proposto a Zero e Astra

- Censire richieste complete con disclosure flag e un insieme dichiarato di casi `unsure`,
  sponsor straniero, review gate e fonti non correnti; mantenere separati data fissata e orologio corrente.
- Per ogni review residua: **100% dei codici con copy dedicato EN/ID, visibile nel componente finale**,
  niente fallback per codici conosciuti. Test anche per `on_unknown=HUMAN_REVIEW` e per gli adattatori
  backend; allowlist di copy mancante vuota. Specificare la vera causa dell'incertezza.
  La review tecnica del client deve avere una spiegazione locale dedicata e verificata;
  non è una motivazione legale da recuperare da un payload respinto.
- `NEEDS_INPUT` senza domanda raggiungibile: **zero**, misurati prima e dopo i flag. Un passaggio
  a review non conta automaticamente come cura. `NO_SUPPORTED_PATH` è un verdetto, non un dead-end.
- Misurare separatamente il tasso di risposte decisive e le review legittime. Il numero fresco
  comparabile qui è **38/67 risposte decisive e 29/67 review**. La soglia “quasi-zero” va fissata
  sul corpus completo e con review residua motivata, non dedotta dal vecchio 21/43.

Osservazione accessoria verificata nel medesimo screenshot: il pannello di contatto dice
“WhatsApp handoff is not configured”. La configurazione del contatto non è stata investigata
né modificata in questo audit; è da distinguere dalla copertura delle motivazioni.
DPIA, replay gold-persona e firma manuale restano i rischi residui già dichiarati, non nuovi blocchi ENFORCE.

## Verifica e riproduzione

**15 test** del censimento esistente + **181 test** frontend esistenti + **1 probe pytest**
(replay completo, entrambi gli orologi) + **4 probe Vitest** (rendering vero EN/ID dei replay,
proiezione dei 38 codici con metadata fixture dichiarati, rendering del payload live immutato,
fallback di verifica client): tutti passati.
Le firme delle decisioni offline usano la vera funzione `seal_decision` con una chiave
esplicitamente non segreta di test; non sono prova dell'integrità di produzione. Prezzi esclusi
tramite `UnavailablePricingCatalog`; nessun DB o LLM nel replay offline.

Artefatti di riproduzione: [generatore input](inputs.mts), [replay](test_census.py),
[probe del renderer](render.test.tsx), [browser sintetico](browser.mts).
I percorsi `/tmp/visaoracle-audit-20260911` sono deliberatamente quelli di questa sessione.
Da un worktree con le dipendenze del progetto:

```bash
# Dalla radice del worktree
mkdir -p /tmp/visaoracle-audit-20260911
npx --no-install tsx research/visa/2026-09-11-review-reason-audit/inputs.mts
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. python -m pytest ../../research/visa/2026-09-11-review-reason-audit/test_census.py -q -o addopts=''
# Prove live: usare esclusivamente credenziale driver in custodia e traffico sintetico.
jq '.rows[] | select(.label == "edge/tourism/unsure") | .request' /tmp/visaoracle-audit-20260911/inputs.json > /tmp/visaoracle-audit-20260911/live-request.json
PYTHONPATH=. python -m backend.scripts.visa_engine.probe_evaluate --payload /tmp/visaoracle-audit-20260911/live-request.json --full-body > /tmp/visaoracle-audit-20260911/live-response.txt
cd ../..
npx --no-install tsx research/visa/2026-09-11-review-reason-audit/browser.mts
# Copia temporanea per risolvere gli import relativi e usare il normale harness Vitest.
cp research/visa/2026-09-11-review-reason-audit/render.test.tsx 'apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/review-reason-session-audit.test.tsx'
cd apps/mouth
npx --no-install vitest run 'src/app/(visa-oracle)/visa-oracle/_lib/review-reason-session-audit.test.tsx' --maxWorkers=1
# Rimuovere soltanto la copia temporanea creata dal comando sopra dopo la verifica.
```

Esistenti: `python -m pytest backend/tests/services/visa_engine/test_interview_walk_census.py -q -o addopts=''`
(dalla root backend, venv attivo, `PYTHONPATH=.`), e Vitest sui file
`engine-adapter.test.ts`, `walk-corpus-determinism.test.ts`, `OutcomeSheet.test.tsx`, `OracleShell.test.tsx`,
`outcome-fallbacks.test.ts`.

## Adversarial review

This README is authored by a Codex session. Independent cross-family review: **Kimi K3**
(`kimi -r session_dbb009de-85fd-4d72-952c-7d21df829beb`), verdict **PASS-WITH-FINDINGS**.

Kimi K3 independently recomputed every load-bearing number from `census.json` (sample=67,
baseline 55/10/2, public 31/7/0/29, review-frequency split, mapped/unmapped/taxonomy counts,
decisive totals) and re-verified every `file:line` reference against `git show
be45266252:<path>` — both categories came back clean. The PII/identity sweep on
`census.json` and the live-claim cross-check against `live-browser.json` also came back
clean. Three MINOR evidentiary findings remain, recorded here **verbatim, as OPEN — not
corrected in the body above** (the body is pinned byte-for-byte to its reviewed source; a
correction here would break that pin, so any fix is a future PR's call):

- **OPEN — K1**: `engine-adapter.test.ts:782` points to a comment line inside the list (the
  list declaration is at :781, the first code entry at :783).
- **OPEN — K2**: `engine-adapter.ts:698` is the `path: string,` parameter line of
  `questionForFact` (the function definition is at :697).
- **OPEN — K3**: the "181 test frontend esistenti" figure is not independently verifiable
  from the artifacts alone — Kimi counted 81 `it()`/`test()` declarations in the 5 named
  files (451 across all 39 visa-oracle test files); 181 is only plausible as a post-`it.each`
  runtime expansion.

Kimi K3's full verdict text opens: `VERDICT: PASS-WITH-FINDINGS`.
