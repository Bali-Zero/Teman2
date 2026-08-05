"""The wa-mirror source of the lead-intent matcher, and its Law 2 boundary.

Context that makes these tests load-bearing rather than decorative: on
2026-05-24 the wa-mirror was deliberately cut off from Fly (Symbiosis Law 2 /
UU PDP), so the live mirror exists only in the Pro's local Postgres. The
matcher reads it there through a second DSN — and the whole point of that
split is that WhatsApp-derived PII does NOT ride back out to the cloud.

Guilt and innocence are both asserted, because a guard that only proves it
bites has never proved it bites the right thing:

- guilt      a mirror row whose client_id is known locally matches its intent
- innocence  a mirror row WITHOUT a local client_id is skipped, and the phone
             lookup is never reached (that lookup runs against Fly)
- innocence  the meta_inbox path still resolves by phone — the fix must not
             silently disarm the source that was already working
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]
_MATCHER_PATH = _REPO_ROOT / "scripts" / "lead_intent_matcher.py"

_spec = importlib.util.spec_from_file_location("lead_intent_matcher", _MATCHER_PATH)
assert _spec is not None and _spec.loader is not None
lim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lim)


class _FakeAcquire:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def __aenter__(self) -> Any:
        return self._conn

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class _FakePool:
    def __init__(self, label: str) -> None:
        self.label = label
        self.closed = False

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self)

    async def close(self) -> None:
        self.closed = True


class _FakeMirrorConn:
    """Stands in for the mirror database at the asyncpg boundary.

    Rows carry the column names measured on the Pro's live
    `whatsapp_message_context` (2026-08-05), not invented ones.
    """

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.queries: list[str] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.queries.append(query)
        return self._rows


@pytest.fixture
def wiring(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Drive run() with both pools faked and every DB helper recorded."""
    state: dict[str, Any] = {
        "pools": [],
        "phone_lookups": [],
        "matches": [],
        "meta_msgs": [],
        "mirror_msgs": [],
        "intents": [],
    }

    async def _create_pool(dsn: str, **_kw: Any) -> _FakePool:
        pool = _FakePool(dsn)
        state["pools"].append(pool)
        return pool

    monkeypatch.setattr(lim.asyncpg, "create_pool", _create_pool)

    async def _ttl_intents(_conn: Any) -> list[dict[str, Any]]:
        return state["intents"]

    async def _meta(_conn: Any) -> list[dict[str, Any]]:
        return state["meta_msgs"]

    async def _mirror(_conn: Any) -> list[dict[str, Any]]:
        return state["mirror_msgs"]

    async def _resolve(_conn: Any, phone_norm: str | None) -> str | None:
        state["phone_lookups"].append(phone_norm)
        return "client-from-phone"

    async def _record(_conn: Any, *, intent: dict[str, Any], client: dict[str, Any], **kw: Any) -> None:
        state["matches"].append((intent["id"], client["id"], kw.get("match_method")))

    async def _nothing(_conn: Any) -> list[dict[str, Any]]:
        return []

    monkeypatch.setattr(lim, "_fetch_unmatched_intents_full_ttl", _ttl_intents)
    monkeypatch.setattr(lim, "_fetch_lead_id_messages_meta", _meta)
    monkeypatch.setattr(lim, "_fetch_lead_id_messages_mirror", _mirror)
    monkeypatch.setattr(lim, "_resolve_client_by_phone", _resolve)
    monkeypatch.setattr(lim, "_record_match", _record)
    monkeypatch.setattr(lim, "_fetch_unmatched_intents", _nothing)
    monkeypatch.setattr(lim, "_fetch_recent_wa_touches", _nothing)
    return state


def _intent(lead_id: str) -> dict[str, Any]:
    return {
        "id": lead_id,
        "source": "homepage_hero",
        "context": {},
        "utm": None,
        "fingerprint": None,
        "created_at": None,
    }


def _mirror_msg(lead_id: str, client_id: str | None) -> dict[str, Any]:
    """Exactly the shape `_fetch_lead_id_messages_mirror` hands back."""
    return {
        "lead_ids": [lead_id],
        "phone": None,
        "client_id": client_id,
        "msg_at": None,
        "source_table": "wa_mirror",
    }


