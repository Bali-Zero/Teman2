---
date: 2026-08-09
domain: operations
client_case: none
sources:
  - https://ai.google.dev/gemini-api/docs/pricing
  - https://developers.openai.com/api/docs/pricing
  - https://github.com/vectara/hallucination-leaderboard/
  - PG ledger llm_cost_events (query live 2026-08-09)
  - Cloud Monitoring serviceruntime/api/request_count, progetto nuzantara
---

# Quale LLM per il bot: costo e qualità contro gemini-3.5-flash

> Nasce dall'audit di spesa dello stesso giorno: $51.31/30gg su Gemini, il 97% del conto API.
> Causa accertata: PR #2611 (17/07) promuove `gemini-3.5-flash` a modello primario. Il volume non
> è cambiato, è cambiato il prezzo per chiamata (×31.7).

## 1. Il carico di lavoro reale (misurato, non stimato)

Interrogato `llm_cost_events` il 2026-08-09, finestra 30 giorni, `model='gemini-3.5-flash'`:

| Corsia | Token in | Token out | Chiamate | Costo |
|---|---|---|---|---|
| `rag.gateway.chat` | 26.053.409 | 312.825 | 1.402 | $40.92 |
| `rag.verifier` | 5.291.369 | 126.530 | 481 | $9.08 |

Fatti strutturali che decidono tutto il resto:

- **Media 18.168 token in ingresso contro 211 in uscita.** Il 92% del conto è INPUT ($47.13 vs $4.05).
  Qualunque leva sull'output è irrilevante per costruzione.
- **~2,9 chiamate al gateway per risposta completa.** Il verifier gira una volta per risposta
  (`reasoning.py:1005`), quindi 481 verdetti ≈ 481 risposte. Il raggruppamento temporale
  indipendente (gap 15s) ne conta 498: due metodi convergono su **~490 risposte in 30 giorni**.
- **Costo per risposta: ~$0.105.** Oggi è irrilevante perché il bot non è pubblico (scelta di Zero).
  È un moltiplicatore lineare il giorno che lo diventa.
- **Prefisso stabile di 5.103 token.** `ZANTARA_MASTER_TEMPLATE` è 22.638 char e i suoi tre soli
  slot variabili (`{user_memory}`, `{rag_results}`, `{query}`) stanno all'83-84%: c'è quindi un
  prefisso contiguo, byte-identico a ogni chiamata, **già pronto per il caching senza toccare il
  prompt**. Vale il 27% dell'input del gateway, $10.73/mese a prezzo pieno.

## 2. Costo — modellato sul nostro volume, non a listino astratto

Prezzi presi verbatim dalle pagine ufficiali il 2026-08-09. Colonna "30gg" = costo del NOSTRO
volume misurato con quel listino (`cost_model.py`, scratchpad; il modello riproduce il ledger a
−0,4%, quindi è tarato).

| Modello | in /1M | out /1M | 30gg | vs oggi |
|---|---|---|---|---|
| gpt-5-nano | $0.05 | $0.40 | **$1.74** | 0.03× |
| ministral-3b-latest | $0.10 | $0.10 | $3.18 | 0.06× |
| gemini-2.5-flash-lite | $0.10 | $0.40 | **$3.31** | 0.06× |
| mistral-small-latest | $0.15 | $0.60 | $4.97 | 0.10× |
| gpt-5.4-nano | $0.20 | $1.25 | $6.82 | 0.13× |
| gemini-3.1-flash-lite | $0.25 | $1.50 | $8.50 | 0.17× |
| gpt-5-mini | $0.25 | $2.00 | $8.71 | 0.17× |
| gemini-2.5-flash | $0.30 | $2.50 | $10.50 | 0.21× |
| gemini-3.5-flash-lite | $0.30 | $2.50 | $10.50 | 0.21× |
| mistral-large-latest | $0.50 | $1.50 | $16.33 | 0.32× |
| gpt-5.4-mini | $0.75 | $4.50 | $25.49 | 0.50× |
| gpt-5.1 | $1.25 | $10.00 | $43.57 | 0.85× |
| mistral-medium-latest | $1.50 | $7.50 | $50.31 | 0.99× |
| gemini-3.6-flash | $1.50 | $7.50 | $50.31 | 0.99× |
| **gemini-3.5-flash (ATTUALE)** | **$1.50** | **$9.00** | **$50.97** | **1.00×** |
| gemini-3.1-pro-preview | $2.00 | $12.00 | $67.96 | 1.33× |

