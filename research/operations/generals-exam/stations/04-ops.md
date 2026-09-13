## Station 4 — ops / CI

This morning every pull request in the merge queue was ejected by the required job
`Guard conformance (superscar antidotes)` → `Every guard proves guilt AND innocence`. The
same job was green on every PR head the day before, and green on main's last run. No diff
on either side explains it.

Reproduce locally first. From the worktree root:

```
apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_evidence_pack_lint.py --no-header -p no:cacheprovider
```

Then:

1. Name the root cause precisely: which rule, which constant, which fixtures, why today and
   not yesterday, why merge groups and not PR heads.
2. Cure it. The cure must satisfy all of these, and you must show each one in EVIDENCE:
   - the full file is green (all tests, including the three that are red now — they keep
     their names and their subject);
   - the rule that fired still fires for what it is meant to catch: after your change,
     a pack written at the deprecated root path `evidence/pack.yml` in a fresh temp repo
     must still make `scripts/evidence_pack_lint.py` exit non-zero with that rule's
     violation. Demonstrate it with a command, or write it as a test;
   - `apps/backend-rag/.venv/bin/python scripts/evidence_pack_lint.py --selftest` still passes
     (the lint imports `yaml`; the system `python3` does not have it).
3. State what would have caught this before it fired, in one paragraph, as a concrete
   guard, not a wish.

Moving the date, deleting the tests, or marking them xfail is not a cure. If you believe
the rule itself is wrong, say so in CLAIM with the argument — but the acceptance above
still stands.
