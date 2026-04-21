# Visa Funnel Fusion — unifying Visa Check and Visa Oracle

**Date:** 2026-04-21
**Author:** Claude (Opus 4.7, 1M ctx) — brainstormed with Antonello (Zero) + redteamed by Codex CLI, DeepSeek R1, Gemini 2.5 Pro (NotebookLM auth broken, skipped)
**Scope:** `apps/mouth/src/app/visa/*`, `apps/mouth/src/app/(visa-oracle)/*`, `apps/mouth/src/components/visa-oracle/*`, `apps/mouth/src/middleware.ts`, `apps/backend-rag/backend/services/visa_unified/*` (new), `apps/backend-rag/backend/app/routers/visa_check.py`, minor edits to `visa_oracle.py`. DNS on `visa.balizero.com`.
**Branch target:** `feat/visa-funnel-fusion` (from `main`, post-merge)
**Budget:** 5 working days.

---

## Why

Today Bali Zero runs **two separate visa funnels** on different URLs with overlapping purpose:

- `balizero.com/visa` — **Visa Check** (shipped 2026-04-21 as PR #143): deterministic 4-step wizard (`nationality → purpose → duration → budget`) over an 18-code authoritative catalogue, producing a visa recommendation + real IDR cost + WhatsApp CTA. Path-based, zero-cost LLM, confidence from a visible scoring rubric.
- `visa.balizero.com` — **Visa Oracle**: subdomain SEO-focused chat agent (Gemini Flash + Qdrant RAG over 68k immigration documents) with a 3-free-questions paywall, same quiz shape, separate Next.js route group `(visa-oracle)`, separate consent / privacy / terms pages.

These are two products with overlapping positioning but non-overlapping strengths. Running both dilutes SEO authority (subdomain = separate site in Google's eyes), fragments analytics across two origins, duplicates quiz UI, splits the brand, and forces the user to choose an entry point they don't understand. The 2026-04-19 CRO audit shows 2 leads / 90 days from website-source — a third of the lead gap is clearly funnel fragmentation.

**Goal:** a single visa funnel at `balizero.com/visa` that combines the deterministic Check wizard (the conversion engine) with the Oracle chat (the edge-case fallback), under one design, one domain, one analytics funnel.

## Terminology note: "wizard_abstained"

The Visa Check backend (shipped in PR #143) already returns a boolean flag in the `/api/visa/match` JSON response named `referral_mode`. The name is legacy and ambiguous — it has nothing to do with partner referrals or affiliate programs. It signals that `match_tree.py` **abstained**: the deterministic tree explored, found no branch that gives a sensible recommendation, and asks the UI to route the user to human review. It fires in exactly three scenarios:

1. `purpose == OTHER` — the user picked "Something else / not sure" at step 2.
2. `purpose == LONG_TOURISM and duration_months > 6` — tourism visas cap at ~180 days under Indonesian law.
3. `purpose == INVESTOR and budget_band == UNDER_50M` — E28A/D12/E33G all have minimum capital or savings requirements above that ceiling.

**Throughout this spec, the concept is called `wizard_abstained`.** This mirrors the `ABSTAIN` state already used by the RAG reasoning module (`evidence_score < 0.15`) elsewhere in the codebase. The JSON field name `referral_mode` is retained at the API boundary to avoid a breaking contract change — renaming it is a separate follow-up PR if we want naming consistency across frontend+backend.

## Scope: what ships in this merge

**Frontend:**

- Landing `balizero.com/visa` keeps its current "Ambient · Bali" hero and Clock-vs-Match split (already live).
- Result page `balizero.com/visa/match/{hash}` grows a new **accordion-inline chat** below the pre-arrival checklist and above the footer. Accordion closed by default; label _"Have doubts? Ask 3 free questions"_. Opens inline, never blocks the primary WhatsApp CTA above.
- Chat component reuses `VisaChat.tsx` from `components/visa-oracle/`, restyled to match the Check palette (Ambient Bali blue, serif headings).
- Consent banner (`ConsentBanner.tsx` from Oracle) mounted once on `/visa` root (cookie-based dismiss, stored under `.balizero.com`).
- Privacy at `/visa/privacy`, terms at `/visa/terms`. Ported verbatim from Oracle, updated to reference the new canonical URL.
- Clock page `/visa/clock/{hash}` gains the same chat accordion with urgency-aware copy ("Timeline shows D-7. Ask questions now before it's too late.").
- `wizard_abstained` cases (where the wizard returns `referral_mode=true` in its JSON — see terminology note above) **skip the chat accordion entirely** and render a pre-compiled `wa.me` link with a summary of the quiz answers + the reason the tree couldn't pick a visa. The 2026-04-19 CRO audit shows that users who reach this state are the hottest leads we have (they're self-identifying as "my case is not standard") — handing them to an AI chat first is the wrong answer; they want a human immediately.

**Backend:**

- **New** `apps/backend-rag/backend/services/visa_unified/bridge.py` (~150 lines) — a facade exposing:
  - `get_funnel_context(check_hash: str) -> FunnelContext | None` — reads the `visa_checks` row by hash (already written by `visa_check.submit_match`), returns a dict with `nationality, purpose, duration_months, budget_band, recommended_visa, ranking_json, alternatives, estimated_cost_idr, referral_mode`.
  - `augment_chat_system_prompt(context: FunnelContext, base_prompt: str) -> str` — prepends ground truth: _"The user just completed our wizard. Recommended visa: {recommended_visa}. Cost from PricingTool: IDR {estimated_cost_idr}. Alternatives: {alternatives}. Always quote this cost unless explicitly asked for update."_
- **Modify** `backend/app/routers/visa_oracle.py` `chat` endpoint: accept an optional `check_hash` field in `ChatRequest`; if present, call `bridge.get_funnel_context(check_hash)` and inject the augmented prompt. No change to existing Oracle-native callers (backwards compatible).
- **No new migration.** `visa_checks` table (created by PR #137, extended by PR #143) is the single source of truth for wizard state; `visa_oracle_sessions` remains as-is for chat-session state.
- `visa_check.submit_match` gains a tiny addition: return a **short-lived signed session token** (JWT, HS256, 1h expiry, claims `{check_hash, iat, exp}`) alongside the hash. The frontend stores this and passes it as `Authorization: Bearer <jwt>` when starting a chat. The `chat` endpoint validates the JWT (using the existing `JWT_SECRET_KEY` env var) before loading context. Prevents a visitor from crafting a fake `check_hash` to explore the chat with arbitrary context (Gemini redteam: _"prompt injection via client-side context"_).

**Infrastructure:**

- `apps/mouth/src/middleware.ts`:
  - Lines 239–248 (the current `visa.balizero.com` → `/visa-oracle/*` rewrite) change to `NextResponse.redirect(..., 302)` with a 1:1 mapping:
    - `/` → `/visa`
    - `/quiz` → `/visa/match`
    - `/result` → `/visa/match` (legacy query params `?hash=...` preserved)
    - `/chat` → `/visa/match` (chat now lives in the result page; legacy traffic goes to a fresh start)
    - `/privacy` → `/visa/privacy`
    - `/terms` → `/visa/terms`
    - any other path → `/visa` (conservative catch-all)
  - 302 (not 301) because the redirect is time-boxed. GSC change of address covers the SEO signal; after 90 days of monitoring (no traffic < 1% of old peak), DNS record for `visa.balizero.com` is removed from Cloudflare + Vercel, subdomain goes dark.
- **GSC** change of address submitted to Google Search Console within 24h of merge, from `visa.balizero.com` property to `balizero.com`.
- **Sitemap** `apps/mouth/src/app/sitemap.ts` updated to include `/visa`, `/visa/match`, `/visa/clock`, `/visa/privacy`, `/visa/terms` with priority 0.9. Old Oracle URLs removed from the sitemap on the same commit.
- **Internal links** on `balizero.com` (footer, homepage funnels) that currently point to `visa.balizero.com` are rewritten to `/visa`. One `grep` + sed pass in `apps/mouth/`.

**Cleanup (same PR):**

- Delete `apps/mouth/src/app/(visa-oracle)/` (route group).
- Delete `apps/mouth/src/components/visa-oracle/` — but **first** move `VisaChat.tsx`, `QuestionCounter.tsx`, `ConsentBanner.tsx` to `apps/mouth/src/components/visa/` (rename without logic changes).
- Keep `apps/backend-rag/backend/app/routers/visa_oracle.py` — it still serves the `/chat`, `/handoff`, `/recommend` endpoints; only the entry point moves.

## Architecture (user flow)

```
balizero.com/visa (landing)
  └─ "Are you already in Indonesia?"
       │
       ├─ Yes → /visa/clock
       │         └─ form: visa_type + entry_date
       │              └─ POST /api/visa/clock (existing)
       │                   └─ /visa/clock/{hash} (result)
       │                        ├─ 5 checkpoints D-60/D-30/D-14/D-7/D-1
       │                        ├─ [Primary CTA] Start on WhatsApp →
       │                        └─ [Accordion] "Ask questions (3 free)"
       │                             └─ chat with urgency context
       │
       └─ No → /visa/match (step 1 of 4)
                └─ step 1 nationality → step 2 purpose → step 3 duration → step 4 budget
                     └─ POST /api/visa/match (existing, returns hash + NEW session_jwt)
                          │
                          ├─ referral_mode=true (wizard_abstained) → /visa/match/{hash}?handoff=1
                          │      └─ NO chat; pre-compiled wa.me link with quiz summary
                          │
                          └─ referral_mode=false → /visa/match/{hash}
                                 ├─ Stamp rosso visa code (e.g. "E33G")
                                 ├─ Reason (name_en + notes + budget + duration)
                                 ├─ Estimated cost IDR
                                 ├─ Pre-arrival checklist (5 items)
                                 ├─ [Primary CTA] Start on WhatsApp →
                                 └─ [Accordion, closed by default]
                                      "Have doubts? Ask 3 free questions"
                                      │ opens in-place, no page nav
                                      └─ POST /api/visa-oracle/chat
                                           Authorization: Bearer <session_jwt>
                                           body: { check_hash, message, session_id }
                                           │
                                           ├─ backend: JWT validated
                                           ├─ bridge.get_funnel_context(check_hash)
                                           ├─ bridge.augment_chat_system_prompt(ctx, base)
                                           ├─ Gemini Flash answers
                                           ├─ confidence gating (ABSTAIN/CAUTIOUS/NORMAL)
                                           └─ response + remaining_questions counter
                                                ├─ confidence ABSTAIN → "Let's WhatsApp"
                                                ├─ remaining_questions == 0 → handoff WA
                                                └─ else → next question
```

## Data flow and contracts

### New `visa_check.submit_match` response field

```json
{
  "hash": "81kealti43kbi40e",
  "recommended_visa": "E33G",
  "reason": "…",
  "estimated_cost_idr": 13000000,
  "cost_source": "E33G Remote Worker (Offshore)",
  "processing_days": 25,
  "pre_arrival_steps": [...],
  "alternatives": ["E23-FREELANCE", "C1"],
  "referral_mode": false,
  "result_url": "/visa/match/81kealti43kbi40e",
  "session_jwt": "eyJhbGciOiJIUzI1NiIs…"     ← NEW
}
```

JWT claims: `{ "check_hash": "81kealti43kbi40e", "iat": <unix>, "exp": <unix+3600> }`. Signed with `JWT_SECRET_KEY`. 1h TTL covers the realistic conversation window; expired → chat 401 → frontend re-prompts a fresh quiz.

### Extended `visa-oracle/chat` request

```json
{
  "session_id": "existing session_id (optional first turn)",
  "check_hash": "81kealti43kbi40e",
  "message": "posso estendere C1 se sono al D-7?",
  "language": "it"
}
```

`Authorization: Bearer <session_jwt>` header required when `check_hash` is present. Without JWT, `check_hash` is ignored (backwards compat for Oracle-only clients — will be none after cleanup, but the compat is cheap).

### Bridge service API (internal only)

```python
# backend/services/visa_unified/bridge.py

@dataclass(frozen=True)
class FunnelContext:
    check_hash: str
    nationality: str
    purpose: str               # work_remote, investor, …
    duration_months: int
    budget_band: str           # under_50m, 50m_500m, over_500m
    recommended_visa: str | None
    estimated_cost_idr: int | None
    alternatives: list[str]
    referral_mode: bool

async def get_funnel_context(check_hash: str, pool: asyncpg.Pool) -> FunnelContext | None:
    """Return the wizard snapshot for a given hash. None if not found or expired (>30d)."""

def augment_chat_system_prompt(ctx: FunnelContext, base: str) -> str:
    """Prepend ground-truth paragraph to the Oracle system prompt.

    The augmentation names the visa, the Bali Zero price, and the alternatives
    so the LLM cannot contradict the wizard. For wizard_abstained users
    (rare path since they skip the chat, but defensive) it tells the LLM to
    gather details for WhatsApp rather than invent advice.
    """
```

## Design decisions and rationale

### Why accordion inline (not drawer, not modal, not route)

Multi-LLM brainstorming converged on inline over drawer: a new route burns the primary CTA's context; a modal disrupts reading flow; a drawer on desktop is redundant on mobile. Inline accordion is mobile-native, composes cleanly with the existing scroll-down info architecture of the result page, and — crucially — keeps WhatsApp visible as the user scrolls. The chat is a _second chance_, not a _first choice_; its visual weight must reflect that.

### Why bridge facade (not schema merge)

The `visa_checks` table is already the durable record of a wizard completion. Adding columns to `visa_oracle_sessions` would duplicate that data and create drift (two places to update on any wizard change). The facade reads the canonical row once per chat turn (1 SELECT with `hash` primary key — sub-millisecond), produces a typed `FunnelContext`, augments the Oracle prompt. No migration. No schema risk. Rollback = delete one folder.

### Why JWT session tokens (not opaque session IDs)

Gemini redteam flagged: passing `check_hash` unauthenticated lets any visitor load any other visitor's context by guessing hashes (16-char alphanumeric = 36¹⁶ ≈ 7.9×10²⁴ space, brute-force infeasible but the principle of client-side trust is wrong). JWT + `JWT_SECRET_KEY` (already present for the hybrid auth middleware) enforces that only someone who completed _this_ wizard can chat about _this_ visa. 1h TTL mirrors realistic session length. No new secret management.

### Why `302` not `301` for subdomain redirect

A 301 is permanent; de-indexing later requires Google to re-crawl and figure out the subdomain is gone. A 302 signals "temporary, keep the old property watched"; after GSC change-of-address propagates (~30-60 days) + 30 days of near-zero traffic, DNS gets removed and there's nothing left to serve. The 15% link-equity loss cited by Moz applies mostly to poorly-mapped 1:N redirects; our 1:1 mapping minimizes the cost.

### Why 3-free-questions paywall stays as-is (cookie-based)

Gemini redteam: _"leaky paywall is a good trade-off, goal is conversion not monetization"_. Fingerprinting adds GDPR complexity (Indonesian UU-PDP also applies), breaks on browser updates, and the users sophisticated enough to clear cookies are exactly the users who read the room and escalate to WhatsApp anyway. The paywall exists to create urgency, not to enforce billing.

### Why `wizard_abstained` users skip chat entirely

Codex + Gemini converged: when the wizard abstains (the user's case falls outside the deterministic tree — OTHER purpose, tourism > 6mo, investor under-budget), the lead is hot. These users have self-identified as "my case is not standard"; routing them through an AI chat first is a step backward and wastes the signal. The wa.me link is pre-compiled with the quiz answers serialized as a readable summary ("Italian investor, budget <50M IDR, 12 months, no clear visa match — please advise"), so the Bali Zero team picks up a warm-handed lead with context, not a cold handoff.

## Testing strategy

**Backend unit (new tests, 9 cases, TDD):**

1. `test_bridge.py::test_get_funnel_context_returns_typed_dataclass` — insert a Match row, fetch, assert fields.
2. `test_bridge.py::test_get_funnel_context_returns_none_when_hash_absent`
3. `test_bridge.py::test_get_funnel_context_returns_none_for_expired_row` — 30d TTL.
4. `test_bridge.py::test_augment_chat_system_prompt_includes_visa_code` — substring match.
5. `test_bridge.py::test_augment_chat_system_prompt_includes_cost_and_alternatives`
6. `test_bridge.py::test_augment_for_wizard_abstained_shifts_tone_to_handoff`
7. `test_visa_check_router.py::test_submit_match_returns_session_jwt` — verify JWT structure + claims.
8. `test_visa_check_router.py::test_session_jwt_signed_with_correct_key`
9. `test_visa_oracle_chat.py::test_chat_with_check_hash_validates_jwt_or_401`

**Frontend component (new tests, 6 cases):**

10. `VisaChat.accordion.test.tsx::test_closed_by_default`
11. `VisaChat.accordion.test.tsx::test_clicking_header_opens_inline`
12. `VisaChat.accordion.test.tsx::test_sends_check_hash_and_jwt_on_first_message`
13. `VisaChat.accordion.test.tsx::test_does_not_render_when_wizard_abstained`
14. `HandoffWaLink.test.tsx::test_generates_wa_me_with_encoded_summary` — assert `?text=` contains quiz fields.
15. `middleware.test.ts::test_visa_subdomain_redirects_301_to_path` — 6 redirect rules.

**E2E (new Playwright spec, 3 scenarios):**

16. Full happy path: landing → match wizard → result → expand chat → ask 1 question → answer received.
17. Wizard-abstained path: investor + under-50M → result shows `handoff=1` query param → no chat accordion → wa.me link present.
18. Subdomain redirect: hit `visa.balizero.com/privacy` → land at `balizero.com/visa/privacy`.

**Integration (smoke):**

19. `/api/visa/match` round-trip with DB → returns `session_jwt` with valid signature.
20. `/api/visa-oracle/chat` with `check_hash` + JWT → returns LLM answer; system prompt (logged) contains visa code.

## Telemetry and KPIs

**Events to instrument (GA4, via existing `logEvent` helper):**

- `visa_landing_view` — `/visa` page load.
- `visa_branch_selected` — `{ branch: "clock" | "match" }`.
- `visa_match_submitted` — `{ purpose, budget_band, duration_months, referral_mode, recommended_visa }`.
- `visa_result_view` — `{ hash, recommended_visa, referral_mode, source: "match" | "clock" }`.
- `visa_chat_opened` — `{ hash, remaining_questions }`.
- `visa_chat_question_sent` — `{ hash, question_index, confidence_bucket }`.
- `visa_wa_click` — `{ hash, source: "primary" | "chat_handoff" | "wizard_abstained", referral_mode }`.
- `visa_paywall_hit` — `{ hash, question_index }`.
- `visa_subdomain_redirect` — `{ from_path, to_path }` (middleware, first 30 days only, for validation).

**Primary KPI:** contact-rate = `(visa_wa_click count) / (visa_match_submitted count)`.
Baseline: ~2% (from 2026-04-19 CRO audit, 2 website-source leads / ~100 inferred funnel completions / 90 days).
Target: **≥ 15%** over the first 30 days post-merge.

**Secondary KPIs:**

- Chat adoption: `visa_chat_opened / visa_result_view` ≥ 10%.
- Chat-to-WA conversion: `visa_wa_click[source=chat_handoff] / visa_chat_opened` ≥ 25%.
- Wizard-abstained WA conversion: `visa_wa_click[source=wizard_abstained] / (visa_result_view where referral_mode=1)` ≥ 40% — these are hot leads, this measures whether the wa.me pre-compile works.

**Alert thresholds (for follow-up sprint, not this PR):**

- Chat adoption < 3% for 14 days → accordion UX failed, reconsider.
- Chat confidence ABSTAIN rate > 30% → Qdrant collection needs re-ingest.
- Overall contact rate drops below 2% baseline → something regressed, rollback.

## Non-goals

- Not porting the Oracle quiz (`/visa-oracle/quiz`). The Check wizard replaces it 1:1; the question set and purposes map directly.
- Not rewriting `match_tree.py` scoring or `pricing_bridge.py` hints — they work.
- Not changing Oracle's confidence-gating thresholds (`< 0.30` ABSTAIN, `0.30-0.55` CAUTIOUS, `> 0.55` NORMAL). Proven in production for months.
- Not consolidating the two backend modules (`visa_check/` + `visa_oracle/`) into one package. Codex: _"don't fuse now"_. Bridge facade is the integration surface.
- Not adding a second language detection layer. Oracle's `_detect_language` in `visa_oracle.py:266` handles it.
- Not introducing fingerprinting or stricter paywall. Gemini redteam: cost > benefit.
- Not refactoring the wider homepage funnel section (the "24+ visa categories" hardcoded copy on the landing will stay as-is for this PR; it's copywriting, separate concern).

## Deliverable

1. This spec at `docs/superpowers/specs/2026-04-21-visa-funnel-fusion.md` (committed).
2. Branch `feat/visa-funnel-fusion` (after implementation plan):
   - `backend/services/visa_unified/bridge.py` + tests (9 cases).
   - `backend/app/routers/visa_check.py` extended to return `session_jwt`.
   - `backend/app/routers/visa_oracle.py` extended to validate JWT + accept `check_hash`.
   - `apps/mouth/src/components/visa/VisaChat.tsx` (moved + restyled) + `QuestionCounter.tsx` + `ConsentBanner.tsx`.
   - `apps/mouth/src/app/visa/match/[hash]/page.tsx` — accordion integration.
   - `apps/mouth/src/app/visa/match/[hash]/HandoffWaLink.tsx` — new component rendered when `referral_mode=true` (wizard_abstained).
   - `apps/mouth/src/app/visa/clock/[hash]/page.tsx` — accordion integration.
   - `apps/mouth/src/app/visa/privacy/page.tsx` + `terms/page.tsx` (ported).
   - `apps/mouth/src/middleware.ts` — 6-rule redirect block.
   - Cleanup: delete `apps/mouth/src/app/(visa-oracle)/` + `apps/mouth/src/components/visa-oracle/`.
   - Frontend tests (6 cases).
   - Playwright E2E (3 scenarios).
   - Sitemap update.
3. GSC change-of-address submitted (manual, 5 min) within 24h of merge.
4. Telemetry: 9 new events wired, GA4 DebugView verified.

## Timeline

Budget: **5 working days** (consensus from Codex + DeepSeek).

- **Day 1** — backend bridge + JWT emission + tests (9 cases). Small frontend move: components `visa-oracle/` → `visa/`.
- **Day 2** — accordion chat integration in `/visa/match/{hash}`, `HandoffWaLink` component for wizard_abstained path, frontend tests (6 cases).
- **Day 3** — clock branch gets the accordion + urgency copy. Privacy/terms ports. Consent banner mount.
- **Day 4** — middleware redirects 6-rule, sitemap update, internal-link rewrite pass, cleanup of `(visa-oracle)/`. GSC change-of-address submission.
- **Day 5** — Playwright E2E (3 scenarios), telemetry wiring, deploy to Fly+Vercel, post-deploy verification via `scripts/post-deploy-verify.sh`, smoke test the 9 GA4 events in DebugView.

## Risks and mitigations

| Risk                                                                | Severity | Mitigation                                                                                                                                                                          |
| ------------------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SEO traffic loss on `visa.balizero.com` during 302→delete window    | Medium   | GSC change-of-address + 1:1 redirect mapping + canonical tags on old URLs for 30d overlap. Track `visa_subdomain_redirect` event to see how much traffic still hits old paths.      |
| Accordion hides chat → low adoption                                 | Medium   | Secondary KPI monitors adoption; if < 3% at day 14, follow-up PR makes the accordion default-open or renames the label.                                                             |
| Oracle chat contradicts Check price                                 | High     | `augment_chat_system_prompt` injects `estimated_cost_idr` as ground truth in every Oracle chat turn. Integration test asserts the prompt contains the visa code and the IDR figure. |
| JWT secret rotation breaks active chats                             | Low      | 1h TTL means any rotation hits ≤ 1h of users with a 401. Frontend handles 401 with a "refresh your quiz" prompt; no data loss (wizard is cheap to redo).                            |
| `referral_mode` wa.me summary is too long / truncated by WhatsApp   | Medium   | Test on Android + iOS WhatsApp: max reliable `?text=` is ~2000 chars URL-encoded. The quiz summary is ~300 chars, well under the cap.                                               |
| Cleanup deletes `(visa-oracle)/` but middleware still references it | High     | Cleanup is the last commit of the PR. Middleware test (case 15) asserts no reference to `/visa-oracle/*` route patterns remains.                                                    |
| Cold start on first chat message (Gemini Flash ~2-4s)               | Low      | Pre-warm: result page on mount silently POSTs to `/api/visa-oracle/session` to provision a session row, so the first user message has a hot path.                                   |

## Fail-loud contract

Same convention as PR #143. During implementation, if any of these occur, **stop and ask the user**, do not improvise:

- JWT validation surface changes between `visa_check` and `visa_oracle` (e.g. the two modules can't agree on where `JWT_SECRET_KEY` is loaded).
- `visa_checks` table schema differs from what `bridge.get_funnel_context` expects.
- Any frontend test asserts a visible `referral_mode=true` accordion (it should never render).
- Playwright E2E subdomain redirect test hits a fresh 404 on a path we didn't map.

## Follow-up (next sprint, not this PR)

- Dynamic "18 visa codes" counter on the landing (currently hardcoded "24+").
- A/B test primary CTA placement (above vs below the stamp) based on day-14 data.
- Instrument `visa_wa_click` with UTM params for attribution in CRM.
- Consider removing the Oracle `recommend` endpoint once the Check wizard is the only producer of recommendations.