Esclusi **per regola, non per prezzo**: Anthropic (API a token vietata — unico canale è la CLI OAuth
sul MAX, marginale $0 ma spawn di processo, inadatta alla corsia interattiva); DeepSeek (ritirato da
Zero il 19/07); Kimi, Qwen, GLM (cloud cinese — confine PII assoluto, e il gateway vede domande
cliente). Grok/xAI: non verificato.

**Caching Gemini** (stessa pagina): 3.5-flash $0.15/1M cachati (−90%) + storage $1.00/1M/ora.
Sul nostro prefisso: $10.73 → $1.07 di token + $3.67 di storage = **risparmio netto $5.98/mese**.
Lo storage si mangia il grosso del guadagno *a questi volumi*; a volume alto la leva scala,
lo storage no.

## 3. Qualità — cosa dice l'evidenza e cosa NON dice

Fonte primaria: **Vectara HHEM** (agg. 2026-05-11), 7.700+ documenti lunghi inclusi legal e
financial, misura quanto il modello inventa **riassumendo un documento fornito**. È il proxy più
vicino che esista al nostro compito reale: restare fedele ai chunk recuperati.

| Modello | Allucinazione | Fedeltà |
|---|---|---|
| gpt-5.4-nano | **3.1%** | 96.9% |
| gemini-2.5-flash-lite | **3.3%** | 96.7% |
| gpt-5.4-mini | 5.5% | 94.5% |
| gemini-2.5-pro | 7.0% | 93.0% |
| gemini-2.5-flash | 7.8% | 92.2% |
| gemini-3.1-flash-lite-preview | 8.2% | 91.8% |
| gpt-5.5 | 9.3% | 90.7% |
| claude-haiku-4-5 | 9.8% | 90.2% |
| gemini-3.1-pro-preview | 10.4% | 89.6% |
| gpt-5-nano | 10.5% | 89.5% |
| gpt-5-mini | 12.9% | 87.1% |
| gemini-3-flash-preview | 13.5% | 86.5% |
| gemini-3-pro-preview | 13.6% | 86.4% |

Il risultato controintuitivo: **su fedeltà, i modelli piccoli battono i grandi**, e i Gemini 3.x
stanno peggio dei 2.5. Il modello che usavamo prima del 17/7 (`gemini-3-flash-preview`) è il
**penultimo della lista Gemini**: era economico e poco fedele. Lo switch a 3.5-flash ha quindi
plausibilmente migliorato la qualità — ma `gemini-2.5-flash-lite` sarebbe stato insieme **più
economico E più fedele** di entrambi.

### Le lacune, dichiarate

- **`gemini-3.5-flash` NON è in classifica HHEM.** Non ha un tasso di allucinazione pubblicato:
  non posso dire se il modello che paghiamo sia migliore o peggiore dei suoi rimpiazzi su questo
  asse. È la lacuna più importante di tutta la ricerca.
- **Nessun dato di tool-calling.** BFCL (Berkeley, V4 agg. 12/04/2026) e llm-stats servono la
  tabella via JavaScript: entrambe le pagine tornano senza righe. Per la corsia gateway — che deve
  scegliere quali collezioni interrogare — non ho evidenza pubblica utilizzabile.
- **Nessun benchmark in bahasa Indonesia** ottenuto. Il bot risponde a clienti in ID/EN/IT/RU/FR.
- **Un solo asse.** HHEM misura la fedeltà nel riassumere, non la scelta della lingua, non il
  rispetto delle istruzioni, non il tool-use.

> **Provenienza, dichiarata.** Le tre corsie di ricerca delegate a subagent sono morte tutte alla
> nascita con `401 OAuth access token has been revoked` e **non hanno prodotto una sola riga**:
> ogni dato di questo documento viene da fetch dirette della sessione, verificate una per una.
> Causa: la sessione porta in ambiente un `CLAUDE_CODE_OAUTH_TOKEN` revocato che gli spawn
> ereditano, mentre la credenziale su disco è viva (sonda `unset … ; claude -p` → PONG, RC=0).
> È lo scar [[m5-claude-oauth-revoked-deploy-rerouted-via-glm]] del 2026-08-08, riprodotto: il
> `/login` dell'operatore NON sana la corsia subagent della sessione già avviata. Conseguenza sul
> perimetro: Grok/xAI e i benchmark indonesiani erano assegnati a quelle corsie e **non sono mai
> stati tentati** — sono lacune non-provate, diverse da BFCL che ho tentato io e trovato illeggibile.

