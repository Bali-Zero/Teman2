"""Unit tests for scripts/kbli_filiera/dossier_pull.py — no network, no real
vault (tmp fixtures only); pdftotext/pdftoppm are monkeypatched wherever a
subprocess would otherwise fire, mirroring the repo convention in
test_vault_fetch_pp28.py (common.http_get monkeypatched there)."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from kbli_filiera import vault_common as common  # noqa: E402
from kbli_filiera import dossier_pull as dp  # noqa: E402


# ---------------------------------------------------------------------------
# Fuzzy digit matching — guilt + innocence corpus (superscar #3 discipline:
# no guard/matcher merges without BOTH arms tested)
# ---------------------------------------------------------------------------

class TestFuzzyCodePattern:
    def test_guilt_ocr_digit_one_confusion_matches(self):
        # Grounded fact (kbli-navigator SKILL.md §3): pdftotext on these
        # scans renders "1" as "t" — "68112" -> "681t2".
        assert dp.find_code_hits("Kode 681t2 Penyewaan Venue", "68112") == [5]

    def test_innocence_neighboring_code_does_not_match(self):
        # "68113" must NOT register as a hit for "68112" — same length,
        # last digit genuinely differs (not an OCR confusion of "2").
        assert dp.find_code_hits("Kode 68113 Penyewaan Venue", "68112") == []

    def test_guilt_ocr_digit_zero_confusion_matches(self):
        assert dp.find_code_hits("kode O8112 misc", "08112") == [5]

    def test_innocence_longer_digit_run_is_not_a_floating_substring_hit(self):
        # "168112" must never register as a hit for "68112" — that would
        # be exactly the over-match class superscar #3 warns about (a
        # match anchored only on the RIGHT, not the whole token).
        assert dp.find_code_hits("ref 168112 misc", "68112") == []

    def test_innocence_trailing_extra_digit_is_not_a_floating_substring_hit(self):
        assert dp.find_code_hits("ref 681123 misc", "68112") == []

    def test_innocence_no_match_in_unrelated_text(self):
        assert dp.find_code_hits("Lampiran I.A Sektor ESDM tidak ada relevansi", "68112") == []

    def test_multiple_isolated_hits_all_found(self):
        text = "68112 first, then again 681t2 later"
        assert dp.find_code_hits(text, "68112") == [0, 24]

    def test_non_digit_code_raises(self):
        try:
            dp.fuzzy_code_pattern("68-11")
            assert False, "expected ValueError"
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# sektor_id -> PP28 lampiran letter candidates
# ---------------------------------------------------------------------------

class TestSektorIdToLampiranLetters:
    def test_single_letter(self):
        assert dp.sektor_id_to_lampiran_letters("I.H") == {"I.H"}

    def test_compound_range_expands_alphabetically(self):
        assert dp.sektor_id_to_lampiran_letters("I.J-P") == {
            "I.J", "I.K", "I.L", "I.M", "I.N", "I.O", "I.P",
        }

    def test_third_level_sub_classification_ignored(self):
        assert dp.sektor_id_to_lampiran_letters("I.F.c") == {"I.F"}

    def test_none_returns_empty_set(self):
        assert dp.sektor_id_to_lampiran_letters(None) == set()

    def test_unparseable_returns_empty_set_never_raises(self):
        assert dp.sektor_id_to_lampiran_letters("not-a-sektor-id") == set()

    def test_malformed_reversed_range_degrades_to_anchor_letter(self):
        assert dp.sektor_id_to_lampiran_letters("I.P-J") == {"I.P"}


class TestPp28ScanScope:
    def test_full_scan_when_l2_source_is_null(self):
        letters, full_scan = dp.pp28_scan_scope({"_l2_source": None, "sektor_id": "I.H"})
        assert full_scan is True

    def test_narrowed_scan_includes_sektor_letters_and_collision_letters(self):
        letters, full_scan = dp.pp28_scan_scope({"_l2_source": "OSS_RBA_resiko_2025", "sektor_id": "I.I"})
        assert full_scan is False
        assert letters == {"I.I", "I.L", "I.H"}

    def test_missing_sektor_id_still_includes_collision_letters(self):
        letters, full_scan = dp.pp28_scan_scope({"_l2_source": "x", "sektor_id": None})
        assert full_scan is False
        assert letters == {"I.L", "I.H"}


# ---------------------------------------------------------------------------
# find_candidate_pages — pure page-matching logic (no subprocess)
# ---------------------------------------------------------------------------

class TestFindCandidatePages:
    def test_finds_pages_with_a_hit_sorted(self):
        pages = {118: "no code here", 117: "row 68112 MICE", 130: "another 681t2 mention"}
        assert dp.find_candidate_pages(pages, "68112") == [117, 130]

    def test_no_hits_returns_empty_list(self):
        pages = {117: "irrelevant", 118: "also irrelevant"}
        assert dp.find_candidate_pages(pages, "68112") == []


# ---------------------------------------------------------------------------
# evidence_item shape
# ---------------------------------------------------------------------------

class TestEvidenceItem:
    def test_shape_has_all_five_fields(self):
        item = dp.evidence_item(
            rel_path="canonical.json", sha256="abc", source="data/x.json#68112",
            locator={"kode_kbli_2025": "68112"}, created_at="2026-07-17T00:00:00Z",
        )
        assert item == {
            "rel_path": "canonical.json",
            "sha256": "abc",
            "source": "data/x.json#68112",
            "locator": {"kode_kbli_2025": "68112"},
            "created_at": "2026-07-17T00:00:00Z",
        }


# ---------------------------------------------------------------------------
# pull_canonical
# ---------------------------------------------------------------------------

class TestPullCanonical:
    def test_writes_record_and_returns_evidence_item(self, tmp_path):
        canonical_path = tmp_path / "canonical.json"
        canonical_path.write_text("{}", encoding="utf-8")
        out_dir = tmp_path / "out" / "68112"
        out_dir.mkdir(parents=True)
        record = {"kode_kbli_2025": "68112", "judul": "test"}

        item = dp.pull_canonical("68112", record, canonical_path, out_dir, fetched_at="2026-07-17T00:00:00Z")

        written = json.loads((out_dir / "canonical.json").read_text(encoding="utf-8"))
        assert written == record
        assert item["rel_path"] == "canonical.json"
        assert item["source"] == f"{canonical_path.as_posix()}#68112"


# ---------------------------------------------------------------------------
# pull_oss
# ---------------------------------------------------------------------------

class TestPullOss:
    def test_present_endpoints_copied_and_indexed(self, tmp_path):
        vault_root = tmp_path / "vault"
        (vault_root / "oss" / "68112").mkdir(parents=True)
        (vault_root / "oss" / "68112" / "detail.json").write_bytes(b'{"ok": true}')
        out_dir = tmp_path / "out" / "68112"
        out_dir.mkdir(parents=True)

        items = dp.pull_oss("68112", vault_root, out_dir, fetched_at="2026-07-17T00:00:00Z")

        rel_paths = {i["rel_path"] for i in items}
        assert "oss/detail.json" in rel_paths
        assert (out_dir / "oss" / "detail.json").read_bytes() == b'{"ok": true}'
        # 3 of the 4 endpoints are missing -> ABSENT.json must exist, never
        # an empty dir pretending nothing is missing.
        assert "oss/ABSENT.json" in rel_paths
        absent = json.loads((out_dir / "oss" / "ABSENT.json").read_text(encoding="utf-8"))
        assert len(absent["missing_endpoints"]) == 3

    def test_absence_record_quoted_verbatim_when_present(self, tmp_path):
        vault_root = tmp_path / "vault"
        vault_root.mkdir(parents=True)
        common.append_jsonl(vault_root / "oss" / "absences.jsonl", {
            "code": "65121", "endpoint": "ruang_lingkup", "status": 404, "recorded_as": "absent",
            "fetched_at": "2026-07-16T00:00:00Z",
        })
        out_dir = tmp_path / "out" / "65121"
        out_dir.mkdir(parents=True)

        dp.pull_oss("65121", vault_root, out_dir, fetched_at="2026-07-17T00:00:00Z")

        absent = json.loads((out_dir / "oss" / "ABSENT.json").read_text(encoding="utf-8"))
        ruang = next(m for m in absent["missing_endpoints"] if m["endpoint"] == "ruang_lingkup")
        assert ruang["verdict"] == "absent"
        assert ruang["record"]["status"] == 404

    def test_no_vault_record_at_all_is_distinguished_from_absent(self, tmp_path):
        vault_root = tmp_path / "vault"
        vault_root.mkdir(parents=True)
        out_dir = tmp_path / "out" / "99999"
        out_dir.mkdir(parents=True)

        dp.pull_oss("99999", vault_root, out_dir, fetched_at="2026-07-17T00:00:00Z")

        absent = json.loads((out_dir / "oss" / "ABSENT.json").read_text(encoding="utf-8"))
        assert all(m["verdict"] == "no_data_no_absence_record" for m in absent["missing_endpoints"])
        assert len(absent["missing_endpoints"]) == 4

    def test_all_present_still_writes_no_absent_file(self, tmp_path):
        vault_root = tmp_path / "vault"
        code_dir = vault_root / "oss" / "65121"
        code_dir.mkdir(parents=True)
        for ep in dp.OSS_ENDPOINTS:
            (code_dir / f"{ep}.json").write_bytes(b"{}")
        out_dir = tmp_path / "out" / "65121"
        out_dir.mkdir(parents=True)

        items = dp.pull_oss("65121", vault_root, out_dir, fetched_at="2026-07-17T00:00:00Z")

        assert len(items) == 4
        assert not (out_dir / "oss" / "ABSENT.json").exists()


# ---------------------------------------------------------------------------
# pull_pp28 — innocence-control (empty pp28_sources) must come out boring
# ---------------------------------------------------------------------------

class TestPullPp28NotApplicable:
    def test_empty_pp28_sources_writes_not_applicable(self, tmp_path):
        vault_root = tmp_path / "vault"
        vault_root.mkdir(parents=True)
        out_dir = tmp_path / "out" / "65121"
        out_dir.mkdir(parents=True)
        record = {"pp28_sources": [], "_l2_source": "OSS_RBA_resiko_2025", "sektor_id": "I.J"}

        items = dp.pull_pp28("65121", vault_root, out_dir, record, fetched_at="2026-07-17T00:00:00Z")

        assert len(items) == 1
        assert items[0]["rel_path"] == "pp28/NOT_APPLICABLE.json"
        payload = json.loads((out_dir / "pp28" / "NOT_APPLICABLE.json").read_text(encoding="utf-8"))
        assert payload["verdict"] == "not_applicable"


class TestSelectPp28Candidates:
    def test_full_scan_returns_every_fetch_log_record(self):
        fetch_log = [{"id": 1, "letter": "I.A"}, {"id": 2, "letter": "I.H"}]
        candidates, full_scan = dp.select_pp28_candidates({"_l2_source": None, "sektor_id": "I.A"}, fetch_log)
        assert full_scan is True
        assert candidates == fetch_log

    def test_narrowed_scan_filters_by_letter(self):
        fetch_log = [{"id": 1, "letter": "I.A"}, {"id": 2, "letter": "I.H"}, {"id": 3, "letter": "I.L"}]
        candidates, full_scan = dp.select_pp28_candidates(
            {"_l2_source": "x", "sektor_id": "I.A"}, fetch_log,
        )
        assert full_scan is False
        ids = {c["id"] for c in candidates}
        # sektor letter I.A + the two always-on collision letters I.L/I.H
        assert ids == {1, 2, 3}

    def test_narrowed_scan_excludes_unrelated_letters(self):
        fetch_log = [{"id": 1, "letter": "I.A"}, {"id": 9, "letter": "I.Z"}]
        candidates, full_scan = dp.select_pp28_candidates(
            {"_l2_source": "x", "sektor_id": "I.A"}, fetch_log,
        )
        assert full_scan is False
        assert {c["id"] for c in candidates} == {1}


# ---------------------------------------------------------------------------
# pull_crosswalk / pull_pp28 — wiring integration, subprocess monkeypatched
# (mirrors the repo convention: common.http_get is monkeypatched in the
# vault_fetch_* tests instead of hitting the network; here extract_pages_text
# / render_page_png / _pdf_page_count are monkeypatched instead of shelling
# to real pdftotext/pdftoppm — still "no network, no real vault")
# ---------------------------------------------------------------------------

def _fake_render_page_png(pdf_path, page, out_prefix, dpi=300):
    p = out_prefix.parent / f"{out_prefix.name}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(f"FAKE-PNG-{pdf_path.name}-{page}".encode("utf-8"))
    return p


class TestPullCrosswalk:
    def test_hit_in_lampiran5_window_renders_one_page(self, tmp_path, monkeypatch):
        vault_root = tmp_path / "vault"
        (vault_root / "bps").mkdir(parents=True)
        bps_pdf = vault_root / "bps" / "tabel.pdf"
        bps_pdf.write_bytes(b"fake-pdf-bytes")
        out_dir = tmp_path / "out" / "68112"
        out_dir.mkdir(parents=True)

        def fake_extract(pdf_path, first, last):
            if (first, last) == dp.BPS_LAMPIRAN5_WINDOW:
                return {117: "row 68112 something", 118: "unrelated"}
            return {233: "unrelated"}

        monkeypatch.setattr(dp, "extract_pages_text", fake_extract)
        monkeypatch.setattr(dp, "render_page_png", _fake_render_page_png)

        items = dp.pull_crosswalk("68112", vault_root, out_dir, bps_pdf=bps_pdf, fetched_at="2026-07-17T00:00:00Z")

        assert len(items) == 1
        assert items[0]["rel_path"] == "crosswalk/lampiran5_p117.png"
        assert items[0]["locator"] == {"lampiran": "5", "page": 117}
        assert (out_dir / "crosswalk" / "lampiran5_p117.png").exists()

    def test_no_hit_in_either_window_writes_absent_with_pages_scanned(self, tmp_path, monkeypatch):
        vault_root = tmp_path / "vault"
        (vault_root / "bps").mkdir(parents=True)
        bps_pdf = vault_root / "bps" / "tabel.pdf"
        bps_pdf.write_bytes(b"fake-pdf-bytes")
        out_dir = tmp_path / "out" / "99999"
        out_dir.mkdir(parents=True)

        monkeypatch.setattr(dp, "extract_pages_text", lambda pdf, first, last: {first: "nothing relevant"})
        monkeypatch.setattr(dp, "render_page_png", _fake_render_page_png)

        items = dp.pull_crosswalk("99999", vault_root, out_dir, bps_pdf=bps_pdf, fetched_at="2026-07-17T00:00:00Z")

        assert len(items) == 1
        assert items[0]["rel_path"] == "crosswalk/ABSENT.json"
        payload = json.loads((out_dir / "crosswalk" / "ABSENT.json").read_text(encoding="utf-8"))
        assert payload["verdict"] == "absent"
        assert sorted(payload["pages_scanned"]) == [117, 233]

    def test_missing_bps_pdf_is_absent_immediately(self, tmp_path):
        vault_root = tmp_path / "vault"
        vault_root.mkdir(parents=True)
        out_dir = tmp_path / "out" / "68112"
        out_dir.mkdir(parents=True)

        items = dp.pull_crosswalk("68112", vault_root, out_dir, bps_pdf=None, fetched_at="2026-07-17T00:00:00Z")

        assert items[0]["rel_path"] == "crosswalk/ABSENT.json"
        payload = json.loads((out_dir / "crosswalk" / "ABSENT.json").read_text(encoding="utf-8"))
        assert payload["pages_scanned"] == []


class TestPullPp28Integration:
    def _vault_with_one_pp28_file(self, tmp_path, letter="I.L"):
        vault_root = tmp_path / "vault"
        (vault_root / "pp28").mkdir(parents=True)
        pdf_path = vault_root / "pp28" / "394941__2.6g Lampiran I.L (I.L.1-500).pdf"
        pdf_path.write_bytes(b"fake-pdf")
        common.append_jsonl(vault_root / "pp28" / "fetch-log.jsonl", {
            "id": 394941, "url": "https://example/394941",
            "rel_path": pdf_path.relative_to(vault_root).as_posix(),
            "http_status": 200, "fetched_at": "2026-07-16T00:00:00Z",
            "fragment": "2.6g", "letter": letter, "range": "1-500",
        })
        return vault_root

    def test_hit_renders_one_page_and_records_locator(self, tmp_path, monkeypatch):
        vault_root = self._vault_with_one_pp28_file(tmp_path, letter="I.L")
        out_dir = tmp_path / "out" / "68112"
        out_dir.mkdir(parents=True)
        record = {"pp28_sources": ["68112"], "_l2_source": None, "sektor_id": "I.J-P"}

        monkeypatch.setattr(dp, "_pdf_page_count", lambda p: 5)
        monkeypatch.setattr(dp, "extract_pages_text", lambda p, first, last: {44: "row 68112 MICE venue"})
        monkeypatch.setattr(dp, "render_page_png", _fake_render_page_png)

        items = dp.pull_pp28("68112", vault_root, out_dir, record, fetched_at="2026-07-17T00:00:00Z")

        assert len(items) == 1
        assert items[0]["rel_path"] == "pp28/394941_p44.png"
        assert items[0]["locator"] == {"lampiran_id": 394941, "page": 44, "code_hunted": "68112"}

    def test_no_hit_writes_absent_with_files_scanned(self, tmp_path, monkeypatch):
        vault_root = self._vault_with_one_pp28_file(tmp_path, letter="I.L")
        out_dir = tmp_path / "out" / "68112"
        out_dir.mkdir(parents=True)
        record = {"pp28_sources": ["68112"], "_l2_source": None, "sektor_id": "I.J-P"}

        monkeypatch.setattr(dp, "_pdf_page_count", lambda p: 5)
        monkeypatch.setattr(dp, "extract_pages_text", lambda p, first, last: {44: "nothing relevant here"})
        monkeypatch.setattr(dp, "render_page_png", _fake_render_page_png)

        items = dp.pull_pp28("68112", vault_root, out_dir, record, fetched_at="2026-07-17T00:00:00Z")

        assert len(items) == 1
        assert items[0]["rel_path"] == "pp28/ABSENT.json"
        payload = json.loads((out_dir / "pp28" / "ABSENT.json").read_text(encoding="utf-8"))
        assert payload["files_scanned"] == [394941]

    def test_narrowed_scan_never_touches_unrelated_letter_file(self, tmp_path, monkeypatch):
        vault_root = self._vault_with_one_pp28_file(tmp_path, letter="I.Z")  # not a candidate letter
        out_dir = tmp_path / "out" / "20111"
        out_dir.mkdir(parents=True)
        # sektor_id "I.F.c" -> candidate letters {I.F, I.L, I.H} — I.Z excluded, _l2_source set (no full scan)
        record = {"pp28_sources": ["20111"], "_l2_source": "OSS_RBA_resiko_2025", "sektor_id": "I.F.c"}

        called = {"n": 0}

        def _boom(*a, **k):
            called["n"] += 1
            raise AssertionError("extract_pages_text must not be called on an excluded file")

        monkeypatch.setattr(dp, "_pdf_page_count", _boom)
        monkeypatch.setattr(dp, "extract_pages_text", _boom)

        items = dp.pull_pp28("20111", vault_root, out_dir, record, fetched_at="2026-07-17T00:00:00Z")

        assert called["n"] == 0
        assert items[0]["rel_path"] == "pp28/ABSENT.json"
        payload = json.loads((out_dir / "pp28" / "ABSENT.json").read_text(encoding="utf-8"))
        assert payload["files_scanned"] == []  # the I.Z file was never a candidate

    def test_page_render_cap_enforced_and_logged(self, tmp_path, monkeypatch, caplog):
        vault_root = self._vault_with_one_pp28_file(tmp_path, letter="I.L")
        out_dir = tmp_path / "out" / "68112"
        out_dir.mkdir(parents=True)
        record = {"pp28_sources": ["68112"], "_l2_source": None, "sektor_id": "I.J-P"}

        # 15 pages, every one a hit — must cap render at PP28_PAGE_CAP (10)
        pages = {p: "68112 hit" for p in range(1, 16)}
        monkeypatch.setattr(dp, "_pdf_page_count", lambda p: 15)
        monkeypatch.setattr(dp, "extract_pages_text", lambda p, first, last: pages)
        monkeypatch.setattr(dp, "render_page_png", _fake_render_page_png)

        items = dp.pull_pp28("68112", vault_root, out_dir, record, fetched_at="2026-07-17T00:00:00Z")

        assert len(items) == dp.PP28_PAGE_CAP


# ---------------------------------------------------------------------------
# pull_one / run — full per-code orchestration, everything monkeypatched at
# the subprocess boundary
# ---------------------------------------------------------------------------

class TestRunEndToEnd:
    def test_full_pull_writes_evidence_index_for_innocence_control_code(self, tmp_path, monkeypatch):
        canonical_path = tmp_path / "canonical.json"
        canonical_path.write_text(json.dumps({"data": [
            {"kode_kbli_2025": "65121", "judul": "x", "sektor_id": "I.J", "_l2_source": "OSS_RBA_resiko_2025",
             "pp28_sources": []},
        ]}), encoding="utf-8")
        vault_root = tmp_path / "vault"
        (vault_root / "oss" / "65121").mkdir(parents=True)
        for ep in dp.OSS_ENDPOINTS:
            (vault_root / "oss" / "65121" / f"{ep}.json").write_bytes(b"{}")
        out_root = tmp_path / "out"

        monkeypatch.setattr(dp, "require_pdf_tools", lambda: None)
        monkeypatch.setattr(dp, "default_bps_pdf", lambda vr: None)

        rc = dp.run(["65121"], vault_root=vault_root, out_root=out_root, canonical_path=canonical_path, bps_pdf=None)

        assert rc == 0
        index = json.loads((out_root / "65121" / "evidence-index.json").read_text(encoding="utf-8"))
        rel_paths = {i["rel_path"] for i in index}
        assert "canonical.json" in rel_paths
        assert any(rp.startswith("oss/") for rp in rel_paths)
        assert "crosswalk/ABSENT.json" in rel_paths
        assert "pp28/NOT_APPLICABLE.json" in rel_paths  # innocence control: no pp28_sources

    def test_code_missing_from_canonical_is_a_visible_failure_not_a_crash(self, tmp_path, monkeypatch):
        canonical_path = tmp_path / "canonical.json"
        canonical_path.write_text(json.dumps({"data": []}), encoding="utf-8")
        vault_root = tmp_path / "vault"
        vault_root.mkdir(parents=True)
        out_root = tmp_path / "out"
        monkeypatch.setattr(dp, "require_pdf_tools", lambda: None)

        rc = dp.run(["99999"], vault_root=vault_root, out_root=out_root, canonical_path=canonical_path, bps_pdf=None)

        assert rc == 1
