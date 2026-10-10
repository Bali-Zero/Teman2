#!/usr/bin/env python3
"""en_purity.py — the en-purity gate (Q12, Z-DECISIONI 2026-10-10: "in English it's English"). Python 3.9, stdlib.

census <encensus.jsonl>  (Tests/encensus output; dataset from env KBLI_JSON). A STRING is one drawn line of one
  (code, view). It is Indonesian when, outside the allowlisted spans, it holds a word of Tools/design/en_lexicon.tsv
  (word, group, English gloss: the gloss is the reason the word is not English), the code's raw official title, or
  a pipeline key — a snake_case identifier or a `key=` locator, which no span allowlists (ruling 1). The allowlist
  is ALLOW below plus three spans checked against THIS code's record: its official title under its label (ruling
  3), its pma_kondisi quoted under the original label (ruling 4), and its curated English Bali reason. Prints
  `en-indonesian-strings: N` per view and category and the allowlisted spans by reason; exit 1 when a GATED view
  holds any string. A synthetic self-test runs first.
static [APP_ROOT]  strings an English reader never sees drawn but meets as a tooltip or a VoiceOver label: in the
  STATIC files, every `.help`/`.accessibility{Label,Value,Hint}` argument may read only a vetted value (SAFE, or
  inside a LabelBook / primaryTitle / headsUp call); `Text(verbatim:` and a raw record field drawn by `Text(` or
  interpolated are findings too. Exit 1 on any, naming file:line and the value."""
import json, os, re, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
# The Views held to 0, and the files the never-drawn check reads (each View joins both as its lot lands).
GATED = ["search-chrome", "registry-chrome"]
STATIC = ["Sources/Views/SearchFieldBar.swift"]

LEX = {}
for line in open(os.path.join(HERE, "en_lexicon.tsv"), encoding="utf-8"):
    if line.strip() and not line.startswith("#"):
        w, g, gloss = line.rstrip("\n").split("\t"); LEX[w] = g
EN_FUNCTION = set("the of and to in for is a an with on this that by or from as at be not are it its into under only any no "
                  "has have can cannot must may your you which who what when where".split())
ALLOW = [  # (regex, reason) — masked before the lexicon is read; never masks a pipeline key
    (r"\b(?:PP|Perpres|Permen|Permen\w+|Perka\w*|Perda|Pergub|Perbup|Kepmen\w*|UU|Inpres|Keppres)(?:\s+[A-Z][\w]*(?:/[A-Z]\w*)?)?"
     r"\s+(?:No\.?\s*)?\d+(?:/\d{4}|\s+Tahun\s+\d{4})",
     "legal citation: an instrument's name, number and year"),
    (r"\b(?:Lampiran|Pasal|ayat|huruf|angka)\s+(?:[IVXL]+\b(?:[.\w]*)(?:\s*(?:,|/|dan|and|or)\s*[IVXL]+\b)*|\(?\d[\w()–\-.]*|\([a-z0-9]+\)|[a-z]\b)",
     "legal citation: an instrument's part (Lampiran / Pasal / ayat / huruf / angka) with its number"),
    (r"\bKBLI\b|\bOSS(?:-RBA)?\b|\bBKPM\b|\bPT\s+PMA\b|\bPMA\b|\bPMDN\b|\bNIB\b|\bUMKM\b|\bBPS\b|\bKITAS\b|\bWNA\b|\bWNI\b",
     "proper noun / official acronym"),
    (r"\bKementerian\s+Investasi(?:/BKPM)?\b|\bBadan\s+Koordinasi\s+Penanaman\s+Modal\b|\bBadan\s+Pusat\s+Statistik\b",
     "official agency name"),
    (r"\bDinas\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b|\bDPMPTSP\b|\bSatpol\s+PP\b", "official regional agency name"),
]
ALLOW_RE = [(re.compile(a), r) for a, r in ALLOW]
R_TITLE = "official title, under its label (ruling 3)"
R_ORIGINAL = "legal text with no English source, quoted under its label (ruling 4)"
R_REASON = "the record's curated English Bali reason: its Indonesian words are the cited instrument's terms"
R_KONDISI = "the record's own condition, written in English: its Indonesian words are the instrument's terms"
CLAUSE_EN = set("the of and to in for with on by or from as at is are not only must may any no".split())
CLAUSE_ID = set("yang dan di ke dari untuk dengan pada dalam atau oleh tidak bukan bagi serta hanya".split())
IDENT_RE = re.compile(r"\b[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+\b")
PROV_RE = re.compile(r"\b[a-z][a-z0-9_.\[\]]*=")
WORD_RE = re.compile(r"[A-Za-zÀ-ÿ]+")

