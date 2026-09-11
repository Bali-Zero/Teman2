---
date: 2026-08-29
domain: operations
plan: beyond-sota-craft-wave
lane: "13 - Security, secrets & PII"
source_report: /Users/nuzantara/nuzantara/.worktrees/research-beyond-sota-0828/research/operations/2026-08-28-beyond-sota-security-secrets-pii.md
status: SPEC-FINAL
---

# L13 - Security, secrets & PII

## Mission

Reduce invisible credential and network exposure without asking an external seat to inventory it: the panel measured full session-environment inheritance by every `codex`/`agy`/`kimi` child, at least three secret-shaped names per interactive child, one confirmed vendor-bound leak on 2026-08-18, a six-node allow-all tailnet, and 45 operator[secret] ledger rows with at least three rotations still open. The target is exec-time minimization, policy-state proprioception, and a value-free operator digest.

## Ground to load (orchestrator first reads)

- [exists] `/Users/nuzantara/nuzantara/.worktrees/research-beyond-sota-0828/research/operations/2026-08-28-beyond-sota-security-secrets-pii.md` — panel findings, scars, recommendations, roadmap, and rulings.
- [exists] `infra/llm-credentials/declared.json` — current credential-name declarations; values must never be loaded into artifacts.
- [exists] `scripts/proprioception.py` — receptor registry and reconciliation semantics.
- [exists] `scripts/hooks/proprioception_sessionstart.sh` — current session-start receptor wiring.
- [exists] `scripts/tests/test_proprioception_run_wrap_exit_code.py` — current wrapped-command exit-code behavior.
- [exists] `infra/tailscale/policy.hujson` — proposed policy source; file existence is not proof of enforcement.
- [exists] `infra/tailscale/README.md` — tailnet operating context and manual-console boundary.
- [exists] `scripts/pending_arms_report.py` — current pending-arms signaler, also modified by lane L10 PR-1.
- [exists] `scripts/tests/test_pending_arms_report.py` — current ledger-report tests.

## PR-1: feat(security): seat broker - exec-time minimal env for external LLM dispatch

**Files:**

- [proposed] `scripts/with_seat.sh`
- [proposed] `infra/llm-credentials/seat-env.json`
- [proposed] `scripts/tests/test_with_seat_env_minimization.sh`
- [exists] `infra/llm-credentials/declared.json`

**Gear:** Gear 2.

**Build:**

- Define each external seat's complete allowed environment-name set in `seat-env.json`, including only required functional names and that seat's credential names.
- Validate registry keys and environment names before execution; reject unknown seats, duplicate names, malformed names, and empty commands.
- Construct the child with `env -i` so the resulting name set equals the declaration rather than subtracting a blacklist from the parent.
- Resolve credential material at execution time from the approved local source; never serialize values into the registry, command line, logs, or test fixtures.
- Use a fixed executable dispatch table for `codex`, `agy`, and `kimi`; do not accept arbitrary vendor executable paths from environment variables.
- Emit only seat name, child exit status, and declaration fingerprint in diagnostics.
- Preserve child exit status and signal behavior without falling back to an unwrapped invocation.
- Test the boundary with a benign local child; never ask an external CLI to print its environment or inspect `launchctl`, plists, shell state, or other seats.
- Add shell syntax validation and restrictive file-mode checks for the registry and wrapper.

**Acceptance:**

- Guilt must turn RED: an unwrapped benign child sees a planted fake token name, proving the fixture is capable of detecting inheritance.
- Innocence must stay GREEN: the wrapped benign child's environment names equal the declared names exactly, and the planted name is ABSENT.
- Exact commands from repository root:

```bash
bash -n scripts/with_seat.sh
python3 -m json.tool infra/llm-credentials/seat-env.json >/dev/null
bash scripts/tests/test_with_seat_env_minimization.sh
```

**Seats:** Implementer = Sonnet 5 subagent. Refuter = Kimi K3. Family exclusion binds the DIFF BUILDER's family, not the spec drafter's: builder is Anthropic (Sonnet 5 implementer under an Opus 5 orchestrator); the refuter must be a non-Anthropic family (Kimi K3 default, Codex GPT-5.6 sol for security-class diffs); a diff built by a non-Anthropic seat is refuted by a different family. Final gate = orchestrator Opus 5 xhigh.

