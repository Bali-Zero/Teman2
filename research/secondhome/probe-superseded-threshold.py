#!/usr/bin/env python3
"""Measure the SUPERSEDED Second Home threshold, and the claims that replace it.

The E33 eligibility threshold is USD 130,000 held in the applicant's own name at a
state-owned (BUMN) Indonesian bank, or USD 1,000,000 of qualifying completed
strata-title property (`e33_base_deposit_amount` / `e33_base_property_alternative`,
both `confirmed` in research/secondhome/e33-fact-registry.json).

"IDR 2 billion" is the SUPERSEDED figure. This probe rewrites nothing. It reports
the CO-OCCURRENCE set — a line naming the product AND the superseded amount —
because an IDR 2 billion figure belonging to another product is not a defect and
must never be swept.

A zero here is NOT a correctness proof, and the W3 PRE-review said so in writing: a
line reading "E33 requires IDR 2B", or a product name and its amount split across two
lines, once escaped this check. `--claims` exists for that reason — it asserts what
each locale must SAY, not only what it must not say, and it fails on the contradictions
the amount check cannot see (a named qualifying title, a decomposed fee table, a
province-varying property threshold).

WHAT THIS PROBE IS, STATED HONESTLY (2026-09-12, after three adversarial rounds).
It is a MEASUREMENT instrument. The zeros it reports are real and reproducible: run it and you
get them. It is NOT a dependable regression BARRIER, and saying otherwise was the defect the
POST refuter kept finding. Nine named mutations of the cured claims do turn it red — that is
measured, in `evidence/.../build-receipts/guard-mutation-run.txt`. Seven evasions are ALSO
measured, and they are open: the currency rule only reads what comes BEFORE the amount, so
`2 billion USD` is a false positive; `Rp. 2.000.000.000` and `IDR 2.0 billion` are not matched at
all; an allowlisted line keeps its allowance when the line ABOVE it reverses the meaning; the
comparison table's `Financial requirement` row is not anchored; the removed-formulation pins cover
the wording of the BASE commit and not the wording removed in the intermediate rounds; and the
180-day figure removed in the last round was never pinned.
The redesign is specified in `research/secondhome/probe-guard-spec-v2.md` and belongs to a
separate PR, written by this session and implemented by another seat. Until that ships, what
actually protects this family at merge time is the fresh independent gate on content-vs-registry,
the i18n claim ratchet, and the literal FORBIDDEN patterns proved red by mutation — not this file
alone. Do not cite a zero from here as proof that a cure cannot regress.

Usage:
  probe-superseded-threshold.py <file> [<file> ...]  # co-occurrence, e.g. a built llms-full.txt
  probe-superseded-threshold.py --sources            # every amount hit in the 5 canonical sources
  probe-superseded-threshold.py --claims             # the whole family: amount + positive + contradiction + anchored
  probe-superseded-threshold.py --attribute <file>   # each hit + the nearest product mention above it
  probe-superseded-threshold.py --selftest           # the probe's own guilt/innocence cases\n  probe-superseded-threshold.py --allowlist-key '<line>'  # the key to paste into the allowlist
"""
import hashlib
import json
import re
import sys

