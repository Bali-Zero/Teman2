# Personal obligations from existing Kita records

## Outcome

Each team member gets a personal Obligations page derived from the clients and
practices assigned to them. Supervisors can inspect the team view. Actions open
the existing client or process page. Updating the source record removes the
corresponding obligation when its rule no longer matches. Reviewing a process
and choosing to keep it open leaves it visible. There is no second completion
state or new task table.

The prior statutory compliance register remains available at
`/obligations/register`, separately labelled, with its existing authorization.
The existing Operations navigation entry `/obligations` becomes the personal page.

## Two rules only

1. An assigned client's passport is expired or expires within 90 days, matching
   the existing client-list warning window. Open the client record to contact
   the client or replace/update the passport using the existing controls.
2. An assigned practice has `created_at` more than 14 days ago and is in an active
   status. Open the process to review it and use its existing state transitions.
   Age alone never mutates the practice. A clarification about automatic failure
   was asked; the safe implementation assumes a human review. Kita currently
   has `completed` and `cancelled` terminal states, not `failed`; do not silently
   add or relabel a state as part of this read view.

Passport ownership comes from `clients.assigned_to`. Practice ownership comes
from `practices.assigned_to`; do not replace it with client ownership, since the
existing process write guard authorizes the practice assignee/creator. Unassigned
items are visible only in the authorized team view and clearly marked unassigned.

## Reuse and boundaries

- Read-only endpoint under the already registered CRM alerts router; bounded SQL
  over existing `clients` and `practices`, paginated, with counts from the same
  predicates. No migration, scheduler, notification sending, or new dependency.
- Default scope is the authenticated user's own assignments, even for admins.
  Use `require_team_member`; client, partner and service identities are rejected.
  Team scope is authorized by `can_view_all_practices`, plus a narrow additional
  read-only allowlist `MEMBER_OBLIGATIONS_SUPERVISOR_EMAILS`. The owner explicitly
  designated Nakhoda as a viewer in this conversation. The active staff account
  was resolved without exposing its identity: role Tax Manager, not a global
  administrator under the checked source policy. Configure this account through
  the server environment, never a public/frontend roster or global admin grant.
  The extra grant applies only to this GET endpoint, not client/process edits or
  other CRM reads. Team scope without permission returns 403. An ordinary member
  cannot override scope by supplying another owner's email.
- A necessary existing detail-read fix adds the practice assignee to the
  existing creator/client-lead predicate in `get_practice`; it aligns the read
  with the already permitted list and write. Preserve the client-contact scrub.
  The additional read-only supervisor sees the overview without edit/source
  actions on other members' processes; existing full-view users keep their links.
- Client actions reuse the existing client header contact controls and passport
  editor. Process actions reuse the existing detail page and state machine.
- Re-fetch on return/focus and expose Refresh; no persistent client data in browser
  storage and no client records in logs or review artifacts.
- Keep the statutory register intact behind its own page. Its completion action
  must not be presented as completion of a passport or a CRM practice.

Internal reuse was grounded in `crm_enhanced_alerts.py`, `crm_utils.py`,
`crm_access.py`, `crm_practices.py`, `practice_state_machine.py`,
`stale_practice_notifier.py`, `ClientDetailClient.tsx`, `client-row-model.ts`,
the existing Obligations page, and `types/navigation.ts`.
The existing expiry endpoint's optional owner filter is not an authorization
primitive; the new read must enforce its own resolved scope before SQL.

External references: [React derived-state guidance](https://react.dev/learn/choosing-the-state-structure)
and [PostgreSQL set queries](https://www.postgresql.org/docs/current/queries-union.html).
Existing React, PostgreSQL and CRM components are sufficient; no external task
manager is required.

## Acceptance

- The additional supervisor setting is empty by default, normalized like the
  existing developer allowlist, and consumed only by the member-obligations GET.
  Human-team membership is required even for an allowlisted identity.
- Exact response fields exclude client contact details, passport numbers, notes,
  prices, metadata and family information. The server computes process-link
  access using the existing detail predicate; the frontend only consumes the flag.
- Real PostgreSQL fixtures prove owner isolation, supervisor scope, unassigned
  handling, deleted-client exclusion, 90-day/14-day boundaries, terminal-state
  exclusion, counts and pagination, and disappearance after source updates.
- Frontend tests prove correct source links, personal/team visibility, error and
  empty states, pagination and refresh. Existing register tests remain green.
- TypeScript, token lint, generated OpenAPI schema/pin parity, required backend
  smoke checks and required CI pass. Independent cross-family review and a fresh
  BLUE gate precede release; the BLUE release owner handles shipping.
- Live proof uses synthetic browser responses and read-only aggregate API checks.
  No real client records are changed for QA and no outbound messages are sent.

## Mission

BLUE, Gear 3: the settings module and measured diff trigger the enforced floor.
Council is not triggered: this is one bounded derived view, with no parallel
research breadth or divergent architecture priors requiring a council.
Codex prepares implementation; Claude Opus 5.5 xhigh
owns design review and release. A distinct fresh Opus 5.5 xhigh session grades
the final candidate. Worktree: `.worktrees/mouth-kita-member-duties-1017`.
Base refreshed from `d9546c7` to `7f670dcde0` before release; generated contracts
include the intervening main changes. Other sessions' workspaces remain untouched.