def flex(s):
    """A pattern for `s` as drawn: any whitespace run may be a line break, and a break may follow / or a dash."""
    out = []
    for part in re.split(r"(\s+)", s):
        if not part: continue
        if part.isspace(): out.append(r"\s+"); continue
        out.append("".join(re.escape(c) + (r"\s*" if c in "/-–—" else "") for c in part))
    return "".join(out)

def english(s): return sum(w.lower() in EN_FUNCTION for w in WORD_RE.findall(s)) >= 3

def english_clause(s):
    """A condition is English when its opening clause (up to " — ", "(" or ";") holds more English than Indonesian
    function words — the rule LabelBook.isEnglish states; an English one is drawn unlabelled."""
    head = [w.lower() for w in WORD_RE.findall(re.split(r" — |[(;]", s)[0])]
    return sum(w in CLAUSE_EN for w in head) > sum(w in CLAUSE_ID for w in head)

def key(s): return "".join(c for c in s if c.isalnum())

class Record:
    """The three record-bound allow spans of one code, compiled once: (pattern, the whole text as drawn, reason)."""
    def __init__(self, rec, reasons):
        self.judul = rec.get("judul") or ""
        self.title_re = re.compile(flex(self.judul)) if self.judul else None
        spans = []
        if self.judul:
            t = "Official title (Bahasa Indonesia) " + self.judul
            spans.append((re.compile(r"Official title \(Bahasa Indonesia\)\s*" + flex(self.judul)), t, R_TITLE))
        k = rec.get("pma_kondisi")
        if k and english_clause(k):
            spans.append((re.compile(flex(k)), k, R_KONDISI))
        elif k:
            t = "Original (Bahasa Indonesia): “%s”" % k
            spans.append((re.compile(r"Original \(Bahasa Indonesia\):\s*“" + flex(k) + "”"), t, R_ORIGINAL))
        raw = (rec.get("l4_bali") or {}).get("reason") or ""
        en = (reasons.get(raw) or {}).get("en") or raw
        if en and english(en):   # an enum inside it is drawn as its label: any short run may stand in for it
            spans.append((re.compile(r".{1,60}?".join(flex(p) for p in IDENT_RE.split(en))), en, R_REASON))
        self.spans = spans

