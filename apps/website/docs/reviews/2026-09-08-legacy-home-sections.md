# Legacy homepage sections in direction A

Local implementation only. No build, preview restart, push or deployment was performed by this worker.

## Implemented

- Homepage order: Hero, four service/tool cards, Reviews, E-VOA, Second Home, portal, Journal, Team, Contact, Footer.
- Reviews now use a compact editorial introduction, one clearly attributed Google source card, and the existing Adit portrait on desktop and mobile. No client names, quotes, rating values or totals were copied or invented.
- `/about` presents the company story in direction A with existing founder portraits and links to Team, services, Journal and contact. `/v2/company/about` renders the same page to preserve the legacy route.
- Homepage Team and Footer link to the local company story. Header/home links and Footer anchors now resolve from inner pages. Team navigation also includes Our story.
- A global Zantara entry opens a native modal dialog with an explicit unavailable-in-preview state and verified contact destinations. Native dialog supplies keyboard focus containment and Escape closure; its close handler restores the trigger focus. Browser verification remains part of the parent's integrated QA.
- The existing conflicting `Since 2020` label was removed from the two owned footer/Team surfaces. No date, volume, license or credential claim was introduced.

## Boundaries found

- The legacy v2 FAB has no click handler. The parent's public click check also found no opening chat.
- The separate legacy `components/ZantaraWidget.tsx` uses POST `/api/agentic-rag/stream`. A read-only OPTIONS request to the actual backend with Origin `http://127.0.0.1:3100` returned HTTP 400, `Disallowed CORS origin`, on 2026-09-08 WITA. No chat message was sent. No proxy or CORS change was introduced.
- Telegram remains suppressed. The existing destination evidence records an unrelated adult/spam bot at that destination. Its continued presence in the public footer does not establish that it is a usable Bali Zero channel.
- About narrative is a restrained adaptation of the current public [company story](https://balizero.com/v2/company/about). Unverified public counts, dates and credentials are excluded. The existing verified roster remains unchanged.
- Reviews remain source-linked, not an embedded testimonial feed. Restoring real cards requires an authorized source/consent contract that meets the site's client data boundary.

## Validation

Command: `npm test -- src/components/LegacySections.test.tsx src/components/Team.test.tsx src/components/Entry.test.tsx src/app/page.test.tsx --maxWorkers=1 --no-file-parallelism`

Result: 12 tests across 4 files passed. Covered destination continuity, existing roster and assets, mobile navigation controls, company-story links and assistant dialog/contact/focus-return behavior. First pass found an outdated `#tools` test expectation and unsupported jsdom close-event helper; both were corrected before the passing run. Existing Vite config and jsdom document-navigation warnings remain non-failing.

## Owned source changes

- `src/app/page.tsx`
- `src/app/layout.tsx`
- `src/app/team/page.tsx`
- `src/app/about/page.tsx` (new)
- `src/app/v2/company/about/page.tsx` (new)
- `src/components/Entry.tsx`, `Entry.test.tsx`
- `src/components/Footer.tsx`
- `src/components/Team.tsx`, `Team.module.css`
- `src/components/Reviews.tsx`
- `src/components/LegacySections.module.css`, `LegacySections.test.tsx` (new)
- `src/components/ZantaraEntry.tsx`, `ZantaraEntry.module.css` (new)

No Journal/service-detail files, global stylesheet, dependencies, environment files, destination release state or production code were changed by this worker. Parent owns integrated typecheck/build, preview and desktop/mobile visual QA.
