# Email Module Analysis & Enhancement Plan

**Date**: January 22, 2026
**Analyst**: Claude Code
**Module**: apps/mouth (Email Page) + apps/backend-rag (Zoho Email API)

---

## 1. Executive Summary

The email module provides Zoho Mail integration with basic email operations. While core functionality works, there are critical bugs to fix and significant feature gaps compared to a professional email experience like Zoho Mail.

---

## 2. Current State Analysis

### 2.1 Architecture Overview

```
Frontend (apps/mouth)
├── src/app/(workspace)/email/page.tsx          # Main page (680 lines)
├── src/lib/api/email/email.api.ts              # API client (250 lines)
├── src/lib/api/email/email.types.ts            # TypeScript types (190 lines)
└── src/components/email/
    ├── EmailCompose.tsx                         # Compose modal (405 lines)
    ├── EmailList.tsx                            # Email list (297 lines)
    ├── EmailViewer.tsx                          # Email viewer (446 lines)
    └── FolderSidebar.tsx                        # Folder sidebar (157 lines)

Backend (apps/backend-rag)
├── backend/app/routers/zoho_email.py           # FastAPI router (776 lines)
└── backend/services/integrations/
    └── zoho_email_service.py                   # Core service (998 lines)
```

### 2.2 Working Features

| Feature          | Status     | Notes                                 |
| ---------------- | ---------- | ------------------------------------- |
| OAuth Connection | ✅ Working | Zoho OAuth flow                       |
| Folder List      | ✅ Working | All Zoho folders visible              |
| Email List       | ✅ Working | Pagination working                    |
| Email Viewing    | ✅ Working | HTML sanitized with DOMPurify         |
| Compose Email    | ✅ Working | Basic compose with attachments        |
| Reply/Reply All  | ✅ Working | Pre-fills recipient, subject          |
| Forward          | ✅ Working | Basic forwarding                      |
| Star/Flag        | ✅ Working | Toggle flag on emails                 |
| Delete           | ✅ Working | Move to trash                         |
| Folder Switching | ✅ Working | All folders accessible                |
| Search           | ⚠️ Partial | Works but may have issues             |
| CRM Integration  | ✅ Working | Shows client badge for known contacts |
| Add to CRM       | ✅ Working | Button appears for unknown contacts   |
| Attachments      | ✅ Working | Upload and download                   |
| Save Draft       | ✅ Working | Saves to Drafts folder                |

---

## 3. Critical Bugs Found

### 3.1 HTML Entity Encoding Bug (HIGH PRIORITY)

**Location**: `EmailViewer.tsx` line ~200-220

**Problem**: The "To" and "CC" fields display raw HTML entities instead of decoded text:

```
&quot;tomaikens&quot;&lt;tom.aikens@tomaikens.co.uk&gt;
```

Should display:

```
"tomaikens" <tom.aikens@tomaikens.co.uk>
```

**Root Cause**: The API returns HTML-encoded strings that are not being decoded before display.

**Fix**: Decode HTML entities in the email detail response:

```typescript
// Add helper function
function decodeHtmlEntities(text: string): string {
  const textarea = document.createElement("textarea");
  textarea.innerHTML = text;
  return textarea.value;
}

// Use in EmailViewer.tsx when rendering recipients
const decodedTo = decodeHtmlEntities(email.to_address || "");
```

### 3.2 Reply Date Bug (MEDIUM PRIORITY)

**Location**: `email/page.tsx` line ~400 (handleReply function)

**Problem**: Reply modal shows "On Unknown date, Sahira wrote:" instead of actual date.

**Root Cause**: Date formatting fails when creating reply content.

**Fix**: Properly parse the email date:

```typescript
const emailDate = new Date(originalEmail.received_time || originalEmail.date);
const formattedDate = emailDate.toLocaleString("it-IT", {
  dateStyle: "full",
  timeStyle: "short",
});
```

### 3.3 Compose Subject Label Bug (LOW PRIORITY)

**Location**: `EmailCompose.tsx`

**Problem**: Subject field shows "Subject Subject" as placeholder/label.

**Fix**: Check for duplicate label rendering in the Subject input field.