**Arming / prove-live:** Ship the broker and local proof first. Migrate each real external-CLI callsite in a separately reviewed arming step, one PENDING-ARMS row per not-yet-wrapped dispatch family. Prove only allowed name fingerprints and absence of the planted name; do not expose values.

**Conflicts / order:** This is the first L13 PR. Credential rotation is operator[secret], is not required to test the broker, and must never be delegated to an external seat. No callsite may silently fall back to the inherited environment.

## PR-2: feat(proprioception): tailnet policy drift receptor

**Files:**

- [proposed] `scripts/tailnet_policy_drift.py`
- [exists] `scripts/proprioception.py`
- [exists] `scripts/hooks/proprioception_sessionstart.sh`
- [exists] `scripts/tests/test_proprioception_run_wrap_exit_code.py`
- [proposed] `scripts/tests/test_tailnet_policy_drift.py`
- [proposed] `scripts/tests/fixtures/tailnet_netmap_allow_all_2026_08_11.json`; [proposed] `scripts/tests/fixtures/tailnet_netmap_policy_match.json`
- [exists] `infra/tailscale/policy.hujson`

**Gear:** Gear 2.

**Build:**

- Parse the locally enforced Tailscale netmap or packet-filter state and compare normalized rules with `policy.hujson`; never infer enforcement from the file alone.
- Add a fixture input mode that performs no network call and accepts only sanitized, recorded netmap structure.
- Emit a stable JSON verdict with `CLEAN`, `DIVERGED`, or `BLIND`, a policy fingerprint, and rule-shape evidence without node names, addresses, identities, or credentials.
- Return exit `0` for CLEAN, `1` for DIVERGED, and `2` for BLIND.
- Treat missing CLI, unreadable netmap, parse failure, and insufficient permission as BLIND; none may become CLEAN.
- Add a `tri_state_exit` wrapped-probe parser to `proprioception.py` so exit `2` maps to unprobeable rather than reconciled or ordinary drift.
- Register the receptor in the default proprioception registry and session-start path without blocking unrelated receptors.
- Make the recorded 2026-08-11 allow-all shape divergent from the proposed policy and a matching shape clean.
- Keep applying policy outside the tool; it observes and reports only.

**Acceptance:**

- Guilt must turn RED: the 2026-08-11 allow-all fixture returns exit `1` and verdict `DIVERGED` against `policy.hujson`.
- Innocence must stay GREEN: the policy-matching fixture returns exit `0` and verdict `CLEAN`.
- Blindness must be explicit: an unreadable netmap returns exit `2` and verdict `BLIND`, never CLEAN.
- Exact commands from repository root:

```bash
python3 -m pytest scripts/tests/test_tailnet_policy_drift.py scripts/tests/test_proprioception_run_wrap_exit_code.py -q
python3 scripts/tailnet_policy_drift.py --policy infra/tailscale/policy.hujson --netmap-fixture scripts/tests/fixtures/tailnet_netmap_policy_match.json
python3 scripts/tailnet_policy_drift.py --policy infra/tailscale/policy.hujson --netmap-fixture scripts/tests/fixtures/tailnet_netmap_allow_all_2026_08_11.json
```

**Seats:** Implementer = Sonnet 5 subagent. Refuter = Kimi K3. Family exclusion binds the DIFF BUILDER's family, not the spec drafter's: builder is Anthropic (Sonnet 5 implementer under an Opus 5 orchestrator); the refuter must be a non-Anthropic family (Kimi K3 default, Codex GPT-5.6 sol for security-class diffs); a diff built by a non-Anthropic seat is refuted by a different family. Final gate = orchestrator Opus 5 xhigh.

**Arming / prove-live:** Wire and test the receptor against recorded fixtures regardless of live console access. On the fleet, CLEAN requires readable enforced state matching the fingerprint; until operator[GUI] applies the policy, retain a PENDING-ARMS row and expect DIVERGED or BLIND.

**Conflicts / order:** The tailnet is currently allow-all and `policy.hujson` is proposed-not-applied. Applying it in the Tailscale console is operator[GUI] and is not authorized by this PR. Policy must precede any team-device expansion.

## PR-3: feat(ledger): operator[secret] ager + weekly digest

**Files:**

