# ADR-001: Thin WR3 Factory Wrapper

- Status: Accepted for the first execution
- Date: 2026-08-29
- Audit baseline: `f8c158e198b1908e71c35bba4803360af883fbd4`
- Decision owner surface: `docs/wr3/factory/`

## Context

WR3 already contains useful production components: typed contracts, PostgreSQL event
transport, spend authority, a pre-render gate, FlowKit integration, credit accounting,
ArcFace verification functions, ffmpeg primitives, WR2 claim provenance, and a companion
translation contract.

Those components do not currently form a closed production lifecycle:

- the supervisor accepts the WR2 route but does not call the companion dispatcher;
- its pre-render prompt starts audio before the audio contract's required clips can exist;
- ArcFace is not called by the render driver, and the holistic VLM identity check is not
  implemented as a connected executable;
- there is no connected post-assembler or production critic transition;
- the manifest cannot represent Factory phase, Season/topic lineage, or multilingual cuts;
- no Season ledger or human topic-approval gate exists.

Repairing every downstream gap is unnecessary and unsafe before the editorial topic set is
approved.

## Decision

Build a thin Factory control-plane wrapper around WR3. Do not replace the existing media
pipeline and do not run it during the first execution.

The wrapper owns only:

1. monotonic, resumable Factory phase state;
2. the Season 01 editorial ledger;
3. bounded editorial model fan-out and quorum;
4. deterministic topic ranking and lineage;
5. the terminal human gate `TOPIC_APPROVAL_REQUIRED`.

The existing WR3 supervisor, grounding, generation, identity, audio, assembly, and critic
surfaces remain downstream dependencies. They are neither started nor silently simulated by
the first execution.

## First-execution policy

### Allowed

Editorial model calls are allowed for:

- independent topic proposals;
- comparison and deduplication of proposals;
- deterministic scoring inputs;
- editorial quorum and dissent capture.

Inputs must be public and non-PII. Outputs must be bounded editorial artifacts with model,
prompt/version, and source lineage sufficient to resume or audit the selection process.

### Prohibited

Before explicit human topic approval, the wrapper must prohibit:

- NotebookLM and regulatory grounding;
- production image, video, voice, music, subtitle, or media generation;
- Google Flow and FlowKit calls;
- rendering, ArcFace/VLM identity checks, audio production, and assembly;
- credit reservations or spend authorization;
- uploads, publication, deployment, and outbound notifications.

This prohibition applies even when a downstream tool offers a dry-run, placeholder, or
zero-credit mode. The first execution validates editorial control, not production plumbing.

## State boundary

The minimum monotonic progression is:

```text
BOOT_AUDIT
  -> REUSE_AUDITED
  -> EDITORIAL_QUORUM_RUNNING
  -> SEASON_01_TOPICS_DRAFTED
  -> TOPIC_APPROVAL_REQUIRED
  -> STOP
```

Re-entry must read the persisted phase and ledger, verify their baseline and input lineage,
and resume only the first incomplete transition. Re-entry must never infer approval from the
presence of topic files or model output.

Only an explicit human approval record may unlock a later ADR and a later production phase.
This ADR grants no authority to render, spend, publish, upload, notify, or deploy.

## Reuse boundary

The wrapper will preserve these existing responsibilities:

- `scripts/wr3_spend_authority.py` remains the sole production spend authority;
- `scripts/wr3_gatekeeper_check.py` remains the downstream pre-render gate;
- `scripts/wr3_flowkit_client.py` remains the Flow/FlowKit generation client;
- `scripts/wr3_credit_ledger.py` remains the financial ledger;
- `scripts/wr2_claims.py` remains the WR2 claim-provenance authority;
- `scripts/wr3_arcface_verify.py` remains the ArcFace primitive;
- `scripts/wr3_ffmpeg_wrapper.py` remains the assembly primitive;
- YAML contracts under `docs/wr3/contracts/` remain the declared agent interfaces.

The wrapper must not duplicate those responsibilities. Later work may wrap or extend them
according to `REUSE_MATRIX.md`, after topic approval.

## Consequences

### Positive

- The first execution is small, reversible, zero-spend, and resumable.
- Editorial model diversity can be tested without activating production systems.
- Existing WR3 investment is preserved.
- Missing identity, audio, assembly, critic, manifest, and multilingual contracts remain
  explicit instead of being hidden behind a nominal end-to-end run.

### Costs

- Topic approval does not prove that media production is operational.
- A later production ADR must define and verify the downstream lifecycle repairs.
- The Factory wrapper adds a control-plane state surface that must remain separate from the
  WR3 financial credit ledger and episode manifest.

## Alternatives rejected

### Run the existing supervisor directly

Rejected because it has no Season/topic gate, does not dispatch WR2 companion events, and
contains an impossible audio/render ordering.

### Rebuild WR3 as a new pipeline

Rejected because spend authority, pre-render checks, FlowKit integration, credit accounting,
claim provenance, ArcFace, and ffmpeg primitives are already reusable.

### Repair every production component before topic selection

Rejected because identity, audio, assembly, critic, manifest, and multilingual work is not
required to select and approve Season 01 topics. It would expand scope and create unnecessary
production risk.

## First-execution acceptance criteria

- `REUSE_MATRIX.md` records the baseline and every required classification.
- Factory state and the Season 01 ledger can resume without rerunning completed editorial
  calls.
- The editorial quorum produces the required recommended and reserve topic sets with lineage
  and deterministic scores.
- No topic is marked approved without an explicit human approval record.
- The persisted terminal state is `TOPIC_APPROVAL_REQUIRED`.
- No NotebookLM, production generation, Flow/FlowKit, render, audio, assembly, upload,
  publication, deployment, spend, or outbound-notification path is invoked.
