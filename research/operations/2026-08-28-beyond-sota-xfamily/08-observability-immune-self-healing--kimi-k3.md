---
panel: beyond-sota-xfamily
lane: 08-observability-immune-self-healing
seat: kimi-k3
model: "kimi-code/k3 · Kimi CLI print mode (tools)"
started: 2026-08-28T18:50:46Z
finished: 2026-08-28T18:59:08Z
duration_s: 502
exit: 0
words: 4345
prompt_sha256_16: e8e1602a12464975
prompt_chars: 18460
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

• [Pro] Executing lane 8 directly. Starting with grounding probes on the hot files.

• Grounding done. Now the SOTA survey — searching primary sources.

• One more grounding batch, then a final search and I'll write the report.

• All grounding and survey work is done. Per the lane instructions, the deliverable is returned here as my final message (no file write; the snapshot is read-only and the protocol's write-path is overridden to "return in final message" — therefore the `ls -la`/`wc -w` post-write probe is not applicable, stated explicitly).

  ---

  ```markdown
  ---
  date: 2026-08-28
  domain: operations
  panel: beyond-sota-2026-08-28
  part: 8/13 — Observability, immune system & self-healing
  model: Moonshot Kimi K3 (pinned lane)
  sources: 16
  repo_files_verified: 31
  ---

  # Lane 8 — Observability, immune system & self-healing

  **Access caveats (stated once, apply throughout):** I ran in a read-only snapshot; all paths are
  repo-relative. Every `$MEM`/memory-directory reference in the lane brief is UNAVAILABLE to me — I
  could not verify the "8 HIGH `healer_pro_tick` rows", "69 NORMAL pending", "28% Sentry drop", the
  `~/.nuzantara-proprioception/last.md` "6 divergences this morning", or the `~/.claude/hooks/*.bak`
  count. Where those figures matter I use the repository's own copies and say where numbers diverge.
  Assumption: the snapshot HEAD equals the panel worktree HEAD at launch.

  ## 0. TL;DR

  Nuzantara's immune system is **AHEAD of SOTA in concept** (no surveyed system — not Google SRE, not
  Meta FBAR, not the 2025-26 LLM-AIOps literature — has a measured-failure scar corpus compiled into
  executable CI antidotes with a one-way ratchet) but **BEHIND in operability of its own receptors**:
  the central ledger is 2.2 MB / 594 open rows with ~95% past its own 48h alarm threshold, SLOs are
  measured by infrastructure checks rather than user symptoms, and there is no recorded MTTD/MTTR for
  any incident. Top-3 moves: (1) close the **declared≠beating** gap — 162 of 170 organs declare a
  heartbeat expectation but nothing gates that a beat actually arrives; (2) shard/compress
  PENDING-ARMS so the receptor stays readable at fleet scale; (3) promote SLO alerting from
  machine-checks to symptom-based burn-rate alerts on the existing Prometheus/Grafana textfile path.

  ## 1. How Nuzantara does it today

  **Proprioception (boundary recon).** `scripts/proprioception.py` + `config/boundaries.yaml`, runbook
  `docs/runbooks/proprioception-boundary-recon.md`, spec `docs/specs/proprioception-boundary-recon-v1.md`.
  It runs ~7 pre-existing per-boundary reconcilers plus builtins (git-lag, ledger freshness, HOME-fork
  sha compare, produced↔promoted, guardian freshness). Design rules verified in the runbook: **"SIGNALER,
  never actuator"**, boundary classes with no probe are listed as **UNWATCHED in every report** ("absence
  is visible, never silent"), `--fleet` streams read-only over ssh, and the organ detects its own staleness
  ("SELF STALE", born from the 2026-08-08 incident where a 219-commit-stale copy emitted a remedy two
  merged PRs had already replaced). This is the reconciliation-of-reconcilers pattern; the Kubernetes
  controller analog, hand-built for a 3-machine fleet.

  **Healer (self-acting cure loop).** `docs/runbooks/healer-organ.md`, `infra/healer/` (`healer-run.sh`,
  `HEALER-MANDATE.md`, `HEALER-PRO-MANDATE.md`, `HEALER-PRO-DESIGN.md`, `CONVERGENCE-MANDATE.md`).
  Launchd tick every 4h (StartInterval 14400); a deterministic pre-check costs zero LLM tokens when
  healthy; only actionable findings spawn a headless Sonnet session that cures in-perimeter items via
  worktree → PR → auto-merge → prove-live → ledger. Safety rails verified: kill switch `HEALER_ENABLED=false`,
  pidfile anti-overlap, `HEALER_RUN=1` anti-loop, and `infra/healer/HEALER-PRO-MANDATE.md:17` forces
  **re-execution of every receptor each tick** ("Ogni finding dai receptor = FANTASMA finché non
  ri-verificato in questo tick (W65/W90)"). All three live pieces are declared HOME-fork pairs watched by
  `lint_home_fork.py`.

  **Organs registry + heartbeats.** `apps/organism/organism/organs_registry.yaml`: **170 organs**
  (`grep -c "^- id:"`), each with `expected_hb_seconds` (162 > 0, 8 = 0), `recovery_action`
  (156 `launchctl_kickstart`, 9 `fly_machines_start`, 4 `human_only`, 1 `noop`), and `severity_on_silence`
  (21 critical, 10 error, 25 info, 114 warning). `infra/eventbus/heartbeat.py` implements the classic
  dead-man switch: Redis key `bz:heartbeat:<daemon>` with TTL 120s, watchdog alerts after >5 min absent —
  the same pattern healthchecks.io productized. `infra/launchagents/` holds **156 plists**.

  **Organ-conformance genome.** `infra/organ-conformance/genes.json` (G1 registry entry, G2 heartbeat,
  etc. — "an organ absent from the registry is dark tissue"), enforced by `check_organ_conformance.py` in
  `.github/workflows/organ-conformance.yml` with a grandfathered baseline whose only legal direction is
  shrink, guarded by `check_baseline_ratchet.py` (exit 2 on uncomparable — "an uncomparable ratchet is not
  a passing ratchet"). Notably self-aware: the workflow header admits promotion to a *required* check is
  operator-gated in PENDING-ARMS.

  **PENDING-ARMS as receptor.** `.claude/skills/modus/PENDING-ARMS.md`: **2,202,762 bytes, 594 open
  rows**. Age profile measured: 188 opened July, 379 opened Aug-01→26 → **~567 rows (95%) are older than
  the 48h alarm threshold**. `scripts/pending_arms_report.py` is a pure signaler that alarms only on
  TECH-DEBT-class rows and treats declared firebreaks (`operator[business|gui|secret|control-plane|consent|
  physical|tcc]`) as informational — and the owner mix (≥145 business, 85 gui, 53 secret, 38 control-plane
  mentions) shows the majority of the backlog is legitimately operator-gated, not debt. Still: a 2.2 MB
  receptor is at the edge of human/agent readability, and several rows I sampled are multi-kilobyte essays.

  **Escalations board.** Repo copies: `shared/escalations_pro.jsonl` = **14 rows** (12 NORMAL, 13 pending,
  1 resolved; zero `healer_pro_tick` rows present), `shared/escalations_air.jsonl` = 2 rows. The brief's
  "69 NORMAL pending / 8 HIGH healer_pro_tick" lives only in the unavailable memory copies — flagged, not
  adopted.

  **Alerting surface.** Telegram gateway (`docs/runbooks/telegram-notification-gateway.md`): born from a
  measured **600 messages/day** overload; census found **171 executables** calling `api.telegram.org`
  directly; now one gateway with three tiers, a daily P0 budget and dedup, plus a CI lint guaranteeing the
  direct-sender family only shrinks. `infra/launchagents/chronic_failure_digest.py` closes the W55
  suppression hole (delta-only alerting drops chronically-red jobs after day 1) with weekly
  consecutive-red-streak digests cross-referenced against circuit-breaker + DLQ state.
  `.github/workflows/cron-sentry-quota-check.yml` daily-polices `SENTRY_TRACES_SAMPLE_RATE > 0.02` and
  `SENTRY_SEND_DEFAULT_PII`. `scripts/organism_digest.py` (`docs/runbooks/organism-digest.md`) routes the
  ≤15-line "what changed" digest into the channel actually read — the session boot — because "Telegram
  alerts go unread (NON LE LEGGO)".

  **Meta-watchers.** `docs/sentinel-watchdog.md` (who-watches-the-watcher for the ~58-job sentinel),
  `.github/workflows/main-push-failure-watch.yml` (one generic workflow-completion watcher replacing three
  hand-rolled ones) plus `watcher-coverage.yml` enforcing set-equality between the watcher's declared list
  and the live workflow census — a watcher that watches the watcher's coverage.

  **CI immune enforcement.** `.github/workflows/immune-enforcement.yml` runs guilt+innocence unit tests of
  the antidote tools on every PR (sentinel pattern; no schedule "by design (W84: no 177th daemon)") and the
  PHANTOM-OPERATOR strict gate; live $HOME runs happen fleet-side because CI has no fleet HOME.

  **SLOs & metrics.** `docs/SLO.md` (2026-04-06): availability targets (99.5% backend, 99.9% frontend)
  measured by "Fly.io health checks + fly-health-check.sh cron" — **infrastructure checks, not user
  symptoms**; no error-budget policy, no burn-rate alerting. `docs/observability/README.md` +
  `grafana-chains.json`: Prometheus-textfile metrics for the 8 MCP workflow chains (cardinality-bounded
  labels) with a Grafana dashboard — real but narrow.

  ## 2. Scars & ledger evidence in this area

  Superscar **#2 "Esiste ≠ Armato (cron theater / blind autopilot)"** (`.claude/rules/cicatrix-superscar.md:44`)
  is the dominant immune-system disease with **~30 member scars** — the largest family. Verified members
  that are directly about observability failing: W108 (19/20 cron jobs mute, 2 causes), W110 (heartbeat
  emitted on the wrong organ), W118 (11h stall, no check red), W120 (**the sentinel of the family itself
  disarmed** — antidote: "the probe must read the SAME key the reporter emits, or the alarm zeroes out
  mutely"), W70 (sentinel log_tail blind), W84-tcc-dead (launchd loses TCC grant → silent death), W81b
  (14 DLQ corpses never cleaned by the blind heal loop), W122 (red lies: work done, SIGINT→130), W123
  (run `success` ≠ armed). The ledger rows I sampled in PENDING-ARMS show the family still biting *this
  week*: the advisory Visa-Oracle fullstack smoke **never green since PR #4709** ("advisory means nothing
  blocks and nobody looks", opened 2026-08-24); `harness/fable-gate` published but not required (opened
  2026-08-24); a guard's 18-test suite executed by no workflow, passing conformance on an
  ancestor-directory loophole (opened 2026-08-22).

  **#7 Daemon-vs-cron KeepAlive** (`:158`): 2026-04-29 measured "53 LaunchAgents, 13% KeepAlive correct";
  executable antidote `scripts/lint_plist_keepalive.py` (verified header: `nohup &` = FAIL).
  **#8 Network flap** (`:175`): W49 (98 TimeoutErrors), W55 (Telegram single-attempt drop — the direct
  ancestor of the gateway and chronic digests), W32. **#10 Active-active split-brain** (`:216`): W67c
  (Telegram spam from the Mini), 12+1 mata_garuda active-active, NLM feeder; antidote is DB-SSOT
  `assigned_node` + graceful exit.

  **AMENDMENTS.md** (the loop's own misfire log) mentions healer/proprioception exactly **once** — the
  cure-loop machinery itself has low recidiva. The recurrence signal instead lives in #2: three separate
  scars (W108 → W118 → W120) are the *same* failure re-discovered at successive layers of the watcher
  stack, and #2's antidote keeps being re-generalized (exit code → output → activation state →
  same-key probe).

  **MTTD/MTTR:** no incident in the repo carries both a detection and a resolution timestamp; `MTTR`
  appears only in April-era plan docs (`docs/archive/2026-07-orphans/...`, `docs/sprint3/...`). The one
  quantified detection latency is W118's **11 hours** of stall with every check green.

  ## 3. World SOTA survey

  | System / practice | Source | Mechanism | Measured effect | Transfer to this organism |
  |---|---|---|---|---|
  | Google SRE: symptom-based alerting + SLO burn-rate alerts | sre.google/workbook/alerting-on-slos (2018+) | Alert on error-budget burn rate over dual windows, not on causes; page only on user symptoms | Google reports paging-precision/recall as first-class metrics; canonical elimination of alert noise | **High & direct**: docs/SLO.md measures machine checks, not symptoms; burn-rate alerting needs only the existing Prometheus path |
  | Google SRE on-call: "paging alerts fire only when customers are impacted" | sre.google/workbook/on-call | Thresholds derived from SLO | — | High: the Telegram gateway already did the noise half; the SLO-derivation half is missing |
  | Meta FBAR auto-remediation | engineering.fb.com 2011 & 2016; @Scale 2021 | Per-host daemons detect failure → take machine out of rotation → run scripted remediation → re-introduce only after verification | Handles thousands of hardware/software remediations daily without humans | **Structural match with the healer**: registry `recovery_action` + kickstart = FBAR's remediation scripts; FBAR's hard rule Nuzantara already exceeds — re-admission only after *probe-verified* health (prove-live) |
  | Kubernetes controller / reconciliation loop | Kubebuilder book; anynines 2025 (external-state drift) | Desired state in a registry; level-triggered loop continuously reconciles *actual* toward *desired*, including drift no event fired for | The entire industry's self-healing substrate | **Already adopted in spirit**: organs_registry.yaml is a desired-state CRD; proprioception is the drift detector for boundaries no informer covers. Gap: reconcile is 4h-ticked, not continuous |
  | Erlang/OTP supervision trees ("let it crash") | C2 wiki; OTP design principles; Zylos 2026 (supervision for AI agents) | Separate fault-handling from business logic; supervisors restart per policy; crash is a first-class, *logged* event | Decades of carrier-grade uptime (Ericsson AXD301: nine nines claimed) | Partial: launchd is the supervisor, but "let it crash" requires crashes to be *loud* — superscar #2 shows crashes here are swallowed (exit 0, empty output). The genes-at-birth genome is the fix vector |
  | systemd `WatchdogSec=` / `sd_notify("WATCHDOG=1")` | freedesktop.org systemd.service; 0pointer.de | Service must keep-alive-ping the manager; silence → restart + optional watchdog action | Failure latency bounded to the configured interval | Direct analog of `heartbeat.py` (Redis TTL 120s) — already AT this practice; macOS/launchd lacks the native equivalent, so the Redis switch is the right port |
  | Healthchecks.io / Dead Man's Snitch | healthchecks.io/docs | Reverse alerting: silence, not error, fires the alarm; per-job period + grace | Industry-standard cron-monitoring pattern | Already AT: sentinel watchdog + Redis heartbeats + cron_log_sentinel.py are a self-hosted healthchecks.io |
  | Sentry spike protection + dynamic sampling | docs.sentry.io/pricing/quotas/spike-protection | Server-side adaptive threshold drops events during spikes; per-key rate limits; client `beforeSend` filtering | Protects monthly quota automatically | Partial: repo polices static config (`SENTRY_TRACES_SAMPLE_RATE > 0.02`) daily, but has no *dynamic* sampling or spike protection — the (memory-reported) 28% quota drop is exactly what spike protection exists to prevent |
  | Honeycomb "observability 2.0" — arbitrarily wide structured events as single source of truth | charity.wtf 2024-12; honeycomb.io 2025-02 | One wide event per unit of work; derive metrics/traces from it; high cardinality is the point | Step-change in debuggability claims; cost-model inversion vs three pillars | Medium: the organism's real telemetry is *prose* (ledger rows, digests, scars) — wide-event thinking applies to making each healer tick / PR / probe one structured, queryable record |
  | Netflix chaos engineering lineage | Basiri et al., IEEE Software 2016; principlesofchaos.org | Deliberate fault injection against a steady-state hypothesis, minimized blast radius, in production | Cultural confidence in resilience; the Simian Army lineage | Low-as-written (solo fleet, no redundancy to exercise) but **high in adaptation**: inject *process* faults (kill a heartbeat, stale a checkout, drop a Telegram) and assert the immune system fires — see R6 |
  | LLM-driven AIOps / agentic RCA | arXiv Cloud-OpsBench 2026; OpenDerisk 2025; awesome-LLM-AIOps; GALA 2025 | LLM agents over telemetry for triage/RCA; benchmarks show plausible-but-unreliable hypotheses; practitioners prefer evidence-cited RCA | Field consensus: LLM RCA is assistive, not yet autonomous-trustworthy | The healer is already past the surveyed frontier in one dimension (it *acts*: PR → merge → prove-live) and matches it in another (W65/W90-mandated re-verification = the literature's "never trust the LLM's recollection") |
  | Shoreline/runbook automation class | (surveyed via AIOps sources) | Codified remediation runbooks triggered by alarms | — | Superseded by the healer's LLM-in-the-loop cure |

  The three that matter most: **(1) Google SRE's symptom/burn-rate alerting** — the single clearest
  technical gap: `docs/SLO.md`'s "measurement" column is infra checks, so a brown-out that fails users
  but passes health checks pages nobody (W118's 11h stall is this, lived). **(2) Meta FBAR** — validates
  the healer's architecture while exposing its soft spot: FBAR re-admits only after verified health, and
  Nuzantara's equivalent gate (prove-live) exists per-cure but the *standing* heartbeat half (does the
  organ beat *now*) is asserted at birth (gene G2) and not continuously ratcheted. **(3) The 2025-26
  LLM-AIOps literature** — confirms the organism's W65/W90 rule (re-execute, never recall) is exactly
  where the frontier landed, and confirms no surveyed system has anything like the scar→antidote→ratchet
  compile chain.

  ## 4. Position vs SOTA

  | Sub-dimension | Verdict | Evidence |
  |---|---|---|
  | Self-healing loop (detect→cure→prove) | **AHEAD** | Healer ticks 4h, zero-token pre-check, cures ship through the real PR pipeline with prove-live (`docs/runbooks/healer-organ.md`); no surveyed system closes the loop through code review |
  | Immune memory (failure corpus → executable antidote) | **AHEAD (unique)** | 10 superscar families, ~30-member #2, antidotes wired into CI (`immune-enforcement.yml`, `organ-conformance.yml`, `check_baseline_ratchet.py`); nothing comparable exists in the survey |
  | Watcher-watching (meta-observability) | **AHEAD** | sentinel-watchdog, watcher-coverage set-equality, guardian-freshness self-staleness, W120 same-key rule |
  | Alert-fatigue engineering | **AHEAD** | 600 msg/day → tiered gateway + P0 budget + dedup + chronic-streak digest + session-boot digest; most SOTA teams still tune Slack channels |
  | Boundary/drift recon across repo↔HOME↔fleet | **AT/AHEAD** | proprioception + declared-pairs lint = the controller pattern applied to a non-K8s estate; unique because the estate (3 Macs + Fly + Vercel) is unique |
  | Liveness/dead-man coverage | **AT** | Redis-TTL heartbeats + watchdog = healthchecks.io pattern; but 162 organs *declare* `expected_hb_seconds` with no verified emission gate |
  | Symptom-based SLOs & error budgets | **BEHIND** | `docs/SLO.md` measures Fly health checks; no burn-rate alert, no error-budget policy, no user-symptom SLI |
  | Quota/cost observability | **AT/BEHIND** | daily static config check; no spike protection / dynamic sampling (Sentry docs' own answer to the reported 28% drop) |
  | Incident metrics (MTTD/MTTR) | **BEHIND** | none recorded anywhere; only scar-embedded latencies (11h in W118) |
  | Chaos/fault-injection practice | **BEHIND** | none; closest is guard-fuzz (`research/operations/2026-07-11-guard-fuzz-immune.md`) which fuzzes guards, not the immune loop |
  | Ledger operability | **BEHIND (self-inflicted)** | 2.2 MB receptor, 95% of rows past the alarm horizon; the receptor risks becoming the next W70 (blind log-tail) |

  ## 5. Beyond-SOTA recommendations

  Ranked by (impact × confidence) / cost. All respect the hard rules (CLI-only LLMs, no paid API, PII
  boundary, Fable not auto-routed).

  **R1 — Declared≠Beating ratchet (the G2 run-time gene).** *What:* extend organ-conformance from
  birth-time to run-time: a fleet-side receptor (healer pre-check, zero tokens) verifies every organ with
  `expected_hb_seconds > 0` produced a `bz:heartbeat:*` key (or its declared equivalent) within 2× its
  declared interval; failures land on the escalations board; CI gate pins that the *checker itself* ran
  fresh (W120 same-key rule: the receptor reads the Redis key, not the organ's log). *Why beyond SOTA:*
  FBAR/K8s assume the kubelet/daemon reports honestly; W110/W120 proved organs here emit heartbeats on
  the wrong subject — no surveyed system ratchets *heartbeat provenance*. *Cost:* ~150 lines, flat-sub
  tokens only. *Gear:* 1. *Risk:* scar family #2 (a ratchet that reads the wrong key re-creates W120 —
  mitigate by reusing the registry's own owner_module as the key source). *Metric:* `organs beating /
  organs declaring hb` published in the organism digest; today: unmeasured (target ≥99%, alert <95%).
  *Kill criterion:* false-positive rate >2% over two weeks. *First PR:* `infra/organ-conformance/`
  + `scripts/healer_receptor_registry.py` — new gene G7 `heartbeat_liveness` + receptor check + 2
  guilt/innocence tests.

  **R2 — PENDING-ARMS sharding + compression (receptor readability).** *What:* split the ledger into
  `PENDING-ARMS/2026-07.md`, `2026-08.md`, … with a ≤200-line rolling index; `pending_arms_report.py`
  gains a summary mode (counts by owner-category × age bucket) that the healer/digest consume instead of
  parsing 2.2 MB. *Why beyond SOTA:* the ledger-as-receptor is already unique; keeping it *machine- and
  human-readable at 10⁴-row scale* is the part nobody else has needed to solve — it turns the receptor
  into a real observability surface (trend of tech-debt vs firebreak over months). *Cost:* ~200 lines +
  one-time migration. *Gear:* 1. *Risk:* family #9 (state-schema mutation drift — every consumer must
  read the new layout in the same PR; grep `PENDING-ARMS.md` consumers first). *Metric:* digest render
  lines for ledger status ≤10 (today: effectively unbounded); healer pre-check parse time. *Kill:* any
  consumer still reading the monolith after 2 weeks. *First PR:* `scripts/pending_arms_report.py` summary
  mode only (no migration yet) — proves the view before moving the data.

  **R3 — Symptom SLI + burn-rate alerting on the existing Prometheus path.** *What:* add one wide
  synthetic probe per user-facing surface (bot answer latency/success, `/kbli` page render, backend
  `/health/ready` *plus one real RAG query*), emitted to the existing textfile (`docs/observability/`),
  with a two-window burn-rate alert against `docs/SLO.md`'s 99.5% target; downgrade machine-check
  alerts to ticket-tier in the Telegram gateway. *Why beyond SOTA:* Google wrote the playbook, but the
  organism's asymmetry — the alert lands **in the next session's boot digest**, where an agent can act on
  it immediately — closes the loop faster than any pager rotation. *Cost:* ~300 lines (probe + alert
  rules + gateway tier change). *Gear:* 2. *Risk:* family #2 (a probe that checks the web tier while
  workers die = 503-RAG recidiva; the probe must exercise the full path) and #8 (probe itself
  network-flap-prone → retry with backoff). *Metric:* MTTD on injected probe failure (drill, R6) — target
  <15 min vs W118's 11h baseline; page-precision ≥95%. *Kill:* probe-induced user-visible cost or >1
  false page/week for a month. *First PR:* one probe (backend RAG path) + one alert rule + digest line.

  **R4 — Every receptor registers its own freshness as a boundary.** *What:* in `config/boundaries.yaml`,
  formalize watch-the-watcher: healer tick age, sentinel status age, digest emission age, this report's
  age — each a first-class boundary with severity; UNWATCHED tail must trend to zero. *Why beyond SOTA:*
  generalizes the one off-meta observation (W120: the family's own sentinel disarmed) into a *structural
  impossibility* — a receptor that cannot be added without adding its own freshness probe. *Cost:* ~80
  lines. *Gear:* 1. *Risk:* family #2 (obviously). *Metric:* UNWATCHED boundary count in the
  proprioception report; target 0 and CI-ratcheted. *Kill:* none — pure addition. *First PR:* registry
  entries + selftest update.

  **R5 — Scar-replay drills (chaos engineering for the immune system).** *What:* monthly, in a worktree/CI
  harness, inject the top-5 superscar fault shapes (kill a heartbeat key, swallow an exception behind
  exit 0, stale a guardian, fork a HOME copy, mute a cron's output) and assert the corresponding antidote
  fires — reusing the guilt-test batteries the antidotes already ship. *Why beyond SOTA:* Netflix injects
  infrastructure faults to test redundancy; this injects *process* faults to test the immune system itself
  — a chaos practice no surveyed system has because no surveyed system has executable antidotes to drill.
  *Cost:* ~350 lines harness + monthly flat-sub minutes. *Gear:* 2. *Risk:* family #6 (a drill that
  "passes" against a phantom antidote — drills must run the live CI gates, not stubs). *Metric:* antidote
  fire rate on drilled faults, target 5/5; published in the organism digest. *Kill:* drills consume >1
  healer-session/month. *First PR:* drill #1 (heartbeat-kill vs R1's G7) — the drill lands *with* the
  control it tests.

  **R6 — Alert-economics ledger.** *What:* the Telegram gateway already budgets P0; add a weekly
  accounting line (delivered / deduped / suppressed / dropped-for-quota per channel, including Sentry
  accept-vs-drop from its stats API) into the chronic-failure digest. *Why beyond SOTA:* observability
  of the observability pipeline's *delivery* — Sentry's own docs treat quota-drop as a billing fact;
  treating it as an SLI of the alerting organ is the step past. *Cost:* ~120 lines. *Gear:* 1. *Risk:*
  family #8 (API flap → retry). *Metric:* weeks with unknown drop-rate → 0. *Kill:* signal unused after 4
  weeks. *First PR:* gateway counters + digest lines.

  ## 6. 90-day roadmap + first PRs

  **Wave 1 (days 1–30) — close the known blind spots.** R1 (declared≠beating), R4 (receptor freshness
  boundaries), R2-stage-1 (ledger summary mode).
  - PR-1 "gene G7 heartbeat-liveness + receptor" — `infra/organ-conformance/genes.json`,
    `check_organ_conformance.py`, `scripts/healer_receptor_registry.py`, tests; ≤350 lines; gear 1;
    acceptance: CI guilt test where a registry organ with stale beat fails, innocence where fresh passes.
  - PR-2 "proprioception watches its watchers" — `config/boundaries.yaml` + `scripts/proprioception.py`
    builtins; ≤150 lines; gear 1; acceptance: `--selftest` lists 0 unwatched receptors.
  - PR-3 "pending_arms_report --summary" — ≤200 lines; gear 1; acceptance: digest renders ≤10 ledger lines.

  **Wave 2 (days 31–60) — symptom truth.** R3 (probe + burn-rate + gateway retiering), R2-stage-2
  (ledger sharding + consumer migration).
  - PR-4 "symptom probe: RAG path" — ≤300 lines; gear 2; acceptance: injected backend-worker kill pages
    within 15 min in a staging drill.
  - PR-5 "ledger shard 2026-07/08 + consumers" — ≤400 lines; gear 2; acceptance: `grep -rl PENDING-ARMS.md
    scripts/ .claude/` consumers all pass CI.

  **Wave 3 (days 61–90) — prove the immune system fires.** R5 (drill harness, 5 faults), R6 (alert
  economics), plus promote `organ-conformance.yml` and `watcher-coverage.yml` to required checks
  (needs-ruling, §7).
  - PR-6 "immune drill harness + fault #1" — ≤350 lines; gear 2; acceptance: 1/1 drill fires R1's alarm,
    recorded in the digest.

  ## 7. Needs-ruling

  1. **Required-check promotion** of `organ-conformance.yml` / `watcher-coverage.yml` — branch protection
     is operator-only control-plane (both workflows' own headers defer it; PENDING-ARMS rows exist).
  2. **Telegram P0 budget numbers** and any alert-severity policy that decides what may wake Zero —
     business judgment (Legge 5).
  3. **Any paid observability component** (Sentry plan changes, hosted dead-man service) — spend order
     requires explicit GO; all recommendations above are deliberately $0.
  4. Ledger rows owned `operator[business]` (145) — the sharding in R2 must not silently reclassify them;
     whether any of those firebreaks can be delegated is Zero's call.

  ## 8. §Meta-pattern

  One defective belief generates nearly everything in this lane: **"a checkable artifact at rest equals a
  live flow in motion."** The organism is superb at *creating* receptors — a registry, a ledger, a probe,
  a gate, a digest — and systematically under-invests in proving the receptor's output is *consumed and
  current*. The same shape recurs at every layer: the advisory smoke that was never once green (artifact:
  workflow; missing: anyone blocked on it); the published-but-not-required gate; the guard test suite
  executed by no workflow; 156 registry `recovery_action`s whose kickstart has never been drill-verified;
  594 ledger rows 95% past the alarm horizon; `sensitive:` flags no code reads; the family's own sentinel
  disarmed (W120). Even this panel's evidence shows it: the *immune* subsystem is the best-documented in
  the repo — and its central receptor is nearing unreadability. The organism's own W120 already stated
  the cure in one sentence — "the probe must read the SAME key the reporter emits" — and R1/R4/R5 are
  just that sentence promoted from scar-antidote to *architectural invariant*: nothing ships as
  observability unless its consumption path is itself observed. That is the beyond-SOTA move the survey
  confirms nobody else needs (they have humans who notice); here the consumer is the next agent session,
  so consumption must be mechanized.

  ## 9. Sources

  1. https://sre.google/workbook/alerting-on-slos/ — accessed 2026-08-28 — canonical burn-rate/symptom alerting method (Google SRE Workbook ch.5).
  2. https://sre.google/workbook/on-call/ — accessed 2026-08-28 — "paging alerts are symptom-based"; thresholds derived from SLOs.
  3. https://engineering.fb.com/2011/09/15/data-center-engineering/making-facebook-self-healing/ — accessed 2026-08-28 — primary: FBAR origin, detection→remediation loop.
  4. https://engineering.fb.com/2016/07/11/production-engineering/making-facebook-self-healing-automating-proactive-rack-maintenance/ — accessed 2026-08-28 — FBAR at scale; verified re-admission.
  5. https://atscaleconference.com/software-and-hardware-remediations-at-meta/ — accessed 2026-08-28 — Meta's own 2021 retrospective on remediation evolution.
  6. https://book.kubebuilder.io/reference/good-practices.html — accessed 2026-08-28 — authoritative statement of the reconciliation-loop contract.
  7. https://anynines.com/blog/external-state-drift-kubernetes-controller-self-healing-design/ — accessed 2026-08-28 — why event-only watching isn't self-healing; level-triggered drift detection (proprioception's exact argument).
  8. https://wiki.c2.com/?LetItCrash — accessed 2026-08-28 — primary-artifact wiki for the OTP supervision philosophy.
  9. https://zylos.ai/research/2026-03-16-supervisor-trees-fault-tolerance-ai-agent-systems/ — accessed 2026-08-28 — 2026 application of supervision trees to agent systems.
  10. https://docs.sentry.io/pricing/quotas/spike-protection/ — accessed 2026-08-28 — official mechanism for the quota-drop problem (dynamic threshold, per-project).
  11. https://healthchecks.io/docs/ — accessed 2026-08-28 — dead-man's-switch reference semantics (period + grace, reverse alerting).
  12. https://charity.wtf/p/there-is-only-one-key-difference-between-observability-1-0-and-2-0 — accessed 2026-08-28 — primary (Majors): wide events as single source of truth.
  13. https://www.honeycomb.io/blog/one-key-difference-observability1dot0-2dot0 — accessed 2026-08-28 — vendor statement of the same; cost-model implications.
  14. https://arxiv.org/html/2603.00468v1 — accessed 2026-08-28 — Cloud-OpsBench (2026): reproducible benchmark for agentic RCA; state of LLM-AIOps.
  15. https://arxiv.org/html/2510.13561 — accessed 2026-08-28 — OpenDerisk (2025): industrial AI-SRE framework, design + case studies.
  16. https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html — accessed 2026-08-28 — `WatchdogSec=`/`sd_notify` watchdog semantics; the native analog of `heartbeat.py`.
  (Plus: Basiri et al., "Chaos Engineering", IEEE Software 33(3), 2016 — the discipline's defining paper, via principlesofchaos.org lineage.)

  **Repo paths verified on disk this session (31):** `docs/runbooks/proprioception-boundary-recon.md`,
  `docs/specs/proprioception-boundary-recon-v1.md`, `docs/runbooks/healer-organ.md`,
  `infra/healer/` (5 files incl. `HEALER-PRO-MANDATE.md`), `shared/escalations_pro.jsonl`,
  `shared/escalations_air.jsonl`, `apps/organism/organism/organs_registry.yaml`,
  `infra/organ-conformance/genes.json`, `infra/organ-conformance/check_baseline_ratchet.py`,
  `infra/eventbus/heartbeat.py`, `infra/eventbus/cron_log_sentinel.py`, `scripts/pending_arms_report.py`,
  `.claude/skills/modus/PENDING-ARMS.md`, `scripts/lint_plist_keepalive.py`, `scripts/lint_home_fork.py`,
  `infra/launchagents/` (156 plists), `infra/launchagents/chronic_failure_digest.py`,
  `docs/runbooks/organism-digest.md`, `docs/runbooks/arsenal-probe.md`,
  `docs/runbooks/telegram-notification-gateway.md`, `docs/sentinel-watchdog.md`,
  `docs/observability/README.md`, `docs/observability/grafana-chains.json`, `docs/SLO.md`,
  `.github/workflows/immune-enforcement.yml`, `.github/workflows/organ-conformance.yml`,
  `.github/workflows/watcher-coverage.yml`, `.github/workflows/main-push-failure-watch.yml`,
  `.github/workflows/cron-sentry-quota-check.yml`, `.claude/rules/cicatrix-superscar.md`,
  `.claude/skills/modus/AMENDMENTS.md`.

  status: complete
  sections_done: [0,1,2,3,4,5,6,7,8,9]
  ```

  **Notes on contract deviations (deliberate, per lane override):** the report is returned in this message instead of written to the worktree path (the lane brief overrides every write instruction with "return the content in your final message", and the snapshot is read-only); consequently the post-write `ls -la`/`wc -w` probe has no file to probe — the content above is the whole artifact. Word count of the report body: ~3,400. Three memory-only figures from the brief (8 HIGH `healer_pro_tick`, 69 NORMAL pending, 28% Sentry drop, hooks `.bak` count) could not be verified inside the snapshot and are flagged as such rather than asserted.

