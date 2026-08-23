"""Deterministic, Faker-free synthetic PII corpus for the G-P3 DLP
recall-floor test (`test_wa_dlp.py::test_recall_floor`).

Every literal here is FABRICATED and deterministic (no random/Faker) —
formulaic generators keyed only on the loop index, so a re-run is
byte-identical. This is OUR corpus, not a sample of real customer data:
per the design spec, a miss on it means a pattern regressed, not that the
corpus was unlucky.

Each category has >=50 distinct positives, one target-category span per
item, chosen so it does NOT also satisfy a DIFFERENT category's pattern
(no cross-category collisions by construction — see the per-shape notes
below). Shapes NOT included in the 50-item corpus (NPWP old-dotted /
new-dotted, NIK label-anchored-separated, BANK_ACCOUNT IBAN, CREDENTIAL
PEM / key-prefix) get their own small guilt tests directly in
`test_wa_dlp.py` instead — kept out of this recall corpus to avoid
mixing shapes with materially different generation risk into one
average.

DECLARED LIMIT (spalla review, 2026-08-20): the recall-floor test's
"matched" count is `sum(1 for h in result.hits if h.category == category)`
— it counts HITS, and `wa_dlp`'s dedup collapses a repeated identical
value into ONE hit (spec rule 1, "same original -> same placeholder").
Every generator here already produces distinct literals per item
specifically so recall == coverage; if a FUTURE corpus edit introduces a
duplicate literal within one category's list, recall would read a false
regression (fewer hits than items) even though nothing leaked — the fix
in that case is to make the literal distinct, not to lower the floor.

G-P3 r2 ADDITION (Kimi round-2 FIX-FIRST batch): `realistic_nik_corpus`,
`realistic_passport_corpus`, `realistic_npwp_old_dotted_corpus`,
`realistic_npwp_new16_bare_corpus` and `realistic_npwp_new16_dotted_corpus`
below generate REAL-ENCODING-SHAPED (never real-VALUE) identifiers for the
r2 guilt tests in `test_wa_dlp.py` — a NIK with a genuine
province/regency/district prefix and a plausible ddmmyy DOB (day +40 for
the official female encoding), a 1-2-letter/6-7-digit passport, and both
NPWP dotted/bare-16 forms. These use a SEEDED `random.Random` instance
(never the bare `random` module's global state, never unseeded entropy)
so a re-run is byte-identical — a different generation strategy than the
formulaic index-keyed functions above, chosen because the realistic
shapes need more structural freedom than a loop index alone provides, but
held to the SAME determinism bar.

PLAINLY, for anyone editing this file: every value anywhere in this
module — formulaic or seeded-random — is FABRICATED. Reading a fixture
out of `conversations`, the CRM, `meta_inbox_*`, or any other live table
is FORBIDDEN for this file, full stop (project CLAUDE.md §14 PII
boundary) — a miss on any test built from this module must always be
traceable to a synthetic literal, never to a real customer's data.
"""

from __future__ import annotations

import random

_CORPUS_SIZE = 50


def nik_ktp_corpus(n: int = _CORPUS_SIZE) -> list[str]:
    """Bare 16-digit NIK, leading digit fixed at a real province-code
    prefix ("32") that never starts with 0 — never collides with the
    NPWP-16 shape (`\\b0\\d{15}\\b`), which is the ONE precedence case the
    design spec calls out."""
    return [f"NIK saya adalah 32{i:014d} untuk verifikasi." for i in range(n)]


def npwp_corpus(n: int = _CORPUS_SIZE) -> list[str]:
    """NPWP new-16 bare shape (`\\b0\\d{15}\\b`) only — the old-dotted and
    new-dotted shapes are covered by dedicated guilt tests instead."""
    return [f"NPWP baru saya adalah 0{i:015d} terdaftar." for i in range(n)]


def passport_corpus(n: int = _CORPUS_SIZE) -> list[str]:
    letters = ("A", "B", "C", "AB", "XY")
    return [
        f"Passport number {letters[i % len(letters)]}{1000000 + i:07d} on file."
        for i in range(n)
    ]


def bank_account_corpus(n: int = _CORPUS_SIZE) -> list[str]:
    """Label-anchored 10-digit account numbers — 10 digits never collides
    with NIK/NPWP's 16-digit shape, and never starts with 08/62 so it
    cannot be mistaken for a phone number either. IBAN shape is covered by
    a dedicated guilt test instead."""
    return [f"no rekening {1000000000 + i:010d} BCA" for i in range(n)]


def phone_corpus(n: int = _CORPUS_SIZE) -> list[str]:
    """Cycles the 4 sentry-derived phone sub-shapes. Deliberately never
    appends an `@...` suffix (no WA-JID-as-email shape) — that form is
    legitimately EMAIL-shaped too (a WA JID `...@s.whatsapp.net` satisfies
    the EMAIL pattern, and EMAIL is a higher-priority category by design),
    so testing it here would measure the wrong category."""
    out: list[str] = []
    for i in range(n):
        shape = i % 4
        if shape == 0:
            out.append(f"Call me at +62 812 {1000 + i:04d} {2000 + i:04d}")
        elif shape == 1:
            out.append(f"WA number +6281234{i:06d}")
        elif shape == 2:
            out.append(f"Nomor lokal 0812-345-{6000 + i:04d}")
        else:
            out.append(f"contact 6281234{i:06d} on whatsapp")
    return out


def email_corpus(n: int = _CORPUS_SIZE) -> list[str]:
    return [f"Hubungi client{i}@example.com untuk detail." for i in range(n)]


