# /dynamic-workflow — brief for the coaches (generic template; sealed, one round)

Filled at invocation by the skill. Same bytes for every seat. Placeholders in `{{ }}`.

```
objective_by_zero: |
  {{OBJECTIVE}}
colour: {{COLOUR}}            # BLUE unless Zero declared ORANGE
gear_floor: {{FLOOR}}         # from scripts/evidence_pack_lint.py if a candidate exists, else "unknown"
date: {{DATE}}
brief_sha256: {{SHA}}
you_are: {{SEAT}}
```

## 0. What you are asked

You are the coach. You know the squad (§2) and the rules of the league (§3). Design the
**formation and the tactics for THIS match** — the objective above — not the general method.
Which seats play, in which role, in what order, parallel or serial, with what round cap per stage,
what exit condition (a command, not an opinion), what runs inside a dynamic `Workflow` script and
what runs in a human or Dux window. You answer ALONE; you do not see other coaches. Where the
brief lacks something, write `ASSUMPTION:` and continue. Do not propose seats or paid APIs that
are not in §2.

`modus` is the loop around whatever you design (GROUND → DESIGN → BUILD → VERIFY → SHIP+ARM →
PROVE-LIVE → ALIGN-FLEET → CLEAN → CAPTURE). Your design is the fan-out arm inside it. The final
on-disk gate, the ship sequence and prove-live are fixed by §3 and are not yours to redesign.

## 1. Scouting report (measured; cite by number, do not re-derive)

