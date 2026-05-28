---
date: 2026-05-26
domain: personal
client_case: corpus-mining-whatsapp-105k
sources:
  - 2026-05-26-whatsapp-corpus-105k-brainstorm/tier1_claude_brainstorm.md
  - 2026-05-26-whatsapp-corpus-105k-brainstorm/tier1_gemini_brainstorm.md
  - 2026-05-26-whatsapp-corpus-105k-brainstorm/tier1_deepseek_brainstorm.md
  - 2026-05-26-whatsapp-corpus-105k-brainstorm/tier1_codex_brainstorm.md
  - 2026-05-26-whatsapp-corpus-105k-brainstorm/tier2_synthesis.md
  - 2026-05-26-whatsapp-corpus-105k-brainstorm/tier3_redteam.md
  - 2026-05-26-whatsapp-corpus-105k-brainstorm/tier4_roadmap.md
---

# WhatsApp Corpus 105k Brainstorm

## 1. Executive Summary

1. Il corpus e' utile solo se prima viene costruito un **trust layer locale**: registry deterministico, conteggi riconciliati, hash, formato parser, warning, zero raw text in output.
2. La verifica Bash del 2026-05-26 trova **698 file `.txt` chat** e **105.532 message-start records**; il target utente e' **105.530**, quindi ci sono due record da riconciliare prima di qualsiasi dashboard.
3. Il consenso multi-LLM converge su tre cluster: **CRM/client timeline**, **ricerca semantica locale**, **FAQ/knowledge extraction**.
4. Il red-team sposta la priorita': prima di CRM/RAG serve un **business/personale/team classifier + PII gate** con policy di esclusione chiara.
5. Top business quick win: **local semantic search su chat business approvate**, con `bge-m3` locale e `qwen3.5:9b` solo su Pro.
6. Top operational quick win: **open-loop + document request tracker**, per trasformare chat approvate in prossime azioni verificabili.
7. Top risk/forensic pilot: **pricing/quote consistency audit vs PricingTool**, ma solo dopo il gate privacy e senza uso disciplinare automatico.
8. Top personal use case: **Personal Memory Vault cifrato local-only**, isolato dal CRM e senza commistione con dati team/clienti.
9. Killer-app idea: **WhatsApp Mission Control locale**: dato un cliente approvato, mostra "chi e', cosa manca, cosa e' stato promesso, prossimo step, rischio, pricing anomaly", con evidence pointers solo interni.
10. Next action consigliata: partire dal **Corpus Registry + Reconciliation**, perche' non richiede LLM, non richiede cloud, non deve esporre contenuto chat e sblocca tutti gli altri use case.

## 2. Tier 1 Panel Raw

Quattro panelisti sono stati eseguiti con lo stesso brief sanitizzato: nessun contenuto raw delle chat, solo conteggi aggregati e vincoli di sovranita' locale.

| Panelist         | File raw                                                                                                | Note operative                                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Claude Opus      | [tier1_claude_brainstorm.md](2026-05-26-whatsapp-corpus-105k-brainstorm/tier1_claude_brainstorm.md)     | Business/strategy synthesis, ha spinto CRM, pricing audit, knowledge mining, response-time e memoria personale. |
| Gemini via `agy` | [tier1_gemini_brainstorm.md](2026-05-26-whatsapp-corpus-105k-brainstorm/tier1_gemini_brainstorm.md)     | Buona copertura operativa: search, lead extraction, summaries, SOP, FAQ, document tracking.                     |
| DeepSeek V4 Pro  | [tier1_deepseek_brainstorm.md](2026-05-26-whatsapp-corpus-105k-brainstorm/tier1_deepseek_brainstorm.md) | Ha enfatizzato classifier, dashboard sentiment, lead detector, response-time e compliance scanner.              |
| Codex GPT-5.5    | [tier1_codex_brainstorm.md](2026-05-26-whatsapp-corpus-105k-brainstorm/tier1_codex_brainstorm.md)       | Ha evidenziato il prerequisito piu' concreto: registry + riconciliazione del mismatch `105.532` vs `105.530`.   |

## 3. Tier 2 Synthesis

Sintesi completa: [tier2_synthesis.md](2026-05-26-whatsapp-corpus-105k-brainstorm/tier2_synthesis.md).

### Convergenza Alta

