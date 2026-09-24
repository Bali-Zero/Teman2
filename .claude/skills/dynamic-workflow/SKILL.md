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
  --colour BLUE [--floor <floor>] [--template <path>] \
  --kit ~/BATTAGLIA-$(date +%Y%m%d)/DYNAMIC-WORKFLOW-<slug>
```

`--template` defaults to `.claude/skills/dynamic-workflow/brief.template.md` — the file beside
this one, which is why the template ships with the skill and not with the launcher. Without it
`brief` refuses before writing anything (`refused: template not found at <path> (pass
--template)`). `--kit` must resolve outside the repo, or exit 2.

Fills `{{OBJECTIVE}} {{COLOUR}} {{FLOOR}} {{DATE}}` from the flags above and
`{{ARSENAL_LIVENESS}}` from `scripts/arsenal_probe.py --json` (600 s timeout; every seat
`unknown (probe failed)` on probe failure, never omitted); writes `BRIEF.md`, `brief.sha`,
`inputs.json` and creates `r1/`, `r2/` under the kit. `{{SEAT}}` stays blank in the master;
`python3 scripts/dynamic_workflow.py check --kit K` recomputes the brief from `inputs.json` +
template and refuses (exit 1) if `BRIEF.md` differs by one byte, or the ledger fails its own
sha check — a hand-edited brief is not a brief (W78).
**Never add the convener's own design to the brief.** A changed brief is a new round, run
`brief` again with a new slug, never a hand patch.

The squad block that lands in `BRIEF.md` is four columns — `seat | status | healthy |
latency_ms` — and carries NONE of the probe's own `evidence` field: that field is raw CLI output
(hook noise, error JSON, org/repo names) and crossing the output boundary with it buys a coach
nothing. A seat whose probe status is exactly `TIMEOUT` renders as `unknown (probe budget 15 s)`
with `healthy` rewritten to `unknown` too, and a fixed sentence under the table states that
`unknown` is not `dead`: the probe's budget is far shorter than a real round's, and a false-dead
table rewrote every formation in the first real run.

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
python3 scripts/dynamic_workflow.py r1 --kit <K> --register astra   # hand-pasted window answer
```

- Refuses (exit 2) unless `r1/fable-5-1.md` already validates, and unless its mtime precedes the
  first `sent` ledger row — the convener answers first, checked, not just recorded.
- Per seat: copies the brief with `{{SEAT}}` filled, asserts its sha (SEAT blanked) equals
  `brief.sha`, launches ONE one-shot with `stdin=DEVNULL`, a per-kind timeout (kimi/TP1 900 s,
  agy 1500 s, astra 1200 s) and **cwd set to a fresh empty temp dir** — launched from the repo,
  a seat with tools reads the launcher's source instead of answering blind, which is what the
  kimi seat did in the first real round. Astra's `codex exec -o` target lives in that same
  per-call temp dir, never in the kit, so r2 and jury cannot overwrite its R1 answer and a
  relaunch that writes nothing returns empty rather than the previous attempt's bytes. Writes
  `r1/<key>.md`, appends a ledger row. Astra without `--astra-fallback` gets `awaiting-window`
  and no launch — Zero pastes the prompt into an open `gpt-6-astra` window by hand.
- A coach CLI's transport wrapper is stripped before any check sees the text: CRLF/CR → LF, a
  whole-answer ` ``` ` fence, and `kimi --output-format text`'s own `• `/two-space
  decoration plus its trailing "To resume this session:" paragraph. Judging those bytes instead
  of the answer is what ledgered four substantive answers `dead` in the first real round. The
  raw bytes always survive beside the normalised file (in round 2, `r2/<key>.raw.md`).
- A file is an answer only if `validate_answer` accepts it: frontmatter `seat:` +
  `objective_sha256:` matching `brief.sha` + non-empty `facts_cited:` + `assumptions:` + all
  seven `## ` sections present IN ORDER (`Formation`, `Tactics`, `Termination`, `Evidence