def analyse(row, rec):
    """[(line, category, tokens)] for the Indonesian strings of one dump, and [(reason, tokens)] for allowlisted spans."""
    lines = [" ".join(l.split()) for l in row["text"].split("\n")]
    text = " ".join(lines); starts, p = [], 0
    for l in lines: starts.append(p); p += len(l) + 1
    line_of = lambda i: max(0, next((n for n, s in enumerate(starts) if s > i), len(starts)) - 1)
    mask, allowed = list(text), []
    spans = [(m.span(), r) for rx, r in ALLOW_RE for m in rx.finditer(text)]
    for rx, whole, r in (rec.spans if rec else []):
        found = [m.span() for m in rx.finditer(text)]
        if not found:
            # PDFKit orders lines by geometry and splits runs at a font change, so a wrapped text can come back
            # with its lines swapped or cut ("m²" / "."). Then the text is allowed when lines that are each a piece
            # of it add up to exactly all of it — a duplicate or an extra piece is not allowed.
            k = key(whole); parts = [n for n, l in enumerate(lines) if key(l) and key(l) in k]
            if parts and sum(len(key(lines[n])) for n in parts) == len(k):
                found = [(starts[n], starts[n] + len(lines[n])) for n in parts]
        spans += [(f, r) for f in found]
    for (a, b), r in spans:
        toks = [w.lower() for w in WORD_RE.findall(text[a:b]) if w.lower() in LEX]
        if toks: allowed.append((r, toks))
        for i in range(a, b): mask[i] = " "
    masked = "".join(mask)
    flagged = defaultdict(lambda: {"toks": [], "raw": [], "title": False})
    for m in WORD_RE.finditer(masked):
        if m.group().lower() in LEX: flagged[line_of(m.start())]["toks"].append(m.group().lower())
    for rx in (IDENT_RE, PROV_RE):
        for m in rx.finditer(text): flagged[line_of(m.start())]["raw"].append(m.group())
    if rec and rec.title_re:
        for m in rec.title_re.finditer(masked): flagged[line_of(m.start())]["title"] = True
    out = []
    for n, f in sorted(flagged.items()):
        groups = Counter(LEX[t] for t in f["toks"])
        cat = ("raw fields" if f["raw"] else "titles" if f["title"] else next(
            (c for g, c in (("verdict", "verdict words"), ("risk", "risk"), ("scale", "scales"), ("authority", "authority"))
             if groups[g]), "statute text" if groups["statute"] or groups["function"] else "labels"))
        out.append((lines[n], cat, f["toks"] + f["raw"]))
    return out, allowed

CATS = ("titles", "verdict words", "risk", "scales", "authority", "statute text", "raw fields", "labels")

def selftest():
    """Guilt and innocence on synthetic dumps: each case is (text, record, want strings)."""
    rec = {"judul": "Aktivitas Vila", "pma_kondisi": "Bidang usaha dialokasikan untuk Koperasi dan UMKM",
           "l4_bali": {"reason": "OSS risk at the Besar (large) scale is Medium-High → not blocked by the moratorium"}}
    r = Record(rec, {})
    cases = [("Villa Rental\nOfficial title (Bahasa Indonesia)\nAktivitas Vila", 0),
             ("55203 Aktivitas Vila", 1),                                            # a raw title
             ("Official title (Bahasa Indonesia)\nAktivitas Hotel", 1),              # someone else's title
             ("Restricted · 0%  Original (Bahasa Indonesia): “Bidang usaha\ndialokasikan untuk Koperasi dan UMKM”", 0),
             ("Restricted · 0%  Bidang usaha dialokasikan untuk Koperasi dan UMKM", 1),  # unlabelled original
             ("Bali status: ATTENZIONE_FASCIA_BALI · blocked: no", 1),               # an Italian enum
             ("pma_status=TERBUKA", 1),                                               # a locator
             ("cited by the record: Perpres 10/2021, 49/2021 Lampiran II, Pasal 5(5)", 0),
             ("OSS risk at the Besar (large) scale is Medium-High → not blocked by\nthe moratorium", 0),
             ("OSS risk at the Besar (large) scale", 1),                              # not the record's reason
             ("TERBUKA Open · 100%", 1),
             ("Restricted · 0%\ndan UMKM”\nOriginal (Bahasa Indonesia): “Bidang usaha dialokasikan untuk Koperasi", 0),  # swapped
             ("dan UMKM”\nOriginal (Bahasa Indonesia): “Bidang usaha dialokasikan untuk Koperasi\nKoperasi dan", 3)]  # + a piece
    r2 = Record({"judul": "Industri Senjata", "pma_kondisi": "may exceed 49% with Menteri Pertahanan approval"}, {})
    cases = [(c, w, r) for c, w in cases] + [
        ("Restricted · 49%  may exceed 49% with Menteri Pertahanan approval", 0, r2),   # English condition, as written
        ("Restricted · 49%  Menteri Pertahanan", 1, r2)]                                 # not the record's condition
    bad = []
    for text, want, r in cases:
        got = len(analyse({"text": text}, r)[0])
        if got != want: bad.append("EN-SELFTEST %r: %d strings, want %d" % (text[:50], got, want))
    return bad

