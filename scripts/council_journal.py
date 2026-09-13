#!/usr/bin/env python3
"""council_journal.py — record a council seat AT DISPATCH, because it cannot be recorded
afterwards without inventing a timestamp.

WHY THIS EXISTS (measured 2026-09-02 while shipping PR #5519). R9
(`scripts/evidence_pack_lint.py::check_council_run_gear3`) counts a journal line only when it
carries `role == "review"` AND `ok is True` AND a non-empty `ts` —
`_read_council_journal_seats` `continue`s on anything else, its own comment saying "the declared
minimal schema requires 'ts' too". A qualifying line is therefore UNWRITEABLE without a
timestamp, and after the fact the only timestamp available is one you make up.

That is not hypothetical. On #5519 the two seats that really did review the diff appeared in
`lanes[]` and in `dissent[]` with their actual objections, but in no journal — and the only
dispatch line on disk named a DIFFERENT roster, so reusing its timestamp would have asserted
those seats took part in a dispatch that the line itself says they did not. There was no honest
journal left to write, so that pack declared `seat_override` instead. An override is legitimate
once; it should not become how this repo passes R9.

Twenty-five `council-journal.jsonl` files already exist under `evidence/2026-08/`, all
hand-authored, with no tool and no documented procedure anywhere in `docs/`, `.claude/skills/`
or `research/`. So the gap this fills is not "nobody journals" — it is that journaling correctly
depends entirely on remembering, at the right moment, a schema written down only inside the
linter that reads it. This makes the honest path the easy one.

WHAT IT DELIBERATELY WILL NOT DO:

  * It will not backdate. `ts` is always `datetime.now(timezone.utc)` at the moment of the call.
    There is no `--ts` flag, on purpose: a flag that accepts a timestamp is a flag that accepts
    an invented one, and inventing it is the exact failure this file exists to prevent.
  * It will not write `ok: true` without a `--note`. A qualifying line CLAIMS a seat returned a
    judgement; a claim with nothing behind it is the "receipt without a command" shape the
    evidence-pack contract already rejects.
  * It will not reimplement R9. `check` imports the real `check_council_run_gear3` and reports
    what THAT says, inheriting its path confinement and seat validation. A second copy of a rule
    is a second rule, and the two drift.
  * It will not write outside the pack directory, nor onto `pack.yml` / `brief.yml` — mirroring
    the confinement `scripts/ci/stage_council_journal.py` enforces on the CI side.

A seat that times out or refuses is recorded with `--outcome non-judgement`. That line does NOT
count toward quorum (R9 requires `ok is True`) and is not meant to — a silence is not an
agreement. Recording it still matters: it is the difference between "this seat was never asked"
and "this seat was asked and could not answer", which is precisely what a later reader needs in
order to judge whether a `seat_override` is honest.

Usage:
    python3 scripts/council_journal.py append \\
        --pack-dir evidence/2026-09/<task-slug>-<8hex> \\
        --seat codex-gpt-5.6-sol --outcome ok \\
        --note "one round on the finished diff, --sandbox read-only, effort=high"

    python3 scripts/council_journal.py check --pack-dir evidence/2026-09/<task-slug>-<8hex>

Exit codes:
    append: 0 = written; 2 = refused (unknown seat is a NOTE not a refusal; refusals are a
            missing note on `ok`, a path escape, a reserved name, or a missing pack dir)
    check:  0 = R9 satisfied on and after its enforcement date (or pack is not Gear-3);
            1 = R9 would fail on/after that date; 2 = could not evaluate
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import hashlib
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

#: The filename every one of the 25 existing journals uses. Matching it is not cosmetic: a pack
#: declares `council_run: council-journal.jsonl` as a bare relative name, and a different
#: filename here would silently produce a journal R9 never looks at.
DEFAULT_JOURNAL_NAME = "council-journal.jsonl"

#: Names harness-floor.yml stages the pack and brief under. A journal must never land on one.
RESERVED_NAMES = frozenset({"pack.yml", "brief.yml"})

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_lint_module() -> Any:
    """Import evidence_pack_lint without requiring it on sys.path.

    Deliberately imports the REAL module rather than copying its constants: COUNCIL_REVIEW_SEATS
    is a moving list — `kimi-code/k3` was quota-dead for a whole week on 2026-09-01 — and a local
    copy would keep validating against a roster that no longer matches the rule.
    """
    path = _REPO_ROOT / "scripts" / "evidence_pack_lint.py"
    spec = importlib.util.spec_from_file_location("_council_journal_lint", path)
    if spec is None or spec.loader is None:  # pragma: no cover - import plumbing
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_journal(pack_dir: Path, name: str) -> tuple[Path | None, str | None]:
    """Resolve `name` inside `pack_dir`, refusing escapes and reserved names.

    Mirrors R9's own confinement — it resolves `council_run:` against the pack's OWN directory
    and rejects anything leaving it — so a journal written elsewhere would be invisible to the
    very rule meant to read it.
    """
    if not name or not name.strip():
        return None, "journal name is empty"
    if Path(name).is_absolute() or name.startswith("//"):
        return None, f"journal name {name!r} must be relative to the pack dir, not absolute"
    if Path(name).name in RESERVED_NAMES:
        return None, f"journal name {name!r} would collide with a staged {Path(name).name}"
    pack_resolved = pack_dir.resolve()
    journal = (pack_resolved / name).resolve()
    if pack_resolved not in (journal, *journal.parents):
        return None, f"journal name {name!r} escapes the pack directory"
    return journal, None


def cmd_append(args: argparse.Namespace) -> int:
    pack_dir = Path(args.pack_dir)
    if not pack_dir.is_dir():
        print(f"council_journal: {pack_dir} is not a directory", file=sys.stderr)
        return 2

    seat = args.seat.strip()
    if not seat:
        print("council_journal: --seat is empty", file=sys.stderr)
        return 2

    ok = args.outcome == "ok"
    if ok and not (args.note and args.note.strip()):
        print(
            "council_journal: --outcome ok requires --note. A qualifying line asserts this seat "
            "returned a judgement; record what it said, or use --outcome non-judgement.",
            file=sys.stderr,
        )
        return 2

    journal, err = _resolve_journal(pack_dir, args.journal)
    if journal is None:
        print(f"council_journal: {err}", file=sys.stderr)
        return 2

    # Field order matches every existing journal in the tree: seat, role, ok, ts, then extras.
    entry: dict[str, Any] = {
        "seat": seat,
        "role": "review",
        "ok": ok,
        # Never a parameter — see the module docstring.
        "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if args.note and args.note.strip():
        entry["note"] = args.note.strip()

    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"council_journal: appended seat={seat} ok={ok} ts={entry['ts']} -> {journal}")

    if ok:
        qualifying = set(getattr(_load_lint_module(), "COUNCIL_REVIEW_SEATS", ()))
        if seat not in qualifying:
            # A NOTE, not a refusal: a council may legitimately include seats R9 does not count
            # (agy/Gemini gave the single most plan-changing objection on #5519). Recording them
            # is right; letting the author believe they counted toward quorum is not.
            print(
                f"council_journal: NOTE — {seat!r} is not one of R9's qualifying seats "
                f"({', '.join(sorted(qualifying))}), so this line is recorded but does NOT "
                "count toward quorum.",
            )

    rel = journal.relative_to(pack_dir.resolve())
    print(f"council_journal: the pack must declare  council_run: {rel}")
    return 0


def _resolve_gear(pack: dict[str, Any], pack_dir: Path) -> tuple[int | None, str]:
    """Find the pack's gear, looking in the SIBLING BRIEF when the pack does not carry it.

    Measured 2026-09-02 across the 40 real evidence packs in this tree: **zero** declare `gear`
    in `pack.yml`; 37 declare it only in the sibling `brief.yml`, and 3 in neither. A checker
    that reads `pack.yml` alone therefore answers "not Gear-3, nothing to check" on every real
    pack in the repo — green on everything, which is worse than no checker at all. (`pack.yml`'s
    `brief_ref:` is the CI-staging literal `evidence/brief.yml`, not a path to the real sibling,
    so it cannot be followed from here; the sibling is found by name.)
    """
    if isinstance(pack.get("gear"), int):
        return pack["gear"], "pack.yml"

    import yaml

    brief = pack_dir / "brief.yml"
    if brief.is_file():
        try:
            data = yaml.safe_load(brief.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            return None, "brief.yml (unparseable)"
        if isinstance(data, dict) and isinstance(data.get("gear"), int):
            return data["gear"], "brief.yml"
    return None, "nowhere"


def cmd_check(args: argparse.Namespace) -> int:
    import yaml  # local import so `append` still works where PyYAML is absent

    pack_dir = Path(args.pack_dir)
    pack_path = pack_dir / "pack.yml"
    if not pack_path.is_file():
        print(f"council_journal: no pack.yml under {pack_dir}", file=sys.stderr)
        return 2
    try:
        pack = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"council_journal: {pack_path} does not parse: {exc}", file=sys.stderr)
        return 2
    if not isinstance(pack, dict):
        print(f"council_journal: {pack_path} did not parse to a mapping", file=sys.stderr)
        return 2

    gear, gear_src = _resolve_gear(pack, pack_dir)
    if gear is None:
        # NEVER a silent pass. "I could not find the gear" and "this is not Gear-3" are different
        # answers, and collapsing them is how a checker reports green on everything.
        print(
            f"council_journal: cannot determine gear — absent from {pack_dir/'pack.yml'} and from "
            f"the sibling brief.yml. Refusing to report a verdict rather than assume not-Gear-3.",
            file=sys.stderr,
        )
        return 2
    if gear != 3:
        print(f"council_journal: gear={gear!r} (from {gear_src}) — R9 is Gear-3 only, nothing to check")
        return 0

    lint = _load_lint_module()
    flip: datetime.date = getattr(lint, "R9_R11_ENFORCEMENT_DATE")
    before = flip - datetime.timedelta(days=1)

    # Asked on BOTH sides of its own enforcement date. Reporting only today's verdict is exactly
    # how a pack sails into a dated cliff: before the flip R9 is a NOTICE, after it the identical
    # finding fails a required check.
    results: dict[str, tuple[list[str], str | None]] = {}
    for label, day in (("before", before), ("on/after", flip)):
        violations, notice = lint.check_council_gear3(
            pack, pack_dir=pack_dir, gear=3, today=day
        )
        results[label] = (list(violations or []), notice)

    if pack.get("seat_override"):
        print("council_journal: pack declares seat_override — R9 is reported, never failed.")
    print(f"council_journal: council_run = {pack.get('council_run')!r}")
    for label, day in (("before", before), ("on/after", flip)):
        violations, notice = results[label]
        if violations:
            state = f"VIOLATION — {violations[0]}"
        elif notice:
            state = f"notice — {notice}"
        else:
            state = "OK"
        print(f"  {label} the flip ({day.isoformat()}): {state}")

    return 1 if results["on/after"][0] else 0


#: SAETTA review policy v2 routes (RULED 2026-09-13). Only first-party CLIs on their existing
#: OAuth/subscription profiles; no raw model HTTP. `{prompt}` is replaced by the packet; a route
#: with `stdin` feeds the packet on stdin instead. The review packet is code-only.
AGY = "/Users/nuzantara/.local/bin/agy"
KIMI = "/Users/nuzantara/.kimi-code/bin/kimi"
SEAT_ROUTES: dict[str, dict[str, Any]] = {
    "agy-gemini-3.1-pro-high": {
        "host": "pro-local", "account_ref": "agy-oauth-default",
        "argv": [AGY, "--model", "gemini-3.1-pro-high", "--effort", "high", "--mode", "plan",
                 "--sandbox", "--output-format", "stream-json", "--print-timeout", "5m",
                 "--add-dir", "{worktree}", "-p", "{prompt}"],
    },
    "kimi-code/k3": {
        "host": "pro-local", "account_ref": "kimi-allegro-oauth",
        "argv": [KIMI, "-m", "kimi-code/k3", "--output-format", "stream-json", "-p", "{prompt}"],
    },
    "codex-gpt-5.6-sol": {"host": "pro-local", "account_ref": "codex-oauth", "argv": None},
}
for _model in ("qwen3.8-max", "glm-5.2", "deepseek-v4-pro"):
    SEAT_ROUTES[f"tp1-{_model}"] = {
        "host": "m5-ssh-air", "account_ref": "tp1-qwen-code-profile",
        "argv": ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "air",
                 f"PATH=$HOME/.local/share/mise/shims:$PATH qwen -m {_model} --output-format stream-json"
                 " -p 'Review the code packet on stdin.'"],
        "stdin": True,
    }

_VERDICT = re.compile(r"VERDICT=(PASS|BLOCK)\b")
_FINDING = re.compile(r"FINDING=([A-Za-z0-9_.-]{1,40})\|(high|medium|low)\|([^\n\\\"]{1,240})")
_MODEL_KEYS = {"model", "modelId", "model_id", "modelVersion", "resolved_model", "modelName"}
_SESSION_KEYS = {"session_id", "sessionId", "conversation_id", "conversationId", "cascade_id", "cascadeId"}
_COUNT_KEYS = {"num_turns", "numTurns", "request_count", "api_requests", "retries", "retry_count"}
_NON_JUDGMENT_HINTS = re.compile(r"\b(429|403|quota|rate.?limit|unauthori[sz]ed|sign.?in|not logged)\b", re.I)


def _walk(node: Any, sink: dict[str, list]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                if key in _MODEL_KEYS and isinstance(value, str):
                    sink["models"].append(value)
                elif key in _SESSION_KEYS:
                    sink["sessions"].append(str(value))
                elif key in _COUNT_KEYS and isinstance(value, int):
                    sink["counts"].append((key, value))
            if isinstance(value, str):
                sink["text"].append(value)
            else:
                _walk(value, sink)
    elif isinstance(node, list):
        for item in node:
            _walk(item, sink)


def classify_output(seat: str, stdout: str, exit_code: int | None, timed_out: bool) -> dict[str, Any]:
    """Turn one real process result into a journal verdict. Only a VERDICT= line from a process
    that exited 0 in time, whose EVERY observed model identity is the exact requested one, is a
    judgment; everything else is NON_JUDGMENT with the reason — never PASS."""
    lint = _load_lint_module()
    _family, accepted = lint.COUNCIL_V2_SEATS[seat]
    sink: dict[str, list] = {"models": [], "sessions": [], "counts": [], "text": []}
    for line in stdout.splitlines():
        try:
            _walk(json.loads(line), sink)
        except (json.JSONDecodeError, RecursionError):
            sink["text"].append(line)
    blob = "\n".join(sink["text"])
    models = sorted(set(sink["models"]))
    result: dict[str, Any] = {
        "observed_models": models,
        "resolved_model": models[0] if len(models) == 1 else None,
        "session_ref": hashlib.sha256(sink["sessions"][0].encode()).hexdigest()[:16] if sink["sessions"] else None,
        "request_counts": dict(sink["counts"]) or None,
        "findings": [],
    }
    verdicts = _VERDICT.findall(blob)
    reason = None
    if timed_out:
        reason = "timeout"
    elif exit_code != 0:
        reason = f"exit_{exit_code}"
    elif not verdicts:
        reason = "quota_or_auth_error" if _NON_JUDGMENT_HINTS.search(blob) else "no_verdict"
    elif not models:
        reason = "model_identity_unproven"
    elif any(m not in accepted for m in models):
        reason = "model_mismatch"
    if reason:
        result.update(outcome="NON_JUDGMENT", non_judgment_reason=reason)
        return result
    result["outcome"] = verdicts[-1]
    result["resolved_model"] = next(m for m in models if m in accepted)
    result["verdict_sha256"] = hashlib.sha256(blob.encode()).hexdigest()
    seen = set()
    for fid, sev, text in _FINDING.findall(blob):
        if fid not in seen:
            seen.add(fid)
            result["findings"].append({"id": fid, "severity": sev, "summary": text.strip()[:240]})
    return result


def _terminate(proc: subprocess.Popen) -> str:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=3)
        return "sigterm"
    except ProcessLookupError:
        return "already_exited"
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=3)
        return "sigkill"


def run_seat(seat: str, route: dict[str, Any], packet: str, worktree: str, timeout: float) -> dict[str, Any]:
    argv = [a.replace("{worktree}", worktree).replace("{prompt}", packet) for a in route["argv"]]
    started = time.monotonic()
    proc = subprocess.Popen(
        argv, stdin=subprocess.PIPE if route.get("stdin") else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
    )
    timed_out, cleanup = False, "exited"
    try:
        out, err = proc.communicate(packet if route.get("stdin") else None, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out, cleanup = True, _terminate(proc)
        out, err = proc.communicate()
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
            cleanup = "group_reaped"
        except (ProcessLookupError, PermissionError):
            pass
    return {
        "stdout": out or "", "stderr": err or "",
        "dispatch": {
            "pid": proc.pid, "binary": Path(argv[0]).name, "host": route["host"],
            "exit_code": None if timed_out else proc.returncode, "timed_out": timed_out,
            "timeout_s": timeout, "elapsed_s": round(time.monotonic() - started, 1), "cleanup": cleanup,
        },
    }


def cmd_dispatch(args: argparse.Namespace) -> int:
    lint = _load_lint_module()
    pack_dir = Path(args.pack_dir)
    journal, err = _resolve_journal(pack_dir, args.journal) if pack_dir.is_dir() else (None, "pack dir missing")
    if journal is None:
        print(f"council_journal: {err}", file=sys.stderr)
        return 2
    if not 0 < args.timeout <= lint.COUNCIL_V2_MAX_TIMEOUT_S:
        print(f"council_journal: --timeout must be in (0, {lint.COUNCIL_V2_MAX_TIMEOUT_S}]", file=sys.stderr)
        return 2
    wt = args.worktree
    head = subprocess.run(["git", "-C", wt, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", wt, "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True).stdout.strip()
    if head != args.candidate_sha or dirty:
        print("council_journal: worktree HEAD is not the frozen, clean candidate — refusing to dispatch", file=sys.stderr)
        return 2
    diff = subprocess.run(["git", "-C", wt, "diff", "--no-color", f"{args.base_sha}..{args.candidate_sha}"],
                          capture_output=True, text=True, check=True).stdout
    packet = (
        f"You are an independent code reviewer. Review ONLY this diff, candidate commit {args.candidate_sha}. "
        "Do not edit files. Report substantive defects only (correctness bugs, policy bypasses, a test that "
        "hides a bug). Put each defect on its own line as FINDING=<short-id>|<high|medium|low>|<one sentence>. "
        "End with exactly one line VERDICT=<PASS|BLOCK>; BLOCK if any high or medium finding.\n\n" + diff
    )
    contributing = set(args.contributing_family) | set(lint.COUNCIL_V2_ALWAYS_CONTRIBUTING)
    capture = Path(args.capture_dir) / pack_dir.resolve().name
    capture.mkdir(parents=True, exist_ok=True, mode=0o700)
    entries: list[dict[str, Any]] = []
    eligible: list[str] = []
    for seat, (family, accepted) in lint.COUNCIL_V2_SEATS.items():
        base = {"policy": lint.COUNCIL_POLICY_V2, "seat": seat, "family": family, "role": "review",
                "requested_model": accepted[0], "candidate_sha": args.candidate_sha,
                "account_ref": SEAT_ROUTES.get(seat, {}).get("account_ref")}
        if family in contributing:
            entries.append({**base, "eligible": False, "invoked": False, "ok": False,
                            "exclusion_reason": f"contributing family {family}"})
        elif not SEAT_ROUTES.get(seat, {}).get("argv"):
            entries.append({**base, "eligible": True, "invoked": False, "ok": False, "outcome": "NON_JUDGMENT",
                            "non_judgment_reason": "no first-party route"})
        else:
            eligible.append(seat)
    # All eligible seats start together and every one runs to its own end: no early-success skip.
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(eligible))) as pool:
        futures = {s: pool.submit(run_seat, s, SEAT_ROUTES[s], packet, wt, args.timeout) for s in eligible}
        for seat in eligible:
            family, accepted = lint.COUNCIL_V2_SEATS[seat]
            ran = futures[seat].result()
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", seat)
            raw = capture / f"{safe}.raw"
            fd = os.open(raw, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(ran["stdout"] + "\n--stderr--\n" + ran["stderr"])
            verdict = classify_output(seat, ran["stdout"], ran["dispatch"]["exit_code"], ran["dispatch"]["timed_out"])
            entries.append({
                "policy": lint.COUNCIL_POLICY_V2, "seat": seat, "family": family, "role": "review",
                "requested_model": accepted[0], "candidate_sha": args.candidate_sha,
                "account_ref": SEAT_ROUTES[seat]["account_ref"], "eligible": True, "invoked": True,
                "dispatch": ran["dispatch"], "capture_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                "ok": verdict["outcome"] in ("PASS", "BLOCK"), **verdict,
            })
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with journal.open("a", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps({**entry, "ts": now}, ensure_ascii=False) + "\n")
    for entry in entries:
        print(f"council_journal: {entry['seat']}: eligible={entry['eligible']} invoked={entry['invoked']} "
              f"outcome={entry.get('outcome', 'EXCLUDED')} {entry.get('non_judgment_reason', '')}".rstrip())
    judged = [e for e in entries if e.get("outcome") in ("PASS", "BLOCK")]
    blocked = [e for e in judged if e["outcome"] == "BLOCK" or e.get("findings")]
    print(f"council_journal: judgments={len(judged)} with_findings={len(blocked)} -> {journal}")
    return 0 if judged and not blocked else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Record a council seat at dispatch; check R9 quorum using the real rule."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ap = sub.add_parser("append", help="append one seat's outcome, stamped with the real clock")
    ap.add_argument("--pack-dir", required=True)
    ap.add_argument("--seat", required=True)
    ap.add_argument("--outcome", required=True, choices=("ok", "non-judgement"))
    ap.add_argument("--note", default="", help="what the seat returned; required for --outcome ok")
    ap.add_argument("--journal", default=DEFAULT_JOURNAL_NAME)
    ap.set_defaults(func=cmd_append)

    dp = sub.add_parser(
        "dispatch",
        help="SAETTA review policy v2: invoke EVERY eligible seat once on a frozen candidate",
    )
    dp.add_argument("--pack-dir", required=True)
    dp.add_argument("--worktree", required=True)
    dp.add_argument("--base-sha", required=True)
    dp.add_argument("--candidate-sha", required=True)
    dp.add_argument("--contributing-family", action="append", default=[])
    dp.add_argument("--timeout", type=float, default=300.0)
    dp.add_argument("--capture-dir", default="/tmp/saetta-review-captures")
    dp.add_argument("--journal", default=DEFAULT_JOURNAL_NAME)
    dp.set_defaults(func=cmd_dispatch)

    cp = sub.add_parser(
        "check", help="report what R9 says about this pack, before and after its flip date"
    )
    cp.add_argument("--pack-dir", required=True)
    cp.set_defaults(func=cmd_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
