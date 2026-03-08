# Prompt: Nuzantara Rebrand & Architecture Brainstorm

## Use with: Claude Opus 4.6, Gemini 2.5 Pro, or any frontier model

---

You are a senior product strategist and brand architect. I need your help planning a major platform evolution.

## Current Situation

**Bali Zero** is a professional services company in Bali, Indonesia — visa, immigration, company setup, tax compliance for foreign entrepreneurs. We built an internal AI platform called **Zantara** (at kita.balizero.com) that powers our operations:

- AI chat assistant (RAG-based, knows Indonesian law, KBLI codes, visa rules)
- CRM (client management, process tracking)
- Document management (Google Drive integration)
- Email (Zoho integration)
- Calendar (Google Calendar)
- Intelligence center (news scraping, competitor analysis)
- Knowledge base (legal documents, regulations)
- Client portal (self-service for clients)
- KBLI Navigator (Indonesian business classification explorer at balizero.com/kbli)

**Tech stack:** Next.js frontend (Vercel), Python FastAPI backend (Fly.io), Qdrant vectors, PostgreSQL, Redis.

**Current URLs:**

- `balizero.com` → Corporate site + blog + KBLI Navigator
- `kita.balizero.com` → Internal AI workspace (login required)
- `kita.balizero.com/portal` → Client self-service portal

## The Evolution

I purchased **nuzantara.co.id** — a .co.id domain (Indonesian commercial domain).

The name "Nuzantara" = "Nu" (new) + "Nusantara" (the Indonesian archipelago). It represents the evolution from a Bali-focused expat tool to a **pan-Indonesian AI business intelligence platform**.

### What I Want to Build

**nuzantara.co.id** becomes the new home for the AI platform — no longer tied to "Bali Zero" branding. This serves:

- Indonesian entrepreneurs (not just foreigners)
- Businesses across all of Indonesia (not just Bali)
- A broader market: KBLI lookup, business licensing, regulatory compliance, tax advisory

**balizero.com** stays as the consulting company's site — the humans behind the AI.

### New Subdomain Architecture

```
nuzantara.co.id              → AI platform landing + public tools (KBLI, chat)
                                The "product" — like how Linear has linear.app

balizero.com                 → Corporate site (services, blog, team, contact)
                                The "company" — like how Linear Inc has linear.com

kita.balizero.com            → Internal team workspace (requires login + clock-in)
                                "Kita" = "us/we" in Indonesian
                                Gate: login here first, then access sub-apps below

├── mail.balizero.com        → Team email client (Zoho)
├── calendar.balizero.com    → Team calendar (Google Calendar)
├── drive.balizero.com       → Team document management (Google Drive)
└── knowledge.balizero.com   → Team knowledge base

portal.balizero.com          → Client self-service portal (existing /portal extracted)
```

## What I Need From You

### 1. Brand Architecture Analysis

- Does this separation make strategic sense?
- What are the risks of splitting the AI product from the services company?
- How do competitors structure this? (think Deel, Papaya Global, Multiplier — they separate product from company)
- Should nuzantara.co.id have its own visual identity or inherit from Bali Zero?

### 2. nuzantara.co.id Product Vision

- What should the landing page communicate? Remember: this is for ALL of Indonesia now
- What public features should be available without login?
  - KBLI Navigator (already built, very popular)
  - AI chat (limited free tier?)
  - Regulation lookup?
  - Pricing calculator?
- What requires authentication?
- How does a user discover nuzantara.co.id? SEO strategy for Indonesian market?

### 3. Domain & DNS Strategy

- nuzantara.co.id — where should this be hosted? Current infrastructure is Vercel + Fly.io + Cloudflare
- .co.id domains have specific requirements (Indonesian business registration). Verify: what's needed to activate and use a .co.id domain?
- Should we keep the KBLI Navigator on balizero.com/kbli OR move it to nuzantara.co.id/kbli?

### 4. Migration Path

We can't do everything at once. Propose a phased migration:

- Phase 1: What ships first? (MVP on nuzantara.co.id)
- Phase 2: What follows? (subdomain extractions)
- Phase 3: Full vision (complete separation)

### 5. Naming & Language

The platform serves both Indonesian and English-speaking users. Consider:

- "Kita" for the team workspace — good or confusing?
- UI language: default Indonesian with English toggle, or the opposite?
- Brand voice: should Nuzantara feel governmental/institutional or modern/startup?

### 6. Technical Concerns

- Cookie domain: .balizero.com cookies won't work on nuzantara.co.id — how to handle shared auth?
- Should nuzantara.co.id have its own backend or share the existing one?
- SEO migration: how to transfer the KBLI Navigator's search authority if we move it?

## Constraints

- Small team (5-10 people), bootstrapped — no VC money, must be pragmatic
- The AI backend is production-stable — don't break what works
- Indonesian market is price-sensitive — freemium model likely needed
- .co.id domain regulations may require specific compliance
- Current users are mostly English-speaking expats — don't lose them in the rebrand

## Output Format

Structure your response as:

1. Executive assessment (2 paragraphs: is this a good idea? what's the biggest risk?)
2. Recommended architecture (table: domain → purpose → priority → effort)
3. Phased roadmap (3 phases with clear deliverables)
4. Open questions that need answers before proceeding
5. Things I haven't thought of that I should consider
