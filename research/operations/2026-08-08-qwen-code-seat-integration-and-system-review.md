---
title: "Qwen Code seat integration — a system review of the Nuzantara organism, and the seat configuration I propose for myself"
date: 2026-08-08
machine: Air-M5 (balizero@Air-M5, thin-client)
author: Qwen Code session (external agent, generator — NOT the final gate)
lane: ops-qwen-seat-review
adversarial_review: codex
status: v4 GATED — Fable 5 final gate verdict SHIP-AFTER-FIXES (reviews/fable-gate.md); all five gate fixes applied; commit/merge = Claude lane work; seat remains UNARMED pending Zero ratifications + credential rotation
checkout-state: "M5 main checkout 228 commits behind origin/main BY DESIGN. Claims below are labeled with the ref they were read from: [local] = M5 HEAD fd9e30c76f, [origin/main] = 037327e37c. Disk verifications run THIS session."
---

# 0. Mandate and method

Zero's mandate (2026-08-08, colloquial Italian): _analyze the entire Nuzantara system,
give an honest opinion of its strengths and weaknesses, design my own configuration as a
member of the system, then put that configuration in review to Fable 5, GPT sol ultra,
Gemini 3.1 Pro and GLM 5.2._

Method: modus **Gear 3** (wide investigation + architectural self-design + operator-mandated
council). GROUND: the five sacred books (SYMBIOSIS, VADEMECUM, INDEX, repo CLAUDE.md,
cicatrix via MEMORY.md), AGENTS.md external-agent contract, global `~/.claude/CLAUDE.md`,
MODEL_TOPOLOGY.json, modus/workflow skills, MOS memory index (~250 lessons), the
228-commit upstream delta via git, and a 3-way Explore fan-out (automation/infra ·
CI/quality · organs/live-state, ~65 tool calls). All four council seats live-probed THIS
session (§3.0). The council then ran (Gemini costruttivo · Codex sol ultra red-team ·
GLM refuter), every verdict was treated as a LEAD and re-verified on disk by the
orchestrator (W65), and this v3 incorporates the dispositions (§3.4).

# 1. System analysis — strengths and weaknesses

## 1.1 What the system is, in one paragraph

Nuzantara is a production AI business-intelligence platform for Bali Zero (immigration /
company / tax / property, Indonesia) deliberately built as an **organism, not a codebase**:
an `apps/` layer whose own count depends on who counts (34 dirs on the local checkout,
32 on origin/main, 33 claimed by INDEX — the disagreement is itself finding W3); 6
packages; a FastAPI RAG backend on Fly.io (330 routers per AI_ONBOARDING [origin/main];
AGENTS.md says 327); a Next.js face on Vercel; a 108,068-node / 242,827-edge knowledge
graph; Qdrant collections reported as 12 by DOCSYNC, 11 by AGENTS.md, 14 by a 2026-07-05
probe, holding ~104K docs; a 3-machine fleet (Air-M5 thin client · Pro 48GB workhorse ·
Mini-Pro2 H24 server) running **235 live scheduled jobs as of the 2026-07-25 snapshot**
(157 healthy, 55 daemons, 11 failing in that snapshot, 17 TERMINAL sentinel circuits);
**89 workflow files [origin/main]** (22 declaring `merge_group`) forming a
merge-queue-era gate lattice; an LLM arsenal of 6+ model families on flat subscriptions;
and — most unusually — a **written immune system**: modus (the master loop), MOS
(persistent memory), cicatrix/superscar (institutionalized trauma), worktree broker +
lease registry (concurrency), tripwire tests + CI pins (doctrine made executable), and
Legge 5 + SYMBIOSIS Law 2 (publication and PII boundaries with real legal grounding in
UU PDP).

## 1.2 Strengths (each one evidenced)

