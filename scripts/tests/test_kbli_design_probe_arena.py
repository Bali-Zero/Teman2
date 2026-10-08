"""anti_flatness.py + arena.py on synthetic sets: an innocent set reads C1..C10 all PASS, a guilty set with one
planted violation per criterion reads all ten FAIL, the controls print their five lines on synthetic baselines,
and the arena seals a 0600 mapping it never reshuffles and links only blind per-letter copies. Needs Playwright's
headless Chromium (skipped where it is absent, e.g. hosted CI)."""
from __future__ import annotations

import json
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
PIL = pytest.importorskip("PIL.Image")
HERE = Path(__file__).resolve().parents[1] / "kbli_design"
if not list(Path.home().glob("Library/Caches/ms-playwright/chromium_headless_shell-*")):
    pytest.skip("no headless chromium", allow_module_level=True)

GLUED = "Built with ChatGPT, GPT5, Gemini3 and Claude3 (gpt-5.6-sol, Sonnet's GPTs): solid console, Solana."
FROZEN = ["55203", "51101", "56101"]
EXTRA = [f"551{i:02d}" for i in range(11)]
ROW = {"scale": ["Mikro"], "risk": "Menengah Rendah", "term": "Otomatis", "permits": [], "authority": ["Bupati"]}
PACK = {"frozen": FROZEN, "inputs": {}, "codes": {
    **{c: {"verdict": "TERBATAS", "cap": "49", "basis": f"Perpres 49/2021 entry {c}", "bali_status": "S",
           "en": {"title": f"Title {c}", "bali_reason": f"Reason {c}", "heads_up": ["HEADS UP — the verdict", "Sentence."],
                  "rows": [ROW]}, "id": {"title": f"Judul {c}"}} for c in FROZEN},
    **{c: {"verdict": "TERBUKA", "cap": "100", "en": {"title": f"Title {c}"}, "id": {"title": f"Judul {c}"}} for c in EXTRA}}}
GRIDS = {"search-results-day": [360, 1000], "registry-table-day": [400, 400, 400], "detail-card-day": [1000],
         "dossier-day": [1000, 360], "sheet-ledger-day": [300, 700, 300], "chat-day": [1200],
         "detail-card-night": [1000], "registry-table-night": [400, 400, 400]}


def span(k: str, v: str) -> str:
    return f'<div style="font-size:12px"><span data-pack="{k}">{v}</span></div>'


def screen(name: str, guilty: bool) -> str:
    night, bad = name.endswith("night"), (lambda c: guilty and c)
    cols = GRIDS["search-results-day"] if bad(name == "registry-table-day") else GRIDS[name]
    m = (0, 0, 0) if bad(name == "chat-day") else (8, 16, 32)
    inner = '<div data-peak style="height:200px;font-size:28px">Peak</div>' * (2 if bad(name == "search-results-day") else 1)
    inner += f'<p style="font-size:12px;margin:{m[0]}px 0">small</p><p style="font-size:20px;margin:{m[1]}px 0">mid</p>'
    inner += f'<p data-editorial style="margin:{m[2]}px 0">quote</p>' * (2 if bad(name == "dossier-day") else 1)
    if name in ("detail-card-day", "dossier-day", "detail-card-night") and not bad(name == "detail-card-day"):
        inner += '<h1 style="font-family:Fraunces,serif;font-size:48px;margin:0">Display</h1>'
    if name.startswith("registry-table"):
        codes = (FROZEN + EXTRA)[: 5 if bad(name == "registry-table-day") else 14]
        inner += "".join(span(f"{c}.verdict", "TERBUKA" if bad(c == "51101") else PACK["codes"][c]["verdict"]) for c in codes)
    if name == "dossier-day":
        inner += "".join(span(k, v) for c in FROZEN for k, v in flat_codes(c))
    if bad(name == "sheet-ledger-day"):
        inner += '<div style="width:600px;height:300px;background:#A44B36"></div>'
    if bad(name == "chat-day"):
        inner += '<span title="Garuda">.</span>'
    if bad(name == "registry-table-night"):
        inner += '<p style="color:#3A4A5A">dim</p>'
    bg, fg = ("#14202B", "#F7F4EE") if night else ("#F7F4EE", "#1D2C3B")
    body = "".join(f'<div style="width:{w}px;min-height:700px">{inner if i == 0 else ""}</div>' for i, w in enumerate(cols))
    return (f'<!doctype html><meta charset="utf-8"><body style="margin:0;background:{bg};color:{fg};font:15px sans-serif">'
            f'<div style="display:flex;gap:20px;justify-content:center">{body}</div>')


