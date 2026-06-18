---
date: 2026-06-16
status: IMPLEMENTED V0.1 DRY-RUN, REVIEWED BY 4-LLM PANEL
owner: Nuzantara autonomous ops
scope: Symbiosis / Genome / Cell learning loop, Skill Coach dry-run evaluator, redacted evidence cards
out_of_scope: installing Hermes as a runtime, automatic skill activation, direct HGT publication, raw customer/OSINT export
---

# SPEC: Symbiosis / Genome / Cell Skill Coach

## 0. Decision

Do not install Hermes as a replacement agent.

Steal the strongest principle from Hermes: successful work must become reusable
operational skill. In Nuzantara this belongs inside the organism we already built:

- **Symbiosis** defines the law and safety perimeter.
- **Genome** stores trajectories, skills, scars, and future skill state.
- **Cells** produce trajectories and later consume approved skills.
- **Skill Coach** is a sidecar reviewer that converts trajectory-derived proposals
  into redacted evidence cards for Zero/admin review.

V0.1 is deliberately dry-run. It produces evidence, not active skill mutation.

## 1. Problem

Nuzantara already has cells, trajectories, HGT, and a skill registry, but the loop is
not closed enough:

1. A cell succeeds at a task.
2. The result may be logged as trajectory memory.
3. A separate aggregator can infer skill-creation proposals from repeated success.
4. There was no dedicated coach layer that asks:
   - Did this really work more than once?
   - Did matching history include harm or false application?
   - Is the proposal safe to show in an admin surface?
   - Is the artifact free of clear customer data before it becomes shareable?

Hermes is useful as a mental model because it treats the agent as something that
accumulates competence. The implementation must remain native to Nuzantara because
our laws, Genome schema, cells, worktree discipline, and data boundary already exist.

## 2. Existing Ground

The repo already had the first half of the loop:

- `apps/backend-rag/backend/scripts/experience_to_skill_aggregator.py`
  reads active Genome rows of `type='trajectory'`.
- It clusters successful trajectories by `(cell_origin, tags)`.
- It writes JSONL proposals to
  `~/.nuzantara/skill_creation_proposals.jsonl`.
- It is already propose-only and does not create active skills.

Therefore V0.1 does not duplicate aggregation. It adds the missing coach/evidence
gate between "proposal exists" and "Zero might approve this into a real skill".

## 3. Architecture

```
Cell work
  -> trajectory rows in Genome SQLite
  -> experience_to_skill_aggregator.py
  -> skill_creation_proposals.jsonl
  -> SkillCoachService dry-run evaluator
  -> skill_coach_evidence.jsonl
  -> admin-only read endpoint
  -> future Zero approval / promotion pipeline
  -> active Genome skill + optional HGT publication
```

The key boundary is after `SkillCoachService`: V0.1 stops at redacted evidence.
Nothing is activated.

## 4. Components

### 4.1 Skill Coach service

Path:

- `apps/backend-rag/backend/services/skill_coach/service.py`
- `apps/backend-rag/backend/services/skill_coach/models.py`

Responsibilities:

- Read trajectory-derived proposals.
- Read active trajectory rows from the Genome SQLite database.
- Match each proposal against historical trajectories by cell and tags.
- Compute evidence counters.
- Decide one dry-run status:
  - `proposed`
  - `shadow_eligible`
  - `rejected`
- Redact or reject any evidence card that contains clear customer-data markers.
- Write evidence cards as JSONL outside the repo.
- Read evidence cards back for admin surfaces, rescanning stored JSON before return.

Non-responsibilities:

- No active skill write.
- No Genome mutation.
- No HGT event.
- No LLM synthesis.
- No raw trajectory payload in output.

### 4.2 CLI evaluator

Path:

- `apps/backend-rag/backend/scripts/skill_coach_evaluate_proposals.py`

Usage:

```bash
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. python backend/scripts/skill_coach_evaluate_proposals.py
```

Default paths:

