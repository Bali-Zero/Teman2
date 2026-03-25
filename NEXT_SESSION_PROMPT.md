# Next Session: NLM Follow-up + NB-2 Population

## Session 2026-03-25b — NLM Knowledge Fabric IMPLEMENTED

### What was done

NLM Knowledge Fabric Integration merged to main (22 commits, 52 files, +2281 lines).
6 AI brainstorm → 3 review rounds → 21 subagent implementation → 3 code reviews → 5 bug fixes.
Bridge on Pro:18790, Fly.io ENABLE_NLM_ENRICHMENT=true, pre-warm running (45 questions).

### TODO (next session)

1. **Check pre-warm**: `tail -50 /tmp/nlm-prewarm.log` + `redis-cli keys "notebooklm:qa:*" | wc -l`
2. **Fix LaunchAgent**: System Preferences → Full Disk Access → add Terminal.app → `launchctl load`
3. **Populate NB-2→8**: Immigration (80 docs), Company (100 docs), Tax (70 docs) — content task
4. **Optimize bridge**: library ~50s → MCP stdio client ~5s (JSON-RPC persistent subprocess)
5. **E2E visual test**: kita.balizero.com/chat → borderline question → badge + citations

### Previous Session (2026-03-25a) — Knowledge Fabric Infrastructure

### Completed

- **NB-1 Codebase**: 35 fonti, 10/10 test, daily refresh cron 04:30 WITA (`scripts/nlm_nb1_daily_refresh.py`)
- **NB-9 Research Lab**: 115 fonti web (Fly.io + A2A), findings backlog in memory
- **ai-dispatch.sh v3**: oracolo, oracolo-nb, research, websearch, reasoning commands + 3-tier safety + Gemini fallback cascade
- **Federation orchestrator**: CLASSIFY_PROMPT + suggest_agents + agent_labels updated with all new agents
- **DeepSeek R1 671b**: tested ($0.01/query, 27K reasoning chars), context injection via `nuzantara_system_context.md`
- **Exa/Brave web search**: tested (Exa >> Brave >> Perplexity not needed)
- **Codex unblocked**: check_safety() 3-tier fix, protected files now readable
- **Source prep decisions**: PDF > chunks, clean OCR, Master+Latest amendments, temporal headers, topic packs

### CRM Audit (earlier same day) — 7 commits pushed

- Data loss fix, portal types aligned, format-date utility, client detail split 6394→481 lines
- Must still run: `normalize_nationalities.py --apply` on prod DB, fix `.husky/pre-commit`

## Next: NB-2 Immigration & Visa

Populate NB-2 (`84375bc3-12d0-4405-a774-9b89189d8c39`) with ~80 individual sources.

### Sources to load

- 14 Drive immigration PDFs (via drive_id — see all_drive_files.json)
- 117 visa_types from PostgreSQL prod → individual markdown exports
- visa_oracle top 200 from Qdrant → markdown
- kbli_tka_hybrid 246 (KBLI→TKA position mapping) → markdown
- Key regulations: PP 40/2023 (`1w1qTHFoPiqlQpDORmc4mj5ha2-mRTNgs`), Permenkumham 22/2023 (in kb*sources), Permenkumham 11/2024 (`1KnmpiLByTIGYX68_cuMQhWwCyQSMnMj*`), Permen Imipas 8/2025 + 3/2024
- 5 topic packs from 205 immigration articles (EN)
- 8 training-data/visa/ files + spouse_mixed_marriage_conversation.md
- visa_imigrasi_list.txt (in kb_sources)
- Priority Note + chat_configure

### Critical discovery

Permenkumham 11/2024 partially revoked by Permen Imipas 3/2025 — include in Priority Note.

### After NB-2

NB-3 Company → NB-4 Tax → NB-5 Property → NB-6 Ops → NB-7 Editorial → NB-8 Expat Life → Phase 4-6 (Oracle service + routing + chain gates)

## Notebook IDs

| NB                | ID                                     |
| ----------------- | -------------------------------------- |
| NB-1 Codebase     | `f6ecd115-dd89-4c9b-b3dd-071e0e2f1876` |
| NB-2 Immigration  | `84375bc3-12d0-4405-a774-9b89189d8c39` |
| NB-3 Company      | `2e84b9b9-3b99-4bc5-8ec5-351a43c52df4` |
| NB-4 Tax          | `837b620b-2aca-43ab-812e-97ca92bdad1d` |
| NB-5 Property     | `568ec624-ceb8-47d1-a2a2-5b2f793ea7ed` |
| NB-6 Operations   | `3e1baa5f-680f-4499-9430-23a901576bcc` |
| NB-7 Editorial    | `dd464d8f-6b8e-4543-8647-f62c498589b1` |
| NB-8 Expat Life   | `1143b525-dd3f-40d7-a34d-2e9263b44460` |
| NB-9 Research Lab | `d2a05271-2f65-4c02-a44d-eefeb7c7f7cd` |

## Memory files to load

- `nlm-knowledge-fabric-plan.md` — piano v2.0
- `nlm-source-preparation-decisions.md` — gate 1-4
- `nlm-nb1-workflow-methodology.md` — oracolo workflow
- `llm-fleet-audit-2026-03-25.md` — fleet completo
- `vision-and-reasoning-model-routing.md` — model routing rules
