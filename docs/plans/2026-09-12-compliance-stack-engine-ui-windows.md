# Compliance stack — ENGINE and UI windows (2026-09-12)

Mission: compliance-stack second wave, BLUE (undeclared), imperator Fable 5.1 (owner-opened, M5),
one Dux Opus 5 xhigh per PR in its own worktree, Sonnet 5 implementers where useful, a FRESH Opus 5
gate per Gear ≥ 2 PR commissioned by the imperator (never by the Dux). Zero's go: "ok" on the
2026-09-12 status report; standing mandate "sviluppare tutto" (2026-09-11).

Predecessor: the 2026-09-11 build (12 PRs, all live) — design and roundtable minutes on Pro under
`~/Desktop/ricerca-nicchie-online-indonesia-2026-09-11/` (`build/DESIGN-lane-A.md`,
`tavolo-llm/00-VERBALE.md`). The roundtable ruled: PSE is the funnel, the product is the obligations
register plus reviewer queue sold to existing PT PMA clients in a 30-day pilot; no client-facing
portal before the service has been sold. This wave respects that fence: every PR below serves the
tax team's reviewer, none serves a client directly.

## State on 2026-09-12 (measured by the imperator)

| Surface                                                           | State                                                                            |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `backend/services/compliance/obligations_register.py` (452 lines) | pure engine; weekend roll only; one_time/event rules schedule nothing            |
| `backend/data/obligations_catalog.yaml`                           | 21 rules, `verified: true` = 0, 10 with needs_review_reason, 3 one_time, 3 event |
| `backend/app/routers/compliance_obligations.py`                   | GET list, GET one, POST generate, POST approve, POST reject; all `is_crm_admin`  |
| `client_obligations` on prod                                      | 0 rows — the first `/generate` has never run (owner input: client_id)            |
| `apps/mouth/src/app/(workspace)/obligations/page.tsx` (680 lines) | live at kita.balizero.com/obligations; shows ids only                            |
| `backend/services/garuda_flow/operating_calendar.py`              | 2026 libur nasional + cuti bersama table (reuse for the roll)                    |
| Company attributes                                                | `companies.custom_fields` keys read by `profile_from_rows`; no client has them   |

## Ground rules for every Dux (binding)

- Worktree: from `/Users/balizero/nuzantara`, `python3 scripts/agent_start.py --lane <lane> --task-id <task-id> --ttl-min 240`;
  work ONLY under the printed path; branch `agent/air-m5/<lane>/<task-id>`. The main checkout is read-only.
- One PR, one concern, ≤ ~400 net lines. Conventional commit, `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`
  on every commit. Push, `gh pr create`, `gh pr merge --auto --squash <n>` are three separate commands; arm at PR-open.
- Evidence pack: `python3 scripts/ci/evidence_paths.py --ref "$(git rev-parse --abbrev-ref HEAD)"` → write `brief.yml`
  (gear as computed by `python3 scripts/evidence_pack_lint.py --print-floor --changed-files-file <cf> --numstat-file <ns>`,
  declare exactly that floor) and, at Gear 3, `pack.yml`.
- PR body carries `Bites:` naming the consumer and the observation, and `## Adversarial review` with the Codex spalla
  verdict (`scripts/codex_tri_llm_review.py::review_codex` or `codex exec --sandbox read-only < /dev/null`).
- Do NOT post `harness/fable-gate`; the imperator commissions a fresh Opus 5 gate on your head sha. Do not rerun a red
  check before knowing why it is red. Three reds for one cause → stop and report.
- Never touch `fly.toml`, `.env*`, `zantara_core.py`, lockfiles. No PII in any artifact: client ids only, never names in
  packs or PR bodies. No paid Anthropic endpoint. `${VAR:+SET}` only, one probe per line.
- Backend tests, from `apps/backend-rag`: `source .venv/bin/activate && PYTHONPATH=.:../crm-cell pytest <paths> -q`.
  Mouth: from `apps/mouth`: `npm run lint`, `npx tsc --noEmit`, `npx vitest run <file>`, `npm run build`.
- Merging a PR under `apps/backend-rag/**` IS the deploy (Fly deploys post-merge main). Merging under `apps/mouth/**`
  auto-deploys Vercel. Prove-live is the imperator's step; report the exact command it should run.
- Report (≤ 250 words): branch, worktree, PR number + URL, head sha, files with net lines, tests with exact commands and
  exit codes, evidence dir, Bites line, what was left out and why, the ONE command the gate should run.

## ENGINE window (lane backend-rag)

### M1 — holiday-aware roll (task-id `obligations-holiday-roll`)

Problem: `due_dates()` rolls Saturday/Sunday only; a statutory due date that falls on libur nasional or cuti bersama
does not move, so the register proposes a date the office cannot act on and DJP does not require. PMK 81/2024 defines
"hari libur" for tax deadlines as Saturday, Sunday, national holidays, election days and cuti bersama; the deadline
moves to the next business day (verify the article and quote it in the module docstring).

Build:

