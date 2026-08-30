---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
type: index+synthesis
status: complete
lanes_complete: 13/13
adversarial_review: kimi-k3
model_selection: "manual — Zero's order of 2026-08-28 for this one panel; pinned by the orchestrating session, not routed by any script, cron or doctrine (Fable 5 has no automated role, ruling 2026-08-20)"
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
| 4 (23:10) | 13 headless `claude -p` processes, one OAuth seat per lane (≤2 concurrent lanes per seat), `--allowedTools` whitelist, `--effort max`, incremental+resumable reports, quota rotation | see per-lane status above; seat pings at launch: slot 1 weekly limit (reset 30/8 09:00), 5 session limit (01:40), 6 Team limit (03:30), 4 alive, 2/3 slow-boot |

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

## Panel-internal on-disk gate (run by the orchestrating session, which Zero had put on Fable 5 by hand for this one panel — never delegated; the repository's final on-disk gate is untouched: Opus 5, ruling 2026-08-20)

Per report: all 10 sections present · ≥10 distinct external URLs · every repo path cited as
"exists today" re-checked on disk (paths under §5/§6 are proposed artifacts, not claims) · no
email/phone/secret-shaped strings. Gate script: scratchpad `panel/gate.py` (a session script, not versioned — a defect the refuters flagged; its checks are restated as receipts in the evidence pack, and a versioned `scripts/research_gate.py` is the follow-up).

## Cross-lane synthesis (13/13 lanes — panel closed 2026-08-29 00:00 WITA, ≈85,044 words across the 13 reports)

