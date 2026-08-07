"""Guilt and innocence for the 47222 TERTUTUP -> TERBATAS one-shot.

The dangerous failure here is not the number (pma_max_asing stays 0 either
way) — it is the STATUS label. `TERTUTUP` says "closed to everyone";
`TERBATAS`/0 says "closed to foreign capital, open to domestic entities,
including Koperasi/UMKM". Getting this wrong in the other direction (writing
TERBATAS on a code that really is closed to everyone) would tell a client an
activity is reachable through an Indonesian partner when it is not. So this
file spends most of its weight on refusals: the compiler must recognise
exactly the one state it is licensed to touch, and refuse anything else.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

import cure_canonical_47222_reservation as mod  # noqa: E402

VALID_BASIS = (
    "Perpres 10/2021 Lampiran II, line 3731 '- Minuman Tidak Beralkohol 47222 V', "
    "V in DIALOKASIKAN-UNTUK-KOPERASI-DAN-UMKM column"
)


def _rec(code="47222", status="TERTUTUP", cap=0, verified=True, basis=VALID_BASIS,
         kondisi=None, **extra):
    return {
        "kode_kbli_2025": code,
        "judul": "x",
        "pma_status": status,
        "pma_max_asing": cap,
        "pma_cap_verified": verified,
        "pma_official_basis": basis,
        "pma_kondisi": kondisi,
        **extra,
    }


def _dataset(tmp_path, records):
    p = tmp_path / "canon.json"
    p.write_text(json.dumps({"data": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


# --- the real dataset, post-cure -------------------------------------------


def test_the_real_canonical_47222_is_terbatas_with_zero_cap():
    records = json.loads(mod.CANONICAL.read_text(encoding="utf-8"))["data"]
    rec = {str(r["kode_kbli_2025"]): r for r in records}["47222"]
    assert rec["pma_status"] == "TERBATAS"
    assert rec["pma_max_asing"] == 0
    assert rec["pma_cap_verified"] is True
    assert "Lampiran II" in rec["pma_official_basis"]


# --- guilt: the patch itself -------------------------------------------------


def test_apply_flips_status_and_fills_an_absent_kondisi(tmp_path):
    path = _dataset(tmp_path, [_rec(kondisi=None)])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))["data"][0]
    assert after["pma_status"] == "TERBATAS"
    assert after["pma_max_asing"] == 0
    assert after["pma_kondisi"] == mod.KONDISI_IF_ABSENT


def test_apply_never_overwrites_an_existing_kondisi(tmp_path):
    path = _dataset(tmp_path, [_rec(kondisi="Kemitraan dengan UMKM/Koperasi")])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))["data"][0]
    assert after["pma_status"] == "TERBATAS"
    assert after["pma_kondisi"] == "Kemitraan dengan UMKM/Koperasi"


def test_second_run_is_a_no_op(tmp_path, capsys):
    path = _dataset(tmp_path, [_rec(kondisi="Kemitraan dengan UMKM/Koperasi")])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    capsys.readouterr()
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    assert "idempotent" in capsys.readouterr().out


def test_official_basis_is_left_byte_unchanged(tmp_path):
    path = _dataset(tmp_path, [_rec(kondisi="Kemitraan dengan UMKM/Koperasi")])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    after = json.loads(path.read_text(encoding="utf-8"))["data"][0]
    assert after["pma_official_basis"] == VALID_BASIS


# --- guilt: refusals ---------------------------------------------------------


def test_refuses_when_the_code_is_missing(tmp_path):
    path = _dataset(tmp_path, [_rec(code="99999")])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_the_cap_is_not_zero(tmp_path):
    path = _dataset(tmp_path, [_rec(cap=49)])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_on_an_unexpected_status(tmp_path):
    """Neither TERTUTUP (what it expects to cure) nor TERBATAS (already cured) —
    e.g. TERBUKA. The world moved under the adjudication; do not guess."""
    path = _dataset(tmp_path, [_rec(status="TERBUKA")])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_the_cap_is_not_verified(tmp_path):
    path = _dataset(tmp_path, [_rec(verified=False)])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_when_the_basis_no_longer_cites_lampiran_ii(tmp_path):
    path = _dataset(tmp_path, [_rec(basis="some other note entirely")])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


# --- guilt: a claimed noop must stand on the same pins as a fresh cure ------
#
# Round-4 review finding: the old noop branch returned True on `TERBATAS`/0
# alone, before EITHER `pma_cap_verified` or `pma_official_basis` was read —
# so an already-cured record with one of those pins silently stripped would
# still report a clean "nothing to do".


def test_refuses_a_claimed_noop_whose_verified_pin_was_stripped(tmp_path):
    path = _dataset(tmp_path, [_rec(status="TERBATAS", cap=0, verified=False)])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


def test_refuses_a_claimed_noop_whose_basis_drifted(tmp_path):
    path = _dataset(tmp_path, [_rec(status="TERBATAS", cap=0, basis="some other note entirely")])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--apply", "--dataset", str(path)]) == 2
    assert path.read_text(encoding="utf-8") == before


# --- innocence ----------------------------------------------------------------


def test_a_neighbor_record_is_never_touched(tmp_path):
    neighbor = _rec(code="47111", status="TERBATAS", cap=0, kondisi="UMKM only")
    path = _dataset(tmp_path, [_rec(), neighbor])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    after = {str(r["kode_kbli_2025"]): r for r in json.loads(path.read_text(encoding="utf-8"))["data"]}
    assert after["47111"] == neighbor


def test_dry_run_writes_nothing(tmp_path):
    path = _dataset(tmp_path, [_rec()])
    before = path.read_text(encoding="utf-8")
    assert mod.main(["--dataset", str(path)]) == 0
    assert path.read_text(encoding="utf-8") == before


def test_already_cured_record_is_left_byte_identical(tmp_path):
    """A no-op run must not reformat the file — the real canonical is 540k
    lines and a spurious diff would make a one-code cure unreviewable."""
    path = _dataset(tmp_path, [_rec(status="TERBATAS", kondisi="Kemitraan dengan UMKM/Koperasi")])
    before = path.read_bytes()
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    assert path.read_bytes() == before


def test_applying_to_a_fixture_never_touches_the_repos_sidecar(tmp_path):
    """W96: a test that rewrites production state is its own defect."""
    sidecar_before = mod.SIDECAR_VERSION.read_bytes()
    copy_before = mod.SIDECAR_DATASET.stat().st_mtime_ns
    path = _dataset(tmp_path, [_rec(kondisi="Kemitraan dengan UMKM/Koperasi")])
    assert mod.main(["--apply", "--dataset", str(path)]) == 0
    assert mod.SIDECAR_VERSION.read_bytes() == sidecar_before
    assert mod.SIDECAR_DATASET.stat().st_mtime_ns == copy_before


# --- guilt: a claimed noop must also verify (and repair) the fleet ---------
#
# Round-4 review finding: the noop branch used to stop at "nothing to do on
# canonical" and never checked whether consumer copies or the version
# sidecar had drifted. A canonical that was itself correctly TERBATAS/0 but
# had one stale consumer copy passed as a clean noop while the fleet was
# still wrong. These tests wire mod.CANONICAL / SYNC_SCRIPT / SIDECAR_DATASET
# / SIDECAR_VERSION at a throwaway fake fleet under tmp_path (never the real
# repo — W96) with a minimal fake sync script standing in for
# sync_kbli_dataset.sh's two relevant modes (`--check`, `sync`).


def _wire_fake_fleet(tmp_path, monkeypatch, canonical_bytes: bytes, consumer_bytes: bytes,
                      sidecar_digest: str | None):
    """Point the module's fleet-facing globals at a one-consumer fake fleet.
    Returns (canonical_path, consumer_path, sidecar_version_path)."""
    canonical_path = tmp_path / "canon.json"
    canonical_path.write_bytes(canonical_bytes)
    consumer_path = tmp_path / "consumer.json"
    consumer_path.write_bytes(consumer_bytes)

    sync_script = tmp_path / "fake_sync.sh"
    sync_script.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
CANONICAL="{canonical_path}"
CONSUMER="{consumer_path}"
MODE="${{1:-sync}}"
if [[ "$MODE" == "--check" ]]; then
  if ! cmp -s "$CANONICAL" "$CONSUMER" 2>/dev/null; then
    echo "DRIFT: $CONSUMER differs from canonical $CANONICAL"
    exit 1
  fi
  echo "ok: $CONSUMER == canonical"
else
  if cmp -s "$CANONICAL" "$CONSUMER" 2>/dev/null; then
    echo "unchanged: $CONSUMER"
  else
    cp -f "$CANONICAL" "$CONSUMER"
    echo "synced: $CONSUMER"
  fi
fi
""",
        encoding="utf-8",
    )
    sync_script.chmod(0o755)

    sidecar_version_path = tmp_path / "version.json"
    sidecar_version_path.write_text(
        json.dumps({"datasetSha256": sidecar_digest, "lastModified": "2000-01-01"}), encoding="utf-8"
    )

    monkeypatch.setattr(mod, "CANONICAL", canonical_path)
    monkeypatch.setattr(mod, "SYNC_SCRIPT", sync_script)
    monkeypatch.setattr(mod, "SIDECAR_DATASET", consumer_path)
    monkeypatch.setattr(mod, "SIDECAR_VERSION", sidecar_version_path)
    return canonical_path, consumer_path, sidecar_version_path


