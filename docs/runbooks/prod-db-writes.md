# Production Postgres: reads are automated, writes are the owner's hands

> Who this is for: any agent seat (Claude, Codex, Kimi, Qwen, agy) that needs a fact out of
> production, or believes production needs a change. Written 2026-09-06 after a loop in which
> several seats needed both at once.
>
> The short version: **an agent has a read path and no write path.** That is not an obstacle to
> work around — it is the control. An agent that needs a write prepares the exact statement,
> hands it to the owner, and then proves the result with the read path.

## The two doors

| Door      | Who                   | Reaches                             | How                                                                                                                                       |
| --------- | --------------------- | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **Read**  | any seat, any machine | `SELECT` only, prod `nuzantara_rag` | `scripts/pg.sh -c "SELECT …"` — role `nuzantara_readonly`, host `127.0.0.1:15432` (Fly proxy `com.nuzantara.fly-pg-tunnel`, auto-started) |
| **Write** | Zero (owner), by hand | anything, as a superuser            | `fly postgres connect -a nuzantara-postgres -d nuzantara_rag`, run interactively by the owner — never by a seat, on any machine           |

Measured 2026-09-06, because a runbook that repeats a stale fact is worse than one that names it:

- `flyctl` is installed at `/opt/homebrew/bin/fly` on **both** the Pro and Air-M5, which contradicts
  `AGENTS.md` §0.1 R5 ("M5 has no `fly`/`flyctl`"). R5's operative rule — deploy is Pro/CI-only —
  stands either way; reconciling the two sentences is an operator decision, not a docs edit, so the
  contradiction is flagged here instead of copied forward.
- The binary is not the door, the token is. `fly auth whoami`, run so that it reported only its exit
  status and never an identity: **Air-M5 NOT authenticated, Pro authenticated**. On M5 the write door
  is therefore technically closed; on the Pro it is technically OPEN to any session that runs there,
  and what keeps a seat out of production data is this rule plus the owner's review — not a missing
  capability. A seat that discovers it can write says so on the board. It does not use it.
- The read door is narrow by construction, and it was measured rather than assumed
  (`docs/plans/2026-08-24-garuda-voa-live/STEP5-PRIVILEGE-DECISION.md`, read-only, 2026-09-02):
  `pg_default_acl` holds four rows and every one of them is a **read** grant to `nuzantara_readonly`,
  there is no migration role, and there is no `SET ROLE` anywhere in the migration chain. A seat that
  "needs write access" is describing a task that needs the owner.

