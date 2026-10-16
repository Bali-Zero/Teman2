#!/usr/bin/env python3
"""title_whole.py <titlewhole.jsonl>... : a title is never cut (the #8492 gate, binding 8).

Reads what Tests/titlewhole writes: for each (code, view, width), the text the sheet DRAWS and the record's title. The title, whitespace
collapsed and ligatures unfolded (NFKC), must stand whole in the drawn text. Whitespace is read out of both sides before the comparison: a title that
wraps at a hyphen or a slash ("Oil-" / "Bearing") is read back by PDFKit with a line break inside the word. A title clipped by `.lineLimit`, by a frame's height or
by an ellipsis loses words, and FAILs here at the first code that does; an empty file FAILs (nothing was read).

PDFKit reads text blocks in its own order, not the drawn one: a title that wraps ("Freight Forwarding Services" / "(JPT)") can come back with
its last line ahead of the lines before it (52311 at 783 pt). So when the title is not one run, it is judged as consecutive word chunks that
each stand as a WHOLE drawn line, every line used once, in any order: a cut title still loses its tail (a tail found only inside another line,
such as the official title's "(JPT)", does not count), and no code is named.

`--self-test` judges synthetic rows: an innocent set passes; a title cut by an ellipsis, one short of its last word and one drawn
nowhere each FAIL.
"""
import json, sys, unicodedata

def norm(s):
    return " ".join(unicodedata.normalize("NFKC", s).split())

def squeeze(s):
    return "".join(s.split())

def whole_lines(words, lines, i=0, used=frozenset()):
    if i == len(words): return True
    for j in range(i + 1, len(words) + 1):
        chunk = squeeze(" ".join(words[i:j]))
        for k, l in enumerate(lines):
            if k not in used and l == chunk and whole_lines(words, lines, j, used | {k}): return True
    return False

def judge(row):
    t, text = norm(row["title"]), norm(row["text"])
    if not t: return False, "the record has no title"
    if squeeze(t) in squeeze(text): return True, "whole"
    if whole_lines(t.split(), [squeeze(l) for l in unicodedata.normalize("NFKC", row["text"]).splitlines() if l.strip()]):
        return True, "whole, read back out of order"
    words = t.split(); drawn = 0
    for i in range(len(words), 0, -1):
        if squeeze(" ".join(words[:i])) in squeeze(text): drawn = i; break
    return False, "%d of %d words drawn, then %r is missing" % (drawn, len(words), " ".join(words[drawn:drawn + 4]))

def self_test():
    title = "Aktivitas Perawatan untuk Orang yang Hidup dengan Diagnosis Mental"
    rows = [("innocent", title, "KBLI 87202\n" + title.replace(" yang ", " yang\n") + "\nBALI", True),
            ("ligature", "Office of the fit", "Office of the ﬁt", True),
            ("wrapped at a hyphen", "Farming of Edible Oil-Bearing Seeds", "KBLI\nFarming of Edible Oil-\nBearing Seeds\nBALI", True),
            ("cut inside a hyphenated word", "Farming of Edible Oil-Bearing Seeds", "KBLI\nFarming of Edible Oil-\nBALI", False),
            ("wrapped, read back out of order", "Freight Forwarding Services (JPT)", "KBLI\n(JPT)\nOfficial title\nJasa Pengurusan Transportasi (JPT)\nFreight Forwarding Services\nNATIONAL", True),
            ("cut, tail only in the official title", "Freight Forwarding Services (JPT)", "KBLI\nOfficial title\nJasa Pengurusan Transportasi (JPT)\nFreight Forwarding Services\nNATIONAL", False),
            ("cut by an ellipsis", title, "KBLI\nAktivitas Perawatan untuk Orang yang Hidup…\nBALI", False),
            ("short of its last word", title, "Aktivitas Perawatan untuk Orang yang Hidup dengan Diagnosis", False),
            ("drawn nowhere", title, "BALI VERDICT", False)]
    wrong = 0
    for name, t, text, want in rows:
        ok, why = judge({"title": t, "text": text})
        if ok != want: wrong += 1; print("SELF-TEST WRONG: %s: %s" % (name, why))
    if main_files([]) != 1: wrong += 1; print("SELF-TEST WRONG: an empty set passed")
    print("title_whole self-test: %d of %d cases judged right" % (len(rows) + 1 - wrong, len(rows) + 1))
    return wrong

def main_files(paths):
    n = bad = 0
    for p in paths:
        for line in open(p):
            if not line.strip(): continue
            r = json.loads(line); n += 1; ok, why = judge(r)
            if not ok:
                bad += 1
                if bad <= 12: print("FAIL %s %s %dpt: %s: %r" % (r["code"], r["view"], r["width"], why, r["title"][:80]))
    if not n: print("title_whole: no rows: nothing was read"); return 1
    print("title_whole: %d rows, %d FAIL" % (n, bad))
    return 1 if bad else 0

if __name__ == "__main__":
    if "--self-test" in sys.argv: sys.exit(1 if self_test() else 0)
    sys.exit(main_files([a for a in sys.argv[1:] if not a.startswith("--")]))
