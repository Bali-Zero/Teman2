# WR3-F20 — manifest validator is dead code, incompatible with the only real manifest on disk

> **Status: SPEC READY — NOT EXECUTED.** Docs-only finding. The fix
> (deterministic builder OR relaxed validator + wiring into the pipeline/CI) is
> an operator decision — no code change is shipped by this spec.
>
> Date: 2026-06-12 · Family: WR3 feature-debt (sibling: WR3-F18, WR3-F21) ·
> Audit source: Fable-5 system audit 2026-06-11 (finding F20) ·
> Index: `WR3-DEBT-INDEX.md`.

## 1. Context

`scripts/wr3_episode_manifest.py` (175 lines) defines a strict episode-manifest
schema + validator + builder, but **no live pipeline calls the builder**, and
the **only real manifest on disk would fail the validator immediately** — so
the validator is dead code guarding an artifact it was never wired to produce.

Verified on disk:

- **`MANDATORY_FIELDS`** tuple (`:20-39`) — 18 fields:
  `episode_id, topic, audience_segment, duration_master_ms, created_at,
  completed_at, claim_ids, asset_hashes, variants_delivered, variants_missing,
  contract_versions, agents_invoked, total_cost_usd, flow_credits_spent,
  critic_verdict, identity_overall_cosine_avg, lufs_measured, wr3_room_version`.
- **`validate_manifest()`** (`:123-142`) gates:
  - `:125` — raise on any missing mandatory field;
  - `:129` — `critic_verdict` must be in
    `{"PENDING", "PASS", "FAIL", "DEGRADED"}`;
  - `:134` — `wr3_room_version` must equal `CURRENT_ROOM_VERSION == "0.1.0"`;
  - `:141` — `claim_ids` must be non-empty
    ("episode must cite at least one fact").
- **`ManifestBuilder.finalize/write`** (`:87-116`) — the deterministic path
  that would emit all 18 fields + sha256 asset hashes.

### The gap

- **No live pipeline calls `ManifestBuilder`.** The real manifest is written by
  a **free-form LLM subagent** (`wr3-post-assembler`), prompted as a **string**
  at `scripts/wr3_supervisor.py:403` — NOT via a `ManifestBuilder.write()` call.
- The only real manifest on disk,
  `apps/war-room/output/episode/content-creator-3-roads-2026-05-29/episode_manifest.json`,
  has **17 keys** and shares **only 2 NAMES** with the schema
  (`episode_id`, `critic_verdict`) →
  **16 of 18 mandatory fields MISSING**, `claim_ids` = `None`,
  `wr3_room_version` = `None`, and `critic_verdict` = `"PASS-WITH-NOTES"`
  (**not in the allowed set**). `validate_manifest()` would raise on the very
  first gate (`:125` missing-fields), and again on `:129`, `:134`, `:141`.
  (Its actual keys: `episode_id, slug, assembled_at, master_mp4, duration_s,
  variants, variants_detail, variants_failed, clips_count, vo_lufs, vo_path,
  music_path, subtitles_ass, identity_gate, render_cost_cr, degradation_flags,
  critic_verdict`.)
- The validator is wired into **NO pipeline / CI / cron**. The only callers are
  the module's own `__main__` smoke block, unit tests, and 2 lint scripts that
  import the `MANDATORY_FIELDS` constant. It is **dead code**.
- The episode path `com.balizero.wr3.supervisor` is **FAILED, exit=78** — so
  even the producer that would emit a manifest is not running (shared upstream
  blocker with F21 — see Index cross-cutting note).

## 2. Why this matters

A validator that no pipeline calls, guarding a schema no producer emits, is a
**false safety net**: it looks like manifest integrity is enforced, but the one
real manifest on disk is structurally incompatible and would be rejected on
sight. Worse, it hides the real divergence — the LLM-authored manifest and the
strict schema agreed on **2 field names out of 18**. If the validator were ever
wired in as-is, every episode would hard-fail at assembly.

## 3. Fix options (operator picks; nothing shipped here)

- **(a) Make the producer deterministic** — have `wr3-post-assembler` call
  `ManifestBuilder.write()` (instead of a free-form prompt) so all 18 fields +
  sha256 asset hashes + `claim_ids` are emitted by construction. This makes the
  LLM-authored, schema-divergent manifest impossible.
- **(b) Relax the validator to the real agent output** — accept the field names
  the assembler actually produces, map `slug`→`topic`/etc. where they
  correspond, and add `"PASS-WITH-NOTES"` to the allowed `critic_verdict` set
  **if** that verdict value is legitimate (it currently is not in the schema's
  enum).
- **Either way:** wire `validate_manifest()` into the supervisor's
  `assembly_ready → critic_verdict` transition **and/or** a CI gate, so the
  validator stops being dead code and actually rejects malformed manifests at
  the moment of assembly.

## 4. Guardrails

- **Do NOT execute autonomously.** (a) vs (b) is a real design fork: (a) forces
  the agent to emit a rigid contract (more robust, less LLM flexibility); (b)
  loosens the contract to match reality (faster, weaker guarantees). The
  operator decides which side the WR3 manifest contract lives on.
- If (b) is chosen, adding `"PASS-WITH-NOTES"` to the allowed verdict set must
  be a deliberate decision — it is currently NOT in `{PENDING, PASS, FAIL,
  DEGRADED}`, and silently widening a verdict enum changes what "passed" means
  to every downstream consumer.
- **Order of operations:** the WR3 supervisor (`com.balizero.wr3.supervisor`
  exit=78) must be revived FIRST — wiring a validator into a dead pipeline
  changes nothing observable, and there are no fresh episodes to validate until
  the supervisor produces them.

## 5. Reference

- Validator/builder: `scripts/wr3_episode_manifest.py`
  (`MANDATORY_FIELDS` `:20-39`, `validate_manifest()` `:123-142`,
  `ManifestBuilder.finalize/write` `:87-116`,
  `CURRENT_ROOM_VERSION == "0.1.0"`).
- Real (incompatible) manifest:
  `apps/war-room/output/episode/content-creator-3-roads-2026-05-29/episode_manifest.json`
  (17 keys, 2 names shared, `critic_verdict="PASS-WITH-NOTES"`,
  `claim_ids=None`, `wr3_room_version=None`).
- Free-form producer prompt: `scripts/wr3_supervisor.py:403`
  (a prompt string, NOT a `ManifestBuilder` call).
- Failed pipeline: `com.balizero.wr3.supervisor` exit=78 (shared upstream
  blocker — see `WR3-DEBT-INDEX.md`).
- Audit: Fable-5 system audit 2026-06-11, finding F20.
