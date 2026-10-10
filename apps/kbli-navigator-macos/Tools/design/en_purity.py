#!/usr/bin/env python3
"""en_purity.py — the en-purity gate (Q12, Z-DECISIONI 2026-10-10: "in English it's English"). Python 3.9, stdlib.

census <encensus.jsonl> --id <encensus-id.jsonl>  (Tests/encensus output, English and the Indonesian dump of the
  gated surfaces; dataset from env KBLI_JSON). A STRING is one drawn line of one (code, view). It is Indonesian when,
  outside the allowlisted spans, it holds a word of Tools/design/en_lexicon.tsv (word, group, English gloss: the gloss
  is the reason the word is not English), the code's raw official title, or a pipeline key — a snake_case identifier
  or a `key=` locator, which no span allowlists (ruling 1). Words are read as drawn, split where PDFKit glued two runs
  ("CodesSemua"). The allowlist is ALLOW below plus spans checked against THIS code's record: its official title
  under its label (ruling 3), its pma_kondisi under the original label (ruling 4) or as written when English, its
  curated English Bali reason (an enum in it may stand only as a short lexicon-free label), and the Indonesian an
  English description quotes in parentheses. Prints `en-indonesian-strings: N` per view and category and the
  allowlisted spans by reason; exit 1 when a GATED view holds any string. The self-test runs first, synthetic and
  over the known corpus: all 1,559 ID titles drawn unlabelled are flagged, every ID-only word of the gated surfaces
  is a lexicon word, and the English titles and descriptions flag nothing (innocence, measured).
static [APP_ROOT]  the never-drawn check, on the entity: a raw Indonesian record field (judul, uraian, pma_kondisi,
  a raw enum), read directly or through a local binding in scope, must not reach a drawn sink (Text, Label,
  TextField, Button, Toggle, Link, Menu titles, .navigationTitle, an interpolation) nor an unseen one (.help,
  .accessibility{Label,Value,Hint}), and an unseen one reads only a vetted value (SAFE, a localiser call, or a name
  bound to one in scope). Text(verbatim:) is a finding. Exit 1 on a finding in a STATIC file; REPORTED files print."""
import json, os, re, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
# The Views held to 0, and the files the never-drawn check gates (each View joins both as its lot lands).
GATED = ["search-chrome", "registry-chrome", "search-field",
         "search-row", "search-peak", "registry-row", "registry-sheet"]                  # EN-1b (Q12)
STATIC = ["Sources/Views/SearchFieldBar.swift",
          "Sources/Views/SearchListView.swift", "Sources/Views/KBLIRegistryTable.swift",
          "Sources/Views/RegistryVerdictSheet.swift"]                                    # EN-1b (Q12)
REPORTED = []

LEX = {}
for line in open(os.path.join(HERE, "en_lexicon.tsv"), encoding="utf-8"):
    if line.strip() and not line.startswith("#"):
        w, g, gloss = line.rstrip("\n").split("\t"); LEX[w] = g
# Words an Indonesian dump of a gated surface may hold that no English dump does and that are not Indonesian.
PROPER = {"kbli": "the classification's name", "oss": "the licensing system's name", "bali": "the island",
          "pma": "the company type", "pt": "the company form", "zantara": "the assistant's name"}
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
R_PAREN = "the Indonesian original the record's English description quotes in parentheses"
R_NAME = "an Indonesian proper name the record's English description carries over from its Indonesian one"
CLAUSE_EN = set("the of and to in for with on by or from as at is are not only must may any no".split())
CLAUSE_ID = set("yang dan di ke dari untuk dengan pada dalam atau oleh tidak bukan bagi serta hanya".split())
IDENT_RE = re.compile(r"\b[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+\b")
PROV_RE = re.compile(r"\b[a-z][a-z0-9_.\[\]]*=")
WORD_RE = re.compile(r"[A-Za-zÀ-ÿ]+")
GLUE_RE = re.compile(r"(?<=[a-zß-ÿ])(?=[A-ZÀ-Þ])")

def words(s):
    """(offset, word) as drawn: a lower→Upper boundary splits what PDFKit glued ("CodesSemua"); digits never join."""
    for m in WORD_RE.finditer(s):
        p = m.start()
        for w in GLUE_RE.split(m.group()):
            yield p, w; p += len(w)

def lexical(s): return [w.lower() for _, w in words(s) if w.lower() in LEX]

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

