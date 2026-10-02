"""T3 promise gate — P2 PR-C precision audit, opt-in real-Postgres half. Skipped
unless a local `pg_ctl`/`initdb` are on PATH AND WA_TEAM_PROMISES_REAL_PG=1 —
same gate and throwaway-cluster pattern as test_wa_team_promises_audit_real_pg.py.

Covers what a fake pool cannot prove: the sample SQL (resolved rows only, evidence
joined, per-kind, bounded, random), that the audit writes nothing to team_promises,
and the digest consumer reading the stored counts. The model is a recorded fake.
Synthetic fixtures only.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest

_PG_CTL = shutil.which("pg_ctl")
_INITDB = shutil.which("initdb")
pytestmark = pytest.mark.skipif(
    os.environ.get("WA_TEAM_PROMISES_REAL_PG") != "1" or not (_PG_CTL and _INITDB),
    reason="opt-in: set WA_TEAM_PROMISES_REAL_PG=1 with pg_ctl/initdb on PATH",
)

if _PG_CTL and _INITDB:
    import asyncpg

    import scripts.wa_team_promises as wtp
    from scripts.wa_team_promises import run_init_schema

T0 = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
NOW = T0 + timedelta(days=30)


def _h(hours):
    return T0 + timedelta(hours=hours)


@pytest.fixture(scope="module")
def pg_socket_dir(tmp_path_factory):
    data = tmp_path_factory.mktemp("wa_team_promises_audit_real_pg")
    sockdir = tempfile.mkdtemp(prefix="watppa_")
    subprocess.run([_INITDB, "-D", str(data), "-U", "postgres", "--auth=trust"],
                    check=True, capture_output=True)
    subprocess.run([_PG_CTL, "-D", str(data), "-w", "-o", f"-k {sockdir} -h ''",
                     "-l", str(data / "log"), "start"], check=True, capture_output=True)
    try:
        yield sockdir
    finally:
        subprocess.run([_PG_CTL, "-D", str(data), "-m", "immediate", "stop"], capture_output=True, check=False)
        shutil.rmtree(sockdir, ignore_errors=True)


@asynccontextmanager
async def _fresh_database(sockdir, name: str):
    admin = await asyncpg.connect(host=str(sockdir), user="postgres", database="postgres")
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
        await admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        await admin.close()
    pool = await asyncpg.create_pool(host=str(sockdir), user="postgres", database=name,
                                      min_size=1, max_size=1)
    try:
        yield pool
    finally:
        await pool.close()
        admin2 = await asyncpg.connect(host=str(sockdir), user="postgres", database="postgres")
        try:
            await admin2.execute(f'DROP DATABASE IF EXISTS "{name}"')
        finally:
            await admin2.close()


_DDL = """
CREATE TABLE whatsapp_message_context (
    id                BIGINT PRIMARY KEY,
    direction         TEXT,
    body              TEXT,
    message_text      TEXT,
    media_type        TEXT,
    message_date      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    team_member_phone TEXT,
    counterpart_phone TEXT,
    counterpart_lid   TEXT,
    group_jid         TEXT,
    client_id         BIGINT,
    team_member_email TEXT
);
CREATE TABLE team_members (email TEXT PRIMARY KEY, name TEXT);
"""


async def _setup(pool) -> None:
    await run_init_schema(pool)
    async with pool.acquire() as conn:
        await conn.execute(_DDL)


async def _msg(pool, msg_id, direction, at, *, text=None, media=None, line="line-1", peer="peer-1",
               lid=None, group=None) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO whatsapp_message_context (id, direction, body, media_type, message_date, "
            "team_member_phone, counterpart_phone, counterpart_lid, group_jid) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
            msg_id, direction, text, media, at, line, peer, lid, group,
        )


async def _promise_on(pool, msg_id, *, ptype="send", due=None, email=None, resolved=False,
                      resolved_at=None, by=None, kind=None) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO team_promises (message_id, promise_text, promise_type, due_at, "
            "team_member_email, resolved, resolved_at, resolved_by_message_id, resolution_kind) "
            "VALUES ($1, 'x', $2, $3, $4, $5, $6, $7, $8) RETURNING promise_id",
            msg_id, ptype, due or _h(24), email, resolved, resolved_at, by, kind,
        )


async def _promise(pool, msg_id=1, **kw) -> int:
    await _msg(pool, msg_id, "outbound", T0, text="I will send it tomorrow")
    return await _promise_on(pool, msg_id, **kw)


async def _state(pool, promise_id):
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT resolved, resolved_at, resolved_by_message_id, resolution_kind "
            "FROM team_promises WHERE promise_id = $1", promise_id)
    return (r["resolved"], r["resolved_at"], r["resolved_by_message_id"], r["resolution_kind"])


OPEN = (False, None, None, None)


@pytest.fixture(autouse=True)
def _state(tmp_path, monkeypatch):
    monkeypatch.setattr(wtp, "_AUDIT_STATE_FILE", tmp_path / "audit.json")
    monkeypatch.setattr(wtp, "STATE_DIR", tmp_path)


class _Model:
    """Records every call and answers from a script; unscripted calls say True."""

    def __init__(self, answers=None):
        self.calls, self._answers = [], list(answers or [])

    def __call__(self, _opener, promise_type, promise_text, evidence):
        self.calls.append((promise_type, promise_text, evidence))
        return self._answers.pop(0) if self._answers else True


async def _resolved(pool, n, kind, *, ptype="send", evid_text=None, evid_media=None, evid_dir="outbound",
                    text="I will send it tomorrow"):
    """One resolved promise (message 10n) with its evidence message (10n+1)."""
    await _msg(pool, 10 * n, "outbound", T0, text=text, peer=f"peer-{n}")
    await _msg(pool, 10 * n + 1, evid_dir, _h(2), text=evid_text, media=evid_media, peer=f"peer-{n}")
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO team_promises (message_id, promise_text, promise_type, due_at, resolved, "
            "resolved_at, resolved_by_message_id, resolution_kind) VALUES ($1, $2, $3, $4, true, $5, $6, $7)",
            10 * n, text, ptype, _h(24), _h(2), 10 * n + 1, kind)


async def _snapshot(pool):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM team_promises ORDER BY promise_id")
    return [tuple(r.values()) for r in rows]


def _static_sql():
    return wtp._AUDIT_SAMPLE_SQL.lower()


def test_the_sample_sql_is_a_read_that_picks_at_random_and_is_bounded():
    sql = _static_sql()
    assert sql.lstrip().startswith("select")
    assert not any(w in sql for w in ("insert", "update", "delete", "truncate", "alter", "drop"))
    assert "order by random()" in sql and "limit $2" in sql and "resolution_kind = $1" in sql


@pytest.mark.asyncio
async def test_each_kind_is_sampled_apart_and_unresolved_rows_never(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "aud_kinds") as pool:
        await _setup(pool)
        for i in range(1, 4):
            await _resolved(pool, i, "media_sent", evid_media="document")
        await _resolved(pool, 4, "team_confirmed", evid_text="already sent")
        await _resolved(pool, 5, "client_ack", evid_text="ok thanks", evid_dir="inbound")
        await _promise(pool, 6)  # open: never sampled
        model = _Model()
        res = await wtp.run_audit_resolution(pool, sample=100, call=model)
        assert {k: v.judged for k, v in res.items()} == {"media_sent": 3, "team_confirmed": 1, "client_ack": 1}
        assert len(model.calls) == 5


@pytest.mark.asyncio
async def test_the_sample_is_bounded_per_kind(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "aud_bound") as pool:
        await _setup(pool)
        for i in range(1, 8):
            await _resolved(pool, i, "media_sent", evid_media="image")
        model = _Model()
        res = await wtp.run_audit_resolution(pool, sample=3, call=model)
        assert res["media_sent"].judged == 3 and len(model.calls) == 3
        assert res["team_confirmed"].judged == 0 and res["client_ack"].judged == 0


@pytest.mark.asyncio
async def test_the_sample_is_random_not_the_first_rows(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "aud_random") as pool:
        await _setup(pool)
        for i in range(1, 31):
            await _resolved(pool, i, "media_sent", evid_media="document")
        picks = set()
        for _ in range(8):
            async with pool.acquire() as conn:
                rows = await conn.fetch(wtp._AUDIT_SAMPLE_SQL, "media_sent", 3)
            picks.add(tuple(sorted(r["promise_id"] for r in rows)))
        assert len(picks) > 1


@pytest.mark.asyncio
async def test_the_audit_writes_nothing_to_team_promises(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "aud_ro") as pool:
        await _setup(pool)
        await _resolved(pool, 1, "media_sent", evid_media="document")
        await _resolved(pool, 2, "team_confirmed", evid_text="already sent")
        await _promise(pool, 3)
        before = await _snapshot(pool)
        await wtp.run_audit_resolution(pool, sample=100, call=_Model([False, True]))
        assert await _snapshot(pool) == before


@pytest.mark.asyncio
async def test_the_sampling_runs_in_a_read_only_transaction(pg_socket_dir, monkeypatch):
    async with _fresh_database(pg_socket_dir, "aud_txn") as pool:
        await _setup(pool)
        await _resolved(pool, 1, "media_sent", evid_media="document")
        before = await _snapshot(pool)
        # a statement that would write, were the transaction not read-only
        monkeypatch.setattr(wtp, "_AUDIT_SAMPLE_SQL",
                            "UPDATE team_promises SET resolved = false WHERE resolution_kind = $1 "
                            "AND $2 > 0 RETURNING promise_id, promise_type, promise_text, "
                            "'x'::text AS evidence_text, 'document'::text AS evidence_media_type")
        with pytest.raises(asyncpg.exceptions.ReadOnlySQLTransactionError):
            await wtp.run_audit_resolution(pool, sample=5, call=_Model())
        assert await _snapshot(pool) == before


@pytest.mark.asyncio
async def test_media_evidence_is_described_by_type_and_text_evidence_is_passed(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "aud_evidence") as pool:
        await _setup(pool)
        await _resolved(pool, 1, "media_sent", evid_media="document", text="I will send the file")
        await _resolved(pool, 2, "team_confirmed", ptype="check", evid_text="gia controllato",
                        text="I will check it")
        model = _Model()
        await wtp.run_audit_resolution(pool, sample=100, call=model)
        assert ("send", "I will send the file", {"kind": "media", "media_type": "document"}) in model.calls
        assert ("check", "I will check it", {"kind": "text", "text": "gia controllato"}) in model.calls


@pytest.mark.asyncio
async def test_a_media_caption_is_passed_with_the_media_type(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "aud_caption") as pool:
        await _setup(pool)
        await _resolved(pool, 1, "media_sent", evid_media="document", evid_text="here is the file",
                        text="I will send the file")
        model = _Model()
        await wtp.run_audit_resolution(pool, sample=100, call=model)
        assert model.calls == [("send", "I will send the file",
                                {"kind": "media", "media_type": "document", "text": "here is the file"})]


# PII canary on the REAL audit path (the model's HTTP edge is the only fake): promise and
# evidence text carry a sentinel that must reach nothing but the request to the local model.
CANARY = "canary-7f3a-4242-+00-INVALID"


class _NoClose:
    def __init__(self, pool):
        self._pool = pool

    def acquire(self):
        return self._pool.acquire()

    async def close(self):
        return None


class _Resp:
    def __init__(self, status, body):
        self.status, self._body = status, body

    def read(self, size=-1):
        return self._body

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _CanaryOpener:
    """Answers from `reply`; records the request bodies so the test can prove the
    canary DID go to the model (else the leak assertions would be vacuous)."""

    def __init__(self, reply=None, exc=None):
        self._reply, self._exc, self.bodies = reply, exc, []

    def open(self, req, timeout=None):
        self.bodies.append(req.data.decode())
        if self._exc is not None:
            raise self._exc
        return _Resp(200, json.dumps({"message": {"content": self._reply}}).encode())


async def _seed_canary(pool):
    await _resolved(pool, 1, "media_sent", evid_media="document", evid_text=f"caption {CANARY}",
                    text=f"I will send {CANARY}")
    await _resolved(pool, 2, "team_confirmed", evid_text=f"already sent {CANARY}", text=f"I will send {CANARY}")
    await _resolved(pool, 3, "client_ack", evid_text=f"ok thanks {CANARY}", evid_dir="inbound",
                    text=f"I will send {CANARY}")


@pytest.mark.asyncio
@pytest.mark.parametrize("reply", [
    json.dumps({"evidence_fulfils_promise": True}),
    json.dumps({"evidence_fulfils_promise": False}),
    f"echo {CANARY}",                                   # the model parrots the data back, invalid
    json.dumps({"evidence_fulfils_promise": CANARY}),   # invalid value carrying the sentinel
])
async def test_the_sentinel_never_leaves_the_audit_except_to_the_local_model(
    pg_socket_dir, monkeypatch, caplog, capsys, reply
):
    async with _fresh_database(pg_socket_dir, "aud_canary") as pool:
        await _setup(pool)
        await _seed_canary(pool)
        opener = _CanaryOpener(reply=reply)
        monkeypatch.setattr(wtp, "_judge_opener", lambda: opener)

        async def _pool(**_kw):
            return _NoClose(pool)

        monkeypatch.setattr(wtp.asyncpg, "create_pool", _pool)
        caplog.set_level(logging.DEBUG)
        assert await wtp.cli_main(["--audit-resolution", "--log-level", "DEBUG"]) == 0
        digest = await wtp._fetch_resolution_digest(pool)
        out, err = capsys.readouterr()
        assert any(CANARY in b for b in opener.bodies)  # it did reach the model, so the checks bite
        assert CANARY not in out and CANARY not in err
        assert CANARY not in caplog.text and CANARY not in digest
        assert CANARY not in wtp._AUDIT_STATE_FILE.read_text()


@pytest.mark.asyncio
@pytest.mark.parametrize("exc", [TimeoutError(CANARY), RuntimeError(f"boom {CANARY}"), OSError(CANARY)])
async def test_a_failing_model_call_leaks_nothing_through_the_error_path(
    pg_socket_dir, monkeypatch, caplog, capsys, exc
):
    async with _fresh_database(pg_socket_dir, "aud_canary_fail") as pool:
        await _setup(pool)
        await _seed_canary(pool)
        monkeypatch.setattr(wtp, "_judge_opener", lambda: _CanaryOpener(exc=exc))

        async def _pool(**_kw):
            return _NoClose(pool)

        monkeypatch.setattr(wtp.asyncpg, "create_pool", _pool)
        caplog.set_level(logging.DEBUG)
        assert await wtp.cli_main(["--audit-resolution", "--log-level", "DEBUG"]) == 1
        out, err = capsys.readouterr()
        assert "stage=ollama" in err
        assert CANARY not in out and CANARY not in err and CANARY not in caplog.text
        assert not wtp._AUDIT_STATE_FILE.exists()


@pytest.mark.asyncio
async def test_invalid_model_output_is_counted_invalid_never_plausible(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "aud_invalid") as pool:
        await _setup(pool)
        for i in range(1, 5):
            await _resolved(pool, i, "media_sent", evid_media="document")
        res = await wtp.run_audit_resolution(pool, sample=100, call=_Model([True, False, None, None]))
        c = res["media_sent"]
        assert (c.judged, c.plausible, c.implausible, c.invalid) == (4, 1, 1, 2)


@pytest.mark.asyncio
async def test_evidence_with_no_text_and_no_media_is_invalid_without_calling_the_model(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "aud_empty") as pool:
        await _setup(pool)
        await _resolved(pool, 1, "team_confirmed", evid_text="")
        model = _Model()
        res = await wtp.run_audit_resolution(pool, sample=100, call=model)
        assert model.calls == [] and (res["team_confirmed"].judged, res["team_confirmed"].invalid) == (1, 1)


@pytest.mark.asyncio
async def test_a_resolved_row_whose_evidence_message_is_gone_is_not_judged(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "aud_orphan") as pool:
        await _setup(pool)
        await _resolved(pool, 1, "media_sent", evid_media="document")
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM whatsapp_message_context WHERE id = 11")
        model = _Model()
        res = await wtp.run_audit_resolution(pool, sample=100, call=model)
        assert res["media_sent"].judged == 0 and model.calls == []


@pytest.mark.asyncio
async def test_a_transport_failure_aborts_the_run(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "aud_down") as pool:
        await _setup(pool)
        await _resolved(pool, 1, "media_sent", evid_media="document")

        def _down(*_a):
            raise wtp.OllamaTransportError("TimeoutError")

        with pytest.raises(wtp.OllamaTransportError):
            await wtp.run_audit_resolution(pool, sample=100, call=_down)


@pytest.mark.asyncio
async def test_the_digest_carries_the_stored_precision_and_stays_int_only(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "aud_digest") as pool:
        await _setup(pool)
        await _resolved(pool, 1, "media_sent", evid_media="document")
        before = await wtp._fetch_resolution_digest(pool)
        assert "precision" not in before
        for i in range(2, 6):
            await _resolved(pool, i, "media_sent", evid_media="document")
        res = await wtp.run_audit_resolution(pool, sample=100, call=_Model([True, True, True, False, None]))
        wtp._save_audit_state(res)
        line = await wtp._fetch_resolution_digest(pool)
        assert "acked (not confirmed) 0; precision media_sent 3/4; overdue 0" in line
        assert "example" not in line and "peer" not in line


@pytest.mark.asyncio
async def test_the_digest_omits_precision_when_no_media_verdict_was_valid(pg_socket_dir):
    async with _fresh_database(pg_socket_dir, "aud_digest_none") as pool:
        await _setup(pool)
        await _resolved(pool, 1, "media_sent", evid_media="document")
        wtp._save_audit_state(await wtp.run_audit_resolution(pool, sample=100, call=_Model([None])))
        assert "precision" not in await wtp._fetch_resolution_digest(pool)
