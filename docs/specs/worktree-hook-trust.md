# Worktree push-hook trust

## Threat model and entity

The threat is a pusher script that lands a `git push` while the repository's trusted pre-push hook
is skipped. The entity is **the effective `core.hooksPath` Git resolves for that push invocation
equals the trusted root, and no flag disables hooks**. A matching substring is not evidence of it.

For the declared Codex autofix pusher the trusted root is the token `$TRUSTED_PREPUSH_HOOKS`; the
pusher prepares and verifies that bundle (`codex_auto_verify_trusted_prepush`) right before the push.

## What a static lint can and cannot prove

A shell script's semantics are not decidable from its text: functions, `sh -c`, command
substitution, unquoted expansion, `PATH` shadowing, abbreviated long options and `#` handling all
defeat an argv walk (14 X rows below were proven on a scratch remote to land a push with the hook
skipped while the previous argv-walking lint said TRUSTED). So the lint proves only the **absence of known
override shapes around one canonical push line**, nothing more.

## Decision rule (canonical form + denylist)

TRUSTED requires all of the following, after `shlex` with comments disabled:

1. the file has exactly one push, and its line reads `[if|!|then|do|elif|while|until]... git -c
core.hooksPath=<trusted root> push <args>`, quotes removed, nothing else between `git` and `push`;
2. each argument is `-u`/`--set-upstream`, a literal remote/ref, or a quoted `"$NAME"` that the
   file assigns exactly once to a literal value that cannot start a flag; after the arguments only
   redirections, a pipe or `then` follow, with no `$` and no backtick;
3. when the trusted root is a variable `$NAME`, that variable is bound as tightly as a push argument:
   the file assigns it exactly once (no `+=`, no `:=`, no `read`/`for`/`declare`/`export`/nameref
   target), and between that assignment and the push there is a reference to `"$NAME"` (the verify
   call). A canonical push line is worthless if the pusher can point `$NAME` at `/dev/null` first,
   even after the verify call (rows A19a-c), so the root is bound, not only the arguments;
4. nowhere in the file: a `GIT_*` assignment, a `--no-v*` prefix of `--no-verify`, `--config-env`,
   `--namespace`/`--git-dir`/`--work-tree`, `-c include*`/`-c alias.*`, `eval`, `exec` or
   `sh|bash|zsh -c` as a command word, `env -i`, a non-literal `git` binary, a `git` whose
   subcommand is built from `$` or a backtick, a function or alias named `git`, a `PATH` outside
   the system directories, or a `push` word other than `git stash push`, a quoted message on a line
   without `git`, or a `case` label `push|...)`.

Anything else is UNTRUSTED with the reason shown. The rule may over-refuse, never over-trust:
`-C` is refused on the push line only, because the real pusher runs one `git -C … fetch`.

## Corpus: guilt

Every row has the same id in the executable corpus. Git column = measured on a scratch bare remote
(git 2.54.0): SKIPPED = the push landed with the trusted hook skipped; RAN = the hook ran (the row
is refused conservatively); NOPUSH = git refused the command.

