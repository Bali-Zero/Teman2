#!/usr/bin/env python3
"""
Post-publish webhook server — ascolta su :7788
Quando riceve POST /trigger?slug=XXX&category=YYY, lancia:
  1. translate_articles.py (traduzioni)
  2. fireworks_image_generator.py per lo slug specifico (via Fireworks.ai Flux)

Girato da: launchd com.balizero.post-publish-webhook (sempre attivo)
Chiamato da: backend Fly.io dopo ogni publish dalla news-room
"""
import json
import importlib.util
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).parent
VENV_PYTHON = SCRIPT_DIR.parent / ".venv" / "bin" / "python3"
LOG_DIR = Path.home() / ".openclaw" / "workspace" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "post_publish_webhook.log"

SECRET = os.environ.get("POST_PUBLISH_SECRET", "balizero-post-publish-2026")


def _load_organism_heartbeat():
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "scripts" / "lib" / "heartbeat.py"
        if not candidate.exists():
            continue
        spec = importlib.util.spec_from_file_location("nuzantara_heartbeat", candidate)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.organism_heartbeat
    return None


def organism_heartbeat(organ_id: str, status: str = "ok", note: str = "") -> None:
    heartbeat = _load_organism_heartbeat()
    if heartbeat:
        heartbeat(organ_id, status, note)


def _start_heartbeat_thread(stop_event: threading.Event) -> threading.Thread:
    def _loop() -> None:
        while not stop_event.wait(60):
            organism_heartbeat("pro.post_publish_webhook", "ok", "webhook alive")

    thread = threading.Thread(target=_loop, name="organism-heartbeat", daemon=True)
    thread.start()
    return thread


def log(msg: str):
    from datetime import datetime
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def run_translate():
    """Run translate pipeline in background."""
    log("▶ Avvio translate_articles.py")
    result = subprocess.run(
        [str(VENV_PYTHON), str(SCRIPT_DIR / "translate_articles.py")],
        capture_output=True, text=True, timeout=45 * 60
    )
    log(f"✅ translate_articles.py exit={result.returncode}")
    if result.stdout:
        log(f"   stdout: {result.stdout[-500:]}")
    if result.stderr and result.returncode != 0:
        log(f"   stderr: {result.stderr[-300:]}")


def run_image(slug: str, category: str):
    """Run Fireworks image generator for a specific slug."""
    log(f"▶ Avvio immagine per {category}/{slug}")
    # Pass slug/category via env vars
    env = {**os.environ, "TARGET_SLUG": slug, "TARGET_CATEGORY": category}
    result = subprocess.run(
        [str(VENV_PYTHON), str(SCRIPT_DIR / "fireworks_image_generator.py")],
        capture_output=True, text=True, timeout=10 * 60, env=env
    )
    log(f"{'✅' if result.returncode == 0 else '❌'} immagine {slug} exit={result.returncode}")


class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence default HTTP logging

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/trigger":
            self.send_response(404)
            self.end_headers()
            return

        # Read body
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode() if length else ""
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        # Auth check
        auth = self.headers.get("X-Webhook-Secret", "")
        if auth != SECRET:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error":"unauthorized"}')
            return

        slug = data.get("slug", "")
        category = data.get("category", "business")
        log(f"📥 Trigger ricevuto: slug={slug} category={category}")

        # Launch in background threads
        t1 = threading.Thread(target=run_translate, daemon=True)
        t1.start()
        if slug:
            t2 = threading.Thread(target=run_image, args=(slug, category), daemon=True)
            t2.start()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "slug": slug, "category": category}).encode())


if __name__ == "__main__":
    port = int(os.environ.get("WEBHOOK_PORT", "7788"))
    stop_heartbeat = threading.Event()
    organism_heartbeat("pro.post_publish_webhook", "starting", f"webhook starting on {port}")
    _start_heartbeat_thread(stop_heartbeat)
    log(f"🌐 Post-publish webhook su ::{port}")
    server = HTTPServer(("127.0.0.1", port), WebhookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        organism_heartbeat("pro.post_publish_webhook", "degraded", "keyboard interrupt")
        raise
    except Exception as exc:
        organism_heartbeat("pro.post_publish_webhook", "error", f"{type(exc).__name__}: {exc}")
        raise
    finally:
        stop_heartbeat.set()
        organism_heartbeat("pro.post_publish_webhook", "degraded", "webhook stopped")