def census(path, n_ex):
    fails = selftest()
    for f in fails: print(f)
    ds = {r["kode_kbli_2025"]: r for r in json.load(open(os.environ["KBLI_JSON"]))["data"]}
    reasons = json.load(open(os.path.join(ROOT, "Resources", "kbli-reason-i18n.json")))
    recs, rows = {}, [json.loads(l) for l in open(path)]
    by_view, by_cat, allow_by, allow_gated = Counter(), Counter(), Counter(), Counter()
    distinct, examples = set(), defaultdict(list)
    for row in rows:
        c = row["code"]
        if c in ds and c not in recs: recs[c] = Record(ds[c], reasons)
        hits, allowed = analyse(row, recs.get(c))
        for r, _ in allowed:
            allow_by[r] += 1
            if row["view"] in GATED: allow_gated[r] += 1
        for line, cat, toks in hits:
            by_view[row["view"]] += 1; by_cat[cat] += 1; distinct.add(line)
            if len(examples[row["view"]]) < n_ex: examples[row["view"]].append((cat, c, line, toks))
    views = sorted({r["view"] for r in rows}, key=lambda v: (v not in GATED, v))
    print("en-indonesian-strings: %d (distinct %d) over %d (code, view) dumps, %d codes · lexicon %d words"
          % (sum(by_view.values()), len(distinct), len(rows), len(recs), len(LEX)))
    for v in views: print("  %-16s %6d  %s" % (v, by_view[v], "GATED" if v in GATED else "counted"))
    print("  by category: " + ", ".join("%s %d" % (c, by_cat[c]) for c in CATS))
    print("allowlisted: %d spans holding Indonesian words, %d of them in gated views (all · gated · reason)"
          % (sum(allow_by.values()), sum(allow_gated.values())))
    for r, n in allow_by.most_common(): print("  %6d %6d  %s" % (n, allow_gated[r], r))
    for v in views:
        for cat, c, line, toks in examples[v]:
            print("  e.g. %-14s %-13s %s  %s   [%s]" % (v, cat, c, line[:100], ",".join(sorted(set(toks)))[:40]))
    gate = ["FAIL: %s holds %d Indonesian strings in English" % (v, by_view[v]) for v in GATED if by_view[v]]
    missing = [v for v in GATED if v not in views]
    if missing: gate.append("FAIL: the census has no dump of %s" % ", ".join(missing))
    for f in gate: print(f)
    fails += gate
    print("en-purity: gated views (%s) %s" % (", ".join(GATED), "0 Indonesian strings" if not fails else "FAILED"))
    return 1 if fails else 0

SINK_RE = re.compile(r"\.(help|accessibilityLabel|accessibilityValue|accessibilityHint)\(")
LOCALISER_RE = re.compile(r"(?:LabelBook\.\w+|Theme\.riskShortLabel|OverlayStore\.shared\.primaryTitle|KBLIVerdict\.headsUp|lang\.t)\(")
RAW_RE = re.compile(r"\b(?:kbli|k|record)\.(?:judul|uraian|pmaStatus|pmaKondisi|pmaSource|pmaRouteTo|pmaNota|statusMapping|ruangLingkup)\b"
                    r"|\bl4(?:Bali)?\??\.(?:status|reason)\b|\.kategoriRisiko\b|\.skalaUsaha\b")
