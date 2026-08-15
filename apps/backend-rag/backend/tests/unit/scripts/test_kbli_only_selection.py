"""Tests for the --only per-code selection logic and the robust repo-root
resolver added to both Qdrant indexers.

Pure-function / filesystem tests only — no network, no Qdrant, no OpenAI.

We exercise:
- ``parse_only_codes`` (flag parsing + validation, shared by both scripts).
- ``filter_to_codes`` / ``filter_entries_to_codes`` (entry filtering).
- ``resolve_repo_root`` (the shared marker-walk that replaced ``parents[N]``).
"""

import argparse

import pytest

from backend.scripts._kbli_repo_root import resolve_repo_root
from backend.scripts.index_kbli_gold_content import (
    build_point,
    certification_content,
    field_coverage,
    filter_to_codes,
    sample_lines,
    tka_total,
)
from backend.scripts.index_kbli_gold_content import (
    parse_only_codes as parse_gold_only,
)
from backend.scripts.reindex_kbli_2025_final import (
    filter_entries_to_codes,
)
from backend.scripts.reindex_kbli_2025_final import (
    parse_only_codes as parse_bps_only,
)
from backend.services.kbli_editorial_certification import (
    pma_editorial_fingerprint,
    stable_editorial_sha256,
)

# ─── parse_only_codes (shared semantics, two copies) ───────────────────────


class TestParseOnlyCodes:
    """Both copies share identical semantics — parametrise over both."""

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_none_when_flag_absent(self, parser):
        assert parser(None) is None
        assert parser("") is None

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_single_code(self, parser):
        assert parser("56101") == ["56101"]

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_multiple_codes(self, parser):
        assert parser("56101,56210,61108") == ["56101", "56210", "61108"]

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_strips_whitespace(self, parser):
        assert parser(" 56101 , 56210 ") == ["56101", "56210"]

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_deduplicates_preserving_order(self, parser):
        assert parser("56101,56210,56101") == ["56101", "56210"]

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_rejects_too_short(self, parser):
        with pytest.raises(argparse.ArgumentTypeError, match="invalid KBLI code"):
            parser("5610")

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_rejects_too_long(self, parser):
        with pytest.raises(argparse.ArgumentTypeError, match="invalid KBLI code"):
            parser("561011")

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_rejects_alpha(self, parser):
        with pytest.raises(argparse.ArgumentTypeError, match="invalid KBLI code"):
            parser("5610a")

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_rejects_empty_token(self, parser):
        with pytest.raises(argparse.ArgumentTypeError, match="invalid KBLI code"):
            parser("56101,,56210")

    @pytest.mark.parametrize("parser", [parse_gold_only, parse_bps_only])
    def test_rejects_junk(self, parser):
        with pytest.raises(argparse.ArgumentTypeError, match="invalid KBLI code"):
            parser("hello")


# ─── filter_to_codes (gold indexer — dict input) ───────────────────────────


class TestFilterToCodes:
    def _entries(self) -> dict[str, dict]:
        return {
            "56101": {"whatItMeans": "Restoran"},
            "56210": {"whatItMeans": "Katering"},
            "61108": {"whatItMeans": "Telekomunikasi"},
        }

    def test_passthrough_when_none(self):
        entries = self._entries()
        assert filter_to_codes(entries, None) is entries

    def test_selects_subset(self):
        result = filter_to_codes(self._entries(), ["56101", "61108"])
        assert set(result.keys()) == {"56101", "61108"}

    def test_preserves_requested_order(self):
        result = filter_to_codes(self._entries(), ["61108", "56101"])
        assert list(result.keys()) == ["61108", "56101"]

    def test_single_code(self):
        result = filter_to_codes(self._entries(), ["56210"])
        assert list(result.keys()) == ["56210"]

    def test_errors_on_missing_code(self):
        with pytest.raises(SystemExit) as exc_info:
            filter_to_codes(self._entries(), ["56101", "99999"])
        assert exc_info.value.code == 1

    def test_errors_name_all_missing(self, caplog):
        with pytest.raises(SystemExit):
            filter_to_codes(self._entries(), ["99999", "88888"])
        msgs = [r.getMessage() for r in caplog.records]
        assert any("99999" in m and "88888" in m for m in msgs)


# ─── filter_entries_to_codes (BPS re-indexer — list input) ──────────────────


