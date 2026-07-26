---
date: 2026-07-19
domain: operations
client_case: none — arsenal revision on Zero's order ("Kimi è entrato nel team… togli DeepSeek, rivedi il nostro arsenale")
adversarial_review: codex
sources:
  - ON-DISK M5 (this session): /Applications/Kimi.app (Kimi Desktop 3.1.2) · ~/Library/Application Support/kimi-desktop/kimi-agent/kimi-work-models-cache.json (model catalog) · daimon-share/config.toml + daimon/ (runtime) · sessions/hosted-logical/conversations.sqlite + wire.jsonl (the real session studied) · ~/.kimi-code/bin/kimi 0.27.0 — 1-token K3 probe PONG re-run by this author
  - PR #2791 "feat(arsenal): Kimi seat (K3 + kimi-for-coding 2.7, Allegro flat sub)" — the Pro twin session's probe+doctrine wiring (arsenal_probe kimi seat, SKILL.md §Arsenal, runbook), read this turn
  - https://www.tomshardware.com/tech-industry/artificial-intelligence/moonshot-releases-2-8-trillion-parameter-kimi-k3 + https://venturebeat.com/technology/chinas-moonshot-ai-releases-kimi-k3-the-largest-open-source-model-ever-rivaling-top-u-s-systems (K3 release 2026-07-16, 2.8T MoE open-weight)
  - https://simonwillison.net/2026/Jul/16/kimi-k3/ + https://aireleasetracker.com/model/moonshot/kimi-k3 (tracker-reported benchmarks: BrowseComp 91.2, MCP Atlas 84.2, GDPval-AA v2 3rd behind Fable 5 Max / GPT-5.6 Sol Max; over-proactivity caveat)
  - https://www.marktechpost.com/2026/06/12/moonshot-ai-releases-kimi-k2-7-code-a-coding-model-reporting-21-8-on-kimi-code-bench-v2-over-k2-6/ + https://platform.kimi.ai/docs/guide/kimi-k2-7-code-quickstart (K2.7-Code 2026-06-12, Kimi Code CLI default, −30% thinking tokens)
  - https://decrypt.co/370954/moonshot-ai-kimi-work-300-agents-desktop + https://www.kimi.com/help/membership/membership-pricing (Kimi Work desktop, Agent Swarm; plans Allegretto $39 / Allegro $99 / Vivace $199)
  - .claude/skills/modus/SKILL.md §Arsenal · CLAUDE.md §5/§6 · scripts/check_adversarial_review.py KNOWN_SEATS (pre-change census)
---

# Kimi enters the arsenal; DeepSeek retires — the 2026-07-19 workflow revision (M5 leg)

Zero's mandate: Kimi (K2.7, K3) è entrato nel team — study it, study its live session on M5,
integrate it into the workflow, retire DeepSeek. **Twin-race note (resolved, scar #5):** while
this study ran, the Pro Fable session opened **PR #2791** (arsenal_probe `kimi` seat + modus
§Arsenal + CLAUDE.md §5 + runbook, CLI armed on Pro AND M5). This capture **concedes those
surfaces to #2791** and carries the complementary half: the M5 desktop-session study, the Kimi
Work surface map, the **DeepSeek removal** (Zero's explicit order — #2791's cascade still names
DeepSeek; coordinated via PR comment), the R1 seat census change, and the PII boundary flag.

## 1. What Kimi concretely is (on-disk + multi-source web)

**On M5:** Kimi Desktop **3.1.2** (`/Applications/Kimi.app`), an Electron app embedding an
agentic runtime ("daimon") with a `kimi-code` kernel, an MCP **client**, a 31-skill library
(ad-creative, campaign-plan, copywriting, kimi-slides, legal-risk-assessment, pricing-strategy,
seo-audit, webapp-building, docx/xlsx/pdf, widgets), and a Widget/canvas artifact system. Model
catalog exposed by the app (`kimi-work-models-cache.json`, read this session):

| Cache key | Display | Context | Capabilities | Role |
|---|---|---|---|---|
| `k3-agent` | **K3** | **1,000,000** | thinking, image_in, **video_in**, dynamic tools | flagship chat+agent |
| `k3-agent-ultra` (modelId/alias `k3-agent-swarm`) | **K3 Swarm** | 1,000,000 | same | "massive search, batch processing" — multi-agent swarm |
| `k2d6-agent` | K2.6 Agent | 262,144 | thinking, image, video | research/slides/websites/docs/sheets artifacts |
| `k2p6` (daimon `kimi-code` kernel) | coding model | 262,144 | thinking, image, video | the work-function coder |

Zero's live desktop conversation runs `k3-agent` at thinking **max**; account capacity
`extended` (XL 1M context available — Allegro-tier features on; flat subscription, no per-token
key). **Headless:** the standalone `kimi` CLI (`~/.kimi-code/bin/kimi` **0.27.0**, OAuth
device-code, no API key) is **armed on M5** — this author re-ran the 1-token probe this turn:
`kimi -p … -m kimi-code/k3` → `PONG`. #2791 reports the same on Pro (author-reported there;
probed by its own session).

