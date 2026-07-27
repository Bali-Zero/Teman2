# CRM and Client Portal Live Reliability Design

**Date:** 2026-07-27
**Scope:** `kita.balizero.com` CRM workspace and `my.balizero.com` client portal
**Release boundary:** no external email, WhatsApp, or client-facing notification is sent during implementation or live QA.

## Problem

The live team and client flows are individually reachable, but the end-to-end
journey is not deterministic:

- a newly created process can be absent from the client portal until a required
  document row exists;
- successful mutations can leave a fresh React Query cache showing the previous
  client or process state;
- the client-status menu closes on its own `mousedown`, preventing mouse
  selection;
- cancelled practices are counted in the client profile tab even though the
  visible lists exclude them;
- a neutral superuser portal session shows an error on the visa page when no
  client has been selected;
- duplicate team identities can render as indistinguishable assignee options;
- several foreground/background pairs fail WCAG AA, and long email addresses can
  overflow the process detail card.

## Chosen Approach

Use existing contracts and add only the missing joins and cache transitions.

1. The portal process page loads `/api/portal/matters` as the authoritative
   practice list and merges required-document rows by `practice_id`. A practice
   therefore exists in the portal even when its document list is empty.
2. The matters payload exposes its existing raw practice status as an additive
   `status` field. No schema migration or new endpoint is required.
3. Successful writes immediately patch or invalidate the exact client query
   before navigation, followed by a background refetch. No arbitrary sleep,
   polling delay, or global cache reset is introduced.
4. The status dropdown reuses the existing tested `useClickOutside` hook and
   scopes the listener to its container.
5. The process tab count is derived from the same visible active/completed
   arrays shown below it, so cancelled items cannot remain in the badge.
6. A superuser without a selected client gets a neutral “select a client” empty
   state on the visa page. Other errors retain the existing error toast.
7. Assignee options are normalized by email, deduplicated, and labels that still
   collide are disambiguated with the email address.
8. Palette changes use the existing operative-dark and operative-light token
   hierarchy. The copper fill remains `#d4845a`; CTA text changes to the
   appropriate theme foreground. Muted text tokens are moved to already
   established AA-safe steps.
9. Long email addresses remain fully visible with wrapping and a non-shrinking
   icon.

## Data Flow

```text
CRM create/update
  -> authoritative API response
  -> patch/invalidate ["client", clientId]
  -> navigate or repaint immediately
  -> background refetch confirms server state

Portal process page
  -> profile
  -> matters (all visible practices)
  -> required documents
  -> merge documents into matter by practice id
  -> render process card even when documents = []
```

## API Compatibility

`GET /api/portal/matters` gains one additive field:

```json
{
  "id": 603,
  "title": "Investor KITAS",
  "status": "inquiry",
  "type": "visa",
  "progress": 10,
  "pending_docs": [],
  "next_deadline": null,
  "next_step": "inquiry"
}
```

Existing consumers continue to receive all prior fields. No database or
migration change is required.

## Error and Privacy Rules

- Only the known superuser selection message is converted to a neutral visa
  state; network, authorization, and backend errors remain visible.
- No client payload is logged by the new code or tests.
- Test fixtures use synthetic names and addresses only.
- Live QA uses one clearly named synthetic client and synthetic process.
- No invitation, notification, email, WhatsApp, or outbound webhook is
  triggered.
- Cleanup cancels/deletes the synthetic process first, then soft-deletes the
  synthetic client, and verifies both are absent from active lists.

## Verification

The release is accepted only after:

- frontend component/hook regression tests pass;
- backend portal-matters tests pass;
- frontend typecheck, lint on changed files, and production build pass;
- backend dependency import smoke and mandatory RAG gate pass;
- an independent reviewer approves the PR;
- CI merges and deploys through the repository’s normal Vercel/Fly paths;
- browser QA repeats the team/client journey on the live domains, captures and
  inspects screenshots, confirms the palette visually, and completes cleanup.