| Cluster normalizzato              | Panelisti convergenti | Interpretazione pragmatica                                                                                                     |
| --------------------------------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| CRM enrichment + client timeline  | 4/4                   | Il valore business principale e' convertire chat sparse in memoria cliente/persona, rispettando il modello CRM person-centric. |
| Local semantic search / RAG       | 3-4/4                 | Query locale su chat approvate: high ROI, ma solo dopo privacy gate.                                                           |
| FAQ / knowledge base extraction   | 4/4                   | Le domande reali dei clienti possono migliorare KBLI/visa/tax/property knowledge, con revisione umana.                         |
| Document tracking / open loops    | 3-4/4                 | Trasforma "abbiamo chiesto/passaporto/invoice/ci penso" in coda operativa.                                                     |
| Sentiment / complaint / churn     | 4/4                   | Potente ma privacy-sensitive: va tenuto informativo, non decisionale.                                                          |
| Response-time / agent performance | 3-4/4                 | Utile per workload, ma rischioso come monitoraggio dipendenti.                                                                 |
| Pricing / quote audit             | 3/4                   | Use case ad alto valore per coerenza prezzi e forensics, con policy no-discipline automation.                                  |
| Personal memory vault             | 4/4                   | Valore storico privato, ma va isolato completamente dal CRM.                                                                   |

### Divergenza / Hidden Gems

| Hidden gem                        | Perche' conta                                                                                | Stato                             |
| --------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------- |
| Corpus Registry + Reconciliation  | Senza conteggi trusted, ogni use case successivo produce numeri non difendibili.             | Da fare subito.                   |
| PII Sanitization Export Gate      | Permette brief aggregati cloud-safe senza raw chat; blocca nomi, telefoni, path e citazioni. | Prerequisito.                     |
| Business/Personal/Team Classifier | Separa privacy personale, patto fiduciario team e business CRM.                              | Prerequisito.                     |
| WhatsApp-to-CRM live forward path | Usa il cutover mirror come flusso nuovo, non solo archivio storico.                          | Dopo registry/gate.               |
| Voice-of-Customer report          | Aggregato trimestrale interno per decisioni owner-level.                                     | Solo su business approved subset. |
| Origin story timeline             | Valore storico Bali Zero, non commerciale.                                                   | Isolare da dati clienti/team.     |

## 4. Tier 3 Red-Team Blockers

Red-team completo: [tier3_redteam.md](2026-05-26-whatsapp-corpus-105k-brainstorm/tier3_redteam.md). Il primo pass DeepSeek era incompleto per limite di output ed e' stato rimosso nella pulizia finale; il file mantenuto e usato nel report e' il secondo pass compatto completo.

Fonti legali usate per il red-team:

