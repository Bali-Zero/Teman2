#!/usr/bin/env python3
"""test_secret_expansion_guard.py — the spec's §5 case corpus (E01-E64), run
against the real hook as a subprocess exactly as the harness would (JSON on
stdin, exit 2 = DENY, exit 0 = ALLOW).

Spec: docs/specs/2026-09-18-secret-expansion-guard-shapes-spec.md
The spec is the oracle. A row that disagrees with the implementation is a BUG IN
ONE OF THEM, and per the spec's own rule the spec wins — do not "fix" a failing
row by editing its expected verdict; that is how output_hygiene_guard v1 drifted
into three rounds of over-match.

Hermetic (W96): HOME is a temp dir for the subprocess, so the registry's `~/…`
store globs resolve inside the fixture and the verdict never depends on whether
the real ~/.nuzantara-secrets.env exists or what its mode is.

Run: python3 infra/claude-hooks/test_secret_expansion_guard.py
Also: pytest infra/claude-hooks/test_secret_expansion_guard.py
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
HOOK = HERE / "secret_expansion_guard.py"

N = "BAILIAN_TOKEN_PLAN_API_KEY"          # registered explicitly
N2 = "ANTHROPIC_API_KEY"                  # registered via the ^ANTHROPIC_ pattern
STORE = "~/.nuzantara-secrets.env"        # registered secret store

_HOME = pathlib.Path(tempfile.mkdtemp(prefix="secret_expansion_guard_"))
(_HOME / ".nuzantara-secrets.env").write_text(
    f"export {N}='fixture-not-a-real-key'\n"
)
(_HOME / ".qwen").mkdir(exist_ok=True)
(_HOME / ".qwen" / "settings.json").write_text('{"env":{}}\n')
(_HOME / ".codex").mkdir(exist_ok=True)
(_HOME / ".codex" / "auth.json").write_text('{"t":"fixture"}\n')
(_HOME / ".claude-zero-team").mkdir(exist_ok=True)   # E55: NO .credentials.json inside, on purpose
SETTINGS_JSON = HERE.parent.parent / ".claude" / "settings.json"


def _expected_rc(expect_deny: bool) -> int:
    """ONE oracle for both runners. ALLOW is rc == 0 EXACTLY, never `rc != 2`: a
    guard that crashes exits 1, and `rc != 2` scores that as a pass on every
    innocence row — the first cut of this file did exactly that and 21 of 25
    innocence rows "passed" on a hook with a SyntaxError. The standalone runner
    below had kept the `rc != 2` form after the pytest path was fixed; the gate
    (2026-09-19) unified them here."""
    return 2 if expect_deny else 0


def _run(tool: str, tool_input: dict, cwd: str | None = None, off: bool = False) -> tuple[int, str]:
    payload = {"tool_name": tool, "tool_input": tool_input, "cwd": cwd or str(_HOME)}
    env = dict(os.environ, HOME=str(_HOME))
    if off:
        env["NUZ_SECRET_EXPANSION_GUARD_OFF"] = "1"
    else:
        env.pop("NUZ_SECRET_EXPANSION_GUARD_OFF", None)
    p = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=30,
    )
    return p.returncode, (p.stderr or "").strip()


def bash(cmd: str, **kw) -> tuple[int, str]:
    return _run("Bash", {"command": cmd}, **kw)


def read_tool(path: str, **extra) -> tuple[int, str]:
    return _run("Read", {"file_path": path, **extra})


# ---------------------------------------------------------------------------
# The corpus. (id, callable -> (rc, stderr), expected DENY?, note)
# ---------------------------------------------------------------------------
CORPUS: list[tuple[str, object, bool, str]] = [
    # --- X1: a secret value expansion reaching stdout ---
    ("E01", lambda: bash(f'echo "${{{N}:-UNSET}}"'), True, "incident 2 verbatim"),
    ("E02", lambda: bash(f'printf "[%s]\\n" "${{{N}:+SET}}${{{N}:-UNSET}}"'), True,
     "incident 3 verbatim; :+ does not launder :-"),
    ("E03", lambda: bash(f"echo ${N}"), True, "bare $NAME in a print stage"),
    ("E04", lambda: bash(f'echo "${{{N}}}"'), True, "braces, no operator, still emits"),
    ("E05", lambda: bash(f'echo "${{{N}:?not set}}"'), True, ":? form"),
    ("E06", lambda: bash(f'echo "${{{N}:+SET}}"'), False, "the sanctioned presence check"),
    ("E07", lambda: bash(f'printf "x=%s\\n" "${{{N}:+SET}}"'), False, "presence check via printf"),
    ("E08", lambda: bash(f'test -n "${N}" && echo present'), False, "expansion not in a print stage"),
    ("E09", lambda: bash(f'curl -H "Authorization: Bearer ${N}" https://api/'), False,
     "THE correct way to use a key"),
    ("E10", lambda: bash(f'python3 tool.py --key "${N}"'), False, "passing, not printing"),
    ("E11", lambda: bash(f'grep -rn "{N}" scripts/'), False, "bare name, no $ — how consumers were found"),
    ("E12", lambda: bash(f"export {N}=something"), False, "assignment, not a dump"),
    # --- X2: environment dumps ---
    ("E13", lambda: bash(f"printenv {N}"), True, "printenv names a secret"),
    ("E14", lambda: bash("printenv"), True, "dumps every secret at once"),
    ("E15", lambda: bash("env"), True, "bare env"),
    ("E16", lambda: bash("env | grep -i token"), True, "first stage is a dump"),
    ("E17", lambda: bash("env -i HOME=/tmp cmd"), False, "sets a clean env, prints nothing"),
    ("E18", lambda: bash(f"env -u {N} python3 x.py"), False, "the sanctioned fallback test"),
    ("E19", lambda: bash("NAME=x python3 x.py"), False, "stage-local assignment"),
    ("E20", lambda: bash("export -p"), True, "prints every variable and value"),
    # --- X3: Keychain value print ---
    ("E21", lambda: bash("security find-generic-password -s svc -w"), True, "-w prints the secret"),
    ("E22", lambda: bash("security find-generic-password -s svc"), False, "metadata only"),
    ("E23", lambda: bash("security find-generic-password -s svc -w | shasum -a 256"), True,
     "piping to a hash does not un-leak stage 1"),
    # --- X4: credential store content dump ---
    ("E24", lambda: bash(f"cat {STORE}"), True, "cat a store"),
    ("E25", lambda: bash(f"head -3 {STORE}"), True, "head a store"),
    ("E26", lambda: bash(f"jq . {STORE}"), True, "jq a store"),
    ("E27", lambda: bash(f"stat -f %Lp {STORE}"), False, "metadata — the mode check itself"),
    ("E28", lambda: bash(f"chmod 600 {STORE}"), False, "THE CURE must not be blocked"),
    ("E29", lambda: bash(f"wc -c {STORE}"), False, "byte count only"),
    ("E30", lambda: bash(f"grep -c {N} {STORE}"), False, "count only"),
    ("E31", lambda: bash(f"grep {N} {STORE}"), True, "prints the matching line, which IS the value"),
    ("E32", lambda: bash(f"ls -la {STORE}"), False, "listing, not content"),
    ("E33", lambda: bash(f"bash <<EOF\necho ${N}\nEOF"), True,
     "heredoc body — why spec §3 does not blank heredocs"),
    ("E34", lambda: bash(f"cat {STORE} > /tmp/x"), True, "redirect does not un-read the secret"),
    # --- innocence / noise ---
    ("E35", lambda: bash("echo hello"), False, "no secret anywhere"),
    # --- X5: Read tool ---
    ("E36", lambda: read_tool(STORE), True, "Read a store"),
    ("E37", lambda: read_tool(STORE, limit=5), True, "a slice can contain the one secret line"),
    ("E38", lambda: read_tool("/etc/hosts"), False, "unregistered path"),
    ("E39", lambda: read_tool("~/.qwen/settings.json"), False,
     "spec §4 out-of-scope, deliberate: config, not a store"),
    # --- registry generality ---
    ("E40", lambda: bash(f'echo "${{{N2}:-x}}"'), True, "registry pattern, not just the TP1 var"),
    ("E41", lambda: bash('echo "$PATH"'), False, "not a registered secret"),
    # --- parsing edge cases ---
    ("E42", lambda: bash(f"# never echo ${N}"), False, "comment prose is not an expansion"),
    ("E43", lambda: bash(rf'echo "use \${{{N}:-x}} carefully"'), False, r"escaped \$ is literal text"),
    # --- fail-open ---
    ("E44", lambda: _run("Bash", "not-a-dict"), False, "malformed tool_input fails open"),
    ("E45", lambda: _run("SomeUnknownTool", {"x": 1}), False, "unrelated tool fails open"),
    ("E46", lambda: bash(f'echo "${{{N}:-UNSET}}"', off=True), False, "kill switch"),
    # --- gate 2026-09-19: over-matches found live on everyday commands ---
    ("E47", lambda: bash("set -o pipefail; ls | head"), False, "-o without xtrace is not tracing"),
    ("E48", lambda: bash("set +x; ls"), False, "+x turns tracing OFF"),
    ("E49", lambda: bash("declare -x FOO=1; ls"), False, "declare -x exports, it does not print"),
    ("E50", lambda: bash("set -euxo pipefail"), True, "combined flag string carries x"),
    ("E51", lambda: bash("declare -p"), True, "declare -p prints every variable with its value"),
    # --- gate 2026-09-19: command substitution is judged, not skipped ---
    ("E52", lambda: bash(f'echo "$(cat {STORE})"'), True, "X4 inside $(...)"),
    ("E53", lambda: bash(f"echo `printenv {N}`"), True, "X2 inside backticks"),
    ("E54", lambda: bash('echo "$(date)"'), False, "substitution with nothing guilty in it"),
    ("E55", lambda: read_tool(str(_HOME / ".claude-zero-team" / ".credentials.json")), True,
     "glob store matched by PATTERN — the file does not exist in the fixture"),
    ("E56", lambda: bash(f'echo "$(curl -H "Authorization: Bearer ${N}" https://api/)"'), False,
     "outer echo prints the response, not the key; the body is E09"),
    # --- gate 2026-09-19: heredocs — literal data vs code a shell will run ---
    ("E57", lambda: bash(f"python3 - <<'PY'\nprint(\"cat {STORE}\")\nPY"), False,
     "quoted heredoc to a non-shell is literal data (the repo's own editing idiom)"),
    ("E58", lambda: bash(f"bash <<'EOF'\ncat {STORE}\nEOF"), True,
     "quoted or not, a heredoc to bash is code the child runs"),
    ("E59", lambda: bash(f"ssh pro <<'EOF'\ncat {STORE}\nEOF"), True,
     "ssh runs a remote shell and its output comes back to the transcript"),
    # --- gate 2026-09-19: the SAME entity as E58, given as a `-c` string argument.
    # The heredoc spelling was judged and the idiomatic one was not (superscar #3,
    # UNDER-match), found by probing the guard independently of this corpus.
    ("E60", lambda: bash(f"bash -c 'cat {STORE}'"), True,
     "`bash -c` runs code the child runs — E58's entity, one spelling apart"),
    ("E61", lambda: bash(f"sh -lc 'printenv {N}'"), True,
     "combined flag string carries c; the payload is still code"),
    ("E62", lambda: bash("bash -c 'echo hello'"), False,
     "innocence: a -c payload with nothing guilty in it"),
    ("E63", lambda: bash(f"eval 'cat {STORE}'"), True,
     "eval runs its argument as code in the CURRENT shell"),
    ("E64", lambda: bash(f"ssh pro 'cat {STORE}'"), False,
     "KNOWN BOUNDARY, not an endorsement: judging a remote inline command needs the "
     "read-vs-write distinction of W94 (a remote WRITE stays remote) and that spec "
     "row is not written yet. Pinned so the gap is visible and flips when it is."),
]


def test_corpus_row_by_row():
    """One assertion per corpus row, so a failure names the E-id, not a blob.

    ALLOW is asserted as rc == 0 EXACTLY, not as "not 2". A guard that crashes
    exits 1, and `rc != 2` would score that as a pass on every innocence row —
    the broken guard would look perfectly well-behaved. That is not a hypothetical:
    the first version of this file shipped with an f-string SyntaxError and 21 of
    25 innocence rows "passed" on a hook that never ran.
    """
    failures = []
    for eid, fn, expect_deny, note in CORPUS:
        rc, err = fn()
        expected_rc = _expected_rc(expect_deny)
        if rc != expected_rc:
            failures.append(
                f"{eid}: expected rc={expected_rc} ({'DENY' if expect_deny else 'ALLOW'}), "
                f"got rc={rc} ({note})\n    stderr: {err[:300]}"
            )
        if rc == 2 and not err:
            failures.append(f"{eid}: DENY with no stderr reason (contract requires one line)")
        if "fixture-not-a-real-key" in err:
            failures.append(f"{eid}: the DENY reason leaked a secret value")
    assert not failures, "\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# Rows that the corpus cannot express as a single command line
# ---------------------------------------------------------------------------


def test_malformed_stdin_fails_open():
    p = subprocess.run(
        [sys.executable, str(HOOK)], input="{not json",
        capture_output=True, text=True,
        env=dict(os.environ, HOME=str(_HOME)), timeout=30,
    )
    assert p.returncode == 0


def test_non_dict_payload_fails_open():
    p = subprocess.run(
        [sys.executable, str(HOOK)], input="[1,2,3]",
        capture_output=True, text=True,
        env=dict(os.environ, HOME=str(_HOME)), timeout=30,
    )
    assert p.returncode == 0


def test_corrupt_registry_fails_open_with_a_warning(tmp_path):
    """A malformed registry must never brick Bash, and must say why it stood down."""
    broken = tmp_path / "infra" / "claude-hooks"
    broken.mkdir(parents=True)
    (broken / "secret-expansion-registry.json").write_text("{ this is not json")
    hook = broken / "secret_expansion_guard.py"
    hook.write_text(HOOK.read_text())
    p = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": f'echo "${{{N}:-UNSET}}"'},
                          "cwd": str(tmp_path)}),
        capture_output=True, text=True,
        env=dict(os.environ, HOME=str(_HOME)), timeout=30,
    )
    assert p.returncode == 0
    assert "WARN" in p.stderr


def test_deny_reason_names_the_shape_and_never_the_value():
    """The reason is what the session reads to correct itself, so it must carry the
    shape id and the sanctioned alternative — and must not carry the secret."""
    rc, err = bash(f'echo "${{{N}:-UNSET}}"')
    assert rc == 2
    assert "X1" in err
    assert ":+SET" in err          # names the correct form
    assert N in err                # names the variable
    assert "fixture-not-a-real-key" not in err


def test_glued_redirect_does_not_hide_the_store():
    """Under-match guard: `cat store>/tmp/x` must not slip past because the operand
    and the redirect operator are one token."""
    rc, err = bash(f"cat {STORE}>/tmp/out.txt")
    assert rc == 2, f"glued redirect hid the store: {err}"
    assert "X4" in err


def test_store_dump_denied_for_every_registered_content_verb():
    for verb in ("cat", "bat", "head", "tail", "less", "strings", "xxd", "od", "base64"):
        rc, err = bash(f"{verb} {STORE}")
        assert rc == 2, f"{verb} on a store was allowed: {err}"


def test_second_secret_store_is_also_covered():
    rc, err = bash("cat ~/.codex/auth.json")
    assert rc == 2, f"~/.codex/auth.json was allowed: {err}"


def test_monitor_tool_is_the_same_shell_channel():
    """Monitor executes arbitrary shell with different scheduling — not a lesser
    surface (data_plane_guard's own wording)."""
    rc, err = _run("Monitor", {"command": f'echo "${{{N}:-UNSET}}"'})
    assert rc == 2, f"Monitor bypassed the guard: {err}"


def test_qwen_harness_tool_name_is_covered():
    """The Qwen harness leaked too, and calls the tool `run_shell_command`."""
    rc, err = _run("run_shell_command", {"command": f'echo "${{{N}:-UNSET}}"'})
    assert rc == 2, f"run_shell_command bypassed the guard: {err}"


def test_multistatement_command_is_judged_per_statement():
    """A clean first statement must not launder a leaking second one."""
    rc, err = bash(f"echo hello && printenv {N}")
    assert rc == 2, f"second statement escaped: {err}"


def test_settings_json_wires_the_hook():
    """The consumer named in the PR's Bites line. A settings-only regression (wrong
    matcher, wrong filename) must fail here even though the guard itself is fine
    — same shape as test_data_plane_guard's B2 assertion."""
    assert HOOK.exists()
    assert SETTINGS_JSON.exists(), f"settings.json missing: {SETTINGS_JSON}"
    data = json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))
    required = {"Bash", "Monitor", "Read"}
    found = False
    for block in data.get("hooks", {}).get("PreToolUse", []):
        if not required <= set(block.get("matcher", "").split("|")):
            continue
        for h in block.get("hooks", []):
            if "infra/claude-hooks/secret_expansion_guard.py" in h.get("command", ""):
                found = True
    assert found, (
        "No PreToolUse block in .claude/settings.json has BOTH a matcher covering "
        f"{sorted(required)} AND a command referencing infra/claude-hooks/secret_expansion_guard.py"
    )


