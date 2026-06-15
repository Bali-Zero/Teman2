---
date: 2026-06-14
domain: compliance
client_case: none
sources:
  - apps/backend-rag/backend/services/rag/agentic/reasoning.py (verified file:line)
  - apps/backend-rag/backend/services/rag/agentic/orchestrator_response.py (verified)
  - apps/backend-rag/backend/services/rag/agentic/reasoning_utils.py (verified)
  - apps/backend-rag/backend/services/rag/agentic/orchestrator_streaming_core.py (verified)
  - apps/backend-rag/backend/app/core/constants.py (verified)
  - apps/backend-rag/backend/services/rag/crag_router.py (verified)
  - apps/backend-rag/backend/services/rag/confidence.py + nlm_verifier.py (verified)
  - apps/backend-rag/backend/services/rag/kg_subgraph_property.py (verified)
  - git commit #298 "v3 quick-wins — domain ABSTAIN thresholds" (root-cause provenance)
  - Multi-LLM panel 2026-06-14: Gemini 3.5 Flash High (synthesis) + GPT-5.5 Codex (refuter)
agent: opus-mythos M1 (Opus 4.8, 1M)
---

# Mythos M1 — TAC del cervello cognitivo RAG (evidence-threshold split-brain)

## §0 Executive

Il LEAD (domanda #31) diceva "due abstain path divergenti". **Falso per difetto: sono
(almeno) TRE decisori** che confrontano la *stessa* `evidence_score` con soglie diverse,
più ~6 copie sparse del literal `0.15` e 4 sistemi di bande di confidenza coesistenti.

Ma il finding di SECONDO ordine è il rovesciamento prodotto dal refuter: **la divergenza
di VALORE è in buona parte LEGITTIMA, non un bug.** `reasoning.py` è un *generation gate*
(genera o sopprime advice regolato — e governa lo STRICT-ABSTAIN dei domini critici);
`orchestrator_response.py` è un *label gate* (setta il flag `abstain`). Sono policy diverse,
con scopi diversi. Consolidare tutto a un numero unico — la "cura ovvia" — sarebbe una
**regressione di sicurezza**: farebbe generare advice fiscale su evidenza 0.11 dove oggi il
sistema correttamente tace.

Il vero difetto non è che divergono: è che divergono **in modo implicito, anonimo e non
testato** → indistinguibili da un bug, si rompono a vicenda silenziosamente, e nessuno
sa quale gate ha quale scopo.

**Terapia eseguita (in-perimetro, zero cambio di tassi prod):** `_abstain_policy.py` —
un `AbstainPolicy` frozen che NOMINA i quattro gate (`generation_threshold`,
`label_threshold`, `confidence_low/high`), li calcola UNA VOLTA dalle SSOT esistenti, ed
espone `is_divergent` per osservabilità. + un test che PINNA la divergenza intenzionale ai
boundary (tax 0.11, kbli 0.18) con un **tripwire anti-regressione** che fallisce se qualcuno
"riordina" reasoning.py al per-dominio. 7/7 verde. Nessun call-site prod toccato.

## §1 Abstain-threshold split-brain (l'organo malato primario)

La `evidence_score` (un numero 0..1 calcolato una volta) è gated da TRE siti indipendenti:

| Sito | file:line | Soglia usata | Cosa decide |
|---|---|---|---|
| **GENERATION** | `reasoning.py:561,630,632,642` (+ gemelli streaming 1187/1246/1248/1259) | flat `ABSTAIN_THRESHOLD=0.15` | genera o SOPPRIME la risposta; `<0.15` + dominio critico → **STRICT-ABSTAIN** (`:567-577`) |
| **LABEL** | `orchestrator_response.py:90-91` | per-dominio `get_abstain_threshold(query)` (tax .10/visa .12/kbli .20/def .15) | setta il flag finale `abstain` (UNICO posto) |
| **CONFIDENCE-ZONE** | `orchestrator_streaming_core.py:356-358` | `0.15`/`0.60` HARDCODED | emette `confidence_zone` nello stream verso il client |

Verificato a mano: `grep -c get_abstain_threshold reasoning.py` = **0**. `reasoning.py` non
setta MAI `.abstain` sullo state (grep vuoto) — decide solo il *contenuto*.

**Conseguenza dimostrata (test verde):**
- *KBLI @ 0.18*: generation genera (`0.18≥0.15`), stream dice non-abstain, ma label etichetta
  `abstain=True` (`0.18<0.20`) → risposta generata + flag astenuto in CONFLITTO.
- *Tax @ 0.11*: generation SOPPRIME (`0.11<0.15`) ma il per-dominio l'avrebbe accettata
  (`0.11≥0.10`) → l'intento #298 "tax over-rejects, abbassa la barra" è MORTO sul path che
  decide davvero se produrre la risposta.

**Provenienza (git):** il per-dominio è arrivato nel commit `#298 v3-quick-wins`, che toccò
SOLO `orchestrator_response.py` + `reasoning_utils.py`, mai `reasoning.py`. Un quick-win
bolt-on non propagato. **Infrastruttura a metà:** `_reasoning_policy.py:83`
`should_apply_low_evidence_policy(abstain_threshold=...)` accetta GIÀ la soglia come parametro
— il binario per la consolidazione è posato a metà, ma `reasoning.py:561` gli passa il flat.

## §2 Retrieval / rerank

Niente split-brain qui (subagent verificato + gate). Dettagli:
- `hybrid_search.py:32 RRF_K=60` (SSOT singolo, OK).
- Prefetch multiplier drift BENIGNO: `hybrid_search.py:431 limit*3` vs `reranker_integration.py overfetch_factor=4`. Euristiche, drift minore.
- `reranker.py:262 top_k=5` default è dead (i caller passano sempre `limit`). Code-smell, non bug.
- `crag_router.py:166,184` usa `EVIDENCE_ABSTAIN`/`EVIDENCE_CONFIDENT` come gate di routing
  (HyDE / deep-research / NLM-downgrade). **Il subagent aveva allucinato "EVIDENCE_ABSTAIN è
  dead code" → FALSIFICATO al gate-1**: è usato. `EVIDENCE_CAUTIOUS_HIGH` invece è davvero unused.

## §3 Confidence scoring

QUATTRO sistemi di bande coesistono con valori diversi (verificati):
- `constants.py:99-101` LOW/CAUTIOUS/HIGH = **0.15 / 0.6 / 0.6** — CAUTIOUS e HIGH IDENTICI → boundary ambiguo. Quasi-unused (solo test importano).
- `crag_router.py:31-33` = 0.15 / 0.60 / **0.70** (CONFIDENT≠HIGH di constants).
- `confidence.py:32-34` = **0.80 / 0.55 / 0.35** — usato davvero (`get_confidence_warning` :246-250).
- `reasoning_utils.py:556` per-dominio = 0.10/0.12/0.15/0.20.
- `nlm_verifier.py:23-24` finestra trigger NLM = 0.15–0.60.

## §4 KG / langgraph

- `kg_langgraph_orchestrator` NON produce un abstain parallelo: ritorna un `workflow.confidence`
  che confluisce nello stesso label-gate di orchestrator_response (verificato subagent + gate).
- **BUG GRAVE (out-of-perimetro, segnalato non fixato):** `kg_subgraph_property.py:388` chiama
  `calculate_subgraph_confidence(chains=, entities=, query=)` ma la firma reale
  (`confidence.py:255`) è `(workflow_source, steps_count, has_db_validation, unique_sources)` →
  **TypeError a ogni run** → cade nel `except` → usa il fallback HARDCODED `0.85/0.4`. Il
  commento sopra recita "Dynamic confidence instead of hardcoded values": l'antibody
  anti-hardcoding **è morto in culla e ripristina proprio l'hardcoded che voleva eliminare.**
  Nessuno se n'è accorto perché "funziona" (non crasha l'app — cade silenziosamente nel fallback).

