#!/usr/bin/env python3
"""Burn lane 5: TP1 media-gen batch (wan2.7-image-pro OG heroes + happyhorse t2v).

Probe verdict 2026-10-05 (tp1_burn_media_probe.py, one call each): the TP1 base
serves image and video generation ONLY through the DashScope native async
paths (/api/v1/services/aigc/...), 200 PENDING + task polling; the OpenAI-style
/images/generations and /audio/speech paths are 404 here. This runner is the
first-of-kind consumer of those paths (Zero GO 2026-10-05).

Outputs are DRAFTS: a manifest JSON under data/burn_drafts/media/ (task ids,
status, result URLs). Nothing is published, nothing enters content trees
(Legge 5). TTS native path was not probed; this runner probes it ONCE at start
and records the verdict in the manifest instead of guessing.

Hardening from the codex adversarial review (2026-10-05): capacity is reserved
atomically before submit; the task id is persisted the moment the provider
accepts (recoverable even if polling dies); each job polls against its OWN
deadline computed at submit; POLL_TIMEOUT/POLL_ERROR stay retryable next run;
manifest checkpoints serialize under the lock via tmp+os.replace; every submit
and the TTS probe write a ledger row so the 12h console calibration is never
blind on this lane; --images 0 disables images instead of meaning "unlimited".

Guard: tp1_burn_common.BurnGuard counts submissions (media usage blocks carry
no chat-completion tokens); caps via BURN_MAX_CALLS / BURN_MAX_TOKENS env.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deepseek_client import api_key, log_cost_event  # noqa: E402
from tp1_burn_common import BurnGuard  # noqa: E402

HOST = "https://token-plan.ap-southeast-1.maas.aliyuncs.com"
IMG_URL = f"{HOST}/api/v1/services/aigc/image-generation/generation"
VID_URL = f"{HOST}/api/v1/services/aigc/video-generation/video-synthesis"
TTS_URL = f"{HOST}/api/v1/services/aigc/multimodal-generation/generation"
TASK_URL = f"{HOST}/api/v1/tasks/"

WT = Path(__file__).resolve().parents[1]
ARTICLES = WT / "apps" / "mouth" / "src" / "content" / "articles"
OUTDIR = WT / "data" / "burn_drafts" / "media"
MANIFEST = OUTDIR / "media_manifest.json"

#: statuses that mean "settled" — everything else is retried by the next run.
TERMINAL = {"SUCCEEDED", "FAILED", "SUBMIT_FAIL", "NO_TASK_ID"}

TITLE_RE = re.compile(r"^title:\s*(.+)$", re.MULTILINE)
DESC_RE = re.compile(r"^description:\s*(.+)$", re.MULTILINE)

VIDEO_TOPICS = [
    "slow aerial drone shot over Bali rice terraces at sunrise, no people",
    "static timelapse of Jakarta skyline clouds, no text",
    "close-up of Indonesian rupiah banknotes on a wooden desk, no hands",
    "office desk with laptop showing a blank spreadsheet, shallow depth of field",
    "harbor boats in Padang Bai harbor, calm water, no people",
    "coffee cup and travel documents on a cafe table, no faces",
    "night street of a Bali market, empty, rain reflections",
    "coral reef underwater slow pan, no divers",
    "volcano silhouette at dawn, static camera, clouds moving",
    "stacked cardboard boxes in a clean warehouse, slow dolly",
    "balinese temple gate without people, morning light",
    "ferry crossing between islands, wide shot, no faces",
]


def _req(url, payload=None):
    headers = {"Authorization": f"Bearer {api_key()}"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        headers["X-DashScope-Async"] = "enable"
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers,
                                     method="POST" if data else "GET")
    with urllib.request.urlopen(request, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def submit_image(prompt):
    return _req(IMG_URL, {"model": "wan2.7-image-pro",
                          "input": {"prompt": prompt},
                          "parameters": {"size": "1024*1024", "n": 1}})


def submit_video(prompt):
    return _req(VID_URL, {"model": "happyhorse-1.1-t2v",
                          "input": {"prompt": prompt}})


def poll(task_id, deadline):
    while time.time() < deadline:
        try:
            data = _req(TASK_URL + task_id)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(15)
            continue
        status = (data.get("output") or {}).get("task_status")
        if status in ("SUCCEEDED", "FAILED", "UNKNOWN"):
            return status, data
        time.sleep(10)
    return "POLL_TIMEOUT", {}


def article_prompts(limit):
    prompts = []
    for en in sorted(ARTICLES.rglob("*.mdx")):
        if "." in en.stem:  # locale-suffixed translation, not an EN original
            continue
        head = en.read_text(encoding="utf-8")[:2000]
        title = TITLE_RE.search(head)
        if not title:
            continue
        desc = DESC_RE.search(head)
        prompts.append((str(en.relative_to(ARTICLES)),
                        f"editorial hero illustration, clean flat style: {title.group(1).strip()}"
                        + (f" — {desc.group(1).strip()[:140]}" if desc else "")))
        if limit and len(prompts) >= limit:
            break
    return prompts


def checkpoint(manifest, lock):
    with lock:
        tmp = MANIFEST.with_suffix(".json.tmp")
        json.dump(manifest, open(tmp, "w"), ensure_ascii=False, indent=1)
        os.replace(tmp, MANIFEST)


def run_task(kind, key, model, payload_fn, poll_seconds, guard, manifest, lock):
    if not guard.reserve():
        return
    deadline = time.time() + poll_seconds  # per-job deadline, computed at submit
    try:
        submitted = payload_fn()
        task_id = (submitted.get("output") or {}).get("task_id")
    except Exception as exc:  # noqa: BLE001 — one bad asset must not kill the batch
        with lock:
            manifest[key] = {"kind": kind, "model": model, "status": "SUBMIT_FAIL",
                             "error": str(exc)[:200]}
        log_cost_event(model, {}, purpose="burn-media-submit-fail")
        return
    log_cost_event(model, {}, purpose="burn-media")
    if not task_id:
        with lock:
            manifest[key] = {"kind": kind, "model": model, "status": "NO_TASK_ID"}
        return
    with lock:  # id persisted the moment the provider accepts (codex review #7)
        manifest[key] = {"kind": kind, "model": model, "task_id": task_id,
                         "status": "SUBMITTED"}
    try:
        status, data = poll(task_id, deadline)
    except Exception as exc:  # noqa: BLE001 — keep the task id, stay retryable
        with lock:
            manifest[key] = {"kind": kind, "model": model, "task_id": task_id,
                             "status": "POLL_ERROR", "error": str(exc)[:200]}
        return
    with lock:
        manifest[key] = {"kind": kind, "model": model, "task_id": task_id,
                         "status": status, "output": (data.get("output") or {})}


def main():
    import argparse
    import threading
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--images", type=int, default=None,
                    help="OG images to generate (default 100; 0 disables)")
    ap.add_argument("--videos", type=int, default=0)
    ap.add_argument("--poll-minutes", type=int, default=20)
    args = ap.parse_args()
    n_images = 100 if args.images is None else args.images

    workers = int(os.environ.get("BURN_WORKERS", "8"))
    guard = BurnGuard()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    if MANIFEST.exists():
        manifest = json.load(open(MANIFEST))
    lock = threading.Lock()

    if guard.reserve():
        try:
            _req(TTS_URL, {"model": "qwen-audio-3.0-tts-plus",
                           "input": {"messages": [{"role": "user",
                                                   "content": [{"text": "probe"}]}]}})
            tts_verdict = "200-accepted"
        except urllib.error.HTTPError as exc:
            tts_verdict = f"http-{exc.code}"
        except Exception as exc:  # noqa: BLE001
            tts_verdict = f"error-{type(exc).__name__}"
        log_cost_event("qwen-audio-3.0-tts-plus", {}, purpose="burn-media-tts-probe")
    else:
        tts_verdict = "skipped-guard"
    manifest["_tts_probe"] = tts_verdict
    print(f"burn-media: tts probe={tts_verdict}", flush=True)

    jobs = []
    if n_images:
        for rel, prompt in article_prompts(n_images):
            if manifest.get(f"img:{rel}", {}).get("status") not in TERMINAL:
                jobs.append(("image", f"img:{rel}", "wan2.7-image-pro",
                             lambda p=prompt: submit_image(p)))
    for i, topic in enumerate(VIDEO_TOPICS[:args.videos]):
        if manifest.get(f"vid:{i}", {}).get("status") not in TERMINAL:
            jobs.append(("video", f"vid:{i}", "happyhorse-1.1-t2v",
                         lambda p=topic: submit_video(p)))
    print(f"burn-media: {len(jobs)} jobs, workers={workers}, cap={guard.stats()}", flush=True)

    poll_seconds = args.poll_minutes * 60
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = set()
        for kind, key, model, fn in jobs:
            if not guard.ok():
                print("burn guard cap reached — stopping submission", flush=True)
                break
            futs.add(ex.submit(run_task, kind, key, model, fn, poll_seconds,
                               guard, manifest, lock))
        n = 0
        for f in as_completed(futs):
            if f.cancelled():
                continue
            f.result()
            n += 1
            if n % 10 == 0:
                checkpoint(manifest, lock)
                print(f"  {n}/{len(futs)} | {guard.stats()}", flush=True)
            if not guard.ok():
                pending = sum(1 for p in futs if p.cancel())
                print(f"burn guard cap reached mid-run — cancelled {pending} pending, "
                      f"draining running", flush=True)
    checkpoint(manifest, lock)
    ok = sum(1 for v in manifest.values()
             if isinstance(v, dict) and v.get("status") == "SUCCEEDED")
    print(f"DONE burn-media: succeeded={ok} total={len(manifest)} | {guard.stats()} "
          f"-> {MANIFEST}", flush=True)


if __name__ == "__main__":
    main()
