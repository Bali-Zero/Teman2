# Visa Oracle — Product Design Specification

**Date:** 2026-04-04
**Author:** Nuzantara + Claude Opus 4.6
**Status:** Approved (pending spec review)
**External Review:** Gemini CLI + Codex (GPT-5.4) — critical feedback incorporated

---

## 1. Overview

Visa Oracle is a consumer-facing AI product at `visa.balizero.com` that answers "What visa do I need for Indonesia?" It serves as a lead generation funnel for Bali Zero's visa processing services, converting free users into WhatsApp leads for team member Damar.

**What it is:** Free quiz + 3 AI chat questions + WhatsApp handoff.
**What it is NOT:** A standalone SaaS product, a subscription service, or a WhatsApp bot.

---

## 2. Target Audience

All audiences equally:

- Digital nomads / remote workers
- Investors / entrepreneurs
- Retirees
- Family reunification
- Students, journalists, visitors

No audience segmentation in MVP. The quiz captures intent and routes to the right visa type.

---

## 3. Key Decisions

| #   | Decision         | Choice                                                                     |
| --- | ---------------- | -------------------------------------------------------------------------- |
| 1   | Audience         | All audiences equally                                                      |
| 2   | Deployment       | Hybrid — route group in `mouth` (apps/mouth), extract later                |
| 3   | Backend          | New FastAPI routes in `backend-rag` on Fly.io (cold start solved)          |
| 4   | Free tier        | 3 free chat questions, then WhatsApp CTA to Damar                          |
| 5   | WhatsApp handoff | wa.me pre-filled link + Telegram notification to Zero (chat_id 1125336968) |
| 6   | User tracking    | localStorage + fingerprint, no login required                              |
| 7   | Visa coverage    | All types from existing KB (B211/B211A abolished — never reference)        |
| 8   | Language         | Auto-detect, respond in user's language                                    |
| 9   | Entry point      | Dual: Quiz-first (primary) + "Ask Directly" bypass to chat                 |
| 10  | SEO pages        | Top 15 nationalities, 50-100 quality pages, expand via GSC                 |
| 11  | Pricing          | Full transparent Bali Zero fees in chat and visa cards                     |
| 12  | Team/timeline    | Solo dev + Claude, 2 weeks (Approach C: lean Week 1, iterate Week 2)       |

---

## 4. User Flow

```
visa.balizero.com (Landing)
  |
  +-- "Start Quiz" (primary CTA)
  |     |
  |     +-- Step 1: Nationality (dropdown + search + flags)
  |     +-- Step 2: Purpose (work / invest / retire / digital nomad / family / study / visit)
  |     +-- Step 3: Duration (< 30 days / 1-6 months / 6-12 months / 1+ years / permanent)
  |     +-- Step 4: Family (solo / spouse / children / spouse + children)
  |     |
  |     +-- Visa Recommendation Cards (NO LLM — pure logic + PricingTool)
  |           - Top 1-3 matching visa types
  |           - Each: name, validity, gov fee + Bali Zero fee, timeline, key requirements
  |           - "Ask a question" → opens chat (question 1 of 3)
  |
  +-- "I already know what I need" (secondary link)
        |
        +-- Chat directly (question 1 of 3, no quiz context)

Chat (3 questions):
  - Context pre-loaded from quiz (if taken)
  - Auto-detect language, respond accordingly
  - Counter: "X questions remaining"
  - Confidence badges: CAUTIOUS (hedged) vs NORMAL (confident)
  - ABSTAIN (<0.15 confidence) → instant WhatsApp CTA (doesn't count as question)
  - Explicit "talk to someone" → instant WhatsApp CTA (doesn't count as question)
  - After question 3 → WhatsApp CTA overlay

WhatsApp CTA:
  - wa.me/[damar_number] pre-filled: "Hi, I used Visa Oracle. I'm [nationality],
    looking to [purpose] in Indonesia for [duration]. Recommended: [visa type].
    Bali Zero fee: [price]."
  - Simultaneously: Telegram POST to chat_id 1125336968 with session summary
    (nationality, purpose, duration, family, visa recommended, 3 Q&A, confidence scores)
```