### A. Where the organism is genuinely AHEAD of the surveyed world (each claim is measured in its lane; "no equivalent" means none found in that lane's surveyed set, not a universal negative)

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
- Capture and compression of lessons: a push-injected, CI-budgeted, guilt/innocence-guarded scar corpus is a working industrial instance of what the field has only *named* ("system prompt learning") and the structural inverse of the NASA-LLIS graveyard — 70% of 164 scars name an executable antidote (whether it is still wired is lane 5's finding: 2 of 66 gates armed), 49% cite an earlier scar (lane 10).

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
2. **Production journey sentinels derived from scars + dead-man that flips the flag OFF** (L11 + L7) — every cured UX defect becomes a scheduled production probe with guilt+innocence self-test; probe silence flips `GARUDA_PUBLIC_ENABLED` off via the existing allowlist actuator. Would have caught 2–3 of the five defects on lane 7's list (lane 11 counts six on its own list; the two lists overlap on four) — an estimate, not a replay.
3. **Seat = trust unit + budget unit** (L13 + L9) — `with_seat` broker (minimal env per external CLI dispatch; secret-shaped env names per child ≥3→1) and a seat-state ledger with pre-dispatch budget check in OAuth-window currency; `fleet_burst` (account-sharded headless fan-out, ≤3 spawns, incremental outputs) as a first-class command, model pinned by doctrine (Fable never auto-routed).
4. **Meter every declared contract** (L1 + L4) — acceptance-bullet→probe lint and an enforced `appetite:` field at the pack-lint door; per-lane outcome telemetry (correction-chain rate, time-to-green, builder attribution from the branch namespace); check-gated stop (`.lane-check.json` consumed by all four termination surfaces).
5. **Verify the verifiers** (L5) — quarterly grader scorecards on a labeled corpus extracted from adjudicated scars/retractions; sampled receipt re-execution at the verdict gate; a re-qualification calendar for every required check; **antidote-liveness lint** — a cure a scar names must still exist AND still be wired into a workflow (L10).
6. **Queue economics** (L6) — batch 1→3 with a symmetric path sentinel + trigger-symmetry lint (runner-min/PR 121–138 → <80; median 61 → ≤40 min); conflict-by-construction linter at PR-open (DIRTY 39% → <10%); the `mq state` oracle encoding the 19 traps.
7. **Signal economics** (L8) — burn-rate + dual-window math on PENDING-ARMS/escalations (error-budget calculus on a debt ledger); CI schema-handshake between every health emitter and its consumers (kills the W120 class); OTP-style restart budgets for a `supervised` organ class + one wide-event stream so MTTR becomes computable; **PENDING-ARMS burndown ratchet** + monthly FixIt sweep + schema-self-testing digest sentinel, and **replay drills** per superscar family (Wheel-of-Misfortune as weekly mutation-verified fixtures) — measure the loop by armed-antibodies-per-week, never scars-per-week (L10).
8. **The data contract's four hidden layers** (L12) — catalog contract probed from prod and replayed in CI as the real role topology; codec-parity cure + lint banning bare `create_pool` in tests; provenance columns (`applied_as`/`applied_via`) and checksum-verified `schema_audit`.
9. **Decision afterlife** (L3) — a decision registry with a status machine and a revisit receptor (findability 6 locations → 1 query); council-yield instrument; doctrine citation-integrity lint (≤150 lines, zero phantom sources in the law).
10. **Deploy parity as receptors** (L7 + L9) — served `?dpl=` must change after bundle-path merges; every live `*.balizero.com` surface names its repo source; `flags.yaml` as the two-platform flag SSOT with lint; conductor calibrations distilled from shipped Evidence-Pack outcomes.

### E. Needs-ruling (consolidated — Legge-5 business and product decisions, credential and GUI actions)

- **Governance**: who decides structure — SYMBIOSIS Law 5 vs CLAUDE.md §2 give opposite answers (L3) · the context budget number (L2; precedent: the ruled 17 KB MEMORY.md target) · whether an exceeded `appetite` suspends by default (L1) · registry bindingness and blind-gate default (L3) · effort default per gear floor (L9, already ledgered as `operator[business]`) · whitelist-vs-CODEOWNERS intent for the 24/73-red orphan test (L6) · harvester promotion policy — who may turn a shadow proposal into an enforced gate, even one rule at a time (L10) · batch-retirement semantics for PENDING-ARMS rows (a signed WON'T-ARM rule in the ledger header) (L10) · monthly FixIt-sweep quota, feature velocity vs debt burndown (L10) · cadence and format of the "decided autonomously" digest (L10).
- **Spend / resources**: Antigravity arm-or-retire (L4) · Pro disk headroom for hermetic caches (L4) · Sentry quota purchase (L8) · TP1 credit thresholds for burst use (L9) · team tailnet expansion GO/NO-GO (L13) · advisory-DB snapshot in the blocking security path + Detect Secrets diff-scoping (L6).
- **Credentials / GUI / physical**: apply `policy.hujson` on the Tailscale console, in that order before any team device (L13) · the three open rotations (L13) · TCC re-grants for DEAD-GREEN launchd jobs (L8) · per-batch ack for retiring canon-less live plists (L8) · Chronicle/ChatGPT.app screen recording on M5 (L13) · standing authorization for the temporary-GRANT ceremony (L12) · sandbox payment credentials and real-fire authority for the dead-man (L7) · Actions secrets for the Qdrant restore-drill leg (L7) · cswap/OAuth profile swapper install (L9).
- **Product**: `/dream` public or gated · `/prime` Google Maps key expired · `/exclusive` unfinished or intended · VOA dark state as bare 404 · experiments on real prospects + consent copy · `/visa/match` investor >500M → E33G misroute (all L11) · crypto-shredding scope and Qdrant estate disposition (L12) · exposure-changing flag flips stay owner gestures (L7).

### F. Proposed first wave (three PRs, three organs, one cure — ready to open on GO)

1. `feat(context): read-side attestation of the injected surface + scar bodies back to cold storage` (L2 R1) — Gear 2, ≤400 lines; acceptance: a fresh headless session reports the delivered surface ≤ the ruled budget (lane 2 proposes 120 KB; the number itself is a §E ruling) and the attestation receptor goes RED on a synthetic 200 KB injection.
2. `feat(probes): production journey sentinel for the VOA funnel, dry-run dead-man` (L11 R1 / L7 R1) — Gear 2; acceptance: the probe fails RED on each of lane 11's six 2026-08-28 defect fixtures replayed, and stays GREEN on prod today; dead-man in dry-run + Telegram until Zero's real-fire GO.
3. `feat(fleet): with_seat broker — minimal per-seat env for external LLM dispatch` (L13 R1) — Gear 2; acceptance: `env` observed by a codex/agy/kimi child under the broker carries exactly the seat's own credential; a fixture lane with a leaked PAT turns the lint RED.

### G. The numbers this panel measured tonight (for the ledger)

774 KB injected context (5× in 7 days) · 39% open PRs DIRTY · Backend Tests 2.5×/PR, 61-min median open→merge · PR p90 1,292 lines vs 400 · 85.8% Sonnet dispatch vs workhorse-first · fix-share 30.6% of main commits · correction tax 12–13% · 81.2% ledger rows overdue, escalations median 30 d · 0/6 prod defects caught by 53 e2e specs · 66 scar gates / 2 armed · 6/24 invariants enforced nowhere · 22 prod tables not app-owned · 97.7% migration rollback coverage · ADR organ dead since 2026-03-22 · two seats + 10 lanes burned in ~5 min by the panel's own first launches · 280/441 PENDING-ARMS rows overdue · scar capture 56 → 18/month · modus-bench dormant since 07-07 · superscar bridge 13,986/14,000 bytes.

### H. First-PR candidates per lane (extracted from each report's §6 — or §5 where §6 points there; leads, not commitments)

Rows for lanes 1-9 and 11-13 were extracted by a separate read-only lane and spot-checked against the reports by the orchestrator (12 title fragments grepped, all present); lane 10's rows were taken by the orchestrator directly from its §6. The files named are the *report's* proposals — most do not exist yet; the acceptance column is the report's own falsifiable test; "—" means the report gave none for that PR — a defect of the report, recorded here rather than invented. Lane numbering follows the partition table above.

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

### I. Cross-family blind replica — coverage, contamination, and where five outside seats disagree

Zero's second order of 2026-08-29 was to hand the same 13 lane briefs, blind, to five non-Anthropic
seats. Method, doors, access model and the discarded first run are in
`2026-08-28-beyond-sota-panel-PROTOCOL.md` §7; the outputs are one file per lane per seat under
`research/operations/2026-08-28-beyond-sota-xfamily/`, each kept verbatim and each carrying
`adversarial_review: exempt-raw-external-seat-output`. **Nothing below is adopted from an xfamily file
directly** — that is the exemption's own condition: the seats are weighed against each other and
against the panel's lane report here, and nowhere else.

**Coverage matrix.** 13 lanes × 5 seats = 65 planned runs; 59 on disk. Each cell is
`words · wall-clock minutes · distinct external URLs · 12-gram overlap with the panel's own report for
that lane`. Overlap and URLs are recomputed from the shipped files, not copied from a run log.

| lane | codex-sol-ultra | kimi-k3 | agy-gemini-3.1-pro | tp1-deepseek-v4-pro | tp1-qwen3.8-max |
|---|---|---|---|---|---|
| 1 intake/triage/spec | 4,935 w · 10.8 m · 14 src · 0.00% | 4,239 w · 13.1 m · 14 src · 0.59% | 2,337 w · 2.7 m · 13 src · 0.04% | 3,544 w · 7.0 m · 14 src · 0.02% | 5,513 w · 8.1 m · 16 src · 0.08% |
| 2 context/grounding | 4,869 w · 9.0 m · 12 src · 0.02% | 3,979 w · 6.9 m · 12 src · 0.05% | 2,118 w · 4.3 m · 12 src · 0.48% | 3,622 w · 5.1 m · 13 src · 0.00% | 4,648 w · 7.4 m · 18 src · 0.59% |
| 3 architecture | 5,285 w · 7.8 m · 15 src · 0.05% | 4,684 w · 10.9 m · 0 src · 0.23% | 1,568 w · 3.0 m · 11 src · 0.00% | 3,133 w · 3.5 m · 14 src · 0.09% | 4,788 w · 9.1 m · 19 src · 0.23% |
| 4 implementation | 5,538 w · 10.4 m · 12 src · 0.15% | 4,444 w · 8.0 m · 14 src · 0.19% | 3,158 w · 3.4 m · 12 src · 0.32% | 2,934 w · 3.1 m · 13 src · 0.18% | 5,223 w · 10.1 m · 19 src · 0.64% |
| 5 verification/gate | 5,305 w · 8.8 m · 12 src · 0.41% | 3,994 w · 10.2 m · 15 src · 0.44% | 1,851 w · 4.9 m · 12 src · 0.00% | 3,981 w · 4.5 m · 18 src · 0.14% | 4,803 w · 8.8 m · 20 src · 0.19% |
| 6 CI/merge queue | 5,369 w · 10.0 m · 14 src · 0.00% | 4,955 w · 11.0 m · 20 src · 0.07% | 2,693 w · 3.1 m · 10 src · 0.20% | 3,841 w · 4.2 m · 15 src · 0.05% | 5,177 w · 5.8 m · 12 src · 0.27% |
| 7 deploy/prove-live | 5,220 w · 8.4 m · 12 src · 0.00% | 4,036 w · 10.5 m · 11 src · 0.20% | 1,971 w · 3.3 m · 10 src · 0.00% | 4,257 w · 4.5 m · 15 src · 0.00% | deferred — TP1 quota |
| 8 observability | 4,924 w · 8.5 m · 12 src · 0.06% | 4,345 w · 8.4 m · 16 src · 0.22% | 1,688 w · 4.0 m · 5 src · 0.00% | 4,049 w · 3.4 m · 17 src · 0.00% | 5,527 w · 8.2 m · 14 src · 0.54% |
| 9 orchestration/fleet | 5,066 w · 8.5 m · 10 src · 0.02% | 4,525 w · 10.6 m · 15 src · 0.02% | 1,666 w · 3.6 m · 10 src · 4.14% | 4,259 w · 4.8 m · 22 src · 0.11% | 5,787 w · 10.2 m · 18 src · 0.02% |
| 10 learning loop | 5,198 w · 9.3 m · 12 src · 0.00% | 5,093 w · 9.6 m · 20 src · 0.17% | 3,342 w · 4.8 m · 14 src · 0.03% | 3,882 w · 4.1 m · 12 src · 0.14% | deferred — TP1 quota |
| 11 product/UX | 5,842 w · 12.2 m · 12 src · 0.01% | 4,415 w · 11.6 m · 14 src · 0.02% | 1,836 w · 3.5 m · 12 src · 0.00% | 4,655 w · 4.1 m · 14 src · 0.06% | deferred — TP1 quota |
| 12 data/migrations | 5,912 w · 8.0 m · 14 src · 0.00% | 3,980 w · 8.0 m · 21 src · 0.25% | 2,189 w · 5.4 m · 10 src · 0.00% | 3,770 w · 3.5 m · 12 src · 0.00% | deferred — TP1 quota |
| 13 security/PII | 5,944 w · 8.6 m · 12 src · 0.00% | 5,072 w · 6.2 m · 14 src · 0.19% | 2,430 w · 4.0 m · 12 src · 0.30% | deferred — TP1 quota | deferred — TP1 quota |

**The six missing cells are deferrals, not failures, and they are all one cause**: the Alibaba TP1
weekly quota. Qwen3.8-Max is short lanes 7, 10, 11, 12 and 13; DeepSeek V4 Pro is short lane 13. They
land in a follow-up PR with their own pack — nothing in this section is derived from a cell that does
not exist. Completed runs by seat: codex-sol-ultra 13, kimi-k3 13, agy-gemini-3.1-pro 13,
tp1-deepseek-v4-pro 12, tp1-qwen3.8-max 8; 243,408 words in total.

**Contamination, measured rather than asserted.** Across all 59 shipped cells there are exactly **two
distinct lines of ≥40 characters shared with the panel report of the same lane**, and both are
structural artefacts of the shared brief rather than content: the mandated heading
`## 2. Scars & ledger evidence in this area` (31 cells) and one survey table header (1 cell). The
highest 12-gram overlap in the whole matrix is 4.14%, and it has an explanation that is not
contamination — see immediately below. Run 1, whose snapshot did hold the answer key, measured 98.2%
overlap and 70 identical lines on its worst cell; that run was archived, not shipped (PROTOCOL §7).

**One provenance correction this replica forced, and it changes how lane 9 must be read.** The panel's
own lane-9 report declares `model: Gemini 3.1 Pro (pinned lane)` in its frontmatter — the only one of
the 13 that is not `claude-fable-5`. So on lane 9 the "outside seat" `agy-gemini-3.1-pro` and the
"panel report" are the same model family answering the same prompt, which is what the 4.14% overlap
and that lane's near-identical recommendations actually measure. It is not independent corroboration
and must never be counted as such: lane 9's genuine cross-family check is codex / kimi / deepseek /
qwen only. Neither this index nor the protocol discloses the substitution anywhere else — the mandate
line at the top of this file still reads "one Fable-5 max-effort lane per part" — so the correction
belongs here, in the open, rather than only in that one file's frontmatter.

**Per-lane agreement and divergence.** "Converges" counts only seats that reached a finding
independently and that the panel's lane report also reaches.

| # | converges with the panel | the seats add what the panel report does not have | contradicts the panel |
|---|---|---|---|
| 1 | gear floor+ceiling computed in CI rated AHEAD (4/5); EARS-shaped acceptance criteria as the top fix (4/5); rule-8 fix-of-fix should be mechanized, not prose (4/5) | codex names a live doctrine contradiction — `karpathy-discipline` says state your assumptions while `CLAUDE.md` says infer rather than ask — and flags `AUTONOMOUS_OPS.md` as 41 days past its own recertification interval; agy proposes a hard plan-mode filesystem lock | agy rates triage automation **BEHIND**, wanting semantic risk scoring over deterministic path/size floors |
| 2 | boot-context bloat is the #1 diagnosis (5/5); the HOME-fork "3 copies, 3 answers" incident (5/5); the ~90K-token fork-lane inheritance (5/5); a scar-derived recall benchmark (panel + 2) | codex and qwen independently flag the 136,238-byte `visaoracle` corner skill as its own bloat defect; deepseek proposes a CI check failing when `MEMORY.md` exceeds its budget; agy proposes a tree-sitter dynamic repomap | agy rates the memory write-side **BEHIND** and calls the corpus "archaic" where the panel rates it AHEAD of Mem0/Letta write paths |
| 3 | the decision loop and council doctrine rated AHEAD (5/5, unanimous); the ADR organ is dead and real decisions live in research dossiers (5/5); W100 as the central cautionary evidence (4/5); extend `genes.json` fitness functions to the decision layer (5/5) | kimi proposes an ex-ante calibration ledger scoring each seat's predictions against outcomes; kimi and codex both find the council-routing script still encoding the retired v2 architecture; codex finds `CLAUDE.md` self-contradicting on `max` vs `xhigh` for the gate | none found |
| 4 | the worktree broker rated AHEAD (5/5); Sonnet dispatch overshoot against workhorse-first (3/5, codex measuring 127/148 = 85.8%); the 400-line PR contract is prose, not a gate (2/5); no build-outcome/rework metric exists (2/5) | agy proposes a declarative migration-dependency graph read from `-- depends:` headers; kimi proposes pushed WIP snapshot refs against the W80 class; deepseek moves generator≠grader from VERIFY into BUILD | agy would abandon the local pre-push suite entirely and validate frontend only in CI, where the panel restores local default-on |
| 5 | the scar-gate arming crisis, 2 of 66 armed (4 sources); W100's 7-of-8 same-family false-clean (4); judge calibration from a scar-derived labelled corpus (4) | three seats make "arm the gates" their own #1, strictly stronger than the panel's re-qualify-only R5; codex proposes a cryptographic execution attestation for the verdict and a structural graph replacing workflow substring matching; qwen proposes a lint failing any PR that deletes a test, guard or workflow | codex disputes the guard-conformance denominator — "the defensible metric is 38/51 normalized bilateral declarations, not 51/51" — against the panel's 38/38; and the correction-tax metric spans 24× across seats (0.5% / 1.2% / 4.5% / 12.2%) on one question |
| 6 | W111's stale merge-ref replay (5/5); W124's silent CI on a DIRTY PR's subset (4/5); the merge-gate-integrity-watch is a detector, not an enforcer (panel + kimi, and qwen measured it CANNOT-VERIFY for 26 consecutive executions); the DIRTY-PR structural-conflict class as the top unsolved gap (5/5, four different cures) | codex and qwen find a live doctrine contradiction the panel never flags — the runbook mandates a bare `--auto` while `auto-merge-whitelist.yml` invokes `--auto --squash --delete-branch`; three seats propose an always-on local webhook receiver instead of GitHub's blind poll; agy measures agent session tokens burned hand-polling CI | kimi, blind, reports queue batching was measured and deliberately **not** flipped (conditional re-entry rising 24%→85% at group size 3) against the panel body's `min_entries_to_merge` 1→3 — the panel's own appendix concedes this, its body was never corrected |
| 7 | the 503-RAG shape (health=200 over a stopped worker) as the central diagnosis (5/5); a two-platform flag registry and parity check (5/5) | all four completed seats want the **deploy itself** gated on process-group functional proof rather than left to a cron-side restart detector — the panel treats the existing detector as adequate and puts this in no recommendation; three seats name the uncomputed DORA change-failure-rate and time-to-restore | deepseek rates deploy frequency medium (~2-3/week from a stale SLO doc) against the panel's AT-elite, and states no rollback action is taken where the panel cites an automatic `flyctl releases rollback --yes` — both are artefacts of an API seat with no file access, and are recorded as seat error, not as a finding |
| 8 | the PENDING-ARMS ledger needs restructuring (panel + 4/5); MTTD/MTTR is uncomputable because no incident record carries both timestamps (panel + 3); burn-rate/SLO alerting against the alarm-cure dead zone (panel + 3) | codex and qwen find `heartbeat.py`'s `is_alive()` **fails open when Redis is down** — absent from the panel's own description of that organ; three seats independently propose chaos/fault-injection drills against the immune system itself | self-healing coverage: the panel rates it BEHIND on breadth (a sliver of 170 organs), agy and kimi rate it AHEAD and codex AT/AHEAD on architecture — the axis is being measured two different ways, and both readings are recorded rather than resolved |
| 9 | *(cross-family = codex/kimi/deepseek/qwen only — see the provenance correction above)* cron tokens cannot read their own quota for want of the `user:profile` scope (5/5), all proposing a locally published quota | codex, kimi, deepseek and qwen all analyse `docs/factory/SEAT-MIX.md`'s measured 85.8% Sonnet dispatch share, which the lane report never cites; codex, kimi and qwen surface `infra/conductor`'s dormant calibration registry (`calibrations.v1.json` is `{"records": []}` against dozens of unconsumed endpoint profiles); kimi verified by `ls` that `scripts/seat_dispatch.py`, named in `FLEET_TOPOLOGY.json`, does not exist on disk | the lane report rates the cascade AHEAD unqualified; codex rates that dimension BEHIND on the same artefact (wrong Team-slot mapping, TP1 absent) and kimi calls it "BEHIND its own design" |
| 10 | the meta-diagnosis that a lesson written is treated as a lesson armed — four independently worded restatements; a recidiva count that triggers mandatory escalation (4/4, thresholds differ); the 27-of-40 pointer-rot measurement; the bridge's byte-size drift against its own token claim | codex, kimi and deepseek each propose **mutation-testing the antidotes themselves** — does the cure still kill its own disease — which is strictly stronger than the panel's antidote-liveness lint that only checks a cure exists and is wired; kimi proposes diff-scoped scar retrieval instead of blanket injection; codex surfaces the 2-of-66 armed-gate census, sharper than the panel's 70%-named statistic | none found |
| 11 | adopting the DTCG token format as the cure for measured fragmentation — **5/5, the strongest convergence in the whole replica**; W99 (a check that never acted) as the central cautionary scar (4/5); production journey sentinels as the top fix (4/5) | kimi proposes self-hosted component visual-regression testing and a "warn is a lie" sweep promoting warn-only brand guards to hard failures, naming a flag with many declarations and no readers; codex proposes a cross-channel durable service receipt | agy and deepseek both rank a VLM semantic critic as their #1 CI gate — agy naming the W99-recurrence risk itself — directly against the panel/codex/kimi position that a vision critic must stay subordinate to structural probes; kimi rejects the panel's CUPED/GrowthBook build as "cargo cult here" at current traffic. Separately, `isAuthenticated()` reference counts disagree across all five sources: trust none of them without a recount |
| 12 | the runtime DSN is also the migration identity and CI is blind to it (4/4); the jsonb codec gap that test pools hide (3/4); the Qdrant estate drift, matched vs dead vs undocumented-live (4/4); a reader-map lint against silent invariant widening — the panel's R4 and kimi's R3 are the same idea reached independently | kimi and codex both propose pgTAP in-database testing, absent from the panel; deepseek proposes a migration risk scorecard trained on the organism's own scar corpus | agy reports a rollback-marker coverage of 32.5% against the panel's 97.7%; codex and kimi independently confirm the panel's figure, so agy is the outlier and is recorded as such |
| 13 | external LLM CLIs inherit the full session environment — the top finding, 3/3 plus the panel; the tailnet allow-all with an unauthenticated writable shell on the machine holding raw PII (kimi, near-verbatim); the secrets auditor's filename-pattern blind spot (codex); the hooks-versus-kernel-sandboxing gap (3/3) | agy and codex both propose **automatic** credential revocation on exposure where the panel's R4 is only a reminder SLA; codex finds the prompt carried in the subprocess argument vector in `claude_oauth_client.py`; agy proposes actively denying the screen-capture entitlement where the panel proposes only a detection receptor; codex proposes Sigstore/SLSA release provenance | agy rates agent sandboxing **AT SOTA** and public-repo secret scanning **BEHIND** — both inverted against the panel, kimi and codex, who rate them BEHIND and AT respectively |

**What the replica establishes that a same-family panel could not.** Three things, in order of weight.
**(1)** On the questions where the organism claimed to be AHEAD, five outside families largely agree —
the worktree broker, the CI-computed gear floor, the council doctrine, the guard guilt/innocence
contract — and where they disagree they disagree *specifically*, on a denominator (5) or a scope (8) or
a stale artefact (9), which is a usable finding rather than a mood. **(2)** Seat depth is not uniform
and it is now measured: codex-sol-ultra and kimi-k3 carry the grounded weight of this replica, while
agy-gemini-3.1-pro delivered roughly half their words at a ~3.6-minute median and produced both of the
replica's clearest factual misses (the lane-12 rollback count, the lane-13 inverted verdicts) — a
cheap fast seat is a real seat, but not one to take a lone verdict from. **(3)** Where four seats
measured the same quantity and got four answers — the correction tax across a 24× spread, the
boot-context byte count, the `isAuthenticated()` reference count — the *spread is the honest
confidence interval*, and every one of those numbers appears in §A-§H as a single figure. That is the
replica's most transferable result: a single measured number from a single seat is a point estimate
wearing a fact's clothes.

**Honest limits of this section.** Six of the 65 planned runs do not exist and are named as deferred
above. The URL column counts links, not sources: lane 3's kimi cell shows `0 src` because that report
cites its sources by archive and date in a `## 9. Sources` section without hyperlinks, not because it
is unsourced. The overlap column measures copying, not reading — for the agy seat, which logs no tool
calls, a low overlap rules out transcription but cannot prove non-exposure, and PROTOCOL §7 says so.
And every verdict in the tables above is a *seat's* verdict: where the seats contradict the panel,
this section records the contradiction and does not adjudicate it, because adjudicating would be
adopting an xfamily file directly — the one thing the exemption forbids.

## Adversarial review

Blind cross-family review (generator ≠ grader), 2026-08-29. The refuters received the full document and the panel's hard rules, nothing else; path existence had already been verified on disk by the orchestrator's gate, so they attack logic, numbers, rule-compliance and the SOTA claims. Dispositions by the orchestrator (claude-fable-5, Zero's manual selection): **survives** = recorded as a standing caveat, not fixed in this PR; **rejected** = the objection misreads the document or the rules (reason given); **accepted** = fixed in the text.
Tally: 16 raised · 4 survive · 3 rejected · 9 accepted.

**Reviewer: `kimi-k3`** — Moonshot Kimi K3 via Kimi CLI (read-only snapshot of the repo). 8 raised.

| # | sev | objection (refuter's words) | disposition |
|---|---|---|---|
| 1 | HIGH | "run one Fable-5 max-effort lane per part" / "pinned `model: fable`" / "Final on-disk gate (orchestrator, Fable 5 interactive — never delegated)" — The protocol and tmux pinning auto-route Fable 5 by doctrine and script, violating hard rule (d); it also contradicts the standing 2026-08-20 ruling assigning the on-disk gate to Opus 5 xhigh with Fable fully out of the workflow. | accepted (wording) — the gate line now reads 'panel-internal on-disk gate … which Zero had put on Fable 5 by hand for this one panel; the repository's final on-disk gate is untouched (Opus 5, ruling 2026-08-20)'; rejected (substance) — Fable ran under Zero's explicit manual order for this panel, and nothing in this diff or in the repo routes to it afterwards |
| 2 | HIGH | "0 of 6 measured 2026-08-28 production defects caught by the 53-spec e2e suite" vs "Would have caught 2–3 of the 5 defects of 2026-08-28" — Defect count is 6 in sections B and G but 5 in D2 and F2 ("the five defect fixtures"); a core measured number is used inconsistently across findings, recommendations, and acceptance tests. | accepted — the INDEX now uses lane 11's six consistently and names lane 7's separate five-item list where that figure is quoted |
| 3 | HIGH | "the context budget number (L2…)" listed under Needs-ruling, yet "acceptance: a fresh headless session reports the delivered surface ≤120 KB" — Section E declares the budget a business decision requiring Zero's ruling, while F hardcodes ≤120 KB into a PR declared "ready to open on GO" — the report de facto decides a ruled-reserved decision. | accepted — F1 acceptance now reads '≤ the ruled budget (lane 2 proposes 120 KB; the number itself is a §E ruling)' |
| 4 | MED | "Where the organism is genuinely AHEAD of the surveyed world (each claim is measured in its lane)" — Negative SOTA claims ("no equivalent in Spec Kit, Kiro…", "a queue-trap corpus nobody has published") are unfalsifiable survey assertions, not measurements; the measured-evidence framing is unsupported by the panel's own method. | accepted (wording) — §A now states that 'no equivalent' means none found in the lane's surveyed set, not a universal negative |
| 5 | MED | "Gate script: scratchpad `panel/gate.py` (throwaway)" — The final evidence gate is an unversioned throwaway script, contradicting the panel's own central doctrine (verify-the-verifiers, cures must persist and stay wired); a skeptical engineer cannot reproduce or audit the gating this index claims. | survives — true: the gate is a session script; its checks are restated as receipts in the evidence pack and a versioned scripts/research_gate.py is the follow-up |
| 6 | MED | "the acceptance column is the report's own falsifiable test" — Two first-PR rows (lane 8 PR-3 ".bak purge", lane 11 R3 "critic conformance corpus") ship with acceptance "—", i.e., no falsifiable test, violating the panel's stated extraction rule and its own anti-tautology doctrine. | accepted — §H now states that '—' means the report gave no falsifiable test for that PR: a defect of the report, recorded rather than invented |
| 7 | MED | "70% of 164 scars carry an executable antidote" — Touted as ahead-of-world in A, but B reports "66 scar gates, 2 armed" and D5 proposes an antidote-liveness lint precisely because named cures may not exist or be wired; "executable" is asserted, not demonstrated, and contradicted by the arming data. | rejected — different denominators: 70% of scars NAME an executable antidote (lane 10's measure) while 2 of 66 GATES are wired (lane 5's); §A now says so explicitly |
| 8 | LOW | "Would have caught 2–3 of the 5 defects of 2026-08-28" — A speculative counterfactual (untested probes vs. historical defects) is used as quantitative impact justification for rank #2; presented with measured-number confidence despite no replay evidence existing yet. | survives — D2 now labels the 2–3 figure an estimate, not a replay |

Refuter's verdict: Not as-is — the hard-rule (d) Fable 5 auto-routing and the 6-vs-5 numerical inconsistency must be corrected and the ≤120 KB budget deferred to Zero's ruling before this report can stand as evidence of anything beyond its own section-B measurements.

**Reviewer: `qwen-3.8-max`** — Alibaba Qwen3.8 Max via TP1 (API, thinking on, no repository access). 8 raised.

| # | sev | objection (refuter's words) | disposition |
|---|---|---|---|
| 1 | HIGH | "13 headless `claude -p` processes, one OAuth seat per lane (≤2 lanes/seat), `--allowedTools` whitelist, `--effort max`, incremental+resumable reports, quota rotation" — This automated fan-out executes the mandated Fable-5 lanes, violating the hard rule that Fable 5 may only be manually selected. | rejected — the fan-out ran under Zero's manual selection of Fable for this one panel (order of 2026-08-28); no script, cron or doctrine in the repo routes to Fable; the run-record wording was tightened to say so |
| 2 | HIGH | "seat pings at launch: slot 1 weekly limit (reset 30/8 09:00), 5 session limit (01:40), 6 Team limit (03:30), 4 alive, 2/3 slow-boot" — Only six seats are accounted, while 13 lanes at ≤2 lanes/seat require at least seven seats and one-per-lane requires thirteen. | rejected — '≤2 lanes/seat' was a concurrency cap (now worded '≤2 concurrent lanes per seat'); the 13 lanes ran sequentially over whichever seats were alive, the last five on a single seat |
| 3 | HIGH | "Would have caught 2–3 of the 5 defects of 2026-08-28." — The report elsewhere measures six production defects that day, and the counterfactual catch claim has no supporting evidence. | accepted — counts harmonized (lane 11's six; lane 7's five named as a separate list) and the catch figure labelled an estimate |
| 4 | HIGH | "no email/phone/secret-shaped strings" — String-shape checks do not enforce the PII/OSINT boundary; semantic client/prospect data can pass, and the report itself mentions investor-routing details. | survives — a string-shape scan is necessary, not sufficient; the reports contain no client data (the investor-routing item is a product rule, not a person), but the caveat stands |
| 5 | MED | "Needs-ruling (consolidated — only Legge-5 / credential / GUI items)" — The section then lists Product items such as `/dream`, `/prime`, and `/exclusive`, contradicting the stated limiting scope. | accepted — the heading now reads 'Legge-5 business and product decisions, credential and GUI actions' |
| 6 | MED | "no equivalent in Spec Kit, Kiro, Anthropic practice or the change-risk literature" — Sweeping absence/SOTA claim with no survey, citations, or method; a negative across multiple ecosystems is not falsifiable as written. | accepted (wording) — as kimi-k3 #4 |
| 7 | MED | "`fleet_burst` (account-sharded headless fan-out, ≤3 spawns, incremental outputs) as a first-class command." — Recommends automated fan-out without barring Fable 5 auto-routing or requiring manual model selection, recreating the forbidden automation pattern. | accepted — D3 now says 'model pinned by doctrine (Fable never auto-routed)' |
| 8 | MED | "batch 1→3 with a symmetric path sentinel + trigger-symmetry lint (runner-min/PR 121–138 → <80; median 61 → ≤40 min)" — Batching increases coupling/waiting; no mechanism shows it reduces both runner-minutes per PR and median open-to-merge time. | survives — lane 6's mechanism (fewer requeues, shared merge-ref builds) is argued, not yet measured; recorded as the caveat on move #6 |

Refuter's verdict: I would not let this report stand as evidence until the Fable-5 automation/seat contradictions, defect-count mismatch, PII-gate insufficiency, and unfalsifiable SOTA claims are corrected and independently re-gated.

