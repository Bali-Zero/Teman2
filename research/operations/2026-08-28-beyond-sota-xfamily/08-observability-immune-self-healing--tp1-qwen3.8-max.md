---
panel: beyond-sota-xfamily
lane: 08-observability-immune-self-healing
seat: tp1-qwen3.8-max
model: "qwen3.8-max · enable_thinking · TP1 API, no tools, ground pack"
started: 2026-08-28T16:56:09Z
finished: 2026-08-28T17:04:23Z
duration_s: 494
exit: 0
words: 5527
prompt_sha256_16: f37a25bb3689ef6e
prompt_chars: 167003
snapshot: "n/a — API seat: no repository access, redacted ground pack only (no panel file embedded)"
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 8/13 — Observability, immune system & self-healing
model: Qwen3.8 Max (pinned lane)
sources: 14
repo_files_verified: 20
---

> **Verification method (anti-hallucination disclosure).** This lane ran with **NO file, shell or web access** (per the lane header). Every repository claim below is grounded **only** on the redacted GROUND PACK appended to the lane prompt; pack files are the on-disk excerpts for this lane. Paths the pack *references but does not include* (e.g. `scripts/proprioception.py`, `infra/healer/healer-run.sh`, `scripts/tg_notify.py`, `shared/escalations_pro.jsonl`) are cited as claims **the pack's runbooks make**, and flagged where I could not inspect the file itself. Anything not supportable from the pack is labelled **ASSUMED**. Items the protocol asks me to compute that I cannot without a shell are marked **UNMEASURED** with the exact command to run. **MEM: unavailable** — `MEMORY_SENTRY.md` and `project_receptor_live_mandate_2026_08_26.md` were **NOT FOUND in the snapshot**; I do not cite memory bodies. Web tools were not loaded in this lane, so the SOTA survey is drawn from model knowledge; URLs I am confident exist are given plainly, uncertain ones marked `(unverified)`, all stamped with the nominal access date.

---

## 0. TL;DR

**Position vs SOTA:** *AHEAD* on self-describing liveness architecture (organs registry + organ-conformance genome + signaler-only proprioception + receptor-consumption model), *AT* on heartbeat/watchdog/Prometheus mechanics, *BEHIND* on telemetry breadth, closed-loop MTTR measurement, chaos injection, and alert-delivery reliability (28% Sentry quota drop; 34.6% of Telegram volume proven non-actionable).

**Biggest gap:** the organism is excellent at *detecting* that it is sick and *refusing to lie* about silence, but the **cure leg is not measured** — no per-incident MTTD/MTTR, no proof the healer's cures actually close the scars that spawned them, and the actuator boundary (SIGNALER-never-actuator, W33/W81) leaves every declared `recovery_action` advisory rather than executable.

**Top-3 moves:**
1. **Scar-conditioned alerting** — compile the scar corpus into live detectors + guilt/innocence regression tests so every measured failure becomes a standing immune rule.
2. **Executable recovery_action reconciler** — a perimeter-limited, audit-logged actuator that runs only the idempotent `recovery_action`s already declared in `organs_registry.yaml`, keeping proprioception a pure signaler.
3. **Closed-loop MTTR ledger** — give the healer an incident object with both timestamps, turning the self-reported "~15–30min" MTTR into a measured, per-family number.

---

## 1. How Nuzantara does it today

The immune system is layered as **sense → reconcile → route → cure → learn**, with an unusually strict separation between *signalers* (never act) and *actuators* (bounded perimeter).

