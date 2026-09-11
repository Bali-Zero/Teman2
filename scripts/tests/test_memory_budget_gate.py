#!/usr/bin/env python3
"""Guilt + innocence suite for memory_budget_gate.py (cicatrice #3).

Runs the hook as a real subprocess with a real JSON payload on stdin, against a
real file on disk — no mocking of the thing under test.

The limit is pinned to a LITERAL here, not imported from the module: a test that
derives its threshold from its subject agrees with it by construction and proves
nothing (lesson: "una verifica che ricava il paragone dal soggetto").
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
GATE = str(_REPO / ".claude" / "hooks" / "memory_budget_gate.py")
LIMIT = 24 * 1024 + 409  # 24985 — pinned literal, must match the module's default

PASS, FAIL = [], []


_N = [0]


def make_index(tmp: pathlib.Path, size: int, name: str = None) -> pathlib.Path:
    """Create .../.claude/projects/<unique>/memory/MEMORY.md of exactly `size` bytes.

    Each fixture gets its OWN project dir: reusing one path let a later fixture
    silently clobber an earlier one and made two innocence cases assert against
    the wrong file.
    """
    if name is None:
        _N[0] += 1
        name = f"-Users-x{_N[0]}"
    d = tmp / ".claude" / "projects" / name / "memory"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "MEMORY.md"
    p.write_bytes(b"x" * size)
    return p


def run(payload: dict, env_extra=None) -> int:
    env = dict(os.environ)
    env.pop("MEMORY_BUDGET_GATE", None)
    env.pop("MEMORY_BUDGET_LIMIT_BYTES", None)
    if env_extra:
        env.update(env_extra)
    r = subprocess.run(
        [sys.executable, GATE],
        input=json.dumps(payload) if isinstance(payload, dict) else payload,
        capture_output=True, text=True, env=env,
    )
    return r.returncode


def check(name: str, got: int, want: int):
    (PASS if got == want else FAIL).append(f"{name}: atteso exit {want}, ottenuto {got}")


def main():
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)

        # ---------- COLPEVOLEZZA (deve BLOCCARE, exit 2) ----------
        p = make_index(tmp, LIMIT - 100)
        check("G1 Write che sfora",
              run({"tool_name": "Write", "tool_input": {
                  "file_path": str(p), "content": "y" * (LIMIT + 500)}}), 2)

        check("G2 Edit che cresce oltre il limite",
              run({"tool_name": "Edit", "tool_input": {
                  "file_path": str(p), "old_string": "x" * 10,
                  "new_string": "y" * 400}}), 2)

        check("G3 MultiEdit con delta netto oltre",
              run({"tool_name": "MultiEdit", "tool_input": {
                  "file_path": str(p), "edits": [
                      {"old_string": "x" * 5, "new_string": "y" * 300},
                      {"old_string": "x" * 5, "new_string": "z" * 300}]}}), 2)

        check("G4 un solo byte oltre il limite",
              run({"tool_name": "Write", "tool_input": {
                  "file_path": str(p), "content": "y" * (LIMIT + 1)}}), 2)

        # byte-accuracy: 200 emoji = 800 byte UTF-8, non 200 caratteri.
        p2 = make_index(tmp, LIMIT - 300)
        check("G5 emoji contati in BYTE non in caratteri",
              run({"tool_name": "Edit", "tool_input": {
                  "file_path": str(p2), "old_string": "x",
                  "new_string": "🔴" * 200}}), 2)

        # ---------- INNOCENZA (deve PASSARE, exit 0) ----------
        # Il caso critico: file GIA' oltre il limite, scrittura che lo rimpicciolisce.
        over = make_index(tmp, LIMIT + 5000)
        check("I1 CRITICO: Edit che RIMPICCIOLISCE mentre e' gia' oltre",
              run({"tool_name": "Edit", "tool_input": {
                  "file_path": str(over), "old_string": "x" * 2000,
                  "new_string": "y" * 10}}), 0)

        check("I2 CRITICO: Write che rimpicciolisce mentre e' gia' oltre",
              run({"tool_name": "Write", "tool_input": {
                  "file_path": str(over), "content": "y" * (LIMIT + 100)}}), 0)

        check("I3 esattamente AL limite (confine, non oltre)",
              run({"tool_name": "Write", "tool_input": {
                  "file_path": str(p), "content": "y" * LIMIT}}), 0)

        small = make_index(tmp, LIMIT - 100)
        check("I4 Edit che resta sotto",
              run({"tool_name": "Edit", "tool_input": {
                  "file_path": str(small), "old_string": "x" * 10,
                  "new_string": "y" * 20}}), 0)

        # File-tema: NON iniettato, deve restare libero di crescere.
        topic = over.parent / "MEMORY_LATEST_WORK.md"
        topic.write_bytes(b"x" * (LIMIT + 9000))
        check("I5 file-tema MEMORY_*.md esente",
              run({"tool_name": "Write", "tool_input": {
                  "file_path": str(topic), "content": "y" * (LIMIT * 3)}}), 0)

        # Un MEMORY.md che NON e' l'indice iniettato (es. dentro un repo).
        other = tmp / "repo" / "docs" / "MEMORY.md"
        other.parent.mkdir(parents=True, exist_ok=True)
        other.write_bytes(b"x" * 100)
        check("I6 MEMORY.md fuori da .claude/projects/*/memory",
              run({"tool_name": "Write", "tool_input": {
                  "file_path": str(other), "content": "y" * (LIMIT * 2)}}), 0)

        check("I7 kill switch",
              run({"tool_name": "Write", "tool_input": {
                  "file_path": str(p), "content": "y" * (LIMIT + 5000)}},
                  {"MEMORY_BUDGET_GATE": "off"}), 0)

        check("I8 payload malformato -> fail-open",
              run("non e' json"), 0)

        check("I9 tool sconosciuto -> fail-open",
              run({"tool_name": "Bash", "tool_input": {"command": "ls"}}), 0)

        check("I10 old_string assente (count 0) non esplode",
              run({"tool_name": "Edit", "tool_input": {
                  "file_path": str(small), "old_string": "NONESISTE",
                  "new_string": "y" * 9000}}), 0)

        check("I11 file inesistente -> fail-open",
              run({"tool_name": "Write", "tool_input": {
                  "file_path": str(tmp / ".claude" / "projects" / "-Users-z"
                                    / "memory" / "MEMORY.md"),
                  "content": "y" * (LIMIT * 2)}}), 0)

        # Path-aware: username diverso (M5 = -Users-balizero) deve essere coperto.
        m5 = tmp / ".claude" / "projects" / "-Users-balizero" / "memory"
        m5.mkdir(parents=True, exist_ok=True)
        (m5 / "MEMORY.md").write_bytes(b"x" * (LIMIT - 50))
        check("G6 path-aware: username diverso e' comunque gated",
              run({"tool_name": "Write", "tool_input": {
                  "file_path": str(m5 / "MEMORY.md"),
                  "content": "y" * (LIMIT + 200)}}), 2)

    print(f"\n{'='*62}")
    for line in PASS:
        print(f"  ok    {line}")
    for line in FAIL:
        print(f"  FAIL  {line}")
    print(f"{'='*62}")
    print(f"passati {len(PASS)}  falliti {len(FAIL)}")
    return 1 if FAIL else 0


def test_memory_budget_gate_guilt_and_innocence():
    """Pytest entry point.

    Without a real `test_` function pytest would collect ZERO tests from this
    file and report green having run nothing — a vacuous proof of exactly the
    kind this repo keeps getting bitten by. The assert carries the failing
    cases so a red says WHICH property broke, not just that something did.
    """
    rc = main()
    assert not FAIL, "casi falliti:\n  " + "\n  ".join(FAIL)
    assert rc == 0
    # Anti-vacuity: a suite that silently stopped building fixtures would also
    # report zero failures. Assert the COUNT, never just the absence of reds.
    assert len(PASS) >= 17, f"attesi >=17 casi, eseguiti {len(PASS)}"


if __name__ == "__main__":
    sys.exit(main())
