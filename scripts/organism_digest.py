#!/usr/bin/env python3
"""organism_digest.py — the compact "what changed while you weren't looking" receptor.

Mission (Zero, 2026-07-06, verbatim: "NON LE LEGGO!!!! ... DEVE NUTRIRE IL SISTEMA E DARE
RESOCONTI COMPATTI AL CANALE GIUSTO"): Telegram is a write-only graveyard — alerts land
there and die unread. The channel Zero reads EVERY day is the Claude Code session itself.
This receptor therefore renders a compact digest of the organism's last-N-hours state at
session boot, reading ONLY state that already exists on disk. It migrates no producers:
the 206 Telegram-sending surfaces keep working; this reader makes their unread pings
structurally irrelevant for the session channel.

Sources (all read-only, all pre-existing):
  1. research/regulatory/*-delta.json   — new regulatory deltas (severity, citation, line)
  2. ~/.organism/arsenal/last.json      — AI seats not LIVE (from arsenal_probe.py)
  3. ~/.organism/last_seen/*.json       — organ heartbeats: stale or self-declared degraded
  4. .claude/skills/modus/PENDING-ARMS.md — overdue suspended armings (via pending_arms_report)
  5. git log origin/main (first-parent)  — what landed on main in the window

Contract (same anti-calm-liar family as proprioception_sessionstart.sh):
  - NEVER silent: all-quiet prints a one-line heartbeat proving the receptor ran.
  - Budget-hard: SIGALRM guard; a hung subprocess cannot block session boot.
  - Read-only: no cursor files, no state writes at boot (sibling sessions race-free).
  - Fail-visible: a broken source contributes an error LINE, never an exception.

Scar refs: #2 Esiste≠Armato (the digest reads OUTCOMES on disk, not exit codes);
W55 (single-attempt Telegram drop — cured by not depending on delivery at all);
superscar #3 (--selftest proves guilt AND innocence before this ever gates a boot).

Usage:
    python3 scripts/organism_digest.py                  # compact digest, last 24h
    python3 scripts/organism_digest.py --hours 48
    python3 scripts/organism_digest.py --json
    python3 scripts/organism_digest.py --selftest

Exit codes: 0 always for --digest/--json (a boot receptor must not block);
            --selftest: 0 all checks pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_DELTA_LINES = 5
MAX_PR_LINES = 5
MAX_STALE_LINES = 4
HEARTBEAT_STALE_H = 26.0  # matches proprioception guardian_freshness for the arsenal report
BUDGET_S = 6

# Env-overridable roots so --selftest can fixture a fake world without touching $HOME.
def _home() -> Path:
    return Path(os.environ.get("ORGANISM_DIGEST_HOME", str(Path.home())))


def _repo_root() -> Path:
    override = os.environ.get("ORGANISM_DIGEST_REPO")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent


def _now() -> float:
    return time.time()


# ------------------------------------------------------------------ sources
def regulatory_deltas(window_h: float) -> tuple[list[str], list[str]]:
    """New regulatory deltas whose file mtime falls inside the window."""
    lines: list[str] = []
    errs: list[str] = []
    reg_dir = _repo_root() / "research" / "regulatory"
    if not reg_dir.is_dir():
        return lines, errs
    cutoff = _now() - window_h * 3600
    seen_citations: set[str] = set()
    for path in sorted(reg_dir.glob("*-delta.json"), reverse=True):
        try:
            if path.stat().st_mtime < cutoff:
                continue
            data = json.loads(path.read_text())
        except Exception as e:  # a corrupt delta must be VISIBLE, not skipped silently
            errs.append(f"regulatory: {path.name} unreadable ({type(e).__name__})")
            continue
        for d in data.get("deltas", []):
            cit = d.get("citation", "?")
            if cit in seen_citations:  # same regulation re-verified across passes: one line
                continue
            seen_citations.add(cit)
            sev = d.get("severity", "?")
            line = d.get("service_line", "?")
            if isinstance(line, list):
                line = ", ".join(str(x) for x in line)
            summ = (d.get("title_en") or d.get("summary") or "").strip()
            if len(summ) > 90:
                summ = summ[:87] + "..."
            lines.append(f"[{sev}] {cit} ({line}) — {summ}")
    return lines[:MAX_DELTA_LINES], errs


def arsenal_seats() -> tuple[list[str], list[str]]:
    """Seats not LIVE from the local arsenal probe report (if this machine has one)."""
    lines: list[str] = []
    errs: list[str] = []
    report = _home() / ".organism" / "arsenal" / "last.json"
    if not report.is_file():
        return lines, errs  # machine without a probe report: not an error (M5 has none yet)
    try:
        data = json.loads(report.read_text())
    except Exception as e:
        errs.append(f"arsenal: last.json unreadable ({type(e).__name__})")
        return lines, errs
    age_h = (_now() - report.stat().st_mtime) / 3600
    stale = f", report {age_h:.0f}h old" if age_h > HEARTBEAT_STALE_H else ""
    for s in data.get("seats", []):
        if s.get("status") != "LIVE":
            lines.append(f"seat {s.get('seat')}: {s.get('status')}{stale}")
    return lines, errs


def stale_heartbeats(window_stale_h: float = HEARTBEAT_STALE_H) -> tuple[list[str], list[str]]:
    """Organ heartbeats in ~/.organism/last_seen/ that are stale or self-declared degraded."""
    lines: list[str] = []
    errs: list[str] = []
    hb_dir = _home() / ".organism" / "last_seen"
    if not hb_dir.is_dir():
        return lines, errs
    for path in sorted(hb_dir.glob("*.json")):
        try:
            age_h = (_now() - path.stat().st_mtime) / 3600
            data = json.loads(path.read_text())
        except Exception as e:
            errs.append(f"heartbeat: {path.name} unreadable ({type(e).__name__})")
            continue
        status = str(data.get("status", "")).lower()
        if age_h > window_stale_h:
            lines.append(f"organ {path.stem}: silent {age_h:.0f}h")
        elif status and status not in ("ok", "live", "green"):
            lines.append(f"organ {path.stem}: status={status}")
    return lines[:MAX_STALE_LINES], errs


def pending_arms_overdue() -> tuple[list[str], list[str]]:
    """Overdue TECH-DEBT lines from the W81 ledger, via the existing reporter."""
    lines: list[str] = []
    errs: list[str] = []
    reporter = _repo_root() / "scripts" / "pending_arms_report.py"
    if not reporter.is_file():
        return lines, errs
    try:
        proc = subprocess.run(
            [sys.executable, str(reporter), "--json"],
            capture_output=True, text=True, timeout=4,
            cwd=str(_repo_root()),
        )
        data = json.loads(proc.stdout or "{}")
        overdue = [
            e for e in data.get("entries", [])
            if e.get("overdue") and e.get("classification") == "TECH-DEBT"
        ]
        if overdue:
            top = overdue[0].get("artifact", "?")[:70]
            lines.append(f"{len(overdue)} armamenti sospesi OVERDUE — top: {top}")
    except Exception as e:
        errs.append(f"pending-arms: reporter failed ({type(e).__name__})")
    return lines, errs


def merged_on_main(window_h: float) -> tuple[list[str], list[str]]:
    """What landed on origin/main in the window (local knowledge, no fetch — W80 style)."""
    lines: list[str] = []
    errs: list[str] = []
    since = datetime.now(timezone.utc) - timedelta(hours=window_h)
    try:
        proc = subprocess.run(
            ["git", "log", "origin/main", "--first-parent", "--oneline",
             f"--since={since.isoformat()}"],
            capture_output=True, text=True, timeout=4, cwd=str(_repo_root()),
        )
        if proc.returncode != 0:
            errs.append(f"git-log: rc={proc.returncode}")
            return lines, errs
        all_lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        for ln in all_lines[:MAX_PR_LINES]:
            sha, _, subject = ln.partition(" ")
            lines.append(subject[:96])
        if len(all_lines) > MAX_PR_LINES:
            lines.append(f"… +{len(all_lines) - MAX_PR_LINES} altri commit su main")
    except Exception as e:
        errs.append(f"git-log: {type(e).__name__}")
    return lines, errs


# ------------------------------------------------------------------ digest
def build_digest(window_h: float) -> dict:
    reg, e1 = regulatory_deltas(window_h)
    seats, e2 = arsenal_seats()
    hbs, e3 = stale_heartbeats()
    arms, e4 = pending_arms_overdue()
    prs, e5 = merged_on_main(window_h)
    return {
        "window_h": window_h,
        "regulatory": reg,
        "seats_not_live": seats,
        "organs": hbs,
        "pending_arms": arms,
        "main": prs,
        "source_errors": e1 + e2 + e3 + e4 + e5,
    }


def render(d: dict) -> str:
    out: list[str] = []
    attention = d["regulatory"] or d["seats_not_live"] or d["organs"] or d["pending_arms"]
    n_main = len(d["main"])
    if not attention:
        out.append(
            f"📰 organismo (ultime {d['window_h']:.0f}h): tutto reconciled — "
            f"{n_main} commit su main, 0 delta regolatori, seats OK, organi OK"
        )
    else:
        out.append(f"📰 ORGANISMO — da guardare (ultime {d['window_h']:.0f}h):")
        for ln in d["regulatory"]:
            out.append(f"  ⚖️  {ln}")
        for ln in d["seats_not_live"]:
            out.append(f"  🔌 {ln}")
        for ln in d["organs"]:
            out.append(f"  💤 {ln}")
        for ln in d["pending_arms"]:
            out.append(f"  🕰️  {ln}")
        if d["main"]:
            out.append(f"  ⬆️  main: {n_main if n_main <= MAX_PR_LINES else f'{MAX_PR_LINES}+'} landing — " + d["main"][0])
    for ln in d["source_errors"]:
        out.append(f"  ⚠️ receptor: {ln}")
    return "\n".join(out)


# ------------------------------------------------------------------ selftest
def _selftest() -> int:
    """Guilt AND innocence, superscar #3: the digest must flag a sick world and must
    NOT flag a healthy one — and must never be silent in either."""
    import tempfile

    failures: list[str] = []
    total = 0

    def expect(name: str, cond: bool) -> None:
        nonlocal total
        total += 1
        print(("PASS " if cond else "FAIL ") + name)
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        fake_home = tmp_path / "home"
        fake_repo = tmp_path / "repo"
        (fake_home / ".organism" / "arsenal").mkdir(parents=True)
        (fake_home / ".organism" / "last_seen").mkdir(parents=True)
        (fake_repo / "research" / "regulatory").mkdir(parents=True)
        (fake_repo / "scripts").mkdir(parents=True)
        # A truly-healthy fixture world needs a real git repo with an origin/main ref,
        # otherwise merged_on_main() correctly emits a fail-visible error line and the
        # one-line-calm innocence check would be testing a SICK world.
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"}
        for cmd in (["git", "init", "-q"],
                    ["git", "commit", "-q", "--allow-empty", "-m", "seed"],
                    ["git", "update-ref", "refs/remotes/origin/main", "HEAD"]):
            subprocess.run(cmd, cwd=str(fake_repo), env=env, capture_output=True, check=True)
        os.environ["ORGANISM_DIGEST_HOME"] = str(fake_home)
        os.environ["ORGANISM_DIGEST_REPO"] = str(fake_repo)
        try:
            # ---- innocence: healthy world → calm one-liner, never silence
            (fake_home / ".organism" / "arsenal" / "last.json").write_text(json.dumps(
                {"seats": [{"seat": "claude", "status": "LIVE"}]}))
            hb = fake_home / ".organism" / "last_seen" / "mini.probe.json"
            hb.write_text(json.dumps({"status": "ok"}))
            d = build_digest(24)
            out = render(d)
            expect("innocence: healthy world not flagged",
                   not d["regulatory"] and not d["seats_not_live"] and not d["organs"])
            expect("innocence: calm output is non-empty (anti-calm-liar)", bool(out.strip()))
            expect("innocence: calm output is one line", len(out.splitlines()) == 1)

            # ---- guilt: dead seat
            (fake_home / ".organism" / "arsenal" / "last.json").write_text(json.dumps(
                {"seats": [{"seat": "codex", "status": "AUTH_DEAD"}]}))
            d = build_digest(24)
            expect("guilt: AUTH_DEAD seat flagged",
                   any("codex: AUTH_DEAD" in ln for ln in d["seats_not_live"]))

            # ---- guilt: stale heartbeat (mtime pushed 30h back)
            old = _now() - 30 * 3600
            os.utime(hb, (old, old))
            d = build_digest(24)
            expect("guilt: 30h-silent organ flagged",
                   any("silent" in ln for ln in d["organs"]))

            # ---- guilt: degraded self-declared status on a FRESH heartbeat
            hb2 = fake_home / ".organism" / "last_seen" / "pro.worker.json"
            hb2.write_text(json.dumps({"status": "degraded"}))
            d = build_digest(24)
            expect("guilt: fresh-but-degraded organ flagged",
                   any("status=degraded" in ln for ln in d["organs"]))

            # ---- guilt: fresh regulatory delta listed with severity+citation
            (fake_repo / "research" / "regulatory" / "2026-01-01-delta.json").write_text(
                json.dumps({"deltas": [{"citation": "PMK 99/2099", "severity": "high",
                                        "service_line": "tax", "title_en": "Test reg"}]}))
            d = build_digest(24)
            expect("guilt: regulatory delta surfaces",
                   any("PMK 99/2099" in ln and "high" in ln for ln in d["regulatory"]))

            # ---- innocence: delta file OUTSIDE window ignored
            oldf = fake_repo / "research" / "regulatory" / "2020-01-01-delta.json"
            oldf.write_text(json.dumps({"deltas": [{"citation": "OLD 1/2020"}]}))
            os.utime(oldf, (old - 90 * 24 * 3600, old - 90 * 24 * 3600))
            d = build_digest(24)
            expect("innocence: out-of-window delta ignored",
                   not any("OLD 1/2020" in ln for ln in d["regulatory"]))

            # ---- fail-visible: corrupt delta file inside window becomes an error LINE
            bad = fake_repo / "research" / "regulatory" / "2026-01-02-delta.json"
            bad.write_text("{not json")
            d = build_digest(24)
            expect("fail-visible: corrupt delta becomes a receptor error line",
                   any("unreadable" in ln for ln in d["source_errors"]))
            expect("fail-visible: error line reaches rendered output",
                   "receptor" in render(d))
        finally:
            os.environ.pop("ORGANISM_DIGEST_HOME", None)
            os.environ.pop("ORGANISM_DIGEST_REPO", None)

    print(f"SELFTEST {'OK' if not failures else 'FAILED'} — "
          f"{total - len(failures)}/{total} checks")
    return 0 if not failures else 1


# ------------------------------------------------------------------ main
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        return _selftest()

    # Boot receptor: hard budget, never block, never raise.
    if hasattr(signal, "SIGALRM"):
        signal.alarm(BUDGET_S)
    try:
        d = build_digest(args.hours)
        print(json.dumps(d, ensure_ascii=False) if args.json else render(d))
    except Exception as e:
        print(f"📰 organismo: receptor error ({type(e).__name__}: {e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
