# MANDATE — GARUDA VOA self-purchase, live-but-off

> For the **Opus 5 orchestrator session**. Written by the design session with Zero, 2026-08-24.
> Procedure: `docs/factory/ASSEMBLY-LINE.md` (this product is the first on the line — where this
> mandate and that file conflict, this mandate wins for GARUDA only).
> Business blueprint (owner-approved picture of the product): artifact
> `claude.ai/code/artifact/52997e3a-2630-49b4-b70f-f515f528f6ce` (rev4).

## 1. The product (owner-framed)

A tourist lands on `balizero.com/visa/voa`, answers 4 questions, gets an instant verdict with ONE
all-inclusive price and the published D-7 deadline. From a positive verdict: passwordless account
(email magic link, created from the website), phone-camera document upload with instant local OCR
feedback and pre-filled fields, review + pay (card / Apple Pay / Google Pay), then follows the
practice on the portal like a parcel (Received → In review → Submitted → Approved → Delivered),
with a clean email at every real state change, and receives the visa in the portal.
**WhatsApp is the assisted lane** for people uncomfortable buying online — same practice, same
portal, same price, a human drives the same steps. Every DECLINE proposes the right alternative
and routes to WhatsApp: a no is an accompanied client, not a wall.

Existing assets — build on, do not rebuild: `services/garuda_flow/` engine (judge, safe clock,
pricing, nationality dataset — hardened through #4685…#4802), owner preview dashboard, the
withdrawn public pages at restore point `665bfd40d` (structure only), the ruled persistence
design `research/visa/2026-08-23-voa-public-funnel-persistence-design.md` (opaque ID, no PII in
URLs, retention primitive extension, self-service deletion, coarse aggregates — BINDING).

## 2. product.yaml seed (orchestrator completes, owner signs at G0)

- customer: tourist/short-stay traveler to Indonesia, mobile-first, English-speaking
- promise: "know in 10 seconds, buy in 5 minutes, follow it like a parcel"
- price: single all-inclusive (PricingTool; PNBP+3jt rule) — NEVER split fee/PNBP
- primary metric: paid orders/week; secondary: check→purchase conversion, decline→WhatsApp
  conversion, % VOA buyers purchasing a second service within 12 months
- guardrails (3): documents OCR runs LOCAL-first (qwen2.5vl primary — speed/cost, cloud
  families as reinforcement, vendor parity per Zero 2026-08-24) · fail-closed commercial
  freshness (if gov rules/prices change and the truth-sheet is stale, the funnel declines to
  sell rather than promise wrong) · payment marked paid ONLY by reconciled webhook, never by
  browser redirect
- kill criterion (PROPOSED, owner may replace): if 60 days after go-live paid orders < 10/week
  and decline→WhatsApp < 5%, narrow to WhatsApp-assisted only
- non-goals v1: other visa types, multi-applicant carts, native apps, loyalty

## 3. Owner switchboard (NOTHING blocks on these — build dark, collect signatures at the end)

| #   | Decision                        | Prepared proposal                                                                                                                                                           | Owner gesture                    |
| --- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| 1   | Payment provider                | comparison table (fees, currencies, payout, Apple/Google Pay support; Midtrans vs Xendit vs Stripe) with one recommendation; build against sandbox + provider-agnostic port | pick + sign up (his credentials) |
| 2   | Terms of sale + refund rule     | drafted on real VOA failure cases; includes UU PDP consent + DPA posture                                                                                                    | read, approve                    |
| 3   | Data/document retention         | 90 days post-delivery, auto-purge (extends the visa-oracle retention primitive 264/266/268 to garuda tables; fail-closed until the policy record is signed)                 | approve or change number         |
| 4   | Legacy `garuda_voa_checks` rows | measure first (count/date-range via Pro MCP), then propose purge                                                                                                            | yes/no                           |
| 5   | Visual identity                 | 3 concepts side-by-side (`docs/design/2026-07-19-garuda-os-unified-surfaces/concepts/`), balizero-palette recommended and used meanwhile (palette = CSS tokens)             | pick                             |
| —   | GO-LIVE                         | `GARUDA_PUBLIC_ENABLED=true` + sitemap/robots PR (prepared)                                                                                                                 | flip                             |

## 4. Lanes (build in `feature/garuda-voa` integration branch — local-first)

Workflow: integration branch from fresh origin/main, pushed to origin nightly (backup, no PR);
each lane = one session = one worktree merging into it; ONLY the orchestrator merges there;
morning rebase on origin/main; refuters review the day's diff every evening; final landing =
a short train of 4-6 reviewable PRs in one day (migrations → backend → frontend → portal →
arming), each pre-approved, flag off.

| Lane                 | Scope (disjoint files)                                                                                                                                                                      | Builder                             | Refuter                                                 |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- | ------------------------------------------------------- |
| L1 retention+archive | extend retention primitive to garuda tables, purge, aggregates, self-service deletion                                                                                                       | Sonnet 5                            | Sol                                                     |
| L2 public API        | POST evaluate + result GET (opaque id ≥128bit), rate-limit, full headers, reason-codes only, flag                                                                                           | Sonnet 5                            | Kimi K3                                                 |
| L3 checkout+orders   | order model, payment port (sandbox), idempotency keys, signed webhooks + inbox dedup, transactional outbox, append-only payment journal, reconciliation job                                 | Sonnet 5 or Terra                   | DeepSeek V4 Pro (re-derives all money/date math)        |
| L4 account+portal    | magic-link auth from website, portal practice view + tracker states, visa delivery page; **cure the open kita↔my audit findings (verify_client_access skipped, deleted_at) — prerequisite** | Terra                               | Sol                                                     |
| L5 documents+OCR     | upload UX, local qwen2.5vl read, quality feedback loop, checklist, pre-fill                                                                                                                 | Kimi-for-coding                     | Gemini (visual QA)                                      |
| L6 frontend+design   | `/visa/voa` pages restored-then-redesigned, tracker, emails (Brevo, zantara@), imagegen assets                                                                                              | Codex builder (Terra) + Haiku grunt | Opus 5 critic gate (screenshots, mobile-first, WCAG AA) |
| L7 control tower     | practice→CRM handoff (zero re-typing), SLA timer, state-change emails, funnel dashboard, business invariant alerts + daily synthetic purchase probe with dead-man switch                    | Sonnet 5                            | Kimi K3                                                 |

Contracts to FREEZE before dispatch (stage 3): wire schema of public VoaResponse (only D-7
date, only allowlisted reason codes) · order/payment state machine + events · OpenAPI for the
whole surface with generated TS client (this product introduces the typed-contract toolchain
to the repo — CI-enforced) · design tokens + page structure · retention interface.

Journey specs (stage 2, written by a NON-builder family, red-first): happy path + expired
magic link/replay, corrupt photo, uncertain OCR, duplicate payment, failed payment, webhook
out-of-order/spoofed, blocked practice, declined-with-alternative, weekend/cuti-bersama dates,
B1-extension max-stay edge.

## 5. Gates & verification (per ASSEMBLY-LINE, tightened here)

- One cross-family refuter per PR; full adversarial pass ALWAYS on L1/L2/L3 (money/state/PII).
- Gauntlet on the integrated branch: full Playwright journey suite green on ephemeral env +
  contract fuzzing + payment attack session. Binary verdict.
- Ship dark to prod, flag off. At 5%: **5 real buyers observed end-to-end** before 100%.
- Operate: paged invariants "paid orders 24h > 0 (once launched)" and "median upload→OCR
  < 60s"; synthetic sandbox purchase every 15 min, dead-man 15 min → flag off + owner alert.
- Session discipline: `scripts/session_declaration.py` open/close per lane session; three
  reds same cause → suspend (rule 8); PR ≤200 logic lines at landing time.

## 6. Constraints the orchestrator must carry (scars, verified 2026-08-24)

- M5 main checkout is deliberately stale — worktrees from fresh origin/main only; ≤2-3 test
  suites in parallel on M5 (false reds); heavy suites via `ssh pro`.
- TP1 door: probe `GET /models` at dispatch (slug `deepseek-v4-flash-0731`); reasoning seats
  need `max_tokens ≥ 16000` or they return HTTP 200 with empty content.
- `agy` prompts as argv (`-p "..."`), stdin is dead; `kimi`/`qwen`/`codex` headless with
  `< /dev/null`; judge OUTPUT, never exit code.
- Seat quota: check `~/.claude/seat-quota.json` (Pro) before assigning lanes; Team seat `_6`
  is LAST resort; two MAX seats were at 94-95% weekly on 23/8 (resets 25/8, 27/8).
- Merge queue: arm `gh pr merge --auto` BARE; draft does not dequeue (W126); the queue merges
  onto entries ahead, not main.
- No PII in URLs, logs, memories, artifacts (Law 2 output boundary — vendor-neutral).
- Deploy from repo ROOT (`fly deploy --config apps/backend-rag/fly.toml ...`); post-deploy QA
  per CLAUDE.md §11.

## 7. Deliverable and definition of done

DONE = the entire self-purchase journey runs in PRODUCTION behind the flag: the orchestrator
(or Zero from his phone) completes a real test purchase — verdict → account → upload → sandbox
pay → tracker moves → test visa delivered in portal + emails received — the synthetic probe is
green for 48h, the funnel dashboard is live, and the owner switchboard (§3) is filled with
prepared proposals. Then Zero reads one page, signs 5 decisions, and flips the flag.
