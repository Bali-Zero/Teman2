#!/usr/bin/env python3
"""Every organ that shells out to tg_notify.py must read the gateway's VERDICT.

WHY THIS IS A CLASS GUARD AND NOT SEVEN TESTS
---------------------------------------------
`tg_notify.py` exits 0 on six different outcomes, and three of them mean the
message did NOT reach Telegram now:

    sent · logged · spooled · deduped · p0_overflow_spooled · p0_unsent_spooled

So `returncode == 0` reads a refusal as a delivery. The verdict is printed to
stderr as `tg_notify: <verdict>`; a caller that never parses it cannot tell
"paged the owner" from "the budget swallowed it".

Measured on 2026-08-10, after the sender-consolidation batches: **seven** live
callers were blind this way — one captured the output and discarded it inside
`except: pass`, one logged `tg_notify exit=N` (the mistake spelled out), two
read stderr only inside the `returncode != 0` branch a refusal never takes, and
three returned a bare `returncode == 0`. Curing the one file that prompted the
census would have left six, which is the W107 mistake exactly: it does not cut
the risk, it only moves which organ goes deaf.

This guard is therefore written against the CLASS. A new caller added next year
fails here on its first PR, which no per-file test can do.

WHAT IT CANNOT SEE (declared, not hidden)
-----------------------------------------
It walks Python only, and only functions that invoke a subprocess *and* name the
gateway. Shell callers use the same convention (`log "tg_notify: $(… | tail -1)"`)
and are covered behaviourally by scripts/tests/test_tg_sender_migration.sh, which
runs each of them against a fake gateway. A Python caller that builds the command
in one function and runs it in another is out of scope here.

Run: python3 scripts/tests/test_gateway_callers_read_the_verdict.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOTS = ("scripts", "apps", "infra")
SUBPROCESS_CALL = re.compile(
    r"(?:subprocess\.(?:run|call|Popen|check_output)|asyncio\.create_subprocess_exec)"
)
# Reading is necessary but not sufficient: the verdict must affect the returned
# success value.  The old guard accepted `parse; log; return rc == 0`, which is
# exactly the refusal-as-delivery bug it was meant to prevent.
READS_VERDICT = re.compile(
    r"tg_notify:|_GATEWAY_VERDICT_RE|VERDICT|extract_gateway_verdict|gateway_delivered"
)
SEMANTIC_VERDICT_USE = re.compile(
    r"verdict|outcome|match|_GATEWAY_VERDICT_RE|tg_notify:|"
    r"extract_gateway_verdict|gateway_delivered",
    re.IGNORECASE,
)


def _is_excluded(p: Path) -> bool:
    sp = str(p)
    return (
        "/tests/" in sp
        or p.name.startswith("test_")
        or p.name == "tg_notify.py"          # the gateway itself
        or "node_modules" in sp
        or "/.venv/" in sp
        or "/site-packages/" in sp
    )


def _subprocess_lines(node: ast.AST, src: str) -> list[int]:
    lines: list[int] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        call_src = ast.get_source_segment(src, child) or ""
        if SUBPROCESS_CALL.search(call_src):
            lines.append(child.lineno)
    return lines


def _return_is_guarded_by_verdict(
    node: ast.Return,
    parents: dict[ast.AST, ast.AST],
    src: str,
) -> bool:
    parent = parents.get(node)
    while parent is not None and not isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if isinstance(parent, ast.If):
            test_src = ast.get_source_segment(src, parent.test) or ""
            if SEMANTIC_VERDICT_USE.search(test_src):
                return True
        parent = parents.get(parent)
    return False


def _returncode_zero_means_success(node: ast.AST) -> bool:
    """Whether an expression converts ``returncode == 0`` into success."""
    if isinstance(node, ast.Compare):
        values = [node.left, *node.comparators]
        has_returncode = any(
            isinstance(value, ast.Attribute) and value.attr == "returncode"
            for value in values
        )
        has_zero = any(isinstance(value, ast.Constant) and value.value == 0 for value in values)
        return has_returncode and has_zero and any(isinstance(op, ast.Eq) for op in node.ops)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return isinstance(node.operand, ast.Attribute) and node.operand.attr == "returncode"
    return any(_returncode_zero_means_success(child) for child in ast.iter_child_nodes(node))


def _reads_verdict_semantically(node: ast.AST, body: str, src: str) -> bool:
    """Reject verdict theatre: parsing/logging followed by blind success."""
    if not READS_VERDICT.search(body):
        return False

    subprocess_lines = _subprocess_lines(node, src)
    if not subprocess_lines:
        return False
    first_subprocess = min(subprocess_lines)
    parents = {
        child: parent
        for parent in ast.walk(node)
        for child in ast.iter_child_nodes(parent)
    }

    for child in ast.walk(node):
        if not isinstance(child, ast.Return) or child.value is None:
            continue
        # Dry-run / local-dedupe returns before the gateway call are unrelated.
        if child.lineno <= first_subprocess:
            continue
        return_src = ast.get_source_segment(src, child.value) or ""
        if _returncode_zero_means_success(child.value) and not SEMANTIC_VERDICT_USE.search(return_src):
            return False
        if (
            isinstance(child.value, ast.Constant)
            and child.value.value is True
            and not _return_is_guarded_by_verdict(child, parents, src)
        ):
            return False
    return True


def find_callers() -> tuple[list[str], list[str]]:
    """Return (blind, reading) as 'path::function' labels."""
    blind: list[str] = []
    reading: list[str] = []
    for root in ROOTS:
        for p in sorted((REPO / root).rglob("*.py")):
            if _is_excluded(p):
                continue
            src = p.read_text(errors="replace")
            if "tg_notify" not in src:
                continue
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            lines = src.splitlines()
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                body = "\n".join(lines[node.lineno - 1 : node.end_lineno])
                if not SUBPROCESS_CALL.search(body) or "tg_notify" not in body:
                    continue
                label = f"{p.relative_to(REPO)}::{node.name}"
                (reading if _reads_verdict_semantically(node, body, src) else blind).append(label)
    return blind, reading


# ── the guard proves itself before it judges anyone (guilt AND innocence) ──────
_GUILTY_BARE = '''
import subprocess, sys
def send(msg):
    gateway = "/x/tg_notify.py"
    return subprocess.run([sys.executable, gateway, msg]).returncode == 0
'''

_GUILTY_PARSE_RC0 = '''
import re, subprocess, sys
_GATEWAY_VERDICT_RE = re.compile(r"^tg_notify:\\s*(\\S+)", re.MULTILINE)
def send(msg):
    gateway = "/x/tg_notify.py"
    p = subprocess.run([sys.executable, gateway, msg], capture_output=True, text=True)
    m = _GATEWAY_VERDICT_RE.search(p.stderr or "")
    print(f"verdict: {m.group(1) if m else 'none'}")
    return p.returncode == 0
'''

_GUILTY_PARSE_TRUE = '''
import re, subprocess, sys
_GATEWAY_VERDICT_RE = re.compile(r"^tg_notify:\\s*(\\S+)", re.MULTILINE)
def send(msg):
    gateway = "/x/tg_notify.py"
    p = subprocess.run([sys.executable, gateway, msg], capture_output=True, text=True)
    m = _GATEWAY_VERDICT_RE.search(p.stderr or "")
    print(f"verdict: {m.group(1) if m else 'none'}")
    return True
'''

_INNOCENT_SEMANTIC = '''
import subprocess, sys
def send(msg):
    gateway = "/x/tg_notify.py"
    p = subprocess.run([sys.executable, gateway, msg], capture_output=True, text=True)
    verdict = extract_gateway_verdict(p.stderr)
    return p.returncode == 0 and gateway_delivered(verdict)
'''

# A neighbour that must NOT be caught: shells out, never touches the gateway.
_BYSTANDER = '''
import subprocess
def backup():
    return subprocess.run(["tar", "czf", "x.tgz", "."]).returncode == 0
'''


def _classify(src: str) -> str:
    tree = ast.parse(src)
    lines = src.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = "\n".join(lines[node.lineno - 1 : node.end_lineno])
        if not SUBPROCESS_CALL.search(body) or "tg_notify" not in body:
            continue
        return "reading" if _reads_verdict_semantically(node, body, src) else "blind"
    return "not-a-caller"


# (fixture, verdetto atteso, cosa si rompe se sbaglia). Tabella e non una catena
# di `if`, così il numero di casi è MISURATO e stampabile: la riga di successo
# nomina il selftest, e "è girato" non si confonde con "è stato saltato".
_SELFTEST_CASES: list[tuple[str, str, str]] = [
    (_GUILTY_BARE, "blind", "un chiamante cieco NON viene colto"),
    (_GUILTY_PARSE_RC0, "blind", "parse+log+returncode viene assolto"),
    (_GUILTY_PARSE_TRUE, "blind", "parse+log+True viene assolto"),
    (_INNOCENT_SEMANTIC, "reading", "un chiamante corretto viene accusato"),
    (_BYSTANDER, "not-a-caller", "un subprocess estraneo al gateway viene giudicato"),
]


def selftest() -> list[str]:
    return [
        f"selftest: {why}"
        for fixture, expected, why in _SELFTEST_CASES
        if _classify(fixture) != expected
    ]


def main() -> int:
    failures = selftest()
    if failures:
        # A probe that cannot tell guilt from innocence must never report on the
        # tree: it would print a clean sweep it did not earn (W107).
        for f in failures:
            print(f"✗ {f}", file=sys.stderr)
        return 2

    blind, reading = find_callers()
    if not reading and not blind:
        # Zero callers traversed is not "clean" — it is a broken scan (W84).
        print("✗ nessun chiamante del gateway trovato: scansione rotta, non albero pulito",
              file=sys.stderr)
        return 2

    # Name the selftest in the SUCCESS line, not only in the failure path. It
    # runs unconditionally above, but a reader who cannot see that in the output
    # cannot tell "the self-check passed" from "the self-check was skipped" —
    # measured 2026-08-10: a PROVE-LIVE run of this guard passed a `--selftest`
    # flag that does not exist, got byte-identical output, and read that as
    # evidence the selftest had been silently ignored. A probe must declare what
    # it verified (the same class as W107's "the probe can have the disease").
    print(
        f"gateway callers: {len(reading)} leggono il verdetto, {len(blind)} ciechi"
        f" (selftest classificatore: {len(_SELFTEST_CASES)} casi OK)"
    )
    if blind:
        print("\nUn chiamante che ignora il verdetto non distingue una CONSEGNA da un", file=sys.stderr)
        print("RIFIUTO: il gateway esce 0 anche su deduped / p0_overflow_spooled /", file=sys.stderr)
        print("p0_unsent_spooled. Leggi `tg_notify: <verdetto>` da stderr (W104).\n", file=sys.stderr)
        for b in blind:
            print(f"  ✗ {b}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
