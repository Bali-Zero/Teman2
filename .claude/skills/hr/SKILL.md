---
name: hr
description: "HR corner — shared context for team roster, departments, leave routing and attendance. Load before touching team/HR code or data, or when Zero says /hr, 'organigramma', 'ferie', 'presenze'."
---

# /hr — HR / team-management corner

> Shared context for the staff roster, who sits in which department, who is Management,
> leave routing, attendance and roster changes. Opened 2026-10-15. Every claim below was read
> from the file named next to it on that date; anything not re-read is marked **UNVERIFIED**.
> Paths are relative to `apps/backend-rag/backend/` unless they start with `.claude/`.
> This file carries NO personal data on purpose (names, roles and departments only; the roster
> itself holds contact and personal fields: never copy them here or anywhere else).

## 1. Roster SSOT and how it reaches the DB

- **File:** `data/team_members.json` (tracked in git, 19 entries on 2026-10-15). Keys per entry:
  `id, name, email, role, department, team, age, religion, languages, preferred_language,
expertise_level, traits, notes, location, emotional_preferences`. Most of those are personal data.
- **Loader:** `core/team_roster.py::load_team_roster()`. Source precedence: env `TEAM_MEMBERS_JSON`
  (the document itself, "a Fly secret in prod" per its docstring) then env `TEAM_MEMBERS_FILE`
  (path; a wrong path raises, no fallback) then the packaged JSON. Returns `[]` if none exists.
  Errors name the source, never the content. Readers: `data/team_members.py` (compat shim,
  `TEAM_MEMBERS`), `services/crm/collaborator_service.py`, migration 027.
  Whether prod actually sets `TEAM_MEMBERS_JSON` is **UNVERIFIED** (not checked: no secret read).
- **DB seeding:** `scripts/seed_users.py` reads `data/team_members.json` DIRECTLY (not through the
  loader) and UPSERTs `full_name, role, department, notes, active` into table `team_members`, matched
  by email. PINs come from an out-of-repo file (`load_pins()`); without a PIN an existing row is
  refreshed metadata-only, a new row is NOT created and the run exits non-zero.
  Run by hand: no migration, cron or deploy step references it (`git grep seed_users` hits only the
  script, two tests, an evidence/research note and a PENDING-ARMS row).
- **Consequence (verified from the code and the NOTE in
  `tests/services/crm/test_lead_assignment_agent.py`, docstring of
  `test_setup_is_a_real_department_with_assignable_people_behind_it`):** `team_members.department`
  is populated out-of-band. Merging a JSON edit changes what the JSON readers see after deploy, but
  the DB `department`/`role` that `assign_lead` queries change ONLY when someone runs the seeder
  against prod, and prod DB writes are operator-only.

## 2. Roster today (id | role | department), from the JSON on 2026-10-15

| id       | role                   | department                   |
| -------- | ---------------------- | ---------------------------- |
| zainal   | CEO                    | management                   |
| ruslana  | Board Member           | management                   |
| zero     | Founder                | technology                   |
| vino     | Junior Consultant      | setup                        |
| krishna  | Executive Consultant   | setup                        |
| adit     | Supervisor             | setup                        |
| ari      | Team Leader            | setup                        |
| dea      | Executive Consultant   | setup                        |
| surya    | Team Leader            | setup                        |
| damar    | Junior Consultant      | setup                        |
| veronika | Tax Manager            | tax                          |
| angel    | Tax Lead               | tax                          |
| kadek    | Tax Lead               | tax                          |
| dewaayu  | Tax Lead               | tax                          |
| faisha   | Tax Care               | tax                          |
| rina     | Reception              | operations (team: reception) |
| nina     | Marketing Advisory     | marketing                    |
| sahira   | Marketing & Accounting | marketing                    |
| asya     | Accounting             | accounting                   |

"Management" in the JSON is department `management` = Zainal (CEO) and Ruslana (Board Member).
Zero is Founder with department `technology`.
**Discrepancy to know:** code comments (`services/agents/team_agent_config.py`, `app/routers/lkpm.py`,
`app/routers/crm_clients.py`, `services/compliance/lkpm_deadline_notifier.py`) say Faisha was
offboarded on 2026-09-19 and removed from agent/LKPM lists, yet she is still in the JSON and in the
leave map (`hr_leave_routing.SUPERVISOR_MAP`). Whether the roster should drop her is **UNVERIFIED**
(a business call for Zero; do not decide it in a docs PR).

## 3. What a department or role change actually affects

Three places hard-code routing by EMAIL, not by the JSON `department`. Editing the JSON alone
never changes them.

1. **Lead assignment** — `services/crm/assignment.py`.
   - `ASSIGNABLE_ROLES` = Supervisor, Team Leader, Executive Consultant, Junior Consultant,
     Specialist Advisor, Advisory, Tax Lead, Tax Care, Tax Manager. Roles outside it (CEO, Founder,
     Board Member, Reception, Marketing Advisory, Marketing & Accounting, Accounting) are never assigned.
   - `PRACTICE_DEPARTMENT_MAP` maps an EXACT `practice_type_code` to `setup` or `tax`
     (14 keys; no prefix match). Per the in-file comment, only four legacy codes (`visa`, `kitas`,
     `tax`, `tax_registration`) plus the two GARUDA VOA codes are seeded in the catalogue; the rest are
     dead keys, and modern `visa_*`/`ext_*`/`tax_*`/`other_*` codes fall to the fallback.
   - `assign_lead`: Strategy 1 = assignable role AND `LOWER(tm.department)` = mapped department,
     fewest active practices first. Fallback = any assignable member, fewest practices. Both read the
     DB table, so they follow the seeded `department`, not the JSON.
