"""Torture + conformance tests for the unified review-queue locking.

Ledger line (PENDING-ARMS 2026-07-07, Codex red-team HIGH): three writers share
`human-review-queue.json` — the renderer's `_append_review_queue` (locked), the
Damar queue-server UI handlers and `wr2_queue_writer` (both lock-free until this
change). A UI action racing the renderer's append lost one of the two writes.

Proof-of-armed required by the ledger: "all three writers take
`human-review-queue.lock`; torture test with concurrent append+publish keeps
both writes". The torture test here runs the two REAL writer code paths in
separate PROCESSES (fcntl.flock is a cross-process lock) hammering one queue
file; every write from both sides must survive.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPTS_DIR.parent
SERVER_PATH = REPO_ROOT / "skills" / "bali-zero-brand" / "_damar-queue-server.py"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str, path: Path) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {name} from {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


qw = _load("wr2_queue_writer", SCRIPTS_DIR / "wr2_queue_writer.py")
server = _load("damar_queue_server", SERVER_PATH)


# ── The torture test (cross-process, both REAL writer paths) ────────────────

_APPEND_WORKER = r"""
import importlib.util, sys, types
from pathlib import Path
scripts_dir, qpath, n = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
sys.modules.setdefault("asyncpg", types.ModuleType("asyncpg"))  # hermetic: html module imports it at top level
spec = importlib.util.spec_from_file_location("html", scripts_dir / "wr2_html_render_apply.py")
html = importlib.util.module_from_spec(spec); sys.modules["html"] = html; spec.loader.exec_module(html)
for i in range(n):
    html._append_review_queue(
        {"id": f"append-{i}", "draft_id": f"draft-{i:04d}", "state": "drafted"},
        queue_path=qpath,
    )
"""

_INGEST_WORKER = r"""
import importlib.util, sys
from pathlib import Path
scripts_dir, qpath, n = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
spec = importlib.util.spec_from_file_location("qw", scripts_dir / "wr2_queue_writer.py")
qw = importlib.util.module_from_spec(spec); sys.modules["qw"] = qw; spec.loader.exec_module(qw)
for i in range(n):
    r = qw.ingest_external_post(qpath, f"https://www.instagram.com/p/TORT{i:04d}x/")
    assert r.status == "ingested", r.status
