#!/usr/bin/env python3
"""secret_expansion_guard.py — PreToolUse(Bash|Monitor|Read) hook.

Denies the shell and Read-tool forms that put a CREDENTIAL VALUE into a tool
result, which is the same thing as putting it into the transcript and therefore
into the model provider's conversation log.

WHY A GUARD AND NOT A RULE. On 2026-09-18 three agent sessions on Air-M5 leaked
the live Token-Plan key: one by `read_file`-ing ~/.qwen/settings.json, two by
using `${VAR:-UNSET}` instead of `${VAR:+SET}` in a diagnostic. The third leak
happened in a handoff brief whose FIRST SECTION forbade it in prose and named the
correct form. Prose failed twice out of three. A full-disk scan that evening found
12 files on this machine holding the key in cleartext, 5 of them mode 0644, plus
two Claude subagent transcripts from ~3 weeks earlier. This is the mechanical
control the prose was not.

GRADED, NOT IMPROVISED. The shapes and the verdicts live in
docs/specs/2026-09-18-secret-expansion-guard-shapes-spec.md (§4 shapes, §5 corpus
E01-E59) and infra/claude-hooks/test_secret_expansion_guard.py asserts the corpus
row by row. Where this file and the spec disagree, THE SPEC WINS. Precedent:
output_hygiene_guard v1 was suspended at three gate rounds, each finding a new
over-match on an everyday command (cicatrix superscar #3). The over-match trap
here is one character wide — `${V:+SET}` is sanctioned and `${V:-UNSET}` leaks —
and the shapes that would be easiest to write are the ones that deny correct work:
`curl -H "Authorization: Bearer $KEY"` (E09) is the RIGHT way to use a key.

CONTRACT (identical stdin/exit-code shape to data_plane_guard.py /
host_boundary.py / output_hygiene_guard.py in this same dir): JSON payload on
stdin with `tool_name` (or `name`), `tool_input`, `cwd`. Exit 2 + one line on
stderr = DENY. Exit 0 = ALLOW. Never rewrites a command, never runs one.

Fails OPEN on any exception, malformed stdin, a non-dict payload, an unrelated
tool, or a missing/corrupt registry — sys.exit(2) is the only thing that
propagates through the wrapper. An infra failure must never brick Bash. No
subprocess calls anywhere. Kill switch: NUZ_SECRET_EXPANSION_GUARD_OFF=1.

NOT REUSED, DELIBERATELY: output_hygiene_guard's segmenter. Its
_strip_heredoc_bodies()/_strip_quotes() BLANK content before judgement, which is
right for "how many bytes will this print" and wrong for "does this text contain
a secret expansion" — a `bash <<EOF\\necho $KEY\\nEOF` must deny (E33) and the
leaking forms live INSIDE quotes, exactly what a quote-blanker erases. So the
parser here is small, quote-AWARE but quote-PRESERVING, and trades precision for
never missing the shape that actually leaked. One idea IS borrowed from that
segmenter: `$(...)` and backtick bodies are masked in the outer text and judged
on their own (E52-E56), because `echo "$(cat STORE)"` must deny and
`echo "$(curl -H "Bearer $KEY" ...)"` must not.

GATE 2026-09-19 (Opus 5, SHIP-WITH-FIXES): store matching is by PATTERN, never by
a disk walk — the first cut glob.glob'd `~/.config/**` on every Bash call (~100 ms
on a real ~/.config, spec budget 5 ms) and could only deny a store that existed
at that instant. `set -o pipefail`, `set +x` and `declare -x` were over-matched
(E47-E49); `declare -p` and command substitutions were under-matched (E51-E53);
quoted heredocs to a non-shell consumer are literal data, not shell (E57).
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parent / "secret-expansion-registry.json"
KILL_SWITCH = "NUZ_SECRET_EXPANSION_GUARD_OFF"

# Shape semantics, owned by spec §4 — not registry data.
PRINT_VERBS = {"echo", "printf", "tee", "xargs"}
ENV_DUMP_VERBS = {"printenv", "env", "export", "set", "declare", "typeset"}
KEYCHAIN_READ_SUBCOMMANDS = {"find-generic-password", "find-internet-password"}
DUMP_VERBS = {
    "cat", "bat", "batcat", "head", "tail", "less", "more", "strings", "xxd",
    "od", "base64", "jq", "sed", "awk", "gawk", "tac", "nl", "grep", "rg",
    "ag", "ack", "python", "python3",
}
# A dump verb reading a store is still fine when it can only report a COUNT or a
# FILENAME, never a line of content.
GREP_BOUNDING_FLAGS = {
    "-c", "--count", "-l", "--files-with-matches", "-q", "--quiet",
    "--count-matches", "-L", "--files-without-match",
}
METADATA_VERBS = {
    "stat", "ls", "chmod", "chown", "test", "[", "wc", "file", "du", "realpath",
    "basename", "dirname", "md5", "shasum", "cksum", "touch", "mkdir", "mv", "cp",
}
PEELABLE = {"env", "sudo", "time", "nice", "command", "exec", "nohup", "stdbuf"}
# A heredoc fed to one of these is CODE the consumer will run (locally or, for
# ssh, remotely) and its output comes back to the transcript — judge the body.
SHELL_HEADS = {"bash", "sh", "zsh", "dash", "ksh", "ssh"}
# The same shells when they take their CODE as a `-c` STRING ARGUMENT. `ssh` is
# deliberately absent: its `-c` is the CIPHER flag, and a remote command needs the
# read/write distinction of W94 before it can be judged (see the spec's E64 note).
LOCAL_SHELL_HEADS = SHELL_HEADS - {"ssh"}
_HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")
_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_REDIRECT_RE = re.compile(r"^\d*(?:>>|<<<|<<-?|&>>|&>|>&\d*|<|>)")
# A redirect glued to its target (`cat store>/tmp/x`, `2>&1`) — the operand before
# the operator is still a real argument and must not be swallowed with it.
_GLUED_REDIRECT_RE = re.compile(r"(?:&>>|&>|>>|>&\d*|<<<|<<-?|<|>)")
# `${NAME…}` — the operator after the name decides value vs presence.
_BRACE_EXP_RE = re.compile(r"(?<!\\)\$\{([A-Za-z_][A-Za-z0-9_]*)([^{}]*)\}")
_BARE_EXP_RE = re.compile(r"(?<!\\)\$([A-Za-z_][A-Za-z0-9_]*)")
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _warn(msg: str) -> None:
    # stderr on an ALLOW path is advisory only; exit code stays 0.
    print(f"[secret-expansion-guard] WARN {msg}", file=sys.stderr)


def _load_registry() -> dict | None:
    """Return the registry, or None (fail-open) if it is missing or malformed."""
    try:
        data = json.loads(REGISTRY_PATH.read_text())
    except Exception as exc:
        _warn(f"registry unreadable ({type(exc).__name__}); passing through")
        return None
    if not isinstance(data, dict):
        _warn("registry is not a JSON object; passing through")
        return None
    return data


def _secret_names(reg: dict) -> tuple[set[str], list[re.Pattern[str]]]:
    names: set[str] = set()
    for n in reg.get("secret_env_vars") or []:
        if isinstance(n, str) and _NAME_RE.match(n):
            names.add(n)
    pats: list[re.Pattern[str]] = []
    for p in reg.get("secret_env_var_patterns") or []:
        if not isinstance(p, str) or not p:
            continue
        try:
            pats.append(re.compile(p))
        except re.error:
            _warn(f"bad pattern {p!r} in registry; skipping it")
    return names, pats


def _is_secret(name: str, names: set[str], pats: list[re.Pattern[str]]) -> bool:
    return name in names or any(p.search(name) for p in pats)


def _store_patterns(reg: dict) -> list[str]:
    """The registry's `secret_files`, ~-expanded and normalized — NOT expanded on disk.

    Matching happens per candidate token in _matches_store with fnmatch, so the
    guard never walks the filesystem. Both the literal and the realpath-resolved
    form of each pattern are kept, so a symlinked $HOME matches either way. A
    referenced store is denied whether or not the file exists right now.
    """
    out: list[str] = []
    for pat in reg.get("secret_files") or []:
        if not isinstance(pat, str) or not pat:
            continue
        expanded = os.path.normpath(os.path.expanduser(pat))
        out.append(expanded)
        try:
            resolved = os.path.normpath(os.path.realpath(expanded))
        except Exception:
            resolved = expanded
        if resolved != expanded:
            out.append(resolved)
    return out


def _path_matches(candidate: str, pattern: str) -> bool:
    if not any(ch in pattern for ch in "*?["):
        return candidate == pattern
    if fnmatch.fnmatchcase(candidate, pattern):
        return True
    # `a/**/b` also names `a/b` (zero intermediate dirs); fnmatch's `*` spans
    # separators but the literal `/` on each side of `**` still has to be there.
    return "/**/" in pattern and fnmatch.fnmatchcase(candidate, pattern.replace("/**/", "/"))


# --------------------------------------------------------------- tokenizing


def _split_quoted(text: str, seps: list[str]) -> list[str]:
    """Split on the first matching separator found OUTSIDE quotes/escapes.

    Quote-aware but quote-PRESERVING: the returned fragments keep their quotes so
    a later expansion scan still sees `"${V:-x}"`. Separators are tried longest
    first so `&&` wins over `&` and `||` over `|`.
    """
    ordered = sorted(seps, key=len, reverse=True)
    out: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if quote:
            buf.append(c)
            if c == "\\" and quote != "'" and i + 1 < n:
                buf.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "\"'":
            quote = c
            buf.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf.append(c)
            buf.append(text[i + 1])
            i += 2
            continue
        hit = next((s for s in ordered if text.startswith(s, i)), None)
        if hit:
            out.append("".join(buf))
            buf = []
            i += len(hit)
            continue
        buf.append(c)
        i += 1
    out.append("".join(buf))
    return out


def _blank_literal_heredocs(text: str) -> str:
    """Blank the body of a QUOTED-delimiter heredoc whose consumer is not a shell.

    `python3 - <<'PY' … PY` and `cat > f <<'EOF' … EOF` carry literal DATA: the
    shell expands nothing in a quoted heredoc and the consumer is not going to
    run it as shell. Judging that body as shell over-matched the repo's own
    editing idiom the moment this guard went live (E57: a Python heredoc whose
    string literals mention a store). A heredoc to bash/sh/zsh/ssh is code the
    child runs, quoted or not, and stays judged (E33, E58, E59); an UNQUOTED
    heredoc to anything is expanded by the outer shell and stays judged too.
    """
    out = list(text)
    for m in _HEREDOC_RE.finditer(text):
        if not m.group(1):
            continue  # unquoted: expansions happen — keep judging
        line_start = text.rfind("\n", 0, m.start()) + 1
        stage = _split_quoted(text[line_start:m.start()], ["&&", "||", ";", "|"])[-1]
        if _head_of(_peel(_tokenize(stage))) in SHELL_HEADS:
            continue
        nl = text.find("\n", m.end())
        if nl < 0:
            continue
        end = re.compile(r"^[ \t]*" + re.escape(m.group(2)) + r"[ \t]*$", re.MULTILINE).search(
            text, nl + 1
        )
        for i in range(nl + 1, end.start() if end else len(text)):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out)


def _strip_comments(text: str) -> str:
    """Drop unquoted `#`-to-end-of-line. E42: a comment naming a secret is prose."""
    out: list[str] = []
    quote: str | None = None
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if quote:
            out.append(c)
            if c == "\\" and quote != "'" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "\"'":
            quote = c
            out.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            out.append(c)
            out.append(text[i + 1])
            i += 2
            continue
        if c == "#" and (i == 0 or text[i - 1] in " \t;|&("):
            nl = text.find("\n", i)
            i = n if nl < 0 else nl
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _tokenize(stage: str) -> list[str]:
    """Shell-ish word split, quote-preserving, redirects removed.

    Three redirect forms, handled separately because getting this wrong is an
    under-match (a secret store hidden behind `>/tmp/x`) rather than a harmless
    over-match: a bare operator (`> file`) consumes the NEXT token; a
    self-contained one (`2>&1`) consumes nothing; a glued one (`store>/tmp/x`)
    keeps the operand before the operator, which is the real argument.
    """
    raw = [t for t in _split_quoted(stage, [" ", "\t"]) if t.strip()]
    out: list[str] = []
    skip_next = False
    for tok in raw:
        if skip_next:
            skip_next = False
            continue
        m = _REDIRECT_RE.match(tok)
        if m:
            if len(m.group(0)) == len(tok) and tok.lstrip("0123456789") in (
                ">", ">>", "<", "<<<", "<<-",
            ):
                skip_next = True
            continue
        g = _GLUED_REDIRECT_RE.search(tok)
        if g and g.start() > 0:
            head = tok[: g.start()].rstrip("0123456789&")
            if head:
                out.append(head)
            continue
        out.append(tok)
    return out


def _unquote(tok: str) -> str:
    t = tok.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        return t[1:-1]
    return t


def _peel(toks: list[str], peel_env: bool = True) -> list[str]:
    """Strip leading VAR=, env/sudo/time/timeout/nohup and their flags.

    `peel_env=False` keeps `env` as the head. It is BOTH a peelable prefix
    (`env -i cmd`) and an X2 target (bare `env` dumps every secret), so the two
    judgements need two different views of the same stage: X1/X3/X4 want the
    program that will actually run, X2 wants to know whether `env` IS the program.
    """
    toks = list(toks)
    peelable = PEELABLE if peel_env else (PEELABLE - {"env"})
    guard = 0
    while toks and guard < 24:
        guard += 1
        head = toks[0]
        if _ASSIGN_RE.match(head):
            toks = toks[1:]
            continue
        if head in ("timeout", "gtimeout") and len(toks) > 1:
            toks = toks[1:]
            while toks and toks[0].startswith("-") and toks[0] not in ("-k",):
                toks = toks[1:]
            if toks and toks[0] in ("-k",):
                toks = toks[2:]
            if toks:
                toks = toks[1:]
            continue
        if head in peelable:
            toks = toks[1:]
            while toks and toks[0].startswith("-"):
                if toks[0] in ("-u", "--unset", "-C") and len(toks) > 1:
                    toks = toks[2:]
                else:
                    toks = toks[1:]
            continue
        break
    return toks


def _head_of(toks: list[str]) -> str:
    if not toks:
        return ""
    h = _unquote(toks[0])
    return os.path.basename(h) if "/" in h else h


# --------------------------------------------------------------- shapes


def _expansions(text: str) -> tuple[set[str], set[str]]:
    """(value-emitting names, presence-only names) expanded in `text`."""
    value: set[str] = set()
    presence: set[str] = set()
    for m in _BRACE_EXP_RE.finditer(text):
        name, rest = m.group(1), m.group(2)
        if rest.startswith(":+") or rest.startswith("+"):
            presence.add(name)
        else:
            value.add(name)
    for m in _BARE_EXP_RE.finditer(text):
        if text[m.end(): m.end() + 1] == "{":
            continue
        if m.start() > 0 and text[m.start() - 1] == "$":
            continue  # $$ pid, not a name
        value.add(m.group(1))
    return value, presence


def _check_x1(stage: str, head: str, secrets) -> str | None:
    """X1 — a print verb carrying a value-emitting secret expansion."""
    if head not in PRINT_VERBS:
        return None
    names, pats = secrets
    value, _presence = _expansions(stage)
    hit = sorted(n for n in value if _is_secret(n, names, pats))
    if not hit:
        return None
    # The presence-only form is the sanctioned check; it does not launder a value
    # form sitting in the SAME stage (E02, incident 3 verbatim).
    # Built by concatenation, not brace escaping: the sanctioned form is itself
    # `${NAME:+SET}`, and nesting that inside an f-string is how this line first
    # shipped with a SyntaxError — which, because the fail-open wrapper exits 0,
    # would have looked like a perfectly innocent guard.
    sanctioned = "${" + hit[0] + ":+SET}"
    return (
        f"X1 secret value expansion: {hit[0]} is expanded in a print stage. "
        f"Use {sanctioned} for presence — never :-, :=, :? or a bare $var, "
        f"which put the value into the transcript and the provider's log."
    )


def _set_enables_xtrace(rest: list[str]) -> bool:
    """`set -x`, `set -euxo pipefail`, `set -o xtrace` turn tracing ON. `set +x`,
    `set -e`, `set -o pipefail`, `set -a` do not — everyday commands (E47/E48),
    and the first cut denied them (superscar #3, found at the gate)."""
    for i, t in enumerate(rest):
        if re.match(r"^-[A-Za-z]*x[A-Za-z]*$", t):
            return True
        if t == "-o" and i + 1 < len(rest) and rest[i + 1] == "xtrace":
            return True
    return False


def _check_x2(toks: list[str], head: str) -> str | None:
    """X2 — an environment dump."""
    if head not in ENV_DUMP_VERBS:
        return None
    rest = toks[1:]
    if head == "printenv":
        return "X2 environment dump: printenv prints secret values. Report presence only."
    if head in ("set", "declare", "typeset"):
        if not rest:
            return f"X2 environment dump: bare `{head}` prints every variable and its value."
        if head == "set":
            if _set_enables_xtrace(rest):
                return (
                    "X2 command echo: `set -x` / `set -o xtrace` traces EXPANDED commands, "
                    "so any secret in them reaches the transcript."
                )
            return None
        # declare/typeset: only -p PRINTS (name and value). -x exports, -a/-f/-r declare.
        if any(re.match(r"^-[A-Za-z]*p[A-Za-z]*$", t) for t in rest):
            return f"X2 environment dump: `{head} -p` prints variables with their values."
        return None
    if head == "export":
        if not rest or "-p" in rest or "--print" in rest:
            return "X2 environment dump: `export -p` prints every variable and its value."
        return None
    # head == "env": a dump only when nothing follows to run.
    if not rest:
        return "X2 environment dump: bare `env` prints every variable and its value."
    i = 0
    while i < len(rest):
        t = rest[i]
        if t in ("-u", "--unset") and i + 1 < len(rest):
            i += 2
            continue
        if t.startswith("-"):
            i += 1
            continue
        if "=" in t and _ASSIGN_RE.match(t):
            i += 1
            continue
        # A real program follows: env is setting an environment, not printing one.
        return None
    return "X2 environment dump: `env` with only flags/assignments prints the environment."


def _check_x3(toks: list[str], head: str) -> str | None:
    """X3 — Keychain value print."""
    if head != "security" or len(toks) < 2:
        return None
    if _unquote(toks[1]) not in KEYCHAIN_READ_SUBCOMMANDS:
        return None
    if any(_unquote(t) in ("-w", "--password") for t in toks[2:]):
        return (
            "X3 Keychain value print: `security find-*-password -w` writes the secret to "
            "stdout. Drop -w for metadata, or pipe through a hash inside the SAME command "
            "only if you never needed the value."
        )
    return None


def _json_tool_dump(toks: list[str]) -> bool:
    """`python3 -m json.tool <store>` is a content dump; `python3 script.py` is not."""
    return len(toks) >= 3 and toks[1] == "-m" and _unquote(toks[2]) in ("json.tool", "json")


def _check_x4(toks: list[str], head: str, cwd: str, stores: list[str]) -> str | None:
    """X4 — a content-dumping verb pointed at a registered credential store."""
    is_json_tool = head in ("python", "python3") and _json_tool_dump(toks)
    if head not in DUMP_VERBS or (head in ("python", "python3") and not is_json_tool):
        return None
    if head in METADATA_VERBS:
        return None
    bounded = head in ("grep", "rg", "ag", "ack") and any(
        _unquote(t) in GREP_BOUNDING_FLAGS for t in toks[1:]
    )
    if bounded:
        return None
    for tok in toks[1:]:
        t = _unquote(tok)
        if not t or t.startswith("-"):
            continue
        if _matches_store(t, cwd, stores):
            return (
                f"X4 credential store dump: `{head}` on {t} puts its contents into the "
                f"transcript. Use stat/ls/wc -c/chmod for metadata, grep -c for a count, "
                f"or a script that extracts what you need without printing it."
            )
    return None


def _matches_store(token: str, cwd: str, stores: list[str]) -> bool:
    if not stores:
        return False
    candidates = {os.path.normpath(token)}
    try:
        exp = os.path.expanduser(token)
        if not os.path.isabs(exp):
            exp = os.path.join(cwd or os.getcwd(), exp)
        candidates.add(os.path.normpath(exp))
        candidates.add(os.path.normpath(os.path.realpath(exp)))
    except Exception:
        pass
    return any(_path_matches(c, p) for c in candidates for p in stores)


def _check_x5(tool: str, tool_input: dict, stores: list[str]) -> str | None:
    """X5 — the Read tool on a registered credential store."""
    if tool not in ("Read", "read_file", "NotebookRead", "notebook_read"):
        return None
    raw = tool_input.get("file_path") or tool_input.get("path") or ""
    if not isinstance(raw, str) or not raw:
        return None
    cwd = tool_input.get("cwd") or os.getcwd()
    if _matches_store(raw, cwd, stores):
        return (
            f"X5 credential store read: {raw} is a registered secret store, and a Read "
            f"puts its whole content into the transcript even when nothing is printed. "
            f"A limit/offset slice does not help — the secret is one line. Extract what "
            f"you need with a script that never prints the value (sha256[:12] to compare)."
        )
    return None


# --------------------------------------------------------------- dispatch

MAX_SUBSTITUTION_DEPTH = 3


def _mask_substitutions(text: str) -> tuple[str, list[str]]:
    """Blank `$(...)` and backtick spans in `text` and return their bodies.

    The OUTER command is judged on the blanked text, each body on its own
    (recursively, bounded). Without this, `echo "$(cat STORE)"` is an echo of a
    quoted string (under-match, E52) and `echo "$(curl -H "Bearer $KEY" ...)"`
    is an X1 hit (over-match, E56) — one blind spot, both directions.
    """
    chars = list(text)
    subs: list[str] = []
    i, n = 0, len(text)
    while i < n:
        escaped = i > 0 and text[i - 1] == "\\"
        if text[i] == "$" and i + 1 < n and text[i + 1] == "(" and not escaped:
            depth, j = 1, i + 2
            while j < n and depth > 0:
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                j += 1
            inner_end = j - 1 if depth == 0 else j
            subs.append(text[i + 2:inner_end])
            for k in range(i, j):
                if chars[k] != "\n":
                    chars[k] = " "
            i = j
            continue
        if text[i] == "`" and not escaped:
            j = text.find("`", i + 1)
            if j == -1:
                i += 1
                continue
            subs.append(text[i + 1:j])
            for k in range(i, j + 1):
                if chars[k] != "\n":
                    chars[k] = " "
            i = j + 1
            continue
        i += 1
    return "".join(chars), subs


def _shell_c_payloads(toks: list[str], head: str) -> list[str]:
    """Code a local shell runs from a STRING ARGUMENT rather than a heredoc body.

    `bash -c 'cat STORE'` is the entity of E58 — code the child runs, whose output
    lands in the transcript — one spelling apart from the heredoc the gate had
    already fixed, and the MORE idiomatic of the two. Judging only the heredoc left
    it open (found by independent probe at the gate, 2026-09-19: superscar #3 in the
    UNDER-match direction). `eval` is the same entity in the CURRENT shell.
    """
    if head == "eval":
        return [" ".join(_unquote(t) for t in toks[1:])] if len(toks) > 1 else []
    if head not in LOCAL_SHELL_HEADS:
        return []
    for i in range(1, len(toks)):
        t = _unquote(toks[i])
        if (t in ("-c", "--command") or re.match(r"^-[A-Za-z]*c[A-Za-z]*$", t)) and i + 1 < len(toks):
            return [_unquote(toks[i + 1])]
    return []


def _judge_command(command: str, cwd: str, reg: dict) -> str | None:
    text = _strip_comments(_blank_literal_heredocs(command))
    return _judge_text(text, cwd, _secret_names(reg), _store_patterns(reg), 0)


def _judge_text(text: str, cwd: str, secrets, stores: list[str], depth: int) -> str | None:
    outer, subs = _mask_substitutions(text)
    for statement in _split_quoted(outer, ["&&", "||", ";", "&", "\n"]):
        if not statement.strip():
            continue
        for stage in _split_quoted(statement, ["|"]):
            if not stage.strip():
                continue
            toks = _tokenize(stage)
            if not toks:
                continue
            peeled = _peel(toks)
            keep_env = _peel(toks, peel_env=False)
            head = _head_of(peeled)
            head_ke = _head_of(keep_env)
            candidates: list[str | None] = []
            if head:
                candidates += [
                    _check_x1(stage, head, secrets),
                    _check_x3(peeled, head),
                    _check_x4(peeled, head, cwd, stores),
                ]
            if head_ke:
                candidates.append(_check_x2(keep_env, head_ke))
            for reason in candidates:
                if reason:
                    return reason
            if head:
                subs.extend(_shell_c_payloads(peeled, head))
    if depth < MAX_SUBSTITUTION_DEPTH:
        for body in subs:
            reason = _judge_text(body, cwd, secrets, stores, depth + 1)
            if reason:
                return reason
    return None


def main() -> int:
    if os.environ.get(KILL_SWITCH) == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    reg = _load_registry()
    if reg is None:
        return 0

    tool = payload.get("tool_name") or payload.get("name") or ""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    cwd = payload.get("cwd") or os.getcwd()

    reason: str | None = None
    if tool in ("Bash", "Monitor", "run_shell_command", "Shell", "shell"):
        command = tool_input.get("command") or ""
        if isinstance(command, str) and command.strip():
            reason = _judge_command(command, cwd, reg)
    else:
        reason = _check_x5(tool, {**tool_input, "cwd": cwd}, _store_patterns(reg))

    if reason:
        print(f"[secret-expansion-guard] DENY {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # fail OPEN: never brick Bash over an infra error
        print(
            f"[secret-expansion-guard] WARN unexpected {type(exc).__name__}; allowing",
            file=sys.stderr,
        )
        sys.exit(0)
