---
title: "THE FLEET ORDER — binding spec for the Nuzantara LLM fleet (conductor: Fable 5)"
date: 2026-08-10
author: Fable 5 interactive session (M5) — conductor, per Zero's mandate 2026-08-10
status: v1.3 — panel-amended (GLM 6 findings · Gemini 8 · Codex 12 · Kimi ABSENT quota-dead; panel = 3 external families, quorum met) + Zero account-estate resolution (3 MAX + 1 Team Premium, no A4) → landing PR
adversarial_review: "3-family panel 2026-08-10 (GLM 5.2 refuter · Gemini agy constructive · Codex red-team); 26 findings, 24 accepted as inline amendments, dispositions in §10"
supersedes: nothing — CONSOLIDATES harness-v2-teman2-2026-08-09.md + FLOTTA-LLM-ruoli-categorici + quattro-gruppi-e-continuita + FLEET_TOPOLOGY v1.1, and CORRECTS them against repo ground truth verified on disk 2026-08-10
ratification: Zero ratified the harness/roster/continuity design 2026-08-09 and delegated this spec's authority 2026-08-10 ("hai potere di scrivere la tua spec per questo nuovo ORDINE")
landing_path: research/operations/2026-08-10-fleet-order-spec.md
---

# 0. What this is

The single binding document for **who sits where** in the Nuzantara LLM fleet: categorical
positions for every seat, the account map, the continuity ladders, and the gate taxonomy.
Orchestrators (conductors) and actors (seats) respect these positions categorically.
The harness mechanics (Evidence Pack, verdicts, floors) live in the harness-v2 doc and are
incorporated by reference; this spec adds the corrections that make the package true on disk,
plus Zero's rulings of 2026-08-10.