2. **Leave approval** — `app/services/hr/hr_leave_routing.py`. `SUPERVISOR_MAP` (email -> approver):
   tax team (Kadek, Angel, Dewa Ayu, Faisha) -> Veronika; Dea and Rina -> Ruslana; everyone else
   (Veronika, Asya, Ruslana, anyone unmapped) -> Zero. Notification: Zero in CC unless he is the TO;
   Asya in CC unless she is the requester. Review mail: requester TO, Zero and Asya in CC unless they
   are reviewer or requester. File docstring: "update SUPERVISOR_MAP and add tests".
3. **Attendance** — `services/analytics/attendance_monitor.py`.
   - Late policy (Bali time): nothing before 09:30, gentle reminder in the grace window, incident from
     09:40; clock-in reminder 09:15; absence alert after 2 consecutive working days without clock-in;
     approved leave covering today suppresses the late alert.
   - `LATE_EXEMPT_EMAILS` = Zero, Ruslana, Veronika (by email).
   - `resolve_responsible_manager()` (CC on the ultimatum email) DUPLICATES the leave map: `*.tax` mailbox
     -> Veronika, Dea/Rina (`RUSLANA_REPORTS`) -> Ruslana, else Zero only. A reporting-line change must
     be made in BOTH files (nothing links them; no shared constant seen).
4. **Agent roles** — `services/agents/team_agent_config.py::TEAM_AGENTS` maps email -> `AgentRole`
   (`admin, hr_manager, crm_full, visa_specialist, executive_consultant, tax_specialist`), which gates
   tools per person. A new member without an entry gets no agent role (`get_agent_role` returns None;
   consequence downstream **UNVERIFIED**).

Tests that pin the roster (both read the packaged JSON, not the DB):

- `tests/services/crm/test_lead_assignment_agent.py` (~L245-310): every GARUDA practice code has a
  department; at least one member is in `setup` with an `ASSIGNABLE_ROLES` role.
- `tests/services/garuda_portal/test_assignment_targets.py`: the set of roles in the JSON drives the
  fixture; every role must come back as an assignable target (derived from the validator, not a list).
- Not read this session: `tests/unit/core/test_team_roster.py` (named in the loader PR evidence brief).

## 4. Rules that apply

- Emails to the `@balizero.com` team are in Bahasa Indonesia (except zero@ and antonellosiano@);
  sent only as `zantara@balizero.com` via Brevo `/api/notifications/send-email`.
- PII is an OUTPUT boundary: no staff or client personal data in code comments, docs, PR bodies,
  memory, logs or skills. Use ids/roles/departments (as here). Never paste roster rows.
- A merge touching `apps/backend-rag/**` IS the backend deploy (memory: merging a backend-rag PR
  deploys by itself). A roster-JSON PR is therefore a deploy of `nuzantara-rag`.
- `DROP`/`INSERT`/`UPDATE` on prod DB (including reseeding `team_members`) is operator-only; M5 has
  no tier-1 guardrails.
- Off-limits per repo rules: `.env*`, `fly.toml`. Secrets (the PIN file, `TEAM_MEMBERS_JSON`) are
  never printed: use `${VAR:+SET}` probes only.
- Ship sequence (CLAUDE.md Builder Contract): worktree via `scripts/agent_start.py`, one concern per
  PR, `Bites:` line in the body, arm auto-merge at PR-open.

## 5. Roster change, safely

1. Read this file and the affected rows; decide what changes: role, department, new/offboarded member.
2. Edit `data/team_members.json` (keep the keys; do not add personal fields beyond what exists).
3. Run from `apps/backend-rag`: `PYTHONPATH=. python -m pytest
backend/tests/services/crm/test_lead_assignment_agent.py
backend/tests/services/garuda_portal/test_assignment_targets.py` (add
   `backend/tests/unit/core/test_team_roster.py` if the loader is touched).
4. Update the email-keyed places that apply: `SUPERVISOR_MAP`, `RUSLANA_REPORTS`/`TAX_MANAGER_EMAIL`,
   `LATE_EXEMPT_EMAILS`, `TEAM_AGENTS`, plus the tests that pin them.
5. Open the PR (merge = backend deploy). State in the body that the DB `team_members` row is NOT
   changed by the merge.
6. DB reseed (`scripts/seed_users.py` against prod) is a SEPARATE operator step; until it runs,
   `assign_lead` still sees the old role/department. Prove it live with a read-only query, not a guess.
7. Impact check before closing: who approves this person's leave, who is CC'd on a late incident,
   are they late-exempt, can lead assignment reach them (assignable role + department).

## 6. Related corners (not duplicated here)

- `/team <name>` — per-member profile, activity log and baseline, and department corners. Lives in
  the user skill dir (`~/.claude/skills/team`), not in this repo.
- `/setupteam` — setup-department corner (roster, aggregated baseline, activity log). Listed as an
  available skill in sessions; its file location is **UNVERIFIED**.