class TestFilterEntriesToCodes:
    def _entries(self) -> list[dict]:
        return [
            {"kode_kbli_2025": "56101", "judul": "Restoran"},
            {"kode_kbli_2025": "56210", "judul": "Katering"},
            {"kode_kbli_2025": "61108", "judul": "Telekomunikasi"},
        ]

    def test_passthrough_when_none(self):
        entries = self._entries()
        assert filter_entries_to_codes(entries, None) is entries

    def test_selects_subset(self):
        result = filter_entries_to_codes(self._entries(), ["56101", "61108"])
        assert [e["kode_kbli_2025"] for e in result] == ["56101", "61108"]

    def test_preserves_requested_order(self):
        result = filter_entries_to_codes(self._entries(), ["61108", "56101"])
        assert [e["kode_kbli_2025"] for e in result] == ["61108", "56101"]

    def test_single_code(self):
        result = filter_entries_to_codes(self._entries(), ["56210"])
        assert len(result) == 1
        assert result[0]["kode_kbli_2025"] == "56210"

    def test_errors_on_missing_code(self):
        with pytest.raises(SystemExit) as exc_info:
            filter_entries_to_codes(self._entries(), ["56101", "99999"])
        assert exc_info.value.code == 1

    def test_errors_name_all_missing(self, caplog):
        with pytest.raises(SystemExit):
            filter_entries_to_codes(self._entries(), ["99999", "88888"])
        msgs = [r.getMessage() for r in caplog.records]
        assert any("99999" in m and "88888" in m for m in msgs)


# ─── build_point (gold indexer — flat payload, KBLI flat-payload golden rule) ──


def _certified_point(
    code: str,
    gold: dict,
    base: dict,
    indexed_at: str,
) -> dict:
    canonical_base = {
        "kode_kbli_2025": code,
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        "pma_verification_status": "located",
        "pma_official_basis": "Perpres 49/2021 test locator",
        "pma_source_vintage": "2021-05-25",
        "pma_cap_verified": True,
        **base,
    }
    canonical_base["kode_kbli_2025"] = code
    registry = {
        "standaloneGold": {
            code: {
                "pmaFingerprint": pma_editorial_fingerprint(canonical_base),
                "contentSha256": stable_editorial_sha256(certification_content(gold)),
            }
        }
    }
    point = build_point(code, gold, canonical_base, indexed_at, registry)
    assert point is not None
    return point


class TestBuildPoint:
    """build_point() is the exact function main() calls per code — never a
    recreated copy of the production logic (Codex review on #3817). It crashed
    on every code since birth (`payload["metadata"]["indexed_at"]` against a
    payload that has no "metadata" key at all — build_payload() is flat)."""

    def _gold(self) -> dict:
        return {"whatItMeans": "Restoran dan penyediaan makanan."}

    def _base(self) -> dict:
        return {"judul": "Restoran", "sektor_id": "I", "pma_status": "TERBUKA"}

    def test_indexed_at_is_flat_not_nested(self):
        """Guilt: the point actually produced sets payload['indexed_at'] and
        carries NO 'metadata' key — this is what crashed unconditionally
        before the fix."""
        point = _certified_point("56101", self._gold(), self._base(), "2026-08-08T00:00:00+00:00")
        assert point["payload"]["indexed_at"] == "2026-08-08T00:00:00+00:00"
        assert "metadata" not in point["payload"]

    def test_point_shape(self):
        """Innocence: the rest of the point shape (id + text-to-embed +
        existing flat fields) is unchanged by the extraction."""
        point = _certified_point("56101", self._gold(), self._base(), "2026-08-08T00:00:00+00:00")
        assert set(point.keys()) == {"id", "payload", "_text_to_embed"}
        assert point["payload"]["kode_kbli"] == "56101"
        assert point["payload"]["doc_type"] == "kbli_gold"
        assert point["_text_to_embed"]

    def test_deterministic_id_across_calls(self):
        """Innocence: id stays deterministic (idempotent upserts) — the
        extraction must not perturb deterministic_uuid's inputs."""
        p1 = _certified_point("56101", self._gold(), self._base(), "2026-08-08T00:00:00+00:00")
        p2 = _certified_point("56101", self._gold(), self._base(), "2026-08-08T01:00:00+00:00")
        assert p1["id"] == p2["id"]
        assert p1["payload"]["indexed_at"] != p2["payload"]["indexed_at"]


