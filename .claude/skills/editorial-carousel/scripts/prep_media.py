#!/usr/bin/env python3
"""
prep_media.py — prepare raw photos / videos for a carousel.

Photo (cover-crop to the slide size, face-safe top anchor by default):
    python prep_media.py photo <in> <out.jpg> [--w 1080] [--h 1350] [--anchor top|center|bottom]

Video (normalize to slide size + trim, H.264):
    python prep_media.py video <in> <out.mp4> [--w 1080] [--h 1350] [--seconds 15]

Notes:
- render.py already scale/crops video backgrounds on the fly, so the video
  command is optional — use it when you want a clean, trimmed, standalone clip.
- Photos SHOULD be prepped: it crops to the exact 1080x1350 and keeps the
  subject's head near the top (where faces usually are), which the on-the-fly
  CSS `cover` cannot guarantee.
"""
import argparse, subprocess, sys


def prep_photo(inp, out, w, h, anchor):
    from PIL import Image
    im = Image.open(inp).convert("RGB")
    iw, ih = im.size
    scale = max(w / iw, h / ih)
    nw, nh = round(iw * scale), round(ih * scale)
    im = im.resize((nw, nh), Image.LANCZOS)
    # horizontal: always center
    x = (nw - w) // 2
    if anchor == "top":
        y = 0
    elif anchor == "bottom":
        y = nh - h
    else:
        y = (nh - h) // 2
    im = im.crop((x, y, x + w, y + h))
    im.save(out, quality=88)
    print(f"photo -> {out} ({w}x{h}, anchor={anchor})")


def prep_video(inp, out, w, h, seconds):
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
          f"crop={w}:{h},setsar=1")
    cmd = ["ffmpeg", "-y", "-i", str(inp), "-vf", vf,
           "-t", str(seconds), "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-crf", "20", "-an", "-movflags", "+faststart",
           str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1200:], file=sys.stderr)
        sys.exit(1)
    print(f"video -> {out} ({w}x{h}, <={seconds}s)")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("photo")
    p.add_argument("inp"); p.add_argument("out")
    p.add_argument("--w", type=int, default=1080); p.add_argument("--h", type=int, default=1350)
    p.add_argument("--anchor", choices=["top", "center", "bottom"], default="top")

    v = sub.add_parser("video")
    v.add_argument("inp"); v.add_argument("out")
    v.add_argument("--w", type=int, default=1080); v.add_argument("--h", type=int, default=1350)
    v.add_argument("--seconds", type=float, default=15.0)

    a = ap.parse_args()
    if a.cmd == "photo":
        prep_photo(a.inp, a.out, a.w, a.h, a.anchor)
    else:
        prep_video(a.inp, a.out, a.w, a.h, a.seconds)


if __name__ == "__main__":
    main()
