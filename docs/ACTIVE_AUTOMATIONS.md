# 🔄 Active Automations - Nuzantara CRM

> Last updated: 2026-02-22 (Added Document Upload v2.0)
>
> This document lists ONLY the automations that are **actually running** in production.

---

## 📊 Summary

| Category                             | Count  |
| ------------------------------------ | ------ |
| **Real-time Triggers**               | 7      |
| **Scheduled (Autonomous Scheduler)** | 5      |
| **Background Services**              | 3      |
| **TOTAL ACTIVE**                     | **15** |

---

## 🚀 REAL-TIME AUTOMATIONS (Trigger-based)

These run immediately when specific events occur in the CRM.

### 1. Invoice Automation

**Trigger:** Practice status → `sending_invoice`  
**File:** `services/invoicing/invoice_service.py`  
**What it does:**

1. Generates PDF invoice with client/practice data
2. Sends email to client with invoice attached
3. Sends notification to Asya@balizero.com
4. Uploads invoice to Google Drive (Individual_CRM or Company_CRM)

**Email sent via:** Zoho Mail API (fallback to SMTP)

---

### 2. Process Start Notification

**Trigger:** Practice status → `on_process`  
**File:** `services/crm/process_automation_service.py`  
**What it does:**

1. Sends warm email to client: "Payment received, we're starting your process!"
2. Sends notification to team leader: "Payment confirmed, start working"

---

### 3. Process Completion

**Trigger:** Practice status → `completed`  
**File:** `services/crm/completed_process_service.py`  
**What it does:**

1. Uploads final documents to client's Drive "Final Documents" folder
2. Sends congratulatory email to client with document links
3. Notifies team leader
4. Creates renewal alert (60 days before expiry)

---

### 4. Drive Folder Creation

**Trigger:** New client created in `/clients`  
**File:** `app/routers/crm_clients.py`  
**What it does:**
Creates standardized folder structure in Google Drive:

```
{ID}_{ClientName}/
├── 00_Profile/
├── 01_Immigration/
├── 02_Company/
├── 03_Tax/
├── 04_Family/
└── 99_Misc/
```

---

### 5. Auto-CRM Extraction

**Trigger:** End of chat conversation  
**File:** `services/crm/ai_crm_extractor.py`  
**What it does:**

1. Uses AI to extract client data from conversation
2. Creates new client if confidence ≥ 0.7
3. Updates existing client if confidence ≥ 0.5
4. Creates practice if intent detected (KITAS, PT PMA, etc.)
5. Logs interaction in database

---

### 6. Lead Assignment

**Trigger:** New client created (from Auto-CRM or manual)  
**File:** `services/crm/lead_assignment_agent.py`  
**What it does:**

1. Checks for duplicates (email, phone, Telegram, WhatsApp)
2. Assigns to team member based on:
   - Department matching (setup/tax)
   - Load balancing (who has fewer active practices)
3. Sends Telegram notification to assigned lead with Accept/Reassign buttons

---

### 7. Document Upload Notification 📄 (NEW v2.0)

**Trigger:** Client uploads document via Portal (`/api/portal/documents/upload`)  
**File:** `services/portal/portal_service.py`  
**What it does:**

1. **Virus Scan:** Checks for malware (extensions, patterns)
2. **Google Drive Upload:** Saves to structured folder:
   ```
   Zantara Portal Uploads/
   └── {client_id}_{name}/
       └── {document_type}/
           └── {timestamp}_{file}
   ```
3. **OCR (Gemini Vision):** Extracts text from PDF/images (same as passport box)
4. **Expiry Detection:** Auto-detects passport/visa/kitas expiry dates
5. **Database Save:** Stores metadata, Drive ID, OCR text, expiry date
6. **Timeline Event:** Creates client-visible event
7. **Email Notification:** Sends to assigned lead with:
   - File details
   - Google Drive link
   - Detected expiry date
   - Link to client workspace

**Email sent via:** Zoho Mail API

**Full documentation:** [docs/DOCUMENT_UPLOAD_ENHANCEMENT.md](./DOCUMENT_UPLOAD_ENHANCEMENT.md)

---

## ⏰ SCHEDULED AUTOMATIONS (Autonomous Scheduler)

These run continuously within the backend application.

### 8. Self-Healing Monitor

**Interval:** Every 5 minutes  
**What it does:**

- Monitors Qdrant, PostgreSQL, AI Router health
- Attempts auto-fix for common issues
- Logs all actions

---

### 9. Conversation Trainer

**Interval:** Every 6 hours  
**What it does:**

1. Analyzes last 7 days of high-rated conversations
2. Identifies winning patterns
3. Generates improved prompts
4. Creates PR with improvements (if significant)

---

### 10. Renewal Alerts Checker

**Interval:** Every 12 hours  
**What it does:**

1. Checks practices expiring in 90/60/30 days
2. Creates `renewal_alerts` records if not exists
3. Alerts are picked up by notification system

---

### 11. Golden Routes Seeder

**Trigger:** Application startup (one-time)  
**What it does:**
Seeds common query patterns to `golden_routes` table for faster routing:

- "What are the requirements for PT PMA?"
- "How much does a KITAS cost?"
- etc.

---

### 12. Birthday Notifier 🎂

**Interval:** Every 24 hours (≈8:00 AM Bali time)  
**File:** `services/crm/birthday_notifier_service.py`  
**What it does:**

1. Finds clients with birthday today
2. Sends personalized email in client's language:
   - 🇮🇹 Italian
   - 🇬🇧 English
   - 🇮🇩 Indonesian
   - 🇺🇦 Ukrainian
   - 🇷🇺 Russian
3. Uses birthplace enrichment data for personalization (if available)

**Email sent via:** Zoho Mail (zero@balizero.com)

---

### 13. Conversation Cleanup

**Interval:** Every 24 hours  
**What it does:**

1. Anonymizes user data older than 7 days
2. Deletes old conversations older than 30 days
3. GDPR/privacy compliance

---

## 🔧 BACKGROUND SERVICES

### 14. Health Monitor

**Interval:** Every 60 seconds  
**What it does:**

- Checks health of all external services
- Qdrant, PostgreSQL, AI Router, Tools
- Sends alerts if issues detected

---

### 14. Auto-Logout Monitor

**Trigger:** Continuous  
**What it does:**

- Monitors team member activity
- Auto-logs out inactive members after timeout

---

## 🗓️ PLANNED (Documented, NOT yet scheduled)

These are implemented in code but intentionally NOT wired to any scheduler
yet. Activation requires a VADEMECUM §1 audit and Zero's approval.

### Skill Registry — Weekly Maintenance

**Proposed schedule:** Every Sunday 06:00 WITA (Air-side cron, after `ragas_eval`)  
**File:** `packages/cell-core/cell_core/genome.py` (`promote_skills`, `silence_stale_skills_v2`)  
**Sprint:** 5.2 Week 3-4

**What it would do (sequential, idempotent):**

1. `Genome.silence_stale_skills_v2()` — soft-silence (valid_to = today) skills
   that are either (a) confidence<0.3 or (b) uses<5 AND dormant >30d.
   Never touches trajectories/scars; reversible via `valid_to = NULL`.
2. `Genome.promote_skills()` — promote survivors:
   - uses≥100 AND confidence≥0.85 → tier1
   - uses≥30 AND confidence≥0.70 (and not tier1) → tier2
   Monotonic: never downgrades.
3. Emit a JSON summary to `shared/skill_registry_maintenance.jsonl` with
   `{date, silenced_n, promoted_tier1, promoted_tier2, total_active}`.

**Why NOT active yet:**

- Seed is still <50 skills; promotion math needs real production usage stats
  (from `/api/skill/record` use counters) before thresholds are trustworthy.
- VADEMECUM §1 audit not run — need to confirm Sunday 06:00 slot doesn't
  collide with `ragas_eval` memory footprint.
- Auto-apply is allowed here (per SYMBIOSIS Legge 5: decay is reversible via
  `valid_to = NULL`, so it's the one place auto-action is safe).

**Activation checklist when the time comes:**

- [ ] Run for 4 weeks in dry-run mode via manual invocation; compare proposed
      changes against a human reviewer.
- [ ] Add Telegram summary notification (owner chat 1125336968).
- [ ] Wire into `~/scripts/` as `skill_registry_maintenance.sh` with lockfile.
- [ ] Add entry to this file's active section; remove from PLANNED.

---

## ❌ REMOVED/DISABLED

These were removed from the codebase or explicitly disabled:

| Automation                     | Reason                                                                    |
| ------------------------------ | ------------------------------------------------------------------------- |
| Deadline Checker (GitHub)      | Removed - functionality covered by Autonomous Scheduler tasks             |
| Auto-Practice Creator (GitHub) | Removed - functionality to be reimplemented in scheduler                  |
| Knowledge Graph Builder        | **Too expensive** - caused 3.9M Rp (€230) in Gemini API costs in Jan 2026 |
| Client Value Predictor         | Skeleton implementation - only logged, no real functionality              |
| Load Testing Workflow          | Not configured, never worked properly                                     |
| Birthplace Enrichment          | Only works in development (requires Ollama, not available on Fly.io)      |
| Auto-Ingestion                 | Disabled - scraper service not configured                                 |

---

## 📝 Configuration Notes

### Email Sending

All automated emails are sent via:

- **Primary:** Zoho Mail API (zero@balizero.com)
- **Fallback:** SMTP (smtppro.zoho.com:587)

### Drive Folders

Files are uploaded to:

- **Individuals:** Individual_CRM folder (1mNi2FkhZqP9inJH2Y1taXLCgS95UkYk4)
- **Companies:** Company_CRM folder (1rLlr2G7TdNUmmvQ_xN9pZQLbPrDFjUsW)

### Telegram Notifications

Sent via Telegram Bot to:

- Assigned team members for new leads
- Clients for urgent deadlines (≤7 days)

---

_Document maintained by: AI Agent_  
_For questions: zero@balizero.com_