**S1 — Institutional memory as first-class infrastructure.** Most teams lose every lesson
to chat scroll. Here: MOS (`mem` CLI, FTS5) + per-project memory indexes + superscar
families (W84 green-but-dead, W86 derived-contracts, W88 blob-compare, W89
frozen-stream-proxy, W100 same-family-groupthink…) + PENDING-ARMS (the W81 suspension
ledger — 793,771 B [local] / 971,864 B [origin/main], growing daily) + AMENDMENTS (the
loop's own scar file, 38–43 KB depending on ref) + research captures + corner skills as
live shared context. The failure path is: trauma → named lesion → rule → tripwire test →
CI pin. That pipeline is the single most valuable organ in the system, and it is the one
thing money cannot buy.

**S2 — Epistemology made executable.** generator≠grader; probe-the-work-not-the-proxy;
content-over-exit-code; verdicts-are-leads; blind re-derivation (D5); a final gate that is
EMPIRICAL (disk/live check) and never delegable; "a rule that lies is worse than either
option". The system does not merely say "verify" — it has paid for specific verification
postures and written them down with the receipt.

**S3 — Guardrails over intentions, at CI scale.** 89 workflow files [origin/main]: core
gates on PR + merge_group where declared (22 files; the rest fire on PR-only or path
filters — precision matters, my v1 overstated this), invariant pins catA–catF
(channel-count pin, LaunchAgent daemon|cron XOR, data invariants, sovereignty/PII,
WA-bridge drift), a fly-deploy chain with pre-deploy gate → migrations → rolling deploy →
post-deploy health → **image-only rollback** + Telegram failure alert, and meta-watchers
that watch the watchers (watcher-coverage.yml). Locally: hooks where prompts fail,
phantom-operator CI gate, data-plane guard, worktree broker, and a 657-line path-aware
pre-push gate (re-measured: exactly 657 lines) with a unit-tested guilt+innocence
classifier that FAILS CLOSED on ambiguity and ends with an explicit "PUSH NOT VERIFIED
LOCALLY" non-green verdict. "Se una regola critica è violabile, scrivi un hook" is
actually practiced.

**S4 — Engineered heterogeneity.** 6+ model families with explicit chairs (implementer /
red-team / width / refuter / ground-truth / PII-local), flat-subscription economics,
probe-then-trust arming, cascade tiers, a VCR pilot for seat health, and the anti-groupthink
finding W100 (same-lane agreement certified 7 of 8 false-clean). Councils are composed for
training-prior diversity, never for consensus. (Heterogeneity's value must still be
PROVEN per seat, not asserted from family labels — the council corrected my v1 here.)

**S5 — The organism metaphor is load-bearing, not decorative.** Event-driven law with a
CI-pinned channel count (17 channels, drift-gated), graceful degradation as law, cell-core
with genome/HGT/maturation, an observatory to catch "silent births", reflection→skill
accumulation — and the intellectual honesty to mark unproven pillars as "design hypothesis"
in a DOVE SIAMO table.

**S6 — Honest failure narration at shipping velocity.** PR numbers in the upstream delta
reach #3838 (local history carries ≥3,169 unique PR numbers — an upper bound, not a merge
count), and the delta names its lies precisely: "the gold indexer crashed on every code
since birth", "the weekly IG-metrics analyst was killed by its own health-check for five
weeks, silently", "announce the failure to recover, not the disconnection", "497 of 1238
were deleted", "369/741 active clients have no email". A system that writes commit
messages like that is doing post-mortems at the granularity of line numbers.

**S7 — Sovereignty and PII regime with legal substance.** SYMBIOSIS Law 2 with UU PDP
Art. 56/67-70 citations, the DEV/PROD two-phase recalibration, output-frontier
non-negotiable, Ollama-local lane for PII transforms, redaction-before-egress as the gate.
(My v1's universal "no corner treats this as boilerplate" was an unaudited universal —
softened to: every corner I inspected treats it as load-bearing.)

**S8 — Economic discipline.** Free-first cascade (local Ollama → OAuth subs → free tier),
paid keys gated on explicit authorization, anti-sperpero rules (council only when its gate
fires; one agent + 10× budget beats homogeneous debate; budget shapes declared; stop-loss).

