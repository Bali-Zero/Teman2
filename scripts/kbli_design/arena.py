#!/usr/bin/env python3
"""arena.py — the blind arena of the KBLI Navigator design contest (plan 2026-10-08 §2.5): every set that
landed becomes a letter, its screens are rendered at 1440x900 into kit/arena/<letter>/ (a kit path names the
slot, so the page links only those PNGs), and kit/mapping.json (letter -> slot, seat, stage) is written once at
mode 0600 and never reshuffled. Model and vendor names are redacted from the visible text of every screen and
from the thesis before anything is shown ("leak-redacted <letter> <file> n=<k>"). The page shows per letter the
thesis, the eight screens, the probe row and the grader/refuter counts; the vote is Zero's. --preview DIR also
drops the renders where the gallery's build_preview.py collects them (DIR/mockups/<letter>/<screen>.png).
Prints "arena <path> sets=<n>"."""
from __future__ import annotations
import argparse, html, json, os, re, secrets, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / ".claude/skills/design/strumenti"))
import measure  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

SCREENS = ("search-results-day", "registry-table-day", "detail-card-day", "dossier-day", "sheet-ledger-day",
           "chat-day", "detail-card-night", "registry-table-night")
LEAK = re.compile(r"\b(gemini|google|gpt|openai|codex|sol|claude|anthropic|sonnet|opus)\b", re.I)
REDACT_JS = r"""(src) => { const R = new RegExp(src, "gi"), w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n = 0;
  for (let t = w.nextNode(); t; t = w.nextNode()) if (!/^(SCRIPT|STYLE|NOSCRIPT)$/.test(t.parentNode.nodeName))
    t.nodeValue = t.nodeValue.replace(R, () => (n++, "\u2587\u2587\u2587"));
  return n; }"""
paragraphs = lambda p: [x for x in re.split(r"\n\s*\n", p.read_text(encoding="utf-8")) if x.strip() and not x.startswith("VERDICT:")] if p.is_file() else []


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kit", type=Path, required=True)
    ap.add_argument("--preview", type=Path)
    a = ap.parse_args(argv)
    kit = a.kit.resolve()
    landed = {}
    for slot in ("a", "b", "c"):
        stage = "repair" if (kit / "mockups" / slot / "repair" / "manifest.json").is_file() else "r1"
        man = kit / "mockups" / slot / stage / "manifest.json"
        if man.is_file():
            landed[slot] = {"slot": slot, "stage": stage, "seat": json.loads(man.read_text())["seat"]}
    mpath = kit / "mapping.json"
    mapping = json.loads(mpath.read_text()) if mpath.is_file() else {}
    free = [x for x in "ABC" if x not in mapping]
    secrets.SystemRandom().shuffle(free)
    for slot, info in landed.items():
        if all(v["slot"] != slot for v in mapping.values()):
            mapping[free.pop()] = info
    mpath.write_text(json.dumps(mapping, indent=1, sort_keys=True) + "\n")
    os.chmod(mpath, 0o600)
    cards = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=measure.CHROME)
        for letter in sorted(mapping):
            slot, stage = mapping[letter]["slot"], mapping[letter]["stage"]
            src, dst = kit / "mockups" / slot / stage, kit / "arena" / letter
            dst.mkdir(parents=True, exist_ok=True)
            for s in SCREENS:
                page = b.new_page(viewport={"width": 1440, "height": 900})
                page.goto((src / f"{s}.html").as_uri(), wait_until="load")
                page.wait_for_timeout(600)
                if n := page.evaluate(REDACT_JS, LEAK.pattern):
                    print(f"leak-redacted {letter} {s} n={n}")
                page.screenshot(path=str(dst / f"{s}.png"))
                page.close()
                if a.preview:
                    (a.preview / "mockups" / letter).mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(dst / f"{s}.png", a.preview / "mockups" / letter / f"{s}.png")
            thesis, n = LEAK.subn("\u2587\u2587\u2587", (src / "thesis.md").read_text(encoding="utf-8"))
            if n:
                print(f"leak-redacted {letter} thesis n={n}")
            probe = json.loads((kit / f"probes-{stage}.json").read_text()).get(slot, {}).get("criteria", {}) \
                if (kit / f"probes-{stage}.json").is_file() else {}
            row = " ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in probe.items()) or "no probe row"
            counts = (f"grader objections kept {len(paragraphs(kit / 'verify' / f'{slot}.md'))} · fact refutation kept "
                      f"{len(paragraphs(kit / 'r2' / f'{slot}.md'))}, rejected {len(paragraphs(kit / 'r2' / f'{slot}.rejected.md'))}")
            shots = "".join(f'<figure><a href="arena/{letter}/{s}.png" target="_blank"><img loading="lazy" '
                            f'src="arena/{letter}/{s}.png"></a><figcaption>{s}</figcaption></figure>' for s in SCREENS)
            cards.append(f"<section><h2>Set {letter}</h2><pre>{html.escape(thesis)}</pre>"
                         f"<p class=m>{html.escape(row)}<br>{html.escape(counts)} ({stage})</p><div class=g>{shots}</div></section>")
        b.close()
    witness = kit / "verify" / "nlm.md"
    (kit / "arena.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>KBLI Navigator — blind arena</title><style>body{font:15px/1.6 '
        "system-ui;margin:28px;background:#F7F4EE;color:#1D2C3B}pre{white-space:pre-wrap;background:#FFFCF7;padding:12px;"
        "border:1px solid #DAD8D1}.g{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}img{width:100%;"
        "border:1px solid #A8ACA9}figure{margin:0}figcaption,.m{font-size:13px;color:#58626B}</style>"
        f"<h1>KBLI Navigator — blind arena ({len(mapping)} sets)</h1><p>Letters are sealed in mapping.json until the vote. "
        f"A hybrid vote is allowed (e.g. A's registry, C's dossier).</p>{''.join(cards)}"
        + (f"<h2>NotebookLM witness (sources only)</h2><pre>{html.escape(witness.read_text(encoding='utf-8'))}</pre>"
           if witness.is_file() else ""), encoding="utf-8")
    print(f"arena {kit / 'arena.html'} sets={len(mapping)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