# `2(?![\d.,]*\d)` keeps IDR 20B, IDR 2.5B and IDR 2,000,000 (not billions) OUT: the
# amount has to be TWO billion, not merely start with a 2.
_TWO = r"2(?![\d.,]*\d)"
_UNIT = r"B\b|Miliar|miliar|milyar|billion|milliards?|miliardi|млрд|миллиард\w*"
# Nine zeros in the three shapes this corpus writes them — dots, commas, the spaces
# French uses, or nothing at all. The trailing guard is the load-bearing part: without
# it `IDR 2,000,000,000,000` matched on its own PREFIX and a figure a thousand times
# larger was convicted as the superseded threshold (POST-refuter finding, 2026-09-12).
# The trailing guard is the load-bearing part and it took three rounds to get right.
# `(?![\d.,\s]*\d)` rejected `IDR 2,000,000,000, 2 passport photos` and
# `IDR 2.000.000.000,00` — a number that FOLLOWS the amount, and the amount's own
# decimals, both read as a continuation of it (POST-refuter round 2, finding 4). So:
# allow up to two decimals, then reject only what would extend the figure — another
# digit glued on, or one more group of three after a separator. A trillion
# (`2,000,000,000,000`) still fails on every backtracking path.
_NINE_ZEROS = r"2(?:[.,\s]?0{3}){3}(?:[.,]\d{1,2})?(?!\d)(?![.,\s]\d{3})"
THRESHOLD = re.compile(
    # IDR 2B · Rp 2 miliar · IDR 2 milliards
    rf"(?:IDR|Rp)\s*{_TWO}\s*(?:{_UNIT})"
    # 2 miliardi di IDR · 2 milliards de roupies · 2 млрд IDR · 2 billion rupiah
    rf"|\b{_TWO}\s*(?:{_UNIT})\s*(?:(?:di|de|of|d'|в)\s+)?(?:rupiah|roupies|IDR|Rp|рупий)?"
    # currency first: IDR 2.000.000.000 · Rp 2,000,000,000 · IDR 2 000 000 000 · IDR 2000000000
    rf"|(?:IDR|Rp)\s*{_NINE_ZEROS}"
    # amount first, currency after — the shape Italian and Indonesian prose actually use:
    # `2.000.000.000 IDR`, `Rp` on the right. Missed entirely until the POST refuter.
    rf"|\b{_NINE_ZEROS}\s*(?:IDR|Rp|rupiah)"
    # ranges that present 2 billion as the floor: IDR 2B-5B · 2 à 5 milliards IDR
    rf"|\b{_TWO}\s*(?:{_UNIT})?\s*(?:[-–—]|à|to|sampai|a|до)\s*\d+\s*(?:{_UNIT})"
    # spelled out
    r"|\b(?:two|due|deux|два|dua)\s+(?:billion|miliardi|milliards?|миллиарда|miliar)"
    # the Rp2M shorthand — flagged for classification, never auto-converted
    rf"|\bRp\s*{_TWO}\s*M\b",
    re.IGNORECASE,
)

# The amount is only the superseded threshold when the CURRENCY bound to it is the
# rupiah. `E33 applicants may own USD 2 billion` was convicted because the amount-first
# branch makes the trailing currency optional and read `2 billion` on its own
# (POST-refuter round 2, finding 5). The entity is amount+currency, so a NON-rupiah
# currency immediately before the figure acquits it — by the currency it names, never by
# proximity to some other word.
_CURRENCY_BEFORE = re.compile(
    r"(?:USD|US\$|\$|EUR|\u20ac|SGD|AUD|GBP|\u00a3|CHF|JPY|CNY|"
    r"dollars?|dolar\w*|dollari|euros?|eur[oi]|"
    r"\u0434\u043e\u043b\u043b\w*|\u0435\u0432\u0440\w*)\s*$",
    re.IGNORECASE,
)


def _non_rupiah_currency(line, match):
    """True when a currency other than the rupiah owns this figure."""
    if re.search(r"(?:IDR|Rp|rupiah|roupies|\u0440\u0443\u043f\u0438\u0439)", match.group(0), re.IGNORECASE):
        return False
    return bool(_CURRENCY_BEFORE.search(line[max(0, match.start() - 24):match.start()]))


# EVERY occurrence of the superseded threshold is a defect. A line that names it IN
# ORDER TO RETIRE IT is acquitted only by being listed, by hand, in the allowlist below.
#
# The earlier design acquitted any occurrence whose clause carried a supersession marker,
# and the POST refuter defeated it twice in two rounds: `E33 requires IDR 2 billion and
# no longer requires a sponsor` was acquitted (the retirement governs the SPONSOR), while
# `For E33, IDR 2 billion, the old threshold, is no longer required` was convicted (an
# apposition separated the amount from the words retiring it). Over-match and under-match
# from one heuristic — cicatrix #3. A marker near an amount says nothing about that
# amount, so no marker acquits anything any more.
ALLOWLIST_PATH = "research/secondhome/superseded-threshold-allowlist.json"


def normalise(line):
    """The text an allowlist key is taken over: no leading/trailing space, one space
    between words, lowercased. Rewrite the line and the key rotates — which is the
    point: the allowance is reviewed again instead of surviving the edit."""
    return " ".join(line.split()).lower()


def allowlist_key(line):
    return hashlib.sha256(normalise(line).encode("utf-8")).hexdigest()


