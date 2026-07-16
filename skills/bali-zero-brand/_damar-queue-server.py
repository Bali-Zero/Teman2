#!/usr/bin/env python3
"""WR2 Damar queue HTTP server.

Local-only HTTP server that backs the queue UI. Damar opens the UI in a browser, every
button click fires a JSON request to this server, the server runs the right Python script
or DB write, returns JSON. Damar never sees a terminal.

Usage:
    python3 _damar-queue-server.py
    # → opens http://localhost:8765 with the UI

Endpoints:
    GET  /                    → serves _damar-queue-ui.html
    GET  /queue.json          → returns current queue state
    POST /api/mark-published  → body: {item_id, ig_url}; transitions state
    POST /api/mark-rejected   → body: {item_id, reason_tag, notes}; transitions state
    POST /api/capture-delta   → body: {item_id}; captures Canva diff (stub if MCP not available)
    POST /api/flag-needs-human-edit → body: {item_id, reason, retry_count, critic_report_path}; transitions to drafted_needs_human_edit
    POST /api/refresh-metrics → triggers ig-metrics-scraper for one item
    GET  /api/health          → liveness check

Local-only: binds to 127.0.0.1 explicitly. No external exposure.
"""

import fcntl
import functools
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

SKILL_DIR = Path.home() / ".claude/skills/bali-zero-brand"
QUEUE_PATH = Path.home() / "nuzantara/apps/war-room/output/queue/human-review-queue.json"
UI_HTML = SKILL_DIR / "_damar-queue-ui.html"
TAG_UI_HTML = SKILL_DIR / "_damar-tag-ui.html"
ANCHOR_UI_HTML = SKILL_DIR / "_damar-anchor-ui.html"
PAST_DIR = SKILL_DIR / "past"
ANCHORS_DIR = SKILL_DIR / "anchors"

VALID_REJECT_TAGS = {
    "factually-wrong", "tone-off", "image-bad", "topic-stale",
    "legal-risk", "client-conflict", "other",
}

VALID_DOMAINS = {"visa", "tax", "property", "regulatory", "health", "brand"}
VALID_REGISTERS = {"rituale", "analitico", "ironico", "militante", "pedagogico", "poetico", "tecnico"}
VALID_LAYOUTS = {"cover-photo", "photo-headline-yellow-sub", "qa-dialogue",
                 "timeline-pinboard", "dark-status-list", "statement-bomb"}
VALID_AUDIENCE = {"founder", "investor", "digital-nomad", "retiree", "mass-tourist", "mixed"}


def load_queue():
    if not QUEUE_PATH.exists():
        return []
    return json.loads(QUEUE_PATH.read_text())


