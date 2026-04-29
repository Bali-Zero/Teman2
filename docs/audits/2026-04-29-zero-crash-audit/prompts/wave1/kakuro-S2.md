# kakuro-S2 — P0-4 SQL v2 migration post-deploy

> Single-file prompt for one Claude Code Max x20 session.
> Macchina: **Pro** (`nuzantara@Nuzantara`). Worktree: `wt/p0-4-sqlv2-postdeploy`.
> Session command: in your tmux pane, simply type:
>
>     leggi kakuro-S2 e esegui

---

## Mission

Implementa **P0-4** dal piano audit zero-crash 2026-04-29: aggiungi job `run-sql-v2-migrations-post-deploy` in `.github/workflows/fly-deploy.yml` che esegua le SQL v2 migrations sull'image FRESCA (post-deploy), eliminando il workaround manuale `gh workflow run` documentato nella cicatrice STRUCTURAL.

**Tempo stimato: 30 min.** Quickest win del Wave 1.

## Context

- Repo: `/Users/nuzantara/Desktop/nuzantara`, branch `main`
- Brainstorm dedicato (READ FIRST): [`11_brainstorms/P0-4_sql_v2_post_deploy.md`](../../11_brainstorms/P0-4_sql_v2_post_deploy.md)
- Cicatrice STRUCTURAL aperta: `.claude/rules/cicatrix-scars.md` — entry "SQL v2 migrations apply on OLD image, not the freshly-built one (2026-04-26)"
- Workflow attuale: `.github/workflows/fly-deploy.yml`

## Files to touch (1)

1. `.github/workflows/fly-deploy.yml` — aggiungi nuovo job `run-sql-v2-migrations-post-deploy`

## Files NOT to touch

- `apps/backend-rag/fly.toml` (off-limits)
- Altri workflow file (NON serve toccarli per questo intervento)

## Workflow

### Phase 1 — Cross-LLM brainstorm (start here)

```bash
cd /Users/nuzantara/Desktop/nuzantara
source docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/_coordination.sh

cat > /tmp/kakuro-S2-brief.txt <<'BRIEF'
You are giving an independent implementation strategy.

PROBLEM: GitHub Actions workflow .github/workflows/fly-deploy.yml has 5 jobs
in this order:
1. pre-deploy-gate (validation)
2. run-migrations - flyctl ssh console runs `python -m backend.db.migrate apply-all` against the CURRENTLY RUNNING container (i.e., previous image, NOT the new one being deployed)
3. deploy - flyctl deploy --strategy rolling builds and deploys new image
4. run-python-migrations (post-deploy, but only handles backend/migrations/apply_migration_NNN.py wrappers, NOT migrations_v2/*.sql)
5. post-deploy-health (probes /health, auto-rollback)
6. deploy-failure-alert (sibling, fires on stage failure)

PROBLEM: When a PR adds a new SQL v2 file in apps/backend-rag/backend/db/migrations_v2/NNN_*.sql, step 2 runs against OLD image which doesn't have the file yet. The new SQL only lands in the image at step 3. So migration is NEVER applied automatically — operator must manually run `gh workflow run "Deploy Backend to Fly.io" --ref main` after merge to trigger a no-op redeploy that this time picks up the new SQL.

FAILURE MODE: 5-30 minute window of production 500s ("column does not exist") on every PR with new SQL.

YOUR TASK: Propose the YAML for a new job `run-sql-v2-migrations-post-deploy`
that:
- Runs AFTER deploy step succeeds
- Waits until 2/2 Fly machines are running the latest image (otherwise would re-hit old image)
- Re-runs `python -m backend.db.migrate apply-all` against fresh image
- Idempotent (runner skips already-applied via _schema_versions table)
- Telegram alert if it actually applied something (signal that previous workflow was masking)
- Fail-loud if migration errors

Constraints:
- Cannot touch fly.toml (off-limits)
- Must use existing FLY_API_TOKEN secret
- Must use existing TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID secrets
- Compatible with current `needs:` chain
- Idempotent on no-op deploys (no harm if no new migrations)

Bonus: how to detect if image is fresh (not OLD image)? Suggest a sentinel approach.
BRIEF

mkdir -p /tmp/kakuro-S2-brainstorms
coord_brainstorm "P0-4 SQL v2 post-deploy job" /tmp/kakuro-S2-brief.txt /tmp/kakuro-S2-brainstorms

# Read all 4 outputs
for llm in codex gemini deepseek notebooklm; do
    echo "=== $llm ==="
    head -150 /tmp/kakuro-S2-brainstorms/$llm.md
done
```