**Precedence (panel fix Codex#1):** where this spec and the consolidated docs disagree, THIS
spec wins. Points explicitly overridden: (a) harness-v2 §6 "Seat Fable morto ⇒ SUSPEND, mai
downgrade" **for the Gear-3 verdict gate only** — superseded by Zero's 2026-08-09 ruling
(Opus-max `gate_degraded` fallback; the final on-disk and WR2 gates keep SUSPEND); (b) harness-v2
§6 "Gear 2 chiude con verdetto Opus" — refined by AGENTS §17.1 family-diversity: the Gear-2
verdict seat must be from a different family than the main builder (§3.2 `gate_gear2`);
(c) FLOTTA roster "GLM = CANDIDATE" — superseded by the dual-door status (§2.5/§2.6);
(d) FLEET_TOPOLOGY v1.1 refuter chain — superseded by §3.2.

**Zero's rulings folded in (2026-08-10):**
1. AZ (Claude Team Premium) and O2 (second ChatGPT Pro) = `zero@balizero.com` — NOT zero@gmail.com.
2. GLM: drain the remaining z.ai quota on high-value work (program in §5), then transition
   the seat to the Alibaba Token Plan (~$68 tier per Zero; PROBE-1-residual confirms).
3. DeepSeek: **re-admitted via Token Plan, PROBATION.** History for the record: the seat was
   retired 2026-07-19 by Zero's own order because the *standalone per-token API seat* was
   repeatedly HTTP-402 balance-dead ("never top up" applied to that seat) — it was an economics
   death, not a quality or trust verdict. The Token Plan serves DeepSeek on flat monthly
   credits, which removes the death cause. Zero reopened it 2026-08-10. PII boundary unchanged
   and absolute (Chinese cloud rules, §2 hard NOs).

# 1. Ground truth this spec is built on (verified on disk, 2026-08-10)

- **Nothing from the 2026-08-09 Cowork package is in the repo** (local or origin/main).
  The Desktop dossier is the delivery vehicle; the landing PR starts from those copies.
  The stray "+Imported Claude Cowork" block in the M5 working-tree AGENTS.md is Cowork
  residue with dead paths — discard, never commit.
- **Token Plan is live and configured**: `~/.qwen/settings.json` (now 0600, was 0644 with the
  key in clear — fixed this session) carries `BAILIAN_TOKEN_PLAN_API_KEY` against
  `token-plan.ap-southeast-1.maas.aliyuncs.com` with 15 models: qwen3.8-max-preview,
  qwen3.7-max, qwen3.7-plus, qwen3.6-plus, qwen3.6-flash, deepseek-v4-pro, deepseek-v4-flash,
  deepseek-v3.2, kimi-k2.7-code, kimi-k2.6, kimi-k2.5, glm-5.2, glm-5.1, glm-5, MiniMax-M2.5.
  PROBE-1's "generate key + enumerate models" is DONE; burn-rate + credits endpoint remain.
- **GLM is ARMED today** via the z.ai Coding Plan (`scripts/claude-glm.sh`, Keychain
  `glm-coding-plan-token`, re-armed 2026-07-26, Zero promoted it first-call refuter 2026-07-19,
  used live for deploy rerouting 2026-08-08). The dossier's "GLM = CANDIDATE" was stale.
- **Qwen Code CLI seat already registered**: PR #3884 (2026-08-09) added `qwen-cloud-code` to
  `scripts/arsenal_probe.py` as UNARMED, keychain-gated (`qwen-cloud-code-token`), with a
  Gear-3 council-reviewed integration study (research/operations/2026-08-08-qwen-code-seat…).
- **Cost-breaker gap (W107 class)**: gemini budget $10/24h would have caught the 26/07
  ($12.53) and 28/07 ($16.22) spike days, but `genai_client.py` — the spender that wrote those
  ledger rows — never consults the breaker (armed since 2026-06-07). The threshold is fine;
  the coverage is not. Open PR #3914 works the same surface: coordinate, don't collide.
- **Claude multi-profile infra already exists on M5**: `~/.claude` (Team seat),
  `~/.claude-kaiser`, `~/.claude-acct2/3/4`, `~/.claude-zero-team` — the `CLAUDE_CONFIG_DIR`
  pattern proven by claude-glm.sh. cswap adds auto-rotation + window introspection, not the
  capability itself.

# 2. THE ORDER — categorical positions

Legend: **ARMED** = load-bearing allowed · **PROBATION** = usable, not load-bearing, burn/quality
under measurement · **UNARMED** = registered, awaiting arming steps · **RETIRED** = do not use.

## 2.1 Anthropic — government and hands (MAX OAuth + Team, CLI only, SDK banned)

| Seat | Position | Stage | Status |
|---|---|---|---|
| **Fable 5** | **The Judge** — final on-disk gate + Gear-3 harness verdict gate + conductor when Zero opens a Fable session. Strategy only by motivated exception (gate allowance has absolute precedence) | Gate | ARMED |
| **Opus 5** | **The Architect** — interactive default, strategy, client quotes, Gear-2 verdicts (when builder ≠ Anthropic — §3.2), **Gear-3-harness-verdict fallback ONLY, forbidden for the final on-disk and WR2 gates** (panel fix Codex#9) | Strategy, Gate-2 | ARMED |
| **Sonnet 5** | **The First Builder** — primary implementer, subagent fan-out | Build | ARMED |
| **Haiku 4.5** | **The Foot Soldier** — triage, intake synthesis, classification above the deterministic floor, light batch | Intake | ARMED |

## 2.2 OpenAI — the adversarial sword (ChatGPT Pro ×2, sandbox only)

| Seat | Position | Stage | Status |
|---|---|---|---|
| **Codex Sol** | **The Prosecutor** — refuter #1: security, regressions, assumptions | Refute | ARMED |
| **Codex Terra/Luna** | **The Second Builder** — alternative patches, Alembic migrations, tests | Build | ARMED |

Slugs `-m sol/terra/luna` are DEAD on ChatGPT accounts (2026-07-21): the account's default
model carries the seat; do not pass `-m` until a probe proves slugs live again.
**Single-role-per-account rule (panel fix Codex#2):** with slugs dead, one account serves ONE
role at a time — O1=refuter, O2=builder are the standing assignments; using O2 as Sol-backup is
an explicit, logged role switch (config change + effective-model probe recorded in the task
evidence), never an implicit fallback.

## 2.3 Google — senses and exploration (AI Ultra)

| Seat | Position | Stage | Status |
|---|---|---|---|
| **Gemini via agy** | **The Explorer** — normative search (Claude hallucinates regulations), multi-app explore, pre-deploy red team, 2nd strategy voice | Strategy, Refute | ARMED |
| **NotebookLM** | **The Oracle** — documentary ground truth; sources, never decisions | Intake, Verify | ARMED |
| **Antigravity** | **The Fenced Arm** — delimited tasks in fresh worktrees; the session re-verifies. Four NOs: architecture, real PII, deploy, choosing which bugs matter | Build | ARMED |
| **Jules** | async worker via PR only | — | CANDIDATE |

Gemini CLI is deprecated (2026-06-18): the Google door is agy. Google overage credits are
per-token-like → Zero's GO required.

## 2.4 Moonshot — the reviewer (Allegro flat, PRIMARY door for K3)

| Seat | Position | Stage | Status |
|---|---|---|---|
| **Kimi K3** | **The Reviewer** — refuter #2, 1M-context auditor, multimodal Evidence-Pack verifier (screenshots/PDF; **multimodal fallback when K1 is down: Gemini via agy** — panel fix GLM#2). Zero-trust fence (AISI sandbox-escape incident): no credentials, no unfenced network, worktree always | Refute, Evidence | ARMED (observed 403 quota-dead for the current Allegro cycle on 2026-08-10 — refreshes next cycle) |
| **kimi-for-coding** | alternative frontend builder | Build | ARMED (never hot-zone alone) |

The Token Plan also lists kimi-k2.5/2.6/2.7-code — **older than K3**: the Allegro sub remains
the load-bearing Kimi door; TP1 Kimi models are second-line redundancy only.

## 2.5 Alibaba Token Plan (TP1, Singapore) — the unified eastern wing

One key, five families. **All PROBATION** until PROBE-1-residual (burn-rate + credits endpoint).
Access doors: Qwen Code CLI (interactive/agentic; UNARMED seat `qwen-cloud-code` pending Zero's
ratifications from the 8/8 study) and direct OpenAI/Anthropic-compatible API (pipelines).

| Seat | Position | Stage | Status |
|---|---|---|---|
| **Qwen 3.8 Max** | **The Third Pole** — 3rd strategy voice in panels; rigorous-instruction pipeline executor (IFBench); non-PII doc/video mass engine; fenced GUI-agent. **Never compliance-exact extraction without independent verification** (documented hallucination weakness — our trade IS exact compliance) | Strategy, Build, Refute | PROBATION |
| **Qwen 3.7 Max/Plus, 3.6** | **The Reserve** — economic second opinions, second-line batch | — | PROBATION |
| **GLM 5.2** | **The Counter-Builder** — counter-implementations for Gear-3 diffs, long-horizon refactors, spikes. `clear_thinking:false` mandatory in agent use. This is the SAME seat as §2.6 — one position, two doors | Build, Refute | ARMED via z.ai (until quota ends) / PROBATION via TP1 |
| **DeepSeek v4-pro/v4-flash/v3.2** | **The Second Reasoner** — reasoning second-opinion, refuter reserve, math/logic chains. Re-admitted 2026-08-10 (ruling §0.3) | Refute (reserve) | PROBATION |
| **MiniMax M2.5** | **The Grinder** — throughput: repetitive tests, docs, mechanical batches; quality gate: a sample of every lot verified by an Anthropic seat | Build | PROBATION (PROBE-4) |
| **Wan** | media-gen radar for WR2 | — | CANDIDATE |

**Hard NOs for the whole wing (no exceptions):** client PII (UU PDP / Law 2 — PII intake is
SEA-LION/local), client-facing outputs, merge/deploy, final gates, credentials in their env.
Boundary clarification (panel fix GLM#6): "client-facing outputs" means **producing or
certifying** content that reaches a client — *reading* a diff that contains channel templates
for refutation is allowed, provided real-client PII is redacted before egress (that boundary
stays absolute). Credential clarification (panel fix Codex#11): "no credentials in their env"
means no NUZANTARA/infra credentials (Fly, Vercel, GitHub, DB, `.env*`) in the model-visible
environment; the seat's OWN provider token lives in the broker layer (Keychain → shim env var),
outside the model's context — that is how the seat operates at all.

## 2.6 GLM z.ai door (until quota exhausted)

`claude-glm -p "…"` (shim: Keychain token + `CLAUDE_CONFIG_DIR=~/.claude-glm`). First-call
refuter for compact reviews (Zero 2026-07-19), agentic file reader. When the z.ai quota dies:
do NOT renew (Zero 2026-08-10) — the position transitions to TP1 `glm-5.2` after its burn-rate
is measured. The `claude-glm` shim then gets repointed or retired; PENDING-ARMS line at landing.

## 2.7 Local / Sovereign (Ollama Pro+Mini — MODEL_TOPOLOGY.json unchanged)

Positions confirmed as in the roster doc: qwen3.5:9b Chronicler (cron, `think:false`, no tools) ·
qwen3:8b Toolsmith · gemma3:27b Translator · gemma4:26b Librarian (Pro only) ·
qwen2.5vl:7b **The Eye** (ONLY authorized vision/OCR) · SEA-LION v4 32B **The Customs Officer**
(PII intake, first door for client documents) · deepseek-r1:32b Local Thinker ·
qwen2.5:7b / qwen3:4b Mini keeper & sentry. PII lanes NEVER leave this tier — fail-closed, queue.

# 3. Accounts & continuity

## 3.1 Account map (Zero-confirmed 2026-08-10)

| Slot | Identity | Plan | Home lane |
|---|---|---|---|
| A1 | antonellosiano@gmail.com | Claude Max 20x | interactive/architect daily driver |
| A2 | kaiser198719871987@gmail.com | Claude Max 20x | subagents/build + Cowork cloud |
| A3 | applevisionpro1987@gmail.com | Claude Max 20x | cron/batch — **designated donor**. Donor semantics (panel fix GLM#1/Gemini#8): scheduler-level pause — the cron auto-pause hook stops SCHEDULING new jobs on A3; in-flight requests finish; nothing is killed. A3 therefore hosts only preemptible work (grunt/batch), never primary builds |
| AZ | **zero@balizero.com** | Claude Team **Premium** | **GATE PRIMARY** — the dedicated Fable weekly allowance lives here |
| O1 | antonellosiano@gmail.com | ChatGPT Pro | refuter primary (Sol) |
| O2 | **zero@balizero.com** | ChatGPT Pro | builders (Terra/Luna) + Sol backup |
| G1 | Google AI Ultra (account email → §8; credential: agy OAuth on disk) | — | agy / NotebookLM / Antigravity |
| K1 | Kimi Allegro flat (Moonshot device-code auth, `~/.kimi-code`) | — | K3 + kimi-for-coding |
| TP1 | Alibaba Token Plan (~$68 tier, Singapore; key: `~/.qwen/settings.json` 0600 — account email → §8) | monthly credits | the §2.5 wing |

Slot identity note (panel fix Codex#3): G1/K1/TP1 rows above name PLANS; the owning account
emails are an §8 operator item — record them at cswap/collector arming so revocation targets
are defined.

**Resolved (Zero, 2026-08-10):** the Anthropic estate is exactly **3 MAX (A1/A2/A3) + 1 Team
Premium (AZ)**. No A4 exists. The "QUAD MAX" wording in the global home CLAUDE.md is stale —
aligned at landing. Residual session check: verify the cron wrapper tokens
(`CLAUDE_CODE_OAUTH_TOKEN_1/2/3` in `~/.nuzantara-secrets.env`) all authenticate against LIVE
slots (the 2026-07-22 planned one-MAX closure appears absorbed; a token pointing at a closed
slot is a silently-dead cron lane, W104 class).

**Conventions decided by this spec:**
- Second Codex home = `~/.codex-o2` (aliases codex-o1/codex-o2). The stray `~/.codex-acct2`
  mention in the global home CLAUDE.md gets aligned at landing (home-file edit, session task).
- Local profile dirs → seats (first seat_map.json; verify at cswap arming): `~/.claude`→AZ ·
  `~/.claude-kaiser`→A2 · `~/.claude-acct2`→A1 · `~/.claude-acct3`→A3 ·
  `~/.claude-acct4`→**orphan** (no seat exists — verify and retire at arming) ·
  `~/.claude-zero-team`→legacy AZ duplicate (verify, likely retire).
  Note (panel disposition of Gemini#6, REJECTED fix): `~/.claude`=AZ on M5 is Zero's
  DELIBERATE 2026-07-22 decision (M5 is the coding station on the Team seat) — do not "fix" it
  by remapping; the Fable weekly allowance is protected by MODEL ROUTING (interactive default =
  Opus, Fable only for gates/motivated exceptions — rulings 2026-07-22/25), not by profile
  segregation.
  **The whole profile→seat mapping is UNARMED until fingerprinted** (panel fix Codex#4): at
  cswap arming, run `claude auth status` under each `CLAUDE_CONFIG_DIR` and record the
  authenticated identity next to the mapping — a presumed mapping can impersonate or drain the
  gate account. **Donor mechanism is likewise UNARMED today** (panel fix Codex#5): the cron
  auto-pause hook does not exist yet (PENDING-ARMS); until it lands, donor rotation is a manual
  act, and pausing never refunds quota already burned — the donor's value is the fresh window,
  which is why A3 carries only preemptible lanes.

## 3.2 Continuity ladders (unchanged in shape, corrected in content)

Escalate IN ORDER, each hop logged in the task evidence: (1) rotate account, same model →
(2) substitute model within the role → (3) cross-family, marked `degraded_execution:true` →
(4) queue in PENDING-ARMS, never silent-stop.

Seat names in chains are POSITIONS, not invocation slugs (panel fix GLM#4): "codex-sol" names
the O1/O2 refuter seat — never pass `-m sol` (§2.2, slugs dead).

**Family-exclusion rule (panel fix Gemini#1, HARD):** a model family that built OR
counter-built on a task is excluded from that task's refuter chain — the ladder skips it and
takes the next hop.

**Quorum semantics, exact (panel fix Codex#6):** ZERO available refuters → the task QUEUES and
never reaches the gate (v1.1 rule, unchanged). Refutation happened but the 2-family diversity
could not be met → pack marked `degraded`, the gate sees it and weighs it. `degraded` is for
diversity shortfall only, never a license to skip refutation. **PROBATION seats carry
`eligible_for_quorum: false`** (panel fix Codex#7): they may add a third opinion, they never
count toward the 2-family quorum until promoted ARMED.

Corrected role chains (deltas vs FLEET_TOPOLOGY v1.1 → v1.2 at landing):
- **refuter**: codex-sol(O1,O2) → **glm-5.2 (z.ai door while alive — Zero's first-call ruling
  2026-07-19 for compact reviews; omitted in v1.1, restored here)** → kimi-k3(K1) →
  gemini-agy-redteam(G1) → **deepseek-v4-pro(TP1, PROBATION reserve)**. Gear-3 quorum: 2
  refuters from 2 different families, else `degraded`.
- **gate_gear2** (panel fixes Gemini#3 + Codex#8): FAMILY-CONDITIONAL — the verdict seat must
  be from a different family than the main builder (AGENTS §17.1). Builder=Anthropic (usual
  Sonnet case) → gemini-agy(G1) → codex(O1). Builder=non-Anthropic → opus-5(A1,A2) first.
  Builder seats NEVER issue verdicts — chain exhaustion queues the PR, it does not route the
  verdict to a builder.
- **builder_primary**: sonnet-5(A2) → codex-terra/luna(O2,O1) → glm-5.2(z.ai→TP1). (A3 removed
  — donor lanes host only preemptible work, §3.1.)
- **reasoner** (panel fix Gemini#7): deepseek-r1:32b(local) → deepseek-v4-pro(TP1) → opus-5(A1).
- **grunt/batch**: haiku(A3,A2) → local ollama → minimax-M2.5(TP1, post-PROBE-4).
- **doc_mass_nonpii**: qwen-3.8-max(TP1) → kimi-k3(K1) → gemini(G1).
- **strategy_panel**: opus-5(A1) + gemini-deepthink(G1) + qwen-3.8-max(TP1) — voices, not
  substitutes; 2+ families minimum, missing voice logged.
- **normative_search**: gemini-agy(G1) → qwen-3.8-max(TP1) **+ mandatory NotebookLM (or
  Anthropic-seat) verification on the Qwen leg** (panel fix Gemini#5 — §2.5 hard-NO applies to
  the fallback too). Claude never searches norms (hallucinates regs).
- **pii_intake**: SEA-LION → local fallbacks → QUEUE. Never cloud, never degraded-to-cloud.

# 4. Gate taxonomy (the drift-killer — land this table verbatim in modus §Arsenal)

Four distinct organs called "gate". Conflating them is the W86-class drift this table prevents:

| Gate | What it judges | Who | Fallback |
|---|---|---|---|
| **Final on-disk gate** (modus VERIFY) | the last empirical grep/disk/live check of every task | Fable 5, max effort | **NONE. Never cascades.** All Anthropic accounts dead → task SUSPENDS |
| **WR2 content gate** | on-disk editorial content | Fable 5 | **NONE.** Window dead → SUSPEND (explicitly outside the 2026-08-09 ruling) |
| **Gear-3 harness verdict gate** | the Evidence Pack of a Gear-3 task (PASS/PWC/REWORK/BLOCK) | Fable 5 first, rotating AZ→A2→A3→A1 | **Ruling Zero 2026-08-09**: only when NO account can run Fable → Opus 5 `effort=max`, verdict marked `gate_degraded: fable→opus` in check + pack. Never pay |
| **Gear-2 verdict** | standard feature PRs | Opus 5 + AI-review action + CI | ordinary cascade rules |

The Fable-paid contingency applies to every row: metered Fable is never purchased.

**Sequencing note (panel fix Gemini#2):** the final on-disk check (modus VERIFY) PRECEDES the
Gear-3 verdict gate. The Opus fallback of row 3 applies ONLY to the verdict stage — the window
where Fable passed the on-disk check and died before the verdict. It never substitutes the
on-disk check itself: if that check cannot run on Fable, the task suspends before any verdict
exists. No contradiction, no bypass.

**Floor note (panel fix GLM#5):** gear classification is the DETERMINISTIC FLOOR computed from
the diff (harness §1), recomputed by CI — never the conductor's choice. Publishing this table
does not create a downgrade lever: a task cannot be talked into Gear-2 when its diff says 3.

# 5. GLM z.ai quota-drain program (Zero's ask, 2026-08-10)

Burn the remaining z.ai quota on work GLM is categorically best at — nothing artificial.
In priority order:

1. **Panel seat on THIS spec** (fires today): adversarial review of this document. The spec's
   own generator≠grader gate doubles as drain.
2. **Refuter first-call on the landing PRs** (§7): compact reviews of every landing diff —
   its standing Zero-promoted duty.
3. **Counter-implementation of `evidence_pack_lint.py`** (PR-3 prep): GLM implements the
   linter from the same brief as Sonnet, own worktree; the diff between the two candidates
   becomes the first real Evidence-Pack dissent artifact. Dogfood + drain in one move.
4. **PENDING-ARMS full-ledger triage**: ~970KB read in one 1M-context pass; classify every
   open line (TECH-DEBT overdue / operator-gated / firebreak / stale-closable) with evidence.
5. **Spender class-audit (W107 census)**: enumerate every cloud-API call-site in the repo and
   report which consult `cost_breaker` and which don't (the genai_client gap already proves
   the class has >1 member). Report only — fixes go through Sonnet lanes.
6. **MODEL_TOPOLOGY consumer census** before the v3 edit: who reads `cloud_fallback` and
   `aider_fix` (the cron lanes read this file — the census de-risks the reconciliation).
7. **`seat_dispatch.py` spike**: throwaway prototype reading FLEET_TOPOLOGY and choosing
   seat+account; Sonnet hardens it afterwards.

Fence unchanged: worktrees, no credentials, no PII, output = candidates.

**Stop-rule (panel fix Gemini#4):** the drain program runs on the z.ai door ONLY. When the
z.ai quota dies (403), the program STOPS — it does not spill onto TP1 credits. TP1 GLM usage
begins only after PROBE-1-residual measures its burn-rate. **Redaction pre-pass (panel fixes
GLM#3 + Codex#12):** before the PENDING-ARMS 1M-context pass (activity 4), a local
deterministic gate greps the ledger for token-shaped strings (hex ≥32, `sk-`/`ghp_`/`xox`/
`AKIA` prefixes, base64 blobs) AND PII patterns (passport/KTP/NPWP-shaped identifiers) —
names of secrets may transit, values and PII never; a hit aborts the send.
**Self-review exclusion (panel fix Codex#10):** GLM never reviews a diff containing code it
authored (its counter-implementation of activity 3, or its cherry-picked patches) — those
diffs route to Codex/Gemini; activity 2 and activity 3 are mutually exclusive per artifact.

# 6. Cost governance & observability

- **Breaker coverage**: every cloud spender must pass a budget guard — the genai_client gap is
  the first fix; the §5.5 census finds the rest. Coordinate with open PR #3914 (same surface).
- **Collector rollout** (scripts/usage/): per-machine by construction → arm on all three
  machines or the picture is M5-only. seat_map.json from §3.1 conventions. Plist only after
  live-log testing (W64/W69 wrapper pattern).
- **Secrets hygiene**: `~/.qwen/settings.json` now 0600 (was 0644 with the TP1 key in clear);
  register the `~/.qwen/` family in `secrets_permissions_audit.py`'s declared set at landing.
- **PROBE ledger**: PROBE-1-residual = burn-rate on 3 sample tasks + credits endpoint + confirm
  the ~$68 tier · PROBE-2 = K3 multimodal pack verification · PROBE-3 = decide CLI vs direct
  API per lane (CLI leg exists UNARMED) · PROBE-4 = MiniMax sample lot with Anthropic
  verification. Every PROBATION→ARMED promotion = one line here + PENDING-ARMS entry.

# 7. Landing plan (the session executes; Sonnet hands, Fable gates)

- **PR-1 — files + corrections** (this package made true): FLEET_TOPOLOGY v1.2 (emails, GLM
  dual-door, DeepSeek PROBATION row, refuter chain, A4 note) · AGENTS.md §17 (from dossier
  copy, NOT the Cowork-polluted working-tree file; add gate-taxonomy pointer) · codex.md §7 ·
  GEMINI.md conductor section · kimi.md · qwen.md (updated: DeepSeek re-admission, 15-model
  list, key location + 0600 rule) · research/operations/ (harness-v2, quattro-gruppi, THIS
  spec) · scripts/usage/*.
- **PR-2 — doctrine fold**: modus SKILL.md §Arsenal gains the §4 gate-taxonomy table + TP1
  wing rows; CLAUDE.md §5 gets a 2-line pointer (no restatement — one SSOT). Self-doctrine
  PR: adversarial review mandatory, Zero's ratification already covers direction.
- **PR-3 — enforcement**: `evidence_pack_lint.py` (registered in guard-conformance with
  guilt+innocence corpus — the linter is itself a guard, famiglia #3) · gear-3 labeler
  (CODEOWNERS-TIER1 protected) · `harness/fable-gate` status check + branch-protection
  requirement (operator[gui] if API token lacks admin) · CI floor recompute from diff.
- Probes run between PR-1 and PR-3 as background lanes; MODEL_TOPOLOGY v3 lands only after
  the §5.6 consumer census.

# 8. §Solo-operatore (nothing else blocks)

1. ~~Map or close the 4th MAX slot~~ **RESOLVED 2026-08-10: estate = 3 MAX + 1 Team Premium, no A4.**
   Follow-up paste: apply the QUAD→TRE-MAX correction to `~/.claude/CLAUDE.md` (host-boundary
   protects that file from agent writes — by design; paste-ready snippet:
   `Desktop/harness-flotta-2026-08-09/global-claudemd-patch.txt`).
2. cswap/profile logins when rotation is armed (OAuth device flows are operator-only).
3. `CODEX_HOME=~/.codex-o2 codex login` with zero@balizero.com (device flow).
4. Token Plan console: confirm tier (~$68) and whether Qoder off-peak is included.
5. z.ai: simply let it lapse when drained (default; no action = correct).
6. Standing unrelated: TG bot token rotation (open since 6/8), Sentry token rotation.

# 9. Declared assumptions (refutable, panel please attack)

- `~/.codex-o2` over `~/.codex-acct2` (dossier+collector already reference it; one convention).
- DeepSeek's position is *reasoner/refuter reserve* — not a builder — because its historical
  value here was math/verify chains and its retirement was economic, not qualitative.
- The Qwen Code CLI remains the interactive TP1 door and the direct API the pipeline door;
  neither becomes load-bearing before PROBE-1-residual numbers exist.
- `~/.claude-zero-team` is presumed a legacy duplicate of AZ — verified at cswap arming, not
  before.

# 10. Panel record (2026-08-10)

Seats dispatched: GLM 5.2 (z.ai, first-call refuter — drain activity #1) · Gemini via agy
(constructive) · Codex default-model high effort (red team) · Kimi K3 (falsifier — **ABSENT**:
403 Allegro-cycle quota exhaustion, observed live; panel = 3 external families, quorum met).
Findings: GLM 6 (1 CONFIRMED + 5 PLAUSIBLE) · Gemini 8 (self-marked CONFIRMED) · Codex 12
(10 CONFIRMED + 2 PLAUSIBLE) = 26 total, each treated as a LEAD and re-judged by the conductor
(W65). Dispositions: **24 ACCEPTED** as inline amendments (marked "panel fix"), **1 REJECTED**
with rationale in place (Gemini#6 — the proposed remap contradicted Zero's 2026-07-22 profile
ruling), **1 resolved as clarification-not-contradiction** (Gemini#2 — sequencing note in §4;
Codex#12 merged into the GLM#3 redaction amendment). Notable cross-family convergence: A3
donor/builder conflict flagged independently by GLM#1, Gemini#8 and Codex#5 —
CONFIRMED-by-convergence under the harness's own rule.
