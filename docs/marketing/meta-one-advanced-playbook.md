# Meta One Advanced — Bali Zero playbook and steward spec

> Written 2026-09-16, the day after Meta launched Meta One (2026-09-15). Zero subscribed to the
> **Advanced** business plan covering Facebook and Instagram. This file is the single shared
> context for the subscription: what we bought, what we do with it, who does it, and the organ
> that keeps it honest. The `/metaone` corner loads it; the steward cron enforces it.
>
> **BUSINESS:** $49.99/month buys reach, clickable links and trust signals. It pays for itself
> with ONE attributed lead per month. Unused monthly quotas are money burned — the steward's job
> is that nothing expires unused and that Zero sees, every Monday, whether the plan is earning.

## 0. TL;DR

| Fact      | Value                                                                                                                           |
| --------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Plan      | Meta One **Advanced** (business/creator bundle), $49.99/month, one subscription = FB + IG + WA                                  |
| Instagram | `@balizero0` (~10.3K followers, April 2026 snapshot)                                                                            |
| Facebook  | `facebook.com/balizero` — dormant; Advanced's growth features are FB-heavy, so FB comes back                                    |
| Publisher | Damar (editorial delegation 2026-09-01). Law 5: a human publishes, never the pipeline                                           |
| Telemetry | The Instagram Graph token is **DEAD since 2026-08-31** (session invalidated on password change). Re-issue is `operator[secret]` |
| Steward   | `pro.meta_one_steward` — daily cron on Pro, quota ledger + token probe + Monday brief on Telegram                               |

## 1. What we bought (Meta Help Centre + newsroom, 2026-09-15)

Business/creator tiers: Essential $14.99 · **Advanced $49.99** · Expert $149 · Max $499 per month.
"Plans, benefits, pricing and availability may vary by region, by app and by account."

**Essential (included in Advanced):** verified badge on Instagram and Facebook; impersonation
protection; images next to links in the profile linksheet; more 24/7 responses from Meta Business
Agent on Messenger; the Facebook Plus / Instagram Plus / WhatsApp Plus consumer features.

**Advanced adds — with the monthly quotas the steward tracks:**

| #   | Benefit (Meta wording)                                                               | Platform  | Quota / month |
| --- | ------------------------------------------------------------------------------------ | --------- | ------------- |
| A1  | Opportunity to be **featured in Feed**                                               | Facebook  | —             |
| A2  | **Optimised search** — easier to find the profile                                    | FB + IG   | —             |
| A3  | **Bold follow button** on Reels                                                      | Facebook  | —             |
| A4  | **Automatic follow invitations** to people who engage                                | Facebook  | —             |
| A5  | **Team access**: up to 4 other people on the Instagram account, no password sharing  | Instagram | 4 seats       |
| A6  | **Schedule** reels and posts up to a year ahead; stories up to 30 days ahead         | FB + IG   | —             |
| A7  | **Clickable links in posts**: 4 Instagram + 8 Facebook                               | FB + IG   | 4 IG / 8 FB   |
| A8  | **Clickable links in reels**: 4 Instagram + 8 Facebook                               | FB + IG   | 4 IG / 8 FB   |
| A9  | **Competitive insights** — compare the profile's performance to others'              | Instagram | —             |
| A10 | **Audience insights** + **exportable analytics**                                     | FB + IG   | —             |
| A11 | Premium support: **chat with a human agent**                                         | Meta      | 1             |
| A12 | **Content credit** notifications (reuse of our content → request the original label) | FB + IG   | 2             |
| A13 | More linked devices, business broadcast credits, more Business Agent responses       | WhatsApp  | plan-defined  |

Sources: Meta Help Centre "About Meta One plans" (960854640235758), Meta Newsroom 2026-09-15,
TechCrunch 2026-09-15, Metricool "Meta subscriptions". Quotas are the Help Centre's wording on
2026-09-16; the steward keeps them in one constant so a Meta change is a one-line edit.

## 2. Where we stand (verified on disk and live, 2026-09-16)

- **IG token dead.** Pro `~/logs/wr2-ig-metrics-scrape.log` 2026-08-31: `Error validating access
token: The session has been invalidated because the user changed their password`. Every Graph
  reader in the repo (`scripts/wr2_ig_metrics_scraper.py`, `wr2_ig_discovery.py`, the measurer
  package) is starving. Prod `war_room_metrics` / `post_metrics_history`: 0 rows.