Synthesize the 4 strategies. Particularly note any of them suggest:
- Different sentinel for "image is fresh" detection
- Different needs: chain (some may suggest needs: [deploy] only, others [deploy, run-python-migrations])
- Telegram alert content variations

### Phase 2 — Worktree

```bash
cd /Users/nuzantara/Desktop/nuzantara
git fetch origin
git worktree add -b feat/p0-4-sqlv2-postdeploy ../nuzantara-wt/p0-4 origin/main
cd ../nuzantara-wt/p0-4
```

### Phase 3 — Implement (single file edit)

Edit `.github/workflows/fly-deploy.yml`. Add new job after `deploy` and `run-python-migrations`.

Reference proposal from brainstorm + intervention plan:

```yaml
run-sql-v2-migrations-post-deploy:
  name: Re-run SQL v2 migrations on fresh image
  needs: [deploy, run-python-migrations]
  if: always() && needs.deploy.result == 'success'
  runs-on: ubuntu-latest
  env:
    FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
  steps:
    - uses: actions/checkout@v4

    - name: Install flyctl
      uses: superfly/flyctl-actions/setup-flyctl@master

    - name: Wait for fresh image to serve traffic
      run: |
        # Wait until 2/2 machines running (image refreshed from rolling deploy)
        for i in {1..30}; do
          STARTED=$(flyctl status -a nuzantara-rag --json 2>/dev/null \
            | jq -r '[.Allocations[] | select(.Status=="running")] | length')
          if [ "$STARTED" = "2" ]; then
            echo "✓ 2/2 machines running latest image"
            break
          fi
          echo "Waiting... ($STARTED/2)"
          sleep 10
        done

    - name: Run SQL v2 migrations against fresh image
      id: migrate
      run: |
        OUTPUT=$(flyctl ssh console --app nuzantara-rag \
          --command "/bin/sh -c 'cd /app && PYTHONPATH=. python -m backend.db.migrate apply-all'" \
          2>&1 | tee migration_output.txt)
        APPLIED=$(echo "$OUTPUT" | grep -c "^Applying migration" || true)
        echo "applied_count=$APPLIED" >> $GITHUB_OUTPUT
        echo "::notice::SQL v2 post-deploy: $APPLIED migrations applied"

    - name: Telegram notify if migrations applied
      if: steps.migrate.outputs.applied_count != '0'
      env:
        TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
        TELEGRAM_OWNER_CHAT_ID: ${{ secrets.TELEGRAM_OWNER_CHAT_ID }}
      run: |
        MSG="🆕 SQL v2 post-deploy: ${{ steps.migrate.outputs.applied_count }} migrations applied on fresh image (cicatrix PR #307 / 2026-04-26 fix verified working)"
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
          --data-urlencode "chat_id=${TELEGRAM_OWNER_CHAT_ID}" \
          --data-urlencode "text=$MSG"

    - name: Fail loud on migration error
      if: failure()
      run: |
        echo "::error::Post-deploy SQL v2 migration failed. Manual investigation required."
        cat migration_output.txt | head -100 || true
        exit 1
```

Compare against brainstorm synthesis. Adjust if any LLM suggested a meaningfully better pattern.

### Phase 4 — Local validation

You can't test the workflow locally without a real Fly + GH Actions run. But you can:

```bash
# 1. YAML validity
yq eval '.jobs."run-sql-v2-migrations-post-deploy"' .github/workflows/fly-deploy.yml
# Expected: prints the job spec

# 2. Reference jobs exist
grep -E "^  (deploy|run-python-migrations|post-deploy-health|deploy-failure-alert):" .github/workflows/fly-deploy.yml
# Expected: 4 lines

# 3. No syntax errors
actionlint .github/workflows/fly-deploy.yml 2>&1 | head -5
# (if actionlint not installed: brew install actionlint)
```

### Phase 5 — Synthetic canary test (RECOMMENDED, optional)

To verify the new job actually fires AND applies a migration:

```bash
# Create a no-op canary migration
cat > apps/backend-rag/backend/db/migrations_v2/141_audit_canary_post_deploy.sql <<EOF
-- Audit canary for P0-4 verification. Creates and drops a temp table.
-- Will be removed in follow-up commit after verify.

CREATE TABLE IF NOT EXISTS p04_canary_$(date +%Y%m%d) (
    id BIGSERIAL PRIMARY KEY,
    note TEXT NOT NULL DEFAULT 'P0-4 verification 2026-04-29'
);

-- === ROLLBACK ===
DROP TABLE IF EXISTS p04_canary_$(date +%Y%m%d);
EOF
```

You'll commit this in Phase 6 along with the workflow change.

### Phase 6 — Commit + Push + Deploy (COORDINATED)

