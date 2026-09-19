---
name: dynamic-workflow
description: "Coach mode. Zero writes an objective; the invited seats each design the workflow formation + tactics for THAT objective knowing the live arsenal; sealed answers, one cross-family refutation, fresh-Opus synthesis, Zero picks; the pick becomes the Workflow script that modus runs. USE when Zero states an objective and says /dynamic-workflow. modus stays the default loop."
---

# /dynamic-workflow — the coaches pick the formation, Zero picks the coach

> Shipped: `scripts/dynamic_workflow.py` is the ONE launcher — `--help` lists every subcommand
> below; run nothing this file doesn't name. Template: `brief.template.md` beside this file.
> modus (`.claude/skills/modus/SKILL.md`) is the loop; `/workflow` is the generic fan-out arm;
> this skill decides the SHAPE of that arm per objective.

## 0. Inputs (from Zero, verbatim)

- `objective` — the argument of `/dynamic-workflow <objective>`. Free text, written to a file
  for `--objective-file`. **It travels to five external clouds: it must carry no client
  PII/OSINT (C2).** `brief` refuses fail-closed (exit 3) if `Redactor.load_default().redact()`
  changes it by one byte — no `--skip-pii` flag exists. Ask for a `client_id`/placeholder
  instead of a client name or case.
- `colour` — BLUE unless Zero says ORANGE (`--colour` must be exactly `BLUE` or `ORANGE`).
  `floor` — from `scripts/evidence_pack_lint.py` if a candidate exists, else `unknown`
  (`--floor`, optional).
- Coaches, default six: Fable 5.1 (the convening window, participant — never dispatched via
  `r1 --seats`, it writes `r1/fable-5-1.md` itself before anything else runs), Astra
  `gpt-6-astra` (Zero opens the window; add `--astra-fallback` to `r1` for the one-shot Codex
  path instead), Kimi K3, Qwen 3.8 Max, DeepSeek V4 Pro, Gemini 3.1 Pro high. Zero may
  add/remove coaches in the same message — anything else passed to `--seats` is refused unless
  it resolves to a known family (`_require_known_family`, r2 pairing/jury both fail closed on
  an unrecognised seat).

## 1. Build the brief (bytes identical for every seat)

```bash
python3 scripts/dynamic_workflow.py brief --slug <slug> --objective-file <file> \
  --colour BLUE --kit ~/BATTAGLIA-$(date +%Y%m%d)/DYNAMIC-WORKFLOW-<slug>
```

Fills `{{OBJECTIVE}} {{COLOUR}} {{FLOOR}} {{DATE}}` from the flags above and
`{{ARSENAL_LIVENESS}}` from `scripts/arsenal_probe.py --json` (600s timeout; every seat
`unknown` on probe failure, never omitted); writes `BRIEF.md`, `brief.sha`, `inputs.json` and
creates `r1/`, `r2/` under the kit. `{{SEAT}}` stays blank in the master;
`python3 scripts/dynamic_workflow.py check --kit K` recomputes the brief from `inputs.json` +
template and refuses (exit 1) if `BRIEF.md` differs by one byte, or the ledger fails its own
sha check — a hand-edited brief is not a brief (W78).
**Never add the convener's own design to the brief.** A changed brief is a new round, run
`brief` again with a new slug, never a hand patch.

## 2. Round 1 — sealed answers (one shot each, stdin closed, watchdog, content-judged)

The convening Fable window writes `r1/fable-5-1.md` itself, **before any other file lands**,
using the prompt prefix below plus the brief, then reads nothing else until R1 closes. It
launches only shell one-shots: no `Agent`, no `Workflow` (C8).

```
You are a coach in a sealed brainstorm. Use ONLY the brief below and the exact skeleton in §4.
No tools, no browsing, no file reads. Output only the answer.

<BRIEF.md>
```

```bash
python3 scripts/dynamic_workflow.py r1 --kit <K> --seats kimi-k3,qwen3.8-max,deepseek-v4-pro,gemini-3.1-pro-high [--astra-fallback]
```

- Refuses (exit 2) unless `r1/fable-5-1.md` already validates, and unless its mtime precedes
  the first `sent` ledger row — the convener answers first, checked, not just recorded.
- Per seat: copies the brief with `{{SEAT}}` filled, asserts its sha (SEAT blanked) equals
  `brief.sha`, launches ONE one-shot with `stdin=DEVNULL` and a per-kind timeout (kimi/TP1
  900s, agy 1500s, astra 1200s), writes `r1/<seat>.md`, appends a ledger row. Astra without
  `--astra-fallback` gets `awaiting-window` and no launch — Zero pastes the prompt into an
  open `gpt-6-astra` window by hand.
