---
adversarial_review: codex
reviewer_seat: codex gpt-6-astra (xhigh, read-only sandbox), two rounds, 2026-09-10
author_seat: claude-fable-5-1 (owner-opened imperator window, session ec87ed52)
---

# PARABELLUM — the two-colour modus. Staff-room record, 10 September 2026

Status: DRAFT written by the Fable 5.1 imperator window (session ec87ed52, jump 3) after two
consultation rounds with Astra (`codex exec -m gpt-6-astra`, xhigh, read-only sandbox, transcripts
in the session scratchpad). Nothing here is installed or law until the doctrine PR in §6 merges.
Fable writes no code and opens no PR: a Claude ship session carries §6 and §7, Fable posts the gate.

## 0. Zero's rulings tonight (verbal, 2026-09-10 03:35-04:10 WITA, Fable window)

1. The modus is runnable in two colours, chosen by Zero with Fable and Astra at mission start.
   BLUE: Dux Opus 5 · Codex spalla · gate a fresh Opus 5 session. ORANGE: Dux Sol · Claude
   spalla · gate a fresh Sol session. Option B: in orange Sol also releases.
2. Name: PARABELLUM.
3. Fable and Astra sit only with Zero (staff room). They never fan out, never implement.
   The staff room fixes the number of battle windows (one for the backend engine, one for
   frontend+design, a third only for an independently owned organ), the team per window, the spec.
4. One window = one mandate = one organ = one worktree. Never two windows on the same path.
5. "Do not complicate your life": minimum viable set, one procedure, no second stage machine.

## 1. What the pilot measured (report on main, `research/operations/2026-09-10-pilot-mission-1-capo-vs-builder.md`)

Codex as Capo of a build did not carry it: 0 lines (spec clause), parked at the 0.4 wall with a
52-59k boot, killed at 127 s by a mandate deadline expired 21 minutes before launch. The 0.6 wall
is UNMEASURED (report §11) — the pilot closed before B-3b. Ten harness defects are in `mem`.

## 2. Verified corrections (Astra round 1, every line checked on disk by Fable)

| # | Claim Fable made | What the disk says |
|---|---|---|
| 1 | builder 0.6 fixes the Codex wall | native children hardcode 0.4 (`context_bridge.py:533`); an undeclared `dux` role falls back to 0.4 (`:719`) |
| 2 | the child cannot report, both families | Codex has an exempt checkpoint helper (`context_bridge.py:494`); Claude exempts SendMessage/TaskStop but not ToolSearch (`child_workflow.py:213`) |
| 3 | B-3 tested Sol at 0.6 | it met an expired root mandate first (report :506, :548) |
| 4 | `.lane-check.json` is a write perimeter | `scope_globs` only decides whether a check applies; out-of-scope edits are not rejected (`lane_check.py:396-419`) |
| 5 | the child hooks need lint pairs | Claude pairs exist (`declared-pairs.json:983/995/415`); CODEX_HOME pairs (`context_bridge.py`, `rpc.py`) are the missing ones |
| 6 | "merge → arm → deploy, three commands" | push, PR-open + arm, merge from the queue, deploy, prove-live (`SKILL.md:89`); the three separate commands are push, create, merge |
| 7 | amend Builder Contract §5 only | AGENTS.md §0.0 (:65) and §17.1 (:839) and `operations.md:15` repeat the ban and must move together |

Also measured tonight: `~/.codex/config.toml` on M5 defaults to `sandbox_mode = "danger-full-access"`
and `approval_policy = "never"`, `gh` holds `repo` + `workflow`, and the gate reader is
model-indifferent. The prepare-only fence is doctrine, not mechanism.

## 3. The colour table (the only thing that differs)

| Assignment | BLUE | ORANGE |
|---|---|---|
| Dux | Opus 5 xhigh | Sol (`gpt-5.6-sol`) xhigh |
| Default implementer when builders are needed | Sonnet 5 | Terra (`gpt-5.6-terra`); Sol implements directly on small work |
| Adversarial reviewer (family ≠ actual builder) | independent Codex | independent Claude via `claude` CLI OAuth |
| Final empirical gate | fresh Opus 5 session, outside the chain | fresh Sol session, outside the chain |
| Release | Dux Opus 5: opens the PR after VERIFY, arms auto-merge at once, proves live | Dux Sol: identical sequence; the gate Sol only signs, never arms or alters the candidate |
| Transport | Claude-native work + Codex review | Codex-native work + Claude OAuth review |

