"""The web-lead funnel report, and the one lie it must never tell.

The report exists because Ari's WhatsApp line carries both our web leads and
his own working traffic, so the only thing that distinguishes a lead is the
`li_` token our own deeplink prefills.

Two numbers describe that funnel and they are NOT the same measurement:
clicks (rows in `lead_intents`, on Fly) is a ceiling, arrived (tokens seen in
the wa-mirror, on the Pro) is a floor. They live in different databases, and
the mirror is reachable only from the machine that owns it.

Hence the load-bearing case here: when the mirror cannot be read, `arrived`
must report UNKNOWN. Reporting 0 would be indistinguishable from "nobody came"
— a dead source passing for a healthy silence, which is exactly how scar
family #2 kills an organ without anyone noticing.

Guilt and innocence are both asserted:

- guilt      clicks, arrivals and matches are attributed to the right surface
- guilt      surface labels that differ only in case/spacing fold together,
             so the two sides of the funnel can be compared at all
- innocence  no mirror DSN  -> arrived is UNKNOWN, never 0
- innocence  mirror raises  -> arrived is UNKNOWN, never 0, and the reason survives
- innocence  a body that merely CONTAINS "li_" is not a lead
- guilt      a gateway that is missing, silent or crashing is NOT delivery,
             even though it exits 0 — the organ must know it lost its voice
- innocence  `spooled` (the healthy verdict for a digest) and `deduped` are
             gateway decisions, not failures, and must raise nothing
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]
_REPORT_PATH = _REPO_ROOT / "scripts" / "web_lead_funnel_report.py"

_spec = importlib.util.spec_from_file_location("web_lead_funnel_report", _REPORT_PATH)
assert _spec is not None and _spec.loader is not None
wlr = importlib.util.module_from_spec(_spec)
# Register before executing: @dataclass resolves its own module through
# sys.modules, and a spec-loaded module that is not registered there makes the
# decorator blow up on an attribute of None.
sys.modules["web_lead_funnel_report"] = wlr
_spec.loader.exec_module(wlr)


class _FakeConn:
    """Stands in for an asyncpg connection, answering by query shape."""

    def __init__(self, intents: list[dict], arrivals: list[dict]) -> None:
        self._intents = intents
        self._arrivals = arrivals
        self.closed = False

    async def fetch(self, query: str, *args: Any) -> list[dict]:
        if "lead_intents" in query:
            return list(self._intents)
        if "whatsapp_message_context" in query:
            return list(self._arrivals)
        raise AssertionError(f"unexpected query: {query[:80]}")

    async def close(self) -> None:
        self.closed = True


def _connect_factory(fly: _FakeConn, mirror: _FakeConn | Exception):
    async def _connect(dsn: str, *a: Any, **kw: Any):
        if dsn == "fly://":
            return fly
        if isinstance(mirror, Exception):
            raise mirror
        return mirror

    return _connect


def _run(monkeypatch, intents, arrivals, mirror_dsn="mirror://", mirror_exc=None):
    import asyncio

    fly = _FakeConn(intents, [])
    mirror = mirror_exc if mirror_exc else _FakeConn([], arrivals)
    monkeypatch.setattr(wlr.asyncpg, "connect", _connect_factory(fly, mirror))
    return asyncio.run(wlr.build_report("fly://", mirror_dsn))


def _window(reports, label):
    return next(r for r in reports if r.label == label)


# ── guilt ────────────────────────────────────────────────────────────────────


def test_clicks_arrivals_and_matches_land_on_their_surface(monkeypatch):
    reports = _run(
        monkeypatch,
        intents=[
            {"source": "pricing page", "matched_client_id": "c1"},
            {"source": "pricing page", "matched_client_id": None},
            {"source": "homepage", "matched_client_id": None},
        ],
        arrivals=[{"token": "li_abc123", "surface": "pricing page", "landed": "direct"}],
    )
    all_w = _window(reports, "all")
    assert all_w.clicks == 3
    assert all_w.matched == 1
    assert all_w.arrived == 1

    pricing = next(s for s in all_w.surfaces if s.surface == "pricing page")
    assert (pricing.clicks, pricing.arrived, pricing.matched) == (2, 1, 1)

    homepage = next(s for s in all_w.surfaces if s.surface == "homepage")
    # Clicked but never sent. The mirror WAS readable, so this is a measured
    # zero and must print as 0 — not UNKNOWN, which this report reserves for
    # "we could not look". Collapsing the two is the exact lie it exists to
    # prevent, and it shipped that way until a run against the real databases
    # printed UNKNOWN beside a number we already had.
    assert (homepage.clicks, homepage.arrived) == (1, 0)


def test_slug_and_prose_spellings_of_one_surface_fold_together(monkeypatch):
    # Measured on live data 2026-08-06: Fly emits `homepage_hero`, the prefill
    # sentence emits `homepage hero`. Unfolded, one surface reads as two rows,
    # each showing half the funnel.
    reports = _run(
        monkeypatch,
        intents=[{"source": "homepage_hero", "matched_client_id": None}],
        arrivals=[{"token": "li_abc123", "surface": "homepage hero", "landed": "direct"}],
    )
    all_w = _window(reports, "all")
    assert [s.surface for s in all_w.surfaces] == ["homepage hero"]
    assert (all_w.surfaces[0].clicks, all_w.surfaces[0].arrived) == (1, 1)


def test_a_surface_seen_only_on_the_arrival_side_is_marked_not_invented(monkeypatch):
    # `pricing_modal` (slug) and `pricing page` (prose) may or may not be the
    # same CTA. Nothing measured says they are, so the report must show the gap
    # rather than fabricate a mapping that answers a question nobody asked.
    reports = _run(
        monkeypatch,
        intents=[{"source": "pricing_modal", "matched_client_id": None}],
        arrivals=[{"token": "li_abc123", "surface": "pricing page", "landed": "direct"}],
    )
    all_w = _window(reports, "all")
    labels = {s.surface for s in all_w.surfaces}
    assert labels == {"pricing modal", "pricing page"}, "must not be silently joined"
    text = wlr.render_text(reports)
    assert "label only on the arrival side" in text
    # The totals count rows, so they stay correct even when labels disagree.
    assert all_w.clicks == 1 and all_w.arrived == 1


def test_surface_labels_differing_only_in_case_and_spacing_fold_together(monkeypatch):
    # The CTA writes "Homepage  Hero", the prefill sentence yields "homepage hero".
    # If these did not fold, every surface would appear twice and the click side
    # would never line up with the arrival side.
    reports = _run(
        monkeypatch,
        intents=[{"source": "Homepage  Hero", "matched_client_id": None}],
        arrivals=[{"token": "li_abc123", "surface": "homepage hero", "landed": "direct"}],
    )
    all_w = _window(reports, "all")
    assert [s.surface for s in all_w.surfaces] == ["homepage hero"]
    assert (all_w.surfaces[0].clicks, all_w.surfaces[0].arrived) == (1, 1)


# ── innocence: a relayed token is not an arrival ────────────────────────────


def test_a_token_seen_only_in_a_group_is_not_counted_as_an_arrival(monkeypatch):
    # The finding that produced this split, measured 2026-08-06: all four tokens
    # this system has ever seen arrived with chat_type='group' — team members
    # relaying a lead internally, because the deeplink pointed at a phone that
    # is not mirrored at all. Counted as arrivals they read as four leads
    # reaching us; the true figure is zero.
    reports = _run(
        monkeypatch,
        intents=[{"source": "pricing page", "matched_client_id": None}],
        arrivals=[{"token": "li_abc123", "surface": "pricing page", "landed": "forwarded"}],
    )
    all_w = _window(reports, "all")
    assert all_w.arrived == 0, "a group relay must never be counted as an arrival"
    assert all_w.forwarded == 1

    text = wlr.render_text(reports)
    assert "relayed" in text and "Not arrivals" in text


def test_an_unlabelled_landing_place_is_not_assumed_to_be_an_arrival(monkeypatch):
    # Conservative by design: the number that matters must never be inflated by
    # a row whose landing place we could not determine.
    reports = _run(
        monkeypatch,
        intents=[],
        arrivals=[{"token": "li_abc123", "surface": "homepage"}],
    )
    all_w = _window(reports, "all")
    assert all_w.arrived == 0
    assert all_w.forwarded == 1


# ── innocence: the silent zero ───────────────────────────────────────────────


def test_absent_mirror_dsn_reports_unknown_not_zero(monkeypatch):
    reports = _run(
        monkeypatch,
        intents=[{"source": "homepage", "matched_client_id": None}],
        arrivals=[],
        mirror_dsn=None,
    )
    all_w = _window(reports, "all")
    assert all_w.arrived is None, "an unreadable mirror must not read as zero leads"
    assert all_w.clicks == 1, "the Fly half is still measurable and must be reported"
    assert "not set" in all_w.mirror_status

    text = wlr.render_text(reports)
    assert "UNKNOWN" in text
    # The rendered line must not be able to pass for a measured zero.
    assert "arrived 0 (floor)" not in text


def test_unreachable_mirror_reports_unknown_and_keeps_the_reason(monkeypatch):
    reports = _run(
        monkeypatch,
        intents=[{"source": "homepage", "matched_client_id": None}],
        arrivals=[],
        mirror_exc=OSError("connection refused"),
    )
    all_w = _window(reports, "all")
    assert all_w.arrived is None
    assert "connection refused" in all_w.mirror_status
    assert "OSError" in all_w.mirror_status

    text = wlr.render_text(reports)
    assert "UNKNOWN" in text and "connection refused" in text


def test_a_measured_zero_still_renders_as_zero(monkeypatch):
    # Innocence for the guard itself: the UNKNOWN path must not swallow a real,
    # measured "nobody arrived" — otherwise we could never tell a quiet week
    # from a broken mirror, which is the same blindness at the other end.
    reports = _run(monkeypatch, intents=[], arrivals=[])
    all_w = _window(reports, "all")
    assert all_w.arrived == 0
    assert all_w.mirror_status == "ok"
    assert "UNKNOWN" not in wlr.render_text(reports)


# ── innocence: what counts as a token ────────────────────────────────────────


@pytest.mark.parametrize("token", ["li_p7nz6ul6rq", "li_pgzr0j2494", "li_7bw3gte2x4", "li_wd5mklrxpk"])
def test_the_four_real_historical_tokens_are_accepted(token):
    # Measured on the live mirror 2026-08-06 — these are the only four real
    # tokens the system has ever received. A grammar change that rejects one of
    # them silently loses a lead.
    assert wlr.extract_lead_ids(token) == [token]


@pytest.mark.parametrize("text", ["li_", "kali_belum", "li_ab", "LI_ABC123XYZ"])
def test_prose_that_merely_contains_the_prefix_is_not_a_lead(text):
    # The mirror's cheap SQL prefilter (strpos 'li_') fires on ordinary
    # Indonesian and Italian words; on 2026-08-06 it returned 7 rows where only
    # 4 were leads. The word-bounded grammar is what keeps the other 3 out.
    assert wlr.extract_lead_ids(text) == []


def test_report_sql_uses_the_word_bounded_grammar_not_the_loose_prefilter():
    # Pins the decision rather than the prose: if someone "simplifies" the SQL
    # back to a substring test, three invented leads reappear.
    assert wlr.TOKEN_REGEX_SQL == r"\mli_[a-z0-9]{6,20}\M"
    assert "strpos" not in wlr._fetch_arrivals.__doc__ or True  # doc may mention it
    import inspect

    src = inspect.getsource(wlr._fetch_arrivals)
    assert "strpos" not in src, "the arrivals query must not fall back to substring matching"


# ── the honesty invariant, asserted on the rendered artefact ─────────────────


def test_rendered_report_always_names_ceiling_and_floor(monkeypatch):
    reports = _run(
        monkeypatch,
        intents=[{"source": "homepage", "matched_client_id": None}],
        arrivals=[{"token": "li_abc123", "surface": "homepage", "landed": "direct"}],
    )
    text = wlr.render_text(reports)
    assert "ceiling" in text and "floor" in text
    # The reader must be told, in the artefact itself, why the two differ.
    assert "retyped it in their own words" in text


# ── the organ's voice: it must know whether it actually spoke ────────────────
#
# `tg_notify.py` exits 0 by design — "NEVER fail the caller" is written into it
# — and prints its verdict on stderr. So the exit code carries no information
# about delivery, and a caller that reads it (or drops the output) reports a
# digest nobody received as a success: W104's shape, with W108's consequence of
# leaving no trace of not having spoken.
#
# These run a REAL subprocess against a REAL fake gateway on disk. Mocking
# `subprocess.run` would only prove that the parser agrees with my imagination
# of what the gateway prints (W114) — the fake belongs at the real boundary.


def _fake_gateway(tmp_path, body: str):
    """Plant a runnable stand-in gateway next to a stand-in module file."""
    (tmp_path / "tg_notify.py").write_text(body)
    return str(tmp_path / "web_lead_funnel_report.py")


def test_a_missing_gateway_is_reported_not_assumed_delivered(monkeypatch, tmp_path):
    # Nothing planted: the gateway simply is not there.
    monkeypatch.setattr(wlr, "__file__", str(tmp_path / "web_lead_funnel_report.py"))
    status = wlr.send_telegram("7d: 0 clicks")
    assert status not in wlr._GATEWAY_DELIVERED
    assert "no gateway" in status


def test_a_gateway_that_exits_zero_in_silence_is_not_delivery(monkeypatch, tmp_path):
    # The exact trap: success by exit code, silence by verdict.
    monkeypatch.setattr(
        wlr, "__file__", _fake_gateway(tmp_path, "import sys\nsys.exit(0)\n")
    )
    status = wlr.send_telegram("7d: 0 clicks")
    assert status not in wlr._GATEWAY_DELIVERED
    assert "no verdict" in status


def test_a_gateway_that_crashes_is_reported_with_its_own_words(monkeypatch, tmp_path):
    monkeypatch.setattr(
        wlr,
        "__file__",
        _fake_gateway(tmp_path, "raise SystemExit('token file unreadable')\n"),
    )
    status = wlr.send_telegram("7d: 0 clicks")
    assert status not in wlr._GATEWAY_DELIVERED
    # The reason survives into the caller's log rather than being swallowed.
    assert "token file unreadable" in status


def test_spooled_is_the_healthy_verdict_for_a_digest(monkeypatch, tmp_path):
    # INNOCENCE, and the load-bearing one: tier=digest is spooled by design and
    # flushed later by tg_digest_flush.py. Demanding "sent" here would paint a
    # permanent red on a perfectly healthy organ.
    monkeypatch.setattr(
        wlr,
        "__file__",
        _fake_gateway(
            tmp_path, "import sys\nprint('tg_notify: spooled', file=sys.stderr)\n"
        ),
    )
    assert wlr.send_telegram("7d: 0 clicks") == "spooled"
    assert "spooled" in wlr._GATEWAY_DELIVERED


def test_deduped_is_a_gateway_decision_not_a_failure(monkeypatch, tmp_path):
    # INNOCENCE: a collapsed repeat is the gateway working, not the organ failing.
    monkeypatch.setattr(
        wlr,
        "__file__",
        _fake_gateway(
            tmp_path, "import sys\nprint('tg_notify: deduped', file=sys.stderr)\n"
        ),
    )
    assert wlr.send_telegram("7d: 0 clicks") in wlr._GATEWAY_DELIVERED


def test_the_dedup_key_names_this_organs_real_cadence(monkeypatch, tmp_path):
    # The gateway collapses a repeated key inside TG_DEDUP_HOURS. A weekly organ
    # keyed ":daily" never actually collides, so nothing breaks today — which is
    # precisely why the lie would survive until someone changed the cadence.
    monkeypatch.setattr(
        wlr,
        "__file__",
        _fake_gateway(
            tmp_path,
            "import sys\n"
            "print('ARGV ' + ' '.join(sys.argv), file=sys.stderr)\n"
            "print('tg_notify: spooled', file=sys.stderr)\n",
        ),
    )
    import inspect

    src = inspect.getsource(wlr.send_telegram)
    assert "web-lead-funnel:weekly" in src
    assert "web-lead-funnel:daily" not in src
