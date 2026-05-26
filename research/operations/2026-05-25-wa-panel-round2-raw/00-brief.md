# Round 2: deep-dive su 4 nuove scoperte empiriche

## Round 1 sintesi (3 panelisti 3/3 convergenti su)
- GraphRAG > flat RAG; team-copilot first; identity 2%→60% blocking; PII scrub locale; no sentiment vanity; Ollama batch zero-cost.

## Nuove scoperte empiriche (verificate query postgres oggi 2026-05-25)

1. **KG regulatorio esistente è MASSIVO ma sganciato dal CRM**:
   - `kg_nodes` postgres = **114.176 entities** (dokumen 42k, kbli 13k, pasal 10k, izin_usaha 9k, biaya 9k, undang_undang 3.7k, jangka_waktu 3.7k, peraturan_pemerintah 2.8k, perizinan 2.8k, ppn, vitas, kitas 403, pt_pma 1.4k)
   - `kg_edges` postgres = **251.872 relations** (REQUIRES 66k, APPLIES_TO 39k, REFERENCES 32k, PART_OF 31k, HAS_DURATION 10k, PENALTY_FOR 8k, REQUIRED_FOR 8k, ISSUED_BY 6k, HAS_FEE 4k)
   - Popolato da NER worker qwen3.5 su corpus regulatorio (UU, PMK, Permenkumham, Perpres) via 60 NB-IO sources
   - CRM-specific subgraph `crm_kg_nodes/edges` = **solo 852 nodes / 711 edges** (crm_document 418, crm_client 325, crm_person 109, relations: BELONGS_TO 418, CONTEMPORANEOUS 176, DESCRIBES 117)

2. **Practices coverage gap MORTALE**: 425 pratiche totali, solo **3 con WA msgs collegati (0.7%)**. Identity match 2% era già noto. Ma practice_id link è quasi inesistente.

3. **kg_entity_mentions** = **76.218 righe** schema `(mention_id, entity_id, collection_name, point_id, mention_text, confidence, match_type, created_at)`. Infrastruttura esiste per linkare entity_id → mention_text in qualunque collection. **Non ancora usato per WA messages**.

4. **Language detection broken**: 24.795/26.743 msg classificati "unknown_other" (regex naive). Russian cyrillic catturato 13 (sample size). Lo strumento NON è affidabile per routing language-aware.

## Nuove domande per panelist (focus deep-dive)

### A. KG regulatorio ↔ WA copilot bridge
Hai 114k nodes di **regulatory ground truth** (KBLI codes, visa types, document requirements, durations, fees, penalties). Hai 30k WA msg dove il team risolve casi cliente. Come **collegare** i due?

Esempi di query che dovrebbero essere triviali:
- "Cliente chiede D12 + business plan italiano: storicamente quante volte hai usato apostille? Quanto costa? Quanti giorni?"
- "KBLI 47299 + cliente straniero: ci sono pattern bloccanti?"
- "Ultimi 3 mesi: clienti con KITAS E33G hanno avuto domande ripetute su 'reentry permit'? Quale risposta funziona?"

Proposal richiesto: design di `whatsapp_extractions` → entity_link → kg_nodes via `kg_entity_mentions`. Quali fact_type estrarre dal msg WA per match con KG esistente (kbli/visa/dokumen/biaya/jangka_waktu)?

### B. Pattern riusabilità `kg_entity_mentions`
Lo schema `(entity_id, collection_name, point_id, mention_text, confidence, match_type)` esiste già con 76k row. È stato usato per RAG su corpus regulatorio (collection_name = NB UUID o similar). Per WA messages quale sarebbe il `collection_name`? `wa_messages`? Quale `point_id` (msg_id? thread_id?). `match_type` enum esistente quali valori contiene? Riuso vs duplicazione.

### C. Practice linking strategy
425 practices, 3 collegate via `practice_id`. Come popolare i restanti 422 da WA chat (ognuna è in folder Drive per cliente, chat ha sender + filename allegati). Algoritmo concreto:
1. Per ogni chat, extract candidate practice_id da: filename pattern (es. "D12 Catia" → search practices WHERE service_type='D12' AND client.name ILIKE '%Catia%')
2. Fuzzy match attachment names vs practices.documents
3. Temporal correlation: msg date range ⊂ practice date range
Confidence + human review?

### D. Action queue: schema concreto + UI minimo
Codex round 1 ha proposto `action_queue (client | practice | reason | recommended_action | due | evidence | owner | status)`. Concretizza:
- Trigger rules deterministic per row creation (es. "silence>72h AND last_team_promise_unresolved → row")
- Dedup logic (stessa action su stesso cliente, non duplicare)
- Snooze/dismiss UX
- Quale framework UI consigliato per 9-10 people team (Streamlit Pro+Mini? Next.js app esistente apps/wa-dashboard? terminal TUI?)
- Notification: Telegram personal? Email? In-app?

### E. Empirical 0-30gg validation strategy
Come **misuriamo** che il sistema funziona dopo 30 giorni? Quali metriche oggettive:
- Identity match % (target 60% concordato)
- Action_queue items resolved/dismissed ratio
- Time-to-first-response su nuovo msg
- # follow-up "salvati" dall'AI (lead riattivati)
- Team satisfaction (survey 1-10)

Quali sono baseline + target realistici per Bali Zero scale (9-10 team, ~150 msg/day live + 30k storical)?

---

Risposta concreta, no ripeti round 1, focus solo su queste 5 nuove questioni. 600-1000 parole. Cita schema SQL concreti se proponi tabelle.