---

## 5. Technical Architecture

### 5.1 Frontend (Route Group in `mouth`)

```
apps/mouth/src/app/(visa-oracle)/
  layout.tsx                          — standalone layout (own nav, no workspace sidebar)
  page.tsx                            — landing with hero + dual CTA
  quiz/page.tsx                       — 4-step wizard
  result/page.tsx                     — visa recommendation cards
  chat/page.tsx                       — 3-question chat + counter + WhatsApp CTA
  privacy/page.tsx                    — privacy policy
  terms/page.tsx                      — terms of service
  [nationality]/page.tsx              — SSG SEO pages (top 15 nationalities)
  [nationality]/[visa-type]/page.tsx  — deep SEO pages (nationality x visa type)

apps/mouth/src/components/visa-oracle/
  QuizWizard.tsx          — 4-step form
  VisaCard.tsx            — recommendation card (name, cost, timeline, requirements)
  VisaChat.tsx            — consumer chat wrapper (reuses MessageBubble internals)
  QuestionCounter.tsx     — "X questions remaining" indicator
  WhatsAppCTA.tsx         — handoff overlay with wa.me link
  ConfidenceBadge.tsx     — CAUTIOUS vs NORMAL visual indicator
  ConsentBanner.tsx       — cookie/privacy consent

apps/mouth/src/lib/visa-oracle/
  api.ts                  — API client for visa-oracle endpoints
  types.ts                — TypeScript types
  quiz-logic.ts           — visa matching (client-side, no LLM)
  nationalities.ts        — top 15 nationalities with flag codes
  storage.ts              — localStorage question counter + session ID
```

### 5.2 Backend (New Router in `backend-rag`)

```
backend/app/routers/visa_oracle.py    — /api/v1/visa-oracle/*

  POST /recommend         — quiz answers → ranked visa recommendations (no LLM)
  POST /chat              — question → RAG pipeline → structured response
  POST /handoff           — triggers Telegram notification + generates wa.me link
  GET  /visa-types        — all current visa types (build-time SSG)
  GET  /visa-types/{code} — detail for one visa type (build-time SSG)
  GET  /nationalities/{iso}/visas — visa options for nationality (build-time SSG)
```

### 5.3 Subdomain Routing

One condition addition in `apps/mouth/src/middleware.ts`:

```
visa.balizero.com → (visa-oracle) route group
```

### 5.4 LLM Routing (Cost Optimization)

| Query Type               | Model                                                       | Cost    |
| ------------------------ | ----------------------------------------------------------- | ------- |
| Quiz → recommendation    | No LLM. Pure logic from pricing JSON + visa_oracle metadata | $0      |
| Simple chat question     | Gemini Flash via existing pipeline                          | ~$0.001 |
| Complex question         | HybridSearch → CrossEncoder → Gemini Flash                  | ~$0.003 |
| ABSTAIN (low confidence) | No LLM answer — direct WhatsApp CTA                         | $0      |

Average cost per user session: **~$0.005-0.01**. At 1,000 daily users = ~$5-10/day.

### 5.5 Rate Limiting

- Server-side IP rate limit on `/api/v1/visa-oracle/chat`: 10 requests/hour/IP
- Cloudflare Turnstile (invisible captcha) added if abuse detected in Week 1
- localStorage counter is cosmetic UX, not security — server-side is the real gate

### 5.6 Database (New Migration)

New table `visa_oracle_sessions`:

| Column            | Type        | Purpose                                         |
| ----------------- | ----------- | ----------------------------------------------- |
| id                | UUID        | Primary key                                     |
| session_id        | VARCHAR(64) | Client-generated session ID                     |
| quiz_answers      | JSONB       | {nationality, purpose, duration, family}        |
| recommended_visas | JSONB       | [{visa_type, score, price}]                     |
| messages          | JSONB       | [{role, content, confidence, sources}]          |
| language_detected | VARCHAR(10) | Auto-detected language code                     |
| handoff_triggered | BOOLEAN     | Whether WhatsApp CTA was clicked                |
| ip_hash           | VARCHAR(64) | SHA-256 of IP (for rate limiting, not tracking) |
| created_at        | TIMESTAMP   | Session start                                   |
| expires_at        | TIMESTAMP   | created_at + 90 days (auto-purge)               |

---

## 6. Conversation Intelligence

### 6.1 Intent Taxonomy (Top 15)

| #   | Intent               | Handling                                                                 |
| --- | -------------------- | ------------------------------------------------------------------------ |
| 1   | visa_recommendation  | Quiz result refines via chat                                             |
| 2   | visa_requirements    | Direct RAG from `visa_oracle`                                            |
| 3   | visa_cost            | PricingTool — exact gov + BZ fees                                        |
| 4   | visa_timeline        | RAG from `visa_oracle` + KG                                              |
| 5   | visa_comparison      | Multi-result RAG, side-by-side                                           |
| 6   | visa_extension       | RAG from `visa_oracle` + `immigration_circulars`                         |
| 7   | visa_conversion      | KG subgraph traversal (visa→visa pathways)                               |
| 8   | company_visa_link    | Cross-domain: visa KG + company KG + KBLI                                |
| 9   | family_dependent     | Multi-entity: primary → dependent options                                |
| 10  | regulation_change    | `immigration_circulars`, recency-weighted                                |
| 11  | overstay_penalty     | RAG from `legal_unified_hybrid`                                          |
| 12  | specific_nationality | Nationality-filtered RAG                                                 |
| 13  | process_step         | KG workflow traversal (ordered steps)                                    |
| 14  | document_validity    | Rule-based (6-month passport minimum) + RAG                              |
| 15  | off_topic            | Deflect: "I'm a visa specialist — for Bali tips check balizero.com/blog" |

### 6.2 Hallucination Prevention (5 Layers)

1. **Evidence scoring** — existing 6-factor ConfidenceBreakdown. <0.15 ABSTAIN, 0.15-0.60 CAUTIOUS, >0.60 NORMAL
2. **PricingTool isolation** — prices ONLY from official JSON, never generated
3. **Narrow system prompt** — "You are an Indonesian visa specialist. You ONLY answer Indonesian immigration questions. If you don't have evidence, say so."
4. **Source citations** — every answer references source document/regulation
5. **Recency check** — `immigration_circulars` recency-weighted, recent contradictions flagged

### 6.3 Escalation Path

| Trigger                 | Action                                                                 |
| ----------------------- | ---------------------------------------------------------------------- |
| Confidence < 0.15       | "This requires expert review" → WhatsApp CTA (not counted as question) |
| 3 questions used        | Counter overlay → WhatsApp CTA                                         |
| User asks for human     | Instant WhatsApp CTA (not counted as question)                         |
| Multi-domain complexity | AI answers what it can, flags rest for team                            |

### 6.4 Data Passed to Damar (Telegram Notification)

- Nationality, purpose, duration, family (from quiz)
- Visa type(s) recommended
- 3 questions + AI answers (summarized)
- Confidence levels per answer
- User's detected language

---

## 7. SEO Strategy

### 7.1 Programmatic Pages (Week 2)

**Top 15 nationalities:** Australia, USA, UK, Russia, China, South Korea, Japan, Germany, France, Netherlands, Canada, India, Brazil, Italy, Singapore.

15 nationalities x ~10 relevant visa types = **~100-150 pages** at launch.

Each page structure:

- H1: "Indonesian [Visa Type] for [Nationality] Citizens"
- Requirements, documents, timeline, costs (from PricingTool)
- FAQ section (3-5 nationality-specific questions from `visa_oracle` + KG)
- Schema.org `FAQPage` + `HowTo` structured data
- "Last verified: [date]" badge (E-E-A-T signal)
- Source citations to actual regulations
- CTA: "Check your eligibility" → Quiz with nationality pre-filled

