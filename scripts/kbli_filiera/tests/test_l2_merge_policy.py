"""PR-B of docs/specs/2026-09-11-kbli-l2-oss-resnapshot-reingest-spec.md (§6 rulings
1-4): the L2 transform MERGES into the canonical instead of rewriting it.

Covered here, each with a guilt case (the old wholesale behaviour would fail it):
  - merge_per_skala: matched rows carry later-layer keys and a sourced jangka_waktu;
    a changed-tier row is fresh (automatic tiers -> "Otomatis"); L2-owned fields
    always come from OSS.
  - a NO_BESAR verdict never rewrites l4_bali (the "no Besar row" inference is withdrawn;
    the Perpres Lampiran II layer owns those codes) — checked on the canonical too.
  - quarantined per_skala (per_skala_disputed_*) is skipped entirely.
  - l4_bali is left byte-identical when the recomputed verdict did not move.
  - a code that HAD scope and is 404 now becomes absent_pending_corroboration with
    its per_skala kept; a code that never had scope stays no_oss_risk; no
    _l4_needs_review is ever written.
  - vault_tier_changeset: the pinned-triple definition on a synthetic pair of vaults.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from kbli_filiera import vault_tier_changeset as changeset  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "l2_repro"
REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"


def _transform():
    sys.path.insert(0, str(REPO_ROOT))
    import scripts.build_kbli_l2_oss_risk as t  # noqa: E402
    return t


def _row(skala, tier, scope=0, jw="", uraian="Seluruh", **extra):
    r = {"skala_usaha": [skala], "kategori_risiko": tier, "jangka_waktu": jw, "scope_index": scope,
         "scope_uraian": uraian, "perizinan": [], "persyaratan": [], "kewajiban": [], "kewenangan": []}
    r.update(extra)
    return r


class TestMergePerSkala:
    def test_matched_row_carries_later_layer_keys_and_sourced_jangka(self):
        t = _transform()
        old = [_row("Besar", "Tinggi", jw="7", jangka_waktu_source="lampiran_parsed_richfile",
                    fiktif_positif=True, pb_umku=["x"])]
        new = [_row("Besar", "Tinggi", jw="3", kewenangan=["Gubernur"])]
        merged = t.merge_per_skala(old, new)
        assert merged[0]["jangka_waktu"] == "7"            # sourced -> preserved
        assert merged[0]["fiktif_positif"] is True         # carried
        assert merged[0]["pb_umku"] == ["x"]               # any later-layer key carried
        assert merged[0]["kewenangan"] == ["Gubernur"]     # L2-owned -> from OSS

    def test_unsourced_jangka_takes_the_oss_value(self):
        t = _transform()
        old = [_row("Besar", "Tinggi", jw="10", fiktif_positif=True)]
        new = [_row("Besar", "Tinggi", jw="5")]
        assert t.merge_per_skala(old, new)[0]["jangka_waktu"] == "5"

    def test_dirty_oss_value_never_overwrites_and_is_never_written_fresh(self):
        t = _transform()
        assert t.merge_per_skala([_row("Besar", "Tinggi", jw="")], [_row("Besar", "Tinggi", jw="-")])[0]["jangka_waktu"] == ""
        assert t.merge_per_skala([_row("Besar", "Tinggi", jw="7")], [_row("Besar", "Tinggi", jw="-")])[0]["jangka_waktu"] == "7"
        assert t.merge_per_skala([], [_row("Besar", "Tinggi", jw="-")])[0]["jangka_waktu"] == ""

    def test_changed_tier_row_is_fresh_and_automatic_tier_gets_otomatis(self):
        t = _transform()
        old = [_row("Besar", "Tinggi", jw="7", jangka_waktu_source="lampiran_parsed_richfile", fiktif_positif=True)]
        new = [_row("Besar", "Menengah Rendah", jw="")]
        m = t.merge_per_skala(old, new)[0]
        assert "fiktif_positif" not in m                    # not carried across a tier change
        assert m["jangka_waktu"] == "Otomatis"
        assert m["jangka_waktu_source"] == "PP28_rule_risk_class"

    def test_scope_split_carries_only_tier_level_facts(self):
        """codex PR-B F1: 'Seluruh' split into two named scopes — the named rows must not
        inherit the old row's scope-specific keys (pb_umku), only the tier-level ones."""
        t = _transform()
        old = [_row("Besar", "Tinggi", jw="7", jangka_waktu_source="lampiran_parsed_richfile",
                    fiktif_positif=True, pb_umku=["x"])]
        new = [_row("Besar", "Tinggi", scope=0, uraian="Sub A", jw="3"),
               _row("Besar", "Tinggi", scope=1, uraian="Sub B", jw="3")]
        m = t.merge_per_skala(old, new)
        assert m[0]["jangka_waktu"] == "7" and m[0]["fiktif_positif"] is True and "pb_umku" not in m[0]
        assert m[1]["jangka_waktu"] == "3" and "fiktif_positif" not in m[1]   # donor consumed once

    def test_duplicate_keys_donate_once_in_order(self):
        """codex PR-B F2: two canonical rows with the same key keep their own values."""
        t = _transform()
        old = [_row("Besar", "Tinggi", jw="7", jangka_waktu_source="s"), _row("Besar", "Tinggi", jw="21", jangka_waktu_source="s")]
        new = [_row("Besar", "Tinggi", jw="1"), _row("Besar", "Tinggi", jw="1")]
        assert [r["jangka_waktu"] for r in t.merge_per_skala(old, new)] == ["7", "21"]

    def test_fresh_lampiran_tier_row_stays_honestly_empty(self):
        t = _transform()
        m = t.merge_per_skala([], [_row("Besar", "Menengah Tinggi", jw="")])[0]
        assert m["jangka_waktu"] == "" and "jangka_waktu_source" not in m


