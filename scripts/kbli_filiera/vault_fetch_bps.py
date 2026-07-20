#!/usr/bin/env python3
"""vault_fetch_bps.py — Batch-0 vault compiler: BPS Tabel Konversi registrar (stub).

BPS's tabel-konversi page (bps.go.id) sits behind Cloudflare Turnstile —
NO headless HTTP fetcher is built for it here, on purpose: an automated
fetch would either be blocked (useless) or, worse, silently succeed against
a challenge page and store garbage as if it were the real PDF — a false
"fetched" signal is worse than no fetch. This script never attempts one.

Two official URLs ONLY (id + en publication pages). No third-party mirror
is ever accepted as a vault source (P4, "no silent mirrors" —
research/operations/2026-07-16-kbli-filiera-methodology.md) — enforced by
`validate_source_url`, not just documented.

Workflow:
  1. `python vault_fetch_bps.py` (no args) prints the two official URLs and
     the registration instructions.
  2. A browser-assisted step (operator, or a browser-driving agent)
     downloads the PDF by hand to any local path.
  3. `python vault_fetch_bps.py --register <downloaded.pdf> --source-url <one of the two URLs>`
     ingests it into <vault-root>/bps/ with full provenance (url, fetch
     date, sha256, fetched_via: "browser-manual").

Usage:
    python scripts/kbli_filiera/vault_fetch_bps.py
    python scripts/kbli_filiera/vault_fetch_bps.py --register ~/Downloads/tabel-konversi.pdf \\
        --source-url https://www.bps.go.id/id/publication/2026/04/22/909d503355d2b7664e43dea8/tabel-konversi-kbli-2020-kbli-2025.html
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

try:
    from kbli_filiera import vault_common as common
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from kbli_filiera import vault_common as common

OFFICIAL_URLS: tuple[str, ...] = (
    "https://www.bps.go.id/id/publication/2026/04/22/909d503355d2b7664e43dea8/tabel-konversi-kbli-2020-kbli-2025.html",
    # NOTE: the EN slug has a TRIPLE dash ("2020---kbli"), not a typo — live-probed
    # 2026-07-16 (vault-scout). A single-dash lookalike is a plausible fetch typo
    # AND a plausible phishing-style lookalike; validate_source_url refuses it
    # (pinned in tests/test_vault_fetch_bps.py).
    "https://www.bps.go.id/en/publication/2026/04/22/909d503355d2b7664e43dea8/tabel-konversi-kbli-2020---kbli-2025.html",
)

LOG = common.setup_logger("vault_fetch_bps")


def instructions() -> str:
    lines = [
        "BPS Tabel Konversi KBLI 2020-2025 is behind Cloudflare Turnstile —",
        "no headless fetcher is built or supported for it here (a silent",
        "failure there would itself become a false ABSENT/fetched signal).",
        "Fetch by hand (browser-assisted or operator download):",
        "",
    ]
    lines += [f"  - {u}" for u in OFFICIAL_URLS]
    lines += [
        "",
        "Then register the downloaded file into the vault:",
        "  python vault_fetch_bps.py --register <downloaded.pdf> --source-url <one of the URLs above>",
    ]
    return "\n".join(lines)


def validate_source_url(url: str) -> bool:
    """No silent mirrors (P4): only the two official BPS URLs are accepted
    as vault provenance — a third-party mirror, even a byte-faithful copy,
    is refused. Enforced here, not just documented in the docstring."""
    return url in OFFICIAL_URLS


def build_bps_record(dest: Path, vault_root: Path, source_url: str, data: bytes, fetched_at: str) -> dict:
    """Pure record-shape builder — no I/O — so the provenance shape is
    directly unit-testable without touching the filesystem."""
    return {
        "filename": dest.name,
        "url": source_url,
        "source_url": source_url,
        "bytes": len(data),
        "sha256": common.sha256_bytes(data),
        "fetched_at": fetched_at,
        "fetched_via": "browser-manual",
        "http_status": 200,
        "rel_path": dest.relative_to(vault_root).as_posix(),
    }


def register(vault_root: Path, src: Path, source_url: str, *, fetched_at: str | None = None) -> dict:
    if not validate_source_url(source_url):
        raise ValueError(
            f"refusing to register: {source_url!r} is not one of the two official BPS URLs "
            f"(no silent mirrors) -- allowed: {OFFICIAL_URLS}"
        )
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"--register target not found: {src}")

    data = src.read_bytes()
    dest = vault_root / "bps" / common.sanitize_filename(src.name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)

    rec = build_bps_record(dest, vault_root, source_url, data, fetched_at or common.now_iso())
    common.append_jsonl(vault_root / "bps" / "fetch-log.jsonl", rec)
    LOG.info("registered %s -> %s (sha256=%s)", src, dest, rec["sha256"][:12])
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault-root", type=Path, default=common.DEFAULT_VAULT_ROOT)
    ap.add_argument("--register", type=Path, default=None, help="path to a manually-downloaded BPS PDF")
    ap.add_argument("--source-url", type=str, default=None, help="which of the two official URLs it came from")
    args = ap.parse_args(argv)

    if args.register is None:
        print(instructions())
        return 0

    if not args.source_url:
        LOG.error("--register requires --source-url (one of the two official BPS URLs)")
        return 2

    try:
        register(args.vault_root.expanduser(), args.register, args.source_url)
    except (ValueError, FileNotFoundError) as exc:
        LOG.error(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
