"""
Mata Garuda — Reddit public JSON listener.

Reads r/{sub}/new.json (no auth, read-only). Reddit requires an
identifying User-Agent — we send Mata-Garuda. CLI-only: curl.
"""
from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

logger = logging.getLogger("mata_garuda.tools.reddit")

USER_AGENT = "Mata-Garuda/0.1 by /u/zeroai87"
TIMEOUT_S = 15
BASE_URL = "https://www.reddit.com/r/{sub}/new.json?limit={limit}"


def fetch_subreddit_new(sub: str, limit: int = 25) -> dict[str, Any]:
    """Fetch latest posts from a subreddit. Returns {"ok":bool, "posts":[...], "reason"}."""
    url = BASE_URL.format(sub=sub, limit=limit)
    try:
        proc = subprocess.run(
            [
                "curl", "-sSL", url,
                "-A", USER_AGENT,
                "--max-time", str(TIMEOUT_S),
                "-w", "\n__HTTP_CODE__%{http_code}",
            ],
            capture_output=True, text=True, timeout=TIMEOUT_S + 5,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "posts": [], "reason": "reddit timeout"}
    except FileNotFoundError:
        return {"ok": False, "posts": [], "reason": "curl missing"}

    body = proc.stdout
    marker = "\n__HTTP_CODE__"
    code = 0
    if marker in body:
        idx = body.rfind(marker)
        try:
            code = int(body[idx + len(marker):].strip())
        except ValueError:
            code = 0
        body = body[:idx]

    if code >= 400 or code == 0:
        return {"ok": False, "posts": [], "reason": f"reddit HTTP {code}"}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"ok": False, "posts": [], "reason": "reddit non-json body"}

    children = (
        data.get("data", {}).get("children")
        if isinstance(data, dict) else None
    )
    if not isinstance(children, list):
        return {"ok": False, "posts": [], "reason": "reddit unexpected shape"}

    posts = []
    for child in children:
        if not isinstance(child, dict):
            continue
        d = child.get("data", {})
        if not isinstance(d, dict):
            continue
        posts.append(
            {
                "title": d.get("title", ""),
                "url": "https://www.reddit.com" + d.get("permalink", ""),
                "subreddit": d.get("subreddit", sub),
                "selftext": d.get("selftext", "")[:500],
            }
        )
    return {"ok": True, "posts": posts, "reason": ""}


def filter_keywords(
    posts: list[dict[str, Any]], keywords: list[str]
) -> list[dict[str, Any]]:
    """Keep posts whose title OR selftext contains any keyword (case-insensitive)."""
    kws = [k.lower() for k in keywords if k]
    if not kws:
        return list(posts)
    out = []
    for p in posts:
        hay = (p.get("title", "") + " " + p.get("selftext", "")).lower()
        if any(k in hay for k in kws):
            out.append(p)
    return out