def flat_codes(code: str):
    sys.path.insert(0, str(HERE))
    from content_pack import flat
    return [(k, v) for k, v in flat(PACK["codes"]).items() if k.split(".")[0] == code]


def make_kit(tmp: Path) -> Path:
    kit = tmp / "kit"
    for slot, guilty in (("a", False), ("b", True)):
        d = kit / "mockups" / slot / "r1"
        d.mkdir(parents=True)
        for name in GRIDS:
            (d / f"{name}.html").write_text(screen(name, guilty), encoding="utf-8")
        (d / "thesis.md").write_text(f"Thesis of set {slot}.\n")
        (d / "manifest.json").write_text(json.dumps({"seat": {"a": "sol", "b": "gemini"}[slot]}))
        for stage in ("grade", "refute"):
            assert ingest(kit, slot, stage, "```\nVERDICT: PASS\n```\n").endswith("kept=0 rejected=0")
    (kit / "content-pack.json").write_text(json.dumps(PACK), encoding="utf-8")
    return kit


def ingest(kit: Path, slot: str, stage: str, answer: str) -> str:
    """Files a grader/refuter answer exactly as the real pipeline does: raw answer, then seat_io.py ingest."""
    (kit / "raw").mkdir(parents=True, exist_ok=True)
    (kit / "raw" / f"{stage}-{slot}.md").write_text(answer, encoding="utf-8")
    return run("seat_io.py", "ingest", "--kit", str(kit), "--slot", slot, "--stage", stage, "--seat", "opus").strip()


