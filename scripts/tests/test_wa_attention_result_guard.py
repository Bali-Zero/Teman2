"""Guard the RESULT of the attention selectors, not the spelling of their SQL.

Rounds #7635/#7652/#7656 hardened tests that read the SQL text and each left survivors of one
family (superscar #3: the guard judges a substring, not the entity). Method per
docs/specs/2026-09-29-wa-attention-result-guard-spec.md: seed a sentinel into EVERY name- or
content-bearing place (each text column of `clients`, enumerated from information_schema; the raw
event's pushName/verifiedBizName/text/caption/vCard; the body columns), run the REAL selectors and
composing functions on a throwaway Postgres, assert an exact key set, no sentinel in any value or
rendered text, and the exact label shape. Second half: rows at 0/6/6.5/7.5/8/10/40 days pin the roster
and backlog counts (window seam; the 6.5 and 7.5 rows sit half a day either side of the 7-day window
edge, so a one-day drift on either window ALONE moves a row into both surfaces or neither).
Sentinels are matched case-insensitively, every text key is pinned to its exact value, and every
rendered line must fullmatch a known shape (a suffix after the masked phone is a leak).
Known intrinsic limit: a JSON path the fixture never seeds returns NULL, which cannot be told from a
legitimate NULL. Synthetic data only; the CI job fails on any skip."""

from __future__ import annotations

import asyncio
import glob
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "scripts" / "wa-mirror-attention-telegram.py"

SENTINEL = "SENTINEL"
AGES = (0, 6, 6.5, 7.5, 8, 10, 40)
KINDS = ("open_high", "resolved_high", "group_high", "medium")

HIGH_KEYS = {
    "phone", "first_high_id", "last_high_id", "first_high_at", "last_high_at",
    "n_high", "reasons", "crm_id", "crm_status", "lead_source",
}
DIGEST_KEYS = {
    "high_open", "high_resolved", "medium", "distinct_phones_24h", "inbound_24h",
    "new_leads_24h", "high_backlog",
}
# clients columns a selector may legitimately return a value from; every other text column carries a sentinel
CLIENT_STRUCTURAL = {
    "status": "active",
    "lead_source": "wa",
    "created_by": "wa-mirror-auto-promote",
}


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
        spec = importlib.util.spec_from_file_location("wa_attention_rg", SRC)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["wa_attention_rg"] = mod
        spec.loader.exec_module(mod)
        yield mod
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


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


# ---------------------------------------------------------------------------- fixtures

def _s(label: str) -> str:
    return f"{SENTINEL}-{label}-7f3a"


def _phone(idx: int) -> str:
    return f"628100{idx:07d}"


def _event(idx: int, group: bool) -> dict:
    phone = _phone(idx)
    if group:
        key = {"fromMe": False, "remoteJid": f"12{idx}@g.us", "id": f"M{idx}",
               "participant": f"9{idx}@lid", "participantAlt": f"{phone}@s.whatsapp.net"}
    else:
        key = {"fromMe": False, "remoteJid": f"{idx}@lid", "id": f"M{idx}",
               "addressingMode": "lid", "remoteJidAlt": f"{phone}@s.whatsapp.net"}
    return {
        "key": key,
        "pushName": _s("PUSHNAME"),
        "verifiedBizName": _s("VERIFIEDBIZ"),
        "message": {
            "conversation": _s("CONVERSATION"),
            "extendedTextMessage": {"text": _s("EXTTEXT")},
            "imageMessage": {"caption": _s("CAPTION")},
            "contactMessage": {"displayName": _s("CONTACTNAME"),
                               "vcard": f"BEGIN:VCARD\nFN:{_s('VCARD')}\nEND:VCARD"},
        },
    }


def _matrix(ages=AGES, kinds=KINDS) -> list[dict]:
    rows, idx = [], 100
    for age in ages:
        for kind in kinds:
            idx += 1
            group = kind == "group_high"
            rows.append({
                "idx": idx, "age": age, "kind": kind, "phone": _phone(idx),
                "priority": "MEDIUM" if kind == "medium" else "HIGH",
                "resolved": kind == "resolved_high",
                "group": group,
                "event": _event(idx, group),
            })
    return rows


def _open_high(rows, *, young: bool | None = None):
    out = [r for r in rows if r["kind"] == "open_high"]
    if young is None:
        return out
    return [r for r in out if (r["age"] < 7) == young]


