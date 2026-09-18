#!/usr/bin/env python3
"""dynamic_workflow.py — the ONE launcher for /dynamic-workflow. Code, not prose; every
verdict judged by CONTENT, never by exit code alone (scar #2, "Esiste != Armato").

Subcommands (PR1a — r1 lands in PR1b, r2/judge/anonymise/capture-check in PR2):
    brief    --slug S --objective-file F --colour BLUE|ORANGE [--floor X] [--template T] [--kit K]
    check    --kit K            # recompute BRIEF.md from template+inputs.json, byte-diff (W78)
    validate FILE --sha S       # frontmatter+skeleton+word-count gate

PII gate is fail-closed, no --skip-pii flag exists: the objective is redacted with the SAME
Redactor used before anything leaves this machine; any change, or any raise, refuses with a
SPAN COUNT only, never the text. DW_FAKE_SEATS=1 makes the arsenal-liveness probe offline and
deterministic — what --selftest runs on, never a real invocation.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
from _redact_pii import RedactionError, Redactor  # noqa: E402

REPO_ROOT = _SCRIPTS_DIR.parent
DEFAULT_TEMPLATE = REPO_ROOT / ".claude" / "skills" / "dynamic-workflow" / "brief.template.md"

PLACEHOLDERS = ("{{OBJECTIVE}}", "{{COLOUR}}", "{{FLOOR}}", "{{DATE}}", "{{ARSENAL_LIVENESS}}")
SEAT_LINE_RE = re.compile(r"^you_are:.*$", re.MULTILINE)
SHA_LINE_RE = re.compile(r"^brief_sha256:.*$", re.MULTILINE)

# ARSENAL_LIVENESS fallback when the probe fails/times out (F8): every seat "unknown", never
# omitted. Informational only — PR1b's r1 launch shapes are the dispatch SSOT, not this list.
FALLBACK_SEATS = [
    "claude", "kimi", "agy", "codex", "ollama", "nlm", "qwen-cloud-code", "jules",
    "tp1-qwen3.8-max", "tp1-deepseek-v4-pro", "tp1-qwen3.7-plus", "tp1-glm-5.2",
]

REQUIRED_SECTIONS = [
    "Formation", "Tactics", "Termination", "Evidence between stages",
    "Never", "First move", "Cost",
]

# A coach's sealed answer shape, valid against REQUIRED_SECTIONS — test fixture only, reused
# unmodified by PR1b's r1 launcher tests (fake-seat + relaunch).
_CANNED_VALID = """---
seat: {seat}
objective_sha256: {sha}
facts_cited: [F1, C1]
assumptions: 0
---
## Formation
| role | seat | why (F ref) | substitute if dead (F8) |
| build | sonnet-5 | F1 | haiku-4-5 |
## Tactics
| stage | seat(s) | in-script or window | parallel/serial | round cap | exit command | hands to next stage |
| r1 | sonnet-5 | in-script | serial | 1 | validate | r2 |
## Termination
Ledger sent-row counter caps relaunch at one; a third sent row is refused by the launcher.
## Evidence between stages
r1/<seat>.md on disk, sha-verified against brief.sha before use.
## Never
- No paid Anthropic per-token endpoint (C1)
## First move
Run --selftest. Bites: CI selftest job; green run.
## Cost
1 call per seat, 0 Anthropic windows opened, wall-clock under 5 minutes.
"""


# --------------------------------------------------------------------- brief rendering

def _set_seat_line(text: str, value: str) -> str:
    return SEAT_LINE_RE.sub(f"you_are: {value}", text, count=1)


def _set_sha_line(text: str, value: str) -> str:
    return SHA_LINE_RE.sub(f"brief_sha256: {value}", text, count=1)


def render_brief(template: str, objective: str, colour: str, floor: str, date: str,
                  arsenal_block: str) -> tuple[str, str]:
    """Fill every placeholder except {{SEAT}}/{{SHA}}; hash with BOTH blanked (line-anchored,
    never a generic substring replace — a seat name appearing elsewhere in the brief text
    must never corrupt an unrelated line). Returns (master_with_seat_token_literal, sha256)."""
    filled = (template
              .replace("{{OBJECTIVE}}", objective)
              .replace("{{COLOUR}}", colour)
              .replace("{{FLOOR}}", floor)
              .replace("{{DATE}}", date)
              .replace("{{ARSENAL_LIVENESS}}", arsenal_block))
    hashable = _set_sha_line(_set_seat_line(filled, ""), "")
    sha = hashlib.sha256(hashable.encode()).hexdigest()
    master = _set_sha_line(filled, sha)
    return master, sha


def _count_changed_spans(a: str, b: str) -> int:
    sm = difflib.SequenceMatcher(None, a, b)
    return sum(1 for tag, *_ in sm.get_opcodes() if tag != "equal")


def _arsenal_liveness_block(timeout: int = 600) -> str:
    if os.environ.get("DW_FAKE_SEATS") == "1":
        rows = [("kimi", "LIVE", True, 400, "PONG (fake)"),
                 ("agy", "LIVE", True, 900, "PONG (fake)")]
    else:
        rows = None
        try:
            proc = subprocess.run(
                [sys.executable, str(_SCRIPTS_DIR / "arsenal_probe.py"), "--json"],
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
            )
            data = json.loads(proc.stdout)
            seats = data.get("seats") or []
            if not seats:
                raise ValueError("0 seats in probe output")
            rows = [(s.get("seat", "?"), s.get("status", "unknown"), s.get("healthy"),
                     s.get("latency_ms"), str(s.get("evidence", ""))[:80]) for s in seats]
        except Exception:
            rows = [(s, "unknown", None, None, "probe failed or timed out") for s in FALLBACK_SEATS]
    lines = ["| seat | status | healthy | latency_ms | evidence |", "|---|---|---|---|---|"]
    lines += [f"| {s} | {st} | {h} | {lat} | {ev} |" for s, st, h, lat, ev in rows]
    return "\n".join(lines)


# --------------------------------------------------------------------- ledger
# Append-only ('a' mode ONLY); ledger.md.sha = sha256 of current content, rewritten after
# every append, so `check` detects a row disappearing without trusting the ledger's own claim.

def _ledger_path(kit: Path) -> Path:
    return kit / "ledger.md"


def _ledger_sha_path(kit: Path) -> Path:
    return kit / "ledger.md.sha"


def ledger_append(kit: Path, seat: str, status: str, sha16: str, when: str | None = None) -> str:
    when = when or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{when} | {seat} | {status} | {sha16}\n"
    path = _ledger_path(kit)
    with open(path, "a") as f:
        f.write(line)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    _ledger_sha_path(kit).write_text(digest + "\n")
    return line


def ledger_verify(kit: Path) -> tuple[bool, str]:
    path, shapath = _ledger_path(kit), _ledger_sha_path(kit)
    if not path.exists():
        return True, "no ledger yet"
    if not shapath.exists():
        return False, "ledger.md exists but ledger.md.sha does not"
    want = shapath.read_text().strip()
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    return (got == want), f"expected {want[:16]} got {got[:16]}"


# --------------------------------------------------------------------- validate

_FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _section_text(body: str, name: str) -> str:
    m = re.search(rf"^##\s+{re.escape(name)}\s*$", body, re.MULTILINE)
    if not m:
        return ""
    rest = body[m.end():]
    nxt = re.search(r"^##\s+", rest, re.MULTILINE)
    return rest[:nxt.start()] if nxt else rest


def validate_answer(text: str, expected_sha: str) -> tuple[bool, str]:
    m = _FM_RE.match(text)
    if not m:
        return False, "no frontmatter block"
    fields: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    for req in ("seat", "objective_sha256", "facts_cited", "assumptions"):
        if not fields.get(req):
            return False, f"missing frontmatter field: {req}"
    if fields["objective_sha256"] != expected_sha:
        return False, "objective_sha256 mismatch"
    body = text[m.end():]
    headings = re.findall(r"^##\s+(.+?)\s*$", body, re.MULTILINE)
    idx = 0
    for h in headings:
        if idx < len(REQUIRED_SECTIONS) and h == REQUIRED_SECTIONS[idx]:
            idx += 1
    if idx != len(REQUIRED_SECTIONS):
        return False, f"sections missing/out of order: matched {idx}/{len(REQUIRED_SECTIONS)}"
    for name in ("Formation", "Tactics"):
        # header row + >=1 data row: the SKILL.md/BRIEF.md §4 skeleton carries no markdown
        # separator line, so "non-empty" means a data row beyond the header.
        rows = [ln for ln in _section_text(body, name).splitlines() if ln.strip().startswith("|")]
        if len(rows) < 2:
            return False, f"{name} table empty or missing a data row"
    wc = len(text.split())
    if wc > 1500:
        return False, f"word count {wc} > 1500"
    return True, "ok"


# --------------------------------------------------------------------- brief / check

def _ensure_outside_repo(kit: Path) -> None:
    resolved = kit.resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        print(f"refused: --kit {kit} is inside the repo; kit dirs must live outside it", file=sys.stderr)
        sys.exit(2)


def _default_kit(slug: str) -> Path:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Path.home() / f"BATTAGLIA-{today}" / f"DYNAMIC-WORKFLOW-{slug}"


def cmd_brief(args: argparse.Namespace) -> None:
    kit = Path(args.kit) if args.kit else _default_kit(args.slug)
    _ensure_outside_repo(kit)
    if args.colour not in ("BLUE", "ORANGE"):
        print("refused: --colour must be BLUE or ORANGE", file=sys.stderr)
        sys.exit(2)

    objective_raw = Path(args.objective_file).read_text()
    try:
        redacted = Redactor.load_default().redact(objective_raw)
    except RedactionError as e:
        print(f"PII gate: redactor raised — refusing fail-closed ({type(e).__name__})", file=sys.stderr)
        sys.exit(3)
    if redacted != objective_raw:
        n = _count_changed_spans(objective_raw, redacted)
        print(f"PII gate: objective changed by redaction ({n} span(s)) — refusing fail-closed. "
              f"No --skip-pii flag exists.", file=sys.stderr)
        sys.exit(3)

    template_path = Path(args.template) if args.template else DEFAULT_TEMPLATE
    if not template_path.exists():
        print(f"refused: template not found at {template_path} (pass --template)", file=sys.stderr)
        sys.exit(2)
    template = template_path.read_text()

    floor = args.floor or "unknown"
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    arsenal_block = _arsenal_liveness_block()
    master, sha = render_brief(template, objective_raw, args.colour, floor, date, arsenal_block)

    (kit / "r1").mkdir(parents=True, exist_ok=True)
    (kit / "r2").mkdir(parents=True, exist_ok=True)
    (kit / "BRIEF.md").write_text(master)
    (kit / "brief.sha").write_text(sha + "\n")
    inputs = {
        "slug": args.slug, "objective": objective_raw, "colour": args.colour,
        "floor": floor, "date": date, "template_path": str(template_path),
        "arsenal_block": arsenal_block,
    }
    (kit / "inputs.json").write_text(json.dumps(inputs, indent=1))
    print(f"BRIEF.md written to {kit} sha256={sha}")


def cmd_check(args: argparse.Namespace) -> None:
    kit = Path(args.kit)
    inputs_path = kit / "inputs.json"
    if not inputs_path.exists():
        print("refused: inputs.json missing — cannot recompute", file=sys.stderr)
        sys.exit(2)
    inputs = json.loads(inputs_path.read_text())
    template = Path(inputs["template_path"]).read_text()
    master = render_brief(template, inputs["objective"], inputs["colour"],
                           inputs["floor"], inputs["date"], inputs["arsenal_block"])[0]
    current = (kit / "BRIEF.md").read_text()
    problems = []
    if master != current:
        problems.append("BRIEF.md differs from template+inputs.json recompute (hand-edited? W78)")
    lok, lmsg = ledger_verify(kit)
    if not lok:
        problems.append(f"ledger tamper detected: {lmsg}")
    if problems:
        print("FAIL: " + "; ".join(problems))
        sys.exit(1)
    print("PASS")


def cmd_validate(args: argparse.Namespace) -> None:
    text = Path(args.file).read_text()
    ok, reason = validate_answer(text, args.sha)
    print(("PASS" if ok else "FAIL") + f": {reason}")
    sys.exit(0 if ok else 1)


# --------------------------------------------------------------------- selftest

def run_selftest() -> None:
    import shutil
    os.environ["DW_FAKE_SEATS"] = "1"
    failures: list[str] = []

    def check(label: str, cond: bool) -> None:
        print(("ok" if cond else "FAIL") + f" - {label}")
        if not cond:
            failures.append(label)

    work = Path(tempfile.mkdtemp(prefix="dw-selftest-"))
    try:
        # A. PII gate refuses a fixture with phone/email, count-only message, writes no kit.
        dirty_obj = work / "dirty.txt"
        dirty_obj.write_text(
            "Reach me at +6281234567890 or foo@example.com for the workflow review. " * 3
        )
        kit_a = work / "kit-a"
        ns = argparse.Namespace(slug="a", objective_file=str(dirty_obj), colour="BLUE",
                                 floor=None, template=str(_fixture_template()), kit=str(kit_a))
        try:
            cmd_brief(ns)
            check("PII gate refuses dirty objective", False)
        except SystemExit as e:
            check("PII gate refuses dirty objective", e.code == 3)
        check("PII gate wrote no kit dir", not kit_a.exists())

        # B. brief sha is stable across two identical runs.
        clean_obj = work / "clean.txt"
        clean_obj.write_text("Design the workflow formation for the dynamic-workflow launcher. " * 3)
        kit_b1, kit_b2 = work / "kit-b1", work / "kit-b2"
        for k in (kit_b1, kit_b2):
            cmd_brief(argparse.Namespace(slug="b", objective_file=str(clean_obj), colour="BLUE",
                                          floor=None, template=str(_fixture_template()), kit=str(k)))
        sha1 = (kit_b1 / "brief.sha").read_text()
        sha2 = (kit_b2 / "brief.sha").read_text()
        check("brief sha stable across identical runs", sha1 == sha2)

        # C. check passes on an untouched kit, fails on a hand-edited BRIEF.md (W78).
        kit_c = work / "kit-c"
        cmd_brief(argparse.Namespace(slug="c", objective_file=str(clean_obj), colour="BLUE",
                                      floor=None, template=str(_fixture_template()), kit=str(kit_c)))
        try:
            cmd_check(argparse.Namespace(kit=str(kit_c)))
            check("check passes on untouched kit", True)
        except SystemExit:
            check("check passes on untouched kit", False)
        brief_path = kit_c / "BRIEF.md"
        brief_path.write_text(brief_path.read_text() + "\nhand-added line\n")
        try:
            cmd_check(argparse.Namespace(kit=str(kit_c)))
            check("check fails on hand-edited BRIEF.md", False)
        except SystemExit as e:
            check("check fails on hand-edited BRIEF.md", e.code == 1)

        # D. ledger tamper is detected by check (ledger_append is the only writer here; PR1b's r1 is the other).
        kit_d = work / "kit-d"
        cmd_brief(argparse.Namespace(slug="d", objective_file=str(clean_obj), colour="BLUE",
                                      floor=None, template=str(_fixture_template()), kit=str(kit_d)))
        ledger_append(kit_d, "kimi-k3", "sent", "deadbeefcafef00d")
        lines = _ledger_path(kit_d).read_text().splitlines()
        _ledger_path(kit_d).write_text("\n".join(lines[:-1]) + "\n")  # drop last row, no re-hash
        try:
            cmd_check(argparse.Namespace(kit=str(kit_d)))
            check("check detects ledger tamper", False)
        except SystemExit as e:
            check("check detects ledger tamper", e.code == 1)
    finally:
        shutil.rmtree(work, ignore_errors=True)
        os.environ.pop("DW_FAKE_SEATS", None)

    if failures:
        print(f"SELFTEST FAILED ({len(failures)}): {failures}")
        sys.exit(1)
    print("SELFTEST OK")


_FIXTURE_TEMPLATE_TEXT = """```
objective_by_zero: |
  {{OBJECTIVE}}
colour: {{COLOUR}}
gear_floor: {{FLOOR}}
date: {{DATE}}
brief_sha256: {{SHA}}
you_are: {{SEAT}}
```

## Squad
{{ARSENAL_LIVENESS}}
"""


def _fixture_template() -> Path:
    p = Path(tempfile.gettempdir()) / "dw-selftest-template.md"
    p.write_text(_FIXTURE_TEMPLATE_TEXT)
    return p


# --------------------------------------------------------------------- CLI

def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--selftest", action="store_true")
    sub = parser.add_subparsers(dest="cmd")

    p_brief = sub.add_parser("brief")
    p_brief.add_argument("--slug", required=True)
    p_brief.add_argument("--objective-file", required=True, dest="objective_file")
    p_brief.add_argument("--colour", required=True)
    p_brief.add_argument("--floor")
    p_brief.add_argument("--template")
    p_brief.add_argument("--kit")
    p_brief.set_defaults(func=cmd_brief)

    p_check = sub.add_parser("check")
    p_check.add_argument("--kit", required=True)
    p_check.set_defaults(func=cmd_check)

    p_val = sub.add_parser("validate")
    p_val.add_argument("file")
    p_val.add_argument("--sha", required=True)
    p_val.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    if args.selftest:
        run_selftest()
        return
    if not getattr(args, "cmd", None):
        parser.print_help()
        sys.exit(2)
    args.func(args)


if __name__ == "__main__":
    main()
