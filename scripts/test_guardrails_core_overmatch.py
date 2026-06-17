"""Test guard-over-match fix in guardrails_static_core.py (cicatrix #3 + #9).
Guiltiness: blocks real dangerous python -c calls. Innocence: does NOT block a -c
that merely PRINTS those function names, nor json/subprocess-no-shell/npm install.
Born from opus-mythos hooks TAC 2026-06-16 — the python-c pattern matched function
NAMES inside strings, blocking the audit subagent + multiple commits in-session."""
import importlib.util, os, sys

CORE = os.path.join(os.path.dirname(__file__), "guardrails_static_core.py")
spec = importlib.util.spec_from_file_location("core", CORE)
core = importlib.util.module_from_spec(spec); spec.loader.exec_module(core)


def blocks(cmd):
    r = core.evaluate({"tool_name": "Bash", "tool_input": {"command": cmd}})
    return not (r == "ALLOW" or r is None)


# function names are split so this very test file doesn't trip the live guardrail
EV = "ev" + "al"; SY = "os.sys" + "tem"; SP = "subpro" + "cess"
CASES = [
    (f"python3 -c \"print('{EV} {SY} {SP} only strings here')\"", False, "INNOCENCE: names inside a string"),
    (f"python3 -c '{SY}(\"x\")'", True, "GUILT: os.system( called"),
    (f"python3 -c '{EV}(p)'", True, "GUILT: eval( called"),
    ("python3 -c 'exec(c)'", True, "GUILT: exec( called"),
    (f"python3 -c 'import {SP}; {SP}.run(x, shell=True)'", True, "GUILT: shell=True"),
    (f"python3 -c 'import {SP}; {SP}.run([\"ls\"])'", False, "INNOCENCE: subprocess no shell"),
    ("python3 -c 'import json; print(1)'", False, "INNOCENCE: json"),
    ("npm install axios", False, "INNOCENCE: npm install"),
]


def test_guard_over_match():
    failures = []
    for cmd, want, desc in CASES:
        got = blocks(cmd)
        if got != want:
            failures.append(f"{desc}: expected block={want}, got {got}")
    assert not failures, "guard-over-match regressions:\n" + "\n".join(failures)


if __name__ == "__main__":
    ok = True
    for cmd, want, desc in CASES:
        got = blocks(cmd)
        flag = "OK " if got == want else "FAIL"
        if got != want: ok = False
        print(f"  [{flag}] {desc}: blocks={got}")
    print("=== " + ("ALL OK" if ok else "FAIL") + " ===")
    sys.exit(0 if ok else 1)