1. `backend/services/compliance/business_days.py`: `is_business_day(day) -> bool`, `next_business_day(day) -> date`,
   `holiday_years_loaded() -> frozenset[int]`. Holiday data: REUSE the 2026 table already in
   `backend/services/garuda_flow/operating_calendar.py` — import its libur_nasional and cuti_bersama dates (read the
   module first; if the table is a private constant, move it to a shared `backend/data/id_holidays.py` or `.json` and
   have BOTH modules read it — never copy the dates by hand). Bali Zero's own closures (the December operating window)
   are NOT statutory and must NOT move a due date.
2. `obligations_register.py`: `roll == "next_business_day"` uses `next_business_day()`. When a due date's year has no
   holiday table, roll weekends only and attach `needs_review_reason` "holiday calendar for <year> not loaded" to the
   proposal (append to the rule's own reason with "; " if one exists). Update the module docstring (the "NOT modelled
   in v1" sentence goes).
3. Tests `backend/tests/services/compliance/test_business_days.py` (≥ 8) and additions to
   `test_obligations_register.py`: due on a national holiday moves; due on cuti bersama moves; due on Friday before a
   Monday holiday moves to Tuesday; a year without a table rolls weekends only and flags the reason; `roll: none` rules
   never move. Existing 42 tests stay green.

Acceptance: `pytest backend/tests/services/compliance -q` exit 0 with ≥ 55 tests; `python3 -c` probe printing the
2026 roll of a synthetic PT PMA profile over 120 days in the PR body (rule_id, period_key, due_date, reason).
Bites: consumer = `POST /api/compliance/obligations/generate`; observation = a proposal dated on a 2026 holiday
before the change, and on the next business day after it, shown in the PR body from the probe.

### M3 — catalog and profile endpoints (task-id `obligations-profile-api`) — parallel with M1

Problem: the reviewer screen can only show `rule_id`, and no client carries the `custom_fields` keys the engine reads,
so every profile collapses to the defaults and `applies()` proposes the minimum.

Build, in `backend/app/routers/compliance_obligations.py` (same admin gate on every route):

1. `GET /api/compliance/obligations/catalog` → `[{id, name, authority, legal_source, verified, frequency, roll,
needs_review_reason, trigger, notes}]` from `_cached_rules()`; no client data.
2. `GET /api/compliance/obligations/profile/{client_id}` → the computed `ClientProfile` as a dict PLUS
   `present_keys` (custom_fields keys found), `missing_keys` (attributes at default), `company_type_raw`
   (the companies.company_type string) and `needs_manual_classification`. 404 when the client does not exist.
3. `PATCH /api/compliance/obligations/profile/{client_id}` body = any subset of the engine ATTRIBUTES
   (`company_type` accepted only as one of COMPANY_TYPES, stored under custom_fields key `compliance_company_type`
   and honoured by `profile_from_rows` BEFORE the company_type string mapping; document this precedence in the
   docstring), validated with the same `_as_bool/_as_int/_valid_fye` rules. Merge into `companies.custom_fields`
   for the client's company (create nothing; 409 when the client has no company row — say so in the detail).
   Follow the JSONB merge already used in `backend/app/routers/crm_enhanced.py` (read it; do not hand-roll a new
   pattern). Return the recomputed profile. Log `compliance.obligations.profile.patch client_id=.. keys=[..]`, never values.
4. Tests in `backend/tests/unit/app/routers/test_compliance_obligations.py` from the existing template: catalog 200
   with 21 rows and 403 non-admin; profile 200 with missing_keys, 404 unknown client; patch merges without wiping
   unrelated keys, rejects an unknown key (422) and an invalid company_type (422), non-admin 403.

Acceptance: router tests exit 0 (≥ 30 total); `PYTHONPATH=. python -c "from backend.app.main_cloud import app"`
imports; no migration. Bites: consumer = the UI PRs U1/U2 below; observation = `GET .../catalog` on prod returning
21 rows (imperator, admin JWT) or, failing a JWT, the CI merge-group run on the head sha plus `/health` build_sha.

### M4 — catalog source verification (task-id `obligations-catalog-sources`) — parallel with M1/M3

Problem: 0 of 21 rules is `verified: true`; every `legal_source` carries "(verify)". The reviewer cannot trust a
proposal whose legal basis is a guess.

Build (data + doc, no code):

1. For each of the 21 rules verify the legal basis and the due-date rule against a PRIMARY source (jdih.kemenkeu.go.id,
   pajak.go.id, peraturan.bpk.go.id, jdih.komdigi.go.id, bkpm.go.id, kemnaker.go.id, bpjs sites). Use WebFetch /
   WebSearch and `agy -p` for the Bahasa reading; NotebookLM verdicts are leads, never facts. Known corrections already
   measured: PMK 81/2024 art. 94 — withholding deposit by the 15th of the following month, SPT Masa by the 20th, PPN by
   the end of the following month (memory 2026-09-11).
2. Edit `backend/data/obligations_catalog.yaml`: fix `legal_source` (article numbers, the source URL in the string),
   fix any wrong `due`, remove "(verify)" only where confirmed, set `verified: true` only when BOTH the basis and the
   date are confirmed by a primary source. Rules that stay unconfirmed keep `verified: false` and get a sharper
   `needs_review_reason`. Do not add or remove rules; do not change ids.
3. `docs/compliance/obligations-catalog-sources-2026-09.md`: one row per rule — rule id, claim, source URL, retrieved
   date, verdict (confirmed / corrected / unconfirmed), what changed. Link it from the catalog header comment.

Acceptance: `pytest backend/tests/services/compliance/test_obligations_register.py -q` exit 0 (fix any date test the
correction invalidates, and say which); ≥ 12 rules `verified: true`; every `verified: true` rule has a URL in
`legal_source`; the doc has 21 rows. Bites: consumer = the reviewer reading `legal_source` in the queue (after U1);
observation = the doc's verdict column and the `verified: true` count in the PR body.

### M2 — one_time triggers (task-id `obligations-one-time-triggers`) — AFTER M1 merges, from fresh origin/main

Problem: `pse_registration`, `pmse_vat_assessment`, `halal_certification` apply to a profile and produce nothing, so
the exact obligations the compliance offer sells never reach the queue.

Build:

1. `propose()`: when `rule.due.frequency == "one_time"` and `applies()`, emit ONE proposal with `period_key = "once"`,
   `due_date = start` (the generation date) and `needs_review_reason` = the rule's reason joined with
   "one_time: due date is the generation date, set the statutory deadline on review". `event` rules stay unscheduled
   (their dates are per person or per event). Idempotent by the existing UNIQUE (client_id, rule_id, period_key).
2. Optional `due.fixed_date: YYYY-MM-DD` for one_time rules (halal UMK deadline): when present and ≥ start, due_date =
   fixed_date; parse and validate it in `_parse_due`; catalog gets it only for `halal_certification` if M4 confirmed
   the date, otherwise leave the catalog untouched.
3. Tests: one_time proposal emitted once per client; event still empty; fixed_date honoured; re-run over the same
   horizon does not duplicate (repository test with mock pool).

Acceptance: engine tests exit 0 (≥ 60 total). Bites: consumer = `POST /generate`; observation = the probe of a
FOREIGN_PLATFORM profile printing `pse_registration/once` and `pmse_vat_assessment/once` in the PR body.

## UI window (lane mouth) — after M3 is live on Fly

### U1 — reviewer usability (task-id `obligations-reviewer-usability`)

Build in `apps/mouth/src/app/(workspace)/obligations/page.tsx` (split components into
`apps/mouth/src/app/(workspace)/obligations/components/` if the page passes ~800 lines):

1. Load `GET /api/compliance/obligations/catalog` once; render rule NAME, authority and a `verified` / `unverified`
   badge in the table; `legal_source` in the row detail. Never duplicate the catalog in the frontend.
2. Client column: resolve `client_id` → display name through the existing CRM read used elsewhere in the workspace
   (ground it: `GET /api/crm/clients/{client_id}/profile` in `crm_enhanced.py`, or the workspace's client list hook);
   cache per id; fall back to the id when the read fails. Client names stay in the browser session only.
3. Status counters (proposed / approved / rejected / alerted) for the current client filter, from the list endpoint's
   `total` with `limit=1` per status, in parallel.
4. Group the table by due month when a client filter is set; keep the flat table otherwise.
5. Tests in `page.test.tsx`: catalog badge rendering, client name fallback, counters, month grouping.

Acceptance: `npx vitest run 'src/app/(workspace)/obligations'` exit 0; `npx tsc --noEmit` exit 0; `npm run build`
exit 0; zero forbidden phrases (`skills/bali-zero-brand/voice/forbidden-phrases.md`) in the copy.
Bites: consumer = the tax team on kita.balizero.com/obligations; observation = the imperator's browser screenshot
of the live page showing a rule name and a verified badge (empty state acceptable while the pilot has not run).

### U2 — client compliance profile form (task-id `obligations-client-profile-form`) — AFTER U1 merges

Build a "Client profile" panel on the same page (own component file): loads `GET .../profile/{client_id}` when the
client filter is set, shows the computed attributes with `missing_keys` highlighted, lets the reviewer edit
`company_type` (select over COMPANY_TYPES), the booleans, `employee_count`, `annual_turnover_idr`,
`fiscal_year_end` (MM-DD), `investment_stage`; `PATCH` on save; on success refresh the profile and offer "Generate"
again. Tests: form renders missing keys, PATCH payload contains only touched keys, 409 shows "no company on file".
Acceptance as U1. Bites: consumer = the reviewer preparing the first pilot client; observation = a PATCH on a
pilot client followed by `/generate` proposing PPh 21 rules that the default profile did not (imperator, after
Zero names the client_id).

## Owner inputs (unchanged)

`client_id` of the pilot PT PMA; delivery owner; advisory freeze; who holds the izin konsultan pajak.

## Sequence

Wave 1 in parallel: this spec (docs, Gear 1), M1, M3, M4. Wave 2: M2 (after M1), U1 (after M3 live). Wave 3: U2
(after U1). Serialize any two PRs that touch the same file; a Dux that finds its base moved rebases on fresh
`origin/main`, never on a sibling branch.
