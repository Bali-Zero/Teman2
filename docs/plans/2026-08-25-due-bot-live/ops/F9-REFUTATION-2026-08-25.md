# F9 failover — cross-family refutation, and a correction to my own gate

Refuter: `gpt-5.6-sol`, effort xhigh, fenced to six files extracted at a FIXED commit
(`c0fd7cf7b`) with no repo access and no live system — the ASSEMBLY-LINE live-writer rule.
It was given the five claims below as targets and told to default to "this is broken".

## The correction I owe first

In the merge commit `fb57ee914` I wrote that the daemon "can be run TODAY EVEN ARMED and
still cannot promote", and called it *a construction that cannot lie*. **That was wrong**,
and it was the strongest praise I gave any lane last night.

Verified at code after the refuter named it: `evaluate_and_act_once` reads the leader
record, and **if the record already names this node it performs the outbound WABA callback
override and returns — before `run_self_prechecks` is ever called.** The three hardcoded
`False` values sit on a branch that path never reaches. The claim is true of *promotion*
(the CAS) and false of the property that matters, which is whether an unhealthy node can
make an outbound state-changing call to Meta.

What remains true: with `TEAM_BOT_FAILOVER_AUTO_ENABLED=false` — the shipped default — the
function returns `SHADOW_WOULD_PROMOTE_BUT_DISABLED` before reaching that branch. **The dark
state is safe.** The armed state is not, and "safe to run armed" is what I asserted.

Why I missed it: I checked the path the design pointed me at. The prechecks exist, they are
honestly hardcoded, `all_pass` is honestly false — every fact I verified was true, and I
never asked which branches reach the outbound call *without* passing through them. A weaker
test agrees with itself; so does a weaker gate.

## Findings

Verdict: broken.

1. **CRITICAL — A losing contender reaches WABA on its next tick, and an obsolete winner can overwrite the current leader’s callback.**  
   Promotion checks only `leader_epoch`; it does not require the incumbent lease to expire ([ingress_state_repo.py:112](ingress_state_repo.py:112)). The daemon repeats indefinitely ([failoverd.py:506](failoverd.py:506)).  
   Scenario: A and B race epoch 1. A wins epoch 2; B conflicts. On B’s next tick, Mini is still unavailable, so B reads epoch 2, promotes itself to epoch 3, and calls WABA ([failoverd.py:249](failoverd.py:249), [failoverd.py:271](failoverd.py:271)). If A was paused after its CAS, it can then resume and POST A’s callback after B owns epoch 3. Final state: DB leader B, WABA callback A.  
   The split-brain test stops after one invocation and counts one POST ([test_staging_drill.py:263](test_staging_drill.py:263), [test_staging_drill.py:273](test_staging_drill.py:273)); it never executes the loser’s next daemon tick.

2. **CRITICAL — Authorization is a check, not a fence; a stale action can commit after takeover.**  
   Production authorization performs a plain read followed by a local comparison ([ingress_state_repo.py:184](ingress_state_repo.py:184), [ingress_state_repo.py:185](ingress_state_repo.py:185)). Nothing couples that result atomically to the protected mutation.  
   Scenario: action at epoch 1 receives `AUTHORIZED`; Pro then promotes to epoch 2; the already-authorized action commits afterward. Wrong outcome: an epoch-1 mutation completes under epoch 2.  
   The “in-flight” test performs no mutation and has no concurrency: it reads, completes takeover, and only then calls `authorize()` ([test_staging_drill.py:323](test_staging_drill.py:323), [test_staging_drill.py:337](test_staging_drill.py:337)). It proves only that a check deliberately placed after takeover returns 409.

3. **CRITICAL — The hardcoded-false prechecks do not make armed operation safe.**  
   If the row already names this node, the daemon calls WABA before running any self-precheck ([failoverd.py:223](failoverd.py:223), [failoverd.py:227](failoverd.py:227)); the three hardcoded `False` values are reached only later ([failoverd.py:240](failoverd.py:240), [failoverd.py:427](failoverd.py:427)).  
   Scenario: a previous CAS or operator state leaves `active_node_id="pro"`, Pro restarts armed, and Mini remains unavailable. After the failure threshold, Pro makes the outbound override despite all three unwired checks being false. The same occurs immediately against the bootstrap row if `TEAM_BOT_FAILOVER_NODE_ID=mini-pro2`, which configuration explicitly permits.

4. **HIGH — An expired leader still performs outbound WABA writes.**  
   The already-leader branch checks only `active_node_id`; it ignores `leader_epoch` ownership and `lease_expires_at` ([failoverd.py:215](failoverd.py:215), [failoverd.py:223](failoverd.py:223)). Elsewhere, an expired lease means authorization must be rejected ([ingress_leader.py:293](ingress_leader.py:293)).  
   Scenario: Pro’s 30-second lease expires without renewal, Mini remains down, and the next eligible tick POSTs Pro’s callback. Wrong outcome: Meta is directed to a node that the same subsystem considers unauthorized to process ingress.