### 7.2 Purpose Landing Pages (Week 2)

5 pages:

- `/visa-oracle/work-in-indonesia`
- `/visa-oracle/invest-in-indonesia`
- `/visa-oracle/retire-in-bali`
- `/visa-oracle/digital-nomad-indonesia`
- `/visa-oracle/move-to-bali-with-family`

### 7.3 Blog Cross-Linking

- Existing 100+ articles at balizero.com/blog → internal links to Visa Oracle pages
- Visa Oracle pages → links to deeper blog articles
- Floating widget on blog: "Check your visa eligibility in 60 seconds" → Quiz

### 7.4 Expansion (Month 2+)

- Monitor GSC for search demand → generate pages for new nationalities
- Comparison pages: "KITAS vs KITAP", "e-visa vs visa on arrival"
- Case study pages from anonymized client journeys (E-E-A-T)
- Author/reviewer pages

---

## 8. Legal & Compliance

### 8.1 Disclaimer Framework

**Static pages (footer + banner):**

> "Visa Oracle provides general informational guidance about Indonesian immigration. This is not legal advice. Immigration regulations change frequently — always verify with official sources or a licensed immigration consultant. Bali Zero is a registered business services provider, not a law firm."

**Chat (system message before first response):**

> "I provide information based on current Indonesian immigration data. For your specific situation, our team can give definitive guidance."

**Chat (on CAUTIOUS confidence):**

> "Based on available information, [answer]. However, this may vary for your specific case. Our team can confirm."

### 8.2 Data Collection & UU No. 27/2022 (PDP)

| Data                                   | Storage                     | Retention     | Justification                      |
| -------------------------------------- | --------------------------- | ------------- | ---------------------------------- |
| Nationality, purpose, duration, family | Server-side session log     | 90 days       | Visa recommendation + auditability |
| Chat messages + AI responses           | Server-side session log     | 90 days       | Auditability + legal defense       |
| IP address                             | SHA-256 hash in session log | 90 days       | Rate limiting                      |
| localStorage fingerprint               | Client-side only            | User controls | Question counter UX                |

**No PII collected:** no name, email, passport, phone number, photos.

**Consent flow:** Cookie banner on first visit linking to `/visa-oracle/privacy` and `/visa-oracle/terms`.

### 8.3 Informational Framing

The AI never says "you should" or "you must." It uses:

- "Based on current regulations, [visa type] typically requires..."
- "The standard process involves..."
- "Bali Zero's fee for this service is..."

### 8.4 Conversation Logging

Every session logged to `visa_oracle_sessions` table with quiz answers, messages, confidence scores, sources cited. 90-day retention, auto-purge. Purpose: defense against disputed advice claims.

---

## 9. Monetization

### 9.1 Revenue Model: Lead Gen Funnel

Not a SaaS. Revenue = Bali Zero service fees from converted leads.

| Metric                   | Conservative | Optimistic  |
| ------------------------ | ------------ | ----------- |
| Daily visitors (Month 1) | 100          | 500         |
| Quiz completion rate     | 60%          | 75%         |
| Chat engagement          | 40%          | 60%         |
| WhatsApp CTA click       | 15%          | 25%         |
| WA → BZ client           | 20%          | 35%         |
| Monthly new clients      | 24           | 294         |
| Revenue ($300-400 avg)   | $7,200/mo    | $117,600/mo |

### 9.2 Cost Structure

| Item                     | Monthly        |
| ------------------------ | -------------- |
| Fly.io (already running) | $0 incremental |
| Vercel (already on plan) | $0 incremental |
| Gemini Flash             | $15-150        |
| **Total**                | **$15-150/mo** |

### 9.3 Future Monetization (v2+)

- Paid document check ($19)
- Booking calendar for consultations
- Email capture → visa roadmap PDF
- Renewal reminder subscription
- B2B API for travel agencies ($199/month)
- Paid tier ($29/month) — unlimited chat, priority escalation, document tracking

