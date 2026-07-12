"""Tests for the scripts/wr2_ig_publish.py operator-gated CLI.

Covers:
  (b) the CLI is dry-run without --confirm (never publishes, never writes ledger).

Also covers the two hard stops:
  - token-scope gate aborts when neither WR2_IG_CONTENT_PUBLISH_VERIFIED=1 nor
    Instagram creds resolve;
  - --confirm fails closed when the ledger DB is unreachable (no DSN).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

# Load scripts/wr2_ig_publish.py as a module without polluting global sys.path
# beyond the scripts dir. Repo root = 6 parents up from this test file:
# publisher(0) services(1) tests(2) backend(3) backend-rag(4) apps(5) repo(6).
_REPO_ROOT = Path(__file__).resolve().parents[6]
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "wr2_ig_publish", _SCRIPTS / "wr2_ig_publish.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_carousel(tmp_path: Path, slug: str, n_slides: int = 3) -> Path:
    """Create a minimal on-disk carousel: slides.json + numbered PNGs."""
    root = tmp_path / "carousel"
    slug_dir = root / slug
    slides_dir = slug_dir / "slides"
    slides_dir.mkdir(parents=True)
    (slug_dir / "slides.json").write_text(
        json.dumps({"carousel_id": slug, "slide_count": n_slides, "slides": []}),
        encoding="utf-8",
    )
    png_magic = b"\x89PNG\r\n\x1a\n"
    for i in range(1, n_slides + 1):
        (slides_dir / f"{i:02d}.png").write_bytes(png_magic + f"slide{i}".encode())
    return root


def test_dry_run_never_publishes_or_writes_ledger(tmp_path, monkeypatch) -> None:
    """(b) Without --confirm: uploads to Tigris + builds draft, but NEVER calls
    publish() and NEVER touches the ledger."""
    cli = _load_cli()
    root = _make_carousel(tmp_path, "dry-run-test-slug")
    monkeypatch.setenv("WR2_CAROUSEL_ROOT", str(root))
    # Satisfy the token gate via the verified-override (no real creds needed).
    monkeypatch.setenv("WR2_IG_CONTENT_PUBLISH_VERIFIED", "1")

    # Stub Tigris so no network call happens; record that it WAS called.
    upload_calls: list[int] = []

    def _fake_upload(png_paths, *, draft_id):  # type: ignore[no-untyped-def]
        upload_calls.append(len(png_paths))
        return [f"https://tigris/{draft_id}/{i:02d}.png" for i in range(len(png_paths))]

    monkeypatch.setattr(cli, "_upload_slides_to_tigris", _fake_upload)

    # Tripwires: these MUST NOT be invoked in a dry run.
    async def _explode_ledger(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("dry-run must NOT call the ledger precondition")

    monkeypatch.setattr(cli, "_ledger_precondition", _explode_ledger)

    # If IGPublisher were ever constructed/called, fail loudly. The CLI imports
    # it lazily inside _run's confirm branch, so patch the source symbol.
    def _explode_publisher(*a, **k):  # type: ignore[no-untyped-def]
        raise AssertionError("dry-run must NOT construct/call IGPublisher")

    monkeypatch.setattr(
        "backend.services.publisher.ig_publisher.IGPublisher",
        _explode_publisher,
        raising=True,
    )

    rc = cli.main(["dry-run-test-slug"])  # no --confirm

    # rc==0 + the ledger/publisher tripwires never firing proves the dry run
    # uploaded to Tigris and built the draft but neither wrote the ledger nor
    # published.
    assert rc == 0
    assert upload_calls == [3], "dry-run should still upload all 3 slides to Tigris"


def test_token_gate_aborts_without_verification(tmp_path, monkeypatch) -> None:
    """Hard stop: no WR2_IG_CONTENT_PUBLISH_VERIFIED and no creds -> exit 1."""
    cli = _load_cli()
    root = _make_carousel(tmp_path, "gate-test-slug")
    monkeypatch.setenv("WR2_CAROUSEL_ROOT", str(root))
    monkeypatch.delenv("WR2_IG_CONTENT_PUBLISH_VERIFIED", raising=False)
    for k in (
        "IG_USER_ID",
        "INSTAGRAM_ACCOUNT_ID",
        "IG_LONG_LIVED_TOKEN",
        "INSTAGRAM_ACCESS_TOKEN",
    ):
        monkeypatch.delenv(k, raising=False)

    rc = cli.main(["gate-test-slug"])
    assert rc == 1


def test_confirm_fails_closed_when_ledger_db_unreachable(tmp_path, monkeypatch) -> None:
    """--confirm with no DSN must FAIL CLOSED (never publish without the guard)."""
    cli = _load_cli()
    root = _make_carousel(tmp_path, "confirm-noledger-slug")
    monkeypatch.setenv("WR2_CAROUSEL_ROOT", str(root))
    monkeypatch.setenv("WR2_IG_CONTENT_PUBLISH_VERIFIED", "1")

    # Stub Tigris (upload happens before the ledger gate).
    monkeypatch.setattr(
        cli,
        "_upload_slides_to_tigris",
        lambda png_paths, *, draft_id: [
            f"https://tigris/{i:02d}.png" for i in range(len(png_paths))
        ],
    )

    # Force "no DSN": clear env and clear settings.database_url.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from backend.app.core.config import settings

    monkeypatch.setattr(settings, "database_url", None, raising=False)

    # Publisher must NEVER be reached because the ledger gate fails first.
    monkeypatch.setattr(
        "backend.services.publisher.ig_publisher.IGPublisher",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("must not publish when ledger DB unreachable")
        ),
        raising=True,
    )

    rc = cli.main(["confirm-noledger-slug", "--confirm"])
    assert rc == 1
