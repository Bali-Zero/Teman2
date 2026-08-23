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
  4. .claude/skills/modus/PENDING-ARMS.md — overdue suspended armings (via pending_arms_report; OFF by default since 2026-08-22, ORGANISM_DIGEST_PENDING_ARMS=1 to show)
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
import re
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

# Arsenal positive card (D4, docs/mandates/2026-08-22-arsenal-routing-mandate.md):
# distinct threshold from HEARTBEAT_STALE_H above — this one governs whether a
# session should trust last.json as "current" (also the freshness threshold the
# sessionstart hook uses to decide whether to kick off a background re-probe).
ARSENAL_CARD_STALE_H = 24.0
ARSENAL_CARD_MAX_LINES = 12  # this block is injected fleet-wide, every session — stay ruthless

# arsenal_probe's AUTOMATED recurring heartbeat is a promise only on its primary
# node (docs/runbooks/arsenal-probe.md §How it is armed: "Mini (primary)"). Any
# other node's `<machine>.arsenal_probe.json` is a one-time on-demand stamp from
# a manual `--table` run there — its staleness is expected, not a silent outage.
# Narrowly scoped to this one organ id (not a generic dot-prefix heuristic) to
# avoid a family #3 under/over-match on unrelated heartbeat naming conventions
# (ledger PENDING-ARMS.md: "boot-report organ-silence classifier cries wolf").
_ARSENAL_PROBE_STEM_RE = re.compile(r"^(?P<machine>[a-z][a-z0-9]*)\.arsenal_probe$")
ARSENAL_PROBE_PRIMARY_NODE = "mini"

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


# ------------------------------------------------------------ arsenal boot card
# D4 (docs/mandates/2026-08-22-arsenal-routing-mandate.md): the digest must be a
# POSITIVE boot card — every probed seat + status, not just the not-LIVE ones
# (that was arsenal_seats() above, kept for the attention-only bucket).
#
# "role" in the seat->role->invocation map is NOT a machine-extractable field in
# MODEL_ROSTER.md today: the file's "Routing rule" table (Grunt/Standard/Hard)
# keys off MODEL names (opus-5, codex-luna, kimi-for-coding...), never off the
# arsenal_probe.py seat ids (codex-spark, qwen-cloud-code, nlm, jules...) — there
# is no row in the roster keyed by probe-seat-id at all. What IS machine-
# extractable, verified 2026-08-22 against the live file, is each PROVIDER
# section's own "## <Provider> — ... door(s): <text>" header (6 of 7 provider
# sections carry it; "## Local Ollama" does not — no "door:"/"doors:" substring
# anywhere in that header, so it is a genuine, reportable gap, not a regex miss).
# So this renders seat -> provider -> door, sourced live from the file, in place
# of the seat -> role -> invocation the mandate asked for. Doors are grouped by
# provider (not simplified). Do not invent a role or a fuller invocation string
# to plug this gap — see the D4 report for the proposed smallest roster change.
_ROSTER_DOOR_RE = re.compile(r"^## (?P<provider>[^—\n]+?)\s+—.*?doors?:\s*(?P<door>.+?)\s*$", re.MULTILINE)
_DOOR_CODE_RE = re.compile(r"`([^`]+)`")
_DOOR_MAX_CHARS = 56

# Which MODEL_ROSTER.md provider section documents each arsenal_probe.py seat id
# (grep-verified 2026-08-22: jules/nlm are both rows inside "## Google", agy is
# that section's own CLI door; codex-spark shares "## OpenAI" with codex). This
# is a structural fact about where the roster's prose already places each seat,
# not an invented invocation — the fallback list below mirrors arsenal_probe.py's
# own ALL_SEATS so a missing/broken import still renders something honest.
_SEAT_PROVIDER = {
    "claude": "Anthropic",
    "kimi": "Moonshot",
    "agy": "Google",
    "codex": "OpenAI",
    "codex-spark": "OpenAI",
    "ollama": "Local Ollama",
    "nlm": "Google",
    "qwen-cloud-code": "Alibaba Token Plan (TP1)",
    "jules": "Google",
}
_FALLBACK_ALL_SEATS = ["claude", "kimi", "agy", "codex", "codex-spark",
                        "ollama", "nlm", "qwen-cloud-code", "jules"]


