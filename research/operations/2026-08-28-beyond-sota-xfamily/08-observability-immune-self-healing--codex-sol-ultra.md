---
panel: beyond-sota-xfamily
lane: 08-observability-immune-self-healing
seat: codex-sol-ultra
model: "gpt-5.6-sol · reasoning_effort=ultra · Codex CLI read-only sandbox · web search on"
started: 2026-08-28T18:53:57Z
finished: 2026-08-28T19:02:29Z
duration_s: 512
exit: 0
words: 4924
prompt_sha256_16: e67ab63378ed18bb
prompt_chars: 18457
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 8/13 — Observability, immune system & self-healing
model: OpenAI GPT-5.6 sol at reasoning effort ULTRA (pinned lane)
sources: 12
repo_files_verified: 20
status: complete
---

## 0. TL;DR

Nuzantara is **AHEAD in detector diversity, provenance, scar-derived guardrails, and bounded healing**, but **BEHIND SOTA in unified observed state, outcome SLOs, sensor self-verification, and measurable incident performance**.
Its largest gap is epistemic: many components prove that a producer ran, while too few prove that the promised outcome occurred and the alert reached its consumer.
The repository has 170 registered organs and 156 canonical launchd plists, but no inspected identity join proves which registered organ is installed, breathing, semantically healthy, and correctly observed.
The 2.2 MB PENDING-ARMS receptor contains 611 parse-shaped open rows; 600 meet its day-granularity two-day age threshold, making Markdown itself an overloaded operational database.
Top move 1: compile all observations into a typed, evidence-bearing organ-state projection.
Top move 2: inject harmless end-to-end immune pulses that continuously test the detectors, alert path, and healer—not merely the workloads.
Top move 3: replace the monolithic receptor view with generated severity/age projections and measure MTTD, MTTR, false-green rate, cure success, and alert-delivery SLOs.
The healer’s narrow whitelist, re-verification, action budget, and refusal to cascade to weaker models are strong controls worth preserving.
Live HOME state, hook backups, runtime heartbeats, current arsenal results, and memory files were explicitly outside this snapshot; panel-premise runtime counts are therefore not treated as verified facts.

## 1. How Nuzantara does it today

### Evidence boundary

This audit treats the repository snapshot as authoritative for mechanisms, not for current machine state. The requested HOME surfaces—`/Users/nuzantara/.nuzantara-proprioception/last.md`, `/Users/nuzantara/.claude/hooks/`, and every `MEM:` reference—were unavailable under the lane’s explicit access boundary. Consequently, I could not independently verify the stated “six divergences this morning,” five boot-time seat timeouts, approximately 25 hook backups, live heartbeat totals, or current Sentry loss percentage.

The snapshot itself shows six partially overlapping immune layers:

| Layer | Verified implementation | What it establishes |
|---|---|---|
| Boundary proprioception | `docs/runbooks/proprioception-boundary-recon.md`; `docs/specs/proprioception-boundary-recon-v1.md` | Reconciles declared and observed boundaries with source hashes, runner/config versions, git state, and expected-versus-actual evidence. It is deliberately a signaler, not an actuator. |
| Organ inventory and genes | `apps/organism/organism/organs_registry.yaml`; `infra/organ-conformance/genes.json`; `infra/organ-conformance/check_baseline_ratchet.py` | Declares organs and ten conformance genes; prevents the grandfather baseline or missing-set debt from growing. |
| Heartbeat transport | `infra/eventbus/heartbeat.py`; `infra/eventbus/cron_log_sentinel.py` | Writes Redis heartbeat keys and translates selected legacy log markers into semantic events. |
| Healing | `docs/runbooks/healer-organ.md`; `infra/healer/HEALER-PRO-MANDATE.md` | Separates a repository-oriented Mini healer from a runtime-only Pro healer, with narrow cures and action limits. |
| Receptors and escalation | `.claude/skills/modus/PENDING-ARMS.md`; `scripts/pending_arms_report.py`; `shared/escalations_pro.jsonl` | Holds unresolved promises, classifies actionable debt, and records healer escalations. |
| Operator notification and digest | `docs/runbooks/organism-digest.md`; `docs/runbooks/telegram-notification-gateway.md`; `infra/launchagents/chronic_failure_digest.py` | Compresses routine state, routes notifications by urgency, and recovers failures hidden by delta-only reporting. |

### Inventory versus observed life

`apps/organism/organism/organs_registry.yaml` contains 170 organ entries: 144 `pro_launchd`, 14 `mini_launchd`, two `air_launchd`, and ten `fly_machine` runtime declarations. Seven entries are disabled, eight declare `expected_hb_seconds: 0`, and 70 use a `bridge_source`.

