---
date: 2026-08-28
domain: operations
part: X2 fleet-runtime-ops
scope: launchd/plist fleet, cascade wrappers, healer/fleet-watch self-monitoring, heartbeats/receptors, secrets slots, sync daemons, Tailscale mesh, local LLM serving on the 3-Mac fleet
sources:
  - https://healthchecks.io/docs/monitoring_cron_jobs/
  - https://healthchecks.io/docs/configuring_checks/
  - https://runbooks.prometheus-operator.dev/runbooks/general/watchdog/
  - https://github.com/gouthamve/deadman
  - https://github.com/nix-darwin/nix-darwin
  - https://bullo.sk/blog/nix-darwin-multi-host-setup/
  - https://docs.temporal.io/workflow-execution
  - https://temporal.io/blog/temporal-replaces-state-machines-for-distributed-applications
  - https://blog.gitguardian.com/a-comprehensive-guide-to-sops/
  - https://tvi.al/commit-your-secrets-to-git-encrypted-with-sops-and-age/
  - https://tailscale.com/kb/1467/grants-vs-acls
  - https://tailscale.com/docs/features/access-control/acls
  - https://uptimepage.dev/compare/uptime-kuma-vs-gatus
  - https://betterstack.com/community/comparisons/uptime-kuma-alternative/
  - https://oneuptime.com/blog/post/2026-02-21-ansible-pull-mode-decentralized-automation/view
  - https://victoriametrics.com/blog/comparing-agents-for-scraping/
  - https://selfhosting.sh/compare/nomad-vs-kubernetes/
  - https://www.windmill.dev/docs/compared_to/peers
  - https://kestra.io/resources/infrastructure/temporal-alternatives
status: DONE 2026-08-29
adversarial_review: kimi-k3
---

> ## ⚠️ Read this before acting on anything below
>
> **These findings are pinned to `11a3c89a2e` (2026-08-28). `origin/main` was 123 commits ahead
> when this file was published on 2026-08-30.** A verdict in here is a **LEAD, not a fact**: it
> was true of a tree that no longer exists. Re-measure before you build on it.
>
> **Defects presented below as current that were already CURED before publication** — each fix
> verified as a descendant of the pin with `git merge-base --is-ancestor 11a3c89a2e <sha>`:
>
> | Presented as a live defect | Actually cured by | Verified |
> |---|---|---|
> | R9 harness time-bomb dated 2026-09-02 (X1) | #5190 | ancestor check |
> | Phantom DeepSeek voter (B8) | #5211 / #5207 (`cc82ed62e4`, `0cccbbc925`) | ancestor check |
> | Auth split-brain across the portals (F3, F4) | #5181 (`d6556a75bf`) | ancestor check |
> | Magic-link `result_id` ownership — which F2 calls "replay-safe" (F2) | #5298 (`3861567e52`) | ancestor check |
> | Meta webhook signature unenforced in prod (B3) | fail-closed by default since 2026-08-26; `WHATSAPP_APP_SECRET` deployed | live probe: unsigned `POST /webhook/whatsapp` → **401 `Invalid signature`** (2026-08-30) |
>
> **Counts that were re-measured and found WRONG** (they were not corrected in the text, so that
> the reports stay the artefact the panel actually produced rather than a quietly-improved one):
> `X3:31` reads 10 directories + 6 symlinks, measured 11 + 5. `X3:45` reads 162 `@mcp.tool`,
> measured 153. Other counts flagged by the review but NOT settled either way are listed in this
> PR's evidence pack under `dissent`, marked PLAUSIBLE — treat every number in these files as
> unverified unless you have just re-run it.
>
> **Known internal contradiction, left standing:** `B4` states that OCR of identity documents
> never leaves the machine, and then, two paragraphs later, that OCR'd passport/NPWP/akta text is
> shipped to Gemini by CRM-Guardian. The second statement is the accurate one. It is ledgered.
>
> **Two things were withheld from this publication rather than edited quietly:** the panel's own
> mandate file (self-labelled `IN-PROGRESS` / `internal`), and the location of a live DNS-write
> credential named in `B5`. Both omissions are declared here because a silently-sanitised audit is
> worth less than an audit that says what it removed.
>
> The reports' own thesis is that a written artefact gets presumed to be in force. This header
> exists because that thesis applies, first, to the reports themselves.


# X2 — Fleet Runtime Ops: the physical fleet vs. the world's best

## Anatomy (as measured)

All claims measured on the pinned worktree (`origin/main` @ `11a3c89a2e`) with Read/Grep/Glob only. No launchctl, no secrets opened.

