"""seat_gate.py is fail-closed: no arsenal report, no row, a stale or unreadable report, or any status but LIVE
reads dead; a missing or in-repo kit is a printed refusal, never a traceback. And two `_job` processes racing on one
grant launch the seat exactly once (seat_io's pending->running flip under the lock)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "kbli_design"
DIAG = "docs/design/diagnosis-2026-09-17.md"


def gate(kit: Path | str, report: Path) -> list[str]:
    r = subprocess.run([sys.executable, "-I", str(HERE / "seat_gate.py"), "--kit", str(kit), "--report", str(report)],
                       capture_output=True, text=True)
    assert r.returncode == 0 and not r.stderr, r.stderr
    return r.stdout.splitlines()


def report(tmp: Path, age_h: float, rows: dict[str, str]) -> Path:
    ts = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=age_h)).strftime("%Y-%m-%dT%H:%M:%SZ")
    p = tmp / f"last-{age_h}.json"
    p.write_text(json.dumps({"schema": 1, "ts": ts, "seats": [{"seat": s, "status": st} for s, st in rows.items()]}))
    return p


def test_a_seat_is_live_only_on_a_fresh_report_row_that_says_live(tmp_path: Path) -> None:
    kit = tmp_path / "kit"
    kit.mkdir()
    ok = f"kit ok {kit}"
    assert gate(kit, report(tmp_path, 1, {"codex": "LIVE", "agy": "LIVE", "nlm": "LIVE"})) == [ok, "live codex", "live agy", "live nlm"]
    assert gate(f"{kit}/", report(tmp_path, 1, {"codex": "LIVE"}))[0] == f"kit ok {kit}/"  # echoed as the workflow wrote it
    assert gate(kit, tmp_path / "absent.json") == [ok] + [f"dead {s}: no arsenal report (NEVER_RAN)" for s in ("codex", "agy", "nlm")]
    assert gate(kit, report(tmp_path, 1, {"codex": "LIVE", "nlm": "LIVE"})) == [ok, "live codex", "dead agy: no row in the arsenal report", "live nlm"]
    assert gate(kit, report(tmp_path, 13, {"codex": "LIVE", "agy": "LIVE", "nlm": "LIVE"}))[1] == "dead codex: arsenal report is 13.0h old, bound 12h"
    assert gate(kit, report(tmp_path, -2, {"codex": "LIVE", "agy": "LIVE", "nlm": "LIVE"}))[1].startswith("dead codex: arsenal report is -2.0h old")
    assert gate(kit, report(tmp_path, 1, {"codex": "QUOTA_DEAD", "agy": "LIVE", "nlm": "LIVE"}))[1] == "dead codex: QUOTA_DEAD"
    (tmp_path / "torn.json").write_text('{"ts": "2026-10-08T06:16:17Z", "seats": [')
    assert gate(kit, tmp_path / "torn.json")[1] == "dead codex: unreadable arsenal report (JSONDecodeError)"


def test_the_gate_reads_the_probes_own_report_path_and_seat_names() -> None:
    sys.path.insert(0, str(HERE.parents[1]))
    import scripts.arsenal_probe as probe
    from scripts.kbli_design import seat_gate

    assert seat_gate.REPORT == probe.REPORT_DIR / "last.json" and set(seat_gate.SEATS) <= set(probe.ALL_SEATS)
    workflow = (HERE.parents[1] / "infra/workflows/kbli-nav-design.js").read_text(encoding="utf-8")
    assert all(f'isLive("{s}")' in workflow for s in seat_gate.SEATS)


def test_a_missing_or_in_repo_kit_is_refused_before_any_seat_is_read(tmp_path: Path) -> None:
    rep = report(tmp_path, 1, {"codex": "LIVE"})
    assert gate(tmp_path / "nope", rep) == [f"refused: kit {tmp_path / 'nope'} does not exist"]
    (tmp_path / "checkout/.git").mkdir(parents=True)
    (tmp_path / "checkout/kit").mkdir()
    assert gate(tmp_path / "checkout/kit", rep)[0].startswith("refused: kit ") and len(gate(tmp_path / "checkout/kit", rep)) == 1


def test_the_previous_gallery_is_emptied_first_even_when_the_kit_is_refused(tmp_path: Path) -> None:
    preview = tmp_path / "preview"
    for f in ("mockups/A/chat-day.png", "mockups/B/x/dossier-day.png", "mockups/notes.txt", "site-now/home-light.png"):
        (preview / f).parent.mkdir(parents=True, exist_ok=True)
        (preview / f).write_text("old run")
    r = subprocess.run([sys.executable, "-I", str(HERE / "seat_gate.py"), "--kit", str(tmp_path / "nope"), "--preview", str(preview)],
                       capture_output=True, text=True)
    assert r.stdout.splitlines() == [f"gallery cleared {preview}/mockups pngs=0", f"refused: kit {tmp_path / 'nope'} does not exist"]
    left = sorted(x.relative_to(preview).as_posix() for x in preview.rglob("*"))
    assert left == ["mockups", "mockups/notes.txt", "site-now", "site-now/home-light.png"]
    out = subprocess.run([sys.executable, "-I", str(HERE / "seat_gate.py"), "--kit", str(tmp_path), "--preview", f"{preview}/"],
                         capture_output=True, text=True).stdout
    assert out.splitlines()[0] == f"gallery cleared {preview}//mockups pngs=0"  # what the workflow builds from a trailing-slash arg


def test_grader_and_refuter_briefs_say_the_verdict_is_the_first_line() -> None:
    rule = "The FIRST line of your answer must be exactly `VERDICT: PASS` or `VERDICT: DEFECT`: no preamble,"
    assert all(rule in (HERE / "briefs" / f"{b}.md").read_text(encoding="utf-8") for b in ("grade", "refute"))


def test_two_jobs_racing_on_one_grant_launch_the_seat_once(tmp_path: Path) -> None:
    app, kit, bin_dir = tmp_path / "app", tmp_path / "kit", tmp_path / "bin"
    (app / "docs/design").mkdir(parents=True)
    (app / DIAG).write_text("# diagnosis\n")
    kit.mkdir()
    bin_dir.mkdir()
    (kit / "content-pack.json").write_text(json.dumps({"frozen": [], "codes": {}, "inputs": {DIAG: hashlib.sha256(b"# diagnosis\n").hexdigest()}}))
    files = [f"{s}.html" for s in ("search-results-day", "registry-table-day", "detail-card-day", "dossier-day", "sheet-ledger-day",
                                   "chat-day", "detail-card-night", "registry-table-night")] + ["thesis.md", "derivability.md", "self-report.md", "motion.md"]
    (tmp_path / "canned.md").write_text("VERDICT: x\n" + "".join(f"=== FILE: {n} ===\n<p>{n}</p>\n=== END FILE ===\n" for n in files))
    (bin_dir / "agy").write_text(f"#!/bin/sh\necho x >> {tmp_path / 'calls'}\nsleep 2\ncat {tmp_path / 'canned.md'}\n")
    (bin_dir / "agy").chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    cmd = [sys.executable, "-I", str(HERE / "seat_io.py")]
    common = ["--kit", str(kit), "--app", str(app), "--slot", "b", "--stage", "r1", "--seat", "gemini"]
    assert subprocess.run(cmd + ["prepare", *common], capture_output=True, text=True).stdout.startswith("granted r1/b 1/1")
    (kit / "raw").mkdir()
    (kit / "raw/r1-b.status").write_text("pending\n")
    procs = [subprocess.Popen(cmd + ["_job", *common], stdout=subprocess.PIPE, text=True, env=env) for _ in range(2)]
    outs = sorted(p.communicate(timeout=60)[0].strip() for p in procs)
    assert outs[0].startswith("b r1 files=12 manifest=") and outs[1] == "refused: r1/b has no pending grant for gemini"
    assert (tmp_path / "calls").read_text().count("x") == 1
