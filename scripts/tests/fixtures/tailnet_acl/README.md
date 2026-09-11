# `tailnet_acl/` — guilt fixtures

Each file reintroduces a defect that `audit_policy()` in
`scripts/tests/test_tailnet_acl_deny_by_default.py` must catch, and the parametrised test asserts
the SPECIFIC finding code the fixture is named for. They are not valid policies and must never be
pasted into the Tailscale admin console. They exist so the guard is proven to go red, not merely
observed to be green — a guard with only innocence tests can report success and never failure.

CORRECTED 2026-08-29: this file used to say each fixture carries "exactly ONE defect". That
stopped being true when the guard began pinning the whole `hosts` table, because most of these
fixtures are minimal — three lines of `hosts` — and a minimal table is by definition not the
fleet's. They now emit `PINNED_HOST_ALIAS_MOVED` alongside the defect they are named for, because a
three-line `hosts` block is missing five of the six pinned aliases. Nothing is
weakened by it (the assertion demands the named code, so the pin cannot carry a fixture on its
own), but a README claiming a property the files no longer have is the kind of small lie this
whole directory exists to prevent. The four `hosts_*` fixtures carry the full pinned table
precisely so that each isolates the spelling it is named for — measured: they emit that one code
and nothing else.