Identical in both colours: TRIAGE and the gear floor; the nine stages; generator ≠ grader;
final gate on every gear, never substituted for quota; mandate accounting, evidence pack,
`Bites:`, PENDING-ARMS, sibling check, stop-loss, freeze, rollback, prove-live. No automatic
colour fallback: a dead orange seat SUSPENDS, it does not turn blue.

## 4. Harness changes agreed (smallest set, ordered)

1. Reporting: exempt `ToolSearch` in `child_workflow.py` (narrowly: the discovery needed to reach
   SendMessage/TaskStop); both deny paths name counter, used/limit, role, next action.
2. Thresholds: add `dux: 0.6` to `nuzantara-context-policy.json` on the three hosts; the native
   child in `context_bridge.py` reads the policy instead of the literal 0.4.
3. Limits per mandate, declared at TRIAGE in the window spec §6: one coordinator-renewable
   absolute deadline within the appetite hours; attempts/concurrency/depth/hops; adapter tool
   ceiling plus NO ship reserve (N = 0): a child at its cap checkpoints and returns the remaining work; shipping is the Dux's and consumes the mandate budget. Same mission deadline consumed by `mandate_budget.py`
   and the Codex continuation supervisor; child active time measured, reported, never conflated.
4. Reservation identity: bind `observe()` to the returned native child identity; uncertain binding
   stays UNKNOWN (the "observed without a dispatch reservation" race).
5. Siblings at GROUND and before SHIP: open PRs' changed paths, worktree leases, native agent
   trees, `fleet --list`; timestamped in the evidence pack, one reference in `Bites:`.
6. AGENTS.md diet to an index (≤ 6 KB; keep Builder Contract, machine boundary, authority,
   worktree rule, pointers) with an explicit door to `.claude/skills/modus/SKILL.md` and the
   assigned spec. Acceptance: first measured Codex context ≤ 10% of the real window.
7. Installation parity: declared pairs for the CODEX_HOME files; fix `.codex/hooks.json`'s dead
   absolute path and prove the spalla matcher fires natively.
8. Gate receipt, first-mission floor: a PR comment by the fresh gate session carrying mission id,
   colour, HEAD sha, gate thread id, commands run with exit codes, verdict; the gate re-checks the
   clean candidate against the current PR HEAD before posting. Publish with
   `scripts/harness_fable_gate.py`: for PASS use `--description` with a short comment reference
   (140-char cap, `--conditions-ref` is silently ignored on PASS — `build_description()`,
   line 102); for PASS-WITH-CONDITIONS `--conditions-ref` is mandatory. Native-identity /
   HEAD-bound receipt validation in `evidence_pack_lint.py` becomes a PENDING-ARMS row, not a
   launch precondition.

Rejected: a second Capo/support tier; a blanket ship-tool exemption; `ORCHESTRATE_GATE_OFF`
or any bypass flag in the launcher; a new attestation service; a planning database.

## 5. Battle-window spec — seven sections, one to two pages, one file per window

1. **Mandate** — mission/window id, colour, organ, objective, gear, host, worktree/branch, base sha, one sentence of what success changes.
2. **Owned perimeter** — writable paths, forbidden/shared paths, one owner per shared schema, fixture, generated file, lockfile. Until a real fence exists, VERIFY and the gate compare changed paths against this list by hand.
3. **Sibling contract** — schema/version and fixture hashes, success/error responses, producer/consumer ownership, compatibility required before either side merges. Frozen before BUILD; a change goes back to the staff room through Zero.
4. **Acceptance** — falsifiable checks incl. one negative case, one integration check, one production observation; fixture success ≠ live integration.
5. **Team** — Dux, optional implementer, adversarial reviewer, gate, release; effective model/effort and thread ids recorded at start.
6. **Appetite and stop-loss** — hours ceiling, absolute deadline, token allowance, attempts/concurrency/depth/hops, adapter tool ceiling and reserve, renewal authority, checkpoint destination (fleet mailbox).
7. **Evidence and release** — pack/ledger refs, `Bites:` consumer + observation, merge order (backend first only when backward-compatible; shared lockfile serialized), gate receipt, deploy path, rollback trigger.

## 6. Doctrine PR (one concern: authority; atomic)