between stages`, `Never`, `First move`, `Cost`) + `Formation`/`Tactics` each carrying at
  least one table row past the header — a markdown separator row (`|---|`) is not a data row —
  and ≤1,500 words. Empty, unparseable or truncated = `dead`: logged, relaunched at most once — a
  seat with two `sent` ledger rows already gets `refused-max-relaunch` on a third `r1`.
- `python3 scripts/dynamic_workflow.py validate <file> --sha <brief.sha>` runs the identical
  check standalone (`PASS`/`FAIL` + reason, exit 0/1) — use it to re-check a hand-pasted Astra
  answer before it counts as `answered`.
- `r1 --register <seat>` is the only path that turns a window answer into an `answered` row: it
  reads `r1/<key>-window.md`, normalises it exactly like a dispatched seat's output, validates
  it against `brief.sha`, and on PASS writes `r1/<key>.md` plus an `answered` row stamped at the
  WINDOW FILE's own mtime (the human pasted it then, not at register time). It refuses (exit 2)
  before touching the window file if the seat is already `answered` or was never marked
  `awaiting-window`, and on a failing paste it records `window-invalid` and exits 1.
- Seat identity (PR2g'/PR2i): every seat FILE — `r1/<key>.md`, `r2/<key>.md`,
  `r2/<key>.rejected.md`, and the r1 sources that `judge`, `jury` and `anonymise` read — is
  named by the canonical key `_seat_key(seat)`: the seat's canonical spelling with `/` collapsed
  to `__` (alias `kimi-2.7` → `r1/kimi-code__kimi-for-coding-highspeed.md`). `ledger.md` rows,
  `pairing.md` cells, `judge.md` rows and stdout keep the RAW spelling passed to `--seats`. Two
  seats in `--seats` that resolve to one key: the second is refused at `r1` before its own
  dispatch, with both spellings in the message (`slug '<key>' already claimed by seat '<a>',
seat '<b>' collides`); the first seat of the pair has already been launched. A corrupt, empty or
  truncated `slugs.json` under the kit refuses with exit 2 naming the file and the class
  (`UnicodeDecodeError`, `JSONDecodeError`, shape error); `slugs.json` and its `.lock`/`.tmp`
  sidecars are never captured (§8).
- `ledger.md` is append-only, and every append holds `ledger.md.lock` (`fcntl.flock`) across
  append → hash → `.sha` write, so a concurrent writer can no longer leave a `.sha` describing
  fewer rows than the ledger holds; `check` (§1) is what catches a tampered row.

## 3. Round 2 — one cross-family refutation

```bash
python3 scripts/dynamic_workflow.py r2 --kit <K>
```

Computes `pairing.md` deterministically (seeded on `brief.sha`): each answered seat (convener
excluded) gets exactly two R1 answers from two OTHER families, refusing if a seat can't find
two (insufficient diversity) or if `pairing.md` already exists and a recompute disagrees with
it — same brief, same pairing, every time. Sends "Object only where you can name an F/C and a
test that would settle it. No test, no objection." plus the sealed sentence, plus the SHAPE it
parses, plus the two target answers, one shot, to `r2/<key>.md`. **The shape it keeps, stated in
the prompt because a filter nobody is told about discards good work:**

- one paragraph per objection, paragraphs separated by a blank line; each paragraph cites at
  least one `F<n>`/`C<n>` and carries a line that starts with `Test:`; or
- ONE markdown table whose header names a `test`/`tests` column (matched as a whole WORD, so
  "Latest status" or "Contested by" is not a test column). Then each DATA row is one objection:
  kept iff the row carries an F/C ref anywhere and its test cell is non-empty after stripping
  (`-`, `—`, `n/a`, `none`, `tbd` read as empty). The separator row is never a data row.

Kept units land in `r2/<key>.md`, rejected ones in `r2/<key>.rejected.md`, and a split table is
re-emitted on both sides as valid markdown (original header + separator + that side's rows).
The ledger row records `r2-kept=<n>-rejected=<m>`; an EMPTY raw output is `r2-dead`, a state of
its own and never `kept=0` (stdout prints `kept=<n> rejected=<m>`, or `dead (empty output)`).
There is no `r2b` — a seat that produced nothing usable here is not relaunched.

## 4. Judge, then jury — two separate subcommands, run in that order

```bash
python3 scripts/dynamic_workflow.py judge --kit <K>
python3 scripts/dynamic_workflow.py jury  --kit <K>
```

`judge` is MECHANICAL disqualification only, before any jury sees anything, and it judges
ENTITIES rather than spellings the brief never asked for:

- **C1** — banned-entity regex (`ANTHROPIC_API_KEY`, `api_key=`, `from anthropic import`,
  `bedrock`, `vertex`, `agy .*claude-`). A match inside a `## Never` bullet is the coach CITING
  the ban, which the brief's own C1 invites, and is forgiven; forgiveness is by POSITION, so a
  byte-identical bullet outside `## Never` is still a use, and a match in the frontmatter is
  never forgiven.