- Indonesia official legal portal: [UU No. 27 Tahun 2022 Tentang Pelindungan Data Pribadi](https://www.peraturan.go.id/id/uu-no-27-tahun-2022), status `Berlaku`, established/promulgated 17 October 2022.
- EDPB GDPR SME guide: [Process personal data lawfully](https://www.edpb.europa.eu/sme-data-protection-guide/process-personal-data-lawfully_en), per lawful basis, consenso, minimizzazione, interesse legittimo e dati sensibili.

| Use case                     | Blocker principale                                                    | Gate pratico                                                                                     |
| ---------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Registry + reconciliation    | Anche metadata/timestamp/chat membership sono dati personali.         | Output senza raw text; retention minima; registry locale; scopo documentato.                     |
| Business/personal classifier | Il classifier puo' leggere dati privati per decidere se sono privati. | Rule-first su metadata; contenuto solo per `unknown_review` e solo locale; audit falsi positivi. |
| Semantic search              | Embedding puo' codificare PII e recuperare chat non autorizzate.      | PII redaction pre-embedding, RBAC, approved business subset only.                                |
| CRM enrichment               | Profilazione cliente e rischio entity resolution errata.              | Consenso/base legittima, revisione umana, diritto di rettifica/esclusione.                       |
| Pricing audit                | Puo' diventare monitoraggio disciplinare del team.                    | Shadow mode, anomaly report non probatorio, policy trasparente.                                  |
| FAQ extraction               | Rischio di pubblicare PII o advice obsoleto.                          | Anonimizzazione + doppia revisione esperta prima di KB.                                          |
| Sentiment/churn              | Profilazione emotiva e falsi positivi.                                | Solo trend informativi, niente decisioni automatiche, opt-out dove applicabile.                  |
| Agent dashboard              | Sorveglianza dipendenti ad alta granularita'.                         | Aggregato/team-level, trasparenza, contestabilita', no sanzioni automatiche.                     |
| Open loops/document tracker  | Falsi loop e contenuti personali intercettati.                        | Solo chat business approvate, confidence score, manual close/reject.                             |
| Personal vault               | Dati di terzi in archivio privato.                                    | Cifratura locale, separazione assoluta dal business, responsabilita' owner esplicita.            |

## 5. Tier 4 Roadmap Top 5

Roadmap completa: [tier4_roadmap.md](2026-05-26-whatsapp-corpus-105k-brainstorm/tier4_roadmap.md).

| Rank | Use case                                          | Files da creare                                                                                                                    | Stack                                                               | Effort                                           | Output deliverable                                                  |
| ---: | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------- |
|    1 | Corpus Registry + Count Reconciliation            | `scripts/whatsapp_corpus/build_registry.py`, `scripts/whatsapp_corpus/README.md`, `research/personal/wa-corpus/registry/README.md` | Python `.venv`, regex parser, SHA-256, SQLite o Postgres locale     | 1-2 giorni                                       | `registry.sqlite`, `registry_summary.md`, discrepancy report no-raw |
|    2 | Privacy Boundary Classifier + PII Gate            | `scripts/whatsapp_corpus/privacy_gate.py`, YAML rules, synthetic tests                                                             | Python, regex PII checks, optional Ollama `qwen3.5:9b` solo locale  | 3-5 giorni                                       | `privacy_audit.md`, allow/deny policy, export blocker               |
|    3 | Local Semantic Search su business approved subset | chunker/indexer under `research/personal/wa-corpus/search/`                                                                        | Ollama `bge-m3`, local Qdrant o `pgvector`, qwen3.5 local synthesis | 3-7 giorni CLI; 2-3 settimane UI                 | Local query CLI, later `kita.balizero.com` internal search          |
|    4 | CRM Timeline + Open Loop / Document Tracker       | event schema, extractor, review queue                                                                                              | Python, qwen3.5 local, Postgres confidence fields                   | 1-2 settimane pilot; 3-4 settimane UI            | `wa_chat_events`, `wa_open_loops`, per-client timeline              |
|    5 | Pricing / Quote / Compliance Audit Pilot          | pricing audit scripts and anomaly report folder                                                                                    | Python currency regex, qwen3.5 disambiguation, `PricingTool`        | 3-5 giorni static; 1-2 settimane review workflow | Internal anomaly report, not disciplinary evidence                  |

## 6. Next-Action Prompt

```text
Implement the first WhatsApp corpus execution unit: a local-only corpus registry and reconciliation report for `~/Desktop/wa-chats-MASTER-2026-05-26/`.

Constraints:
- Do not upload or call cloud LLMs.
- Do not output raw message text, phone numbers, or message snippets.
- Use repo `.venv`.
- Create a deterministic parser for:
  - `01_wa-mirror-db/*.txt`: `YYYY-MM-DD HH:MM [SENT|RECEIVED] ...`
  - WhatsApp exports: `[DD/MM/YY, HH.MM.SS] Name: ...` and close variants.
- Produce:
  - per-source file count,
  - per-file message-start count,
  - total parser count,
  - discrepancy report explaining `105,532` parser count vs target `105,530`,
  - parse warnings by file,
  - no raw text.
- Suggested files:
  - `scripts/whatsapp_corpus/build_registry.py`
  - `scripts/whatsapp_corpus/README.md`
  - `research/personal/wa-corpus/registry/README.md`
  - generated `registry.sqlite`
  - generated `registry_summary.md`
- Add focused parser tests with synthetic fixtures only.
- Verify by running the script on the real local corpus and tests on synthetic fixtures.
```

## Verification Notes

Local shell checks run before using corpus quantities:

- `find "$HOME/Desktop/wa-chats-MASTER-2026-05-26" -type f \( -name '*.txt' -o -name '_chat.txt' \) | wc -l` returned `698`.
- Per-source file counts returned `288`, `400`, `10`.
- Python regex parser in repo `.venv` returned `105.532` message-start records total: `14.847` mirror, `74.753` ZIP, `15.932` Drive/iCloud.
- `01_wa-mirror-db/INDEX.md` reports `288` contacts with chats and `18.034` total messages; filename prefix sum was `16.836`; regex message-start count was `14.847`. Treat mirror counts as a known reconciliation target, not settled truth.
- Peer `mini` was unreachable from Pro during this run, so no Pro/Mini sync verification was possible.
