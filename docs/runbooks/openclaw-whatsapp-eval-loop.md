# OpenClaw WhatsApp Eval Loop

Purpose: test Zantara on the WhatsApp/OpenClaw path for KB access, tool discipline, client-safe replies, and escalation behavior before trusting autonomous replies.

## Fast loop

Run from the repo root worktree:

```bash
source apps/backend-rag/.venv/bin/activate
PYTHONPATH=. pytest \
  apps/backend-rag/backend/tests/unit/scripts/test_openclaw_whatsapp_bridge_script.py \
  apps/backend-rag/backend/tests/unit/scripts/test_openclaw_whatsapp_eval_script.py \
  apps/backend-rag/backend/tests/unit/scripts/test_openclaw_whatsapp_nlm_validate_script.py \
  apps/backend-rag/backend/tests/unit/scripts/test_openclaw_whatsapp_science_loop_script.py \
  -q
python scripts/openclaw_whatsapp_eval.py --live --max-cases 3 --timeout-seconds 180
python scripts/openclaw_whatsapp_nlm_validate.py --live --require-pass
python scripts/openclaw_whatsapp_science_loop.py --no-write
```

The eval report is written to `.openclaw-evals/openclaw-whatsapp-eval-*.json`.
By default, the runner also scores OpenClaw trajectory files under
`~/.openclaw/agents/wa/sessions` and fails KB/pricing cases when the required
MCP tool was not called or returned an error.

The May 31 readiness protocol is defined in
`docs/runbooks/openclaw-zantara-scientific-team.md`. The science loop reads the
latest eval report plus the latest NLM validation report and converts them into
explicit readiness gates.

The current gate requires at least 20 cases, including tool-required probes and
WhatsApp history/follow-up context probes. A previous 12-case green report is a
baseline only; it is not May 31 ready under the stricter gate.

## Full loop

1. Run the unit tests above.
2. Run all eval cases:

```bash
python scripts/openclaw_whatsapp_eval.py --live --timeout-seconds 180
python scripts/openclaw_whatsapp_nlm_validate.py --live --require-pass
python scripts/openclaw_whatsapp_science_loop.py --require-report
```

3. Read failed cases in the JSON reports.
   - `failures` explains reply or tool trace failures.
   - `tool_trace.called_tools` shows which MCP tools OpenClaw actually used.
   - `tool_trace.error_count` must stay `0` for cases with `max_tool_errors: 0`.
   - `openclaw-whatsapp-nlm-validation-*.json` shows NotebookLM domain verdicts,
     failed case ids, warnings, and source-grounding gaps.
4. Apply the smallest fix in one of these places:
   - `scripts/openclaw_whatsapp_bridge.py` for bridge prompt, runtime contract, model/thinking/session handling.
   - OpenClaw `wa` agent configuration for KB/tool availability.
   - Backend settings only if the Fly webhook is sending the wrong payload.
5. Re-run the exact failed cases with `--max-cases` or a temporary case file until they pass.
6. Restart the local bridge only after tests pass:

```bash
install -m 700 scripts/openclaw_whatsapp_bridge.py ~/.openclaw/bin/openclaw_whatsapp_bridge.py
launchctl kickstart -k "gui/$(id -u)/com.nuzantara.openclaw-whatsapp-bridge"
curl -fsS http://127.0.0.1:8789/health
```

## Safety rules

- Do not put secrets in reports.
- Do not include raw WhatsApp corpus content in eval cases.
- Do not make the bridge send WhatsApp messages directly; Fly remains responsible for Meta delivery.
- The bridge must pass `--channel whatsapp`, `--to`, `--session-key`, `--model`, and `--thinking` to OpenClaw.
- The bridge session key is scoped per inbound message id. Backend-provided
  recent history is the memory source; per-message OpenClaw isolation prevents
  stale MCP transports from leaking across WhatsApp turns.
- The bridge must not pass `--deliver`; otherwise OpenClaw and Fly could both send a reply.
