---
adversarial_review: exempt-verbatim-brief-sent-to-the-refuter
source: the round-2 brief passed to Astra on stdin, 2026-09-10
note: >-
  An input artifact, not a claim-making document. Refuted in astra-r2.md.
---

# PARABELLUM — round 2 from Fable 5.1 to Astra. Your round-1 answer is attached below the line.

Fable verified every file:line you cited; all seven "What Fable got wrong" items stand and are
accepted. Convergence on A, D, E(a)(c)(d)(e), F and G. Two disagreements to settle, one
question. Answer in ≤ 80 lines, English, sections 1-3, each ending `POSITION: agree | hold`.

1. RELEASE OWNER IN ORANGE. You propose the independent gate session also owns release. Fable
   holds that this breaks blue/orange symmetry and adds a role: in blue the Dux opens the PR
   AFTER VERIFY and arms auto-merge immediately (SKILL.md:89 standing rule 2026-06-25); the
   independent gate posts `harness/fable-gate`; the merge queue fires; backend-rag merge IS the
   deploy; the Dux proves live. Orange mirror: Dux Sol pushes, opens, arms; fresh gate Sol posts
   the verdict; queue merges; Dux Sol proves live. "Sol does the release" = the Dux Sol arms and
   proves live, the gate Sol only signs. No session other than the Dux needs Contents/PR write
   beyond what `gh` already has on every host (M5: keyring, scopes repo+workflow, verified).
   Which is smaller and safer, and why? If you hold, name the concrete risk the mirror leaves open.

2. SHIP RESERVE vs SHIP EXEMPTION. Accepted: no blanket "ship tools exempt". Concretely: a
   completion reserve of N tool calls beyond the declared cap, usable only after the cap fires,
   for push + PR-open + arm + one checkpoint report. What N, and where does it live (declared in
   the window spec §6, consumed by child_workflow.py and context_bridge.py)? Or is "return the
   shipping work to the Dux" always cheaper? Pick one.