def _known_seats() -> list[str]:
    """The canonical seat list, imported live from arsenal_probe.py so the two
    files cannot silently drift apart (test_roster_seat_drift asserts this stays
    a strict import, not a permanently-tolerated except-pass fallback)."""
    try:
        sys.path.insert(0, str(_repo_root() / "scripts"))
        import arsenal_probe  # noqa: PLC0415 (deliberately lazy — a boot receptor
        return list(arsenal_probe.ALL_SEATS)
    except Exception:
        return list(_FALLBACK_ALL_SEATS)


def _roster_doors(repo_root: Path) -> tuple[dict[str, str], list[str]]:
    """Provider -> short door text, parsed live from MODEL_ROSTER.md's own
    '## Provider — ... door(s): text' headers. A provider absent from the return
    dict (e.g. 'Local Ollama' as of 2026-08-22) genuinely has no such header —
    callers must render that as a stated gap, never silently omit the seat."""
    path = repo_root / "MODEL_ROSTER.md"
    if not path.is_file():
        return {}, ["roster: MODEL_ROSTER.md not found"]
    try:
        text = path.read_text()
    except Exception as e:
        return {}, [f"roster: unreadable ({type(e).__name__})"]
    doors: dict[str, str] = {}
    for m in _ROSTER_DOOR_RE.finditer(text):
        provider = m.group("provider").strip()
        door_text = m.group("door").strip()
        code = _DOOR_CODE_RE.search(door_text)
        door = code.group(1) if code else door_text
        if len(door) > _DOOR_MAX_CHARS:
            door = door[: _DOOR_MAX_CHARS - 3] + "..."
        doors[provider] = door
    return doors, []


def arsenal_card() -> tuple[list[str], list[str]]:
    """The positive boot card: every probed seat + status + age + a roster-
    derived door map — never just the not-LIVE seats (that's arsenal_seats()
    above). Anti-calm-liar: missing/corrupt last.json still renders a line,
    never a crash, never a false all-clear."""
    errs: list[str] = []
    report = _home() / ".organism" / "arsenal" / "last.json"
    if not report.is_file():
        return ["\U0001f50c arsenal: no probe report yet on this machine"], errs
    try:
        raw = report.read_text()
        age_h = (_now() - report.stat().st_mtime) / 3600
        data = json.loads(raw)
    except Exception as e:
        return [f"\U0001f50c arsenal: last.json unreadable ({type(e).__name__})"], errs

    seats = data.get("seats", [])
    if not isinstance(seats, list):
        seats = []
    known = _known_seats()
    probed_ids = [s.get("seat") for s in seats if isinstance(s, dict) and s.get("seat")]
    missing = [s for s in known if s not in probed_ids]

    age_tag = f"{age_h:.0f}h" if age_h >= 1 else "<1h"
    if age_h > ARSENAL_CARD_STALE_H:
        age_tag += ", STALE"
    header = f"\U0001f50c arsenal (probe {age_tag} ago"
    if missing:
        header += f" — PARTIAL {len(probed_ids)}/{len(known)}, missing: {', '.join(missing)}"
    header += "):"

    def mark(s: dict) -> str:
        st = s.get("status", "?")
        seat = s.get("seat", "?")
        return f"{seat}✓" if st == "LIVE" else f"{seat}✗{st.lower()}"

    rollup = "  " + " ".join(mark(s) for s in seats if isinstance(s, dict)) if seats else "  (report has no seats)"

    doors, derr = _roster_doors(_repo_root())
    errs.extend(derr)
    by_provider: dict[str, list[str]] = {}
    for seat in known:
        provider = _SEAT_PROVIDER.get(seat, "?")
        by_provider.setdefault(provider, []).append(seat)
    parts = []
    for provider, seat_ids in by_provider.items():
        door = doors.get(provider, "no door: line in roster")
        parts.append(f"{'+'.join(seat_ids)}={door}")
    role_line = "  doors: " + " · ".join(parts)

    return [header, rollup, role_line], errs


