"""seat_io.py: the on-disk round cap survives a new process, C6 is refused on disk, r1 prompts are the
same bytes for every slot, a complete answer splits into 12 hashed files and an incomplete one is
dead, objections are kept only with a C/F ref and a `Test:` line, and a detached codex/agy one-shot
(fake CLIs on PATH) lands through `wait`."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "kbli_design" / "seat_io.py"
DIAG = "docs/design/diagnosis-2026-09-17.md"
FILES = [f"{s}.html" for s in ("search-results-day", "registry-table-day", "detail-card-day", "dossier-day",
                               "sheet-ledger-day", "chat-day", "detail-card-night", "registry-table-night")] + [
    "thesis.md", "derivability.md", "self-report.md", "motion.md"]


def answer(drop: str = "") -> str:
    return "VERDICT: paper ledger\n" + "".join(f"=== FILE: {n} ===\n<p>{n}</p>\n=== END FILE ===\n" for n in FILES if n != drop)


def kit_and_app(tmp: Path) -> tuple[Path, Path]:
    app, kit = tmp / "app", tmp / "kit"
    (app / "docs/design").mkdir(parents=True)
    (app / DIAG).write_text("# diagnosis\n")
    kit.mkdir()
    pack = {"frozen": ["55203", "51101", "56101"], "inputs": {DIAG: hashlib.sha256(b"# diagnosis\n").hexdigest()}, "codes": {}}
    (kit / "content-pack.json").write_text(json.dumps(pack))
    return kit, app


def io(kit: Path, app: Path, *args: str, env: dict | None = None) -> str:
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), *args, "--kit", str(kit), "--app", str(app)],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_round_cap_survives_restart_and_c6_is_refused_on_disk(tmp_path: Path) -> None:
    kit, app = kit_and_app(tmp_path)
    a = io(kit, app, "prepare", "--slot", "a", "--stage", "r1", "--seat", "sonnet")
    c = io(kit, app, "prepare", "--slot", "c", "--stage", "r1", "--seat", "sonnet")
    assert a.startswith("granted r1/a 1/1 prompt=") and a.split("prompt=")[1] == c.split("prompt=")[1]
    assert io(kit, app, "prepare", "--slot", "a", "--stage", "r1", "--seat", "sonnet") == "refused: r1/a at cap 1/1 (taken by sonnet)"
    (kit / "raw").mkdir()
    (kit / "raw/r1-a.md").write_text(answer())
    assert io(kit, app, "ingest", "--slot", "a", "--stage", "r1", "--seat", "sonnet").startswith("a r1 files=12 manifest=")
    assert io(kit, app, "prepare", "--slot", "a", "--stage", "grade", "--seat", "opus").startswith("refused: C6")
    assert io(kit, app, "prepare", "--slot", "a", "--stage", "repair", "--seat", "sol").startswith("refused: repair/a by sol")
    assert io(kit, app, "prepare", "--slot", "a", "--stage", "grade", "--seat", "gemini").startswith("granted grade/a 1/1")
    graded = (kit / "prompts/grade-a.md").read_text()
    assert graded.index("search-results-day.html") < graded.index("AUTHOR SELF-REPORT")
    assert json.loads((kit / "rounds.json").read_text()) == {"r1/a": "sonnet", "r1/c": "sonnet", "grade/a": "gemini"}


def test_split_keeps_complete_answers_and_filter_keeps_only_tested_objections(tmp_path: Path) -> None:
    kit, app = kit_and_app(tmp_path)
    (kit / "raw").mkdir()
    (kit / "raw/r1-b.md").write_text("```markdown\n" + answer(drop="motion.md") + "```\n")
    assert io(kit, app, "ingest", "--slot", "b", "--stage", "r1", "--seat", "gemini") == "b r1 dead: missing motion.md"
    (kit / "raw/r1-c.md").write_text("```\n" + answer() + "```\n")
    line = io(kit, app, "ingest", "--slot", "c", "--stage", "r1", "--seat", "sonnet")
    man = json.loads((kit / "mockups/c/r1/manifest.json").read_text())
    assert line == f"c r1 files=12 manifest={hashlib.sha256((kit / 'mockups/c/r1/manifest.json').read_bytes()).hexdigest()[:16]}"
    assert man["verdict"] == "VERDICT: paper ledger" and len(man["files"]) == 12
    (kit / "raw/grade-c.md").write_text("VERDICT: DEFECT\n\ndossier-day.html breaks C9: the cap is retyped.\n"
                                        "Test: [data-pack=\"55203.cap\"] reads 0% not 0\n\nIt feels flat.\n")
    assert io(kit, app, "ingest", "--slot", "c", "--stage", "grade", "--seat", "sol") == "grade c by sol kept=1 rejected=1"
    assert "Test:" in (kit / "verify/c.md").read_text() and "flat" in (kit / "verify/c.rejected.md").read_text()


def test_detached_one_shots_land_through_wait(tmp_path: Path) -> None:
    kit, app = kit_and_app(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "canned.md").write_text(answer())
    (bin_dir / "agy").write_text(f"#!/bin/sh\ncat {tmp_path / 'canned.md'}\n")
    (bin_dir / "codex").write_text("#!/bin/sh\nwhile [ $# -gt 0 ]; do [ \"$1\" = -o ] && out=$2; shift; done\n"
                                   f"cp {tmp_path / 'canned.md'} \"$out\"\n")
    for f in ("agy", "codex"):
        (bin_dir / f).chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    for slot, seat in (("a", "sol"), ("b", "gemini")):
        out = io(kit, app, "run", "--slot", slot, "--seat", seat, "--stage", "r1", "--detach", env=env).splitlines()
        assert out[0].startswith(f"granted r1/{slot} 1/1 prompt=") and out[1] == "pending"
        assert io(kit, app, "wait", "--slot", slot, "--stage", "r1", "--max-s", "60", env=env).startswith(f"{slot} r1 files=12 manifest=")
    assert io(kit, app, "run", "--slot", "a", "--seat", "sol", "--stage", "r1", "--detach", env=env) == "refused: r1/a at cap 1/1 (taken by sol)"


def test_refusals_are_printed_lines_jobs_run_once_and_the_kit_stays_outside_git(tmp_path: Path) -> None:
    kit, app = kit_and_app(tmp_path)
    pack = json.loads((kit / "content-pack.json").read_text())
    (kit / "content-pack.json").write_text(json.dumps({**pack, "inputs": {DIAG: "0" * 64}}))
    assert io(kit, app, "prepare", "--slot", "a", "--stage", "r1", "--seat", "sol").startswith("refused: ")
    assert not (kit / "rounds.json").is_file() or "r1/a" not in json.loads((kit / "rounds.json").read_text())
    (kit / "content-pack.json").write_text(json.dumps(pack))
    calls, bin_dir = tmp_path / "calls", tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "canned.md").write_text(answer())
    (bin_dir / "agy").write_text(f"#!/bin/sh\necho x >> {calls}\ncat {tmp_path / 'canned.md'}\n")
    (bin_dir / "agy").chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    assert io(kit, app, "run", "--slot", "b", "--seat", "gemini", "--stage", "r1", env=env).splitlines()[-1].startswith("b r1 files=12")
    assert io(kit, app, "_job", "--slot", "b", "--seat", "gemini", "--stage", "r1", env=env).startswith("refused: r1/b has no pending grant")
    assert calls.read_text().count("x") == 1
    inside = tmp_path / "checkout"
    (inside / ".git").mkdir(parents=True)
    (inside / "kit").mkdir()
    assert io(inside / "kit", app, "prepare", "--slot", "a", "--stage", "r1", "--seat", "sol").startswith("refused: kit ")
    assert not (inside / "kit" / "prompts").exists()
