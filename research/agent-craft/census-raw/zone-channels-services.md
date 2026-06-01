# Zone Census — CHANNELS + AGENTIC SERVICES (backend-rag)

> Method: read REAL code in this turn (Read/Grep/Bash read-only), not docs/memory.
> Scope root: `apps/backend-rag/backend/channels/` + representative sample of
> `apps/backend-rag/backend/services/` (the agentic ones: crm, intel, rag/agentic,
> guardian, wa_copilot, naga, research/council, cognitive, self_healing,
> federation_alerts, autonomous_*).
> Date: 2026-06-02. All entities below were verified against the source files
> in this session. Read-only — nothing modified.

---

## Part 1 — CHANNELS

Architecture (read from `channels/__init__.py` + `channels/router.py`):
`Channel adapter → ChannelRouter → ConversationEngine → Orchestrator`.
Production wiring is in `app/setup/service_initializer.py:1160-1228`
(`ChannelRouter` built, adapters `register_adapter`-ed conditionally on creds).

| name | kind | status | evidence | macro_group |
|---|---|---|---|---|
| **web** | channel | **OPERATIVO** | `service_initializer.py:1182-1191` registers it UNCONDITIONALLY ("always enabled"). `web/adapter.py` = full SSE streaming impl (token/thinking/tool_call/sources/answer events). Last commit 2026-05-19. | channels |
| **telegram** | channel | **OPERATIVO** (conditional) | `service_initializer.py:1167-1180` registers iff `settings.telegram_bot_token`. `telegram/adapter.py` full impl + progressive updates, wraps `TelegramBotService`. Last commit 2026-05-19. | channels |
| **whatsapp** | channel | **OPERATIVO** (conditional) | `service_initializer.py:1193-1208` registers iff `WHATSAPP_ACCESS_TOKEN`+`WHATSAPP_PHONE_NUMBER_ID`. `whatsapp/adapter.py` full Meta Cloud API impl, persistent AsyncClient (Golden Rule #10), DLQ-safe send. Last commit 2026-05-19. | channels |
| **instagram** | channel | **OPERATIVO** (conditional) | `service_initializer.py:1210-1224` registers iff `INSTAGRAM_ACCESS_TOKEN`+`INSTAGRAM_ACCOUNT_ID`. `instagram/adapter.py` full impl, echo-suppression (`is_echo` + sender==account_id), `mark_seen` loop-guard. Last commit 2026-05-19. | channels |
| **twitter** | channel | **ROTTO / QUARANTENA** | Lives ONLY in `channels/.disabled-2026-04-30/twitter/` (adapter+config+formatter+test). `service_initializer.py:1226-1228` is a comment block, NO registration. Grep for active `channels.twitter` import = ZERO hits. README: "CRC broken (X webhook handshake fails)". | channels (quarantined) |
| **gchat** (Google Chat) | channel | **MAI_USATO (scaffold-only, no code)** | `ls channels/gchat` → "No such file or directory". `.disabled-2026-04-30/README.md`: "scaffold only, never wired… no scaffold files were ever committed". Exists only in CLAUDE.md taxonomy table. | channels (phantom) |
| **slack** | channel | **MAI_USATO (scaffold-only, no code)** | `ls channels/slack` → "No such file or directory". Same README note as gchat — taxonomy entry only, no files. | channels (phantom) |

Supporting channel infra (not adapters, but channel-zone): `channels/router.py`
(routing + dedup + persist + `_enrich_with_routing` → identity resolve + intent
classify + thread mgmt), `channels/optimizations.py` (rate limiter, Redis dedup,
DLQ retry loop — started at `service_initializer.py:1231-1238`),
`channels/base.py`, `channels/format.py`. All OPERATIVO (imported by router/initializer in this turn).

---

## Part 2 — AGENTIC SERVICES (representative sample)

"Agentic" classified two ways seen in code: (A) **LLM-driven** (imports a
genai/ollama/claude client or shells to `claude`/`codex`/`gemini` CLI), or
(B) **autonomous decision/orchestration** (LangGraph StateGraph, threshold
auto-action, scheduled self-running loop) even without an LLM.

| name | kind | status | evidence | macro_group |
|---|---|---|---|---|
| `crm/enrichment.py` :: **AICRMExtractor** | service | **OPERATIVO (LLM)** | Class `AICRMExtractor` (line 41) instantiates `ZantaraAIClient` (LLM) for structured entity extraction from conversations → CRM fields. Consolidated module (absorbed birthplace + conv-title + ai_crm_extractor). | crm-ai |
| `crm/assignment.py` :: **lead-assignment workflow** | service | **OPERATIVO (agentic, LangGraph)** | `from langgraph.graph import StateGraph` (line 19). `create_lead_assignment_workflow` (line 679) builds 3-node graph: `check_duplicates` → `assign_lead` → `notify_telegram`. `LeadAssignmentState` TypedDict. Rule-based routing (no LLM) but autonomous workflow. | crm-ai |
| `crm/automation.py` :: **ProcessAutomationService / CompletedProcessService / WaitingDocumentsService** | service | **OPERATIVO (autonomous, NO LLM)** | 3 classes (217/477/757). Event-triggered email/notification automation on practice status change (`trigger_on_process_start` etc.). Grep for `llm/genai/ollama/claude` = ZERO. Deterministic + cache-invalidating. Last commit 2026-05-28. | crm-automation |
| `crm/ai_crm_extractor.py` | service | **DUPLICATO (shim)** | 193-byte file: `"""Backward-compat shim — all symbols moved to enrichment.py."""` Re-exports `AICRMExtractor`, `get_extractor`, `AsyncpgJSONEncoder`. | crm-ai (shim) |
| `crm/lead_assignment_agent.py` | service | **DUPLICATO (shim)** | 343-byte shim → re-exports from `assignment.py` (`assign_lead`, `create_lead_assignment_workflow`, etc.). | crm-ai (shim) |
| `crm/client_identity_resolver.py` | service | **DUPLICATO (shim)** | shim → `ClientIdentityResolver`, `normalize_phone` from `assignment.py`. | crm-ai (shim) |
| `crm/enhanced_crm_service.py` | service | **DUPLICATO (shim)** | shim → `EnhancedCRMService` from `client_core.py`. | crm-ai (shim) |
| `crm/birthplace_enrichment_service.py`, `crm/document_categorizer.py`, `crm/cache_manager.py`, `crm/validators.py` | service | **DUPLICATO (shim)** | All <400-byte backward-compat shims (re-export to enrichment/client_core/etc.). Confirmed by size-scan in this turn. | crm (shim) |
| `intel/intel_validators.py` | service | **OPERATIVO (autonomous, NO LLM)** | Docstring "Intel 3-tier validators": Tier1 `regex_schema` (hard gate 0.3), Tier2 `citation_check` (HTTP HEAD 0.4), Tier3 `kg_crossref` (KG match 0.3). Weighted-score validation pipeline; no LLM. | intel |
| `intel/intel_classification_service.py` :: **IntelClassificationService** | service | **OPERATIVO (autonomous, NO LLM)** | `classify_intel_type` (line 30) = keyword-count classifier (visa vs news) for staging-folder routing. Pure heuristic, no LLM. | intel |
| `intel/intel_kg_bridge.py` :: **propose_kg_entities** | service | **OPERATIVO (autonomous)** | `propose_kg_entities` (line 35) PROPOSES tier-3 matches into `kg_proposals` (never auto-promotes) — human-in-loop gate. | intel |
| `intel/dossier_compiler.py` | service | **OPERATIVO (LLM via subprocess)** | In the subprocess-CLI dispatch grep set (shells to LLM CLI). Compiles intel dossiers. | intel |
| `intel/trend_hunter/orchestrator.py` | service | **OPERATIVO (LLM via subprocess)** | Subprocess-CLI dispatch grep hit; trend-hunting orchestration. | intel |
| `rag/agentic/orchestrator.py` (+ 35 sibling files in `rag/agentic/`) | service | **OPERATIVO (LLM, core agent loop)** | `rag/agentic/` = 36 files: ReAct-style reasoning loop (`reasoning.py`, `tool_executor.py`, `tools.py`, `query_planner.py`, `chat_session.py`, streaming core). This is the central Zantara RAG agent. Last commit 2026-05-19. | rag-agentic (CORE) |
| `rag/agentic/llm_gateway.py` :: **LLMGateway** | service | **OPERATIVO (LLM, cascade)** | Class `LLMGateway` (line 76): Gemini Flash → Flash-Lite → OpenRouter cascade; `_max_fallback_depth=3`, `_max_fallback_cost_usd=0.10`. Native function-calling + regex fallback. | rag-agentic |
| `rag/kg_langgraph_orchestrator.py` | service | **OPERATIVO (LLM, LangGraph)** | `StateGraph` (line 18). Claude-via-MAX-OAuth (sonnet-4-6) PRIMARY (`claude_oauth`), OpenAI gpt-4o-mini FALLBACK (lines 107-127). Domain routing → visa/tax/property/company subgraphs. PostgresSaver checkpointer (optional). | rag-agentic |
| `rag/hyde_expander.py`, `rag/query_expansion.py`, `rag/verification_service.py`, `rag/vision_rag.py`, `rag/nlm_verifier.py` | service | **OPERATIVO (LLM)** | All in the genai/subprocess LLM grep set: HyDE doc expansion, query expansion, answer verification, vision-RAG (qwen2.5vl), NLM cross-check. RAG support agents. | rag-agentic |
| `crm_guardian/consolidator.py` + `crm_guardian/base.py` | service | **OPERATIVO (autonomous, NO LLM)** | `base.py` `compute_rule` (line 53) = deterministic Rule enum (`SKIP_EXCEPTION` etc.); `consolidator.py` `plan_consolidation`/`apply_consolidation_for_client` autonomously reorganizes client Drive folders; every action append-only to `crm_guardian_events`. Rule-engine guardian, not LLM. | crm-guardian |
| `crm_guardian/ocr.py` | service | **OPERATIVO (vision, via subprocess)** | In subprocess-CLI grep set; OCR layer (qwen2.5vl per project invariants) for guardian doc validation. | crm-guardian |
| `wa_copilot/extraction_pipeline.py` | service | **OPERATIVO (LLM, local Ollama)** | Docstring "fact extraction pipeline via Ollama qwen3.5:9b LOCAL". `ollama_extract` with `think:False` (mandatory), `DEFAULT_MODEL="qwen3.5:9b"` + `FALLBACK_MODEL="qwen3:8b"`. Append-only into `whatsapp_extractions`, idempotent by extractor_version. Last commit 2026-05-25. | wa-copilot |
| `wa_copilot/practice_scorer.py` | service | **OPERATIVO (autonomous, NO LLM)** | Weighted-score auto-linker: score≥0.85+≥2 signals → `auto_linked`; 0.60-0.85 → `pending_review`; <0.60 skip. Threshold-driven autonomy, no LLM. | wa-copilot |
| `wa_copilot/staging_promoter.py`, `wa_copilot/kg_bridge.py`, `wa_copilot/identity_resolver.py`, `wa_copilot/team_promises.py` | service | **OPERATIVO (autonomous, NO LLM)** | Pipeline stages around the extraction (promote staging, KG bridge, identity resolution, promise tracking). Deterministic. | wa-copilot |
| `naga/orchestrator.py` :: **NagaOrchestrator** | service | **OPERATIVO (LLM, research loop)** | Docstring "Naga Orchestrator — research loop coordinator". `NagaResearchState` TypedDict (line 50), `research()` loop (line 160): decompose query → search (ask_legal/search_intel/Exa/Brave) → score → Gemini bulk-read → synthesize. Tier-budgeted. | naga-research |
| `naga/deps.py` / `naga/gateway.py` / `naga/persist.py` | service | **OPERATIVO (LLM via subprocess)** | `deps.py`: "server mode… uses Gemini CLI via subprocess"; tool deps `_ask_legal`/`_search_intel`/`_exa_search`/`_brave_search`. Gateway + persistence for the research agent. | naga-research |
| `research/consiglio_orchestrator.py` :: **Consiglio v1** | service | **OPERATIVO (multi-LLM council)** | 4-LLM deliberation: claude (Opus via OAuth CLI) + gemini (3.1 Pro CLI) + deepseek (V4 Pro) + notebooklm (MCP). Gate-6: ≥3/4 agreement per claim. Graceful degrade if a member fails. Read-only (no publish). | research-council |
| `cognitive/oracle.py` :: **OracleCouncil / OracleOrchestrator** | service | **OPERATIVO (multi-LLM council)** | `OracleCouncil` (line 151) + `OracleOrchestrator` (line 294): claude -p (Opus analyst) + gemini + deepseek + ollama, judge = claude -p (Sonnet) → ≤3 UltraMove. Strategic-advisor agent. Last commit 2026-05-19. | cognitive-oracle |
| `cognitive/anomaly_detector.py` + `anomaly_alerter.py` + `anomaly_subscriber.py` | service | **OPERATIVO (autonomous)** | Anomaly detection/alert/subscribe trio (EventBus-driven). Autonomous monitoring. | cognitive-oracle |
| `self_healing/orchestrator.py` (+ `backend_agent.py`, `checks/{db,system,cache,http_api}.py`, `actions/{restart_service,gc,reconnect_cache}.py`, `circuit_breaker.py`) | service | **OPERATIVO (autonomous auto-recovery agent)** | Multi-check → multi-action self-healing agent. Ticked by `AutonomousScheduler` task `self_healing` (`enabled=True`, `auto_fix_enabled=True`, see `autonomous_scheduler.py:376-393`). Located `backend/services/self_healing/`. | self-healing |
| `misc/autonomous_scheduler.py` :: **AutonomousScheduler** | service | **OPERATIVO-ma-GUTTED** | Instantiated in prod (`service_initializer.py:1067` `create_and_start_scheduler`, registered `critical=False`). BUT of ~10 registered tasks, ~half are `enabled=False` (migrated to OpenClaw cron on Pro): `conversation_trainer`/`renewal_alerts`/`birthday_notifier`/`daily_ops_autopilot`(BUG self-call)/`drive_changes_poll` DISABLED; `auto_ingestion`/`self_healing`/`golden_routes_seeder`/`birthplace_enrichment`/`conversation_cleanup`/`kg_incremental_builder` ENABLED. | scheduler (core) |
| `autonomous_agents/knowledge_graph_builder.py` :: **KG Builder** | service | **OPERATIVO (autonomous, NO LLM)** | "Phase 4 Advanced Agent" — builds KG nodes/edges (kbli→requires→NIB etc.) into PG. Imported by `agents.py`/`autonomous_agents.py` routers + `incremental_builder.py` (ticked by scheduler `kg_incremental_builder` every 24h). Regex/rule extraction. | knowledge-graph |
| `autonomous_lab/planner.py` | service | **INCERTO (orphan-ish)** | `autonomous_lab/` = only `__init__.py` + `planner.py`. Grep for external import of `autonomous_lab`/`AutonomousLab` (excluding self) = ZERO hits in this turn. Likely WIP/scaffold (dir mtime 2026-06-01 — very recent). Needs deeper read to confirm wiring. | autonomous-lab |
| `federation_alerts/dispatcher.py` (+ `daemon.py`, `actions/codex_{image_gen,visual_dispatch,xhigh_fix}.py`) | service | **OPERATIVO (multi-LLM via subprocess)** | `dispatcher.py`: subprocess wrapper around `scripts/ai-dispatch.sh` + `ConsiglioV1.deliberate()`. Strips `ANTHROPIC_API_KEY` (Golden Rule #13 defense-in-depth). `actions/` dispatch Codex for image-gen / visual / xhigh code-fix. Autonomous alert→action agent. | federation-alerts |
| `knowledge_graph/extractor_gemini.py` :: **GeminiKGExtractor** | service | **OPERATIVO (LLM)** | Class `GeminiKGExtractor` (line 28) via `get_genai_client()`, model `gemini-2.0-flash`, entity+relation extraction from Indonesian legal docs. (`api_key` param deprecated → facade.) | knowledge-graph |
| `knowledge_graph/coreference.py`, `knowledge_graph/pipeline.py` | service | **OPERATIVO (LLM)** | Both in genai/subprocess LLM grep set — coreference resolution + KG extraction pipeline. | knowledge-graph |
| `oracle/reasoning_engine.py`, `oracle/smart_oracle.py`, `oracle/nlm_shadow_retrieval.py`, `oracle/cross_notebook_correlator.py` | service | **OPERATIVO (LLM)** | In genai/subprocess LLM grep set. `oracle/` = grounding/reasoning layer (NLM shadow retrieval, cross-notebook correlation). Distinct from `cognitive/oracle.py`. | oracle-grounding |
| `article_composer/claude_client.py` | service | **OPERATIVO (LLM via subprocess)** | Shells to `claude` CLI (OAuth path) for blog/article composition. Paired with DeepSeek per CLAUDE.md routing. | content-composer |
| `ingestion/auto_ingestion_orchestrator.py`, `ingestion/legal_ingestion_service.py`, `ingestion/scraper_normalizer.py` | service | **OPERATIVO (LLM)** | genai grep set. Auto-ingestion orchestration (ticked by scheduler `auto_ingestion` enabled=True), legal-doc ingestion, scraper output normalization. | ingestion |
| `routing/surface_router.py` | service | **OPERATIVO (LLM)** | genai grep set — LLM-assisted surface/intent routing. | routing |
| `multimodal/pdf_vision_service.py` | service | **OPERATIVO (vision LLM)** | genai grep set — PDF vision (OCR/extraction). | multimodal |
| `council/tone_council.py` (+ `cli_runners.py`, `prompts.py`) | service | **OPERATIVO (multi-LLM)** | genai + subprocess grep set — tone/style council (multi-LLM voting on copy). | council |

---

## GAP — agentic work missing / weak in this zone

1. **No agentic adapter for the dead/scaffold channels.** Twitter (CRC broken),
   gchat, slack have ZERO live agent surface. Any "omnichannel agent" promise
   is really 4 channels (web always-on + telegram/whatsapp/instagram credential-
   gated). gchat/slack are phantom (taxonomy entries, no code at all).

2. **`autonomous_lab/planner.py` looks orphaned.** Dir contains only
   `__init__.py` + `planner.py`, created 2026-06-01, and nothing outside the
   package imports it (grep ZERO in this turn). Either brand-new WIP not yet
   wired, or dead scaffold — no router/scheduler hook found. GAP: an autonomous
   "planner" agent exists on disk but has no execution entrypoint visible here.

3. **AutonomousScheduler is half-gutted in-process.** The Fly-side scheduler
   keeps ~5 tasks `enabled=False` because they were migrated to OpenClaw cron on
   Pro (auto_stop incompatibility + one literal BUG: `daily_ops_autopilot` calls
   `localhost:8000` = itself). The in-app "autonomous agent" surface is thinner
   than the registered-task list suggests; the real autonomy lives in Pro cron,
   OUTSIDE this zone. GAP: no single source-of-truth in-code that says which
   autonomy runs on Fly vs Pro — you must read `enabled=` flags + comments.

4. **CRM shim sprawl (8 files).** `crm/` has 8 sub-400-byte backward-compat
   shims (`ai_crm_extractor`, `lead_assignment_agent`, `client_identity_resolver`,
   `enhanced_crm_service`, `birthplace_enrichment_service`, `document_categorizer`,
   `cache_manager`, `validators`). Not broken (they re-export), but they inflate
   the "75 services" count and dilute the real agentic surface. Cleanup candidate.

5. **Multi-LLM council duplication.** Three separate council/deliberation agents
   exist with overlapping intent: `research/consiglio_orchestrator.py` (Consiglio
   v1, 4-LLM ≥3/4 gate), `cognitive/oracle.py` (OracleCouncil, 4 voices + Sonnet
   judge), `council/tone_council.py` (tone voting). Plus `federation_alerts`
   embeds `ConsiglioV1.deliberate()`. No shared council primitive — each
   re-implements subprocess fan-out + degrade-on-failure. GAP: a unified
   council/deliberation service.

6. **No agentic layer over inbound channel content beyond RAG.** The channel
   router enriches (identity/intent/thread) and hands to ConversationEngine →
   RAG agent. There is NO autonomous post-conversation agent that, e.g., opens a
   CRM practice, drafts a quote, or triggers follow-up directly from a live
   WhatsApp/Telegram thread — that work is split into the OFFLINE `wa_copilot`
   batch pipeline (Ollama extraction on the wa-mirror corpus, local-only per
   Symbiosis Law 2) rather than an inline real-time agent. GAP: real-time
   conversational → action bridge.

7. **Guardian + scorer are rule-engines, not LLM-judged.** `crm_guardian`
   (compute_rule enum) and `wa_copilot/practice_scorer` (weighted thresholds)
   make autonomous WRITE/auto-link decisions with NO LLM in the loop and NO LLM
   second-opinion gate. For high-stakes Drive moves / auto-linking that is fast
   and auditable, but there's no escalation-to-LLM path on ambiguous cases.

---

### Count

Channels: 7 entities (4 OPERATIVO incl. 3 credential-gated, 1 ROTTO/quarantena = twitter, 2 MAI_USATO phantom = gchat/slack).
Services sampled: ~44 agentic entities — ~33 OPERATIVO (LLM or autonomous), 8 DUPLICATO (crm shims), 1 OPERATIVO-ma-gutted (AutonomousScheduler), 1 INCERTO (autonomous_lab/planner). 0 hard-ROTTO in the services sample (twitter is the only ROTTO, in channels).