**Daemon inventory.** The repo tracks **156 plists in `infra/launchagents/`**, 1 in `infra/launchagents/mini/` (`com.nuzantara.fw-guard.plist`), and 3 in `infra/launchd/` — ~160 canonical launchd jobs, against **170 organs declared in `apps/organism/organism/organs_registry.yaml`**. Naming encodes lineage, not machine: 74 `com.nuzantara.*`, 56 `com.balizero.*`, 26 `com.matagaruda.*`. Scheduling split: 73 plists use `StartInterval`, 68 `StartCalendarInterval`, and 76 carry a `KeepAlive` key. 51 wrapper scripts live in `infra/launchagents/wrappers/`; 8 of them route their LLM work through `claude-cascade.sh`.

**The cascade wrapper** (`infra/launchagents/wrappers/claude-cascade.sh`, 895 lines) is the single entry point for autonomous LLM invocations and the most heavily engineered artifact in the fleet. Tier order: 5 explicit Claude OAuth seats + legacy token + keychain (`claude-cascade.sh:802-861`), then Gemini `agy`, Kimi K3, Codex (with per-seat rotation and a separate `gpt-5.3-codex-spark` weekly bucket retry, `:625-648`), Ollama `qwen3.5:9b`, and Apple's on-device `fm` as tier 6 zero-daemon last resort (`:739-775`). Notable engineering: per-attempt process-group watchdogs via `os.setsid` + `killpg` because macOS has no guaranteed `timeout(1)` (`:268-341`); per-provider env isolation so no provider's credential reaches another's process (`:243-261`); scrubbing of Anthropic paid-API/Bedrock/Vertex vars *after* sourcing secrets (`:91-113`); and a "lying success" classifier that treats an exit-0 stdout as retryable only when the whole payload matches a known error-envelope shape (`:187-222`) — a direct answer to scar W104/W89 ("green ≠ working").

**Secrets discipline.** Runtime secrets live in `~/.nuzantara-secrets.env` (0600), sourced with `set -a` by the cascade (`claude-cascade.sh:108-112`) and the healer (`healer-run.sh:110`). `scripts/secrets_permissions_audit.py` is the superscar-#4 auditor: it inspects **permission bits only via `os.lstat()`, never file contents** (its header states the invariant: an audit tool for secrets must not become an exfiltration path), covers backup-suffix inheritance (`.bak`, `.orig`, `~`), and exits 2 when a scan is *blind* (roots exist, zero files traversed — TCC denial), refusing to certify "clean" (`secrets_permissions_audit.py:23-29`). A second, unusual credential control: `infra/llm-credentials/declared.json` is an allowlist of sha256-hashed credential UIDs permitted to make billable Gemini calls, born 2026-08-12 when a dev key made 5,344 billable calls invisible to every repo-side cost check and silenced the production WhatsApp bot — the file's own comment records the incident and designates Google Cloud Monitoring as the independent observer.

**Self-monitoring stack** (four layers, each born from a named failure):
1. **Heartbeat sidecars** — organs write `~/.organism/last_seen/<id>.json` on success *and* failure paths (gene G2). Long-running eventbus daemons additionally beat into Redis (`bz:heartbeat:<daemon>`, TTL 120s, `infra/eventbus/heartbeat.py:22-38`) — though `is_alive()` **fails open** (returns True when Redis is down, `heartbeat.py:43-48`).
2. **`scripts/launchd_liveness_detector.py`** — cross-references launchd exit codes against actual log content to catch "green-but-TCC-dead" (W84); its own wrapper records that the detector existed for weeks with 4 test suites *and nothing scheduling it* (`launchd-liveness-detector.sh:5-11`) — superscar #2 applied to the sensor itself.
3. **`scripts/fleet_watch.py`** — mutual cross-node watch (Pro↔Mini per `infra/fleet-watch/peers.json`), two structured signals (Tailscale `status --json` `Online` bool + BatchMode ssh probe), DARK only when both explicitly fail, **exit 4 if no probe machinery ran** ("a blind sentinel must not report green", `fleet_watch.py:10-15`). Its re-alert ladder (30min → 6h → 24h → daily, per-stage dedup keys) encodes the 2026-08-17 lesson: one alert then 65h of silence made a three-day-dead node indistinguishable from a recovered one (`fleet_watch.py:17-30`).
4. **The healer** (`infra/healer/healer-run.sh`, 552 lines, Mini, every 4h) — deterministic pre-check over three receptors (proprioception report, PENDING-ARMS ledger, escalations board); only if something is actionable does it spawn a headless claude with a standing mandate; healthy-idle runs cost zero tokens (`healer-run.sh:4-10`). Rails: kill switch, pidfile anti-overlap, `HEALER_RUN=1` anti-recursion, wall-clock hard kill, W84 ssh-localhost trampoline for TCC-denied launchd contexts, and a heartbeat *from the healer itself* ("Esiste≠Armato applies to healers", `:18-21`).

