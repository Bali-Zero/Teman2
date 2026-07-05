# IMMUNE FORGE — scar-family antidotes promoted to executable enforcement

- **date**: 2026-07-05
- **machine**: Mini-Pro2 (session `fable-immune`, worktree `.worktrees/infra-immune-forge`)
- **mandate**: `~/.fable-mandates/immune.md` — turn the antidotes of the 10 cicatrix superscar
  families (`.claude/rules/cicatrix-superscar.md`) from prose into guardians that REFUSE, in
  ROI order: #3 guard conformance, #1 HOME-fork lint, #4 secrets permissions, #2 pending-arms
  reconciliation, stretch #7/#9/#10.
- **loop**: modus Gear 3 (GROUND → DESIGN → BUILD → VERIFY → SHIP+ARM → PROVE → CAPTURE)
- **sources**: cicatrix-superscar.md + cicatrix-scars.md (W68/W72/W73/W82-W85 bodies re-read on
  disk) · proprioception.py home_fork probe · infra/scar-gates/ + MANIFEST · hook-innocence-gate
  vaccine suite · Codex GPT-5.5 red-team ×2 (design pass + diff pass) · first live runs on Mini.

## What shipped (4 PRs + 1 in flight)

| PR | Family | Artifact | State |
|---|---|---|---|
| #1970 | **#1 HOME-fork** | `scripts/lint_home_fork.py` + `infra/home-fork/declared-pairs.json` (11 pairs) + 23 tests + `immune-enforcement.yml` CI | **MERGED**, blob-verified on main |
| #1971 | **#4 Secret-in-clear** | `scripts/secrets_permissions_audit.py` + 19 tests; live `--fix` on Mini | **MERGED**, blob-verified |
| #1972 | **#2 Esiste≠Armato (W81)** | `scripts/pending_arms_report.py` + 18 tests | **MERGED**, blob-verified |
| #1973 | **#3 Guard-over/under-match** | `infra/guard-conformance/` registry + enforcer + `guard-conformance.yml` + W85 pin + red-team hardening | **OPEN — operator merge by design** (guardrail-critico, no auto-merge) |
| #1975 | **#7 KeepAlive misconfig** (stretch) | `scripts/lint_plist_keepalive.py` + 24 tests + branch-cleanup plist XML fix | auto-merge armed |
| docs PR | close | superscar ANTIDOTO pointers + PENDING-ARMS lines + this report | this PR |

Every exit contract is fail-visible (W84 discipline): `1|2` = findings, `4`/`2` = the scan
itself could not see (blind/partial) — a guardian that cannot see never reports clean.

## What the tools found on their FIRST live runs (the forge already bit)

1. **A live HOME-fork caught in the act**: `~/scripts/mlx-server-run.sh` (Mini, 20-giu) diverges
   from repo canon `infra/launchagents/wrappers/mlx-server-run.sh` (03-lug). Comment-only drift
   today — but this is exactly how W50/W81 start. Realign = operator (HOME writes beyond chmod
   were outside this session's boundary).
2. **18 undeclared HOME-executed payloads** on Mini (plists + crontab): 4 had byte-identical repo
   twins → declared as pairs on the spot; 1 divergent (mlx above); **13 have NO repo source of
   truth at all** (wa-mirror-runner, wr2-warroom-sync, zero-design/run.sh,
   fly-pg-tunnel-from-config ×2, mini-git-pull-bridge, ollama-warm-pin.sh, openclaw-cron ×3,
   WR2Control.app, local-livekit ×2) — each is a W50-class fork waiting to happen; triage line
   in PENDING-ARMS.
3. **A corrupt LaunchAgent**: `com.nuzantara.daily-gsc-indexing-sweep.plist` (ExpatError line 11,
   mtime 07-giu, not loaded) — surfaced as an operational error, not silently skipped.
4. **14 credential-named files with 0644** on Mini (13 memory `*.md` named after tokens/api-keys
   + 1 `tokens.json` backup) → tightened to 0600, re-verified 0 residual across 3902 files.
5. **W81 theater inside the immune system itself**: `test_w83_remote_dispatch.py` (21 cases) and
   `test_w84_strip_noise_cross_line.py` (22 cases) existed since their scars but **no workflow
   executed them** — they satisfied naive "is it armed?" checks via path-filter substrings only.
   `guard-conformance.yml` is now their direct executor (both green at day 1).
6. **Ledger truth**: first `pending_arms_report.py` run on the real ledger: 7 open entries —
   3 TECH-DEBT overdue, 1 OPERATOR-GATED overdue, 3 legitimate FIREBREAKs, 0 malformed.
7. **W85 confirmed still open in code**: `BLOCKED_SUBCMD_RE` still carries bare `stash`
   (`worktree_isolation.py:105`) — read-only `git stash list/show` still blocked. Now PINNED
   (`test_w85_stash_readonly.py`, W82-tripwire semantics: green while the bug is present AND
   documented; flips loudly when the fix lands). Fix deferred on purpose: repo-only patch would
   HOME-fork the live hook (W83 GOTCHA-d), and the live copy governs the very session editing it.

## Verification story (generator ≠ grader, enforced)

- **Two Codex GPT-5.5 red-team passes** (agy seat dead on Mini — declared, cascaded): the design
  pass produced 25 findings (blind-scan bit, crontab rc/stderr semantics, `.worktrees`-as-OK
  rejection, `${HOME}` normalization, day-precision overdue rule — all folded in); the diff pass
  on #1973 produced 12 findings, 4 fixed same-PR (sentinel paths covering all registered
  surfaces, W83/W84 direct execution, transitive arming proof for delegated gates, exempt-symbol
  staleness), the rest accepted-as-limits and documented in the enforcer's docstring.
