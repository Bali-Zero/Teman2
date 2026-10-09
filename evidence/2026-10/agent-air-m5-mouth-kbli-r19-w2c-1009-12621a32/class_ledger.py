"""Every class row of the contract (section 5 class rows and section 7.1 state rows), and what this
head does with it: occurrences in the /kbli* fence on origin/main and here, and how it paints.

  python3 class_ledger.py <repo root> <base ref> <out.tsv> [<state_rows_probe.json>]
"""
import json
import pathlib
import re
import subprocess
import sys

R, BASE, OUT = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
sys.path.insert(0, str(R / "scripts/mouth"))
import r19_wrapper_token_census as C  # noqa: E402

TEXT = C.CONTRACT.read_text()
CON = C.parse_contract(TEXT)
ST = C.parse_states(TEXT, CON)
FENCE = ["apps/mouth/src/components/kbli", "apps/mouth/src/app/kbli", "apps/mouth/src/app/kbli-explorer"]
CSS = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", re.sub(r"\s+", " ", (R / "apps/mouth/src/styles/kbli-r19-wrapper.css").read_text())))


def files_at(ref: str | None) -> dict[str, str]:
    if ref is None:
        return {str(p.relative_to(R)): p.read_text() for d in FENCE for p in (R / d).rglob("*.tsx")
                if ".test." not in p.name}
    names = subprocess.run(["git", "-C", str(R), "ls-tree", "-r", "--name-only", ref, "--", *FENCE],
                           capture_output=True, text=True, check=True).stdout.split()
    return {n: subprocess.run(["git", "-C", str(R), "show", f"{ref}:{n}"], capture_output=True, text=True,
                              check=True).stdout for n in names if n.endswith(".tsx") and ".test." not in n}


def count(token: str, srcs: dict[str, str]) -> int:
    pat = re.compile(r"(?<![\w:/\[\]()-])" + re.escape(token) + r"(?![\w/\[\]()-])")
    return sum(len(pat.findall(s)) for s in srcs.values())


def css_escape(token: str) -> str:
    return re.sub(r"([^\w-])", r"\\\1", token)


main, head = files_at(BASE), files_at(None)
NO_RULE = set(json.loads(pathlib.Path(sys.argv[4]).read_text())["not_generated_at_head"]) if len(sys.argv) > 4 else set()
rows = {t: CON[("class", t)]["value"] for k, t in CON if k == "class"}
for t, r in ST.items():
    rows.setdefault(t, r["value"])
out = ["contract_class\ttable\tcontract_value\tcategory\twrapper_override\toccurrences_main\toccurrences_head"]
tally: dict[str, list[int]] = {}
for t in sorted(rows):
    m, h = count(t, main), count(t, head)
    table = "7.1" if t in ST and ("class", t) not in CON else "5+7.1" if t in ST else "5"
    painted = rows[t] != C.NOT_PAINTED
    lead = r"(?:^|[\s,}])\." + re.escape(css_escape(t))
    override = bool(re.search(lead + re.escape(":is(.kbli-r19, .kbli-r19 *)"), CSS)) or (
        "@scope (.kbli-r19)" in CSS and re.search(lead + re.escape(" *::selection"), CSS) is not None)
    if h and t in NO_RULE:
        cat = "kept-by-name-no-rule-generated"
    elif h and override:
        cat = "kept-by-name-scoped-override"
    elif h:
        cat = "kept-by-name-resolves-through-wrapper-token" if painted else "kept-by-name-not-painted"
    elif m:
        cat = "rewritten-to-contract-class" if painted else "removed-contract-not-painted"
    else:
        cat = "not-in-fence-source"
    tally.setdefault(cat, [0, 0, 0])
    tally[cat][0] += 1
    tally[cat][1] += m
    tally[cat][2] += h
    out.append(f"{t}\t{table}\t{rows[t]}\t{cat}\t{'yes' if override else 'no'}\t{m}\t{h}")
OUT.write_text("\n".join(out) + "\n")
print(f"contract class rows: {len(rows)} (section 5 class {sum(1 for k, _ in CON if k == 'class')}, "
      f"state table {len(ST)}, both {sum(1 for t in ST if ('class', t) in CON)})")
for cat, (n, m, h) in sorted(tally.items()):
    print(f"  {cat}: {n} rows, {m} occurrences on {BASE}, {h} here")