```bash
source /Users/nuzantara/Desktop/nuzantara/docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/_coordination.sh

cd /Users/nuzantara/Desktop/nuzantara-wt/p0-4

git add .github/workflows/fly-deploy.yml
# If you created the canary migration:
git add apps/backend-rag/backend/db/migrations_v2/141_audit_canary_post_deploy.sql

coord_commit "fix(deploy): add run-sql-v2-migrations-post-deploy to fly-deploy.yml

P0-4 from zero-crash audit 2026-04-29.

Closes the cicatrix STRUCTURAL 2026-04-26 'SQL v2 migrations apply on
OLD image, not freshly-built one'. New job runs after deploy step,
waits for 2/2 machines to serve fresh image, then re-runs
'python -m backend.db.migrate apply-all'. Idempotent (runner skips
already-applied via _schema_versions). Telegram alert fires when
migrations actually applied (signal previous workflow was masking).

Includes canary migration 141_audit_canary_post_deploy.sql to verify
the fix in production. Will be removed in follow-up commit after
post-deploy verification.

Cicatrix STRUCTURAL 2026-04-26 PR #307 resolved."

coord_push origin feat/p0-4-sqlv2-postdeploy

gh pr create \
  --title "fix(deploy): SQL v2 post-deploy job + canary migration verify" \
  --body "Resolves cicatrix STRUCTURAL 2026-04-26.

## Summary
- New job run-sql-v2-migrations-post-deploy waits for fresh image, re-runs SQL v2 migration runner
- Idempotent — no-op cost ~5-10s extra on deploys without new migrations
- Telegram alert fires only when migrations actually apply
- Canary migration 141_audit_canary_post_deploy.sql verifies the fix end-to-end

## Test plan
- [x] yq + actionlint validate workflow
- [ ] First deploy after merge: canary migration 141 applies via NEW job (not pre-deploy)
- [ ] Telegram message fires with applied_count=1
- [ ] Follow-up PR removes canary migration

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

gh pr merge --auto --squash

# Watch deploy
PR_NUMBER=$(gh pr view --json number -q .number)
echo "PR #$PR_NUMBER merging when CI green..."
sleep 60
gh run watch $(gh run list --workflow="Deploy Backend to Fly.io" --limit 1 --json databaseId -q '.[0].databaseId')

# Verify the new job fired correctly
RUN_ID=$(gh run list --workflow="Deploy Backend to Fly.io" --limit 1 --json databaseId -q '.[0].databaseId')
gh run view $RUN_ID --log | grep -A 5 "run-sql-v2-migrations-post-deploy"
# Expected: see the job ran, applied_count=1 (canary migration)

# Cleanup canary in follow-up (after verifying)
git checkout main && git pull
git checkout -b chore/cleanup-p04-canary
git rm apps/backend-rag/backend/db/migrations_v2/141_audit_canary_post_deploy.sql
coord_commit "chore: remove P0-4 canary migration after verify"
coord_push origin chore/cleanup-p04-canary
gh pr create --title "chore: remove P0-4 canary" --body "Followup cleanup. Canary verified P0-4 working."
gh pr merge --auto --squash

~/.claude/scripts/mem save decision "P0-4 SQL v2 post-deploy completed — PR #$PR_NUMBER. Canary migration verified new job applies migrations against fresh image. Cicatrix STRUCTURAL 2026-04-26 resolved." 9
```

### Phase 7 — Cleanup worktree

```bash
cd /Users/nuzantara/Desktop/nuzantara
git worktree remove ../nuzantara-wt/p0-4
```

## Reporting

```
[kakuro-S2 DONE] P0-4 merged in PR #<num>. Fly deploy success.
Canary migration 141 verified post-deploy job applies migrations on fresh image.
Telegram alert fired with applied_count=1. Cicatrix STRUCTURAL 2026-04-26 resolved.
Brainstorms saved in /tmp/kakuro-S2-brainstorms.
```

## Failure modes

- **Brainstorm CLI fails**: log + retry once. Same as kakuro-S1.
- **YAML syntax error**: actionlint catches before push. Fix locally.
- **CI red**: read logs in `gh run view --log-failed`. Common: missing flyctl install step (already in template above), wrong needs: chain, syntax.
- **Canary migration fails to apply**: investigate. Probably the runner isn't seeing the file in fresh image — that's the bug we're fixing, so failure here means deeper issue with workflow ordering. Escalate to Zero.
- **Coord lock stuck**: `coord_status` check holder. Break stale lock if PID dead.

## Autonomy boundary

L2 autonomous for everything in this prompt. NO Zero handoff needed unless canary fails to apply (which would mean the fix itself didn't work).