### 3.4 Page Redirect Bug (HIGH PRIORITY)

**Location**: `email/page.tsx` - useEffect hooks

**Problem**: Email page sometimes redirects to /chat after a few seconds of loading.

**Root Cause**: Likely a race condition in the connection check or an authentication redirect.

**Fix**: Review the `useEffect` hooks that check connection status and add proper guards.

---

## 4. Missing Features (Zoho Mail Comparison)

### 4.1 Critical Missing Features

| Feature                  | Priority | Effort | Description                             |
| ------------------------ | -------- | ------ | --------------------------------------- |
| Unread Count Badges      | HIGH     | Low    | Show unread count on folder buttons     |
| Contact Autocomplete     | HIGH     | Medium | Suggest contacts when typing recipients |
| Rich Text Editor         | HIGH     | Medium | WYSIWYG editor for compose              |
| Email Signatures         | HIGH     | Medium | Configurable email signatures           |
| Keyboard Shortcuts       | HIGH     | Medium | Standard email shortcuts (r=reply, etc) |
| Thread/Conversation View | HIGH     | High   | Group related emails together           |

### 4.2 Important Missing Features

| Feature             | Priority | Effort | Description                         |
| ------------------- | -------- | ------ | ----------------------------------- |
| Labels/Tags         | MEDIUM   | Medium | Color-coded labels for organization |
| Email Filters/Rules | MEDIUM   | High   | Auto-sort incoming emails           |
| Snooze Emails       | MEDIUM   | Medium | Remind about email later            |
| Undo Send           | MEDIUM   | Low    | Cancel sent email within X seconds  |
| Schedule Send       | MEDIUM   | Medium | Send email at future time           |
| Email Templates     | MEDIUM   | Medium | Reusable email templates            |

### 4.3 Nice-to-Have Features

| Feature                | Priority | Effort | Description                     |
| ---------------------- | -------- | ------ | ------------------------------- |
| Split Pane Options     | LOW      | Low    | Horizontal/vertical/off preview |
| Bulk Selection         | LOW      | Low    | Shift+click for range selection |
| Drag & Drop to Folders | LOW      | Medium | Move emails by dragging         |
| Print Email            | LOW      | Low    | Print formatted email           |
| Read Receipts          | LOW      | Medium | Request/send read confirmations |
| Email Priority         | LOW      | Low    | Set importance level            |
| Calendar Integration   | LOW      | High   | Schedule meetings from email    |
| Notes on Emails        | LOW      | Medium | Add internal notes              |

---

## 5. UI/UX Improvements

### 5.1 Visual Design Issues

1. **Email List Density**
   - Current: Fixed height rows
   - Improve: Add density options (compact/comfortable/default)

2. **Action Button Visibility**
   - Current: Action buttons require scrolling in email viewer
   - Improve: Sticky header with actions always visible

3. **Folder Sidebar**
   - Current: No visual distinction for folders with unread
   - Improve: Bold text + badge for folders with unread emails

4. **Email Preview**
   - Current: Full-width layout only
   - Improve: Add split-view options (right panel, bottom panel)

5. **Loading States**
   - Current: Basic skeleton loaders
   - Improve: Shimmer animations, progress indicators

### 5.2 Interaction Improvements

1. **Quick Actions on Hover**
   - Add archive, delete, snooze buttons on email row hover

2. **Swipe Gestures (Mobile)**
   - Swipe right to archive
   - Swipe left to delete

3. **Drag & Drop**
   - Drag emails to folders
   - Drag attachments to compose

4. **Context Menu**
   - Right-click for quick actions

5. **Inline Reply**
   - Reply without opening modal (expandable in list)

---

## 6. System Integrations

### 6.1 Existing Integrations (Working)

1. **CRM Integration**
   - Auto-lookup sender in CRM
   - "Add to CRM" button for new contacts
   - Shows client badge for existing contacts

### 6.2 Proposed New Integrations

1. **Zantara AI Integration**

   ```
   - Auto-summarize long emails
   - Suggest reply drafts
   - Extract action items
   - Sentiment analysis
   - Language translation
   ```

2. **Process/Workflow Integration**

   ```
   - Create task from email
   - Link email to existing process
   - Auto-categorize by process type
   ```

