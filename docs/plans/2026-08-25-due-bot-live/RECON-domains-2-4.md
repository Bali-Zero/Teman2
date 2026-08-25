# RECON — domains 2-4 against the machinery that already exists

Directive #1 §3 widened v1 from "the F5 tool set" to **domains 1-4**. Domain 1 is built.
This is what a read-only sweep found for 2, 3 and 4, verified on disk rather than taken
from any doc's description of itself. It is a map, not a design: it says what may be
reused, what must be built, and what is dangerous.

## The finding that reorders the work

**The team bot cannot call anything.** `apps/team-bot/README.md` says it of itself: *"No
server, no CRM client, no I/O — nothing in this package is imported by any running
service."* The ten-tool registry is pure Pydantic specification with **no executors**.

So the bottleneck is not the content of domains 2-4. All three need the same missing
piece — an executor layer that turns a validated `ToolDecision` into an authenticated,
`assigned_to`-scoped call against the backend. Build that once, and 2/3/4 become tool
definitions on top of machinery that already works. Build it three times inside three
domain lanes and we get three divergent answers to the same question, which is the shape
this repo has paid for before.

**That layer is the keystone lane, and it precedes the domain lanes.**

## Domain 2 — documents in chat: an INTEGRATION domain, not a build

Every stage the directive asks for is live in production today, not merely present:

| Stage | Where | State |
|---|---|---|
| WhatsApp media in | `services/intake/whatsapp_live_adapter.py` `ingest_live_media()` | live webhook path |
| OCR | `services/intake/classify.py` `ocr_pages()` — `qwen2.5vl:7b` via local Ollama | the exact model the directive names |
| Classify | `classify.py` `classify_document()` — keyword-scored, 20 types, vision + text-LLM fallbacks confidence-capped into a review band | anti-hallucination floor is `unknown/0.0`, never a guess |
| Auto-attach | `services/intake/auto_attach.py` — 3 gates | strong-identifier corroboration only |
| Commit | `services/intake/writer.py` `plan_commit()` / `execute_commit()` | writes both `documents` and `practices.documents[]` |
| "missing: X" | table `practice_required_documents`, column `practices.missing_documents`, `crm_practices.py:2122` | a CRM feature, not intake-specific |

**Armed, not dark.** `infra/launchagents/com.nuzantara.intake-worker.plist` carries
`INTAKE_WRITER_ENABLED=true`, `INTAKE_AUTO_ATTACH_ENABLED=true`, both phone/name-id
auto-attach flags true, `INTAKE_TEXT_LLM_CLASSIFY_ENABLED=true`. The intake skill's
"all default OFF" line describes the CODE default and does not describe this daemon —
reading it as the live state is the mistake to avoid.

To build: a team-bot read tool over `practice_required_documents` (the registry already
declares `get_required_documents` R0 at `registry/tools.py:252` — it needs an executor,
not a schema). Separately, today's flow is queue -> worker -> minutes later; if the
product wants the bot to answer "here's what's missing" immediately after a photo lands,
that near-real-time path is genuinely new work and should be named as such, not assumed.

## Domain 3 — deadlines: two systems, each doing a different half

1. **The sweep is live and is a broadcast**, not per-staff: `routers/cron_notifiers.py`
   (`visa-expiry`, `lkpm-deadlines`, `compliance-forecast`, ...) driven by GitHub Actions
   cron -> Fly, each endpoint gated on a `system_settings.<name>_enabled` kill switch.
   Pipeline `predictive_engine.py` -> `alerts_engine.py` -> `alert_dispatcher.py`.
   `services/misc/proactive_compliance_monitor.py` is deprecated in its own source — do
   not reuse it.
2. **`assigned_to`-scoped querying already exists but on a different bot**:
   `services/rag/agentic/team_crm_tools.py` `TeamMyDeadlinesTool` reads
   `client_expiry_alerts_view` + `compliance_alerts` filtered by `assigned_to`, gated
   behind `WA_TEAM_CRM_TOOLS_ENABLED` (default off). `app/deps/crm_access.py`
   `get_crm_user_filter()` is the REST-router equivalent, proven live.

Nothing new is needed at the data layer. The team bot needs an executor that reuses one
of those two scope resolvers — **not a third derivation of `assigned_to` filtering.**

## Domain 4 — knowledge and pricing: call the backend, skip the MCP

Both seams are real. `apps/nuzantara-mcp/nuzantara_mcp/server_knowledge.py` exists as the
PII-free surface for a **cloud** client (Cowork), and every one of its tools is a thin
wrapper making an HTTP call to the same Fly backend. The team bot is a local process
already calling that backend, so routing through MCP adds a process and transport hop and
inherits a `@require_role` model built for Claude-desktop conventions rather than F5's
typed-tool contract.

Reuse the internal REST endpoints directly: `/api/pricing/*`, `/api/agentic-rag/query`,
`/api/v1/kbli-notebook/*`. The MCP server is the wrong-consumer seam, not a wrong answer.

Naming correction worth carrying: the class is `PricingService`
(`services/pricing/pricing_service.py:113`). "PricingTool" in MANDATE prose and in
`alerts_engine.py` is informal shorthand; searching for a class by that name finds
nothing.

## Dangerous — flagged, not fixed by this recon

- `services/agents/tool_authorizer.py` `_check_client_scope` is a **confirmed no-op**
  whose call site reads as enforcement. F5 already names closing it as a gate before any
  mutation arms. *Lane dispatched 2026-08-25.*
- `services/messaging_identity_service.py` logs **raw phone numbers in cleartext**. F7
  already names fixing it as a precondition for extending that module.
  *Lane dispatched 2026-08-25.*
- Domain 2's writer path writes passport/KITAS numbers into CRM rows in production. Any
  team-bot reply text, or any B8 per-member memory row, that echoes an extracted document
  field sits exactly on the Law-2 output frontier that Directive #1 §4.1 says needs **one
  boundary sentence from Zero**, stated once — not re-derived per lane. A documents tool
  makes that question due, rather than theoretical.
- `client_expiry_alerts_view` is created in `apps/backend-rag/scripts/apply_migration_033.py`,
  **not** under `migrations_v2/`. Anyone looking for it by the usual convention finds
  nothing and may conclude it is absent.

## Addendum — the F7 class census (2026-08-25)

The F7 lane closed `messaging_identity_service.py`. A census over the ENTITY rather than
that file found the real size:

**~40 raw-identifier log sites across ~13 files.** `app/routers/whatsapp_chat.py` alone
carries ~14, on the live client-bot path. Fixing one file and calling "Raw phone never in
logs" done is the W107 shape — a wrapper cured out of five, with the class left open and
the ledger reading closed.

Mitigating, and stated so severity is not overread: `app/setup/sentry_config.py`'s
`_before_send` ALREADY redacts phone shapes before an event reaches Sentry, with
shape-anchored regexes and its accepted collateral written down. Third-party egress is
therefore covered. What stays exposed is **local and Fly log files**, which is precisely
what CLAUDE.md §14 and Law 2 name.

The sweep is dispatched as its own branch off `main`, NOT on the integration branch: it is
a live surface outside this mandate's perimeter, and a PII exposure on a live surface does
not wait for a product train to land. The shared helper travels with it by cherry-pick, so
both branches carry identical content and the final train merges by content rather than
conflicting.
