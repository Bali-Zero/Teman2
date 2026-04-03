# Visa Oracle — Brainstorming Prompt (Claude Opus 4.6 Max Effort)

## Context

You are the lead product architect for **Bali Zero** (balizero.com), an Indonesian business services company in Bali with 5,000+ clients. The company handles visa processing, company setup (PT PMA/PMDN), tax compliance, and everything an expat or foreign investor needs to operate legally in Indonesia.

The company runs **Nuzantara**, a production AI platform (v5.2) at kita.balizero.com — a monorepo with ~20 apps, 105 MCP tools, 8 autopilot chains, a RAG pipeline with 93,000+ vectors, and a Knowledge Graph with 56,113 nodes / 161,173 edges built from Indonesian legal documents.

We want to build **Visa Oracle** — a standalone consumer-facing product that monetizes our existing intelligence infrastructure.

---

## What We Already Have (Build on This)

### Data & Intelligence Layer

- **visa_oracle** — Qdrant vector collection with visa requirements, processes, durations, costs for all Indonesian visa types
- **legal_unified_hybrid** — 68,000+ legal document chunks (regulations, circulars, immigration law)
- **immigration_circulars** — Immigration-specific regulations collection
- **Knowledge Graph** — Visa subgraph fully built: node types include visa types, requirements, fees, documents, timelines, government agencies
- **RAG Pipeline** — Hybrid search (BM25 + Dense + RRF) → CrossEncoder reranking → Evidence scoring with confidence thresholds (<0.15 ABSTAIN, 0.15-0.60 CAUTIOUS, >0.60 NORMAL)
- **PricingTool** — Single source of truth for all Bali Zero service prices (visa processing fees, government fees, agent fees)
- **bali_zero_pricing_hybrid** — Vector collection with service pricing

### Existing Channels & Infrastructure

- **WhatsApp** — Live channel on Fly.io (Gemini Flash + RAG + triage). Already handles client conversations.
- **Telegram** — Live on Pro (Opus 4.6 + SOUL.md personality)
- **Web Chat** — Live at zantara.balizero.com (Fly.io)
- **Instagram** — Live adapter on Fly.io
- **Client Portal** — my.balizero.com with document uploads, OCR (passport → auto-extract name, nationality, expiry), case tracking, messaging
- **Blog** — 100+ articles on immigration, business setup, tax, property, lifestyle at balizero.com

### Existing MCP Tools (relevant subset)

- `list_visa_types` — All Indonesian visa categories
- `get_visa_details` — Deep info on specific visa type
- `ask_legal` — Legal Q&A against the full regulation corpus
- `calculate_pricing` / `get_all_prices` / `search_service_pricing` — Pricing engine
- `search_kbli` / `inspect_kbli` / `chat_kbli` — Business activity code lookup (relevant for work visas tied to company KBLI)
- `create_client` / `create_practice` — CRM onboarding
- `send_whatsapp` / `send_email` / `send_portal_message` — Multi-channel outreach
- `chain_new_client_onboarding` — Full onboarding autopilot
- `chain_journey_accelerator` — End-to-end client journey automation
- `compose_article` / `publish_article` — Content pipeline
- `subscribe_newsletter` — Newsletter subscription
- `search_intel` / `publish_intel` — Regulatory intelligence

### Tech Stack Available

- **Frontend**: Next.js 16 + React 19 on Vercel (auto-deploy)
- **Backend**: Python 3.11+ FastAPI on Fly.io (Singapore)
- **Databases**: PostgreSQL (Fly.io), Qdrant vectors (Fly.io), Redis cache
- **Edge**: Cloudflare Workers + D1 + KV + R2
- **LLMs**: Gemini Flash (chat), Claude Haiku (intent classification), Ollama local models, OpenRouter
- **Embedding**: text-embedding-3-small (1536 dims) — FROZEN
- **OCR**: Passport extraction pipeline (name, nationality, expiry, photo)
- **Canva MCP**: Programmatic design generation (carousel builder)
- **Google Drive**: Structured document storage per client

---

## The Product Vision: Visa Oracle

A standalone, consumer-facing AI product that answers the question: **"What visa do I need for Indonesia?"**

Target users: digital nomads, expats, remote workers, investors, retirees, entrepreneurs considering Indonesia/Bali. They're currently lost in contradictory blog posts, Facebook groups, and outdated visa agent websites.

### Revenue Model Hypothesis

- **Free tier**: Unlimited visa Q&A chat (lead generation)
- **Paid tier ($19-29/month or one-time $49)**: Personalized visa roadmap, document checklist with status tracking, renewal calendar, regulation change alerts
- **Upsell**: Direct booking of Bali Zero services (visa processing, company setup) with transparent pricing from PricingTool
- **B2B**: API access for travel agencies, relocation companies, coworking spaces ($199/month)