def partition(k, pieces):
    """Lines whose keys, in some order and each used once, spell exactly `k`. A span's label leads it, so the label
    line is always among them; a duplicate or a missing piece leaves no partition."""
    def go(p, used):
        if p == len(k): return used
        for n, kk in pieces:
            if n not in used and k.startswith(kk, p):
                got = go(p + len(kk), used + [n])
                if got: return got
        return None
    return go(0, []) or []

class Record:
    """The record-bound allow spans of one code, compiled once: (pattern, the whole text as drawn, reason, gapped)."""
    def __init__(self, rec, reasons, i18n=None):
        self.judul = rec.get("judul") or ""
        self.title_re = re.compile(flex(self.judul)) if self.judul else None
        spans = []
        if self.judul:
            t = "Official title (Bahasa Indonesia) " + self.judul
            spans.append((re.compile(r"Official title \(Bahasa Indonesia\)\s*" + flex(self.judul)), t, R_TITLE, False))
        k = rec.get("pma_kondisi")
        if k and english_clause(k):
            spans.append((re.compile(flex(k)), k, R_KONDISI, False))
        elif k:
            t = "Original (Bahasa Indonesia): “%s”" % k
            spans.append((re.compile(r"Original \(Bahasa Indonesia\):\s*“" + flex(k) + "”"), t, R_ORIGINAL, False))
        raw = (rec.get("l4_bali") or {}).get("reason") or ""
        en = (reasons.get(raw) or {}).get("en") or raw
        if en and english(en):   # an enum inside it is drawn as its label: a short run, checked lexicon-free
            spans.append((re.compile("(.{1,40}?)".join(flex(p) for p in IDENT_RE.split(en))), en, R_REASON, True))
        desc, own = (i18n or {}).get(rec.get("uraian") or "", ""), rec.get("uraian") or ""
        for m in re.finditer(r"\([^()]+\)", desc):
            if lexical(m.group()): spans.append((re.compile(flex(m.group())), m.group(), R_PAREN, False))
        for m in re.finditer(r"[A-Z][\w-]*(?:\s+[A-Z][\w-]*)+", desc):   # a run of Capitalised words: the longest
            ws, i = m.group().split(), 0                                    # parts the ID description holds verbatim
            while i < len(ws) - 1:
                j = next((j for j in range(len(ws), i + 1, -1)
                          if lexical(" ".join(ws[i:j])) and " ".join(ws[i:j]) in own), None)
                if j: spans.append((re.compile(flex(" ".join(ws[i:j]))), " ".join(ws[i:j]), R_NAME, False))
                i = j or i + 1
        self.spans = spans