# ─── field_coverage / tka_total / sample_lines (gold indexer stats blocks) ──
#
# These are the 4 REMAINING nested-metadata crash sites that #3832 did not
# touch (it only fixed build_point()) — never reached by any prior run since
# build_point() crashed first. Every test here builds its points with the
# REAL build_point() and feeds them to the REAL helper — build→stats→sample,
# end to end on the actual production call path, per the W101-recidiva
# symmetry lesson (a fix that only covers the site that bit you is half a
# fix).


class TestFieldCoverage:
    def test_counts_fields_across_points_synthetic(self):
        """Direct unit check on the counting logic with hand-built points."""
        points = [
            {"payload": {"gold_fields": ["whatItMeans", "whatYouNeed"]}},
            {"payload": {"gold_fields": ["whatItMeans"]}},
        ]
        assert field_coverage(points) == {"whatItMeans": 2, "whatYouNeed": 1}

    def test_end_to_end_via_real_build_point(self):
        """Guilt: real build_point() output flows into field_coverage() —
        this is exactly the shape that KeyError'd on `["metadata"]` at the
        original line 428."""
        gold = {"whatItMeans": "Restoran", "whatYouNeed": "Izin usaha mikro"}
        base = {"judul": "Restoran", "sektor_id": "I"}
        point = _certified_point("56101", gold, base, "2026-08-08T00:00:00+00:00")
        coverage = field_coverage([point])
        assert coverage["whatItMeans"] == 1
        assert coverage["whatYouNeed"] == 1


class TestTkaTotal:
    def test_counts_flagged_points_synthetic(self):
        points = [
            {"payload": {"has_tka_info": True}},
            {"payload": {"has_tka_info": False}},
            {"payload": {"has_tka_info": True}},
        ]
        assert tka_total(points) == 2

    def test_end_to_end_via_real_build_point(self):
        """Guilt: real build_point() output flows into tka_total() — this is
        exactly the shape that KeyError'd on `["metadata"]` at the original
        line 434."""
        gold_with_tka = {
            "whatItMeans": "x",
            "tka_positions": [{"en": "Engineer", "id": "Insinyur"}],
        }
        gold_without_tka = {"whatItMeans": "y"}
        base = {"judul": "x", "sektor_id": "I"}
        points = [
            _certified_point("11111", gold_with_tka, base, "2026-08-08T00:00:00+00:00"),
            _certified_point("22222", gold_without_tka, base, "2026-08-08T00:00:00+00:00"),
        ]
        assert tka_total(points) == 1


class TestSampleLines:
    def test_lines_shape_synthetic(self):
        point = {
            "payload": {"kode": "56101", "judul": "Restoran dan Penyediaan Makanan"},
            "_text_to_embed": "preview text " * 40,
        }
        lines = sample_lines(point)
        assert len(lines) == 3
        assert any("56101" in line for line in lines)
        assert any("Restoran dan Penyediaan Makanan" in line for line in lines)

    def test_end_to_end_via_real_build_point(self):
        """Guilt: real build_point() output flows into sample_lines() — this
        is exactly the shape that KeyError'd on `["metadata"]` at the
        original lines 440/441 (Code + Judul)."""
        gold = {"whatItMeans": "Restoran"}
        base = {"judul": "Restoran Padang Asli", "sektor_id": "I"}
        point = _certified_point("56101", gold, base, "2026-08-08T00:00:00+00:00")
        lines = sample_lines(point)
        assert any("56101" in line for line in lines)
        assert any("Restoran Padang Asli" in line for line in lines)


# ─── resolve_repo_root (shared marker-walk, replaces parents[N]) ────────────

_MARKER = "apps/kbli-navigator/lib/kbli-gold-content.ts"


