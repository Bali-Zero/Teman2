"""GARUDA VOA — nationality eligibility dataset (pure, no I/O).

Closes the gap `intake.py` previously left open: `_build_eligibility_input`
hardcoded ``nationality_entry_eligible=True`` for every request because, in
that module's own words, "no nationality-eligibility dataset yet [existed]".
This module IS that dataset — a decree-sourced, independently-verified list
of the ISO 3166-1 alpha-3 nationalities eligible for a Visa on Arrival.

Provenance — every code below is traceable to ONE decree, and was retrieved
and cross-checked by TWO independent, non-overlapping methods in the same
session with ZERO divergence on any entry:

    KEPUTUSAN MENTERI HUKUM DAN HAK ASASI MANUSIA REPUBLIK INDONESIA NOMOR
    M.HH-02.GR.01.06 TAHUN 2024 tentang Daftar Negara, Pemerintah Dari
    Daerah Administrasi Khusus Suatu Negara, Dan Entitas Tertentu Yang
    Warga Negaranya Dapat Diberikan Visa Kunjungan Saat Kedatangan (Visa on
    Arrival) — "Daftar Negara Subjek Visa on Arrival".

    Primary source (live page, retrieved 2026-08-23):
    https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-subjek-visa-on-arrival
    ("Daftar Subjek Visa on Arrival" tab). Retrieved via a DIRECT PARSE of
    the page's raw HTML (`curl` + regex over the `<ol><li><span>...</span>
    </li></ol>` list) — not an LLM summary of the rendered page — yielding
    97 entries, numbered 1-97, "Afrika Selatan" through "Yunani", in the
    exact printed order.

    Corroborated (2026-08-23, same session) against an independent
    Google-grounded research pass over the same URL, produced before the
    direct-parse retrieval and without sight of it: 97/97 country names
    matched, in the same order, ZERO divergence.

    ISO 3166-1 alpha-3 codes for each Indonesian country name were then
    verified against the standard ISO 3166-1 reference table
    (github.com/lukes/ISO-3166-Countries-with-Regional-Codes, `all/all.csv`,
    249 rows) by resolving each candidate alpha-3 code back to its official
    English short name and confirming that name semantically matches the
    Indonesian name printed on the source page — e.g. "Tiongkok" -> `CHN`
    "China", "Hongkong" -> `HKG` "Hong Kong", "Inggris" -> `GBR` "United
    Kingdom of Great Britain and Northern Ireland", "Vatikan" -> `VAT`
    "Holy See". 97/97 codes resolved with a matching name. ZERO mismatches,
    ZERO entries left unresolved — so this dataset carries no invented code.

    COUNT = 97. `TestNonVacuity.test_count_matches_verified_count`
    (test_nationality_eligibility.py) pins this so a future edit that
    silently empties, truncates, or over-extends the set fails loudly
    instead of quietly changing who gets a VOA.

Unknown-code decision (2026-08-23, this module) — matching
`operating_calendar.py`'s fail-closed, never-guess house style, but landing
on a DIFFERENT answer for a structural reason stated here explicitly:

    `operating_calendar.py` distinguishes "too soon" (a confident decline)
    from `ARRIVAL_DATE_UNCONFIRMED` ("cannot compute without guessing") because
    its underlying data genuinely has a coverage boundary — the 2027 Cuti
    Bersama decree does not exist yet, so a 2027 date is a real unknown, not
    a decline in disguise.

    This dataset has NO equivalent boundary. The decree above is a POSITIVE,
    CLOSED enumeration — it names WHO is eligible, exhaustively, as of
    RETRIEVED_ON. Consequently a nationality code that is absent from
    `VOA_ELIGIBLE_NATIONALITIES` is NOT VOA-eligible with full confidence,
    regardless of WHY it is absent: whether the code names a real country
    the decree simply does not list (e.g. `AFG`), or is not a recognized
    ISO 3166-1 country code at all (upstream, the only production caller —
    `internal_preview_cli.InternalPreviewRequest` — already constrains the
    field to `^[A-Za-z]{3}$` before it ever reaches this module, so the
    latter case is limited to unassigned 3-letter combinations like `ZZZ`).
    Both cases resolve to the SAME true, non-misleading reason text already
    carried by `eligibility.DeclineCode.NATIONALITY_NOT_ELIGIBLE` —
    "nationality or entry point not eligible for VOA" — which holds
    whether or not the code names a real country. Introducing a second,
    ~249-entry all-of-ISO-3166-1 reference purely to relabel that outcome
    would add unrelated-to-VOA surface without changing the decision (still
    DECLINE; still hands off to the ordinary channel per the SOP amendment
    referenced in `intake.py` — never a bare no), so this module
    deliberately does not carry one. `is_voa_eligible_nationality` therefore
    never raises and never returns a third state: it is a total function
    from any string to a bool.

⚠️ A future amending decree could add or remove a country. On amendment,
re-source this list the same way (direct parse + independent cross-check,
both dated) — never hand-edit an entry without updating `RETRIEVED_ON` and
`COUNT` together, and never carry forward a stale count.

PURE — no I/O, no network call at import or call time. The fetch above was
a one-time, out-of-band research step, not a runtime dependency.
"""