def run(script: str, *args: str) -> str:
    r = subprocess.run([sys.executable, "-I", str(HERE / script), *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_innocent_set_passes_all_ten_and_guilty_set_fails_all_ten(tmp_path: Path) -> None:
    kit = make_kit(tmp_path)
    out = run("anti_flatness.py", "--kit", str(kit), "--stage", "r1", "--slots", "a,b").splitlines()
    assert out[0] == "a " + " ".join(f"C{i}=PASS" for i in range(1, 11)) and out[1] == "a verdict=PASS fails=0"
    assert out[2] == "b " + " ".join(f"C{i}=FAIL" for i in range(1, 11)) and out[3] == "b verdict=FAIL fails=10"
    assert set(json.loads((kit / "probes-r1.json").read_text())["b"]["content"]) == {"mismatch 51101.verdict"}


def test_stacked_or_covered_verdicts_and_a_plain_night_card_fail_and_a_missing_screen_prints_the_full_row(tmp_path: Path) -> None:
    kit = make_kit(tmp_path)
    shutil.copytree(kit / "mockups/a", kit / "mockups/c")
    occluded = kit / "mockups/c/r1/registry-table-night.html"
    occluded.write_text(occluded.read_text() + '<div style="position:fixed;inset:0;background:#14202B"></div>')
    reg = kit / "mockups/a/r1/registry-table-day.html"
    src, cell = reg.read_text(), '<div style="font-size:12px"><span'
    i, j = src.index(cell), src.rindex("</span></div>") + len("</span></div>")
    stacked = src[i:j].replace(cell, '<div style="font-size:12px;position:absolute;left:0;top:0"><span')
    reg.write_text(src[:i] + f'<div style="position:fixed;left:0;top:0;width:0;height:0">{stacked}</div>' + src[j:])
    night = kit / "mockups/a/r1/detail-card-night.html"
    night.write_text(night.read_text().replace("font-family:Fraunces,serif;", ""))
    (kit / "mockups/b/r1/chat-day.html").unlink()
    out = run("anti_flatness.py", "--kit", str(kit), "--slots", "a,b,c").splitlines()
    assert out[0] == "a " + " ".join(f"C{i}={'FAIL' if i in (3, 8) else 'PASS'}" for i in range(1, 11)) and out[1] == "a verdict=FAIL fails=2"
    assert out[2] == "b " + " ".join(f"C{i}=FAIL" for i in range(1, 11)) and out[3] == "b verdict=FAIL fails=10"
    assert out[4] == "c " + " ".join(f"C{i}={'FAIL' if i == 8 else 'PASS'}" for i in range(1, 11)) and out[5] == "c verdict=FAIL fails=1"
    assert json.loads((kit / "probes-r1.json").read_text())["b"]["missing"] == ["chat-day"]


def test_controls_print_the_five_lines_on_synthetic_baselines(tmp_path: Path) -> None:
    kit, app = make_kit(tmp_path), tmp_path / "app"
    base = app / "docs/design/baseline-2026-09-17"
    base.mkdir(parents=True)
    for s in ("search-results", "registry-table", "detail-card", "dossier", "sheet-ledger", "chat"):
        for t in ("day", "night"):
            for lang in ("en", "id"):
                PIL.new("RGB", (720, 450), "#F2EEE2").save(base / f"{s}-{t}-{lang}.png")
    assert run("anti_flatness.py", "--controls", "--kit", str(kit), "--app", str(app)).splitlines() == [
        "calib good contrast=PASS", "calib bad contrast=FAIL", "reference variety=PASS",
        "innocence variety=FAIL content=PASS", "guilt content=FAIL"]


def test_arena_seals_a_stable_mapping_and_links_only_blind_copies(tmp_path: Path) -> None:
    kit = make_kit(tmp_path)
    shutil.copytree(kit / "mockups/a/r1", kit / "mockups/a/repair")
    (kit / "mockups/a/repair/thesis.md").write_text(GLUED + "\n")
    chat = kit / "mockups/b/r1/chat-day.html"
    chat.write_text(chat.read_text().replace("Peak</div>", "Peak</div><p>made with Gemini</p>"))
    out = run("arena.py", "--kit", str(kit), "--preview", str(tmp_path / "preview")).splitlines()
    mapping = json.loads((kit / "mapping.json").read_text())
    letter = {v["slot"]: k for k, v in mapping.items()}
    assert sorted(out[:-1]) == sorted([f"leak-redacted {letter['a']} thesis n=8", f"leak-redacted {letter['b']} chat-day n=1"])
    assert out[-1] == f"arena {kit / 'arena.html'} sets=2"
    assert stat.S_IMODE((kit / "mapping.json").stat().st_mode) == 0o600
    assert sorted(v["slot"] for v in mapping.values()) == ["a", "b"] and set(mapping) <= {"A", "B", "C"}
    page = (kit / "arena.html").read_text(encoding="utf-8")
    assert "mockups/" not in page and ".html" not in page and not re.search(r"sol\b|gemini|claude|gpt", page, re.I)
    assert "solid console, Solana" in page and "(r1)" not in page and "repair" not in page
    assert len(list((tmp_path / "preview/mockups").rglob("*.png"))) == 16
    run("arena.py", "--kit", str(kit))
    assert json.loads((kit / "mapping.json").read_text()) == mapping


def test_a_set_nobody_read_never_reaches_the_arena(tmp_path: Path) -> None:
    kit, preview = make_kit(tmp_path), tmp_path / "preview"
    shutil.copytree(kit / "mockups/a", kit / "mockups/c")
    for stage in ("grade", "refute"):
        ingest(kit, "c", stage, "VERDICT: PASS\n")
    assert run("arena.py", "--kit", str(kit), "--preview", str(preview)).splitlines()[-1].endswith("sets=3")
    letter = {v["slot"]: k for k, v in json.loads((kit / "mapping.json").read_text()).items()}
    assert ingest(kit, "b", "refute", "Error: agy exited 1 (quota)\n") == "refute b by opus kept=0 rejected=1"
    (kit / "r2/c.md").unlink()
    out = run("arena.py", "--kit", str(kit), "--preview", str(preview)).splitlines()
    assert out[:2] == ["excluded b: r2 has no VERDICT: first line", "excluded c: r2 has no VERDICT: first line"]
    assert out[-1] == f"arena {kit / 'arena.html'} sets=1" and "(1 sets)" in (kit / "arena.html").read_text(encoding="utf-8")
    assert sorted(x.name for x in (preview / "mockups").iterdir()) == [letter["a"]]
    assert ingest(kit, "a", "grade", "C3 is flat.\nTest: count the font sizes\n") == "grade a by opus kept=1 rejected=0"
    r = subprocess.run([sys.executable, "-I", str(HERE / "arena.py"), "--kit", str(kit)], capture_output=True, text=True)
    assert r.returncode == 1 and r.stdout.splitlines()[-1].startswith("refused: no set has both")
    assert not (kit / "arena.html").exists()