def stale_heartbeats(window_stale_h: float = HEARTBEAT_STALE_H) -> tuple[list[str], list[str]]:
    """Organ heartbeats in ~/.organism/last_seen/ that are stale or self-declared degraded."""
    lines: list[str] = []
    errs: list[str] = []
    hb_dir = _home() / ".organism" / "last_seen"
    if not hb_dir.is_dir():
        return lines, errs
    for path in sorted(hb_dir.glob("*.json")):
        m = _ARSENAL_PROBE_STEM_RE.match(path.stem)
        if m and m.group("machine") != ARSENAL_PROBE_PRIMARY_NODE:
            continue  # on-demand elsewhere; no recurring promise here, never "silent"
        try:
            age_h = (_now() - path.stat().st_mtime) / 3600
            data = json.loads(path.read_text())
        except Exception as e:
            errs.append(f"heartbeat: {path.name} unreadable ({type(e).__name__})")
            continue
        # wr2_runtime_stamp provenance files (ts/pid/host/checkout/head_sha/...,
        # scripts/lib/wr2_runtime_stamp.py) are written per-INVOCATION by one-shot
        # workers, not on a recurring cadence — a `checkout` under .worktrees/ is
        # an ephemeral agent sandbox (superscar #5/#1) that is reaped after its
        # task ends and can never be the canonical recurring producer, so its
        # mtime aging forever is not a broken promise, just an unreaped one-off
        # stamp. Evidence 2026-07-29: Mini's wr2.html_apply.runtime.json read
        # "silent 79h" from a worktree (docs-inventory-check-blocker2-surgical-0725)
        # reaped days earlier, while the SAME organ's stamp on Pro's canonical
        # deploy-clone (~/nuzantara-deploy) was 3 minutes old.
        checkout = data.get("checkout")
        if isinstance(checkout, str) and "/.worktrees/" in checkout:
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
    # OFF by default since 2026-08-22 (Zero GO on the regression diagnosis).
    # Measured 20-22/8: "190 armamenti sospesi OVERDUE" greeted every session
    # and the sessions chose the ledger over the business — 118 of 195 merged
    # PRs from the M5 ops lane alone, ~10 business commits, 27 of 200 commits
    # correcting a previous commit's claim. The ledger is still read at modus TRIAGE and by
    # `pending_arms_report.py`; this only stops it from being the FIRST thing a
    # session sees at boot. Opt back in: ORGANISM_DIGEST_PENDING_ARMS=1.
    if os.environ.get("ORGANISM_DIGEST_PENDING_ARMS", "0") != "1":
        return lines, errs
    try:
        proc = subprocess.run(
            [sys.executable, str(reporter), "--json"],
            capture_output=True, text=True, timeout=4,
            cwd=str(_repo_root()),
        )
        data = json.loads(proc.stdout or "{}")
        # The reporter emits per-entry "class", not "classification" (see
        # pending_arms_report.py, the "class": e.cls key). This read used the
        # latter for its whole life, so e.get(...) was always None, the filter
        # was always empty, and this branch never once fired against the real
        # ledger — 262 overdue TECH-DEBT entries reported as silence.
        # The COUNT now comes from counts.tech_debt_overdue, which the reporter
        # computes itself: a future key rename can then cost us the top-artifact
        # detail but can no longer zero the alarm.
        counts = data.get("counts") or {}
        n_overdue = counts.get("tech_debt_overdue") or 0
        overdue = [
            e for e in data.get("entries", [])
            if e.get("overdue") and e.get("class") == "TECH-DEBT"
        ]
        # On this call-path the two sides must agree exactly: the reporter
        # derives counts from the same entries list, and TECH-DEBT-OVERDUE is
        # `cls == "TECH-DEBT" and overdue and not merged_pr_refs` — the last
        # term only being non-empty under --check-pr-refs, which we never pass.
        # So ANY inequality is drift, not just a total wipeout: checking only
        # `not overdue` would stay silent while HALF the entries renamed a key.
        if n_overdue != len(overdue):
            errs.append(
                f"pending-arms: {n_overdue} overdue by counts, {len(overdue)} matched "
                "in entries (per-entry key drift?)"
            )
        if n_overdue or overdue:
            # `or "?"` and not a get() default: a drifted payload can carry the
            # key with a null value, and None[:70] would raise inside the
            # catch-all below — losing the alarm to fix a detail.
            top = (overdue[0].get("artifact") or "?")[:70] if overdue else "?"
            lines.append(f"{n_overdue or len(overdue)} armamenti sospesi OVERDUE — top: {top}")
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
    card, e6 = arsenal_card()
    return {
        "window_h": window_h,
        "regulatory": reg,
        "seats_not_live": seats,
        "organs": hbs,
        "pending_arms": arms,
        "main": prs,
        "arsenal_card": card,
        "source_errors": e1 + e2 + e3 + e4 + e5 + e6,
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
    # Positive arsenal card (D4): always shown, attention or not — a session
    # needs to know what it CAN use every boot, not only when something died.
    out.extend(d["arsenal_card"])
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
        # A minimal MODEL_ROSTER.md so the door-extraction path is exercised
        # cleanly in this fixture too — every provider _SEAT_PROVIDER names
        # gets a door line, so a healthy world has zero "no door: line" gaps.
        (fake_repo / "MODEL_ROSTER.md").write_text(
            "## Anthropic — door: `claude` CLI\n"
            "## Moonshot — door: `kimi` CLI\n"
            "## Google — door: `agy` CLI\n"
            "## OpenAI — door: `codex exec` CLI\n"
            "## Local Ollama — door: `ollama run` CLI\n"
            "## Alibaba Token Plan (TP1) — doors: DashScope\n"
        )
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
            arsenal_json = fake_home / ".organism" / "arsenal" / "last.json"
            known = _known_seats()

            # ---- innocence: healthy world → calm summary + full positive arsenal
            # card, never silence, never a spurious PARTIAL/STALE marker.
            arsenal_json.write_text(json.dumps(
                {"seats": [{"seat": s, "status": "LIVE"} for s in known]}))
            hb = fake_home / ".organism" / "last_seen" / "mini.probe.json"
            hb.write_text(json.dumps({"status": "ok"}))
            d = build_digest(24)
            out = render(d)
            expect("innocence: healthy world not flagged",
                   not d["regulatory"] and not d["seats_not_live"] and not d["organs"])
            expect("innocence: calm output is non-empty (anti-calm-liar)", bool(out.strip()))
            expect("innocence: calm summary + arsenal card, no more no less",
                   out.splitlines()[0].startswith("📰 organismo")
                   and len(out.splitlines()) == 1 + len(d["arsenal_card"]))
            expect("innocence: full probe shows no PARTIAL marker",
                   not any("PARTIAL" in ln for ln in d["arsenal_card"]))
            expect("innocence: fresh probe shows no STALE marker",
                   not any("STALE" in ln for ln in d["arsenal_card"]))
            expect("innocence: arsenal card within the 12-line budget",
                   len(d["arsenal_card"]) <= ARSENAL_CARD_MAX_LINES)

            # ---- guilt: partial probe (fewer seats than the roster knows about)
            # must NOT read as a complete all-clear.
            arsenal_json.write_text(json.dumps(
                {"seats": [{"seat": known[0], "status": "LIVE"}]}))
            d = build_digest(24)
            expect("guilt: partial probe renders the PARTIAL marker",
                   any("PARTIAL" in ln for ln in d["arsenal_card"]))
            expect("guilt: partial marker names a missing seat",
                   len(known) < 2 or any(known[1] in ln for ln in d["arsenal_card"]))

            # ---- guilt: a last.json older than 24h must not read as current
            arsenal_json.write_text(json.dumps(
                {"seats": [{"seat": s, "status": "LIVE"} for s in known]}))
            old_report = _now() - 30 * 3600
            os.utime(arsenal_json, (old_report, old_report))
            d = build_digest(24)
            expect("guilt: stale (>24h) arsenal report flagged STALE, not current",
                   any("STALE" in ln for ln in d["arsenal_card"])
                   and any("30h" in ln for ln in d["arsenal_card"]))

            # ---- innocence: missing report never crashes, never a false all-clear
            arsenal_json.unlink()
            d = build_digest(24)
            expect("innocence: missing arsenal report doesn't crash the digest",
                   bool(d["arsenal_card"]))
            expect("innocence: missing report is stated, not a silent all-clear",
                   not any("PARTIAL" in ln or "✓" in ln for ln in d["arsenal_card"]))

            # ---- innocence: corrupt report never crashes, never a false all-clear
            arsenal_json.write_text("{not json")
            d = build_digest(24)
            expect("innocence: corrupt arsenal report doesn't crash the digest",
                   bool(d["arsenal_card"]))
            expect("innocence: corrupt report becomes a stated error, not silence",
                   any("unreadable" in ln for ln in d["arsenal_card"]))

            # restore a full, fresh report for the rest of this fixture run
            arsenal_json.write_text(json.dumps(
                {"seats": [{"seat": s, "status": "LIVE"} for s in known]}))

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

            # ---- innocence: stale arsenal_probe on a NON-primary node is not "silent"
            # (ledger: "boot-report organ-silence classifier cries wolf" — a one-time
            # on-demand stamp there, not a broken recurring promise)
            hb3 = fake_home / ".organism" / "last_seen" / "m5.arsenal_probe.json"
            hb3.write_text(json.dumps({"status": "ok"}))
            os.utime(hb3, (old, old))
            d = build_digest(24)
            expect("innocence: stale non-primary arsenal_probe not flagged silent",
                   not any("arsenal_probe" in ln for ln in d["organs"]))

            # ---- innocence: a wr2_runtime_stamp provenance file whose `checkout`
            # is under .worktrees/ is a one-off stamp from a reaped ephemeral
            # sandbox, never a recurring promise on THIS host — must not be
            # flagged "silent" no matter how old (2026-07-29 finding: Mini read
            # 79h-silent from a worktree gone days earlier while the real
            # production daemon's own heartbeat on Pro was minutes old)
            hb5 = fake_home / ".organism" / "last_seen" / "wr2.html_apply.runtime.json"
            hb5.write_text(json.dumps({
                "ts": "2026-07-25T22:02:05Z", "pid": 1, "host": "mini-pro2",
                "checkout": "/Users/nuzantara/nuzantara/.worktrees/some-reaped-lane",
                "head_sha": "deadbeef", "dirty": True, "stale_modules": [], "errors": [],
            }))
            os.utime(hb5, (old, old))
            d = build_digest(24)
            expect("innocence: worktree-sourced runtime stamp not flagged silent",
                   not any("wr2.html_apply" in ln for ln in d["organs"]))

            # ---- guilt: same organ, but stamped from a CANONICAL (non-worktree)
            # checkout — e.g. the real deploy-clone daemon — must still flag when
            # stale. Proves the exemption is scoped to .worktrees/, not to any
            # file carrying a `checkout` field.
            hb6 = fake_home / ".organism" / "last_seen" / "wr2.supervisor.runtime.json"
            hb6.write_text(json.dumps({
                "ts": "2026-07-25T22:02:05Z", "pid": 1, "host": "Nuzantara",
                "checkout": "/Users/nuzantara/nuzantara-deploy",
                "head_sha": "deadbeef", "dirty": False, "stale_modules": [], "errors": [],
            }))
            os.utime(hb6, (old, old))
            d = build_digest(24)
            expect("guilt: canonical-checkout runtime stamp still flags silent",
                   any("wr2.supervisor.runtime: silent" in ln for ln in d["organs"]))

            # ---- guilt: stale arsenal_probe on its PRIMARY node still flags
            hb4 = fake_home / ".organism" / "last_seen" / "mini.arsenal_probe.json"
            hb4.write_text(json.dumps({"status": "ok"}))
            os.utime(hb4, (old, old))
            d = build_digest(24)
            expect("guilt: stale primary-node arsenal_probe still flagged",
                   any("mini.arsenal_probe: silent" in ln for ln in d["organs"]))

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

    # ---- roster-drift guard: run against the REAL repo (env overrides are
    # unset again at this point) so it fails the moment MODEL_ROSTER.md's
    # provider headers or arsenal_probe.py's seat list actually move, not a
    # fixture's frozen copy of either.
    real_known = _known_seats()
    expect("roster-drift: _SEAT_PROVIDER covers every known arsenal_probe.py seat",
           set(_SEAT_PROVIDER.keys()) == set(real_known))
    real_doors, real_door_errs = _roster_doors(_repo_root())
    expect("roster-drift: MODEL_ROSTER.md was readable for the door extraction",
           not real_door_errs)
    expected_providers_with_doors = {p for p in _SEAT_PROVIDER.values() if p != "Local Ollama"}
    expect("roster-drift: every provider _SEAT_PROVIDER names (except the "
           "known Local-Ollama gap) still has a 'door(s):' header in MODEL_ROSTER.md",
           expected_providers_with_doors <= set(real_doors.keys()))
    expect("roster-drift: Local Ollama still has no door: line (update this "
           "test, and the D4 report's proposed fix, the day it gains one)",
           "Local Ollama" not in real_doors)

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