- `EXPERIENCE_DB_PATH=~/.nuzantara/experience.db`
- `SKILL_CREATION_PROPOSALS_PATH=~/.nuzantara/skill_creation_proposals.jsonl`
- `SKILL_COACH_EVIDENCE_PATH=~/.nuzantara/skill_coach_evidence.jsonl`

The CLI reads proposal JSONL, evaluates against Genome trajectory history, then
writes evidence JSONL. It logs counts and line/index positions only. It does not log
raw proposal lines.

### 4.3 Admin endpoint

Path:

- `apps/backend-rag/backend/app/routers/skill.py`

Endpoint:

```http
GET /api/skill/creation-proposals?status=shadow_eligible&limit=100
```

Properties:

- Admin-only via `_require_skill_admin`.
- Read-only.
- Returns validated, re-scanned evidence cards.
- Does not approve, activate, or publish.

## 5. Evidence Model

`SkillCoachEvidence` contains only aggregate-safe fields:

- `proposal_id`
- `skill_id`
- `cell`
- `tags`
- `scope`
- `status`
- `source_trajectory_ids`
- `preconditions`
- `procedure`
- `success_criteria`
- `confidence`
- `redaction_status`
- `redaction_findings`
- `support_count`
- `hurt_count`
- `false_apply_count`
- `neutral_count`
- `history_sample_size`
- `decision_reason`
- `created_at`

Important constraints:

- `confidence` is capped at `0.5` in dry-run.
- `source_trajectory_ids` are intersected with matching history, deduplicated,
  rescanned, and capped to 20.
- Raw trajectory payload is never copied into the evidence card.
- Malformed JSONL rows are skipped with sanitized warnings.

## 6. Status Rules

Default `min_support` is 3.

| Condition | Status | Reason |
|---|---|---|
| Proposal or serialized evidence contains clear customer-data markers | `rejected` | unsafe to expose |
| Matching history includes `failure` or `partial` | `rejected` | historical harm exists |
| Clean matching history has at least 3 successful supports | `shadow_eligible` | enough clean evidence for shadow mode |
| Clean but below support threshold | `proposed` | evidence exists but not enough support |

Counters:

- `support_count`: matching trajectories with `outcome == "success"`.
- `hurt_count`: matching trajectories with `outcome in {"failure", "partial"}`.
- `false_apply_count`: matching trajectories with `outcome == "failure"` only.
- `neutral_count`: matching history not counted as support or harm.

## 7. Law 2 Update

Law 2 was corrected in `SYMBIOSIS.md`.

The intended rule is not "no customer data can ever be touched by any system".
The intended rule is:

- OSINT/intelligence data does not leave the Pro.
- Customer/personal data can be processed only inside the authorized organ that
  needs it.
- No LLM, agent, or tool may transcribe sensitive customer/personal data in clear
  into outputs, logs, skills, insights, HGT, frontend, or shared artifacts.
- Shared skill artifacts contain operational knowledge and redacted references,
  not raw data.

This rule applies to every LLM path in the organism, not only to Hermes-like agents.

## 8. Safety Design

### 8.1 No raw data path

The coach never copies raw trajectory body into a public artifact. It reads proposal
fields, evaluates counters, and emits bounded evidence.

### 8.2 Redaction before serialization

The implementation scans:

- proposal id
- skill id
- cell
- scope
- tags
- source trajectory ids
- preconditions
- procedure
- success criteria

If clear customer-data markers are found, the card is rejected and sensitive fields
are replaced with stable redacted identifiers or redacted text.

### 8.3 Redaction after serialization

After building the Pydantic model, the implementation scans the serialized JSON
again. If leakage is detected at that final boundary, it returns a fully redacted
rejected card.

### 8.4 Read-side guard

The admin endpoint does not trust the JSONL file blindly. Stored cards are validated
with Pydantic and scanned again before being returned.

### 8.5 Dry-run confidence

Dry-run evidence can help review, but it must not pretend to be a curated skill.
For that reason confidence is capped at `0.5`.

## 9. Promotion Model