---

## 10. Competitive Positioning

### 10.1 Unfair Advantages

1. 5,000+ real clients — operational knowledge no competitor can replicate
2. 68,000+ legal document chunks in RAG — actual regulations, not scraped blogs
3. 108K node Knowledge Graph — visa→requirement→fee→timeline relationships
4. Live transparent pricing from PricingTool
5. Same-day human handoff (Damar on WhatsApp with full context)
6. End-to-end lifecycle: Oracle → WhatsApp → onboarding → processing → portal tracking

### 10.2 Positioning

- vs cheap agents: "See exactly what it costs. No hidden fees."
- vs lawyers: "Get instant answers for free. Only pay for processing."
- vs ChatGPT: "Built on 68,000 Indonesian legal documents, not internet guesses."
- vs government portals: "In your language, in 60 seconds, with expert help one tap away."

### 10.3 Moat

NOT "AI chat" — anyone can build that. The moat is: data freshness (daily intel scraper), conversion speed (Oracle → WhatsApp → service in minutes), price transparency, and operational depth (full visa lifecycle management).

---

## 11. MVP Scope

### 11.1 Week 1 (Days 1-7): Core Product

~15 new files. Target: live by Day 7.

- Landing page (hero + dual CTA)
- Quiz wizard (4 steps)
- Visa recommendation cards (no LLM)
- Chat (3 questions, counter, confidence badges)
- WhatsApp CTA overlay (wa.me pre-filled)
- Telegram handoff (session summary to chat_id 1125336968)
- Backend API (`/api/v1/visa-oracle/`)
- Subdomain routing (`visa.balizero.com`)
- Server-side rate limiting (10 req/hour/IP on chat)
- Disclaimer + consent banner
- Conversation logging (migration + service)

### 11.2 Week 2 (Days 8-14): SEO + Polish

- 50-100 quality SEO pages (top 15 nationalities)
- 5 purpose landing pages
- Blog cross-linking
- Schema.org structured data
- Analytics tracking
- Prompt tuning from Week 1 data
- Turnstile if abuse detected

### 11.3 Explicitly NOT in v1

Login, email capture, paid tiers, B2B API, document upload, OCR, renewal calendar, multi-language quiz UI, WhatsApp bot, mobile app, booking calendar, referral program, partnership widget, more than ~150 SEO pages.

### 11.4 Success Metrics (30 Days)

| Metric                        | Target     |
| ----------------------------- | ---------- |
| Daily unique visitors         | >50        |
| Quiz completion rate          | >50%       |
| Chat engagement               | >30%       |
| WhatsApp CTA click rate       | >10%       |
| Telegram notifications/day    | >5         |
| WA → BZ client conversion     | >15%       |
| New clients/month from Oracle | >15        |
| Revenue from Oracle leads     | >$3,000/mo |
| Legal incidents               | 0          |

---

## 12. Roadmap

### Month 1-3: MVP → PMF

- Week 1-2: Ship MVP
- Week 3: Analytics review (which nationalities, visa types, questions dominate)
- Week 4: Prompt tuning, fix top 5 failure modes
- Month 2: Expand SEO to 30 nationalities (~300 pages), Instagram content via War Room
- Month 3: Decision gate — >15 clients/month? Invest. Otherwise pivot or kill.

### Month 3-6: Scale (if validated)

- Email capture + visa roadmap PDF
- Document check ($19, reuse OCR pipeline)
- Booking calendar
- i18n (Indonesian, Russian, Chinese, Korean)
- Content freshness automation
- Partnership widget
- SEO expansion to 450+ pages with E-E-A-T

### Month 6-12: Platform (if scaling)

- B2B API ($199/month)
- User accounts + saved roadmaps
- Paid tier ($29/month)
- Cross-sell to company setup (PT PMA wizard)
- Domain expansion (tax oracle, property oracle)
- Extract from `mouth` into standalone app

