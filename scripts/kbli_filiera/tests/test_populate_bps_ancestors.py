"""Tests for the gate-bound `populate_bps_ancestors.py` compiler.

Guilt + innocence per scar #3, on tiny synthetic fixtures (pure-stdlib, no vault
PDF, no 36 MB canonical). The mutation must be strictly ADDITIVE (§2.2): only the
new `bps_2020_ancestors` field appears. Batch B (`_l2_status is None`) remains the
default population; Batch A (`no_oss_risk`) joins only through the explicit second-
pass opt-in. Every pre-existing key/value survives byte-identical. The fail-closed
guards — full gate PASS, matching digest, non-empty ancestry, and a locator for
every edge — each get guilt and innocence coverage.
"""

from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import populate_bps_ancestors as P  # noqa: E402
from kbli_filiera import bps_crosswalk_parser as parser  # noqa: E402

# A syntactically-valid but fake parse digest (64 hex). Not a credential.
DIGEST = "a" * 64  # pragma: allowlist secret


def _digest_of(relation: dict) -> str:
    """The output_relation_digest the parser would stamp for this relation."""
    return parser._relation_digest({"relation": relation})


def _rec(code: str, l2_status, extra: dict | None = None) -> dict:
    r = {
        "kode_kbli_2025": code,
        "judul": f"Judul {code}",
        "uraian": "uraian text",
        "_l2_status": l2_status,
    }
    if extra:
        r.update(extra)
    return r


def _relation(spec: dict[str, list[tuple[str, bool]]]) -> dict:
    """spec: {code2025: [(ancestor2020, sebagian_bool), ...]}."""
    rel = {}
    for code, edges in spec.items():
        rel[code] = {
            "codes": [a for a, _ in edges],
            "sebagian": [s for _, s in edges],
            "source_locator": [
                {"lampiran": 10, "pdf_page": 325, "printed_page": 311} for _ in edges
            ],
        }
    return rel


