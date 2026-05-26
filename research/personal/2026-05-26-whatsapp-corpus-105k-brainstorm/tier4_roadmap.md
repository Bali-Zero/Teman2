# Tier 4 — Actionable Roadmap

## Selection Logic

The top roadmap intentionally starts with infrastructure and privacy gates before any semantic or CRM use case. This is the only defensible order because the corpus mixes business, team, and personal conversations. The fastest business value comes from making a trusted, local registry first, then allowing only reviewed business slices into search, CRM enrichment, and operational follow-up workflows.

## Top 5 Implementation Plan

| Rank | Use case                                         | Concrete implementation                                                                                                                                                                                                                                                                                                                               | Stack                                                                                                                                 | Effort                                                              | Deliverable location                                                                                                                          | Pre-flight check                                                                                                                                                                   |
| ---: | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|    1 | Corpus Registry + Count Reconciliation           | Create deterministic parser for both mirror and WhatsApp export formats. Store one row per source file with hash, source folder, parser type, message-start count, line count, min/max timestamp when parseable, parse warnings, and discrepancy report for `105,532` parser count vs `105,530` target. Never store raw message text in the registry. | Python in repo `.venv`, SQLite or local Postgres, SHA-256, regex parser, optional Markdown report.                                    | 1-2 days                                                            | `research/personal/wa-corpus/registry/`; optional tables `wa_corpus_files`, `wa_corpus_parse_events`.                                         | Confirm exact source root, decide SQLite vs Postgres, define no-raw-output invariant, verify `.gitignore` excludes generated registry if it contains file paths or contact names.  |
|    2 | Privacy Boundary Classifier + PII Gate           | Build rule-first classifier at chat/file level: `personal_private`, `team_internal`, `business_client`, `business_vendor`, `unknown_review`. Start from path/source/contact-name metadata, not message content. Add a PII export gate that blocks phone numbers, names, raw paths, quotes, and message snippets from any cloud-bound artifact.        | Python, YAML allow/deny lists, local qwen3.5 only for `unknown_review` if needed, regex PII checks, pytest fixtures.                  | 3-5 days                                                            | `scripts/whatsapp_corpus/privacy_gate.py`; `research/personal/wa-corpus/privacy_audit.md`; possible skill `skills/wa-corpus-local-only/`.     | Define initial allow/deny lists for team names and personal contacts; decide whether any human reviewer can see ambiguous messages; document Symbiosis Law 2 export policy.        |
|    3 | Local Semantic Search on Approved Business Chats | Index only chats explicitly approved by the privacy gate. Chunk messages by conversation/time window, redact PII before embedding where feasible, embed with `bge-m3`, store vectors locally, and expose a local CLI query first before any dashboard.                                                                                                | Ollama `bge-m3:latest`, local Qdrant or Postgres `pgvector`, Python chunker, FastAPI later, qwen3.5 for answer synthesis only on Pro. | 3-7 days for CLI pilot; 2-3 weeks with UI.                          | `research/personal/wa-corpus/search/`; optional local collection `wa_business_chat_chunks`; later internal route on `kita.balizero.com`.      | Need approved business subset from use case #2, vector store choice, chunking policy, RBAC rule for who can search what.                                                           |
|    4 | CRM Timeline + Open Loop / Document Tracker      | For approved business chats, extract events: inquiry, document request, document claimed-sent, payment/invoice mention, appointment, promise/follow-up, issue/escalation, resolution. Store as reviewable suggestions, not automatic truth. Produce per-client timeline and open-loop queue.                                                          | Python event schema, local qwen3.5 extraction, Postgres tables, confidence fields, admin review UI later.                             | 1-2 weeks for extraction pilot; 3-4 weeks with review UI.           | `research/personal/wa-corpus/events/`; later backend tables `wa_chat_events`, `wa_open_loops`; internal admin surface in `kita.balizero.com`. | Need CRM person matching source, event taxonomy, confidence thresholds, manual review workflow, rule that `my.balizero.com` never exposes raw chat evidence.                       |
|    5 | Pricing / Quote / Compliance Audit Pilot         | On approved business chats only, detect currency amounts, package/service names, discount language, and quote commitments. Compare candidates to `PricingTool`/approved references through a manual review queue. No employee discipline automation; output is anomaly report only.                                                                   | Python regex and currency normalizer, local qwen3.5 disambiguation, `PricingTool`, Postgres review table, Markdown anomaly report.    | 3-5 days for static anomaly report; 1-2 weeks with review workflow. | `research/personal/wa-corpus/pricing_audit/`; internal-only report under `research/operations/` if promoted.                                  | Need approved business subset, current `PricingTool` source, explicit policy that flags are leads for review, not proof; decide whether team internal chats are excluded entirely. |

## Recommended First Execution Unit

Start with **Use Case 1: Corpus Registry + Count Reconciliation**. It produces the least privacy risk, requires no cloud and no LLM, and creates the audit foundation for every later step. It should not output raw message text, personal names, phone numbers, or message snippets. It should output counts, hashes, parser warnings, and source-relative paths only if the report stays local.

## Architecture Skeleton

| Component      | First version                                                            | Later version                                                      |
| -------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| Parser         | `scripts/whatsapp_corpus/build_registry.py`                              | Importable package under `packages/wa_corpus/` if reused           |
| Storage        | SQLite file under `research/personal/wa-corpus/registry/registry.sqlite` | Postgres tables once schema stabilizes                             |
| Privacy gate   | YAML rules + regex PII blocker                                           | Human review UI + RBAC                                             |
| Embeddings     | Not used in first unit                                                   | Ollama `bge-m3` local only                                         |
| LLM extraction | Not used in first unit                                                   | Ollama `qwen3.5:9b` local only                                     |
| Dashboard      | Markdown report                                                          | `kita.balizero.com` internal/admin only                            |
| Client portal  | Out of scope                                                             | Only approved CRM summaries, never raw chat links or source traces |

## Next-Action Prompt

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
