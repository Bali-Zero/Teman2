# docs_audit Test Fixtures

A miniature repo structure used by `test_docs_audit.py`. Each doc is crafted
to trigger exactly one classification rule in `docs_audit.py`.

- `CLAUDE.md`, `INDEX.md` — reference root files that contain `refs_in` to
  some of the `docs/` files. Used to verify ref-counting.
- `docs/LIVE_DOC.md` — referenced by CLAUDE.md, recent mtime → LIVE.
- `docs/STALE_DRIFT.md` — contains a DOCSYNC marker with a wrong value → STALE.
- `docs/ORPHAN_OLD.md` — zero refs, mtime forced >90d via os.utime → ARCHIVED
  (orphan).
- `docs/BROKEN_LINK.md` — has a markdown link to a nonexistent file → STALE.
- `docs/WHITELIST_KEEPER.md` — zero refs, old mtime, BUT in WHITELIST → LIVE.
- `docs/DUP_V1.md`, `docs/DUP_V2.md` — both in a test-only cluster definition
  → STALE with cluster="test-dup".
- `docs/archive/OLD_ARCHIVED.md` — already archived → ARCHIVED.

The test fixture `WHITELIST` and `CLUSTERS` are passed to `docs_audit` as
CLI flags or env vars, not hardcoded in the fixture itself.
