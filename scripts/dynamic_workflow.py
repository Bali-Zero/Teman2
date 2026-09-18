#!/usr/bin/env python3
"""dynamic_workflow.py — the ONE launcher for /dynamic-workflow. Code, not prose; every
verdict judged by CONTENT, never by exit code alone (scar #2, "Esiste != Armato").

Subcommands (PR1a+PR1b+PR2a+PR2b — anonymise/reveal/capture-check land in PR2c):
    brief    --slug S --objective-file F --colour BLUE|ORANGE [--floor X] [--template T] [--kit K]
    check    --kit K            # recompute BRIEF.md from template+inputs.json, byte-diff (W78)
    r1       --kit K --seats a,b,c [--astra-fallback]   # one-shot per seat, ledger, relaunch<=1
    validate FILE --sha S       # frontmatter+skeleton+word-count gate
    r2       --kit K            # deterministic cross-family pairing, one shot, F/C+Test filter
    judge    --kit K            # mechanical C1/C5/C8 disqualification of every r1 answer
    jury     --kit K            # blind peer review of survivors, six axes, Borda + firsts

PII gate is fail-closed, no --skip-pii flag exists: the objective is redacted with the SAME
Redactor used before anything leaves this machine; any change, or any raise, refuses with a
SPAN COUNT only, never the text. DW_FAKE_SEATS=1 makes the arsenal-liveness probe AND every
r1/r2 seat launch offline and deterministic — what --selftest runs on, never a real invocation
and never a paid Anthropic endpoint.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Any
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
from _redact_pii import RedactionError, Redactor  # noqa: E402

REPO_ROOT = _SCRIPTS_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from scripts.lib.codex_seat import codex_seat_env  # noqa: E402

DEFAULT_TEMPLATE = REPO_ROOT / ".claude" / "skills" / "dynamic-workflow" / "brief.template.md"

PLACEHOLDERS = ("{{OBJECTIVE}}", "{{COLOUR}}", "{{FLOOR}}", "{{DATE}}", "{{ARSENAL_LIVENESS}}")
SEAT_LINE_RE = re.compile(r"^you_are:.*$", re.MULTILINE)
SHA_LINE_RE = re.compile(r"^brief_sha256:.*$", re.MULTILINE)

# ARSENAL_LIVENESS fallback when the probe fails/times out (F8): every seat "unknown", never
# omitted. Informational only — the r1 launch shapes below are the dispatch SSOT, not this list.
FALLBACK_SEATS = [
    "claude", "kimi", "agy", "codex", "ollama", "nlm", "qwen-cloud-code", "jules",
    "tp1-qwen3.8-max", "tp1-deepseek-v4-pro", "tp1-qwen3.7-plus", "tp1-glm-5.2",
]

REQUIRED_SECTIONS = [
    "Formation", "Tactics", "Termination", "Evidence between stages",
    "Never", "First move", "Cost",
]

TP1_IDS = {"qwen3.8-max", "deepseek-v4-pro", "qwen3.7-plus", "glm-5.2"}
SEAT_TIMEOUTS = {"kimi": 900, "tp1": 900, "agy": 1500, "astra": 1200}

# A coach's sealed answer shape, valid against REQUIRED_SECTIONS — DW_FAKE_SEATS=1's canned
# answer for both r1's fake-seat path and its own tests.
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
| gate | opus-5 | window | serial | 1 | sign | done |
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


def _ledger_rows(kit: Path) -> list[list[str]]:
    path = _ledger_path(kit)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4:
            rows.append(parts)
    return rows


def ledger_sent_count(kit: Path, seat: str) -> int:
    return sum(1 for r in _ledger_rows(kit) if r[1] == seat and r[2] == "sent")


def _ledger_has_seat(kit: Path, seat: str) -> bool:
    return any(r[1] == seat for r in _ledger_rows(kit))


def _parse_ledger_when(when: str) -> datetime:
    return datetime.strptime(when, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _earliest_sent_when(kit: Path) -> datetime | None:
    """Earliest `sent` row in the ledger, or None if no seat has been dispatched yet.
    `sent` rows are written right before a non-convener seat is launched (see
    `_run_one_seat`), so this is the moment the round actually started."""
    whens = [r[0] for r in _ledger_rows(kit) if r[2] == "sent"]
    return min((_parse_ledger_when(w) for w in whens), default=None)


def _ledger_when(kit: Path, seat: str) -> datetime | None:
    """Timestamp recorded on `seat`'s own ledger row (first one), or None if absent."""
    for r in _ledger_rows(kit):
        if r[1] == seat:
            return _parse_ledger_when(r[0])
    return None


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


# --------------------------------------------------------------------- r1

def _seat_kind(seat: str) -> str | None:
    if seat == "astra":
        return "astra"
    if seat in TP1_IDS:
        return "tp1"
    if seat.startswith("gemini"):
        return "agy"
    if seat.startswith("kimi"):
        return "kimi"
    return None


_PROMPT_PREFIX = ("You are a coach in a sealed brainstorm. Use ONLY the brief below and the "
                   "exact skeleton in §4. No tools, no browsing, no file reads. Output "
                   "only the answer.\n\n")