def analyse(row, rec):
    """[(line, category, tokens)] for the Indonesian strings of one dump, and [(reason, tokens)] for allowlisted spans."""
    lines = [" ".join(l.split()) for l in row["text"].split("\n")]
    text = " ".join(lines); starts, p = [], 0
    for l in lines: starts.append(p); p += len(l) + 1
    line_of = lambda i: max(0, next((n for n, s in enumerate(starts) if s > i), len(starts)) - 1)
    mask, allowed = list(text), []
    spans = [(m.span(), r) for rx, r in ALLOW_RE for m in rx.finditer(text)]
    for rx, whole, r, gapped in (rec.spans if rec else []):
        found = [m.span() for m in rx.finditer(text) if not (gapped and any(lexical(g) for g in m.groups()))]
        if not found:
            # PDFKit orders lines by geometry and splits runs at a font change, so a wrapped text can come back
            # with its lines swapped or cut ("m²" / "."): then lines that partition it exactly are allowed.
            k = key(whole)
            parts = partition(k, [(n, key(l)) for n, l in enumerate(lines) if key(l) and key(l) in k])
            found = [(starts[n], starts[n] + len(lines[n])) for n in parts]
        spans += [(f, r) for f in found]
    for (a, b), r in spans:
        toks = lexical(text[a:b])
        if toks: allowed.append((r, toks))
        for i in range(a, b): mask[i] = " "
    masked = "".join(mask)
    flagged = defaultdict(lambda: {"toks": [], "raw": [], "title": False})
    for p, w in words(masked):
        if w.lower() in LEX: flagged[line_of(p)]["toks"].append(w.lower())
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
    """Guilt and innocence on synthetic dumps: each case is (text, want strings, record)."""
    rec = {"judul": "Aktivitas Vila", "pma_kondisi": "Bidang usaha dialokasikan untuk Koperasi dan UMKM",
           "l4_bali": {"reason": "OSS risk at the Besar (large) scale is Medium-High → not blocked by the moratorium"}}
    r = Record(rec, {})
    r2 = Record({"judul": "Industri Senjata", "pma_kondisi": "may exceed 49% with Menteri Pertahanan approval"}, {})
    r3 = Record({"judul": "Aktivitas Vila", "l4_bali": {"reason": "OSS risk is CHIUSO_BALI at the Besar scale, so the moratorium applies"}}, {})
    cases = [("Villa Rental\nOfficial title (Bahasa Indonesia)\nAktivitas Vila", 0, r),
             ("55203 Aktivitas Vila", 1, r),                                            # a raw title
             ("Official title (Bahasa Indonesia)\nAktivitas Hotel", 1, r),              # someone else's title
             ("Restricted · 0%  Original (Bahasa Indonesia): “Bidang usaha\ndialokasikan untuk Koperasi dan UMKM”", 0, r),
             ("Restricted · 0%  Bidang usaha dialokasikan untuk Koperasi dan UMKM", 1, r),  # unlabelled original
             ("Bali status: ATTENZIONE_FASCIA_BALI · blocked: no", 1, r),               # an Italian enum
             ("pma_status=TERBUKA", 1, r),                                               # a locator
             ("cited by the record: Perpres 10/2021, 49/2021 Lampiran II, Pasal 5(5)", 0, r),
             ("OSS risk at the Besar (large) scale is Medium-High → not blocked by\nthe moratorium", 0, r),
             ("OSS risk at the Besar (large) scale", 1, r),                              # not the record's reason
             ("TERBUKA Open · 100%", 1, r),
             ("Restricted · 0%\ndan UMKM”\nOriginal (Bahasa Indonesia): “Bidang usaha dialokasikan untuk Koperasi", 0, r),  # swapped
             ("dan UMKM”\nOriginal (Bahasa Indonesia): “Bidang usaha dialokasikan untuk Koperasi\nKoperasi dan", 1, r),  # + a piece
             # the #8213 gate's B4: the original unlabelled, plus a duplicate piece as long as the label
             ("Restricted · 0%\nBidang usaha dialokasikan untuk Koperasi dan UMKM\nBidang usaha dialokasikan", 2, r),
             ("Restricted · 49%  may exceed 49% with Menteri Pertahanan approval", 0, r2),   # English condition, as written
             ("Restricted · 49%  Menteri Pertahanan", 1, r2),                                 # not the record's condition
             ("OSS risk is Closed in Bali at the Besar scale, so the moratorium applies", 0, r3),  # enum drawn as its label
             # the gate's C1: the enum's place taken by Indonesian free text
             ("OSS risk is Bidang usaha tertutup untuk asing at the Besar scale, so the moratorium applies", 1, r3),
             ("Cari kode KBLI · 26 codes shown · catalogue of 1,559", 1, None),          # the gate's mut1
             ("CodesSemua sektor · 26 codes shown", 1, None),                             # mut2, glued by PDFKit
             ("CodesSemua · 26 codes shown", 1, None),                                    # its only Indonesian, glued
             ("Codes26 codes shown · catalogue of 1,559: 395 not determined", 0, None),
             ("Search code or activity…\nCari kode atau kegiatan…", 1, None)]             # mut3, the placeholder
    bad = []
    for text, want, rr in cases:
        got = len(analyse({"text": text}, rr)[0])
        if got != want: bad.append("EN-SELFTEST %r: %d strings, want %d" % (text[:50], got, want))
    return bad

