---
date: 2026-06-02
domain: operations
client_case: false
sources:
  - FASE1 census 7 zone (codice reale, ~241 entità)
  - FASE2 Codex GPT-5.5 (480 righe, 44 fonti primarie SOTA)
  - FASE2 DeepSeek V4 Pro (economics/ROI)
  - FASE2 Claude-Workflow (browser+predictive verificate)
---

# DOSSIER STRATEGICO AGENTICO NUZANTARA — Mappa + SOTA + 5 Liste Azionabili

> Sintesi 3-fasi: FASE 1 mappa il codice reale (7 zone), FASE 2 deep-research SOTA 2026
> (Codex+DeepSeek+Claude), FASE 3 = questo dossier. Ogni numero ancorato a fonte in-turn.
> Metodo onesto: agy fallito 2× (timeout), aree 1-6 coperte da FASE1+Codex di striscio, NON
> da un 4° LLM. Claude-Workflow: bug StructuredOutput, 11/13 aree perse, salvate via Codex.

---

## 1. NUMERI CARDINALI (verificati sul disco)

| Metrica | Valore | Fonte |
|---|---|---|
| Entità agentiche censite | ~241 (con overlap) / 177 nette synthesis | 7 zone FASE 1 |
| OPERATIVO | ~65% (116/177) | phase1-synthesis |
| ROTTO | 15 | phase1-synthesis |
| MAI_USATO | 8 | phase1-synthesis |
| DUPLICATO | 7 (= 5-6 relazioni) | phase1-synthesis |
| INCERTO | 31 (WR3 intero) | phase1-synthesis |
| Agenti Claude `~/.claude/agents/` | 34 | ls reale |
| LaunchAgent | ~169 | ls reale |
| chain MCP | 8-17 | chains.py |
| Servizi backend | 75 | ls reale |

**Costo mantenere 241 entità**: ~2 FTE = $100-140k/anno (DeepSeek). Consolidare a 15-20
macro-agenti → 0.5 FTE = $30-50k/anno → **risparmio $70k/anno** (payback 12-18 mesi).

---

## 2. MAPPA MACRO-GRUPPI (chi ha un comandante, chi è sparso)

