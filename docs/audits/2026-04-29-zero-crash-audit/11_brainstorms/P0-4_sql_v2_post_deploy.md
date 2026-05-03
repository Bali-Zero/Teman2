# P0-4 Brainstorm — SQL v2 migration deploy ordering bug fix

**Goal:** Re-run SQL v2 migrations against fresh image after `deploy` step, eliminating the manual `gh workflow run` workaround documented in cicatrix.
**Effort:** 30 min
**Dependencies:** None — purely workflow YAML.

---

## Strategy options

### Option A: New post-deploy job (recommended in cicatrix)

Add `run-sql-v2-migrations-post-deploy` job that needs `[deploy]`, runs `flyctl ssh console -C "python -m backend.db.migrate apply-all"` against the freshly-deployed image.

**Pros:**
- Surgical fix — only touches one workflow file
- Idempotent (runner skips already-applied)
- Explicit, audit-friendly
- Cicatrix-recommended approach

**Cons:**
- Adds ~5-10s to deploy on no-op runs
- Requires sentinel detection that new image is live (similar to existing `run-python-migrations` pattern)

**Effort:** 30 min including verification.

### Option B: Reverse the order — deploy first, migrate after

Move `run-migrations` to AFTER `deploy`. This breaks the current "fail-deploy-on-bad-migration" semantic (we want to refuse deploy if migration is broken).

**Pros:**
- Single migration step, no duplication

**Cons:**
- Loses pre-deploy gate for migrations
- Breaks existing semantic
- Higher risk

**Effort:** 1 hour but undesirable trade.

### Option C: Run migrations in entrypoint instead of separate job

Have the FastAPI app run `migrate apply-all` on startup before binding 8080.

**Pros:**
- No separate job needed
- Fly will retry container on migration failure

**Cons:**
- Couples migration timing to container start
- If migration takes >180s (warmup deadline), backend marked unhealthy
- Race: 2 machines starting simultaneously may both try migration

**Effort:** 2 hours but introduces new failure modes.

**Recommendation:** **Option A** — cicatrix already recommends it. Implement straight.

---

## Implementation plan (Option A)

### File: `.github/workflows/fly-deploy.yml`

Add new job after `deploy`:

```yaml
run-sql-v2-migrations-post-deploy:
  name: Re-run SQL v2 migrations on fresh image
  needs: [deploy, run-python-migrations]
  if: always() && needs.deploy.result == 'success'
  runs-on: ubuntu-latest
  env:
    FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
    FLY_ACCESS_TOKEN: ${{ secrets.FLY_API_TOKEN }}

  steps:
    - name: Wait for fresh image to serve traffic
      run: |
        # Wait until 2/2 machines are running latest image (deployed_image_ref matches)
        DEPLOY_REF="${{ needs.deploy.outputs.image_ref }}"
        # Fall back to checking image SHA in fly status
        for i in {1..30}; do
          STARTED=$(flyctl status -a nuzantara-rag --json 2>/dev/null | jq -r '[.Allocations[] | select(.Status=="running")] | length')
          if [ "$STARTED" = "2" ]; then
            echo "✓ 2/2 machines running"
            break
          fi
          echo "Waiting for machines... ($STARTED/2)"
          sleep 10
        done

    - name: Run SQL v2 migrations against fresh image
      id: migrate
      run: |
        OUTPUT=$(flyctl ssh console --app nuzantara-rag \
          --command "/bin/sh -c 'cd /app && PYTHONPATH=. python -m backend.db.migrate apply-all'" \
          2>&1 | tee migration_output.txt)
        echo "$OUTPUT"
        # Idempotent: if no new migrations, this is a no-op (~5s round-trip)
        APPLIED=$(echo "$OUTPUT" | grep -c "^Applying migration" || true)
        echo "applied_count=$APPLIED" >> $GITHUB_OUTPUT

    - name: Telegram notify if migrations applied
      if: steps.migrate.outputs.applied_count != '0'
      env:
        TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
        TELEGRAM_OWNER_CHAT_ID: ${{ secrets.TELEGRAM_OWNER_CHAT_ID }}
      run: |
        MSG="🆕 Post-deploy SQL v2 migrations: ${{ steps.migrate.outputs.applied_count }} applied on fresh image (was needed because pre-deploy ran against old image — cicatrix PR #307)"
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
          -d "chat_id=${TELEGRAM_OWNER_CHAT_ID}&text=$MSG"

    - name: Fail if migrations errored
      if: failure()
      run: |
        echo "::error::Post-deploy SQL v2 migration failed. Manual investigation required."
        cat migration_output.txt | head -50
        exit 1
```

---

## Dependencies

- **Before:** None.
- **After:** Cicatrix `STRUCTURAL: SQL v2 migrations apply on OLD image` can be RESOLVED. Update `.claude/rules/cicatrix-scars.md` to mark resolved.

## Rollback plan

`git revert` removes the new job. Behavior reverts to manual `gh workflow run` workaround.

## L2 autonomy decision

**Auto-implementable: YES.**

Single workflow YAML change, additive, reversible.

## Verification

### Synthetic test (DO ONCE)

```bash
# Plant a canary migration
cat > apps/backend-rag/backend/db/migrations_v2/141_audit_canary.sql <<EOF
CREATE TABLE audit_canary_$(date +%s) (id BIGSERIAL PRIMARY KEY);
-- === ROLLBACK ===
DROP TABLE IF EXISTS audit_canary_$(date +%s);
EOF

# Open PR + merge
git checkout -b test/audit-canary-migration
git add apps/backend-rag/backend/db/migrations_v2/141_audit_canary.sql
git commit -m "test: audit canary migration"
gh pr create --title "test: audit canary migration" --body "Verify P0-4 fix" --base main
gh pr merge --auto --squash

# After merge, watch the run
gh run watch

# Verify both:
# - run-migrations (pre-deploy): does NOT apply 141 (old image)
# - run-sql-v2-migrations-post-deploy: applies 141 ✓

gh run view <run-id> --log | grep -E "Applying migration 141|Applied:"

# Cleanup canary
psql ... -c "DROP TABLE audit_canary_*"
git checkout main
git rm apps/backend-rag/backend/db/migrations_v2/141_audit_canary.sql
git commit -m "test: cleanup audit canary"
```

### Production verification

After landing the workflow change, the next PR with a real migration:
1. PR opens, Squawk lints SQL
2. PR merges, fly-deploy.yml runs
3. `run-migrations` (pre-deploy) — runs but doesn't see new file (old image)
4. `deploy` — builds new image with new SQL
5. `run-sql-v2-migrations-post-deploy` — runs, applies the new migration

Telegram alert fires. Cicatrix marked resolved.

Numbers:
- Before: window 5-30 min of 500s on every migration PR + manual `gh workflow run` recovery
- After: 0s window — migration applied automatically post-deploy
