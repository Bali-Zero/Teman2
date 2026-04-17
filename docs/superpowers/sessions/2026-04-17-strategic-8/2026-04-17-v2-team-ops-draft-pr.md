# v2 Rollout — Sub-plan 04: L3 Team Ops — DRAFT PR prep

> **Status:** Branch `v2-team-ops` ready. PR NOT opened per session rules.
> **Next action (Zero / human):** open draft PR against `main` with the body below.

## Branch
`v2-team-ops` (6 commits ahead of `main` at `eca76044b`)

## Commits (oldest → newest)

| SHA (short) | Subject |
|---|---|
| `107f998ab` | feat(kita): inbox-first default + omnichannel feed API |
| `2516f8913` | feat(kita): Cmd+K command palette with 8 actions |
| `a0df5afbd` | feat(kita): Prime map view toggle in /clients |
| `e3d9ba72d` | feat(kita): /analytics/funnel dashboard (admin only) |
| `f31dc5b22` | chore: remove 4 orphan satellite apps |
| `bbb8992b9` | docs(sessions): v2 team-ops lighthouse audit deferred |

## Diff summary
191 files changed · +760 insertions · −25139 deletions
(Net ~−24k LOC — almost entirely deletion of unused mail/calendar/drive/knowledge apps.)

## Suggested PR title
`feat(kita): L3 Team Ops — inbox-first + Cmd+K + Prime map + /analytics/funnel + cleanup 4 orphans`

## Suggested PR body

```markdown
## Summary
Implements Sub-plan 04 (L3 Team Ops) of the v2 subdomain rollout.

- **Inbox-first:** new `/kita/inbox` default post-login; omnichannel unified feed
  backed by `/api/workspace/inbox` (queries `conversation_messages` JOIN `clients`,
  RBAC-gated: admins see all, team users see only their assigned clients).
  `+/api/workspace/inbox/stats` returns 24h counts by channel.
- **Cmd+K palette:** `KitaCommandPalette` mounted at workspace layout. 8 actions
  (navigation + practice-creation shortcuts + Prime/analytics jumpers). Wraps
  `@balizero/core` `CommandPalette`.
- **Prime map view:** new `'map'` ViewMode in `/kita/clients`. Dynamically imports
  `PrimeNexusLayout` (ssr: false) with `initialMode="crm"` — PrimeNexusProvider
  now accepts `initialMode` prop.
- **Analytics funnel:** admin-only `/kita/analytics/funnel` with recharts bar
  chart (sessions vs first-touch conversions) + 3 KPI cards. Backend resilient
  to missing `funnel_sessions`/`funnel_attributions` tables (returns empty
  buckets rather than 500).
- **Cleanup:** removed 4 orphan Next.js apps (`apps/{mail,calendar,drive,knowledge}`)
  — these subdomains already redirect to kita internal routes via middleware
  `SSO_SUBDOMAINS`. Zero incoming imports from monorepo. ~−24k LOC.

## Not in this PR (known blockers / deferrals)
- **Task 5 (ContextPanel on /clients):** blocked by sub-plan 03 (client-app) —
  requires `ClientMatters / ClientVisa / ClientTax / ClientDocs / ClientPrime`
  subcomponents not yet merged.
- **Task 7 (Zantara inline suggestions):** blocked — requires
  `/api/zantara/suggest` endpoint (sub-plan 02 funnel-hub).
- **Task 11 Lighthouse:** deferred until preview URL is live. See
  `docs/superpowers/sessions/2026-04-17-strategic-8/2026-04-17-v2-team-ops-lighthouse-deferred.md`.
- **Vercel project unlinks** for mail/calendar/drive/knowledge: manual dashboard
  step, not scripted.

## Test plan
- [ ] Backend: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/setup/ backend/tests/services/rag/test_confidence.py -q` → green (42/42 already verified)
- [ ] Frontend: `cd apps/mouth && tsc --noEmit` → clean (verified)
- [ ] Preview deploy: verify `/inbox` renders, Cmd+K opens, `/clients` map toggle works, `/analytics/funnel` shows (admin login)
- [ ] Lighthouse audit on preview URL (see deferred doc for commands)
- [ ] Manual regression: `/dashboard`, `/clients` list/kanban/table views, `/whatsapp`, `/terminal` unaffected

## Related
- Master plan: `docs/superpowers/plans/2026-04-17-v2-rollout-00-master.md`
- Sub-plan 04: `docs/superpowers/plans/2026-04-17-v2-rollout-04-team-ops.md`
- Federation findings: (local-only, gitignored) — gemini-explore mapped workspace route deps

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

## Verifications run
- ✅ Backend import chain: `from backend.app.dependencies import get_current_user, get_database_pool` OK
- ✅ Backend tests: 42/42 pass (setup + rag/confidence)
- ✅ Frontend typecheck: `tsc --noEmit` clean
- ✅ Router manifest: 18/18 pass (including new `workspace_inbox`, `workspace_analytics`)

## Open the PR (when authorized)

```bash
cd .worktrees/v2-team-ops
gh pr create --draft --base main --head v2-team-ops \
  --title "feat(kita): L3 Team Ops — inbox-first + Cmd+K + Prime map + /analytics/funnel + cleanup 4 orphans" \
  --body-file <(sed -n '/^## Suggested PR body$/,/^## Verifications run$/p' \
    docs/superpowers/sessions/2026-04-17-strategic-8/2026-04-17-v2-team-ops-draft-pr.md \
    | sed '1d;$d;/^```markdown$/d;/^```$/d')
```