class TestNoBesarDecidesNothing:
    def test_verdict_on_a_synthetic_no_besar_code(self):
        t = _transform()
        assert t.besar_block_verdict([_row("Mikro", "Rendah"), _row("Kecil", "Rendah")]) == "NO_BESAR"

    def test_no_besar_never_rewrites_l4(self, tmp_path):
        """50131 (Besar-only) is turned into a no-Besar code by dropping the Besar row
        from the vault payload: the transform must leave its l4_bali byte-identical —
        the withdrawn "reserved for UMKM" inference must not come back (guilt: the
        pre-PR-B scripts/ copy wrote OK_or_HIGHER_RISK; the backend copy wrote
        CHIUSO_PMA_NO_BESAR + the withdrawn reason)."""
        t = _transform()
        root, canon = _seed_root(tmp_path)
        v = tmp_path / "vault"
        shutil.copytree(FIXTURES / "vault", v)
        pj = v / "oss" / "50131" / "ruang_lingkup.json"
        payload = json.loads(pj.read_text(encoding="utf-8"))
        for rl in payload["data"]:
            rl["KbliResikos"] = [x for x in rl["KbliResikos"]
                                 if "Besar" not in (x.get("SkalaUsaha", {}).get("localization", {}).get("id", {}).get("uraian") or "")]
            rl["KbliResikos"].append({"SkalaUsaha": {"localization": {"id": {"uraian": "Usaha Mikro"}}},
                                      "Resiko": {"localization": {"id": {"uraian": "Rendah"}}}})
        pj.write_text(json.dumps(payload), encoding="utf-8")
        before = next(r for r in canon["data"] if str(r["kode_kbli_2025"]) == "50131")
        _, by = _run(t, root, v, tmp_path)
        assert t.besar_block_verdict(by["50131"]["per_skala"]) == "NO_BESAR"
        assert by["50131"]["l4_bali"] == before["l4_bali"]
        assert "reserved for UMKM" not in json.dumps(by["50131"])

    def test_canonical_no_besar_codes_keep_their_perpres_layer_labels(self):
        """On the canonical the codes whose OSS rows have no Besar row are closed or not
        by the Perpres Lampiran II layer, never by the missing row: none of them carries
        the transform's own labels, and every CHIUSO_PMA_NO_BESAR reason cites the annex."""
        t = _transform()
        ds = json.loads(CANONICAL.read_text(encoding="utf-8"))
        no_besar = [r for r in ds["data"]
                    if r.get("per_skala") and r.get("_l2_source") == t.L2_SOURCE
                    and not any(k.startswith(t.QUARANTINE_PREFIX) for k in r)
                    and (r.get("l4_bali") or {}).get("status") not in t.PRESERVE_STATUSES
                    and t.besar_block_verdict(r["per_skala"]) == "NO_BESAR"]
        assert no_besar
        for r in no_besar:
            l4 = r["l4_bali"]
            assert "reserved for UMKM" not in (l4.get("reason") or ""), r["kode_kbli_2025"]
            if l4.get("status") == "CHIUSO_PMA_NO_BESAR":
                assert "Lampiran II" in l4.get("reason", ""), r["kode_kbli_2025"]


