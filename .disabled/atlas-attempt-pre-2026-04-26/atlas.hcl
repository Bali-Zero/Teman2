# atlas.hcl — config for Atlas migrate-lint, used in CI only.
#
# This file does NOT define the runtime migration source of truth. The
# active runner (apps/backend-rag/backend/db/migration_manager.py) reads
# its own SQL files from db/migrations_v2/. Atlas only consumes a derived
# directory produced by scripts/atlas_split_migrations.sh during CI.
#
# What we lint:
#   destructive   — fails on DROP COLUMN / DROP TABLE without explicit
#                   `-- atlas:nolint destructive` annotation.
#   data_depend   — warns on changes that may fail when data exists
#                   (e.g. NOT NULL on a column without DEFAULT).
#   incompatible  — fails on backward-incompatible changes (e.g. ALTER
#                   COLUMN TYPE that loses precision/silently truncates).
#   naming        — informational, low-noise naming convention checks.
#
# Diagnostics emitted by the adapter (empty `*_down.sql` for migrations
# without a rollback marker) are surfaced by Atlas as "missing down
# migration" — exactly the PR #302 class of bug we want to catch.

env "ci" {
  # Dev URL: ephemeral docker postgres started by the GitHub Action.
  # The version (15) tracks the rest of our CI (.github/workflows/{tests,fly-deploy}.yml).
  dev = "docker://postgres/15/dev"

  migration {
    # Migration directory written by scripts/atlas_split_migrations.sh.
    # We pass this via the --dir flag in CI; this default is for local runs.
    dir    = "file:///tmp/atlas_migrations"
    format = golang-migrate
  }

  lint {
    # Each block declares which diagnostic codes elevate to errors. Codes
    # not listed here remain warnings (informational only) so we can ship
    # the workflow without retroactive cleanup of older patterns.
    destructive {
      error = true
    }
    incompatible {
      error = true
    }
    data_depend {
      # Only warn for now — many of our migrations legitimately add NOT NULL
      # columns with backfills handled by the runtime runner. Promote to
      # error after we audit a few PRs and add `-- atlas:nolint` where
      # warranted.
      error = false
    }
    naming {
      error = false
    }
  }
}
