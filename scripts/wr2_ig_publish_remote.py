#!/usr/bin/env python3
"""wr2_ig_publish_remote — publish a WR2 carousel to Instagram FROM the operator's
workstation (M5), driving the Fly backend over HTTP. The operator gate (Legge 5).

WHY A SECOND CLI (2026-06-26)
-----------------------------
``scripts/wr2_ig_publish.py`` runs the publish SERVER-SIDE: it imports the backend
Tigris client + IGPublisher directly, so it only works where those creds live (Fly).
The WR2 Control app runs on M5, where there are NO Tigris creds and NO IG token. So
the app cannot use that CLI. THIS CLI is the M5 path: it talks to the deployed
backend over HTTP and never needs any secret beyond the operator's own login.

Flow (mirrors the server-side dry-run that PASSED 2026-06-26):
  1. POST /api/auth/login {email, pin}            -> admin JWT (never printed)
  2. For each local slide PNG:
       POST /api/war-room/upload-slide (multipart) -> public Tigris URL
  3. build_caption(slug) locally (pure stdlib, no backend deps)
  4. POST /api/war-room/publish-ig {slug, image_urls, caption, confirm}
       - confirm=False (DEFAULT): backend dry-validates, NEVER posts (Legge 5)
       - confirm=True  (--confirm): backend publishes the carousel

LEGGE 5 — nothing posts without --confirm. The flag maps 1:1 to the backend's
``confirm`` gate; a dry run exercises upload + the real Graph carousel assembly
(child + parent containers) but the backend never calls /media_publish.

CREDENTIALS (no secret ever printed, none persisted by this CLI):
  WR2_PUBLISH_EMAIL  — admin email (default: zero@balizero.com)
  WR2_PUBLISH_PIN    — admin login PIN/password (or via macOS Keychain, see below)
  WR2_BACKEND_URL    — backend base URL (default: https://nuzantara-rag.fly.dev)

If WR2_PUBLISH_PIN is unset, the PIN is read from the macOS Keychain item
``wr2-publish-pin`` (account = the email) via ``security find-generic-password``.

USAGE
    python scripts/wr2_ig_publish_remote.py <slug>            # DRY-RUN (default)
    python scripts/wr2_ig_publish_remote.py <slug> --confirm  # PUBLISH (operator click)
    python scripts/wr2_ig_publish_remote.py <slug> --print-caption
    python scripts/wr2_ig_publish_remote.py <slug> --caption-file /path/to/caption.txt

EXIT 0 = dry-run validated OR publish succeeded. EXIT 1 = failure (reason printed).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("wr2.ig.remote")

_DEFAULT_BACKEND = "https://nuzantara-rag.fly.dev"
_DEFAULT_EMAIL = "zero@balizero.com"
_KEYCHAIN_ITEM = "wr2-publish-pin"


def _carousel_root_from_env(env: Mapping[str, str], home: Path) -> Path:
    """Resolve the carousel root shared by cockpit and Mini launch environments."""
    if explicit_root := env.get("WR2_CAROUSEL_ROOT"):
        return Path(explicit_root)
    if war_room_root := env.get("WR2_WARROOM_ROOT"):
        return Path(war_room_root) / "carousel"
    return home / "Desktop/nuzantara/apps/war-room/output/carousel"


_CAROUSEL_ROOT = _carousel_root_from_env(os.environ, Path.home())


class PublishAborted(RuntimeError):
    """Raised when the run cannot proceed (missing creds, bad slug, HTTP error)."""


# ── Local slide discovery ──────────────────────────────────────────────────────


def _slug_dir(slug: str) -> Path:
    d = _CAROUSEL_ROOT / slug
    if not d.is_dir():
        raise PublishAborted(f"carousel dir not found: {d}")
    return d


def _discover_slide_pngs(slug_dir: Path) -> list[Path]:
    """Return the numbered slide PNGs (``<digits>.png``) in slide order.

    Matches the app's slide filter: any digit-stem PNG, sorted by int(stem). The
    re-render sweep guarantees a single padding scheme, so there are no dupes.
    """
    slides_dir = slug_dir / "slides"
    src = slides_dir if slides_dir.is_dir() else slug_dir
    pngs = [p for p in src.glob("*.png") if p.stem.isdigit()]
    if not pngs:
        raise PublishAborted(f"no numbered slide PNGs under {src}")
    pngs.sort(key=lambda p: int(p.stem))
    if len(pngs) > 10:
        raise PublishAborted(f"{len(pngs)} slides — IG carousel max is 10")
    return pngs


# ── Caption (pure, local) ──────────────────────────────────────────────────────


def _build_caption(slug: str) -> str:
    """Deterministic brand caption via the pure-stdlib author (no backend deps)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from wr2_ig_caption import build_caption  # noqa: PLC0415

    return build_caption(slug, base_dir=_CAROUSEL_ROOT)


def _resolve_caption(slug: str, caption_file: Path | None) -> str:
    """Return the generated caption or the exact UTF-8 operator override."""
    if caption_file is None:
        caption = _build_caption(slug)
        source = "generated caption"
    else:
        try:
            caption = caption_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise PublishAborted(f"cannot read caption file {caption_file}: {exc}") from exc
        source = "caption file"

    if not caption.strip():
        raise PublishAborted(f"{source} is empty")
    return caption


# ── Credentials (never printed, never persisted) ───────────────────────────────


