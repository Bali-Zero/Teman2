# secret_expansion_guard — shapes spec and case corpus

Status: ACCEPTED at the BLUE gate 2026-09-19 with fixes (PROPOSED 2026-09-18). Implementation `infra/claude-hooks/secret_expansion_guard.py`,
registry `infra/claude-hooks/secret-expansion-registry.json`, tests graded against §5 of this file.

Precedent and reason this file exists first: `output_hygiene_guard` v1 (PR #6724) was **SUSPENDED at
three on-disk gate rounds, each finding a NEW over-match on an everyday command** (cicatrix superscar
#3), and v2 was re-implemented _against a spec and a case corpus_ rather than against its own
improvisation. A guard that denies a credential expansion is far more over-match-prone than one that
denies output volume, because the sanctioned and the leaking forms differ by **one character**
(`${VAR:+SET}` vs `${VAR:-UNSET}`). So the corpus is written before the code, and the code is graded
against it. Where this file and the implementation disagree, **this file wins**.

## 1. The problem, measured — not hypothetical

On 2026-09-18, three separate agent sessions on Air-M5 put the live Alibaba Token-Plan key into a
persisted transcript:

| #   | session          | vector                                 | form                                                       |
| --- | ---------------- | -------------------------------------- | ---------------------------------------------------------- |
| 1   | Qwen builder     | `read_file` on `~/.qwen/settings.json` | whole-file read dumps the `env` block into the tool result |
| 2   | Claude gate lane | `${VAR:-UNSET}` in a shell diagnostic  | the `:-` default expansion prints the value                |
| 3   | Claude gate lane | `${VAR:+SET}${VAR:-UNSET}`             | same, concatenated after the sanctioned form               |

Incident 3 happened **in a brief whose first section forbade it in prose**, naming the correct form.
Prose failed twice out of three. This guard is the mechanical control that prose was not.

A full-disk scan that evening found **12 files on M5 containing the key in cleartext, 5 of them
mode 0644** inside a `~/.qwen` directory that is 0755 — plus two Claude subagent transcripts dated
2026-08-26/28, i.e. the exposure predates this incident by ~3 weeks. All 12 were chmod'd to 0600;
this guard exists so the count does not grow back.

## 2. Decision, not detection

Same contract as `data_plane_guard.py` / `host_boundary.py` / `output_hygiene_guard.py` in this
directory: JSON payload on stdin carrying `tool_name` (or `name`), `tool_input`, `cwd`.
**Exit 2 + one line on stderr = DENY.** Exit 0 = ALLOW. The guard never rewrites a command and never
runs it.

Fails **OPEN** on any exception, malformed/non-JSON stdin, a non-dict payload, an unrelated tool, or
a missing/corrupt registry — `sys.exit(2)` is the only thing that propagates through that wrapper. An
infra failure must never brick Bash. No subprocess calls anywhere (filesystem APIs only). Latency
budget: under 5 ms of guard work per call — pure regex over the command string plus path
normalisation of the tokens; **no filesystem walk, no file read**. Store paths are matched by
PATTERN (`fnmatch` against the registry's `secret_files`), not by expanding the registry's globs on
disk: the first cut did `glob.glob("~/.config/**/…")` on every Bash call, which cost ~100 ms on a
real `~/.config` and could only deny a store that existed at that instant (gate finding 2026-09-19).

Kill switch: `NUZ_SECRET_EXPANSION_GUARD_OFF=1` → always exit 0.

## 3. What this guard does NOT reuse, and why

`output_hygiene_guard.py` already contains a segmenter graded against 82 corpus cases, and reuse is
this repo's default. It is deliberately **not** reused here, because its blanking semantics are
inverted for this concern: `_strip_heredoc_bodies()` and `_strip_quotes()` _erase_ content before
judgement, which is correct when the question is "how many bytes will this print" and wrong when the
question is "does this text contain a secret expansion". A `bash <<EOF … echo $KEY … EOF` must be
denied, and quoting must not hide `"${KEY:-x}"` — the leaking forms are almost always _inside_
quotes, which is exactly what a quote-blanker removes.

The parser here is therefore small and self-contained, and its segmentation is deliberately
conservative: it splits into statements on `&&`, `||`, `;`, `&`, `|` and newlines **without**
unquoting, so a quoted expansion is still visible. That trades a little precision for never missing
the shape that actually leaked.

One idea from that segmenter **is** borrowed (`_mask_substitutions`): `$(…)` and backtick bodies are
blanked in the outer text and judged on their own, recursively (depth ≤ 3). Without it,
`echo "$(cat STORE)"` is an echo of a quoted string (under-match, E52) and
`echo "$(curl -H "Bearer $KEY" …)"` is an X1 hit (over-match, E56) — one blind spot, both directions.

## 4. Shapes

Nothing outside this table is a guilt shape. `NAME` below means any env var matched by the registry's
`secret_env_vars` or `secret_env_var_patterns`; `STORE` means any path matched by `secret_files`.

| ID  | shape                            | heads                                                                                                                                                           | DENY when                                                                                                                                                                                                                                                    | ALLOW carve-outs                                                                                                                                                                                                                          |
| --- | -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| X1  | secret expansion reaching stdout | `echo`, `printf`, `tee`, `xargs`                                                                                                                                | the stage contains `$NAME` or `${NAME…}` in a **value-emitting** form                                                                                                                                                                                        | the presence-only forms `${NAME:+…}` and `${NAME+…}` are ALLOW **unless** the same stage also carries a value form — `${V:+SET}${V:-UNSET}` (incident 3) must DENY                                                                        |
| X2  | environment dump                 | `printenv`, `env`, `export`, `set`, `declare`, `typeset`                                                                                                        | `printenv` in any form; bare `env`/`set`/`declare` with no following program; `export -p`; `declare -p` (with or without a name); `set -x` / `set -o xtrace` / a combined flag string carrying `x` (`set -euxo pipefail`) — tracing echoes EXPANDED commands | `env VAR=val cmd`, `env -i …`, `env -u NAME cmd`, `VAR=val cmd` — these set or strip, they do not print. `set -o pipefail`, `set -e`, `set -a`, `set +x` (tracing OFF), `declare -x`/`-a`/`-f`/`-r` — everyday flags, not dumps (E47-E49) |
| X3  | Keychain value print             | `security`                                                                                                                                                      | `find-generic-password` (or `find-internet-password`) with `-w` / `--password`                                                                                                                                                                               | the same command **without** `-w` prints metadata only → ALLOW                                                                                                                                                                            |
| X4  | secret store content dump        | `cat`, `bat`, `batcat`, `head`, `tail`, `less`, `more`, `strings`, `xxd`, `od`, `base64`, `jq`, `sed`, `awk`, `grep`, `rg`, `python3 -m json.tool`, `tac`, `nl` | any registered STORE appears as a non-flag target                                                                                                                                                                                                            | metadata verbs (`stat`, `ls`, `chmod`, `chown`, `test`, `[`, `wc`, `file`, `du`, `realpath`, `basename`, `dirname`) → ALLOW. For `grep`/`rg`: `-c`, `--count`, `-l`, `--files-with-matches`, `-q`, `--quiet` bound it → ALLOW             |
| X5  | Read tool on a secret store      | tools `Read`, `read_file`, `NotebookRead`                                                                                                                       | `tool_input.file_path` resolves to a registered STORE — matched by PATTERN against `secret_files`, so a glob store is denied whether or not the file exists right now (E55)                                                                                  | a `limit`/`offset` slice does NOT exempt it — the secret is one line, and any slice can contain it                                                                                                                                        |

Three consequences of the shapes, stated so they are not mistaken for accidents. **A store dump inside
a command substitution or captured into a variable** (`x=$(cat STORE)`) is denied like E34 — the dump
verb on the store is the shape, not where its bytes go; `source STORE` is the sanctioned way to load
it and stays ALLOW. **Single-quoted literals** (`echo '${NAME:-x}'`) are denied although the shell
would not expand them: the parser preserves quotes rather than evaluating them, and a session that
wants to print the literal form can write it without the `$`. **Heredocs**: a quoted-delimiter heredoc
(`<<'EOF'`) fed to a non-shell consumer (`python3 -`, `cat > file`) is literal data and is not judged
(E57) — the outer shell expands nothing in it and the consumer does not run it as shell; a heredoc to
`bash`/`sh`/`zsh`/`ssh` is code the child runs and is judged quoted or not (E33, E58, E59); an unquoted
heredoc to anything is expanded by the outer shell and is judged too.

Explicitly **out of scope**, stated so nobody assumes coverage:

- **Interpreter one-liners.** `python3 -c 'print(os.environ["NAME"])'` is not caught. Detecting it
  means parsing the embedded program, and a name-plus-`print` heuristic would deny the _sanctioned_
  fingerprint pattern (`print(hashlib.sha256(KEY.encode()).hexdigest()[:12])`) used throughout this
  repo's own diagnostics. A guard that denies the correct workaround is worse than no guard.
- **`~/.qwen/settings.json` is NOT a registered STORE.** It is a config file that legitimate work
  must read — the 2026-09-18 tuning task read it to do its job — and PR #6765 removed the credential
  from it precisely so it would stop being a secret store. Registering it would deny config work on
  migrated hosts to protect a file that no longer holds a secret. **Known gap on unmigrated hosts**
  (Pro still keeps the key there); the cure is migrating Pro, not blocking config reads. Its secret
  is still covered by X1/X2 the moment anyone tries to print it.
- **Copying, moving or chmod'ing a STORE** is not a leak (no content reaches a transcript) and is
  ALLOW; `data_plane_guard` and ordinary file hygiene own those surfaces.
- **Vendor CLIs that print a credential on purpose** — `gh auth token`, `gcloud auth
print-access-token`, `flyctl auth token` — are not shapes yet (gate finding 2026-09-19, ALLOW today).
  Each needs its own innocence row (`gh auth status` must stay ALLOW) and belongs in the registry as
  a `value_print_commands` list rather than in code. Follow-up, not this PR.

## 5. Case corpus — the gate grades against THIS table, by ID

`NAME` = `BAILIAN_TOKEN_PLAN_API_KEY` (registered). `STORE` = `~/.nuzantara-secrets.env` (registered).

| ID  | command / tool input                                                      | verdict | reason                                                                                                                      |
| --- | ------------------------------------------------------------------------- | ------- | --------------------------------------------------------------------------------------------------------------------------- |
| E01 | `echo "${NAME:-UNSET}"`                                                   | DENY    | X1 — incident 2 verbatim                                                                                                    |
| E02 | `printf "[%s]\n" "${NAME:+SET}${NAME:-UNSET}"`                            | DENY    | X1 — incident 3 verbatim; the `:+` half does not launder the `:-` half                                                      |
| E03 | `echo $NAME`                                                              | DENY    | X1                                                                                                                          |
| E04 | `echo "${NAME}"`                                                          | DENY    | X1 — braces with no operator still emit the value                                                                           |
| E05 | `echo "${NAME:?not set}"`                                                 | DENY    | X1                                                                                                                          |
| E06 | `echo "${NAME:+SET}"`                                                     | ALLOW   | X1 carve-out — the sanctioned presence check                                                                                |
| E07 | `printf "x=%s\n" "${NAME:+SET}"`                                          | ALLOW   | X1 carve-out                                                                                                                |
| E08 | `test -n "$NAME" && echo present`                                         | ALLOW   | expansion is not in a print stage                                                                                           |
| E09 | `curl -H "Authorization: Bearer $NAME" https://api/`                      | ALLOW   | **the correct way to use a key**; head is not a print verb                                                                  |
| E10 | `python3 tool.py --key "$NAME"`                                           | ALLOW   | passing, not printing                                                                                                       |
| E11 | `grep -rn "NAME" scripts/`                                                | ALLOW   | bare NAME, no `$` — this is how the consumers were found                                                                    |
| E12 | `export NAME=something`                                                   | ALLOW   | assignment, not a dump                                                                                                      |
| E13 | `printenv NAME`                                                           | DENY    | X2                                                                                                                          |
| E14 | `printenv`                                                                | DENY    | X2 — dumps every secret at once                                                                                             |
| E15 | `env`                                                                     | DENY    | X2                                                                                                                          |
| E16 | `env \| grep -i token`                                                    | DENY    | X2 on the first stage                                                                                                       |
| E17 | `env -i HOME=$HOME cmd`                                                   | ALLOW   | X2 carve-out — sets a clean env, prints nothing                                                                             |
| E18 | `env -u NAME python3 x.py`                                                | ALLOW   | X2 carve-out — strips, and is the sanctioned way to test a fallback                                                         |
| E19 | `NAME=x python3 x.py`                                                     | ALLOW   | stage-local assignment                                                                                                      |
| E20 | `export -p`                                                               | DENY    | X2                                                                                                                          |
| E21 | `security find-generic-password -s svc -w`                                | DENY    | X3                                                                                                                          |
| E22 | `security find-generic-password -s svc`                                   | ALLOW   | X3 carve-out — metadata only                                                                                                |
| E23 | `security find-generic-password -s svc -w \| shasum -a 256`               | DENY    | X3; piping to a hash does not un-leak the first stage's stdout                                                              |
| E24 | `cat STORE`                                                               | DENY    | X4                                                                                                                          |
| E25 | `head -3 STORE`                                                           | DENY    | X4                                                                                                                          |
| E26 | `jq . STORE`                                                              | DENY    | X4                                                                                                                          |
| E27 | `stat -f %Lp STORE`                                                       | ALLOW   | X4 carve-out — metadata                                                                                                     |
| E28 | `chmod 600 STORE`                                                         | ALLOW   | X4 carve-out — this is the cure, it must not be blocked                                                                     |
| E29 | `wc -c STORE`                                                             | ALLOW   | X4 carve-out                                                                                                                |
| E30 | `grep -c NAME STORE`                                                      | ALLOW   | X4 carve-out — count only                                                                                                   |
| E31 | `grep NAME STORE`                                                         | DENY    | X4 — prints the matching line, which IS the value                                                                           |
| E32 | `ls -la STORE`                                                            | ALLOW   | X4 carve-out                                                                                                                |
| E33 | `bash <<EOF\necho $NAME\nEOF`                                             | DENY    | X1 inside a heredoc body — the reason §3 does not blank heredocs                                                            |
| E34 | `cat STORE > /tmp/x`                                                      | DENY    | X4; redirecting the output does not un-read the secret                                                                      |
| E35 | `echo hello`                                                              | ALLOW   | no secret anywhere                                                                                                          |
| E36 | Read tool, `file_path=STORE`                                              | DENY    | X5                                                                                                                          |
| E37 | Read tool, `file_path=STORE`, `limit=5`                                   | DENY    | X5 — a slice can contain the one secret line                                                                                |
| E38 | Read tool, `file_path=/etc/hosts`                                         | ALLOW   | X5, unregistered path                                                                                                       |
| E39 | Read tool, `file_path=~/.qwen/settings.json`                              | ALLOW   | §4 out-of-scope, deliberate                                                                                                 |
| E40 | `echo "${ANTHROPIC_API_KEY:-x}"`                                          | DENY    | X1 via registry pattern — not just the one TP1 var                                                                          |
| E41 | `echo "$PATH"`                                                            | ALLOW   | not a registered secret                                                                                                     |
| E42 | `# never echo $NAME` (comment only)                                       | ALLOW   | comments are stripped before judgement                                                                                      |
| E43 | `echo "use \${NAME:-x} carefully"`                                        | ALLOW   | escaped `\$` is literal text, not an expansion                                                                              |
| E44 | malformed stdin / non-dict payload / unknown tool                         | ALLOW   | fail-open, §2                                                                                                               |
| E45 | corrupt or missing registry                                               | ALLOW   | fail-open with a WARN, never brick Bash                                                                                     |
| E46 | `NUZ_SECRET_EXPANSION_GUARD_OFF=1` + E01                                  | ALLOW   | kill switch                                                                                                                 |
| E47 | `set -o pipefail; ls \| head`                                             | ALLOW   | X2 carve-out — `-o` is tracing only when followed by `xtrace`; found DENIED at the gate                                     |
| E48 | `set +x; ls`                                                              | ALLOW   | X2 carve-out — `+x` turns tracing OFF; found DENIED at the gate                                                             |
| E49 | `declare -x FOO=1; ls`                                                    | ALLOW   | X2 carve-out — `declare -x` exports, it neither traces nor prints; found DENIED at the gate                                 |
| E50 | `set -euxo pipefail`                                                      | DENY    | X2 — the combined flag string carries `x`                                                                                   |
| E51 | `declare -p`                                                              | DENY    | X2 — prints every variable with its value (`declare -p NAME` prints one); found ALLOWED at the gate                         |
| E52 | `echo "$(cat STORE)"`                                                     | DENY    | X4 inside a command substitution — the body is judged on its own; found ALLOWED at the gate                                 |
| E53 | ``echo `printenv NAME` ``                                                 | DENY    | X2 inside backticks                                                                                                         |
| E54 | `echo "$(date)"`                                                          | ALLOW   | a substitution with nothing guilty in it                                                                                    |
| E55 | Read tool, `file_path=~/.claude-zero-team/.credentials.json`, file ABSENT | DENY    | X5 — a glob store is matched by pattern, never by a disk walk; absence today does not un-register it                        |
| E56 | `echo "$(curl -H "Authorization: Bearer $NAME" https://api/)"`            | ALLOW   | the outer `echo` prints the response, not the key; the body is E09                                                          |
| E57 | `python3 - <<'PY'\nprint("cat STORE")\nPY`                                | ALLOW   | a quoted heredoc to a non-shell is literal data — the repo's own editing idiom; found DENIED the moment the guard went live |
| E58 | `bash <<'EOF'\ncat STORE\nEOF`                                            | DENY    | X4 — quoted or not, a heredoc to `bash` is code the child runs                                                              |
| E59 | `ssh pro <<'EOF'\ncat STORE\nEOF`                                         | DENY    | X4 — `ssh` runs a remote shell and its output comes back to the transcript                                                  |

## 6. Wiring

Registered as PreToolUse on `Bash|Monitor|Read` in `.claude/settings.json` (repo-tracked, invoked via
`${CLAUDE_PROJECT_DIR}/infra/claude-hooks/…`) alongside `data_plane_guard.py`, and on the equivalent
event in `~/.qwen/settings.json` for the Qwen harness — **both harnesses leaked**, so both are wired.

Registered in `infra/guard-conformance/registry.json` (superscar #3 census, C1) with
`infra/claude-hooks/test_secret_expansion_guard.py` as its dedicated guilt+innocence proof, and with
a short guilt+innocence block in the shared vaccine `infra/claude-hooks/test_hook_innocence.py`, which
`.github/workflows/hook-innocence-gate.yml` (a required check) executes on every hooks change — the
dedicated corpus is _reachable_ by that workflow's path filter, the vaccine block is what actually
_runs_ (W81: reachable is not armed). The gate found the first cut unregistered; CI would have been red.

Invoked from the repo path rather than installed to `~/.claude/hooks/` on purpose: that keeps it
version-controlled and reviewable, and avoids adding a 191st pair to `infra/home-fork/declared-pairs.json`
whose whole failure mode (superscar #1) is a `$HOME` copy silently diverging from its repo twin.

## 7. Adding a secret

The registry is the extension point; this file and the guard code should not need to change. Add a
name to `secret_env_vars`, a pattern to `secret_env_var_patterns`, or a path to `secret_files`, and
add the corresponding C-row here.
