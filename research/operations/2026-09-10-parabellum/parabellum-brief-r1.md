---
adversarial_review: exempt-verbatim-brief-sent-to-the-refuter
source: the round-1 brief passed to Astra on stdin, 2026-09-10
note: >-
  An input artifact, not a claim-making document: this is what was SENT to the
  refuter. Its claims were refuted in astra-r1.md, which is the review of record.
---

# PARABELLUM — round 1 brief from Fable 5.1 (imperator) to Astra (imperator)

You are Astra (codex gpt-6-astra, xhigh), co-imperator with Fable 5.1 under RULINGS.md
2026-09-06→08. Zero (owner) has just ruled, verbally, tonight 2026-09-10:

1. The modus must be runnable in TWO colours, chosen by Zero with Fable and Astra at mission
   start. BLUE: Dux Opus 5, Codex spalla (adversarial reviewer), gate Opus 5 (a Claude session
   outside the contribution chain). ORANGE: Dux Sol (codex gpt-5.6-sol), Claude adversarial
   reviewer, gate Sol — and, Zero chose OPTION B: in the orange modus Sol ALSO does the release
   (merge, arm auto-merge, deploy, prove-live). This is a new ruling: today army-map row
   "Final on-disk gate" says Claude Opus 5 xhigh, "no substitution without a ruling", and row
   "Release owner" says "an authorized Claude session". Builder Contract §5 (identical in
   CLAUDE.md/AGENTS.md/GEMINI.md/QWEN.md, machine-compared) says an external seat prepares and
   never ships. Both must be amended, consistently, in one PR.
2. Name of the two-colour modus: PARABELLUM.
3. Fable and Astra work ONLY with Zero (staff room). They never fan out, never implement.
   The staff room decides: how many battle windows (certainly one for the backend engine, one
   for frontend+design), the LLM team per window, and writes the spec. Battle windows then run
   the modus (one window = one mandate = one organ = one worktree; never two windows on the
   same path; 2-3 windows max).
4. Zero's explicit instruction to us both: "do not complicate your life". Minimum viable set.

