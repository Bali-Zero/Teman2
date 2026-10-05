#!/usr/bin/env python3
"""Burn lane 5 probe: first-of-kind TP1 media-gen reachability (no callers exist).

One throwaway call per capability, every candidate endpoint shape logged with
its status + body head. NEVER retries, never loops: this is a reachability
measurement, not a burn lane. Run once per machine; the verdict decides whether
lane 5 (wan2.7-image-pro / happyhorse-1.1-* / qwen-audio-3.0-tts-plus) gets a
real runner this cycle. Prints a table; exit 0 always.
"""
import json
import sys
import urllib.error
import urllib.request

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from deepseek_client import api_key  # noqa: E402

HOST = "https://token-plan.ap-southeast-1.maas.aliyuncs.com"
KEY = api_key()

PROBES = [
    ("wan2.7-image-pro / OpenAI-style images",
     f"{HOST}/compatible-mode/v1/images/generations",
     {"model": "wan2.7-image-pro", "prompt": "a plain white square", "n": 1, "size": "512*512"},
     {}),
    ("wan2.7-image-pro / DashScope native async",
     f"{HOST}/api/v1/services/aigc/image-generation/generation",
     {"model": "wan2.7-image-pro", "input": {"prompt": "a plain white square"},
      "parameters": {"size": "512*512", "n": 1}},
     {"X-DashScope-Async": "enable"}),
    ("qwen-audio-3.0-tts-plus / OpenAI-style speech",
     f"{HOST}/compatible-mode/v1/audio/speech",
     {"model": "qwen-audio-3.0-tts-plus", "input": "probe", "voice": "default"},
     {}),
    ("happyhorse-1.1-t2v / DashScope native async",
     f"{HOST}/api/v1/services/aigc/video-generation/video-synthesis",
     {"model": "happyhorse-1.1-t2v", "input": {"prompt": "a plain white square, static"}},
     {"X-DashScope-Async": "enable"}),
]


def probe(name, url, payload, extra_headers):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}",
                 **extra_headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace")[:200]
            return resp.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")[:200]
    except Exception as exc:  # noqa: BLE001 — probe reports, never raises
        return -1, f"{type(exc).__name__}: {exc}"[:200]


def main():
    for name, url, payload, extra in PROBES:
        status, body = probe(name, url, payload, extra)
        print(f"{status:>4} | {name} | {url}\n       {body}", flush=True)
    print("probe complete — verdict goes into the task brief", flush=True)


if __name__ == "__main__":
    main()