3. **Documents Integration**

   ```
   - Save attachments to Drive
   - Link to related documents
   - Preview attachments inline
   ```

4. **Intelligence Center Integration**

   ```
   - News alerts in inbox
   - Visa status notifications
   - Compliance reminders
   ```

5. **Calendar Integration**
   ```
   - Detect meeting requests
   - Quick schedule from email
   - Show availability
   ```

---

## 7. Implementation Roadmap

### Phase 1: Bug Fixes (Week 1)

1. [ ] Fix HTML entity encoding bug
2. [ ] Fix reply date formatting
3. [ ] Fix compose subject label
4. [ ] Fix page redirect issue
5. [ ] Add unread count badges

### Phase 2: Core UX (Week 2-3)

1. [ ] Contact autocomplete
2. [ ] Rich text editor (TipTap or Quill)
3. [ ] Email signatures
4. [ ] Keyboard shortcuts
5. [ ] Quick actions on hover

### Phase 3: Advanced Features (Week 4-5)

1. [ ] Thread/conversation view
2. [ ] Labels/tags system
3. [ ] Email templates
4. [ ] Snooze functionality
5. [ ] Undo send

### Phase 4: AI Integration (Week 6-7)

1. [ ] Email summarization (Zantara AI)
2. [ ] Smart reply suggestions
3. [ ] Action item extraction
4. [ ] Auto-categorization

### Phase 5: Polish (Week 8)

1. [ ] Split pane views
2. [ ] Density options
3. [ ] Drag & drop
4. [ ] Mobile optimizations
5. [ ] Performance optimization

---

## 8. Technical Recommendations

### 8.1 Backend Improvements

```python
# zoho_email_service.py improvements needed:

1. Add HTML entity decoding for recipient fields
2. Add proper error handling for OAuth token refresh
3. Implement email threading logic
4. Add caching for folder list (Redis)
5. Add rate limiting for API calls
```

### 8.2 Frontend Improvements

```typescript
// Suggested tech stack additions:

1. TipTap or Quill for rich text editor
2. react-select or downshift for autocomplete
3. framer-motion for animations
4. react-hotkeys-hook for keyboard shortcuts
5. react-virtuoso for large email lists
```

### 8.3 Performance Optimizations

1. **Virtualized List**: Use react-virtuoso for email list (already partially implemented)
2. **Lazy Loading**: Load email content only when selected
3. **Prefetching**: Prefetch next page of emails
4. **Caching**: Cache email list with React Query
5. **Web Workers**: Parse large HTML emails in background

---

## 9. Files to Modify

### Critical Bug Fixes

- `apps/mouth/src/components/email/EmailViewer.tsx` (HTML entity fix)
- `apps/mouth/src/app/(workspace)/email/page.tsx` (date fix, redirect fix)
- `apps/mouth/src/components/email/EmailCompose.tsx` (subject fix)

### Feature Additions

- `apps/mouth/src/components/email/EmailList.tsx` (quick actions, density)
- `apps/mouth/src/components/email/FolderSidebar.tsx` (unread badges)
- `apps/mouth/src/lib/api/email/email.api.ts` (new endpoints)
- `apps/backend-rag/backend/services/integrations/zoho_email_service.py` (threading, AI)

### New Files Needed

- `apps/mouth/src/components/email/ContactAutocomplete.tsx`
- `apps/mouth/src/components/email/RichTextEditor.tsx`
- `apps/mouth/src/components/email/EmailSignatureManager.tsx`
- `apps/mouth/src/components/email/EmailLabels.tsx`
- `apps/mouth/src/components/email/EmailThreadView.tsx`
- `apps/mouth/src/hooks/useEmailKeyboardShortcuts.ts`

---

## 10. Success Metrics

1. **Bug-Free Core**: Zero critical bugs in basic email operations
2. **Feature Parity**: 80% of Zoho Mail features implemented
3. **Performance**: <500ms email list load, <200ms folder switch
4. **User Satisfaction**: Positive feedback from team users
5. **AI Integration**: At least 3 AI-powered features active

---

_Document generated by Claude Code analysis on January 22, 2026_