## §5 Soglie sparse / SSOT

Il literal `0.15` vive in ≥6 posti indipendenti: `constants.py:96,99,103` ·
`reasoning_utils.py:561` (+ bucket di calcolo) · `crag_router.py:31` · `orchestrator_streaming_core.py:356`
· `nlm_verifier.py:23` · `query_plan.py:110` (`min_evidence_threshold` — **dead field**, grep prova
zero lettori non-test). ENV-seam asimmetrica: solo `DOMAIN_ABSTAIN_THRESHOLDS` è override-abile,
e solo su un path → un operatore che tuna l'env crede di aver cambiato la sensibilità ma 2 path
su 3 lo ignorano.

## §Meta-pattern — perché il cervello ha "doppia personalità" sulle soglie

> Sintesi-pattern Gemini 3.5 Flash High (verbatim): *"la decentralizzazione delle decisioni di
> dominio: trattare le policy di business come costanti locali da duplicare nei vari layer
> architetturali (generazione, response, streaming) anziché delegarle a un unico Motore di
> Policy autoritativo."*

Il refuter GPT-5.5 ha **raffinato** (e in parte rovesciato) questa diagnosi, e il mio gate-2 su
disco l'ha confermato: la malattia-delle-malattie NON è "duplicazione da pigrizia". È più sottile:

