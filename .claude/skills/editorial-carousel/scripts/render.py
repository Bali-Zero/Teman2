#!/usr/bin/env python3
"""
render.py — render a built carousel to PNG (static slides) and MP4 (video slides).

Usage:
    python render.py <build_dir> [--out <output_dir>] [--max-seconds 15]

Reads <build_dir>/carousel.html and <build_dir>/render_manifest.json.
- image slides  -> <out>/NN_name.png      (1080x1350)
- video slides  -> <out>/NN_name.mp4      (text+scrim overlay composited onto the clip)

Robustness: each slide is shot in its own browser with retries, because the
headless Chromium + software-GL combo intermittently crashes on large
composited surfaces.
"""
import argparse, json, pathlib, subprocess, sys, tempfile, time
from playwright.sync_api import sync_playwright

LAUNCH_ARGS = ["--disable-gpu", "--disable-gpu-compositing", "--force-color-profile=srgb"]


def probe_duration(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30)
        return float(out.stdout.strip())
    except Exception:
        return None


def shoot(p, url, sid, dest, w, h, transparent=False):
    browser = p.chromium.launch(args=LAUNCH_ARGS)
    try:
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        page.goto(url, wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(800)
        el = page.query_selector(f"#{sid}")
        el.scroll_into_view_if_needed()
        page.wait_for_timeout(150)
        el.screenshot(path=str(dest), omit_background=transparent)
    finally:
        browser.close()


def shoot_retry(p, url, sid, dest, w, h, transparent=False, tries=3):
    for attempt in range(1, tries + 1):
        try:
            shoot(p, url, sid, dest, w, h, transparent)
            return True
        except Exception as e:
            print(f"    attempt {attempt} failed: {type(e).__name__}", file=sys.stderr)
            time.sleep(1.0)
    return False


def composite_video(bg_path, overlay_png, out_mp4, w, h, dur):
    vf = (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
          f"crop={w}:{h},setsar=1,fps=30[bg];[bg][1:v]overlay=0:0:format=auto")
    cmd = ["ffmpeg", "-y", "-i", str(bg_path), "-i", str(overlay_png),
           "-filter_complex", vf,
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-crf", "20", "-t", f"{dur:.2f}", "-an", "-movflags", "+faststart",
           str(out_mp4)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1200:], file=sys.stderr)
        raise RuntimeError("ffmpeg composite failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-seconds", type=float, default=15.0)
    args = ap.parse_args()

    build_dir = pathlib.Path(args.build_dir).resolve()
    out_dir = pathlib.Path(args.out).resolve() if args.out else (build_dir.parent / "output")
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((build_dir / "render_manifest.json").read_text(encoding="utf-8"))
    w, h = manifest.get("size", [1080, 1350])
    url = (build_dir / "carousel.html").as_uri()

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="ec_render_"))
    ok, fail = [], []

    with sync_playwright() as p:
        for m in manifest["slides"]:
            sid, name, mode = m["id"], m["name"], m["mode"]
            if mode == "video":
                overlay = tmp / f"{name}_overlay.png"
                if not shoot_retry(p, url, sid, overlay, w, h, transparent=True):
                    fail.append(name); print("FAILED overlay", name); continue
                bg = build_dir / m["video"]
                dur = probe_duration(bg) or args.max_seconds
                dur = min(dur, args.max_seconds)
                out_mp4 = out_dir / f"{name}.mp4"
                try:
                    composite_video(bg, overlay, out_mp4, w, h, dur)
                    print("rendered", out_mp4.name, f"({dur:.1f}s)")
                    ok.append(name)
                except Exception as e:
                    fail.append(name); print("FAILED video", name, e)
            else:
                dest = out_dir / f"{name}.png"
                if shoot_retry(p, url, sid, dest, w, h):
                    print("rendered", dest.name); ok.append(name)
                else:
                    fail.append(name); print("FAILED", name)

    print(f"\ndone: {len(ok)} ok, {len(fail)} failed -> {out_dir}")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
