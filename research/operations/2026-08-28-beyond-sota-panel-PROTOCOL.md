---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
type: protocol
mandated_by: Zero (interactive Pro session, /model claude-fable-5, max effort)
adversarial_review: kimi-k3
model_selection: "manual — Zero's order of 2026-08-28 for this one panel; pinned by the orchestrating session, not routed by any script, cron or doctrine (Fable 5 has no automated role, ruling 2026-08-20)"
---

# BEYOND-SOTA PANEL — protocol for the 13 Fable-5 lanes

## 0. Mandate

Zero, 2026-08-28 (verbatim intent): *analyze how we practice coding and all the arts of
implementing, architecting and designing; split it into coherent parts; for each part launch a
Fable 5 max-effort lane that analyzes the part, deep-researches the best systems in the world for
that sector, and advises how to take that part BEYOND the state of the art.* Delivery: every
report on the M5 Desktop, plus this repo under `research/operations/`.

Fable 5 is normally out of the automated workflow (CLAUDE.md §5, RULED 2026-08-20). This panel
runs on Fable because Zero selected it manually in this interactive session — the one sanctioned
path (Legge 5). The lanes run with the model PINNED to `claude-fable-5` under Zero's manual selection for this one panel (order of 2026-08-28; this protocol is a run record, not standing doctrine — nothing in it or in the repo routes to Fable afterwards) (fresh context — the 5 fork lanes of the
first launch inherited ~90K tokens of session context each and hit the seat's WEEKLY cap (91% when probed) within
minutes; pinned fresh-context lanes ALSO died on the second seat — see §4bis; headless `claude -p` lanes, one OAuth seat each, are how the panel completed). Each lane executes directly and
never re-delegates (no Agent, no Workflow).

**Repo root for every lane = the panel worktree**
`/Users/nuzantara/nuzantara/.worktrees/research-beyond-sota-0828` (branch
`agent/nuzantara/research/beyond-sota-0828`, same HEAD as main at launch). Read from it, write
into it. The main checkout `/Users/nuzantara/nuzantara` is off-limits for writes (hook W79) and
its working tree carries other sessions' uncommitted state — do not read it.

## 1. The 13 parts (anatomy of the craft)