SAFE = {  # identifier chains a sink may read, each with its reason
    "isID": "the language switch", "expanded": "a Bool", "compact": "a Bool", "rowDensity": "a density enum",
    "kbli.kode": "the code number, language-free", "voiceOverLabel": "VerdictBadge's literal-only, isID-switched sentence",
    "title": "bound by LabelBook.title / OverlayStore.shared.primaryTitle in the same file (checked)",
    "hu.label": "bound by KBLIVerdict.headsUp in the same file (checked)",
}
BINDINGS = {"title": r"let title = (?:LabelBook\.title|OverlayStore\.shared\.primaryTitle)\(", "hu.label": r"let hu = KBLIVerdict\.headsUp\("}
KEYWORDS = {"true", "false", "nil", "let", "if", "else", "return"}

def balanced(src, i):
    """The text from src[i] (an opening paren) to its matching close, strings skipped."""
    depth, j, instr = 0, i, False
    while j < len(src):
        ch = src[j]
        if instr:
            if ch == "\\" and src[j + 1:j + 2] == "(":   # an interpolation is code
                j = balanced(src, j + 1); continue
            if ch == "\\": j += 2; continue
            if ch == '"': instr = False
        elif ch == '"': instr = True
        elif ch == "(": depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0: return j + 1
        j += 1
    return j

def code_only(arg):
    """Literal text removed (interpolations kept), localiser calls removed whole."""
    out, j = [], 0
    while j < len(arg):
        m = LOCALISER_RE.match(arg, j)
        if m: j = balanced(arg, m.end() - 1); out.append(" "); continue
        if arg[j] == '"':
            j += 1
            while j < len(arg) and arg[j] != '"':
                if arg[j] == "\\" and arg[j + 1:j + 2] == "(":
                    k = balanced(arg, j + 1); out.append(" " + code_only(arg[j + 2:k - 1]) + " "); j = k; continue
                j += 2 if arg[j] == "\\" else 1
            j += 1; continue
        out.append(arg[j]); j += 1
    return "".join(out)

def static(app_root):
    findings = []
    for rel in STATIC:
        src = open(os.path.join(app_root, rel), encoding="utf-8").read()
        src = re.sub(r"//[^\n]*", lambda m: " " * len(m.group()), src)   # comments, same offsets
        lineno = lambda i: src.count("\n", 0, i) + 1
        for m in SINK_RE.finditer(src):
            end = balanced(src, m.end() - 1); arg = src[m.end():end - 1]
            for chain in re.findall(r"(?<![.\w])[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", code_only(arg)):
                if chain in KEYWORDS: continue
                if chain in SAFE and (chain not in BINDINGS or re.search(BINDINGS[chain], src)): continue
                findings.append("%s:%d .%s(…) reads `%s` — not a vetted label (LabelBook, primaryTitle, headsUp or SAFE)"
                                % (os.path.basename(rel), lineno(m.start()), m.group(1), chain))
        for m in re.finditer(r"Text\(verbatim:", src):
            findings.append("%s:%d Text(verbatim:) draws a string no localiser saw" % (os.path.basename(rel), lineno(m.start())))
        for m in re.finditer(r"\bText\(", src):
            end = balanced(src, m.end() - 1); arg = code_only(src[m.end():end - 1])
            for r in RAW_RE.finditer(arg):
                findings.append("%s:%d Text(…) draws the raw record field `%s`" % (os.path.basename(rel), lineno(m.start()), r.group().strip(".")))
        for m in re.finditer(r"\\\(", src):
            end = balanced(src, m.end() - 1)
            for r in RAW_RE.finditer(code_only(src[m.end():end - 1])):
                findings.append("%s:%d interpolates the raw record field `%s`" % (os.path.basename(rel), lineno(m.start()), r.group().strip(".")))
    for f in findings: print("never-drawn: " + f)
    print("never-drawn: %d finding(s) in %d files (SAFE %d values)" % (len(findings), len(STATIC), len(SAFE)))
    return 1 if findings else 0

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["census"] and len(a) > 1:
        sys.exit(census(a[1], int(a[a.index("--examples") + 1]) if "--examples" in a else 3))
    if a[:1] == ["static"]:
        sys.exit(static(a[1] if len(a) > 1 else ROOT))
    print(__doc__); sys.exit(2)