**Web (2026-07, tracker-reported figures):** **K3** (2026-07-16) is a 2.8T-param open-weight MoE
(16/896 experts, Kimi Delta Attention, ~6.3× faster decode at 1M ctx). BrowseComp **91.2%** (best
published at release), MCP Atlas 84.2, HLE-with-tools 56.0, #1 LMArena Frontend Code Arena (6/7
domains, ahead of Fable 5 and GPT-5.6 Sol), AA Coding Index 76.24; GDPval-AA v2 **3rd overall**
behind only Fable 5 Max and GPT-5.6 Sol Max. **K2.7-Code** (2026-06-12, open-weight, Modified
MIT): +21.8% Kimi Code Bench v2 vs K2.6, −30% thinking tokens; the standalone CLI's default
coding model. Evaluator-reported deployment caveat: K3 is **excessively proactive on ambiguous
tasks** — scope tightly, verify independently.

## 2. How it works here (the M5 desktop session, from wire.jsonl — read by this author)

One completed conversation (`8be3425d…`, 2026-07-19, model k3-agent, workspace
**`/Users/balizero/nuzantara`** — the MAIN checkout). Zero asked "cosa potresti fare per il mio
sistema con la funzione work?". Kimi, in **yolo permission mode**, autonomously: (1) ran
fleet-aware Bash (hostname→pro/mini ssh case logic — it absorbed our conventions); (2) called
**five of our production MCP tools** (`lam_grounding_snapshot`, `get_agents_status`,
`check_health_detailed`, `get_client_stats`, `get_intel_metrics`); (3) loaded its widget skills
(11 reference reads) and built+validated+showed a live "Nuzantara · Mission Control" HTML widget
(16KB). Usage: 111k cache-read tokens, 829 out. Its MCP client is wired to **our stack**:
`server-github`, `playwright`, `server-postgres` on the **readonly proxy**
(`nuzantara_readonly@localhost:15432`), plus Kimi-native tools (imagegen, audiogen, webbridge,
sec_edgar, scholar, yahoo_finance, world_bank, IMF). (These session-anatomy facts are from this
author's direct reads of the local artifacts; an external reviewer cannot re-verify the volatile
parts and graded them author-reported — see §Adversarial review.)

**Risk flags (each with an ops/ledger action):**
- **PII boundary (HARD).** Kimi is a Chinese cloud stack (Moonshot) — same absolute rule DeepSeek
  had: **no client PII ever** (UU PDP / Law 2). Its MCP surface today includes the prod readonly
  DB and `nuzantara-mcp` client tools (`get_client`, `list_clients`…): a Kimi query touching
  client rows would egress PII to Moonshot. The observed session called only aggregate/health
  tools, but nothing structural prevents worse. **Interim session-side rule (active now): any
  prompt we hand Kimi (CLI or desktop) must not require `server-postgres`, CRM/client, or
  raw-record tools — aggregate/health/intel/KBLI surfaces only.** Restricting/unplugging the MCP
  config itself is the operator's (`operator[consent]`, ledgered) — not silently done for him.