**Il sistema confonde DUE policy semanticamente diverse (generare advice regolato ≠ etichettare
un risultato) sotto UN nome unico ("abstain threshold"), e poi le implementa con valori che — a
ragione — devono divergere, ma senza mai DICHIARARE che la divergenza è voluta.** Il risultato:
ogni divergenza legittima è indistinguibile da un bug, ogni "fix di consolidazione" rischia di
cancellare una safety policy scambiandola per drift, e l'osservabilità è zero.

Tre evidenze trasversali:
1. **Schizofrenia tra layer**: generation-gate (contenuto) vs label-gate (flag) vs stream-zone,
   tre decisori che possono emettere risposta-generata + zona-confident + flag-abstain insieme.
2. **Antibody ciechi**: il fix per-dominio toccò solo 1 path su 3; il fix anti-hardcoding di
   `kg_subgraph_property` fallisce SEMPRE per un TypeError mascherato da `except` e ripristina
   l'hardcoded. Quando il sistema prova a curarsi, lo fa su un percorso parziale e non verifica.
3. **Nomi che mentono**: `CONFIDENCE_CAUTIOUS`==`CONFIDENCE_HIGH`==0.6; `EVIDENCE_ABSTAIN` vs
   `ABSTAIN_THRESHOLD` (stesso valore, due nomi); 4 triplette di bande con valori diversi. Il
   linguaggio del codice non distingue concetti che sono diversi.

**Contromisura strutturale (la cura che impedisce il riformarsi):** un `AbstainPolicy` object
upstream, calcolato una volta per query, che NOMINA esplicitamente i 4 gate distinti e li
distribuisce — preservando i valori divergenti correnti (niente cambio di tassi prod). Tutti i
siti leggono i campi nominati, nessuno hardcoda più il suo literal. Più un test che pinna la
divergenza INTENZIONALE ai boundary, NON la convergenza (sarebbe la regressione di sicurezza).

## §Terapia eseguita (test verde, in-perimetro)

Creato `apps/backend-rag/backend/services/rag/agentic/_abstain_policy.py` —
`AbstainPolicy` frozen + `build_abstain_policy(query)` che centralizza i 4 gate dalle SSOT
esistenti (NON inventa valori). Espone `is_divergent` per osservabilità.

Creato `.../tests/services/rag/agentic/test_abstain_threshold_convergence.py` — **7/7 PASS**:
- `TestAbstainPolicySSOT`: il policy pesca i valori dalle SSOT esistenti, è frozen.
- `TestIntentionalDivergenceIsPinned`: tax@0.11 generation-SOPPRIME (safe) / label-NO;
  kbli@0.18 generation-GENERA / label-ABSTAIN; default-domain → nessuna divergenza.
- `TestPanelGuardrail` (il tripwire del panel): **fallisce** se qualcuno fa diventare il
  generation-gate per-dominio su tax → cattura la regressione di sicurezza prima che bruci.

Verificato live: import-chain `get_current_user` OK, nessun import circolare (i 3 moduli
co-importano puliti), ruff pulito, `CONFIDENCE_LOW/HIGH` esistono. Suite RAG 168/170 (i 2
falliti sono `TestDetectTeamQuery`, env-driven su `settings.COMPANY_NAME`, FUORI dal mio scope
— provato: `test_reasoning_utils` non importa i miei file).

**NON eseguito by-design:** il wiring dei 3 call-site prod al `AbstainPolicy` cambierebbe il
percorso caldo → è il passo invasivo. Lo lascio come PR proposta (additivo già pronto: i siti
hanno ora un oggetto concreto da leggere). Il valore di oggi è SSOT + contratto + tripwire,
senza toccare i tassi di abstain in prod.

## §Solo-operatore (confine Zero)

1. **Wiring dei call-site al `AbstainPolicy`** — cambia il path prod (anche se a parità di
   valori). Decisione Zero su tempistica/deploy, con QA post-deploy (CLAUDE.md §11).
2. **`kg_subgraph_property.py:388` TypeError** — fix fuori dal mio perimetro (KG, non agentic).
   Va sistemato (passare i kwargs giusti o ripristinare l'intento dynamic-confidence) ma è un
   altro lane. Segnalato, non toccato.
3. **Embedding / re-index** — non toccato, nessuna proposta. `text-embedding-3-small` FROZEN.
4. **Cambio dei VALORI di soglia** (es. portare tax a 0.08) — altera i tassi di abstain in prod
   = decisione Zero, non drift di refactor. Questo audit ha esplicitamente NON cambiato valori.