| id   | form                                                 | git     | verdict / reason                    |
| ---- | ---------------------------------------------------- | ------- | ----------------------------------- |
| G01  | later `-c core.hooksPath=/dev/null` (last `-c` wins) | SKIPPED | UNTRUSTED / hooks-path-setter-count |
| G02  | later lowercase `core.hookspath`                     | SKIPPED | UNTRUSTED / hooks-path-setter-count |
| G03  | later `Core.HooksPath`                               | SKIPPED | UNTRUSTED / hooks-path-setter-count |
| G04  | later double-quoted pair                             | SKIPPED | UNTRUSTED / hooks-path-setter-count |
| G05  | later single-quoted pair                             | SKIPPED | UNTRUSTED / hooks-path-setter-count |
| G06  | later empty value `-c core.hooksPath=`               | SKIPPED | UNTRUSTED / hooks-path-setter-count |
| G07  | sole setter with a wrong value                       | SKIPPED | UNTRUSTED / hooks-path-value        |
| G08  | `--config-env=core.hooksPath=HV`                     | SKIPPED | UNTRUSTED / config-env              |
| G09  | `--config-env core.hooksPath=HV`                     | SKIPPED | UNTRUSTED / config-env              |
| G10  | `GIT_CONFIG_PARAMETERS=…` on the push line           | RAN     | UNTRUSTED / git-config-env          |
| G11  | `GIT_CONFIG_COUNT/KEY/VALUE` on the push line        | RAN     | UNTRUSTED / git-config-env          |
| G12  | `GIT_CONFIG_GLOBAL=…`                                | RAN     | UNTRUSTED / git-config-env          |
| G13  | `GIT_CONFIG_SYSTEM=…`                                | RAN     | UNTRUSTED / git-config-env          |
| G14  | `GIT_DIR=…`                                          | RAN     | UNTRUSTED / relocation              |
| G15  | `GIT_WORK_TREE=…`                                    | RAN     | UNTRUSTED / relocation              |
| G16  | `git -C <dir>` on the push line                      | RAN     | UNTRUSTED / relocation              |
| G17  | `--git-dir=<dir>`                                    | RAN     | UNTRUSTED / relocation              |
| G18  | `--work-tree <dir>`                                  | RAN     | UNTRUSTED / relocation              |
| G19  | `-c includeIf.gitdir:<dir>.path=<cfg>`               | SKIPPED | UNTRUSTED / indirect-include        |
| G20  | `-c include.path=<cfg>`                              | SKIPPED | UNTRUSTED / indirect-include        |
| G21  | `push --no-verify`                                   | SKIPPED | UNTRUSTED / no-verify               |
| G22  | `-c alias.ship='… push' ship`                        | SKIPPED | UNTRUSTED / git-alias               |
| G23  | second push on the same line                         | SKIPPED | UNTRUSTED / multiple-pushes         |
| G24  | second push on a later line                          | SKIPPED | UNTRUSTED / multiple-pushes         |
| G25  | `eval '…push'`                                       | RAN     | UNTRUSTED / dynamic-command         |
| G26  | `$GIT … push`                                        | RAN     | UNTRUSTED / dynamic-command         |
| G27  | `git $OPTS … push`                                   | RAN     | UNTRUSTED / dynamic-command         |
| G28  | `env -i git … push`                                  | RAN     | UNTRUSTED / env-i                   |
| G29  | `--git-dir <dir>`                                    | RAN     | UNTRUSTED / relocation              |
| G30  | `--work-tree=<dir>`                                  | RAN     | UNTRUSTED / relocation              |
| G31  | extra `-c color.ui=false` before the token           | RAN     | UNTRUSTED / non-canonical           |
| G32  | extra `-c user.name=robot` after the token           | RAN     | UNTRUSTED / non-canonical           |
| G33  | `env LC_ALL=C git … push`                            | RAN     | UNTRUSTED / non-canonical           |
| X01  | abbreviated `push --no-verif`                        | SKIPPED | UNTRUSTED / no-verify               |
| X02  | second push through `/usr/bin/git`                   | SKIPPED | UNTRUSTED / git-binary              |
| X03  | second push inside `sh -c '…'`                       | SKIPPED | UNTRUSTED / shell-string            |
| X04  | second push after a mid-word `#`                     | SKIPPED | UNTRUSTED / multiple-pushes         |
| X05  | second push through a backtick-built `git`           | SKIPPED | UNTRUSTED / dynamic-command         |
| X06  | second push behind `--namespace <ns>`                | SKIPPED | UNTRUSTED / relocation              |
| X07  | wrapper function `g(){ git "$@"; }` then `g push`    | SKIPPED | UNTRUSTED / dynamic-command         |
| X08  | function named `git` that appends `--no-verify`      | SKIPPED | UNTRUSTED / git-shadowed            |
| X09  | `push $(…)` expanding to `--no-verify`               | SKIPPED | UNTRUSTED / dynamic-argument        |
| X10  | `--no-verify` after a ref containing `#`             | SKIPPED | UNTRUSTED / no-verify               |
| X11  | `-c core.hooksPath` without `=`                      | NOPUSH  | UNTRUSTED / hooks-path-setter-count |
| X12  | `push "$NV"`, `NV` never assigned in the file        | SKIPPED | UNTRUSTED / dynamic-argument        |
| X13  | `PATH=<dir>:$PATH` with a non-system directory       | SKIPPED | UNTRUSTED / path-override           |
| X14  | unquoted `push $EXTRA`                               | SKIPPED | UNTRUSTED / dynamic-argument        |
| X15  | `-c alias.push=…` (Git keeps the builtin)            | RAN     | UNTRUSTED / git-alias               |
| X17  | `NV=--no-verify` then `push "$NV"`                   | SKIPPED | UNTRUSTED / dynamic-argument        |
| X19  | push argument `"$B"` where `B` is a `read` target    | NOPUSH  | UNTRUSTED / dynamic-argument        |
| A19a | root rebound to `/dev/null` before the push          | SKIPPED | UNTRUSTED / root-rebound            |
| A19b | root rebound to empty before the push                | SKIPPED | UNTRUSTED / root-rebound            |
| A19c | root rebound after the verify call                   | SKIPPED | UNTRUSTED / root-rebound            |

## Corpus: innocence

Each innocence row carries the prepare-and-verify preamble, so the trusted root is bound once before
the push.

| id  | form                                                                  | git | verdict / reason             |
| --- | --------------------------------------------------------------------- | --- | ---------------------------- |
| I01 | preamble, then the real pusher line pushing `"$FIX_BRANCH"`           | RAN | TRUSTED / trusted-hooks-path |
| I04 | preamble, then the whole trusted pair quoted `-c "core.hooksPath=$T"` | RAN | TRUSTED / trusted-hooks-path |
| I06 | preamble, then literal arguments `push -u origin main`                | RAN | TRUSTED / trusted-hooks-path |

## Declared remainders

- A shell script's behaviour cannot be decided from its text; the lint proves the absence of the
  shapes above around one canonical line, nothing more.
- Not visible to it: a push issued by another script, including the library the pusher sources
  (`$CODEX_SEAT_LIB`), which could rebind the trusted-root variable after the lint has read the one
  in-file assignment; an alias in the user's Git configuration; a `git` binary planted in one of the
  system `PATH` directories; tampering with the contents of a correctly selected hook root. Trust in
  the sourced library and in the verify helper rests on review of that code, not on this lint:
  `codex_auto_verify_trusted_prepush` is required between the root assignment and the push, and its
  guarantee that the bundle is the reviewed one is a property of the helper, not of the text.
- Follow-up, out of scope here: a runtime witness. The trusted pre-push hook writes a marker keyed by
  the pushed SHA, and a reconciler compares the refs that reached the remote with the markers. That
  observes the entity instead of inferring it from text.
