# Native App Server qualification evidence

This directory records the opt-in synthetic native transport experiment described
in [native-shadow.md](../../docs/architecture/dual-consul/native-shadow.md).
The scope is non-PII text, zero delegates, no external effect authority, and no
fleet activation. Runtime identity is not inference-response identity.

The final native source verdict is **PASS**. The first review was
**PASS-WITH-CONDITIONS**; its producer provenance, catalog reproducibility, and
identity vocabulary conditions were corrected in `c03b182fcd` and closed by the
independent native delta review. The table describes regenerated producer-bound
proofs and passing current-source tests. The reviewer inspected supplied source
and evidence; it did not run tests or recompute hashes. Those checks were
performed separately by the conductor and evidence author.

| Artifact | Observation | Limitation |
| --- | --- | --- |
| [native-invoke.json](native-invoke.json) | Two completed Terra `medium` turns, one native thread, final cumulative native total 15,945 tokens; local process group stopped after context exit. | `inference_model: null`; only same-process continuity within a temporary native home. |
| [native-cancel.json](native-cancel.json) | Local process group stopped; `interrupt_acknowledged: false`, `interrupt_error_code: rpc_error`; thread and turn IDs retained. | Native interrupt was not acknowledged. `remote_cancelled: null`, and final remote consumption is unknown. |
| [discovery.json](discovery.json) | Reproducible `--catalog`: nine models including hidden entries, complete catalog, `catalog.requested_model_available: false` for Astra; zero inference calls. | Discovery is specific to its producer, runtime, configuration, host, and authentication context. |
| [fleet-observations.json](fleet-observations.json) | Host-specific native versions and binary digests from the conductor's read-only inspection. | Existing auth files do not prove valid access; different versions and a distinct service identity remain unqualified. |
| [parent-gate.json](parent-gate.json), [selected text](parent-gate.txt), [input](parent-gate-input.txt) | Review provenance for the preceding implementation commit. | Does not review or authorize this new native increment. |
| [validation.json](validation.json), [source-manifest.json](source-manifest.json) | 125 targeted tests passed in 2.22s; Ruff passed; eleven source/test files bound by SHA-256. | Verification applies to those recorded bytes, not subsequent changes or operational deployment. |
| [review-1.json](review-1.json), [selected text](review-1.txt), [exact compressed input](review-1-input.txt.gz) | Historical native `claude-fable-5-1`, `end_turn`, PASS-WITH-CONDITIONS; three provenance/vocabulary conditions. | Its original conditional verdict remains preserved; review 2 closes the conditions. |
| [review-2.json](review-2.json), [selected text](review-2.txt), [exact compressed input](review-2-input.txt.gz) | Native `claude-fable-5-1`, `end_turn`, PASS; all three conditions closed; eleven-file source manifest bound. | Source and selected-evidence review only; no tests or hash recomputation by the reviewer, operational qualification, or release gate publication. |

The native JSON files contain selected normalized local probe outputs.
Normalization preserves parsed values; raw-output byte equality is not
claimed. The exact frozen reviewer input is retained separately in compressed
form. Native `observed_at`
fields come from the probe start clock; they are not
separate timestamps for each event. Proof fields contain selected identifiers,
hashes, outcomes, and native counters. They contain no access credential, refresh
credential, account email, prompt text, reply text, or raw reasoning stream.
The native `input_hash` covers literal user text only. Runtime config and auth
hashes supply contextual evidence, not a full effective-prompt or history hash.
Each of the three probes records a six-module `source_producer` and
`source_verification: unchanged`, checked before and after execution. Its producer
manifest hash is distinct from the eleven-file source/test manifest. Checkpoints
use `identity_evidence: request_observed` and
`model_evidence_source: native_thread_configuration`; inference identity remains
unknown. Only final-answer text contributes to the selected output hash.

The successful native runtime was Air-M5 `codex-cli 0.147.0`. The runtime and profile
digests identify the collected configuration; they are evidence fingerprints,
not secrets or grants. The recorded model was `gpt-5.6-terra`. Astra was unavailable
in the conductor's catalog diagnostic, so no served-Astra claim is made. Different
Pro and Mini versions require their own qualification.

The corrected launcher preserves `last_refresh` while withholding refresh
authority from its temporary OAuth snapshot. Its source credential file is read
only. Earlier diagnostics that refreshed a temporary copy are not evidence of
the corrected launcher's behavior. Persisted thread history lives only inside
the disposable private native home; context cleanup removes it.

The corrected-source targeted result is **125 passed in 2.22s**. The exact
command recorded in `validation.json` is:

```sh
/Users/balizero/nuzantara/.venv/bin/python -m pytest scripts/tests/test_codex_shadow.py scripts/tests/test_codex_shadow_launch.py scripts/tests/test_conductor_app_server_rpc.py scripts/tests/test_conductor_adapter_contracts.py scripts/tests/test_codex_shadow_probe.py -q
```

The conductor ran these three native commands separately from the worktree root;
each exited zero. The first is catalog-only; the other two use the fixed synthetic
prompt. The selected JSON files preserve their parsed output values.

```sh
/Users/balizero/nuzantara/.venv/bin/python -m scripts.conductor.codex_shadow_probe --auth-home /Users/balizero/.codex --model gpt-6-astra --catalog > /tmp/dual-consul-native-catalog-bound.json
/Users/balizero/nuzantara/.venv/bin/python -m scripts.conductor.codex_shadow_probe --auth-home /Users/balizero/.codex --model gpt-5.6-terra --invoke > /tmp/dual-consul-native-invoke-bound.json
/Users/balizero/nuzantara/.venv/bin/python -m scripts.conductor.codex_shadow_probe --auth-home /Users/balizero/.codex --model gpt-5.6-terra --cancel > /tmp/dual-consul-native-cancel-bound.json
```

The launcher now rejects unexpected tool or delegation item events and shuts
down the local process group. This is an activity detector, not a distinct OS
identity or proof of preventing an external effect before its event arrives.

The selected evidence budget for this increment is **160 KiB**. Source and review
bindings retain hashes and selected public technical material; raw account
state, credentials, provider error payloads, and reasoning streams stay out.

The source review is PASS. Native cancellation remains only
partially qualified because the interrupt was not acknowledged.
A prior review, local process stop,
or successful synthetic text reply cannot supply an operational broker grant,
distinct service identity, remote cancellation proof, or deployment authority.