def corpus(ds, i18n, reasons, rows, id_rows):
    """The known corpus: (printed lines, failures)."""
    out, bad = [], []
    titles = [r["judul"] for r in ds.values() if r.get("judul")]
    missed = [t for t in titles if not analyse({"text": t}, None)[0]]
    out.append("self-test: ID official titles drawn unlabelled, flagged with no record: %d/%d" % (len(titles) - len(missed), len(titles)))
    bad += ["EN-SELFTEST title not flagged: %s" % t for t in missed]
    gated = lambda rs: {w.lower() for r in rs if r["view"] in GATED for _, w in words(r["text"])}
    only = sorted(gated(id_rows) - gated(rows) - set(PROPER))
    miss = [w for w in only if w not in LEX]
    out.append("self-test: ID-only words of the gated surfaces (%s) in the lexicon: %d/%d"
               % (", ".join(sorted({r["view"] for r in id_rows if r["view"] in GATED})), len(only) - len(miss), len(only)))
    if not {r["view"] for r in id_rows} >= set(GATED): bad.append("EN-SELFTEST the --id dump lacks a gated surface")
    bad += ["EN-SELFTEST ID-only word of a gated surface not in the lexicon: %s" % w for w in miss]
    en_titles = [i18n[r["judul"]] for r in ds.values() if r.get("judul") in i18n]
    flagged = [t for t in en_titles if analyse({"text": t}, None)[0]]
    out.append("innocence: English titles flagged %d/%d" % (len(flagged), len(en_titles)))
    descs = [(i18n[r["uraian"]], r) for r in ds.values() if r.get("uraian") in i18n]
    dflag = [d for d, r in descs if analyse({"text": d}, Record(r, reasons, i18n))[0]]
    out.append("innocence: English descriptions flagged outside their record-bound spans %d/%d" % (len(dflag), len(descs)))
    bad += ["EN-SELFTEST English text flagged: %s" % t[:80] for t in flagged + dflag]
    modal = sum(len(re.findall(r"\bmodal\b", t, re.I)) for t in en_titles + [d for d, _ in descs])
    out.append("innocence: `modal` in the English corpus %d (a lexicon word: the app has no English modal)" % modal)
    return out, bad

def census(path, id_path, n_ex):
    fails = selftest()
    ds = {r["kode_kbli_2025"]: r for r in json.load(open(os.environ["KBLI_JSON"]))["data"]}
    reasons = json.load(open(os.path.join(ROOT, "Resources", "kbli-reason-i18n.json")))
    i18n = json.load(open(os.path.join(ROOT, "Resources", "kbli-data-i18n-en.json")))
    recs, rows = {}, [json.loads(l) for l in open(path)]
    id_rows = [json.loads(l) for l in open(id_path)] if id_path else []
    lines, bad = corpus(ds, i18n, reasons, rows, id_rows)
    fails += bad
    for f in fails: print(f)
    for l in lines: print(l)
    by_view, by_cat, allow_by, allow_gated = Counter(), Counter(), Counter(), Counter()
    distinct, examples = set(), defaultdict(list)
    for row in rows:
        c = row["code"]
        if c in ds and c not in recs: recs[c] = Record(ds[c], reasons, i18n)
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

# --- the never-drawn check -------------------------------------------------------------------------------------
SINK_RE = re.compile(r"(?<![\w.])(Text|Label|TextField|SecureField|Button|Toggle|Link|Menu)\("
                     r"|\.(help|navigationTitle|navigationSubtitle|accessibilityLabel|accessibilityValue|accessibilityHint)\(")
UNSEEN = {"help", "accessibilityLabel", "accessibilityValue", "accessibilityHint"}   # never drawn: vetted values only
LOCALISER_RE = re.compile(r"(?:LabelBook\.\w+|Theme\.(?:riskShortLabel|kbliStatusLabel)|PP28ScalePanel\.scaleLabel"
                          r"|OverlayStore\.shared\.(?:primaryTitle|displayReason|dataString)|KBLIVerdict\.headsUp|lang\.t)\(")
RAW_RE = re.compile(r"\.(?:judul|uraian|pmaStatus|pmaKondisi|pmaSource|pmaRouteTo|pmaNota|statusMapping|ruangLingkup"
                    r"|kategoriRisiko|skalaUsaha|riskLabelRaw)\b|\.l4Bali[?!]?\.(?:status|reason)\b")
BIND_RE = re.compile(r"\b(?:let|var)\s+([A-Za-z_]\w*)(?:\s*:[^=\n{]+)?\s*=\s*([^\n]*(?:\n\s*(?:\?\?|\?|:|\.|\+|&&|\|\|)[^\n]*)*)")
SAFE = {  # identifier chains an unseen sink may read, each with its reason
    "isID": "the language switch", "expanded": "a Bool", "compact": "a Bool", "rowDensity": "a density enum",
    "kbli.kode": "the code number, language-free", "voiceOverLabel": "VerdictBadge's literal-only, isID-switched sentence",
}
KEYWORDS = {"true", "false", "nil", "let", "if", "else", "return", "self"}

