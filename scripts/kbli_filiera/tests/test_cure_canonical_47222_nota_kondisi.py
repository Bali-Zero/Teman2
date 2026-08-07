"""Guilt and innocence for cure G — 47222's pma_nota/pma_kondisi contradicted
their own pma_official_basis.

47221 and 47222 sit next to each other (alcoholic vs non-alcoholic retail);
the dangerous failure here is not "the wrong sentence", it's bleeding 47221's
alcohol subject into 47222's note, or touching 47221 at all while fixing its
neighbour — same class of risk as the 86101/86103 cure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

import cure_canonical_47222_nota_kondisi as mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_SPEC = json.loads(
    (
        REPO_ROOT
        / "scripts"
        / "kbli_filiera"
        / "cure_specs"
        / "canonical_47222_nota_kondisi_2026_08_07.json"
    ).read_text(encoding="utf-8")
)


def _canonical_file(tmp_path, records):
    p = tmp_path / "canon.json"
    p.write_text(
        json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return p


_OLD_WHATCHANGED = (
    "Unchanged from KBLI 2020 — direct match. Direct match from KBLI 2020 — "
    "same code, same scope. The closed-to-foreign-investment status "
    "(TERTUTUP, 0% PMA) carries over unchanged: retail of non-alcoholic "
    "beverages remains reserved for domestic ownership, exactly as under "
    "the 2020 classification."
)
_NEW_WHATCHANGED = (
    "Unchanged from KBLI 2020 — direct match. Direct match from KBLI 2020 — "
    "same code, same scope. The activity is allocated to Koperasi and UMKM "
    "under Perpres 49/2021 Lampiran II; foreign investment is 0% (TERBATAS "
    "by reservation, not TERTUTUP by law) — carried over unchanged from the "
    "2020 classification."
)


def _base_record(**overrides):
    rec = {
        "kode_kbli_2025": "47222",
        "pma_status": "TERBATAS",
        "pma_max_asing": 0,
        "pma_cap_verified": True,
        "pma_official_basis": "... KEMITRAAN column EMPTY = pure reservation ...",
        "pma_kondisi": "Kemitraan dengan UMKM/Koperasi",
        "pma_nota": "Perdagangan eceran minuman beralkohol di bar",
        "intel_2026": {"whatChanged": _OLD_WHATCHANGED},
    }
    rec.update(overrides)
    return rec


def _spec(fields=None, expect=None):
    return {
        "code": "47222",
        "expect": expect
        if expect is not None
        else {
            "pma_status": "TERBATAS",
            "pma_max_asing": 0,
            "pma_cap_verified": True,
            "pma_official_basis_contains": "KEMITRAAN column EMPTY",
        },
        "fields": fields
        if fields is not None
        else {
            "pma_nota": {
                "old": "Perdagangan eceran minuman beralkohol di bar",
                "new": "Dialokasikan untuk Koperasi dan UMKM — Perpres 49/2021 Lampiran II (Minuman Tidak Beralkohol)",
            },
            "pma_kondisi": {
                "old": "Kemitraan dengan UMKM/Koperasi",
                "new": None,
            },
            "intel_2026.whatChanged": {
                "old": _OLD_WHATCHANGED,
                "new": _NEW_WHATCHANGED,
            },
        },
    }


# --- the real record, post-cure -----------------------------------------------


def test_the_real_47222_is_cured():
    _, records, _ = mod.load(mod.CANONICAL)
    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    rec = by_code["47222"]
    assert "beralkohol" not in (rec.get("pma_nota") or "")
    assert rec.get("pma_kondisi") is None
    assert rec.get("pma_status") == "TERBATAS"
    assert rec.get("pma_max_asing") == 0
    assert rec.get("pma_cap_verified") is True
    assert "KEMITRAAN column EMPTY" in (rec.get("pma_official_basis") or "")
    what_changed = ((rec.get("intel_2026") or {}).get("whatChanged")) or ""
    assert "TERTUTUP, 0% PMA) carries over unchanged" not in what_changed
    assert "Koperasi and UMKM under Perpres 49/2021 Lampiran II" in what_changed
    assert what_changed.startswith(
        "Unchanged from KBLI 2020 — direct match. Direct match from KBLI 2020 — same code, same scope."
    )


def test_47221_is_byte_untouched():
    """The innocence that matters most here: 47221 (alcoholic) and 47222
    (non-alcoholic) sit next to each other and the cure must not bleed."""
    _, records, _ = mod.load(mod.CANONICAL)
    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    rec = by_code["47221"]
    assert rec.get("pma_nota") == "Perdagangan eceran minuman beralkohol"
    assert rec.get("pma_kondisi") == "Kemitraan dengan UMKM/Koperasi"


def test_the_real_cure_is_a_clean_noop_without_writing():
    """W96: never risk writing production state, even a believed no-op."""
    _, records, _ = mod.load(mod.CANONICAL)
    verdicts = mod.plan(REAL_SPEC, records)
    assert verdicts and all(v["action"] == "noop" for v in verdicts.values())


# --- guilt --------------------------------------------------------------------


def test_apply_patches_all_three_fields(tmp_path):
    path = _canonical_file(tmp_path, [_base_record()])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    _, records, _ = mod.load(path)
    rec = records[0]
    assert rec["pma_nota"] == (
        "Dialokasikan untuk Koperasi dan UMKM — Perpres 49/2021 Lampiran II (Minuman Tidak Beralkohol)"
    )
    assert rec["pma_kondisi"] is None
    assert rec["intel_2026"]["whatChanged"] == _NEW_WHATCHANGED


def test_apply_leaves_sibling_intel_2026_keys_alone(tmp_path):
    """write_field must only ever touch the one dotted leaf it was told to —
    a sibling key on the same nested dict is the innocence control for the
    dotted-path walk itself."""
    rec = _base_record()
    rec["intel_2026"]["riskLabel"] = "Medium-Low"
    path = _canonical_file(tmp_path, [rec])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    _, records, _ = mod.load(path)
    after = records[0]
    assert after["intel_2026"]["whatChanged"] == _NEW_WHATCHANGED
    assert after["intel_2026"]["riskLabel"] == "Medium-Low"


def test_second_run_is_a_no_op(tmp_path, capsys):
    path = _canonical_file(tmp_path, [_base_record()])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    capsys.readouterr()
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    assert "already cured" in capsys.readouterr().out


def test_untouched_fields_survive(tmp_path):
    rec = _base_record()
    path = _canonical_file(tmp_path, [rec])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    _, records, _ = mod.load(path)
    after = records[0]
    assert after["pma_status"] == "TERBATAS"
    assert after["pma_max_asing"] == 0
    assert after["pma_cap_verified"] is True
    assert "KEMITRAAN column EMPTY" in after["pma_official_basis"]


# --- guilt: refusals ---------------------------------------------------------


def test_refuses_when_the_code_is_missing(tmp_path):
    path = _canonical_file(tmp_path, [{"kode_kbli_2025": "99999"}])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_status_has_drifted(tmp_path):
    path = _canonical_file(tmp_path, [_base_record(pma_status="TERTUTUP")])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_cap_has_drifted(tmp_path):
    path = _canonical_file(tmp_path, [_base_record(pma_max_asing=49)])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_cap_verified_is_not_true(tmp_path):
    path = _canonical_file(tmp_path, [_base_record(pma_cap_verified=None)])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_official_basis_no_longer_names_the_premise(tmp_path):
    path = _canonical_file(
        tmp_path, [_base_record(pma_official_basis="something unrelated")]
    )
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_live_nota_has_drifted(tmp_path):
    path = _canonical_file(tmp_path, [_base_record(pma_nota="something else entirely")])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_live_kondisi_has_drifted(tmp_path):
    path = _canonical_file(
        tmp_path, [_base_record(pma_kondisi="a human already fixed this differently")]
    )
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_live_whatchanged_has_drifted(tmp_path):
    """Nested-path drift must refuse exactly like a top-level field — someone
    already rewrote the tail differently, do not clobber it."""
    path = _canonical_file(
        tmp_path,
        [_base_record(intel_2026={"whatChanged": "a human already rewrote this tail"})],
    )
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_intel_2026_is_missing_entirely(tmp_path):
    """`_has_field` must walk the dotted path and refuse — not KeyError —
    when the parent dict itself is absent."""
    rec = _base_record()
    del rec["intel_2026"]
    path = _canonical_file(tmp_path, [rec])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


# --- innocence ----------------------------------------------------------------


def test_a_neighbor_record_in_a_fixture_is_never_touched(tmp_path):
    neighbor = {
        "kode_kbli_2025": "47221",
        "pma_nota": "Perdagangan eceran minuman beralkohol",
        "pma_kondisi": "Kemitraan dengan UMKM/Koperasi",
    }
    path = _canonical_file(tmp_path, [_base_record(), dict(neighbor)])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    _, records, _ = mod.load(path)
    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    assert by_code["47221"] == neighbor


def test_dry_run_writes_nothing(tmp_path):
    path = _canonical_file(tmp_path, [_base_record()])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--dataset", str(path)]) == 0
    assert path.read_text(encoding="utf-8") == before
