"""Generate one image through the Antigravity CLI (`agy`) in headless mode.

Uses the paid-for Ultra subscription via the official Antigravity CLI: no API
key, no FlowKit. Generator is never grader: callers MUST QA the returned image
(content, text, brand fit) before using it anywhere.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

AGY_BIN = os.environ.get("AGY_BIN", "agy")
_FILE_RE = re.compile(r"file://(/[^\s)\]\"']+\.(?:jpe?g|png))")
_SUFFIX = (
    "\n\nUse your image generation tool to produce exactly one image. "
    "Do NOT write, save, crop, or move any files yourself."
)
_SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD")
_SECRET_PREFIXES = ("ANTHROPIC", "AWS", "GOOGLE_API", "GEMINI_API")


class AgyImageError(RuntimeError):
    """agy failed to produce a usable image."""


def agy_image_available() -> bool:
    return shutil.which(AGY_BIN) is not None


def _agy_env(extra: dict | None = None) -> dict:
    # SECURITY BOUNDARY: agy is an external seat that inherits its environment.
    # Start minimal and strip anything credential-shaped; never pass os.environ.
    env = {
        "HOME": os.environ.get("HOME", os.path.expanduser("~")),
        "USER": os.environ.get("USER", ""),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "TERM": "dumb",
        "PATH": os.path.expanduser("~/.local/bin") + os.pathsep + os.environ.get("PATH", ""),
    }
    env = {
        k: v
        for k, v in env.items()
        if not any(m in k.upper() for m in _SECRET_MARKERS)
        and not k.upper().startswith(_SECRET_PREFIXES)
    }
    env.update(extra or {})
    return env


def _center_crop(img: Image.Image, width: int, height: int) -> Image.Image:
    src_w, src_h = img.size
    target_ratio = width / height
    if src_w / src_h > target_ratio:
        crop_w = int(src_h * target_ratio)
        left = (src_w - crop_w) // 2
        box = (left, 0, left + crop_w, src_h)
    else:
        crop_h = int(src_w / target_ratio)
        top = (src_h - crop_h) // 2
        box = (0, top, src_w, top + crop_h)
    return img.crop(box)


def generate_image_with_agy(
    prompt: str,
    dest: str | os.PathLike,
    *,
    width: int = 1344,
    height: int = 768,
    timeout: float = 240.0,
    env: dict | None = None,
) -> Path:
    full_prompt = prompt.strip() + _SUFFIX
    argv = [AGY_BIN, "-p", full_prompt, "--print-timeout", f"{max(30, int(timeout) - 20)}s"]
    cwd = tempfile.mkdtemp(prefix="agy_image_")
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            env=_agy_env(env),
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
    stdout = proc.stdout or ""
    matches = _FILE_RE.findall(stdout)
    if not matches:
        raise AgyImageError(
            f"agy returned no image link (rc={proc.returncode}); "
            f"stdout tail: {stdout[-400:]!r}; stderr tail: {(proc.stderr or '')[-400:]!r}"
        )
    src = Path(matches[-1])
    if not src.is_file():
        raise AgyImageError(f"agy reported an image that does not exist: {src}")
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as image:
        card = _center_crop(image.convert("RGB"), width, height)
        card = card.resize((width, height), Image.LANCZOS)
        card.save(out, format="JPEG", quality=90, optimize=True)
    return out
