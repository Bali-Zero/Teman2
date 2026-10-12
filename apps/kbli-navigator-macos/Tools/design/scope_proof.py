#!/usr/bin/env python3
"""scope_proof.py <dir> - the six-or-more scope selector, proved by selection on the EXPANDED live sheet (IMM-5b).

<dir> holds en.jsonl and id.jsonl, each from
  encensus <out> --lang L --codes 71109 --views registry-sheet-open,registry-sheet-open-imm,registry-sheet-scopes
For each scope, every word of its opened flat row is drawn in some (scope, scale) state of the immersive sheet, and every
word of the flat default is drawn in some state at all. Words split on / and -, so a line wrap cannot tell two spellings apart.
Exit 1 on a word that is in no state; a guilt case (a state dropped) runs first and must fail.
"""
import json, re, sys
from collections import Counter

CODE = "71109"
W = lambda t: Counter(re.findall(r"[^\s/-]+", t))

def lost(rows):
    flat = W(rows[(CODE, "registry-sheet-open")])
    ids = sorted({int(k[0].split("#flat")[1]) for k in rows if "#flat" in k[0]})
    seen, bad = set(W(rows[(CODE, "registry-sheet-open-imm")])), []
    for i in ids:
        states = [W(t) for k, t in ((k[0], t) for k, t in rows.items()) if k.startswith("%s#imm%d#" % (CODE, i))]
        union = Counter()
        for s in states:
            union |= s
            seen |= set(s)
        missing = sorted(w for w in (W(rows[("%s#flat%d" % (CODE, i), "registry-sheet-scopes")]) - flat) if w not in union)
        if missing: bad.append((i, missing))
    return ids, bad, sorted(set(flat) - seen)

def main(d):
    rc = 0
    for lang in ("en", "id"):
        rows = {(r["code"], r["view"]): r["text"] for r in map(json.loads, open("%s/%s.jsonl" % (d, lang)))}
        ids, bad, unseen = lost(rows)
        dropped = {k: v for k, v in rows.items() if not k[0].startswith("%s#imm0#" % CODE)}   # guilt: scope 0 never drawn
        g_ids, g_bad, _ = lost(dropped)
        assert g_bad, "guilt case: a scope with no immersive state must fail"
        print("%s %s: %d scopes x 4 scales; scopes with a word in no state: %d; flat-default words in no state: %d (guilt case rejected)"
              % (lang, CODE, len(ids), len(bad), len(unseen)))
        rc |= bool(bad or unseen)
    return rc

sys.exit(main(sys.argv[1]))
