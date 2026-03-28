#!/usr/bin/env python3
"""
Canva OAuth2 - One-time authorization flow.
Salva access_token e refresh_token in .env della war room.
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

WAR_ROOM = Path(__file__).parent.parent
ENV_FILE = WAR_ROOM / ".env"

env = {}
for line in ENV_FILE.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

CLIENT_ID     = env["CANVA_CLIENT_ID"]
CLIENT_SECRET = env["CANVA_CLIENT_SECRET"]
REDIRECT_URI  = env.get("CANVA_REDIRECT_URI", "http://127.0.0.1:8080/callback")
PORT          = int(REDIRECT_URI.split(":")[-1].split("/")[0])

SCOPES = "asset:read asset:write design:content:read design:content:write design:meta:read profile:read folder:read folder:write"

code_verifier  = secrets.token_urlsafe(64)
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).rstrip(b"=").decode()
state = secrets.token_urlsafe(16)

auth_url = (
    "https://www.canva.com/api/oauth/authorize"
    f"?client_id={CLIENT_ID}"
    f"&response_type=code"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&scope={urllib.parse.quote(SCOPES)}"
    f"&code_challenge={code_challenge}"
    f"&code_challenge_method=s256"
    f"&state={state}"
)

auth_code = None
callback_received = threading.Event()

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h2>Autorizzazione completata! Puoi chiudere questa finestra.</h2>")
        callback_received.set()

    def log_message(self, *args): pass

server = http.server.HTTPServer(("127.0.0.1", PORT), CallbackHandler)
thread = threading.Thread(target=server.handle_request)
thread.start()

print(f"\nAprendo browser per autorizzazione Canva...")
print(f"URL: {auth_url}\n")
webbrowser.open(auth_url)

callback_received.wait(timeout=120)
server.server_close()

if not auth_code:
    print("❌ Nessun codice ricevuto. Timeout o errore.")
    exit(1)

print(f"✅ Codice ricevuto. Scambio per token...")

credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
data = urllib.parse.urlencode({
    "grant_type":    "authorization_code",
    "code":          auth_code,
    "redirect_uri":  REDIRECT_URI,
    "code_verifier": code_verifier,
}).encode()

req = urllib.request.Request(
    "https://api.canva.com/rest/v1/oauth/token",
    data=data,
    headers={
        "Authorization": f"Basic {credentials}",
        "Content-Type":  "application/x-www-form-urlencoded",
    }
)

with urllib.request.urlopen(req, timeout=30) as resp:
    tokens = json.loads(resp.read())

access_token  = tokens["access_token"]
refresh_token = tokens["refresh_token"]
expires_in    = tokens.get("expires_in", 14400)

print(f"✅ Token ottenuti! Expires in: {expires_in}s")

env_text = ENV_FILE.read_text()
for key, val in [
    ("CANVA_ACCESS_TOKEN",  access_token),
    ("CANVA_REFRESH_TOKEN", refresh_token),
]:
    if key in env_text:
        lines = []
        for line in env_text.splitlines():
            if line.startswith(key + "="):
                lines.append(f"{key}={val}")
            else:
                lines.append(line)
        env_text = "\n".join(lines)
    else:
        env_text += f"\n{key}={val}"

ENV_FILE.write_text(env_text)
print(f"✅ Token salvati in {ENV_FILE}")
print(f"\n✅ Canva API pronta. Refresh token salvato — non scade mai.")