def _fake_seat_output(seat: str, sha: str, attempt: int) -> str:
    if seat.endswith("fakeinvalid"):
        return ""
    if seat.endswith("fakeflaky"):
        return "" if attempt < 2 else _CANNED_VALID.format(seat=seat, sha=sha)
    return _CANNED_VALID.format(seat=seat, sha=sha)


def _launch_seat(seat: str, prompt: str, timeout: int, kit: Path) -> str:
    kind = _seat_kind(seat)
    try:
        if kind == "kimi":
            cmd = ["kimi", "-p", prompt, "-m", "kimi-code/k3", "--output-format", "text"]
        elif kind == "tp1":
            cmd = ["qwen", "--model", seat, "--approval-mode", "plan", prompt]
        elif kind == "agy":
            cmd = ["agy", "-p", prompt, "--model", seat, "--output-format", "text"]
        elif kind == "astra":
            out_file = kit / "r1" / "astra.md"
            with tempfile.TemporaryDirectory() as tmp:
                cmd = ["codex", "exec", "-m", "gpt-6-astra", "-C", tmp, "-s", "read-only",
                       "--skip-git-repo-check", "-o", str(out_file), prompt]
                subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, timeout=timeout, env=codex_seat_env())
            return out_file.read_text() if out_file.exists() else ""
        else:
            return ""
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except Exception:
        return ""


def _run_one_seat(kit: Path, seat: str, brief_master: str, brief_sha: str, attempt: int) -> str:
    seat_copy = _set_seat_line(brief_master, seat)
    reconstructed = _set_sha_line(_set_seat_line(seat_copy, ""), "")
    if hashlib.sha256(reconstructed.encode()).hexdigest() != brief_sha:
        print(f"{seat}: per-seat brief hash mismatch — refusing to send", file=sys.stderr)
        return "refused-hash-mismatch"
    prompt = _PROMPT_PREFIX + seat_copy
    prompt_hash16 = hashlib.sha256(prompt.encode()).hexdigest()[:16]
    ledger_append(kit, seat, "sent", prompt_hash16)

    fake = os.environ.get("DW_FAKE_SEATS") == "1"
    if fake:
        output = _fake_seat_output(seat, brief_sha, attempt)
    else:
        kind = _seat_kind(seat) or "kimi"
        timeout = SEAT_TIMEOUTS.get(kind, 900)
        output = _launch_seat(seat, prompt, timeout, kit)

    out_path = kit / "r1" / f"{seat}.md"
    out_path.write_text(output or "")
    if not output or not output.strip():
        ledger_append(kit, seat, "dead", prompt_hash16)
        return "dead"
    ok = validate_answer(output, brief_sha)[0]
    ans_hash16 = hashlib.sha256(output.encode()).hexdigest()[:16]
    if ok:
        ledger_append(kit, seat, "answered", ans_hash16)
        return "answered"
    ledger_append(kit, seat, "dead", ans_hash16)
    return "dead"


def cmd_r1(args: argparse.Namespace) -> dict[str, str]:
    kit = Path(args.kit)
    brief_sha = (kit / "brief.sha").read_text().strip()
    fable = kit / "r1" / "fable-5-1.md"
    if not fable.exists():
        print("refused: r1/fable-5-1.md (convener) missing — it answers first", file=sys.stderr)
        sys.exit(2)
    ok, reason = validate_answer(fable.read_text(), brief_sha)
    if not ok:
        print(f"refused: convener answer invalid: {reason}", file=sys.stderr)
        sys.exit(2)
    # REWORK-BUILD fix (gate verdict on 8ffb9bc278/PR1b): "the convener answers first" was
    # recorded (mtime into the ledger) but never COMPARED against anything, so a convener
    # file rewritten after other seats had already been dispatched went undetected — theatre,
    # not enforcement. Both checks below run before any seat is launched, so a refusal here
    # writes no ledger row for anyone else.
    # Floored to whole seconds: the ledger's own "when" column carries second precision
    # (strftime "%Y-%m-%dT%H:%M:%SZ"), so comparing a sub-second mtime against a floored
    # ledger timestamp would spuriously call a same-second write "later" in either direction.
    fable_mtime = datetime.fromtimestamp(fable.stat().st_mtime, tz=timezone.utc).replace(microsecond=0)
    earliest_sent = _earliest_sent_when(kit)
    if earliest_sent is not None and fable_mtime > earliest_sent:
        print("refused: convener answer written after the first dispatch", file=sys.stderr)
        sys.exit(2)
    if _ledger_has_seat(kit, "fable-5-1"):
        recorded = _ledger_when(kit, "fable-5-1")
        if recorded is not None and fable_mtime > recorded:
            print("refused: convener answer rewritten after its own ledger row", file=sys.stderr)
            sys.exit(2)
    else:
        ledger_append(kit, "fable-5-1", "answered", brief_sha[:16],
                      when=fable_mtime.strftime("%Y-%m-%dT%H:%M:%SZ"))

    brief_master = (kit / "BRIEF.md").read_text()
    seats = [s.strip() for s in args.seats.split(",") if s.strip()]
    summary: dict[str, str] = {}
    for seat in seats:
        if seat in ("fable-5-1", "fable"):
            continue
        if seat == "astra" and not args.astra_fallback:
            ledger_append(kit, "astra", "awaiting-window", "-")
            summary[seat] = "awaiting-window"
            continue
        sent = ledger_sent_count(kit, seat)
        if sent >= 2:
            summary[seat] = "refused-max-relaunch"
            continue
        result = _run_one_seat(kit, seat, brief_master, brief_sha, sent + 1)
        if result == "dead" and sent + 1 == 1:
            result = _run_one_seat(kit, seat, brief_master, brief_sha, 2)
        summary[seat] = result
    for seat, status in summary.items():
        print(f"{seat}: {status}")
    return summary