V0.1 stops before promotion. Future states can be added only after this evidence
surface proves useful.

Proposed future states:

- `promoted`: Zero/admin approved the evidence card.
- `active`: a real Skill Registry entry exists and passed admission checks.
- `deprecated`: skill exists but should no longer be applied.
- `scarred`: skill caused harm and produced a cicatrix/scar.

Future promotion requirements:

1. Admin/Zero approval.
2. Law 2 output scan.
3. Skill Registry validation.
4. Admission test through `packages/cell-core`.
5. Shadow-mode execution before active use.
6. Metrics before/after per Symbiosis Law 7.
7. HGT publication only after the active skill is validated.

## 10. Review Panel

The code/spec were reviewed with four independent LLM routes. Final review was
rerun after the admin-gate/counter patches.

| Reviewer | Route | Verdict | Applied action |
|---|---|---|---|
| Claude | Requested `opus-mythos`; model unavailable. Opus route hung twice, so Claude Sonnet was used as fallback. | Conditional pass | Added admin guard to `/merge-proposals`; zeroed counters in fully redacted cards. |
| Gemini | `agy` Gemini route, compact JSON blocker review | Pass | No blocker; documented heuristic redaction and proposal-noise risks. |
| Codex | GPT-5.5 via `codex exec`, prompt-only blocker review | Pass | No blocker after Claude patch. |
| DeepSeek | `deepseek-v4-pro`, compact JSON blocker review | No blockers | No patch required. |

Earlier review also caught `false_apply_count` semantics; fixed to count only
`outcome == "failure"` while `hurt_count` counts `failure` and `partial`.

Residual risks accepted for V0.1:

- Regex DLP is a heuristic, not a complete privacy classifier.
- JSONL is a local dry-run artifact, not a concurrent production queue.
- `fetchall()` can be replaced with streaming if the Genome trajectory table grows.
- Matching by cell+tags is intentionally conservative and may miss semantically
  equivalent skills.
- The admin guard depends on the normal authenticated backend context.
- Source trajectory ids must remain non-customer-derived identifiers at the Cell
  layer; the coach scans obvious cleartext markers but does not prove semantic
  unlinkability of opaque ids.

These are acceptable because V0.1 does not activate skills, mutate Genome, or publish
HGT.

## 11. Tests

Added unit coverage:

- `apps/backend-rag/backend/tests/unit/services/skill_coach/test_service.py`
- `apps/backend-rag/backend/tests/unit/scripts/test_skill_coach_evaluate_proposals.py`
- `apps/backend-rag/backend/tests/unit/app/routers/test_skill.py`

Covered behaviors:

- Three clean successes make a proposal `shadow_eligible`.
- Failure history rejects the proposal.
- Partial history counts as hurt but not false apply.
- Low support remains `proposed`.
- Clear customer data causes rejection without echoing the value.
- Redaction scans every output field before serialization.
- Evidence cards do not include raw trajectory payload.
- Source trajectory ids must match history and are capped.
- JSONL read path filters by status.
- Unsafe manually edited evidence rows are skipped.
- Malformed JSONL warnings do not log raw line content.
- CLI writes redacted evidence cards.
- Router requires admin and returns evidence cards.

## 12. Acceptance Criteria

V0.1 is accepted when:

1. The existing aggregator remains propose-only.
2. Skill Coach writes only redacted evidence cards.
3. No active skill is written by the coach.
4. No HGT event is published by the coach.
5. Admin endpoint is read-only and admin-only.
6. Law 2 wording reflects no clear sensitive-data transcription across all LLMs.
7. Targeted tests pass.
8. Ruff passes on touched Python files.

## 13. Operator Summary

In plain terms:

Nuzantara already has memories of work. The new Skill Coach looks at repeated success
and says, "this might become a skill", but it does not let the organism learn blindly.
It checks whether the pattern was clean, whether it failed before, whether it has
enough support, and whether the resulting artifact is safe to show.

That is the Hermes principle, translated into Symbiosis/Genome/Cell.
