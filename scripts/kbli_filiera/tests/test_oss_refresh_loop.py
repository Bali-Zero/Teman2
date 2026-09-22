"""oss_refresh_loop.py — guilt AND innocence, no network.

Answer shapes are the ones measured live on 2026-09-22 (gw.oss.go.id ruang-lingkup):
404 = {"success": false, "data": null, "message": "Data Not Found!", "code": 404},
200 = {"success": true, "data": [scope{localization, KbliResikos[...]}], "meta": {...}}.
Every OSS call goes through a fake session; the canonical and the uuid map are
tiny synthetic files, never the 37 MB dataset.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import _hardened_cure_io as H  # noqa: E402
import kbli_coverage_scoreboard as S  # noqa: E402
import oss_refresh_loop as L  # noqa: E402

NOW = datetime(2026, 9, 22, 1, 2, 3, tzinfo=timezone.utc)
NOT_FOUND = json.dumps({"success": False, "data": None, "message": "Data Not Found!", "code": 404}).encode()


def _loc(text: str) -> dict:
    return {"localization": {"id": {"uraian": text, "deskripsi": None}, "en": {"uraian": text, "deskripsi": None}}}


def scope_payload(code: str = "10001", risk: str = "Menengah Tinggi",
                  kewenangan: tuple[str, ...] = ("Bupati/Walikota", "Gubernur")) -> dict:
    resikos = [
        {
            "kode": f"{code}-01-0{i}",
            "SkalaUsaha": _loc(skala),
            "Resiko": _loc(risk),
            "jangka_waktu": "",
            "KbliIzins": [_loc("Perizinan Berusaha")],
            "KbliPersyaratans": [],
            "KbliKewajibans": [_loc("Memiliki Dokumen")],
            "KbliResikoKewenangans": [{"Kewenangan": _loc(k)} for k in kewenangan],
        }
        for i, skala in enumerate(("Usaha Mikro", "Usaha Besar"), start=1)
    ]
    scope = {**_loc("Seluruh"), "Kbli": {"id": uuid_of(code)}, "KbliResikos": resikos}
    return {"success": True, "data": [scope], "meta": {"count": 1, "totalPage": 1}}


def ok(payload: dict) -> L.Answer:
    return L.Answer(200, json.dumps(payload).encode())


def classify(answer: L.Answer, rows: list, code: str = "10001") -> tuple:
    return L.classify_answer(answer, rows, code, uuid_of(code))


def published_world(*codes: str, **payload_kw) -> dict[str, L.Answer]:
    """Controls answer with their own scope; each named gap publishes one."""
    answers = {uuid_of(c): ok(scope_payload(c)) for c in ("01111", "99999")}
    answers.update({uuid_of(c): ok(scope_payload(c, **payload_kw)) for c in codes})
    return answers


def rows_for(payload: dict) -> list:
    return L.L2.merge_per_skala([], L.L2.parse_per_skala(payload))


def uuid_of(code: str) -> str:
    return f"00000000-0000-4000-8000-{int(code):012d}"


def strong(code: str) -> dict:
    return {"kode_kbli_2025": code, "per_skala": rows_for(scope_payload(code)), "_l2_source": "OSS_RBA_resiko_2025"}


def gap(code: str, **extra) -> dict:
    return {"kode_kbli_2025": code, "per_skala": [], "_l2_status": "no_oss_risk", **extra}


def pp28(code: str) -> dict:
    return {"kode_kbli_2025": code, "_l2_status": "no_oss_risk", "pp28_sources": ["PP28 Lampiran I"],
            "per_skala": [{"skala_usaha": ["Kecil"], "kategori_risiko": "Rendah", "perizinan": ["NIB"]}]}


class FakeSession:
    """Answers keyed by uuid; records every call."""

    def __init__(self, answers: dict[str, L.Answer], default: L.Answer | None = None):
        self.answers = answers
        self.default = default or L.Answer(404, NOT_FOUND)
        self.calls: list[str] = []

    def get(self, uuid: str) -> L.Answer:
        self.calls.append(uuid)
        return self.answers.get(uuid, self.default)

    def close(self) -> None:
        pass


def write_world(tmp_path: Path, records: list[dict]) -> tuple[Path, Path]:
    canonical = tmp_path / "canonical.json"
    canonical.write_text(json.dumps({"metadata": {"version": "vTEST"}, "data": records}), encoding="utf-8")
    gt = tmp_path / "gt.json"
    gt.write_text(json.dumps({"data": [{"kode": r["kode_kbli_2025"], "uuid": uuid_of(r["kode_kbli_2025"]), "digits": 5}
                                       for r in records]}), encoding="utf-8")
    return canonical, gt


def default_world() -> list[dict]:
    return [
        strong("01111"), strong("50000"), strong("99999"),
        gap("10001"), gap("10002"),
        gap("10003", per_skala_disputed_pp28_collision=[{"skala_usaha": ["Kecil"]}]),
        pp28("10004"),
    ]


def run(tmp_path: Path, records: list[dict], session: FakeSession, *extra: str) -> tuple[int, Path]:
    canonical, gt = write_world(tmp_path, records)
    out = tmp_path / "out"
    rc = L.main(["--canonical", str(canonical), "--ground-truth", str(gt), "--out-root", str(out), *extra],
                session=session, now=lambda: NOW, sleep=lambda s: None)
    return rc, out


def report_path(out: Path) -> Path:
    return out / "data/kbli-filiera/oss-refresh/2026-09-22.json"


def spec_path(out: Path) -> Path:
    return out / "scripts/kbli_filiera/cure_specs/oss_refresh_2026_09_22.json"


# ------------------------------------------------------------------ classifier


def test_404_is_still_an_honest_gap():
    assert classify(L.Answer(404, NOT_FOUND), []) == (L.STILL_404, "HTTP 404", None)


def test_published_scope_on_an_empty_gap_proposes_the_l2_rows():
    klass, _, proposed = classify(ok(scope_payload(risk="Rendah")), [])
    assert klass == L.PUBLISHED
    assert [r["skala_usaha"] for r in proposed] == [["Mikro"], ["Besar"]]
    # The L2 merge policy's fresh-row rule, not a re-derivation: Rendah -> Otomatis.
    assert {r["jangka_waktu"] for r in proposed} == {"Otomatis"}


def test_rows_that_differ_from_canonical_are_changed():
    klass, _, proposed = classify(ok(scope_payload(risk="Tinggi")), rows_for(scope_payload()))
    assert klass == L.CHANGED and proposed and proposed[0]["kategori_risiko"] == "Tinggi"


def test_a_reordered_kewenangan_is_not_a_change():
    canonical = rows_for(scope_payload(kewenangan=("Bupati/Walikota", "Gubernur", "Menteri/Kepala Badan")))
    answer = ok(scope_payload(kewenangan=("Menteri/Kepala Badan", "Bupati/Walikota", "Gubernur")))
    assert classify(answer, canonical)[0] == L.UNCHANGED


def test_a_scope_served_for_another_uuid_is_never_a_proposal():
    klass, why, proposed = classify(ok(scope_payload("55203")), [], code="10001")
    assert klass == L.MALFORMED and "not this code's" in why and proposed is None


def test_a_risk_row_of_another_code_is_never_a_proposal():
    payload = scope_payload("10001")
    payload["data"][0]["KbliResikos"][1]["kode"] = "55203-01-02"
    assert classify(ok(payload), [])[0] == L.MALFORMED


def test_a_scope_without_identity_is_malformed():
    payload = scope_payload("10001")
    del payload["data"][0]["Kbli"]
    assert classify(ok(payload), [])[0] == L.MALFORMED


@pytest.mark.parametrize("body, reason", [
    (b"<html>maintenance</html>", "not JSON"),
    (json.dumps([1, 2]).encode(), "not an object"),
    (json.dumps({"success": False, "data": []}).encode(), "success:true"),
    (json.dumps({"success": True, "data": None}).encode(), "not a list"),
    (json.dumps({"success": True, "data": []}).encode(), "no risk rows"),
    (json.dumps({"success": True, "data": ["scope"]}).encode(), "not this code's"),
])
def test_malformed_200_answers(body, reason):
    klass, why, proposed = classify(L.Answer(200, body), [])
    assert klass == L.MALFORMED and reason in why and proposed is None


@pytest.mark.parametrize("status, expected", [(401, L.AUTH_FAILED), (403, L.AUTH_FAILED),
                                              (500, L.FETCH_ERROR), (429, L.FETCH_ERROR), (0, L.FETCH_ERROR)])
def test_non_answers(status, expected):
    assert classify(L.Answer(status, error="x"), [])[0] == expected


# ---------------------------------------------------------------- persistent session


class FakeResponse:
    def __init__(self, status: int, body: bytes = b"{}", headers: dict | None = None):
        self.status, self._body, self._headers = status, body, headers or {}

    def read(self) -> bytes:
        return self._body

    def getheader(self, name: str, default=None):
        return self._headers.get(name, default)


class FakeConnection:
    def __init__(self, script: list):
        self.script = script
        self.requests: list[tuple[str, dict]] = []
        self.closed = False

    def request(self, method, path, headers):
        self.requests.append((path, headers))

    def getresponse(self):
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def close(self):
        self.closed = True


def session_over(script: list, user_key: str = "") -> tuple[L.OssSession, list[FakeConnection], list[float]]:
    made: list[FakeConnection] = []
    sleeps: list[float] = []

    def factory():
        made.append(FakeConnection(script))
        return made[-1]

    return L.OssSession(user_key, connection_factory=factory, sleep=sleeps.append), made, sleeps


def test_one_connection_serves_the_whole_run():
    session, made, sleeps = session_over([FakeResponse(404, NOT_FOUND), FakeResponse(200), FakeResponse(404)])
    statuses = [session.get(uuid_of(c)).status for c in ("1", "2", "3")]
    assert statuses == [404, 200, 404] and len(made) == 1 and sleeps == []


def test_a_dropped_socket_reconnects_and_retries():
    session, made, sleeps = session_over([ConnectionResetError("flap"), FakeResponse(200, b'{"success": true}')])
    answer = session.get(uuid_of("1"))
    assert (answer.status, answer.attempts) == (200, 2)
    assert len(made) == 2 and made[0].closed and sleeps == [L.BACKOFF_S]


def test_a_404_is_never_retried():
    session, made, sleeps = session_over([FakeResponse(404, NOT_FOUND)])
    assert session.get(uuid_of("1")).attempts == 1 and len(made[0].requests) == 1 and sleeps == []


def test_5xx_retries_honour_a_bounded_retry_after_then_give_up():
    session, _, sleeps = session_over([FakeResponse(503, headers={"Retry-After": "999"}),
                                       FakeResponse(503), FakeResponse(503)])
    answer = session.get(uuid_of("1"))
    assert (answer.status, answer.attempts, answer.error) == (503, 3, "HTTP 503")
    assert sleeps == [L.MAX_RETRY_AFTER_S, L.BACKOFF_S * 2]


def test_user_key_is_sent_only_when_set():
    with_key, made_k, _ = session_over([FakeResponse(200)], user_key="k")
    with_key.get(uuid_of("1"))
    without, made_n, _ = session_over([FakeResponse(200)])
    without.get(uuid_of("1"))
    assert made_k[0].requests[0][1]["user_key"] == "k"
    assert "user_key" not in made_n[0].requests[0][1]
    assert made_n[0].requests[0][0] == L.SCOPE_PATH + uuid_of("1")


# ------------------------------------------------------------------ population


def test_population_is_the_scoreboard_complement_of_strong_codes():
    records = default_world() + [{"kode_kbli_2025": "10005", "per_skala": [{"x": 1}]}]  # a bare code
    gaps, strong_codes = L.gap_population(records)
    board = S.build_scoreboard(records)["axes"]["licensing"]
    assert strong_codes == sorted(board["strong_codes"]) == ["01111", "50000", "99999"]
    assert [r["kode_kbli_2025"] for r in gaps] == ["10001", "10002", "10003", "10004", "10005"]


def test_controls_are_the_lowest_and_highest_sourced_codes():
    assert L.pick_controls(["01111", "50000", "99999"]) == ["01111", "99999"]
    assert L.pick_controls(["01111"]) == ["01111"]
    assert L.pick_controls([]) == []


# ---------------------------------------------------------------------- runs


def test_dry_run_writes_nothing_even_when_scopes_are_proposed(tmp_path):
    rc, out = run(tmp_path, default_world(), FakeSession(published_world("10001")))
    assert rc == L.EXIT_PROPOSED
    assert not out.exists()


def test_apply_with_nothing_new_writes_report_and_summary_but_no_spec(tmp_path, capsys):
    session = FakeSession(published_world())
    rc, out = run(tmp_path, default_world(), session, "--apply")
    report = json.loads(report_path(out).read_text())
    assert rc == L.EXIT_NOTHING_NEW == report["exit_code"]
    assert not spec_path(out).exists() and report["cure_spec"] is None
    assert report_path(out).with_suffix(".md").read_text().startswith("KBLI OSS refresh — 2026-09-22")
    assert f"OSS_REFRESH_REPORT={report_path(out)}" in capsys.readouterr().out
    # controls first, then gaps in code order: every gap asked exactly once
    assert session.calls == [uuid_of(c) for c in ("01111", "99999", "10001", "10002", "10003", "10004")]


def test_report_shape(tmp_path):
    answers = published_world()
    answers[uuid_of("10002")] = L.Answer(0, error="timeout", attempts=3)
    _, out = run(tmp_path, default_world(), FakeSession(answers), "--apply")
    report = json.loads(report_path(out).read_text())
    assert set(report) == {"schema", "date", "generated_at", "source", "canonical", "population", "coverage",
                           "controls", "counts", "exit_code", "verdict", "cure_spec", "codes"}
    assert report["schema"] == "kbli-oss-refresh/v1" and report["generated_at"] == "2026-09-22T01:02:03Z"
    assert report["source"]["user_key"] in {"present", "absent"}
    assert report["canonical"]["version"] == "vTEST" and len(report["canonical"]["sha256"]) == 64
    assert report["population"] == {
        "derivation": report["population"]["derivation"], "count": 4, "quarantined": 1,
        "by_state": {"declared_gap": 3, "sourced_pp28_vintage_pending": 1}}
    assert report["coverage"] == {"asked": 4, "fetched": 4, "trusted_answers": 3, "errors": 1, "deferred": 0}
    assert set(report["counts"]) == set(L.CLASSES) and report["counts"]["still_404"] == 3
    assert [c["class"] for c in report["controls"]] == [L.UNCHANGED, L.UNCHANGED]
    entry = next(c for c in report["codes"] if c["code"] == "10003")
    assert entry["quarantined_by"] == ["per_skala_disputed_pp28_collision"]
    assert not any(k.startswith("_") for c in report["codes"] for k in c)


def test_one_unanswered_code_is_not_nothing_new(tmp_path):
    """Guilt (Kimi K3 refutation): 3 honest 404s and 1 timeout used to read
    "nothing new" — the timed-out code may be the one OSS just published."""
    answers = published_world()
    answers[uuid_of("10002")] = L.Answer(0, error="timeout", attempts=3)
    rc, out = run(tmp_path, default_world(), FakeSession(answers), "--apply")
    report = json.loads(report_path(out).read_text())
    assert rc == L.EXIT_CANNOT_VERIFY == report["exit_code"]
    assert report["verdict"] == "partial: 1 of 4 code(s) got no trustworthy answer"


def test_a_proposal_still_surfaces_on_a_partial_run(tmp_path):
    answers = published_world("10001")
    answers[uuid_of("10002")] = L.Answer(0, error="timeout", attempts=3)
    assert run(tmp_path, default_world(), FakeSession(answers))[0] == L.EXIT_PROPOSED


def test_cure_spec_shape_and_routes(tmp_path):
    records = default_world()
    rc, out = run(tmp_path, records, FakeSession(published_world("10001", "10003", risk="Rendah")), "--apply")
    spec = json.loads(spec_path(out).read_text())
    report = json.loads(report_path(out).read_text())
    assert rc == L.EXIT_PROPOSED and report["cure_spec"] == "scripts/kbli_filiera/cure_specs/oss_refresh_2026_09_22.json"
    assert spec["_generated_by"] == "scripts/kbli_filiera/oss_refresh_loop.py"
    assert spec["fetched"] == "2026-09-22" and set(spec["codes"]) == {"10001", "10003"}
    expected_rows = rows_for(scope_payload("10001", risk="Rendah"))
    item = spec["codes"]["10001"]
    assert item["route"] == "l2_transform" and item["per_skala"] == expected_rows
    assert item["premises"]["per_skala"] == {"old_sha256": H.sha256_of([]), "new_sha256": H.sha256_of(expected_rows)}
    assert item["premises"]["_l2_status"] == {"old_sha256": H.sha256_of("no_oss_risk"), "new_sha256": H.sha256_of(None)}
    assert item["set"] == {"_l2_source": "OSS_RBA_resiko_2025"} and item["drop_keys"] == ["_l2_status", "absent_probes"]
    assert item["besar_verdict"] == "BLOCKED"
    # a quarantined code is evidence for its owner, with nothing a compiler could apply
    quarantined = spec["codes"]["10003"]
    assert quarantined["route"] == "quarantine_owner" and quarantined["oss_rows"]
    assert not {"per_skala", "set", "drop_keys", "premises"} & set(quarantined)
    assert quarantined["record_sha256"] == H.sha256_of(records[5])
    # the loop proposes; the canonical it read is byte-identical afterwards
    assert json.loads((tmp_path / "canonical.json").read_text())["data"] == records


def test_empty_fetch_exits_4(tmp_path):
    rc, out = run(tmp_path, default_world(), FakeSession({}, default=L.Answer(0, error="unreachable", attempts=3)), "--apply")
    assert rc == L.EXIT_CANNOT_VERIFY == json.loads(report_path(out).read_text())["exit_code"]


def test_every_answer_malformed_exits_4(tmp_path):
    session = FakeSession(published_world(), default=L.Answer(200, b"<html>maintenance</html>"))
    assert run(tmp_path, default_world(), session)[0] == L.EXIT_CANNOT_VERIFY


def test_a_blind_endpoint_cannot_report_nothing_new(tmp_path):
    """Guilt: every code 404, controls included. Without the positive control
    this run would read as 219 honest gaps and exit 0."""
    rc, _ = run(tmp_path, default_world(), FakeSession({}))
    assert rc == L.EXIT_CANNOT_VERIFY


def test_auth_refusal_exits_4_whatever_else_answered(tmp_path):
    answers = published_world("10001")
    answers[uuid_of("10002")] = L.Answer(401, error="HTTP 401")
    assert run(tmp_path, default_world(), FakeSession(answers))[0] == L.EXIT_CANNOT_VERIFY


def test_deadline_defers_and_logs_fetched_vs_asked(tmp_path):
    canonical, _ = write_world(tmp_path, default_world())
    records = S.load_records(canonical)
    gaps, strong_codes = L.gap_population(records)
    by_code = {r["kode_kbli_2025"]: r for r in records}
    ticks = iter([0.0, 0.0, 0.0, 0.0, 999.0, 999.0, 999.0])  # start, 2 controls, 1st gap, then past deadline
    controls, targets = L.run_loop(gaps, [by_code[c] for c in L.pick_controls(strong_codes)],
                                   {c: uuid_of(c) for c in by_code}, FakeSession(published_world()),
                                   deadline_s=10, clock=lambda: next(ticks), sleep=lambda s: None)
    counts = Counter(t["class"] for t in targets)
    assert counts == Counter({L.STILL_404: 1, L.DEFERRED: 3})
    assert L.decide_exit(counts, controls_ok=True)[0] == L.EXIT_CANNOT_VERIFY
    report = L.build_report(date="2026-09-22", generated_at="x", canonical={}, population=gaps,
                            control_results=controls, target_results=targets, exit_code=4, verdict="v",
                            cure_spec_rel=None, user_key_present=False)
    assert (report["coverage"]["asked"], report["coverage"]["fetched"], report["coverage"]["deferred"]) == (4, 1, 3)


def test_only_restricts_to_a_gap_subset(tmp_path):
    session = FakeSession(published_world())
    rc, _ = run(tmp_path, default_world(), session, "--only", "10002")
    assert rc == L.EXIT_NOTHING_NEW and session.calls[-1] == uuid_of("10002") and len(session.calls) == 3


def test_only_refuses_a_code_outside_the_gap_population(tmp_path):
    session = FakeSession({})
    assert run(tmp_path, default_world(), session, "--only", "10001,50000")[0] == L.EXIT_USAGE
    assert session.calls == []


def test_a_catalogue_with_no_gap_is_an_empty_run_not_a_clean_one(tmp_path):
    session = FakeSession({})
    assert run(tmp_path, [strong("01111"), strong("99999")], session)[0] == L.EXIT_CANNOT_VERIFY
    assert session.calls == []


def test_unreadable_canonical_exits_4(tmp_path):
    rc = L.main(["--canonical", str(tmp_path / "missing.json")], session=FakeSession({}), now=lambda: NOW)
    assert rc == L.EXIT_CANNOT_VERIFY
