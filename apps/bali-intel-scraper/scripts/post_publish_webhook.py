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
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SCRIPT_DIR = Path(__file__).parent
VENV_PYTHON = SCRIPT_DIR.parent / ".venv" / "bin" / "python3"
LOG_DIR = Path.home() / ".openclaw" / "workspace" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "post_publish_webhook.log"

SECRET = os.environ.get("POST_PUBLISH_SECRET", "balizero-post-publish-2026")


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
    log(f"🌐 Post-publish webhook su ::{port}")
    server = HTTPServer(("127.0.0.1", port), WebhookHandler)
    server.serve_forever()