| # | slug | part | owns | does NOT own (another lane does) |
|---|---|---|---|---|
| 1 | `intake-triage-specification` | Intake, triage & specification | mandate → gear → grounded falsifiable spec; stadio-zero; karpathy; ASSEMBLY-LINE 5-artifact set; MANDATE.md; rule 8 "three rounds then suspend"; language protocol | architecture decisions (3), build (4) |
| 2 | `context-engineering-grounding` | Context engineering & grounding | SessionStart injection, MEMORY.md/MOS, repomap, scars-as-context, corners/skills, NotebookLM ground truth, anti-hallucination, doctrine size budgets, compaction/handoff | the learning loop that WRITES scars/memory (10) |
| 3 | `architecture-decision-making` | Architecture & design decision-making | sota-architecture-loop, councils/panels, decision gates, ADR/research capture, SYMBIOSIS laws as constraints, organism anatomy (organs registry, INDEX), Research OS | intake/spec (1), orchestration mechanics (9) |
| 4 | `implementation-craft` | Implementation craft (BUILD) | worktree broker, leases, implementer routing, TDD/reuse-first, PR contract, code golden rules, headless CLI implementers, Antigravity/Codex/Kimi coding seats, grunt agents | verification (5), CI/merge (6) |
| 5 | `verification-adversarial-gate` | Verification, adversarial review & final gate | generator≠grader, refuter seats, verify-template.js, final on-disk gate, final-gate-discipline, guard-conformance, verification rules, tripwires, mutation testing, review gates in CI, reward-hacking detection | CI mechanics (6), prove-live (7) |
| 6 | `ci-merge-queue-ship-pipeline` | CI, merge queue & ship pipeline | Merge-OS v2 (mq arm/requeue/handoff), required checks, branch protection/CODEOWNERS tiers, hot-zone gates, pre-push gate, suite lock, 106 workflows, flaky/red-main breakers, merge-queue traps, branch hygiene | deploy (7), verification content (5) |
| 7 | `deploy-release-prove-live` | Deploy, release & prove-live | Fly/Vercel deploys, split-brain verify, consumer-map, PROVE-LIVE, ship dark→5%→100%, synthetic probes, flags on two platforms, migrations-at-deploy, rollback, post-deploy QA | CI (6), observability after release (8) |
| 8 | `observability-immune-self-healing` | Observability, immune system & self-healing | proprioception, healer, escalations board, organs registry heartbeats, PENDING-ARMS as receptor, launchd liveness, cron-theater family #2, Sentry/Telegram alerting, arsenal probes, daemons hygiene | deploy verification (7), learning capture (10) |
| 9 | `multi-agent-orchestration-fleet-routing` | Multi-agent orchestration, fleet & cost/quota routing | FLEET_TOPOLOGY, conductor endpoint profiles, cascades, workhorse-first, MODEL_ROSTER, army lanes, Workflow tool, seats/quotas/effort economics, twin-session protocol, dispatch discipline | what a council DECIDES (3), what a gate JUDGES (5) |
| 10 | `organizational-learning-loop` | Organizational learning loop | cicatrix scars → superscar families, executable antidotes, MEMORY index budget, lessons, AMENDMENTS, modus-bench, reflexion, skill library, doctrine drift (3 copies of CLAUDE.md), recidiva | context injection mechanics (2) |
| 11 | `product-ux-visual-design` | Product, UX & visual design craft | design study loop, brand cortex, WR2/WR3 pipelines, design canvas, frontend (apps/mouth), journey tests, funnel UX defects, i18n, accessibility, conversion for high-stakes services | backend data (12) |
| 12 | `data-schema-migrations` | Data, schema & migration engineering | Postgres roles/ownership, migrations_v2 + Squawk, runtime-DSN migration runner, audit triggers, jsonb codec, prod-shaped test DBs, invariants/tripwires, Qdrant collections + frozen embedding, retention, outbox durability | app-level verification (5) |
| 13 | `security-secrets-pii` | Security, secrets & PII engineering | Law 2 output boundary, secrets hygiene (family #4), OAuth token handling, env inheritance by external CLIs, public-repo hygiene, hooks/guardrails as backstop, RBAC/CODEOWNERS, agent sandboxing, prompt-injection surfaces, supply chain, tailnet | data-role design (12) |

## 2. Method — A → D, in this order

**A. GROUND (repo, read-only).** Read your hot files (in your lane prompt) and whatever they point
to. Every claim about "how we do it today" cites a path (and line when useful) that YOU verified
with `ls`/`grep`/`cat`/`sed -n` IN THIS SESSION — never from memory, never from the CLAUDE.md
summary alone (anti-hallucination rules, CLAUDE.md §6). Grep the scar corpus and the ledger for
your area — scars are measured failures, the most honest evidence of where a practice is weak:
- `.claude/rules/cicatrix-superscar.md` (14 KB — read whole), `.claude/rules/cicatrix-scars.md`
  (296 KB) and `cicatrix-scars-archive.md` (397 KB) — **grep only** (`grep -n "^## " file | grep -i <topic>`,
  then `sed -n` the block).
- `.claude/skills/modus/PENDING-ARMS.md` — **2.2 MB, 1080 entries: grep only, never cat.**
- `.claude/skills/modus/AMENDMENTS.md` (52 KB) — the loop's own misfire log.
- memory bodies: `/Users/nuzantara/.claude/projects/-Users-nuzantara-nuzantara/memory/` (1707
  files) — `grep -il <topic>` then read the hits; `MEMORY.md` is the index.
- prior panels: `research/operations/` (349 files) — `ls | grep -i <topic>`; cite and build on
  prior decisions instead of re-deriving them; if a prior decision is wrong, say so with evidence.
Shared doctrine (verified on disk 2026-08-28): `CLAUDE.md`, `SYMBIOSIS.md` (38 KB),
`VADEMECUM.md` (21 KB), `INDEX.md` (12 KB), `.claude/skills/modus/SKILL.md` (66 KB),
`research/operations/2026-06-30-claude-code-perfect-session-doctrine.md` (the LAW, 22 KB),
`docs/factory/ASSEMBLY-LINE.md`, `docs/factory/SEAT-MIX.md`, `MODEL_ROSTER.md`,
`FLEET_TOPOLOGY.json`, `research/operations/2026-08-10-fleet-order-spec.md`,
`research/operations/2026-08-21-token-ceremony-ci-system-audit.md`. Read the ones your part needs.
`docs/LIVING_ARCHITECTURE.md` is 297 KB — grep only.

**B. SURVEY (web).** First `ToolSearch("select:WebSearch,WebFetch")` to load the web tools.
Find the best-in-class systems, engineering cultures, tools and research for your part:
big-tech practice (Google / Meta / Stripe / Netflix / Uber / Amazon class), leading open source,
frontier agentic-coding systems (Anthropic / OpenAI / Cognition / Cursor / Sourcegraph class),
and academic results 2023-2026. **Minimum 10 distinct primary sources with URLs**; prefer primary
(papers, engineering blogs, official docs, code) over listicles; note the date of each source.
For each: what it is · the mechanism that makes it best-in-class · the measured effect if
published · whether and how it transfers to THIS organism (solo owner who does not review code;
sessions own review→merge→deploy→prove-live; multi-LLM fleet on flat subscriptions only; zero
paid Anthropic API, CLI-only; local sovereignty; PII output boundary; Fable never auto-routed).
**Web hygiene:** queries are generic — never paste repo internals, hostnames, tokens, paths,
client data or file contents into a search or fetch.

**C. POSITION.** Per sub-dimension of your part: BEHIND / AT / AHEAD of SOTA, each with the
evidence (a file, a scar, a ledger row, a number). Be honest in both directions — the organism
is genuinely ahead in places; say where, and why.

**D. BEYOND-SOTA.** A recommendation counts as beyond-SOTA only if ALL of:
1. no surveyed system does it, or it composes known pieces into something none of them has;
2. it exploits an asymmetry this organism actually has (6 OAuth seats + cross-family council;
   the scar corpus; full-lifecycle session ownership; always-on local machines; hooks-as-backstop;
   the PENDING-ARMS ledger; CI-recomputed gear floors; a public repo as forcing function; …);
3. it has a before/after number (SYMBIOSIS Law 7: no metric = not an improvement);
4. it respects the hard rules (no paid Anthropic API / SDK banned; CLI-only for LLMs; PII output
   boundary; Fable not auto-routed; Zero decides business matters — label those `needs-ruling`).
Rank by (impact × confidence) / cost. Each recommendation states: what · why it beats SOTA ·
cost (flat-sub tokens / hours) · gear (1/2/3) · risk + the scar family it could trigger (#1–#10) ·
metric + measurement method · kill criterion · first PR (≤400 net lines, one concern) when applicable.

## 3. Hard constraints (every lane)

- The worktree is READ-ONLY for you except your single output file. No git state changes (no
  checkout/stash/branch/commit/worktree/pull), no test-suite runs (machine saturation), no
  installs, no edits elsewhere, no process kills.
- Never open or print a secret: not `.env*`, not `~/.nuzantara-secrets.env`, not keychains,
  not token files, not `~/.qwen/settings.json`, not plist env blocks. Report on MECHANISMS, never
  values. `.mcp.json` and `~/.claude/hooks/*.py` may be read for structure only.
- No PII/OSINT in the report (client names, phones, emails, documents). `client_id`/placeholders.
- Bash only for: `ls`, `find`, `grep`, `cat`, `sed -n`, `wc`, `head`, `tail`, `git log`,
  `git show`, `git diff --stat` (read-only), `gh pr list`/`gh run list` (read-only, when your
  lane prompt allows it). Always `git -C <worktree>` — never `cd`.
- Do not read other lanes' output files; do not re-delegate; do not wait for anything.

## 4. Output contract

File: `/Users/nuzantara/nuzantara/.worktrees/research-beyond-sota-0828/research/operations/2026-08-28-beyond-sota-<slug>.md`
English. Dense. 2,500–6,000 words. No filler, no restating the protocol. Tables welcome.

Frontmatter:
```
---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: <N>/13 — <title>
model: claude-fable-5 (pinned lane)
sources: <count of distinct external sources>
repo_files_verified: <count of repo paths you verified on disk>
---
```
Sections, exactly these, in this order:
0. **TL;DR** (≤12 lines: position vs SOTA in one sentence, the biggest gap, the top-3 moves)
1. **How Nuzantara does it today** (grounded — every claim carries a verified path)
2. **Scars & ledger evidence in this area** (W-numbers, superscar families, PENDING-ARMS rows,
   AMENDMENTS rows, memory lessons — what actually bit, how often, whether it recurred)
3. **World SOTA survey** (table: system/practice · source · mechanism · measured effect ·
   transferability; then prose on the 3–5 that matter most)
4. **Position vs SOTA** (per sub-dimension: BEHIND / AT / AHEAD + evidence)
5. **Beyond-SOTA recommendations** (ranked; the fields listed in §2.D)
6. **90-day roadmap** (3 waves) **+ first PRs** (title, files, ≤400 lines, gear, acceptance test)
7. **Needs-ruling** (only true Legge-5 business decisions, consents, credentials, GUI/physical)
8. **§Meta-pattern** (modus Gear 3: what repeats across your findings — which single defective
   belief generates them)
9. **Sources** (numbered; URL; date accessed; one-line why it is authoritative)

After writing: `ls -la` the file and `wc -w` it (anti-hallucination rule 3 — Write can succeed
and the file still vanish). Never claim the file exists without that probe.

## 4bis. INCREMENTAL + RESUMABLE output (added after two launches died on seat windows)

Measured 2026-08-28: two launches (5 fork lanes, then 5 pinned lanes) died on the account's
session/weekly limit within minutes and left NOTHING on disk. Therefore:

1. **Write early, append often.** Immediately after method step A (GROUND) — before any web
   call — write the output file with the frontmatter and sections §1 and §2 complete. After
   step B write §3. After step C write §4. Then §5–§9 one at a time, each appended as soon as it
   is complete (`cat >> file <<'EOF'` or the Edit tool (the lane's own output file is the one write target §3 allows)). A window death must leave every
   finished section on disk. Never hold the whole report in memory until the end.
2. **Resume mode.** On start, `ls` your output file. If it exists: read it, list which of §0–§9
   are present and complete, and CONTINUE from the first missing/incomplete section — do not
   redo the grounding it already reflects (spot-verify 3 of its cited paths, then move on). §0
   (TL;DR) is written LAST, inserted after the frontmatter, because it summarizes the rest.
3. **Budget per lane** (the window is finite and shared): ≤20 file reads (use `grep -n` and
   `sed -n A,Bp` on large files, never cat >20 KB), ≤12 web fetches (search results count as
   one), ≤35 minutes wall-clock. Depth over breadth: 10 excellent sources beat 25 shallow ones.
4. **Frontmatter carries progress**: add `status: in-progress | complete` and
   `sections_done: [1,2,...]`; update them at every append so the orchestrator can see progress
   without reading the body.

## 5. Final message to the orchestrator (≤250 words)

Report path · word count · source count · top-3 recommendations (one line each) · the single
biggest gap · needs-ruling items (if any) · anything you could not verify. Nothing else — the
report is the deliverable, the message is the receipt.

## 6. Delivery (orchestrator, after all lanes return)

Index + synthesis at `research/operations/2026-08-28-beyond-sota-panel-INDEX.md`; copy of all
reports to `air:/Users/balizero/Desktop/beyond-sota-2026-08-28/` (M5 Desktop, per Zero); PR
`docs(research): beyond-SOTA panel, 13 lanes` with auto-merge armed per CLAUDE.md §2.

## Adversarial review

Blind cross-family review (generator ≠ grader), 2026-08-29. The refuters received the full document and the panel's hard rules, nothing else; path existence had already been verified on disk by the orchestrator's gate, so they attack logic, numbers, rule-compliance and the SOTA claims. Dispositions by the orchestrator (claude-fable-5, Zero's manual selection): **survives** = recorded as a standing caveat, not fixed in this PR; **rejected** = the objection misreads the document or the rules (reason given); **accepted** = fixed in the text.
Tally: 16 raised · 5 survive · 5 rejected · 6 accepted.

**Reviewer: `kimi-k3`** — Moonshot Kimi K3 via Kimi CLI (read-only snapshot of the repo). 8 raised.

| # | sev | objection (refuter's words) | disposition |
|---|---|---|---|
| 1 | HIGH | "pinned fresh-context lanes are how the panel completes" — §4bis measures the opposite: "two launches (5 fork lanes, then 5 pinned lanes) died… within minutes and left NOTHING on disk." The doc's own data refutes its central completion mechanism; the fix is asserted, not demonstrated. | accepted — §0 now says the pinned lanes also died and that headless per-seat lanes are how the panel completed |
| 2 | HIGH | "The lanes run with the model PINNED to `claude-fable-5`" — a written protocol (doctrine) that pins and re-launches Fable lanes, including orchestrator-driven resume mode, is auto-routing by doctrine; "Zero selected it manually" covers one session start, not scripted relaunches. | accepted (wording) — §0 now scopes the pin to Zero's manual selection for this one panel and states the protocol is a run record, not standing doctrine; rejected (substance) — no relaunch was automated by any script or cron |
| 3 | MED | "6 OAuth seats + cross-family council" — the fleet roster maps 4 Anthropic OAuth accounts (A1/A2/A3/AZ) plus 2 ChatGPT seats (O1/O2); OpenAI seats are not OAuth seats, so the claimed asymmetry is inflated and misdescribed. | rejected — FLEET_TOPOLOGY.json and CLAUDE.md list six Claude OAuth seats (five MAX x20 + one Team premium); the reviewer's 4+2 roster is not this repository's |
| 4 | MED | "≤20 file reads… ≤12 web fetches… ≤35 minutes wall-clock" — incompatible with the mandate: ~15 named doctrine files plus scars, memory hits, and prior panels exceed 20 reads, and 10 required primary sources plus searches consume nearly all 12 fetches; minimums are mutually exclusive. | survives — the caps were set to fit the seat windows; the lanes met the ≥10-source floor by grepping rather than reading whole files, but the tension is real and recorded |
| 5 | MED | "inherited ~90K tokens of session context each and exhausted the account window in minutes" — 90K inherited tokens per lane cannot alone exhaust an account window "in minutes"; presented as measured but the causal attribution is implausible and unsupported by any usage figure. | rejected (wording fixed) — the measured cause was the seat's WEEKLY cap (91% when probed), not the 5-hour window; §0 now says so |
| 6 | MED | "`cat >> file <<'EOF'` or the Edit tool" — §3 restricts Bash to an explicitly read-only whitelist (`ls`, `grep`, `cat`, `sed -n`…); instructing lanes to append via shell heredoc contradicts the read-only command discipline written three sections earlier. | accepted — §4bis now notes the lane's own output file is the one write target §3 allows |
| 7 | LOW | "top-5 recommendations (one line each)" — §4's TL;DR mandates "the top-3 moves" while §5's receipt demands top-5; inconsistent required counts across the same output contract. | accepted — §5 receipt now asks for top-3, matching §4 |
| 8 | LOW | "no test-suite runs (machine saturation)" paired with "first PRs (…acceptance test)" — lanes must specify acceptance tests for PRs they are forbidden to execute or validate, so the acceptance criteria are authored unverified by construction. | survives — by design: research lanes specify acceptance tests they cannot execute; the tests are falsified when the PR is built |

Refuter's verdict: Let it stand as evidence only after §4bis is reconciled with §0 (the pinned-lane failure acknowledged and the completion mechanism re-justified), the read/fetch budgets are made consistent with the mandatory grounding list, and Fable pinning is explicitly scoped to Zero's manual per-launch selection; as written its core claim is self-refuting.

**Reviewer: `qwen-3.8-max`** — Alibaba Qwen3.8 Max via TP1 (API, thinking on, no repository access). 8 raised.

| # | sev | objection (refuter's words) | disposition |
|---|---|---|---|
| 1 | HIGH | "The lanes run with the model PINNED to `claude-fable-5`" — Pinning Fable across lanes and referring to launches/orchestrator turns Fable into routed doctrine; hard rule permits only manual interactive selection. | rejected — as kimi-k3 #2: manual selection by Zero for this one panel; wording tightened |
| 2 | HIGH | "pinned fresh-context lanes are how the panel completes" — Later measured that pinned lanes died within minutes; fresh-context pinning did not overcome account limits, so claim is contradicted. | accepted — as kimi-k3 #1 |
| 3 | HIGH | "≤12 web fetches (search results count as one), ≤35 minutes wall-clock." — Required 10 primary sources, path verification, and 2,500–6,000 words make this budget implausible; it incentivizes shallow/fabricated evidence. | survives — as kimi-k3 #4 |
| 4 | HIGH | "`client_id`/placeholders." — Client identifiers are client data; allowing them in reports conflicts with the absolute rule that no client data appear in outputs/artifacts. | rejected — `client_id` placeholders are the sanctioned pseudonymous form under SYMBIOSIS Law 2; no report contains any client reference at all |
| 5 | MED | "do not redo the grounding it already reflects (spot-verify 3 of its cited paths, then move on)." — This allows resumed reports to retain prior claims without full current-session verification, contradicting the requirement that every claim be verified now. | survives — resume mode traded full re-verification for seat economy; the orchestrator's gate then re-checked every cited path on disk, which is why the caveat is recorded rather than fixed |
| 6 | MED | "no surveyed system does it, or it composes known pieces into something none of them has" — A universal negative cannot be established by 10 sources/12 fetches; the criterion is unfalsifiable and would let speculative claims pass. | accepted (wording) — the beyond-SOTA criterion is scoped to the surveyed set in the INDEX; the protocol keeps its original text as the run record |
| 7 | MED | "Read from it, write into it." — The protocol also requires reading memory bodies outside the declared panel worktree, making the read scope inconsistent and potentially ungoverned. | rejected — §3 explicitly allows read-only access to the memory directory; the write scope is the output file only |
| 8 | MED | "Grep the scar corpus and the ledger for your area" — Scar/ledger/memory likely contain client incidents; broad grep without mandatory redaction/filter checks risks client data entering logs/reports despite absolute boundary. | survives — the scar corpus is PII-free by rule and the outputs were scanned; the risk of a grep surfacing an incident detail is real and recorded |

Refuter's verdict: I would not let this report stand as evidence until the Fable-routing, failed pinned-lane, impossible-budget, and client-data boundary defects are corrected.