The canonical repository directory contains 156 `infra/launchagents/*.plist` files. These numbers must not be subtracted as if they represented the same population: the registry also describes Fly and other runtime classes. The absence of a demonstrated identity join is the finding. The inspected system does not emit one authoritative row per organ answering:

1. Is it declared?
2. Is its canonical runtime artifact present?
3. Is it installed on its assigned node?
4. Is its heartbeat fresh?
5. Is its semantic outcome healthy?
6. Is the sensor itself functioning?
7. Is a cure in progress, successful, exhausted, or prohibited?

Live sidecars were outside the snapshot, so “organs with a live heartbeat” cannot be responsibly calculated.

### Proprioception

The current runbook composes existing reconcilers and adds git alignment, PENDING-ARMS freshness, HOME-fork hashes, artifact promotion state, and guardian freshness. Reports carry runner version, configuration source and hash, repository head, and expected/actual evidence (`docs/runbooks/proprioception-boundary-recon.md`). This provenance is unusually strong.

The original specification expected a repository configuration file such as `config/boundaries.yaml`; the runbook documents an embedded default registry with an optional JSON override (`docs/specs/proprioception-boundary-recon-v1.md`; `docs/runbooks/proprioception-boundary-recon.md`). That may be legitimate evolution, but it means the specification and implemented control surface no longer describe exactly the same source of truth.

The runbook also records known blind spots: no scheduled cron at that point, a session-start receptor as the principal consumer, and unobserved Qdrant/backend-process provenance. Its stale-runner example correctly distinguishes “the measurement ran recently” from “the measuring code was current.”

### Heartbeats and semantic bridges

`infra/eventbus/heartbeat.py` uses a 120-second Redis TTL and throttles beats to 30 seconds. Its most dangerous choice is that `is_alive()` returns `True` when Redis access fails. That is graceful degradation for the caller but fail-open health semantics: loss of the truth channel is represented as life.

`infra/eventbus/cron_log_sentinel.py` polls legacy logs every ten seconds and recognizes four regular-expression rules. It is a pragmatic migration bridge, but some emitted semantic events infer success from matched prose—for example, constructing a passing draft event or a publication-complete event from a log marker. This creates a second false-green path: “the producer printed the phrase” can become “the outcome exists.”

### Healer

The Mini healer runs every four hours, performs deterministic checks before invoking an LLM, allows at most three PRs per tick, writes a heartbeat every run, and notifies only for acted, alerted, or degraded states (`docs/runbooks/healer-organ.md`). The Pro healer is runtime-only: it must not modify the repository and is limited to three cures per tick. Its whitelist includes kickstarting or enabling an already-installed, non-disabled organ, refreshing declared HOME pairs, and acting on log-backed evidence. It re-verifies findings each tick and requires content-delta proof (`infra/healer/HEALER-PRO-MANDATE.md`).

The mandate explicitly rejects restarting a process when the process is alive but its sidecar is dead. It also refuses a fallback to weaker models. These are excellent actuator-safety properties. What is missing from the inspected surfaces is a normalized cure journal with precondition, action, postcondition, independent verifier, attempt budget, rollback state, and causal linkage to the originating observation.

### Escalation board and chronic failure

The snapshot’s `shared/escalations_pro.jsonl` contains 14 rows: 13 pending, one resolved, 12 marked `NORMAL`, no `HIGH`, and no `healer_pro_tick` row. Displayed pending dates span 2026-07-07 through 2026-08-05. This does not corroborate the lane brief’s live “69 NORMAL plus eight HIGH” premise; the likely explanation is that live HOME/runtime state is newer than the snapshot, but that cannot be assumed.

`infra/launchagents/chronic_failure_digest.py` examines eight snapshots and reports organs red for at least three consecutive days. It deliberately complements a delta-only daily audit, including circuit-breaker, DLQ, and terminal-archive evidence. This is the correct antidote to unchanged failures disappearing from daily attention.

### PENDING-ARMS receptor

`.claude/skills/modus/PENDING-ARMS.md` is 2,202,762 bytes. Strict parse-shaped counting found 611 open rows:

- 203 opened in July 2026.
- 408 opened in August 2026.
- 11 were dated August 28–29.
- 600 were dated no later than August 27.

Because the rows carry dates rather than timestamps, 600 satisfy the report’s day-granularity `age >= 2` rule; exact wall-clock “older than 48 hours” cannot be recovered for August 27 entries.