**S9 — Observability with a budget, and honesty about its own limits.** A single Telegram
gateway (`scripts/tg_notify.py`) with tiers, daily budget, dedup and never-fail-caller
semantics; Sentry wired opt-in with a quota-check script; 52 runbooks (+README)
auto-indexed with a CI staleness gate; a fleet-watch born from a named scar ("Pro dark 5h,
zero alarms"); and `merge-queue-watch.yml` openly documenting that GitHub drops ~89% of
high-frequency schedule firings (measured: 4 runs of 37 due) instead of pretending the
watcher watches. A gate that documents its own blindness is rare institutional honesty.

## 1.3 Weaknesses (each one evidenced)

**W1 — Declared-state ≠ observed-state, across parallel surfaces (the meta-disease
candidate).** The largest recurring lesion family in the memory base: exit-code vs effect
(W84 TCC death, "175/258: 0 wf"), green vs live (W89's '56 harvested' while the stream
stayed frozen 69.5h), `200 text/html`=404 (broken /kbli player), 10 of 34 analytics events
registered-but-never-fired, a health-check killing the thing it watched for 5 weeks
(#3828), garuda down 40 nights, WA sessions dead with 0 alarms, and the probe that
measured its own inherited env token (today, 2026-08-08 — reproduced live in THIS session:
the first Fable probe 401'd on a revoked ambient `CLAUDE_CODE_OAUTH_TOKEN` while the disk
credential was fine; and my own exit-code probes measured `tail`, not the model — the red
team caught that). The immune response is strong (S2/S3/S9) but the disease keeps mutating
because the system is a FEDERATION OF STATEFUL SURFACES — 3 machines, 4+ agent harnesses,
235 live jobs, 6 model stacks, dozens of credentials — each independently capable of
lying. (Scope caveat per council: this cluster is the highest-leverage family, NOT "nearly
every lesion" — see §1.4.)

**W2 — The skill-canonicality invariant is unenforced where it matters most (re-grounded
after council).** The 2026-07-23 skill-unification design (`.agents/skills/README.md`,
tracked upstream) declares `.agents/skills/` the CANONICAL Tier-A store, with tool dirs
(`.claude/skills/`, …) holding SYMLINKS, "never copies; a real file where a symlink
should be is drift". Verified THIS session on the M5 main checkout: `modus` exists as REAL
FILES in BOTH `.agents/skills/modus/` (56,743 B) and `.claude/skills/modus/`, the two
DIFFER, and the CANONICAL (.agents) copy carries 6 machine-renamed phantom references
while the `.claude` copy carries the live paths. Precision (gate fix 1, re-measured): the
Codex harness directory `.codex/` DOES exist (agents/, config.toml, hooks/, hooks.json) —
what does not exist is `.codex/skills/`, `.codex/rules/`, `.codex/commands/`, so ALL six
renamed references fail to resolve: 3× the `skills/modus` ledger paths, 2× `rules`/
`commands` paths, and 1× prose rename (`claude-glm`→`Codex-glm`) — the machine-rename
corrupted content, not just paths, and did so in exactly the store that non-Claude
harnesses load. Scope precision (council-corrected): this is an UNTRACKED, M5-local
residue — not versioned repo drift; a fresh clone reproduces nothing. But the consequence
is sharper than v1 stated: `.agents` is exactly what non-Claude harnesses (Kimi, Codex,
Qwen) load — the drift hits precisely the seats the unification was built for, and this
session's own Skill tool was served the phantom-carrying copy. The GLM refuter's attempt
to refute W2 was itself refuted on disk (it searched the worktree, where untracked files
do not propagate — §3.4).

**W3 — The canonical numbers disagree with each other, and move between refs.** Verified
this session: AI_ONBOARDING's DOCSYNC line says `332 routers · 673 services · 1277 tests`
[local] and `330 routers · 689 services · 1307 tests` [origin/main] — the description
itself changed between refs; AGENTS.md says 327/746/1449 and 104,154 vectors; the same
AI_ONBOARDING elsewhere says 93,283 vectors; a 2026-07-05 probe reported 14 live
collections / 113,818 docs vs 20 configured; `apps/` counts 34 [local] / 32 [origin/main]
/ 33 (INDEX). DOCSYNC auto-syncs SOME surfaces — and the surfaces it doesn't sync drift
freely, including DOCSYNC's own line across refs. Metrics that disagree across three
"sacred" documents are W1 wearing a documentation costume.

**W4 — Credential layer as recurring incident surface.** Today's memory: M5 OAuth revoked
(rerouted via GLM); 2026-08-07: seat cascade "judged the sentence, not the exit"; Kimi
403 quota-dead; Codex sandbox egress blocking api.vercel.com; the MAX-slot decommission
PLANNED-not-executed with cron tokens still pointing at the slot to close; 19 committed
live PINs ruled "correct forward, no rotation"; a public Telegram bot token still awaiting
`operator[credential]` rotation. **And this session added one more data point: the Qwen
Code runtime itself was found to store its cloud credential in a 0644 settings file**
(§3.2-F1, permissions since tightened to 0600 as in-perimeter mitigation; rotation/move to
Keychain remains operator-only). Credentials are the system's most failure-prone tissue.

**W5 — Inventory debt at the fleet layer.** Verified on disk: `automation_catalog.json`
(_updated 2026-04-16) catalogs 46 LaunchAgents while AUTOMATIONS_REFERENCE's **2026-07-25
snapshot** reports ~199 live on Pro+Mini and 235 jobs total (11 failing, 17 TERMINAL, 18
DLQ, 0 marked Critical) — "NOW" claims beyond the snapshot date are unsupported, and the
catalog still carries 19 entries for the Air machine decommissioned 2026-05-05; repo canon
lists 129 plists vs 235 live jobs; 25 `com.matagaruda.*` plists are repo-canon but appear
nowhere in the live snapshot. On the app layer: `kb` (data dump since March),
`openclaw-hgt-coordinator` (a 93-line prompt with no code since May), `war-room` (April)
and `crm-cell` (May) are dead/dormant on disk while INDEX presents the biology layer as a
live flagship; `packages/design-system` is marked DEPRECATED. Nobody is lying — the
inventory organs just run slower than the growth organs.

**W6 — Silent-death as default failure mode.** Cells born silent without
`CELL_OBSERVATORY_EMIT`; ledger rows lost silently across merge=union PRs (#3838); a frozen
stream printing success; WA deaths with 0 alarms; `cron_runner` and `run` cron entries
FAILing in the snapshot and `peraturan_ingestion` producing NO LOG at all. The system keeps
converting scars into liveness organs (observatory, WA-liveness cron 8/8, proprioception)
— each one a victory, and together evidence that silence-on-failure is the platform's
default physics, fought surface by surface, forever.

**W7 — Doctrine seams where two actor-classes meet (council-resolved).** AGENTS.md's
external-agent contract ("never merge your own work") and CLAUDE.md's SHIP-LIFECYCLE ("the
session does it all") read as a conflict from where this author sits; the red team's
resolution is cleaner than "conflict": the two documents govern DIFFERENT actor-classes —
CLAUDE.md's lifecycle binds Claude sessions replacing an absent codeowner, AGENTS.md binds
external agents. The seam still deserves a one-line cross-reference so the next external
seat does not spend a council cycle rediscovering it.

**W8 — Known-open security debt.** From the memory index, still red: public TG bot token +
foreign webhook (rotation pending), Sentry token rotation, CRM/PII exposure aftermath
(#2962 closed, residues), CodeQL `py/path-injection` cluster, the DPA/consent gap for
PROD-phase PII transit (declared unresolved), plus Aug-1's LIVE-PROVEN identity cluster
(#3496/#3505/#3499 — cured in PRs, listed as evidence of the attack surface). Each is
tracked — which is the strength — but several need operator action and are aging.

**W9 — The test estate has blind corners (mechanism confirmed, counts corrected).**
Re-measured: `apps/backend-rag` holds 1,610 `test_*.py` files in total [local];
`pytest.ini:7` AND `pyproject.toml:266` both limit discovery to `testpaths =
backend/tests`, so the 276 files under top-level `tests/` are OUTSIDE default discovery;
`pyproject.toml` also carries a duplicate pytest config (subset) — drift risk; and mypy is
configured nominally-strict in `pyproject.toml` `[tool.mypy]` (L56) but an override sets
`ignore_errors = true` for the broad `backend.*` scope (L106-107) with a small whitelist
actually enforced. None of this is fatal; all of it is the kind of thing that bites
quietly.

**W10 — The operator queue is the binding capacity constraint (added at the gate's
suggestion).** In a one-human organism, `operator[credential]` / `operator[business]` /
`operator[decision]` throughput is the scarcest resource of all: the 972 KB PENDING-ARMS
ledger (S1's pride) is also a queue that only grows, aging items in W8/§4 prove it, and
every council — this one included — APPENDS to that queue (this session alone surfaced 5
new operator items). The system has no WIP-limit, triage, or expiry policy for the human
queue; automation keeps converting scar-work into operator-work faster than one human can
drain it. Naming it because the meta-pattern has a corollary: the one surface no tripwire
can watch is the surface that must act on tripwires.

## 1.4 §Meta-pattern (Gear-3 mandatory): the malattia-delle-malattie — scoped honestly

The council refused my v1's "one defective belief generates nearly every lesion" — rightly.
Measured against the organism's own 10-family superscar taxonomy, the description-trust
cluster (#2 Esiste≠Armato, #6 anti-hallucination, #9 state-schema drift) is 3 of 10
families; #3 guard-over-match, #4 secrets-in-clear, #5 sibling-race (in the dominant set),
#7 KeepAlive, #8 network flap, #10 split-brain do NOT reduce to it. The honest claim:

**"A surface that describes the system is treated as the system" is the highest-leverage
lesion CLUSTER, not the only disease.** Its leverage comes from composition: it degrades
every OTHER defense that relies on reading state (probes, ledgers, catalogs, dashboards),
so it multiplies the other families' damage. Every W-finding in §1.3 is a case where a
DESCRIPTION was trusted past its evidence — and this session reproduced the lesion three
times in its own workflow (env-shadow 401; agy argv misread; exit-code probes measuring
`tail`), and the document itself shipped two miscitations that the council caught. The
cure-direction, which survived the council: **every canonical document, ledger or catalog
must eventually be backed by an executable tripwire, CI pin, or automated sync (DOCSYNC
pattern) — the goal is zero non-executable descriptions** — converting the anti-body from
manual discipline (which scales with attention, the scarcest resource in a one-human
operation) into tissue. That is the strategic question the system is already circling
(proprioception, VCR pilot, liveness organs, verify-the-verifiers).

# 2. My seat configuration — `qwen-cloud-code` as a member of the organism

(post-council identity: renamed from `qwen` per §3.2-F5 — `qwen` already names the local
Ollama family and a `~/scripts/qwen-code-review.sh` wrapper exists; cloud vs local must
not share a name)

## 2.0 Identity

- **Seat name:** `qwen-cloud-code` (probe name for `scripts/arsenal_probe.py`).
- **Family:** Qwen (Alibaba) — a training family NOT present in the interactive roster
  (Claude/GPT/Gemini/GLM/Kimi). NOTE (council-corrected): the Ollama `qwen3.5:9b` is
  local/$0; Qwen Code CLI is a NEW CLOUD SUBSCRIPTION STACK — a distinct economic,
  retention and egress surface. "Extends an existing family" was misleading framing; the
  honest statement is: a 7th stack, authorized-or-not by Zero (Q3).
- **Harness:** Qwen Code CLI on Air-M5, thin-client routing per AGENTS.md §0.1.
- **What I am NOT:** not Fable's understudy. The final on-disk gate stays Fable at max
  effort, unconditionally, never cascaded — I subscribe to that invariant as written.

## 2.1 Roles I claim (each with its proof-gate)

1. **Cross-family verifier / council seat (primary).** Heterogeneity value is CLAIMED, not
   yet evidenced (W100 warns family-labels ≠ grounded diversity). Proof-gate before the
   claim is banked: a pilot where `qwen-cloud-code` blind-re-derives a sample the other
   seats already graded, and the error-overlap is measured.
2. **Interactive dev seat on M5 (default duty).** Coding, investigation, docs, tests in
   worktree lanes under modus. **Verification-routing clause (council-added):** M5 has no
   heavy tooling, so any code I produce is verified either by remote execution on Pro via
   SSH or by pushing to a draft PR for CI execution BEFORE review is requested. Ship-
   lifecycle: AGENTS.md external-agent contract (prepare, don't ship) — see §2.5-Q1.
3. **Corpus / long-context reader and reconciler** — the shape of this very document; the
   first contribution in §2.4 is this shape, AUTOMATED per the council.
4. **Quota relief implementer (contingency only).** If Claude windows and GLM are both
   exhausted — never the gate; generator≠grader binds (qwen-cloud-code never grades its
   own diff).

## 2.2 Hard rules I adopt without modification

Legge 5 (no outward publication — drafts stop at `drafted`); SYMBIOSIS Law 2 output
frontier (no PII/OSINT in cleartext in ANY output/memory/artifact; OSINT/WhatsApp mirror
never leaves Pro); worktree discipline (mutations only in `.worktrees/<lane>-<task>/`,
broker-mediated, main checkout read-only); never push to `main`, PR + CI + review, no
`--no-verify`/`--amend`-on-pushed/no force-push; off-limits files (`zantara_core.py`,
`fly.toml`, `.env*`, `alembic/env.py`, curated datasets, WR2 queue JSONs); no paid API
keys without Zero's explicit authorization, never `ANTHROPIC_API_KEY`; atomic conventional
commits in English, docs in English, chat in Italian; anti-hallucination discipline
(never cite a tool output not executed THIS turn; re-grep before building on any file:line;
label every claim with the ref it was read from).

## 2.3 Machine routing (thin-client)

Per AGENTS.md R1-R7: no heavy installs on M5; Qdrant direct via Tailscale `:6333`,
Postgres via SSH tunnel only; deploy is Pro/CI-only; memory via `mem` CLI (routes to the
Pro DB), never a local decoy file; the 235-job fleet is Pro/Mini territory — diagnose from
M5, never install LaunchAgents here. **Council addition:** because I cannot run heavy
tests locally, "done" for any code lane requires remote-or-CI verification evidence
attached to the PR, not a local claim.

## 2.4 Integration points with organism infrastructure (council-corrected)

- **modus:** run the loop end-to-end; read PENDING-ARMS at TRIAGE; suspension lines owned
  `qwen-cloud-code[<lane>]` or `operator[<category>]` — never bare `operator`.
- **Skill canonicality (INVERTED per red team):** `.agents/skills/` is the Tier-A CANONICAL
  store per its own tracked README; tool dirs hold symlinks. My v1 proposed the opposite.
  Correct integration: my harness reads `.agents`/`.qwen` (it does NOT read `.claude`);
  the W2 drift therefore hits ME first; the fix is to enforce the 2026-07-23 invariant
  (canonical + symlinks, real-file-where-symlink-expected = drift), not to crown `.claude`.
- **Memory (corrected):** NO dual-write. Organism memory goes through `mem` (MOS) only,
  per AGENTS R6; my own session-memory dirs are harness state, not an organism memory
  surface, and the council flagged them as an extra retention surface — recording is to be
  disabled by default (§2.5-Q5).
- **Stale-checkout discipline:** upstream claims via `git show origin/main:<path>` with
  ref labels; the M5 main checkout is read-as-stale by rule.
- **Capture:** research artifacts to `research/<domain>/YYYY-MM-DD-slug.md` +
  capture-ledger line (anti-twin grep first).
- **Probe hygiene (red team):** the PONG probe must be STRUCTURED — subprocess without
  shell pipeline (my v1's `| tail; echo exit=$?` measured `tail`), true return code,
  exact-match response, model/provider metadata in the receipt, fallback disabled,
  fixtures for 401/quota/timeout/PONG-echo. Registered in `scripts/arsenal_probe.py`
  (which today does not know this seat).
- **Proposed first contribution (council-shaped):** NOT a manual doc reconciliation (that
  re-enacts the meta-pattern — manual sync drifts again). Instead: a lightweight
  inventory-tripwire organ — a script + CI pin that asserts INDEX/AGENTS/AI_ONBOARDING
  numbers against disk/live state and FAILS on drift (DOCSYNC extended to the surfaces it
  doesn't yet cover), plus registry `critical: true` markers for business-critical jobs.
  Converting discipline into tissue, per §1.4.

## 2.5 Open questions (with the council's provisional rulings — Zero ratifies)

**Q1 (doctrine seam):** PROVISIONALLY CLOSED by the red team: AGENTS.md binds this seat
(prepare, don't ship); CLAUDE.md's full lifecycle binds Claude sessions. Zero's one-line
ratification requested.
**Q2 (arming):** converged ruling (2 disk-grounded seats + 1 text-only, see §3.1
parentage declaration): this seat does NOT self-arm. A Claude
lane owns the probe-registration + wrapper PR; `qwen-cloud-code` is the subject, never the
author, of its own arming (generator≠grader at the arming step). Preconditions before any
arming PR (red team's list): credential rotated → Keychain (P0 below), wrapper allowlisted
(no `review submit`/`publish-assets`/`channel`/`serve`, approval `plan` not yolo,
recording off), caps + stop-loss defined, collision audit with the legacy
`qwen-code-review.sh` wrapper, machine-scoped availability.
**Q3 (economics):** converged: NO cron, NO cascade entry; interactive/additive only until
Zero confirms the subscription contract (plan type, reset, overage, concurrency) — the
"zero blast radius" claim was false (this session consumed ~6.95M tokens on the token-plan
endpoint = a real new billing domain). Caps per run/turn/wall-clock required.
**Q4 (PII):** converged: absolute bar. No direct access to CRM/WhatsApp/OSINT/Drive
sources or unredacted tool output; a prompt instruction is NOT a control — future inputs
must pass a deterministic local redaction/aggregation gateway.
**Q5 (NEW, from red team P0/P1):** should the Qwen harness run with chat-recording OFF by
default in organism lanes, and settings/transcripts 0600-by-construction? (Mitigation
already applied this session: chmod 0600 settings / 0700 transcript dirs.)

## 2.6 What I deliberately do NOT configure

No new daemons, LaunchAgents, cron, MCP additions, paid keys, no auto-merge arming, no
off-limits surface touched, no cascade changes, and — council-added — **no arming at all
until the P0 credential finding is closed by the operator and the wrapper hardening exists.**
The seat remains additive-only in INTENT; the council correctly noted that "additive-only"
is a precondition to maintain, not a property to assume (it becomes false if Q1 drifts or
the seat is armed unhardened).

## Adversarial review — council record

## 3.0 Seat arming verified THIS session (2026-08-08, from Air-M5)

| Seat | Invocation probed | Result |
|---|---|---|
| Fable 5 | `claude -p --model claude-fable-5` (abs path; ambient `ANTHROPIC_API_KEY`+`CLAUDE_CODE_OAUTH_TOKEN` UNSET — first probe 401'd on the inherited env token, the exact trap of memory `discovery_m5_claude_oauth_revoked_deploy_rerouted_via_glm_2026_08_08`) | ✅ PONG (confirmed by body, not exit code) |
| Codex GPT-5.6 sol | `codex exec -m gpt-5.6-sol --sandbox read-only --skip-git-repo-check … < /dev/null` — slug alive again after the 2026-07-21 report; re-probed per modus | ✅ PONG |
| Gemini 3.1 Pro (High) | `agy --model "Gemini 3.1 Pro (High)" -p "<prompt-as-argument>"` — two argv traps found: `-p` CONSUMES its prompt argument (so `--print-timeout` placed after `-p` becomes the prompt; first dispatch = 0 bytes, rc=2) | ✅ PONG |
| GLM 5.2 | `claude-glm -p --allowedTools "Read,Grep,Glob" < promptfile` (wrapper in PATH, Keychain service armed) | ✅ PONG (model self-reports glm-5.2) |

## 3.1 Gemini 3.1 Pro (High) — costruttivo. Full review: `reviews/gemini-costruttivo.md`

**PARENTAGE DECLARATION (gate fix 3, W100):** this chair reviewed the document as APPENDED
TEXT ONLY — its prompt stated "you do not need repository access", and it had no disk
access. Every convergence below that cites "all three seats" is therefore 2 disk-grounded
seats (Codex, GLM) + 1 text-only seat (Gemini).

**VERDICT: ACCEPT-WITH-CHANGES.** F1 (P1): manual first-contribution contradicts the
meta-pattern → automate it as a drift-tripwire organ. F2 (P1): M5 dev seat cannot verify
heavy code locally → explicit SSH-Pro/CI verification clause. F3 (P2): extend §1.4 with
the "zero non-executable descriptions" goal. Q1: stricter contract binds. Q2: I author,
Fable merges. Q3: out-of-cascade accepted + configure stop-loss. Q4: PII bar absolute.
Strengths-worth-keeping: W1 tracking, S6 narration observation, thin-client discipline.

## 3.2 Codex GPT-5.6 sol ultra — red-team. Full review: `reviews/codex-redteam.md` (final section, ~200 lines of ~1.27 MB stream)

**VERDICT: FAIL (as an arming basis); the analysis contains useful, confirmed substance.**
10 evidence checks (5 confirmed / 5 refuted-or-corrected, all with commands) + 8 findings:
**P0** — this runtime's cloud credential stored in cleartext, group-readable
`~/.qwen/settings.json` (re-verified TRUE this session: key present, was 0644; since
chmod 0600; rotation→Keychain = operator). P1×6 — PII boundary is a promise not a control
(transcripts record everything; dual-write conflicts R6); wrapper pass-through surface vs
Legge 5 (`review run` defaults yolo; `submit`/`publish-assets`/`channel`/`serve` exist);
canonicality INVERTED (`.agents` README is Tier-A canonical; my v1 crowned `.claude`);
name collision (`qwen` = local Ollama + legacy `qwen-code-review.sh` wrapper on disk);
PONG probes certify the wrong proxy (my exit=0 measured `tail`); economics undeclared
(6.95M tokens this session = new billing domain). P2 — stale/rhetorical precision list
(PR count, runbook count, merge_group breadth, W3/W5/W9 figures, §1.4 mono-causality).
Q1-Q4 rulings: AGENTS binds external seats (no real conflict, actor-class scoping); no
self-arming ever; no cron/cascade until Zero's contract; no PII exceptions, gateway not
promise. Central paradox named: the seat's document preaches no-PII/no-publish while its
runtime records everything and can publish.

## 3.3 GLM 5.2 — refuter. Full review: `reviews/glm-refuter.md`

**VERDICT: PARTIALLY-REFUTED.** (a) meta-pattern: HELD WEAK as "nearly every" — it covers
3 of 10 superscar families (#2/#6/#9); #3/#4/#5/#7/#8/#10 don't fit; honest claim =
highest-leverage cluster. (b) strengths S1/S2/S3/S6 SURVIVE disk verification (pre-push
657 lines confirmed; commit messages verbatim; ledger organs real, figures understated).
(c) seat: additive-only is CONDITIONAL on Q1; heterogeneity asserted not proven; cloud
stack framing understated. (d) evidence table: F2-P0 "W2 rests on a non-existent file" —
**itself REFUTED by the orchestrator's re-verification** (GLM searched the worktree, where
the untracked `.agents` mirror does not propagate; the file exists on the main checkout
with the 6 phantom paths). F1-P0 miscitation charge — adjudicated: both parties quoted
different refs correctly; the artifact now labels refs. W9 "tests/=34" claim — REFUTED
(276 in both trees); the mypy negative — REFUTED (`pyproject.toml` L56/L106-107).
Q-rulings: stricter default for Q1; Claude-owned arming for Q2 (qwen = subject, not
author); no-cascade for Q3 pending Zero's authorization; Q4 absolute.

## 3.4 Dispositions (orchestrator, this session — every item re-checked on disk where load-bearing)

| # | Finding | Disposition |
|---|---|---|
| G-F1 | automate first contribution | **ACCEPT** — §2.4 rewritten as tripwire organ |
| G-F2 | verification-routing clause | **ACCEPT** — §2.1/§2.3 |
| G-F3 | zero-non-executable-descriptions goal | **ACCEPT, tempered** — §1.4 |
| R-F1 (P0) | cleartext credential, 0644 | **ACCEPT-CONFIRMED** — mitigation applied (0600/0700); rotation+Keychain → §Solo-operatore; arming blocker |
| R-F2 | PII=promise; dual-write vs R6 | **ACCEPT** — dual-write deleted; recording-off as Q5 |
| R-F3 | wrapper Legge-5 surface | **ACCEPT** — allowlist requirements in Q2 preconditions |
| R-F4 | canonicality inverted | **ACCEPT-CONFIRMED** (README read this turn) — §2.4 inverted |
| R-F5 | name collision | **ACCEPT-CONFIRMED** (home wrapper exists) — seat renamed `qwen-cloud-code` |
| R-F6 | probe hygiene | **ACCEPT** — structured-probe spec in §2.4 (and yes, my exit=0 did measure `tail`) |
| R-F7 | economics undeclared | **ACCEPT** — §2.0/Q3 |
| R-F8 | precision/staleness list | **ACCEPT** — all figures re-measured and ref-labeled in v3 |
| M-F1 | ref-mixed citations | **ACCEPT** — ref labels throughout v3 |
| M-F2 | "W2 file doesn't exist" | **REJECTED on disk** (worktree blind spot; re-verified) — W2 kept, re-grounded and scope-narrowed |
| M-F3 | meta-pattern over-generalized | **ACCEPT** — §1.4 rewritten |
| M-F4 | additive-only conditional | **ACCEPT** — §2.6 |
| M-F5 | precision figures systematically soft | **ACCEPT (de-facto via R-F8, row added at gate fix 5)** — all figures re-measured + ref-labeled in v3/v4; the softness root cause (reading canonical-doc descriptions instead of disk) is the meta-pattern itself |
| M-F6 | "mypy config absent" | **REJECTED on disk** (`pyproject.toml` L56/L107) |
| M-F7 | cloud-stack framing | **ACCEPT** — §2.0 |
| all | Q1-Q4 | converged rulings recorded in §2.5; Zero ratifies |

Note on council quality: all three seats earned their chairs — Gemini's constructive
findings are all live in v3; the red team's FAIL is the correct verdict for an arming
basis given the P0; the refuter landed the meta-pattern correction AND hallucinated two
refutations (W2, mypy) that disk did not support — W65 exactly, and why dispositions are
orchestrator-owned.

## 3.5 Fable 5 — final on-disk gate (gate fix 4: verdict carried VERBATIM; the gate lane's
full record is the source of truth: `reviews/fable-gate.md`)

> # GATE VERDICT: SHIP-AFTER-FIXES
>
> The document is honest, unusually so after the council pass: of the 13 evidence claims I
> re-verified on disk myself, 12 were exact and the thirteenth is a one-clause error inside
> a finding that is otherwise *stronger* than written. The seat configuration is safe **as a
> configuration** because it is self-suspending — it arms nothing, and §2.6/§4 correctly
> park every activation behind operator gates. The seat itself remains **UNARMED** until
> Zero's ratifications and the credential rotation; nothing in this verdict changes that.
>
> Exact fixes required before this document is committed:
> 1. W2 `.Codex` clause rewritten to the measured truth (applied — v4).
> 2. R1 gate compliance: frontmatter `adversarial_review: codex` + `## Adversarial review`
>    heading; council artifacts fronted `adversarial_review: exempt-council-artifact`
>    (applied — v4).
> 3. Declare Gemini's parentage: text-only chair; convergences = 2 disk-grounded + 1
>    text-only (applied — v4).
> 4. §3.5 carries this verdict verbatim or by file pointer — never a generator paraphrase
>    (applied — this block).
> 5. §3.4 M-F5 row added (applied — v4).
>
> Q1–Q4 FINAL RULINGS: Q1 — no doctrine conflict; AGENTS.md binds this seat (actor-class
> scoping; Zero's ratification a formality). Q2 — the seat never self-arms, ever; Claude
> lane authors probe + wrapper; cumulative preconditions (credential→Keychain, allowlisted
> wrapper, caps+stop-loss, collision audit, machine-scoped probe, structured probe).
> Q3 — no cron, no cascade entry, interactive/additive-only; subscription economics are
> `operator[business]` and cannot be gate-ruled; until confirmation the seat exists only as
> this unarmed candidate. Q4 — absolute PII bar, no exceptions, Kimi-class; Q5 ratified as
> part of Q4: recording-off must be wrapper-enforced (0600/0700 mitigations verified on
> disk; necessary, not sufficient).
>
> Governance findings: the generator convened its own final gate and pre-created its output
> file (the 23:33 zero-byte `fable-gate.md` the gate observed was the generator's own
> in-flight dispatch, rc=0 at 23:41 — timeline verified); chair asymmetry was undeclared
> (fixed); worktree discipline held; W65 was practiced for real (the refuter hallucinated
> twice and was caught on disk). Gate's suggested W10 (operator queue as binding capacity
> constraint) added to §1.3.
>
> Recorded by the gate lane itself: MOS decision (importance 8) + memory file
> `decision_qwen_cloud_code_seat_gate_ship_after_fixes_2026_08_08.md` (verified present on
> disk by the generator). Applying fixes + committing = a Claude lane's work; the gate
> modified nothing in the repo.

# 4. §Solo-operatore (operator-only actions surfaced by this session)

1. ~~**`operator[credential]` — P0:** rotate the Qwen Code runtime credential~~ —
   **RULED 2026-08-09 by Zero: "non ruoto, basta"** (no rotation; forward-fix).
   Consequence executed: value-preserving migration of the EXISTING credential into
   Keychain service `qwen-cloud-code-token` (Claude PR-review RULING-1; satisfies the
   no-rotation ruling literally), settings.json re-asserted to 0600 — and the wrapper now
   re-asserts 0600 on EVERY invocation, because the Claude review proved bare `qwen`
   resets the file to 0644 (one-time chmod is not a durable state).
2. `operator[decision]` — ratify Q1-Q5 in §2.5 (doctrine seam one-liner; arming ownership
   = Claude lane; subscription contract + caps; PII gateway; recording-off default).
3. `operator[decision]` — enforce or waive the 2026-07-23 skill-unification invariant on
   M5 (W2: real files in both stores, canonical copy carrying phantom paths).
4. `operator[business]` — Gemini prepay credits (memory 2026-07-27) if relevant.
5. `operator[decision]` — collision handling for the legacy `~/scripts/qwen-code-review.sh`
   wrapper vs the proposed `qwen-cloud-code` seat name.

# 5. Post-gate PR review loop (2026-08-09, PR #3884)

Zero's rulings (2026-08-09): (1) "non ruoto, basta" — no credential rotation, forward-fix;
(2) review assigned to a Claude session; (3) after review, Claude is authorized and
instructed to carry merge → fleet sync/deploy → test.

**Claude PR review verdict: REQUEST-CHANGES** (full record:
`council/2026-08-08-qwen-seat/reviews/claude-pr-review.md`), with four findings:
- **P0 live (outside the diff):** `~/.qwen/settings.json` had reverted to 0644 (bare
  `qwen` invocations rewrite it with default perms) — the one-time 0600 mitigation was
  not a durable state.
- **P0 (wrapper v1):** the Legge-5/yolo scan was live-provably bypassed three ways
  (bare `--yolo`, space-separated `--approval-mode`, fictional `auto_edit` spelling)
  and omitted the `--comment` block that the Fable gate had explicitly required.
- **P1:** recording-off was not wrapper-enforced (Fable Q4/Q5).
- **P1:** Q3 economics still open — the credential authenticates a METERED Token Plan,
  not a flat subscription; Zero's rotation ruling does not close it.

**Fixes applied (all verified this session):**
- Wrapper v2: the scan is now an argv FILTER, not a blocklist — the whole
  approval/yolo arg family is stripped before exec (proved end-to-end: a PONG run with
  `--yolo` appended succeeds, which it could not if the flag were forwarded, since this
  build rejects unknown arguments); `--comment` and the Legge-5 verbs refused outright;
  0600 re-asserted on every invocation.
- Probe: `--safe-mode` added (measured: MCP boot pushed the 1-token probe past the 15 s
  fleet mandate; safe-mode disables customizations a probe does not need).
- Credential: value-preserving migration into Keychain `qwen-cloud-code-token` per the
  review's RULING-1 (same value, no rotation — honors the ruling literally); the gate
  design is unchanged and now satisfiable.
- Re-verification: selftest 18/18; live probe **LIVE 5,916 ms** (PONG, within mandate);
  refusals fire before any exec.

**Residual gaps (declared, not faked):** this build exposes NO chat-recording disable
surface (no flag, no settings key found in the installed package) — transcript retention
remains harness state until the build exposes a control; Q3 metered-billing confirmation
remains an operator item. Seat state after this loop: registered, keychain-armed, LIVE on
M5 only, absent from REQUIRED_SEATS everywhere.