from __future__ import annotations

DECREE: str = (
    "Keputusan Menteri Hukum dan Hak Asasi Manusia Republik Indonesia "
    "Nomor M.HH-02.GR.01.06 Tahun 2024"
)
SOURCE_URL: str = (
    "https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/"
    "daftar-negara-subjek-visa-on-arrival"
)
RETRIEVED_ON: str = "2026-08-23"
COUNT: int = 97

# The one and only place a VOA-eligible nationality may be added or removed
# — see the module docstring for provenance and the re-sourcing rule on
# amendment. Alphabetical by ISO 3166-1 alpha-3 code; the Indonesian name
# from the source page is kept as an inline comment for auditability.
VOA_ELIGIBLE_NATIONALITIES: frozenset[str] = frozenset(
    {
        "ALB",  # Albania
        "AND",  # Andorra
        "ARE",  # Uni Emirat Arab
        "ARG",  # Argentina
        "ARM",  # Armenia
        "AUS",  # Australia
        "AUT",  # Austria
        "AZE",  # Azerbaijan
        "BEL",  # Belgia
        "BGR",  # Bulgaria
        "BHR",  # Bahrain
        "BIH",  # Bosnia Herzegovina
        "BLR",  # Belarus
        "BRA",  # Brazil
        "BRN",  # Brunei Darussalam
        "CAN",  # Kanada
        "CHE",  # Swiss
        "CHL",  # Chile
        "CHN",  # Tiongkok
        "COL",  # Kolombia
        "CYP",  # Siprus
        "CZE",  # Ceko
        "DEU",  # Jerman
        "DNK",  # Denmark
        "ECU",  # Ekuador
        "EGY",  # Mesir
        "ESP",  # Spanyol
        "EST",  # Estonia
        "FIN",  # Finlandia
        "FRA",  # Perancis
        "GBR",  # Inggris
        "GRC",  # Yunani
        "GTM",  # Guatemala
        "HKG",  # Hongkong
        "HRV",  # Kroasia
        "HUN",  # Hungaria
        "IND",  # India
        "IRL",  # Irlandia
        "ISL",  # Islandia
        "ITA",  # Italia
        "JOR",  # Yordania
        "JPN",  # Jepang
        "KAZ",  # Kazakhstan
        "KEN",  # Kenya
        "KHM",  # Kamboja
        "KOR",  # Korea Selatan
        "KWT",  # Kuwait
        "LAO",  # Laos
        "LIE",  # Liechtenstein
        "LTU",  # Lithuania
        "LUX",  # Luksemburg
        "LVA",  # Latvia
        "MAR",  # Maroko
        "MCO",  # Monako
        "MDV",  # Maladewa
        "MEX",  # Meksiko
        "MLT",  # Malta
        "MMR",  # Myanmar
        "MNG",  # Mongolia
        "MOZ",  # Mozambik
        "MUS",  # Mauritius
        "MYS",  # Malaysia
        "NLD",  # Belanda
        "NOR",  # Norwegia
        "NZL",  # Selandia Baru
        "OMN",  # Oman
        "PER",  # Peru
        "PHL",  # Filipina
        "PNG",  # Papua Nugini
        "POL",  # Polandia
        "PRT",  # Portugal
        "PSE",  # Palestina
        "QAT",  # Qatar
        "ROU",  # Rumania
        "RUS",  # Rusia
        "RWA",  # Rwanda
        "SAU",  # Arab Saudi
        "SGP",  # Singapura
        "SRB",  # Serbia
        "SUR",  # Suriname
        "SVK",  # Slovakia
        "SVN",  # Slovenia
        "SWE",  # Swedia
        "SYC",  # Seychelles
        "THA",  # Thailand
        "TLS",  # Timor Leste
        "TUN",  # Tunisia
        "TUR",  # Turki
        "TWN",  # Taiwan
        "TZA",  # Tanzania
        "UKR",  # Ukraina
        "USA",  # Amerika Serikat
        "UZB",  # Uzbekistan
        "VAT",  # Vatikan
        "VEN",  # Venezuela
        "VNM",  # Vietnam
        "ZAF",  # Afrika Selatan
    }
)


def is_voa_eligible_nationality(nationality: str) -> bool:
    """Case-insensitive VOA-eligibility membership check.

    Total function: never raises, never returns a third state — see the
    module docstring's "Unknown-code decision" for why absence (whatever
    its cause) is always a confident, non-guessed ``False`` here, unlike
    `operating_calendar.last_open_day_before`'s genuine ``None`` case.
    """
    return nationality.strip().upper() in VOA_ELIGIBLE_NATIONALITIES


__all__ = [
    "COUNT",
    "DECREE",
    "RETRIEVED_ON",
    "SOURCE_URL",
    "VOA_ELIGIBLE_NATIONALITIES",
    "is_voa_eligible_nationality",
]
