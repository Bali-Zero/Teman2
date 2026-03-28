#!/usr/bin/env python3
"""
Fireworks + Tigris MCP Server
Espone 2 tool a Claude Desktop:
  - generate_image: Fireworks Flux.1 Dev → salva JPG → upload Tigris → URL pubblica
  - upload_to_tigris: upload file locale → Tigris → URL pubblica

Avviato da .mcp.json come server stdio.
"""
import os
import sys
import json
import hashlib
import hmac
import datetime
import urllib.request
from pathlib import Path

# FastMCP (già dipendenza di nuzantara-mcp)
try:
    from fastmcp import FastMCP
except ImportError:
    sys.exit("fastmcp not installed — run: pip install fastmcp")

# ── Config da env (settato in .mcp.json) ─────────────────────────────────────
FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "")
TIGRIS_ACCESS_KEY = os.environ.get("TIGRIS_ACCESS_KEY", "")
TIGRIS_SECRET_KEY = os.environ.get("TIGRIS_SECRET_KEY", "")
TIGRIS_BUCKET     = os.environ.get("TIGRIS_BUCKET", "nuzantara-warroom-images")

FIREWORKS_URL = (
    "https://api.fireworks.ai/inference/v1/workflows/"
    "accounts/fireworks/models/flux-1-dev-fp8/text_to_image"
)
TIGRIS_ENDPOINT   = "https://fly.storage.tigris.dev"
TIGRIS_PUBLIC_BASE = f"https://{TIGRIS_BUCKET}.fly.storage.tigris.dev"

mcp = FastMCP("fireworks-tigris")


def _tigris_put(img_bytes: bytes, key: str) -> str:
    """PUT bytes to Tigris S3. Returns public URL or raises."""
    now      = datetime.datetime.utcnow()
    date_str = now.strftime("%Y%m%d")
    ts_str   = now.strftime("%Y%m%dT%H%M%SZ")
    region   = "auto"
    host     = "fly.storage.tigris.dev"
    ctype    = "image/jpeg"
    chash    = hashlib.sha256(img_bytes).hexdigest()

    canonical = "\n".join([
        "PUT",
        f"/{TIGRIS_BUCKET}/{key}",
        "",
        f"content-type:{ctype}",
        f"host:{host}",
        f"x-amz-content-sha256:{chash}",
        f"x-amz-date:{ts_str}",
        "",
        "content-type;host;x-amz-content-sha256;x-amz-date",
        chash,
    ])
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256", ts_str,
        f"{date_str}/{region}/s3/aws4_request",
        hashlib.sha256(canonical.encode()).hexdigest(),
    ])

    def _hmac(key, msg):
        return hmac.new(
            key if isinstance(key, bytes) else key.encode(),
            msg.encode(), hashlib.sha256
        ).digest()

    signing_key = _hmac(
        _hmac(_hmac(_hmac(f"AWS4{TIGRIS_SECRET_KEY}", date_str), region), "s3"),
        "aws4_request",
    )
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    auth = (
        f"AWS4-HMAC-SHA256 Credential={TIGRIS_ACCESS_KEY}/{date_str}/{region}/s3/aws4_request,"
        f"SignedHeaders=content-type;host;x-amz-content-sha256;x-amz-date,"
        f"Signature={signature}"
    )
    req = urllib.request.Request(
        f"{TIGRIS_ENDPOINT}/{TIGRIS_BUCKET}/{key}",
        data=img_bytes,
        method="PUT",
        headers={
            "Content-Type": ctype,
            "Authorization": auth,
            "x-amz-date": ts_str,
            "x-amz-content-sha256": chash,
            "x-amz-acl": "public-read",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status not in (200, 204):
            raise RuntimeError(f"Tigris PUT {resp.status}")
    return f"{TIGRIS_PUBLIC_BASE}/{key}"


@mcp.tool()
def generate_image(
    prompt: str,
    key: str,
    width: int = 1024,
    height: int = 1280,
    steps: int = 28,
    cfg_scale: float = 3.5,
) -> dict:
    """
    Genera un'immagine con Fireworks Flux.1 Dev e la carica su Tigris.

    Args:
        prompt: Testo del prompt per la generazione immagine.
        key: Path S3 di destinazione, es. 'warroom/20260329_120000/slide_01.jpg'
        width: Larghezza in pixel (default 1024).
        height: Altezza in pixel (default 1280, portrait 4:5).
        steps: Numero di step diffusion (default 28).
        cfg_scale: Guidance scale (default 3.5).

    Returns:
        dict con 'url' (URL pubblica Tigris) e 'size_kb'.
    """
    if not FIREWORKS_API_KEY:
        return {"error": "FIREWORKS_API_KEY not set"}
    if not TIGRIS_ACCESS_KEY or not TIGRIS_SECRET_KEY:
        return {"error": "TIGRIS_ACCESS_KEY / TIGRIS_SECRET_KEY not set"}

    payload = json.dumps({
        "prompt": prompt,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg_scale,
    }).encode()

    req = urllib.request.Request(
        FIREWORKS_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {FIREWORKS_API_KEY}",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        img_bytes = resp.read()

    if len(img_bytes) < 5000:
        return {"error": f"Response troppo piccola ({len(img_bytes)} bytes) — prompt rifiutato?"}

    url = _tigris_put(img_bytes, key)
    return {"url": url, "size_kb": len(img_bytes) // 1024}


@mcp.tool()
def upload_to_tigris(file_path: str, key: str) -> dict:
    """
    Carica un file locale su Tigris e restituisce l'URL pubblica.

    Args:
        file_path: Path assoluto al file locale da caricare.
        key: Path S3 di destinazione, es. 'warroom/run_id/slide_01.jpg'

    Returns:
        dict con 'url' (URL pubblica) e 'size_kb'.
    """
    if not TIGRIS_ACCESS_KEY or not TIGRIS_SECRET_KEY:
        return {"error": "TIGRIS_ACCESS_KEY / TIGRIS_SECRET_KEY not set"}

    p = Path(file_path)
    if not p.exists():
        return {"error": f"File not found: {file_path}"}

    img_bytes = p.read_bytes()
    url = _tigris_put(img_bytes, key)
    return {"url": url, "size_kb": len(img_bytes) // 1024}


if __name__ == "__main__":
    mcp.run()
