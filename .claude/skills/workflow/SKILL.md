---
name: workflow
description: >
  Strategic multi-agent orchestration playbook — the Workflow tool wired to the full
  cross-family arsenal (Sonnet 5 implementers, Codex red-team, Gemini agy width, Kimi K3,
  GLM refuter, Ollama PII-local). USE when the mandate is strategic/wide: architectural
  decision, exhaustive audit/review, corpus research, design tournament, council panel —
  anything needing many independent perspectives or scale one context can't hold. Also the
  shared protocol for TWIN FABLE SESSIONS (e.g. M5 + Pro) doing joint strategic work:
  disjoint lanes, durable artifacts on disk, handoff via ledger. Invoking this skill IS the
  user's explicit opt-in to the Workflow tool. SKIP for single-lane fixes — that's plain
  modus Gear 1/2 with at most one spalla.
---

# /workflow — strategic orchestration (the arsenal, made deterministic)

> modus (`.claude/skills/modus/SKILL.md`) is the LOOP; this skill is the FAN-OUT ARM the
> loop reaches for at Gear 3. Doctrine: `sota-architecture-loop` (council gate, asymmetric
> adversarial review) · executable ancestors: `infra/workflows/README.md`. Nothing here
> overrides the modus final-gate invariant: **Fable does the last on-disk grep — never
> delegable, never cascadable.**

## 0. Opt-in and when to fire

The Workflow tool needs explicit user opt-in — **a user invoking `/workflow` (or a mandate
that names this skill) is that opt-in.** Fire it when at least one of:

- **Breadth**: ≥3 genuinely independent units (files, codes, angles, brands, sources).
- **Confidence**: findings must survive adversarial verification before they ship
  (security, regulatory, client-facing, architectural).
- **Scale**: the corpus doesn't fit one context (migrations, audits, 60-NB sweeps).
- **Strategy**: a decision where divergent priors can change the answer (council gate,
  modus TRIAGE: divergent priors ∧ error-cost >15× tokens ∧ parallel breadth — ALL three,
  else solo + 1 spalla).

Do NOT fire for: mechanical batches a for-loop covers (use pipeline inside ONE workflow,
not N workflows), single-file fixes, anything already owned by a live sibling lane.

## 1. The contract (non-negotiable)

1. **Fable orchestrates, Sonnet builds, externals grade.** `agent()` lanes default to the
   session model; pass `model:"sonnet"` for implementer lanes, `model:"haiku"` for grunt.
2. **generator≠grader, always.** No lane grades its own output; a grader gets FRESH
   context and never sees the generator's answer before deriving its own (D5 pattern).
3. **Cross-family beats same-family** (W100: same-lane agreement certified 7 false-clean
   of 8). At least one verify seat from a DIFFERENT training family than the generator.
4. **Verdicts are LEADS** (W65: even the refuter hallucinates). The orchestrator re-probes
   on disk whatever a lane's verdict would make it do.
5. **PII never enters a cloud lane's prompt** — redact to `client_id`/placeholders first,
   or route the transform to Ollama local (SYMBIOSIS Law 2).
6. **Durable output on disk** (research/, specs/, docs/) — a workflow whose result lives
   only in the return value is un-armed by construction (W81).

## 2. Arsenal wiring inside workflow scripts