class TestResolveRepoRoot:
    """The resolver must work in any directory layout — dev checkout, Fly
    container, or a tmp_path test sandbox — and never raise IndexError."""

    def test_honors_env_override(self, tmp_path, monkeypatch):
        """KBLI_REPO_ROOT is the authoritative source when set."""
        root = tmp_path / "fake-repo"
        marker_dir = root / "apps" / "kbli-navigator" / "lib"
        marker_dir.mkdir(parents=True)
        (marker_dir / "kbli-gold-content.ts").write_text("// stub")

        monkeypatch.setenv("KBLI_REPO_ROOT", str(root))
        result = resolve_repo_root([_MARKER], script_file=str(tmp_path / "script.py"))
        assert result == root.resolve()

    def test_env_override_missing_marker_exits_with_error(self, tmp_path, monkeypatch):
        """If KBLI_REPO_ROOT points at a dir without the marker, exit 1."""
        root = tmp_path / "empty-root"
        root.mkdir()

        monkeypatch.setenv("KBLI_REPO_ROOT", str(root))
        with pytest.raises(SystemExit) as exc_info:
            resolve_repo_root([_MARKER], script_file=str(tmp_path / "script.py"))
        assert exc_info.value.code == 1

    def test_env_override_not_a_dir_exits_with_error(self, tmp_path, monkeypatch):
        """If KBLI_REPO_ROOT points at a file, exit 1."""
        junk = tmp_path / "not-a-dir"
        junk.write_text("oops")

        monkeypatch.setenv("KBLI_REPO_ROOT", str(junk))
        with pytest.raises(SystemExit) as exc_info:
            resolve_repo_root([_MARKER], script_file=str(tmp_path / "script.py"))
        assert exc_info.value.code == 1

    def test_walk_up_finds_marker(self, tmp_path, monkeypatch):
        """Without env override, walking up from the script's location finds
        the first ancestor that contains the marker file."""
        root = tmp_path / "repo"
        deep = root / "a" / "b" / "c" / "scripts"
        deep.mkdir(parents=True)

        marker_dir = root / "apps" / "kbli-navigator" / "lib"
        marker_dir.mkdir(parents=True)
        (marker_dir / "kbli-gold-content.ts").write_text("// stub")

        monkeypatch.delenv("KBLI_REPO_ROOT", raising=False)
        script = deep / "indexer.py"
        script.write_text("# stub")
        result = resolve_repo_root([_MARKER], script_file=str(script))
        assert result == root.resolve()

    def test_walk_up_finds_shallow_root(self, tmp_path, monkeypatch):
        """Simulates the Fly container layout: /app/backend/scripts/indexer.py
        with only 2 ancestors before /app — parents[4] would IndexError here."""
        root = tmp_path / "app"
        scripts_dir = root / "backend" / "scripts"
        scripts_dir.mkdir(parents=True)

        marker_dir = root / "apps" / "kbli-navigator" / "lib"
        marker_dir.mkdir(parents=True)
        (marker_dir / "kbli-gold-content.ts").write_text("// stub")

        monkeypatch.delenv("KBLI_REPO_ROOT", raising=False)
        script = scripts_dir / "indexer.py"
        script.write_text("# stub")
        result = resolve_repo_root([_MARKER], script_file=str(script))
        assert result == root.resolve()

    def test_exhausted_walk_exits_without_index_error(self, tmp_path, monkeypatch):
        """If no ancestor has the marker, sys.exit(1) with a message — NOT
        IndexError (the original bug)."""
        # A deep tree with NO marker anywhere.
        deep = tmp_path / "x" / "y" / "z"
        deep.mkdir(parents=True)
        monkeypatch.delenv("KBLI_REPO_ROOT", raising=False)
        script = deep / "orphan.py"
        script.write_text("# stub")

        with pytest.raises(SystemExit) as exc_info:
            resolve_repo_root([_MARKER], script_file=str(script))
        assert exc_info.value.code == 1

    def test_exhausted_walk_names_probed_paths(self, tmp_path, monkeypatch, capsys):
        """The error message should name the marker paths probed."""
        deep = tmp_path / "x" / "y" / "z"
        deep.mkdir(parents=True)
        monkeypatch.delenv("KBLI_REPO_ROOT", raising=False)
        script = deep / "orphan.py"
        script.write_text("# stub")

        with pytest.raises(SystemExit):
            resolve_repo_root([_MARKER], script_file=str(script))
        captured = capsys.readouterr()
        assert _MARKER in captured.err

    def test_multiple_markers_all_required(self, tmp_path, monkeypatch):
        """When multiple markers are given, ALL must exist for a candidate."""
        root = tmp_path / "repo"
        scripts_dir = root / "deep" / "scripts"
        scripts_dir.mkdir(parents=True)

        # Only one marker present.
        m1_dir = root / "apps" / "kbli-navigator" / "lib"
        m1_dir.mkdir(parents=True)
        (m1_dir / "kbli-gold-content.ts").write_text("// stub")

        monkeypatch.delenv("KBLI_REPO_ROOT", raising=False)
        script = scripts_dir / "indexer.py"
        script.write_text("# stub")

        # Two markers, second missing → should NOT resolve here.
        with pytest.raises(SystemExit):
            resolve_repo_root(
                [_MARKER, "apps/kbli-navigator/data/kbli-2025.json"],
                script_file=str(script),
            )