- **The real metrics live on Pro**, in `apps/war-room/output/queue/human-review-queue.json`:
  102 items — 51 published (50 with metrics, last published 2026-08-13), 49 drafted, 2 rejected.
  This is the backlog Advanced's scheduling turns into a quarter of content.
- **WR2 is manual-only** (Zero ruling 2026-09-01): `wr2.measurer` disabled in
  `apps/organism/organism/organs_registry.yaml`; the weekly IG analyst plist is `.disabled`.
- **Zantara already answers IG DMs and WhatsApp** (`services/integrations/instagram_service.py`,
  `channels/instagram/adapter.py`) with the grounded RAG brain and local PII handling.
- **Competitor watch is screen-scrape** (`.claude/agents/competitor-monitor.md`: Lets Move
  Indonesia, Emerhub, Flado). Advanced's competitive insights replace its Instagram half.
- **Site handle drift:** `apps/mouth/src/components/seo/JsonLd.tsx:26` says `instagram.com/balizero`,
  `EnhancedJsonLd.tsx:46` says `balizero0`. With optimised search and a verified badge the
  `sameAs` must name the verified handle. One-line fix, separate PR.

## 3. The seven plays

Each play: benefit → action → owner → KPI. Cadence is weekly unless stated.

**P1 — Trust shield (A2, badge, impersonation).** Complete Meta verification on both FB and IG
(ID documents = Zero). Align bio, name, category, location and website on FB, IG and WhatsApp
Business so search and impersonation matching see one entity. Fix `sameAs` on the site. KPI:
badge visible on both profiles; 0 impersonation incidents; profile search position for
"bali zero visa" (manual monthly check). Owner: Zero (verification), session (site).

**P2 — Link engine (A7, A8).** Every clickable-link slot carries a UTM link to the matching
service page: `https://balizero.com/<page>?utm_source=<instagram|facebook>&utm_medium=meta_one_link&utm_campaign=<WR2-ref>`.
Instagram slots (4 posts + 4 reels) are reserved for the four highest-intent topics of the month
(E33 Second Home, KITAS/investor, PT PMA setup, tax deadlines); Facebook slots (8 + 8) take every
carousel and reel. The steward counts used slots and, five days before month end, flags unused
ones. KPI: `profile_links_taps` and post clicks; `war_room_leads` rows with
`utm_medium=meta_one_link`. **ROI rule: ≥1 attributed lead/month covers the plan.** Owner: Damar
(placement), steward (count), session (UTM landing pages already exist under `/visas`, `/business`).

**P3 — Schedule the backlog (A6), Law 5 intact.** The 49 drafted carousels become a scheduled
quarter: Damar schedules 3 posts + 3 stories per week in Business Suite, up to a year ahead. The
human schedules; no script ever calls a publish or schedule endpoint. Damar keeps sending the
`PUBBLICATO WR2-XXXXXX <url>` self-note so the queue advances. KPI: scheduled count ≥ 12 at any
time; published/week ≥ 3. Owner: Damar; steward reports queue → scheduled → published.

**P4 — Facebook revival (A1, A3, A4).** Advanced's growth features (featured in Feed, bold follow
on Reels, automatic follow invitations) are Facebook-only, and our Page is dormant. Cross-post
every IG carousel as an FB post and every reel as an FB reel; complete the Page (services,
location, hours, WhatsApp CTA, reviews on). KPI: Page follows/week, reach/week from the export.
Owner: Damar (posting), Zero (Page ↔ IG link in Business Suite).

**P5 — Intelligence (A9, A10).** Once a month Damar exports Instagram and Facebook analytics
from Business Suite and drops the CSV into `shared/meta_one/exports/YYYY-MM/` on Pro (no PII:
aggregates only). The steward ingests it — a token-free telemetry path that works while the Graph
token is dead. Competitive insights vs Emerhub / Lets Move / Flado go into the monthly
competitor digest instead of screen-scraping. KPI: export present every month; competitor delta
recorded. Owner: Damar (export), steward (ingest), `competitor-monitor` (digest).

**P6 — Team and support (A5, A11, A12).** Add Damar plus one backup as Instagram team members —
no shared password, which is exactly the authenticated channel Law 5 requires. The one monthly
human-support chat is a ticket to spend, never to waste: the steward keeps a queue of questions
(first: why the Instagram-Login token is invalidated on password change and how to issue a
long-lived one that survives). Content-credit: when a reel of ours is reused, request the label
(2/month). Owner: Zero (seats), steward (ticket queue), Damar (credit requests).