@pytest.mark.asyncio
async def test_mirror_row_with_local_client_id_matches_its_intent(wiring: dict[str, Any]) -> None:
    """GUILT: the case that has never once fired in production."""
    wiring["intents"] = [_intent("li_p7nz6ul6rq")]
    wiring["mirror_msgs"] = [_mirror_msg("li_p7nz6ul6rq", "client-local-42")]

    result = await lim.run("postgres://fly/db", "postgres://127.0.0.1/mirror")

    assert wiring["matches"] == [("li_p7nz6ul6rq", "client-local-42", "lead_id")]
    assert result["matched_lead_id"] == 1
    assert result["lead_id_messages_mirror"] == 1
    assert wiring["phone_lookups"] == []


@pytest.mark.asyncio
async def test_mirror_row_without_client_id_never_reaches_the_phone_lookup(
    wiring: dict[str, Any],
) -> None:
    """INNOCENCE (the Law 2 line): unresolved locally means unresolved, full stop.

    The phone lookup runs against Fly. Reaching it for a mirror-sourced sender
    would carry a WhatsApp-derived number off the machine the 2026-05-24
    cutover confines it to — so its absence, not merely the absence of a match,
    is what this asserts.
    """
    wiring["intents"] = [_intent("li_pgzr0j2494")]
    wiring["mirror_msgs"] = [_mirror_msg("li_pgzr0j2494", None)]

    result = await lim.run("postgres://fly/db", "postgres://127.0.0.1/mirror")

    assert wiring["phone_lookups"] == []
    assert wiring["matches"] == []
    assert result["lead_id_unresolved_sender"] == 1
    assert result["matched_lead_id"] == 0


@pytest.mark.asyncio
async def test_meta_inbox_row_still_resolves_by_phone(wiring: dict[str, Any]) -> None:
    """INNOCENCE: the Fly-side source is untouched by the mirror guard.

    Without this, tightening the mirror path could disarm meta_inbox and the
    two other tests would still pass.
    """
    wiring["intents"] = [_intent("li_metaonly01")]
    wiring["meta_msgs"] = [
        {
            "lead_ids": ["li_metaonly01"],
            "phone": "628123456789",
            "client_id": None,
            "msg_at": None,
            "source_table": "meta_inbox",
        }
    ]

    result = await lim.run("postgres://fly/db", "postgres://127.0.0.1/mirror")

    assert wiring["phone_lookups"] == ["8123456789"]
    assert wiring["matches"] == [("li_metaonly01", "client-from-phone", "lead_id")]
    assert result["lead_id_messages_mirror"] == 0


@pytest.mark.asyncio
async def test_both_pools_are_closed(wiring: dict[str, Any]) -> None:
    """A second pool that leaks would exhaust the Pro's local connections."""
    await lim.run("postgres://fly/db", "postgres://127.0.0.1/mirror")

    assert len(wiring["pools"]) == 2
    assert all(p.closed for p in wiring["pools"])


@pytest.mark.asyncio
async def test_without_mirror_dsn_only_one_pool_is_opened(wiring: dict[str, Any]) -> None:
    """Unset second DSN stays a valid configuration, not a crash."""
    result = await lim.run("postgres://fly/db")

    assert len(wiring["pools"]) == 1
    assert result["lead_id_messages_mirror"] == 0


@pytest.mark.asyncio
async def test_mirror_fetch_drops_the_body_and_returns_no_phone() -> None:
    """The extraction boundary: bodies are consumed here, never handed on.

    `phone is None` is the assertion that matters — it is what makes the
    guard in run() unreachable-by-accident rather than merely unused.
    """
    conn = _FakeMirrorConn(
        [
            {
                "text": "Hi Bali Zero\n\nLead ID: li_wd5mklrxpk",
                "client_id": "client-local-7",
                "msg_at": None,
            }
        ]
    )

    rows = await lim._fetch_lead_id_messages_mirror(conn)

    assert rows == [
        {
            "lead_ids": ["li_wd5mklrxpk"],
            "phone": None,
            "client_id": "client-local-7",
            "msg_at": None,
            "source_table": "wa_mirror",
        }
    ]
    assert "text" not in rows[0]
    assert "whatsapp_message_context" in conn.queries[0]
