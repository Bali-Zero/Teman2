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
"""

from __future__ import annotations

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
