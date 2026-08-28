---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
type: index+synthesis
status: complete
lanes_complete: 13/13
---

# BEYOND-SOTA PANEL — index & cross-lane synthesis

Mandate (Zero, 2026-08-28): analyze how this organism practices coding and every art of implementing,
architecting and designing; split it into coherent parts; run one Fable-5 max-effort lane per part
that grounds itself in the repo, deep-researches the world's best systems for that part, and
recommends how to go BEYOND the state of the art. Protocol: `2026-08-28-beyond-sota-panel-PROTOCOL.md`.

## The 13 parts

| # | part | report | status |
|---|---|---|---|
| 1 | Intake, triage & specification | `2026-08-28-beyond-sota-intake-triage-specification.md` | complete · gated |
| 2 | Context engineering & grounding | `2026-08-28-beyond-sota-context-engineering-grounding.md` | complete · gated |
| 3 | Architecture & design decision-making | `2026-08-28-beyond-sota-architecture-decision-making.md` | complete · gated |
| 4 | Implementation craft (BUILD) | `2026-08-28-beyond-sota-implementation-craft.md` | complete · gated |
| 5 | Verification, adversarial review & final gate | `2026-08-28-beyond-sota-verification-adversarial-gate.md` | complete · gated |
| 6 | CI, merge queue & ship pipeline | `2026-08-28-beyond-sota-ci-merge-queue-ship-pipeline.md` | complete · gated |
| 7 | Deploy, release & prove-live | `2026-08-28-beyond-sota-deploy-release-prove-live.md` | complete · gated |
| 8 | Observability, immune system & self-healing | `2026-08-28-beyond-sota-observability-immune-self-healing.md` | complete · gated |
| 9 | Multi-agent orchestration, fleet & cost/quota routing | `2026-08-28-beyond-sota-multi-agent-orchestration-fleet-routing.md` | complete · gated |
| 10 | Organizational learning loop | `2026-08-28-beyond-sota-organizational-learning-loop.md` | complete · gated |
| 11 | Product, UX & visual design craft | `2026-08-28-beyond-sota-product-ux-visual-design.md` | complete · gated |
| 12 | Data, schema & migration engineering | `2026-08-28-beyond-sota-data-schema-migrations.md` | complete · gated |
| 13 | Security, secrets & PII engineering | `2026-08-28-beyond-sota-security-secrets-pii.md` | complete · gated |

## How the panel actually ran (measured, in order)

| launch | shape | outcome |
|---|---|---|
| 1 (22:2x WITA) | 5 `fork` subagents on Fable 5 (inherit ~90K tokens of session context each) | all 5 died on the account session limit within ~2 min; 0 bytes on disk |
| 2 (22:35) | 5 fresh-context lanes pinned `model: fable`, tmux panes, second seat | all 5 died the same way within ~3 min; 0 bytes on disk |
| 3 (22:58) | 2 pinned lanes (3, 4) on a third seat measured at 3% of 5h / 91% weekly | alive and productive (4.4K/4.6K words, §1-4 in ~12 min) — stopped by the orchestrator on a false "blocked" belief; their files carried over |
| 4 (23:10) | 13 headless `claude -p` processes, one OAuth seat per lane (≤2 lanes/seat), `--allowedTools` whitelist, `--effort max`, incremental+resumable reports, quota rotation | see per-lane status above; seat pings at launch: slot 1 weekly limit (reset 30/8 09:00), 5 session limit (01:40), 6 Team limit (03:30), 4 alive, 2/3 slow-boot |

Lessons already captured: memory `discovery_fable_fan_out_burns_a_seat_in_minutes_headless_multi_seat_is_the_shape_2026_08_28`,
AMENDMENTS 2026-08-28 entry, protocol §4bis.

## Sibling panel (same day, different axis)

