#!/usr/bin/env python3
"""Every background class in the /kbli* sources, found by rg, resolved by Chrome, and named or not.

  python3 -I surface_scan.py BASE_URL LABEL=SRC_ROOT [LABEL=SRC_ROOT ...] > surface-scan.tsv

SRC_ROOT is an apps/mouth/src directory (main=origin/main's worktree, 8161=#8161's head
extracted by `git archive`). The scope is components/kbli, app/kbli and app/kbli-explorer plus the files they
import that paint inside the wrapper (IMPORTED), tests excluded.
Each token is resolved on a live dev server by injecting it on a bare element in <body>,
outside any wrapper, so the colour is the one the source asks for. A token is a dark slab
when ink #1D2C3B on its colour is below 4.5:1 and its alpha is at least 0.5, or when it is a
gradient stop of that colour. Named means it has a row in section 5, 7 or 8 of the contract.
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/mouth"))
import r19_wrapper_token_census as census  # noqa: E402

FENCE = ["components/kbli", "app/kbli", "app/kbli-explorer"]
IMPORTED = ["components/ui/button.tsx", "components/ui/skeleton.tsx", "components/lead/WhatsAppLeadButton.tsx",
            "components/funnel/funnel-nav.ts", "app/v2/_components/MobileNav.tsx", "lib/kbli-*.ts"]
TOKEN = r"""(?:^|[\s"'`{(])((?:[a-z-]+:)*(?:bg|from|via|to)-(?:\[[^\]]+\]|[a-z]+(?:-[a-z0-9]+)*)(?:/(?:\[[^\]]+\]|\d+))?)"""
LAYOUT = census.NON_COLOUR_BG

RESOLVE_JS = r"""
(tokens) => {
  const ctx = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  const parse = (c) => {
    if (!c || c === "none") return null;
    const am = c.match(/\/\s*([\d.]+)(%?)\s*\)$/);
    let a = am ? parseFloat(am[1]) / (am[2] ? 100 : 1) : 1;
    const opaque = c.replace(/\s*\/\s*[\d.]+%?\s*\)$/, ")");
    let m, p;
    if ((m = opaque.match(/^rgba?\(([^)]+)\)$/))) {
      const q = m[1].split(/[\s,]+/).filter(Boolean).map(Number);
      p = q.slice(0, 3); if (q.length > 3) a = q[3];
    } else if ((m = opaque.match(/^color\(srgb ([^)]+)\)$/))) {
      p = m[1].split(/\s+/).filter(Boolean).slice(0, 3).map(Number).map((x) => x * 255);
    } else {
      ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = "#000"; ctx.fillStyle = opaque; ctx.fillRect(0, 0, 1, 1);
      const d = ctx.getImageData(0, 0, 1, 1).data;
      p = [d[0], d[1], d[2]];
    }
    if (a === 0) return null;
    const hex = "#" + p.map((x) => Math.max(0, Math.min(255, Math.round(x))).toString(16).padStart(2, "0")).join("").toUpperCase();
    return { hex, a: Math.round(a * 1000) / 1000 };
  };
  const out = {};
  for (const t of tokens) {
    const el = document.createElement("div");
    el.className = t;
    document.body.append(el);
    const cs = getComputedStyle(el);
    const stop = /^(from|via|to)-/.test(t) ? cs.getPropertyValue("--tw-gradient-" + t.split("-")[0]).trim() : "";
    out[t] = stop ? parse(stop) : parse(cs.backgroundColor);
    el.remove();
  }
  return out;
}
"""


def tokens(src_roots: list[str]) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for spec in src_roots:
        label, root = spec.split("=", 1)
        paths = [str(f.relative_to(root)) for g in FENCE + IMPORTED for f in sorted(Path(root).glob(g))]
        out = subprocess.run(["rg", "-o", "-n", "--no-heading", "-g", "!*.test.*", "-g", "!__tests__",
                              TOKEN, "-r", "$1", *paths], cwd=root, capture_output=True, text=True, check=True)
        for line in out.stdout.splitlines():
            path, _, tok = line.split(":", 2)
            found.setdefault(tok.strip(), set()).add(f"{label}:{path}")
    return found


def main(argv: list[str]) -> int:
    from playwright.sync_api import sync_playwright
    base, roots = argv[0].rstrip("/"), argv[1:]
    text = census.CONTRACT.read_text()
    contract = census.load_contract(text)
    states = census.parse_states(text, contract)
    surfaces = census.parse_surfaces(text, contract, states)
    found = tokens(roots)
    rest = sorted(t for t in found if census.split_variant(t)[0] == "" and not t.startswith(LAYOUT))
    variants = sorted(t for t in found if census.split_variant(t)[0])
    m = census._load_measure()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=m.CHROME)
        page = browser.new_page()
        page.goto(base + "/kbli", wait_until="load", timeout=180000)
        resolved = page.evaluate(RESOLVE_JS, rest)
        browser.close()
    ink = census.DIRECTION_A["ink"]
    slabs_unnamed = grounds_unnamed = 0
    print("token\ton:files\tresolved\talpha\tink_on_it\tdark_slab\tnamed_in")
    for t in rest:
        r = resolved.get(t)
        named = "8.1" if t in surfaces else "5" if ("class", t) in contract else "none"
        if r is None:
            print(f"{t}\t{','.join(sorted(found[t]))}\tpaints nothing\t-\t-\tno\t{named}")
            continue
        ratio = census.contrast(ink, r["hex"])
        slab = ratio < 4.5 and (r["a"] >= 0.5 or t.startswith(("from-", "via-", "to-")))
        slabs_unnamed += slab and named == "none"
        grounds_unnamed += named == "none"
        print(f"{t}\t{','.join(sorted(found[t]))}\t{r['hex']}\t{r['a']}\t{ratio:.2f}\t{'yes' if slab else 'no'}\t{named}")
    unnamed_variants = [t for t in variants if t not in states]
    print(f"# rest background tokens: {len(rest)}; state-variant background tokens: {len(variants)}, "
          f"without a section 7 row: {len(unnamed_variants)} {' '.join(unnamed_variants)}")
    print(f"# unnamed-grounds: {grounds_unnamed}")
    print(f"# unnamed-dark-slabs: {slabs_unnamed}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