# --------------------------------------------------------------------- r2

# Vendor family map for r2 pairing diversity. Deliberately NOT
# evidence_pack_lint._reviewer_family: that helper tokenizes a seat as
# "everything before its first '-'", which answers a DIFFERENT question
# (same-string reviewer/contributor collision) and would split every
# Anthropic model into its OWN family (fable/opus/sonnet/haiku) instead of
# treating them as ONE family — exactly the grouping r2 pairing needs so a
# seat is never paired with two answers from its own vendor. Forking that
# tokenizer here would silently answer the wrong question, so this is a
# fresh, explicit map instead (mandate's own family list).
FAMILY_MAP: dict[str, frozenset[str]] = {
    "anthropic": frozenset({"fable-5-1", "opus-5", "sonnet-5", "haiku-4-5"}),
    "openai": frozenset({"astra", "sol", "luna"}),
    "moonshot": frozenset({"kimi-k3", "kimi-code/kimi-for-coding-highspeed"}),
    "alibaba": frozenset({"qwen3.8-max", "qwen3.7-plus", "qwen3.6-flash"}),
    "deepseek": frozenset({"deepseek-v4-pro", "deepseek-v4-flash"}),
    "zhipu": frozenset({"glm-5.2"}),
    "google": frozenset({"gemini-3.1-pro-high", "gemini-3.8-flash"}),
}


# Short/alternate spellings the mandate itself uses for a seat that's already in FAMILY_MAP
# under a different spelling — e.g. MANDATE-builder.md §family list writes "kimi-2.7 =
# kimi-code/kimi-for-coding-highspeed", and its CLI section invokes the k3 seat as
# "kimi-code/k3" while FAMILY_MAP (and the ledger, historically) call it "kimi-k3". Resolved
# once here, at the single point `_seat_family` turns a seat id into a family — never by
# renaming ledger rows or r1/r2 output files, which keep whatever spelling was actually used
# to dispatch them.
_SEAT_ALIASES: dict[str, str] = {
    "kimi-2.7": "kimi-code/kimi-for-coding-highspeed",
    "kimi-code/k3": "kimi-k3",
}


def _canonical_seat(seat: str) -> str:
    return _SEAT_ALIASES.get(seat, seat)


def _seat_family(seat: str) -> str | None:
    canonical = _canonical_seat(seat)
    for family, seats in FAMILY_MAP.items():
        if canonical in seats:
            return family
    return None


def _require_known_family(seat: str) -> str:
    """Fail closed (REWORK-BUILD gate verdict on PR2a/4c062d2e09): a seat absent from
    FAMILY_MAP must never silently pair/review within its own (unrecognised) vendor. Every
    call site that needs a family — r2 pairing today, jury tomorrow — goes through this."""
    fam = _seat_family(seat)
    if fam is None:
        print(f"refused: seat {seat} not in FAMILY_MAP", file=sys.stderr)
        sys.exit(2)
    return fam


def _answered_r1_seats(kit: Path) -> list[str]:
    """Every seat with an `answered` ledger row, convener excluded — r2 pairs and reviews
    R1 ANSWERS, and the convener's is the brief for the round, not a peer to review."""
    return sorted({r[1] for r in _ledger_rows(kit) if r[2] == "answered" and r[1] != "fable-5-1"})


def compute_pairing(kit: Path, brief_sha: str) -> dict[str, list[str]]:
    """seat -> up to two R1 answers from two OTHER families. Deterministic: seeded on
    brief_sha, so recomputing against the same ledger state reproduces the identical
    pairing byte-for-byte (that reproducibility IS the refusal check in cmd_r2)."""
    answered = _answered_r1_seats(kit)
    for seat in answered:
        _require_known_family(seat)  # fail closed BEFORE pairing.md is ever written
    rng = random.Random(brief_sha)
    pairing: dict[str, list[str]] = {}
    for seat in answered:
        own = _seat_family(seat)
        candidates = [s for s in answered if s != seat and _seat_family(s) != own]
        rng.shuffle(candidates)
        picked: list[str] = []
        seen_families: set[str | None] = set()
        for c in candidates:
            fam = _seat_family(c)
            if fam in seen_families:
                continue
            picked.append(c)
            seen_families.add(fam)
            if len(picked) == 2:
                break
        pairing[seat] = picked
    return pairing


def _render_pairing_md(pairing: dict[str, list[str]]) -> str:
    lines = ["| seat | reviews |", "|---|---|"]
    for seat in sorted(pairing):
        targets = ", ".join(pairing[seat]) or "(none — insufficient family diversity)"
        lines.append(f"| {seat} | {targets} |")
    return "\n".join(lines) + "\n"


