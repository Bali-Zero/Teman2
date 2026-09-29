"""The alerter went blind when WhatsApp dropped `key.senderPn`.

Measured on Pro 2026-09-29: `senderPn` is absent from 100% of inbound rows since
~2026-07-20, so the selectors gated on `senderPn ~ '^[0-9]+@'` saw nothing: the digest
said 0 inbound / 0 HIGH and the realtime HIGH alert never fired. The identity now
lives in the `sender_phone` column and in `key.remoteJidAlt` (1:1) / `participantAlt`
(groups). These tests run the real selectors, against rows in the REAL post-LID shape
(synthetic numbers only), on a throwaway local Postgres; they skip where no server
binaries exist. A static twin runs everywhere.
"""

from __future__ import annotations

import asyncio
import glob
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "scripts" / "wa-mirror-attention-telegram.py"


def _bin(name: str) -> str | None:
    hit = shutil.which(name)
    if hit:
        return hit
    cands = sorted(glob.glob(f"/usr/lib/postgresql/*/bin/{name}"))
    return cands[-1] if cands else None


@pytest.fixture(scope="module")
def wa(tmp_path_factory):
    home = tmp_path_factory.mktemp("home")
    prev = {k: os.environ.get(k) for k in ("HOME", "WA_MIRROR_DATABASE_URL")}
    os.environ["HOME"] = str(home)
    os.environ["WA_MIRROR_DATABASE_URL"] = "postgresql://test/none"
    try:
        spec = importlib.util.spec_from_file_location("wa_attention_sp", SRC)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["wa_attention_sp"] = mod
        spec.loader.exec_module(mod)
        yield mod
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class _Recorder:
    def __init__(self):
        self.sql = []

    async def fetch(self, q, *a):
        self.sql.append(q)
        return []

    async def fetchrow(self, q, *a):
        self.sql.append(q)
        return {}

    async def fetchval(self, q, *a):
        self.sql.append(q)
        return 0


def test_selectors_do_not_gate_on_senderpn_alone(wa):
    rec = _Recorder()
    asyncio.run(wa.fetch_high_unresolved(rec))
    asyncio.run(wa.fetch_digest_metrics(rec))
    gated = [q for q in rec.sql if "window_msgs" in q or "highs" in q]
    assert len(gated) == 2
    for q in gated:
        assert "remoteJidAlt" in q and "sender_phone" in q
        assert "'^[0-9]+@'" not in q


@pytest.fixture(scope="module")
def pg(tmp_path_factory):
    initdb, pg_ctl = _bin("initdb"), _bin("pg_ctl")
    if not (initdb and pg_ctl) or os.geteuid() == 0:
        pytest.skip("no local postgres server binaries (or running as root)")
    root = Path(tmp_path_factory.mktemp("pg"))
    data = root / "data"
    sock = Path(tempfile.mkdtemp(prefix="wapg"))  # short: AF_UNIX paths cap at ~104 bytes
    subprocess.run([initdb, "-D", str(data), "-U", "t", "-A", "trust", "-E", "UTF8"],
                   check=True, capture_output=True)
    opts = f"-c listen_addresses='' -c unix_socket_directories={sock}"
    subprocess.run([pg_ctl, "-D", str(data), "-o", opts, "-w", "-l", str(root / "log"), "start"],
                   check=True, capture_output=True)
    try:
        yield str(sock)
    finally:
        subprocess.run([pg_ctl, "-D", str(data), "-m", "immediate", "stop"], capture_output=True)
        for leftover in sock.iterdir():
            leftover.unlink()
        sock.rmdir()


def _row(*, remote, alt=None, palt=None, part=None, sender_phone=None, prio=None, resolved=False,
         sender_pn=None, age_days=0):
    key = {"fromMe": False, "remoteJid": remote, "id": "X", "addressingMode": "lid"}
    if alt:
        key["remoteJidAlt"] = alt
    if part:
        key["participant"] = part
    if palt:
        key["participantAlt"] = palt
    if sender_pn:
        key["senderPn"] = sender_pn
    return (json.dumps({"key": key}), sender_phone, prio, resolved, age_days)


ROWS = [
    # 1:1 LID chat, HIGH open, phone only in remoteJidAlt + sender_phone
    _row(remote="111@lid", alt="6280000000001@s.whatsapp.net", sender_phone="+6280000000001",
         prio="HIGH"),
    # 1:1, sender_phone missing: falls back to remoteJidAlt
    _row(remote="112@lid", alt="6280000000002@s.whatsapp.net", prio="MEDIUM"),
    # legacy row still carrying senderPn keeps working
    _row(remote="6280000000003@s.whatsapp.net", sender_pn="6280000000003@s.whatsapp.net",
         sender_phone="6280000000003", prio="HIGH"),
    # group message: participantAlt only; must stay out (1:1 intent)
    _row(remote="120@g.us", part="113@lid", palt="6280000000004@s.whatsapp.net",
         sender_phone="6280000000004", prio="HIGH"),
    # 1:1 HIGH already resolved
    _row(remote="114@lid", alt="6280000000005@s.whatsapp.net", sender_phone="6280000000005",
         prio="HIGH", resolved=True),
    # 1:1 HIGH open but 40 days old: backlog, not news
    _row(remote="115@lid", alt="6280000000006@s.whatsapp.net", sender_phone="6280000000006",
         prio="HIGH", age_days=40),
]


def _seed_and_run(wa, sock, fn):
    import asyncpg

    async def go():
        c = await asyncpg.connect(host=sock, user="t", database="postgres")
        try:
            await c.execute("""
              CREATE TEMP TABLE whatsapp_message_context (
                id serial PRIMARY KEY, direction text, created_at timestamptz DEFAULT now(),
                raw_baileys_event jsonb, sender_phone text, attention_priority text,
                attention_reason text[], attention_resolved_at timestamptz);
              CREATE TEMP TABLE clients (id int, status text, lead_source text,
                phone_normalized text, deleted_at timestamptz, created_by text,
                created_at timestamptz DEFAULT now());""")
            for ev, sp, prio, res, age in ROWS:
                await c.execute(
                    "INSERT INTO whatsapp_message_context (direction, raw_baileys_event, sender_phone,"
                    " attention_priority, attention_reason, attention_resolved_at, created_at)"
                    " VALUES ('inbound', $1::jsonb, $2, $3, ARRAY['deadline'],"
                    " CASE WHEN $4 THEN now() END, now() - make_interval(days => $5))",
                    ev, sp, prio, res, age)
            return await fn(c)
        finally:
            await c.close()

    return asyncio.run(go())


def test_digest_counts_post_lid_rows(wa, pg):
    m = _seed_and_run(wa, pg, wa.fetch_digest_metrics)
    assert m["inbound_24h"] == 4  # 4 recent one-to-one rows; group and 40-day-old rows excluded
    assert m["high_open"] == 2
    assert m["high_resolved"] == 1
    assert m["medium"] == 1
    assert m["distinct_phones_24h"] == 4


def test_high_unresolved_finds_post_lid_rows(wa, pg):
    rows = _seed_and_run(wa, pg, wa.fetch_high_unresolved)
    assert sorted(r["phone"] for r in rows) == ["6280000000001", "6280000000003"]
    assert all(r["phone"].isdigit() for r in rows)