def _resolve_pin(email: str) -> str:
    pin = os.environ.get("WR2_PUBLISH_PIN")
    if pin:
        return pin
    # Fall back to the macOS Keychain — value is captured, never logged.
    try:
        out = subprocess.run(
            [
                "security", "find-generic-password",
                "-s", _KEYCHAIN_ITEM, "-a", email, "-w",
            ],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PublishAborted(f"keychain lookup failed: {exc}") from exc
    pin = (out.stdout or "").strip()
    if not pin:
        raise PublishAborted(
            "no PIN: set WR2_PUBLISH_PIN or add Keychain item "
            f"'{_KEYCHAIN_ITEM}' for account '{email}' "
            f"(security add-generic-password -s {_KEYCHAIN_ITEM} -a {email} -w)"
        )
    return pin


# ── Backend HTTP ───────────────────────────────────────────────────────────────


async def _login(client: httpx.AsyncClient, base: str, email: str, pin: str) -> str:
    resp = await client.post(
        f"{base}/api/auth/login", json={"email": email, "pin": pin}, timeout=30
    )
    if resp.status_code != 200:
        raise PublishAborted(f"login failed: HTTP {resp.status_code} {resp.text[:160]}")
    data = resp.json().get("data") or {}
    token = data.get("token")
    if not token:
        raise PublishAborted("login response had no token")
    return token  # never logged


async def _upload_slide(
    client: httpx.AsyncClient, base: str, headers: dict[str, str],
    png: Path, draft_id: str, slide_index: int,
) -> str:
    with png.open("rb") as fh:
        files = {"file": (png.name, fh, "image/png")}
        data = {"draft_id": draft_id, "slide_index": str(slide_index)}
        resp = await client.post(
            f"{base}/api/war-room/upload-slide",
            headers=headers, files=files, data=data, timeout=120,
        )
    if resp.status_code != 200:
        raise PublishAborted(
            f"upload slide {slide_index} failed: HTTP {resp.status_code} {resp.text[:160]}"
        )
    url = resp.json().get("url")
    if not url:
        raise PublishAborted(f"upload slide {slide_index}: no url in response")
    logger.info("uploaded slide %d -> %s", slide_index, url)
    return url


async def _publish(
    client: httpx.AsyncClient, base: str, headers: dict[str, str],
    slug: str, image_urls: list[str], caption: str, confirm: bool,
) -> dict[str, Any]:
    resp = await client.post(
        f"{base}/api/war-room/publish-ig",
        headers=headers,
        json={
            "slug": slug,
            "image_urls": image_urls,
            "caption": caption,
            "confirm": confirm,
        },
        timeout=180,
    )
    if resp.status_code == 409:
        detail = resp.json().get("detail", {})
        raise PublishAborted(
            f"already published: {detail.get('permalink') or detail}"
        )
    if resp.status_code != 200:
        raise PublishAborted(f"publish failed: HTTP {resp.status_code} {resp.text[:240]}")
    return resp.json()


# ── Orchestration ──────────────────────────────────────────────────────────────


async def _run(args: argparse.Namespace) -> int:
    base = os.environ.get("WR2_BACKEND_URL", _DEFAULT_BACKEND).rstrip("/")
    email = os.environ.get("WR2_PUBLISH_EMAIL", _DEFAULT_EMAIL)
    slug = args.slug.strip()
    caption = _resolve_caption(slug, args.caption_file)

    if args.print_caption:
        sys.stdout.write(caption)
        return 0

    slug_dir = _slug_dir(slug)
    pngs = _discover_slide_pngs(slug_dir)
    pin = _resolve_pin(email)

    logger.info(
        "slug=%s slides=%d caption_chars=%d backend=%s confirm=%s",
        slug, len(pngs), len(caption), base, args.confirm,
    )

    # draft_id groups the slides under one Tigris prefix; deterministic per slug.
    draft_id = f"app-{slug}"[:64]

    async with httpx.AsyncClient() as client:
        token = await _login(client, base, email, pin)
        headers = {"Authorization": f"Bearer {token}"}

        image_urls: list[str] = []
        for idx, png in enumerate(pngs):
            url = await _upload_slide(client, base, headers, png, draft_id, idx)
            image_urls.append(url)

        result = await _publish(
            client, base, headers, slug, image_urls, caption, args.confirm
        )

    if not args.confirm:
        val = result.get("validation", {})
        logger.info(
            "DRY-RUN OK: backend validated %d slides (valid=%s). %s",
            result.get("would_publish", {}).get("slide_count", len(image_urls)),
            val.get("ok"),
            result.get("note", ""),
        )
        logger.info("Re-run with --confirm to PUBLISH (Legge 5 — explicit operator click).")
        return 0

    permalink = result.get("permalink") or result.get("post_url")
    logger.info("✅ PUBLISHED: %s", permalink or "(no permalink returned)")
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug", help="carousel dir name under output/carousel/")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="LEGGE 5 operator gate. Without it = dry-run (no post). With it = PUBLISH.",
    )
    parser.add_argument(
        "--caption-file",
        type=Path,
        help="UTF-8 file containing the exact operator-approved Instagram caption.",
    )
    parser.add_argument(
        "--print-caption",
        action="store_true",
        help="Print the resolved caption and exit without credentials, upload, or publish.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except PublishAborted as exc:
        logger.error("ABORTED: %s", exc)
        return 1
    except httpx.HTTPError as exc:
        # Network/transport failure (backend down, DNS, TLS) — clean message, not
        # a raw traceback (the app surfaces this stderr line to the operator).
        logger.error("ABORTED: backend unreachable: %s", exc)
        return 1
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        logger.exception("publish crashed: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
