# Atlas migrate-lint attempt — DISABLED 2026-04-29

Attempted Atlas migrate-lint integration before discovering the v0.38
paywall (cicatrix `2026-04-26`). Atlas v0.38+ moved `migrate lint` behind
a paid Atlas Pro tier, so this approach was abandoned.

**Replaced by Squawk** in
[`.github/workflows/migration-lint.yml`](../../.github/workflows/migration-lint.yml)
— same value prop (destructive-op detection at PR-check time) without
the paywall risk. MIT-licensed, Postgres-specific, ~600K monthly
downloads.

## Files in this directory

| File | What it was | Why kept |
|------|-------------|----------|
| `atlas-migrate-lint.yml` | GitHub Actions workflow that ran `ariga/atlas-action/migrate/lint@v1` on PR | Audit: shows the original CI integration shape |
| `atlas.hcl` | Atlas project config pointing at `apps/backend-rag/backend/db/migrations_v2/` | Audit: shows the migrations dir wiring |
| `atlas_split_migrations.sh` | Helper that pre-processed `-- === ROLLBACK ===` markers before invoking Atlas | Audit: shows how the team planned to reconcile the runtime convention with Atlas's expectations |

## Do NOT reactivate without

1. Re-reading [`.claude/rules/cicatrix-scars.md`](../../.claude/rules/cicatrix-scars.md)
   — the scar entry "RESOLVED: Atlas migrate-lint paywalled in v0.38 —
   pivoted to Squawk (2026-04-26)".
2. Confirming Atlas has reverted the paywall OR that the team has
   purchased an Atlas Pro license.
3. Deleting `.github/workflows/migration-lint.yml` (Squawk) so we don't
   double-lint.

The runtime rollback-marker validation in
`apps/backend-rag/backend/db/migration_manager.py` is unaffected by this
choice and stays as-is — it operates at deploy time, complementary to
whichever PR-check-time linter is active.