def credential_corpus(n: int = _CORPUS_SIZE) -> list[str]:
    """Cycles JWT and Bearer-token shapes. PEM header and vendor
    key-prefix shapes are covered by dedicated guilt tests instead."""
    out: list[str] = []
    for i in range(n):
        if i % 2 == 0:
            seg1 = f"eyJhbGciOiJIUzI1NiJ9{i:06d}"
            seg2 = f"eyJzdWIiOiJ1c2VyIn0{i:06d}"
            seg3 = f"SIGNATURE{i:06d}abcdefgh"
            out.append(f"token: {seg1}.{seg2}.{seg3}")
        else:
            out.append(f"Authorization: Bearer abcdefghij0123456789{i:04d}")
    return out


CORPUS: dict[str, list[str]] = {
    "NIK_KTP": nik_ktp_corpus(),
    "NPWP": npwp_corpus(),
    "PASSPORT": passport_corpus(),
    "BANK_ACCOUNT": bank_account_corpus(),
    "PHONE": phone_corpus(),
    "EMAIL": email_corpus(),
    "CREDENTIAL": credential_corpus(),
}

# Registered floor (spec G-P3 Tests section): "start 1.00 on the synthetic
# corpus — it is OUR corpus; a miss means a pattern regressed." ONE
# constant, read by the test — lowering it is a visible diff.
RECALL_FLOOR = 1.00


# ============================================================================
# G-P3 r2 — real-encoding-shaped synthetic generators (seeded, deterministic)
#
# Deliberately kept OUT of `CORPUS`/`RECALL_FLOOR` above: these feed
# dedicated guilt tests in test_wa_dlp.py (F1/F4 r2 batch), not the
# per-category recall-floor sweep, so a rare structural coincidence in one
# generated item (e.g. a NIK digit run that also happens to read as an
# amount) can never silently erode the registered 1.00 floor for a
# category it was never meant to test.
# ============================================================================


def realistic_nik_corpus(n: int = 20) -> list[str]:
    """16-digit NIK built from the REAL encoding, not a flat random string:
    2-digit province + 2-digit regency/city + 2-digit district (kecamatan)
    code, then a plausible date of birth as ddmmyy (day +40 on odd indices,
    the official female-encoding offset), then a 4-digit sequence number.
    Province codes are drawn from 11-94 (real range, never leading zero) so
    these can never collide with NPWP's leading-zero 16-digit shape — the
    ONE precedence case the design spec names explicitly."""
    rng = random.Random(20260822)
    out: list[str] = []
    for i in range(n):
        province = rng.randint(11, 94)
        regency = rng.randint(1, 79)
        district = rng.randint(1, 79)
        day = rng.randint(1, 28) + (40 if i % 2 == 1 else 0)
        month = rng.randint(1, 12)
        year = rng.randint(0, 99)
        seq = rng.randint(1, 9999)
        nik = (
            f"{province:02d}{regency:02d}{district:02d}"
            f"{day:02d}{month:02d}{year:02d}{seq:04d}"
        )
        out.append(f"NIK saya {nik} terdaftar di Dukcapil.")
    return out


def realistic_passport_corpus(n: int = 20) -> list[str]:
    """1-2 letter prefix + 6-7 digit passport number. Letters are chosen
    from a pool that never collides with `_PASSPORT_DECLINE_PREFIXES`, so
    these stay guilty regardless of whether the F4 context-override cure
    has landed yet."""
    rng = random.Random(20260823)
    letters_pool = ("A", "B", "C", "X", "Y", "AB", "XY", "CN", "MZ")
    out: list[str] = []
    for _ in range(n):
        letters = rng.choice(letters_pool)
        digit_len = rng.choice((6, 7))
        number = rng.randint(10 ** (digit_len - 1), 10**digit_len - 1)
        out.append(f"Passport {letters}{number} on file for verification.")
    return out


def realistic_npwp_old_dotted_corpus(n: int = 20) -> list[str]:
    """Old NPWP shape: `XX.XXX.XXX.X-XXX.XXX` (2-3-3-1-3-3 dotted digit
    groups with a hyphen before the last pair) — matches `_NPWP_OLD_RE`
    verbatim."""
    rng = random.Random(20260824)
    out: list[str] = []
    for _ in range(n):
        a = rng.randint(0, 99)
        b = rng.randint(0, 999)
        c = rng.randint(0, 999)
        d = rng.randint(0, 9)
        e = rng.randint(0, 999)
        f = rng.randint(0, 999)
        npwp = f"{a:02d}.{b:03d}.{c:03d}.{d}-{e:03d}.{f:03d}"
        out.append(f"NPWP lama {npwp} terdaftar di KPP.")
    return out


def realistic_npwp_new16_bare_corpus(n: int = 20) -> list[str]:
    """New 16-digit bare NPWP: a leading zero plus 15 more digits — matches
    `_NPWP_NEW16_RE` verbatim."""
    rng = random.Random(20260825)
    out: list[str] = []
    for _ in range(n):
        rest = "".join(str(rng.randint(0, 9)) for _ in range(15))
        out.append(f"NPWP baru saya 0{rest} sudah aktif.")
    return out


def realistic_npwp_new16_dotted_corpus(n: int = 20) -> list[str]:
    """New 16-digit dotted NPWP: `0XX.XXX.XXX.X-XXX.XXX` — matches
    `_NPWP_NEW_DOTTED_RE` verbatim."""
    rng = random.Random(20260826)
    out: list[str] = []
    for _ in range(n):
        xx = rng.randint(0, 99)
        b = rng.randint(0, 999)
        c = rng.randint(0, 999)
        d = rng.randint(0, 9)
        e = rng.randint(0, 999)
        f = rng.randint(0, 999)
        npwp = f"0{xx:02d}.{b:03d}.{c:03d}.{d}-{e:03d}.{f:03d}"
        out.append(f"NPWP terformat {npwp} untuk verifikasi.")
    return out