"""


def test_torture_concurrent_append_and_ingest_lose_nothing(tmp_path):
    """Two processes hammer the same queue via the two real writer modules.

    Renderer-append (html_render_apply) races queue_writer ingest, N rounds
    each. Without the shared flock this loses entries (both load the same
    baseline, second os.replace erases the first's write); with it, the final
    queue must hold ALL 2N entries and stay valid JSON.
    """
    qpath = tmp_path / "human-review-queue.json"
    qpath.write_text("[]")
    n = 25
    procs = [
        subprocess.Popen([sys.executable, "-c", w, str(SCRIPTS_DIR), str(qpath), str(n)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for w in (_APPEND_WORKER, _INGEST_WORKER)
    ]
    for p in procs:
        _, err = p.communicate(timeout=120)
        assert p.returncode == 0, err.decode()

    queue = json.loads(qpath.read_text())  # valid JSON = no partial write seen
    appended = {e["id"] for e in queue if str(e.get("id", "")).startswith("append-")}
    ingested = {e.get("item_id") for e in queue if str(e.get("item_id", "")).startswith("ig-TORT")}
    assert len(appended) == n, f"lost renderer appends: {n - len(appended)}"
    assert len(ingested) == n, f"lost queue_writer ingests: {n - len(ingested)}"
    assert (tmp_path / "human-review-queue.lock").exists()


# ── queue-server handlers: locked + atomic ───────────────────────────────────


def _seed_server_queue(tmp_path, monkeypatch, items):
    qpath = tmp_path / "human-review-queue.json"
    qpath.write_text(json.dumps(items))
    monkeypatch.setattr(server, "QUEUE_PATH", qpath)
    return qpath


def test_server_mark_published_takes_lock_and_writes(tmp_path, monkeypatch):
    qpath = _seed_server_queue(tmp_path, monkeypatch, [
        {"id": "it-1", "state": "drafted"},
    ])
    body, code = server.mark_published("it-1", "https://www.instagram.com/p/ABC/")
    assert code == 200 and body["ok"]
    assert json.loads(qpath.read_text())[0]["state"] == "published"
    assert qpath.with_suffix(".lock").exists()


def test_server_mark_rejected_no_write_on_bad_tag(tmp_path, monkeypatch):
    """Innocence: a refused transition must not touch the file."""
    qpath = _seed_server_queue(tmp_path, monkeypatch, [
        {"id": "it-2", "state": "drafted"},
    ])
    before = qpath.read_text()
    body, code = server.mark_rejected("it-2", "not-a-valid-tag", "")
    assert code == 400 and not body["ok"]
    assert qpath.read_text() == before


def test_server_save_queue_is_atomic_no_partial_tmp_left(tmp_path, monkeypatch):
    qpath = _seed_server_queue(tmp_path, monkeypatch, [])
    server.save_queue([{"id": "x"}])
    assert json.loads(qpath.read_text()) == [{"id": "x"}]
    leftovers = [p for p in qpath.parent.iterdir() if p.name.startswith(".queue-")]
    assert leftovers == []


# ── CRITICAL #1 (Codex red-team, 2026-07-16): render_incomplete fail-closed ──


def test_server_capture_delta_refuses_render_incomplete(tmp_path, monkeypatch):
    """capture_delta had NO state guard at all — it flipped ANY state
    straight to 'reviewed', including render_incomplete, which
    mark_published already accepts. That was a live render_incomplete ->
    reviewed -> published path with zero completeness check in between."""
    qpath = _seed_server_queue(tmp_path, monkeypatch, [
        {"id": "it-ri", "state": "render_incomplete"},
    ])
    before = qpath.read_text()
    body, code = server.capture_delta("it-ri")
    assert code == 400 and not body["ok"]
    assert qpath.read_text() == before  # untouched


def test_server_capture_delta_allows_drafted(tmp_path, monkeypatch):
    """INNOCENCE: a normal drafted carousel can still advance via capture_delta."""
    qpath = _seed_server_queue(tmp_path, monkeypatch, [
        {"id": "it-ok", "state": "drafted"},
    ])
    body, code = server.capture_delta("it-ok")
    assert code == 200 and body["ok"]
    assert json.loads(qpath.read_text())[0]["state"] == "reviewed"


def test_server_mark_published_refuses_disk_intent_mismatch(tmp_path, monkeypatch):
    """Defense-in-depth (CRITICAL #1): even from an allow-listed state,
    publish is refused if disk disagrees with the item's own recorded intent —
    re-verified independently of whatever state-machine guard let us reach
    this point."""
    slides_dir = tmp_path / "carousel" / "x" / "slides"
    slides_dir.mkdir(parents=True)
    (slides_dir / "01.png").write_bytes(b"\x89PNG")
    (slides_dir / "02.png").write_bytes(b"\x89PNG")
    qpath = _seed_server_queue(tmp_path, monkeypatch, [
        {"id": "it-mismatch", "state": "reviewed",
         "slides_dir": str(slides_dir), "intended_slide_count": 3},
    ])
    body, code = server.mark_published("it-mismatch", "https://www.instagram.com/p/ABC/")
    assert code == 409 and not body["ok"]
    assert json.loads(qpath.read_text())[0]["state"] == "reviewed"  # unchanged


def test_server_mark_published_allows_when_disk_matches_intent(tmp_path, monkeypatch):
    """INNOCENCE: a genuinely complete carousel still publishes normally
    through the new defense-in-depth check."""
    slides_dir = tmp_path / "carousel" / "y" / "slides"
    slides_dir.mkdir(parents=True)
    (slides_dir / "01.png").write_bytes(b"\x89PNG")
    (slides_dir / "02.png").write_bytes(b"\x89PNG")
    qpath = _seed_server_queue(tmp_path, monkeypatch, [
        {"id": "it-complete", "state": "reviewed",
         "slides_dir": str(slides_dir), "intended_slide_count": 2},
    ])
    body, code = server.mark_published("it-complete", "https://www.instagram.com/p/ABC/")
    assert code == 200 and body["ok"]
    assert json.loads(qpath.read_text())[0]["state"] == "published"


def test_queue_writer_mark_published_locks_and_publishes(tmp_path):
    qpath = tmp_path / "human-review-queue.json"
    item_id = "carousel_x"
    qpath.write_text(json.dumps([
        {"id": item_id, "state": "approved", "topic_slug": "x"},
    ]))
    ref = qw.compute_ref_code(item_id)
    res = qw.mark_published(qpath, ref, "https://www.instagram.com/p/XYZ/")
    assert res.status == "published", res.detail
    assert json.loads(qpath.read_text())[0]["state"] == "published"
    assert qpath.with_suffix(".lock").exists()