- **The enforcer refuted its own author twice**: the C3 anti-phantom rule rejected 2 wrong
  symbol→test links in the first draft of the registry (W83's suite exercises
  `_is_remote_dispatch`, not the regex name; W79's exercises `_write_hits_main`, not
  `_extract_write_targets`). Exactly the W65 lesson, fired against the person who wrote it down.
- **Guilt-probe of the enforcer**: a phantom `_guard_probe_unregistered_reply` appended to the
  bridge (worktree copy) → exit 1 with an actionable message; file restored byte-identical;
  conformant state exits 0.
- **Every subagent claim re-verified on disk**: implementer test suites re-run by the
  orchestrator; merged files blob-compared (`git rev-parse origin/main:<f>` vs branch blob, W88
  discipline, never three-dot).

## Gotchas captured (new scar-grade material)

- **The test suite that mutated the live HOME** (#4-family, new vector): the first version of
  the secrets-audit fix-test passed `--root tmp` which EXTENDED default roots → `pytest` chmod'd
  14 real files in `~/.claude` as a side effect (discovered via ctime forensics 18:14:28, not
  via the test output). Cure: `--no-default-roots` isolation for every `main()`-level test.
  Lesson: *a test that touches `Path.home()` defaults is a live-fire exercise, not a test* —
  candidate for a scar entry and for the karpathy-discipline checklist.
- **Sandbox/TCC partial blindness produced a false-clean**: the very first live secrets run
  reported `FINDINGS: 0` while 14 existed — the sandboxed environment hid part of `~/.claude`
  and `os.walk(onerror=None)` swallowed it. Cure shipped: traversal stats + BLIND-scan guard
  (exit 2, "do not read as clean"). The W84 dead-green family extends to *scans*, not just crons.
- **The guardrails static hook over-matched a diagnostic grep** during this very session (a grep
  whose PATTERN contained `rm -rf` + a `cd` in the same compound was blocked as a destructive
  command): live specimen of #3 on the guardrails surface. Report-only today; the pattern-in-arg
  vs pattern-as-command distinction belongs in `test_guardrails_core_overmatch.py`'s corpus.
- **Census agents can be slower than doing it yourself**: two Explore subagents dispatched for
  the guard/vaccine census never returned within the session's working window; the census that
  actually shipped was done first-hand with targeted greps in ~15 minutes. Fan-out has a
  latency floor — for bounded, precision-critical censuses, the orchestrator's own eyes win.

## Addendum — late census deliveries (arrived at session close; claims re-verified first-hand)

The two census agents DID eventually deliver, hours late, and two findings were load-bearing:

1. **Claude-hooks live-drift on Mini** (#1 family, cmp-verified by me): `host_boundary.py`,
   `dispatch_nudge.py`, `orchestrate_gate.py`, `stadio_zero_nudge.py` all diverge repo↔
   `~/.claude/hooks/`, and `_phase.py` is MISSING live (`install_phase_aware.sh` never ran here).
   This drift was invisible to every automated gate — and it mechanically explains why
   `orchestrate_gate` kept biting this session: the live copy lacks the phase-aware relax the
   repo already has. Ledger line filed (fold-in + declare the 5 pairs in declared-pairs.json).
2. **The scar-gate registry is TWO registries, and only one is CI-consumed** (adjudicated
   first-hand): `verify_the_verifiers.py` reads `verify_the_verifiers_gates.yaml`; MANIFEST.json
   feeds only the manual `run_scar_gates.py`. Consequences: (a) my own #1973 checker's
   delegated-armed proof read MANIFEST — a W81 theater specimen inside the anti-theater tool,
   fixed same-day (3rd hardening commit: proof now reads the YAML); (b) the homefork scar-gate
   test is executed by NO workflow — ledger line filed for its arming. The guard census also
   confirmed all 10 bridge guards carry guilt+innocence redundantly (named tests + a ×3-language
   matrix with structural completeness meta-gates) — stronger than my registry assumed — and
   flagged two untested bare-substring matchers (`_tool_mandates`, `_villa_answer_language`
   fallback) as future conformance candidates.

Lane 3's remote report-only sweep of Pro (57 findings; 2 REAL live `.env` at 0644 worth
rotation review, ~34 jiti-cache false positives → PRUNE follow-up) is folded into the ledger.

## §Meta-pattern (the malattia-delle-malattie, mandatory)

**Every guardian is born watching something else and dies of the diseases it watches.** All four
lanes converged on the same second-order fact: the enforcement layer itself exhibits the scar
families it polices —

- my home-fork lint over-matched on its first run (log sinks as "payloads": #3 inside a #1 tool);
- my keepalive linter over-matched on ITS first run (exec-into-server flagged as one-shot: #3
  inside a #7 tool — demoted to WARN after live calibration);
- the secrets audit produced a W84 dead-green (blind scan reading as clean: #2 inside a #4 tool);
- its test suite HOME-forked reality by chmod-ing live files (#1/#4 inside the tests);
- the vaccine's own W83/W84 suites were W81-theater (armed-looking, never executed);
- my conformance checker's delegated-armed proof read the registry no workflow executes
  (W81 theater inside the anti-theater tool — caught by the census, fixed same-day);
- the guardrails hook over-matched the investigation of over-matching.

The corollary is structural, not moral: **guardians need guardians, but the second level must be
CHEAP and SELF-APPLIED** — guilt+innocence proofs for every detector (the lint's own 23/19/18
tests), blind-scan self-probes (traversal stats), pins for documented-broken contracts (W85),
and an enforcement census so the set of guardians itself cannot drift (guard-conformance C1).
That is one rung of reliability recursion — and it terminates at the operator gate, by design
(A4 terminology note 2026-06-28: this is self-healing, not RSI).

## §Solo-operatore (actions only Zero can take)

1. **Review + merge PR #1973** (guard-conformance gate — opened without auto-merge by mandate
   rule 4). Then, if wanted as hard gate: flip `guard-conformance` to a REQUIRED status check in
   branch protection.
2. **W85 fix fold-in**: patch `BLOCKED_SUBCMD_RE` in repo AND live `~/.claude/hooks/` in the same
   operation (the pin + registry note flip in the same PR).
3. **agy re-login on Mini** (GUI/interactive — OAuth timed out in ssh/tmux; the width seat is
   dead on this node until then).
4. **mlx-server-run.sh realign** on Mini (`cp` from repo canon; HOME writes were out of my
   boundary), and the **corrupt gsc-indexing plist** (repair or delete).
5. **Secrets sweep on Pro + M5** (run `secrets_permissions_audit.py --fix` after their next pull
   — or leave to my next resident session on each; PENDING-ARMS carries it either way).
6. **Triage of the 13 orphan HOME payloads** on Mini (promote to repo or allow-list; two belong
   to currently-fenced lanes: local-livekit, mini-sync).

## Stretch status

- **#7 KeepAlive-vs-one-shot plist linter**: SHIPPED (PR #1975). Day-1 calibration on the real
  repo forced an honesty demotion — the first version flagged all 8 `exec` wrappers as FAIL, but
  sampling proved them exec-into-long-running-servers (the correct daemon idiom): plain `exec`
  is now WARN-class (`--strict` elevates), `nohup &` stays FAIL. The 8 warns are the operator
  triage list. Bonus: the linter's first run found a SECOND malformed plist, this one TRACKED —
  `com.nuzantara.branch-cleanup.weekly.plist` carried `--apply` inside an XML comment (`--` in a
  comment is illegal XML; plutil tolerates it, expat rejects it) — fixed in the same PR.
- **#9 content_on_main coverage**: audited. The blob-per-file cure exists only inside
  `branch_graveyard_cleanup.sh`; the worktree reaper (`agent_start.py --cleanup`) still decides
  via `merge-base --is-ancestor` — W88's lying proxy, but in the FAIL-SAFE direction (zombies
  accumulate; nothing is destroyed). Documented as a PENDING-ARMS line with the cure design
  (content_on_main as additional evidence, never sole trigger). No code change today: reap logic
  is high-blast-radius and the current failure mode is the safe one.
- **#10 expected_node audit**: not executed (fuel spent on closing quality). The W67c/mata-garuda
  antidote (`assigned_node` + graceful-exit) remains prose; noted for a future mandate.

## Numbers (Law 7)

- 4 PRs shipped, 3 merged + blob-verified, 1 operator-gated open; ~3.1k insertions.
- 60 unit tests written and green (23 + 19 + 18) + guilt-probe + blind-canary, all re-run by the
  orchestrator, not trusted from implementers.
- Enforcement census: 10 bridge guards + 8 hook entries + guardrails core + 1 delegated
  under-match sentinel; 0 conformance violations at ship; 2 previously-unexecuted regression
  suites (43 cases) now CI-armed.
- Live yield on Mini day 1: 1 live fork + 13 orphan payloads + 1 corrupt plist + 14 permission
  fixes + ledger classified (3 overdue debts).