def _write_world(
    tmp_path,
    records,
    relation,
    *,
    digest=None,
    verdict="PASS",
    aggregate_passes=True,
    gate_digest=None,
):
    # Default the stored digest to the parser's own recompute of this relation so the
    # content-bind in load_relation_artifact passes; pass an explicit `digest` to force a
    # mismatch (stale-digest guilt case) or to unit-test the gate binding in isolation.
    stored = digest if digest is not None else _digest_of(relation)
    canon = tmp_path / "canon.json"
    canon.write_text(
        json.dumps({"data": records}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    rel = tmp_path / "rel.json"
    rel.write_text(
        json.dumps(
            {"relation": relation, "manifest": {"output_relation_digest": stored}},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    gate = tmp_path / "gate.json"
    gate.write_text(
        json.dumps(
            {
                "verdict": verdict,
                "aggregate": {"passes": aggregate_passes},
                "parser_run_digest": gate_digest or stored,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return canon, rel, gate


# --------------------------------------------------------------------------- #
# build_field — schema §2.2                                                    #
# --------------------------------------------------------------------------- #


def test_build_field_schema_and_verbatim_edges():
    anc = {
        "codes": ["49214", "49219"],
        "sebagian": [False, True],
        "source_locator": [{"lampiran": 10, "pdf_page": 399, "printed_page": 385}],
    }
    f = P.build_field(anc, DIGEST, "2026-07-24")
    assert set(f.keys()) == {
        "codes",
        "sebagian",
        "source_locator",
        "parser_run_digest",
        "adjudication_status",
        "inheritance_verdict",
        "adjudicated_by",
        "adjudicated_at",
    }
    assert f["codes"] == ["49214", "49219"]
    assert f["sebagian"] == [False, True]
    assert f["source_locator"] == [
        {"lampiran": 10, "pdf_page": 399, "printed_page": 385}
    ]
    assert f["parser_run_digest"] == DIGEST
    assert f["adjudication_status"] == "mechanical-only"
    assert f["inheritance_verdict"] == "not-adjudicated"
    assert f["adjudicated_by"] == "mechanical-only"
    assert f["adjudicated_at"] == "2026-07-24"


def test_build_field_deep_copies_edges():
    anc = {
        "codes": ["49214"],
        "sebagian": [False],
        "source_locator": [{"lampiran": 10, "pdf_page": 399, "printed_page": 385}],
    }
    f = P.build_field(anc, DIGEST, "2026-07-24")
    f["codes"].append("X")
    f["source_locator"][0]["lampiran"] = 5
    assert anc["codes"] == ["49214"]  # source untouched
    assert anc["source_locator"][0]["lampiran"] == 10


# --------------------------------------------------------------------------- #
# load_relation_artifact — fail-loud on malformed edge source                  #
# --------------------------------------------------------------------------- #


def test_load_relation_ok(tmp_path):
    relation = _relation({"01111": [("01111", False)]})
    _, rel, _ = _write_world(tmp_path, [], relation)
    got, digest = P.load_relation_artifact(rel)
    assert digest == _digest_of(relation)
    assert got["01111"]["codes"] == ["01111"]


def test_load_relation_content_digest_mismatch_fails(tmp_path):
    # stored digest does not match the relation content — the artifact was edited but its
    # digest left stale; the content-bind (W88) must catch it, gate binding notwithstanding.
    relation = _relation({"01111": [("01111", False)]})
    _, rel, _ = _write_world(
        tmp_path, [], relation, digest="d" * 64
    )  # pragma: allowlist secret
    with pytest.raises(P.PopulateError, match="recomputed from the relation content"):
        P.load_relation_artifact(rel)


def test_load_relation_locator_not_dict_fails(tmp_path):
    rel = tmp_path / "rel.json"
    rel.write_text(
        json.dumps(
            {
                "relation": {
                    "01111": {
                        "codes": ["01111"],
                        "sebagian": [False],
                        "source_locator": ["not-a-dict"],
                    }
                },
                "manifest": {"output_relation_digest": DIGEST},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(P.PopulateError, match="not an object"):
        P.load_relation_artifact(rel)


def test_load_relation_missing_per_edge_locator_fails(tmp_path):
    relation = _relation({"01111": [("01111", False), ("01112", False)]})
    relation["01111"]["source_locator"] = relation["01111"]["source_locator"][:1]
    _, rel, _ = _write_world(tmp_path, [], relation)
    with pytest.raises(
        P.PopulateError, match="every ancestor needs its own checkable locator"
    ):
        P.load_relation_artifact(rel)


def test_load_relation_incomplete_locator_fails(tmp_path):
    relation = _relation({"01111": [("01111", False)]})
    relation["01111"]["source_locator"] = [{"lampiran": 10, "pdf_page": 325}]
    _, rel, _ = _write_world(tmp_path, [], relation)
    with pytest.raises(P.PopulateError, match="incomplete source_locator"):
        P.load_relation_artifact(rel)


def test_load_relation_empty_ancestry_fails(tmp_path):
    relation = _relation({"01111": []})
    _, rel, _ = _write_world(tmp_path, [], relation)
    with pytest.raises(P.PopulateError, match="EMPTY ancestry"):
        P.load_relation_artifact(rel)


def test_load_relation_len_mismatch_fails(tmp_path):
    rel = tmp_path / "rel.json"
    bad = {
        "relation": {
            "01111": {
                "codes": ["01111", "01112"],
                "sebagian": [False],
                "source_locator": [],
            }
        },
        "manifest": {"output_relation_digest": DIGEST},
    }
    rel.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(P.PopulateError, match="len"):
        P.load_relation_artifact(rel)


def test_load_relation_missing_digest_fails(tmp_path):
    rel = tmp_path / "rel.json"
    rel.write_text(
        json.dumps(
            {
                "relation": {
                    "01111": {
                        "codes": ["01111"],
                        "sebagian": [False],
                        "source_locator": [],
                    }
                },
                "manifest": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(P.PopulateError, match="output_relation_digest"):
        P.load_relation_artifact(rel)


def test_load_relation_unexpected_keys_fail(tmp_path):
    rel = tmp_path / "rel.json"
    rel.write_text(
        json.dumps(
            {
                "relation": {
                    "01111": {
                        "codes": ["01111"],
                        "sebagian": [False],
                        "source_locator": [],
                        "title": "X",
                    }
                },
                "manifest": {"output_relation_digest": DIGEST},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(P.PopulateError, match="unexpected keys"):
        P.load_relation_artifact(rel)


# --------------------------------------------------------------------------- #
# assert_gate_certifies — the fail-closed gate binding (W88/W90)               #
# --------------------------------------------------------------------------- #


def test_gate_pass_and_matching_digest_ok(tmp_path):
    _, _, gate = _write_world(tmp_path, [], {}, digest=DIGEST)
    P.assert_gate_certifies(gate, DIGEST)  # innocence: does not raise


def test_gate_verdict_not_pass_fails(tmp_path):
    _, _, gate = _write_world(tmp_path, [], {}, digest=DIGEST, verdict="FAIL")
    with pytest.raises(P.PopulateError, match="not a full PASS"):
        P.assert_gate_certifies(gate, DIGEST)


def test_gate_aggregate_failure_refuses_even_if_verdict_string_says_pass(tmp_path):
    _, _, gate = _write_world(
        tmp_path, [], {}, digest=DIGEST, verdict="PASS", aggregate_passes=False
    )
    with pytest.raises(P.PopulateError, match="aggregate.passes=False"):
        P.assert_gate_certifies(gate, DIGEST)


def test_gate_digest_mismatch_fails(tmp_path):
    _, _, gate = _write_world(
        tmp_path, [], {}, digest=DIGEST, gate_digest="b" * 64
    )  # pragma: allowlist secret
    with pytest.raises(P.PopulateError, match="diverged"):
        P.assert_gate_certifies(gate, DIGEST)


# --------------------------------------------------------------------------- #
# plan_and_apply — populate Batch-B only, additive, idempotent                 #
# --------------------------------------------------------------------------- #


def _std_world():
    records = [
        _rec("01111", None),  # Batch-B
        _rec("01112", None),  # Batch-B
        _rec("77510", "no_oss_risk"),  # Batch-A (out of scope)
    ]
    relation = _relation(
        {
            "01111": [("01111", False)],
            "01112": [("01112", False), ("01113", True)],
            "77510": [
                ("77100", False)
            ],  # relation has it, but Batch-A won't be populated
        }
    )
    return records, relation


def test_populates_batch_b_only():
    records, relation = _std_world()
    before = copy.deepcopy(records)
    n, problems = P.plan_and_apply(
        records, relation, DIGEST, "2026-07-24", expected_batch_b=2, do_apply=True
    )
    assert problems == []
    assert n == 2
    by = {r["kode_kbli_2025"]: r for r in records}
    assert "bps_2020_ancestors" in by["01111"]  # guilt: Batch-B got it
    assert "bps_2020_ancestors" in by["01112"]
    assert "bps_2020_ancestors" not in by["77510"]  # innocence: Batch-A did not
    # edges verbatim from relation
    assert by["01112"]["bps_2020_ancestors"]["codes"] == ["01112", "01113"]
    assert by["01112"]["bps_2020_ancestors"]["sebagian"] == [False, True]
    # additive: every original key/value survives byte-identical
    for b in before:
        m = by[b["kode_kbli_2025"]]
        for k, v in b.items():
            assert m[k] == v


def test_batch_a_requires_explicit_opt_in_and_then_gets_verbatim_edges():
    records, relation = _std_world()
    before = copy.deepcopy(records)

    # Default population is unchanged: only the two Batch-B records are selected.
    n, problems = P.plan_and_apply(
        records, relation, DIGEST, "2026-08-13", expected_batch_b=2, do_apply=False
    )
    assert (n, problems) == (2, [])
    assert records == before

    n, problems = P.plan_and_apply(
        records,
        relation,
        DIGEST,
        "2026-08-13",
        expected_batch_b=2,
        expected_batch_a=1,
        include_batch_a=True,
        do_apply=True,
    )
    assert (n, problems) == (3, [])
    batch_a = next(r for r in records if r["kode_kbli_2025"] == "77510")
    assert batch_a["bps_2020_ancestors"] == {
        "codes": ["77100"],
        "sebagian": [False],
        "source_locator": [{"lampiran": 10, "pdf_page": 325, "printed_page": 311}],
        "parser_run_digest": DIGEST,
        "adjudication_status": "mechanical-only",
        "inheritance_verdict": "not-adjudicated",
        "adjudicated_by": "mechanical-only",
        "adjudicated_at": "2026-08-13",
    }


def test_real_batch_a_01287_and_multi_01700_plus_batch_b_innocence():
    """Pin the certified source facts that motivated the second pass."""
    payload = json.loads(P.DEFAULT_CANONICAL.read_text(encoding="utf-8"))
    real_by_code = {r["kode_kbli_2025"]: r for r in payload["data"]}
    records = copy.deepcopy(
        [real_by_code["01287"], real_by_code["01700"], real_by_code["01111"]]
    )
    # Recreate the pre-second-pass guilt state from the now-cured canonical.
    # The source records stay real; only the deliberately missing field is removed.
    records[0].pop(P.FIELD)
    records[1].pop(P.FIELD)
    relation, digest = P.load_relation_artifact(P.DEFAULT_RELATION)
    batch_b_before = copy.deepcopy(records[2])

    n, problems = P.plan_and_apply(
        records,
        relation,
        digest,
        "2026-08-13",
        expected_batch_b=1,
        expected_batch_a=2,
        include_batch_a=True,
        do_apply=True,
    )
    assert (n, problems) == (2, [])
    by_code = {r["kode_kbli_2025"]: r for r in records}

    one = by_code["01287"]["bps_2020_ancestors"]
    assert one["codes"] == ["01287"]
    assert one["source_locator"] == [
        {"lampiran": 10, "pdf_page": 326, "printed_page": 312}
    ]
    assert one["adjudication_status"] == "mechanical-only"
    assert one["inheritance_verdict"] == "not-adjudicated"

    multi = by_code["01700"]["bps_2020_ancestors"]
    assert multi["codes"] == ["01711", "01712", "01713", "01714", "01715", "01719"]
    assert (
        multi["source_locator"]
        == [{"lampiran": 10, "pdf_page": 329, "printed_page": 315}] * 6
    )

    # Batch-B already carried the field and remains byte-identical after the
    # explicit second pass, not merely semantically equivalent.
    assert by_code["01111"] == batch_b_before


def test_dry_run_does_not_mutate():
    records, relation = _std_world()
    before = copy.deepcopy(records)
    n, problems = P.plan_and_apply(
        records, relation, DIGEST, "2026-07-24", expected_batch_b=2, do_apply=False
    )
    assert n == 2 and problems == []
    assert records == before  # nothing mutated in dry-run


def test_idempotent_skip_present_same_digest():
    records, relation = _std_world()
    P.plan_and_apply(
        records, relation, DIGEST, "2026-07-24", expected_batch_b=2, do_apply=True
    )
    # second pass: everything already carries the field → 0 to populate, no problems
    n, problems = P.plan_and_apply(
        records, relation, DIGEST, "2026-07-24", expected_batch_b=2, do_apply=True
    )
    assert n == 0
    assert problems == []


def test_present_diff_digest_reported_not_clobbered():
    records, relation = _std_world()
    # pre-seed 01111 with an entry from a DIFFERENT (older) digest, e.g. tier-adjudicated
    by = {r["kode_kbli_2025"]: r for r in records}
    by["01111"]["bps_2020_ancestors"] = {
        "codes": ["99999"],
        "sebagian": [False],
        "source_locator": [],
        "parser_run_digest": "c" * 64,  # pragma: allowlist secret
        "adjudication_status": "tier1-2-adjudicated",
        "inheritance_verdict": "inherited-uniform",
        "adjudicated_by": "seat-x",
        "adjudicated_at": "2026-07-01",
    }
    n, problems = P.plan_and_apply(
        records, relation, DIGEST, "2026-07-24", expected_batch_b=2, do_apply=True
    )
    assert n == 1  # only 01112 populated
    assert any("DIFFERENT" in p for p in problems)
    # the pre-existing adjudication is NOT clobbered
    assert (
        by["01111"]["bps_2020_ancestors"]["adjudication_status"]
        == "tier1-2-adjudicated"
    )
    assert by["01111"]["bps_2020_ancestors"]["codes"] == ["99999"]


def test_missing_in_relation_fails_loud():
    records = [_rec("01111", None), _rec("09999", None)]
    relation = _relation({"01111": [("01111", False)]})  # 09999 absent
    n, problems = P.plan_and_apply(
        records, relation, DIGEST, "2026-07-24", expected_batch_b=2, do_apply=True
    )
    assert any("absent from certified relation" in p for p in problems)
    # the innocent one is still populated
    assert n == 1


def test_empty_ancestry_fails_loud():
    records = [_rec("01111", None), _rec("09999", None)]
    relation = _relation({"01111": [("01111", False)], "09999": []})  # empty ancestry
    n, problems = P.plan_and_apply(
        records, relation, DIGEST, "2026-07-24", expected_batch_b=2, do_apply=True
    )
    assert any("EMPTY ancestry" in p for p in problems)


def test_batch_b_count_drift_fails_loud():
    records, relation = _std_world()  # 2 Batch-B
    n, problems = P.plan_and_apply(
        records, relation, DIGEST, "2026-07-24", expected_batch_b=1338, do_apply=False
    )
    assert any("Batch-B population is 2, expected 1338" in p for p in problems)


def test_unclassified_l2_status_fails_loud():
    records = [_rec("01111", None), _rec("55555", "some_future_status")]
    relation = _relation({"01111": [("01111", False)]})
    n, problems = P.plan_and_apply(
        records, relation, DIGEST, "2026-07-24", expected_batch_b=1, do_apply=False
    )
    assert any("unrecognized _l2_status" in p for p in problems)


def test_existing_batch_a_same_digest_is_valid_after_deliberate_second_pass():
    records, relation = _std_world()
    by = {r["kode_kbli_2025"]: r for r in records}
    by["77510"]["bps_2020_ancestors"] = P.build_field(
        relation["77510"], DIGEST, "2026-08-13"
    )
    n, problems = P.plan_and_apply(
        records, relation, DIGEST, "2026-07-24", expected_batch_b=2, do_apply=False
    )
    assert (n, problems) == (2, [])


# --------------------------------------------------------------------------- #
# main() — wiring, exit codes, on-disk additive write                          #
# --------------------------------------------------------------------------- #


def test_main_dry_run_writes_nothing(tmp_path):
    records, relation = _std_world()
    canon, rel, gate = _write_world(tmp_path, records, relation)
    before = canon.read_bytes()
    rc = P.main(
        [
            "--canonical",
            str(canon),
            "--relation",
            str(rel),
            "--gate-report",
            str(gate),
            "--expect-batch-b",
            "2",
        ]
    )
    assert rc == 0
    assert canon.read_bytes() == before  # untouched


def test_main_dry_run_exit1_on_problem(tmp_path):
    records, relation = _std_world()
    canon, rel, gate = _write_world(tmp_path, records, relation)
    # expected mismatch → problem → dry-run exit 1
    rc = P.main(
        [
            "--canonical",
            str(canon),
            "--relation",
            str(rel),
            "--gate-report",
            str(gate),
            "--expect-batch-b",
            "1338",
        ]
    )
    assert rc == 1


def test_main_apply_writes_additive(tmp_path, monkeypatch):
    records, relation = _std_world()
    canon, rel, gate = _write_world(tmp_path, records, relation)
    calls = {"sync": 0, "sidecar": 0}
    monkeypatch.setattr(
        P, "run_sync_script", lambda: calls.__setitem__("sync", calls["sync"] + 1)
    )
    monkeypatch.setattr(
        P, "update_sidecar", lambda: calls.__setitem__("sidecar", calls["sidecar"] + 1)
    )
    rc = P.main(
        [
            "--canonical",
            str(canon),
            "--relation",
            str(rel),
            "--gate-report",
            str(gate),
            "--expect-batch-b",
            "2",
            "--as-of",
            "2026-07-24",
            "--apply",
        ]
    )
    assert rc == 0
    assert calls == {"sync": 1, "sidecar": 1}
    data = json.loads(canon.read_text())["data"]
    by = {r["kode_kbli_2025"]: r for r in data}
    assert "bps_2020_ancestors" in by["01111"]
    assert "bps_2020_ancestors" not in by["77510"]
    assert by["01111"]["bps_2020_ancestors"]["adjudicated_at"] == "2026-07-24"


def test_main_apply_reconciles_when_nothing_to_populate(tmp_path, monkeypatch):
    # Recovery path (family #2): a second --apply with nothing new to write must STILL
    # run sync + sidecar, so a prior partial apply (canonical written, sync failed) can be
    # recovered by re-running — never a dead end that leaves consumers stale.
    records, relation = _std_world()
    canon, rel, gate = _write_world(tmp_path, records, relation)
    calls = {"sync": 0, "sidecar": 0}
    monkeypatch.setattr(
        P, "run_sync_script", lambda: calls.__setitem__("sync", calls["sync"] + 1)
    )
    monkeypatch.setattr(
        P, "update_sidecar", lambda: calls.__setitem__("sidecar", calls["sidecar"] + 1)
    )
    argv = [
        "--canonical",
        str(canon),
        "--relation",
        str(rel),
        "--gate-report",
        str(gate),
        "--expect-batch-b",
        "2",
        "--apply",
    ]
    assert P.main(argv) == 0
    assert calls == {"sync": 1, "sidecar": 1}  # first apply populated + reconciled
    assert P.main(argv) == 0
    assert calls == {"sync": 2, "sidecar": 2}  # nothing new, still reconciled


def test_main_apply_refuses_on_failed_gate(tmp_path, monkeypatch):
    records, relation = _std_world()
    canon, rel, gate = _write_world(tmp_path, records, relation, verdict="FAIL")
    before = canon.read_bytes()
    monkeypatch.setattr(
        P,
        "run_sync_script",
        lambda: (_ for _ in ()).throw(AssertionError("must not sync")),
    )
    with pytest.raises(P.PopulateError, match="not a full PASS"):
        P.main(
            [
                "--canonical",
                str(canon),
                "--relation",
                str(rel),
                "--gate-report",
                str(gate),
                "--expect-batch-b",
                "2",
                "--apply",
            ]
        )
    assert canon.read_bytes() == before  # never touched


def test_main_existing_different_digest_is_loud_and_no_file_is_overwritten(
    tmp_path, monkeypatch, caplog
):
    records, relation = _std_world()
    records[0]["bps_2020_ancestors"] = P.build_field(
        relation["01111"],
        "c" * 64,
        "2026-07-01",  # pragma: allowlist secret
    )
    canon, rel, gate = _write_world(tmp_path, records, relation)
    before = canon.read_bytes()
    monkeypatch.setattr(
        P,
        "run_sync_script",
        lambda: (_ for _ in ()).throw(AssertionError("must not sync")),
    )
    monkeypatch.setattr(
        P,
        "update_sidecar",
        lambda: (_ for _ in ()).throw(AssertionError("must not sidecar")),
    )

    rc = P.main(
        [
            "--canonical",
            str(canon),
            "--relation",
            str(rel),
            "--gate-report",
            str(gate),
            "--expect-batch-b",
            "2",
            "--apply",
        ]
    )
    assert rc == 1
    assert "DIFFERENT parser_run_digest (not overwritten)" in caplog.text
    assert canon.read_bytes() == before


def test_main_apply_exit1_on_problem_no_write(tmp_path, monkeypatch):
    records = [_rec("01111", None), _rec("09999", None)]  # 09999 missing from relation
    relation = _relation({"01111": [("01111", False)]})
    canon, rel, gate = _write_world(tmp_path, records, relation)
    before = canon.read_bytes()
    monkeypatch.setattr(
        P,
        "run_sync_script",
        lambda: (_ for _ in ()).throw(AssertionError("must not sync")),
    )
    monkeypatch.setattr(
        P,
        "update_sidecar",
        lambda: (_ for _ in ()).throw(AssertionError("must not sidecar")),
    )
    rc = P.main(
        [
            "--canonical",
            str(canon),
            "--relation",
            str(rel),
            "--gate-report",
            str(gate),
            "--expect-batch-b",
            "2",
            "--apply",
        ]
    )
    assert rc == 1
    assert canon.read_bytes() == before  # problems present → refused to write


def test_running_apply_twice_is_byte_noop_and_does_not_touch_sidecar(
    tmp_path, monkeypatch
):
    records, relation = _std_world()
    canon, rel, gate = _write_world(tmp_path, records, relation)
    synced = tmp_path / "mouth-dataset.json"
    sidecar = tmp_path / "kbli-dataset-version.json"
    sidecar.write_text(
        json.dumps(
            {"datasetSha256": "sha256:old", "lastModified": "2026-01-01"}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )

    def sync_fixture() -> None:
        shutil.copyfile(canon, synced)

    monkeypatch.setattr(P, "run_sync_script", sync_fixture)
    monkeypatch.setattr(P, "SIDECAR_DATASET_PATH", synced)
    monkeypatch.setattr(P, "SIDECAR_PATH", sidecar)
    argv = [
        "--canonical",
        str(canon),
        "--relation",
        str(rel),
        "--gate-report",
        str(gate),
        "--expect-batch-b",
        "2",
        "--as-of",
        "2026-08-13",
        "--apply",
    ]

    assert P.main(argv) == 0
    first_bytes = {
        "canonical": canon.read_bytes(),
        "synced": synced.read_bytes(),
        "sidecar": sidecar.read_bytes(),
    }
    first_sidecar_mtime = sidecar.stat().st_mtime_ns

    assert P.main(argv) == 0
    assert canon.read_bytes() == first_bytes["canonical"]
    assert synced.read_bytes() == first_bytes["synced"]
    assert sidecar.read_bytes() == first_bytes["sidecar"]
    assert sidecar.stat().st_mtime_ns == first_sidecar_mtime
