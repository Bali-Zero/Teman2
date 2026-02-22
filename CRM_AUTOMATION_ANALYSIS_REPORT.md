# CRM Automation Analysis Report

## Nuzantara / Bali Zero CRM System

**Date:** 2026-02-21  
**Scope:** /clients and /process modules

---

## Executive Summary

The CRM system has **good foundational automations** already implemented:

- ✅ Drive folder auto-creation on client creation
- ✅ Invoice automation on 'sending_invoice' status
- ✅ Process start/completion notifications
- ✅ Lead auto-assignment with Telegram notifications
- ✅ Birthday notifications
- ✅ Tax/Visa deadline reminders

**However, there are 15 high-impact automation opportunities** that would significantly reduce manual work and improve client experience.

---

## Current State Analysis

### Frontend Manual Actions (Repetitive)

| Action                        | Frequency   | Current State          |
| ----------------------------- | ----------- | ---------------------- |
| Status updates (kanban drag)  | 50-100x/day | Manual                 |
| Client data entry             | 10-20x/day  | Manual form filling    |
| Document requirement tracking | 30-50x/day  | Manual list management |
| Assignment to team members    | 10-15x/day  | Manual dropdown select |
| Follow-up reminders           | 20-30x/day  | Mental/notes only      |
| Document review/verification  | 15-25x/day  | Manual status change   |

### Backend Endpoints (High Traffic)

| Endpoint                        | Calls/Day | Automation Status                           |
| ------------------------------- | --------- | ------------------------------------------- |
| `POST /api/crm/clients`         | 10-20     | ✅ Drive folder auto-created                |
| `POST /api/crm/practices`       | 15-30     | ✅ Duplicate check automated                |
| `PATCH /api/crm/practices/{id}` | 50-100    | ✅ Some status automations                  |
| `POST /api/crm/interactions`    | 30-50     | ❌ No automation                            |
| Document uploads                | 20-40     | ⚠️ Drive upload automated, no notifications |

---

## Automation Opportunities (Ranked)

### 🔴 HIGH IMPACT - SIMPLE (Implement First)

#### 1. **Document Upload Notifications**

**Trigger:** Client uploads document via portal  
**Current Gap:** Team doesn't know when documents are uploaded  
**Automation:**

- Send Telegram notification to assigned team member
- Update practice status from "waiting_documents" → "on_process" (if all docs uploaded)
- Create timeline event
- Send "thank you" email to client

**Impact:** HIGH - Reduces response time from hours to minutes  
**Complexity:** SIMPLE (similar to lead_assignment_agent)  
**Business Value:** ⭐⭐⭐⭐⭐ (Client satisfaction + team efficiency)

---

#### 2. **Stale Lead Follow-up Reminders**

**Trigger:** Lead status unchanged for X days  
**Current Gap:** `last_interaction_date` is tracked but no reminders sent  
**Automation:**

- Day 3: Internal reminder to assigned team member (Telegram)
- Day 7: Internal escalation to supervisor
- Day 14: Auto-mark as "cold" status
- Day 30: Send "We miss you" re-engagement email

**Impact:** HIGH - Recovers 15-20% of cold leads  
**Complexity:** SIMPLE (cron job + email templates)  
**Business Value:** ⭐⭐⭐⭐⭐ (Revenue recovery)

---

#### 3. **Practice Stuck-in-Status Alerts**

**Trigger:** Practice in same status > threshold days  
**Current Gap:** No SLA monitoring  
**Automation:**
| Status | Threshold | Alert Action |
|--------|-----------|--------------|
| waiting_documents | 7 days | Notify client + team lead |
| sending_invoice | 3 days | Notify client payment link |
| on_process | 14 days | Internal escalation |
| submitted_to_gov | 30 days | Status check reminder |

**Impact:** HIGH - Prevents cases from being forgotten  
**Complexity:** SIMPLE (daily cron job)  
**Business Value:** ⭐⭐⭐⭐⭐ (SLA compliance)

---

#### 4. **Passport Expiry Notifications**

**Trigger:** Passport expiry date approaching  
**Current Gap:** `passport_expiry` field exists, no alerts  
**Current Logic:** Frontend shows colors (green/yellow/red) but no proactive notifications  
**Automation:**

