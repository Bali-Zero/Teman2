---
name: metaone
description: "Meta One Advanced corner — shared context for the Meta subscription (FB+IG+WA). Load before touching Meta One/Verified/IG-FB growth, or when Zero says /metaone, 'meta one', 'abbonamento meta', 'badge'"
---

## Notes (moved from description 2026-09-16)

Advanced plan since 2026-09-15 ($49.99/month, one subscription = FB + IG + WA). Holds: the
benefits + monthly-quota table, owners per play, LIVE STATE (token/badge/seats/export/steward),
and the steward's ledger commands. Full charter and rationale live in the playbook this corner
points to — read that first for anything not answered here.

# /metaone — Meta One Advanced corner

> Created 2026-09-16, the day after Meta launched Meta One (2026-09-15) and Zero subscribed to
> the **Advanced** business plan. This file is the HOT CONTEXT the `/metaone` corner loads and
> the steward cron enforces. Full charter, the seven plays and the 30-day rollout:
> `docs/marketing/meta-one-advanced-playbook.md`. **Update §1 LIVE STATE whenever it changes.**

## 0. What this serves

One subscription, three surfaces (Facebook `facebook.com/balizero`, Instagram `@balizero0`,
WhatsApp — already Zantara's channel). The corner's job is narrow: make sure nothing we paid
for expires unused, and give Zero one Monday read on whether the plan earns. Everything else —
the seven plays, the rollout weeks, the scoreboard — is in the playbook, not duplicated here.

## 1. LIVE STATE (2026-09-16 22:30 WITA — keep current)

- **IG Graph token: DEAD since 2026-08-31** (session invalidated on password change). Every
  Graph reader in the repo is starving; re-issue is `operator[secret]`.
- **Meta verification (badge): NOT yet done** on either FB or IG. Owner: Zero (ID documents).
- **Instagram team seats: 0/4 used** (A5). Damar + one backup not yet added.
- **Meta Business Agent (P7): UNDECIDED.** Recommendation on file (OFF on WhatsApp/Instagram,
  evaluate Messenger-only) — Zero has not ruled.
- **Last analytics export: none.** `shared/meta_one/exports/` does not yet hold a CSV.
- **Steward: ARMED on Pro since 2026-09-16 14:24Z** — launchd `com.nuzantara.meta-one-steward`
  (daily 06:20 WITA, one-shot, no KeepAlive), wrapper `scripts/meta-one-steward.sh`. First real tick:
  heartbeat `warning` (`token=dead`), ledger month `2026-09` with 0/24 link slots used, queue
  49 drafted / 51 published (last 2026-08-13). PRs #6632 #6633 #6634 #6635 merged; PENDING-ARMS
  row of 2026-09-16 tracks the operator steps (token, badge, seats, Page link, Business Agent).

## 2. What we bought — quotas the steward tracks

Source: Meta Help Centre "About Meta One plans" (id `960854640235758`), read 2026-09-16.
Plans: Essential $14.99 · **Advanced $49.99** · Expert $149 · Max $499/month; availability
varies by region/app/account.

| #   | Benefit                                  | Platform  | Quota / month |
| --- | ---------------------------------------- | --------- | ------------- |
| A1  | Featured-in-Feed opportunity             | Facebook  | —             |
| A2  | Optimised search                         | FB + IG   | —             |
| A3  | Bold follow button on Reels              | Facebook  | —             |
| A4  | Automatic follow invitations             | Facebook  | —             |
| A5  | Team access (no password sharing)        | Instagram | 4 seats       |
| A6  | Schedule reels/posts (1y), stories (30d) | FB + IG   | —             |
| A7  | Clickable links in posts                 | FB + IG   | 4 IG / 8 FB   |
| A8  | Clickable links in reels                 | FB + IG   | 4 IG / 8 FB   |
| A9  | Competitive insights                     | Instagram | —             |
| A10 | Audience insights + exportable analytics | FB + IG   | —             |
| A11 | Premium support (human chat)             | Meta      | 1             |
| A12 | Content-credit notifications             | FB + IG   | 2             |
| A13 | More devices/broadcast/Business Agent    | WhatsApp  | plan-defined  |

Quotas live in ONE constant (`ADVANCED_QUOTAS`) in the steward script — a Meta change is a
one-line edit there, not a rewrite of this table.

## 3. Owners per play (playbook §3 — one line each)

- **P1 Trust shield** (badge, impersonation, `sameAs` fix) — Zero (verification), session (site).
- **P2 Link engine** (UTM links on the 4+8 / 4+8 slots) — Damar (placement), steward (count),
  session (landing pages already exist under `/visas`, `/business`).
- **P3 Schedule the backlog** (49 drafted carousels → a scheduled quarter, Law 5 intact) —
  Damar; steward reports queue → scheduled → published.
- **P4 Facebook revival** (cross-post, complete the Page) — Damar (posting), Zero (Page↔IG link).
- **P5 Intelligence** (monthly export → steward ingest → competitor digest) — Damar (export),
  steward (ingest), `competitor-monitor` (digest).
- **P6 Team and support** (IG seats, the one support ticket, content-credit requests) —
  Zero (seats), steward (ticket queue), Damar (credit requests).
- **P7 Business Agent** — a decision, not a default; Zero decides, steward records it here.

## 4. Ledger commands — `pro.meta_one_steward`

```
python3 scripts/meta_one_steward.py status [--json]
python3 scripts/meta_one_steward.py use --benefit ig_post_link --ref WR2-XXXXXX
python3 scripts/meta_one_steward.py tick
python3 scripts/meta_one_steward.py --selftest
```

Data lives on Pro under `shared/meta_one/`: `ledger.json` (current month's quota/token/queue
state), `metrics/YYYY-MM-DD.json` (when the token is alive), `exports/YYYY-MM/*.csv` (the
token-free path — monthly Business Suite export), `usage.jsonl` (append-only, idempotent on
`(month, benefit, ref)`).

Organ id `pro.meta_one_steward`, launchd label `com.nuzantara.meta-one-steward`, one-shot daily
06:20 WITA (no `KeepAlive` — W67), heartbeat `~/.organism/last_seen/pro.meta_one_steward.json`.
Weekly reviewer: `.claude/agents/meta-one-steward.md` — writes
`research/marketing/meta-one/YYYY-WW-brief.md` + an Italian summary for Zero.

## 5. Hard rules

- **Law 5** (`SYMBIOSIS.md:271-279`): a human publishes, the organism proposes — «nessuna cella,
  cron o sessione pubblica di propria iniziativa». The steward never calls a publish or schedule
  endpoint; Damar schedules by hand in Business Suite.
- **Law 2** (`SYMBIOSIS.md:179`): output boundary, aggregates only. No token value, no raw
  message content, no `@`-handle other than the brand's, ever in a log, alert or digest.
- **The IG token value is never printed or logged** — presence-only probe, `${VAR:+SET}` shape.
- **No paid per-token API.** The token probe is Meta's free Graph endpoint under our own app;
  the steward is stdlib + urllib, no `claude` CLI invocation from the cron.
- **No auto-schedule, no auto-publish.** A5's team-access benefit removes password sharing, not
  the human-in-the-loop.

## §Solo-operatore (Zero)

1. Complete Meta verification (ID) for the FB Page and `@balizero0`.
2. Re-issue the Instagram long-lived token (Instagram Login family) and land it in Fly and Pro's
   secrets file — `operator[secret]`; the steward will turn green by itself.
3. Add Damar (+1 backup) as Instagram team members (Advanced A5).
4. Link the Facebook Page and the Instagram account in Business Suite; complete the Page.
5. Decide Meta Business Agent (P7): OFF everywhere, or Messenger-only FAQ.
6. Confirm the first Telegram digest arrives.
