# lint_model_cards Test Fixtures

A miniature `docs/arsenal/cards/` tree used by `test_lint_model_cards.py`. Each card is
crafted to trigger exactly one rule from `scripts/lint_model_cards.py`'s own docstring.

- `repo/docs/arsenal/cards/untagged_bullet.md` — a claim bullet with no SELF:/MEASURED:/
  PUBLIC: tag → RULE 1 violation.
- `repo/docs/arsenal/cards/measured_bad_path.md` — `MEASURED:` names a path that is
  neither in the repo nor memory-slug shaped → RULE 2 violation.
- `repo/docs/arsenal/cards/expired.md` — frontmatter `date: 2020-01-01`, permanently >30
  days old → RULE 3 violation ("expired"). The exact "31 days ago" boundary is tested with
  a computed date in `test_lint_model_cards.py` itself, not pinned here (a fixed calendar
  date could only ever prove ONE moment in the 30/31-day boundary, and would eventually
  stop meaning "31 days ago" the day after it was written).
- `repo/docs/arsenal/cards/bad_roles.md` — `roles_allowed: overlord` (not in the allowed
  set) → RULE 4 violation.
- `repo/docs/arsenal/cards/bad_seat.md` — `seat: not-a-real-seat` (does not resolve via
  scripts/dynamic_workflow.py's FAMILY_MAP/_SEAT_ALIASES) → RULE 5 violation.
- `repo/docs/arsenal/cards/clean.md` — passes all five rules (innocence).

Caveat (PR3c cure round, 2026-09-19): `clean.md`'s `date:` is a STATIC value. Tests
that call `find_violations(..., today=FIXTURE_TODAY)` are pinned against it safely,
but `lint_model_cards.py`'s `main()` takes no `today=` override — any test driving
`main()` on this fixture (or a copy of it) must interpolate
`date.today().isoformat()` over the literal `2026-09-18`, or it goes stale and
starts tripping RULE 3 ("expired") 30 days after this file was last touched.
