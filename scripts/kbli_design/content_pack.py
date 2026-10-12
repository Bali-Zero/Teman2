#!/usr/bin/env python3
"""content_pack.py — the frozen strings every KBLI Navigator mockup seat pastes, never retypes (plan 2026-10-08
§2.2). Each value is a canonical field or ONE lookup the app performs (CodeOverlay dataString/reasonString,
KBLIRegistryView primaryTitle/recordReason, Localization.swift); KBLIVerdict headlines are not re-derived. The
registry slice (frozen codes' divisions) feeds a >=12-row registry with no invented row. --verify prints N/3."""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path
REPO, FROZEN, EXPECT = Path(__file__).resolve().parents[2], ("55203", "51101", "56101"), "c29d6e6aea7a4fdb"
SCREENS, BASE = ("search-results", "registry-table", "detail-card", "dossier", "sheet-ledger", "chat"), "docs/design/baseline-2026-09-17"
APP_FILES = ("Sources/Localization.swift", "Resources/kbli-overlay.json", "Resources/kbli-data-i18n-en.json",
             "Resources/kbli-reason-i18n.json", f"{BASE}/manifest.json", "docs/design/diagnosis-2026-09-17.md")
REQUIRED = ("verdict", "cap", "basis", "en.title", "id.title", "en.bali_reason", "en.heads_up.0", "en.heads_up.1")
ROW_RE = re.compile(r"\.en\.rows\.\d+\.(scale\.0|risk|term)$")
COMBOS = [f"{s}-{t}-{lang}" for s in SCREENS for t in ("day", "night") for lang in ("en", "id")]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
dump = lambda o: json.dumps(o, ensure_ascii=False, sort_keys=True, indent=1)
content_verdict = lambda bad: "content=PASS" if not bad else f"content=FAIL n={len(bad)}"

def build(app: Path, canonical: Path) -> dict:
    recs = {r["kode_kbli_2025"]: r for r in json.loads(canonical.read_bytes())["data"]}
    ov, en_map, rsn = (json.loads((app / f).read_bytes()) for f in APP_FILES[1:4])
    en_blk, _, id_blk = (app / APP_FILES[0]).read_text(encoding="utf-8").partition(".id: [")
    ui = {lang: dict(re.findall(r'^\s*"([\w.]+)": "((?:[^"\\]|\\.)*)",\s*$', b, re.M))
          for lang, b in (("en", en_blk), ("id", id_blk))}
    tr = lambda s, lang: s if lang == "id" else en_map.get(s, s)
    def title(r: dict, lang: str) -> str:
        o, j = ov.get(r["kode_kbli_2025"], {}), r["judul"]
        if lang == "id":
            t = (o.get("id") or {}).get("title")
            return j if t is None else t
        t = ((o["en"] if "en" in o else next(iter(o.values()), None)) or {}).get("title")
        return t if t is not None and t.strip(" \t") != j.strip(" \t") else tr(j, "en")
    def reason(raw: str, lang: str) -> str:
        pair = rsn.get(raw)
        shown = raw if pair is None or pair.get(lang) is None else pair[lang]
        return f"Kutipan catatan (EN): {raw}" if lang == "id" and shown == raw else shown
    codes: dict[str, dict] = {}
    for c in sorted(k for k in recs if k[:2] in {f[:2] for f in FROZEN}):
        r = recs[c]
        codes[c] = {"verdict": r["pma_status"], "cap": str(r["pma_max_asing"]),
                    **{lang: {"title": title(r, lang)} for lang in ("en", "id")}}
        if c not in FROZEN:
            continue
        l4, key = r["l4_bali"], "blocked" if r["l4_bali"].get("blocked") is True else "open"
        codes[c].update(basis=r["pma_official_basis"], bali_status=l4["status"])
        for lang in ("en", "id"):
            codes[c][lang].update(
                bali_reason=reason(l4["reason"], lang),
                heads_up=[ui[lang][f"rich.verdict.{key}"], ui[lang][f"dossier.holding.{key}"]],
                rows=[{"scale": [tr(s, lang) for s in row["skala_usaha"]], "risk": tr(row["kategori_risiko"], lang),
                       "term": tr(row["jangka_waktu"], lang), "permits": [tr(p, lang) for p in row["perizinan"]],
                       "authority": [tr(k, lang) for k in row["kewenangan"]]} for row in r["per_skala"]])
    return {"canonical_sha256": sha(canonical), "frozen": list(FROZEN), "combinations": COMBOS, "codes": codes,
            "inputs": {f: sha(app / f) for f in APP_FILES}, "baselines": {c: sha(app / BASE / f"{c}.png") for c in COMBOS}}