def save_queue(queue):
    """Atomic write (tmp + os.replace) — a reader must never see a partial file."""
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(QUEUE_PATH.parent), prefix=".queue-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(queue, f, indent=2)
        os.replace(tmp, QUEUE_PATH)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def with_queue_lock(fn):
    """Serialize read-modify-write against the other queue writers.

    Same lock file and protocol as wr2_html_render_apply._append_review_queue and
    wr2_queue_writer (fcntl EX on human-review-queue.lock) — without it, a UI
    action racing the renderer's append loses one of the two writes (Codex
    red-team HIGH, PENDING-ARMS 2026-07-07)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
        lock_path = QUEUE_PATH.with_suffix(".lock")
        with open(lock_path, "w", encoding="utf-8") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            try:
                return fn(*args, **kwargs)
            finally:
                fcntl.flock(lock_fh, fcntl.LOCK_UN)
    return wrapper


def find_item(queue, item_id):
    for it in queue:
        if it["id"] == item_id:
            return it
    return None


@with_queue_lock
def mark_published(item_id, ig_url):
    queue = load_queue()
    item = find_item(queue, item_id)
    if not item:
        return {"ok": False, "error": f"item {item_id} not found"}, 404
    if item["state"] not in ("drafted", "reviewed"):
        return {"ok": False, "error": f"cannot publish from state '{item['state']}'"}, 400
    if not ig_url or not ig_url.startswith("https://"):
        return {"ok": False, "error": "ig_url must be an https URL"}, 400

    has_edits = bool((item.get("designer_override_diff") or {}).get("has_changes"))
    new_state = "published_with_edits" if has_edits else "published"
    now = datetime.now(timezone.utc).isoformat()

    item["state"] = new_state
    item["instagram_post_url"] = ig_url
    item["instagram_published_at"] = now
    item.setdefault("state_history", []).append(
        {"state": new_state, "at": now, "by": "damar"}
    )
    save_queue(queue)
    return {"ok": True, "new_state": new_state, "item_id": item_id}, 200


@with_queue_lock
def mark_rejected(item_id, reason_tag, notes):
    queue = load_queue()
    item = find_item(queue, item_id)
    if not item:
        return {"ok": False, "error": f"item {item_id} not found"}, 404
    if reason_tag not in VALID_REJECT_TAGS:
        return {
            "ok": False,
            "error": f"reason_tag must be one of {sorted(VALID_REJECT_TAGS)}",
        }, 400

    now = datetime.now(timezone.utc).isoformat()
    item["state"] = "rejected"
    item["damar_action_at"] = now
    item["damar_notes"] = f"[{reason_tag}] {notes or ''}".strip()
    item.setdefault("state_history", []).append(
        {"state": "rejected", "at": now, "by": "damar", "reason_tag": reason_tag}
    )
    save_queue(queue)
    return {"ok": True, "item_id": item_id, "reason_tag": reason_tag}, 200


@with_queue_lock
def capture_delta(item_id):
    """Stub: full Canva-MCP-driven diff requires orchestrator runtime.

    For now: marks item state as 'reviewed' and writes a placeholder diff. Real diff comes
    from the orchestrator when Damar reopens the carousel after editing. Future: hook this
    endpoint to the actual mcp__claude_ai_Canva__get-design-content tool.
    """
    queue = load_queue()
    item = find_item(queue, item_id)
    if not item:
        return {"ok": False, "error": f"item {item_id} not found"}, 404

    now = datetime.now(timezone.utc).isoformat()
    item["state"] = "reviewed"
    item["damar_action_at"] = now
    item.setdefault("state_history", []).append(
        {"state": "reviewed", "at": now, "by": "damar", "via": "ui-capture-stub"}
    )
    item.setdefault("designer_override_diff", {
        "_pending_canva_mcp": True,
        "captured_at": now,
        "note": "Damar marked reviewed via UI. Full diff will be computed when orchestrator next runs.",
    })
    save_queue(queue)
    return {"ok": True, "item_id": item_id, "state": "reviewed"}, 200


@with_queue_lock
def flag_needs_human_edit(item_id, reason, retry_count, critic_report_path):
    """Transition a drafted carousel to drafted_needs_human_edit after orchestrator
    exhausts retry budget. Used by wr2-design-architect Failure mode."""
    queue = load_queue()
    item = find_item(queue, item_id)
    if not item:
        return {"ok": False, "error": f"item {item_id} not found"}, 404
    if item["state"] not in ("drafted", "drafted_needs_human_edit"):
        return {
            "ok": False,
            "error": f"can only flag from 'drafted' state, got '{item['state']}'",
        }, 400

    now = datetime.now(timezone.utc).isoformat()
    item["state"] = "drafted_needs_human_edit"
    item["needs_human_edit_reason"] = reason or "(none provided)"
    item["needs_human_edit_retry_count"] = int(retry_count or 0)
    item["needs_human_edit_critic_report"] = critic_report_path or None
    item["needs_human_edit_flagged_at"] = now
    item.setdefault("state_history", []).append(
        {"state": "drafted_needs_human_edit", "at": now, "by": "wr2-design-architect",
         "reason": reason, "retry_count": int(retry_count or 0)}
    )
    save_queue(queue)
    return {"ok": True, "item_id": item_id, "new_state": "drafted_needs_human_edit"}, 200


def list_past_carousels():
    """Return list of past carousels with metadata + cover slide path."""
    if not PAST_DIR.exists():
        return []
    items = []
    for d in sorted(PAST_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        meta_path = d / "metadata.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        cover = d / "01.jpg"
        items.append({
            "bucket": d.name,
            "metadata": meta,
            "cover_path": str(cover.relative_to(SKILL_DIR)) if cover.exists() else None,
            "is_tagged": meta.get("topic_slug") not in (None, "", "unknown"),
        })
    return items


def update_past_metadata(bucket, fields):
    """Update tagging fields on a past carousel's metadata.json."""
    target = PAST_DIR / bucket
    if not target.is_dir():
        return {"ok": False, "error": f"bucket {bucket} not found"}, 404

    meta_path = target / "metadata.json"
    if not meta_path.exists():
        return {"ok": False, "error": f"metadata.json missing for {bucket}"}, 404

    meta = json.loads(meta_path.read_text())

    if "domain" in fields and fields["domain"] not in VALID_DOMAINS:
        return {"ok": False, "error": f"invalid domain; must be one of {sorted(VALID_DOMAINS)}"}, 400
    if "register" in fields and fields["register"] not in VALID_REGISTERS:
        return {"ok": False, "error": f"invalid register; must be one of {sorted(VALID_REGISTERS)}"}, 400
    if "layout_primary" in fields and fields["layout_primary"] not in VALID_LAYOUTS:
        return {"ok": False, "error": f"invalid layout; must be one of {sorted(VALID_LAYOUTS)}"}, 400
    if "audience" in fields and fields["audience"] not in VALID_AUDIENCE:
        return {"ok": False, "error": f"invalid audience; must be one of {sorted(VALID_AUDIENCE)}"}, 400

    if "topic_slug" in fields:
        meta["topic_slug"] = fields["topic_slug"].strip().lower().replace(" ", "-")
    if "domain" in fields:
        meta["domain"] = fields["domain"]
    if "register" in fields:
        meta["tone_register_primary"] = fields["register"]
    if "layout_primary" in fields:
        meta["layout_family_primary"] = fields["layout_primary"]
    if "audience" in fields:
        meta["audience_segment"] = fields["audience"]
    if "skip" in fields and fields["skip"]:
        meta["skipped_by_damar"] = True
    if "notes" in fields:
        meta["notes_damar"] = fields["notes"]
    meta["last_tagged_at"] = datetime.now(timezone.utc).isoformat()
    meta["last_tagged_by"] = fields.get("tagged_by", "damar")

    meta_path.write_text(json.dumps(meta, indent=2))
    return {"ok": True, "bucket": bucket, "metadata": meta}, 200