def _seed_root(tmp_path: Path, mutate=None) -> tuple[Path, dict]:
    canon = json.loads((FIXTURES / "canonical_slice.json").read_text(encoding="utf-8"))
    if mutate:
        mutate(canon)
    root = tmp_path / "root"
    for rel in ("data/source_documents/KBLI_2025_FINAL_CLEAN.json", "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(json.dumps(canon, ensure_ascii=False), encoding="utf-8")
    return root, canon


def _vault_without(tmp_path: Path, code: str) -> Path:
    """Copy of the fixture vault where `code` lost its scope (404 recorded)."""
    v = tmp_path / "vault"
    shutil.copytree(FIXTURES / "vault", v)
    shutil.rmtree(v / "oss" / code)
    with (v / "oss" / "absences.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"code": code, "endpoint": "ruang_lingkup", "status": 404, "recorded_as": "absent"}) + "\n")
    return v


def _run(t, root: Path, vault: Path, tmp_path: Path, *extra):
    from kbli_filiera import vault_to_risk_jsonl as adapter
    raw = tmp_path / "raw.jsonl"
    assert adapter.main(["--vault-root", str(vault), "--ground-truth", str(FIXTURES / "ground_truth.json"), "--out", str(raw)]) == 0
    t.main(["--root", str(root), "--raw", str(raw), "--apply", *extra])
    out = json.loads((root / "data/source_documents/KBLI_2025_FINAL_CLEAN.json").read_text(encoding="utf-8"))
    return out, {str(r["kode_kbli_2025"]): r for r in out["data"]}


class TestApplyMergesInsteadOfRewriting:
    def test_unchanged_verdict_leaves_l4_and_later_layer_fields_byte_identical(self, tmp_path):
        t = _transform()
        root, canon = _seed_root(tmp_path)
        _, by = _run(t, root, FIXTURES / "vault", tmp_path)
        for rec in canon["data"]:
            code = str(rec["kode_kbli_2025"])
            if rec.get("_l2_status") == "no_oss_risk":
                continue
            assert by[code]["l4_bali"] == rec["l4_bali"], code
            assert "_l4_needs_review" not in by[code]
            old_src = {(p["scope_index"], tuple(p["skala_usaha"])): p.get("jangka_waktu_source") for p in rec["per_skala"]}
            for p in by[code]["per_skala"]:
                k = (p["scope_index"], tuple(p["skala_usaha"]))
                if old_src.get(k):
                    assert p["jangka_waktu_source"] == old_src[k]
                assert "fiktif_positif" in p, code   # carried, not dropped

    def test_l4_is_rewritten_when_the_verdict_moves(self, tmp_path):
        t = _transform()

        def stale_verdict(canon):
            for rec in canon["data"]:
                if str(rec["kode_kbli_2025"]) == "10215":
                    rec["l4_bali"]["verdict"] = "BLOCKED"
                    rec["l4_bali"]["blocked"] = True
                    rec["l4_bali"]["status"] = "BLOCCATO_CLASSE_RISCHIO"
        root, _ = _seed_root(tmp_path, stale_verdict)
        _, by = _run(t, root, FIXTURES / "vault", tmp_path)
        assert by["10215"]["l4_bali"]["verdict"] == "OPEN"
        assert by["10215"]["l4_bali"]["blocked"] is False
        assert by["10215"]["l4_bali"]["status"] == "OK_or_HIGHER_RISK"

    def test_lost_scope_is_pending_not_absent_and_never_had_scope_stays_no_oss_risk(self, tmp_path):
        t = _transform()
        root, canon = _seed_root(tmp_path)
        before = next(r for r in canon["data"] if str(r["kode_kbli_2025"]) == "56101")
        out, by = _run(t, root, _vault_without(tmp_path, "56101"), tmp_path, "--fetched", "2026-09-11")
        assert by["56101"]["_l2_status"] == "absent_pending_corroboration"
        assert by["56101"]["absent_probes"] == ["2026-09-11"]
        assert by["56101"]["per_skala"] == before["per_skala"]      # kept, not wiped
        assert by["56101"]["l4_bali"] == before["l4_bali"]
        assert by["85583"]["_l2_status"] == "no_oss_risk"          # never had scope
        assert "absent_probes" not in by["85583"]

    def test_presence_closes_an_absence_episode_and_non_404_is_not_evidence(self, tmp_path):
        """codex PR-B F3/F4: a 5xx / missing record leaves the record untouched; a 200
        after a pending absence clears absent_probes."""
        t = _transform()

        def pending(canon):
            for rec in canon["data"]:
                if str(rec["kode_kbli_2025"]) == "10215":
                    rec["_l2_status"] = "absent_pending_corroboration"
                    rec["absent_probes"] = ["2026-09-01"]
        root, canon = _seed_root(tmp_path, pending)
        _, by = _run(t, root, FIXTURES / "vault", tmp_path)
        assert "absent_probes" not in by["10215"] and "_l2_status" not in by["10215"]
        # now a 500 for 56101: untouched, not pending
        from kbli_filiera import vault_to_risk_jsonl as adapter
        raw = tmp_path / "raw500.jsonl"
        lines = []
        for line in (tmp_path / "raw.jsonl").read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if rec["kode"] == "56101":
                rec = {"kode": "56101", "uuid": rec["uuid"], "status": 500, "data": {}}
            lines.append(json.dumps(rec, ensure_ascii=False))
        raw.write_text("\n".join(lines) + "\n", encoding="utf-8")
        before = next(r for r in canon["data"] if str(r["kode_kbli_2025"]) == "56101")
        root2, _ = _seed_root(tmp_path / "b")
        t.main(["--root", str(root2), "--raw", str(raw), "--apply", "--fetched", "2026-09-11"])
        out = json.loads((root2 / "data/source_documents/KBLI_2025_FINAL_CLEAN.json").read_text(encoding="utf-8"))
        rec = next(r for r in out["data"] if str(r["kode_kbli_2025"]) == "56101")
        assert rec == before
        assert all("_l4_needs_review" not in r for r in by.values())

    def test_quarantined_per_skala_is_skipped_entirely(self, tmp_path):
        t = _transform()

        def quarantine(canon):
            for rec in canon["data"]:
                if str(rec["kode_kbli_2025"]) == "10215":
                    rec["per_skala_disputed_pp28_collision"] = {"note": "cure-owned"}
                    rec["per_skala"] = []
                    rec["l4_bali"]["status"] = "NON_CLASSIFICABILE"
        root, canon = _seed_root(tmp_path, quarantine)
        before = next(r for r in canon["data"] if str(r["kode_kbli_2025"]) == "10215")
        _, by = _run(t, root, FIXTURES / "vault", tmp_path)
        assert by["10215"]["per_skala"] == []
        assert by["10215"]["l4_bali"] == before["l4_bali"]
        assert by["10215"].get("_l2_status") == before.get("_l2_status")

    def test_metadata_provenance_flags(self, tmp_path):
        t = _transform()
        root, _ = _seed_root(tmp_path, lambda c: c["metadata"].update({"source": "X + PP28_2024 (y)"}))
        out, _ = _run(t, root, FIXTURES / "vault", tmp_path,
                      "--version", "v11.0-test", "--fetched", "2026-09-11", "--snapshot-vault", "v",
                      "--snapshot-manifest-sha256", "abc", "--snapshot-codes-changed", "181",
                      "--source-fix", "PP28_2024", "PP28_2025")
        md = out["metadata"]
        root2, _ = _seed_root(tmp_path / "only-count")
        out2, _ = _run(t, root2, FIXTURES / "vault", tmp_path / "only-count", "--snapshot-codes-changed", "181")
        assert out2["metadata"]["l2_snapshot"]["codes_changed"] == 181   # codex PR-B F5
        assert md["version"] == "v11.0-test" and md["source"] == "X + PP28_2025 (y)"
        assert md["l2_snapshot"] == {"vault": "v", "manifest_sha256": "abc", "fetched": "2026-09-11",
                                     "codes_changed": 181, "absent_pending": 0}


class TestVaultTierChangeset:
    def _payload(self, scope, rows):
        return {"success": True, "data": [{"localization": {"id": {"uraian": scope}}, "KbliResikos": [
            {"SkalaUsaha": {"kode": s}, "Resiko": {"localization": {"id": {"uraian": r}}}} for s, r in rows]}]}

    def _vault(self, tmp_path, name, codes: dict):
        v = tmp_path / name
        for code, payload in codes.items():
            (v / "oss" / code).mkdir(parents=True)
            (v / "oss" / code / "ruang_lingkup.json").write_text(json.dumps(payload), encoding="utf-8")
        return v

    def test_changed_old_only_new_only(self, tmp_path):
        gt = tmp_path / "gt.json"
        gt.write_text(json.dumps({"data": [{"kode": c, "uuid": "u", "digits": 5} for c in ("10001", "10002", "10003", "10004")]}))
        same = self._payload("Seluruh", [("UB", "Tinggi"), ("UK", "Rendah")])
        old = self._vault(tmp_path, "old", {"10001": same, "10002": same, "10003": same})
        new = self._vault(tmp_path, "new", {"10001": same,
                                            "10002": self._payload("Seluruh", [("UB", "Tinggi"), ("UK", "Menengah Rendah")]),
                                            "10004": same})
        r = changeset.changeset(old, new, gt)
        assert r == {"changed": ["10002"], "old_only": ["10003"], "new_only": ["10004"], "both": 2}

    def test_reordered_rows_are_not_a_change(self, tmp_path):
        gt = tmp_path / "gt.json"
        gt.write_text(json.dumps({"data": [{"kode": "10001", "uuid": "u", "digits": 5}]}))
        a = self._payload("Seluruh", [("UB", "Tinggi"), ("UK", "Rendah")])
        b = self._payload("Seluruh", [("UK", "Rendah"), ("UB", "Tinggi")])
        assert changeset.changeset(self._vault(tmp_path, "o", {"10001": a}), self._vault(tmp_path, "n", {"10001": b}), gt)["changed"] == []