DDL = """
CREATE TEMP TABLE whatsapp_message_context (
  id serial PRIMARY KEY, direction text, created_at timestamptz DEFAULT now(),
  raw_baileys_event jsonb, sender_phone text, counterpart_phone text,
  attention_priority text, attention_reason text[], attention_resolved_at timestamptz,
  body text, message_text text, sender_push_name_snapshot text);
CREATE TEMP TABLE clients (
  id int, status text, lead_source text, phone_normalized text, deleted_at timestamptz,
  created_by text, created_at timestamptz DEFAULT now(),
  full_name text, company_name text, email text, address text, notes text,
  nationality text, passport_number text, tax_id text, phone text, display_name varchar(80));
"""


async def _seed(conn, rows, *, known_phone: str | None, client_id: int = 41) -> list[str]:
    """Create the schema, seed messages and one client; returns the sentinel-carrying client columns."""
    await conn.execute(DDL)
    for r in rows:
        await conn.execute(
            "INSERT INTO whatsapp_message_context (direction, raw_baileys_event, sender_phone,"
            " counterpart_phone, attention_priority, attention_reason, attention_resolved_at, created_at,"
            " body, message_text, sender_push_name_snapshot)"
            " VALUES ('inbound', $1::jsonb, $2, $2, $3, ARRAY['deadline'],"
            " CASE WHEN $4 THEN now() END, now() - make_interval(secs => $5::float8 * 86400), $6, $7, $8)",
            json.dumps(r["event"]), r["phone"], r["priority"], r["resolved"], r["age"],
            _s("BODY"), _s("MESSAGETEXT"), _s("SNAPSHOT"))
    cols = await conn.fetch(
        "SELECT column_name, data_type FROM information_schema.columns"
        " WHERE table_name = 'clients' AND data_type IN ('text', 'character varying')"
        " ORDER BY ordinal_position")
    sentinel_cols = []
    if known_phone:
        values = {}
        for c in cols:
            name = c["column_name"]
            if name == "phone_normalized":
                values[name] = known_phone
            elif name in CLIENT_STRUCTURAL:
                values[name] = CLIENT_STRUCTURAL[name]
            else:
                values[name] = _s(name.upper())
                sentinel_cols.append(name)
        names = ["id", "created_at"] + list(values)
        marks = ", ".join(f"${i + 2}" for i in range(len(values)))
        await conn.execute(
            f"INSERT INTO clients ({', '.join(names)}) VALUES ($1, now(), {marks})",
            client_id, *values.values())
    return sentinel_cols


def _run(wa, sock, rows, body, *, known_phone=None):
    import asyncpg

    async def go():
        conn = await asyncpg.connect(host=sock, user="t", database="postgres")
        try:
            cols = await _seed(conn, rows, known_phone=known_phone)
            return await body(conn, cols)
        finally:
            await conn.close()

    return asyncio.run(go())