def flat(o, pre: str = "") -> dict[str, str]:
    if isinstance(o, (dict, list)):
        items = o.items() if isinstance(o, dict) else enumerate(o)
        return {k2: v2 for k, v in items for k2, v2 in flat(v, f"{pre}{k}.").items()}
    return {pre[:-1]: o}

def check_content(pack: dict, pairs: list[tuple[str, str]], need: bool = True) -> list[str]:
    """(data-pack key, rendered text) pairs read from a mockup DOM, against the pack byte for byte."""
    ref, seen = flat(pack["codes"]), {k for k, _ in pairs}
    bad = [f"unknown key {k}" for k, _ in pairs if k not in ref] + [f"mismatch {k}" for k, v in pairs if k in ref and ref[k] != v]
    want = [f"{c}.{f}" for c in pack["frozen"] for f in REQUIRED] + [k for k in ref if k[:5] in pack["frozen"] and ROW_RE.search(k)]
    return bad + ([f"missing {k}" for k in want if k not in seen] if need else [])

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path.home() / "BATTAGLIA-20261008/DYNAMIC-WORKFLOW-kbli-nav-design")
    ap.add_argument("--app", type=Path, default=Path.home() / "kbli-navigator-app")
    ap.add_argument("--canonical", type=Path, default=REPO / "data/source_documents/KBLI_2025_FINAL_CLEAN.json")
    ap.add_argument("--expect-sha", default=EXPECT)
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args(argv)
    out = a.out / "content-pack.json"
    need = [a.canonical, *(a.app / f for f in APP_FILES), *(a.app / BASE / f"{c}.png" for c in COMBOS)] + [out] * a.verify
    if gone := [str(p) for p in need if not p.is_file()]:
        return print("\n".join(f"missing: {p}" for p in gone)) or 1
    if not sha(a.canonical).startswith(a.expect_sha):
        return print(f"refused: canonical sha256={sha(a.canonical)[:16]} expected {a.expect_sha}") or 2
    fresh = build(a.app, a.canonical)
    if not a.verify:
        a.out.mkdir(parents=True, exist_ok=True)
        out.write_text(dump(fresh) + "\n", encoding="utf-8")
        (a.out / "pack.sha").write_text(sha(out) + "\n")
        return print(f"pack sha256={sha(out)} codes={len(fresh['codes'])} frozen={len(FROZEN)}") or 0
    stored = json.loads(out.read_bytes())
    same = sum(dump(stored["codes"].get(c)) == dump(fresh["codes"][c]) for c in FROZEN)
    rest_of = lambda p: dump({**p, "codes": {k: v for k, v in p["codes"].items() if k not in FROZEN}})
    rest, sealed = rest_of(stored) == rest_of(fresh), (a.out / "pack.sha").read_text().strip() == sha(out)
    print(f"{same}/{len(FROZEN)} byte-identical sha256={stored['canonical_sha256'][:16]}")
    if not (rest and sealed):
        print(f"refused: inputs+registry identical={rest} pack.sha matches={sealed}")
    return 0 if same == len(FROZEN) and rest and sealed else 1

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
