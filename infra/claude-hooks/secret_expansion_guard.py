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
E01-E46) and infra/claude-hooks/test_secret_expansion_guard.py asserts the corpus
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
never missing the shape that actually leaked.
"""
from __future__ import annotations

import glob
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


def _store_paths(reg: dict) -> set[str]:
    """Expand the registry's globs ONCE per invocation into normalized paths.

    Non-glob entries are kept even when the file does not exist, so a referenced
    store is denied rather than allowed just because it is absent right now.
    """
    out: set[str] = set()
    for pat in reg.get("secret_files") or []:
        if not isinstance(pat, str) or not pat:
            continue
        expanded = os.path.expanduser(pat)
        if any(ch in expanded for ch in "*?["):
            try:
                hits = glob.glob(expanded, recursive="**" in expanded)
            except Exception:
                hits = []
            for h in hits[:512]:
                out.add(os.path.normpath(h))
        else:
            out.add(os.path.normpath(expanded))
    return out


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
        if any(t in ("-x", "-o", "+x") or t == "xtrace" for t in rest):
            return (
                f"X2 command echo: `{head} -x` traces EXPANDED commands, so any secret "
                f"in them reaches the transcript."
            )
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


def _check_x4(toks: list[str], head: str, cwd: str, stores: set[str]) -> str | None:
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


def _matches_store(token: str, cwd: str, stores: set[str]) -> bool:
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
    return bool(candidates & stores)


def _check_x5(tool: str, tool_input: dict, stores: set[str]) -> str | None:
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


def _judge_command(command: str, cwd: str, reg: dict) -> str | None:
    secrets = _secret_names(reg)
    stores = _store_paths(reg)
    text = _strip_comments(command)
    for statement in _split_quoted(text, ["&&", "||", ";", "&", "\n"]):
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
        reason = _check_x5(tool, {**tool_input, "cwd": cwd}, _store_paths(reg))

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