**Reconciliation organs.** `scripts/proprioception.py` (1,424 lines) is "the reconciler of reconcilers": 14 named boundary classes (`home<->repo`, `canon<->installed`, `seat<->armed`, `tunnel<->reachable`, … `proprioception.py:63-78`), with anti-calm-liar contracts — the report stamps its own provenance (runner version, config sha, repo HEAD, expected-vs-actual probe count); unprobeable ≠ reconciled; boundary classes with no probe are listed UNWATCHED; exit 0 means "the organ worked", never "all is well" (`:16-24`). Declared limitation: **v1 has no cron** — with no session, there is no alarm (`:25-26`). `scripts/lint_home_fork.py` is the superscar-#1 antidote: sha256 comparison across **167 declared live↔repo pairs** (`infra/home-fork/declared-pairs.json`, per-machine scoped) plus a `--discover` arm that parses live plists and `crontab -l` for undeclared HOME-rooted payloads; bitmask exit, 4 = "a scan that cannot see is NOT clean". `scripts/lint_plist_keepalive.py` is the superscar-#7 antidote with a documented innocence carve-out (fd-redirect `exec 9>lock` is not process-replacing exec) and the rule "every FAIL class ships with an innocence test".

**Alert plane.** `scripts/tg_notify.py` is the single Telegram gate (born from "non posso più ricevere 600 messaggi al giorno"): three tiers (p0 / digest / log), a semantic dedup key (first sentence with numbers stripped, so a condition that only moved a counter is the *same* condition), a widening repeat ladder that makes persisting conditions quieter without hiding magnitude, a daily P0 budget with meta-P0 overflow, and a token chain ending in spool-only — it never fails its caller. `infra/tg-gateway/grandfathered.json` freezes the direct-Bot-API senders at gateway birth; the list only shrinks, CI-enforced.

**Organ genome.** `infra/organ-conformance/genes.json` defines 10 genes every organ must inherit at birth — G1 registry entry, G2 heartbeat, G3 declared HOME pair, G4 node guard, G5 kill switch, G6 hardened spawn, G7 ledger line, G8 KeepAlive sanity, G9 fail-visible, G10 single-instance — enforced by `check_organ_conformance.py` as a CI regression gate with a shrink-only baseline. **135 plists are grandfathered** (known-missing genes recorded at gate birth), i.e. ~84% of the fleet predates its own constitution.

**Mesh and sync.** `infra/tailscale/policy.hujson` is a fully drafted deny-by-default ACL with tagged team devices and a `tests` block — **header status: PROPOSED, not applied**. The same header records what was measured live 2026-08-11: the tailnet runs default allow-all, and `tailscale serve` on Pro published a **tailnet-wide, unauthenticated, writable ttyd zsh shell** (`-W`, no credential flag) on the machine holding raw PII and the secrets file; plus a latent passwordless-root Tailscale-SSH grant, currently unarmed. Applying the policy is `operator[GUI]` because the fleet deliberately holds no Tailscale API token. Memory sync (`infra/sync-daemons/memory-sync-bidirectional.sh`) is hub-and-spoke (hub=Pro, spokes Mini+M5), rsync-based, lock-guarded, fail-soft per spoke, with a conflict quarantine dir; comment says cron `*/5` (live arming not verifiable from this worktree — unverified).

**Seat quota.** `scripts/claude_seat_quota.py` reads the real endpoint (`GET /api/oauth/usage`) and documents two measured constraints: long-lived cron tokens get 403 (no `user:profile` scope) so quota is readable only per interactive Keychain profile — on this fleet, only Pro; and the Keychain access token staleness (~1h) requires warming each profile first. Pro publishes a report; readers refuse one older than 90 min with exit 2 — "a cached report that outlives its truth is the same disease as the watcher this file replaced".

## Honest state vs. SOTA

**Genuinely good — in places beyond what the industry ships:**
- **Scar-derived executable lints.** The failure taxonomy (10 superscar families) is not documentation: 5+ of the families have *executable antidotes* wired into CI (`lint_home_fork.py`, `lint_plist_keepalive.py`, `secrets_permissions_audit.py`, `pending_arms_report.py`, guard-conformance). Mainstream SRE has postmortems and runbooks; almost nobody compiles postmortems into lint rules with guilt+innocence test pairs. This is the system's most exportable idea.
- **Fail-visible epistemics.** The consistent contract — exit 2/4 for "I could not see", UNPROBEABLE ≠ RECONCILED, blind scan ≠ clean, empty report impossible by construction — is a discipline most monitoring stacks lack (a Prometheus scrape failure is famously easy to alert-miss).
- **The alert-plane design.** Semantic dedup + widening repeat ladder + budget-with-meta-overflow in `tg_notify.py`, and per-stage re-alert dedup in `fleet_watch.py`, are textbook-quality alert-fatigue engineering, derived from lived incidents rather than copied.
- **The cascade's failure-mode realism.** Classifying exit-0 stdout as error-envelope, per-provider env isolation, process-group kill discipline — this is more careful than most published LLM-router code.

