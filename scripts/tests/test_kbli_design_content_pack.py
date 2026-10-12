"""content_pack.py: innocence (untouched pack verifies 3/3, its own strings read content=PASS) and
guilt (one verdict word changed reads content=FAIL; a tampered pack verifies 2/3), on a synthetic
app + canonical so the test needs neither ~/kbli-navigator-app nor the 39 MB dataset."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "kbli_design" / "content_pack.py"
spec = importlib.util.spec_from_file_location("content_pack", SCRIPT)
cp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cp)

SWIFT = """    static let strings = [
        .en: [
            "rich.verdict.open": "YOU CAN DO THIS — the verdict",
            "rich.verdict.blocked": "HEADS UP — the verdict",
            "dossier.holding.blocked": "A PT PMA cannot register this code in Bali.",
            "dossier.holding.open": "Open to foreign ownership.",
        ],
        .id: [
            "rich.verdict.open": "BISA — putusan",
            "rich.verdict.blocked": "PERHATIAN — putusan",
            "dossier.holding.blocked": "PT PMA tidak dapat mendaftarkan kode ini di Bali.",
            "dossier.holding.open": "Terbuka untuk kepemilikan asing.",
        ],
    ]
"""


def _rec(code: str, judul: str, status: str, cap: int, blocked: bool, reason: str) -> dict:
    row = {"skala_usaha": ["Mikro"], "kategori_risiko": "Menengah Rendah", "jangka_waktu": "Otomatis",
           "perizinan": [], "kewenangan": ["Bupati/Walikota"]}
    return {"kode_kbli_2025": code, "judul": judul, "pma_status": status, "pma_max_asing": cap,
            "pma_official_basis": f"basis {code}", "per_skala": [row],
            "l4_bali": {"status": "S", "reason": reason, "blocked": blocked}}


def _world(tmp: Path) -> tuple[Path, Path, str]:
    app = tmp / "app"
    (app / "Sources").mkdir(parents=True)
    (app / "Sources/Localization.swift").write_text(SWIFT, encoding="utf-8")
    (app / "Resources").mkdir()
    (app / "Resources/kbli-overlay.json").write_text(json.dumps(
        {"56101": {"en": {"title": "Aktivitas Makan"}}, "51101": {"id": {"title": "Angkutan ID"}, "en": {}}}))
    (app / "Resources/kbli-data-i18n-en.json").write_text(json.dumps({"Aktivitas Makan": "Food Service", "Mikro": "Micro"}))
    (app / "Resources/kbli-reason-i18n.json").write_text(
        json.dumps({"r-open": {"en": "open (en)", "id": "terbuka (id)"}, "r-empty": {"en": "", "id": ""}}))
    base = app / cp.BASE
    base.mkdir(parents=True)
    (base / "manifest.json").write_text("{}")
    for c in cp.COMBOS:
        (base / f"{c}.png").write_bytes(c.encode())
    (app / "docs/design/diagnosis-2026-09-17.md").write_text("# diagnosis\n")
    canonical = tmp / "canonical.json"
    canonical.write_text(json.dumps({"metadata": {}, "data": [
        _rec("55203", "Aktivitas Vila", "TERBATAS", 0, True, "r-blocked-untranslated"),
        _rec("51101", "Angkutan Udara", "TERBATAS", 49, False, "r-open"),
        _rec("56101", "Aktivitas Makan", "TERBUKA", 100, False, "r-empty"),
        _rec("55101", "Hotel Bintang", "TERBUKA", 100, False, "r-open"),
        _rec("10101", "Out of slice", "TERBUKA", 100, False, "r-open")]}))
    return app, canonical, hashlib.sha256(canonical.read_bytes()).hexdigest()[:16]


def _run(app: Path, canonical: Path, prefix: str, out: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", str(SCRIPT), "--app", str(app), "--canonical", str(canonical),
                           "--expect-sha", prefix, "--out", str(out), *extra], capture_output=True, text=True)


def test_innocence_untouched_pack_verifies_and_reads_content_pass(tmp_path: Path) -> None:
    app, canonical, prefix = _world(tmp_path)
    assert _run(app, canonical, prefix, tmp_path / "kit").returncode == 0
    v = _run(app, canonical, prefix, tmp_path / "kit", "--verify")
    assert (v.returncode, v.stdout) == (0, f"3/3 byte-identical sha256={prefix}\n")
    pack = json.loads((tmp_path / "kit/content-pack.json").read_text(encoding="utf-8"))
    assert sorted(pack["codes"]) == ["51101", "55101", "55203", "56101"]
    assert cp.content_verdict(cp.check_content(pack, list(cp.flat(pack["codes"]).items()))) == "content=PASS"


def test_guilt_one_verdict_word_reads_content_fail_and_tamper_verifies_2_of_3(tmp_path: Path) -> None:
    app, canonical, prefix = _world(tmp_path)
    _run(app, canonical, prefix, tmp_path / "kit")
    pack_file = tmp_path / "kit/content-pack.json"
    pack = json.loads(pack_file.read_text(encoding="utf-8"))
    pairs = [(k, "TERBUKA" if k == "51101.verdict" else v) for k, v in cp.flat(pack["codes"]).items()]
    assert cp.content_verdict(cp.check_content(pack, pairs)) == "content=FAIL n=1"
    dropped = [(k, v) for k, v in cp.flat(pack["codes"]).items() if k not in ("55203.basis", "51101.en.rows.0.risk")]
    assert sorted(cp.check_content(pack, dropped)) == ["missing 51101.en.rows.0.risk", "missing 55203.basis"]
    pack["codes"]["55203"]["verdict"] = "TERBUKA"
    pack_file.write_text(json.dumps(pack), encoding="utf-8")
    v = _run(app, canonical, prefix, tmp_path / "kit", "--verify")
    assert v.returncode == 1 and v.stdout.startswith(f"2/3 byte-identical sha256={prefix}\n")


def test_lookups_follow_the_app_and_missing_inputs_are_named(tmp_path: Path) -> None:
    app, canonical, prefix = _world(tmp_path)
    _run(app, canonical, prefix, tmp_path / "kit")
    codes = json.loads((tmp_path / "kit/content-pack.json").read_text(encoding="utf-8"))["codes"]
    assert codes["56101"]["en"]["title"] == "Food Service"
    assert codes["55203"]["id"]["bali_reason"] == "Kutipan catatan (EN): r-blocked-untranslated"
    assert codes["51101"]["id"]["bali_reason"] == "terbuka (id)"
    assert (codes["56101"]["en"]["bali_reason"], codes["56101"]["id"]["bali_reason"]) == ("", "")
    assert (codes["51101"]["en"]["title"], codes["51101"]["id"]["title"]) == ("Angkutan Udara", "Angkutan ID")
    assert json.loads((tmp_path / "kit/content-pack.json").read_text(encoding="utf-8"))["frozen"] == ["55203", "51101", "56101"]
    assert codes["55203"]["en"]["heads_up"] == ["HEADS UP — the verdict", "A PT PMA cannot register this code in Bali."]
    assert codes["56101"]["id"]["heads_up"][1] == "Terbuka untuk kepemilikan asing."
    assert codes["51101"]["en"]["rows"][0]["scale"] == ["Micro"] and codes["51101"]["id"]["rows"][0]["scale"] == ["Mikro"]
    assert _run(app, canonical, "deadbeef", tmp_path / "k2").returncode == 2
    (app / cp.BASE / "chat-night-id.png").unlink()
    r = _run(app, canonical, prefix, tmp_path / "k3")
    assert r.returncode == 1 and "missing: " in r.stdout and r.stdout.strip().endswith("chat-night-id.png")
