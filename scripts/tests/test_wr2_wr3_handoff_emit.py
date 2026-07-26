"""WR2 → WR3 ignition: the emitting end of `wr2_episode_published`.

Migration 186 shipped the channel, the SQL helper, the WR3 supervisor's LISTEN
and the `wr3-design-architect` route in 2026-05. Nothing ever emitted the event,
so WR3 produced zero episodes for 57 days. `scripts/wr2_ig_publish.py` is now the
emitter, and this file is its guilt-and-innocence corpus.

GUILT   — a fully published carousel with a complete brief emits a payload that
          satisfies the dispatcher's contract, verbatim.
INNOCENCE — the emitter stays silent when it is switched off, when the brief
          cannot satisfy the contract, and when the database refuses; and a
          failure in here never turns a successful Instagram publish into a
          failed run (the post already exists — that is the whole reason the
          call site is best-effort).
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]


def _load_module(name: str) -> Any:
    """Import a scripts/ module by path (scripts/ is not a package)."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def pub(monkeypatch: pytest.MonkeyPatch) -> Any:
    """wr2_ig_publish with its hard env preconditions satisfied."""
    monkeypatch.setenv("WR2_IG_CONTENT_PUBLISH_VERIFIED", "1")
    return _load_module("wr2_ig_publish")


