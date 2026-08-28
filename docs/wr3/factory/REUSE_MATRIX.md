# Zantara Video Factory V3 — Reuse Matrix

- Audit baseline: `f8c158e198b1908e71c35bba4803360af883fbd4`
- Scope: minimum reusable surface for the first Factory V3 execution
- Method: static, read-only inspection of the baseline tree
- Decision vocabulary:
  - `REUSE`: use the existing component and contract without changing its responsibility.
  - `WRAP`: keep the component behind a thin Factory lifecycle or adapter.
  - `EXTEND`: retain the component but add a missing contract field, transition, or enforcement point.
  - `MISSING`: no executable component satisfying the requirement exists at the baseline.

## First-execution boundary

The first execution may use editorial model calls only for independent topic proposal,
comparison, scoring, and quorum. Those calls must use public, non-PII editorial context and
must stop at `TOPIC_APPROVAL_REQUIRED`.

The first execution must not invoke:

- NotebookLM or regulatory grounding;
- production image, video, voice, music, subtitle, or other media generation;
- Google Flow or FlowKit, including zero-credit or placeholder render paths;
- clip rendering, identity verification, audio production, or assembly;
- upload, publication, deployment, or outbound notifications.

The zero-spend and no-publish switches recorded in `docs/wr3/factory/FACTORY_STATE.md`
remain authoritative.

## Matrix