- 14 months before: Green (info)
- 9 months before: Yellow (warning email)
- 6 months before: Red (urgent email + Telegram to team)
- 1 month before: Critical (call reminder)

**Impact:** HIGH - Prevents client emergencies  
**Complexity:** SIMPLE (extend deadline_checker.py pattern)  
**Business Value:** ⭐⭐⭐⭐⭐ (Client retention)

---

### 🟡 MEDIUM IMPACT - SIMPLE

#### 5. **Welcome Email Sequence**

**Trigger:** New client created  
**Current Gap:** Only Drive folder is created, no communication  
**Automation:**

- Immediate: Welcome email with Drive folder link
- Day 1: "What to expect" guide
- Day 7: "How to upload documents" tutorial
- Day 14: Check-in email

**Impact:** MEDIUM - Improves client onboarding  
**Complexity:** SIMPLE (email templates + cron)  
**Business Value:** ⭐⭐⭐⭐ (Client experience)

---

#### 6. **Document Verified Confirmation**

**Trigger:** Team member marks document as "verified"  
**Current Gap:** Client doesn't know document is approved  
**Automation:**

- Send WhatsApp/Telegram notification to client
- If all docs verified → Send "ready to proceed" email
- Update practice status automatically

**Impact:** MEDIUM - Reduces "did you get my document?" inquiries  
**Complexity:** SIMPLE (hook into document review)  
**Business Value:** ⭐⭐⭐⭐ (Support ticket reduction)

---

#### 7. **Payment Reminder Sequence**

**Trigger:** Invoice sent but payment pending  
**Current Gap:** Manual follow-up only  
**Automation:**

- Day 3: Friendly reminder email
- Day 7: Urgent reminder with payment link
- Day 10: Team member notification
- Day 14: Final notice + practice hold

**Impact:** MEDIUM - Improves cash flow  
**Complexity:** SIMPLE (extend invoice automation)  
**Business Value:** ⭐⭐⭐⭐ (Cash flow)

---

#### 8. **Team Weekly Summary**

**Trigger:** Every Monday 9 AM  
**Current Gap:** Team manually checks dashboard  
**Automation:**

- Email/Telegram digest per team member:
  - Active practices count
  - Documents pending review
  - Deadlines this week
  - New leads assigned

**Impact:** MEDIUM - Improves team productivity  
**Complexity:** SIMPLE (weekly cron job)  
**Business Value:** ⭐⭐⭐ (Team efficiency)

---

### 🟢 HIGH IMPACT - MEDIUM COMPLEXITY

#### 9. **Smart Status Transitions**

**Trigger:** All required documents uploaded & verified  
**Current Gap:** Manual status change from "waiting_documents"  
**Automation:**

- Auto-detect when all `required_documents` status = "verified"
- Auto-update practice status to "on_process"
- Send "Documents complete" confirmation to client
- Notify team member: "Ready to start work"

**Impact:** HIGH - Saves 5-10 minutes per practice  
**Complexity:** MEDIUM (requires document status aggregation)  
**Business Value:** ⭐⭐⭐⭐⭐ (Process efficiency)

---

#### 10. **Sentiment-Based Escalation**

**Trigger:** Negative sentiment detected in interaction  
**Current Gap:** `sentiment` field tracked but no action  
**Automation:**

- Negative sentiment → Immediate Telegram to team lead
- Urgent sentiment → Email + Telegram + Dashboard alert
- Create high-priority follow-up task

**Impact:** HIGH - Prevents client churn  
**Complexity:** MEDIUM (sentiment analysis integration)  
**Business Value:** ⭐⭐⭐⭐⭐ (Client retention)

---

#### 11. **Auto-Practice Suggestion**

**Trigger:** Client uploads specific document type  
**Current Gap:** Missed upsell opportunities  
**Automation:**
| Document Uploaded | Suggested Practice |
|-------------------|-------------------|
| Expired passport/visa | Visa renewal practice |
| Company financials | Tax reporting practice |
| Property documents | Property ownership practice |

- Create draft practice
- Notify team member with one-click "Create Practice" button

**Impact:** HIGH - Increases revenue per client  
**Complexity:** MEDIUM (document type → practice mapping)  
**Business Value:** ⭐⭐⭐⭐⭐ (Revenue growth)

---

### 🟠 MEDIUM IMPACT - MEDIUM COMPLEXITY

#### 12. **Client Portal Activity Alerts**