The M5 session runs a parallel beyond-SOTA program partitioned by **system anatomy** (16 lanes:
B1 rag-retrieval-engine, B2 llm-gateway, B3 omnichannel-bot, B4 crm-intake-documents, B5
client-portal-billing-compliance, …; worktree `.worktrees/ops-beyond-sota-0828` on M5, spec
`00-MANDATE-AND-PARTITION.md`). This panel is partitioned by **engineering craft** (13 lanes: how we
intake, decide, build, verify, ship, observe, learn, design, model data, secure). They are
complementary, not duplicates: a B-lane says what a given organ should become; a craft lane says how
any organ gets built and kept alive. Delivery on the M5 Desktop keeps them side by side:
`~/Desktop/beyond-sota-2026-08-28/` (B-lanes at the root) and
`~/Desktop/beyond-sota-2026-08-28/engineering-craft-13-lanes/` (this panel).

## Final on-disk gate (orchestrator, Fable 5 interactive — never delegated)

Per report: all 10 sections present · ≥10 distinct external URLs · every repo path cited as
"exists today" re-checked on disk (paths under §5/§6 are proposed artifacts, not claims) · no
email/phone/secret-shaped strings. Gate script: scratchpad `panel/gate.py` (throwaway).

## Cross-lane synthesis (13/13 lanes — panel closed 2026-08-29 00:00 WITA, ≈85,044 words across the 13 reports)

### A. Where the organism is genuinely AHEAD of the surveyed world (each claim is measured in its lane)

- Intake classification and grounding: a CI-recomputed gear floor+ceiling and an entry gate that never blocks judgment — no equivalent in Spec Kit, Kiro, Anthropic practice or the change-risk literature (lane 1).
- How a decision is *argued*: cross-family asymmetric councils, a CI lint that rejects unwarranted deliberation, per-finding adversarial dispositions (lane 3).
- Git-tree isolation: the worktree broker (TTL, RAM admission, 2-AND reap, fleet placement) has no surveyed match (lane 4).
- Verification doctrine: executable generator≠grader, family-exclusion backed by the W100 measurement, guilt+innocence conformance 38/38, a never-cascading final gate on a CI-recomputed floor (lane 5).
- Merge-queue correctness (ALLGREEN, evidence-curated required checks) and a queue-trap corpus nobody has published (lane 6).
- Deploy frequency and post-deploy *truth*: ≥8 deploys/day, 15/15 green, 401-vs-503 split-brain probe, ancestry-semantics frontend sentinel, an *exercised* monthly restore drill (lane 7).
- Failure semantics: DEAD-GREEN taxonomy, guardian-of-guardians, alarm↔cure CI linting (lane 8).
- Routing that carries judgment: invariant-carrying fleet topology, family-exclusion as a routing constraint, measured effort economics no lab publishes (lane 9).
- Deciding what a design should be: adversarially-refuted design study loop, constitutional WR2 critic, computed-contrast token contract (lane 11).
- Migration authoring: 97.7% rollback coverage, migration-as-ADR headers, 5 CI gates, lint-enforced durability doctrine (lane 12).
- The Law-2 PII output boundary, the insider/RBAC model and the incident memory (lane 13); the typed, integrity-linted, family-compressed scar corpus (lane 2).
- Capture and compression of lessons: a push-injected, CI-budgeted, guilt/innocence-guarded scar corpus is a working industrial instance of what the field has only *named* ("system prompt learning") and the structural inverse of the NASA-LLIS graveyard — 70% of 164 scars carry an executable antidote, 49% cite an earlier scar (lane 10).

### B. The meta-disease — one belief, twelve costumes

Every lane's §Meta-pattern names the same defective belief: **"what was written / built / emitted / announced IS what is in force."** It is superscar family #2 (esiste ≠ armato) lifted one level: the organism monitors its organs, not the meta-layers that certify, deliver, decide, declare, isolate, observe, expose and secure them.

