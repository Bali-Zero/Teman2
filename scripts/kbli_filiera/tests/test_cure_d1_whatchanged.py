"""Guilt and innocence for D-1 (Zero, 2026-10-11): nine whatChanged fields, canonical + copies + gold, and the
knowledge-graph script that carries the same sentences to the conversational channels."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _hardened_cure_io as H  # noqa: E402
import cure_d1_whatchanged as mod  # noqa: E402
import kg_cure_d1_whatchanged as kg  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC = json.loads(mod.SPEC_PATH.read_text(encoding="utf-8"))
EDGES = mod._edges(REPO_ROOT / SPEC["edges_file"])
# What a client must never read in this field: pipeline provenance, Italian, a predecessor the record cannot carry.
JARGON = re.compile(
    r"PR #|pp28_sources|score=|\.png|corrected 20\d\d|con aggregazione|codice|rinumerato|"
    r"Auto-matched|Previous code\(s\)|KBLI 2020:|Lampiran|sha ",
    re.IGNORECASE,
)


def test_the_nine_new_sentences_carry_no_pipeline_jargon():
    news = [e["patch"][mod.FIELD] for e in SPEC["canonical"]]
    assert len(news) == 9 and not [t for t in news if JARGON.search(t)]


def test_the_old_texts_are_what_the_guard_catches():
    caught = [e["code"] for e in SPEC["canonical"] if JARGON.search(e["old_text"])]
    assert set(caught) == {e["code"] for e in SPEC["canonical"]}


def test_gold_and_kg_say_what_canonical_says():
    canon = {e["code"]: e["patch"][mod.FIELD] for e in SPEC["canonical"]}
    assert {g["code"] for g in SPEC["gold"]} == {"46100", "60103", "60203"}
    assert all(g["new"] == canon[g["code"]] for g in SPEC["gold"])
    assert all(k["new"] == canon[k["entity_id"].split(":")[1]] for k in SPEC["kg"])


def test_the_real_dataset_and_gold_are_cured_and_a_rerun_is_a_noop():
    _, records, _ = H.load_dataset(mod.CANONICAL)
    by_code = {r["kode_kbli_2025"]: r for r in records}
    for e in SPEC["canonical"]:
        assert H.read_field(by_code[e["code"]], mod.FIELD) == e["patch"][mod.FIELD]
    assert mod.plan_canonical(SPEC, records, EDGES) == {}
    assert mod.plan_gold(SPEC, json.loads(mod.GOLD.read_text(encoding="utf-8"))) == {}


def test_every_sentence_rests_on_the_record_and_on_the_bps_edges_it_names():
    for e in SPEC["canonical"]:
        for a, b in e.get("expect_bps_edges", []):
            assert (a, b) in EDGES
    assert ["52101", "52109"] in next(
        e for e in SPEC["canonical"] if e["code"] == "52101"
    )["expect_bps_edges"]


def _fixture(code="60103"):
    entry = copy.deepcopy(next(e for e in SPEC["canonical"] if e["code"] == code))
    rec = {
        "kode_kbli_2025": code,
        "bps_2020_ancestors": {"codes": entry["expect"]["bps_2020_ancestors.codes"]},
        "intel_2026": {"whatChanged": entry["old_text"], "whatItMeans": "x"},
    }
    entry["old_sha256"] = H.sha256_of(rec)
    after = copy.deepcopy(rec)
    H.write_field(after, mod.FIELD, entry["patch"][mod.FIELD])
    entry["new_sha256"] = H.sha256_of(after)
    return {**SPEC, "canonical": [entry]}, [rec]


def test_a_clean_fixture_plans_the_one_patch():
    spec, records = _fixture()
    assert list(mod.plan_canonical(spec, records, EDGES)) == ["60103"]


def test_refuses_when_the_ancestors_moved():
    spec, records = _fixture()
    records[0]["bps_2020_ancestors"]["codes"] = ["60102"]
    with pytest.raises(H.CureError, match="expect"):
        mod.plan_canonical(spec, records, EDGES)


def test_refuses_when_a_named_bps_edge_is_absent():
    spec, records = _fixture("52101")
    with pytest.raises(H.CureError, match="52101 -> 52109"):
        mod.plan_canonical(spec, records, EDGES - {("52101", "52109")})


def test_refuses_a_record_that_drifted_elsewhere():
    spec, records = _fixture()
    records[0]["intel_2026"]["whatItMeans"] = "edited by hand"
    with pytest.raises(H.CureError, match="drifted"):
        mod.plan_canonical(spec, records, EDGES)


def test_gold_refuses_a_live_text_that_is_neither_old_nor_new():
    gold = {g["code"]: {"whatChanged": g["old"]} for g in SPEC["gold"]}
    assert set(mod.plan_gold(SPEC, gold)) == {"46100", "60103", "60203"}
    gold["60103"]["whatChanged"] = "rewritten elsewhere"
    with pytest.raises(H.CureError, match="60103"):
        mod.plan_gold(SPEC, gold)


def _live():
    return {e["entity_id"]: "old " + e["entity_id"] for e in SPEC["kg"]} | {
        k: None for k in SPEC["kg_without_the_field"]
    }


def _kg_spec(live):
    return {
        **SPEC,
        "kg": [
            {
                **e,
                "old_sha256": hashlib.sha256(live[e["entity_id"]].encode()).hexdigest(),
            }
            for e in SPEC["kg"]
        ],
    }


def test_kg_writes_only_rows_whose_text_hashes_to_the_pin():
    live = _live()
    spec = _kg_spec(live)
    live["kbli:60103"] = "changed between the export and the run"
    writes, report = kg.plan(spec, live)
    assert (
        "kbli:60103" not in {w["entity_id"] for w in writes}
        and len(writes) == len(SPEC["kg"]) - 1
    )
    assert kg.drifted(report)


def test_kg_never_gives_a_field_to_a_node_without_one():
    live = _live()
    writes, report = kg.plan(_kg_spec(live), live)
    assert not {w["entity_id"] for w in writes} & set(SPEC["kg_without_the_field"])
    assert not kg.drifted(report)
    live["kbli:10433"] = "a field appeared"
    assert kg.drifted(kg.plan(_kg_spec(live), live)[1])


def test_kg_backup_inside_the_repository_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="inside the repository"):
        kg.backup({}, SPEC, REPO_ROOT / "tmp-backups")
    assert kg.backup({"kbli:46100": "x"}, SPEC, tmp_path).exists()
