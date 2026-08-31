# Zantara Video Factory V3 — Control-Plane Runbook

## Scope

`scripts/cli/factory` is the deterministic control plane around the existing WR3
specialists. It owns state, evidence hashes, reconciliation, dry-run, authorization
validation, and language-package metadata. It does not replace the WR3 supervisor,
FlowKit client, spend authority, identity gate, audio pipeline, assembler, or critic.

All commands emit machine-readable JSON. Upload, publication, deployment, and outward
messages remain disabled.

## Routine commands

Run from the repository root:

```bash
scripts/cli/factory plan
scripts/cli/factory status
scripts/cli/factory prepare S01E13
scripts/cli/factory dry-run S01E13
scripts/cli/factory validate S01E13
scripts/cli/factory package S01E13 --languages en,id
```

- `plan` validates the 20-topic recommendation set, 10 reserves, and zeroed safety switches.
- `status` reads persisted episode manifests without advancing them.
- `prepare` advances only through consecutive gates supported by hash-bound evidence.
- `dry-run` performs the same reconciliation in memory and reports zero writes, jobs,
  credits, and network calls.
- `validate` reports evidence drift and untracked MP4 files.
- `package` writes only package metadata. It verifies that the canonical English script is
  frozen and claim-bound, rejects overlapping or invalid SRT/VTT cue timing, and requires
  every translation to bind the exact English script SHA-256 and preserve its complete
  claim-ID set. Localized metadata must carry passing semantic and terminology QA. It never
  modifies the canonical English master and never uploads anything.

The emitted `metadata/language_manifest.json` follows
`docs/wr3/factory/schemas/language-package.schema.json`. Multilingual levels are explicit:

- `CANONICAL`: immutable English native-audio master, frozen transcript, SRT/VTT, and
  claim bindings;
- level 1: YouTube automatic-dubbing canary package. The command prepares translated
  captions and metadata, but does not generate a dub or perform the human YouTube action;
- level 2: manually supplied additional-language dialogue and full mix over the same
  visual master. It requires duration QA, approved voice and human review, and explicitly
  rejects any claim of perfect lip sync;
- level 3: a separate premium native-language Flow cut. It requires a target-language
  canary and all QA fields to pass. Only `SYNC_FOREGROUND` shots may be regenerated;
  `PURE_BROLL` and `TRANSITION` material is reused.

No level is inferred from whatever files happen to be present. The requested level lives
in `languages/<tag>/metadata_<tag>.json`, defaults to level 1, and is validated exactly.
Levels 2 and 3 consume only already-supplied artifacts; `package` never renders them.

## Resume after interruption

```bash
scripts/cli/factory status
scripts/cli/factory validate S01E13
scripts/cli/factory prepare S01E13
```

If `validate` reports drift, restore or explicitly replace the affected evidence. Do not
edit a stored hash to make the warning disappear. Completed render evidence may satisfy
the consecutive `RENDERING` and `RENDERED` transitions during resume; no state is skipped.

Manifest writes use a temporary file, `fsync`, and atomic replacement. An episode lock
rejects concurrent state transitions.

## State sequence

```text
PROPOSED -> TOPIC_APPROVED -> GROUNDED -> SCRIPT_LOCKED -> STORY_LOCKED
-> WARDROBE_LOCKED -> SHOTPACK_LOCKED -> PRE_RENDER_PASS -> READY_FOR_SPEND
-> CANARY_SUBMITTED -> CANARY_RENDERED -> CANARY_QA_PASS -> RENDER_AUTHORIZED
-> RENDERING -> RENDERED -> ASSEMBLED -> FINAL_QA_PASS
-> YOUTUBE_PACKAGE_READY -> HUMAN_APPROVED
```

`READY_FOR_SPEND` never submits. `YOUTUBE_PACKAGE_READY` means local files are ready for
human handling, not uploaded or published.

## Canary boundary

The authorization record must bind one human-approved episode, one `shot_id`, exactly one
clip, a positive credit cap, and the SHA-256 of the current shot pack. Its text must be
literal:

```text
AUTHORIZE FLOW CANARY: S01E13 MAX_CREDITS: 10
```

Both `ALLOW_FLOW_SPEND=1` and `ALLOW_REAL_RENDER=1` are required, and execution is forbidden
on Air-M5. The control plane currently returns `CANARY_EXECUTOR_NOT_BOUND` before importing
the spend authority or writing its decision log. This is intentional: connect the existing
one-shot WR3/FlowKit adapter only after its measured-cost contract can enforce the stated
cap. Do not route `canary` through the whole-episode renderer.

Full rendering requires a separate episode authorization and remains outside this command
until the adapter is connected and tested.

## Current S01E13 boundary

The machine-readable pilot approval advances S01E13 only to `TOPIC_APPROVED`. The next
honest blocker is a grounded `brief.json` with verified claim IDs. Existing camera-probe
media is R&D evidence; its presence cannot skip grounding, script, story, wardrobe, shot-pack,
or pre-render gates.