| lane | the belief | the number that falsifies it |
|---|---|---|
| 2 | written = read | auto-injected surface **774 KB ≈ 190–220K tokens**, 5× in 7 days; the only armed budget guards 1.8% of it |
| 5 | a verifier, once written, keeps verifying | 66 scar gates, 2 armed; 6/24 stated invariants enforced nowhere; a 24/73-red test no workflow runs; correction tax ~12–13% of commits |
| 1 | declared = bound | acceptance/assumptions/budget declared, only the gear bound by CI; 27/200 corrective commits; a 44 h / 8.6 M-token blowup |
| 4 | isolating the tree = isolating the work | 60 tests red in a worktree / green in CI on the same commit; 13/14 spawns ENXIO; PR p90 = 1,292 lines vs the 400 contract; 85.8% Sonnet dispatches against the workhorse-first ruling; fix-share of main commits 30.6% |
| 3 | a well-argued decision keeps itself | ADR organ dead since 2026-03-22; decisions in ≥6 locations with no status/supersedes/revisit; the governing skill cites a file that never existed |
| 6 | the artifact GitHub hands you = the entity | 39% of open PRs DIRTY on fixed shared files; Backend Tests ~2.5× per merged PR; median open→merge 61 min; the queue never batches |
| 7 | the control plane's announcement = the data plane | health=200 over a dead worker; READY deployments serving yesterday; a green Build Guard verifying nothing; `applied_by='system'` over superuser hands; dark→5%→100% designed, never ridden |
| 8 | a signal, once emitted, = information | 81.2% of ledger rows overdue; escalations median 30 days; MTTD/MTTR uncomputable (10 disjoint state formats); 34.6% of a month's Telegram was one unactionable alarm; 28% of Sentry errors dropped |
| 9 | a routing rule in prose = a router | quota discovered by dying (two launches burned 2 seats + 10 lanes in ~5 min on a weekly cap invisible at dispatch); 75 endpoint cards, 0 calibration records, no live reader |
| 11 | verify where I control = the experience | 0 of 6 measured 2026-08-28 production defects caught by the 53-spec e2e suite; 3+ live palettes vs one refuted identity |
| 12 | the schema = the contract | 22 prod tables not owned by the app role; catalog/codec/reader/provenance layers invisible to tests; 5 incidents in 20 days from one belief |
| 13 | the machine = the trust boundary | every codex/agy/kimi child inherits the session env (PAT + tokens, one vendor-bound print confirmed); one public credential unrotated ~7 months |
| 10 | a lesson captured = a lesson armed | PENDING-ARMS **280 of 441** open rows overdue; scar capture declining May 56 → Aug 18/month; modus-bench dormant since 07-07; AMENDMENTS silent during both August bursts; superscar bridge saturated at 13,986/14,000 bytes; the overdue-alarm itself had never fired |

### C. The cure-class (what "beyond SOTA" concretely means here)

The organism already owns the antidote shape — the receptor, the tripwire, the guilt+innocence test, "read the OUTPUT not the color" — and has applied it to organs and cron jobs far more thoroughly than to its own meta-layers. Every lane's recommendations reduce to one move in different tissues:

1. **Put the meter on the consumption/enforcement side**, not on the artifact: attest what a session actually receives (2); re-prove that a guard can still go red (5); bind a declared acceptance to a runnable probe (1); price every signal and verify its consumer (8); read the entity, never GitHub's proxy field (6).
2. **Enforce at a door that already exists, as code, never as a blocking gate on judgment** — the gear floor and the receptor-not-rule ruling are the two precedents (1, 6, 9).
3. **Move the judge to where reality is**: the anonymous visitor in production (11, 7), the prod catalog rather than the CI role (12), the enforced tailnet netmap rather than the policy file (13).
4. **Shrink the trust and budget unit from machine/session to process/seat** (13, 9, 4): minimal per-seat env for every external CLI, seat-state ledger with a pre-dispatch budget check denominated in OAuth windows, resources(w₁)∩resources(w₂) declared and brokered — not just trees.
5. **Conservation of adversariality**: whatever skepticism targets the work must recursively target whatever certified the work (5), delivered it (2), decided it (3), announced it (7), captured it as a lesson (10).