F1. PARABELLUM, first 36 h (2026-09-10/12): 111 PRs merged; 29% ledger/gate ceremony PRs; 20% of
red checks were harness false reds; 0 ORANGE missions; 2 customer-visible results.
(source: docs/rules/RULINGS.md, SAETTA 2026-09-12 retrospective — 111 PRs, the 20% harness-false-red
rate and the 2 customer-visible results grep-confirmed there; the 0-ORANGE-missions clause is not
independently confirmed)
F2. Ledger rule (one row per mission, healer at most daily) vs practice: 88 commits on
`PENDING-ARMS.md` since 09-12, 6 healer ticks on 09-16 alone.
(source: session 2026-09-18, unverified)
F3. Second army (Sonnet Dux verifies on disk, inferior cross-family seats build), 2 runs: 7 tasks,
2 shipped as-is, 1 died. Every shipped item was re-verified by a fresh Opus 5 session. The run
report did not pass the adversarial gate.
(source: session 2026-09-18, unverified)
F4. Same-family review: 7 false-clean of 8 (W100). A refuter must be a different family.
(source: .claude/skills/workflow/SKILL.md:49)
F5. Codex Sol loses its verdict to a context rollover at ~176K unless launched with cwd OUTSIDE the
repo, the material inlined, and `VERDICT:` requested first.
(source: session 2026-09-18, unverified)
F6. Gemini via `agy` returns empty unless told "no tools" with the material inlined; a 12 KB
research lane took 848 s.
(source: session 2026-09-18, unverified)
F7. Alibaba TP1 is ONE weekly bucket shared by 7 models; agentic multi-turn use drains it in hours;
one-shot calls do not.
(source: session 2026-09-18, unverified)
F8. Kimi K3 has a monthly quota (dead 09-15, live 09-18). Codex Spark: HTTP 400 dead since 09-15.
Jules: 3/day, queues often empty. The daily liveness probe covers 1 of 16 seats; the Gear-3
quorum lint counts seats from a static roster, not from the probe.
(source: docs/architecture/dual-consul/army-map.md:72,74,76 — Codex Spark HTTP-400-since-09-15 and
Jules 3/day clauses grep-confirmed there; the Kimi K3 quota dates and the probe-coverage clause
are not independently confirmed)
F9. A `claude -p` child costs ~37K context tokens before doing anything; ~15K with
`--restricted --strict-mcp-config`.
(source: research/agent-craft/cc-meta-loop/BACKLOG.md:207-208 — confirms the ~15K
`--restricted --strict-mcp-config` figure exactly (15,064); the ~37K baseline is not
independently confirmed)
F10. Eight lanes launched without `model:` inherited Fable and died together 25 s in. Five Fable
lanes exhaust a MAX seat in 2–3 min. The 113-agent run was Opus (6 readers, 106 refuters,
1 synthesizer, peak 8 concurrent).
(source: .claude/skills/workflow/SKILL.md:37-41 — eight-lanes/25s clause; research/operations/
2026-09-07-astra-operative-workflow-audit.md — 113-agent run composition and Opus attribution)
F11. A Sonnet "courier" lane allowed to fix "only syntax" re-authored 14/19 lines of a Qwen seat's
output and reported "title fix". A read-only diff of disk vs seat transcript caught it.
Self-reported journals are not evidence.
(source: session 2026-09-18, unverified)
F12. Strengths, measured here and globally: Opus 5 = architecture, red-team, long-horizon, gate;
Sonnet 5 = well-specified BUILD units (rewrites others' work when used as courier); Haiku =
grunt. Sol = empirical sandbox, migrations, working React UIs (Website Arena 1415 vs 1238);
Luna = mechanical edits, wrong on shared semantics. Gemini 3.1 Pro = corpus ingestion (1M),
regulatory search; 3.8 Flash = cheap width, last in both local design juries. Kimi K3 =
long-context audit, evidence-pack verifier, design (Design Arena #2, R19 tied first).
Qwen 3.8 Max = strategy voice, instruction following, non-PII mass documents, design (won the
08-30 blind jury). DeepSeek V4 Pro = hard logic, counter-analysis. GLM 5.2 = first-call refuter
for diffs <5K chars. deepseek-v4-flash / qwen3.7-plus / qwen3.6-flash = batch and grunt.
NotebookLM = ground-truth verifier, never synthesizer. Ollama local = the only PII lane.
(source: MODEL_ROSTER.md — Gemini 3.1 Pro and Kimi K3 role descriptions grep-confirmed there;
the Website Arena / Design Arena / 08-30 blind jury competition-score numbers are not
independently confirmed)
F13. Real missions to date ran on tmux windows with pasted prompts; the dynamic executor
`saetta.js` never ran a mission; `second-army.js` ran twice; a design tournament ran once.
(source: session 2026-09-18, unverified)
F14. Claude→Codex has no native channel: a file in the shared folder is published, not delivered.
(source: research/operations/2026-09-10-fable-max-sessions/README.md:69; docs/architecture/
dual-consul/army-map.md:81-90 — the doctrine there is framed as dual-consul Claude↔Claude;
the Claude→Codex scoping stated here is an extension of it, not independently confirmed)
F15. Merged ≠ live: backend-rag merge is the deploy; mouth stays STAGED until `vercel promote`.
(source: memory discovery-merging-a-backend-rag-pr-deploys-by-itself;
discovery_mouth_production_deployments_land_staged_and_go_live_only_on_vercel_promote_2026_09_17)

## 2. The squad today

{{ARSENAL_LIVENESS}}

(Filled at invocation from `scripts/arsenal_probe.py --json` and `MODEL_ROSTER.md`: door, seat,
live/dead/slow with probe time, launch shape that works.)

## 3. Rules of the league (binding; a design that breaks one is disqualified)

C1. No Claude model through a paid per-token Anthropic endpoint, any alias or Bedrock/Vertex route.
Only the `claude` CLI on OAuth. Other paid per-token APIs need Zero's explicit OK.
C2. PII is an OUTPUT boundary: no client PII/OSINT in cleartext anywhere. Client documents: Ollama.
C3. One PR, one concern, ≤ ~400 net lines. Auto-merge armed at PR-open; armed branch frozen. Push,
create, merge are three separate commands. Every PR body carries `Bites:` (consumer + the
observation that proves it is live).
C4. The session that owns the mandate ships end to end; the codeowner never merges/reviews/
deploys. External seats PREPARE, never ship. ORANGE exception: one appointed Sol Dux ships,
a fresh Sol signs.
C5. Final on-disk gate: a FRESH Opus 5 `xhigh` session outside the chain (BLUE). Never cheaper
than the builder, never cascaded, never an `agent()` lane.
C6. Generator ≠ grader, always; grader from a different family; never shown the builder's claim first.
C7. Fix-of-a-fix stops at depth 1. Three reds for the same cause: suspend. Never rerun a red
before knowing why it is red.
C8. Imperators (Fable 5.1, Astra) never fan out and never implement. Every `agent()` pins `model:`.
C9. Ceremony has a budget: coordination only while measured overhead (wait + rework + human
interventions) stays below the time it saves.
C10. Agents work in `.worktrees/<lane>-<id>/`; the main checkout is read-only for agents.

## 4. Deliverable — formation and tactics (exact skeleton; the synthesizer parses it)

```
---
seat: <family/model>
objective_sha256: {{SHA}}
facts_cited: [F.., C..]
assumptions: <count>
---
## Formation
| role | seat | why (F ref) | substitute if dead (F8) |
## Tactics
| stage | seat(s) | in-script or window | parallel/serial | round cap | exit command | hands to next stage |
## Termination
<the counter that makes a fourth round impossible: where it lives, who reads it>
## Evidence between stages
<what a stage hands over so the receiver verifies without trusting the sender's journal (F11, F14)>
## Never
- ... (F/C ref)
- ... (F/C ref)
- ... (F/C ref)
## First move
<the first ≤100-line thing to build or run> · Bites: <consumer> · <observation>
## Cost
<calls per seat; Anthropic windows opened; expected wall-clock>
```

Limits: ≤ 1,500 words. Command lines allowed, no other code. Judge nothing by exit code.