def list_anchors():
    """Return current anchor assignments."""
    if not ANCHORS_DIR.exists():
        return {}
    out = {}
    for d in VALID_DOMAINS:
        anchor_path = ANCHORS_DIR / f"{d}-anchor.jpg"
        anchor_meta = ANCHORS_DIR / f"{d}-anchor.json"
        if anchor_path.exists():
            meta = json.loads(anchor_meta.read_text()) if anchor_meta.exists() else {}
            out[d] = {
                "path": f"anchors/{d}-anchor.jpg",
                "source_bucket": meta.get("source_bucket"),
                "assigned_at": meta.get("assigned_at"),
            }
        else:
            out[d] = None
    return out


def assign_anchor(domain, source_bucket, source_slide=1):
    """Copy a past carousel slide to anchors/<domain>-anchor.jpg."""
    import shutil

    if domain not in VALID_DOMAINS:
        return {"ok": False, "error": f"invalid domain"}, 400

    source_dir = PAST_DIR / source_bucket
    source_slide_path = source_dir / f"{source_slide:02d}.jpg"
    if not source_slide_path.exists():
        return {"ok": False, "error": f"source slide not found: {source_slide_path}"}, 404

    ANCHORS_DIR.mkdir(parents=True, exist_ok=True)
    dest_jpg = ANCHORS_DIR / f"{domain}-anchor.jpg"
    dest_meta = ANCHORS_DIR / f"{domain}-anchor.json"

    # Archive previous anchor if exists
    if dest_jpg.exists():
        archive_dir = ANCHORS_DIR / "_archive"
        archive_dir.mkdir(exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        shutil.copy(dest_jpg, archive_dir / f"{domain}-anchor-{ts}.jpg")
        if dest_meta.exists():
            shutil.copy(dest_meta, archive_dir / f"{domain}-anchor-{ts}.json")

    shutil.copy(source_slide_path, dest_jpg)
    meta = {
        "domain": domain,
        "source_bucket": source_bucket,
        "source_slide": source_slide,
        "assigned_at": datetime.now(timezone.utc).isoformat(),
        "assigned_by": "damar",
    }
    dest_meta.write_text(json.dumps(meta, indent=2))

    return {"ok": True, "domain": domain, "path": f"anchors/{domain}-anchor.jpg",
            "source_bucket": source_bucket}, 200


def trigger_metrics_refresh(item_id):
    """Run ig-metrics-scraper for this single item (out-of-band)."""
    script = SKILL_DIR / "_ig-metrics-scraper.py"
    if not script.exists():
        return {"ok": False, "error": "scraper script missing"}, 500

    venv_py = "/Users/nuzantara/nuzantara/.venv/bin/python"
    py = venv_py if Path(venv_py).exists() else sys.executable
    try:
        result = subprocess.run(
            [py, str(script)],
            capture_output=True, text=True, timeout=300,
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-1000:],
            "exit": result.returncode,
        }, 200
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "metrics scrape timed out (5min)"}, 504


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quieter logs (default writes one line per request)
        sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {format % args}\n")

    def _json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # No `Access-Control-Allow-Origin: *` — this is a localhost-only tool
        # (binds 127.0.0.1). A wildcard CORS header would let any web page read
        # the queue/responses cross-origin. State-changing POSTs are Origin-gated
        # in do_POST (#1708 hardening).
        self.end_headers()
        self.wfile.write(body)

    def _origin_ok(self) -> bool:
        """CSRF guard for state-changing requests (#1708). A request is allowed
        when it has NO Origin header (curl / same-origin fetch / non-browser
        clients) OR an Origin whose host is loopback. A browser page on any other
        site sends its real Origin, which is rejected — so a malicious tab cannot
        drive the local queue server. Bind is already 127.0.0.1-only; this closes
        the only realistic remote vector (cross-site request from Damar's browser)."""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        try:
            host = urlparse(origin).hostname
        except ValueError:
            return False
        return host in ("127.0.0.1", "localhost", "::1")

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return None

    def _serve_html(self, html_path):
        if not html_path.exists():
            self._json(500, {"error": f"UI HTML missing: {html_path}"})
            return
        html = html_path.read_text().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def _serve_image(self, file_path):
        if not file_path.exists() or not file_path.is_file():
            self._json(404, {"error": "image not found"})
            return
        # Security: must be within SKILL_DIR
        try:
            file_path.resolve().relative_to(SKILL_DIR.resolve())
        except ValueError:
            self._json(403, {"error": "path outside skill dir"})
            return
        suffix = file_path.suffix.lower()
        ctype = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(suffix, "application/octet-stream")
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            self._serve_html(UI_HTML)
            return

        if path == "/tag" or path == "/tag.html":
            self._serve_html(TAG_UI_HTML)
            return

        if path == "/anchors" or path == "/anchors.html":
            self._serve_html(ANCHOR_UI_HTML)
            return

        if path == "/queue.json":
            self._json(200, load_queue())
            return

        if path == "/api/past":
            self._json(200, list_past_carousels())
            return

        if path == "/api/anchors":
            self._json(200, list_anchors())
            return

        if path == "/api/observations":
            obs_dir = SKILL_DIR / "_observations"
            if not obs_dir.exists():
                self._json(200, [])
                return
            items = []
            for f in sorted(obs_dir.glob("*.log"), reverse=True)[:50]:
                stat = f.stat()
                items.append({
                    "filename": f.name,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                })
            self._json(200, items)
            return

        if path.startswith("/api/observation/"):
            name = path[len("/api/observation/"):]
            obs_path = SKILL_DIR / "_observations" / name
            try:
                obs_path.resolve().relative_to((SKILL_DIR / "_observations").resolve())
            except ValueError:
                self._json(403, {"error": "path traversal"})
                return
            if not obs_path.exists():
                self._json(404, {"error": "log not found"})
                return
            data = obs_path.read_text(errors="replace")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(data.encode("utf-8"))
            return

        if path == "/inject" or path == "/inject.html":
            self._serve_html(SKILL_DIR / "_damar-inject-ui.html")
            return

        if path == "/api/health":
            self._json(200, {"ok": True, "queue_path": str(QUEUE_PATH),
                            "queue_exists": QUEUE_PATH.exists(),
                            "past_count": len(list(PAST_DIR.iterdir())) if PAST_DIR.exists() else 0})
            return

        # Serve images from past/ and anchors/
        if path.startswith("/past/") or path.startswith("/anchors/"):
            rel = path.lstrip("/")
            self._serve_image(SKILL_DIR / rel)
            return

        # Serve carousel preview PNGs from queue items' slides_dir
        # Format: /carousel-preview/<item_id>/<NN>.png
        if path.startswith("/carousel-preview/"):
            parts = path.lstrip("/").split("/")
            if len(parts) == 3:
                _, item_id, filename = parts
                queue = load_queue()
                item = next((it for it in queue if it["id"] == item_id), None)
                if item and item.get("slides_dir"):
                    slides_dir = Path(item["slides_dir"])
                    target = slides_dir / filename
                    # Path traversal guard: target must be inside slides_dir
                    try:
                        target.resolve().relative_to(slides_dir.resolve())
                    except ValueError:
                        self._json(403, {"error": "path traversal blocked"})
                        return
                    if filename.endswith(".png") and target.exists():
                        data = target.read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", "image/png")
                        self.send_header("Content-Length", str(len(data)))
                        self.send_header("Cache-Control", "public, max-age=300")
                        self.end_headers()
                        self.wfile.write(data)
                        return
            self._json(404, {"error": "carousel preview not found"})
            return

        self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        # CSRF guard (#1708): every POST here mutates state (mark-published,
        # inject-topic which spawns a bypassPermissions claude run, open-folder).
        # Reject cross-site browser requests before reading the body.
        if not self._origin_ok():
            self._json(403, {"ok": False, "error": "cross-origin request rejected"})
            return
        body = self._read_json()
        if body is None:
            self._json(400, {"error": "invalid JSON body"})
            return

        if path == "/api/mark-published":
            payload, status = mark_published(
                body.get("item_id", ""), body.get("ig_url", "")
            )
            self._json(status, payload)
            return

        if path == "/api/mark-rejected":
            payload, status = mark_rejected(
                body.get("item_id", ""),
                body.get("reason_tag", ""),
                body.get("notes", ""),
            )
            self._json(status, payload)
            return

        if path == "/api/capture-delta":
            payload, status = capture_delta(body.get("item_id", ""))
            self._json(status, payload)
            return

        if path == "/api/flag-needs-human-edit":
            payload, status = flag_needs_human_edit(
                body.get("item_id", ""),
                body.get("reason", ""),
                body.get("retry_count", 0),
                body.get("critic_report_path", ""),
            )
            self._json(status, payload)
            return

        if path == "/api/refresh-metrics":
            payload, status = trigger_metrics_refresh(body.get("item_id", ""))
            self._json(status, payload)
            return

        if path == "/api/tag-past":
            payload, status = update_past_metadata(body.get("bucket", ""), body)
            self._json(status, payload)
            return

        if path == "/api/open-folder":
            item_id = body.get("item_id", "")
            queue = load_queue()
            item = next((it for it in queue if it["id"] == item_id), None)
            if not item or not item.get("slides_dir"):
                self._json(404, {"ok": False, "error": "slides_dir not found"})
                return
            slides_dir = item["slides_dir"]
            # Defense-in-depth (#1708): slides_dir comes from the queue (pipeline-
            # written, not raw HTTP), but verify it is an existing directory and
            # terminate `open` option parsing with `--` so a value starting with
            # `-` can't be read as an `open` flag (e.g. `-a`/`--args`).
            if not Path(slides_dir).is_dir():
                self._json(404, {"ok": False, "error": "slides_dir not a directory"})
                return
            try:
                subprocess.run(["open", "--", slides_dir], check=True, timeout=10)
                self._json(200, {"ok": True, "opened": slides_dir})
            except Exception as e:
                self._json(500, {"ok": False, "error": str(e)})
            return

        if path == "/api/inject-topic":
            topic = (body.get("topic") or "").strip()
            report = (body.get("report") or "").strip()
            archetype = (body.get("archetype") or "regulatory-explainer").strip()
            audience = (body.get("audience") or "").strip() or None
            register = (body.get("register") or "").strip() or None
            # Article 14 SOTA fields (added 2026-05-12)
            primary_regulation_code = (body.get("primary_regulation_code") or "").strip() or None
            primary_source_url = (body.get("primary_source_url") or "").strip() or None
            qr_caption = (body.get("qr_caption") or "").strip() or None
            if not topic or not report:
                self._json(400, {"ok": False, "error": "topic and report required"})
                return
            if len(report) < 200:
                self._json(400, {"ok": False, "error": "report too thin (<200 chars)"})
                return

            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            slug = "".join(c if c.isalnum() else "-" for c in topic.lower())[:60].strip("-")
            obs_dir = SKILL_DIR / "_observations"
            obs_dir.mkdir(parents=True, exist_ok=True)
            obs_log = obs_dir / f"{ts}__{slug}.log"

            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                f.write(report)
                report_file = f.name

            # Argument-injection guard (#1708): user-supplied values are passed
            # as a single `--flag=value` token, NOT `["--flag", value]`. A value
            # beginning with `--` therefore stays the flag's VALUE and can never be
            # re-parsed by the downstream argparse as a separate flag (flag-smuggling).
            # report_file/archetype are server-controlled, but use the same form for
            # uniformity.
            cmd = [
                "/Users/nuzantara/nuzantara/.venv/bin/python",
                str(SKILL_DIR / "_manual_inject_runner.py"),
                f"--topic={topic}",
                f"--report-file={report_file}",
                f"--archetype={archetype}",
            ]
            if audience:
                cmd.append(f"--audience={audience}")
            if register:
                cmd.append(f"--register={register}")
            # Article 14 SOTA fields pass-through to manual_inject_runner
            if primary_regulation_code:
                cmd.append(f"--primary-regulation-code={primary_regulation_code}")
            if primary_source_url:
                cmd.append(f"--primary-source-url={primary_source_url}")
            if qr_caption:
                cmd.append(f"--qr-caption={qr_caption}")

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=open(obs_log, "a"),
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                self._json(200, {
                    "ok": True,
                    "pid": proc.pid,
                    "topic": topic,
                    "archetype": archetype,
                    "audience": audience,
                    "register": register,
                    "primary_regulation_code": primary_regulation_code,
                    "primary_source_url": primary_source_url,
                    "qr_caption": qr_caption,
                    "observation_log": str(obs_log),
                    "report_file": report_file,
                    "note": "Pipeline running in background. Tail the log to observe.",
                })
            except Exception as e:
                self._json(500, {"ok": False, "error": str(e)})
            return

        if path == "/api/assign-anchor":
            payload, status = assign_anchor(
                body.get("domain", ""),
                body.get("source_bucket", ""),
                int(body.get("source_slide", 1)),
            )
            self._json(status, payload)
            return

        self._json(404, {"error": "endpoint not found"})


def main():
    host = "127.0.0.1"
    port = 8765
    server = HTTPServer((host, port), Handler)
    print(f"WR2 queue UI ready at http://{host}:{port}")
    print(f"Queue path: {QUEUE_PATH}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