`agent()` lanes are Claude-family. External seats are reached FROM a lane via Bash — the
lane prompt says "run this command, treat stdout as the seat's verdict". Probe-then-trust:
a seat that fails its 1-token probe is a dead tier, DECLARED, never silently skipped
(cascade: GLM → Kimi → Codex for the refuter chair — DeepSeek RETIRED 2026-07-19, Zero's order + repeat HTTP-402; never route to it).

| Seat (family)              | Command from inside a lane                                                                                                                                                                                                                                                                                                                                                                                                             | Chair                                    |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| Sonnet 5 (Claude)          | native `agent(prompt, {model:"sonnet"})`                                                                                                                                                                                                                                                                                                                                                                                               | implementer / reader fan-out             |
| Codex GPT-5.6 sol (OpenAI) | `codex exec -m gpt-5.6-sol -c model_reasoning_effort=xhigh --sandbox read-only --skip-git-repo-check "<prompt>" < /dev/null` — NOTE 2026-07-19 (timeboxed): sol@high exceeded the 590s Bash cap twice on multi-file R1 reviews; `terra` medium is the reliable R1 default until a latency log says otherwise; on timeout DECLARE and escalate along the cascade                                                                        | red-team / empirical sandbox             |
| Gemini via agy (Google)    | `agy -p "<prompt>"` (long input: `cat file \| agy -p --print-timeout 5m`)                                                                                                                                                                                                                                                                                                                                                              | costruttivo / corpus width / normativa   |
| **Kimi K3 (Moonshot)**     | `kimi -p "<prompt>" -m kimi-code/k3` (coding lane: `-m kimi-code/kimi-for-coding`; grunt: `-highspeed`; scriptable seat: `scripts/kimi_client.py`) — ARMED M5+Pro+Mini 2026-07-19 (probed). NON-PII prompts only (Chinese cloud, Law 2); K3 hyper-proactive on ambiguous tasks — scope tight. Desktop = separate operator-driven surface, see `research/operations/2026-07-19-kimi-arsenal-integration-deepseek-retirement.md`         | refuter #2 / cross-family second opinion |
| GLM 5.2 (Zhipu)            | `claude-glm` wrapper (Keychain-bound — probe first; dead under locked keychain) — PROMOTED 2026-07-19 (Zero: "glm deve essere un po' più utilizzato"): FIRST-CALL refuter and default R1 seat for compact reviews (<5k chars prompt — z.ai 529s above); it runs the claude CLI shim so it READS FILES AGENTICALLY — hand it paths, don't paste diffs; escalate along the cascade (Kimi → Codex) only on multi-file scope or probe-fail | refuter #1 — USE FIRST, not last-resort  |
| Ollama (local)             | `ollama run qwen3.5:9b "<prompt>"` (vision: `qwen2.5vl:7b`)                                                                                                                                                                                                                                                                                                                                                                            | PII-bearing transforms, offline          |
| NotebookLM                 | MCP `mcp__notebooklm-mcp__notebook_query` from the ORCHESTRATOR (not lanes; ToolSearch loads schemas in-lane if unavoidable)                                                                                                                                                                                                                                                                                                           | ground-truth verifier (facts, normativa) |

### 2bis. Capability-map upgrades (2026-07-19 — capture: research/operations/2026-07-19-arsenal-capability-map-magic-combos.md)

New seat capabilities every workflow should know:

- **Codex search chair**: `codex exec --search "<prompt>"` — native live web search
  (flat-sub, non-Anthropic/non-Google index) → 4th independent witness in research sweeps.
- **Codex vision chair**: `codex exec -i <img.png> "<prompt>"` — OpenAI-family eyes on the
  SAME rendered artifact for image-grounded verify (W100 D5 pattern; sits next to GLM-vision).
- **Seat health probes**: `codex doctor --json` (auth-aware, replaces --version greps) ·
  `claude agents --json` (fan-out liveness) — probe-then-trust on real signals, not proxies.
- **Red-team as native tool**: from the ORCHESTRATOR, prefer `mcp__codex-redteam__codex`
  (typed MCP call) over Bash shell-out — lanes still use the Bash command.
- **Claude-via-agy overflow** (ruled by Zero 2026-07-19): `agy --model "Claude Opus 4.6 (Thinking)" -p`
  (PONG-proven) — extra Claude-family pool on Ultra flat quota when MAX windows saturate.
  Overflow lanes ONLY; NEVER the final gate (modus invariant untouched).
- **GLM Web Search/Reader MCP** (bundled free in the Coding Plan) — differently-biased second
  search lane for regulatory delta-hunting.
- **Kimi at corpus scale**: K3 Swarm (≤300 subagents, Desktop/operator-driven) +
  `kimi-agent-sdk` for headless swarms; `scripts/kimi_client.py` is the scriptable seat
  wrapper for lanes. NON-PII prompts only, always.
- **Structured CLI seats**: `claude -p --json-schema '<schema>'` (schema-validated output from
  CLI-called Claude seats) · `claude -p --fallback-model sonnet,haiku` (native same-provider
  fallback — replaces stdout-grep tier logic in wrapper scripts).

New patterns (compose with §3):

- **ultrareview-first**: `claude ultrareview <PR#|branch>` (cloud multi-agent, MAX-quota) as
  the automated first pass of any review workflow — external chairs then grade what it missed.
- **Server-side best-of-N**: `codex cloud exec --attempts 2-4` — tournament outsourced to
  OpenAI infra for the hardest single-shot problems (one-time Codex Cloud env setup).
- **Agent-Teams adversarial pair**: flag already armed fleet-wide — two peer sessions with
  SendMessage for iterative propose/critique rounds; cheaper than council when the shape is a
  dialogue, not a panel.
- **Triage-first research**: the bundled native `/deep-research` workflow answers easy
  questions free; reserve the multi-LLM sweep for regulatory/client-facing/hard ones.

Framing rule for external seats: "independent correctness review", never adversarial
rhetoric in the prompt text (provider refusal filters). All seats are flat-quota (DeepSeek, the one per-token seat, is RETIRED — pre-auth revoked) — cost is not a reason to skip a chair.

## 3. Pattern library (pick, don't reinvent)

**verify — the default for findings** (already versioned, cite it, don't rewrite it):

```
Workflow({ scriptPath: "infra/workflows/verify-template.js", args: {
  question: "...", angles: [{key,prompt}...], skeptics: 1  // 3 for high-stakes
}})
```

**council — strategic decision** (inline script): proponent lane drafts the position →
3 external chairs in parallel (Codex red-team: _find the flaw, default defective_ · agy
costruttivo: _save it by improving it_ · Kimi/GLM refuter: _falsify the core claim_) →
Fable synthesizes VERDICTS-AS-LEADS into the decision artifact on disk. Max 3 external
chairs, rounds capped at 2, never "do you all agree?" (conformity hallucination).

**sweep — corpus-scale ground** (pipeline, no barrier): readers fan out per organ/domain
with `phase:'Read'`, each returns structured JSON (`schema`), a verify stage refutes
per-item as items complete. Wall-clock = slowest chain, not sum. Dedup vs SEEN (not vs
confirmed) when looping until dry.

**tournament — wide design space**: N independent design lanes from DIFFERENT angles
(MVP-first / risk-first / operator-burden-first) → judge panel scores blind (judges never
see author labels) → synthesis grafts runner-up ideas onto the winner. Use when the
solution space is wide and one-attempt-iterated would anchor.

**per-item adjudication — data programs**: the KBLI shape (`infra/workflows/
kbli-pilot-a1.js`): D1 proposes from evidence → D5 blind-rederives on fresh context
(image-grounded where the evidence is a render, W100) → divergence escalates to a
cross-family seat. Copy its structure for any per-record certification program.

## 4. Twin-Fable protocol (M5 + Pro/Mini strategic pair)

Two Fable sessions on different machines multiply strategy ONLY with hard lane
discipline — without it they produce twin-race casualties (PR #2781):

1. **Claim before work**: each session claims a DISJOINT scope in the corner skill's LIVE
   STATE or `.claude/skills/modus/PENDING-ARMS.md` (`TRACK X claimed by <machine>/<date>`),
   committed in its first PR — the claim line is the lock.
2. **Scopes never overlap on files.** If both need the same surface, one owns the surface,
   the other consumes its merged output (pull-after-merge, never shared worktrees — #5).
3. **Handoff is a merged artifact + ledger line**, never chat memory: research files,
   specs, PENDING-ARMS entries. On wake, the twin re-GROUNDs from disk (files may have
   moved while it slept).
4. **One deploy lease at a time** (quad-session rule 2026-07-18): deploys/migrations
   stagger; the non-owning twin arms `--auto` PRs but never touches Fly/DB while the
   lease is out.
5. **Each twin runs its own workflows** — a Workflow's agents live and die with the
   session that spawned it; cross-machine "shared workflow" is done by SPLITTING the
   item-list in the claim, not by sharing a run.

## 5. Anti-sperpero (condensed from modus — still binding here)

- Declare the budget shape up front ("~N agents, ~1 council") — stop-loss at TRIAGE.
- pipeline() by default; parallel() only when a stage genuinely needs ALL prior results.
- One agent with 10× budget beats homogeneous debate at ⅓ cost — council only when its
  gate fires; never for a rubber stamp.
- Async always: workflows run in background; close the turn, act on the completion
  notification. A "completed" run is UNVERIFIED until its report/journal is READ
  (journal: `<transcriptDir>/journal.jsonl`).
- No silent caps: if a script bounds coverage (top-N, sampling), `log()` what was dropped.

## 6. Capture

Every strategic workflow ends with: artifact on disk (research/ or specs/, frontmatter
per §15 when it qualifies) · `mem save` decision/discovery · PENDING-ARMS line for
anything built-but-not-armed · AMENDMENTS line if the ORCHESTRATION itself misfired
(wrong pattern, wasted council, barrier that should have been a pipeline).