- **C5** — the LAST Tactics row whose stage names a `gate`/`gates` as a whole word decides (a
  coach may list pre-gates before its final one). That row's seat must match `opus-5-5` as an
  entity (RULED 2026-09-23, `opus-5-5` replaces `opus-5` in every seat) — `opus-5-5`,
  `Opus 5.5`, `fresh opus-5-5 xhigh` pass; `opus-5`, `opus-5-50`, `opus-5.55`, `opus-5-1` do
  not — and its mode must contain the word `window`/`windows`.
- **C8** — `fable-5-1`/`astra` Formation rows carry only role `coach`/`imperator`; EVERY Tactics
  row carries a bare-integer round cap in column 5 (`3`, not "3 rounds"); every `## Never` bullet
  cites an F/C; ≤1,500 words.

Writes `judge.md` — the pass/fail table jury reads back as its own list of survivors. `jury`
refuses (exit 2) if `judge.md` doesn't exist yet, and refuses again (exit 2) if judge
disqualified every answered seat: zero survivors is not a green round, it is a round with
nothing to score.

`jury` blinds every survivor to A–F (`jury/mapping.json`, chmod 600, same letters `anonymise`
below reuses), sends each juror the OTHER survivors' formations with the `seat:`/
`objective_sha256:` lines stripped, and asks for an integer 1–5 on six axes (termination, cost,
robustness, evidence, implementability, fit) as ONE markdown table, no prose. Each ballot is
persisted at `jury/ballot-<letter>.md` under the JUROR'S OWN letter, never its seat id — the
only place a seat id lives before reveal is `jury/mapping.json`. A ballot missing any letter it
was shown, or not a parseable table, is `dead` for that juror — no partial credit. The script
itself tabulates Borda + firsts into `jury/tabulation.md`; no synthesizer LLM writes this file.

## 5. Round 3 — synthesis by a fresh Opus 5.5 `xhigh` (not the convener)

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

The BLUE Dux (Opus 5.5 window, not the imperator) writes `infra/workflows/<slug>.js` from the
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
`dead_at_launch`, `wall_clock`, `bites` keys) — an unrevealed kit is not decided. It copies
exactly the nine required items and nothing else — `ledger.md`, `pairing.md`, `inputs.json`,
`slugs.json` (+ `.lock`/`.tmp`), `jury/mapping.json`, `jury/ballot-*.md` and `Z-BLIND/` stay in
the kit. Refuses before creating anything: exit 2 if `--dest` is not the canonical path above or
already holds files, exit 3 if any required file fails the same per-file PII gate `brief` uses —
naming the FILE and the span COUNT only, never the text. Exits non-zero naming whatever is
missing rather than shipping a partial capture — the outcome becomes the next brief's F-line.

## Selftest

```bash
python3 scripts/dynamic_workflow.py --selftest
```

Runs offline (`DW_FAKE_SEATS=1`, canned valid/invalid answers) through lettered sections A–Q:
PII gate refusal, brief sha stability, `check` on an untouched vs hand-edited kit, ledger tamper
detection, the convener-first refusal, invalid-answer → dead → one relaunch → third-launch
refusal, deterministic r2 pairing and the objection filter, judge C1/C5/C8, the blind jury with
its Borda tabulation and one dead ballot, the full anonymise chain, `reveal`'s seal,
`capture-check`, wrapper normalisation, attempt preservation and `r1 --register`. The
`capture-check` section (labelled `N.`) runs under a temporary `REPO_ROOT` (PR2i): `--selftest`
writes nothing under the real `research/operations/` — prove it with a marker file and
`find research/operations -maxdepth 1 -newer <marker>` → empty.

