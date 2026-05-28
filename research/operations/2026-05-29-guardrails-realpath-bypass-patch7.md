# Guardrails `cd`+`rm` / absolute-`$HOME` Bypass — Patch 7

_2026-05-29 WITA · branch `fix/guardrails-realpath-bypass-2026-05-29`_

## Executive Summary

The guardrails destructive-command evaluator (the PreToolUse hook that blocks
`rm -rf` against protected roots) could be bypassed by **changing directory
first and then issuing a relative `rm -rf`**, e.g.:

```bash
cd ~/Projects && rm -rf nuzantara
```

The pre-Patch-7 matcher only inspected the literal `rm` argument. Because
`nuzantara` is a *relative* path, it did not match the protected-root patterns
(`~`, `$HOME`, `/Users/nuzantara`, `/`), so the destructive command was
**ALLOWED**. The effective target after the `cd` was a protected directory.

Two adjacent argument forms were also under-covered:

- **Quoted / braced `$HOME`**: `rm -rf "$HOME"`, `rm -rf ${HOME}`,
  `rm -rf ${HOME}/Projects`.
- **Pre-expanded absolute home**: `rm -rf /Users/nuzantara`,
  `rm -rf /Users/nuzantara/Desktop` (the shell had already expanded `~`/`$HOME`
  before the string reached the matcher).

## Patch 7 (what changed)

Patch 7 hardens the static evaluator so it:

1. **Resolves the effective target of a `cd <dir> && rm -rf <rel>` chain** — when
   a command does `cd` into a protected root (`~`, `$HOME`, `${HOME}`,
   `/Users/nuzantara`, `/`) and then `rm -rf` a relative path (joined by `&&`
   *or* `;`), it now BLOCKS.
2. **Normalizes quoted/braced `$HOME`** (`"$HOME"`, `${HOME}`, `${HOME}/...`) to
   the protected-home form before matching.
3. **Treats pre-expanded absolute home paths** (`/Users/nuzantara`,
   `/Users/nuzantara/...`) as protected.

Legacy Patch-6 protections are preserved (`rm -rf /`, `rm -rf $HOME`,
`rm -rf ~`, `rm -rf ~/something`), and legitimate operations are still ALLOWED
with no new false positives (`rm -rf /tmp/...`, relative `rm -rf node_modules`,
`rm -f` of a single home file, `cd /tmp/work && rm -rf build`, `cd` + non-`rm`).

### Files changed by Patch 7 (NOT in this repo)

The hook logic is **user-global infrastructure** under `~/.claude/`, which is
gitignored and cannot be committed to this repo. Patch 7 was applied directly to
those two files on the operator machine:

| File | Role |
|---|---|
| `~/.claude/hooks/guardrails-static.py` | PreToolUse static evaluator (the synchronous BLOCK path) |
| `~/.claude/daemons/guardrails.py` | Guardrails daemon (the resident matcher) |

Because those live outside the repo, the only artifact that *can* be captured in
version control is the **regression test** — which is the point of this commit:
the test pins the contract so a future edit to the user-global hook that
re-introduces the bypass is caught.

## Regression test (the committed artifact)

`scripts/tests/test_guardrails_patch7_cd_rm_bypass.py` drives the **real hook**
as a subprocess with crafted Bash payloads and asserts BLOCK on every bypass
form plus ALLOW on legitimate ops. 24 cases:

- 12 new Patch-7 bypasses that MUST now BLOCK (the `cd`+`rm` chain in `&&` and
  `;` forms, quoted/braced `$HOME`, pre-expanded absolute home).
- 4 legacy Patch-6 cases that MUST still BLOCK.
- 8 legitimate ops that MUST still be ALLOWED (false-positive guards).

### Running it

```bash
python3 scripts/tests/test_guardrails_patch7_cd_rm_bypass.py
# → 24/24 passed   (exit 0)
```

The test resolves the hook at `~/.claude/hooks/guardrails-static.py` by default.
Override the path on a different machine/CI with:

```bash
GUARDRAILS_STATIC_HOOK=/path/to/guardrails-static.py \
  python3 scripts/tests/test_guardrails_patch7_cd_rm_bypass.py
```

If the hook is **absent** (e.g. fresh checkout / CI without the user-global
`~/.claude` tree), the test prints `SKIP:` and exits 0 rather than failing —
the hook is operator infra, not a repo dependency.

## Gotchas

- **The hook is the SSOT, the test is the witness.** Editing
  `~/.claude/hooks/guardrails-static.py` does not change anything in this repo;
  re-run this test after any future edit to confirm the contract still holds.
- **PreToolUse hooks need a Claude Code session restart to take effect** — an
  in-session edit of the hook will not change the live BLOCK behavior until the
  session restarts. The subprocess test bypasses that (it execs the file
  directly), so it reflects on-disk hook state immediately.
- **Skip-on-missing is intentional.** A hard failure on machines without
  `~/.claude` would make the suite non-portable; the env-override exists so CI
  can still opt in by pointing at a copy of the hook.