def balanced(src, i, open_="(", close=")"):
    """The offset just past the bracket matching src[i], strings (and their interpolations) skipped."""
    depth, j, instr = 0, i, False
    while j < len(src):
        ch = src[j]
        if instr:
            if ch == "\\" and src[j + 1:j + 2] == "(":   # an interpolation is code
                j = balanced(src, j + 1); continue
            if ch == "\\": j += 2; continue
            if ch == '"': instr = False
        elif ch == '"': instr = True
        elif ch == open_: depth += 1
        elif ch == close:
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

def first_arg(code):
    """A title sink's first argument (its title), up to the first top-level comma of its literal-free code."""
    depth = 0
    for j, ch in enumerate(code):
        if ch in "([{": depth += 1
        elif ch in ")]}": depth -= 1
        elif ch == "," and depth == 0: return code[:j]
    return code

def flow(code):
    """The part of literal-free code whose VALUE flows on: a closure, a count, an emptiness test and a comparison
    read a field without passing its text (a count of risk rows is a number, not a risk word)."""
    while True:
        new = re.sub(r"\{[^{}]*\}", " ", code)
        if new == code: break
        code = new
    code = re.sub(r"[A-Za-z_][\w.?!]*\.(?:count|isEmpty)\b", " ", code)
    return re.sub(r"[\w.?!)\]]+\s*(?:==|!=)\s*[\w.?!(\[]*", " ", code)

CHAIN_RE = re.compile(r"(?<![.\w])[A-Za-z_]\w*(?:\??\.[A-Za-z_]\w*)*")

def scan(src):
    """[(line, message)] for one Swift source, comments blanked."""
    src = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group()), src, flags=re.S)
    src = re.sub(r"(?m)(^|[ \t])//[^\n]*", lambda m: " " * len(m.group()), src)   # same offsets and lines
    lineno = lambda i: src.count("\n", 0, i) + 1
    def scope(i):   # the end of the innermost { … } holding offset i
        depth = 0
        for j in range(i, -1, -1):
            if src[j] == "}": depth += 1
            elif src[j] == "{":
                if depth == 0: return balanced(src, j, "{", "}")
                depth -= 1
        return len(src)
    binds = [{"name": m.group(1), "at": m.start(), "end": scope(m.start()), "code": code_only(m.group(2)),
              "line": lineno(m.start()), "kind": None} for m in BIND_RE.finditer(src)]
    def resolve(name, at):
        live = [b for b in binds if b["name"] == name and b["at"] < at < b["end"]]
        return max(live, key=lambda b: b["at"]) if live else None
    def kind(name, at):
        b = resolve(name, at)
        return b["kind"] if b else None
    def vetted(chain, at):   # SAFE, a type (its arguments are chains of their own), or bound to vetted code in scope
        return chain in SAFE or chain in KEYWORDS or chain[0].isupper() or kind(chain.split(".")[0].rstrip("?"), at) == "vetted"
    for _ in range(3):   # a name bound to a tainted name is tainted, to a fixpoint for short chains
        for b in binds:
            chains = CHAIN_RE.findall(flow(b["code"]))
            if RAW_RE.search(flow(b["code"])) or any(kind(c.split(".")[0].rstrip("?"), b["at"]) == "raw" for c in chains):
                b["kind"] = "raw"
            elif re.search(r"\.l4Bali\b", b["code"]): b["kind"] = "holder"
            elif all(vetted(c, b["at"]) for c in chains): b["kind"] = "vetted"
    def raw_reads(code, at):
        code = flow(code)
        for r in RAW_RE.finditer(code): yield "the raw record field `%s`" % r.group().strip(".")
        for m in re.finditer(r"(?<![.\w])([A-Za-z_]\w*)(\??\.(?:status|reason)\b)?", code):
            b = resolve(m.group(1), at)
            if b and (b["kind"] == "raw" or (b["kind"] == "holder" and m.group(2))):
                yield "`%s`, bound to a raw record field at :%d" % (m.group(), b["line"])
    out = []
    for m in SINK_RE.finditer(src):
        end = balanced(src, m.end() - 1); arg = src[m.end():end - 1]
        if m.group(1) == "Text" and arg.lstrip().startswith("verbatim:"):
            out.append((lineno(m.start()), "Text(verbatim:) draws a string no localiser saw"))
        name = m.group(1) or m.group(2)
        body = code_only(arg) if m.group(2) else first_arg(code_only(arg))
        reads = list(raw_reads(body, m.start()))
        out += [(lineno(m.start()), "%s(…) draws %s" % ("." * bool(m.group(2)) + name, what)) for what in reads]
        if m.group(2) in UNSEEN and not reads:
            for chain in CHAIN_RE.findall(body):
                if not vetted(chain, m.start()):
                    out.append((lineno(m.start()), ".%s(…) reads `%s` — not a vetted label (a localiser, SAFE, or a "
                                "name bound to vetted code in scope)" % (name, chain)))
    for m in re.finditer(r"\\\(", src):
        end = balanced(src, m.end() - 1)
        for what in raw_reads(code_only(src[m.end():end - 1]), m.start()):
            out.append((lineno(m.start()), "interpolates %s" % what))
    return sorted(set(out))

