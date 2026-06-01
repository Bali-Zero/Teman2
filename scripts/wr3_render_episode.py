#!/usr/bin/env python3
"""WR3 clip-renderer driver — Step 5/6.
Adapts our shot-pack schema (shot_id/prompt_positive) to the FlowKit client,
submits Veo 3.1 Fast Tier_ONE jobs, handles the 503 extension-drop health gate
explicitly (does NOT burn retries on 503), and emits a render report.
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wr3_flowkit_client as fk  # noqa: E402

EP = Path(sys.argv[1])
ENDPOINT = os.environ.get("WR3_FLOWKIT_ENDPOINT", "http://127.0.0.1:8100")


def _health() -> dict:
    import urllib.request
    with urllib.request.urlopen(ENDPOINT + "/health", timeout=10) as r:
        return json.loads(r.read().decode())


async def main() -> int:
    shot_pack = json.loads((EP / "shot-pack.json").read_text())
    shots = shot_pack["shots"]

    # Pre-flight health gate (commit 4c98e00 returns 503 if extension dropped)
    h = _health()
    if not h.get("extension_connected"):
        print(json.dumps({"status": "HALT", "reason": "extension_not_connected", "health": h}))
        return 2
    print(f"[render] health OK: {h}", file=sys.stderr)

    ctx = await fk.setup_episode_context(name=EP.name, endpoint=ENDPOINT)
    (EP / "_flowkit_context.json").write_text(json.dumps(ctx.to_dict(), indent=2))
    print(f"[render] episode context project={ctx.project_id} video={ctx.video_id}", file=sys.stderr)

    report = {"rendered": [], "failed": [], "extension_drop": False, "total_cost_cr": 0}

    for shot in shots:
        idx = int(shot["shot_id"].lstrip("s"))  # s001 -> 1
        req = fk.ClipRequest(
            shot_index=idx,
            positive_prompt=shot["prompt_positive"],
            negative_prompt=shot.get("prompt_negative", ""),
            identity_tokens=tuple(shot.get("identity_tokens") or []),
            duration_s=int(round(shot.get("duration_s", 8))),
            resolution=shot_pack.get("resolution", "720x1280"),
            aspect=shot_pack.get("aspect_ratio", "9:16"),
            image_prompt=shot["prompt_positive"],
        )
        last_err = None
        for attempt in range(3):  # 1 + 2 retries
            try:
                clip = await fk.submit_clip(req, episode_dir=EP, episode_context=ctx, endpoint=ENDPOINT)
                report["rendered"].append({"shot_id": shot["shot_id"], "mp4": str(clip.mp4_path),
                                           "cost_cr": clip.cost_credits, "veo_job_id": clip.veo_job_id,
                                           "duration_ms": clip.duration_ms})
                report["total_cost_cr"] += clip.cost_credits
                print(f"[render] {shot['shot_id']} OK ({clip.duration_ms}ms)", file=sys.stderr)
                break
            except urllib.error.HTTPError as e:
                if e.code == 503:
                    # health gate — extension dropped. Do NOT burn retries.
                    report["extension_drop"] = True
                    report["failed"].append({"shot_id": shot["shot_id"], "reason": "503_extension_dropped"})
                    print(json.dumps({"status": "HALT", "reason": "extension_dropped_503",
                                      "shot": shot["shot_id"], "report": report}))
                    (EP / "render-report.json").write_text(json.dumps(report, indent=2))
                    return 3
                last_err = f"HTTP {e.code}"
            except fk.FlowkitQuotaError as e:
                report["failed"].append({"shot_id": shot["shot_id"], "reason": f"quota:{e}"})
                print(json.dumps({"status": "HALT", "reason": "quota_exceeded", "report": report}))
                (EP / "render-report.json").write_text(json.dumps(report, indent=2))
                return 4
            except (fk.FlowkitError, fk.FlowkitTimeoutError, Exception) as e:
                last_err = str(e)
                print(f"[render] {shot['shot_id']} attempt {attempt+1} failed: {last_err}", file=sys.stderr)
        else:
            report["failed"].append({"shot_id": shot["shot_id"], "reason": last_err, "needs_broll_curator": True})

    (EP / "render-report.json").write_text(json.dumps(report, indent=2))
    status = "OK" if not report["failed"] else "PARTIAL"
    print(json.dumps({"status": status, "rendered": len(report["rendered"]),
                      "failed": len(report["failed"]), "total_cost_cr": report["total_cost_cr"]}))
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
