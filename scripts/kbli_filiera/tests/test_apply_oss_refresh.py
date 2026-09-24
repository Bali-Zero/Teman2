"""Tests for apply_oss_refresh.py (#7136 OSS refresh loop, ADOPT adjudication).

Two routes: l2_transform (93114, cure-owned per_skala, applyable premises) and
quarantine_owner (the other 9, gated on the signed session adjudication —
cure_specs/oss_refresh_adjudication_2026_09_22.json). Fabricated in-memory
records exercise the classify()/plan() guards in isolation (guilt: a missing
or tampered pin refuses; innocence: the real pre-cure shape patches, the
real post-cure shape noops) — same discipline as
test_cure_pr2b_source_rows_93114_43110.py. TestRealCatalogue checks the
actually-applied canonical after this PR's own --apply, including the real
20111 dict-shaped disputed value and the coverage axis.
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from pathlib import Path

import pytest

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import _coverage_basis as coverage  # noqa: E402
import _hardened_cure_io as H  # noqa: E402
import apply_oss_refresh as cure  # noqa: E402

DISPUTED_KEY = "per_skala_disputed_pp28_collision"
CODE = "TQ01"          # synthetic quarantine_owner code
L2_CODE = "TL01"       # synthetic l2_transform code

OSS_ROWS = [
    {"skala_usaha": ["Besar"], "kategori_risiko": "Tinggi", "scope_index": 0, "scope_uraian": "Test scope A"},
    {"skala_usaha": ["Menengah"], "kategori_risiko": "Menengah Tinggi", "scope_index": 1, "scope_uraian": "Test scope B"},
]

L2_NEW_PER_SKALA = [
    {"skala_usaha": ["Mikro"], "kategori_risiko": "Rendah"},
    {"skala_usaha": ["Besar"], "kategori_risiko": "Tinggi"},
]


_UNSET = object()
DISPUTED_BLOCK = [{"kategori_risiko": "Tinggi", "skala_usaha": ["Besar"], "parameter": "legacy"}]


# --------------------------------------------------------------------- fixtures


def _base_record(**overrides) -> dict:
    rec = {
        "kode_kbli_2025": CODE,
        "judul": "Test Quarantine Code",
        "per_skala": [],
        DISPUTED_KEY: copy.deepcopy(DISPUTED_BLOCK),
        "_l2_status": "no_oss_risk",
        "l4_bali": {
            "status": "NON_CLASSIFICABILE", "blocked": False, "confidence": "LOW",
            "needs_review": True, "verdict_state": "unknown",
        },
    }
    rec.update(overrides)
    return rec


def _spec_entry(record: dict, *, oss_rows: list | None = None) -> dict:
    return {
        "class": "published",
        "uuid": "11111111-1111-1111-1111-111111111111",
        "licensing_state": "declared_gap",
        "route": "quarantine_owner",
        "quarantined_by": [DISPUTED_KEY],
        "body_sha256": "deadbeef",
        "besar_verdict": "OPEN",
        "record_sha256": H.sha256_of(record),
        "oss_rows": copy.deepcopy(oss_rows if oss_rows is not None else OSS_ROWS),
    }


def _adjudication_entry(entry: dict, *, decision="adopt_oss_2025", disputed_key=DISPUTED_KEY,
                         record_sha256=None, oss_rows_sha256=None, disputed_sha256=_UNSET,
                         data_note_append="Test note.") -> dict:
    return {
        "decision": decision,
        "record_sha256": record_sha256 if record_sha256 is not None else entry["record_sha256"],
        "body_sha256": entry["body_sha256"],
        "oss_rows_sha256": oss_rows_sha256 if oss_rows_sha256 is not None else H.sha256_of(entry["oss_rows"]),
        "disputed_key": disputed_key,
        "disputed_sha256": H.sha256_of(DISPUTED_BLOCK) if disputed_sha256 is _UNSET else disputed_sha256,
        "reason": "test reason",
        "data_note_append": data_note_append,
    }


def _l2_record(**overrides) -> dict:
    rec = {
        "kode_kbli_2025": L2_CODE,
        "judul": "Test L2 Transform Code",
        "per_skala": [{"skala_usaha": ["Mikro"], "kategori_risiko": "Rendah"}],
        "_l2_source": None,
        "_l2_status": "no_oss_risk",
        "absent_probes": ["x"],
        "l4_bali": {
            "status": "NON_CLASSIFICABILE", "blocked": False, "confidence": "LOW",
            "needs_review": True, "verdict_state": "unknown",
        },
    }
    rec.update(overrides)
    return rec


def _l2_spec_entry(record: dict, *, new_per_skala: list | None = None) -> dict:
    new_rows = copy.deepcopy(new_per_skala if new_per_skala is not None else L2_NEW_PER_SKALA)
    return {
        "class": "changed",
        "uuid": "22222222-2222-2222-2222-222222222222",
        "licensing_state": "declared_gap",
        "route": "l2_transform",
        "quarantined_by": [],
        "body_sha256": "cafebabe",
        "besar_verdict": "AMBIGUOUS",
        "premises": {
            "per_skala": {"old_sha256": H.sha256_of(record.get("per_skala")), "new_sha256": H.sha256_of(new_rows)},
            "_l2_source": {"old_sha256": H.sha256_of(record.get("_l2_source")), "new_sha256": H.sha256_of(coverage.OSS_2025_SOURCE)},
            "_l2_status": {"old_sha256": H.sha256_of(record.get("_l2_status")), "new_sha256": H.sha256_of(None)},
            "absent_probes": {"old_sha256": H.sha256_of(record.get("absent_probes")), "new_sha256": H.sha256_of(None)},
        },
        "per_skala": new_rows,
        "set": {"_l2_source": coverage.OSS_2025_SOURCE},
        "drop_keys": ["_l2_status", "absent_probes"],
    }


def _spec_doc(*entries: tuple[str, dict], canonical_sha256: str | None = None) -> dict:
    doc = {
        "_generated_by": "test",
        "_doc": "test",
        "version": "test",
        "fetched": "2026-09-22",
        "source": {},
        "codes": {code: entry for code, entry in entries},
    }
    # Omitted by default: the whole-file pin is only meaningful on an all-patch
    # run and would otherwise gate every fixture on the tmp canonical's bytes.
    if canonical_sha256 is not None:
        doc["canonical_sha256"] = canonical_sha256
    return doc


def _adjudication_doc(*entries: tuple[str, dict]) -> dict:
    return {
        "_doc": "test",
        "adjudicated_by": "test",
        "basis": "test",
        "codes": {code: entry for code, entry in entries},
    }


def _write_json(tmp_path: Path, name: str, obj: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_dataset(tmp_path: Path, records: list[dict]) -> Path:
    path = tmp_path / "canonical.json"
    path.write_text(json.dumps({"data": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# --------------------------------------------------------- classify_quarantine_owner


class TestGuiltQuarantineOwner:
    def test_missing_adjudication_entry_refuses(self):
        rec = _base_record()
        entry = _spec_entry(rec)
        with pytest.raises(H.CureError, match="no adjudication entry"):
            cure.classify_quarantine_owner(rec, CODE, entry, {})

    def test_wrong_decision_refuses(self):
        rec = _base_record()
        entry = _spec_entry(rec)
        adj = _adjudication_entry(entry, decision="hold")
        with pytest.raises(H.CureError, match="not 'adopt_oss_2025'"):
            cure.classify_quarantine_owner(rec, CODE, entry, {CODE: adj})

    def test_adjudication_record_sha256_mismatch_refuses(self):
        """Adjudication's own record_sha256 pin disagrees with the spec's —
        an independently-forged/stale adjudication, not a live-record drift."""
        rec = _base_record()
        entry = _spec_entry(rec)
        adj = _adjudication_entry(entry, record_sha256="0" * 64)
        with pytest.raises(H.CureError, match="record_sha256 does not match the spec's pin"):
            cure.classify_quarantine_owner(rec, CODE, entry, {CODE: adj})

    def test_tampered_oss_rows_refuses(self):
        rec = _base_record()
        entry = _spec_entry(rec)
        adj = _adjudication_entry(entry)
        tampered_entry = copy.deepcopy(entry)
        tampered_entry["oss_rows"] = [{"kategori_risiko": "TAMPERED"}]
        with pytest.raises(H.CureError, match="tampered or stale oss_rows"):
            cure.classify_quarantine_owner(rec, CODE, tampered_entry, {CODE: adj})

    def test_missing_disputed_key_on_record_refuses(self):
        rec_without_key = _base_record()
        del rec_without_key[DISPUTED_KEY]
        entry = _spec_entry(rec_without_key)  # pinned WITHOUT the key present
        adj = _adjudication_entry(entry)
        with pytest.raises(H.CureError, match="missing from the live record"):
            cure.classify_quarantine_owner(rec_without_key, CODE, entry, {CODE: adj})

    def test_drifted_record_refuses(self):
        rec = _base_record()
        entry = _spec_entry(rec)
        adj = _adjudication_entry(entry)
        drifted = copy.deepcopy(rec)
        drifted["judul"] = "mutated after the spec was pinned"
        with pytest.raises(H.CureError, match="matching neither"):
            cure.classify_quarantine_owner(drifted, CODE, entry, {CODE: adj})

    def test_partial_state_per_skala_done_l2_source_not_refuses(self):
        rec = _base_record()
        entry = _spec_entry(rec)
        adj = _adjudication_entry(entry)
        partial = copy.deepcopy(rec)
        partial["per_skala"] = copy.deepcopy(OSS_ROWS)  # per_skala already patched
        # _l2_source is still absent/None — post-cure state is NOT fully reached
        with pytest.raises(H.CureError, match="matching neither"):
            cure.classify_quarantine_owner(partial, CODE, entry, {CODE: adj})


class TestInnocenceQuarantineOwner:
    def test_valid_pre_cure_state_classifies_as_patch(self):
        rec = _base_record()
        entry = _spec_entry(rec)
        adj = _adjudication_entry(entry)
        assert cure.classify_quarantine_owner(rec, CODE, entry, {CODE: adj}) == "patch"

    def test_valid_post_cure_state_classifies_as_noop(self):
        rec = _base_record()
        entry = _spec_entry(rec)
        adj = _adjudication_entry(entry)
        cured = copy.deepcopy(rec)
        cured["per_skala"] = copy.deepcopy(OSS_ROWS)
        cured["_l2_source"] = coverage.OSS_2025_SOURCE
        cured.pop("_l2_status", None)
        assert cure.classify_quarantine_owner(cured, CODE, entry, {CODE: adj}) == "noop"

    def test_disputed_key_never_read_for_shape_list_or_dict(self):
        """classify_quarantine_owner pins the disputed key's presence and its
        CONTENT HASH, but never interprets its shape — a list (most codes) or a
        dict (20111's real {per_skala, per_skala_legacy}) must both pass
        identically once their own hash is the adjudicated one."""
        for disputed_value in (
            [{"kategori_risiko": "Tinggi"}],
            {"per_skala": [{"a": 1}], "per_skala_legacy": [{"b": 2}]},
        ):
            rec = _base_record(**{DISPUTED_KEY: disputed_value})
            entry = _spec_entry(rec)
            adj = _adjudication_entry(entry, disputed_sha256=H.sha256_of(disputed_value))
            assert cure.classify_quarantine_owner(rec, CODE, entry, {CODE: adj}) == "patch"


# ----------------------------------------------- council round 2026-09-23 (guilt)


class TestCouncilRound:
    """One guilt test per finding of the 2026-09-23 council (Codex F1-F4,
    Kimi F1/F2/F3/F6). Each fails on the code as it stood before its fix."""

    @pytest.fixture(autouse=True)
    def _never_touch_the_real_consumers(self, monkeypatch):
        """No test in this class may reach the real sync_kbli_dataset.sh. On the
        cured code these are all refusal paths that never reach propagate(), but
        a mutant that removes the guard under test turns them into --apply runs
        against the live canonical's consumers. Tests that need propagate to
        behave differently override this with their own setattr, which lands
        after the fixture."""
        monkeypatch.setattr(cure, "propagate", lambda: None)

    def _build(self, tmp_path, *, spec=None, adj=None, records=None):
        rec, l2rec = _base_record(), _l2_record()
        q_entry, l2_entry = _spec_entry(rec), _l2_spec_entry(l2rec)
        spec_doc = spec(q_entry, l2_entry) if spec else _spec_doc((CODE, q_entry), (L2_CODE, l2_entry))
        adj_doc = adj(q_entry) if adj else _adjudication_doc((CODE, _adjudication_entry(q_entry)))
        dataset_path = _write_dataset(tmp_path, records if records is not None else [rec, l2rec])
        return (rec, l2rec, dataset_path,
                _write_json(tmp_path, "spec.json", spec_doc),
                _write_json(tmp_path, "adj.json", adj_doc))

    def _run(self, paths, *extra):
        _, _, dataset_path, spec_path, adj_path = paths
        return cure.main(["--spec", str(spec_path), "--adjudication", str(adj_path),
                          "--canonical", str(dataset_path), *extra])

    # --- Codex F1: refuse means write nothing, including after the write ---

    def test_set_carrying_per_skala_refuses_before_any_write(self, tmp_path, monkeypatch, capsys):
        """A `set` that collides with per_skala used to overwrite the pinned
        rows AFTER they were applied: the canonical was committed and only then
        did the read-back notice, leaving nine adoptions on disk and exit 2."""
        monkeypatch.setattr(cure, "propagate", lambda: None)

        def spec(q_entry, l2_entry):
            l2_entry["set"] = {"_l2_source": coverage.OSS_2025_SOURCE, "per_skala": []}
            return _spec_doc((CODE, q_entry), (L2_CODE, l2_entry))

        paths = self._build(tmp_path, spec=spec)
        before = paths[2].read_text(encoding="utf-8")
        assert self._run(paths, "--apply") == 2
        assert "per_skala" in capsys.readouterr().out
        assert paths[2].read_text(encoding="utf-8") == before, "a refusal must leave the canonical untouched"

    def test_read_back_mismatch_restores_the_pre_cure_canonical(self, tmp_path, monkeypatch, capsys):
        """If the bytes on disk disagree with the plan after the write, the
        canonical is put back — the compiler never leaves a half-cured file."""
        monkeypatch.setattr(cure, "propagate", lambda: None)
        paths = self._build(tmp_path)
        dataset_path = paths[2]
        before = dataset_path.read_text(encoding="utf-8")

        real_write = cure.H.atomic_write_text
        state = {"first": True}

        def corrupting_write(path, text):
            if state["first"] and pathlib.Path(path) == dataset_path:
                state["first"] = False
                payload = json.loads(text)
                for r in payload["data"]:
                    if r["kode_kbli_2025"] == CODE:
                        r["per_skala"] = [{"corrupted": True}]
                return real_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            return real_write(path, text)

        monkeypatch.setattr(cure.H, "atomic_write_text", corrupting_write)
        assert self._run(paths, "--apply") == 2
        assert "restored" in capsys.readouterr().out
        assert dataset_path.read_text(encoding="utf-8") == before

    # --- Codex F2: the record decides whether the declared route is admissible ---

    def test_quarantined_record_relabelled_as_l2_transform_refuses(self, tmp_path, capsys):
        """Relabelling a quarantined code as l2_transform used to walk past the
        adjudication gate entirely, with no adjudication entry for the code at all.

        The entry below is a COMPLETE, internally consistent l2_transform entry —
        every premise present, the rows hashing to their own pin, nothing in
        `set`/`drop_keys` outside this compiler's writable fields. That is the
        point: remove the route-admissibility guard and this run SUCCEEDS. If the
        entry were left incomplete, the row-pin guard would do the refusing and
        this test would pass for a reason that has nothing to do with F2."""
        rec = _base_record()

        def spec(q_entry, l2_entry):
            q_entry.update(
                route="l2_transform",
                premises={
                    "per_skala": {"old_sha256": H.sha256_of(rec["per_skala"]),
                                   "new_sha256": H.sha256_of(q_entry["oss_rows"])},
                    "_l2_source": {"old_sha256": H.sha256_of(rec.get("_l2_source")),
                                    "new_sha256": H.sha256_of(coverage.OSS_2025_SOURCE)},
                    "_l2_status": {"old_sha256": H.sha256_of(rec.get("_l2_status")),
                                    "new_sha256": H.sha256_of(None)},
                },
                per_skala=copy.deepcopy(q_entry["oss_rows"]),
                set={"_l2_source": coverage.OSS_2025_SOURCE},
                drop_keys=["_l2_status"],
            )
            return _spec_doc((CODE, q_entry), (L2_CODE, l2_entry))

        paths = self._build(tmp_path, spec=spec, adj=lambda q: _adjudication_doc())
        dataset_path = paths[2]
        before = dataset_path.read_text(encoding="utf-8")
        assert self._run(paths, "--apply") == 2
        out = capsys.readouterr().out
        assert "quarantine_owner" in out
        assert DISPUTED_KEY in out, "the refusal must name the disputed key it found on the record"
        assert dataset_path.read_text(encoding="utf-8") == before

    def test_drop_keys_naming_the_disputed_block_refuses(self, tmp_path, capsys):
        """The disputed block is the audit trail; no route may drop it."""
        def spec(q_entry, l2_entry):
            l2_entry["drop_keys"] = ["_l2_status", "absent_probes", DISPUTED_KEY]
            return _spec_doc((CODE, q_entry), (L2_CODE, l2_entry))

        paths = self._build(tmp_path, spec=spec)
        assert self._run(paths, "--apply") == 2
        assert "disputed" in capsys.readouterr().out

    # --- Codex F3: the rows the spec hands over must be pinned too ---

    def test_l2_rows_not_matching_their_premise_hash_refuses(self, tmp_path, capsys):
        """Another code's rows pasted into an l2 entry, with every pin left
        intact, used to be applied to the wrong code — the cross-contamination
        class that quarantined 93191/93193 in the first place."""
        def spec(q_entry, l2_entry):
            l2_entry["per_skala"] = copy.deepcopy(q_entry["oss_rows"])  # pins untouched
            return _spec_doc((CODE, q_entry), (L2_CODE, l2_entry))

        paths = self._build(tmp_path, spec=spec)
        assert self._run(paths, "--apply") == 2
        assert "premises.per_skala.new_sha256" in capsys.readouterr().out

    # --- Codex F4 / Kimi F1: a failed propagation must be repairable ---

    def test_propagate_failure_says_the_copies_are_stale(self, tmp_path, monkeypatch, capsys):
        def boom():
            raise cure.CureError("injected copy failure")

        monkeypatch.setattr(cure, "propagate", boom)
        paths = self._build(tmp_path)
        assert self._run(paths, "--apply") == 2
        out = capsys.readouterr().out
        assert "canonical is WRITTEN but its consumer copies are NOT" in out
        assert "re-run with --apply" in out

    def test_apply_on_an_already_cured_canonical_reconciles_the_copies(self, tmp_path, monkeypatch):
        """The no-op path used to return 0 without ever looking at the copies,
        so the one run that could heal a failed propagation was the run that
        skipped it."""
        calls = []
        monkeypatch.setattr(cure, "propagate", lambda: calls.append(1))
        paths = self._build(tmp_path)
        assert self._run(paths, "--apply") == 0          # first: patch
        assert self._run(paths, "--apply") == 0          # second: already cured
        assert len(calls) == 2, "the no-op run must still reconcile"
        assert self._run(paths) == 0                      # dry-run must NOT
        assert len(calls) == 2

    # --- Kimi F2: the disputed block's CONTENT, not just its presence ---

    def test_disputed_block_rewritten_post_cure_refuses(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(cure, "propagate", lambda: None)
        paths = self._build(tmp_path)
        dataset_path = paths[2]
        assert self._run(paths, "--apply") == 0

        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
        for r in payload["data"]:
            if r["kode_kbli_2025"] == CODE:
                r[DISPUTED_KEY] = [{"kategori_risiko": "REWRITTEN"}]
        dataset_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        assert self._run(paths, "--apply") == 2
        assert "audit trail moved" in capsys.readouterr().out

    def test_adjudication_without_a_disputed_pin_refuses(self, tmp_path, capsys):
        paths = self._build(tmp_path, adj=lambda q: _adjudication_doc(
            (CODE, _adjudication_entry(q, disputed_sha256=None))))
        assert self._run(paths, "--apply") == 2
        assert "disputed_sha256" in capsys.readouterr().out

    # --- Kimi F3: the spec's whole-canonical pin is enforced where it speaks ---

    def test_all_patch_run_refuses_a_wrong_whole_canonical_pin(self, tmp_path, capsys):
        paths = self._build(tmp_path, spec=lambda q, l2: _spec_doc(
            (CODE, q), (L2_CODE, l2), canonical_sha256="0" * 64))
        assert self._run(paths, "--apply") == 2
        assert "re-derive" in capsys.readouterr().out

    def test_all_patch_run_accepts_the_right_whole_canonical_pin(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cure, "propagate", lambda: None)
        rec, l2rec = _base_record(), _l2_record()
        q_entry, l2_entry = _spec_entry(rec), _l2_spec_entry(l2rec)
        dataset_path = _write_dataset(tmp_path, [rec, l2rec])
        digest = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
        spec_path = _write_json(tmp_path, "spec.json",
                                 _spec_doc((CODE, q_entry), (L2_CODE, l2_entry), canonical_sha256=digest))
        adj_path = _write_json(tmp_path, "adj.json", _adjudication_doc((CODE, _adjudication_entry(q_entry))))
        assert cure.main(["--spec", str(spec_path), "--adjudication", str(adj_path),
                          "--canonical", str(dataset_path), "--apply"]) == 0

    # --- Kimi F6: a refusal must read as a refusal, never as a traceback ---

    def test_a_bad_record_shape_reads_as_a_refusal_not_a_traceback(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(cure, "propagate", lambda: None)

        def exploding_derive(record):
            raise ValueError("l4_bali.blocked is not boolean")

        monkeypatch.setattr(cure.basis, "derive_verdict_state", exploding_derive)
        paths = self._build(tmp_path)
        before = paths[2].read_text(encoding="utf-8")
        assert self._run(paths, "--apply") == 2
        assert "REFUSED (apply): ValueError" in capsys.readouterr().out
        assert paths[2].read_text(encoding="utf-8") == before


# ------------------------------------------------------------- classify_l2_transform


class TestGuiltL2Transform:
    def test_premises_drift_refuses(self):
        rec = _l2_record()
        entry = _l2_spec_entry(rec)
        drifted = copy.deepcopy(rec)
        drifted["per_skala"][0]["kategori_risiko"] = "MUTATED"
        with pytest.raises(H.CureError, match="drifted under this adjudication"):
            cure.classify_l2_transform(drifted, L2_CODE, entry["premises"])

    def test_partial_application_disagreement_refuses(self):
        rec = _l2_record()
        entry = _l2_spec_entry(rec)
        partial = copy.deepcopy(rec)
        partial["per_skala"] = copy.deepcopy(L2_NEW_PER_SKALA)  # already patched
        # _l2_source / _l2_status / absent_probes still pre-cure -> disagreement
        with pytest.raises(H.CureError, match="premises disagree on state"):
            cure.classify_l2_transform(partial, L2_CODE, entry["premises"])


class TestInnocenceL2Transform:
    def test_valid_pre_cure_state_classifies_as_patch(self):
        rec = _l2_record()
        entry = _l2_spec_entry(rec)
        assert cure.classify_l2_transform(rec, L2_CODE, entry["premises"]) == "patch"

    def test_valid_post_cure_state_classifies_as_noop(self):
        rec = _l2_record()
        entry = _l2_spec_entry(rec)
        cured = copy.deepcopy(rec)
        cured["per_skala"] = copy.deepcopy(L2_NEW_PER_SKALA)
        cured["_l2_source"] = coverage.OSS_2025_SOURCE
        cured.pop("_l2_status", None)
        cured.pop("absent_probes", None)
        assert cure.classify_l2_transform(cured, L2_CODE, entry["premises"]) == "noop"


# ------------------------------------------------------------------------- plan()


class TestPlanGuilt:
    def test_l2_transform_empty_per_skala_refuses(self):
        rec = _l2_record()
        entry = _l2_spec_entry(rec)
        entry["per_skala"] = []
        spec = _spec_doc((L2_CODE, entry))
        with pytest.raises(H.CureError, match="non-empty list"):
            cure.plan([rec], spec, {}, {L2_CODE: "patch"})

    def test_ambiguous_quarantined_by_refuses(self):
        rec = _base_record()
        entry = _spec_entry(rec)
        entry["quarantined_by"] = [DISPUTED_KEY, "per_skala_disputed_other"]
        adj = _adjudication_entry(entry)
        with pytest.raises(H.CureError, match="not exactly one key"):
            cure.classify_quarantine_owner(rec, CODE, entry, {CODE: adj})


# --------------------------------------------------------------------- CLI / main()


class TestCLI:
    def _build(self, tmp_path):
        rec = _base_record()
        l2rec = _l2_record()
        q_entry = _spec_entry(rec)
        l2_entry = _l2_spec_entry(l2rec)
        spec = _spec_doc((CODE, q_entry), (L2_CODE, l2_entry))
        adj = _adjudication_doc((CODE, _adjudication_entry(q_entry)))
        dataset_path = _write_dataset(tmp_path, [rec, l2rec])
        spec_path = _write_json(tmp_path, "spec.json", spec)
        adj_path = _write_json(tmp_path, "adj.json", adj)
        return rec, l2rec, dataset_path, spec_path, adj_path

    def test_dry_run_writes_nothing(self, tmp_path):
        rec, l2rec, dataset_path, spec_path, adj_path = self._build(tmp_path)
        before = dataset_path.read_text(encoding="utf-8")

        rc = cure.main(["--spec", str(spec_path), "--adjudication", str(adj_path), "--canonical", str(dataset_path)])

        assert rc == 0
        assert dataset_path.read_text(encoding="utf-8") == before

    def test_apply_then_second_apply_is_noop_disputed_key_untouched(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cure, "propagate", lambda: None)
        rec, l2rec, dataset_path, spec_path, adj_path = self._build(tmp_path)

        rc1 = cure.main(["--spec", str(spec_path), "--adjudication", str(adj_path), "--canonical", str(dataset_path), "--apply"])
        assert rc1 == 0

        applied = json.loads(dataset_path.read_text(encoding="utf-8"))["data"]
        by_code = {r["kode_kbli_2025"]: r for r in applied}
        tq = by_code[CODE]
        assert tq["per_skala"] == OSS_ROWS
        assert tq["_l2_source"] == coverage.OSS_2025_SOURCE
        assert "_l2_status" not in tq
        assert "absent_probes" not in tq
        assert tq[DISPUTED_KEY] == rec[DISPUTED_KEY], "disputed key must survive apply byte-identical"
        assert tq["_data_note"] == "Test note."

        tl = by_code[L2_CODE]
        assert tl["per_skala"] == L2_NEW_PER_SKALA
        assert tl["_l2_source"] == coverage.OSS_2025_SOURCE
        assert "_l2_status" not in tl
        assert "absent_probes" not in tl

        after_first = dataset_path.read_text(encoding="utf-8")
        rc2 = cure.main(["--spec", str(spec_path), "--adjudication", str(adj_path), "--canonical", str(dataset_path), "--apply"])
        assert rc2 == 0
        assert dataset_path.read_text(encoding="utf-8") == after_first, "second apply must be a byte-identical no-op"

    def test_only_declared_paths_change_bystander_untouched(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cure, "propagate", lambda: None)
        rec, l2rec, dataset_path, spec_path, adj_path = self._build(tmp_path)
        bystander = {
            "kode_kbli_2025": "OTHER1", "judul": "bystander",
            "per_skala": [{"skala_usaha": ["Mikro"], "kategori_risiko": "Rendah"}],
            "l4_bali": {"status": "TERTUTUP", "blocked": True, "confidence": "HIGH", "needs_review": False, "verdict_state": "blocked"},
        }
        records = json.loads(dataset_path.read_text(encoding="utf-8"))["data"]
        records.append(copy.deepcopy(bystander))
        dataset_path.write_text(json.dumps({"data": records}, ensure_ascii=False, indent=2), encoding="utf-8")

        rc = cure.main(["--spec", str(spec_path), "--adjudication", str(adj_path), "--canonical", str(dataset_path), "--apply"])
        assert rc == 0

        applied = json.loads(dataset_path.read_text(encoding="utf-8"))["data"]
        by_code = {r["kode_kbli_2025"]: r for r in applied}
        assert by_code["OTHER1"] == bystander

    def test_missing_adjudication_refuses_and_writes_nothing(self, tmp_path):
        rec, l2rec, dataset_path, spec_path, adj_path = self._build(tmp_path)
        # empty adjudication: 93114-style code (quarantine_owner) is unnamed
        empty_adj_path = _write_json(tmp_path, "empty_adj.json", _adjudication_doc())
        before = dataset_path.read_text(encoding="utf-8")

        rc = cure.main(["--spec", str(spec_path), "--adjudication", str(empty_adj_path), "--canonical", str(dataset_path), "--apply"])

        assert rc == 2
        assert dataset_path.read_text(encoding="utf-8") == before, "a refusal must write nothing, even with --apply"

    def test_usage_error_exits_64(self):
        with pytest.raises(SystemExit) as excinfo:
            cure.main(["--not-a-real-flag"])
        assert excinfo.value.code == 64


# --------------------------------------------------------------- TestRealCatalogue


REAL_CODES = ["19206", "20111", "75002", "75009", "93113", "93114", "93115", "93191", "93193", "93195"]


class TestRealCatalogue:
    """Checks against the ACTUAL committed spec/adjudication + the live
    canonical, after THIS PR's own --apply has landed (matches the
    TestRealCatalogue convention in test_cure_pr2b_source_rows_93114_43110.py)."""

    @staticmethod
    @pytest.fixture(scope="class")
    def records():
        payload = json.loads(cure.CANONICAL.read_text(encoding="utf-8"))
        return {r["kode_kbli_2025"]: r for r in payload["data"]}

    @staticmethod
    @pytest.fixture(scope="class")
    def real_spec():
        return json.loads(cure.SPEC_PATH.read_text(encoding="utf-8"))

    @staticmethod
    @pytest.fixture(scope="class")
    def real_adjudication():
        return json.loads(cure.ADJUDICATION_PATH.read_text(encoding="utf-8"))["codes"]

    def test_all_10_codes_present(self, records):
        for code in REAL_CODES:
            assert code in records

    def test_all_10_codes_classify_sourced_oss_2025(self, records):
        for code in REAL_CODES:
            assert coverage.classify_licensing(records[code]) == coverage.LIC_SOURCED_OSS_2025, code

    def test_all_10_codes_noop_on_the_live_canonical(self, records, real_spec, real_adjudication):
        for code in REAL_CODES:
            entry = real_spec["codes"][code]
            record = records[code]
            if entry["route"] == "l2_transform":
                verdict = cure.classify_l2_transform(record, code, entry["premises"])
            else:
                verdict = cure.classify_quarantine_owner(record, code, entry, real_adjudication)
            assert verdict == "noop", code

    def test_20111_dict_shaped_disputed_value_survives_untouched(self, records):
        rec = records["20111"]
        value = rec[DISPUTED_KEY]
        assert isinstance(value, dict)
        assert set(value.keys()) >= {"per_skala", "per_skala_legacy"}

    def test_disputed_keys_survive_on_every_code(self, records, real_spec):
        for code in REAL_CODES:
            entry = real_spec["codes"][code]
            for key in entry.get("quarantined_by") or []:
                assert key in records[code], f"{code}: {key} missing after cure"

    def test_second_apply_is_a_byte_identical_noop(self, monkeypatch):
        monkeypatch.setattr(cure, "propagate", lambda: None)
        before = cure.CANONICAL.read_bytes()
        exit_code = cure.main(["--apply"])
        after = cure.CANONICAL.read_bytes()
        assert exit_code == 0
        assert before == after
