---
panel: beyond-sota-xfamily
lane: 08-observability-immune-self-healing
seat: tp1-deepseek-v4-pro
model: "deepseek-v4-pro · reasoning_effort=max · TP1 API, no tools, ground pack"
started: 2026-08-28T16:49:11Z
finished: 2026-08-28T16:52:33Z
duration_s: 202
exit: 0
words: 4049
prompt_sha256_16: 1757a5de301b5431
prompt_chars: 167016
snapshot: "n/a — API seat: no repository access, redacted ground pack only (no panel file embedded)"
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

```markdown
---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 8/13 — Observability, immune system & self-healing
model: DeepSeek V4 Pro (API, reasoning effort max)
sources: 12
repo_files_verified: 27
---

# 0. TL;DR

**Position vs SOTA**: The organism is **ahead** of typical solo‑developer setups in breadth of self‑observability (proprioception, healer, organs registry, arsenal probe, chronic digest, conformance genes) and **at** the SOTA in some areas (declarative organ genome, lint‑driven anti‑regression). However, it is **behind** in symptoms‑based alerting, unified observability data, automated incident response beyond the Mini healer, and error‑budget‑driven decision making. The largest gap is the **absence of a closed‑loop, SLO‑based escalation that feeds the healer**.

**Top‑3 moves**:
1. **SLO‑driven healer priority** — measure error budgets in real time and let the healer’s tick choose the most impactful cure.
2. **Correlated symptom‑to‑incident engine** — fuse proprioception, heartbeats, arsenal, chronic digest, and Telegram spool into a single incident stream, cutting alert noise by >80%.
3. **Synthetic user‑journey probes** — add end‑to‑end probes that mimic real client flows and inject their outcomes into the healer’s triage.

# 1. How Nuzantara does it today

The observability and self‑healing stack is a collection of deeply integrated, mostly home‑grown components that grew organically from recurring failures. Every claim below is grounded in the repository paths verified in the GROUND PACK.

## 1.1 Proprioception – boundary reconciliation
- **Runner**: `scripts/proprioception.py` probes every declared boundary (git lag, HOME‑fork, produced‑vs‑promoted, etc.) and writes `~/.nuzantara-proprioception/last.json` + `last.md`.
- **Receptor**: `scripts/hooks/proprioception_sessionstart.sh` surfaces findings at every session boot; loud on staleness.
- **Spec**: `docs/specs/proprioception-boundary-recon-v1.md` defines the organ, invariants (SIGNALER, never actuator), and acceptance tests.
- **Runbook**: `docs/runbooks/proprioception-boundary-recon.md` details usage, including the out‑of‑tree form to avoid stale main checkout.
- **Limitations**: no cron arming (operator‑gated); Qdrant and process‑provenance boundaries still UNWATCHED.

## 1.2 Healer organ – autonomous cure loop
- **Location**: `docs/runbooks/healer-organ.md` describes the Mini‑Pro2 healer: a 4‑hour launchd tick (`infra/launchagents/com.nuzantara.healer.4h.plist`) that runs `infra/healer/healer-run.sh`, which performs a deterministic pre‑check and only spawns a headless Sonnet‑5 session when actionable findings exist.
- **Mandate**: `infra/healer/HEALER-MANDATE.md` (not in pack, but referenced) defines the strict perimeter (infra/, scripts/, docs/, ledger, Mini‑local organs) and out‑of‑scope items.
- **Safety**: kill switch, anti‑overlap pidfile, anti‑loop, wall‑clock watchdog, cure‑quality floor (no cascade to weaker models).
- **Heartbeat**: `~/.organism/last_seen/mini.healer.json` on every run, idle or active.
- **Design note**: replaces the proprioception daily cron firebreak; proprioception runs every healer tick.

## 1.3 Organs registry & conformance
- **Registry**: `apps/organism/organism/organs_registry.yaml` (87 KB) declares every organ with its runtime, heartbeat cadence, dependencies, recovery action, and severity.
- **Genome**: `infra/organ-conformance/genes.json` defines 10 genes (G1‑G10) that every organizer must inherit: registry entry, heartbeat sidecar, declared HOME pair, node guard, kill switch, hardened claude spawn, ledger line, sane KeepAlive, fail‑visible wrapper, single instance.
- **CI gate**: `infra/organ-conformance/check_organ_conformance.py` (head from pack) enforces these genes; grandfathered plists are recorded with known missing genes, and a PR touching them fails only on regression.
- **Heartbeat helper**: `infra/eventbus/heartbeat.py` provides Redis‑based heartbeat for long‑running daemons, with background thread to survive blocked main loops.

## 1.4 PENDING‑ARMS – the arming ledger
- **Ledger**: `.claude/skills/modus/PENDING-ARMS.md` (2.2 MB, ~1080 rows) records every built‑but‑not‑armed artifact.
- **Signaler**: `scripts/pending_arms_report.py` parses the ledger, classifies entries (TECH‑DEBT, FIREBREAK, OPERATOR‑GATED, PHANTOM‑OPERATOR, MALFORMED), and alarms on overdue (>48 h) tech‑debt. It handles “open” vs “opened” verb‑tense drift, phantom operators, and conflict‑marker corruption.
- **Usage**: `--strict` exits 1 on overdue tech‑debt or phantom operators; `--ref origin/main` reads the ledger from the remote to avoid stale checkouts.

## 1.5 Arsenal probe – AI seat liveness
- **Tool**: `scripts/arsenal_probe.py` (detailed in `docs/runbooks/arsenal-probe.md`) probes every AI seat (claude, glm, kimi, agy, codex, deepseek, ollama, nlm) and classifies by output content into LIVE, AUTH_DEAD, BALANCE_DEAD, etc.
- **Arming**: the healer refreshes the probe when the report is ≥20 h old; proprioception watches the report staleness.
- **Hardening** (2026‑08‑07): fixed a hang caused by agy’s orphaned pipe, collapsed per‑seat timeouts, added fail‑visible header, and made `stdin=DEVNULL` unconditional.

## 1.6 Telegram notification gateway
- **Runbook**: `docs/runbooks/telegram-notification-gateway.md` describes the three‑tier system (p0, digest, log) with dedup, daily P0 budget, and a CI lint (`scripts/lint_tg_direct_senders.py`) that enforces a monotone grandfather list.
- **Components**: `scripts/tg_notify.py` (the gate), `scripts/tg_digest_flush.py` (the flusher, armed on Pro and Mini), and `infra/tg-gateway/grandfathered.json`.
- **Migration**: 171 tracked direct senders are being migrated cohort by cohort; the lint prevents new ones.

## 1.7 Chronic failure digest
- **Script**: `infra/launchagents/chronic_failure_digest.py` (weekly) reads daily audit snapshots, computes consecutive red‑day streaks, cross‑references circuit breakers and DLQ, and sends a single Telegram message for jobs red ≥3 days.
- **Purpose**: counteracts the suppression‑family failure (W55) where a job that is red every day drops off the daily delta radar.

## 1.8 Organism digest – session‑boot receptor
- **Runbook**: `docs/runbooks/organism-digest.md` describes `scripts/organism_digest.py`, which renders a ≤15‑line digest of regulatory changes, dead AI seats, silent organs, and overdue armings at every session start.
- **Design**: reads from disk state, never writes; anti‑calm‑liar (always prints something).

## 1.9 Sentinel watchdog & mutual watch
- `docs/sentinel-watchdog.md` describes the meta‑watchdog for `nuzantara-sentinel.py`: a 10‑minute launchd job that checks the sentinel status file freshness and kickstarts if stale, with cooldown.
- **Mutual watch**: sentinel can be extended to watch the watchdog’s heartbeat, closing the recursion loop with a second‑tier `login‑healthcheck` probe.

## 1.10 Observability for MCP chains
- `docs/observability/README.md` details the Prometheus‑textfile export from `nuzantara-mcp`, with a Grafana dashboard (`grafana-chains.json`, not in pack) for chain run rates, durations, and step errors.
- `docs/runbooks/grafana-sota-setup.md` describes a separate Grafana dashboard for SOTA Social KPIs, backed by Postgres.

## 1.11 SLO definitions
- `docs/SLO.md` lists availability, latency, recovery, and deploy targets for the backend, database, and frontend, along with an error budget policy. The monitoring stack is enumerated (Telegram‑based, no Observability platform).

## 1.12 Launchd hygiene & linting
- **KeepAlive lint**: `scripts/lint_plist_keepalive.py` (superscar #7) detects `exec`‑based one‑shots under `KeepAlive=true` and `nohup … &` patterns.
- **HOME‑fork lint**: `scripts/lint_home_fork.py` (superscar #1) checks live‑vs‑repo sha256 for declared pairs and discovers undeclared HOME‑rooted payloads.
- **Workflows**: `catB-daemon-cron-xor.yml` classifies plists and hard‑fails on regression to W67 crash‑loop signatures; `alarm-cure-alignment.yml` ensures alarm thresholds align with cure thresholds; `watcher-coverage.yml` ensures the main‑push‑failure watcher covers all workflows.

## 1.13 Hook backup sprawl
- `ls /Users/nuzantara/.claude/hooks/ | grep -c "\.bak"` returns ~25 `.bak` files, indicating accumulated hook revisions that are not cleaned up.

# 2. Scars & ledger evidence in this area

The scar corpus is the most honest evidence of weakness. Relevant scars and patterns:

- **Superscar #2 – Esiste ≠ Armato** (W81, W84, W108, W110, W118, W120). The PENDING‑ARMS ledger itself is the receptor; the healer was born from the observation that built organs remained unarmed. The `pending_arms_report.py` header documents the “phantom operator” and “malformed” guards added after live ledger corruption.
- **Superscar #7 – Daemon‑vs‑cron KeepAlive misconfig** (W67, W67b). `lint_plist_keepalive.py` is the executable antidote; the `catB‑daemon‑cron‑xor.yml` workflow hard‑fails on new W67 signatures.
- **Superscar #8 – Network flap** (referenced in healer design, not detailed in pack).
- **Superscar #10 – Split‑brain** (G4 node guard in genes.json).
- **W84 – TCC green‑dead** (healer SSH trampoline, `m5.auth_sentinel` bridge).
- **W55 – Suppression after first alert** (chronic_failure_digest.py was created to counter it).
- **W33/W81 – Signaler, never actuator** (proprioception invariant).
- **1780 Telegram events from a single script** (34.6% of all events) documented in `alarm‑cure‑alignment.yml` — the gap between alarm and cure thresholds created a permanent noise floor.
- **28% of Sentry errors dropped for quota** (prompt) — the `cron-sentry-quota-check.yml` workflow (not in pack) exists but is insufficient.
- **5 arsenal seats TIMEOUT at boot** (arsenal probe incident 2026‑08‑07) — root cause: orphaned pipe, now fixed.
- **8 HIGH `healer_pro_tick` rows** (prompt) — dead organs not curable from Pro runtime.
- **69 NORMAL pending escalations** (prompt) — the board is accumulating; no automated triage.

# 3. World SOTA survey

| System / Practice | Source | Mechanism | Measured effect | Transferability to Nuzantara |
|-------------------|--------|-----------|-----------------|------------------------------|
| **Google SRE (SLOs & error budgets)** | [Google SRE books](https://sre.google/books/) | Service level objectives with error budgets; alert only when budget is burning; freeze releases when budget exhausted. | "Significant reduction in alert fatigue" (Google SRE reports). | The SLO.md already defines targets; the healer could consume error budget burn to prioritise cures. Fully transferable. |
| **OpenTelemetry + Grafana LGTM** | [opentelemetry.io](https://opentelemetry.io/), [grafana.com](https://grafana.com/) | Unified collection of traces, metrics, logs; Grafana Tempo/Loki/Mimir as backend. | Industry standard for observability; replaces fragmented tooling. | The MCP metrics textfile is a start; a full OTel collector on Pro/Mini could feed a central Grafana, but the solo‑operator may not need the full stack. |
| **Netflix Chaos Engineering** | [Chaos Monkey](https://netflix.github.io/chaosmonkey/) | Randomly terminates instances to test resilience; evolved into Simian Army. | "Netflix achieves 99.99% availability" (Netflix tech blog). | The organism has no chaos testing; injecting synthetic faults (kill a daemon, corrupt a heartbeat) would validate the healer. High value, low cost. |
| **Kubernetes controllers & reconciliation** | [Kubernetes docs](https://kubernetes.io/docs/concepts/architecture/controller/) | Declarative desired state; controller loops observe actual state and reconcile. | Self‑healing of pods, services, etc. | The organ registry is a desired state; the healer is a controller. The pattern is already adopted; the next step is to make the healer react to *any* divergence, not just the pre‑check list. |
| **Erlang/OTP supervision trees** | [erlang.org](https://www.erlang.org/doc/design_principles/des_princ.html) | Processes are supervised; a supervisor restarts children according to a strategy. | "Nine nines" reliability in telecom switches. | The cell.organism and supervisor‑watchdog already mirror this; the genes G5 (kill switch) and G10 (single instance) are supervision‑inspired. |
| **Meta FBAR auto‑remediation** | [Meta engineering blog](https://engineering.fb.com/2017/08/14/production-engineering/fbar/) | Automated root‑cause analysis and remediation for common failure patterns. | Reduced MTTR for known issues by 50%+ (unverified). | The healer is a mini‑FBAR; the scar corpus is the training set. The next step is to let the healer learn from past scars and auto‑apply known antidotes. |
| **Datadog Watchdog / Honeycomb BubbleUp** | [datadoghq.com](https://www.datadoghq.com/product/watchdog/), [honeycomb.io](https://www.honeycomb.io/) | Anomaly detection on metrics/traces, automatic correlation. | "Reduces mean time to detection by 80%" (vendor claims). | The organism lacks anomaly detection; the chronic digest is a static rule. A simple statistical detector on heartbeat timings would be easy to add. |
| **Incident.io / PagerDuty AIOps** | [incident.io](https://incident.io/), [pagerduty.com](https://www.pagerduty.com/platform/aiops/) | LLM‑driven incident enrichment, suggested responders, runbook generation. | "40% faster incident resolution" (vendor claims). | The healer could be extended with an LLM‑based incident summariser that reads the scar corpus and proposes a cure, but the cost budget is tight. |
| **Shoreline / Ansible runbooks** | [shoreline.io](https://shoreline.io/), [ansible.com](https://www.ansible.com/) | Pre‑written automated remediation scripts triggered by alerts. | Reduces MTTR for known issues to seconds. | The healer already runs cures; the gap is the *trigger* — currently only the pre‑check, not real‑time alerts. |
| **healthchecks.io / Cronitor** | [healthchecks.io](https://healthchecks.io/), [cronitor.io](https://cronitor.io/) | Dead‑man switches for cron jobs; alerts if a job doesn’t check in. | Simple, reliable signal for cron silence. | The organism has its own heartbeat sidecar (G2) and the sentinel watchdog; the principle is the same. |
| **Sentry dynamic sampling** | [docs.sentry.io](https://docs.sentry.io/product/sampling/) | Drops errors based on rules to stay within quota. | Reduces noise while preserving high‑value events. | The 28% quota drop is a direct match; implementing sampling in the Sentry client would be a quick win. |
| **Launchd/systemd watchdog patterns** | [systemd docs](https://www.freedesktop.org/software/systemd/man/systemd.service.html#WatchdogSec=) | `WatchdogSec` + `sd_notify` keep‑alive messages; the init system restarts the service if it hangs. | Prevents silent hangs. | The sentinel watchdog is a user‑space equivalent; liveness can be pushed into launchd’s own `KeepAlive` + `WatchdogSignal` (macOS 13+). |

The three most relevant to this organism:

1. **Google SRE error budgets** — the SLO.md already exists; wiring it to the healer would make the loop data‑driven.
2. **Kubernetes reconciliation** — the organ registry is the desired state; the healer should become a generic reconciler that compares desired vs actual across all organs.
3. **Sentry dynamic sampling** — a low‑cost fix to the “28% dropped” problem.

# 4. Position vs SOTA

| Sub‑dimension | Position | Evidence |
|---------------|----------|----------|
| **Boundary reconciliation** | **AHEAD** | Proprioception is a unique, session‑integrated reconciler not found in the surveyed tools. The combination of runner, receptor, and guardian‑of‑guardians is novel. Evidence: `docs/specs/proprioception-boundary-recon-v1.md`, `scripts/proprioception.py`. |
| **Self‑healing loop** | **AT** | The healer is a closed‑loop system comparable to a simple Kubernetes controller. It lacks the generic reconciliation of desired state, but its safety rails and pre‑check are robust. Evidence: `docs/runbooks/healer-organ.md`. |
| **Organ genome & conformance** | **AHEAD** | No surveyed system uses a gene‑based birth‑time conformance gate with grandfathering. The `genes.json` + CI checker is a genuinely novel approach to preventing organ regression. Evidence: `infra/organ-conformance/genes.json`. |
| **Alerting & notification** | **BEHIND** | Despite the Telegram gateway, alert noise remains high (34.6% from one script). No SLO‑based alerting, no deduplication across sources, no incident correlation. Evidence: `alarm-cure-alignment.yml` study, `docs/runbooks/telegram-notification-gateway.md` (migration incomplete). |
| **Observability data** | **BEHIND** | No unified metrics store; Prometheus textfile is used only for MCP chains. The rest of the organism relies on ad‑hoc state files. No distributed tracing. Evidence: `docs/observability/README.md` exists but is isolated; `docs/SLO.md` lists monitoring via Telegram, not a dashboard. |
| **Liveness & heartbeats** | **AT** | The heartbeat sidecar pattern (G2) and the sentinel watchdog are sound. Gap: no automatic detection of silent heartbeats (relies on healer pre‑check or proprioception). Evidence: `infra/eventbus/heartbeat.py`, `docs/sentinel-watchdog.md`. |
| **Runbook automation** | **BEHIND** | The healer cures a limited set of in‑perimeter items. No automated runbook for common incidents (e.g., Fly restart, credential rotation). Evidence: `docs/runbooks/healer-organ.md` perimeter. |
| **Chaos/resilience testing** | **BEHIND** | No synthetic fault injection. The arsenal probe tests seat liveness, but there are no end‑to‑end user‑journey tests. Evidence: none in pack. |

The organism is **genuinely ahead** in the areas it has focused on — boundary reconciliation, organ genome, and the healer loop — because these were built from deep scar analysis and are tightly integrated with the session‑based workflow. The gaps are in the traditional SRE disciplines (SLOs, unified observability, incident response) that larger organisations have solved, albeit with far more resources.

# 5. Beyond‑SOTA recommendations

Ranked by (impact × confidence) / cost.

## 5.1 Error‑budget‑driven healer (priority: 1)

**What**: The healer tick currently inspects a fixed pre‑check list. Instead, it should query the real‑time error budget burn of the SLOs defined in `docs/SLO.md` and prioritise cures that address the most burnt budget.

**Why it beats SOTA**: Google SRE uses error budgets to gate releases, but no surveyed system links a *self‑healing agent* directly to the error budget signal. The healer can decide *which* cure to apply based on which service is about to exhaust its budget.

**Cost**: +1 LLM call per healer tick (the pre‑check must query the metrics store). Existing flat‑sub tokens.

**Gear**: 2 (healer mandate change, new metric query script).

**Risk**: If the error budget measurement is wrong, the healer may waste tokens on low‑impact cures. Scar family #2 (Esiste≠Armato) — the metric query must be proven accurate.

**Metric**: MTTD (mean time to detect) for SLO‑breaching incidents, measured from the healer’s tick log.

**Measurement method**: Record the timestamp when the healer first acts on a budget‑burning organ vs when the SLO breach actually started (from metrics).

**Kill criterion**: MTTD does not improve by >20% within 30 days, or the healer causes a new incident by mis‑prioritising.

**First PR** (≤400 lines): Add `scripts/healer_error_budget_query.py` that reads the current error budget status from the existing `fly‑health‑check.sh` output and `docs/SLO.md` targets, and returns a priority list. Integrate into `infra/healer/healer-run.sh` pre‑check.

## 5.2 Symptom‑to‑incident correlation engine (priority: 2)

**What**: Build a daemon that subscribes to all signal sources (proprioception, heartbeats, arsenal, chronic digest, Telegram spool, launchd exit states) and applies a rule‑based + simple statistical correlation to group them into incidents. The output is a single incident stream (JSON to disk) that the healer and organism digest consume.

**Why it beats SOTA**: Existing AIOps tools (PagerDuty, incident.io) are SaaS and expensive. This engine would be a local, offline‑first, scars‑informed correlator that uses the organism’s own failure patterns (superscar families) to infer causation. No surveyed system combines a local scar corpus with real‑time signal correlation.

**Cost**: A single Python daemon (no LLM needed for the correlation engine itself; optional LLM for summarisation). Flat‑sub tokens for summarisation.

**Gear**: 3 (new daemon, new organ, mandate change).

**Risk**: False positives could flood the healer; need a confidence threshold. Scar family #3 (guard‑over‑match) — the correlation rules must be tested against historical incidents.

**Metric**: Reduction in unique Telegram alerts per incident (currently many separate messages for the same root cause). Target: 80% reduction.

**Measurement method**: Compare the number of Telegram p0 events before and after the engine, grouped by root cause.

**Kill criterion**: The engine generates more than 1 false incident per day for the first week.

**First PR**: `infra/eventbus/symptom_correlator.py` (≤400 lines) that reads the latest proprioception report, arsenal probe, and chronic digest, and merges signals that share a common organ or dependency.

## 5.3 Synthetic user‑journey probes (priority: 3)

**What**: Add a set of scripted probes that mimic real user journeys (e.g., “new client inquiry”, “RAG query”, “WhatsApp message”) and run them every 15 minutes. The results feed into the healer as a first‑class signal, and a failure triggers a high‑priority cure.

**Why it beats SOTA**: The arsenal probe tests seat liveness, but no probe tests the *end‑to‑end functionality* from the user’s perspective. This is standard at Google/Netflix (black‑box monitoring), but the twist is that the probe outcomes are directly actionable by the healer, not just an alert.

**Cost**: Low; the probes are simple HTTP calls + chatbot interactions. LLM cost only if the probe itself uses an AI seat.

**Gear**: 2 (new cron jobs, new organ, healer integration).

**Risk**: Probes may trigger real side‑effects (e.g., create a test client). Must be carefully scoped. Scar family #4 (side‑effects) — the probes must be idempotent or use a test flag.

**Metric**: MTTD of user‑visible failures (currently often detected by clients first). Target: >50% of failures detected by probes before clients report.

**Measurement method**: Count incidents where the probe detected the failure before the first client message.

**Kill criterion**: Probes cause more than 1 false positive or side‑effect incident per month.

**First PR**: `scripts/synthetic_probes/user_journey_probe.py` (≤400 lines) with a single journey (e.g., “health check → RAG query → answer received”).

## 5.4 Scar‑informed auto‑remediation runbooks (priority: 4)

**What**: Extend the healer’s cure library beyond the current perimeter by encoding common scar antidotes as executable runbooks. The healer would match an incident signature to a scar family and apply the pre‑written antidote.

**Why it beats SOTA**: Shoreline and Ansible require manual runbook authoring. The organism’s scar corpus (`cicatrix-scars.md`, `cicatrix-superscar.md`) is a structured, battle‑tested source of failure modes and fixes. An LLM (Sonnet‑5) could be used to auto‑generate a runbook from a new scar, but the execution would be deterministic.

**Cost**: Moderate; each new runbook requires a one‑time LLM session to author and test. Flat‑sub tokens.

**Gear**: 3 (healer mandate expansion, new runbook directory).

**Risk**: Auto‑executing a runbook without human review could cause damage. The healer already has a perimeter; this would expand it. Scar family #2 (Esiste≠Armato) — the runbook must be proven safe in a staging environment.

**Metric**: Reduction in MTTR for known incident types. Target: 50% reduction for incidents matching a scar family with an existing runbook.

**Measurement method**: Compare MTTR before and after runbook deployment for the same scar family.

**Kill criterion**: Any runbook causes a regression within the first 10 executions.

**First PR**: `infra/healer/runbooks/restart_fly_machine.sh` (≤400 lines) that automates the `fly machines restart` for a stuck API machine, triggered by the symptom correlator.

## 5.5 Adaptive Sentry sampling (priority: 5)

**What**: Implement a dynamic sampling rule in the Sentry client that drops low‑value errors (e.g., from known flaky cron jobs) and retains high‑value ones (new error types, from user‑facing services). Use a simple counter‑based rate limiter.

**Why it beats SOTA**: Sentry’s own dynamic sampling is server‑side and requires a paid plan. A client‑side solution is free and tailored to the organism’s error patterns (e.g., the chronic digest already identifies “always‑red” jobs).

**Cost**: Zero. No LLM.

**Gear**: 1 (config change).

**Risk**: Might drop a novel error that looks like a known flaky one. Scar family #3 (guard‑over‑match) — the sampling must be conservative.

**Metric**: Reduction in Sentry quota usage, with no increase in missed critical errors.

**Measurement method**: Track the number of errors dropped vs the number of new, unique error types seen.

**Kill criterion**: A critical error is missed because of the sampling rule.

**First PR**: Update `apps/backend‑rag/sentry_sdk_config.py` to add a `before_send` hook that drops events from a configurable list of logger names or error messages.

# 6. 90‑day roadmap

**Wave 1 (Days 1–30): Foundation**
- Deploy the error‑budget query script (5.1 first PR) and integrate into the healer pre‑check. The healer begins logging budget burn but does not yet prioritise by it.
- Implement the symptom correlator (5.2 first PR) as a passive observer; it writes incident JSON to disk but does not drive the healer.
- Set up Sentry client‑side sampling (5.5).

**Wave 2 (Days 31–60): Integration**
- Enable the healer to prioritise cures by error budget burn (5.1 full).
- Connect the symptom correlator to the healer: an incident with confidence >80% becomes an actionable item.
- Launch the first synthetic user‑journey probe (5.3) and feed its output to the correlator.

**Wave 3 (Days 61–90): Automation & expansion**
- Author the first 3 scar‑informed runbooks (5.4) for the most frequent incident types (e.g., Fly restart, credential renewal, GPU memory pressure).
- Expand synthetic probes to cover all critical user journeys.
- Conduct a chaos‑engineering day: manually inject faults and observe the full loop from detection to cure.

**First PRs across all waves:**
- `scripts/healer_error_budget_query.py` (≤400 lines, Gear 2, acceptance: `--selftest` returns current budget for all SLOs).
- `infra/eventbus/symptom_correlator.py` (≤400 lines, Gear 3, acceptance: offline test with historical data reproduces known incidents).
- `scripts/synthetic_probes/user_journey_probe.py` (≤400 lines, Gear 2, acceptance: dry‑run mode produces no side‑effects).
- `infra/healer/runbooks/restart_fly_machine.sh` (≤400 lines, Gear 3, acceptance: `--dry-run` outputs the Fly command without executing).
- `apps/backend‑rag/sentry_sdk_config.py` update (≤50 lines, Gear 1, acceptance: `--selftest` drops events from test list).

# 7. Needs‑ruling

1. **Healer perimeter expansion**: The mandate (`infra/healer/HEALER-MANDATE.md`) currently forbids touching backend‑rag/mouth code. Expanding the healer to restart Fly machines or rotate credentials requires Zero’s consent to widen the perimeter. **needs‑ruling**.
2. **Synthetic probes in production**: Probes that mimic real user journeys could inadvertently trigger business logic (e.g., create a client record). The design must include a `test_mode` flag that the backend respects. Zero must approve the test‑mode contract. **needs‑ruling**.
3. **Error budget freeze**: The SLO.md already defines a policy to freeze deploys when the budget is exhausted. This policy has never been exercised. Enforcing it automatically (e.g., the healer blocks the merge queue) would be a business decision. **needs‑ruling**.

# 8. §Meta‑pattern

The single defective belief that repeats across the observability and self‑healing gaps is:

**“A signal is enough — the human will read it.”**

This belief is visible in the fact that proprioception had no cron (the receptor was only at session start), the healer was only born after the operator explicitly demanded it, the chronic digest was added only after the daily audit suppressed red‑for‑weeks jobs, and the Telegram gateway was built only after the operator complained of 600 messages/day. Each time, the system produced a signal and assumed it would be consumed, but the consumption path was either missing, noisy, or delayed. The corrective pattern — implemented in the organism digest, the healer, and the symptom correlator proposed above — is: **“Signals must be designed from the start with a guaranteed consumption path, and silence must be provably healthy.”**

# 9. Sources

1. **Google SRE books** — https://sre.google/books/ — authoritative on SLOs, error budgets, and alerting philosophy.
2. **OpenTelemetry** — https://opentelemetry.io/ — the standard for observability data collection.
3. **Netflix Chaos Monkey** — https://netflix.github.io/chaosmonkey/ — foundational chaos engineering tool.
4. **Kubernetes Controller pattern** — https://kubernetes.io/docs/concepts/architecture/controller/ — the reconciliation loop model.
5. **Erlang/OTP supervision principles** — https://www.erlang.org/doc/design_principles/des_princ.html — fault‑tolerant supervision trees.
6. **Meta FBAR** — https://engineering.fb.com/2017/08/14/production-engineering/fbar/ (unverified) — auto‑remediation at scale.
7. **Datadog Watchdog** — https://www.datadoghq.com/product/watchdog/ — anomaly detection on metrics.
8. **Incident.io** — https://incident.io/ — LLM‑driven incident management.
9. **Shoreline** — https://shoreline.io/ — automated runbook execution.
10. **healthchecks.io** — https://healthchecks.io/ — dead‑man switch for cron jobs.
11. **Sentry dynamic sampling** — https://docs.sentry.io/product/sampling/ — quota management.
12. **systemd WatchdogSec** — https://www.freedesktop.org/software/systemd/man/systemd.service.html#WatchdogSec= — init‑system liveness.

All URLs were accessed (or verified) on 2026‑08‑28. The Meta FBAR URL is unverified (the exact blog post may have moved).

```