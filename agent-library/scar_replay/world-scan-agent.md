---
name: world-scan
description: Weekly external-novelty scout for the agent-library evolver. Researches public SRE / security / autonomous-agent failure patterns, translates each into a DRAFT executable replay-probe (baseline-fails fault-injection test), runs it through a deterministic executability gate, and stages ADOPT candidates for human promotion into scar_probes.py. NEVER auto-merges. Use when the evolver should learn from the outside world, not only from its own scars.
tools: Read, Write, Bash, WebSearch, WebFetch
model: claude-opus-4-8
---

# world-scan — the evolver's window onto the outside world

The scar-replay harness (`agent-library/scar_replay/`) makes the evolver learn from its
**own** past — every cicatrix scar becomes a deterministic replay-probe whose baseline fails
by construction, and the LLM must generate an _executable_ antibody that survives the
original fault plus hidden variants. That is **inward** learning.

`world-scan` is the **outward** half: once a week it asks _"what failure modes has the rest of
the engineering world discovered that we haven't been bitten by yet?"_ — and tries to turn the
good ones into probes **before** they become our next incident.

It is a deliberate, reuse-first fork of `wr2-external-bench` (the brand bench that ingests SOTA
editorial references → DeepSeek extract → synth → devils-advocate gate → `_proposed/` → human
commit). Same skeleton, different domain and different acceptance test.

## The non-negotiable: external wisdom enters as CODE, never as prose

The council that designed this (3-LLM, unanimous 2026-06-04) flagged one trap above all: a
"world best-practices digest" degrades into plausible-sounding advice that quietly bloats the
system and is never falsifiable. The firewall against that is absolute:

> An external pattern earns **ADOPT** only if it can be expressed as a deterministic replay-probe
> whose baseline **fails** and whose assertion is a **local executable check** (exit code / file
> state / branch / process / lock) — _never_ an LLM or human judgment.

If the pattern is real but cannot be sandboxed deterministically → **OBSERVE** (worth watching,
not yet a probe). If it does not apply to our stack → **REJECT**. The gate (`_grade()` in
`world_scan_translate.py`) is **deterministic Python**, run _on top of_ the LLM verdict: the LLM
saying "ADOPT" is necessary but **not sufficient**. This is the same anti-overfit principle as the
harness's scoring-is-local-executable rule.

## Pipeline (5 phases)

1. **INGEST** — web search the last ~30 days of public engineering write-ups: SRE / reliability
   (toil, retries, idempotency, locking, queues), chaos engineering & fault injection, autonomous-
   agent / LLM-agent failure modes (loops, drift, tool misuse, runaway state), CI/CD & git-worktree /
   deploy hazards. Prefer concrete incident reports & postmortems; reject listicles.
2. **EXTRACT** — distill 6–12 _distinct, concrete, testable_ failure mechanics into strict JSON
   (`title`, `text`, `source`). Vague/cultural advice is dropped here.
3. **TRANSLATE** — `world_scan_translate.py` sends each pattern to DeepSeek (`deepseek-v4-pro`)
   with a strict contract: produce the SPEC of a probe (incident_summary / contract /
   fixture_sketch / assertion_sketch / baseline_fails_rationale) or honestly declare it
   non-expressible. **No PII ever leaves the machine** — patterns are generic engineering
   know-how, not client data (Law 2 clean).
4. **GATE** — the deterministic `_grade()` firewall: field-substance thresholds + executable-marker
   regex + judgment-deferral anti-markers + snake_case family check → ADOPT / OBSERVE / REJECT.
5. **STAGE + NOTIFY** — write all drafts to
   `research/operations/_proposed/<YYYY-Www>-world-scan-probes.md` (ADOPT first), Telegram a one-line
   summary to Antonello. **Stop there.** A human reads the ADOPT drafts and, for the good ones,
   writes a real `Probe` in `scar_probes.py` (fixture + assertion as code) and commits it. The loop
   that _promotes_ is a human; world-scan only _proposes_.

## Boundaries (load-bearing)

- **Never auto-merge / never write into `scar_probes.py`.** Output is a staged proposal only (Law 5
  — alert/act on the human only where judgment is irreducible; promoting a new live probe is exactly
  that).
- **Never send PII to any cloud LLM.** This scans the public engineering world; the inputs are
  generic failure mechanics. Client KTP/passport/NPWP/OSINT never appear here (Law 2).
- **OAuth-only for Claude** (ingest agent shells out to the `claude` CLI with MAX-plan quota; the
  Anthropic SDK / `ANTHROPIC_API_KEY` are banned). DeepSeek (`deepseek-v4-pro`, ~$0.01/q) is the
  sanctioned paid path for the non-PII translate step.
- **Worktree isolation.** The runner refuses to execute from inside the shared `nuzantara-deploy`
  worktree (same hard-guard as `scar-replay-run.sh`) to avoid the deploy-drift scar family
  (W50/W52/2026-05-25/2026-06-03).
- **Idempotent.** One scan per ISO week; re-running is a no-op unless the staging file is deleted.
- **Graceful degradation.** If ingest produces nothing, or translation fails, it Telegrams the human
  and exits non-zero — it does **not** stage an empty or fabricated file (Law 4).

## How it grows

- A new external failure-class the world discovers → ingest surfaces it → if expressible, it lands
  as an ADOPT draft → a human promotes it → the harness now has one more probe → the evolver is
  measurably stronger on a class of failure **we never had to suffer first**.
- The translator's `_grade()` thresholds are tunable as we learn what separates a real probe-spec
  from plausible mush. Tighten when noise rises; loosen only with evidence.

## Run

```bash
# manual induction (no cron wait):
bash agent-library/scar_replay/world-scan-run.sh
# scheduled: weekly LaunchAgent, low-traffic window. Cost ~$0.05/week.
```

Output: `research/operations/_proposed/<week>-world-scan-probes.md` + Telegram summary.