def test_store_match_never_walks_the_filesystem():
    """Spec §2: the guard does no filesystem walk. The first cut glob.glob'd the
    registry's `~/.config/**` patterns on EVERY call (~100 ms on a real ~/.config,
    against a 5 ms budget) and could only deny a store that existed at that
    instant. Pin it: a HOME with a deep ~/.config tree must cost no more than an
    empty one, and an absent glob-store path must still be denied (E55)."""
    import time
    deep = pathlib.Path(tempfile.mkdtemp(prefix="secret_expansion_deep_"))
    for i in range(40):
        d = deep / ".config" / f"app{i}" / "nested" / "deeper"
        d.mkdir(parents=True)
        for j in range(25):
            (d / f"f{j}.txt").write_text("x")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -la ~"},
                          "cwd": str(deep)})

    def per_call_ms(home: pathlib.Path) -> float:
        env = dict(os.environ, HOME=str(home))
        env.pop("NUZ_SECRET_EXPANSION_GUARD_OFF", None)
        start = time.monotonic()
        for _ in range(5):
            subprocess.run([sys.executable, str(HOOK)], input=payload,
                           capture_output=True, text=True, env=env, timeout=30)
        return (time.monotonic() - start) / 5 * 1000

    empty, populated = per_call_ms(_HOME), per_call_ms(deep)
    assert populated < empty * 2 + 40, f"deep HOME {populated:.0f}ms vs empty {empty:.0f}ms — a walk is back"
    rc, err = _run("Read", {"file_path": str(_HOME / ".config" / "gcloud" / "credentials.json")})
    assert rc == 2 and "X5" in err, f"absent glob-store path was not denied: rc={rc} {err}"