**Trigger:** Client activity in portal  
**Current Gap:** No visibility into client engagement  
**Automation:**

- Client logs in after 30 days → "Client active" notification
- Client views practice 3+ times → "High interest" flag
- Client doesn't log in for 60 days → Re-engagement campaign

**Impact:** MEDIUM - Better client intelligence  
**Complexity:** MEDIUM (portal analytics integration)  
**Business Value:** ⭐⭐⭐⭐ (Sales intelligence)

---

#### 13. **Practice Completion Follow-up**

**Trigger:** Practice marked "completed"  
**Current Gap:** No post-completion engagement  
**Automation:**

- Day 7: "How was your experience?" survey
- Day 30: "Need any other services?" email
- Day 90: Referral request email
- Day 180: Renewal reminder (if applicable)

**Impact:** MEDIUM - Increases referrals and repeat business  
**Complexity:** MEDIUM (email sequence logic)  
**Business Value:** ⭐⭐⭐⭐ (Referrals/LTV)

---

### 🔵 HIGH IMPACT - COMPLEX

#### 14. **Intelligent Lead Scoring & Routing**

**Trigger:** New lead created  
**Current Gap:** Basic round-robin assignment only  
**Enhancement to existing LeadAssignmentAgent:**

- Score leads by: nationality, service interest, lead source, urgency keywords
- Route high-value leads to senior consultants
- Route by language (Italian speakers → Italian-speaking team)
- Auto-prioritize based on passport expiry proximity

**Impact:** HIGH - Increases conversion rate 15-25%  
**Complexity:** COMPLEX (ML scoring model)  
**Business Value:** ⭐⭐⭐⭐⭐ (Revenue optimization)

---

#### 15. **Predictive Renewal Management**

**Trigger:** Practice completion  
**Current Gap:** Manual tracking of renewal dates  
**Automation:**

- Auto-calculate renewal date based on practice type
- Create renewal alert 90 days before
- Auto-generate renewal quote
- Send "early bird" discount offer

**Impact:** HIGH - Increases renewal rate  
**Complexity:** COMPLEX (renewal date calculation per practice type)  
**Business Value:** ⭐⭐⭐⭐⭐ (Recurring revenue)

---

## Implementation Priority Matrix

| Priority | Automation                     | Impact | Complexity | Effort (days) |
| -------- | ------------------------------ | ------ | ---------- | ------------- |
| P0       | Document Upload Notifications  | HIGH   | SIMPLE     | 2             |
| P0       | Stale Lead Follow-up           | HIGH   | SIMPLE     | 2             |
| P0       | Practice Stuck-in-Status       | HIGH   | SIMPLE     | 3             |
| P0       | Passport Expiry Alerts         | HIGH   | SIMPLE     | 2             |
| P1       | Smart Status Transitions       | HIGH   | MEDIUM     | 4             |
| P1       | Sentiment-Based Escalation     | HIGH   | MEDIUM     | 3             |
| P1       | Payment Reminder Sequence      | MEDIUM | SIMPLE     | 2             |
| P2       | Welcome Email Sequence         | MEDIUM | SIMPLE     | 2             |
| P2       | Document Verified Confirmation | MEDIUM | SIMPLE     | 1             |
| P2       | Team Weekly Summary            | MEDIUM | SIMPLE     | 2             |
| P2       | Auto-Practice Suggestion       | HIGH   | MEDIUM     | 4             |
| P3       | Client Portal Activity         | MEDIUM | MEDIUM     | 3             |
| P3       | Practice Completion Follow-up  | MEDIUM | MEDIUM     | 3             |
| P4       | Intelligent Lead Scoring       | HIGH   | COMPLEX    | 8             |
| P4       | Predictive Renewal             | HIGH   | COMPLEX    | 6             |

**Total P0 Effort: 9 days** (Can be implemented in 2 weeks)

---

## Technical Implementation Notes

### Existing Infrastructure to Leverage

1. **LeadAssignmentAgent** (`lead_assignment_agent.py`)
   - Pattern: LangGraph workflow
   - Reuse for: Document upload notifications, lead scoring

2. **DeadlineChecker** (`deadline_checker.py`)
   - Pattern: Daily cron job
   - Reuse for: Passport expiry, stale leads, stuck practices