5. **HIGH — Crashes leave a durable state that falsely implies callback completion.**  
   The CAS writes `active_node_id` and the new callback hash in one committed UPDATE ([ingress_state_repo.py:106](ingress_state_repo.py:106), [ingress_state_repo.py:110](ingress_state_repo.py:110)); the external POST happens afterward ([failoverd.py:271](failoverd.py:271)). The schema has no pending/confirmed state ([281_migration.sql:65](281_migration.sql:65)).  
   Scenario A: crash after CAS but before POST → DB says Pro and stores Pro’s callback hash while Meta still routes to Mini.  
   Scenario B: crash after POST but before GET confirmation ([waba_override.py:127](waba_override.py:127), [waba_override.py:154](waba_override.py:154)) → Meta may have switched, but durable state cannot distinguish success, failure, or uncertainty. Restart blindly POSTs again through the already-leader path.

6. **HIGH — Lease and failure safety depend on unsynchronized wall clocks.**  
   Failure duration uses subtraction of injected wall-clock datetimes ([failoverd.py:135](failoverd.py:135), [failoverd.py:153](failoverd.py:153)), sourced from `datetime.now(UTC)` ([failoverd.py:509](failoverd.py:509)). Lease deadlines are also calculated from the calling node’s clock ([ingress_state_repo.py:117](ingress_state_repo.py:117), [ingress_state_repo.py:165](ingress_state_repo.py:165)), and authorization compares using another caller-supplied clock.  
   Scenario: a node’s clock reads 11:55 while a lease expired at real 12:00 and real time is 12:05. It supplies 11:55, so authorization returns 200. A forward clock jump can likewise satisfy the “30 seconds sustained” condition after only three rapid failures; a backward jump can suppress takeover indefinitely.

7. **HIGH — SQL does not enforce monotonic epochs or CAS-only writes.**  
   The only epoch constraint is `leader_epoch > 0` ([281_migration.sql:73](281_migration.sql:73)). “Written ONLY via compare-and-swap” is merely a comment ([281_migration.sql:79](281_migration.sql:79)); no schema rule prevents a bare UPDATE or epoch rollback.  
   Scenario: any holder of the table’s write credentials changes epoch 2 back to epoch 1, names Mini, and supplies a future lease. A previously stale `(mini-pro2, 1)` ticket then passes `evaluate_authorize()` and receives 200. The primary-key uniqueness assumption is enforced; epoch monotonicity is not.

8. **HIGH — Startup failures can restart-storm before the long-running loop exists.**  
   Required environment validation runs before `asyncio.run()` and raises on a missing value ([failoverd.py:529](failoverd.py:529)); database connection creation is also outside the runner’s exception-catching loop ([failoverd.py:533](failoverd.py:533)).  
   Scenario: one required variable is absent or Postgres is unavailable at launch. The process exits immediately; a KeepAlive supervisor repeatedly relaunches it. The loop is genuinely long-running only after initialization succeeds.

**Claims surviving the attack**

- The narrow same-expected-epoch CAS property survives: the Postgres `UPDATE … WHERE leader_epoch = expected` permits exactly one successful row update, and that invocation’s conflict branch does not call WABA. The broader “split-brain impossible / loser never reaches WABA” claim does not survive subsequent ticks or post-CAS interleavings.
- Claim 3 survives within these six files under the stated Pro-only deployment: a healthy Mini causes an immediate return before any store or WABA operation ([failoverd.py:202](failoverd.py:202)), and no automatic recovered-primary promotion path is present.

## The orchestrator's reading: four faces, one defect

Findings 1, 2, 3 and 4 are not four bugs. They are one structural defect: **a decision is
made from a belief about leadership that is not re-established at the moment of acting.**

- #3 and #4: the already-leader branch acts on `active_node_id` read earlier, checking
  neither epoch ownership nor lease validity, and reaches an outbound write.
- #1: the CAS loser's *next tick* re-reads, finds an epoch it can match, and promotes —
  because promotion tests epoch equality alone, never whether the incumbent lease is live.
- #2: `authorize()` returns a verdict that is already stale by the time the protected
  mutation commits, because nothing binds the verdict to the write.

This is precisely the class B5 itself identified in `F6-F9-PENDING-ACTION-EPOCH-GAP.md` —
state acted on under an epoch that was true a moment ago. The lane found the class in
another lane's module and did not turn it on its own. That is not a criticism of the lane;
it is the reason generator≠grader exists, and the reason the grader needs a different
instrument than the generator's own tests.

Per the Agent PR Contract: when a correction would itself be under-specified, write the
spec rather than open the patch. Four patches against four faces would leave the fifth
face unfound.

## Routing

- **#1, #3, #4, #7, #8 — B5's, inside its own modules.** Each must first be reproduced as a
  RED test, then fixed. A fix landed without a test that failed before it is indistinguishable
  from a fix that changed nothing.
- **#2 — NOT B5's alone.** The fence has to live where the mutation commits, which is the CRM
  endpoints and F6's confirmation store. It belongs in the gap doc, whose fix now serves three
  consumers: pending actions, per-member memory, and this.
- **#5, #6 — design questions, not patches.** A crash window between the CAS and the outbound
  POST needs a durable intermediate state the schema does not currently have; wall-clock
  dependence needs a stated trust model for node clocks. Both are answerable; neither is a
  one-line change.

## What survived

The narrow same-tick CAS property survives: `UPDATE … WHERE leader_epoch = expected` admits
exactly one winner, and that invocation's conflict branch does not call WABA. "No automatic
failback" also survives within these files. The broader claims built on top of them do not.