| File | Amendment |
|---|---|
| `docs/rules/RULINGS.md` | dated 2026-09-10 PARABELLUM ruling; "Routing vigente" updated; Claude-only gate/release clauses superseded; staff room = Zero only |
| `docs/architecture/dual-consul/army-map.md` | Dux, reviewer, gate, release rows parameterised by colour |
| `CLAUDE.md` Builder Contract §5 | the appointed orange Sol seat ships; every other external seat stays prepare-only |
| `AGENTS.md` | identical canon copy; §0.0 and §17.1 reconciled; door to modus + spec |
| `GEMINI.md`, `QWEN.md` | identical canon copy; no release authority for Gemini/Qwen |
| `docs/rules/operations.md` | external-seat caveat and ship sequence wording reconciled |
| `.claude/skills/modus/SKILL.md` | one skill; VERIFY, SHIP+ARM, arsenal rows read the colour table |
| `FLEET_TOPOLOGY.json` | blue chain untouched; new `gear3_final_gate_orange` Sol-only, no cross-colour fallback |
| `PENDING-ARMS.md` | three open observations: native orange execution/return · independent HEAD-bound gate + authorized release · per-profile fleet installation/auth parity |

`harness-floor.yml` needs no colour branch (model-indifferent; keep the required recompute job).

## 7. Sequence

1. Doctrine PR (§6) and harness PR(s) (§4 items 1-4, 7) — a Claude ship session, Fable gate.
2. AGENTS.md diet (§4 item 6) — own PR, measured boot before/after.
3. First orange mission at Gear 2 on a small organ, with the §5 spec; measure: native return
   at the wall, gate receipt bound to HEAD, release by Sol, boot ≤ 10%.
4. Only then the first two battle windows on the feature Zero names.

## 8. Convergence record

Round 1 (Astra, 203 lines): seven corrections to Fable's premises, all verified on disk (§2);
two disagreements (release owner; ship reserve) and one open question (gate receipt).
Round 2 (Astra, 40 lines): all three closed with `POSITION: agree` — Dux Sol owns release and
the gate only signs; no ship reserve; PR-comment receipt suffices for the first orange mission.
Confirmed: `dux: 0.6` + policy read in the native child is the whole threshold fix; Terra is the
default orange implementer; the seven-section spec is final. Transcripts: `astra-r1.md`,
`astra-r2.md`, briefs `parabellum-brief-r1.md`, `parabellum-brief-r2.md` in this directory.

Method note: `codex exec` with the brief as an argument hangs on "Reading additional input from
stdin" when run without a TTY; pass the brief on stdin with `-` instead. Both rounds ran with
`CODEX_CONTEXT_ROLE=builder` (0.6) because the imperator threshold (0.2 of 258k ≈ 52k) is below
the measured Codex boot — an Astra consultation at the imperator threshold would park at its
first tool. That number belongs in the AGENTS.md diet acceptance.

## Adversarial review

Reviewer: **Astra** (`codex exec -m gpt-6-astra`, xhigh, read-only sandbox), two rounds on
2026-09-10, read-only against this checkout. Author: the Fable 5.1 imperator window. Transcripts
verbatim in `astra-r1.md` and `astra-r2.md`; briefs in `parabellum-brief-r1.md` and
`parabellum-brief-r2.md`.

**Round 1 — seven objections raised, seven SURVIVED and were adopted.** Every one was a factual
correction to a premise this record was built on, and every one was re-verified on disk by the
author before adoption; the corrected statements are §2's table, and none of the original claims
survived contact. In short: the builder 0.6 threshold does not fix the Codex wall because native
children hardcode 0.4 and an undeclared `dux` role falls back to 0.4; the child CAN report in both
families through existing exemptions; the pilot never tested Sol at 0.6 because it met an expired
root mandate first; `.lane-check.json` is not a write perimeter; the missing lint pairs are the
CODEX_HOME ones, not the Claude ones; the ship sequence is five steps and only push/create/merge
are the three separate commands; and amending Builder Contract §5 alone is not enough because
`AGENTS.md` §0.0 and §17.1 and `operations.md` repeat the ban and must move with it.

**Round 1 — two disagreements and one open question, carried to round 2.** Who owns release in
orange; whether an exhausted child gets a ship reserve; what the minimum gate receipt is.

**Round 2 — all three closed, each `POSITION: agree`, and on two of them the reviewer withdrew its
own round-1 proposal.** Release belongs to the Dux Sol and the gate only signs (Astra withdrew its
gate-owned-release proposal: with the same repository credential available to both sessions it
creates no credential-enforced separation, while costing one accountable release owner). No ship
reserve, N = 0: an exhausted child checkpoints and returns, and shipping consumes the Dux's mandate
budget. The PR-comment receipt suffices as the FIRST-MISSION floor, with one correction that
changed the instruction this record gives: `--conditions-ref` is silently ignored on a plain PASS,
so PASS must use `--description` with a short reference, and descriptions truncate at 140
characters.

**Nothing was left unrefuted and unadopted.** The one thing both rounds agree is NOT settled is
empirical: orange has never executed, and the receipt's independence is procedurally checked rather
than mechanically authenticated. Both are carried as PENDING-ARMS rows rather than as confidence.