## 4. Le corsie vanno separate

Sono due lavori diversi che oggi girano sullo stesso modello caro:

**Corsia verifier** — giudice deterministico (`temperature=0.0`), output JSON schema-validato di
~95 token, compito = "questa bozza è fedele al contesto?". È **esattamente** ciò che HHEM misura.

| | costo 30gg | allucinazione |
|---|---|---|
| gemini-3.5-flash (oggi) | $9.08 | non pubblicata |
| gpt-5.4-nano | $1.22 | 3.1% |
| gemini-2.5-flash-lite | **$0.58** | **3.3%** |

**Corsia gateway** — deve fare function calling e generare in 5 lingue. HHEM è un proxy debole e
non ho BFCL. Qui non si cambia sulla fiducia: si misura.

Scenari sul volume misurato:

| | 30gg | oggi | se il bot va pubblico (×20) |
|---|---|---|---|
| A. com'è oggi | $50.97 | 100% | ~$1.019/mese |
| B. solo verifier → 2.5-flash-lite | $42.48 | 83% | ~$850 |
| C. B + caching del prefisso | $36.49 | 72% | ~$730 |
| D. tutto su 2.5-flash-lite | $3.31 | 6% | ~$66 |

## 5. Stato degli attuatori (verificato su disco e su Fly)

- **`VERIFIER_MODEL`** — variabile d'ambiente, default `gemini-3.5-flash`
  (`verification_service.py:101`), **non impostata** su nuzantara-rag. Cambiare corsia verifier è
  un `fly secrets set`, senza deploy di codice.
- **`PRIMARY_MODEL_NAME`** — è un secret su Fly ma **nessuna riga di codice lo legge** (0 occorrenze
  in `apps/` e `scripts/`). È una leva apparente: il modello primario è cablato in
  `ModelName.PRIMARY`. Cambiarlo richiede codice + deploy. Superscar #2, esiste ≠ armato.
- **`llm_gateway.py:259-260`** — `model_name_pro` e `model_name_flash` puntano **entrambi** a
  `ModelName.PRIMARY`: esiste uno slot progettato per due livelli, collassato su uno. Ogni turno,
  facile o difficile, paga il modello caro.
- **`apps/backend-rag/scripts/verifier_model_ab.py`** — harness A/B già scritto: confronta modelli
  candidati sugli STESSI (query, risposta, contesto) misurando latenza e accordo sul gate 0.7.
  Gira offline su `data/curated_qa/*.jsonl`, input non-PII pre-vagliati.

## 6. Raccomandazione

1. **Verifier → `gemini-2.5-flash-lite`**: −$8.50/mese, e con la miglior fedeltà misurata sul
   board (3.3% contro un modello attuale senza dato pubblico). Reversibile con una variabile.
   Da provare prima con `verifier_model_ab.py` sull'accordo dei verdetti.
2. **Caching del prefisso sul gateway**: −$5.98/mese oggi, molto di più a volume. Il prompt è già
   strutturato per riceverlo. Da verificare prima: se il caching *implicito* di Gemini è già
   attivo, potremmo già pagare meno di quanto il ledger dichiari.
3. **Gateway: non toccare senza A/B.** È la corsia che parla ai clienti, non ho evidenza di
   tool-calling, e HHEM non copre né la scelta della lingua né il function calling.
4. **Il ledger va corretto perché registri i token cachati** (`cached_content_token_count`), oggi
   letto solo dal client DeepSeek ritirato: senza, non potremo misurare l'effetto della leva 2.

## §Solo-operatore

- La fattura vera di Cloud Billing (progetto `nuzantara`, `930328104463`) — non esposta da
  `gcloud`, nessun export BigQuery: serve la console.
- La scelta del modello per la corsia client-facing è una decisione qualità/business (Legge 5).
- Un'eventuale chiave OpenAI per il piano gateway/verifier: OpenAI è già in produzione per gli
  embedding, ma allargarne l'uso è autorizzazione di Zero.