| Requirement                | Existing component and entrypoint                                                                                                            | Class     | First-execution use                                                                                    | Verified gap at baseline                                                                                                                                                                                   |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Factory lifecycle state    | Current-lane seed: `docs/wr3/factory/FACTORY_STATE.md` (not present at the baseline)                                                         | `MISSING` | Persist the current phase and stop state in the new control plane.                                     | No executable Factory/Season state machine exists at the baseline.                                                                                                                                         |
| Event transport            | `scripts/wr3_supervisor.py`: `publish()`, `route_event()`, `run_supervisor()`                                                                | `WRAP`    | Do not start it. Retain it for a later production phase.                                               | It is a transport supervisor, not a Factory controller; prompt routing contains stale sequencing and no topic-approval gate.                                                                               |
| Durable event ownership    | `scripts/wr3_supervisor.py`: `_reserve_outbox()`                                                                                             | `EXTEND`  | Not used.                                                                                              | `FOR UPDATE SKIP LOCKED` has no persisted claimed/reserved state; multi-supervisor ownership is best effort. Reconciliation is limited to a recent, bounded window.                                        |
| Typed agent contracts      | `scripts/wr3_contracts.py`: contract dataclasses and loader                                                                                  | `REUSE`   | Use only as static contract inventory.                                                                 | Runtime validation may be skipped when `jsonschema` is unavailable; critic is not classified as a gate.                                                                                                    |
| Route registry             | `docs/wr3/contracts/_router.yaml`                                                                                                            | `EXTEND`  | No event dispatch.                                                                                     | The WR2 route exists, but the supervisor has no WR2 companion branch and falls through to a no-op prompt.                                                                                                  |
| Season 01 editorial ledger | No matching component under `scripts/` or `docs/wr3/`                                                                                        | `MISSING` | Create a compact ledger for recommended topics, reserves, lineage, scores, quorum, and approval state. | The credit ledger is financial and must not be overloaded with editorial state.                                                                                                                            |
| Human topic approval gate  | No executable gate at baseline                                                                                                               | `MISSING` | End the run at `TOPIC_APPROVAL_REQUIRED`.                                                              | Existing gates cover render spend and pre-render quality, not editorial approval.                                                                                                                          |
| WR2 claim provenance       | `scripts/wr2_claims.py`: `resolve_primary_claim_ids()`                                                                                       | `REUSE`   | Reuse identifiers only if the editorial input already carries verified WR2 claims; do not publish.     | Claim lineage is not propagated safely into the current WR3 manifest normalizer.                                                                                                                           |
| WR2 companion translation  | `scripts/wr3_companion_dispatcher.py`: `dispatch_companion()`; `docs/wr3/contracts/modes/companion-mode.yaml`                                | `WRAP`    | Do not invoke during topic selection.                                                                  | No production caller was found; the CLI is dry-run only, and the supervisor does not dispatch to it.                                                                                                       |
| WR2 outbox emission        | `scripts/wr2_ig_publish.py`: payload builder and `_emit_wr3_companion_event()`                                                               | `REUSE`   | Keep disabled.                                                                                         | The emitter runs after outward WR2 publication, so it cannot be the first-execution entrypoint. Migration `186_wr2_content_published_outbox.sql` validates only `slug`, not every documented required key. |
| Regulatory grounding       | `scripts/wr3_nlm_subprocess.py`: `query_nb()`, `scrub_for_brief()`, `persist_private_sources()`; `docs/wr3/contracts/brief-interpreter.yaml` | `WRAP`    | Prohibited until after topic approval.                                                                 | The privacy split is reusable, but no deterministic Factory grounding coordinator or claim-ledger transition exists.                                                                                       |
| Episode manifest           | `scripts/wr3_episode_manifest.py`: `ManifestBuilder`, `validate_manifest()`, `finalize_episode_manifest()`                                   | `EXTEND`  | Do not finalize an episode manifest.                                                                   | Missing Factory phase, Season/topic lineage, language/cut lineage, originality, and wardrobe fields. The finalizer has no production caller.                                                               |
| Manifest claim extraction  | `scripts/wr3_episode_manifest.py`: `_extract_claim_ids()`                                                                                    | `EXTEND`  | Not used.                                                                                              | It does not consume the companion brief's top-level `primary_claim_ids`, so claim lineage can be lost.                                                                                                     |
| Spend authority            | `scripts/wr3_spend_authority.py`: `assert_spend_authorized()`                                                                                | `REUSE`   | Preserve as a downstream hard gate; do not request a token.                                            | No first-execution gap. Zero-spend refusal is already fail-closed.                                                                                                                                         |
| Pre-render gate            | `scripts/wr3_gatekeeper_check.py`; `docs/wr3/contracts/pre-render-gatekeeper.yaml`                                                           | `REUSE`   | Prohibited because no render phase is entered.                                                         | Spend/quota/ledger checks are reusable. The external cliche library is not wired; only inline rules are enforced.                                                                                          |
| Flow/FlowKit generation    | `scripts/wr3_flowkit_client.py`: `_generate_start_image()`, `_generate_video()`, `submit_clip()`, `render_shot_pack()`                       | `REUSE`   | Strictly prohibited.                                                                                   | Spend authorization is correctly checked before remote generation, but this is a later production component, not an editorial tool.                                                                        |
| Render orchestration       | `scripts/wr3_render_episode.py`                                                                                                              | `WRAP`    | Strictly prohibited.                                                                                   | The render loop does not invoke the identity verifier or persist an identity-approved clip transition.                                                                                                     |
| ArcFace identity check     | `scripts/wr3_arcface_verify.py`: `verify_clips_dir()`                                                                                        | `WRAP`    | Strictly prohibited.                                                                                   | The verifier exists but is not wired into the render lifecycle; its CLI only reports configuration.                                                                                                        |
| Holistic identity review   | `docs/wr3/contracts/clip-renderer.yaml`                                                                                                      | `MISSING` | Strictly prohibited.                                                                                   | The VLM holistic check is contractual prose without a connected executable implementation.                                                                                                                 |
| Audio contract             | `docs/wr3/contracts/audio-asset-producer.yaml`                                                                                               | `EXTEND`  | Strictly prohibited.                                                                                   | The contract consumes `pre_render_ready` and claims parallel execution, while its required inputs already include rendered clips.                                                                          |
| Voice generation           | `scripts/wr3_chatterbox_runner.py`: `generate_voiceover()`                                                                                   | `EXTEND`  | Strictly prohibited.                                                                                   | The existing path defaults to English and explicitly does not support Indonesian output.                                                                                                                   |
| Assembly primitives        | `scripts/wr3_ffmpeg_wrapper.py`: `assemble_master()`, `export_all_variants()`                                                                | `WRAP`    | Strictly prohibited.                                                                                   | Reusable ffmpeg primitives exist, but no connected post-assembler executable or durable join coordinates clips and audio.                                                                                  |
| Assembly contract          | `docs/wr3/contracts/post-assembler.yaml`                                                                                                     | `EXTEND`  | Strictly prohibited.                                                                                   | It does not emit a concrete transition to critic, and the required clip/audio join is not implemented.                                                                                                     |
| Critic rubric              | `docs/wr3/contracts/critic.yaml`                                                                                                             | `MISSING` | Strictly prohibited.                                                                                   | The rubric exists, but no production critic executable, consumer, event emitter, or retry map exists.                                                                                                      |
| Multilingual cut intent    | `language_cuts` in companion-mode and `scripts/wr3_companion_dispatcher.py`                                                                  | `MISSING` | No media cuts are produced.                                                                            | No downstream consumer, per-language manifest fields, cut hashes, or two-cut assembly coordinator exists.                                                                                                  |
| Financial credit ledger    | `scripts/wr3_credit_ledger.py`                                                                                                               | `REUSE`   | Do not create reservations or spend entries.                                                           | Correct for spend accounting only; it is not an editorial or Season ledger. Actual clip cost is not directly measured in every path.                                                                       |

## Minimum first-execution build

Only the following new control-plane artifacts are justified before topic approval:

1. a thin Factory lifecycle wrapper with monotonic, resumable phases;
2. a Season 01 editorial ledger separate from the financial credit ledger;
3. a hard `TOPIC_APPROVAL_REQUIRED` terminal gate for the first execution;
4. bounded editorial quorum outputs with provenance and deterministic scores.

Everything downstream remains dormant and is integrated only after an explicit later-phase
decision.

## Evidence commands

The audit used only baseline-tree reads:

```bash
git show f8c158e198b1908e71c35bba4803360af883fbd4:<path> | nl -ba
git grep -n '<pattern>' f8c158e198b1908e71c35bba4803360af883fbd4 -- scripts docs/wr3
git ls-tree -r --name-only f8c158e198b1908e71c35bba4803360af883fbd4
```

No matching Season ledger or topic-approval implementation was found with:

```bash
git grep -ni \
  -e 'season.*ledger' \
  -e 'ledger.*season' \
  -e 'topic_approval' \
  -e 'topic approval' \
  f8c158e198b1908e71c35bba4803360af883fbd4 -- scripts docs/wr3
```
