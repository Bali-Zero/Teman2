VERDICT: BLOCK

1. BLOCKER: Missing modules in the provisioning install list
   File: `scripts/provision_zantara_codex.sh`
   Failure scenario: `_support_signal.py` includes `evaluate_support`, a cloud-side function that invariably imports internal backend modules (like Pydantic, database models, or telemetry) that are NOT provisioned to the daemon's restricted `stdlib + httpx` environment. Importing `_support_signal` in `wa_codex_daemon.py` will instantly crash the daemon on startup with a `ModuleNotFoundError`.
   Minimal fix: Extract the shared runtime components (`CodexSupportJudge`, `majority`, `support_inputs_from_wire`, etc.) into a pure-stdlib module (e.g., `_support_judge.py`) and provision that file instead.

2. MAJOR: Uncaught exception on lone surrogates breaks daemon's existing error handling
   File: `apps/backend-rag/backend/services/integrations/wa_codex_daemon.py`
   Failure scenario: If a prompt injection tricks the model into generating a lone UTF-16 surrogate, `encode_completion` will raise a `UnicodeEncodeError` when encoding the canonical JSON for the MAC. Because the `encode_completion` call was placed in the `else:` block, it sits outside the `try...except Exception:` handler. The exception escapes and crashes the daemon's main polling loop (DoS).
   Minimal fix: Move the `encode_completion` invocation and size-check logic inside the `try` block so exceptions are safely caught and reported as `cli_failure`.

3. MAJOR: Size-cap checks measured on the wrong bytes
   File: `apps/backend-rag/backend/services/integrations/wa_codex_daemon.py`
   Failure scenario: The byte cap evaluates `len(_encode_body({"result_text": envelope}))`, which measures a dictionary with a single key. However, `_complete` ultimately builds an HTTP payload that also includes `job_id`, `completion_key`, `error_class`, and `exec_ms`. A borderline envelope will clear the check but still trigger a `413` at the router because the actual payload is larger, abandoning the job.
   Minimal fix: Construct the full exact dictionary as `_complete` does before calling `_encode_body`, or explicitly deduct an overhead margin from `_RESULT_BYTES_MAX`.

4. MINOR: Budget/timeout arithmetic errors (negative or zero timeouts)
   File: `apps/backend-rag/backend/services/integrations/wa_codex_daemon.py`
   Failure scenario: If `budget_s <= 0` (e.g. the broker lease expired before the daemon began processing the claim), `judge_budget` will evaluate to `<= 0`. This is passed blindly to `CodexSupportJudge(timeout_s=judge_budget)`. Depending on the client implementation, a `<= 0` timeout can be treated as an infinite timeout, causing the daemon to hang indefinitely on an expired job. Generation handles this properly (`if remaining <= 0`), but the judge does not.
   Minimal fix: Insert an early return `if budget_s <= 0:` check prior to initializing the judge, or clamp `judge_budget` to a strictly positive minimum value.