### Con comandante (governati)
| Macro-gruppo | Entità | Comandante | Stato reale |
|---|---|---|---|
| **WR2 carousel** | 8 agent + 21 launchagent + servizi | `wr2-design-architect` + `wr2.supervisor` (pid 17298) | ✅ produzione vera (33 output, 15 log) |
| **WR3 video** | 13 agent + 4 launchagent | `wr3-design-architect` + `wr3.supervisor` ROTTO (binary missing) | ❌ INCERTO 100%, mai a regime |
| **Organism core** | 9 launchagent + supervisor | `organism.supervisor` (pid 1016) | ⚠️ SHADOW: 92k eventi consumati, 0 attuati |
| **Channels** | 10 (4 live + quarantena) | `ChannelRouter`→`ConversationEngine`→`AgenticRAGOrchestrator` | ✅ 3-layer pulito |
| **Cell** | 2 launchagent + PulseEngine | `com.cell.organism` (pid 9380) | ✅ vivo (Pulse #2947), observatory ROTTO |

### Sparsi (NESSUN comandante — zone non governate)
| Macro-gruppo | Entità | Problema |
|---|---|---|
| **mata-garuda OSINT** | 40+ harvester | KG MORTO (2 entità/0 relazioni), no orchestratore |
| **chain MCP** | 8 | code-complete ma 0 auto-invocate |
| **intel-lake / sentinel / monitors / wa-mirror** | ~19 | peer scattered, nessun supervisore |
| **3 council multi-LLM** | consiglio + oracle + tone_council | sovrapposti, no primitiva comune |

---

## 3. MATRICE: agenti × stato (i problematici, con evidenza)

### ROTTI (15) — i principali
| Entità | Evidenza | Vale riparare? |
|---|---|---|
| `wr3.supervisor` + WR3 13 agenti | binary missing, .openclaw/bin/wr3 cancellato, no log | ⚠️ valutare (over-eng?) |
| `agent-library-evolver` (Voyager) | generation=0 MAI evoluto, DEEPSEEK_KEY mancante, 3 run falliti | ✅ SÌ (alto ROI) |
| `wr3.reflexion` | OS_REASON_CODESIGNING, interprete .venv non parte | ✅ SÌ (parte del loop) |
| `cell-observatory` repo collector | crash-loop su MiniMax API key mancante | ⚠️ HOME-fork fa già il lavoro |
| `federation-alert-dispatcher` | ROTTO | ⚠️ |
| `organism control-panel` | ROTTO | ⚠️ |
| `bridge.nerve` (mata-garuda→business) | ROTTO (handoff OSINT spento) | ✅ SÌ |
| Twitter channel | CRC broken, .disabled-2026-04-30 | ❌ NO (quarantena) |

### MAI_USATO (8)
- `competitor-monitor`, `yield-optimizer` (agenti esistono, MAI invocati)
- 2/3 `codex-autonomy` launchagent (NOT LOADED)
- chain MCP (8 code-complete, 0 auto-invocate)
- `autonomous_lab/planner.py` (orfano, 0 import)
- 2 canali phantom (gchat/slack: zero file, solo tassonomia)

### DUPLICATI (5-6 relazioni)
| # | Coppia | Verdetto |
|---|---|---|
| D1 | `wr2-brief-interpreter` ≈ `wr3-brief-interpreter` | merge → `BriefGrounder` |
| D2 | `wr2-external-bench` ≈ `wr3-editorial-bench` | merge → `ExternalBench` |
| D3 | `canva_renderer` v1 vs v2 | elimina v1 (solo v2 importato) |
| D4 | `wa-mirror` vs `wa-mirror-launcher` | elimina label morta (launcher vivo) |
| D5 | namespace `com.balizero.*` vs `com.nuzantara.*` | reconciler job |
| D6 | `matagaruda.sentinel.hourly` vs aggregate | elimina hourly (exit-1 noise) |

---

## 4. SOTA 2026 — i pattern chiave (FASE 2, fonti primarie)

| Tema | SOTA 2026 (fonte) | Gap Nuzantara |
|---|---|---|
| **Consolidamento** | "agenti solo dove servono", supervisor+handoff con contratti (Anthropic, LangChain, OpenAI Agents SDK, A2A) | 5 duplicati, 3 council, no agent-registry |
| **Document-AI** | OCR layout-aware + schema+confidence+human-review (Docling, Document AI, Textract, Mistral) | pezzi sparsi (crm_guardian/ocr, pdf_vision), no catena end-to-end |
| **Browser-agent** | sandbox + Playwright MCP + checkpoint + HITL, benchmark WebArena/OSWorld | portali gov manuali, organism shadow |
| **Voice/WhatsApp** | WhatsApp Flows + voice-note→task + copilot-non-autoreply (Meta, Twilio, OpenAI Realtime) | WA vivo ma "cervello non collegato all'azione" |
| **Predictive** | regole+ML calibrato (survival/GBM), LLM solo per spiegazione (scikit-survival, lifelines) | competitor/yield mai usati, no deadline-queue |
| **Evals/Obs** | trajectory eval + OTEL GenAI + cost-gate (LangSmith, Phoenix, tau-bench) | loop self-improvement rotto, no health-contract |
| **Self-improvement** | Voyager/ADAS che merge solo se benchmark migliora | evolver gen=0, loop aperto a ogni giunto |

---

## 5. 🗑️ LISTA 1 — ELIMINARE (duplicati / rotti non-vale)

| # | Cosa | Perché | Rischio rimozione | Priorità |
|---|---|---|---|---|
| E1 | `canva_renderer` v1 legacy | solo v2 importato in prod | basso (grep 0 importer attivi) | ALTA |
| E2 | `com.balizero.wa-mirror` label | superseded da wa-mirror-launcher | basso (non bootstrapped) | ALTA |
| E3 | `com.matagaruda.sentinel.hourly` | superseded, exit-1 noise permanente | basso | ALTA |
| E4 | Canali phantom gchat/slack | zero file, solo tassonomia | nullo | MEDIA |
| E5 | `autonomous_lab/planner.py` | orfano, 0 import | basso | MEDIA |
| E6 | 2/3 `codex-autonomy` launchagent NOT LOADED | mai girati | basso | BASSA |
| E7 | Twitter channel | CRC broken, già quarantena | nullo (già off) | BASSA |
| E8 | WR3 video 13 agenti — **DECISIONE** | 100% INCERTO, mai a regime, supervisor rotto | ALTO (è lavoro fatto) | ⚠️ Antonello decide |

**E8 è la decisione strategica**: WR3 è 13 agenti mai andati a regime. O lo si ripara
(effort alto) o lo si archivia. DeepSeek: video-agent ROI incerto vs document-AI certo.

---

## 6. 👑 LISTA 2 — MACRO-AGENTI da creare (governare le zone sparse)

| # | Macro-agente | Governa | Perché | Priorità |
|---|---|---|---|---|
| M1 | **Agent Contract Registry** | TUTTI (241) | registro operativo: agent_id, owner, schema, health, deprecated_by. Reconciler che fallisce su duplicati non-governati, launchagent senza contract, frontend senza backend | 🔥 FONDAZIONALE (Codex priorità #1) |
| M2 | **CouncilService** | consiglio + oracle + tone_council | 3 council sovrapposti → 1 primitiva | ALTA |
| M3 | **mata-garuda OSINT Commander** | 40+ harvester scattered | zona OSINT senza comandante, KG morto | MEDIA |
| M4 | **ChatStreamContract** | FAB + portal + KBLI + web-chat | 4 chat frontend frammentate → 1 contratto | ALTA |
| M5 | **LaunchNamespaceReconciler** | com.balizero.* / com.nuzantara.* | orphan dup, no reconciliation | MEDIA |

**M1 è il keystone**: SOTA dice "senza contratti e trace ogni nuovo agente aumenta entropia".
Va creato PRIMA di nuovi agenti.

---

## 7. 🔧 LISTA 3 — RIPARARE (rotti che valgono)

| # | Cosa | Fix | Effort | ROI |
|---|---|---|---|---|
| R1 | **Self-improvement loop** (Voyager evolver + 2 reflexion + checkpointer) | DEEPSEEK_KEY in evolver env, fix interprete WR3 codesigning, PostgresSaver in federation_orchestrator, alimentare reflexion dalla pipeline | 400-600h ($40-80k) | **250% / payback <12 mesi** (DeepSeek: $70k/anno) |
| R2 | **organism supervisor: shadow→attua** | abilitare LLM-tiers (W1), observe→decide→**act** con approval-gate Law-5 | medio | alto (92k eventi sprecati) |
| R3 | **mata-garuda KG morto** | re-popolare entity-resolution (2 entità→vivo), GraphRAG | medio | medio (intel inutilizzabile ora) |
| R4 | **bridge.nerve** (OSINT→business) | riparare handoff | basso | medio |
| R5 | **broker worktree reaper** (W62) | LaunchAgent --cleanup daily WIP-safe | basso | basso (igiene) |

**R1 è il più strategico**: l'architettura di auto-miglioramento è sofisticata ma NESSUN
loop si chiude. Riparare i giunti sblocca l'evoluzione autonoma del sistema.

---

## 8. ⚡ LISTA 4 — POTENZIARE (operativi che possono di più)

| # | Cosa | Potenziamento | ROI |
|---|---|---|---|
| P1 | **WR2 carousel** (già produzione) | alimentare reflexion (ora carousel_runs=0) → migliora da solo | medio |
| P2 | **wa_copilot/extraction** (Ollama locale) | aggiungere schema + eval + approval gate → diventa WA Operator Copilot (vedi G1) | alto |
| P3 | **CRM Guardian** (rule-engine) | escalation-a-LLM sulle decisioni write | medio |
| P4 | **Channels AgenticRAGOrchestrator** | aggiungere trajectory-eval gate (no regressioni silenziose) | medio |
| P5 | **chain MCP** (8 code-complete) | autonomous scheduler che le invoca (ora 0 auto-invocate) | medio |

---

## 9. 🚀 LISTA 5 — CREARE GAME-CHANGER (nuovi, alto impatto)

Rankati per ROI (DeepSeek + Codex convergono):

| # | Game-changer | Cosa fa | ROI 3-anni | Effort | Aggancio |
|---|---|---|---|---|---|
| **G1** | **WA Operator Copilot + Flow Pack** | thread-summary + reply-draft (no auto-send) + lead-qualifier + voice-note→CRM + WhatsApp Flows | **alto** (canale #1) | 3-5gg MVP→3-4set | wa-mirror vivo ✅ |
| **G2** | **Akta/OCR Triage Agent** | classifica+estrae akta/KITAS/NIB/NPWP con confidence→staging→approval | **4-6x** (DeepSeek: $200k/anno) | 1set MVP→3-5set | crm_guardian/ocr esiste |
| **G3** | **Revenue & Deadline Sentinel** | regole-deadline + ML-calibrato churn/upsell/renewal → queue giornaliera (no auto-contact) | **5-7x** (DeepSeek: $250k/anno) | 1set→4-6set | event-exhaust c'è |
| **G4** | **Agent Observatory + Eval Gate** | trace+health+trajectory-eval per tutte le entità; "alive-but-idle" detection | **fondazionale** | 3-5gg→1mese | nessuno (nuovo) |
| **G5** | **Portal Copilot** (cliente) | copilot nel portale (il team ce l'ha, cliente no) — read-only prima | **3-5x** (DeepSeek: $350k/anno) ma change-mgmt | MVP read-only | portale esiste, FAB morto |
| **G6** | **Resuscitare "Ask Zantara" FAB** | il widget pubblico è MORTO (.backup), funnel lead spento | **1.5-2x** (lead) | basso (widget esiste in backup) | recupero da backup |

---

## 10. SEQUENZA RACCOMANDATA (convergenza 3-LLM)

**Codex priorità + DeepSeek ROI + il mio giudizio:**

1. **PRIMA: G4 Agent Observatory + M1 Contract Registry** — fondazionali. "Senza trace e
   contratti ogni nuovo agente aumenta entropia". Misurano cosa vive, cosa è duplicato,
   cosa è alive-but-idle.
2. **POI: eliminazioni E1-E7** (basso rischio, dopo che il registry le rende sicure).
3. **POI: G1 WA-Copilot + G2 Akta-OCR** — i 2 game-changer più vicini al fatturato,
   agganciati a canali vivi. Document-AI ha il ROI più certo (DeepSeek: dipendenza minima
   dal comportamento cliente).
4. **POI: G3 Predictive Sentinel** (regole+ML, no LLM-prediction).
5. **POI: R1 self-improvement loop** — sblocca l'auto-evoluzione ($70k/anno).
6. **PARALLELO: M2-M5 macro-agenti + R2-R4 riparazioni.**
7. **DECISIONE Antonello: E8 WR3** (riparare vs archiviare 13 agenti).

**Economia totale (DeepSeek):**
- Consolidamento → -$70k/anno costi
- G2+G3 → +$450k/anno (document-AI + predictive)
- R1 loop → +$70k/anno
- G5 portale → +$350k/anno (con change-mgmt)
- Multi-agente È sostenibile: il token extra è irrisorio vs valore-errore-evitato.

---

## 11. NEEDS-ANTONELLO (decisioni che spettano a te)

1. **E8**: WR3 video — riparare (effort alto) o archiviare (13 agenti)?
2. **R1**: investire $40-80k per riparare il self-improvement loop (ROI 250%)?
3. **Priorità game-changer**: G1/G2 (vicini al fatturato) o G4 (fondazionale prima)?
4. **G5 Portal Copilot**: alto ROI ma richiede change-management cliente — quando?