- [exists] `scripts/pending_arms_report.py`
- [exists] `scripts/tests/test_pending_arms_report.py`

**Gear:** Gear 1.

**Build:**

- Extend the existing parser with an `operator[secret]` view; do not create a second ledger parser.
- Select only open rows whose owner/action class is `operator[secret]` and exclude every closed row.
- Derive a stable non-reversible fingerprint from the ledger row identity, never from secret material.
- Compute age from an injected clock and normalized opened timestamp so fixture output is deterministic.
- Render a weekly digest containing fingerprint, age, and non-sensitive action class only; omit prose that could contain credentials, PII, endpoints, or recovery details.
- Support machine-readable JSON and stable text ordering for downstream delivery.
- Preserve all L10 PR-1 behavior and tests after rebasing onto its merged implementation.
- Add a fixture with at least three open rows plus one closed row and assert exact inclusion and exclusion.
- Leave transport and actual rotation to the arming boundary; the report command must have no send side effect.

**Acceptance:**

- Guilt must turn RED: a fixture that incorrectly includes the closed row or exposes a ledger payload fails the digest test.
- Innocence must stay GREEN: the digest lists at least three open rotation rows by fingerprint and age, and the closed row is absent.
- Exact commands from repository root:

```bash
python3 -m pytest scripts/tests/test_pending_arms_report.py -q
python3 scripts/pending_arms_report.py --help
```

**Seats:** Implementer = Sonnet 5 subagent. Refuter = Kimi K3. Family exclusion binds the DIFF BUILDER's family, not the spec drafter's: builder is Anthropic (Sonnet 5 implementer under an Opus 5 orchestrator); the refuter must be a non-Anthropic family (Kimi K3 default, Codex GPT-5.6 sol for security-class diffs); a diff built by a non-Anthropic seat is refuted by a different family. Final gate = orchestrator Opus 5 xhigh.

**Arming / prove-live:** After merge, connect the value-free output to the approved weekly healthchecked delivery lane. Record one PENDING-ARMS row until a digest run proves at least three open fingerprints with ages and no closed row; actual rotation remains operator[secret].

**Conflicts / order:** Lane L10 PR-1 also extends `scripts/pending_arms_report.py`. L10 merges first; L13 PR-3 then rebases on it and preserves its interface and tests. Do not implement this PR against the pre-L10 file.

## Needs-ruling carried (Zero only)

1. **Apply `policy.hujson`** — `operator[GUI]` (Tailscale admin console; the fleet deliberately holds no API token). The file is ready; ordering is load-bearing (policy before any team device).
2. **Team tailnet expansion GO/NO-GO** — business decision (phased plan already in memory 2026-08-27; Standard plan <ruled value - Zero> (report proposal: ≈ $8/user/mo at full rollout) is a spend decision).
3. **The three open rotations** — `operator[secret]`(+business where ledgered): Supabase project check (dashboard, never the credential), Google OAuth client revocation on Cloud Console, TP1 key rotate-or-accept given historical 0644. Proof-of-rotation by fingerprint comparison, per the ledger rows.
4. **Chronicle / ChatGPT.app screen recording on M5** — whether an AI vendor app that records the screen may run on a machine with CRM surfaces is Zero's machine-use decision; the receptor (R6) only makes it visible.
5. **Canary service choice** (R7) — if an external canary provider is used rather than a self-minted endpoint: external-service adoption, Zero's call.

## Suspend & ledger rules

- Three RED results from the same cause mean SUSPEND: do not attempt a fourth round.
- On suspension, append one PENDING-ARMS line naming the artifact, repeated cause, owner class, missing arming action, and falsifiable proof required to close it.
- Every built-but-not-armed wrapper migration, live receptor, policy application, digest delivery, or rotation gets exactly one PENDING-ARMS row.
- A suspended security boundary cannot be waived by logging more environment data, exposing credential values, or asking a vendor seat to diagnose the host.

## Out of scope

- Applying `policy.hujson`, adding team devices, rotating or revealing credentials, inspecting external-seat environments, secret-zero trifecta migration, PII regression lint, screen-recorder receptor, and canary lattice.
- Any client PII, raw OSINT, credential value, secret-bearing ledger prose, outward publication, or autonomous operator[GUI]/operator[secret] action.
