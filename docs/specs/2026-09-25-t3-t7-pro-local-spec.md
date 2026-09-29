# Spec draft — Zantara team-agent gates T3–T7, rebuilt PRO-LOCAL

> Recovered 2026-09-29 from the at37-spec subagent transcript; the /tmp original was lost.

## Status 2026-09-29

- P1 extractor: live (#7646 judge).
- Linker: live (#7671; client 198/202, member 202/202 on Pro).
- Resolver (P2): next.
- Owner rulings: D2, D3, D5, D6 ruled 2026-09-28; D1 and D4 still open.

> Owner ruling 2026-09-25: "attiva": rebuild T3–T7, data never leaves Pro (Symbiosis Law 2).
> Drafted 2026-09-25 on M5, read-only. Every number below was measured on 2026-09-25 with the
> command noted; the file carries ids, hashes and counts only (no message bodies, names or phones).
> Status: DRAFT, needs the owner decisions in §7 before phases P5–P8.

## 0. What was grounded (and how)

- Code: `git grep` on `origin/main` for each table name across `apps/ scripts/ infra/`.
- Pro DB: `ssh pro` then `/opt/homebrew/bin/psql -h 127.0.0.1 -d nuzantara_dev` (psql is NOT on
  the non-interactive PATH on Pro; use the absolute path). Counts, schemas, max timestamps only.
- Fly DB: `scripts/pg.sh` (read-only role `nuzantara_readonly`, counts only).
- Pro-local regex dry-run: the v1 promise catalog was piped to `ssh pro 'python3 -'`; bodies were
  read and matched on Pro, and only aggregate counts came back to M5.

## 1. Measured state per gate

| Gate                | Pro today (measured)                                                                                                                                                                                                                                                                                                                                                                                                                          | Fly-era organ                                                                                                                                                                               | Verdict                                                                                                                                       |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| T3 promises         | `team_promises` **absent** on Pro. v1 regex dry-run, 30 d of mirror: 13,222 outbound, 10,719 with text, **372 matched** (342 direct, 30 group), 368 with `client_id`, **63 with a temporal cue** (83% would get `due_at` NULL and never go overdue). Fulfilment proxies inside the horizon: 168 have a later outbound media, 263 have a later customer ack.                                                                                   | `wa_copilot/team_promises.py` (523 l, regex, CLI). Fly: 7 rows, last 2026-05-25.                                                                                                            | No organ. Extractor exists and would feed ~12 rows/day.                                                                                       |
| T4 action queue     | `action_queue` **absent** on Pro. Naive R2 backlog (14 d, direct, client-linked): **68** threads whose last message is inbound, older than 24 h and newer than 7 d; 9 of them end with `?`.                                                                                                                                                                                                                                                   | `wa_copilot/action_queue_rules.py` (930 l, 9 rules, CLI). Fly: 110 rows, all `open`, last 2026-05-25. `telegram_notifier.py` needs Redis + `team_members.telegram_chat_id` (absent on Pro). | No organ. `≤20 open` needs a question filter plus auto-close.                                                                                 |
| T5 practice linking | `whatsapp_practice_candidates` **absent**. 30 d: 831 client-linked threads (thread×client), 576 distinct clients: 300 shared with Fly (same id+uuid), 276 Pro-only leads (`wa-mirror-crm-writer`). Only **68 clients / 77 threads** have any practice on Fly, and 12 threads have an open one. Pro `practices` = 141 rows (133 are Fly rows, stale since 2026-07-20); Fly has 1,093 rows, 400 of them added since.                            | `wa_copilot/practice_scorer.py` (743 l, pure SQL, no LLM). Fly: **0 candidates ever**.                                                                                                      | Blocked twice: no practices on Pro, and the 70% target is structurally unreachable (≤ 9.3% of client threads have a practice).                |
| T6 permissions      | `team_member_visibility_rules` 7 rows (1 viewer), `team_member_phone_authorizations` **0**. The cockpit `apps/wa-dashboard-m1` (Pro LaunchAgent `com.balizero.wa-dashboard-m1`, reads local `nuzantara_dev`) has **no per-user identity**, listens on `*:7790`, the macOS firewall is **off**, and `GET http://<pro-LAN>:7790/health.json` from M5 on 192.168.0.x returned **200**. `/data.json` and `/thread.json` sit on the same listener. | Fly `routers/team.py` applies the visibility rules to the team _roster_ only, not to chats.                                                                                                 | **Live Law-2 exposure**: anyone on the Pro's LAN can read mirrored chats. The negative test cannot pass because there is no identity to test. |
| T7 team outbound    | `wa_dashboard_outbound_queue` 0 rows, `whatsapp_operator_actions` 0. No producer or consumer in code (mig 193 only). wa-mirror has no send path; the only `sendMessage` is `apps/wa-mirror/scripts/wa-tester.ts`. `apps/wa-dashboard` was deleted 2026-08-06. The cockpit's only send is the proxy to `wa-meta-inbox` `/api/send` (business line).                                                                                            | none                                                                                                                                                                                        | No organ, and none can exist without an owner decision (§7 D5).                                                                               |

Mirror baseline (Pro): 147,344 rows, 1,644 in the last 24 h. 30 d: 31,132 rows (17,910 inbound /
13,222 outbound; 25,313 direct / 5,819 group); `client_id` set on 96.8%. 5 lines were active in
30 d and 4 in 7 d; all 4 `team_member_email` values map to `team_members`.

Fly-era truth: the wa_copilot pipeline was a **one-shot pilot on 2026-05-24/25**. It never had a
scheduler on `main` (no cron, plist or wrapper references any `wa_copilot` CLI), and it was already
dead before the cutover: Fly `whatsapp_conversations` 3,507 rows, 54 with `client_id`;
`whatsapp_extractions` 152 rows. Still imported on Fly: `telegram_notifier` (main_api, garuda
outbox). `routers/wa_actions.py` has no known caller (its own docstring says so, 2026-08-06).

## 2. Structural findings the plan must respect

1. **Pro migration ledger collision.** On Pro, `_schema_versions` slot 200 holds
   `200_strip_rollback_probe` (2026-05-10, a test probe), so `200_wa_copilot_infrastructure.sql`
   will never apply on Pro by number. Pro's ledger also stops at 246 (2026-07-18) while `main` is at 320. Any copilot table on Pro therefore needs a **new** migration number, written so it depends
   on nothing after 246.
2. **Merging `apps/backend-rag/**` deploys Fly, and the Fly release runs `migrate apply-all`**
   (`fly.toml:15`). A new migration must be a no-op on Fly: every statement `IF NOT EXISTS`. The
   index `uix_team_promises_msg_type` exists on Fly without any migration defining it (drift), and
   Fly has 0 duplicate `(message_id, promise_type)` rows, so `CREATE UNIQUE INDEX IF NOT EXISTS`
   under that name is safe on both sides.
3. **Pro `whatsapp_message_context` lacks the mig-200 columns** (`sender_role`, `conversation_id`,
   `identity_*`). Do NOT ALTER the hot mirror table. Derive the team role from `direction =
'outbound'` and a thread key `md5(team_member_phone || '|' || coalesce(chat_jid,
counterpart_phone, counterpart_lid))`; any per-thread state goes into a side table.
4. **v1 logic defects to fix, not port.** (a) The extractor counts past tense ("already sent",
   "sudah kirim", "già inviato") as a promise, when it is a fulfilment. (b) The resolver marks a
   promise resolved when the _customer_ says "ok/thanks" within 24 h of `due_at`, which measures
   politeness and not fulfilment. (c) `due_at` is NULL without a cue, so 83% of promises never go
   overdue. (d) `ON CONFLICT` relies on an index no migration creates.
5. **CRM authority is split.** Fly owns `practices` (the team creates them there). Pro owns the
   mirror-born leads (276 of the 576 active clients exist only on Pro, with ids above Fly's max, and
   there are 0 id collisions among the active 576). Practice data therefore has to flow **Fly → Pro**
   (into the Law-2 perimeter, never out), matched on client `uuid`.
6. **Notifications leave Pro.** Telegram and email are cloud. The established pattern
   (`scripts/wa-mirror-attention-telegram.py`, via `scripts/tg_notify.py`) sends codes, counts and a
   local link, never a body or a draft. `tg_notify` reaches only Zero; it has no per-member recipient.

## 3. Target architecture (everything runs on Pro)

| Organ                        | Runs                                                      | Reads                                          | Writes                                                                                           | Model                                                                                                 | PII boundary                                                                     |
| ---------------------------- | --------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| promise extractor + resolver | Pro cron `*/15` via `cron-runner.sh`, flock, id watermark | `whatsapp_message_context` (local)             | `team_promises` (local)                                                                          | none (regex)                                                                                          | bodies read locally; the table stores a ≤200-char window locally; nothing leaves |
| thread map                   | Pro cron `*/15`                                           | mirror                                         | `wa_thread_map` (local side table: `thread_key`, line, `client_id`, first/last customer/team ts) | none                                                                                                  | local only                                                                       |
| practices replica            | Pro launchd hourly                                        | Fly `practices` via `pg.sh` read-only role     | Pro `practices` upsert by `uuid` (client re-keyed by client `uuid`)                              | none                                                                                                  | inbound into Pro only; Pro-only rows untouched                                   |
| practice scorer              | Pro cron hourly                                           | `wa_thread_map`, `practices`, `practice_types` | `whatsapp_practice_candidates`                                                                   | none (SQL)                                                                                            | local only                                                                       |
| action rules R1+R2           | Pro cron `*/15`                                           | promises, thread map                           | `action_queue`                                                                                   | Pro Ollama `qwen3.5:9b` (`think:false`) classifies "question/request vs closing" and writes the draft | draft stored locally only; ping = `action_id`, type, member, count, cockpit link |
| notifier                     | Pro, after rules                                          | `action_queue`, `team_promises`                | ping ledger column                                                                               | none                                                                                                  | per §2.6; the channel is owner decision D2                                       |
| cockpit + identity           | Pro `wa-dashboard-m1`                                     | all of the above                               | none (read-only)                                                                                 | none                                                                                                  | loopback/tailnet only (P0); per-member filter via authorizations (P7)            |

LLM seat: Pro Ollama (`com.nuzantara.ollama`, 48 GB RAM; `qwen3.5:9b` already serves the
PII-bearing `wa-mirror-attention-classifier`, plus `qwen3.8:27b-mlx` and `bge-m3`). **Excluded:**
Mini's Ollama (the data would leave Pro), the `claude` CLI OAuth (cloud; allowed for writing code,
never for bodies), and any paid API. `extraction_pipeline.py` is already Ollama-local, but T3–T5 do
not need it in this plan.

Code placement: Pro-local organs live in `scripts/` (repo convention for Pro-only organs, e.g.
`scripts/wa_mirror_intake_sweeper.py`) and run under `apps/backend-rag/.venv/bin/python` with
`PYTHONPATH=apps/backend-rag`, importing the v1 regex catalog from
`backend.services.wa_copilot.team_promises` (light imports: stdlib + asyncpg). This keeps
organ PRs out of `apps/backend-rag/**`, so they do not trigger a Fly deploy. Only the migration
PRs touch backend-rag. Plists and wrappers are tracked in `infra/launchagents/` (scar #1): no
HOME-only wrapper like `~/scripts/wa-mirror-enrichment-wrapper.sh`.

## 4. Phased PR plan (one concern each, ≤ ~400 net lines)

**P0: cockpit containment (T6 prerequisite, security, ~40 l).** `wa-dashboard-m1` default
`HOST` → `127.0.0.1`. Tailnet access goes through `tailscale serve` (single-user tailnet, 11
devices, all Zero's), and the LaunchAgent plist is tracked in `infra/launchagents/`.
Bites: Zero's cockpit over the tailnet URL. Observation: from M5 on the LAN,
`curl -m4 http://<pro-LAN>:7790/health.json` → `000` (refused); the tailnet URL → `200`.
KPI: LAN probe code.

**P1: T3 extractor goes live (THE phase-1 PR; ~330 l incl. tests).**

- `apps/backend-rag/backend/db/migrations_v2/<next>_team_promises_pro_local.sql`:
  `CREATE TABLE IF NOT EXISTS team_promises` (mig-200 shape; `conversation_id` without FK) + `ADD
COLUMN IF NOT EXISTS thread_key text, team_member_email text, extractor_version text,
resolution_kind text` + `CREATE UNIQUE INDEX IF NOT EXISTS uix_team_promises_msg_type
(message_id, promise_type)`. Fly: no-op on the tables, 4 nullable columns on a frozen 7-row table.
- `scripts/wa_team_promises.py`: imports `_PROMISE_PATTERNS_RE`/`_TEMPORAL_CUES`. Only
  `direction='outbound'` rows with text count. Past-tense matches are split off as fulfilment
  (not stored as promises). `due_at` = the cue, else the D6 default. Id watermark, flock, metrics
  JSON, counts-only logs.
- A tracked wrapper plus a crontab line (`*/15`, `cron-runner.sh`). The consumer ships in the same PR:
  a `tg_notify --tier digest` line with counts only (`promises: new N, open N, overdue N`, per line hash).
- Tests: catalog split (future vs past tense, id/en/it), watermark idempotency, a guilt case (a
  past-tense line is NOT a promise) and an innocence case.
- Bites: the Pro cron writes `team_promises`; Zero's digest shows the count. Observation after the
  first tick on Pro: `select count(*), count(due_at) from team_promises where created_at > now() -
interval '1 hour'` > 0, and the digest spool carries the line. Expected rate ≈ 12/day (30 d dry-run).
- Deploy: the migration applies on Pro by number (session; additive, new tables/columns only, not
  the mirror table) and on Fly via release (no-op).

**P2: T3 resolver + precision audit (~300 l).** Resolution evidence, in order: a later outbound
media in the thread (`resolution_kind='media_sent'`), a later team past-tense match of the same type
(`'team_confirmed'`), a later customer ack (`'client_ack'`, weakest; kept separate so it can be
excluded from the KPI). A local precision judge (`qwen3.5:9b` on 100 random promises; the output is
precision and recall _counts_; generator = regex, grader = local LLM). Bites: the digest reports
`resolved_by_kind`. KPI: precision ≥ 0.8 on the judged sample; overdue-unresolved trend.

**P3: T3 overdue → responsible member (~200 l, needs D2).** One ping per member per day with
counts and a cockpit link, keyed by `team_member_email`, deduped by `promise_id`. The body never
carries a promise window or a client name. KPI: `overdue ∧ ¬notified` = 0 after the daily tick.

**P4: T5 practices replica Fly → Pro (~250 l, needs D3).** Hourly pull of Fly `practices` through
`pg.sh` (read-only). Upsert into Pro by `uuid`, and re-key `client_id` through the client `uuid`. The
8 Pro-only rows are left as they are, and unmatched clients are counted, not created. Bites: the P5
scorer. Observation: Pro `practices` ≈ Fly count (1,093 on 2026-09-25); active clients with a
practice go 12 → ~68. Writes to Pro `practices` = the session, under D3.

**P5: T5 thread map + scorer (~380 l).** Migration for `wa_thread_map` and
`whatsapp_practice_candidates` (`IF NOT EXISTS`, plus a `thread_key` column), and the scorer
adapted to the thread map. Weights stay: client 0.35, temporal 0.15, name 0.10; service-token 0.25
falls back to practice-type keywords in the local window, and attachment stays 0.
Bites: the cockpit shows the candidate practice per thread (a read-only column). KPI (D3
denominator):

```sql
with t as (select thread_key, client_id from wa_thread_map
           where last_msg_at > now() - interval '30 days' and client_id is not null
             and exists (select 1 from practices p where p.client_id = wa_thread_map.client_id))
select count(*) filter (where exists (select 1 from whatsapp_practice_candidates c
                                      where c.thread_key = t.thread_key)) as linked,
       count(*) as eligible from t;   -- target linked/eligible >= 0.70 (today 0/77)
```

**P6: T4 action queue R1 + R2 (~380 l).** Migration `action_queue` (`IF NOT EXISTS` + `notified_at`).
R1 `followup_team_commitment` fires when a promise is overdue and unresolved. R2
`followup_client_unanswered` fires when the last message is inbound, older than 24 h and newer than
7 d, _and_ local qwen classifies it as a question or request. The draft comes from local qwen
(stored only). Auto-close runs when an outbound reply or a resolution arrives. Bites: the P3
notifier pings each `followup_*`. KPI:
`select count(*) filter (where status='open') open, count(*) filter (where action_type like
'followup_%' and (suggested_message_draft is null or notified_at is null)) gap from action_queue;`
target open ≤ 20, gap = 0.

**P7: T6 identity + filter (~380 l, needs D1 + D4).** Every cockpit read goes through one
`authorizedLines(userEmail)` = active `team_member_phone_authorizations` ∪ lines of the members
visible under `team_member_visibility_rules`. Identity comes from either the tailnet (Tailscale
identity header via `serve`) or the intake-review pattern (`HybridAuthMiddleware` + the Fly JWT,
behind cloudflared). Seeding the grants is a Pro DB write of business data (D4). The negative test
ships in the PR: member A's identity → member B's `/thread.json` → 403 and `/data.json` without B's
lines. KPI: the probe runs daily in cron; 0 cross-member rows.

**P8: T7, no PR until D5.**

## 5. Data-migration needs

- The new migration numbers must come from `origin/main` at PR time; `320` is the highest today.
  On Pro they are applied by number with `migrate.py` against the Pro DSN. The slot-200 probe row
  stays (deleting ledger rows = operator).
- No ALTER on `whatsapp_message_context` (1.6k writes/day from the live bridge).
- Practices replica: 133 rows update in place by `uuid`, ~960 are new, 8 Pro-only are kept.
  Clients are NOT replicated (Pro-only leads are Pro's own; Fly clients missing on Pro are
  counted, not created).
- Backfill: P1 seeds its watermark 30 d back (≈372 candidate messages) so the gate has history on day 1.

## 6. Risks

| Risk                                                                                                 | Mitigation                                                                                                 |
| ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Regex precision (past tense, courtesy "I'll check") inflates T3/T4                                   | P1 tense split; P2 local judge gate ≥ 0.8 before P3 pings anyone                                           |
| Ollama contention with the live attention classifier (same `qwen3.5:9b`) and the 22:05 unload window | P6 batches ≤ 50 per tick, degrades to "no draft, no ping" (never cloud); the metric counts the degradation |
| Migration applies on Fly via release                                                                 | `IF NOT EXISTS` everywhere; guilt test on a scratch DB that already holds the Fly shape                    |
| HOME-fork (#1): wrappers outside the repo                                                            | Tracked wrappers + plists; `lint_home_fork` covers them                                                    |
| Esiste≠Armato (#2): cron "green" with 0 rows                                                         | Every organ emits `rows_written` to the digest; 0 for 24 h = digest RED line                               |
| Notification carries PII to the cloud                                                                | Payload allowlist = codes, counts, ids, link; a unit test fails if a window or name reaches the gateway    |
| Two CRMs diverge further (Pro leads vs Fly)                                                          | Out of scope; the replica is one-way and uuid-keyed; the drift is reported, not fixed                      |

## 7. Decisions only the owner can take

- **D1 Cockpit transport for team members.** Tailnet-only (today a single-user tailnet: members
  would need invites) or the intake-review precedent (TLS transit through Fly/Cloudflare, JWT, no
  store/cache). The ruling "data never leaves Pro" has to say whether TLS transit counts.
- **D2 Member notification channel (T3/T4).** Per-member Telegram (needs chat ids), a WA template
  from the business line, or cockpit-only plus Zero's digest. The content is PII-free in every case.
- **D3 T5 denominator + practices replica.** The literal target (≥70% of client threads) is
  unreachable: 77/831 = 9.3% of client threads in 30 d belong to a client with any practice.
  Proposal: denominator = threads whose client has ≥1 Fly practice, and Fly → Pro one-way replica
  of `practices`.
- **D4 Access matrix.** Who sees which line (today 7 rules for 1 viewer, 0 phone grants).
- **D5 T7.** Sending from members' personal Baileys lines carries ban risk, and those lines are
  already fragile (2 logged out, 1 unlinked). Recommendation: retire T7 as written, or re-scope it
  to "drafts approved in the cockpit go out on the Meta business line" (reuse `wa_outbox`
  idempotency).
- **D6 Default `due_at` without a temporal cue.** Proposal: +48 h (v1: NULL → never overdue).
- **D7 P0 containment.** Needs no business decision, but it changes the cockpit URL for anyone
  who uses the LAN address.

## 8. Side findings (outside T3–T7, report only)

- The kita.balizero.com WA timeline (`routers/wa_mirror_messages.py` → mouth
  `lib/api/whatsapp/whatsapp.api.ts`) reads **Fly** `whatsapp_message_context`, which has been
  frozen since 2026-05-25, so the team sees stale history there.
- `apps/team-agent` (MCP role wrapper) is a different organ and not the T3–T7 host.