`scripts/tests/test_dynamic_workflow.py` (pytest) mirrors it. Its case count grows with every
launcher PR, so read it from
`python3 -m pytest scripts/tests/test_dynamic_workflow.py --collect-only -q -p no:cacheprovider | tail -1`
rather than from a number frozen in this file. CI consumer:
`.github/workflows/dynamic-workflow-selftest.yml` runs `--selftest`, that suite and
`scripts/tests/test_dynamic_workflow_skill.py` (this skill's own guard) on every PR touching the
launcher, its tests, or this skill directory.

## Invariants (bans as entities)

- Brief bytes identical across seats; answers move as bytes until R3; nobody rewrites a seat.
- The convener never summarises before R3, never fans out, never implements the pick.
- The gate is never an `agent()` lane and never cheaper than the builder.
- Judge by content, never by exit code or by a listing.
- An empty outcome is never a green one: `r2-dead`, `jury` on zero survivors, `capture-check` on
  a missing file all refuse instead of reporting a round that never happened.
- The objective is PII-free or `brief` refuses at §0.

## Source map — every CLI fact above, at the symbol that enforces it

> Cited by SYMBOL, not by line: a launcher line number is stale the next time anything above it
> is edited, and this lane merges a launcher PR most days. `scripts/tests/test_dynamic_workflow_skill.py`
> requires every symbol below to still occur in `scripts/dynamic_workflow.py` and the set here to
> equal its own curated list, both ways — so a fact whose enforcement was renamed or deleted goes
> red, while a fact that merely moved does not. Re-point by symbol, never delete.

| fact (§)                                                                    | source                                                             |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `brief` needs no `--template`: the default is the file beside this one (§1) | (source: scripts/dynamic_workflow.py::DEFAULT_TEMPLATE)            |
| the probe budget the squad block reports (§1)                               | (source: scripts/dynamic_workflow.py::PROBE_TIMEOUT_S)             |
| the fixed `unknown` is not `dead` sentence under the table (§1)             | (source: scripts/dynamic_workflow.py::_ARSENAL_UNKNOWN_NOTE)       |
| per-kind one-shot timeouts (§2)                                             | (source: scripts/dynamic_workflow.py::SEAT_TIMEOUTS)               |
| the arsenal probe's own 600 s budget (§1)                                   | (source: scripts/dynamic_workflow.py::_arsenal_liveness_block)     |
| the squad block's four columns, `evidence` absent (§1)                      | (source: scripts/dynamic_workflow.py::latency_ms)                  |
| the ledger lock held across append → hash → `.sha` (§2)                     | (source: scripts/dynamic_workflow.py::_ledger_lock)                |
| a markdown separator row is not a data row (§2)                             | (source: scripts/dynamic_workflow.py::_is_md_separator_row)        |
| what makes a file an answer (§2)                                            | (source: scripts/dynamic_workflow.py::validate_answer)             |
| wrapper normalisation before any check sees the text (§2)                   | (source: scripts/dynamic_workflow.py::_normalise_seat_output)      |
| `--kit` must resolve outside the repo (§1)                                  | (source: scripts/dynamic_workflow.py::_ensure_outside_repo)        |
| the refusal when the template is missing (§1)                               | (source: scripts/dynamic_workflow.py::template not found)          |
| the sealed sentence every round's prompt carries (§2, §3)                   | (source: scripts/dynamic_workflow.py::_SEALED_SENTENCE)            |
| one shot, stdin closed, empty temp cwd, astra's `-o` outside the kit (§2)   | (source: scripts/dynamic_workflow.py::_launch_seat)                |
| the canonical key every seat FILE is named by (§2)                          | (source: scripts/dynamic_workflow.py::_seat_key)                   |
| the two-seats-one-key refusal, both spellings named (§2)                    | (source: scripts/dynamic_workflow.py::already claimed by seat)     |
| `r1 --register`, the only path from a window answer to `answered` (§2)      | (source: scripts/dynamic_workflow.py::_cmd_r1_register)            |
| the r2 prompt stating the shape it parses (§3)                              | (source: scripts/dynamic_workflow.py::_R2_PROMPT_PREFIX)           |
| one objection per table row, kept or rejected (§3)                          | (source: scripts/dynamic_workflow.py::_filter_objection_paragraph) |
| `r2-dead` is a state of its own (§3)                                        | (source: scripts/dynamic_workflow.py::r2-dead)                     |
| C1 forgiven inside a `## Never` bullet, by position (§4)                    | (source: scripts/dynamic_workflow.py::_check_c1)                   |
| C5 reads the LAST gate row, seat and mode as entities (§4)                  | (source: scripts/dynamic_workflow.py::_check_c5)                   |
| C8's bare-integer round cap and Never-bullet F/C (§4)                       | (source: scripts/dynamic_workflow.py::_check_c8)                   |
| the six jury axes (§4)                                                      | (source: scripts/dynamic_workflow.py::JURY_AXES)                   |
| `jury` refuses on zero survivors (§4)                                       | (source: scripts/dynamic_workflow.py::0 surviving formations)      |
| the nine items `capture-check` requires and copies (§8)                     | (source: scripts/dynamic_workflow.py::_CAPTURE_REQUIRED)           |
| `OUTCOME.md`'s four required keys (§8)                                      | (source: scripts/dynamic_workflow.py::_OUTCOME_KEYS)               |