def _deep_strings(value):
    """Every scalar, dict key and nested JSON string, stringified."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from _deep_strings(v)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            yield from _deep_strings(v)
    elif isinstance(value, str):
        yield value
        try:
            inner = json.loads(value)
        except ValueError:
            return
        if isinstance(inner, (dict, list)):
            yield from _deep_strings(inner)
    else:
        yield str(value)


def _assert_no_sentinel(value, where):
    hits = [s for s in _deep_strings(value) if SENTINEL.lower() in s.lower()]
    assert not hits, f"{where} carries a sentinel: {hits[:2]}"


_LABEL = r"(?:client #\d+ — )?\+\d{4}\*{4}\d{4}"
_TAG = r"(?:CRM #\d+|new lead)"


def _line_shapes(wa) -> list[re.Pattern]:
    """Every line the digest and the realtime composer may emit; anything else (a suffix after the masked
    phone, an extra line) fails `fullmatch`, so a leak appended to a label cannot hide behind `search`."""
    dash = re.escape(wa.DASHBOARD_URL)
    return [re.compile(p) for p in (
        r"📊 WA mirror daily digest",
        r"[A-Za-z]{3} \d{2} [A-Za-z]{3} \d{4}, \d{2}:\d{2} WITA",
        r"",
        r"Last 24h:",
        r"  • \d+ inbound msgs from \d+ contacts",
        r"  • \d+ HIGH unresolved · \d+ resolved",
        r"  • \d+ MEDIUM",
        r"  • \d+ new leads auto-promoted to CRM",
        r"🚨 Needs your attention:",
        rf"  • {_LABEL}(?: \(new lead\))? — \d+ msg · deadline",
        r"  …and \d+ more",
        rf"📦 \d+ older HIGH msgs unresolved \(>{wa.HIGH_WINDOW_DAYS}d, count only\)",
        r"🟢 Everything is acknowledged\.",
        rf"→ {dash}",
        r"(?:🚨 HIGH attention|🔔 still unresolved)(?: — \d+ contacts)?",
        _LABEL,
        rf"{_TAG} · \d+ unresolved msg",
        r"Reasons: deadline",
        rf"• {_LABEL}",
        rf"  {_TAG} · \d+ unresolved · deadline",
    )]


def _assert_every_line_has_a_known_shape(text, shapes):
    for line in text.splitlines():
        assert any(p.fullmatch(line) for p in shapes), f"line with no known shape: {line!r}"


class _Pool:
    """acquire() yields the REAL connection, so cmd_* run the real selectors."""

    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class _A:
            async def __aenter__(self_):
                return conn

            async def __aexit__(self_, *_a):
                return False

        return _A()

    async def close(self):
        return None


async def _capture(wa, monkeypatch, conn, which):
    sent: list[str] = []

    async def create_pool(*_a, **_k):
        return _Pool(conn)

    monkeypatch.setattr(wa.asyncpg, "create_pool", create_pool)
    monkeypatch.setattr(wa, "send_telegram", lambda text, **_k: sent.append(text) or True)
    if wa.STATE_PATH.exists():
        wa.STATE_PATH.unlink()  # this module's own throwaway HOME, never production state
    await (wa.cmd_digest() if which == "digest" else wa.cmd_realtime(force=True))
    return sent


# ---------------------------------------------------------------------------- the result guard

def test_each_selector_returns_exactly_its_contract_and_no_sentinel(wa, pg):
    rows = _matrix()
    known = _open_high(rows)[0]["phone"]

    async def body(conn, cols):
        stored = dict(await conn.fetchrow("SELECT * FROM clients"))
        return await wa.fetch_high_unresolved(conn), await wa.fetch_digest_metrics(conn), cols, stored

    high, digest, cols, stored = _run(wa, pg, rows, body, known_phone=known)
    # the guard only bites if the sentinels are really there (enumerated, not hand-listed)
    assert {"full_name", "company_name", "email", "address", "notes", "display_name"} <= set(cols)
    assert all(SENTINEL in stored[c] for c in cols)
    assert high, "the fixture must produce roster rows or this proves nothing"
    for row in high:
        assert set(row) == HIGH_KEYS
    assert set(digest) == DIGEST_KEYS
    _assert_no_sentinel(high, "fetch_high_unresolved")
    _assert_no_sentinel(digest, "fetch_digest_metrics")
    by_phone = {r["phone"]: r for r in high}
    young_phones = {r["phone"] for r in _open_high(rows, young=True)}
    assert set(by_phone) == young_phones and len(high) == len(young_phones)
    # exact value of every text key, not "no sentinel present": a transformed client column
    # (lower-case, substring, whole-row JSON) is neither a sentinel nor structural
    assert by_phone[known]["crm_id"] == 41
    assert by_phone[known]["crm_status"] == CLIENT_STRUCTURAL["status"]
    assert by_phone[known]["lead_source"] == CLIENT_STRUCTURAL["lead_source"]
    for phone, row in by_phone.items():
        assert row["reasons"] == ["deadline"], row["reasons"]
        assert row["n_high"] == 1
        if phone != known:
            assert (row["crm_id"], row["crm_status"], row["lead_source"]) == (None, None, None)


def test_the_rendered_digest_and_realtime_texts_carry_no_sentinel_and_the_exact_label(wa, pg, monkeypatch):
    rows = _matrix()
    known = _open_high(rows)[0]["phone"]
    lead = next(r["phone"] for r in _open_high(rows, young=True) if r["phone"] != known)

    async def body(conn, cols):
        digest = await _capture(wa, monkeypatch, conn, "digest")
        realtime = await _capture(wa, monkeypatch, conn, "realtime")
        return digest, realtime

    digest, realtime = _run(wa, pg, rows, body, known_phone=known)
    assert len(digest) == 1 and realtime, "both paths must have sent something"
    for text in digest + realtime:
        _assert_no_sentinel(text, "a rendered text")
        for phone in (known, lead):
            assert phone not in text, "a full phone reached a message"
    label_known = f"client #41 — {wa.mask_phone(known)}"
    shapes = _line_shapes(wa)
    for text in digest + realtime:
        assert label_known in text
        # a new lead is the masked phone alone, never prefixed by anything that could be a name
        assert wa.mask_phone(lead) in text
        assert f"client #None" not in text
        _assert_every_line_has_a_known_shape(text, shapes)


# ---------------------------------------------------------------------------- backlog and window seam

def test_the_window_seam_splits_open_high_rows_between_roster_and_backlog_exactly(wa, pg):
    rows = _matrix()

    async def body(conn, cols):
        return await wa.fetch_high_unresolved(conn), await wa.fetch_digest_metrics(conn)

    high, digest = _run(wa, pg, rows, body)
    young = {r["phone"] for r in _open_high(rows, young=True)}
    old = _open_high(rows, young=False)
    assert {r["age"] for r in _open_high(rows, young=True)} == {0, 6, 6.5}  # 6d and 6d12h are INSIDE
    assert {r["age"] for r in old} == {7.5, 8, 10, 40}  # 7d12h and 8d are OUTSIDE
    assert {r["phone"] for r in high} == young, "the roster is the unresolved 1:1 HIGH rows younger than the window"
    assert digest["high_backlog"] == len(old) == 4
    # every open HIGH 1:1 row lands in exactly one of the two surfaces: the rows half a day either side
    # of the edge make a +/-1 day drift on ONE window alone put a row in both surfaces or in neither
    on_roster = {r["phone"] for r in high}
    assert len(high) + digest["high_backlog"] == len(_open_high(rows)) == 7
    inside, outside = (next(r for r in _open_high(rows) if r["age"] == a) for a in (6.5, 7.5))
    assert inside["phone"] in on_roster and outside["phone"] not in on_roster
    # 24h block: only the age-0 one-to-one rows (open HIGH, resolved HIGH, MEDIUM); the group row is out
    assert (digest["inbound_24h"], digest["high_open"], digest["high_resolved"], digest["medium"],
            digest["distinct_phones_24h"], digest["new_leads_24h"]) == (3, 1, 1, 1, 3, 0)


def test_the_backlog_excludes_resolved_group_and_medium_rows_at_forty_days(wa, pg):
    rows = _matrix(ages=(40,))

    async def body(conn, cols):
        return (await wa.fetch_digest_metrics(conn))["high_backlog"]

    assert _run(wa, pg, rows, body) == 1  # only the open 1:1 HIGH row; 3 other kinds sit at 40 days too


def test_the_digest_never_says_all_clear_over_a_backlog_end_to_end(wa, pg, monkeypatch):
    rows = [r for r in _matrix() if r["age"] >= 7]  # empty roster, backlog only

    async def body(conn, cols):
        return await _capture(wa, monkeypatch, conn, "digest")

    sent = _run(wa, pg, rows, body)
    assert len(sent) == 1
    assert "Everything is acknowledged" not in sent[0]
    assert "4 older HIGH msgs unresolved" in sent[0]
    _assert_no_sentinel(sent[0], "the backlog-only digest")


# ---------------------------------------------------------------------------- the guard's own innocence

def test_the_sentinel_matcher_and_the_line_shapes_reject_transformed_and_suffixed_leaks(wa):
    for leak in (_s("FULL_NAME").lower(), {"crm_status": _s("EMAIL").swapcase()}, ["x", {"k": f"a {_s('TAX').lower()}"}]):
        with pytest.raises(AssertionError):
            _assert_no_sentinel(leak, "probe")
    _assert_no_sentinel({"crm_status": "active", "reasons": ["deadline"]}, "probe")
    shapes = _line_shapes(wa)
    _assert_every_line_has_a_known_shape("  • client #41 — +6281****0041 — 1 msg · deadline", shapes)
    _assert_every_line_has_a_known_shape("• +6281****0041\n  new lead · 2 unresolved · deadline", shapes)
    for bad in ("  • client #41 — +6281****0041 active — 1 msg · deadline", "client #41 — +6281****0041 x",
                "  • client #41 — +6281****0041 — 1 msg · deadline · sentinel-full_name-7f3a"):
        with pytest.raises(AssertionError):
            _assert_every_line_has_a_known_shape(bad, shapes)