@pytest.fixture
def carousel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """A complete on-disk carousel: brief, slides.json, 10 slide PNGs."""
    slug = "2026-07-26-bkpm-paid-up-capital-2-5-mld"
    root = tmp_path / "carousel"
    d = root / slug
    (d / "slides").mkdir(parents=True)
    (d / "brief.json").write_text(
        json.dumps({"domain": "company", "audience_segment": "founder"}),
        encoding="utf-8",
    )
    (d / "slides.json").write_text(json.dumps({"slides": []}), encoding="utf-8")
    for i in range(1, 11):
        (d / "slides" / f"{i:02d}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setenv("WR2_CAROUSEL_ROOT", str(root))
    return slug


# ── GUILT ────────────────────────────────────────────────────────────────


def test_payload_satisfies_the_dispatchers_contract_verbatim(pub, carousel) -> None:
    """The keys are not a local opinion — they come from the consumer.

    Anchoring on `wr3_companion_dispatcher.REQUIRED_PAYLOAD_KEYS` is what stops
    the two ends of the nerve from drifting apart again.
    """
    dispatcher = _load_module("wr3_companion_dispatcher")
    payload = pub._build_wr3_handoff_payload(carousel)
    assert payload is not None
    assert set(payload) == set(dispatcher.REQUIRED_PAYLOAD_KEYS)


def test_payload_carries_the_real_carousel_shape(pub, carousel) -> None:
    payload = pub._build_wr3_handoff_payload(carousel)
    assert payload["slug"] == carousel
    assert payload["slides_count"] == 10
    assert payload["domain"] == "company"
    assert payload["audience_segment"] == "founder"
    # Paths are repo-relative — the dispatcher resolves them against the repo
    # root, never against the publisher's cwd.
    assert payload["hero_image_path"] == (
        f"apps/war-room/output/carousel/{carousel}/slides/01.png"
    )
    assert payload["brief_path"] == f"apps/war-room/output/carousel/{carousel}/brief.json"
    assert payload["slides_path"] == f"apps/war-room/output/carousel/{carousel}/slides.json"


def test_enabled_emitter_calls_the_migration_186_helper(
    pub, carousel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WR2_WR3_HANDOFF_ENABLED", "1")
    seen: dict[str, Any] = {}

    class _Conn:
        async def fetchval(self, sql: str, arg: str) -> int:
            seen["sql"] = sql
            seen["payload"] = json.loads(arg)
            return 4242

        async def close(self) -> None:
            seen["closed"] = True

    async def _connect(_dsn: str) -> _Conn:
        return _Conn()

    monkeypatch.setattr(pub, "_pg_dsn_for_handoff", lambda: "postgres://x", raising=False)
    monkeypatch.setattr(pub, "_connect_for_handoff", _connect, raising=False)

    asyncio.run(pub._emit_wr3_handoff(carousel))

    assert "publish_wr2_episode_published_event" in seen["sql"]
    assert seen["payload"]["slug"] == carousel
    assert seen["closed"] is True, "connection must be closed even on the happy path"


def test_the_emitter_is_actually_wired_into_the_publish_path() -> None:
    """An emitter nobody calls is the defect this whole change exists to cure.

    WR3 sat idle for 57 days because the channel, the SQL helper, the LISTEN and
    the route all existed while nothing emitted. A unit test on the function
    alone would have stayed green through exactly that. This asserts the call
    site itself, and its position: after the publish is recorded, before the
    `IG_URL=` stdout contract line the app parses.
    """
    src = (_SCRIPTS / "wr2_ig_publish.py").read_text(encoding="utf-8")
    call = src.find("await _emit_wr3_handoff(slug)")
    assert call != -1, "publish path no longer emits wr2_episode_published"

    marked = src.find("_mark_queue_published(slug=slug")
    contract_line = src.find('print(f"IG_URL={permalink}")')
    assert marked != -1 and contract_line != -1
    assert marked < call < contract_line, (
        "the handoff must fire after the publish is fully recorded and before "
        "the stdout contract line"
    )


# ── INNOCENCE ────────────────────────────────────────────────────────────


def test_disabled_by_default_touches_no_database(
    pub, carousel, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The firebreak: unset env must not reach Postgres at all.

    Arming this today would ship 15-second stories against a ruled 60-150 s
    contract, so "off" has to mean off — not "connects, then decides".
    """
    monkeypatch.delenv("WR2_WR3_HANDOFF_ENABLED", raising=False)
    connects: list[str] = []

    # Two things this test learned the hard way, both by mutation.
    #
    # 1. The DSN seam is stubbed to a WORKING value on purpose. Without it the
    #    emitter dies earlier on config import and this test passes for the
    #    wrong reason — the env check must be the ONLY thing in the way.
    # 2. The trap RECORDS instead of raising. `_emit_wr3_handoff` is
    #    best-effort by design and catches `Exception`, which includes
    #    `AssertionError` — a raising trap would be swallowed by the very
    #    guard it is meant to test, and stay green under a default-ON
    #    mutation. Assert after the call, never inside it.
    def _record(dsn: str) -> Any:
        connects.append(dsn)
        raise RuntimeError("unreachable in the disabled path")

    monkeypatch.setattr(pub, "_pg_dsn_for_handoff", lambda: "postgres://x", raising=False)
    monkeypatch.setattr(pub, "_connect_for_handoff", _record, raising=False)
    asyncio.run(pub._emit_wr3_handoff(carousel))

    assert connects == [], "disabled handoff must not open a connection"


@pytest.mark.parametrize(
    "brief",
    [
        {"audience_segment": "founder"},          # domain missing
        {"domain": "company"},                    # audience_segment missing
        {"domain": "", "audience_segment": ""},   # present but empty
    ],
    ids=["no-domain", "no-audience", "empty-strings"],
)
def test_incomplete_brief_is_skipped_not_half_emitted(
    pub, carousel, tmp_path: Path, brief: dict[str, str]
) -> None:
    """2 of 23 real briefs lack one of these fields.

    Both the SQL helper and the dispatcher treat them as required, so a partial
    payload would raise downstream. Skipping is the only honest outcome.
    """
    root = Path(pub._carousel_root())
    (root / carousel / "brief.json").write_text(json.dumps(brief), encoding="utf-8")
    assert pub._build_wr3_handoff_payload(carousel) is None


def test_unreadable_brief_is_skipped(pub, carousel) -> None:
    (Path(pub._carousel_root()) / carousel / "brief.json").write_text("{ not json", encoding="utf-8")
    assert pub._build_wr3_handoff_payload(carousel) is None


def test_carousel_without_slides_is_skipped(pub, carousel) -> None:
    for p in (Path(pub._carousel_root()) / carousel / "slides").glob("*.png"):
        p.unlink()
    assert pub._build_wr3_handoff_payload(carousel) is None


def test_missing_claim_ids_still_emits_with_empty_list(pub, carousel) -> None:
    """0 of 23 WR2 briefs carry claim ids today.

    Empty is a real degradation (WR3 falls back to story_15s) but it is not a
    reason to withhold the event — the emitter logs it and passes an explicit
    empty list rather than omitting the key.
    """
    payload = pub._build_wr3_handoff_payload(carousel)
    assert payload is not None
    assert payload["primary_claim_ids"] == []


def test_claim_ids_are_inherited_when_wr2_finally_emits_them(pub, carousel) -> None:
    root = Path(pub._carousel_root())
    (root / carousel / "brief.json").write_text(
        json.dumps({
            "domain": "company",
            "audience_segment": "founder",
            "primary_claim_ids": ["bkpm-5-2025-paid-up", "kbli-46100-pma"],
        }),
        encoding="utf-8",
    )
    payload = pub._build_wr3_handoff_payload(carousel)
    assert payload is not None
    assert payload["primary_claim_ids"] == ["bkpm-5-2025-paid-up", "kbli-46100-pma"]


def test_database_failure_never_fails_the_publish(
    pub, carousel, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The post is already live on Instagram by the time this runs.

    Asserting the attempt HAPPENED matters as much as asserting nothing
    escaped: a test that only checks "did not raise" also passes when the
    emitter silently skipped and never touched the failing path at all.
    """
    monkeypatch.setenv("WR2_WR3_HANDOFF_ENABLED", "1")
    attempts: list[str] = []
    monkeypatch.setattr(pub, "_pg_dsn_for_handoff", lambda: "postgres://x", raising=False)

    def _explode(dsn: str) -> Any:
        attempts.append(dsn)
        raise RuntimeError("connection refused")

    monkeypatch.setattr(pub, "_connect_for_handoff", _explode, raising=False)
    asyncio.run(pub._emit_wr3_handoff(carousel))

    assert attempts == ["postgres://x"], "the failing path must actually be exercised"


def test_no_dsn_is_a_skip_not_a_crash(
    pub, carousel, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No DSN is a logged skip — never a connect attempt against nothing."""
    monkeypatch.setenv("WR2_WR3_HANDOFF_ENABLED", "1")
    connects: list[Any] = []
    monkeypatch.setattr(pub, "_pg_dsn_for_handoff", lambda: None, raising=False)
    monkeypatch.setattr(
        pub, "_connect_for_handoff", lambda dsn: connects.append(dsn), raising=False
    )
    asyncio.run(pub._emit_wr3_handoff(carousel))

    assert connects == [], "a missing DSN must short-circuit before connecting"