`scripts/pending_arms_report.py` is more sophisticated than the Markdown view: it distinguishes actionable technical debt from natural waits, operator-gated items, firebreaks, malformed rows, and phantoms. Strict mode fails on actionable debt beyond the two-day threshold and on phantom/malformed entries. It can inspect `origin/main`, but warns implicitly through its design that the ref is only as fresh as the last fetch.

This is a good compiler attached to the wrong storage ergonomics. A 2.2 MB mixed human/machine document is no longer a readable receptor for a solo operator.

### Notifications, arsenal and Sentry

`docs/runbooks/telegram-notification-gateway.md` defines P0, digest, and log tiers, a P0 allowance of 12 messages per day per machine, six-hour deduplication, a durable fallback spool, and preservation of failed sends. The runbook also records a large historical population of direct senders still awaiting convergence. `docs/runbooks/organism-digest.md` acknowledges the same broad sender population and constrains the boot digest to at most 15 lines.

`docs/runbooks/arsenal-probe.md` shows careful hardening after a probe hung with a zero-byte report: per-seat timeouts, partial-reply classification before timeout, `DEVNULL` stdin, PATH fallbacks, a fail-visible header, and an explicit N/M summary. Known residual weaknesses include stale cached reports and a valid response being classified `UNKNOWN` when identifying output is truncated.

`.github/workflows/cron-sentry-quota-check.yml` checks configured trace sampling and a PII-related flag. It does not measure accepted versus discarded Sentry events. Runtime-read failure becomes a warning and exits successfully; missing Telegram secrets and send failure also do not fail the workflow. Therefore the brief’s “28% dropped for quota” is not verifiable here, and the check itself can be green without proving either quota health or alert delivery.

Eight relevant workflows exist under `.github/workflows/`—`watcher-coverage.yml`, `alarm-cure-alignment.yml`, `catB-daemon-cron-xor.yml`, `organ-conformance.yml`, `immune-enforcement.yml`, `main-push-failure-watch.yml`, `telegram-secret-healthcheck.yml`, and `cron-sentry-quota-check.yml`. Only the final workflow’s content was included in the 20-file evidence budget; existence is not evidence that the other seven currently enforce their names.

## 2. Scars & ledger evidence in this area

The superscar corpus identifies family #2, **“Esiste ≠ Armato,”** as the largest family: a green exit, installed plist, or heartbeat call is repeatedly mistaken for working behavior (`.claude/rules/cicatrix-superscar.md`). Families #7, #8, and #10 cover restart storms, network flaps, and active-active split brain.

| Evidence | What actually happened | Immune-system implication |
|---|---|---|
| W84-tcc-dead | Two launchd jobs exited zero while their logs recorded permission denial. | Exit state is not an outcome probe; some cures require operator/TCC action and must never become restart loops. |
| W108 | 19 of 20 NotebookLM cron wrappers failed silently; 16 made their alert path unreachable through shell fail-fast behavior, and 18 attempted ineffective token-poor direct notification. | Every failure path needs an independently exercised delivery receipt. Static wrapper conformance is insufficient. |
| W110 | A heartbeat call survived while writing the wrong organ identity/status/path due to a shell binding failure. The test asserted caller survival, not correct sidecar contents. | Heartbeats need schema, identity binding, provenance, and content assertions—not merely “write returned.” |
| W118 | The repository remained halted for more than 11 hours without a failed check: one job was cancelled by fail-fast after an external advisory change and another exceeded its total job budget. | Monitoring must classify `cancelled`, timeout, missing, and stale states—not just explicit failure. |
| W120 | A producer emitted `class`; its consumer read `classification`; the alarm branch never ran. At that historical snapshot, 280 of 441 open rows were overdue technical debt. | Producer/consumer contracts require schema tests and contradiction alarms. |
| Superscar #7 | KeepAlive on one-shot work caused restart storms. | Supervisors need workload-type-aware policy and restart intensity limits. |
| Superscar #8 | The family includes a 98-timeout network incident and single-attempt Telegram loss. | Network loss must become `UNKNOWN` plus durable retry, never healthy or silently complete. |
| Superscar #10 | Duplicate active hosts created split-brain risk. | Every cure and heartbeat needs assigned-node identity plus a single-writer lease. |

`scripts/lint_plist_keepalive.py` is an executable family-#7 antidote. It rejects backgrounding such as `nohup ... &`, warns on short wrappers without blocking markers, and calibrates `exec` as potentially correct for daemons. Its scope is repository plists, not live installation, and unresolved inline shell or binary behavior remains a blind spot.

`infra/organ-conformance/genes.json` encodes ten genes: registry membership, heartbeat, declared HOME pair, node guard, kill switch, hardened spawn, ledger integration, sane KeepAlive, fail-visible behavior, and single instance. `infra/organ-conformance/check_baseline_ratchet.py` ensures grandfathered absence only shrinks. This is strong evolutionary pressure, though it proves non-regression from a baseline rather than present health.