- **Sibling discipline (#5).** Workspace = main checkout, in yolo mode — the combination our
  worktree discipline forbids for agents. Recommend the operator point Kimi work-mode at
  `.worktrees/ops-kimi-<task>` lanes (Antigravity precedent). Ledgered.
- **Secret hygiene (#4).** `daimon-share/config.toml` carries the app's own coding-gateway key in
  cleartext; permissions verified 0600 this session (value not reproduced anywhere).

## 3. The arsenal revision (this PR + #2791 together)

**DeepSeek OUT (Zero's order + the record):** HTTP 402 balance-dead at two consecutive councils
(2026-06-30, 2026-07-02); already demoted behind GLM on 2026-07-03. This PR removes it from the
R1 seat census (`check_adversarial_review.py`), the §6 panel line, and the wr2 agent-def
mentions; the modus §Arsenal cascade edit is **coordinated with #2791** (whose draft still names
DeepSeek — flagged to the twin via PR comment, per Zero's newer order). The **local**
`deepseek-r1:32b` Ollama weights are NOT the API seat — they stay (offline reasoning, $0).

**Kimi IN — three roles, two surfaces:**

| Role | Model/surface | When |
|---|---|---|
| **Cross-family refuter / R1 seat (headless)** | `kimi` CLI (`-m kimi-code/k3`, or `kimi-for-coding` for code) — **armed on M5+Pro** | Councils, R1 adversarial reviews, panel seat. Refuter cascade (post-#2791, DeepSeek stripped): **GLM 5.2 → Kimi K3 → Codex** per #2791's ordering — probe-then-trust per seat, as ever. Mini login = `operator[consent]` (#2791 ledger). |
| **Agentic web-research / massive sweep / sheets-batch** | K3 / K3 Swarm via desktop (operator-driven) | BrowseComp-class deep research, competitor/IG sweeps, spreadsheet batch — the independent second-sweep organ. NON-PII only. |
| **Frontend/UI + artifact builder (verified-arm)** | K3 / K2.6-Agent / kimi-code via desktop work-mode | Antigravity-model: Kimi builds (sites/slides/docs/UI), **the session independently verifies, tests, commits** — Kimi never self-merges; brand surfaces still pass the WR2 constitution gates. |

**Unchanged spine:** Fable 5 architect/final-gate (never cascaded) · Sonnet 5 implementer ·
Haiku grunt · Codex GPT-5.6 red-team+sandbox · Gemini `agy` width/ingestion · GLM 5.2
second-brain · Ollama local PII/$0 · NotebookLM ground truth. Operational note (timeboxed, not a
durable conclusion): Codex `sol` at high effort exceeded the 590s harness cap **twice today** on
multi-file reviews — use `terra` medium as the R1 default for now, log latencies, and on a
timeout record the failure and escalate along the declared cascade; never silently downgrade.

**Panels (corrected arithmetic):** the pre-approval panel = **three external LLM seats** (Gemini
`agy` + Codex GPT-5.6 + Kimi K3 — GLM 5.2 substitutes if a seat is dead) **+ the Fable
orchestrator + optional NB-1 ground-truth verifier** (NB is retrieval, not an LLM seat). The
historical label "4-LLM panel" stays as the section name; the composition line is now honest.

**Cost posture:** Kimi = Zero's flat subscription (like MAX / ChatGPT Pro / AI Ultra) —
free-first/OAuth-first preserved. The per-token `platform.kimi.ai` API is NOT enabled; any
per-token key would need Zero's explicit authorization. The desktop app's bundled gateway key is
the app's own — never extracted or reused.

## 4. Recommendation (ONE, actionable)

Adopt the split shipped across #2791 (probe + doctrine) and this PR (DeepSeek removal + R1 seats
+ panel line + this capture), then close the two ledgered operator gates: **(a)** Kimi MCP
PII-surface restriction (`operator[consent]` — until then the session-side refusal rule above is
the guard); **(b)** Kimi desktop workspace → `.worktrees/ops-kimi-*`. Expected: a 3-family
headless refuter cascade led by living seats (GLM/Kimi/Codex), panels with true 3-LLM-seat
diversity plus NB verification, a BrowseComp-91-class research organ, and zero marginal cost —
with the PII boundary explicit instead of implicit.

## Adversarial review

Reviewed by Codex `gpt-5.6-terra` (medium effort), generator≠grader — the author did not grade
its own claims; the reviewer was told to ignore the author's placeholder section. Real verdicts,
all applied:

- **On-disk catalog — STANDS-WITH-CORRECTION:** reviewer independently verified
  `kimi-work-models-cache.json` exists with `k3-agent` maxContextSize 1,000,000; caught the Swarm
  row mislabeled (`k3-agent-swarm` is the modelId/alias — the cache **key** is `k3-agent-ultra`).
  Fixed in §1.
- **Session anatomy — STANDS-WITH-CORRECTION:** wire.jsonl anatomy, yolo mode, MCP wiring are
  author-reported reads of local artifacts the reviewer could not independently re-verify —
  now attributed as such in §2 (not "verified" tout court).
- **DeepSeek retirement — STANDS-WITH-CORRECTION:** sound, but the draft's present-tense
  "docs in this PR / as §Arsenal now reads" was false at review time (repo still named DeepSeek).
  Fixed: §3 states what THIS PR changes vs what is coordinated with #2791; adoption language is
  tied to the actual diffs + the checker's self-test passing.
- **Kimi refuter lead — STANDS-WITH-CORRECTION:** the reviewer demanded the seat not be routed
  on a desktop catalog alone (W81 esiste≠armato) and precise acceptance criteria (CLI installed,
  login, explicit model selection, 1-token probe, model identity). Superseded-and-satisfied by
  events: #2791 armed the CLI on Pro+M5 and this author re-ran the M5 K3 probe (PONG) this turn —
  the criteria are met with live evidence, not catalog inference.
- **`terra` R1 default — STANDS-WITH-CORRECTION:** two same-day timeouts justify a *timeboxed
  operational* default, not a durable performance claim; timeout-handling now specified. Fixed in §3.
- **"4-LLM panel / true 4-seat diversity" — CADE:** the proposed panel is three external LLM
  seats; NB-1 is not an LLM and modus caps external seats at three. Fixed: composition rewritten
  as 3 LLM seats + orchestrator + optional NB; the "regain 4-seat diversity" claim deleted.
- **PII consent — STANDS-WITH-CORRECTION:** do not silently reconfigure the operator's MCP setup,
  but waiting must not leave the agent free to invoke PII-bearing tools — an interim session-side
  refusal rule is now explicit in §2, with config restriction staying `operator[consent]`.