### 1.1 Proprioception — the boundary-reconciliation organ
`docs/runbooks/proprioception-boundary-recon.md` describes `scripts/proprioception.py` as "the reconciler of reconcilers": it *runs* the existing per-boundary reconcilers (launchd liveness W84, launchagent canon #1926, organ heartbeats, docs sync W86) and adds builtins for previously-unwatched classes — git lag + **PENDING-ARMS ledger freshness** (checkout↔origin), **HOME-fork sha compare**, **produced↔promoted**, and **guardian freshness** ("a stale guardian is itself DIVERGED"). Boundary classes with no probe are listed as `UNWATCHED` — *"absence is visible, never silent."* It is **SIGNALER, never actuator (W33/W81)**: "it never pulls, restarts, unloads or fixes anything."

The spec (`docs/specs/proprioception-boundary-recon-v1.md`) names the disease it treats as the *"malattia-delle-malattie"*: "Every recurring trauma family reduces to: a signal emitted on ONE side of a boundary … is trusted as truth for BOTH sides, and nothing probes across." Output verdicts are `RECONCILED|DIVERGED|UNPROBEABLE`. Invariants: content-compare never proxy (W88), machine-aware paths, no secret values, **no new daemon** (176 already exist; W84). The receptor `scripts/hooks/proprioception_sessionstart.sh` reads `last.json` at every session boot and "is never silent": fresh+clean → one-line heartbeat; divergences → compact block; report missing/older than 48h → loud STALE alarm. Exit contract: `0` organ worked, `1` only under `--strict` with a P1 divergence, `2` infrastructure failure ("never trust a run that exited 2").

A self-awareness wrinkle worth flagging: the runbook documents the **W106b** incident where a report "6.7h old — fresh by every check that existed — carried a remedy two merged PRs had already replaced, because the writer was 219 commits behind," and prescribes the out-of-tree form (`git -C ~/nuzantara show origin/main:scripts/proprioception.py > /tmp/prop_main.py && NUZ_REPO_ROOT=~/nuzantara python3 /tmp/prop_main.py`) to separate *the code that measures* from *the checkout being measured*.

The lane brief states **6 divergences this morning**; `last.md` was **NOT FOUND in the snapshot**, so I cannot independently confirm the count — **ASSUMED** as of pack time.

### 1.2 Organs registry + heartbeats
`apps/organism/organism/organs_registry.yaml` (version 1, sha256 checksummed, ~87 KB, truncated in pack) declares each organ with: `id`, `runtime` (`fly_machine`/`pro_launchd`/`air_launchd`), `type` (`daemon`/`webhook`/`cron`), `expected_hb_seconds`, `owner_module`, `dependencies`, **`recovery_action`** (`fly_machines_start`/`launchctl_kickstart`/`human_only`), `recovery_params`, **`severity_on_silence`** (`critical`/`warning`/`info`), `cicatrix_refs`, and a **`bridge_source`** (`state_file` with `timestamp_field`/`status_field`, or `http` with `json_path`). ~26 organs are visible in the 12,000-char excerpt (e.g. `infra.postgres`, `backend.api`, `pro.sentinel`, `cell.organism`, `channel.*`); the full file clearly carries dozens more. Disabled organs carry `disabled_reason` (e.g. `backend.crm.drive_poll` "saturated PG" 2026-04-29; `backend.kg_langgraph_orchestrator` feature-flagged).

Liveness is proven by the organ itself via heartbeat sidecars. `infra/eventbus/heartbeat.py` implements a Redis TTL heartbeat (`bz:heartbeat:<daemon>`, TTL 120s, throttled 1/30s) with `is_alive()` that **fails open** when Redis is down, and `start_background_beater()` specifically to solve the case where the main loop blocks longer than the TTL (XREADGROUP BLOCK).

### 1.3 Organ-conformance genome (the "DNA self-healing genome")
`infra/organ-conformance/genes.json` is "the ORGAN GENOME: single source of truth for the genes every launchd/cron organ must inherit at birth," consumed by `check_organ_conformance.py` (CI gate) and `scripts/organ_birth.py` (generator). **10 genes**: `G1_registry`, `G2_heartbeat`, `G3_declared_pair`, `G4_node_guard`, `G5_kill_switch`, `G6_spawn_hardened`, `G7_ledger`, `G8_keepalive_sane`, `G9_fail_visible`, `G10_single_instance`. The `grandfathered` map (~50 plists visible) records known-missing genes at gate birth and is **report-only**: "a PR touching a grandfathered plist FAILS only on REGRESSION … Regenerate after curing an organ … shrinking the baseline is the cure metric; growing it requires a PR reviewer's eyes." (`check_baseline_ratchet.py` was **NOT FOUND in the snapshot** — **ASSUMED** to be the ratchet enforcement.)

### 1.4 Healer organ — the autonomous cure loop
`docs/runbooks/healer-organ.md`: born 2026-07-06, it "converts the three receptor-only organs (proprioception, PENDING-ARMS ledger, escalations board) into a self-acting loop." launchd fires every 4h (`StartInterval 14400`); a **deterministic pre-check costs zero LLM tokens when healthy**; only actionable findings spawn a headless Sonnet-5 session that "cures in-perimeter items (worktree → PR → auto-merge → prove-live → ledger)." Safety rails: kill switch `HEALER_ENABLED=false`, anti-overlap pidfile, anti-loop `HEALER_RUN=1`, wall-clock watchdog (`HEALER_MAX_WALL_S` default 3300s). Perimeter is *tassativo*: IN = infra/scripts/docs/ledger/Mini-local organs/declared-pair HOME sync; OUT = backend-rag/mouth code, hooks, workflows, migrations, secrets, publish, remote machines, the healer itself, modus. Max 3 PR/tick. **Cure-quality floor:** if the claude tier is degraded it "does NOT cascade cures to weaker models — heartbeat `degraded` + Telegram + exit." Observability: heartbeat sidecar `~/.organism/last_seen/mini.healer.json` EVERY run, *including idle* (`status=ok note=idle`).

The lane brief references **8 HIGH `healer_pro_tick` rows** ("dead organs root-caused as not curable from the Pro runtime") and a **Pro healer mandate**, but `HEALER-PRO-MANDATE.md` was **NOT FOUND in the snapshot** — the Pro variant's existence is taken from the runbook's Mini/Pro framing + the brief (**ASSUMED**).

### 1.5 Receptors & the notification economy
- **Organism digest** (`docs/runbooks/organism-digest.md`): born from Zero's "NON LE LEGGO" — Telegram alerts go unread, so a ≤15-line digest of the last 24h is delivered at **session boot** via a third SessionStart hook. It is "a READER over state that already exists on disk," migrating no producers. Doctrine: *"Feed the system first … Chat pings are a VIEW, never the store,"* "session boot = daily read guaranteed; Telegram = P0-only," and "nothing may exist ONLY as a Telegram message."
- **Telegram gateway** (`docs/runbooks/telegram-notification-gateway.md`): born from "non posso più ricevere 600 messaggi al giorno." A census found **171 tracked executable files** calling `api.telegram.org` directly. Three tiers — `p0` (immediate, `TG_P0_BUDGET` 12/day/machine, 6h dedup), `digest` (one grouped message 08:00+20:00), `log` (disk-only). `lint_tg_direct_senders.py` enforces a **monotone-shrinking** `grandfathered.json`; ~169 senders migrate cohort-by-cohort.
- **Sentinel meta-watchdog** (`docs/sentinel-watchdog.md`): the explicit answer to "who watches the watcher?" A short-lived job every 10min stats `sentinel_status.json`; if missing/stale (>15min = 3× the 5-min cadence) it alerts + `launchctl kickstart`, with a 1h cooldown. Recursion is closed by **mutual watch** (each daemon watches the other's heartbeat file) plus the independent `login-healthcheck` catch-all; non-persistent execution (~50ms–2s) means it cannot hang like the sentinel can.
- **Chronic-failure digest** (`infra/launchagents/chronic_failure_digest.py`): the **W55** fix. The daily audit "alerts ONLY on a delta … A job that has been red for many consecutive days produces ZERO delta after day 1, so it silently drops off the daily radar — the exact W55 'suppression after first alert' failure family that masked the 2026-05-25 evolver/deploy-puller 32h drift and the 6 stale ops worktrees (W62)." The digest computes consecutive-day red streaks, cross-refs the circuit-breaker registry + DLQ, and emits ONE weekly Telegram for jobs red ≥ THRESHOLD (default 3) days, deliberately excluding static config smells so it "would not relist the whole plist-shape backlog every week."
- **Arsenal probe** (`docs/runbooks/arsenal-probe.md`): seat liveness for the multi-LLM cascade, classifying by **OUTPUT CONTENT, never exit code alone** (`LIVE/AUTH_DEAD/CONTEXT_AUTH/QUOTA_DEAD/BALANCE_DEAD/MODEL_ERR/SHED/TIMEOUT/CRED_UNAVAILABLE/NOT_INSTALLED/UNKNOWN_ERR`). It documents the 2026-08-07 hang ("agy's stdout pipe never closes … the probe ate its FULL per-seat timeout") and the fix: **"Judge the reply, not the timeout" (W104)**, timeouts collapsed to ~15s, fail-visible stderr header, `stdin=DEVNULL`, `resolve_bin` fallback, "final line always states `N of M seats OK`." The lane brief's **5 seats TIMEOUT at boot** matches this disease class (**ASSUMED** mapping; the pack does not carry the specific boot row).

### 1.6 CI immune gates & telemetry
Workflows verified in pack: `watcher-coverage.yml` (set-equality self-conformance, "no plausible false-positive mode"), `alarm-cure-alignment.yml` (see §2), `catB-daemon-cron-xor.yml` (daemon|cron classification + W67 crash-loop hard-fail; encodes "52 LIVE plist … carry BOTH KeepAlive AND a schedule"; 93 committed / 45 ambiguous / 7 bare KeepAlive=true / 0 W67-class on 2026-06-11). The `.github/workflows/` directory listing shows **106 entries** including `organ-conformance.yml`, `immune-enforcement.yml`, `main-push-failure-watch.yml`, `telegram-secret-healthcheck.yml`, `cron-sentry-quota-check.yml` (bodies omitted at pack cap — contents **ASSUMED**).

Telemetry: `docs/observability/README.md` — the MCP server emits **4 Prometheus-shaped series** (`chain_runs_total`, `chain_duration_seconds`, `chain_steps_total`, `chain_step_errors_total`) for 8 workflow chains to a textfile, scraped into Grafana with 4 panels (run rate, error rate with 0.1-investigate/0.3-page thresholds, p95 duration, step errors). All labels cardinality-bounded; **error arguments never used as labels** (Legge 2 / PII). **The baseline table is entirely TBD** ("Fill these in after the first week"). `docs/SLO.md` declares availability/latency/recovery targets but is **Last Updated 2026-04-06** (≈5 months stale) and lists "Vector DB (Qdrant Cloud)" while `organs_registry.yaml` declares `infra.qdrant` as `runtime: fly_machine` — an unreconciled doc↔registry boundary.

**MEASURE items I cannot compute (no shell) — commands:**
- plists-on-disk vs registry entries vs live heartbeats:
  `ls ~/Library/LaunchAgents/*.plist | wc -l` ; `grep -c '^- id:' apps/organism/organism/organs_registry.yaml` ; `ls ~/.organism/last_seen/*.json | wc -l` (then freshness-compare each `ts` vs `expected_hb_seconds`).
- PENDING-ARMS by month & >48h: `grep -c '^- open' .claude/skills/modus/PENDING-ARMS.md` ; `grep -o 'opened 2026-0[0-9]' .claude/skills/modus/PENDING-ARMS.md | sort | uniq -c` ; `python3 scripts/pending_arms_report.py --strict` (overdue count).
- Alert delivery: `ls ~/.organism/tg_spool/ ; cat ~/.organism/tg_spool/last_flush.json`.
- **UNMEASURED** — MTTD/MTTR per incident (no incident in pack carries both timestamps).

---

## 2. Scars & ledger evidence in this area

**Scar-corpus caveat:** I had no shell to `grep` `cicatrix-scars.md` / `cicatrix-superscar.md` directly. Evidence below is drawn from **verbatim scar quotations embedded in the pack's docstrings** plus the brief's W-numbers. W110/W118/W120 content was **not present in the pack** → **ASSUMED**.

| Family / W# | What bit | Evidence (pack) | Recurred? |
|---|---|---|---|
| **superscar #2 "Esiste≠Armato"** (largest) | Exists ≠ armed; **green ≠ working** (cron theater). Built but not armed; loaded but not firing. | Pervades `pending_arms_report.py` (W81), `arsenal-probe.md` ("audit 2026-05-24 found the cascade 2-deep with nobody noticing"), `organism_digest` rationale. | Yes — it spawned three organs (proprioception receptor, PENDING-ARMS, healer) and still recurs. |
| **superscar #1 HOME-fork drift** (~30% of corpus) | Live `$HOME` copy diverges from git-tracked source. W50/51/52, W68/70/72/73, W76, W81. | `lint_home_fork.py` docstring; cure = `cmp -s` live↔tracked CI. | Yes — the lint exists *because* fixes landed in repo but live copies never saw them. |
| **superscar #7 daemon-vs-cron KeepAlive** | `KeepAlive=true` on one-shot payload = restart storm. W67/W67b wa-mirror, W60 Fly flapping, 2026-04-29 "53 LaunchAgents, only 13% KeepAlive correct." | `lint_plist_keepalive.py`, `catB-daemon-cron-xor.yml`. | Yes — `catB` re-verified 45 ambiguous committed plists 2026-06-11. |
| **superscar #3 guard over/under-match** | A guard that matches the *word* not the *intent*. | `lint_plist_keepalive.py` fd-redirect carve-out; `pending_arms_report.py` verb-tense drift (`open` vs `opened`) and the stray `|||||||` diff3 conflict marker. | Yes — the doctrine "every FAIL ships an innocence test" is the recurrence brake. |
| **W84 TCC-green-dead / "green lies"** | launchd TCC denies `~/Desktop`; job is green but dead. | cicatrix_ref `2026-06-16-W84-tcc-green-dead` on `m5.auth_sentinel`, `pro.claude_settings_watcher`; healer ssh-trampoline note. | Yes — "fail-visible, W84 discipline" recurs across lints. |
| **W55 suppression-after-first-alert** | Delta-only alerting drops chronically-red jobs after day 1. Masked 32h drift + 6 stale worktrees (W62). | `chronic_failure_digest.py`. | Addressed by the digest; the *class* (alert fatigue) reappears as the Telegram 34.6% finding below. |
| **alarm/cure dead-zone** | Alarm line (1MB) below cure line (10MB): 11 files 1.1–7.1MB "permanently loud and permanently ineligible for the cure." One script = **1798 of 5202 Telegram events in 29.5 days (34.6%), none actionable.** | `alarm-cure-alignment.yml`. | Yes — "the gap had already been found once" (2026-07-20) and "NOTHING DETECTED THE HALF LEFT." |
| **nb-agents-daily-dr cause-escape** | Failed 13 days running, sent 13 P0s "Exit: 1" while the day log held "Authentication expired. Run 'nlm login'." | `alarm-cure-alignment.yml` (cause-escapes job). | Recurs as superscar-family "sensor measures its own environment, not the seat" (W108 lineage). |
| **W106b stale-measurer** | Propioception report 6.7h-fresh but 219 commits behind, carrying a superseded remedy. | `proprioception-boundary-recon.md`. | Motivated `SELF STALE` + out-of-tree execution. |
| **W104/W108 arsenal sensor errors** | Probe hung on agy's never-closing pipe (0 bytes output); PATH-poor context reported false `NOT_INSTALLED`. | `arsenal-probe.md` 2026-08-07 incident. | Recurs as the "judge the reply, not the timeout" doctrine. |
| **Sentry quota drop** | **28% of errors dropped for quota** (brief); `cron-sentry-quota-check.yml` exists. | Brief + workflow listing (body omitted). | **ASSUMED**; **UNMEASURED** delivery rate. |

**MTTD/MTTR:** the only MTTR number is `docs/SLO.md` self-report ("Target <15min / Current ~15–30min"). No incident in the pack carries both detection and resolution timestamps → **UNMEASURED**. Command: `jq -r '[.detected_ts,.resolved_ts]|@tsv' shared/escalations_pro.jsonl` then diff, **but the file was not in the snapshot.**

---

## 3. World SOTA survey

**Web tools were not loaded in this lane.** The following is model knowledge, not fetched content; access date is nominal (2026-08-28). `(unverified)` = URL not certain.

| System / practice | Source | Mechanism that makes it best-in-class | Measured effect (if published) | Transferability to THIS organism |
|---|---|---|---|---|
| Google SRE — Monitoring Distributed Systems | https://sre.google/sre-book/monitoring-distributed-systems/ (2016) | The four golden signals (latency/traffic/errors/saturation); "monitoring should be automated, humans only for judgment." | Canonical. | High — maps onto organ `expected_hb_seconds` + severity_on_silence. |
| Google SRE — SLOs | https://sre.google/sre-book/service-level-objectives/ (2016) | SLOs as a contract; error budgets gate release velocity. | Canonical. | Partial — `SLO.md` exists but is stale and not wired to automation. |
| Google SRE Workbook — Alerting on SLOs | https://sre.google/workbook/alerting-on-slos/ (2018) | Multi-window multi-burn-rate alerts → alert only when budget burns. | Canonical. | High — would replace fixed-threshold alerts (the 1MB/10MB dead-zone class). |
| Kubernetes controllers | https://kubernetes.io/docs/concepts/architecture/controller/ | Declarative desired-state + continuous reconciliation (level-triggered, not edge-triggered). | Industry-standard self-healing. | High — organs_registry `recovery_action` is already a desired-state spec; needs a reconciler. |
| Erlang/OTP supervision trees | https://www.erlang.org/doc/design_principles/sup_princ.html | "Let it crash" + restart strategies (one-for-one/rest-for-one) with bounded restart intensity. | Decades of telecom uptime. | High — identical shape to W67 restart-storm avoidance + healer anti-overlap. |
| systemd watchdog (`WatchdogSec`/`sd_notify`) | https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html | Process must *prove* liveness by ping; watchdog kills on silence. | OS-native. | High — this is exactly "healthy-silence must be provable," but launchd has no native `sd_notify`. |
| healthchecks.io — dead-man switch | https://healthchecks.io/ | Alert on **absence** of a periodic ping (cron monitoring). | Widely used. | High — the organism already has this pattern (`last_flush.json` self-probe) but hand-rolled. |
| OpenTelemetry | https://opentelemetry.io/docs/concepts/signals/ | Unified traces/metrics/logs with context propagation. | Industry standard. | Medium — organism is Mac-local + Fly; tracing breadth is the gap. |
| Netflix Chaos Monkey | https://github.com/Netflix/chaosmonkey | Randomly terminate prod instances to force resilience. | Proved resilience at scale. | Medium — safe to adapt for non-prod local organs; NOT for prod fly machines without ruling. |
| Google Borg (EuroSys'15) | https://research.google/pubs/large-scale-cluster-management-at-google-with-borg/ (2015) `(unverified)` | Auto-restart/reschedule as a first-class scheduler property. | Canonical. | Conceptual — validates "recovery_action should be executable." |
| Meta Twine (OSDI'20) | https://www.usenix.org/conference/osdi20/presentation/talwar (2020) `(unverified)` | Cluster-wide automated remediation + health checks. | Large-scale. | Conceptual. (The brief's "FBAR" has no public primary source I can confirm — **not cited as fact**.) |
| Grafana LGTM stack | https://grafana.com/oss/lgtm-stack/ | Loki+Grafana+Tempo+Mimir unified observability. | Widely adopted. | Medium — organism already runs Grafana (dashboards in pack). |
| PagerDuty AIOps | https://www.pagerduty.com/platform/aiops/ | Noise reduction, alert correlation, incident routing. | Commercial. | Partial — the organism's tg-gateway dedup/budget is a hand-rolled AIOps-lite. |
| Honeycomb wide events / Observability 2.0 | https://www.honeycomb.io/blog/observability-2-0 `(unverified)` | High-cardinality wide events; debug with arbitrary slicing. | Influential. | Partial — conflicts with Legge 2 (PII) → wide events on CRM data are banned; usable for infra-only. |

**Academic 2023–2026 (LLM-driven incident response), all `(unverified)`:** Microsoft "Empowering Practical Root Cause Analysis by LLMs for Cloud Incidents" (2024); `RCACopilot` (on-call LLM triage); `D-Bot`/LLM database diagnosis (arXiv/VLDB 2024); `AIOpsLab` (agent benchmark). These validate the *direction* of the healer organ but none ship a **scar-corpus-conditioned** detector library — that asymmetry is the organism's.

### The 3–5 that matter most here
1. **Kubernetes reconciliation** is the single most transferable pattern: `organs_registry.yaml` is already a declarative desired-state spec (`recovery_action`, `severity_on_silence`, `dependencies`). The organism detects drift superbly but does not *reconcile* it. A perimeter-limited reconciler is the obvious next step — and the organism's SIGNALER/actuator firebreak (W33/W81) is the right guardrail, not a reason to skip it.
2. **Alerting-on-SLOs (multi-burn-rate)** directly cures the `alarm-cure-alignment` dead-zone class: instead of two independently-maintained constants (1MB alarm vs 10MB cure), the alert is derived from one budget. This is the principled fix for "permanently loud and permanently ineligible for the cure."
3. **systemd `WatchdogSec` + dead-man switches** formalize what the organism already believes ("healthy-silence must be provable") but implements ad hoc per-organ. Standardizing the ping/absence contract across all ~156 plists would close the launchd gap (launchd has no native watchdog).
4. **Erlang supervision trees** are the correct mental model for W67/W60 restart storms: bounded restart intensity + explicit child specs. The `catB` daemon|cron XOR lint is a static shadow of this; a runtime supervisor would be the live form.
5. **Chaos Monkey** is the *missing* discipline. The organism has guilt/innocence tests for detectors but never **injects** faults to prove MTTD. On always-on local machines this is cheap and safe for non-prod organs.

---

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| Self-describing organ inventory (registry+recovery_action+severity) | **AHEAD** | `organs_registry.yaml` ties every organ to a recovery_action, silence severity, and cicatrix_refs. Big-tech has this for services, rarely for a solo operator's ~156 launchd jobs. |
| Liveness-genome enforced at birth (genes.json) | **AHEAD** | 10 genes + regression-only grandfathered baseline + "shrinking baseline is the cure metric" is beyond standard practice. |
| Signal-vs-actuator separation + fail-visible + content-compare | **AHEAD** | W33/W81, W84, W88 invariants; "a report that can't prove its provenance is not a clean report." |
| Watchdog-of-watchdogs (explicit recursion answer) | **AHEAD** | `sentinel-watchdog.md` mutual watch + non-persistent execution is a rigorous, rare treatment. |
| Notification economy (state-on-disk + tiers + dedup + monotone lint) | **AHEAD** | tg-gateway (3 tiers, budget, monotone grandfather) + organism-digest receptor model. |
| Chronic-failure (delta-blindness) detection | **AHEAD** | `chronic_failure_digest.py` streak logic explicitly cures W55. |
| Alarm/cure alignment as CI | **AHEAD** | `alarm-cure-alignment.yml` — almost nobody CI-checks that alarm threshold ≤ cure threshold. |
| Heartbeat/TTL watchdog mechanics | **AT** | `heartbeat.py` is standard (Redis TTL + watchdog), with a nice fail-open + background-beater touch. |
| Prometheus metrics + Grafana dashboards | **AT** | `docs/observability/README.md` — correct shape, bounded cardinality, but **baseline TBD** (never filled). |
| SLO definition | **AT→BEHIND** | `SLO.md` exists but is 5 months stale, error-budget policy not enforced, and Qdrant Cloud↔fly_machine divergence. |
| Telemetry breadth (traces/logs) | **BEHIND** | Metrics cover only 8 MCP chains; no distributed tracing; Legge 2 blocks wide events on CRM data. |
| Alert-delivery reliability | **BEHIND** | 28% Sentry quota drop (brief); 34.6% of Telegram volume non-actionable (`alarm-cure-alignment.yml`). |
| Autonomous remediation that *measures itself* | **BEHIND** | Healer exists, but MTTR is a self-report; no incident object with both timestamps; `recovery_action` advisory only. |
| Chaos / fault injection | **BEHIND** | No runtime fault injection; only static guilt/innocence tests. |
| Ledger-as-receptor scalability | **BEHIND** | PENDING-ARMS at **2.2MB / 1080 rows** (brief) is past human-readable scale; the parser survives (positional guard removed, per `pending_arms_report.py`), but human navigation is the bottleneck. |

---

## 5. Beyond-SOTA recommendations

**Assumption on `gear`:** I read gear as effort/autonomy tier — **gear 1** = deterministic/cheap (no LLM), **gear 2** = LLM-assisted, **gear 3** = autonomous/meta-loop. (Not verifiable from pack; flagged.)

Ranked by (impact × confidence)/cost.

### R1 — Scar-conditioned alerting (compile the scar corpus into live immune rules)
- **What:** every superscar family and each closed W# becomes (a) a standing detector (lint/guard/probe) and (b) a guilt+innocence regression test, tracked in a coverage ledger: "scar → detector → test → armed."
- **Why it beats SOTA:** no surveyed system has a *corpus of its own measured failures that is itself compiled into detection rules automatically*. Google/Netflix alert on symptoms generically; the organism's asymmetry is that scars are **already structured, measured, and honest** ("scars are measured failures, the most honest evidence"). This closes learn→detect with no new sensing.
- **Cost:** gear 2 (LLM to draft detectors from scar text); ~1–2 PRs per family. Flat-subscription tokens only.
- **Gear:** 2.
- **Risk + scar family it could trigger:** over-matching → **#3**. Mitigate with the existing "every FAIL ships an innocence test" doctrine.
- **Metric + method:** % of scar families with a live armed detector (before: partial — #1/#2/#7 have lints; after: 100%); recurrence rate of closed families (target 0). Method: `grep -c` armed-detector rows in a new `research/operations/scar-detector-coverage.md` vs `grep -c '^## '` superscar families.
- **Kill criterion:** if a generated detector's false-positive rate >10% over 2 weeks, revert it (a #3 over-match is worse than no detector).
- **First PR:** add `scripts/scar_detector_coverage.py` that parses superscar headers and asserts each has a `detector:` pointer; wire into `immune-enforcement.yml` (≤400 lines).

### R2 — Executable `recovery_action` reconciler (the cure leg becomes real)
- **What:** a new, perimeter-limited **actuator organ** that reconciles only the idempotent `recovery_action`s already declared in `organs_registry.yaml` (`fly_machines_start`, `launchctl_kickstart`) when `severity_on_silence` is breached and the silence exceeds `expected_hb_seconds`. Distinct from proprioception, which stays SIGNALER-only (W33/W81 preserved). Audit-logged, kill-switched, max-N-restarts/hour (Erlang restart-intensity bound), never touches `human_only`.
- **Why it beats SOTA:** Kubernetes reconciles but has no scar-conditioned recovery_actions; the organism has recovery_actions but no reconciler. Composing them is novel, and the registry makes it *safe* (only pre-declared, idempotent actions).
- **Cost:** gear 2; reuses existing recovery_params. No paid API.
- **Gear:** 2.
- **Risk + scar family:** restart storm → **#7**; split-brain → **#10** (G4 node guard must be honored); acting on a green-but-dead organ → **W84**. Mitigate with node-guard + restart-intensity + content-probe before acting.
- **Metric + method:** auto-recovered silences / total silences; MTTR for recoverable organs (before: manual ~15–30min self-report; after: measured). Method: reconciler writes `~/.organism/reconcile_log.jsonl` with detect/act/resolve timestamps.
- **Kill criterion:** if any reconciler action correlates with a new scar within 7 days, disable the organ and revert to signaler-only.
- **First PR:** `scripts/organ_reconciler.py` handling only `launchctl_kickstart` for `severity_on_silence: warning` organs, dry-run mode default-on (≤400 lines).

### R3 — Closed-loop MTTR ledger (measure the healer, don't self-report)
- **What:** give the healer and reconciler an **incident object** `{family, detected_ts, acted_ts, resolved_ts, cure_pr, outcome}` and emit a weekly MTTR/MTTD digest per scar family. Replace `SLO.md`'s "~15–30min" with a measured number.
- **Why it beats SOTA:** SRE measures MTTR but not *per scar family, attributed to autonomous cures*. The organism can prove "this specific autonomous cure closed this specific measured failure" — no surveyed system does that loop.
- **Cost:** gear 1 (pure aggregation) for the ledger; gear 2 for healer attribution.
- **Gear:** 1–2.
- **Risk + scar family:** a cure that *looks* resolved but isn't → **#2** (Esiste≠Armato). Require the same prove-live gate the healer already uses.
- **Metric + method:** measured MTTR per family vs the SLO target; healer-attributed cure count/month. Method: `jq` over the incident ledger.
- **Kill criterion:** if attributed cures cannot be distinguished from manual fixes after 30 days, the ledger isn't earning its keep — fold it into the existing escalations board.
- **First PR:** `scripts/incident_mttr_report.py` reading healer heartbeat sidecars + escalations rows (≤400 lines).

### R4 — Burn-rate alerting to kill the alarm/cure dead-zone class for good
- **What:** migrate fixed-threshold alerts (the log-size 1MB-vs-10MB class) to **multi-window burn-rate** alerts derived from one SLO budget, so an alert can only fire when a cure exists and is below the cure line.
- **Why it beats SOTA:** applies Google's burn-rate model to a *solo-operator Mac fleet*, and specifically encodes the organism's hard-won insight that an alarm must name a condition some organ will act on (`alarm-cure-alignment.yml`).
- **Cost:** gear 1.
- **Gear:** 1.
- **Risk + scar family:** under-matching → **#3** (burn-rate too lenient). Ship guilt+innocence fixtures.
- **Metric + method:** non-actionable Telegram share (before: 34.6%; after: <5%). Method: parse `tg_spool/log-only.jsonl` + digest footer.
- **Kill criterion:** if burn-rate alerts miss a real incident that the old threshold caught, restore the threshold and widen the window.
- **First PR:** generalize `test_log_watchdog_dead_zone.py` into a `burn_rate.py` helper used by the watchdog (≤400 lines).

### R5 — Runtime chaos drills for non-prod organs (prove MTTD, don't assume it)
- **What:** a scheduled, operator-gated fault injector that kills/silences one *non-prod* organ and asserts the watcher fires within its `expected_hb_seconds`+tolerance. Records pass/fail per organ.
- **Why it beats SOTA:** Netflix injects faults at infra scale; the organism can do it at launchd scale with *scar-conditioned expectations* (assert the *specific* superscar detector fires). Guilt/innocence tests exist statically; this makes them runtime.
- **Cost:** gear 2; must be gated (`needs-ruling` for anything touching prod fly machines — see §7).
- **Gear:** 2.
- **Risk + scar family:** network flap → **#8**; accidentally hitting prod → **W84** green-lie if the drill itself looks healthy. Hard-scope to local non-prod labels.
- **Metric + method:** MTTD under injected fault per organ; % of organs with a passed drill (before: 0; after: rising). Method: drill writes `~/.organism/chaos/<organ>.json`.
- **Kill criterion:** first drill that fails to fire a watcher is itself a finding — if the *drill* is flaky twice, stop and fix the detector first.
- **First PR:** `scripts/chaos_drill.py` with a single safe target (a `warning` cron organ), dry-run default (≤400 lines).

### R6 — Ledger sharding/index for the PENDING-ARMS readability cliff
- **What:** keep `PENDING-ARMS.md` as SSOT but generate a **machine index + monthly shards** (open/closed, by owner-class, by age) so the receptor and humans query, never scroll. The parser already handles 1080 rows (positional guard removed); human navigation is the cliff.
- **Why it beats SOTA:** turns a markdown ledger into a queryable receptor without abandoning the single-file forcing function.
- **Cost:** gear 1.
- **Gear:** 1.
- **Risk + scar family:** HOME-fork drift → **#1** if index copies diverge; keep index derived/regenerated, never hand-edited.
- **Metric + method:** time-to-find-an-item; receptor parse time (before: grep-only at 2.2MB; after: O(1) index). Method: `time python3 scripts/pending_arms_report.py --json`.
- **Kill criterion:** if the index ever disagrees with `pending_arms_report.py --strict`, delete the index and regenerate.
- **First PR:** `scripts/pending_arms_index.py` emitting `.claude/skills/modus/PENDING-ARMS.index.json` (≤400 lines).

---

## 6. 90-day roadmap + first PRs

**Wave 1 (days 0–30): measure the cure leg.**
- Ship R3 incident-MTTR ledger (gear 1) → get a real MTTR number.
- Ship R6 ledger index → defuse the 1080-row cliff.
- Fill `docs/observability/README.md`'s TBD baseline table with one real week of chain metrics; reconcile `SLO.md` Qdrant entry against `organs_registry.yaml`.

**Wave 2 (days 31–60): make recovery executable + burn-rate.**
- Ship R2 reconciler in dry-run → then enable for `warning`-only organs.
- Ship R4 burn-rate helper; migrate the log-size watchdog.

**Wave 3 (days 61–90): prove it under fire.**
- Ship R5 chaos drills for non-prod organs (operator-gated).
- Ship R1 scar-detector coverage gate; target 100% of superscar families armed.

**First PRs (each ≤400 net lines, one concern):**
| PR | Files | Gear | Acceptance test |
|---|---|---|---|
| `incident_mttr_report.py` | `scripts/incident_mttr_report.py`, test | 1 | Reads ≥1 healer heartbeat + ≥1 escalation row, emits MTTR; empty-input → exit 2 (fail-visible, W84). |
| `pending_arms_index.py` | `scripts/pending_arms_index.py`, test | 1 | Index row-count == `grep -c '^- open'`; `--strict` agreement is the guilt test. |
| `organ_reconciler.py` (dry-run) | `scripts/organ_reconciler.py`, test | 2 | Dry-run names the correct `recovery_action` for a synthetic stale organ; refuses `human_only` + unknown actions. |
| `burn_rate.py` | `scripts/burn_rate.py`, extend `test_log_watchdog_dead_zone.py` | 1 | No alert fires when alarm-line ≥ cure-line (dead-zone guilt test). |
| `chaos_drill.py` | `scripts/chaos_drill.py`, test | 2 | Kills one safe organ, asserts watcher fires within tolerance; refuses prod labels. |
| `scar_detector_coverage.py` | `scripts/scar_detector_coverage.py`, `immune-enforcement.yml` | 2 | Fails if any superscar family lacks a `detector:` pointer. |

**File-write / anti-hallucination probe:** this lane returned content in the final message (no file write). Had it written `research/operations/2026-08-28-beyond-sota-observability-immune-self-healing.md`, the verification would be: `ls -la research/operations/2026-08-28-beyond-sota-observability-immune-self-healing.md && wc -w research/operations/2026-08-28-beyond-sota-observability-immune-self-healing.md` — **UNMEASURED** (no shell). Estimated word count: ~4,300.

---

## 7. Needs-ruling (Legge-5 business / consents / credentials / GUI / physical)

1. **Actuation on remote/prod machines.** R2/R5 touching Fly machines or remote Pro/Mini is control-plane + business. The healer perimeter explicitly excludes remote writes. **needs-ruling:** may the reconciler ever act on `fly_machines_start` (prod), and may chaos drills touch prod at all?
2. **Sentry quota / observability spend.** Fixing the 28% drop by raising quota or adding a paid backend (Grafana Cloud/Datadog) costs money against the $40–60/mo budget (`SLO.md`). **needs-ruling** (business). The no-cost path is R4/local buffering.
3. **TCC grants** for launchd jobs on macOS (W84 class) are per-principal, operator-only. **needs-ruling** (tcc).
4. **PENDING-ARMS SSOT format change** (R6 sharding) touches the modus ledger doctrine — confirm the single-file forcing function must be preserved before sharding.

---

## 8. §Meta-pattern (modus Gear 3)

Across every finding — HOME-fork drift, Esiste≠Armato, KeepAlive restart storms, W84 green-lies, W55 delta-suppression, the alarm/cure dead-zone, the arsenal probe hang, the stale-measurer (W106b) — the **single defective belief** is identical:

> **"A green signal is the thing. Absence of alarm is presence of health."**

Every trauma is a case of trusting a *proxy* (an exit code, an mtime, a `KeepAlive=true` flag, a `loaded` bit, a single Telegram, a 6.7h-fresh report) as truth for a reality on the other side of a boundary, with nothing probing across. And every cure the organism has already built is one move in the same direction: **make silence prove itself.** Proprioception's "absence is visible, never silent," the heartbeat's "liveness proven by the organ itself, every run," the tg-flusher's "healthy-silence must be provable," the sentinel's mutual watch, W104's "judge the reply, not the timeout," W88's "content compare, never proxy" — these are all the *same* doctrine discovered independently each time the organism got burned.

The beyond-SOTA frontier is therefore not a new sensor; it is **inverting the default everywhere**: health is not the absence of alarm, health is a continuously-proven, content-compared, dead-man-switched claim — and the cure leg must be held to the same standard the sense leg already is. The organism's sense side is beyond-SOTA precisely because it stopped believing green; the cure side will be beyond-SOTA the moment it stops *self-reporting* and starts *proving* (measured MTTR, executable recovery, chaos-proven MTTD).

---

## 9. Sources

1. Google SRE Book — "Monitoring Distributed Systems." https://sre.google/sre-book/monitoring-distributed-systems/ · accessed 2026-08-28 · authoritative: defines the golden signals + "automate monitoring, humans for judgment."
2. Google SRE Book — "Service Level Objectives." https://sre.google/sre-book/service-level-objectives/ · accessed 2026-08-28 · authoritative: SLO-as-contract + error budget gating.
3. Google SRE Workbook — "Alerting on SLOs." https://sre.google/workbook/alerting-on-slos/ · accessed 2026-08-28 · authoritative: multi-window burn-rate alerting (basis of R4).
4. Kubernetes — "Controllers." https://kubernetes.io/docs/concepts/architecture/controller/ · accessed 2026-08-28 · authoritative: declarative desired-state + reconciliation loop (basis of R2).
5. Erlang/OTP — "Supervisor Behaviour." https://www.erlang.org/doc/design_principles/sup_princ.html · accessed 2026-08-28 · authoritative: let-it-crash + bounded restart intensity (W67/W60 model).
6. systemd.service — `WatchdogSec`/`sd_notify`. https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html · accessed 2026-08-28 · authoritative: prove-liveness-by-ping watchdog pattern.
7. healthchecks.io. https://healthchecks.io/ · accessed 2026-08-28 · authoritative: dead-man-switch / alert-on-absence.
8. OpenTelemetry — "Signals." https://opentelemetry.io/docs/concepts/signals/ · accessed 2026-08-28 · authoritative: unified telemetry model (the breadth gap).
9. Netflix Chaos Monkey. https://github.com/Netflix/chaosmonkey · accessed 2026-08-28 · authoritative: fault-injection-for-resilience lineage (basis of R5).
10. Google Borg (EuroSys 2015). https://research.google/pubs/large-scale-cluster-management-at-google-with-borg/ `(unverified)` · accessed 2026-08-28 · authoritative: auto-restart as a first-class scheduler property.
11. Meta Twine (OSDI 2020). https://www.usenix.org/conference/osdi20/presentation/talwar `(unverified)` · accessed 2026-08-28 · authoritative: cluster-wide automated remediation.
12. Grafana LGTM stack. https://grafana.com/oss/lgtm-stack/ · accessed 2026-08-28 · authoritative: self-hosted metrics/logs/traces stack the organism already partially runs.
13. PagerDuty AIOps. https://www.pagerduty.com/platform/aiops/ · accessed 2026-08-28 · authoritative: alert correlation/noise reduction (context for the tg-gateway).
14. Honeycomb — "Observability 2.0." https://www.honeycomb.io/blog/observability-2-0 `(unverified)` · accessed 2026-08-28 · authoritative: wide-events philosophy, here noted as *incompatible* with Legge 2 for CRM data.

---
status: complete
sections_done: [0,1,2,3,4,5,6,7,8,9]
---