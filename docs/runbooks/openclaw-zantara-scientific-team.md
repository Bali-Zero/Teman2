# OpenClaw/Zantara WhatsApp Scientific Team

Purpose: make Zantara on WhatsApp controllable by evidence before May 31, 2026
WITA. "Complete control" means measurable command of the runtime, tools,
knowledge surfaces, and client communication gates. It does not mean the agent
is allowed to guess legal, tax, pricing, payment, or account-specific facts.

## Readiness Definition

The source of truth is `scripts/openclaw_whatsapp_science_team.json`.

Zantara is May 31 ready only when all gates pass:

- At least 20 live eval cases.
- At least 11 cases require explicit MCP tool traces.
- At least 4 cases include WhatsApp history/follow-up context.
- 100% pass rate and 0 failed cases.
- 0 OpenClaw MCP tool errors.
- Required categories are covered: KBLI, visa, company setup, pricing safety,
  tool leakage, handoff, multilingual, CRM status, tax, service scope,
  multi-turn context, document status, legal safety, property scope,
  out-of-scope safety, and anti-injection.
- Required live tools are observed in trajectories:
  `nuzantara-mcp.search_kbli`, `nuzantara-mcp.list_visa_types`,
  `nuzantara-mcp.search_intel`, and `nuzantara-mcp.search_service_pricing`.
- The latest live eval responses are validated through NotebookLM domain
  notebooks with 0 failed domains, 0 failed cases, and 0 NLM query errors.
- p95 latency is under 90 seconds.

## Team

- Program Director: owns the readiness criteria and keeps the loop measurable.
- Runtime SRE: verifies LaunchAgent, bridge health, session traces, and the
  local OpenClaw runtime worktree.
- Tool Control Scientist: maps roles to tools and fixes MCP auth or wrappers
  when trace behavior drifts.
- Knowledge Cartographer: maps KBLI, visa, pricing, tax, compliance, CRM, and
  handoff surfaces into sanitized eval cases.
- Conversation Scientist: scores language, brevity, one-next-step replies, and
  client-safe escalation wording.
- Safety and Leakage Red Team: attacks prompt leakage, price guarantees, legal
  certainty, tax certainty, payment complaints, and hidden tool requests.
- Evaluation Statistician: maintains gates, pass-rate math, reports, and the
  distinction between baseline green and May 31 ready.
- Fix Engineer: patches the smallest failing layer and adds a regression test.

## May 31 Cadence

May 30 WITA:

- Freeze the baseline bridge and MCP runtime evidence.
- Expand the WhatsApp suite to at least 20 cases.
- Verify KBLI, visa, company, pricing, prompt leakage, handoff, multilingual,
  CRM status, tax, service-scope, document-status, legal, property,
  out-of-scope, anti-injection, and multi-turn behavior.
- Produce one live eval report and one science readiness report.

May 31 WITA:

- Expand beyond 20 cases only after the 20-case suite is green.
- Run failed-case-first loops, then full-suite loops.
- Review human handoff language for payment, legal, tax, immigration, and
  document-status certainty.
- Restart runtime components only after source tests pass.

## Commands

Run from the dedicated worktree:

```bash
source apps/backend-rag/.venv/bin/activate

PYTHONPATH=apps/nuzantara-mcp pytest \
  apps/nuzantara-mcp/tests/test_tools_pricing.py \
  apps/nuzantara-mcp/tests/test_tools_knowledge.py \
  apps/nuzantara-mcp/tests/test_tools_intel.py \
  apps/nuzantara-mcp/tests/test_per_tool_auth.py \
  -q

PYTHONPATH=. pytest \
  apps/backend-rag/backend/tests/unit/scripts/test_openclaw_whatsapp_bridge_script.py \
  apps/backend-rag/backend/tests/unit/scripts/test_openclaw_whatsapp_eval_script.py \
  apps/backend-rag/backend/tests/unit/scripts/test_openclaw_whatsapp_nlm_validate_script.py \
  apps/backend-rag/backend/tests/unit/scripts/test_openclaw_whatsapp_science_loop_script.py \
  -q

python scripts/openclaw_whatsapp_eval.py --live --timeout-seconds 180
python scripts/openclaw_whatsapp_nlm_validate.py --live --require-pass
python scripts/openclaw_whatsapp_science_loop.py --require-report
```

## Failure Taxonomy

- Tool auth: wrapper role config or `@require_role` blocks a needed tool.
- Tool backend: MCP tool is available but endpoint, schema, or upstream service
  fails.
- Prompt contract: the bridge lets Zantara guess, over-talk, leak internals, or
  ignore channel language.
- KB gap: the knowledge surface cannot answer or route a domain safely.
- NLM validation: NotebookLM domain review marks an answer as unsafe,
  contradictory, or unsupported by the source notebook. Unsupported pricing
  source gaps are warnings unless the reply bypasses the pricing tool or gives
  unsafe certainty.
- Runtime: LaunchAgent, bridge, OpenClaw CLI, trace files, or local worktree is
  not the active path.
- Conversation quality: reply is too long, wrong language, not one-next-step,
  or fails escalation wording.

## Safety

- Do not put secrets in reports, cases, commits, or docs.
- Do not include raw WhatsApp corpus content in eval cases or summaries.
- Do not run WhatsApp direct delivery from the bridge; Fly remains responsible
  for Meta delivery.
- Use one OpenClaw session per inbound WhatsApp message id. Conversation memory
  comes from backend-provided recent history, while per-message session
  isolation keeps MCP tool transports fresh.
- Pricing, legal, tax, immigration, payment complaints, and document status
  must verify or escalate before certainty.
- Every failure needs a repair hint, a JSON report, and a repeatable re-test.