### D. Top-10 beyond-SOTA moves across lanes (de-duplicated, ranked by impact × confidence / cost)

1. **Read-side attestation + scar cold storage** (L2) — 774 KB → ≤120 KB injected; a receptor that measures what a real session receives at turn 1. Urgent: every session currently boots at the edge of the measured context-rot zone.
2. **Production journey sentinels derived from scars + dead-man that flips the flag OFF** (L11 + L7) — every cured UX defect becomes a scheduled production probe with guilt+innocence self-test; probe silence flips `GARUDA_PUBLIC_ENABLED` off via the existing allowlist actuator. Would have caught 2–3 of the 5 defects of 2026-08-28.
3. **Seat = trust unit + budget unit** (L13 + L9) — `with_seat` broker (minimal env per external CLI dispatch; secret-shaped env names per child ≥3→1) and a seat-state ledger with pre-dispatch budget check in OAuth-window currency; `fleet_burst` (account-sharded headless fan-out, ≤3 spawns, incremental outputs) as a first-class command.
4. **Meter every declared contract** (L1 + L4) — acceptance-bullet→probe lint and an enforced `appetite:` field at the pack-lint door; per-lane outcome telemetry (correction-chain rate, time-to-green, builder attribution from the branch namespace); check-gated stop (`.lane-check.json` consumed by all four termination surfaces).
5. **Verify the verifiers** (L5) — quarterly grader scorecards on a labeled corpus extracted from adjudicated scars/retractions; sampled receipt re-execution at the verdict gate; a re-qualification calendar for every required check; **antidote-liveness lint** — a cure a scar names must still exist AND still be wired into a workflow (L10).
6. **Queue economics** (L6) — batch 1→3 with a symmetric path sentinel + trigger-symmetry lint (runner-min/PR 121–138 → <80; median 61 → ≤40 min); conflict-by-construction linter at PR-open (DIRTY 39% → <10%); the `mq state` oracle encoding the 19 traps.
7. **Signal economics** (L8) — burn-rate + dual-window math on PENDING-ARMS/escalations (error-budget calculus on a debt ledger); CI schema-handshake between every health emitter and its consumers (kills the W120 class); OTP-style restart budgets for a `supervised` organ class + one wide-event stream so MTTR becomes computable; **PENDING-ARMS burndown ratchet** + monthly FixIt sweep + schema-self-testing digest sentinel, and **replay drills** per superscar family (Wheel-of-Misfortune as weekly mutation-verified fixtures) — measure the loop by armed-antibodies-per-week, never scars-per-week (L10).
8. **The data contract's four hidden layers** (L12) — catalog contract probed from prod and replayed in CI as the real role topology; codec-parity cure + lint banning bare `create_pool` in tests; provenance columns (`applied_as`/`applied_via`) and checksum-verified `schema_audit`.
9. **Decision afterlife** (L3) — a decision registry with a status machine and a revisit receptor (findability 6 locations → 1 query); council-yield instrument; doctrine citation-integrity lint (≤150 lines, zero phantom sources in the law).
10. **Deploy parity as receptors** (L7 + L9) — served `?dpl=` must change after bundle-path merges; every live `*.balizero.com` surface names its repo source; `flags.yaml` as the two-platform flag SSOT with lint; conductor calibrations distilled from shipped Evidence-Pack outcomes.

### E. Needs-ruling (consolidated — only Legge-5 / credential / GUI items)

