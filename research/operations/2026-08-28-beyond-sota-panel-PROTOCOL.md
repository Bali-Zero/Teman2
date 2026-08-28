---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
type: protocol
mandated_by: Zero (interactive Pro session, /model claude-fable-5, max effort)
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
path (Legge 5). The lanes run with the model PINNED to `claude-fable-5` (fresh context — the 5 fork lanes of the
first launch inherited ~90K tokens of session context each and exhausted the account window in
minutes; pinned fresh-context lanes are how the panel completes). Each lane executes directly and
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
   is complete (`cat >> file <<'EOF'` or the Edit tool). A window death must leave every
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

Report path · word count · source count · top-5 recommendations (one line each) · the single
biggest gap · needs-ruling items (if any) · anything you could not verify. Nothing else — the
report is the deliverable, the message is the receipt.

## 6. Delivery (orchestrator, after all lanes return)

Index + synthesis at `research/operations/2026-08-28-beyond-sota-panel-INDEX.md`; copy of all
reports to `air:/Users/balizero/Desktop/beyond-sota-2026-08-28/` (M5 Desktop, per Zero); PR
`docs(research): beyond-SOTA panel, 13 lanes` with auto-merge armed per CLAUDE.md §2.