def test_noop_repairs_a_stale_consumer_copy_when_applied(tmp_path, monkeypatch):
    """Acceptance: a cured canonical with ONE stale consumer copy — the
    second run must repair it, never just report "nothing to do"."""
    cured = json.dumps({"data": [_rec(status="TERBATAS", cap=0,
                                       kondisi="Kemitraan dengan UMKM/Koperasi")]},
                        ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    stale_consumer = cured.replace(b"UMKM/Koperasi", b"something else entirely")
    digest_of_stale = "sha256:" + hashlib.sha256(stale_consumer).hexdigest()
    canonical_path, consumer_path, sidecar_path = _wire_fake_fleet(
        tmp_path, monkeypatch, cured, stale_consumer, digest_of_stale
    )
    assert mod.main(["--apply", "--dataset", str(canonical_path)]) == 0
    assert consumer_path.read_bytes() == cured, "the stale consumer must be repaired to match canonical"
    sidecar_after = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar_after["datasetSha256"] == "sha256:" + hashlib.sha256(cured).hexdigest()

    # A THIRD run on the now-consistent fleet reports clean, repairs nothing
    # further — proves this isn't re-syncing on every call regardless of need.
    assert mod.main(["--apply", "--dataset", str(canonical_path)]) == 0
    assert consumer_path.read_bytes() == cured


def test_noop_dry_run_reports_a_stale_consumer_without_writing(tmp_path, monkeypatch):
    """Without --apply, a stale fleet must be NAMED, never silently repaired
    (dry-run's own contract) and never silently reported clean."""
    cured = json.dumps({"data": [_rec(status="TERBATAS", cap=0,
                                       kondisi="Kemitraan dengan UMKM/Koperasi")]},
                        ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    stale_consumer = cured.replace(b"UMKM/Koperasi", b"something else entirely")
    canonical_path, consumer_path, sidecar_path = _wire_fake_fleet(
        tmp_path, monkeypatch, cured, stale_consumer,
        "sha256:" + hashlib.sha256(stale_consumer).hexdigest(),
    )
    consumer_before = consumer_path.read_bytes()
    sidecar_before = sidecar_path.read_bytes()
    assert mod.main(["--dataset", str(canonical_path)]) == 2
    assert consumer_path.read_bytes() == consumer_before, "dry-run must never write the consumer copy"
    assert sidecar_path.read_bytes() == sidecar_before, "dry-run must never write the sidecar"