def test_latency_budget_under_5ms():
    """Spec §2 budget. A guard on every Bash call cannot be slow."""
    import time
    cmd = f'grep -rn "{N}" scripts/ && echo "${{{N}:+SET}}" && ls -la ~'
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd},
                          "cwd": str(_HOME)})
    env = dict(os.environ, HOME=str(_HOME))
    start = time.monotonic()
    for _ in range(5):
        subprocess.run([sys.executable, str(HOOK)], input=payload,
                       capture_output=True, text=True, env=env, timeout=30)
    per_call_ms = (time.monotonic() - start) / 5 * 1000
    # Interpreter startup dominates and the budget is for the guard's own work;
    # assert a ceiling that still catches an accidental O(files) walk.
    assert per_call_ms < 250, f"{per_call_ms:.0f}ms per call"


def _main() -> int:
    failures = []
    for eid, fn, expect_deny, note in CORPUS:
        rc, err = fn()
        ok = rc == _expected_rc(expect_deny)
        failures.append(None if ok else f"{eid}: want {'DENY' if expect_deny else 'ALLOW'} got rc={rc}")
        verdict = "DENY" if rc == 2 else ("ALLOW" if rc == 0 else f"CRASH(rc={rc})")
        print(f"  {'PASS' if ok else 'FAIL'}  {eid}  {verdict}  {note}")
    bad = [f for f in failures if f]
    print(f"\n{len(CORPUS) - len(bad)}/{len(CORPUS)} corpus rows as specified")
    for b in bad:
        print("  ", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(_main())