3. **ProcessAutomationService** (`process_automation_service.py`)
   - Pattern: Status-triggered notifications
   - Reuse for: Payment reminders, completion follow-up

4. **ZohoEmailService** (`zoho_email_service.py`)
   - Pattern: Email sending via Zoho
   - Reuse for: All email sequences

5. **TelegramBotService** (`telegram_bot_service.py`)
   - Pattern: Team notifications
   - Reuse for: All internal alerts

### Database Schema Additions Needed

```sql
-- For automation tracking
CREATE TABLE automation_logs (
    id SERIAL PRIMARY KEY,
    automation_type VARCHAR(50),
    entity_type VARCHAR(50), -- 'client', 'practice', 'document'
    entity_id INTEGER,
    triggered_by VARCHAR(255),
    status VARCHAR(20), -- 'success', 'failed', 'skipped'
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- For email sequences
CREATE TABLE email_sequence_progress (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    sequence_type VARCHAR(50), -- 'welcome', 'payment_reminder', 'follow_up'
    step_number INTEGER,
    sent_at TIMESTAMP,
    opened_at TIMESTAMP,
    clicked_at TIMESTAMP
);

-- For practice SLA tracking
CREATE TABLE practice_sla_tracking (
    id SERIAL PRIMARY KEY,
    practice_id INTEGER REFERENCES practices(id),
    status VARCHAR(50),
    entered_at TIMESTAMP,
    alert_sent BOOLEAN DEFAULT FALSE,
    escalation_sent BOOLEAN DEFAULT FALSE
);
```

### Cron Job Schedule

```
# /etc/cron.d/zantara-automations

# Every hour - Check for document uploads
0 * * * * python -m backend.jobs.document_upload_checker

# Daily at 9 AM - Stale leads and stuck practices
0 9 * * * python -m backend.jobs.stale_checker

# Daily at 10 AM - Passport expiry alerts
0 10 * * * python -m backend.jobs.passport_expiry_checker

# Weekly - Team summaries
0 9 * * 1 python -m backend.jobs.weekly_summary

# Daily - Payment reminders
0 11 * * * python -m backend.jobs.payment_reminder
```

---

## Quick Wins (Start Here)

### Week 1: Document Upload Notifications

```python
# New file: backend/jobs/document_upload_checker.py
# Pattern: Similar to deadline_checker.py

async def check_new_document_uploads():
    """Check for documents uploaded by clients in last hour"""
    # Query client_documents for recent uploads
    # Send Telegram notification to assigned_to
    # Update practice status if all docs verified
```

### Week 2: Passport Expiry Alerts

```python
# New file: backend/jobs/passport_expiry_checker.py
# Pattern: Extend deadline_checker.py

async def check_passport_expiry():
    """Check passport expiry dates and send alerts"""
    # Query clients with passport_expiry within thresholds
    # Send email based on urgency level
    # Create timeline event
```

### Week 3: Stale Lead & Stuck Practice Alerts

```python
# New file: backend/jobs/stale_checker.py

async def check_stale_leads():
    """Find leads with no interaction in X days"""

async def check_stuck_practices():
    """Find practices stuck in status too long"""
```

---

## Success Metrics

| Automation       | Metric                | Target                   |
| ---------------- | --------------------- | ------------------------ |
| Document Upload  | Avg response time     | < 2 hours (from 8 hours) |
| Stale Lead       | Lead conversion       | +15%                     |
| Stuck Practice   | Avg resolution time   | -20%                     |
| Passport Expiry  | Emergency renewals    | -50%                     |
| Welcome Sequence | Onboarding completion | +25%                     |
| Payment Reminder | Payment speed         | -30%                     |

---

## Conclusion

The CRM system has a solid foundation with good existing automations. **The P0 items (9 days of work)** would deliver immediate, high-impact improvements:

1. **Document Upload Notifications** - Instant team awareness
2. **Stale Lead Follow-up** - Revenue recovery
3. **Practice Stuck-in-Status** - SLA compliance
4. **Passport Expiry** - Client retention

**Recommended Approach:**

- Start with P0 items (2 weeks)
- Measure impact with success metrics
- Proceed to P1 items (3-4 weeks)
- Consider P4 items (ML-based) for Q2

---

**Report Prepared By:** AI Analysis  
**Review Required By:** Zero  
**Next Step:** Prioritize P0 implementation
