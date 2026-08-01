"""What the patch may touch, and — more importantly — what it may not.

The dangerous failure here is not a wrong number: it is patching a code whose
2025 scope is WIDER than the activity the annex restricts, which would assert a
foreign-ownership cap over business the instrument never touched. So most of
this file is innocence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

import apply_perpres_foreign_caps as mod  # noqa: E402
from apply_perpres_foreign_caps import ADJUDICATION, BROADER, PLAIN, RENAMED, plan  # noqa: E402
from perpres_foreign_cap_relation import RELATION, classify_join  # noqa: E402

CANONICAL = Path(__file__).resolve().parents[2].parent / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"


def _rec(code, ancestors, cap, status="TERBUKA", **extra):
    return {"kode_kbli_2025": code, "judul": "x", "pma_max_asing": cap,
            "pma_status": status, "bps_2020_ancestors": {"codes": ancestors}, **extra}


# --- the table must exactly cover the evidence ------------------------------

def test_every_divergent_code_on_the_real_dataset_is_adjudicated():
    records = json.loads(CANONICAL.read_text())["data"]
    _, refusals = plan(records)
    assert refusals == [], "a divergence with no written verdict is a decision made by silence"


def test_the_table_names_no_code_the_evidence_does_not():
    """Every adjudicated code must be one the instrument actually reaches.

    This asserted `set(ADJUDICATION) == divergent` until the cure ran, and that
    equality is only true BEFORE it: once the plain codes are patched they stop
    being divergent while the table must keep them — the table is the record of
    what was decided, not a snapshot of what is still broken. The version that
    survives the cure is: no phantom entries, and no divergence left undecided
    (the test above). Written down because the equality passed locally and
    failed in CI for exactly this reason: the suite was run before the data
    change it was about.
    """
    records = json.loads(CANONICAL.read_text())["data"]
    result = classify_join(RELATION, records)
    judged = {i["kbli_2025"] for bucket in ("agree", "disagree", "ambiguous")
              for i in result[bucket]}
    assert set(ADJUDICATION) <= judged


def test_every_plain_code_now_carries_the_lawful_cap():
    """The cure's own end-proof, read off the dataset rather than the applier.

    A `plain` verdict is a promise that the code SHOULD carry the annex's cap.
    Once applied, it must actually agree — so this test fails both if the patch
    was never run and if something later reverts one of the twenty.
    """
    records = json.loads(CANONICAL.read_text())["data"]
    result = classify_join(RELATION, records)
    agreeing = {i["kbli_2025"] for i in result["agree"]}
    plain = {c for c, (verdict, _) in ADJUDICATION.items() if verdict == PLAIN}
    assert plain <= agreeing, f"plain but still divergent: {sorted(plain - agreeing)}"


# --- guilt ------------------------------------------------------------------

def test_a_plain_code_is_patched_with_its_cap_and_its_locator():
    planned, refusals = plan([_rec("25200", ["25200"], 100)])
    assert refusals == [] and len(planned) == 1
    patch = planned[0]["patch"]
    assert patch["pma_max_asing"] == 49
    assert patch["pma_status"] == "TERBATAS"
    assert patch["pma_cap_verified"] is True
    assert "49/2021" in patch["pma_official_basis"]
    assert "Menteri Pertahanan" in patch["pma_kondisi"]


def test_zero_percent_foreign_becomes_TERBATAS_not_TERTUTUP():
    """'Modal dalam negeri 100%' closes the activity to FOREIGN capital, not to
    everyone. TERTUTUP in this catalogue holds narcotics and alcohol."""
    planned, _ = plan([_rec("79122", ["79122"], 100)])
    patch = planned[0]["patch"]
    assert patch["pma_max_asing"] == 0
    assert patch["pma_status"] == "TERBATAS"
    # the annex's OWN condition wins over the generic 0% wording
    assert patch["pma_kondisi"] == "domestic capital and Islamic faith requirement"

    # ...and a 0% entry the annex states bare still says why it is 0
    bare, _ = plan([_rec("16221", ["16221"], 100)])
    assert bare[0]["patch"]["pma_max_asing"] == 0
    assert "domestic capital only" in bare[0]["patch"]["pma_kondisi"]


# --- innocence: the whole point ---------------------------------------------

def test_a_broader_code_is_never_patched():
    planned, refusals = plan([_rec("10761", ["10761"], 100)])
    assert planned == [] and refusals == []
    assert ADJUDICATION["10761"][0] == BROADER


def test_a_renamed_but_unproven_code_is_never_patched():
    planned, _ = plan([_rec("21021", ["21021"], 100)])
    assert planned == [] and ADJUDICATION["21021"][0] == RENAMED


def test_a_record_already_matching_the_law_is_left_alone():
    planned, _ = plan([_rec("25200", ["25200"], 49, status="TERBATAS")])
    assert planned == []


def test_a_code_outside_the_instrument_is_untouched():
    planned, refusals = plan([_rec("62010", ["62010"], 100)])
    assert planned == [] and refusals == []


# --- the guards are guards, not decoration ----------------------------------

def test_marking_a_two_cap_code_plain_is_refused(monkeypatch):
    monkeypatch.setitem(ADJUDICATION, "30111", (PLAIN, "wrong on purpose"))
    _, refusals = plan([_rec("30111", ["30111"], 100)])
    assert any("two caps" in r and "30111" in r for r in refusals)


def test_an_unadjudicated_divergence_refuses_the_run(monkeypatch):
    monkeypatch.delitem(ADJUDICATION, "25200")
    planned, refusals = plan([_rec("25200", ["25200"], 100)])
    assert planned == []
    assert any("never adjudicated" in r for r in refusals)


# --- writing ----------------------------------------------------------------

def _dataset(tmp_path, records):
    p = tmp_path / "canon.json"
    p.write_text(json.dumps({"data": records}, ensure_ascii=False))
    return p


def test_apply_writes_then_a_second_run_is_a_no_op(tmp_path, capsys):
    path = _dataset(tmp_path, [_rec("25200", ["25200"], 100)])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    after = json.loads(path.read_text())["data"][0]
    assert after["pma_max_asing"] == 49 and after["pma_status"] == "TERBATAS"
    capsys.readouterr()
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    assert "planned patches: 0" in capsys.readouterr().out


def test_apply_never_overwrites_an_existing_condition(tmp_path):
    path = _dataset(tmp_path, [_rec("79122", ["79122"], 100, pma_kondisi="hand-written note")])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    after = json.loads(path.read_text())["data"][0]
    assert after["pma_kondisi"] == "hand-written note"
    assert after["pma_max_asing"] == 0        # the cap still lands


def test_apply_preserves_the_datasets_own_serialisation(tmp_path):
    """The canonical file is 540k lines at indent=2. If this writer's format
    drifts, a 20-record change arrives as a whole-file diff nobody can review —
    so a run with nothing to patch must leave the bytes untouched."""
    path = tmp_path / "canon.json"
    body = json.dumps({"data": [_rec("62010", ["62010"], 100)]}, ensure_ascii=False, indent=2)
    path.write_text(body + "\n", encoding="utf-8")
    before = path.read_bytes()
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    assert path.read_bytes() == before


def test_applying_to_a_fixture_never_touches_the_repos_sidecar(tmp_path):
    """Applying to the real canonical fans the change out to four copies and
    bumps the SEO sidecar. Applying to a fixture must do neither — a test that
    rewrites production state is its own defect (W96)."""
    sidecar_before = mod.SIDECAR_PATH.read_bytes()
    copy_before = mod.SIDECAR_DATASET_PATH.stat().st_mtime_ns
    path = _dataset(tmp_path, [_rec("25200", ["25200"], 100)])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    assert mod.SIDECAR_PATH.read_bytes() == sidecar_before
    assert mod.SIDECAR_DATASET_PATH.stat().st_mtime_ns == copy_before


def test_dry_run_writes_nothing(tmp_path):
    path = _dataset(tmp_path, [_rec("25200", ["25200"], 100)])
    before = path.read_text()
    assert mod.main(["--dataset", str(path)]) == 0
    assert path.read_text() == before


def test_a_refusal_exits_nonzero_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.delitem(ADJUDICATION, "25200")
    path = _dataset(tmp_path, [_rec("25200", ["25200"], 100)])
    before = path.read_text()
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text() == before