The 611 open PENDING rows, 600 crossing the report’s day-granularity threshold, show that the receptor itself has accumulated operational mass. They must not all be called overdue actionable debt: classification is required first. Nonetheless, retrieval cost and triage latency are now first-class failures.

No inspected scar supplied both exact detection and exact restoration timestamps, so MTTD and MTTR cannot be calculated. W118 supplies an outage duration but not a complete canonical incident clock. The unavailable memory corpus and uninspected `AMENDMENTS.md` cannot be used to fill that gap.

## 3. World SOTA survey

| System/practice | Primary source and date | Mechanism | Published effect | Transferability |
|---|---|---|---|---|
| Google SRE symptom monitoring | [Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/), 2016 | Black-box symptoms, four golden signals, low-noise actionable paging | Google reports teams of roughly 10–12 commonly spending one or two engineers on monitoring; no causal availability figure | Transfer principles, not staffing. Each organ should expose an outcome symptom distinct from causes and runtime state. |
| Google SLO burn alerts | [Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/), 2019 | Multiwindow, multi-burn-rate alerts optimize precision, recall, detection, and reset time | Worked example: naive alerting could page 144 times/day; recommended fast page consumes 2% budget and resets on a five-minute window | Highly transferable, with synthetic events for Nuzantara’s low-volume organs. |
| Kubernetes controllers | [Controllers](https://kubernetes.io/docs/concepts/architecture/controller/), live documentation | Repeated comparison of desired and current state; idempotent convergence | No universal numerical effect published | Direct conceptual fit for registry→observation→bounded cure, without importing Kubernetes. |
| Erlang/OTP supervision | [Supervisor Behaviour](https://www.erlang.org/doc/system/sup_princ.html), live OTP documentation | `one_for_one`, `one_for_all`, and `rest_for_one` strategies with restart-intensity escalation | No universal field metric | Transfer restart budgets and escalation semantics to launchd healers. |
| Meta FBAR | [Making Facebook Self-Healing](https://engineering.fb.com/2011/09/15/data-center-engineering/making-facebook-self-healing/), 2011 | Monitoring alerts feed queued, typed remediation plugins; post-repair verification restores service | Two engineers reported automation equivalent to about 200 administrators and coverage above 50% of infrastructure | Strong fit for typed, whitelisted cures; Nuzantara must keep a much smaller blast radius and Zero gate. |
| Netflix Chaos Monkey | [Netflix/chaosmonkey](https://github.com/Netflix/chaosmonkey), repository accessed 2026-08-29 | Controlled production instance termination forces resilience to become continuously demonstrated | No causal uptime number in the repository | Do not kill production organs; translate the principle into fixture-level, side-effect-free scar mutation pulses. |
| OpenTelemetry | [Signals](https://opentelemetry.io/docs/concepts/signals/), modified 2026-03-10 | Common resource identity and context correlate metrics, logs, traces, baggage, and emerging profiles | No vendor-neutral operational effect published | Adopt the semantic model and correlation IDs locally; avoid a costly wholesale telemetry migration. |
| systemd watchdogs | [sd_notify watchdog contract](https://cgit.freedesktop.org/systemd/systemd/tree/man/sd_notify.xml), live source accessed 2026-08-29 | Daemon sends watchdog proof within half its declared interval; supervisor records watchdog and start-limit failures | No universal numerical effect | launchd lacks the same native contract, but sidecars can reproduce its ownership and deadline semantics. |
| Healthchecks.io dead-man switch | [Healthchecks.io documentation](https://healthchecks.io/docs/), live documentation | Separate start, success, and failure signals; schedule plus grace time detects absence and hung runs | No public aggregate effect | Directly transferable as a local protocol; no external SaaS or PII is required. |
| Sentry quota observability | [Sentry Stats](https://docs.sentry.io/product/stats/), live documentation | Exposes accepted and discarded events by quota, rate limit, sampling, or spike protection | No general reduction figure | Measure actual discard reasons rather than checking only configured sample rate. |
| Honeycomb wide events | [Structured Events Are the Basis of Observability](https://www.honeycomb.io/blog/structured-events-basis-observability), 2022 | One high-cardinality event carries the complete context of a unit of work; mature examples approach 100 dimensions | No independently published MTTR effect on this page | A compact local “organ observation” event is preferable to regex reconstruction across logs. |
| Microsoft AIOpsLab | [AIOpsLab, MLSys 2025](https://proceedings.mlsys.org/paper_files/paper/2025/file/d1f9e4a9f109b6e8b75ed362736f22ec-Paper-Conference.pdf), 2025 | Workload generation, fault injection, telemetry, guarded agent interface, and evaluator in a reproducible environment | 100 benchmark problems across four agents; agent registration required 41–60 lines | Transfer the benchmark architecture to local scar-derived fixtures. The paper reinforces that LLM remediation remains evaluation-limited. |

Five patterns matter most:

1. **Controllers separate desired state from observed state.** Nuzantara has both ingredients, but not one joined reconciliation record.
2. **Supervisors distinguish retry from escalation.** A restart is not healing; restart intensity and causal grouping are essential against family #7.
3. **SLOs page on threatened outcomes.** Current controls emphasize component freshness and configuration more than service promises.
4. **FBAR couples typed diagnosis, rate-limited action, and postcondition verification.** The Pro healer already approximates this safely.
5. **Chaos and AIOpsLab evaluate the immune system by injecting known failures.** Nuzantara’s scar corpus supplies a uniquely relevant fault distribution that generic platforms do not possess.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence and judgment |
|---|---|---|
| Boundary provenance | **AHEAD** | Versioned runner/config provenance and expected/actual evidence in `docs/runbooks/proprioception-boundary-recon.md` exceed many small-fleet systems. |
| Desired/observed reconciliation | **BEHIND** | `apps/organism/organism/organs_registry.yaml` defines desired state, but no inspected projection joins it to installation, assigned node, heartbeat, outcome, sensor state, and cure state. |
| Heartbeat semantics | **BEHIND** | `infra/eventbus/heartbeat.py` converts Redis observation failure to alive; W110 shows survival-only heartbeat tests allowed false identity. |
| Cron dead-man detection | **AT** | Freshness, chronic failure, arsenal timeout, and sidecar patterns rival dedicated cron monitors, but remain distributed across heterogeneous formats. |
| Semantic outcome probes | **BEHIND** | `infra/eventbus/cron_log_sentinel.py` can infer pass/completion from regex prose; producer logs are not independent outcome evidence. |
| Conformance and anti-regression | **AHEAD** | Ten genes plus a monotone grandfather ratchet in `infra/organ-conformance/` turn scars into executable evolutionary pressure. |
| Safe auto-remediation | **AT/AHEAD** | Narrow whitelist, re-verification, three-action budget, evidence requirement, and no weak-model fallback in `infra/healer/HEALER-PRO-MANDATE.md` compare well with FBAR principles. |
| Restart/supervision policy | **AT** | `scripts/lint_plist_keepalive.py` encodes daemon-versus-cron knowledge, but live installation and runtime restart intensity are not established. |
| Alert quality and delivery | **BEHIND** | The Telegram gateway has durability, but direct sender debt remains; `cron-sentry-quota-check.yml` permits observation and delivery failures to remain green. |
| SLO/error-budget practice | **BEHIND** | No inspected control calculates organ outcome budgets or multiwindow burn rates. |
| Telemetry correlation | **BEHIND** | Registry, heartbeat, log bridge, healer, escalation, and ledger identifiers lack one demonstrated causal contract. |
| Operational receptor usability | **BEHIND** | The 2.2 MB PENDING file and 611 open rows exceed a human-readable working receptor’s practical scale. |
| Network and split-brain defense | **AT** | Node guards and single-instance genes exist; family #8 and #10 scars show why proof must remain continuous. |
| Incident-performance measurement | **BEHIND** | No canonical MTTD/MTTR pair was recoverable from inspected incidents. |
| Sensor self-observation | **BEHIND** | Many workload checks exist, but no inspected periodic negative control proves detector→alert→consumer delivery end to end. |

## 5. Beyond-SOTA recommendations

Ranking uses `(impact 1–5 × confidence) / implementation days`.

### 1. Compile PENDING-ARMS into operational projections — score 0.95

**What:** Preserve the append-only Markdown history, but generate separate `P0`, actionable-overdue, operator-gated, natural-wait, malformed, and recently-resolved views. Every row receives a stable ID, canonical class, owner boundary, deadline semantics, and source-line link.

**Why beyond SOTA:** Ticket systems provide views; Nuzantara can additionally compile its scar taxonomy, business-consent boundary, and agent lifecycle into one receptor without moving operational context to a SaaS.

**Before → after:** 2,202,762 bytes and 611 open rows in one view → default view ≤200 lines, 100% parse-shaped rows classified, malformed rows zero, p95 lookup under two seconds.

**Cost/gear:** Four engineering days; zero LLM tokens for runtime; Gear 2.

**Risk:** A projection could become another false source of truth—superscar #2. Measure source/projection count equality and content hashes.

**Kill criterion:** Stop migration if any source row disappears, duplicates, or changes class without an explicit diagnostic.

**First PR:** `feat(modus): emit typed pending-arms projections`; modify `scripts/pending_arms_report.py` and add fixture tests; ≤300 net lines.

### 2. Introduce the Organ Truth Contract — score 0.56

**What:** Emit one typed observation per organ:

`organ_id`, desired state, assigned node, artifact identity, process state, heartbeat state, semantic outcome, sensor state, evidence time/hash, causal run ID, confidence, cure state, and explicit `HEALTHY|UNHEALTHY|UNKNOWN`.

**Why beyond SOTA:** It composes Kubernetes reconciliation, OpenTelemetry correlation, dead-man timing, local sovereignty, and Nuzantara’s organ genes. Unlike generic platforms, it treats sensor failure as part of the observed state and binds every assertion to evidence.

**Before → after:** Zero inspected unified join rows → 170/170 registry entries projected; zero Redis-observation errors classified healthy; 100% non-healthy claims carry evidence provenance.

**Cost/gear:** Eight engineering days; deterministic runtime, with at most one redacted CLI council during schema design; Gear 3.

**Risk:** Wrong joins can amplify split brain or phantom health—families #2 and #10.

**Kill criterion:** Do not make it authoritative until it matches existing detectors for seven days and every disagreement is visible rather than overwritten.

**First PR:** `feat(organism): define evidence-bearing organ observation`; add a schema module beside `apps/organism/organism/organs_registry.yaml` and adapt `infra/eventbus/heartbeat.py`; ≤400 net lines.

### 3. Add sensor-of-sensor immune pulses — score 0.43

**What:** Inject harmless synthetic observations representing stale heartbeat, wrong organ ID, Redis unavailable, cancelled workflow, notification failure, TCC denial, timeout, and split-brain identity. Each pulse must traverse detector, escalation projection, durable alert channel, and receipt collector without actuating a real organ.

**Why beyond SOTA:** Chaos systems test workloads; this tests the immune system itself using the organism’s measured scar distribution.

**Before → after:** Zero inspected end-to-end detector pulses → at least 12 daily scenarios; ≥99% expected classification; MTTD below two detector intervals; unsafe real actions zero.

**Cost/gear:** Ten engineering days; zero runtime cloud tokens; Gear 2.

**Risk:** Pulse leakage could page the owner or trigger a cure—families #2, #7, and #8.

**Kill criterion:** Immediate disable on any real action, external publication, or more than one false P0 per 1,000 pulses.

**First PR:** `test(immune): add side-effect-free heartbeat fault pulses`; target `infra/eventbus/heartbeat.py` plus fixture-only pulse runner; ≤350 net lines.

### 4. Establish outcome and alert-delivery SLOs — score 0.36

**What:** Define SLIs for scheduled outcome completion, daemon semantic health, observation coverage, alert acknowledgement, Sentry acceptance, and healer postcondition success. Use Google-style multiwindow burn alerts; low-volume organs receive safe synthetic traffic.

**Why beyond SOTA:** Conventional SLOs stop at customer services. Nuzantara can assign error budgets to the observers and healers themselves, including “unknown” time.

**Before → after:** No inspected outcome/error-budget calculation and no verified delivery acknowledgement in the Sentry workflow → 100% critical organs assigned an SLI; alert-delivery success ≥99%; unknown observation time below 0.5%; discarded-event reason coverage 100%.

**Cost/gear:** Ten engineering days; deterministic calculations; Gear 2.

**Risk:** Poor SLO selection creates noise or false calm—families #2 and #8.

**Kill criterion:** Roll back any page rule with precision below 80% over 30 days or more than two unactionable P0s per week.

**First PR:** `feat(observability): measure alert delivery and discarded-event reasons`; harden `.github/workflows/cron-sentry-quota-check.yml` against silent observation failure using fixtures first; ≤350 net lines.

### 5. Promote healer actions to evidence-bound cure transactions — score 0.27

**What:** Record diagnosis evidence, independent precondition, lease/node identity, action, postcondition, rollback, attempt intensity, and escalation as one causal transaction. Permit no third failed cure in a rolling window; escalate instead.

**Why beyond SOTA:** FBAR provides plugins and Erlang supplies restart intensity. Nuzantara can add cross-family verification, scar-risk classification, and a cryptographic evidence trail while retaining Zero’s business authority.

**Before → after:** Three-action tick limit but zero inspected normalized cure transactions → 100% actions independently post-verified; cure success ≥90%; duplicate simultaneous cures zero; more than two failed attempts per incident zero.

**Cost/gear:** Fourteen engineering days; deterministic cures, optional redacted flat-sub CLI diagnosis only after prechecks; Gear 3.

**Risk:** The actuator is the highest-blast-radius surface—families #7 and #10.

**Kill criterion:** Any wrong-host action, restart storm, unverified recovery, PII persistence, or action outside the existing whitelist disables autonomous actuation.

**First PR:** `feat(healer): persist dry-run cure transactions`; touch `infra/healer/HEALER-PRO-MANDATE.md` and a new local transaction module; dry-run only, ≤400 net lines.

### 6. Build a scar-derived immune benchmark — score 0.27

**What:** Encode W84, W108, W110, W118, W120, and families #7/#8/#10 as reproducible scenarios with expected observation, alert, prohibited action, and resolution evidence.

**Why beyond SOTA:** AIOpsLab supplies generic cloud incidents. No surveyed system has this organism’s longitudinal, executable failure prior combined with local multi-machine controls and a generator≠grader culture.

**Before → after:** Zero inspected standardized immune benchmark scenarios → 20 scenarios by day 90; 100% critical historical scars detected; false-cure rate zero; benchmark runtime under five minutes locally.

**Cost/gear:** Twelve engineering days; no production fault injection and no paid API; Gear 3.

**Risk:** Tests may encode current implementation instead of intended truth—superscar #2.

**Kill criterion:** Reject any scenario whose oracle is merely the same function being tested or whose fixture can touch live launchd, Telegram, Redis, or client data.

**First PR:** `test(organ-conformance): encode six historical false-green scenarios`; add fixtures adjacent to `infra/organ-conformance/check_baseline_ratchet.py`; ≤400 net lines.

All recommendations preserve CLI-only LLM use, local sovereignty, the PII output boundary, bounded action, and the prohibition on automatic Fable routing.

## 6. 90-day roadmap + first PRs

### Wave 1 — Days 1–30: make truth measurable

- Compile PENDING-ARMS projections and establish lookup, classification, and age baselines.
- Define the Organ Truth Contract in shadow mode.
- Change heartbeat observation failure from implicit healthy to explicit `UNKNOWN`.
- Instrument delivery receipts and actual Sentry accepted/discarded reasons.
- Begin canonical incident clocks: `first_bad_evidence`, `detected_at`, `action_started`, `restored_at`, `verified_at`.

### Wave 2 — Days 31–60: test the observers

- Launch non-actuating immune pulses.
- Define outcome, observation, and alert-delivery SLOs.
- Correlate registry, heartbeat, escalation, cure, and notification through one causal ID.
- Run seven days of shadow reconciliation and analyze every disagreement.
- Add supervisor restart-intensity and assigned-node checks without expanding cure authority.

### Wave 3 — Days 61–90: prove bounded healing

- Introduce dry-run cure transactions, then enable only current-whitelist actions that meet success and safety gates.
- Expand the scar benchmark to 20 scenarios.
- Publish a weekly local scorecard: false-green rate, unknown time, detector precision/recall, MTTD, MTTR, cure success, repeat-cure rate, notification delivery, and ledger age.
- Authority remains local; only redacted aggregates may enter cloud CLI prompts.

| First PR | Files | Net-line ceiling | Gear | Acceptance test |
|---|---|---:|---:|---|
| `feat(modus): emit typed pending-arms projections` | `scripts/pending_arms_report.py`, fixture tests | 300 | 2 | All 611 snapshot rows reconcile exactly once; malformed input is explicit. |
| `fix(eventbus): report heartbeat backend failure as unknown` | `infra/eventbus/heartbeat.py`, tests | 200 | 2 | Simulated Redis failure can never return healthy; callers still degrade gracefully. |
| `feat(organism): define organ observation contract` | New schema beside `apps/organism/organism/organs_registry.yaml` | 400 | 3 | All 170 registry rows validate; evidence-less health is rejected. |
| `test(immune): exercise detector delivery pulse` | `infra/eventbus/cron_log_sentinel.py`, fixture-only pulse code | 350 | 2 | Synthetic failure produces the expected typed observation and receipt with no network/action. |
| `feat(observability): distinguish Sentry config from ingestion health` | `.github/workflows/cron-sentry-quota-check.yml`, parser fixtures | 350 | 2 | Missing runtime statistics is non-green; discarded reasons are reported without secret values. |
| `feat(healer): record dry-run cure transactions` | `infra/healer/HEALER-PRO-MANDATE.md`, new local transaction module | 400 | 3 | Every proposed action has precondition, lease, postcondition, and prohibited-action test. |
| `test(organ-conformance): add scar fault matrix` | `infra/organ-conformance/genes.json`, benchmark fixtures | 400 | 3 | W84/W108/W110/W118/W120 classes are detected without touching live services. |

## 7. Needs-ruling

1. **Outcome SLOs and paging thresholds:** Zero must decide which business outcomes justify immediate interruption, acceptable monthly error budgets, and quiet-hour policy.
2. **Actuator expansion:** Any cure beyond the current Pro whitelist—especially process termination, plist installation, credential repair, or cross-node action—requires explicit approval.
3. **Sentry commercial allocation:** Any quota increase, retention change, or paid telemetry allocation is a business-cost decision. Measurement of existing quota is technical; spending is not.
4. **Credentialed statistics access:** Enabling read-only Sentry usage statistics or delivery acknowledgement requires owner-approved credentials and scope.
5. **macOS TCC and GUI consent:** TCC-denied organs require physical/GUI authorization; automation must classify these as operator-only.
6. **Telegram P0 budget:** Changing the current daily cap, escalation recipients, or notification hours requires operator consent.

## 8. §Meta-pattern

The single defective belief is:

> **If a producer ran successfully, its claim exists, is correct, reached its consumer, and remains actionable.**

That belief generates green launchd jobs with dead outcomes, heartbeats with wrong identity, regex-derived success, cancelled CI that is not red, alerts that never arrive, stale reports treated as current, schema mismatches that suppress alarms, and a ledger that stores promises without guaranteeing retrieval.

The replacement belief is stricter: **every operational claim is a typed, evidence-bearing transaction whose observer, delivery path, consumer, and postcondition are independently falsifiable.** Nuzantara already has most of the raw organs needed; the next evolution is not more detectors, but a verifiable metabolism between them.

## 9. Sources

1. [Google, “Monitoring Distributed Systems”](https://sre.google/sre-book/monitoring-distributed-systems/) — 2016; accessed 2026-08-29. Primary Google SRE guidance on symptom monitoring, golden signals, and actionable alerts.
2. [Google, “Alerting on SLOs”](https://sre.google/workbook/alerting-on-slos/) — 2019; accessed 2026-08-29. Primary derivation of multiwindow, multi-burn-rate alerting and its precision/recall tradeoffs.
3. [Kubernetes, “Controllers”](https://kubernetes.io/docs/concepts/architecture/controller/) — live documentation; accessed 2026-08-29. Authoritative desired-versus-current reconciliation model.
4. [Erlang/OTP, “Supervisor Behaviour”](https://www.erlang.org/doc/system/sup_princ.html) — live OTP documentation; accessed 2026-08-29. Authoritative supervision strategies and restart-intensity model.
5. [Meta Engineering, “Making Facebook Self-Healing”](https://engineering.fb.com/2011/09/15/data-center-engineering/making-facebook-self-healing/) — 2011; accessed 2026-08-29. Primary FBAR architecture and reported automation scale.
6. [Netflix, `chaosmonkey`](https://github.com/Netflix/chaosmonkey) — source repository; accessed 2026-08-29. Primary implementation of controlled resilience fault injection.
7. [OpenTelemetry, “Signals”](https://opentelemetry.io/docs/concepts/signals/) — modified 2026-03-10; accessed 2026-08-29. Authoritative cross-signal telemetry model.
8. [systemd, `sd_notify` watchdog source documentation](https://cgit.freedesktop.org/systemd/systemd/tree/man/sd_notify.xml) — live source; accessed 2026-08-29. Primary watchdog notification contract.
9. [Healthchecks.io Documentation](https://healthchecks.io/docs/) — live documentation; accessed 2026-08-29. Primary dead-man-switch, grace-time, start, success, and failure semantics.
10. [Sentry, “Stats”](https://docs.sentry.io/product/stats/) — live documentation; accessed 2026-08-29. Authoritative definitions for accepted and discarded event reasons.
11. [Honeycomb, “Structured Events Are the Basis of Observability”](https://www.honeycomb.io/blog/structured-events-basis-observability) — 2022; accessed 2026-08-29. Primary exposition of wide, high-cardinality operational events.
12. [Microsoft Research et al., “AIOpsLab”](https://proceedings.mlsys.org/paper_files/paper/2025/file/d1f9e4a9f109b6e8b75ed362736f22ec-Paper-Conference.pdf) — MLSys 2025; accessed 2026-08-29. Peer-reviewed framework for fault injection and reproducible evaluation of operational agents.

Delivery note: this report was returned directly as required. No repository file was created, so no file-existence or `wc -w` claim is made.