- **Governance**: who decides structure — SYMBIOSIS Law 5 vs CLAUDE.md §2 give opposite answers (L3) · the context budget number (L2; precedent: the ruled 17 KB MEMORY.md target) · whether an exceeded `appetite` suspends by default (L1) · registry bindingness and blind-gate default (L3) · effort default per gear floor (L9, already ledgered as `operator[business]`) · whitelist-vs-CODEOWNERS intent for the 24/73-red orphan test (L6) · harvester promotion policy — who may turn a shadow proposal into an enforced gate, even one rule at a time (L10) · batch-retirement semantics for PENDING-ARMS rows (a signed WON'T-ARM rule in the ledger header) (L10) · monthly FixIt-sweep quota, feature velocity vs debt burndown (L10) · cadence and format of the "decided autonomously" digest (L10).
- **Spend / resources**: Antigravity arm-or-retire (L4) · Pro disk headroom for hermetic caches (L4) · Sentry quota purchase (L8) · TP1 credit thresholds for burst use (L9) · team tailnet expansion GO/NO-GO (L13) · advisory-DB snapshot in the blocking security path + Detect Secrets diff-scoping (L6).
- **Credentials / GUI / physical**: apply `policy.hujson` on the Tailscale console, in that order before any team device (L13) · the three open rotations (L13) · TCC re-grants for DEAD-GREEN launchd jobs (L8) · per-batch ack for retiring canon-less live plists (L8) · Chronicle/ChatGPT.app screen recording on M5 (L13) · standing authorization for the temporary-GRANT ceremony (L12) · sandbox payment credentials and real-fire authority for the dead-man (L7) · Actions secrets for the Qdrant restore-drill leg (L7) · cswap/OAuth profile swapper install (L9).
- **Product**: `/dream` public or gated · `/prime` Google Maps key expired · `/exclusive` unfinished or intended · VOA dark state as bare 404 · experiments on real prospects + consent copy · `/visa/match` investor >500M → E33G misroute (all L11) · crypto-shredding scope and Qdrant estate disposition (L12) · exposure-changing flag flips stay owner gestures (L7).

### F. Proposed first wave (three PRs, three organs, one cure — ready to open on GO)

1. `feat(context): read-side attestation of the injected surface + scar bodies back to cold storage` (L2 R1) — Gear 2, ≤400 lines; acceptance: a fresh headless session reports the delivered surface ≤120 KB and the attestation receptor goes RED on a synthetic 200 KB injection.
2. `feat(probes): production journey sentinel for the VOA funnel, dry-run dead-man` (L11 R1 / L7 R1) — Gear 2; acceptance: the probe fails RED on each of the five 2026-08-28 defect fixtures replayed, and stays GREEN on prod today; dead-man in dry-run + Telegram until Zero's real-fire GO.
3. `feat(fleet): with_seat broker — minimal per-seat env for external LLM dispatch` (L13 R1) — Gear 2; acceptance: `env` observed by a codex/agy/kimi child under the broker carries exactly the seat's own credential; a fixture lane with a leaked PAT turns the lint RED.

### G. The numbers this panel measured tonight (for the ledger)

774 KB injected context (5× in 7 days) · 39% open PRs DIRTY · Backend Tests 2.5×/PR, 61-min median open→merge · PR p90 1,292 lines vs 400 · 85.8% Sonnet dispatch vs workhorse-first · fix-share 30.6% of main commits · correction tax 12–13% · 81.2% ledger rows overdue, escalations median 30 d · 0/6 prod defects caught by 53 e2e specs · 66 scar gates / 2 armed · 6/24 invariants enforced nowhere · 22 prod tables not app-owned · 97.7% migration rollback coverage · ADR organ dead since 2026-03-22 · two seats + 10 lanes burned in ~5 min by the panel's own first launches · 280/441 PENDING-ARMS rows overdue · scar capture 56 → 18/month · modus-bench dormant since 07-07 · superscar bridge 13,986/14,000 bytes.

### H. First-PR candidates per lane (extracted from each report's §6 — or §5 where §6 points there; leads, not commitments)

Rows for lanes 1-9 and 11-13 were extracted by a separate read-only lane and spot-checked against the reports by the orchestrator (12 title fragments grepped, all present); lane 10's rows were taken by the orchestrator directly from its §6. The files named are the *report's* proposals — most do not exist yet; the acceptance column is the report's own falsifiable test. Lane numbering follows the partition table above.

| lane | PR title (as written in the report) | files (≤3) | gear | acceptance test | wave |
|---|---|---|---|---|---|
| 1 | PR-1 `feat(evidence): acceptance-as-probe lint (notice mode) + baseline report` | `scripts/evidence_pack_lint.py`, `scripts/tests/test_evidence_pack_lint.py`, para in `docs/factory/ASSEMBLY-LINE.md` | 2 | Selftest green; fires on synthetic probe-less pack, silent on live visa-retention pack (innocence) | 1 |
| 1 | PR-2 `feat(evidence): assumptions register block + lint notice` | same files as PR-1 | 2 | Notice names each unverified assumption; zero-assumption brief passes silently | 1 |
| 1 | PR-3 `feat(evidence): appetite block + appetite_exceeded acknowledgment rule` | linter+tests+TRIAGE para in `.claude/skills/modus/SKILL.md` | 2 | Pack exceeding declared rounds without acknowledgment fails the lint selftest | 2 |
| 2 | PR-1 `chore(context): scar re-cold-storage + injected-surface attestation` | `docs/scars/` (git mv target), `lint_scar_number_collision.py`, `scripts/tests/test_injected_surface_budget.py` | 2 | Fresh session transcript shows attestation line total ≤120 KB; `scar query W76` still resolves | 1 |
| 2 | PR-2 `fix(repomap): rank-truncate to hard 20 KB cap` | — | 1 | `wc -c ~/.nuzantara-repomap.txt` ≤20,480 after next cron tick; probe goes red if not | 1 |
| 2 | PR-3 `feat(eval): scarbench v0` | — | 2 | One table in PR body — recall@3 for {full-injection, bridge-only, grep-cascade} on 99-scar set | 1 |
| 3 | W1-PR1 `docs(decisions): decision registry v0 — schema, backfill, collision+coverage lint` | `docs/decisions/registry.yaml`, `scripts/lint_decision_registry.py` (+test) | 2 | Reused number → red (fixture); every `evidence:` path resolves; ADR-001 marked `superseded-by` | 1 |
| 3 | W1-PR2 `chore(doctrine): citation-integrity lint + cure the sota-architecture-loop phantom` | `scripts/lint_doctrine_citations.py` (+test), skill line 11-12 edit | 1-2 | Red on phantom pre-cure, green post-cure; innocence fixture (path in code block ≠ citation) | 1 |
| 3 | W2-PR1 `feat(evidence): council block in pack.yml + council_yield_report.py` | `pack.yml`, `council_yield_report.py` | 2 | Report runs on ≥5 historical packs; a 0-applied council emits the AMENDMENTS line | 2 |
| 4 | PR-1 `feat(hooks): lane check contract — .lane-check.json gates the stop boundary` | `infra/claude-hooks/lane_check.py`, `infra/claude-hooks/subagent_stop_verify.py`, `infra/claude-hooks/test_lane_check.py` | 2 | Failing check → stop blocked quoting stderr; no `.lane-check.json` → byte-identical (innocence); tautological check flagged | 1 |
| 4 | PR-2 `feat(telemetry): lane_outcome_report — correction-chain, time-to-green, builder attribution` | `scripts/lane_outcome_report.py`, `scripts/tests/test_lane_outcome_report.py`, SEAT-MIX append | 2 | Reproduces 27-of-200 correction count within ±3 on 08-20..22 window; builder attribution ≥80% | 1 |
| 4 | PR-3 `feat(ci): pr_size_taxonomy — typed exceptions for the 400-line contract (advisory)` | `scripts/pr_size_taxonomy.py`, advisory workflow, tests | 2 | Classifies the 26 measured over-400 merges, assigning a class to ≥20; report-only, zero gating | 1 |
| 5 | `feat(verify): hermetic verification runner + W121 census` | `scripts/hermetic_verify.sh`, workflow edit, `scripts/tests/test_hermetic_census.py` | 1-2 | Self-canary run flips a byte and harness goes red; census fails on deliberately-bare invocation fixture | 1 |
| 5 | `feat(verify): correction-tax KPI` | `scripts/correction_tax.py` + ledger + SessionStart line | 1 | Reproduces 106/866 on the frozen window; weekly row appended | 1 |
| 5 | `fix(council): launcher docstring names the ruled gate seat` | `scripts/launch_worker_plane_review_panel.py` (1-line) + doctrine-conformance grep test | 1 | New test fails when docstring and modus taxonomy disagree on the gate seat | 1 |
| 6 | 1. `ci(queue): trigger-symmetry lint — pull_request and merge_group path filters must match` | `scripts/ci/lint_trigger_symmetry.py`, `scripts/tests/test_lint_trigger_symmetry.py`, `immune-enforcement.yml` hook | 2 | Guilt fixture exits 1; innocence exits 0; live tree reports current asymmetries as dated allowlist | 1 |
| 6 | 2. `feat(mq): mq state — the queue-state oracle` | `scripts/mq.sh` (+verb), `scripts/tests/test_mq_state_oracle.sh` | 2 | Every trap-derived fixture yields the verdict the trap's postmortem says was true; raw-field read fails lint | 1 |
| 6 | 3. `ci(conflicts): open-PR add/add collision check (advisory)` | `scripts/ci/pr_collision_check.py`, tests, workflow | 2 | Replay of C1/W125 pair and #4783/#4782 pair each produce the historically-correct verdict | 2 |
| 7 | 1. `fix(e2e): make the visa-oracle fullstack smoke green, then required` | `apps/mouth/e2e/visa-oracle-fullstack.spec.ts` | 2 | Job-level success on 2 consecutive unrelated PRs + guilt check (break evaluate route → red) | 1 |
| 7 | 2. `feat(probes): anonymous VOA journey probe, sandbox-tenant, Mini-scheduled` | `scripts/probes/voa_journey_probe.mjs`, `infra/launchagents/com.nuzantara.voa-probe.plist`+wrapper, `scripts/tests/test_voa_probe_wrapper.sh` | 2 | Probe runs from clean env, writes heartbeat, leaves 0 sandbox rows; wrapper corpus green in CI | 1 |
| 7 | 3. `feat(probes): dead-man receptor — heartbeat silence flips GARUDA_PUBLIC_ENABLED off` | `scripts/probes/voa_deadman.py`, plist, tests | 2 | Seeded stale heartbeat → dry-run fire of garuda-arm.yml + Telegram proof; real-fire gated until go-live | 1 |
| 8 | 1. `feat(immune): contracts.json + lint_immune_contracts.py` | `contracts.json`, `lint_immune_contracts.py` | 2 | W120 fixture red; escalations NORMAL/normal drift normalized to pass | 1 |
| 8 | 2. `fix(sentry): repoint fleet quota probe at the org with traffic; deprioritize known-noise at the edge` | config + probe diff | 1-2 | Probe returns nonzero accepted-count; weekly rate_limited% appears in digest (baseline 28%) | 1 |
| 8 | 3. `chore(hooks): purge .bak sprawl + guard` | 35 `.bak` under `~/.claude/hooks/`, `lint_home_fork.py --discover` | 2 | — | 1 |
| 9 | 1. `feat(fleet): seat-state ledger + cascade pre-dispatch check` | `scripts/lib/seat_state.sh`, `infra/launchagents/wrappers/claude-cascade.sh`, `scripts/tests/test_seat_state.sh` | 2 | Guilt: exhausted seat skipped; innocence: fresh seat used; staleness: old ledger ignored (exit-2) | 1 |
| 9 | 2. `feat(fleet): fleet_burst — account-sharded headless fan-out` | `scripts/fleet_burst.sh`, `scripts/tests/test_fleet_burst.sh` | 2 | Dry-run asserts: one distinct seat/lane, ≤3 concurrent spawns, sterile config flags, output dir per lane | 1 |
| 9 | 3. `feat(effort): bind dispatch effort to compute_floor` | `scripts/seat_build.sh`, `scripts/tests/test_seat_build_effort.sh` | 2 (+needs-ruling) | Floor-1 diff ⇒ medium; floor-3 ⇒ xhigh; explicit override wins | 1 |
| 10 | R1 PR-1 `feat(ledger): pending-arms overdue ratchet + digest row-naming + reporter schema self-test` | `scripts/pending_arms_report.py` (extend), `scripts/tests/test_pending_arms_ratchet.py`, digest wiring | 2 | Ratchet red on synthetic +1 overdue, green with override line; digest names 10 rows in live run; schema self-test red when reporter key renamed | 1 |
| 10 | R3 PR-1 `feat(proprioception): canon-block comparator for global CLAUDE.md` | — | 2 | Synthetic divergent block on one machine → P1 line within one probe cycle; identical blocks → silent | 1 |
| 10 | `docs(cicatrix): prune superscar MEMBRI to restore ≥1.5 KB headroom` | `.claude/rules/cicatrix-superscar.md` | 1 | `test_superscar_budget.py` green with ≥1,500 bytes free; every displaced W-token still resolves | 1 |
| 11 | R1 `feat(journeys): production journey sentinels wave 1 — dream, clock, magic-link` | `apps/mouth/e2e/production/*.spec.ts`, `scripts/journey_sentinel.sh`, plist in `infra/launchagents/` | 2 | Suite red against replayed pre-#5143 build, green against prod, self-test fails on demand | 1 |
| 11 | R2 `feat(design-tokens): Merah Putih DTCG source + contrast tripwire` | tokens file, `scripts/check_token_contrast.py`, CI job | 2 | NO surface migration yet; tripwire red when `$value` edited to failing hex, green on spec | 2 |
| 11 | R3 `feat(wr2): critic conformance corpus + font structural probe` | fixtures dir, runner, CI job | 2 | — | 2 |
| 12 | 1. `feat(db): jsonb codec default=str + shared prod-shaped pool fixture + bare-create_pool lint` | `app/core/database.py`, `app/setup/service_initializer.py`, `scripts/lint_test_pool_codec_parity.py` | 2 | Lint red on fixture w/ bare create_pool, green on tree; GARUDA suites green w/ codec; guilt test proves jsonb array | 1 |
| 12 | 2. `feat(db): migration provenance columns + checksum verification in schema_audit` | `migrations_v2/29X_schema_versions_provenance.sql`, `migration_manager.py`, `schema_audit.py` | 2 | Fresh apply records applied_as/applied_via; tampering post-apply turns schema_audit red naming the number | 1 |
| 12 | 3. `feat(ci): restore drill level-5 application verification` | `.github/workflows/restore-drill.yml`, `scripts/ci/restore_drill_verify.py` | 1 | Drill fails if any golden query returns degenerate shape; per-invariant verdicts; no `\|\| true` on any step | 1 |
| 13 | PR-1 `feat(security): seat broker — exec-time minimal env for external LLM dispatch` | `scripts/with_seat.sh`, `infra/llm-credentials/seat-env.json`, `scripts/tests/test_with_seat_env_minimization.sh` | 2 | Guilt: unwrapped child sees planted fake token; innocence: wrapped child's env = exactly declared names, planted name ABSENT | 1 |
| 13 | PR-2 `feat(proprioception): tailnet policy drift receptor` | `scripts/tailnet_policy_drift.py`, receptor wiring, tests w/ recorded netmap fixtures | 2 | RED on 2026-08-11 allow-all fixture; GREEN on policy.hujson-matching fixture; BLIND → exit 2, never CLEAN | 1 |
| 13 | PR-3 `feat(ledger): operator[secret] ager + weekly digest` | `scripts/pending_arms_report.py` (extend) + test | 1 | Digest lists ≥3 open rotation rows by fingerprint+age from ledger fixture; closed row does not appear | 1 |
