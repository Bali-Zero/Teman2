"""Corpus for llm_provider_reconcile: guilt, innocence, and the refusal to guess.

The fake sits at the HTTP payload boundary — a real-shaped Monitoring response —
so the parsing that decides "billable vs rejected" runs under every assertion.
A fake placed one layer higher (handing the code a ready-made Observation) would
confirm the fixture's opinion of the payload, not the payload (W114).

The live world is already the strongest case and it was run before this file
existed: on WITA 2026-08-09 the organ returns exit 3 naming 456 foreign calls,
and on 2026-08-04..08 it returns 0. What is pinned here is the behaviour those
runs cannot pin — the edges nobody produced on those days.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import llm_provider_reconcile as organ  # noqa: E402

DECLARED_UID = "a3f0b4d9-2ec2-43af-8483-9fd7f9a7f6aa"
FOREIGN_UID = "11eaa0d3-f520-48e2-92d0-c138889cdcfb"


def series(uid: str, *, code: str, count: int, method: str = "GenerateContent") -> dict:
    """One Monitoring series, shaped as the API really returns it."""
    return {
        "metric": {
            "type": "serviceruntime.googleapis.com/api/request_count",
            "labels": {"response_code": code, "response_code_class": f"{code[0]}xx"},
        },
        "resource": {
            "type": "consumed_api",
            "labels": {
                "credential_id": f"apikey:{uid}",
                "service": organ.SERVICE,
                "method": f"google.ai.generativelanguage.v1beta.GenerativeService.{method}",
                "project_id": "nuzantara",
            },
        },
        "points": [
            {
                "interval": {
                    "startTime": "2026-08-10T16:00:00Z",
                    "endTime": "2026-08-11T16:00:00Z",
                },
                "value": {"int64Value": str(count)},
            }
        ],
    }


def wire(monkeypatch, payload: dict, *, ledger: int | None = 0):
    monkeypatch.setattr(
        organ, "fetch_observation", lambda *a, **k: organ._parse_observation(payload)
    )
    if ledger is None:

        def _boom(*a, **k):
            raise RuntimeError("no database here")

        monkeypatch.setattr(organ, "fetch_ledger_rows", _boom)
    else:
        monkeypatch.setattr(organ, "fetch_ledger_rows", lambda *a, **k: ledger)


def run(monkeypatch, payload: dict, *, ledger: int | None = 0) -> organ.Verdict:
    wire(monkeypatch, payload, ledger=ledger)
    return organ.reconcile(date(2026, 8, 11))


class TestGuiltTheOrganNamesWhatTheLedgerCannotSee:
    def test_an_undeclared_credential_that_spends_is_named(self, monkeypatch):
        verdict = run(
            monkeypatch,
            {
                "timeSeries": [
                    series(DECLARED_UID, code="200", count=40),
                    series(FOREIGN_UID, code="200", count=456),
                ]
            },
            ledger=40,
        )
        assert verdict.exit_code & organ.EXIT_FOREIGN
        assert [uid for uid, _ in verdict.foreign] == [FOREIGN_UID]
        assert dict(verdict.foreign)[FOREIGN_UID] == 456

    def test_calls_the_ledger_never_wrote_are_counted(self, monkeypatch):
        verdict = run(
            monkeypatch,
            {"timeSeries": [series(DECLARED_UID, code="200", count=500)]},
            ledger=52,
        )
        assert verdict.unseen == 448
        assert verdict.exit_code & organ.EXIT_UNSEEN

    def test_zero_series_is_unread_not_silent(self, monkeypatch):
        # A live product with a scheduled credit probe is never at zero. Reading
        # that as health is the blind-scan failure this organ exists to avoid.
        verdict = run(monkeypatch, {"timeSeries": []}, ledger=0)
        assert verdict.exit_code & organ.EXIT_CANNOT_VERIFY
        assert verdict.exit_code != 0

    def test_an_unreadable_ledger_is_cannot_verify_not_drift(self, monkeypatch):
        verdict = run(
            monkeypatch,
            {"timeSeries": [series(DECLARED_UID, code="200", count=40)]},
            ledger=None,
        )
        assert verdict.exit_code & organ.EXIT_CANNOT_VERIFY
        assert not verdict.exit_code & organ.EXIT_UNSEEN
        assert verdict.unseen is None


class TestInnocenceTheOrganStaysQuietOnAHealthyDay:
    def test_the_declared_key_alone_is_clean(self, monkeypatch):
        verdict = run(
            monkeypatch,
            {"timeSeries": [series(DECLARED_UID, code="200", count=36)]},
            ledger=36,
        )
        assert verdict.exit_code == 0

    def test_a_few_rows_of_edge_timing_is_not_a_missing_writer(self, monkeypatch):
        # 08-04..08-07 really did run 1-3 apart: a call straddling midnight lands
        # on either side. An organ that alarmed there would be off within a week.
        verdict = run(
            monkeypatch,
            {"timeSeries": [series(DECLARED_UID, code="200", count=100)]},
            ledger=97,
        )
        assert verdict.exit_code == 0

    def test_a_rejected_call_is_not_spend(self, monkeypatch):
        # 429 and 404 are not billed. Counting them would manufacture a gap that
        # is not money — and on 2026-08-11 that would have been 1,388 phantom calls.
        verdict = run(
            monkeypatch,
            {
                "timeSeries": [
                    series(DECLARED_UID, code="200", count=36),
                    series(DECLARED_UID, code="429", count=1388),
                    series(FOREIGN_UID, code="404", count=972),
                ]
            },
            ledger=36,
        )
        assert verdict.exit_code == 0
        assert verdict.foreign == []
        assert verdict.observation.rejected[FOREIGN_UID] == 972

    def test_a_non_generate_method_is_not_spend(self, monkeypatch):
        # CountTokens and ListModels return 200 and cost nothing.
        verdict = run(
            monkeypatch,
            {
                "timeSeries": [
                    series(DECLARED_UID, code="200", count=36),
                    series(FOREIGN_UID, code="200", count=50, method="CountTokens"),
                ]
            },
            ledger=36,
        )
        assert verdict.exit_code == 0


class TestTheFingerprintIsTheEntity:
    def test_declared_file_carries_the_real_production_key(self):
        # Pins the declared file to the key the ledger actually proxies. If the
        # production key is ever rotated this test fails loudly, which is the
        # point: a rotation must be declared, not discovered by an alarm.
        assert organ.credential_fingerprint(DECLARED_UID) in organ.load_declared()

    def test_the_ab_key_is_not_declared(self):
        assert organ.credential_fingerprint(FOREIGN_UID) not in organ.load_declared()

    def test_the_declared_file_carries_no_raw_uid(self):
        # Minimisation: a public repo does not need infrastructure identifiers.
        raw = organ.DECLARED_PATH.read_text()
        assert DECLARED_UID not in raw
        assert FOREIGN_UID not in raw


class TestWindowIsTheLocalDayNotTheUtcOne:
    def test_a_wita_day_starts_at_1600z_the_day_before(self):
        start, end = organ.wita_day_bounds(date(2026, 8, 11))
        assert start == "2026-08-10T16:00:00Z"
        assert end == "2026-08-11T16:00:00Z"


class TestPaginationIsRefusedNotTruncated:
    def test_a_paginated_read_raises_rather_than_under_report(self, monkeypatch):
        payload = {
            "timeSeries": [series(DECLARED_UID, code="200", count=1)],
            "nextPageToken": "more",
        }

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps(payload).encode()

        monkeypatch.setattr(organ, "_access_token", lambda: "t")
        monkeypatch.setattr(organ.json, "load", lambda fh: payload)
        monkeypatch.setattr(organ.urllib.request, "urlopen", lambda *a, **k: _Resp())
        with pytest.raises(RuntimeError, match="paginated"):
            organ.fetch_observation("2026-08-10T16:00:00Z", "2026-08-11T16:00:00Z")