---

## Your Task

Think deeply and expansively about this product. I need you to cover ALL of the following dimensions. Be specific, opinionated, and reference our existing infrastructure wherever possible. Don't be generic — this is a real product for a real company with real data.

### 1. Product Architecture

- How should the user flow work? Map every screen/interaction from first touch to conversion.
- What's the optimal conversation design for the AI? (Consider: the user doesn't know what they don't know about Indonesian immigration)
- How do we handle the "confidence gap"? Immigration law changes frequently — how does the product communicate certainty levels to users?
- Should this be chat-first, form-first, or hybrid? Why?
- How does the free experience differ from paid? What's the "aha moment" that triggers upgrade?

### 2. Technical Architecture

- Should this be a new Next.js app on its own subdomain (visa.balizero.com) or a section of the main site?
- Backend: new FastAPI routes vs. Cloudflare Workers edge functions vs. both?
- How do we serve the RAG pipeline at consumer scale (potentially 10,000+ daily users) without blowing up Fly.io costs? Consider: edge caching, pre-computed answers, tiered LLM routing (Haiku for simple → Gemini for complex → Opus for edge cases)
- Database schema for user accounts, saved roadmaps, document checklists, alert subscriptions
- How do we sync regulatory changes from our intel pipeline into user-facing alerts?

### 3. Conversation Intelligence

- Design the intent taxonomy for visa queries. What are the top 20 intents and how should each be handled?
- How should the AI handle: ambiguous situations, multi-visa scenarios (e.g., "I want to start a business AND bring my family"), contradictory regulations, "it depends" answers?
- What context should the AI collect from the user before making a recommendation? (nationality, purpose, duration, budget, family situation, employment status, etc.)
- How do we prevent hallucination on legal/immigration topics? What guardrails beyond evidence scoring?
- Design the escalation path: AI → human consultant. When, how, and what data gets passed?

### 4. Content & SEO Strategy

- How do we turn the visa oracle into an SEO machine? We already have 100+ blog articles and the KBLI navigator model (1,563 static pages).
- What programmatic SEO pages should we generate? (e.g., "B211 visa for [nationality]" × 195 countries = 195 pages)
- How does the chat interact with long-form content? (user reads article → enters chat with context → gets personalized advice)
- Newsletter/alert product: what regulatory changes matter to which user segments?

### 5. Growth & Distribution

- WhatsApp is where our users already are. How do we design a WhatsApp-native experience that doesn't feel like a downgrade from web?
- Instagram integration: can we use the War Room pipeline to auto-generate visa-related content that drives traffic?
- Referral mechanics: what incentive structure works for immigration/visa products?
- Partnership model: coworking spaces, relocation agents, travel agencies, digital nomad communities. What do we offer them?
- How do we handle multi-language? (English primary, but Indonesian, Chinese, Russian, Korean are huge expat demographics)

### 6. Monetization Deep Dive

- Price sensitivity analysis: what do competitors charge? What's the willingness-to-pay for visa guidance?
- Transaction-based vs. subscription vs. freemium — model each with realistic numbers
- The Bali Zero upsell funnel: what conversion rate from free user → paying Bali Zero client is realistic? How do we optimize it?
- B2B API: who would buy this and what would the integration look like?

### 7. Legal & Compliance

- What disclaimers do we need? We're not a law firm.
- How do we handle the liability of giving immigration advice that turns out to be wrong?
- Data privacy: GDPR (European users), Indonesian PDP law. What data do we collect, store, share?
- Terms of service considerations for an AI immigration advisor

### 8. Competitive Landscape

- Who else is doing this? (visa agencies with chatbots, immigration SaaS products, government portals)
- What's our unfair advantage? (hint: 5,000 real clients, 68,000 legal documents, live Knowledge Graph, actual case data)
- How do we position against cheap visa agents on Instagram vs. expensive immigration lawyers?

### 9. MVP Definition

- What's the absolute minimum we can ship in 2 weeks that validates demand?
- What existing Nuzantara infrastructure can we reuse as-is vs. what needs new development?
- Define the MVP feature set, tech stack choices, and success metrics (specific numbers)
- What do we explicitly NOT build in v1?

### 10. Roadmap (3-6-12 months)

- Month 1-3: MVP → product-market fit validation
- Month 3-6: scaling, paid tier, B2B API
- Month 6-12: expansion (other countries? Other compliance domains?)

---

## Output Format

Structure your response as a comprehensive product brief. Be specific with numbers, timelines, and technical decisions. Reference our existing tools and infrastructure by name. I don't want hand-wavy startup advice — I want an actionable blueprint from someone who understands our exact stack and data.

Think step by step. Challenge assumptions. Identify risks. Propose alternatives where you see trade-offs.

This is a real product that will be built starting next week. Treat it accordingly.