`fly postgres connect` defaults are `-d postgres -u postgres`; passing `-d nuzantara_rag` is what
lands the owner in the application database. Its `-p/--password` flag exists and must never be
used — see [Credentials](#credentials).

## What an agent does instead of writing

1. **Measure first, read-only.** The statement you ask the owner to run is justified by a
   measurement, not by a theory. `scripts/pg.sh -A -F'|' -c "SELECT …"` and quote the result.
   Counts and hashes, never rows of client data (Law 2 / Builder Contract §4: the read path is
   allowed to _reach_ client rows, a transcript is not allowed to _carry_ them — compare an
   `md5(lower(email))` instead of selecting the address).
2. **Write the exact statement** in the PR body or the scratchpad, with four things attached:
   the measurement that justifies it, the `ROLLBACK` statement, the expected affected-row count,
   and whether re-running it is idempotent.
3. **Hand it over as a blocked item, never as progress.** On a shared board:
   `blocked=<what is missing> needs=operator[secret]`. In a PR: the statement plus "owner-run".
   A prepared statement is not an applied one, and reporting it as done is the exact distance
   between a merged diff and a live one.
4. **Verify after the owner runs it — with the read path.** The owner's "fatto" is not evidence;
   the read-back is. Re-run the step-1 `SELECT` and put the before/after on the board with the
   command that produced each.

## Schema changes are releases, not writes

DDL does not go through the owner's psql session either — it goes through a migration:

- files: `apps/backend-rag/backend/db/migrations_v2/NNN_name.sql`, each with a mandatory
  `-- === ROLLBACK ===` marker;
- production applies them in the Fly release, forward-only, and then audits the schema
  (`apps/backend-rag/fly.toml:15`):
  `release_command = "sh -c 'python -m backend.db.migrate apply-all && python -m backend.db.schema_audit'"`;
- local: `PYTHONPATH=. python -m backend.db.migrate apply-all`.

A hand-run `psql -f` writes **neither** ledger (`schema_migrations`, `_schema_versions` are written
only by the Python runner's `_log_migration`), so the next deploy re-applies the same file and dies
on its first non-idempotent statement. The measured consequence, and the one legitimate exception —
an ownership transfer that only a superuser member of `visa_ledger_owner` can perform
(`flypgadmin`, `postgres`, `repmgr`), run as a manual superuser transaction and recorded in the
migration's own header, as 301's does — are in STEP5-PRIVILEGE-DECISION.md.

## Credentials

- **Never on argv, never in a transcript.** `fly postgres connect -p <password>` and
  `PGPASSWORD=… psql` both put a secret in the process list and in shell history. The connect
  command resolves the password itself; let it.
- **Presence, not value:** `${VAR:+SET}` reports that a variable is set, `${VAR:-default}` prints
  it. Only the first form belongs in a command anyone else will read.
- **Read-path secret:** Keychain service `nuzantara-postgres-readonly`, account
  `nuzantara_readonly`. `security find-generic-password` needs an unlocked LOGIN keychain, so a
  cron/launchd caller gets an EMPTY result — not an error — and `pg.sh` falls back to its own
  narrowly-scoped 0600 credential file (refused outright unless the mode is exactly 600). Both
  behaviours are documented in that script's header; an ssh probe that cannot read the Keychain is
  a limit of the probe, not a database failure.
- **Locators live in memory, not in docs.** `mem query "nuzantara-prod-smoke-login"` for the
  current smoke-login locator; `docs/runbooks/prod-crm-smoke.md` for the 0600 discipline, the
  secret-adjacent storage-state cache, and why `cat` on those files is forbidden in a shared
  transcript.

## Temporary principals: created for a probe, deactivated with proof

A gate probe sometimes needs a principal that must be refused (a partner-role account, to prove a
403 is a role decision and not a network accident). The rules:

- the owner creates it — an agent has no write path, and creating a row in `team_members` is a
  prod write like any other;
- it is deactivated at the end of the loop, and **deactivation is proven, not asserted**: a login
  attempt returns `401` with detail `Account inactive`
  (`apps/backend-rag/backend/app/routers/auth.py:407`, recorded as `failure_reason` at `:391`).
  The probe command and its 401 go on the board/PR as the proof line;
- a deactivated probe principal is never reactivated to re-run a test. Ask the owner; if the answer
  is no, the test is written against a fixture instead;
- no client PII in the principal's fields, and none in the proof line: the account is named by role
  and by the command that produced the 401, not by a pasted credential.

## If a credential reached a transcript

Rotate first, tidy second. A session transcript that ever carried a password, PIN, JWT or cookie is
an exposed artifact:

1. ask for rotation on the board — `needs=operator[secret]`, naming the credential class and where
   it landed, never repeating the value;
2. treat the transcript as quarantine: local only, never uploaded, copied into a doc/PR/memory, or
   synced to Drive (the same boundary `prod-crm-smoke.md` draws around the storage-state cache);
3. say plainly that the value already left the room. Editing the transcript without rotating the
   credential is theater — the copy you cannot see is the one that matters.

## The M5 classifier will refuse some of this — that is the guard working

On Air-M5 the auto-mode permission classifier denies commands that prepare a production write or
carry a credential literal. Expected. Do not fight it: no rephrasing, no encoding, no indirection
through a generated script or a config change, no `--dangerously-bypass`. Route the step to the
owner, or to the Pro where an operator runs it interactively, and record the denial verbatim on the
board with `needs=operator[gui]` or `needs=operator[secret]`. A denied command is a report to
relay, not a wall to tunnel through — and a seat that tunnels through it has just proved the guard
was the only thing standing between the fleet and production.

Machine routing for every other data service (Qdrant direct over Tailscale, the dev-DB tunnel, what
is never installed on M5) is `AGENTS.md` §0.1 R3; the local dev Postgres is
`docs/runbooks/m5-local-postgres.md` and is not production.

## See also

- `scripts/pg.sh` — the read-only one-true-way, its header documents the proxy, the Keychain and
  the cron fallback
- `docs/runbooks/prod-crm-smoke.md` — credential locators, 0600, secret-adjacent caches
- `docs/plans/2026-08-24-garuda-voa-live/STEP5-PRIVILEGE-DECISION.md` — the measured privilege
  facts quoted above
- `.claude/skills/pipeline-ship/SKILL.md` §6 — done means prove-live; the same standard applies to
  a write the owner ran for you
