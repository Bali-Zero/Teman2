VERDICT: SHIP

1. (MINOR) `apps/backend-rag/backend/services/integrations/wa_codex_leg.py:244`
   **Scenario:** Old Fly builder + New Fly worker transition drift. An old package (built before PR-2) was pushed to the `wa_outbox` retry ladder. Because the old builder did not populate the `abstain_unsupported` key in `evidence_inputs`, it is absent. The new `wa_codex_leg` picks up the job and unconditionally offers it (since the pre-offer stub is gone). The new daemon judges it as `NOT_SUPPORTED` and returns an authenticated `NOT_SUPPORTED` envelope. The leg decodes the envelope and delegates to `_stub_unsupported()`. At L244, `bool(evidence_inputs.get("abstain_unsupported"))` evaluates `bool(None)` to `False`, mislabeling the stub's evidence carrier as a non-abstain and breaking telemetry for that row.
   **Fix:** Provide a fail-closed default for the transition gap: `bool(evidence_inputs.get("abstain_unsupported", True))`.
