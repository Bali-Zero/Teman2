#!/usr/bin/env python3
"""WR3 one-shot diagnostic probe — generate ONE clip and log every raw response.
Diagnoses the 2026-05-29 `500 INTERNAL` download failure under PAYGATE_TIER_TIER1P5.
Reuses the existing episode FlowKit context (no new project). Spends ~10 Veo cr.
"""
from __future__ import annotations
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wr3_flowkit_client as fk  # noqa: E402

EP = Path(sys.argv[1])
ENDPOINT = "http://127.0.0.1:8100"


def log(stage: str, obj) -> None:
    s = obj if isinstance(obj, str) else json.dumps(obj, default=str)
    print(f"\n[{time.strftime('%H:%M:%S')}] === {stage} ===\n{s[:1500]}", file=sys.stderr, flush=True)


async def main() -> int:
    sp = json.loads((EP / "shot-pack.json").read_text())
    shot = sp["shots"][0]
    ctx_raw = json.loads((EP / "_flowkit_context.json").read_text())

    ctx = fk.EpisodeContext.from_dict({**ctx_raw, "endpoint": ENDPOINT})
    log("CONTEXT (reused)", ctx.to_dict())

    # Step A: scene
    scene_id = await fk._create_scene(ctx, shot_index=1, positive_prompt=shot["prompt_positive"])
    log("SCENE created", {"scene_id": scene_id})

    # Step B: start image
    img_id = await fk._generate_start_image(ctx, prompt=shot["prompt_positive"])
    log("START IMAGE media_id", {"image_media_id": img_id})

    # Step C: generate video
    workflow_id, video_media_id = await fk._generate_video(
        ctx, start_image_media_id=img_id, scene_id=scene_id, prompt=shot["prompt_positive"],
    )
    log("GENERATE-VIDEO returned", {"workflow_id": workflow_id, "video_media_id": video_media_id})

    # Step D: poll media manually (raw) — this is where 500 hit
    import urllib.request
    import urllib.error
    url = f"{ENDPOINT}/api/flow/media/{video_media_id}"
    for i in range(24):  # up to 4 min
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                body = json.loads(r.read().decode())
            keys = list(body.keys())
            has_video = bool((body.get("video") or {}).get("encodedVideo"))
            log(f"MEDIA POLL #{i} (HTTP 200)", {"keys": keys, "has_encodedVideo": has_video,
                                                "detail": body.get("detail"), "status": body.get("status")})
            if has_video:
                log("SUCCESS", {"encodedVideo_len": len((body['video']['encodedVideo']))})
                return 0
            if "detail" in body and "error" in (body.get("detail") or {}):
                err = body["detail"]["error"]
                code = err.get("code")
                if code in (404, "404", "NOT_FOUND"):
                    pass  # pending
                else:
                    log("NON-404 ERROR ENVELOPE (the 500 class)", err)
                    return 3
        except urllib.error.HTTPError as e:
            raw = e.read().decode()[:800]
            log(f"MEDIA POLL #{i} HTTPError {e.code}", raw)
            if e.code != 404:
                return 4
        await asyncio.sleep(10)
    log("TIMEOUT", "media never became ready in 4 min")
    return 5


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