**Theater or unarmed (the system's own disease, esiste≠armato, applied to itself):**
- **The Tailscale ACL is a drafted constitution that does not govern.** The live tailnet is allow-all with a measured unauthenticated writable shell on the PII machine. The mitigating fact: all six nodes are Zero's own devices. The aggravating fact: the tailnet-expansion plan (team devices) exists, and join-then-restrict leaves a window the file's own header calls out.
- **84% of the fleet is grandfathered against its own genome** (135/~160 plists). The genome gate prevents *regression* but the conversion rate — the shrink of the baseline — is the real cure metric, and it is the number nobody is paid to move.
- **Proprioception has no cron by design (v1)** — the deepest reconciler runs only when a session runs. On a machine that stops opening sessions, the reconciler-of-reconcilers is mute exactly when needed. (Accepted and recorded in PENDING-ARMS — honest, but still a hole.)
- **Quota observability is single-homed on Pro** (interactive Keychain profiles); Mini and M5 hold six cron tokens and can measure nothing. The publish/read pattern mitigates but the measuring node is also the node with the most history of going dark.
- **Redis heartbeat `is_alive()` fails open** (`heartbeat.py:43-48`): when Redis itself dies, every eventbus daemon reads as alive — a guardian that dies with its patient, family #2's exact signature, one layer down.
- **No off-fleet observer exists at all.** Every alarm path (Telegram gateway, fleet_watch, healer) originates *on* the fleet. Site-wide power/ISP loss in Bali = total silence, indistinguishable from "nothing to report". Law 6 says disconnection is a natural state, not a fault — but "natural state" and "unobserved state" are different things; today Zero cannot tell them apart from Milan or from his phone.

## Deep research: the world's best

**1. Dead-man's-switch monitoring (Healthchecks.io / Prometheus Watchdog).** The sector's canonical answer to "green cron, dead worker" is inversion: never watch for failure signals, *require* success signals, and let an observer *outside the blast radius* alarm on their absence. Healthchecks.io's contract per check: a Period (expected interval), a Grace Time (a little above expected duration), success ping via `curl -fsS -m 10 --retry 5 https://hc-ping.com/<uuid>` chained with `&&`, plus optional `/start` (measures runtime), `/fail`, and `/<exit-status>` endpoints with logs in the POST body ([docs](https://healthchecks.io/docs/monitoring_cron_jobs/)). It is open-source and self-hostable. The complementary pattern from the Prometheus world is the **Watchdog / always-firing alert**: an alert on `vector(1)` fires forever, routed to an external service (Dead Man's Snitch, PagerDuty DMS integration) that pages when the heartbeat *stops* — testing the entire alerting pipeline end-to-end, continuously ([kube-prometheus Watchdog runbook](https://runbooks.prometheus-operator.dev/runbooks/general/watchdog/); [gouthamve/deadman](https://github.com/gouthamve/deadman)). The load-bearing idea for Nuzantara: the fleet already implements the *internal* half of this (heartbeat sidecars, fleet_watch mutual probes) with unusual rigor, but the recursion of guardians terminates on-fleet — the sector's answer is that at least one expectation-holder must live off the failure domain.

**2. Declarative fleet state (nix-darwin, ansible-pull).** The drift problem Nuzantara attacks with a 167-pair sha256 lint is solved *by construction* elsewhere. [nix-darwin](https://github.com/nix-darwin/nix-darwin) manages macOS declaratively the way NixOS manages systemd units — including first-class `launchd.user.agents` / `launchd.daemons` generation: the installed plist is a build artifact of the repo, so a live/canon divergence is not detected, it is impossible; one flake can describe all three machines and a new machine is a rebuild, not a runbook ([multi-host flake write-up](https://bullo.sk/blog/nix-darwin-multi-host-setup/)). The lighter-weight relative is **ansible-pull**: each node runs a cron that pulls the repo and converges itself — no central controller at runtime (control node down ≠ fleet unmanaged), minimal agent (git + cron + interpreter), bootstrap-once ([pull-mode guide](https://oneuptime.com/blog/post/2026-02-21-ansible-pull-mode-decentralized-automation/view)). Pull-mode convergence is philosophically identical to Law 6: each machine owns its own state, the network is optional.

**3. Durable execution (Temporal; Windmill/Inngest as the small-scale tier).** Temporal's contribution is architectural, not a product detail: split code into deterministic workflow + non-deterministic activities, persist an **event history** of every step, and on any crash *replay* the workflow — completed activities are skipped, their recorded results returned, so a process death anywhere resumes exactly where it stopped ([workflow-execution docs](https://docs.temporal.io/workflow-execution); [Temporal blog](https://temporal.io/blog/temporal-replaces-state-machines-for-distributed-applications)). Retry policy is declared, not hand-rolled. The full server is oversized for three Macs, but the tier below fits: [Windmill](https://www.windmill.dev/docs/compared_to/peers) (self-hosted, Postgres-only, turns Python/TS/Bash scripts into scheduled flows with per-step retry and a run history UI) and Inngest (durable steps/sleeps/retries without a full orchestration platform) are explicitly positioned for small teams ([Temporal-alternatives survey](https://kestra.io/resources/infrastructure/temporal-alternatives)). The exportable idea even without adopting any engine: **a step journal with idempotency keys turns a killed multi-step job into a resumable one**.

**4. Secrets for small fleets (sops + age).** The sector norm for a git-centered solo/small operation: secrets live *in the repo, encrypted*, via sops with age keys — structure-preserving YAML/env encryption, multiple recipients so each machine (and CI) decrypts with its own key, private keys never in git, rotation is a commit with history ([GitGuardian sops guide](https://blog.gitguardian.com/a-comprehensive-guide-to-sops/); [sops+age walkthrough](https://tvi.al/commit-your-secrets-to-git-encrypted-with-sops-and-age/)). No cloud KMS required. Contrast with Nuzantara today: one plaintext 0600 file per machine, whose *content map is documentary* (the 6-seat token↔account mapping is explicitly non-remeasurable) and whose only git presence is the audit script that checks its permission bits.

**5. Network policy as code (Tailscale grants).** Tailscale's own guidance: the default allow-all policy is for day one; production tailnets move to **deny-by-default grants** with tagged (tailnet-owned, not user-owned) nodes for servers, and policy tests validated at save time ([grants vs ACLs](https://tailscale.com/kb/1467/grants-vs-acls); [ACL docs](https://tailscale.com/docs/features/access-control/acls)). Nuzantara's `policy.hujson` is already written in exactly this idiom (tagged team devices, tests block) — the gap is purely that it is not applied.

**6. On-prem observability at homelab scale (Gatus, VictoriaMetrics).** Two sector patterns matter here. First, **monitoring-as-code**: [Gatus](https://uptimepage.dev/compare/uptime-kuma-vs-gatus) is a single Go binary whose every endpoint/alert is YAML in version control (read-only web UI) — the correct shape for an operator who reviews everything as diffs, vs Uptime Kuma's click-configured dashboard ([Better Stack comparison](https://betterstack.com/community/comparisons/uptime-kuma-alternative/)). Second, **lightweight metrics**: VictoriaMetrics is a Prometheus-compatible single binary at roughly 1/8th the memory per series, with vmagent as a minimal scraper ([agent comparison](https://victoriametrics.com/blog/comparing-agents-for-scraping/)) — the point at which "how often did the cascade fall past tier 1 this month" stops being a grep and becomes a query.

**7. Orchestrators at small scale (Nomad/k3s) — the negative result.** The survey verdict for 3-node fleets: k3s wins on ecosystem, Nomad on simplicity (single binary, mixed workloads) ([selfhosting.sh comparison](https://selfhosting.sh/compare/nomad-vs-kubernetes/)) — but both assume Linux-first containerized workloads. This fleet's workloads are macOS-native by necessity (TCC-gated GUI surfaces, Keychain-bound OAuth profiles, Ollama on Apple Silicon, local PII sovereignty). Container orchestration would fight the platform and add a control plane where launchd + lints already work. **Adopting Nomad/k3s is anti-recommended**; the SOTA to import is their *ideas* (declared desired state, one scheduler config format, job specs as artifacts), which nix-darwin/pull-converge deliver natively on macOS.

## Gap table

| Dimension | Nuzantara today (measured) | Sector SOTA | Gap |
|---|---|---|---|
| Failure detection epistemics | Fail-visible exit contracts (2/4 = "could not see"); UNPROBEABLE ≠ RECONCILED | Rarely explicit anywhere | **Nuzantara leads** |
| Postmortem → control | Scar families compiled into CI lints with guilt+innocence tests | Postmortems + runbooks, rarely executable | **Nuzantara leads** |
| Alert fatigue engineering | Semantic dedup, widening ladders, P0 budget + meta-P0 (`tg_notify.py`) | Alertmanager grouping/inhibition | **Nuzantara leads** (bespoke but stronger) |
| Dead-man topology | All expectation-holders on-fleet; site-dark = silence | Off-domain observer (Healthchecks/DMS Watchdog) | **P0 gap** |
| Network policy | Drafted deny-by-default ACL, live tailnet allow-all + unauthenticated writable ttyd measured | Deny-by-default grants, tagged nodes, applied | **P0 gap** (apply = operator[GUI]) |
| Drift control | Detective (sha256 lint over 167 declared pairs, --discover arm) | Preventive (generated state: nix-darwin / pull-converge) | P1 |
| Secrets at rest | Plaintext 0600 env file ×3 machines, permission auditor, documentary seat map | sops+age: encrypted in git, per-machine keys, rotation history | P1 |
| Durable multi-step jobs | Fire-and-forget one-shots + hand-rolled retry per wrapper; cascade is the one shared retry engine | Event-history replay (Temporal); step journals (Windmill tier) | P1 (import the journal idea, not the engine) |
| Genome enforcement | 10 genes, CI regression gate, ratchet script — but 135/~160 plists grandfathered | N/A (no sector equivalent) — but "constitution ≠ coverage" | P1 (move the baseline) |
| Metrics/trends | JSON sidecars + logs + 1 Grafana JSON (no TSDB); trends = grep | VictoriaMetrics single binary + textfile-style export | P2 |
| Redis heartbeat semantics | `is_alive()` fail-open when Redis down (`heartbeat.py:43-48`) | Three-state (alive/dead/UNKNOWN) + absent() alerting | P1 (small fix) |
| Orchestration substrate | launchd + plists + wrappers | Nomad/k3s at small scale | **No gap — keep launchd** (anti-recommendation) |

## Recommendations — reach SOTA

**R1 — Off-fleet dead-man's switch (P0).** Stand up one expectation-holder outside the Bali failure domain. Cheapest sovereignty-compatible shape: the fleet already pays for an always-on Fly app (`nuzantara-rag`); add a tiny staleness-checker there (or a self-hosted Healthchecks instance) that receives pings from `tg_digest_flush` / `fleet_watch` runs and sends Telegram *from Fly* when they stop. Only check names travel off-site — zero PII, and Law 6 is respected because the observer holds *expectations*, not data or control. Critically, it distinguishes "site dark" (one meta-alarm, natural state) from "one cron dead" (per-check alarm). *Acceptance metric (falsifiable): power off Pro and Mini for 45 minutes → exactly one Telegram alert arrives, sent from off-fleet, within 15 minutes of the missed window; restore → recovery notice.*

**R2 — Apply the Tailscale policy; kill or authenticate the ttyd serve (P0).** The file is written, tested-in-syntax, and its own header proves the risk (unauthenticated writable zsh on the PII machine, tailnet-wide). Application is `operator[GUI]` (see §Solo-operatore); the session-side half is: remove or credential the `tailscale serve /term` publication now, before any team-device conversation resumes. *Acceptance: `tailscale debug netmap` from M5 shows a packet filter with more than one rule; `GET /term` from a non-Pro node stops answering 200.*

**R3 — Make the Redis heartbeat fail-visible (P1).** `is_alive()` returning True on RedisError inverts the fleet's own W104 doctrine one layer down. Return a three-state verdict; the daemon-watchdog treats UNKNOWN persisting past a grace window as an alarm (the `absent()` idiom). *Acceptance: stop Redis for 10 minutes → a p0/digest event names "heartbeat plane unprobeable", instead of every daemon reading alive.*

**R4 — Pull-mode converge loop for the launchd fleet (P1).** Today `lint_home_fork.py` *detects* what an installer once copied; nothing re-converges. Add one idempotent `fleet_converge.py` (ansible-pull shape, no Ansible needed): render every canon plist+wrapper from the repo into `~/Library/LaunchAgents`/`~/scripts`, `cmp` first, bootstrap/kickstart only on change, refuse to run from a worktree, heartbeat sidecar, kill switch — i.e., an organ with all 10 genes whose job is making the other organs match canon. The 167-pair lint then becomes the *auditor of the converger* instead of the only line of defense. *Acceptance: hand-edit a live wrapper → within one converge period the edit is reverted (or quarantined + alarmed if dirty-by-a-sibling), and `lint_home_fork.py --check` stays at zero breaches for 30 days.*

**R5 — Secrets to sops+age (P1).** Encrypt `~/.nuzantara-secrets.env` content into the repo (`secrets/fleet.env.sops`), one age recipient per machine plus one offline recovery key; wrappers decrypt to a 0600 tmpfile or pipe at source-time. This converts three divergent plaintext files with a documentary seat-map into one versioned, diffable, recoverable artifact — the 2026-08-23 "three copies, three answers" class dies structurally. Key custody and the first re-encryption of live tokens are operator[secret]. *Acceptance: a fresh machine given only its age key reconstructs a working secrets file from git alone; `git log` shows the next token rotation as a commit.*

**R6 — Genome ratchet with a rate target (P1).** The mechanism exists (`check_organ_conformance.py --update-baseline`, shrink-only; `check_baseline_ratchet.py`); what is missing is a *rate*. Adopt: healer's idle branch cures ≥2 grandfathered plists/week (add missing genes, regenerate baseline). At the measured 135, that is ~15 months to full conformance — acceptable if the trend is CI-visible. *Acceptance: `genes.json` grandfathered count strictly decreases week-over-week for 8 consecutive weeks, plotted in the weekly digest.*

**R7 — Schedule proprioception (P1).** v1's "no cron — the receptor is the consumption point" was honest debt; on a machine that stops opening sessions the deepest reconciler is mute. One genome-conformant daily plist per machine running `proprioception.py --strict`, exit≠0 → tg digest. *Acceptance: three machines each show a `~/.nuzantara-proprioception/last.json` younger than 26h for 14 consecutive days, with zero sessions opened on at least one of them.*

**R8 — Cascade metrics (P2).** Emit one structured line per cascade invocation (tier used, tiers skipped, latency, prompt bytes) into a sidecar; a trivial exporter feeds VictoriaMetrics on Mini (single binary, ~100MB-class footprint) or, minimally, a weekly digest aggregation. The question this answers is a money question: how often the fleet silently degrades from Claude to Ollama-quality output. *Acceptance: "tier-fallthrough rate per week per wrapper" is a query, not a grep; one month of history exists.*

## Recommendations — beyond SOTA

**B1 — Guardian drills: chaos engineering for the alarm plane (P1).** The industry tests uptime; almost nobody tests *detection*. W108 (19/20 crons mute) proves alarms rot faster than daemons. Institutionalize a monthly drill: deliberately kill one randomly chosen canary organ (or suppress its heartbeat) and *measure* time-to-Telegram end-to-end; the drill runner asserts the alarm arrived and files a scar if not. This is the Watchdog pattern generalized from "is the pipeline up" to "does each detection layer actually fire". *Acceptance: 3 consecutive monthly drill reports each showing measured alarm latency < the layer's declared window; one drill deliberately run during a network flap.*

**B2 — Step journals for healer/LLM sessions: durable execution without the engine (P1).** Import Temporal's core idea into the headless-claude pattern: the healer mandate requires each cure step to append an idempotency-keyed line to a journal *before* acting; a restarted session reads the journal and skips completed steps. A killed 50-minute healer run today restarts from zero (or worse, half-repeats); with a journal it resumes. No new infrastructure — a JSONL file and a mandate clause. *Acceptance: kill a healer session mid-cure twice; the third run completes the cure with zero duplicated PRs/commits.*

**B3 — Organ birth as the only door (P2).** `organ_birth.py` + the genome already exist as generator + gate. Close the loop the nix-darwin way: CI rejects any new plist not generated by `organ_birth.py` (generator watermark), making G1-G10 compliance by construction and turning the grandfathered set into a closed, shrinking museum. *Acceptance: 6 months after adoption, zero hand-authored plists have entered `infra/launchagents/`.*

**B4 — Export the alert-plane library (P2).** `tg_notify.py`'s semantic dedup key + widening repeat ladder + budget-with-meta-overflow is genuinely ahead of Alertmanager's grouping model for single-operator use. Extract the ladder/dedup as a shared lib (gene candidate G11) so every future sentinel inherits it instead of reimplementing (fleet_watch already had to re-derive per-stage dedup independently — the same idea, written twice, is how the third copy diverges). *Acceptance: fleet_watch and tg_notify share one ladder implementation with one test suite; a new sentinel adopts it in <10 lines.*

**B5 — Scar-antidote coverage metric (P2).** The superscar doc names 10 families; 5-6 have executable antidotes. Publish a per-family coverage number (families × {lint, drill, none}) in the weekly digest and treat a new scar in an antidote-less family as pressure to write the lint, not just the memory line. The compiler-from-postmortems is this system's most original asset; measuring its coverage keeps it honest. *Acceptance: coverage table exists in CI output; ≥8/10 families have an executable antidote or a dated declared-no-antidote line within a quarter.*

## §Meta-pattern

The dominant disease of this part, measured repeatedly: **the constitution precedes the enforcement, and the gap between them is invisible from inside.** The Tailscale ACL is drafted but the live mesh is allow-all; the genome exists but 84% of organs are grandfathered; the liveness detector had four test suites and no scheduler; proprioception — the reconciler-of-reconcilers — has no cron. The organism's own doctrine names this (esiste≠armato) and is world-class at *detecting* the gap after the fact; the sector's strongest answer is to make the gap *unconstructible* — generated state instead of audited state, deny-by-default instead of drafted policy, generator-as-only-door instead of gate-plus-grandfathering. Every P1 above is the same move in a different organ: shift enforcement left, from detection-time to construction-time. The second, subtler pattern: **the guardian recursion terminates on-fleet.** Guardians guard guardians with unusual rigor (fleet_watch watches the watchers, the healer heartbeats itself), but the fixed point of the recursion — the thing that notices when *everything* is dark — must live outside the failure domain, and today nothing does.

## §Solo-operatore

Decisions only Zero can take (business calls, spend, credentials, GUI):

1. **Apply `policy.hujson` in the Tailscale admin console** (operator[GUI] — the fleet holds no API token by design). Order matters: before any team device joins. Companion decision: whether the ttyd `/term` serve dies or gets credentialed.
2. **Off-fleet observer placement** (R1): self-hosted on the existing Fly app ($0 marginal, more moving parts) vs Healthchecks.io hosted free tier (20 checks, third-party sees check names + ping times only). Sovereignty judgment — Law 6 permits either, since only expectations leave the machines.
3. **sops/age migration GO + key custody** (R5): where the offline recovery age key lives (password manager vs paper), and the operator[secret] session to re-encrypt the live seat tokens.
4. **RAM budget ruling for Mini**: VictoriaMetrics + exporter (R8) on a 24GB box that also serves Ollama — approve, defer, or cap.
5. **Ratify the genome ratchet rate** (R6, ≥2 organs/week of healer idle-branch time) — a standing work-allocation decision, Legge 5.
6. **nix-darwin pilot scope** (long horizon): whether M5 — his daily driver, the machine with the fewest daemons — becomes the pilot for generated machine state, or whether pull-converge (R4) is declared sufficient for this fleet's lifetime.

## Sources

1. Healthchecks.io — Monitoring cron jobs: https://healthchecks.io/docs/monitoring_cron_jobs/
2. Healthchecks.io — Configuring checks (Period/Grace): https://healthchecks.io/docs/configuring_checks/
3. kube-prometheus Watchdog runbook (always-firing alert): https://runbooks.prometheus-operator.dev/runbooks/general/watchdog/
4. gouthamve/deadman — dead-man's switch for Alertmanager: https://github.com/gouthamve/deadman
5. nix-darwin — declarative macOS incl. launchd agents: https://github.com/nix-darwin/nix-darwin
6. One flake, three machines (nix-darwin multi-host): https://bullo.sk/blog/nix-darwin-multi-host-setup/
7. Temporal — Workflow Execution / event history & replay: https://docs.temporal.io/workflow-execution
8. Temporal — beyond state machines (durable execution rationale): https://temporal.io/blog/temporal-replaces-state-machines-for-distributed-applications
9. GitGuardian — comprehensive sops guide: https://blog.gitguardian.com/a-comprehensive-guide-to-sops/
10. Commit your secrets to git, encrypted, with sops and age: https://tvi.al/commit-your-secrets-to-git-encrypted-with-sops-and-age/
11. Tailscale — Grants vs ACLs (deny-by-default): https://tailscale.com/kb/1467/grants-vs-acls
12. Tailscale — ACL / access control docs: https://tailscale.com/docs/features/access-control/acls
13. Uptime Kuma vs Gatus (monitoring-as-code): https://uptimepage.dev/compare/uptime-kuma-vs-gatus
14. Better Stack — self-hosted uptime monitor survey: https://betterstack.com/community/comparisons/uptime-kuma-alternative/
15. Ansible pull-mode decentralized automation: https://oneuptime.com/blog/post/2026-02-21-ansible-pull-mode-decentralized-automation/view
16. VictoriaMetrics — scraping-agent resource comparison: https://victoriametrics.com/blog/comparing-agents-for-scraping/
17. selfhosting.sh — Nomad vs Kubernetes for self-hosters: https://selfhosting.sh/compare/nomad-vs-kubernetes/
18. Windmill — compared to peers (Temporal/Airflow/etc.): https://www.windmill.dev/docs/compared_to/peers
19. Kestra — Temporal alternatives survey (incl. Inngest, Windmill): https://kestra.io/resources/infrastructure/temporal-alternatives

## Adversarial review

**Reviewer: `kimi-k3` (Moonshot K3) and `codex` (OpenAI gpt-5.6-sol at xhigh effort), 2026-08-30 — cross-family, generator ≠ grader.** Neither seat wrote any part of this panel. Both read all 18 files of the set in full and were asked the *publication* question rather than a proof-reading one: what in this diff creates real incremental risk beyond what the repository already discloses, whether "it is already public elsewhere" is a sound argument or a rationalisation, whether the sequencing is wrong, and what is simply FALSE. Every concrete file claim either seat made was then re-derived independently with `grep`/`git` before being recorded, and objections that measurement falsified are kept as RETRACTED rather than quietly dropped. The full journal and the complete objection list, with per-objection status, are in this PR's evidence pack (`council-journal.jsonl` and the pack's `dissent` block).

**Limits of this review, stated so it is not read as more than it was.** It happened at PUBLICATION time, not at authoring time: no seat re-derived this lane's technical findings against the codebase, so it is not a correctness review of the analysis. Nine numeric objections across the set were recorded PLAUSIBLE because the fact-checking pass ran out of time, not because they were investigated and cleared — an open list, not an all-clear.

**Finding for this file:** The sharpest disclosure in the whole panel sits here — an unauthenticated writable shell published tailnet-wide on the machine holding client PII. Both seats agreed it adds ZERO marginal exposure, because `infra/tailscale/policy.hujson` on the default branch already publishes it verbatim, with the same URL, port and writable flag. That scoping is the only form in which the 'already public elsewhere' argument survived review. Measured on 2026-08-30, the exposure itself is still open; it is ledgered.