_R2_PROMPT_PREFIX = ("Object only where you can name an F/C and a test that would settle it. "
                      "No test, no objection.\n\n")
_FC_REF_RE = re.compile(r"\b[FC]\d+\b")


def _split_objections(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _objection_ok(paragraph: str) -> bool:
    return bool(_FC_REF_RE.search(paragraph)) and bool(re.search(r"^Test:", paragraph, re.MULTILINE))


def _fake_r2_output(seat: str) -> str:
    if seat.endswith("fakenoobject"):
        return "No objections. Everything checks out fine here."
    return ("F1 pairing may be unstable across brief revisions.\nTest: rerun r2 twice on the "
            "same kit, diff pairing.md byte-for-byte.\n\n"
            "This one is just a vague worry with no F/C ref and no Test line, drop it.")


def cmd_r2(args: argparse.Namespace) -> dict[str, dict[str, int]]:
    kit = Path(args.kit)
    brief_sha = (kit / "brief.sha").read_text().strip()
    pairing = compute_pairing(kit, brief_sha)
    rendered = _render_pairing_md(pairing)
    pairing_path = kit / "pairing.md"
    if pairing_path.exists():
        if pairing_path.read_text() != rendered:
            print("refused: pairing.md exists and differs from a fresh recompute", file=sys.stderr)
            sys.exit(2)
    else:
        pairing_path.write_text(rendered)

    (kit / "r2").mkdir(parents=True, exist_ok=True)
    fake = os.environ.get("DW_FAKE_SEATS") == "1"
    summary: dict[str, dict[str, int]] = {}
    for seat, targets in pairing.items():
        if fake:
            output = _fake_r2_output(seat)
        else:
            answers = "\n\n".join((kit / "r1" / f"{t}.md").read_text() for t in targets)
            prompt = _R2_PROMPT_PREFIX + answers
            kind = _seat_kind(seat) or "kimi"
            timeout = SEAT_TIMEOUTS.get(kind, 900)
            output = _launch_seat(seat, prompt, timeout, kit)
        paragraphs = _split_objections(output)
        kept = [p for p in paragraphs if _objection_ok(p)]
        rejected = [p for p in paragraphs if not _objection_ok(p)]
        (kit / "r2" / f"{seat}.md").write_text("\n\n".join(kept) + ("\n" if kept else ""))
        if rejected:
            (kit / "r2" / f"{seat}.rejected.md").write_text("\n\n".join(rejected) + "\n")
        ledger_append(kit, seat, f"r2-kept={len(kept)}-rejected={len(rejected)}", brief_sha[:16])
        summary[seat] = {"kept": len(kept), "rejected": len(rejected)}
    for seat, counts in summary.items():
        print(f"{seat}: kept={counts['kept']} rejected={counts['rejected']}")
    return summary


# --------------------------------------------------------------------- judge (mechanical only)

_C1_BANNED_RE = re.compile(
    r"ANTHROPIC_API_KEY|api_key\s*=|from\s+anthropic\s+import|\bbedrock\b|\bvertex\b|agy\s+.*claude-",
    re.IGNORECASE,
)


def _check_c1(full_text: str) -> tuple[bool, str]:
    m = _C1_BANNED_RE.search(full_text)
    return (m is None), ("clean" if m is None else f"banned entity matched: {m.group(0)!r}")


def _md_table_rows(body: str, section: str) -> list[list[str]]:
    lines = [ln for ln in _section_text(body, section).splitlines() if ln.strip().startswith("|")]
    return [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines[1:]]  # skip header


def _check_c5(body: str) -> tuple[bool, str]:
    for row in _md_table_rows(body, "Tactics"):
        if len(row) < 3:
            continue
        stage, seat, mode = row[0], row[1], row[2]
        if "gate" in stage.lower():
            if seat == "opus-5" and mode == "window":
                return True, "gate row ok"
            return False, f"gate row seat={seat!r} mode={mode!r}, want opus-5/window"
    return False, "no gate row in Tactics"


def _check_c8(body: str) -> tuple[bool, str]:
    for role, seat, *_ in _md_table_rows(body, "Formation"):
        if seat in ("fable-5-1", "astra") and role not in ("coach", "imperator"):
            return False, f"seat {seat} carries role {role!r}, must be coach/imperator"
    for row in _md_table_rows(body, "Tactics"):
        if len(row) < 5 or not row[4].isdigit():
            return False, f"Tactics round cap missing/non-integer: {row}"
    for line in _section_text(body, "Never").splitlines():
        line = line.strip()
        if line.startswith("-") and not _FC_REF_RE.search(line):
            return False, f"Never bullet cites no F/C: {line!r}"
    wc = len(body.split())
    if wc > 1500:
        return False, f"word count {wc} > 1500"
    return True, "ok"


def cmd_judge(args: argparse.Namespace) -> dict[str, dict[str, object]]:
    kit = Path(args.kit)
    verdicts: dict[str, dict[str, object]] = {}
    rows = ["| seat | C1 | C5 | C8 | disqualified |", "|---|---|---|---|---|"]
    for seat in _answered_r1_seats(kit):
        text = (kit / "r1" / f"{seat}.md").read_text()
        m = _FM_RE.match(text)
        body = text[m.end():] if m else text
        c1_ok, c1_msg = _check_c1(text)
        c5_ok, c5_msg = _check_c5(body)
        c8_ok, c8_msg = _check_c8(body)
        disq = not (c1_ok and c5_ok and c8_ok)
        verdicts[seat] = {"c1": c1_ok, "c5": c5_ok, "c8": c8_ok, "disqualified": disq}
        rows.append(f"| {seat} | {'pass' if c1_ok else 'FAIL: ' + c1_msg} "
                     f"| {'pass' if c5_ok else 'FAIL: ' + c5_msg} "
                     f"| {'pass' if c8_ok else 'FAIL: ' + c8_msg} | {'yes' if disq else 'no'} |")
    (kit / "judge.md").write_text("\n".join(rows) + "\n")
    for seat, v in verdicts.items():
        print(f"{seat}: disqualified={v['disqualified']}")
    return verdicts


# --------------------------------------------------------------------- jury (blind peer review;
# anonymise/reveal/capture-check land in PR2c)

JURY_AXES = ("termination", "cost", "robustness", "evidence", "implementability", "fit")
_JURY_LETTERS = "ABCDEF"
_JURY_PROMPT_PREFIX = (
    "You are a juror in a sealed brainstorm. Score each OTHER formation below on six axes, "
    "integer 1-5 each. Output ONLY a markdown table, one row per formation letter, columns "
    "exactly: formation, " + ", ".join(JURY_AXES) + ". No prose outside the table.\n\n")


def _strip_identity(text: str) -> str:
    """The two frontmatter lines that would deanonymise a formation to its reviewer — shared
    by cmd_jury's blinding and cmd_anonymise's Z-BLIND artifact (PR2c) so the stripped fields
    never drift between the two (mandate: 'seat: and objective_sha256 lines stripped,
    nothing else')."""
    text = re.sub(r"^seat:.*$", "seat: [REDACTED]", text, count=1, flags=re.MULTILINE)
    text = re.sub(r"^objective_sha256:.*$", "objective_sha256: [REDACTED]", text, count=1,
                   flags=re.MULTILINE)
    return text


def _jury_survivors(kit: Path) -> list[str]:
    """Seats judge.md marked NOT disqualified, in judge.md's own row order. judge.md — not a
    recompute — is the SSOT for who survives (scar #2, "Esiste != Armato": never re-derive a
    verdict already written to disk)."""
    judge_path = kit / "judge.md"
    if not judge_path.exists():
        print("refused: judge.md does not exist — run judge before jury", file=sys.stderr)
        sys.exit(2)
    survivors = []
    for line in judge_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("| seat") or set(stripped) <= {"|", "-"}:
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 5:
            continue
        seat, disqualified = cells[0], cells[-1]
        if disqualified == "no":
            survivors.append(seat)
    return survivors


def _jury_mapping(kit: Path, survivors: list[str]) -> dict[str, str]:
    """One global letter->seat map for the whole round (max 6, A-F), persisted to
    jury/mapping.json chmod 600 so cmd_anonymise's Z-BLIND artifact (PR2c) reuses the SAME
    letters jury/tabulation.md already named, instead of assigning a second, inconsistent
    mapping later. Refuses like pairing.md/mapping.json do elsewhere: exists-and-differs is
    a refusal, not a silent overwrite."""
    if len(survivors) > len(_JURY_LETTERS):
        print(f"refused: {len(survivors)} surviving formations, jury supports at most "
              f"{len(_JURY_LETTERS)} (A-F)", file=sys.stderr)
        sys.exit(2)
    mapping = dict(zip(_JURY_LETTERS, survivors))
    mapping_path = kit / "jury" / "mapping.json"
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(mapping, indent=2, sort_keys=True) + "\n"
    if mapping_path.exists():
        if mapping_path.read_text() != rendered:
            print("refused: jury/mapping.json exists and differs from a fresh recompute",
                  file=sys.stderr)
            sys.exit(2)
    else:
        mapping_path.write_text(rendered)
        os.chmod(mapping_path, 0o600)
    return mapping


def _fake_jury_output(juror: str, letters: list[str]) -> str:
    if not letters:
        return ""
    if juror.endswith("fakejurydead"):
        return "not a table"
    lines = ["| formation | " + " | ".join(JURY_AXES) + " |",
              "|---|" + "---|" * len(JURY_AXES)]
    for i, letter in enumerate(letters):
        base = 3 + (i % 2)
        lines.append(f"| {letter} | " + " | ".join(str(base) for _ in JURY_AXES) + " |")
    return "\n".join(lines) + "\n"


def _parse_jury_ballot(text: str, valid_letters: set[str]) -> dict[str, list[int]] | None:
    """A parseable table or it is dead for the jury (mandate, verbatim): every letter this
    juror was shown must appear EXACTLY once with six 1-5 integer scores, or the whole
    ballot is dead — a partial table is not a partial credit."""
    rows: dict[str, list[int]] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != 1 + len(JURY_AXES):
            continue
        letter = cells[0].upper()
        if letter not in valid_letters or letter in rows:
            continue
        scores = []
        for c in cells[1:]:
            if not re.fullmatch(r"[1-5]", c):
                scores = None
                break
            scores.append(int(c))
        if scores is not None:
            rows[letter] = scores
    if set(rows) != valid_letters:
        return None
    return rows


def _tabulate_jury(mapping: dict[str, str],
                    ballots: dict[str, dict[str, list[int]] | None]) -> dict[str, Any]:
    """Borda + firsts, tabulated BY THE SCRIPT (mandate, verbatim) — never by a synthesizer
    LLM. Borda: per live ballot, rank formations by summed axis score (ties broken by letter
    for determinism), award (n-1-rank) points. Firsts: count of #1 rankings. Disagreement: any
    formation where the SAME axis spans >=3 points (of a 1-5 scale) across live ballots."""
    letters = sorted(mapping)
    borda: dict[str, int] = {ltr: 0 for ltr in letters}
    firsts: dict[str, int] = {ltr: 0 for ltr in letters}
    axis_scores: dict[str, dict[str, list[int]]] = {ltr: {a: [] for a in JURY_AXES} for ltr in letters}
    live = 0
    for ballot in ballots.values():
        if ballot is None:
            continue
        live += 1
        totals = {ltr: sum(scores) for ltr, scores in ballot.items()}
        ranked = sorted(totals, key=lambda ltr: (-totals[ltr], ltr))
        n = len(ranked)
        for idx, ltr in enumerate(ranked):
            borda[ltr] += (n - 1 - idx)
        if ranked:
            firsts[ranked[0]] += 1
        for ltr, scores in ballot.items():
            for axis, score in zip(JURY_AXES, scores):
                axis_scores[ltr][axis].append(score)

    disagreements = []
    for ltr in letters:
        for axis in JURY_AXES:
            scores = axis_scores[ltr][axis]
            if len(scores) >= 2 and (max(scores) - min(scores)) >= 3:
                disagreements.append(
                    f"{ltr} ({mapping[ltr]}): {axis} spread {min(scores)}-{max(scores)}")

    dead = sorted(j for j, b in ballots.items() if b is None)
    rows = ["| formation | seat | borda | firsts |", "|---|---|---|---|"]
    for ltr in sorted(letters, key=lambda ltr: (-borda[ltr], ltr)):
        rows.append(f"| {ltr} | {mapping[ltr]} | {borda[ltr]} | {firsts[ltr]} |")
    lines = [f"# Jury tabulation — {live} live ballot(s), {len(dead)} dead: "
             f"{', '.join(dead) or 'none'}", ""]
    lines += rows
    lines.append("")
    lines.append("## Disagreements" if disagreements else "## Disagreements: none")
    lines += [f"- {d}" for d in disagreements]
    return {"borda": borda, "firsts": firsts, "dead": dead, "disagreements": disagreements,
            "rendered": "\n".join(lines) + "\n"}


def cmd_jury(args: argparse.Namespace) -> dict[str, Any]:
    kit = Path(args.kit)
    survivors = _jury_survivors(kit)
    mapping = _jury_mapping(kit, survivors)
    (kit / "jury").mkdir(parents=True, exist_ok=True)

    fake = os.environ.get("DW_FAKE_SEATS") == "1"
    ballots: dict[str, dict[str, list[int]] | None] = {}
    for juror in survivors:
        others = sorted(ltr for ltr, seat in mapping.items() if seat != juror)
        if not others:
            continue  # no peers to review — never sent, never scored, never dead
        if fake:
            output = _fake_jury_output(juror, others)
        else:
            bodies = "\n\n".join(
                f"### Formation {ltr}\n" + _strip_identity((kit / "r1" / f"{mapping[ltr]}.md").read_text())
                for ltr in others)
            prompt = _JURY_PROMPT_PREFIX + bodies
            kind = _seat_kind(juror) or "kimi"
            timeout = SEAT_TIMEOUTS.get(kind, 900)
            output = _launch_seat(juror, prompt, timeout, kit)
        (kit / "jury" / f"{juror}.md").write_text(output or "")
        ballot = _parse_jury_ballot(output or "", set(others))
        ballots[juror] = ballot
        ledger_append(kit, juror, "jury-dead" if ballot is None else "jury-scored", "0" * 16)

    tabulation = _tabulate_jury(mapping, ballots)
    (kit / "jury" / "tabulation.md").write_text(tabulation["rendered"])
    for juror, ballot in ballots.items():
        print(f"{juror}: {'dead' if ballot is None else 'scored'}")
    return tabulation


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

        # D. ledger tamper is detected by check.
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

        # E. r1 refuses without the convener file.
        kit_e = work / "kit-e"
        cmd_brief(argparse.Namespace(slug="e", objective_file=str(clean_obj), colour="BLUE",
                                      floor=None, template=str(_fixture_template()), kit=str(kit_e)))
        try:
            cmd_r1(argparse.Namespace(kit=str(kit_e), seats="kimi-k3", astra_fallback=False))
            check("r1 refuses without convener file", False)
        except SystemExit as e:
            check("r1 refuses without convener file", e.code == 2)
        check("r1 wrote no seat files without convener", not (kit_e / "r1" / "kimi-k3.md").exists())

        # F. invalid answer -> dead -> one relaunch -> refusal on third sent row.
        kit_f = work / "kit-f"
        cmd_brief(argparse.Namespace(slug="f", objective_file=str(clean_obj), colour="BLUE",
                                      floor=None, template=str(_fixture_template()), kit=str(kit_f)))
        sha_f = (kit_f / "brief.sha").read_text().strip()
        (kit_f / "r1" / "fable-5-1.md").write_text(_CANNED_VALID.format(seat="fable-5-1", sha=sha_f))
        summary_f1 = cmd_r1(argparse.Namespace(kit=str(kit_f), seats="x-fakeinvalid", astra_fallback=False))
        check("first r1 call: seat dead after auto-relaunch", summary_f1["x-fakeinvalid"] == "dead")
        check("two sent rows recorded after one r1 call", ledger_sent_count(kit_f, "x-fakeinvalid") == 2)
        summary_f2 = cmd_r1(argparse.Namespace(kit=str(kit_f), seats="x-fakeinvalid", astra_fallback=False))
        check("third attempt refused", summary_f2["x-fakeinvalid"] == "refused-max-relaunch")
        check("refusal added no third sent row", ledger_sent_count(kit_f, "x-fakeinvalid") == 2)

        # G. r2: deterministic pairing, filter drops weak objections, refuses a mutated recompute.
        kit_g = work / "kit-g"
        cmd_brief(argparse.Namespace(slug="g", objective_file=str(clean_obj), colour="BLUE",
                                      floor=None, template=str(_fixture_template()), kit=str(kit_g)))
        sha_g = (kit_g / "brief.sha").read_text().strip()
        (kit_g / "r1" / "fable-5-1.md").write_text(_CANNED_VALID.format(seat="fable-5-1", sha=sha_g))
        cmd_r1(argparse.Namespace(kit=str(kit_g), seats="kimi-k3,qwen3.8-max,gemini-3.1-pro-high",
                                   astra_fallback=False))
        summary_g1 = cmd_r2(argparse.Namespace(kit=str(kit_g)))
        check("r2 wrote pairing.md", (kit_g / "pairing.md").exists())
        pairing_first = (kit_g / "pairing.md").read_text()
        summary_g2 = cmd_r2(argparse.Namespace(kit=str(kit_g)))
        check("r2 recompute matches, no refusal", summary_g2 == summary_g1)
        check("r2 filter kept exactly one objection per seat",
              all(v["kept"] == 1 for v in summary_g1.values()))
        check("r2 filter rejected exactly one objection per seat",
              all(v["rejected"] == 1 for v in summary_g1.values()))
        (kit_g / "pairing.md").write_text(pairing_first + "| tampered | row |\n")
        try:
            cmd_r2(argparse.Namespace(kit=str(kit_g)))
            check("r2 refuses on a mutated pairing.md", False)
        except SystemExit as e:
            check("r2 refuses on a mutated pairing.md", e.code == 2)

        # H. judge: mechanical C1/C5/C8 disqualification — clean answer passes, C1-dirty fails.
        kit_h = work / "kit-h"
        cmd_brief(argparse.Namespace(slug="h", objective_file=str(clean_obj), colour="BLUE",
                                      floor=None, template=str(_fixture_template()), kit=str(kit_h)))
        sha_h = (kit_h / "brief.sha").read_text().strip()
        (kit_h / "r1" / "fable-5-1.md").write_text(_CANNED_VALID.format(seat="fable-5-1", sha=sha_h))
        ledger_append(kit_h, "kimi-k3", "sent", "aaaa")
        (kit_h / "r1" / "kimi-k3.md").write_text(_CANNED_VALID.format(seat="kimi-k3", sha=sha_h))
        ledger_append(kit_h, "kimi-k3", "answered", "aaaa")
        dirty_answer = _CANNED_VALID.format(seat="qwen3.8-max", sha=sha_h).replace(
            "1 call per seat", "1 call per seat, leaked key=ANTHROPIC_API_KEY")
        ledger_append(kit_h, "qwen3.8-max", "sent", "bbbb")
        (kit_h / "r1" / "qwen3.8-max.md").write_text(dirty_answer)
        ledger_append(kit_h, "qwen3.8-max", "answered", "bbbb")
        verdicts_h = cmd_judge(argparse.Namespace(kit=str(kit_h)))
        check("judge.md written", (kit_h / "judge.md").exists())
        check("judge passes a clean canned answer", verdicts_h["kimi-k3"]["disqualified"] is False)
        check("judge disqualifies a C1-dirty answer", verdicts_h["qwen3.8-max"]["disqualified"] is True)

        # I. r1 refuses when the convener file is rewritten after the round's first dispatch
        # (REWORK-BUILD verdict on 8ffb9bc278/PR1b: mtime was recorded, never compared).
        kit_i = work / "kit-i"
        cmd_brief(argparse.Namespace(slug="i", objective_file=str(clean_obj), colour="BLUE",
                                      floor=None, template=str(_fixture_template()), kit=str(kit_i)))
        sha_i = (kit_i / "brief.sha").read_text().strip()
        (kit_i / "r1" / "fable-5-1.md").write_text(_CANNED_VALID.format(seat="fable-5-1", sha=sha_i))
        cmd_r1(argparse.Namespace(kit=str(kit_i), seats="kimi-k3", astra_fallback=False))
        check("innocence: first r1 call proceeds (mtime precedes any dispatch)",
              (kit_i / "r1" / "kimi-k3.md").exists())
        time.sleep(1.1)  # cross a whole-second boundary — ledger "when" has second precision
        (kit_i / "r1" / "fable-5-1.md").write_text(_CANNED_VALID.format(seat="fable-5-1", sha=sha_i))
        try:
            cmd_r1(argparse.Namespace(kit=str(kit_i), seats="qwen3.8-max", astra_fallback=False))
            check("guilt: r1 refuses convener rewritten after the first dispatch", False)
        except SystemExit as e:
            check("guilt: r1 refuses convener rewritten after the first dispatch", e.code == 2)
        check("refusal launched no new seat", not (kit_i / "r1" / "qwen3.8-max.md").exists())
        check("refusal wrote no new ledger row for the new seat",
              not _ledger_has_seat(kit_i, "qwen3.8-max"))

        # J. r2 fails closed on a seat absent from FAMILY_MAP, and an alias resolves correctly
        # (REWORK-BUILD verdict on 4c062d2e09/PR2a: unknown seat paired within its own vendor).
        kit_j = work / "kit-j"
        cmd_brief(argparse.Namespace(slug="j", objective_file=str(clean_obj), colour="BLUE",
                                      floor=None, template=str(_fixture_template()), kit=str(kit_j)))
        sha_j = (kit_j / "brief.sha").read_text().strip()
        (kit_j / "r1" / "fable-5-1.md").write_text(_CANNED_VALID.format(seat="fable-5-1", sha=sha_j))
        cmd_r1(argparse.Namespace(kit=str(kit_j), seats="kimi-k3,totally-unknown-seat",
                                   astra_fallback=False))
        try:
            cmd_r2(argparse.Namespace(kit=str(kit_j)))
            check("guilt: r2 refuses a seat absent from FAMILY_MAP", False)
        except SystemExit as e:
            check("guilt: r2 refuses a seat absent from FAMILY_MAP", e.code == 2)
        check("refusal wrote no pairing.md", not (kit_j / "pairing.md").exists())
        check("kimi-2.7 alias resolves to the moonshot family",
              _seat_family("kimi-2.7") == "moonshot")
        check("kimi-code/k3 alias resolves to the moonshot family",
              _seat_family("kimi-code/k3") == "moonshot")

        # K. jury: blind peer review, Borda + firsts, a malformed ballot is dead not partial.
        kit_k = work / "kit-k"
        cmd_brief(argparse.Namespace(slug="k", objective_file=str(clean_obj), colour="BLUE",
                                      floor=None, template=str(_fixture_template()), kit=str(kit_k)))
        sha_k = (kit_k / "brief.sha").read_text().strip()
        (kit_k / "r1" / "fable-5-1.md").write_text(_CANNED_VALID.format(seat="fable-5-1", sha=sha_k))
        cmd_r1(argparse.Namespace(
            kit=str(kit_k), seats="kimi-k3,qwen3.8-max,gemini-3.1-pro-high-fakejurydead",
            astra_fallback=False))
        cmd_judge(argparse.Namespace(kit=str(kit_k)))
        tab_k = cmd_jury(argparse.Namespace(kit=str(kit_k)))
        mapping_path = kit_k / "jury" / "mapping.json"
        check("jury/mapping.json written", mapping_path.exists())
        check("jury/mapping.json is chmod 600", oct(mapping_path.stat().st_mode)[-3:] == "600")
        check("jury/tabulation.md written", (kit_k / "jury" / "tabulation.md").exists())
        check("one dead ballot named (the malformed-table seat)",
              tab_k["dead"] == ["gemini-3.1-pro-high-fakejurydead"])
        check("borda tabulated for every surviving formation letter",
              set(tab_k["borda"]) == {"A", "B", "C"})
        check("re-running jury on an unchanged mapping does not refuse",
              cmd_jury(argparse.Namespace(kit=str(kit_k))) is not None)
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

    p_r1 = sub.add_parser("r1")
    p_r1.add_argument("--kit", required=True)
    p_r1.add_argument("--seats", required=True)
    p_r1.add_argument("--astra-fallback", action="store_true", dest="astra_fallback")
    p_r1.set_defaults(func=cmd_r1)

    p_val = sub.add_parser("validate")
    p_val.add_argument("file")
    p_val.add_argument("--sha", required=True)
    p_val.set_defaults(func=cmd_validate)

    p_r2 = sub.add_parser("r2")
    p_r2.add_argument("--kit", required=True)
    p_r2.set_defaults(func=cmd_r2)

    p_judge = sub.add_parser("judge")
    p_judge.add_argument("--kit", required=True)
    p_judge.set_defaults(func=cmd_judge)

    p_jury = sub.add_parser("jury")
    p_jury.add_argument("--kit", required=True)
    p_jury.set_defaults(func=cmd_jury)

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