- A file is an answer only if `validate_answer` accepts it: frontmatter `seat:` +
  `objective_sha256:` matching `brief.sha` + non-empty `facts_cited:` + `assumptions:` + all
  seven `## ` sections present IN ORDER (`Formation`, `Tactics`, `Termination`, `Evidence
between stages`, `Never`, `First move`, `Cost`) + `Formation`/`Tactics` each carrying at
  least one table row past the header + ≤1,500 words. Empty, unparseable or truncated = `dead`:
  logged, relaunched at most once — a seat with two `sent` ledger rows already gets
  `refused-max-relaunch` on a third `r1`.
- `python3 scripts/dynamic_workflow.py validate <file> --sha <brief.sha>` runs the identical
  check standalone (`PASS`/`FAIL` + reason, exit 0/1) — use it to re-check a hand-pasted Astra
  answer before it counts as `answered`.
- Seat identity (PR2g'/PR2i): every seat FILE — `r1/<key>.md`, `r2/<key>.md`,
  `r2/<key>.rejected.md`, and the r1 sources that `judge`, `jury` and `anonymise` read — is
  named by the canonical key `_seat_key(seat)`: the seat's canonical spelling with `/` collapsed
  to `__` (alias `kimi-2.7` → `r1/kimi-code__kimi-for-coding-highspeed.md`). `ledger.md` rows,
  `pairing.md` cells, `judge.md` rows and stdout keep the RAW spelling passed to `--seats`. Two
  seats in `--seats` that resolve to one key are refused at `r1` before dispatch: exit 2, and
  the message names both spellings (`slug '<key>' already claimed by seat '<a>', seat '<b>'
collides`). A corrupt, empty or truncated `slugs.json` under the kit refuses with exit 2
  naming the file and the class (`UnicodeDecodeError`, `JSONDecodeError`, shape error);
  `slugs.json` and its `.lock`/`.tmp` sidecars are never captured (§8).
- `ledger.md` is append-only; `check` (§1) is what catches a tampered row.

## 3. Round 2 — one cross-family refutation

```bash
python3 scripts/dynamic_workflow.py r2 --kit <K>
```

Computes `pairing.md` deterministically (seeded on `brief.sha`): each answered seat (convener
excluded) gets exactly two R1 answers from two OTHER families, refusing if a seat can't find
two (insufficient diversity) or if `pairing.md` already exists and a recompute disagrees with
it — same brief, same pairing, every time. Sends "Object only where you can name an F/C and a
test that would settle it. No test, no objection." plus the two target answers, one shot, to
`r2/<seat>.md`. An objection paragraph without an `F\d+`/`C\d+` reference AND a `Test:` line is
split into `r2/<seat>.rejected.md`; the ledger row records `r2-kept=<n>-rejected=<m>` (stdout
prints `kept=<n> rejected=<m>` per seat — same numbers, different spelling). There is no
`r2b` — a seat that produced nothing usable here is not relaunched.

## 4. Judge, then jury — two separate subcommands, run in that order

```bash
python3 scripts/dynamic_workflow.py judge --kit <K>
python3 scripts/dynamic_workflow.py jury  --kit <K>
```

`judge` is MECHANICAL disqualification only, before any jury sees anything: C1 (banned-entity
regex — `ANTHROPIC_API_KEY`, `api_key=`, `from anthropic import`, `bedrock`, `vertex`, `agy
.*claude-`), C5 (the Tactics gate row must read `opus-5` / `window`), C8 (fable/astra rows
carry only role `coach`/`imperator`, every Tactics row has an integer round cap, every Never
bullet cites an F/C, ≤1,500 words). Writes `judge.md` — the pass/fail table jury reads back as
its own list of survivors; `jury` refuses (exit 2) if `judge.md` doesn't exist yet.

`jury` blinds every survivor to A–F (`jury/mapping.json`, chmod 600, same letters `anonymise`
below reuses), sends each juror the OTHER survivors' formations with the `seat:`/
`objective_sha256:` lines stripped, and asks for an integer 1–5 on six axes (termination, cost,
robustness, evidence, implementability, fit) as ONE markdown table, no prose. Each ballot is
persisted at `jury/ballot-<letter>.md` under the JUROR'S OWN letter, never its seat id — the
only place a seat id lives before reveal is `jury/mapping.json`. A ballot missing any letter it
was shown, or not a parseable table, is `dead` for that juror — no partial credit. The script
itself tabulates Borda + firsts into `jury/tabulation.md`; no synthesizer LLM writes this file.

## 5. Round 3 — synthesis by a fresh Opus 5 `xhigh` (not the convener)

New window, cwd outside the repo, reads `jury/tabulation.md` (and `r1/`/`r2/` for the
formations themselves) only, writes `DECISION.md`: per skeleton section, a table of
agreement/disagreement with seat names; which R2 objections survived (had a test); the
candidate formations side by side; each coach's `First move` with its `Bites:`. **It names
disagreements — it does not pick. No round 4.** This step is prose because judging open-ended
design agreement is not code's job; the tabulation it reads already is.

## 6. Zero picks — `Z-DECISIONI.md`

Zero names the coach (or an explicitly-stated merge of two). That text is the mandate — the
one step the launcher cannot run for Zero.

```bash
python3 scripts/dynamic_workflow.py reveal --kit <K>          # only after Z-DECISIONI.md exists
python3 scripts/dynamic_workflow.py anonymise --kit <K>       # (re)writes Z-BLIND/, if not already current
```

`reveal` refuses (exit 2) until `Z-DECISIONI.md` exists, then prints the letter→seat mapping
`jury`/`anonymise` already computed — it never computes one of its own — and writes
`jury/tabulation.revealed.md`, the same tabulation recomputed from the persisted per-juror
ballots but with seats named; `jury/tabulation.md` (the blind one) is never rewritten here.

## 7. The pick becomes the script

The BLUE Dux (Opus 5 window, not the imperator) writes `infra/workflows/<slug>.js` from the
chosen formation: `model:` pinned on every `agent()`, the round caps as literal counters, the
exit commands as the phase gates, dead-seat substitution read at start from
`~/.organism/arsenal/last.json` (`scripts/arsenal_probe.py --read-last`) —
`scripts/lint_workflow_script.py` enforces only the first and second of these (RULE 1
model-pin, RULE 3 bounded-rounds) in CI; exit-command phase gates and dead-seat substitution
are not linted. It runs via the `Workflow` tool inside a normal modus session; gate, ship and
prove-live are modus's, unchanged.

## 8. Capture (research convention §15)

```bash
python3 scripts/dynamic_workflow.py capture-check --kit <K> \
  --dest research/operations/<date>-dynamic-workflow-<slug>/
```

Requires `BRIEF.md`, `brief.sha`, `r1/`, `r2/`, `judge.md`, `jury/tabulation.md`,
`jury/tabulation.revealed.md`, `Z-DECISIONI.md`, `OUTCOME.md` (with `rounds_used`,
`dead_at_launch`, `wall_clock`, `bites` keys) — an unrevealed kit is not decided;
Copies exactly the nine required items and nothing else — `ledger.md`, `pairing.md`,
`inputs.json`, `slugs.json` (+ `.lock`/`.tmp`), `jury/mapping.json`, `jury/ballot-*.md` and
`Z-BLIND/` stay in the kit. Refuses before creating anything: exit
2 if `--dest` is not the canonical path above or already holds files, exit 3 if any required
file fails the same per-file PII gate `brief` uses — naming the FILE and the span COUNT only,
never the text. Exits non-zero naming whatever is missing rather than shipping a partial
capture — the outcome becomes the next brief's F-line.

## Selftest

```bash
python3 scripts/dynamic_workflow.py --selftest
```

Runs offline (`DW_FAKE_SEATS=1`, canned valid/invalid answers): PII gate refusal, brief sha
stability, the convener-first refusal, invalid-answer → dead → one relaunch → third-launch
refusal, ledger tamper detection. Section L runs under a temporary `REPO_ROOT` (PR2i):
`--selftest` writes nothing under the real `research/operations/` — prove it with a marker file
and `find research/operations -maxdepth 1 -newer <marker>` → empty. `scripts/tests/test_dynamic_workflow.py` (pytest,
`--collect-only` counts 112 cases) mirrors it; CI consumer arrives in PR3c
(`.github/workflows/dynamic-workflow-selftest.yml`).

## Invariants (bans as entities)

- Brief bytes identical across seats; answers move as bytes until R3; nobody rewrites a seat.
- The convener never summarises before R3, never fans out, never implements the pick.
- The gate is never an `agent()` lane and never cheaper than the builder.
- Judge by content, never by exit code or by a listing.
- The objective is PII-free or `brief` refuses at §0.