def load_allowlist(path=ALLOWLIST_PATH):
    """{(file, key): reason}. Absent file = empty allowlist, which is the strict end."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {}
    return {(e["file"], e["key"]): e.get("reason", "") for e in data.get("entries", [])}


ALLOWLIST = load_allowlist()


def is_allowed(path, line):
    return (path, allowlist_key(line)) in ALLOWLIST


def stale_allowlist_entries(paths):
    """Entries claiming a line that no longer carries the threshold. A stale allowance is
    a FAILURE: it is an allowance nobody re-read, and the ratchet it copies rejects one
    for the same reason."""
    live = set()
    for path in paths:
        try:
            lines = open(path, encoding="utf-8").read().split("\n")
        except FileNotFoundError:
            continue
        for line in lines:
            if any(not _non_rupiah_currency(line, m) for m in THRESHOLD.finditer(line)):
                live.add((path, allowlist_key(line)))
    return sorted(set(ALLOWLIST) - live)


# E33E/E33F/E33G are DIFFERENT products with different thresholds: `\bE33\b` matches
# the base code only, never the senior or remote-worker routes.
PRODUCT = re.compile(r"second\s*home|rumah\s*kedua|\bSHV\b|\bE33\b", re.IGNORECASE)

LOCALES = ("", ".it", ".id", ".ru", ".fr")
FAMILY = [
    f"apps/mouth/src/content/articles/immigration/second-home-visa-indonesia{s}.mdx"
    for s in LOCALES
]

# What each locale must SAY (the cure), and must NOT say (the contradiction).
# Deliberately short: each entry is a claim the fact registry settles.
# Ruling 4 of shweb-imp-w3-round2-rulings, verified against the official page by this
# session (HTTP 200 through the kanwilpapuabarat service-proxy, 2026-09-12): the list
# titles E33 "Special Residency Visa" and the Second Home name comes from the
# classification decree. Every locale carries the naming sentence and the canonical URL.
REQUIRED_EVERYWHERE = [
    "Special Residency Visa",
    "M.IP-08.GR.01.01/2025",
    "imigrasi.go.id/wna/daftar-visa-indonesia/E33",
]
REQUIRED = {
    "": ["6 (six) months", "USD 130,000", "own name", "state-owned (BUMN)", "USD 1,000,000", "completed apartment or strata unit", "Pasal 113", "entry window stated on the approval letter", "not settled in public regulation", "stay permit of up to 5 years", "held jointly", "first grant is 5 years or more"],
    ".it": ["6 (sei) mesi", "USD 130.000", "a nome del richiedente", "banca statale (BUMN)", "USD 1.000.000", "unità strata già ultimata", "Pasal 113", "finestra d'ingresso indicata sulla lettera", "non è fissato da una norma pubblica", "soggiorno fino a 5 anni", "conto cointestato", "prima concessione è di 5 anni o più"],
    ".id": ["6 (enam) bulan", "USD 130.000", "atas nama pemohon sendiri", "bank milik negara (BUMN)", "USD 1.000.000", "unit strata yang sudah selesai dibangun", "Pasal 113", "jendela waktu masuk yang tertera", "belum diatur secara publik", "izin tinggal hingga 5 tahun", "rekening bersama", "pemberian pertama 5 tahun atau lebih"],
    ".ru": ["6 (\u0448\u0435\u0441\u0442\u0438) \u043c\u0435\u0441\u044f\u0446\u0435\u0432", "USD 130 000", "на собственное имя", "(BUMN)", "USD 1 000 000", "strata-юнита", "Pasal 113", "в пределах срока, указанного в письме", "публичной нормой не установлено", "пребывание сроком до 5 лет", "совместный счёт", "первая выдача на 5 лет и более"],
    ".fr": ["6 (six) mois", "130 000 USD", "au nom propre du demandeur", "banque publique (BUMN)", "1 000 000 USD", "lot en copropriété (rumah susun) déjà achevé", "Pasal 113", "fenêtre d'entrée indiquée sur la lettre", "n'est pas fixé par un texte public", "jusqu'à 5 ans", "compte joint", "première délivrance est de 5 ans ou plus"],
}
# Contradictions the amount check is blind to. `Hak Pakai` and `PT PMA` are barred as
# ELIGIBLE-TITLE claims: `e33_base_property_title_type` is an `unknown` fact, so naming
# any qualifying title resolves it by assertion. The fee patterns catch the decomposed
# cost table the 2026-07-23 owner ruling forbids.
#
# These are UNCONDITIONAL. An UNCERTAIN-marker acquittal used to exempt a title named
# inside a hedged sentence, and the POST refuter round 2 (finding 7) walked through it
# with `Hak Pakai qualifies for E33 and the processing time remains unknown` — the hedge
# governed the PROCESSING TIME and acquitted the title anyway. Same defect as the
# supersession marker, same cure: the corpus does not need to name a title in order to
# say the title is unknown, and if a future line genuinely does, it is allowlisted by
# hand like any other exception.
FORBIDDEN = [
    (r"Hak Pakai", "names a qualifying property title; e33_base_property_title_type is `unknown`"),
    (r"Sertifikat Hak Milik Satuan Rumah Susun", "same — names a certificate as the qualifying title"),
    (r"PT PMA .{0,40}(shareholder|azionista|pemegang saham|actionnaire|\u0430\u043a\u0446\u0438\u043e\u043d\u0435\u0440)", "PT PMA majority holding as an E33 property route: no registry fact"),
    (r"(3[.,]000[.,]000|3 000 000)\s*-\s*(5[.,]000[.,]000|5 000 000)", "an invented government/renewal fee range"),
    (r"(varies by province|varia da provincia|berbeda-beda per provinsi|varie selon la province|\u0440\u0430\u0437\u043b\u0438\u0447\u0430\u044e\u0442\u0441\u044f \u043f\u043e \u043f\u0440\u043e\u0432\u0438\u043d\u0446\u0438\u044f\u043c)", "a province-varying property threshold; the requirement is USD 1,000,000"),
    (r"(Costs Breakdown|Dettaglio dei Costi|Rincian Biaya|\u0420\u0430\u0441\u043f\u0440\u0435\u0434\u0435\u043b\u0435\u043d\u0438\u0435 \u0437\u0430\u0442\u0440\u0430\u0442|R\u00e9partition des co\u00fbts)", "the decomposed cost table"),
    # Added 2026-09-12 after the cross-family review: the English source had been cured of
    # both of these and the four translations had not, so each translated file contradicted
    # its OWN FAQ. A per-locale check is the only thing that catches a cure applied to 1 of 5.
    (r"\b90\s*(days|giorni|hari|\u0434\u043d\u0435\u0439|jours)\b", "asserts a 90-day entry window; `entry_window_90d_and_force_majeure` is `pending`"),
    (r"(SHV|E33)[^\n]{0,80}(does not count|non conta|tidak dihitung|\u043d\u0435 \u0443\u0447\u0438\u0442\u044b\u0432\u0430\u0435\u0442\u0441\u044f|ne compte pas)", "asserts how E33 time counts toward KITAP; `itap_after_3y_criteria` is `unknown` and marketing it is forbidden"),
]

# The formulations this mandate REMOVED, in every locale. Restoring one has to turn the
# probe red, and until now it did not: the POST refuter round 2 (finding 11) put
# `verification with BPN records` back in all five files and `--claims` still printed
# zero, because REQUIRED is satisfied file-wide by strings that live somewhere else
# entirely. A cure that cannot be regressed is a cure nobody is guarding. Each pattern
# below was checked twice: present in the base commit 70b43c5459, absent from the cured
# tree.
REMOVED_EVERYWHERE = [
    (r"\bBPN\b", "immigration validating property against BPN records — the method is not published"),
    (r"14\s*-\s*30", "the 14-30 working-day processing estimate: no source"),
    (r"(?:(?:IDR|Rp)\s*5[.,\s]000[.,\s]000|5[.,\s]000[.,\s]000\s*(?:IDR|Rp))(?![-\u2013\u2014\s]*\d)", "the IDR 5,000,000 Wajib Lapor fine: no source for the amount"),
    # Imperator ruling 1 of shweb-imp-w3-round2-rulings: a day range in a stage heading is
    # a working-day estimate wearing a title, and it is decidable at no cost.
    # Removed in the successor round (imperator ruling 3 of shweb-imp-w3-round2-rulings):
    # the figure goes, the obligation stays, because none of the three had a verbatim
    # official source and the article ships under a gate that reads "content vs registry
    # PASS". The 31 March filing date is here for the same reason — pajak.go.id answered
    # 403/404 when this session tried to source it (measured 2026-09-12).
    # 14 days is NOT here: the published Dukcapil procedure states it verbatim ("wajib
    # melaporkan ... paling lambat 14 hari sejak diterbitkan ITAS"), fetched HTTP 200 on
    # 2026-09-12, so the figure has a source and stays in the article. Only the Wajib Lapor
    # 7-day window remains unsourced.
    (r"(?:within|entro|dalam waktu|\u0432 \u0442\u0435\u0447\u0435\u043d\u0438\u0435|dans les)\s+7\s+(?:days|giorni|hari|\u0434\u043d\u0435\u0439|jours)", "the 7-day Wajib Lapor deadline: no verbatim source"),
    (r"2\s*(?:[-\u2013]|\u00e0)\s*6\s*(?:weeks|settimane|minggu|\u043d\u0435\u0434\u0435\u043b\u044c|semaines)", "the 2-6 week apostille estimate: no source"),
    (r"31\s*(?:March|marzo|Maret|\u043c\u0430\u0440\u0442\u0430|mars)", "the 31 March filing date: no verbatim official source could be fetched"),
    (r"(?m)^#{1,6}[^\n]*\(\s*\d+\s*[-\u2013]\s*\d+\s*(?:Days|Hari Kerja|Hari|Working Days|jours ouvr\u00e9s|jours|\u0434\u043d\u0435\u0439|\u0440\u0430\u0431\u043e\u0447\u0438\u0445 \u0434\u043d\u0435\u0439|Giorni Lavorativi|Giorni)\s*\)", "a day range inside a stage heading: an unsourced processing estimate"),
]
REMOVED = {
    "": ["What counts as proof", "60 months", "grants a 5-year stay permit", "single account or combined across multiple accounts", "stamps passport with 5-year stay permit", "Total first year"],
    ".it": ["Cosa conta come prova", "60 mesi", "concede un permesso di soggiorno di 5 anni", "un unico conto o combinati tra pi\u00f9 conti", "Totale primo anno", "Nota importante sulla propriet\u00e0"],
    ".id": ["Apa yang dihitung sebagai bukti", "60 bulan", "memberikan izin tinggal selama 5 tahun", "Proses Perbaruan", "Total tahun pertama", "Badan Pertanahan Nasional"],
    ".ru": ["\u0427\u0442\u043e \u0441\u0447\u0438\u0442\u0430\u0435\u0442\u0441\u044f \u0434\u043e\u043a\u0430\u0437\u0430\u0442\u0435\u043b\u044c\u0441\u0442\u0432\u043e\u043c", "60 \u043c\u0435\u0441\u044f\u0446\u0435\u0432", "\u0440\u0430\u0437\u0440\u0435\u0448\u0435\u043d\u0438\u0435 \u043d\u0430 \u043f\u0440\u0435\u0431\u044b\u0432\u0430\u043d\u0438\u0435 \u0441\u0440\u043e\u043a\u043e\u043c \u043d\u0430 5 \u043b\u0435\u0442", "\u0412\u0430\u0436\u043d\u043e\u0435 \u043f\u0440\u0438\u043c\u0435\u0447\u0430\u043d\u0438\u0435 \u043e \u0432\u043b\u0430\u0434\u0435\u043d\u0438\u0438 \u043d\u0435\u0434\u0432\u0438\u0436\u0438\u043c\u043e\u0441\u0442\u044c\u044e", "\u0418\u0442\u043e\u0433\u043e \u0437\u0430 \u043f\u0435\u0440\u0432\u044b\u0439 \u0433\u043e\u0434", "14-30 \u0440\u0430\u0431\u043e\u0447\u0438\u0445 \u0434\u043d\u0435\u0439"],
    ".fr": ["Ce qui compte comme preuve", "60 mois", "accorde un permis de s\u00e9jour de 5 ans", "un seul compte ou combin\u00e9s", "Total premi\u00e8re ann\u00e9e", "Note importante sur la propri\u00e9t\u00e9 immobili\u00e8re"],
}

# REQUIRED is file-wide and that is its limit: it proves the corpus says a thing SOMEWHERE.
# These anchor a claim to the FIELD or the TABLE ROW that has to carry it, which is what
# finding 11 showed was missing — restore the old Duration cell and a file-wide "up to 5
# years" elsewhere still satisfies the check. (anchor regex, needle, what it guards.)
_DURATION = r"(?m)^\|\s*\*\*(?:Duration|Durata|Durasi|\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c|Dur\u00e9e)\*\*[^\n]*$"
_RENEWAL = r"(?m)^\|\s*\*\*(?:Renewal|Rinnovo|Perpanjangan|\u041f\u0440\u043e\u0434\u043b\u0435\u043d\u0438\u0435|Renouvellement)\*\*[^\n]*$"
_META = (
    ("description", r"(?m)^description:[^\n]*$"),
    ("excerpt", r"(?m)^excerpt:[^\n]*$"),
    ("seoDescription", r"(?m)^seoDescription:[^\n]*$"),
    ("answerSnippet", r"(?m)^\s*answerSnippet:[^\n]*$"),
)
# (duration cell needle, own-name needle, completed-unit needle) per locale.
_ANCHOR_NEEDLES = {
    "": ("Up to 5 years", "own name", "completed"),
    ".it": ("Fino a 5 anni", "proprio nome", "ultimat"),
    ".id": ("Hingga 5 tahun", "atas nama", "selesai dibangun"),
    # Russian says the same condition two ways and both are native: a strata unit that is
    # `\u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d\u043d\u044b\u0439` (completed) and an apartment that is `\u0433\u043e\u0442\u043e\u0432\u0430\u044f` (ready). The anchor accepts
    # either FORM but still demands the CONDITION, in that field.
    ".ru": ("\u0414\u043e 5 \u043b\u0435\u0442", "\u0441\u043e\u0431\u0441\u0442\u0432\u0435\u043d\u043d\u043e\u0435 \u0438\u043c\u044f", ("\u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d\u043d", "\u0433\u043e\u0442\u043e\u0432")),
    ".fr": ("Jusqu", "nom", "achev\u00e9"),
}


def anchored_checks(suffix):
    """[(anchor regex, needle, what it guards)] for one locale."""
    duration, own_name, completed = _ANCHOR_NEEDLES[suffix]
    checks = [
        (_DURATION, duration, "the comparison table's Duration cell"),
        (_RENEWAL, "Pasal 113", "the comparison table's Renewal cell"),
    ]
    for name, field in _META:
        checks.append((field, own_name, f"the {name} metadata field (own-name condition)"))
        checks.append((field, completed, f"the {name} metadata field (completed-unit condition)"))
    return checks


def offending_match(line, require_product=True, path=None):
    """The first match on `line` that is a live claim, or None.

    Three things disqualify a match, and every one of them is decidable: the line is
    about another product (when `require_product`), a non-rupiah currency owns the
    figure, or the line is listed in the allowlist FOR THIS FILE. Nothing is acquitted
    by a word standing near it any more.
    """
    if require_product and not PRODUCT.search(line):
        return None
    if path is not None and is_allowed(path, line):
        return None
    for match in THRESHOLD.finditer(line):
        if not _non_rupiah_currency(line, match):
            return match
    return None


def scan(path, require_product=True):
    """Offending (line_number, text) pairs in `path`."""
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    return [
        (n, line)
        for n, line in enumerate(lines, 1)
        if offending_match(line, require_product, path) is not None
    ]


def run_cooccurrence(paths, require_product):
    total = 0
    for path in paths:
        hits = scan(path, require_product)
        total += len(hits)
        print(f"{len(hits):4d}  {path}")
        for n, line in hits:
            print(f"        {n}: {line.strip()[:140]}")
    kind = "second-home lines" if require_product else "amount occurrences"
    print(f"TOTAL {kind} carrying the superseded threshold: {total}")
    return 1 if total else 0


def run_attribution(paths, window=40):
    """Attribute every amount hit to the nearest product mention ABOVE it.

    The line-scoped co-occurrence check has a measured blind spot: in a comparison
    table the product is the COLUMN HEADER and the amount is a body row, and in a
    document checklist the product is a section heading. Three families were
    classified "not an E33 claim" by the line check and turned out to be E33 claims
    exactly that way (e311a-retirement-visa-kitas-guide, indonesia-visa-timeline-comparison,
    kitas-for-digital-nomads-reality, measured 2026-09-12). This mode prints the
    evidence a human classifies from; it never classifies by itself.
    """
    for path in paths:
        lines = open(path, encoding="utf-8").read().split("\n")
        hits = [(n, l) for n, l in enumerate(lines, 1) if THRESHOLD.search(l)]
        if not hits:
            continue
        print(f"=== {path}")
        for n, line in hits:
            context = None
            for back in range(n - 1, max(0, n - 1 - window), -1):
                if PRODUCT.search(lines[back - 1]):
                    context = (back, lines[back - 1].strip()[:110])
                    break
            print(f"  {n}: {line.strip()[:120]}")
            print(f"      nearest product mention: {context if context else 'NONE within %d lines' % window}")
    return 0


def run_claims():
    """Every locale must carry the cure, in the PLACE that has to carry it, and must
    carry none of the contradictions or of the formulations this mandate removed."""
    failures = 0
    for suffix, path in zip(LOCALES, FAMILY):
        before = failures
        text = open(path, encoding="utf-8").read()
        # The amount check runs HERE too, not only under --sources. A mutation that put
        # `E33 no longer requires IDR 2 billion` back into the English source left
        # --claims green, because the two halves of this probe were two commands and
        # nobody runs both (measured 2026-09-12, successor session). One command now
        # answers for the whole family.
        for number, line in scan(path, require_product=False):
            print(f"THRESHOLD  {path}:{number}: {line.strip()[:120]}")
            failures += 1
        for needle in REQUIRED[suffix] + REQUIRED_EVERYWHERE:
            if needle not in text:
                print(f"MISSING  {path}: {needle!r}")
                failures += 1
        for anchor, needle, what in anchored_checks(suffix):
            rows = re.findall(anchor, text)
            if not rows:
                print(f"NO ANCHOR  {path}: {what} not found at all")
                failures += 1
                continue
            forms = (needle,) if isinstance(needle, str) else needle
            for row in rows:
                if not any(f.lower() in row.lower() for f in forms):
                    print(f"UNANCHORED  {path}: {what} does not carry {needle!r}")
                    print(f"            {row.strip()[:150]}")
                    failures += 1
        for pattern, why in FORBIDDEN + REMOVED_EVERYWHERE:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                print(f"PRESENT  {path}: {match.group(0).strip()[:70]!r} — {why}")
                failures += 1
        for literal in REMOVED[suffix]:
            if literal.lower() in text.lower():
                print(f"RESTORED  {path}: {literal!r} — a formulation this mandate removed")
                failures += 1
        print(f"{'ok  ' if failures == before else 'FAIL'}  {path}")
    stale = stale_allowlist_entries(FAMILY)
    for path, key in stale:
        print(f"STALE ALLOWANCE  {path}: {key[:16]}… claims a line that no longer carries the threshold")
        failures += 1
    print(f"TOTAL claim failures: {failures}")
    return 1 if failures else 0


def run_selftest():
    """The probe's own guilt and innocence cases. Innocence matters as much here:
    a probe that flags another product's figure is what produces a blind sweep."""
    guilt = [
        "IDR 2B", "IDR 2 billion", "Rp 2 miliar", "IDR 2Miliar", "2 \u043c\u043b\u0440\u0434 IDR",
        "2 milliards IDR", "2 miliardi di IDR", "IDR 2.000.000.000",
        "IDR 2 000 000 000", "2 \u00e0 5 milliards IDR", "IDR 2B-5B", "two billion rupiah",
        "due miliardi", "deux milliards", "\u0434\u0432\u0430 \u043c\u0438\u043b\u043b\u0438\u0430\u0440\u0434\u0430", "Rp2M",
        # POST-refuter 2026-09-12: both were MISSED. Nine zeros with no separator at
        # all, and the amount-before-currency order Italian and Indonesian prose use.
        "IDR 2000000000", "Rp2000000000",
        "2.000.000.000 IDR", "2 000 000 000 IDR", "2.000.000.000 rupiah",
        # POST-refuter round 2, finding 4: the old trailing guard read the NEXT number,
        # and the amount's own decimals, as a continuation of the figure.
        "E33 requires IDR 2,000,000,000, 2 passport photos and insurance.",
        "E33 requires IDR 2.000.000.000,00.",
        "Rp 2.000.000.000,50 disebut dalam dokumen lama.",
    ]
    innocence = [
        "IDR 20B", "IDR 2.5 billion", "USD 350K+ investment", "Above IDR 5B",
        "IDR 500M - IDR 5B", "IDR 2,000,000 fine",
        # POST-refuter 2026-09-12: convicted on its own PREFIX. A trillion is not the
        # superseded threshold, and a guard that cannot tell them apart measures nothing.
        "IDR 2,000,000,000,000", "IDR 2.000.000.000.000", "Rp 2000000000000",
    ]
    # The ENTITY is amount+currency. Two billion of something that is not the rupiah is
    # not the superseded threshold, and is acquitted by the currency it names — not by a
    # word standing near it (POST-refuter round 2, finding 5).
    other_currency = [
        "E33 applicants may own USD 2 billion.",
        "A portfolio of \u20ac 2 billion does not qualify.",
        "Un patrimonio di USD 2 miliardi non basta.",
    ]
    # No marker acquits anything: a line that retires the figure is still CONVICTED, and
    # the allowlist is the only way out. This is the round-2 ruling of the imperator, and
    # the fourth case is the apposition the refuter used to defeat the old clause window.
    retired_but_convicted = [
        "E33 no longer requires IDR 2 billion.",
        "IDR 2 miliar \u00e8 la cifra superata: oggi la soglia \u00e8 USD 130.000.",
        "IDR 2 miliar adalah angka lama sebelum 2024.",
        "Le seuil de 2 milliards IDR est obsol\u00e8te.",
        "For E33, IDR 2 billion, the old threshold, is no longer required.",
    ]
    live_claims = [
        # The evasion routes of both refuter rounds. Each was acquitted once.
        "You do not need a sponsor, you need IDR 2 billion in the bank.",
        "E33 requires IDR 2,000,000,000 in savings.",
        "The old figure was USD 100,000. E33 requires IDR 2 billion today.",
        "The rules used to be simpler, but today the Second Home Visa still requires "
        "IDR 2 billion in the bank.",
        "IDR 2 billion is the old figure; the Second Home Visa requires IDR 2 billion.",
        # POST-refuter round 2, finding 6: the retirement governs the SPONSOR, and the
        # financial requirement is asserted as current. The marker acquitted it anyway.
        "E33 requires IDR 2 billion and no longer requires a sponsor.",
    ]
    # A named qualifying title is a defect however the sentence is hedged: the hedge in
    # the last case governs the processing time (POST-refuter round 2, finding 7).
    title_guilty = [
        "The qualifying title for the E33 property route is Hak Pakai.",
        "Gunakan Sertifikat Hak Milik Satuan Rumah Susun sebagai alas hak yang memenuhi syarat.",
        "The bank letter format is not confirmed, but the qualifying title for the E33 "
        "property route is Hak Pakai.",
        "The processing time remains unknown! Hak Pakai qualifies for E33.",
        "Hak Pakai qualifies for E33 and the processing time remains unknown.",
        "Whether Hak Pakai qualifies for E33 remains unknown.",
    ]
    product_yes = ["Second Home Visa", "Visa Rumah Kedua", "the SHV", "E33 requires it"]
    product_no = ["E33E senior route", "E33G remote worker", "KITAP holders"]
    bad = 0
    for s in guilt:
        if not THRESHOLD.search(s):
            print(f"GUILT MISSED: {s!r}"); bad += 1
    for s in innocence:
        if THRESHOLD.search(s):
            print(f"INNOCENCE FLAGGED: {s!r}"); bad += 1
    for s in product_yes:
        if not PRODUCT.search(s):
            print(f"PRODUCT MISSED: {s!r}"); bad += 1
    for s in product_no:
        if PRODUCT.search(s):
            print(f"PRODUCT OVER-MATCHED: {s!r}"); bad += 1
    for s in other_currency:
        if offending_match(s, require_product=False) is not None:
            print(f"OTHER-CURRENCY CONVICTED: {s!r}"); bad += 1
    for s in retired_but_convicted + live_claims:
        if offending_match(s, require_product=False) is None:
            print(f"THRESHOLD ACQUITTED WITHOUT AN ALLOWANCE: {s!r}"); bad += 1
    for s in title_guilty:
        if not any(re.search(p, s, re.IGNORECASE) for p, _ in FORBIDDEN):
            print(f"ASSERTED-TITLE ACQUITTED: {s!r}"); bad += 1

    # The allowlist is the ONLY acquittal, and it is exercised here rather than asserted:
    # the same sentence is convicted, then allowed for ONE file, then shown stale when the
    # line it claims is gone.
    global ALLOWLIST
    saved = ALLOWLIST
    sentence = retired_but_convicted[0]
    fake = "some/file.mdx"
    try:
        ALLOWLIST = {(fake, allowlist_key(sentence)): "test"}
        if offending_match(sentence, require_product=False, path=fake) is not None:
            print("ALLOWLISTED LINE STILL CONVICTED"); bad += 1
        if offending_match(sentence, require_product=False, path="other/file.mdx") is None:
            print("ALLOWANCE LEAKED TO ANOTHER FILE"); bad += 1
        if offending_match(sentence + " Extra words.", require_product=False, path=fake) is None:
            print("ALLOWANCE SURVIVED A REWRITE OF ITS OWN LINE"); bad += 1
        if not stale_allowlist_entries([]):
            print("STALE ALLOWANCE NOT REPORTED"); bad += 1
        ALLOWLIST = {}
        if offending_match(sentence, require_product=False, path=fake) is None:
            print("EMPTY ALLOWLIST STILL ACQUITTED"); bad += 1
    finally:
        ALLOWLIST = saved

    print(f"selftest failures: {bad}")
    return 1 if bad else 0


def main(argv):
    if argv == ["--selftest"]:
        return run_selftest()
    if argv[:1] == ["--allowlist-key"] and len(argv) == 2:
        print(allowlist_key(argv[1]))
        return 0
    if argv[:1] == ["--attribute"]:
        return run_attribution(argv[1:] or FAMILY)
    if argv == ["--claims"]:
        return run_claims()
    if argv == ["--sources"]:
        # Inside this family every amount is about this product, and the listing below
        # is printed so that premise is auditable rather than assumed.
        return run_cooccurrence(FAMILY, require_product=False)
    if not argv:
        print(__doc__)
        return 2
    return run_cooccurrence(argv, require_product=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
