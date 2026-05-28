# Sintesi convergente — 20 Use Cases per corpus WhatsApp locale

## 1) Consenso alto (3+ panelisti)

| Normalized name                            | Claude                                      | Gemini                                               | DeepSeek                              | Codex                                                     |
| ------------------------------------------ | ------------------------------------------- | ---------------------------------------------------- | ------------------------------------- | --------------------------------------------------------- |
| **CRM enrichment & client timeline**       | #1 CRM enrichment cliente→pratiche→timeline | #2 Lead & Intent Extraction, #6 Entity/KG Enrichment | #17 CRM Metadata Tagging              | #4 CRM Person Matching, #5 Client Timeline Reconstruction |
| **Semantic search locale sui chat**        | (implicito in #3)                           | #1 Local Semantic Chat Search                        | #10 Local Semantic Search             | #20 Local RAG Assistant                                   |
| **FAQ / Knowledge base extraction**        | #3 FAQ→KBLI/visa/tax KB                     | #5 FAQ & Auto-Reply, #4 SOP Generation               | #3 FAQ Auto-Extraction                | #13 FAQ Miner                                             |
| **Document submission tracking**           | #7 Document collection audit                | #9 Document Submission Tracking                      | (parte di #17)                        | #7 Document Request Extractor                             |
| **Sentiment / churn early-warning**        | #8 Sentiment trajectory cliente             | #14 Sentiment-Based Churn Prevention                 | #2 Sentiment & Satisfaction Dashboard | #11 Complaint & Escalation Mining                         |
| **Team response-time / agent performance** | #6 Response-time SLA dashboard              | #11 Agent Performance & Tone                         | #5 Agent Response Time Analytics      | (parte di #15)                                            |
| **Pricing/quote consistency audit**        | #2 Pricing reality-check vs catalog         | #10 Payment & Invoice Reminders                      | (parte di #12 Compliance)             | #8 Pricing & Quote Consistency                            |
| **Per-client conversation summary**        | (parte di #1)                               | #3 Automated Chat Summarization                      | #6 Per-Client Timeline & Summary      | #10 Consultant Handoff Digest                             |
| **Lead opportunity / dormant detector**    | #4 Lead-quality scoring                     | #2 Lead Extraction                                   | #4 Lead Opportunity Detector          | #12 Referral & Lead Source Detector                       |
| **Personal memory vault (own chats)**      | #11 Personal timeline reconstruction        | #19 Personal Milestone Vault                         | #16 Personal Memory Vault             | #16 Personal Memory Capsule                               |
| **Multi-language detection / glossary**    | #10 Multi-lingua, #14 Glossary EN↔ID↔IT     | #15 Multi-lingual Glossary                           | #9 Language ID & Translation          | #14 Language & Tone Playbook                              |

## 2) Consenso medio (2 panelisti)

| Normalized name                                    | Panelisti                                                                                        |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **Compliance/RBAC scope audit team**               | Claude #5, DeepSeek #12 (Rule Violation Scanner)                                                 |
| **Off-listino / fraud forensics**                  | Claude #20, DeepSeek #12 (overlap parziale)                                                      |
| **Topic trend / service-type classification**      | DeepSeek #13 Topic Trend Forecaster, Codex #9 Service-Type Classifier                            |
| **Customer segmentation via clustering**           | DeepSeek #14, Claude #4 (parziale)                                                               |
| **Open loop / commitment tracker**                 | DeepSeek (parte di #7 CTA Flagging), Codex #6 Open Loop Detector + #18 Task Tracker (Gemini #18) |
| **Visa expiry & follow-up triggers**               | Gemini #12, Claude (parte di #1)                                                                 |
| **Referral chain / relationship graph**            | Claude #17, Codex #17 Relationship Graph                                                         |
| **Edge-case visa scenario library / case studies** | Claude #18, Codex #18 Case Study Generator                                                       |
| **Knowledge transfer "what Surya knows"**          | Claude #9, Codex #18 (overlap concettuale)                                                       |
| **Appointment/meeting extraction**                 | Gemini #16, (Codex #6 parziale)                                                                  |
| **Contact dedup / resolution**                     | Gemini #13, Codex #4                                                                             |

## 3) Hidden gems (1 panelista, alto valore)

| Use case                                                      | Panelista            | Perché vale                                                                                               |
| ------------------------------------------------------------- | -------------------- | --------------------------------------------------------------------------------------------------------- |
| **Local Corpus Registry + reconciliation 105,532 vs 105,530** | Codex #1+#2          | Foundational. Senza counts trusted ogni dashboard downstream è inquinato. Prerequisito di tutto il resto. |
| **PII Sanitization Pipeline + Export Gate**                   | Gemini #7, Codex #19 | Sblocca uso cloud aggregati senza violare Law 2. Defense-in-depth.                                        |
| **Business/Personal Conversation Classifier**                 | DeepSeek #1          | Gate primario. Tutti i pipeline downstream dipendono da questa separazione. Codex #15 conferma necessità. |
| **Bali Zero Origin Story Timeline (2022-2023)**               | Gemini #17           | Valore storico/biografico aziendale unico. Documenta decisioni fondative.                                 |
| **WhatsApp→CRM auto-link forward-looking (wa-mirror live)**   | Claude #19           | Estende il cutover 2026-05-24 esistente. Ogni nuovo msg = interaction CRM zero-effort.                    |
| **Crisis pattern detection retroattivo**                      | Claude #13           | Pattern recognition → trigger live su nuovi clienti. Predictive maintenance commerciale.                  |
| **Competitor mention extraction**                             | Claude #16           | Market intelligence passiva, gratis. Capisci dove perdi vs Smart Bali/ILA/etc.                            |
| **Agent-Assist Reply Draft Generator (RAG inline)**           | DeepSeek #11         | Tool day-to-day operatori. Riduce tempo risposta + consistency.                                           |
| **MCP Tool for Contextual Chat Lookup**                       | DeepSeek #18         | Integration nativa con architettura MCP esistente Bali Zero.                                              |
| **Voice-of-Customer Quarterly Report**                        | DeepSeek #15         | Output management-grade sanitized. Decision support owner-level.                                          |

## 4) Categorie emergenti

Aggregando i 78 use case proposti emergono **8 categorie operative**:

1. **Foundation/Hygiene** (Codex #1-2, DeepSeek #1, Gemini #7) — registry, reconciliation, PII gate, classifier business/personal. Prerequisito.
2. **CRM augmentation** (15+ proposte) — il cluster più denso. Conferma valore primario.
3. **Operations live** (response-time, SLA, open loops, document tracking) — observability team Bali Zero.
4. **Sales intelligence** (lead scoring, pricing audit, competitor, referral) — pipeline commerciale data-driven.
5. **Knowledge management** (FAQ, SOP, case studies, glossary, tone) — knowledge transfer + RAG augmentation.
6. **Compliance/Risk** (RBAC scope, fraud forensics, sentiment churn, complaint) — controllo interno + early-warning.
7. **Personal/biographical** (memory vault, relationship graph, origin story) — valore privato non-commercial.
8. **Predictive/forward-looking** (crisis pattern, churn prevention, dormant alert, agent-assist) — da retroattivo a live.

## 5) Top-10 ranked

Criteri scoring (1-5): **BV** business value, **PV** personal/historical value, **TF** local technical feasibility (Ollama + Postgres + bge-m3, Pro 48GB), **L2** Symbiosis Law 2 compliance (locale, no cloud raw).

| Rank   | Use case                                                        | BV  | PV  | TF  | L2  | Tot | Note                                                                                                                               |
| ------ | --------------------------------------------------------------- | --- | --- | --- | --- | --- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **1**  | **Local Corpus Registry + Reconciliation 105,532 vs 105,530**   | 4   | 3   | 5   | 5   | 17  | Foundational. 1-2gg Python+Postgres, zero LLM. Sblocca tutto. (Codex #1-2)                                                         |
| **2**  | **Business/Personal Classifier + PII Sanitization Gate**        | 5   | 5   | 4   | 5   | 19  | Gate primario obbligatorio. Determina cosa entra in CRM vs cosa resta personal vault. (DeepSeek #1 + Gemini #7 + Codex #15+#19)    |
| **3**  | **Local Semantic Search su business chats (pgvector + bge-m3)** | 5   | 3   | 5   | 5   | 18  | Quick win 2-3gg. ROI immediato per Antonello/admin. (Gemini #1 + DeepSeek #10 + Codex #20 parziale)                                |
| **4**  | **CRM enrichment: client→timeline→interactions**                | 5   | 3   | 4   | 5   | 17  | 4 panelisti convergenti. Sblocca onboarding nuovi team, riduce key-person dependency Surya/Adit.                                   |
| **5**  | **Pricing/Quote Consistency Audit vs PricingTool**              | 5   | 2   | 5   | 5   | 17  | Risponde direttamente al case Surya/BTV/Receh OPEN. 2-3gg Python regex + qwen3.5 disambiguation. (Claude #2 + Codex #8)            |
| **6**  | **FAQ Extraction → NB-2/NB-3 KB augmentation**                  | 4   | 2   | 4   | 5   | 15  | Migliora RAG retrieval kita.balizero.com con query reali. 4-6gg con clustering bge-m3. (4 panelisti)                               |
| **7**  | **Sentiment/Churn Early-Warning + Complaint Mining**            | 4   | 2   | 4   | 5   | 15  | 4 panelisti. Recupero retention prima della perdita. qwen3.5 + Telegram alert.                                                     |
| **8**  | **Agent Performance & Response-Time Dashboard**                 | 4   | 2   | 5   | 5   | 16  | Workload balancing oggettivo e SLA review, ma solo con privacy/labour guardrails. 3gg Python+Postgres+Next.js admin. (4 panelisti) |
| **9**  | **Open Loop Detector + Document Request Tracker**               | 5   | 3   | 4   | 5   | 17  | Immediatamente actionable. Detect "cliente dice ho mandato ma non c'è" + commitment unresolved. (Codex #6+#7 + Gemini #9+#18)      |
| **10** | **Personal Memory Vault (own chats, encrypted local-only)**     | 1   | 5   | 4   | 5   | 15  | Valore biografico puro. Mai cloud. SQLite encrypted + qwen3.5 summaries. Separato e isolato dal CRM business. (4 panelisti)        |

## Note di raccomandazione

**Ordine implementativo suggerito** (deriva dal ranking ma rispetta dipendenze):

- **Settimana 1**: #1 Registry + #2 Classifier+PII Gate (prerequisiti, no LLM)
- **Settimana 2**: #3 Semantic Search + #5 Pricing Audit (quick wins, BV alto, case Surya)
- **Settimana 3-4**: #4 CRM enrichment + #8 Agent Dashboard (operations core)
- **Mese 2**: #6 FAQ KB + #7 Churn + #9 Open Loop (knowledge + risk)
- **Parallelo isolato**: #10 Personal Vault (encrypted, branch separato, mai mescolato con business)

**Pattern comune confermato dai 4 panelisti**: stack `bge-m3` (embed) + `qwen3.5:9b` (extraction/classification) + Postgres `nuzantara_dev` + pgvector. Niente cloud raw content. Output cloud-shareable solo aggregati/metadata sanitized.

**Convergenza forte sul caso Surya/BTV**: 3 panelisti (Claude, DeepSeek, Codex) propongono indipendentemente strumenti che indirizzano il OPEN CASE 2026-05-14 — pricing audit, compliance scanner, fraud forensics. Segnale che il corpus contiene evidence già estraibile.
