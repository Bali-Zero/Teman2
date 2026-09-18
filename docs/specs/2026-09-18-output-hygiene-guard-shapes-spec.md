# Spec — the output-hygiene Bash guard: what an "unbounded" command is, stated once

**Date:** 2026-09-18 · **Status:** SPEC, not implemented · **Surface:** one PreToolUse hook under the `Bash`, `Read` (S9) and `Skill` (S10) matchers
(`infra/claude-hooks/output_hygiene_guard.py`, first attempted in PR #6724, SUSPENDED)

This spec exists because PR #6724 took three on-disk gate rounds (Opus 5, heads bd0a9a131a,
abae8f514b, f5bb4f868b) and each round found NEW over-matches on everyday commands outside the
previous round's surface. That is the Builder Contract's definition of an under-specified surface
(three reds, same cause — cicatrix family #3, guard over/under-match). The guard is not patched a
fourth time; it is re-implemented from a fresh `origin/main` against THIS document, and the gate of
that PR grades against the case table in §6, not against its own improvisation.

What the guard is for, unchanged from the mandate (Zero, 2026-09-18, long-session cost list,
point 6): a session must not be able to dump a 300-line directory listing or a whole log into its
own context by accident. Two incidents the same day: `ls ~/.nuzantara-mailbox` (957 entries) and
`ls evidence/2026-09` (300+). Every later turn re-read them.

**Revision S9/S10 (2026-09-18, same day, same mandate).** The `Bash` guard went live and the
next measured session (Zero's per-component table) still lost ~67K tokens through two doors this
spec had left open: the `Read` tool returned `MODEL_ROSTER.md` (46 KB),
`docs/architecture/dual-consul/army-map.md` (30 KB) and `FLEET_TOPOLOGY.json` (13 KB) whole, and
the built-in `claude-api` skill loaded 106 KB (~27K tokens) on its own "mandatory trigger" (any
prompt naming Claude/Anthropic/Opus/Sonnet...), teaching the paid per-token SDK path the Builder
Contract §3 bans. §8's reason for leaving `Read` out — "the harness already truncates it" — was
measured false: the harness caps LINES (2,000 per call), never bytes, and a 5,005-character line
came back whole. Per §8's own clause the two doors become S9 and S10 below: the same guard file,
registered under two more matchers.

---

## 1. Decision, not detection

The guard DENIES (exit 2 with a one-line reason and a suggestion) or ALLOWS (exit 0). It never
rewrites the command, never runs it, never prints file contents or the full command back. It
fails OPEN: any exception, malformed stdin, missing `command`, or `NUZ_OUTPUT_HYGIENE_OFF=1` is
exit 0. No subprocess. Latency budget: under 50 ms per call on M5.

A command is judged by its **segments**. The verdict is DENY if ANY segment is an unbounded shape
(§3) that is not bounded (§4) — otherwise ALLOW.

## 2. Segmentation — where the rounds went wrong first

1. **Strip** quoted strings (single, double, `$'…'`) and heredoc bodies (`<<TAG` … `TAG`,
   `<<'TAG'`, `<<-TAG`) to blanks of the same length, so byte offsets still resolve. Command
   substitutions `$(…)` and backticks are NOT stripped: what runs inside them also lands in the
   output when the outer command echoes it, but the inner command is judged as its own segment.
2. **Split** into segments on `|`, `||`, `&&`, `;`, `&` (background), AND on newlines. Round 3
   found `git status\ngit log` allowed because the splitter never split on `\n`; multi-line tool
   calls are the norm, not the exception.
3. **Peel prefixes** from each segment before recognising the shape, in this order, repeatedly:
   `cd X &&` (already consumed by splitting; remember X as the segment's cwd), leading
   `VAR=value` assignments, `env [VAR=value…]`, `time`, `timeout [-k …] <duration>`, `nice`,
   `sudo`, `command`, `exec`. `xargs` is not a prefix: it is a consumer (§4). Round 3: `timeout 300
pytest <dir>` and `FOO=1 pytest` were allowed because the trigger was anchored at `^`.
4. **Peel `git` global options** before the subcommand: `-C <path>`, `-c <k>=<v>`, `--no-pager`,
   `--git-dir=…`, `--work-tree=…`, `-p`/`--paginate`. Round 3: `git --no-pager log` was allowed.
5. **Resolve paths** relative to the segment's cwd (from `cd X &&`), else the payload `cwd`.
   `~` and `$HOME` expand to the home directory. Any other `$VAR` is unresolvable → that path
   contributes nothing (fail-open for that path, not for the segment).
6. A segment whose first word after peeling is `ssh`, `scp`, `rsync` is remote and ALLOWED as a
   whole — its output is somebody else's flood, and the remote command text is opaque.

## 3. Unbounded shapes (the complete list — adding one is a spec change)

| ID  | Shape           | Trigger, after §2 peeling                                                                                                                                                                                                                                                                                                                           | Own-bound (the command bounds itself)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| --- | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S1  | directory flood | `ls`, `eza`, `exa`, `tree`                                                                                                                                                                                                                                                                                                                          | none if recursive (`-R`, `--recursive`, `--tree`, `eza -T`, `tree` itself) → DENY regardless of count. Else DENY only if the **visible** entry count of ANY listed target > 150 (see §5). `-d` / `--directory` → ALLOW (lists the dir itself).                                                                                                                                                                                                                                                                               |
| S2  | file flood      | `cat`, `bat`, `batcat`                                                                                                                                                                                                                                                                                                                              | DENY if ANY named file > 24 KiB. A `cat > file <<EOF` / `cat > file` (stdout redirected) is a write, ALLOW. `cat` with no file (stdin) → ALLOW.                                                                                                                                                                                                                                                                                                                                                                              |
| S3  | git history     | `git log`, `git reflog`, `git shortlog`                                                                                                                                                                                                                                                                                                             | `-n N`, `-N`, `--max-count[= ]N`, any `..`/`...` range **with at least one side** (`main..`, `..HEAD`, `a..b`), `-1`, `--since`/`--until`/`--after`/`--before`, `-L`, `--` followed by a single path, `--format`/`--pretty` do NOT bound (a format still prints every commit).                                                                                                                                                                                                                                               |
| S4  | git patch       | `git diff`, `git show`, `git stash show`                                                                                                                                                                                                                                                                                                            | `--stat`, `--shortstat`, `--numstat`, `--name-only`, `--name-status`, `--dirstat`, `--summary`, `-s`, `--no-patch`, `--quiet`, `--exit-code`, `--check`, `--compact-summary`. `git show` of a tree-ish path (`git show HEAD:file`) is a file flood → judge as S2 by the blob size if resolvable, else ALLOW.                                                                                                                                                                                                                 |
| S5  | filesystem walk | `find`, `fd`, `fdfind`                                                                                                                                                                                                                                                                                                                              | `-maxdepth N` / `--max-depth N` / `-d N` (fd), `-name`/`-iname`/`-path` with a literal (no `*`) pattern, `-newer*`, `-mmin`/`-mtime`, `-delete` without `-print`/`-print0`/`-ls`/`-printf`/`-fprint`/`-fprint0`/`-fprintf`, `-type` alone does not bound. `fd <pattern>` with a non-empty pattern is ALLOW (fd requires a match).                                                                                                                                                                                            |
| S6  | recursive grep  | `grep -r`/`-R`/`--recursive`, `rg`, `ag`, `ack`                                                                                                                                                                                                                                                                                                     | `-l`, `-L`, `-c`, `-m N`/`--max-count[= ]N`, `--files-with-matches`, `--count`, `--stats`, `-q`; OR every non-flag target after the pattern is an existing regular FILE (a named file is not a flood). The pattern slot: the first non-flag token unless it was stripped as a quoted string (then the file may be the only token left). `grep` without `-r` and with a file target is not S6 at all.                                                                                                                         |
| S7  | test runner     | `pytest`, `python[3] -m pytest`, `npm test`, `pnpm test`, `yarn test`, `vitest`, `jest`, `mocha`, `go test`, `cargo test`, `npx <runner>`, `pnpm exec <runner>`, `bunx <runner>`                                                                                                                                                                    | `-q`/`--quiet` **as a flag OR inside a flag cluster** (`-xq`, `-qx`, `-sq`, `-qq`, `-rA -q`), `--tb=short`, `--tb=line`, `--tb=no`, `-x` alone does not bound, `--reporter=dot`/`--reporter dot`, `--silent`, `-k <expr>` alone does not bound.                                                                                                                                                                                                                                                                              |
| S8  | live tail       | `tail -f`/`-F`/`--follow`, `less +F`, `watch`, `journalctl -f`                                                                                                                                                                                                                                                                                      | never bounded by itself; `timeout N tail -f` IS bounded (the peeled `timeout` prefix is recorded as a bound for S8 only).                                                                                                                                                                                                                                                                                                                                                                                                    |
| S9  | file read       | tool `Read` (not Bash): `file_path` resolved against `cwd` (`~` expanded), a regular file whose suffix is not an image/PDF/notebook (`.png .jpg .jpeg .gif .webp .bmp .ico .tif .tiff .heic .svg .pdf .ipynb` — the harness renders those through its own path)                                                                                     | bounded when the slice the harness would return — `limit` lines (default 2,000) starting at 1-based line `offset` (absent or 0 = the first) — is ≤ 24 KiB of RAW bytes (S2's `MAX_FILE_BYTES`; the harness does not cap line length, measured). A missing path, a directory, an unreadable file, or a non-integer `offset`/`limit`: ALLOW (fail-open, the harness reports its own error). The message names the slice's KiB, the lines it spans, the file's total line count (counted up to 100,000) and the ≤ 24 KiB bound. |
| S10 | skill load      | tool `Skill` (not Bash): the bare skill name — `tool_input.skill` after its last `:` (`plugin:skill`, `dir:skill` forms) — is in the DENIED set, today exactly `claude-api` (a Claude Code BUILT-IN, 84 KiB, not disable-able through `enabledPlugins` — measured 2026-09-18 — and a manual for the paid per-token endpoint of Builder Contract §3) | never by size: this repo's own `modus` (79 KiB) and `intake` (57 KiB) are loaded whole by design, so a size rule would bite them; S10 is enumerated NAMES, and adding one is a spec change with its own C-row. Every other skill: ALLOW. The message names the skill, its size, the ban, and the two sanctioned substitutes (`claude-code-guide` agent, context7).                                                                                                                                                           |

Everything not in this table is ALLOWED. In particular `wc`, `head`, `tail -n`, `ls -d`, `du`,
`df`, `echo`, `printf`, `python3 -c`, `sed -n 'a,bp'` on their own are never denied; under the
`Read` and `Skill` matchers, every `tool_input` the S9/S10 rows do not name is ALLOWED.

## 4. Bounded downstream (any one is enough for the flood segment)

A flood segment is ALLOWED when, in the SAME pipeline (segments joined by `|` up to the next `;`,
`&&`, `||`, newline), ANY later segment starts with one of: `head`, `tail` (any form),
`wc`, `cut`, `grep -c`, `grep -m N`, `grep -l`, `jq`, `--jq` inside a `gh` call, `sed -n` with
an address range (quoted or bare), `awk` whose program contains `NR` (quoted or bare), `sort | uniq -c` (either), `xargs`,
`tee <file>` (stdout still flows — NOT a bound unless followed by another bound), `python3 -`
/ `python3 -c` (a consumer script), `md5`/`shasum`, `> /dev/null`, `>/dev/null`. Also when the
flood segment's own **stdout** is redirected to a file (`> f`, `>> f`, `&> f`, `>f 2>&1`,
`2>&1 >f`). A stderr-only redirect (`2>/dev/null`, `2>&1` alone, `2>f`) is NOT a bound — round 1
found `ls X 2>/dev/null` allowed for exactly this reason. Running in the background (`&` as the
segment terminator) is a bound (output goes to the task file, not the context).

## 5. Counting entries — visible, not raw

S1's count is what the command would PRINT: `os.listdir` minus dotfiles unless `-a`/`-A`/
`--all`/`--almost-all` is present (round 3: `ls ~` printed 55 lines but was denied as
"190-entry" because dotfiles were counted). Every listed target counts separately; the
verdict is on the maximum; a target that is a file or unresolvable counts as 0. `ls` with no
target counts the segment cwd. The threshold is **150 visible entries**: the repo root (71
visible) and `infra/claude-hooks` (76) must pass; `~/.nuzantara-mailbox` (957) and
`evidence/2026-09` (300+) must not. The message names the count and the first over-threshold
target, truncated to 80 chars, never the entries.

## 6. Case corpus — the gate grades against THIS table, by ID

Each case is a full command as a session would type it, judged with `cwd` = the repo root of a
checkout at `origin/main`, `HOME` a fixture with a 957-entry `mailbox/broadcast`, and fixtures
`bigdir/` (151 visible), `middir/` (100 visible), `dotdir/` (30 visible + 160 dotfiles),
`small.py` (1 KiB), `big.log` (25 KiB, one line), `huge.md` (100 KiB: 1,600 lines of 64 bytes),
`photo.png` (200 KiB of bytes; only the suffix matters). Every case from rounds 1-3 is here; a new round may ADD
cases, and an added case that flips the verdict of an existing one is a spec change, not a patch.
Rows written as `Read(path[, offset=N][, limit=N])` or `Skill(name)` are probed with `tool_name`
`Read`/`Skill` and exactly that `tool_input` (relative paths against the fixture `cwd`), never as
a Bash command.

| ID  | Command                                                           | Verdict | Why                                                    |
| --- | ----------------------------------------------------------------- | ------- | ------------------------------------------------------ |
| C01 | `ls` (at repo root, 71 visible)                                   | ALLOW   | S1 under threshold                                     |
| C02 | `ls -la` (repo root)                                              | ALLOW   | 71 + dotfiles still < 150                              |
| C03 | `ls ~/mailbox/broadcast`                                          | DENY    | S1 957 visible                                         |
| C04 | `ls ~/mailbox/broadcast 2>/dev/null`                              | DENY    | stderr redirect is not a bound                         |
| C05 | `ls ~/mailbox/broadcast \| head -5`                               | ALLOW   | bounded by head                                        |
| C06 | `ls ~/mailbox/broadcast > /tmp/x.txt`                             | ALLOW   | stdout redirected                                      |
| C07 | `ls -R apps`                                                      | DENY    | recursive, count irrelevant                            |
| C08 | `eza -T smalldir`                                                 | DENY    | recursive                                              |
| C09 | `ls ~` (dotdir semantics: 30 visible)                             | ALLOW   | visible count, not raw                                 |
| C10 | `ls -a dotdir`                                                    | DENY    | 190 with `-a`                                          |
| C11 | `ls infra apps ~/mailbox/broadcast`                               | DENY    | every target counted                                   |
| C12 | `ls -d ~/mailbox/broadcast`                                       | ALLOW   | `-d` lists the dir itself                              |
| C13 | `cat big.log`                                                     | DENY    | S2 > 24 KiB                                            |
| C14 | `cat big.log \| jq .`                                             | ALLOW   | consumer                                               |
| C15 | `cat > out.txt <<'EOF'` + body with `find . -name x`              | ALLOW   | heredoc body stripped, stdout redirected               |
| C16 | `git log`                                                         | DENY    | S3 unbounded                                           |
| C17 | `git log --oneline origin/main..HEAD`                             | ALLOW   | range                                                  |
| C18 | `git log --oneline main..`                                        | ALLOW   | one-sided range                                        |
| C19 | `git log --format=%H`                                             | DENY    | format does not bound                                  |
| C20 | `git --no-pager log`                                              | DENY    | global option peeled, still S3                         |
| C21 | `git -C ~/nuzantara log`                                          | DENY    | same                                                   |
| C22 | `git log -1 --format=%cd -- CLAUDE.md`                            | ALLOW   | `-1`                                                   |
| C23 | `git diff`                                                        | DENY    | S4                                                     |
| C24 | `git diff --stat`                                                 | ALLOW   | own-bound                                              |
| C25 | `git diff --quiet && echo clean`                                  | ALLOW   | prints nothing                                         |
| C26 | `git show -s --format=%H HEAD`                                    | ALLOW   | no patch                                               |
| C27 | `git show --no-patch HEAD`                                        | ALLOW   | no patch                                               |
| C28 | `git -c core.pager=cat diff`                                      | DENY    | global `-c` peeled, still S4                           |
| C29 | `find . -name '*.x'`                                              | DENY    | S5 no depth, glob pattern does not bound               |
| C30 | `find . -maxdepth 2 -name x`                                      | ALLOW   | depth                                                  |
| C31 | `find . -name x \| head`                                          | ALLOW   | consumer                                               |
| C32 | `rg foo`                                                          | DENY    | S6 no target, no bound                                 |
| C33 | `rg foo small.py`                                                 | ALLOW   | named file                                             |
| C34 | `rg "def main" small.py`                                          | ALLOW   | quoted pattern stripped, file still named              |
| C35 | `rg foo small.py apps`                                            | DENY    | a directory target                                     |
| C36 | `rg --max-count 5 foo apps`                                       | ALLOW   | long-form `-m`                                         |
| C37 | `grep -rn foo . \| head`                                          | ALLOW   | consumer                                               |
| C38 | `grep -n foo small.py`                                            | ALLOW   | not recursive                                          |
| C39 | `pytest scripts/tests`                                            | DENY    | S7                                                     |
| C40 | `pytest -q scripts/tests`                                         | ALLOW   | `-q`                                                   |
| C41 | `pytest -xq scripts/tests`                                        | ALLOW   | cluster contains `q`                                   |
| C42 | `pytest -qq scripts/tests`                                        | ALLOW   | cluster                                                |
| C43 | `python3 -m pytest scripts/tests`                                 | DENY    | python -m form                                         |
| C44 | `timeout 300 pytest scripts/tests`                                | DENY    | prefix peeled                                          |
| C45 | `FOO=1 pytest scripts/tests`                                      | DENY    | assignment peeled                                      |
| C46 | `npx vitest run`                                                  | DENY    | package runner                                         |
| C47 | `npx jest -q`                                                     | ALLOW   | `-q`                                                   |
| C48 | `pytest scripts/tests 2>&1 \| tail -20`                           | ALLOW   | consumer                                               |
| C49 | `tail -f x.log`                                                   | DENY    | S8                                                     |
| C50 | `timeout 10 tail -f x.log`                                        | ALLOW   | timeout bounds S8                                      |
| C51 | `tail -n 20 x.log`                                                | ALLOW   | not S8                                                 |
| C52 | `git status` + newline + `git log`                                | DENY    | newline split                                          |
| C53 | `cd apps` + newline + `ls ~/mailbox/broadcast`                    | DENY    | newline split, cwd tracked                             |
| C54 | `echo "git log"`                                                  | ALLOW   | quoted                                                 |
| C55 | `ssh pro 'git log'`                                               | ALLOW   | remote                                                 |
| C56 | `ls "$UNKNOWN_VAR/x"`                                             | ALLOW   | unresolvable path, fail-open                           |
| C57 | `NUZ_OUTPUT_HYGIENE_OFF=1` in env, any of C03/C16/C39             | ALLOW   | kill switch                                            |
| C58 | stdin empty / not JSON / a list / `command: 123` / tool `Edit`    | exit 0  | fail-open                                              |
| C59 | `ls ~/mailbox/broadcast &`                                        | ALLOW   | background                                             |
| C60 | `git log \| git diff --stat $(git merge-base main HEAD)`          | DENY    | first segment unbounded (tee/pipe into a non-consumer) |
| C61 | `find . -name x`                                                  | ALLOW   | literal -name is an S5 own-bound (§3 row)              |
| C62 | `cat big.log \| sed -n '1,40p'`                                   | ALLOW   | §4 sed -n range, quoted                                |
| C63 | `cat big.log \| awk 'NR<=20'`                                     | ALLOW   | §4 awk NR bound, quoted                                |
| C64 | `find /tmp/x -depth -delete`                                      | ALLOW   | S5 own-bound: -delete prints nothing                   |
| C65 | `find . -name '*.pyc' -delete`                                    | ALLOW   | S5 own-bound: -delete, glob irrelevant                 |
| C66 | `find . -delete -print`                                           | DENY    | -print re-opens the walk's output                      |
| C67 | `Read(huge.md)`                                                   | DENY    | S9: default slice = 1,600 lines = 100 KiB              |
| C68 | `Read(huge.md, limit=200)`                                        | ALLOW   | S9 own-bound: slice 12.5 KiB                           |
| C69 | `Read(huge.md, offset=1500)`                                      | ALLOW   | S9 own-bound: ~100 lines left, ~6 KiB                  |
| C70 | `Read(huge.md, offset=10, limit=1000)`                            | DENY    | S9: slice 62.5 KiB                                     |
| C71 | `Read(big.log)`                                                   | DENY    | S9: 25 KiB in ONE line, no line cap (C13 twin)         |
| C72 | `Read(small.py)`                                                  | ALLOW   | S9 under threshold                                     |
| C73 | `Read(photo.png)`                                                 | ALLOW   | S9 exempt suffix, rendered not read                    |
| C74 | `Read(missing.md)` / `Read(bigdir)`                               | ALLOW   | not a regular file — fail-open                         |
| C75 | `Read(huge.md, limit="200")`                                      | exit 0  | non-integer bound — fail-open, harness rejects it      |
| C76 | `Skill(claude-api)`                                               | DENY    | S10 denied name                                        |
| C77 | `Skill(anthropic-agent-skills:claude-api)`                        | DENY    | S10: bare name after the last `:`                      |
| C78 | `Skill(modus)`                                                    | ALLOW   | S10 is names, not size — 79 KiB whole by design        |
| C79 | `NUZ_OUTPUT_HYGIENE_OFF=1` in env, C67 / C76                      | ALLOW   | kill switch (C57 twin)                                 |
| C80 | `Read` without `file_path` / `Skill` without `skill` / `skill: 7` | exit 0  | fail-open (C58 twin)                                   |

## 7. Tests and gate contract for the re-implementation

- `infra/claude-hooks/test_output_hygiene_guard.py` carries every C-case above with its ID in
  the case label; the shared vaccine `test_hook_innocence.py` carries at least C01, C03, C04,
  C07, C16, C17, C24, C25, C33, C39, C41, C46, C52, C55 (the ones that bit or leaked in a gate),
  and C67, C68, C71, C76, C78 for the S9/S10 doors.
- The gate prompt for that PR cites this spec by path and asks the grader to probe the C-table
  first, then to add at most FIVE shapes of its own; a new over-match on an everyday command is
  REWORK-BUILD as before, and the cure is an ADDED case + a diff that keeps every existing case
  green — never a threshold or regex tweak that is not traceable to a case ID.
- Registration: guard-conformance census (`infra/guard-conformance/registry.json`) with
  guilt+innocence proofs, declared HOME-fork pair in `infra/home-fork/declared-pairs.json`,
  installed by the shipping session into the PreToolUse `Bash` matcher of `~/.claude/settings.json`
  on M5 and Pro right after merge; the Bites observation is a live denial of C03 with the count
  in the message and a live pass of C05. Since S9/S10 the same command is registered under the
  `Read` and `Skill` matchers too (one entry each); their Bites observation is a live denial of
  `Read MODEL_ROSTER.md` naming the slice's KiB and line count, a live pass of the same `Read`
  with `limit=120`, and a live denial of `Skill claude-api` naming the substitutes.

## 8. What is deliberately out of scope

`curl`/`wget` bodies, `docker logs`, `kubectl logs`, `fly logs` (each has its own follow flag
and its own consumers, and none caused an incident), MCP tool outputs, and every skill NOT in
the S10 set (a skill is loaded whole by design). The `Read` tool left this list on 2026-09-18
as S9 and `Skill` entered as S10 — measured, not assumed (revision note above). If one of these
bites, it becomes S11 by a spec revision.