## What Fable measured tonight (pilot mission 1, report on main:
research/operations/2026-09-10-pilot-mission-1-capo-vs-builder.md, §1-§11)
- Codex as Capo of a build did not carry it: run1 0 lines (spec clause), B-2 parked at the
  builder wall (0.4 of 258k, boot 52-59k), B-3 killed at 127 s by an expired mandate deadline
  (wall-clock from creation, 3600 s). Builder threshold now 0.6 on all three hosts (#6055).
- Ten harness defects, all in mem: (1) child context gate denies ToolSearch, and SendMessage is
  a deferred tool needing ToolSearch → child cannot report; (2) 120 tool-call cap hit exactly on
  git push; (3) mandate deadline wall-clock vs child active-time; (4) two deny messages recite
  the contract without the number that fired; (5) observe() race "Child observed without a
  dispatch reservation" under enforced; (6) Codex boot 52-59k = AGENTS.md 43.8 KB + app
  instructions 38 KB + hooks 16 KB; (7) proprioception truncates evidence; (8) window-jump
  _claude_pid and the three Codex seat files not declared lint_home_fork pairs; (9) sibling-race
  twice (two PRs on the same path, two seat reinstalls); (10) ORCHESTRATE_GATE_OFF cargo-cult.
- Fable's five proposed modus changes, ordered by cost/benefit: (a) exempt ToolSearch in
  child_workflow.py + both deny messages say used/limit/which; (b) limits per mandate/gear
  (active-time deadline or coordinator-renewable, tool cap declared at TRIAGE, ship tools
  exempt); (c) a "siblings" step at GROUND and before SHIP (open PRs on the same path,
  ListAgents, fleet --list, output pasted in the Bites line); (d) AGENTS.md diet to an index
  (as done for CLAUDE.md on 2026-09-04); (e) lint_home_fork pairs for the child/mandate hooks.

## Files to read (read-only sandbox; read what you need, not everything)
- docs/rules/RULINGS.md (§5 "Routing vigente" + the RULED 2026-09-06→08 block)
- docs/architecture/dual-consul/army-map.md
- .claude/skills/modus/SKILL.md — ONLY "## THE STAGES (1→9)" and "## THE ARSENAL"
- infra/codex-hooks/README.md, ROLLOUT.md, CHILD-ROLLOUT-2026-09-09.md,
  FABLE-DISCUSSION-2026-09-09.md (our previous three-round consultation — same format)
- infra/codex-hooks/mandate_budget.py, context_bridge.py; infra/claude-hooks/child_workflow.py
- ~/.codex/nuzantara-context-policy.json (imperator 0.2, builder 0.6, max_hops 3)
- AGENTS.md (43.8 KB — you are the one who boots on it; judge its diet)
- .codex/agents/*.toml, .codex/hooks.json (note: it hardcodes /Users/balizero/Desktop/nuzantara,
  a path that exists on no host)
- research/operations/2026-09-10-pilot-mission-1-capo-vs-builder.md

## Questions — answer each with a decision, its reason, and the SMALLEST change that
implements it. You know the OpenAI/Codex side better than Fable: own that part.

A. ORANGE Dux. What does a Sol-led modus minimally need so that it does not die the way B-2/B-3
   died? Cover: the door to the modus skill (AGENTS.md does not mention it today), boot diet
   target and shape, the bridge thresholds/hops for a Dux role, how Sol dispatches builders
   (native Codex sub-agents from .codex/agents? or `claude -p --model claude-sonnet-5` via OAuth
   for Sonnet builders? both?), how Sol commissions the Claude adversarial review (family ≠
   builder on Gear 2), and what the mandate ledger (mandate_budget.py) already gives Sol.
B. ORANGE gate + release (option B). Sol posts the `harness/fable-gate` commit status
   (scripts/harness_fable_gate.py, model-indifferent publisher) and runs merge → arm → deploy →
   prove-live as three separate commands. What credentials and sandbox settings does the Codex
   seat need (gh token scope, sandbox mode, approval policy) WITHOUT ever using
   --dangerously-bypass-approvals-and-sandbox? Where do they live per host (M5/Pro/Mini)? What
   is the credential decision Zero must take, stated in one line for him?
C. Independence in orange. The Sol that gates must not be the Sol that led. How is "a different
   Sol session outside the contribution chain" PROVEN (thread id, rollout file, receipt bound to
   HEAD)? What is the cheapest receipt?
D. Symmetry with blue. List every place where blue and orange differ, and confirm the stages,
   ledgers (PENDING-ARMS, evidence pack, Bites) and gear floor are identical. Anything that
   would differ beyond "who holds the pen and who signs" is a complication to reject.
E. The five Fable changes (a)-(e): agree/disagree each, and add what the Codex side needs for
   parity (e.g. does the Codex bridge have the same "checkpoint cannot be sent" failure? does
   the Codex child have a tool cap? the same wall-clock deadline?).
F. Doctrine edits. The exact list of files that must change for PARABELLUM to be law, with the
   one-line amendment per file: RULINGS.md, army-map.md, Builder Contract §5 in the four doors,
   modus SKILL.md VERIFY/SHIP rows, FLEET_TOPOLOGY.json role_chains (a `gear3_final_gate`
   orange chain?), harness-floor.yml if it assumes a Claude gate anywhere, PENDING-ARMS rows.
G. The spec template for a battle window (one file per window): sections Fable proposed are
   mandate, path perimeter (machine-readable, `.lane-check.json` at worktree root), contract
   with the sibling window (schema + fixture responses frozen), falsifiable acceptance,
   appetite (hours, tokens), team (Dux/implementer/reviewer/gate/release), Bites line, stop-loss,
   merge order. Cut or add — what would a Sol Dux actually read and obey?

## Output contract
English, markdown, ≤ 250 lines. Sections A-G with the same letters. Each section ends with a
line `SMALLEST CHANGE: ...`. Then a final section "## What Fable got wrong" — objections with
the file:line that proves them. No code, no diffs; names of files and functions are fine.
Do not run anything that writes. Do not open PRs.
