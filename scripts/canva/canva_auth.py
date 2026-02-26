#!/usr/bin/env python3
"""
Canva OAuth Setup con PKCE — run once to get your tokens.

Usage:
    python3 canva_auth.py
"""

import base64
import hashlib
import http.server
import json
import os
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

CLIENT_ID = os.getenv("CANVA_CLIENT_ID", "OC-AZyQGrxp8EfH")
CLIENT_SECRET = os.getenv("CANVA_CLIENT_SECRET", "")
REDIRECT_URI = "http://127.0.0.1:8080/callback."   # exactly as registered in Canva portal
TOKENS_FILE = Path.home() / ".canva_tokens.json"

SCOPES = [
    "design:content:read",
    "design:content:write",
    "design:meta:read",
    "asset:read",
    "asset:write",
    "brandtemplate:content:read",
    "brandtemplate:meta:read",
    "profile:read",
]

auth_code: str | None = None
auth_event = threading.Event()
server_ready = threading.Event()

VERIFIER_FILE = Path.home() / ".canva_pkce_verifier"


# ------------------------------------------------------------------ #
# PKCE helpers                                                         #
# ------------------------------------------------------------------ #

def generate_code_verifier() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()

def generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


# ------------------------------------------------------------------ #
# Callback server                                                      #
# ------------------------------------------------------------------ #

class CallbackServer(http.server.HTTPServer):
    def server_activate(self):
        super().server_activate()
        server_ready.set()  # signal that we're actually bound and listening


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        # Canva redirects to /callback. (with trailing dot)
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("""
                <html><body style="font-family:sans-serif;text-align:center;padding:60px;background:#f9f9f9">
                <h2 style="color:#00b341">✅ Autorizzazione completata!</h2>
                <p>Puoi chiudere questa finestra e tornare al terminale.</p>
                </body></html>
            """.encode("utf-8"))
        else:
            error = params.get("error", ["unknown"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<html><body>❌ Errore: {error}</body></html>".encode("utf-8"))

        auth_event.set()

    def log_message(self, *args):
        pass


# ------------------------------------------------------------------ #
# Token exchange                                                       #
# ------------------------------------------------------------------ #

def exchange_code_for_tokens(code: str, verifier: str) -> dict:
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code_verifier": verifier,
    }).encode()

    req = urllib.request.Request(
        "https://api.canva.com/rest/v1/oauth/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"Token exchange failed {e.code}: {body}") from e


# ------------------------------------------------------------------ #
# Main                                                                 #
# ------------------------------------------------------------------ #

def main():
    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)

    # Save verifier to disk — survives if browser is faster than server
    VERIFIER_FILE.write_text(verifier)
    VERIFIER_FILE.chmod(0o600)

    params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": "nuzantara-canva-setup",
        "code_challenge_method": "S256",
        "code_challenge": challenge,
    })
    auth_url = f"https://www.canva.com/api/oauth/authorize?{params}"

    # Start callback server on port 8080 — wait until actually bound
    server = CallbackServer(("127.0.0.1", 8080), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Wait until socket is bound before opening browser
    server_ready.wait(timeout=5)

    print("\n🎨 Canva OAuth Setup (PKCE)")
    print("=" * 50)
    print("Server in ascolto su http://127.0.0.1:8080")
    print("Apertura browser...")
    print(f"\nSe il browser non si apre, vai a:\n{auth_url}\n")
    webbrowser.open(auth_url)

    print("In attesa del callback...")
    auth_event.wait(timeout=120)
    server.shutdown()

    if not auth_code:
        print("❌ Timeout o errore — riprova.")
        return

    print("✅ Codice ricevuto, scambio con token...")

    # Load verifier from disk (in case it was a resumed session)
    saved_verifier = VERIFIER_FILE.read_text().strip() if VERIFIER_FILE.exists() else verifier
    VERIFIER_FILE.unlink(missing_ok=True)

    try:
        tokens = exchange_code_for_tokens(auth_code, saved_verifier)
    except Exception as e:
        print(f"❌ {e}")
        return

    import time
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
    TOKENS_FILE.write_text(json.dumps(tokens, indent=2))
    TOKENS_FILE.chmod(0o600)

    print(f"✅ Token salvati in {TOKENS_FILE}")
    print(f"   access_token : {tokens.get('access_token', '')[:20]}...")
    print(f"   expires_in   : {tokens.get('expires_in')}s")
    print(f"   scope        : {tokens.get('scope', '')}")
    print("\nOra puoi usare: python3 canva_carousel.py --template DAHBtCC2-9A --inspect")


if __name__ == "__main__":
    main()
