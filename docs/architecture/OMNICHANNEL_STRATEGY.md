# OMNICHANNEL STRATEGY: The Hydrated Frontend

**Last Updated:** 2026-01-16
**Status:** Strategic Architecture
**Context:** Nuzantara Intelligence System

---

## 1. The Core Philosophy: "Headless Intelligence, Hydrated Interfaces"

The Nuzantara backend (`backend-rag`) is a headless intelligence engine. It doesn't "know" it's serving a web app. It serves **Intent, Logic, and Reasoning**.

The "Frontend" is not a single Next.js app. It is a **ubiquitous layer of interaction** that manifests wherever the user is. We call this the **Hydrated Interface** strategy.

## 2. The Channels (The Declinations)

### 🖥️ The Web Command Deck (High Bandwidth)

**Role:** Deep Work, Analysis, Admin, Complete Visualization.

- **Tech:** Next.js 16 + React 19 + Tailwind 4 (The `apps/mouth`).
- **Use Cases:**
  - Complex dashboard analytics (Grafana/Custom).
  - CRM deep dives (Client 360).
  - Data ingestion/management.
  - "God Mode" system control.

### 📱 Telegram: The Tactical Companion (Low Friction)

**Role:** Notifications, Approvals, Quick Tasks, Intelligence Feed.

- **Tech:** Telegram Bot API (Webhooks) + `apps/bali-intel-scraper` pipeline.
- **Bot:** `@Balizerobot` (Zantara - Bali Zero)
- **Use Cases:**
  - **Approval Flows:** Reviewing Intel articles (Approve/Reject/Edit buttons).
  - **Daily Briefing:** Morning push of critical stats/news.
  - **Quick Query:** "Find client X status" (via RAG).
  - **Alerts:** System health, Critical User Actions.

### 💬 WhatsApp: The Client Direct Line (External)

**Role:** Client Communication, Automated Service, Document Collection.

- **Tech:** WhatsApp Business API (via BSP) + `zoho-integration`.
- **Use Cases:**
  - **Client Onboarding:** Automated flow to collect basic info.
  - **Status Updates:** "Your KITAS is ready".
  - **Document Submission:** User sends photo of passport -> Ingested to CRM.

### 🗣️ Voice: The Invisible Interface (Ambient)

**Role:** High-touch concierge, Hands-free operation.

- **Tech:** ElevenLabs (Synthesis) + OpenAI Whisper (ASR) + Twilio/VAPI.
- **Use Cases:**
  - **Concierge Calls:** "Welcome to Nuzantara".
  - **Voice Notes:** Team dictating meeting notes -> Transcribed to CRM Interaction.

### 🌐 Social Satellites (Instagram, X)

**Role:** Outreach, Brand Presence, Trend Monitoring.

- **Tech:** API Integrations.
- **Use Cases:**
  - **Publishing:** Auto-posting approved content from `zantara-media`.
  - **Listening:** Monitoring hashtags/mentions for `bali-intel-scraper`.

## 3. The Unified Context Layer

To prevent fragmentation, all channels share the **Single Source of Truth**:

1.  **Shared Memory (Postgres/Qdrant):**
    - A conversation on Telegram is stored in the same `conversations` table as a Web Chat.
    - Context (Memory) is retrieved regardless of the input channel.
2.  **Universal Router (FastAPI):**
    - Specific endpoints for channels (e.g., `/webhook/telegram`, `/webhook/whatsapp`).
    - All map to the same **Service Layer** (`rag_service.py`, `crm_service.py`).
3.  **Unified Auth:**
    - Team members are identified by Email/Telegram ID mapping.
    - Clients are identified by Phone Number/Email mapping.

## 4. Implementation Roadmap (2026)

- [x] **Web Command Deck:** Live in `apps/mouth`.
- [x] **Telegram Intel Approval:** Live in `apps/bali-intel-scraper`.
- [ ] **Telegram Agentic Chat:** Enable full RAG capabilities via Bot.
- [ ] **WhatsApp CRM Binding:** Link incoming WA messages to CRM Clients automatically.
- [ ] **Voice Concierge:** Prototype VAPI integration.

---

> _"The Interface is liquid. It takes the shape of the container it fills, but the Intelligence remains solid."_
