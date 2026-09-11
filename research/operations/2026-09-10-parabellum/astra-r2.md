---
adversarial_review: exempt-verbatim-refuter-transcript
source: codex exec -m gpt-6-astra, xhigh, read-only sandbox, 2026-09-10 round 2
note: >-
  This file IS the adversarial review, round 2, verbatim. It closes the three
  questions round 1 left open, each with POSITION: agree. See
  PARABELLUM-staff-room-2026-09-10.md §8.
---

### 1. RELEASE OWNER IN ORANGE

**Agree: Dux Sol owns release; fresh gate Sol verifies and signs. I withdraw my gate-owned release proposal.**

Use the blue sequence: VERIFY passes → Dux pushes → opens PR → immediately arms auto-merge → gate publishes its HEAD-bound verdict → queue merges → existing CI deploys → Dux proves live. Push, PR-open and arm remain separate invocations. This matches [modus/SKILL.md:89](/Users/balizero/nuzantara/.claude/skills/modus/SKILL.md:89).

The gate’s empirical verification belongs in VERIFY; attaching its receipt and publishing the status can follow PR-open. Arming does not replace the required verdict.

The mirror is smaller and operationally safer: it preserves one accountable release owner and avoids transferring release context to the verifier. With the same repository credential available to both sessions, my proposal creates no additional credential-enforced separation.

The gate alone signs; the Dux cannot substitute its own verdict or alter the armed candidate. The coherent doctrine amendment must authorize **Dux Sol**, replacing round 1’s gate/release-seat exception.

POSITION: agree

### 2. SHIP RESERVE vs SHIP EXEMPTION

**Pick return-to-Dux. N = 0 additional shipping calls.**

Window spec §6 declares: child cap reached → checkpoint and return remaining work; shipping belongs to the Dux and consumes the existing coordinator/mandate budget.

`child_workflow.py` and `context_bridge.py` enforce that return path, including the accepted narrow reporting/discovery allowance. They need no reserve counter, shipping-command classifier or post-cap release authority.

This is cheaper to implement and govern, though not necessarily fewer calls in every individual run. The Dux already owns release under section 1; letting an exhausted child ship introduces an unnecessary exception.

An exhausted Dux checkpoints and resumes with spent counters preserved. An exhausted mandate suspends or uses its explicitly declared renewal authority; a continuation cannot manufacture fresh allowance.

POSITION: agree

### 3. MINIMUM GATE RECEIPT

**Yes: the PR-comment floor suffices for the first orange mission. Withdraw mandatory lint extension as a launch precondition.**

Keep the proposed fields: mission ID, colour, HEAD SHA, gate thread ID, commands actually run with exit codes, and verdict. The fresh gate must be outside the contribution/continuation chain and verify the clean candidate against the current PR HEAD before posting. Candidate changes invalidate the receipt.

One concrete correction: **`--conditions-ref` is included only for PASS-WITH-CONDITIONS; plain PASS silently ignores it.** Use `--description` with a short, resolvable comment reference for PASS. Descriptions truncate at 140 characters; do not depend on a long URL surviving. I confirmed this with a local dry-run and [the publisher implementation](/Users/balizero/nuzantara/scripts/harness_fable_gate.py:102).

For PASS-WITH-CONDITIONS, the referenced comment must also contain or link the conditions’ owner/deadline ledger. Post against the explicitly checked SHA. Preserve the existing required-check relay.

Record native-identity/HEAD-receipt lint validation in PENDING-ARMS with an owner and closing observation. Until implemented, independence is procedurally checked and auditable, rather than mechanically authenticated. That is an acceptable first-mission floor.

(i) **Confirmed:** add `dux: 0.6` and replace the native-child literal `0.4` with the validated builder-policy lookup; that is the complete threshold logic fix, with installation and parent/child probes still required.
(ii) **Confirmed:** Terra (`-m gpt-5.6-terra`) is the default orange implementer when delegating; Sol implements small work directly.
(iii) **Confirmed:** the seven-section window spec is final; sections 5–7 incorporate these decisions without adding sections.

POSITION: agree