def static_selftest():
    guilt = ['Label(kbli.judul, systemImage: "x")', "TextField(kbli.judul, text: $q)", "x.navigationTitle(kbli.judul)",
             "Text(item.judul)", "func f() {\n let t = kbli.judul\n Text(t)\n}", "x.accessibilityLabel(kbli.judul)",
             "x.help(kbli.judul)", "Text(verbatim: s)", "Text(String(kbli.judul))", 'Text("\\(kbli.judul)")',
             "x.accessibilityLabel(Text(kbli.judul))", "Button(kbli.judul) { go() }", "x.help(state.query)",
             "func f() {\n guard let l4 = k.l4Bali else { return }\n Text(l4.status)\n}",
             "func f() {\n let t = isID\n ? kbli.judul : x\n Text(t)\n}",
             "func a() {\n let title = LabelBook.title(k, isID: i)\n}\nfunc b() {\n Text(\"x\").help(title)\n}",
             "func f() {\n let k = (r.pmaKondisi?.isEmpty == false) ? r.pmaKondisi! : x\n Text(\"\\(k)\")\n}"]
    innocent = ["func a() {\n let title = LabelBook.title(k, isID: i)\n Text(title).help(title)\n}",
                'TextField(lang.t("search.placeholder"), text: $q)', "Text(LabelBook.pmaStatus(kbli.pmaStatus, isID: isID))",
                "func a() {\n let t = kbli.judul\n _ = t\n}\nfunc b() {\n let t = lang.t(\"x\")\n Text(t)\n}",
                'Button("Clear") { state.query = kbli.judul }',
                'func f() {\n let n = rows.filter { $0.kategoriRisiko != nil }.count\n Text("\\(n) rows")\n}', "x.help(isID ? lang.t(\"a\") : lang.t(\"b\"))",
                'func a() {\n let hu = KBLIVerdict.headsUp(record: k, isID: i)\n Text("x").accessibilityLabel("\\(kbli.kode) \\(hu.label)")\n}']
    bad = ["NEVER-DRAWN-SELFTEST guilt not caught: %r" % g for g in guilt if not scan(g)]
    bad += ["NEVER-DRAWN-SELFTEST innocent flagged: %r %s" % (s, scan(s)) for s in innocent if scan(s)]
    return bad

def static(app_root):
    bad = static_selftest()
    for b in bad: print(b)
    gated = reported = 0
    for rel in STATIC + REPORTED:
        for line, msg in scan(open(os.path.join(app_root, rel), encoding="utf-8").read()):
            if rel in STATIC: gated += 1; print("never-drawn: %s:%d %s" % (os.path.basename(rel), line, msg))
            else: reported += 1; print("never-drawn (reported, gated by EN-1b): %s:%d %s" % (os.path.basename(rel), line, msg))
    print("never-drawn: %d finding(s) in %d gated files; %d reported in %d files (self-test %s, SAFE %d values)"
          % (gated, len(STATIC), reported, len(REPORTED), "FAILED" if bad else "ok", len(SAFE)))
    return 1 if bad or gated else 0

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["census"] and len(a) > 1:
        sys.exit(census(a[1], a[a.index("--id") + 1] if "--id" in a else None,
                        int(a[a.index("--examples") + 1]) if "--examples" in a else 3))
    if a[:1] == ["static"]:
        sys.exit(static(a[1] if len(a) > 1 else ROOT))
    print(__doc__); sys.exit(2)