**P7 — Meta Business Agent (A13): a decision, not a default.** Zantara already owns WhatsApp and
Instagram DMs with grounded, price-safe, PII-local answers. Business Agent is generic and would
answer in parallel. Recommendation: OFF on WhatsApp and Instagram; evaluate on **Messenger only**
(a channel we do not cover) with FAQ scope and hand-off to WhatsApp. Zero decides; the steward
records the decision in the corner.

## 4. The steward — `pro.meta_one_steward`

Three layers, one purpose: nothing we paid for expires unused, and Zero sees every Monday whether
the plan earns.

### 4.1 Corner skill `/metaone`

`.agents/skills/metaone/SKILL.md` + symlink `.claude/skills/metaone` (same convention as `/bot`,
`/wr2`). Holds: this playbook's link, §1 quota table, §3 owners, **LIVE STATE** (token alive/dead,
badge status, seats, Business Agent decision, last export date), and the ledger commands. Every
session touching Meta One updates LIVE STATE.

### 4.2 Agent `.claude/agents/meta-one-steward.md` (model: sonnet)

Weekly reviewer. Reads the ledger, the latest metrics or export, the queue counts and the
competitor digest; writes `research/marketing/meta-one/YYYY-WW-brief.md` (English) and a
10-line Italian summary for Zero. Proposes next week's link allocation (which 4 IG slots) and
Damar's schedule in Bahasa Indonesia. Never publishes, schedules, or touches Meta.

### 4.3 Cron `scripts/meta_one_steward.py` (deterministic, stdlib + urllib, Pro-resident)

Runs daily 06:20 WITA through `scripts/meta-one-steward.sh` (sources `~/.nuzantara-secrets.env`,
heartbeat via `scripts/lib/heartbeat.py`, notifications via `scripts/tg_notify.py`).

Subcommands:

- `tick` — the cron entry: probe → ingest → ledger → digest → heartbeat.
- `use --benefit <ig_post_link|ig_reel_link|fb_post_link|fb_reel_link|support_chat|content_credit> --ref <WR2-XXXXXX|free text>`
  — appends one JSON line to `shared/meta_one/usage.jsonl` (idempotent on `(month, benefit, ref)`).
- `status [--json]` — prints the current month's ledger and probe state.
- `--selftest` — runs against a temp world: healthy-silent must be distinguishable from dead.

Inputs (all read-only): `INSTAGRAM_ACCESS_TOKEN` (presence only, value never logged, never printed —
probe `GET https://graph.instagram.com/me?fields=id,username`); the Pro queue JSON (counts of
`drafted / published`, last `published_at`); `shared/meta_one/usage.jsonl`;
`shared/meta_one/exports/YYYY-MM/*.csv` (newest mtime).

Outputs: `shared/meta_one/ledger.json` (per month: used/quota per benefit, `days_to_month_end`,
`token_state`, `followers_count` when the token is alive, `export_age_days`, `queue` counts);
`shared/meta_one/metrics/YYYY-MM-DD.json` when the token is alive (`followers_count`,
`media_count`, `reach` day total, `profile_links_taps`, `follows_and_unfollows`); heartbeat
`~/.organism/last_seen/pro.meta_one_steward.json` carrying the run's REAL verdict
(`ok` / `warning` / `error`, note = one line).

Alerts through `tg_notify.py`, Italian, no PII, numbers only in aggregate:

- `--tier p0` (dedup key `meta-one-token-dead`): token probe fails → "token Instagram morto dal
  <date>: nessuna telemetria; serve nuovo token (Zero)".
- `--tier p0` (dedup `meta-one-quota-expiring`): `days_to_month_end ≤ 5` and any link benefit
  with `used/quota < 0.5`.
- `--tier digest`: every tick, one block: quota table, followers Δ7d (or `source=export`), queue
  drafted/published, export age, days to month end.
- `--tier log`: heartbeat-only lines.

Quotas live in ONE constant `ADVANCED_QUOTAS = {"ig_post_link": 4, "ig_reel_link": 4,
"fb_post_link": 8, "fb_reel_link": 8, "support_chat": 1, "content_credit": 2}` with the Help
Centre date beside it.