3. MINIMUM GATE RECEIPT. Your C wants native identity + HEAD-bound receipt validated by
   evidence_pack_lint before the status posts. Fable's cheaper floor: the gate verdict is a PR
   comment (as tonight's Fable adjudications on #6056) carrying mission id, colour, HEAD sha,
   gate thread id, commands run + exit codes, verdict; `harness_fable_gate.py --conditions-ref`
   points at it. Lint extension becomes a PENDING-ARMS row, not a precondition. Does the floor
   suffice for the first orange mission, given Zero's "do not complicate"?

Also confirm in one line each: (i) `dux: 0.6` in nuzantara-context-policy.json plus the native
child literal 0.4 -> policy read (context_bridge.py:533) is the whole threshold fix; (ii) Terra
(`-m gpt-5.6-terra`) as the default orange implementer, Sol implements directly on small work;
(iii) the seven-section window spec is final.

----------------------------------------------------------------------------------------------
## A. ORANGE Dux

**Decision: use one Sol coordinator, with native Codex leaf builders only when the gear warrants delegation. Do not reproduce the pilot’s extra Capo/support hierarchy.** PARABELLUM should parameterize the existing modus.

I inspected the repository on Air-M5 without modifying it. Pro access was blocked by this session’s network sandbox; remote installation and authentication claims below are therefore documentary, not live verification.

The minimum entry contract is:

- **Door:** AGENTS.md must explicitly direct a battle-window session to `.claude/skills/modus/SKILL.md` and its assigned spec. State the selected colour, Dux role, mandate ID and worktree before execution.
- **Boot diet:** reduce AGENTS.md from the measured **43,826 bytes / 865 lines** to an index targeting **≤6 KB**, retaining the Builder Contract, machine boundary, authority, worktree rule and task-document pointers. Move domain material to files loaded when needed. Target **first measured context consumption ≤10% of the actual window**—about 25.8k tokens for the pilot’s 258,400-token window. This is an acceptance target, not a predicted saving: repository text, global instructions, app instructions and tool catalogs all contribute.
- **Role policy:** explicitly add `dux: 0.6`; retain `imperator: 0.2`, `builder: 0.6`, `max_hops: 3` and child depth one. Today an unrecognized `dux` role falls back to **0.4**, while native children independently hardcode **0.4**. Raising the policy’s builder value alone cannot fix both. See [context_bridge.py:719](/Users/balizero/nuzantara/infra/codex-hooks/context_bridge.py:719) and [context_bridge.py:533](/Users/balizero/nuzantara/infra/codex-hooks/context_bridge.py:533).
- **Delegation:** use a short, explicitly pinned native builder profile—Terra for suitable implementation work—with objective, owned files, expected result and checks. Sol remains the top-level coordinator; a child returns unfinished work instead of spawning another layer. Within a battle worktree, serialize writers. Existing project agent files do not explicitly pin model/effort; do not infer the effective model from their names. Native project profiles support those settings. [OpenAI subagent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- **Claude participation:** use the sanctioned Claude CLI/OAuth path for the independent adversarial review. Pass the spec, frozen candidate and acceptance criteria; require findings with reproduction evidence. Do not make Sonnet builders a second default orange execution path: a Claude reviewer would then share the main builder’s family. Family separation follows the **actual builder**, not the Dux label.

For small work, Sol can implement directly and receive independent review. A Dux title does not require spawning builders.

`mandate_budget.py` already supplies locked reservations, attempt/concurrency/depth limits, a root deadline, cancellation state and child transport bookkeeping. It does **not** supply total token accounting, independent acceptance or release authorization. Moreover, the Claude and Codex adapters use different ledger directories: shared source code is not a shared cross-family budget. Native dispatch is accounted for; a shell-launched Claude reviewer is not automatically a native child reservation. Reuse the module through a small adapter for that invocation, preserving the mission ID, deadline and attempt count.

Finally, repair the existing spalla hook’s host-specific command and prove that its event matcher fires in native Codex; changing a pathname alone is not installation evidence. [.codex/hooks.json:5](/Users/balizero/nuzantara/.codex/hooks.json:5)

SMALLEST CHANGE: Add the modus entry, a lean pinned builder profile, an explicit Dux threshold consumed by parent and child, and one budgeted Claude-review invocation; retain three hops and a flat contribution chain.

## B. ORANGE gate and release — option B

**Decision: authorize the named independent Sol gate session to own release as well.** This avoids another permanent role while preserving separation from the contributing Dux.

The release credential must provide:

| Capability | Minimum practical permission |
|---|---|
| Publish `harness/fable-gate` | Repository **Commit statuses: write** |
| Push permitted branches and merge PRs | **Contents: write** |
| Create/manage PRs and their review evidence | **Pull requests: write** |
| Observe CI and perform the existing post-verdict rerun | **Actions: write**; read alone cannot rerun |
| Deploy through the existing main-branch pipeline | Existing CI deployment credentials; no new local Fly/Vercel token |

GitHub documents the permissions for [commit statuses](https://docs.github.com/en/rest/commits/statuses#create-a-commit-status), [merging PRs](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request) and [workflow reruns](https://docs.github.com/en/rest/actions/workflow-runs#re-run-a-workflow). An existing classic OAuth credential with `repo` may already cover these operations; do not manufacture a replacement before checking it. Workflow-file modification permissions are needed only if that operation enters the mandate. No administrator or branch-protection bypass is required.

**Sandbox:** use `workspace-write`, explicitly enabled network access, and `on-request` approvals for operations outside that boundary. Where the installed runtime and managed policy support it, automatic approval review can handle eligible requests under Zero’s existing authorization. `never` suppresses approval requests; it does not grant missing access. In particular, default workspace-write protects `.git`, resolved worktree Git directories, `.agents` and `.codex`. Do not promise that `workspace-write + never` can commit or modify those paths. [OpenAI approval and sandbox documentation](https://learn.chatgpt.com/docs/agent-approvals-security)

Neither the bypass flag nor `danger-full-access` is necessary. This current read-only/never session cannot become a release seat merely because a repository file changes.

**Placement, per host:**

| Host | Documented Codex configuration locations | Credential placement |
|---|---|---|
| M5 | `/Users/balizero/.codex`, `.codex-o2`, `.codex-acct2` | Selected profile’s configuration; GitHub credential in the local credential store/Keychain, supplied to the appointed process |
| Pro | `/Users/nuzantara/.codex`, `.codex-acct2` | Same separation; deployment secrets remain with existing CI/Pro deployment facilities |
| Mini | `/Users/nuzantara/.codex`, `.codex-acct2` | Same separation; release can use GitHub/CI without installing another deployment stack |

These profile locations come from the [September 9 rollout:37](/Users/balizero/nuzantara/infra/codex-hooks/CHILD-ROLLOUT-2026-09-09.md:37). That report explicitly distinguishes installation from authentication verification. Do not copy OAuth material between profiles or hosts, put credentials in agent TOMLs, or assume GUI Keychain access works over SSH.

Correct the sequencing language: **push, create PR and arm auto-merge are separate invocations; actual merge precedes deployment; prove-live follows deployment.** Arming auto-merge after the PR has merged makes no sense. The independent gate must pass before arming freezes the candidate. The existing CI deployment remains the release mechanism.

**Credential decision for Zero:** “Authorize the appointed orange Sol gate/release seat to use a repository-scoped GitHub credential with Contents, Pull requests, Commit statuses and Actions write, through each approved host’s existing credential store.”

SMALLEST CHANGE: Provision and verify one orange release profile first, using existing GitHub/CI paths and bounded sandbox approvals; do not distribute new deployment credentials across the fleet.

## C. Independence in orange

**Decision: a fresh Sol session performs the final gate; the contributing Sol’s continuation or renamed child does not qualify.** The fresh session can take over the same battle window after its writers stop. No additional battle mandate is needed.

The cheapest useful receipt is one small record associated with the existing evidence pack, containing:

- Mission ID, colour, repository, frozen HEAD and candidate-content identity.
- Gate’s native thread ID, effective model and effort.
- Dux and material contributor thread IDs, including their continuations; the gate’s parent/fork/continuation provenance.
- Native rollout reference plus a hash of the relevant metadata/evidence, without copying raw transcripts into shared artifacts.
- Commands actually executed, results, verdict and timestamp.

Collect identity from native session metadata and continuation state, rather than accepting typed labels such as “Sol reviewer.” Reject a gate identity that intersects the contributing chain. Verify the checked worktree has no additional candidate changes and that the PR still points at the reviewed HEAD. **Any candidate change invalidates the receipt.** A gate that fixes the artifact becomes a contributor and needs a replacement gate.

Store the final receipt outside the candidate commit—for example, as a referenced PR evidence attachment—so recording the verdict does not change the HEAD it attests. Add its link through the status’s supported `target_url`; keep `harness/fable-gate` unchanged.

There is an existing foundation, but it is insufficient today. The evidence-pack consumer compares author-entered seat strings, is NOTICE-only until September 21, and deliberately feeds identical `"unattested"` hashes to neutralize freshness checking. [evidence_pack_lint.py:2225](/Users/balizero/nuzantara/scripts/evidence_pack_lint.py:2225)

Extend that consumer and the existing status publisher/reader rather than creating another attestation service. **This produces auditable provenance, not cryptographic proof against a malicious process sharing the same OS account and GitHub credential.** A thread ID or self-authored receipt alone cannot prove independence.

SMALLEST CHANGE: Add one native-identity, HEAD-bound gate receipt to the existing evidence path, and require its validation before posting or accepting the gate status.

## D. Symmetry with blue

**Decision: one procedure, one colour selection at mission start, no automatic colour fallback.**

| Assignment | BLUE | ORANGE |
|---|---|---|
| Dux | Opus 5 | Sol |
| Default implementation family, when builders are needed | Anthropic, normally Sonnet | OpenAI, normally Terra or Sol |
| Adversarial reviewer | Independent Codex | Independent Claude |
| Final empirical gate | Fresh Opus 5, xhigh | Fresh Sol, xhigh |
| Release owner | Authorized Claude session | Authorized Sol session; preferably the independent gate session |
| Native transport/authentication adapter | Claude-native work plus Codex review | Codex-native work plus Claude OAuth review |

Those are the necessary differences. Builder selection remains a staff-room assignment, subject to the same cross-family review rule.

Everything else stays identical:

- TRIAGE and the existing gear floor; no cheaper orange interpretation of Gear 2 or Gear 3.
- GROUND → DESIGN → BUILD → VERIFY → SHIP+ARM → PROVE-LIVE → ALIGN-FLEET → CLEAN → CAPTURE, including existing legitimate gear skips.
- Generator≠grader, final gate on every gear, and no quota-driven substitution of the final gate.
- One mandate, organ and worktree per battle window; two windows initially, a third only for an independently owned organ.
- Mandate accounting, evidence pack, `Bites:`, PENDING-ARMS, sibling checks, stop-loss, freeze, rollback and public verification.
- Fable and Astra remain exclusively in Zero’s staff room; the specification carries their decisions into execution.

Native APIs may require different adapters. They must not introduce different budget meanings, acceptance standards or release privileges beyond the selected role.

SMALLEST CHANGE: Add one colour-to-role table and reference it from the existing stages; reject a second stage machine, ledger or release pipeline.

## E. Fable’s five changes and Codex parity

| Proposal | Decision, reason and minimum implementation |
|---|---|
| **(a) ToolSearch exemption and useful denials** | **Agree, narrowly.** Permit discovery of the reporting/stop tools needed to return, rather than opening arbitrary tool discovery after exhaustion. Both denial paths should name the triggering counter, used/limit, role and required next action. |
| **(b) Mandate/gear limits, deadlines, ship exemptions** | **Partly agree.** Declare limits at TRIAGE. Use one coordinator-renewable absolute deadline within the staff-approved hours ceiling; preserve the mandate ID and spent attempts. Reject blanket “ship tools are exempt”: a finite completion reserve or returning shipping work to the Dux is sufficient. |
| **(c) Siblings at GROUND and before SHIP** | **Agree.** Compare open PR changed paths, existing worktree leases, native agent trees and fleet sessions. Record timestamped evidence in the pack and a short reference in `Bites:`. Raw command dumps do not belong in the Bites line. Snapshot checks complement the existing broker; they do not prevent races by themselves. |
| **(d) AGENTS.md diet** | **Agree.** Make it a lazy index with the A targets. Measure total boot consumption; moving text into another automatically loaded file achieves nothing. |
| **(e) HOME-fork pairs** | **Agree with correction.** Add missing Codex/profile coverage. Do not duplicate the Claude child and window-guard pairs already declared. |

The important parity differences are concrete:

- **Codex can checkpoint after its context wall.** Its exact helper is exempt, and the PreToolUse hook records the checkpoint even in a read-only session. Native `send_message` is nevertheless denied by the generic post-threshold rule. Preserve the working helper/final-return path; optionally allow reporting to the verified parent. [context_bridge.py:494](/Users/balizero/nuzantara/infra/codex-hooks/context_bridge.py:494), [context_bridge.py:571](/Users/balizero/nuzantara/infra/codex-hooks/context_bridge.py:571)
- **Codex has no equivalent 120-tool child cap in this adapter.** It counts events without enforcing that ceiling. Claude’s constants are 120 calls and 3,600 active seconds. [child_context.py:20](/Users/balizero/nuzantara/infra/claude-hooks/child_context.py:20)
- **Both adapters use a wall-clock mandate deadline**, but Claude additionally measures child active time. Codex continuation supervision introduces another deadline starting at first rollover. Unify the mission deadline across these consumers; keep active-time measurements explicitly separate. [mandate_budget.py:49](/Users/balizero/nuzantara/infra/codex-hooks/mandate_budget.py:49), [context_bridge.py:874](/Users/balizero/nuzantara/infra/codex-hooks/context_bridge.py:874)
- **Both families need comparable mission limits, not necessarily identical raw tool counts.** Claude and Codex package tool work differently. Declare any adapter-specific ceiling and reserve rather than silently pretending the counters are equivalent.
- **The observation race remains a separate defect.** A file lock cannot prove dispatch identity when observation binds the first available reservation. Bind the actual reservation to the returned native child identity; uncertain binding remains unverified. [mandate_budget.py:192](/Users/balizero/nuzantara/infra/codex-hooks/mandate_budget.py:192)

Do not carry `ORCHESTRATE_GATE_OFF` or other bypass flags into the normal PARABELLUM launcher. A quota denial should produce a checkpoint and a coordinator decision, not automatically terminate every unaffected part of the mission.

SMALLEST CHANGE: Fix reporting, threshold consumption and reservation identity first; unify deadline semantics next; retain bounded budgets and extend existing installation-parity declarations.

## F. Doctrine edits

**Decision: one atomic doctrine PR must remove contradictory authority statements together.** The following is the amendment list; historical reports remain historical.

| File | One-line amendment |
|---|---|
| `docs/rules/RULINGS.md` | Add the dated September 10 PARABELLUM ruling, update “Routing vigente,” explicitly supersede the Claude-only gate/release clauses, and record Zero-only staff-room interaction. |
| `docs/architecture/dual-consul/army-map.md` | Parameterize Dux, reviewer, final gate and release rows by colour; update repeated gate/release prose, mission packets and the staff-room boundary. |
| `CLAUDE.md` | Amend canonical Builder Contract §5: the named independent orange Sol release seat is authorized; all other external builders retain prepare-only authority. |
| `AGENTS.md` | Copy the identical amended canon, reconcile §0.0 and §17.1’s blanket bans, and add the explicit modus/spec entry. |
| `GEMINI.md` | Copy the identical amended canon; the orange exception grants no Gemini release authority. |
| `QWEN.md` | Copy the identical amended canon; the orange exception grants no Qwen release authority. |
| `docs/rules/operations.md` | Reconcile the external-seat caveat and lifecycle wording with the colour-selected release owner and actual arm-before-merge sequence. |
| `.claude/skills/modus/SKILL.md` | Keep one skill; parameterize VERIFY, SHIP+ARM and arsenal assignments, and align its summary with the same role table. |
| `FLEET_TOPOLOGY.json` | Update authority invariants; preserve the blue final-gate chain and add an explicitly selected orange Sol-only chain with no cross-colour fallback. |
| `.claude/skills/modus/PENDING-ARMS.md` | Record the unverified activation obligations, with owner and closing observation, rather than marking PARABELLUM armed when doctrine merely merges. |

In `FLEET_TOPOLOGY.json`, **do not append Sol to the blue fallback list**. A separately named `gear3_final_gate_orange` is acceptable if the mission’s colour selection actually resolves to it. Its name does not mean that lower gears lose their final gate. A declarative chain without an executing consumer is not an armed capability.

**`harness-floor.yml` needs no colour-specific branch.** Its executable gate path is model-indifferent. Preserve `Harness floor recompute` as the required check and the relay from the PR’s real HEAD to merge-queue verification; making the classic status independently required would recreate the documented synthetic-SHA deadlock. [.github/workflows/harness-floor.yml:169](/Users/balizero/nuzantara/.github/workflows/harness-floor.yml:169)

Runnable prerequisites belong in bounded implementation changes, with these exact owning surfaces:

- Entry/dispatch: `.codex/hooks.json`, the spalla script it invokes, and a short new `.codex/agents/parabellum-builder.toml`.
- Budgets/reporting: `infra/codex-hooks/context_bridge.py`, `infra/codex-hooks/mandate_budget.py`, `infra/claude-hooks/child_workflow.py`, and `child_context.py` where declared limits are consumed.
- Independence: `scripts/conductor/review_eligibility.py`, `scripts/evidence_pack_lint.py`, `scripts/harness_fable_gate.py` and `scripts/ci/harness_gate_read.py`.
- Installation: `infra/home-fork/declared-pairs.json` and the existing installers, covering `context_bridge.py`, `rpc.py`, `mandate_budget.py` in every installed CODEX_HOME.
- Perimeter: `infra/claude-hooks/lane_check.py` and its actual Codex/Claude callers, if adopting G’s proposed perimeter field.

PENDING-ARMS should track three observations: **native orange execution/return**, **independent HEAD-bound gate plus authorized release**, and **per-profile fleet installation/authentication parity**. No obligation closes from file existence or matching configuration alone.

SMALLEST CHANGE: Merge the coherent authority amendment as one doctrine concern; keep activation explicitly pending until the bounded runtime changes have real consumers and successful probes.

## G. Battle-window specification template

**Decision: keep one short file per window, normally one to two pages.** Fable’s sections are substantially right. Merge overlapping sections and add identity, frozen inputs and explicit failure handling.

| Section | Required content |
|---|---|
| **1. Mandate** | Mission/window ID, colour, organ, objective, gear, assigned host, worktree/branch and base commit; one sentence stating what success changes. |
| **2. Owned perimeter** | Explicit writable paths and forbidden/shared paths; one owner for every shared schema, fixture, generated file and lockfile. |
| **3. Sibling contract** | Schema/version and fixture hashes, success/error responses, producer/consumer ownership, and compatibility expected before either side merges. |
| **4. Acceptance** | Falsifiable outcomes and exact checks, including a negative case, integration check and production observation; distinguish fixture success from live integration. |
| **5. Team** | Named Dux, optional implementer, adversarial reviewer, independent gate and release owner; effective model/effort and thread identities recorded when started. |
| **6. Appetite and stop-loss** | Hours ceiling, current absolute deadline, token allowance, attempts/concurrency/depth/hops, declared adapter tool limits, renewal authority and the checkpoint destination. |
| **7. Evidence and release** | Existing pack/ledger references, Bites consumer and observation, merge order, final-gate receipt, deployment path and rollback trigger. |

**Correct the proposed `.lane-check.json` interpretation.** Its existing `scope_globs` field controls whether the check applies; it does not reject out-of-perimeter modifications. If no changed path matches, it returns `OUT_OF_SCOPE` and skips the command. [lane_check.py:396](/Users/balizero/nuzantara/infra/claude-hooks/lane_check.py:396)

Keep its existing command/expected-exit/timeout contract. Add a separately named allowed-path field only with a consumer that rejects **every** out-of-perimeter changed path, including relevant untracked files. Until that exists, require an explicit perimeter comparison during VERIFY and the independent gate; do not advertise a write fence.

The sibling contract should be frozen before implementation. A necessary schema change returns to the staff-room decision through Zero; neither window silently edits the sibling’s contract. Backend-first merge is a default only when the API change is backward-compatible. Shared lockfile changes must be serialized.

Cut duplicated doctrine, model catalogs, generic architecture essays and raw fleet output. Sol needs the exact task, constraints, proof and stopping conditions. “On first tool denial, stop the whole mission” should not appear in the template.

SMALLEST CHANGE: Use the seven-section spec above, the existing evidence/ledger locations, and a real perimeter check; add no separate planning database or additional coordinator tier.

## What Fable got wrong

1. **“Builder threshold is now 0.6” is not true of every Codex execution path.** Native children still compare against literal `0.4`; an undeclared Dux role also falls back to `0.4`. [context_bridge.py:533](/Users/balizero/nuzantara/infra/codex-hooks/context_bridge.py:533), [context_bridge.py:719](/Users/balizero/nuzantara/infra/codex-hooks/context_bridge.py:719)

2. **The Codex reporting failure is not identical to Claude’s ToolSearch trap.** Codex has a working checkpoint-helper exemption; Claude exempts SendMessage/TaskStop but omits the discovery tool needed to reach a deferred SendMessage. [context_bridge.py:494](/Users/balizero/nuzantara/infra/codex-hooks/context_bridge.py:494), [child_workflow.py:213](/Users/balizero/nuzantara/infra/claude-hooks/child_workflow.py:213)

3. **B-3 did not test whether 0.6 made Sol viable.** It encountered an already expired root mandate before reaching the relevant context threshold. The pilot report itself says that experiment remained unmeasured. [pilot report:506](/Users/balizero/nuzantara/research/operations/2026-09-10-pilot-mission-1-capo-vs-builder.md:506), [pilot report:548](/Users/balizero/nuzantara/research/operations/2026-09-10-pilot-mission-1-capo-vs-builder.md:548)

4. **`.lane-check.json` is not currently a perimeter guard.** Its scope condition can skip checking; it does not forbid edits outside the declared glob. [lane_check.py:419](/Users/balizero/nuzantara/infra/claude-hooks/lane_check.py:419)

5. **The HOME-pair proposal partly repeats work already present.** Claude child_workflow, child_context and mandate_budget are declared, as are context_window_guard—the file containing `_claude_pid`—and window_jump. Missing Codex/profile coverage remains valid work. [declared-pairs.json:983](/Users/balizero/nuzantara/infra/home-fork/declared-pairs.json:983), [declared-pairs.json:415](/Users/balizero/nuzantara/infra/home-fork/declared-pairs.json:415), [context_window_guard.py:271](/Users/balizero/nuzantara/infra/claude-hooks/context_window_guard.py:271)

6. **“Merge → arm auto-merge → deploy → prove-live as three commands” combines the wrong ordering with the wrong count.** The current stage explicitly arms auto-merge before merge and deploys afterward; the separate-command contract names push, PR creation and merge/arming. [modus/SKILL.md:89](/Users/balizero/nuzantara/.claude/skills/modus/SKILL.md:89), [AGENTS.md:50](/Users/balizero/nuzantara/AGENTS.md:50)

7. **Amending only Builder Contract §5 would leave contradictory law.** AGENTS §0.0 and §17.1 independently prohibit external release, and operations.md repeats that caveat. They must be reconciled in the same authority amendment. [AGENTS.md:65](/Users/balizero/nuzantara/AGENTS.md:65), [AGENTS.md:839](/Users/balizero/nuzantara/AGENTS.md:839), [operations.md:15](/Users/balizero/nuzantara/docs/rules/operations.md:15)

