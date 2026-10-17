"""Render the signed Visa Oracle rulepack as a family -> product -> rule map (read-only).

Usage: python3 scripts/visa_oracle_family_map.py <rulepack.source.json>
       python3 scripts/visa_oracle_family_map.py <pack> --coverage <seed_visa_types.py> <official_prices.json>
"""

import collections
import json
import sys


def fmt(w):
    op = w["op"]
    if op in ("all", "any"):
        return (" AND " if op == "all" else " OR ").join(
            fmt(x) for x in w.get("args") or w.get("conditions") or w.get("items") or []
        )
    if op == "between":
        return f"{w.get('fact')} in [{w.get('lower')},{w.get('upper')}]"
    if op == "not":
        return "NOT(" + fmt(w.get("arg") or w.get("condition")) + ")"
    f = (
        w.get("fact", "?")
        .replace("intent.", "")
        .replace("investment.", "inv.")
        .replace("secondhome.", "sh.")
        .replace("family.", "fam.")
    )
    v = w.get("value", w.get("values"))
    sym = {
        "eq": "=",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
        "gt": ">",
        "intersects": "∩",
        "in": "∈",
        "ne": "!=",
    }.get(op, op)
    if isinstance(v, list):
        v = (
            "{" + ",".join(map(str, v)) + "}"
            if len(v) <= 12
            else "{" + ",".join(map(str, v[:6])) + f",...+{len(v) - 6}" + "}"
        )
    return f"{f}{sym}{v}"


def coverage(pack_path, seed_path, price_path):
    """Index coverage: every visa code in the seed, flagged SOLD (price list) and IN_ORACLE (pack)."""
    import re as _re

    with open(pack_path) as fh:
        pack_codes = {p["product_code"] for p in json.load(fh)["products"]}
    with open(seed_path) as fh:
        seed = fh.read()
    codes = _re.findall(r'"code":\s*"([^"]+)"', seed)
    names = _re.findall(r'"name":\s*"([^"]+)"', seed)
    with open(price_path) as fh:
        price_txt = json.dumps(json.load(fh)["services"])

    def sold(c):
        if _re.search(r"\b" + _re.escape(c) + r"\b", price_txt):
            return True
        m = _re.match(r"^([A-E]\d+)([A-C])$", c)
        return bool(
            m
            and _re.search(
                r"\b" + m.group(1) + r"[A-C]?[,&]?[A-C,&]*" + m.group(2), price_txt
            )
        )

    rows = [(c, n, sold(c), c in pack_codes) for c, n in zip(codes, names)]
    print("| Code | Name (seed) | Sold | In Oracle |\n|---|---|---|---|")
    for c, n, s, o in rows:
        print(f"| {c} | {n[:55]} | {'yes' if s else ''} | {'yes' if o else ''} |")
    gap = [c for c, _, s, o in rows if s and not o]
    print(f"\nSold but NOT in Oracle ({len(gap)}): {', '.join(gap)}")


def main() -> None:
    with open(sys.argv[1]) as _fh:
        d = json.load(_fh)
    pv = {p["product_version_id"]: p for p in d["products"]}

    FAM = [
        ("A", "Visa-free", ["A1"]),
        ("B", "VOA", ["B1"]),
        ("C", "Single-entry visit", ["C1", "C2", "C6"]),
        ("D", "Multiple-entry visit", ["D1", "D2", "D12"]),
        ("E23", "Work", ["E23", "E23U", "E23V"]),
        ("E28", "Investor", ["E28A", "E28B", "E28C", "E28D", "E28F"]),
        ("E30", "Study", ["E30", "E30A", "E30B", "E30E", "E30F"]),
        (
            "E31",
            "Family",
            ["E31A", "E31B", "E31C", "E31D", "E31E", "E31F", "E31G", "E31H", "E31J"],
        ),
        ("E33", "Second Home", ["E33", "E33A", "E33B", "E33C", "E33E", "E33F", "E33G"]),
        ("X", "Status bridging", ["BRIDGING"]),
    ]
    if "--coverage" in sys.argv:
        FAM = []
    by = collections.defaultdict(list)
    glob = []
    for r in d["rules"]:
        ids = r.get("product_version_ids") or []
        if not ids:
            glob.append(r)
        for x in ids:
            by[pv[x]["product_code"]].append(r)
    code2p = {p["product_code"]: p for p in d["products"]}
    out = []
    for k, name, codes in FAM:
        facts = set()
        for c in codes:
            for r in by[c]:
                facts.update(f for f in r["required_facts"] if f != "intent.purposes")
        out.append(
            f"\n### {k} — {name} ({len(codes)} products, {len(facts)} gate facts)\n"
        )
        for c in codes:
            p = code2p[c]
            sp = p.get("stay_policy") or {}
            out.append(
                f"- **{c}** {p['names'].get('en', '')} · purposes {','.join(p['covered_purposes'])} · stay {sp.get('maximum_days', '?')}d"
            )
            for r in sorted(by[c], key=lambda r: r["stage"]):
                tag = {
                    "ELIGIBILITY": "SUPPORT",
                    "HARD_FILTER": "EXCLUDE",
                    "HUMAN_REVIEW": "REVIEW",
                }[r["stage"]]
                out.append(
                    f"  - {tag} `{fmt(r['when'])}` → {r['effect'].get('reason_code', '')}"
                )
    out.append("\n### GLOBAL hard filters\n")
    for r in glob:
        out.append(f"- `{fmt(r['when'])}` → {r['effect'].get('reason_code', '')}")
    if "--coverage" not in sys.argv:
        print("\n".join(out))

    if len(sys.argv) > 2 and sys.argv[2] == "--coverage":
        coverage(sys.argv[1], sys.argv[3], sys.argv[4])


if __name__ == "__main__":
    main()