Organism wiring: block in `apps/organism/organism/organs_registry.yaml` (`id: pro.meta_one_steward`,
`runtime: pro_launchd`, `type: cron`, `expected_hb_seconds: 93600` — one day + slack,
`recovery_action: launchctl_kickstart`, label `com.nuzantara.meta-one-steward`,
`severity_on_silence: warning`); plist `infra/launchagents/com.nuzantara.meta-one-steward.plist`
(`StartCalendarInterval` 06:20, `RunAtLoad` false, **no `KeepAlive`** — one-shot, W67),
logs in `~/logs/meta-one-steward.*.log`.

Tests `scripts/tests/test_meta_one_steward.py` (stdlib `unittest`, sealed to `tmp_path`-style
temp dirs — no real HOME, no network, `TG_DRY_RUN=1`): quota math and month rollover; `use`
idempotency; token classification guilt (HTTP 400 OAuthException → `dead`) and innocence
(200 with `username` → `alive`, network error → `unknown`, never `dead`); the expiring-quota rule
fires at day −5 with 1/4 used and stays silent at 3/4; digest contains no token substring and no
`@`-handles other than the brand's; heartbeat status equals the run verdict on all paths.

Boundaries: never publishes, never schedules, never writes to any Meta endpoint; token value never
in logs, errors or stdout; aggregates only (Law 2); no paid per-token API; the `claude` CLI is not
invoked by the cron at all — the weekly agent is a session act.

### 4.4 Acceptance (falsifiable)

1. `python3 scripts/meta_one_steward.py --selftest` exits 0 in a temp world and its output names
   both a healthy and a dead verdict.
2. On Pro after arming: `launchctl print gui/$(id -u)/com.nuzantara.meta-one-steward` shows the
   job; `~/.organism/last_seen/pro.meta_one_steward.json` exists with a fresh `ts` and
   `status` matching the log's last verdict; `shared/meta_one/ledger.json` has the current month.
3. The first real tick reports `token_state=dead` (true today) and spools/sends the P0 once.
4. `python3 scripts/organism_stale_detector.py` lists the organ as breathing, not missing.
5. Zero receives the Monday digest on Telegram (manual confirmation).

## 5. 30-day rollout

| Week           | Human (Zero / Damar)                                                                                                                                                           | Organism                                                           |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| W1 (16–22 Sep) | Zero: verification ID on FB + IG; re-issue IG token; add Damar as IG team member; link Page ↔ IG. Damar: complete FB Page, first 4 IG link slots on E33 / KITAS / PT PMA / tax | Steward armed on Pro; corner live; `sameAs` fix live; first digest |
| W2             | Damar: schedule 4 weeks of posts + stories from the 49 drafts; first export CSV                                                                                                | First Monday brief; queue → scheduled counts                       |
| W3             | Damar: cross-post reels to FB; spend the support chat on the token question                                                                                                    | Ledger shows FB slots in use; competitor delta from insights       |
| W4             | Zero: Business Agent decision; review 30-day scoreboard                                                                                                                        | 30-day scoreboard vs baseline; PENDING-ARMS row closed or updated  |

## 6. Scoreboard (baseline → 30d → 90d)

| KPI                                           | Baseline (2026-09-16)                           | 30d target           | 90d target        |
| --------------------------------------------- | ----------------------------------------------- | -------------------- | ----------------- |
| IG followers                                  | ~10.3K (Apr snapshot; live unknown, token dead) | live number restored | +5%               |
| Link slots used                               | 0/24                                            | ≥ 18/24              | 24/24 every month |
| Attributed leads (`utm_medium=meta_one_link`) | 0                                               | ≥ 1                  | ≥ 3/month         |
| Published carousels/week                      | ~0 (last 2026-08-13)                            | 3                    | 3 sustained       |
| FB Page follows/week                          | unknown (dormant)                               | measured             | growing           |
| Badge on FB + IG                              | no                                              | yes                  | yes               |
| Monthly analytics export present              | no                                              | yes                  | yes               |

## §Solo-operatore (Zero)

1. Complete Meta verification (ID) for the FB Page and `@balizero0`.
2. Re-issue the Instagram long-lived token (Instagram Login family) and land it in Fly and Pro's
   secrets file — `operator[secret]`; the steward will turn green by itself.
3. Add Damar (+1 backup) as Instagram team members (Advanced A5).
4. Link the Facebook Page and the Instagram account in Business Suite; complete the Page.
5. Decide Meta Business Agent (P7): OFF everywhere, or Messenger-only FAQ.
6. Confirm the first Telegram digest arrives.