### Kill Criteria

After Month 3, kill if:

- <5 WhatsApp leads/week
- <2% quiz-to-WhatsApp conversion
- SEO pages not indexing
- Damar reports lead quality is garbage

---

## 13. Infrastructure Reuse

| Existing Component                             | Used How                | Changes                |
| ---------------------------------------------- | ----------------------- | ---------------------- |
| `HybridSearchService` + `CrossEncoderReranker` | Chat RAG pipeline       | None                   |
| `ConfidenceBreakdown`                          | ABSTAIN/CAUTIOUS/NORMAL | None                   |
| `PricingService` + prices JSON                 | Visa cards + chat       | None                   |
| `visa_oracle` Qdrant collection                | Vector search           | None                   |
| `legal_unified_hybrid` Qdrant collection       | Legal Q&A               | None                   |
| `immigration_circulars` Qdrant collection      | Regulation changes      | None                   |
| KG visa subgraph                               | Visa relationships      | None                   |
| `ChatInputBar`, `MessageBubble`                | Reuse internals         | Wrapped in consumer UI |
| `useAgenticRAGStream`                          | Chat streaming          | None                   |
| `middleware.ts`                                | Subdomain routing       | +1 condition           |
| `bz-tokens.css`                                | Design tokens           | None                   |
| Telegram bot (8295471667)                      | Handoff notifications   | None                   |

---

## 14. External Review Summary

Reviewed by Gemini CLI and Codex (GPT-5.4) on 2026-04-04.

### Incorporated Feedback

| Issue                                | Resolution                                                            |
| ------------------------------------ | --------------------------------------------------------------------- |
| 3 questions too few for trust        | Quiz result is the primary value (free, rich, no LLM). Chat is bonus. |
| Need "Ask Directly" bypass           | Added dual entry point on landing                                     |
| Bot abuse risk                       | Server-side IP rate limit + Turnstile if needed                       |
| 450 thin SEO pages                   | Reduced to 50-100 quality pages with E-E-A-T                          |
| Legal: need conversation logging     | Added `visa_oracle_sessions` table, 90-day retention                  |
| Legal: informational framing         | AI never says "you should/must"                                       |
| YMYL content needs freshness signals | "Last verified" dates + source citations on SEO pages                 |

### Acknowledged but Deferred

| Issue                         | Why Deferred                                        |
| ----------------------------- | --------------------------------------------------- |
| Email capture before WhatsApp | Adds friction, goal is WA conversion not email list |
| Paid document check ($19)     | v2 feature                                          |
| Separate repo isolation       | Route group isolation sufficient for MVP            |
| 3+ weeks legal QA             | Data already in production RAG serving real clients |
| Booking calendar              | v2 feature                                          |

---

## 15. Risks & Mitigations

| Risk                                    | Likelihood | Impact   | Mitigation                                                                                             |
| --------------------------------------- | ---------- | -------- | ------------------------------------------------------------------------------------------------------ |
| Wrong visa advice → user deported       | Low        | Critical | 5-layer hallucination prevention + ABSTAIN threshold + disclaimers + conversation logging              |
| SEO pages flagged as thin               | Medium     | High     | Quality over quantity (50-100 not 450), E-E-A-T signals, real sources                                  |
| Users game localStorage limit           | High       | Low      | Doesn't matter — more engagement = warmer leads. Server-side rate limit prevents abuse                 |
| ChatGPT eats top-of-funnel              | High       | Medium   | Moat is pricing + Damar handoff + operational depth, not information                                   |
| Regulation changes invalidate content   | Medium     | High     | `immigration_circulars` collection updated by intel scraper. "Last verified" dates on pages            |
| WhatsApp drop-off (users don't message) | Medium     | Medium   | Pre-filled message reduces friction. Telegram notification means Damar has context even if user delays |
| Solo dev burnout                        | Medium     | Medium   | Approach C — ship lean, iterate with data. No over-building                                            |
