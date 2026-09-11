"""Reproduction test — spec docs/specs/2026-09-11-kbli-l2-oss-resnapshot-reingest-spec.md
rule 4 ("reproduce before you change"), run on a 6-code slice of REAL July
(2026-07-17) vault evidence (fixtures/l2_repro/) instead of the full
1559-code vault (that full run is a separate manual gate, not CI — see the
PR-A report for its SUMMARY line and /tmp/l2/field_diff_*.md for the
full-scale field-level measurement).

Codes: 56101, 10215 (typical single/dual-scope), 47111 (multi-scope,
substitutes 02401 — 02401's ruang_lingkup.json is ~1 MB even minified, too
large for a fixture), 85583 (404/no-scope, absence record only), 50131
(Besar-only tier), 68111. No code in the July vault carries a
`fiktif_positif` field on OSS's raw payload (grepped the whole vault, zero
hits) — see below for why the CANONICAL corpus has it anyway.

SCOPE — what this test does and does NOT check, and why:

L2-OWNED fields (what `parse_per_skala` in scripts/build_kbli_l2_oss_risk.py
actually computes from the OSS raw payload, and what this test asserts
reproduces exactly): `skala_usaha`, `kategori_risiko`, `scope_index`,
`scope_uraian`, `perizinan`, `persyaratan`, `kewajiban`, `kewenangan`, plus
the record-level `_l2_source`/`_l2_status`.

EXCLUDED, on purpose, NOT a weaker check — two fields the L2 transform does
NOT own, confirmed by the team lead 2026-09-11:
  - `per_skala[*].jangka_waktu` is rewritten AFTER L2 runs, by
    scripts/enrich_kbli_jangka_waktu.py (2026-06-28, PP28-rule-derived text
    like "Otomatis") — the canonical corpus's jangka_waktu values were never
    produced by THIS script in the first place, so comparing them against
    this script's raw-payload-only computation was always comparing two
    different pipeline stages, not a reproduction check. Two more
    canonical-only keys, `jangka_waktu_source` (4,095 rows corpus-wide) and
    `fiktif_positif` (9,095 rows corpus-wide), are silently DROPPED when
    this script's --apply replaces a code's `per_skala` wholesale (measured
    on the full 1559-code July run: 941 and 1,337 codes respectively lose
    the field) — a real, separately-reported data-loss finding, but a
    POST-L2-layer concern, not this test's job.
  - `l4_bali.*` — this script does compute a verdict/blocked/status/reason,
    but the STATUS LABELS already sitting in the canonical corpus (e.g.
    "CHIUSO_MORATORIA_BALI", "BLOCCATO_DIPENDE_SCOPE") were set by later
    cure scripts on top of this script's original June output, not by this
    script alone — so "does l4_bali reproduce" is a different, larger
    question (the NO_BESAR handling divergence between scripts/ and
    apps/backend-rag/'s copy, reported separately) than "does the L2
    transform reproduce its own output".

Why the earlier version of this test passed on 56101 despite
`jangka_waktu` diverging ("Otomatis" vs `""`): it explicitly excluded
`jangka_waktu` from the failure condition (asserted `field == "jangka_waktu"`
for every diff found) — so the PASS was legitimate given that assertion, not
weaker than claimed. But the small 6-code sample also happened not to
exercise the ONE code (49213, not in this fixture set) where the full 1559-
code scan found a genuine, non-jangka_waktu content drift on
`scope_uraian`/`perizinan`/`persyaratan`/`kewajiban`/`kewenangan` between the
June raw fetch and the July vault — a real, rare (1/1559) upstream content
change, unrelated to jangka_waktu, that a 6-code fixture cannot catch by
construction. Flagged here so the gap is explicit, not implied.

CODEX ROUND 1 (F2): the previous version of this file checked
`canon_rec.get("_l2_status")`/`_l2_source` on the FIXTURE input against a
hardcoded string, without ever invoking the transform's write path — a
broken `main()` (bad CLI wiring, a write that silently no-ops, wrong target
path, a broken JSON dump) would have stayed green. `TestApplyWritePath`
below calls `build_kbli_l2_oss_risk.main([..., "--apply"])` for real, reads
back the file IT wrote, and — to make sure a no-op `--apply` can't pass by
coincidence (the owned fields already match the canonical seed, so a no-op
would trivially "reproduce" too) — first CORRUPTS the seed's owned fields
with an obviously-wrong placeholder, then asserts the written output is
NEITHER the placeholder NOR anything but the correct recomputed value.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from kbli_filiera import vault_to_risk_jsonl as adapter  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "l2_repro"
REPO_ROOT = Path(__file__).resolve().parents[3]

# The subset of per_skala fields THIS transform computes from the OSS raw
# payload — jangka_waktu/jangka_waktu_source/fiktif_positif and the other
# canonical-only keys (dati_inferiti, parameter, pb_umku, sanksi_*) are
# owned by later enrichment layers, not by parse_per_skala.
L2_OWNED_PER_SKALA_FIELDS = [
    "skala_usaha", "kategori_risiko", "scope_index", "scope_uraian",
    "perizinan", "persyaratan", "kewajiban", "kewenangan",
]
CORRUPT_SENTINEL = "__CORRUPTED_SEED__"


def _import_transform():
    sys.path.insert(0, str(REPO_ROOT))
    import scripts.build_kbli_l2_oss_risk as transform  # noqa: E402
    return transform


def _run_adapter(tmp_path: Path) -> dict:
    """Runs the adapter over the fixture vault and returns {kode: record}."""
    raw_out = tmp_path / "july.jsonl"
    rc = adapter.main([
        "--vault-root", str(FIXTURES / "vault"),
        "--ground-truth", str(FIXTURES / "ground_truth.json"),
        "--out", str(raw_out),
    ])
    assert rc == 0
    lines = raw_out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6
    return {json.loads(line)["kode"]: json.loads(line) for line in lines}, raw_out


def _project(ps_rows: list[dict]) -> list[dict]:
    """per_skala rows reduced to the L2-owned field subset, sorted by
    (scope_index, skala_usaha) so row order never causes a false diff."""
    projected = [{f: row.get(f) for f in L2_OWNED_PER_SKALA_FIELDS} for row in ps_rows]
    return sorted(projected, key=lambda r: (r["scope_index"], tuple(r["skala_usaha"] or [])))


def _load_canon_slice() -> dict:
    return json.loads((FIXTURES / "canonical_slice.json").read_text(encoding="utf-8"))


class TestL2OwnedFieldsPureFunction:
    def test_parse_per_skala_reproduces_l2_owned_fields(self, tmp_path):
        """Pure-function check: parse_per_skala(raw), projected to the
        L2-owned field subset, matches the canonical corpus for the 5 data
        codes. Does NOT exercise --apply/main() — see TestApplyWritePath
        for the write-path check codex round 1 (F2) asked for."""
        transform = _import_transform()
        raw_by_code, _ = _run_adapter(tmp_path)
        canon_by_code = {str(r["kode_kbli_2025"]): r for r in _load_canon_slice()["data"]}

        checked_data_codes = 0
        for code, canon_rec in canon_by_code.items():
            r = raw_by_code[code]
            if r["status"] != 200 or not r["data"].get("success"):
                continue
            checked_data_codes += 1
            new_ps = transform.parse_per_skala(r["data"])
            old_ps = canon_rec.get("per_skala", []) or []
            assert _project(new_ps) == _project(old_ps), code

        assert checked_data_codes == 5  # 56101, 10215, 47111, 50131, 68111

    def test_jangka_waktu_is_excluded_not_silently_matching(self, tmp_path):
        """Guards the docstring's claim: jangka_waktu genuinely DOES diverge
        for this fixture set (it is excluded by design, not because it
        happens to match) — if a future vault snapshot ever restores that
        field, this test should be revisited, not silently kept green."""
        transform = _import_transform()
        raw_by_code, _ = _run_adapter(tmp_path)
        canon_by_code = {str(r["kode_kbli_2025"]): r for r in _load_canon_slice()["data"]}

        any_jangka_diff = False
        for code, canon_rec in canon_by_code.items():
            r = raw_by_code[code]
            if r["status"] != 200 or not r["data"].get("success"):
                continue
            new_ps = transform.parse_per_skala(r["data"])
            old_ps = canon_rec.get("per_skala", []) or []

            def key(p):
                return (p["scope_index"], tuple(p["skala_usaha"]))

            new_by = {key(p): p for p in new_ps}
            old_by = {key(p): p for p in old_ps}
            for k in set(new_by) & set(old_by):
                if new_by[k].get("jangka_waktu") != old_by[k].get("jangka_waktu"):
                    any_jangka_diff = True

        assert any_jangka_diff, (
            "jangka_waktu matched everywhere in this fixture set — the exclusion "
            "in test_parse_per_skala_reproduces_l2_owned_fields is no longer masking "
            "a real diff; re-check whether it should still be excluded"
        )


class TestApplyWritePath:
    """Exercises scripts/build_kbli_l2_oss_risk.py's ACTUAL --apply write
    path end to end (argparse, --root/--raw resolution, per-code branching,
    JSON dump, file write) — the thing F2 said must exist: a broken main()
    must be able to fail this test."""

    def _build_root_with_corrupted_seed(self, tmp_path: Path) -> Path:
        """Copies the canonical slice to both --root targets, then corrupts
        every L2-owned per_skala field with an obvious sentinel value. If
        --apply were a no-op (or wrote the wrong target, or crashed
        silently), the written file would still carry the sentinel — the
        only way to see the CORRECT recomputed value is for --apply to have
        actually run and actually written its result back out."""
        canon = _load_canon_slice()
        for rec in canon["data"]:
            for row in rec.get("per_skala", []) or []:
                for f in L2_OWNED_PER_SKALA_FIELDS:
                    if f in row and f not in ("scope_index",):
                        row[f] = CORRUPT_SENTINEL

        root = tmp_path / "root"
        for rel in ("data/source_documents/KBLI_2025_FINAL_CLEAN.json",
                    "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"):
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(canon, ensure_ascii=False), encoding="utf-8")
        return root

    def test_apply_writes_correct_l2_owned_fields_not_the_corrupted_seed(self, tmp_path):
        transform = _import_transform()
        raw_by_code, raw_out = _run_adapter(tmp_path)
        root = self._build_root_with_corrupted_seed(tmp_path)

        transform.main(["--root", str(root), "--raw", str(raw_out), "--apply"])
        # main() has no explicit return contract (prints a report, writes on
        # --apply) — the write path is what this test verifies, not an exit code.

        written = json.loads((root / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json").read_text(encoding="utf-8"))
        written_by_code = {str(r["kode_kbli_2025"]): r for r in written["data"]}
        canon_by_code = {str(r["kode_kbli_2025"]): r for r in _load_canon_slice()["data"]}  # uncorrupted original

        checked_data_codes = 0
        checked_absent_codes = 0
        for code, canon_rec in canon_by_code.items():
            r = raw_by_code[code]
            wrec = written_by_code[code]

            if r["status"] != 200 or not r["data"].get("success"):
                # 85583: no_oss_risk path — per_skala untouched (still
                # carries the corrupted seed, that branch never rewrites
                # it), but _l2_status IS written fresh by --apply.
                assert wrec.get("_l2_status") == "no_oss_risk", code
                checked_absent_codes += 1
                continue
            checked_data_codes += 1

            written_projected = _project(wrec.get("per_skala", []) or [])
            expected_projected = _project(canon_rec.get("per_skala", []) or [])
            assert written_projected == expected_projected, code
            assert CORRUPT_SENTINEL not in json.dumps(written_projected), (
                f"{code}: written per_skala still carries the corrupted seed — "
                f"--apply did not actually recompute it"
            )
            assert wrec.get("_l2_source") == "OSS_RBA_resiko_2025", code

        assert checked_data_codes == 5
        assert checked_absent_codes == 1
