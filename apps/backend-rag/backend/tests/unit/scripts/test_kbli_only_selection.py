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
    filter_to_codes,
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
        point = build_point("56101", self._gold(), self._base(), "2026-08-08T00:00:00+00:00")
        assert point["payload"]["indexed_at"] == "2026-08-08T00:00:00+00:00"
        assert "metadata" not in point["payload"]

    def test_point_shape(self):
        """Innocence: the rest of the point shape (id + text-to-embed +
        existing flat fields) is unchanged by the extraction."""
        point = build_point("56101", self._gold(), self._base(), "2026-08-08T00:00:00+00:00")
        assert set(point.keys()) == {"id", "payload", "_text_to_embed"}
        assert point["payload"]["kode_kbli"] == "56101"
        assert point["payload"]["doc_type"] == "kbli_gold"
        assert point["_text_to_embed"]

    def test_deterministic_id_across_calls(self):
        """Innocence: id stays deterministic (idempotent upserts) — the
        extraction must not perturb deterministic_uuid's inputs."""
        p1 = build_point("56101", self._gold(), self._base(), "2026-08-08T00:00:00+00:00")
        p2 = build_point("56101", self._gold(), self._base(), "2026-08-08T01:00:00+00:00")
        assert p1["id"] == p2["id"]
        assert p1["payload"]["indexed_at"] != p2["payload"]["indexed_at"]


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
