# Omnichannel 2.0: The Unified Command Center

## Product Specification & Roadmap (2026)

### 1. Vision

Transform the Omnichannel Dashboard from a passive message viewer into a pro-active **Lead Operating System**. It serves as the central nervous system where the Sales, Legal, and Support teams interact with clients across all channels (WA, TG, IG, Email).

### 2. Core Philosophy

- **Unified Inbox:** No channel silos. A lead is a lead, regardless of where they message.
- **Context is King:** Never open a chat without knowing who the client is (CRM Data) and what they want (AI Intent).
- **Collaboration First:** Internal notes, tagging, and assignment are as important as the reply itself.
- **AI Augmented:** The AI drafts responses, summarizes long threads, and scores leads automatically.

### 3. User Interface: The 3-Pane Layout

The dashboard will adopt the industry-standard "Command Center" layout:

#### Pane A: The Unified Inbox (Left)

- **Filters:** All Open, My Leads, Unassigned, VIP, High Risk.
- **Channel Icons:** Small badges (WA, TG, IG) to distinguish sources.
- **Status Indicators:** 🟢 New, 🟡 In Progress, 🔴 Action Required.
- **Preview:** Client Name + Last Message Snippet + Time.

#### Pane B: The Action Stream (Center)

- **Chat Interface:** Modern bubble layout.
- **Internal Notes:** Toggle to switch between "Reply to Client" and "Internal Team Note" (Yellow background).
- **AI Drafts:** "Ghost text" suggestions that users can Tab-complete.
- **Rich Media:** Support for Images, PDFs, and Voice Notes.

#### Pane C: The Intelligence Panel (Right)

- **CRM Card:** Name, Company, Current Visa Status, Deal Value.
- **Lead Score:** 0-100 Score based on interaction sentiment and intent.
- **Smart Actions:**
  - [Assign to Me] / [Assign to Legal]
  - [Convert to Deal]
  - [Close Conversation]
- **Tags:** #Visa, #RealEstate, #PMA, #Complaint.

### 4. Technical Architecture Changes

#### Frontend (apps/mouth)

- **New Directory:** `src/app/(workspace)/omnichannel`
- **State Management:** React Query for real-time syncing.
- **Types:** Enhanced `Conversation` type to include `status`, `assignee`, `tags`.

#### Backend (apps/backend-rag)

- **Database:** Migration to add `status`, `assigned_to`, `priority` columns to `conversations` table.
- **API:**
  - `PATCH /api/conversations/{id}/status`
  - `POST /api/conversations/{id}/assign`
  - `POST /api/conversations/{id}/notes`

### 5. Implementation Phases

1.  **Phase 1 (Immediate):** UI Overhaul. Implement the 3-pane layout using existing data. Mock missing CRM/Status fields to validate UX.
2.  **Phase 2 (Functionality):** Connect "Assign" and "Status" buttons to temporary local state or new API endpoints.
3.  **Phase 3 (AI Integration):** Enable "AI Summarization" and "Drafting" features in the center pane.
