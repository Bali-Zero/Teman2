# Cursor Patch 2: Extract Calendar → calendar.balizero.com

## Model: Claude Sonnet 4.6

## Context

You are working on a Next.js monorepo at `apps/mouth/`. The current app has a calendar feature at `/calendar` that integrates with Google Calendar API. It needs to be extracted into a standalone Next.js app deployed to `calendar.balizero.com`.

The calendar feature is the SMALLEST extraction (784 lines, single file):

### Source Files to Extract

```
apps/mouth/src/app/(workspace)/calendar/page.tsx       (784 lines - entire feature)
apps/mouth/src/app/api/calendar/                        (API routes for Google Calendar)
```

### Shared Dependencies Used

```
apps/mouth/src/lib/utils.ts       → cn() classname utility
lucide-react                      → Icons
```

Calendar is the simplest feature — it's a single page component with inline API calls. No external component files, no hooks, no complex state management.

## Task

### Step 1: Create New App

Create a new Next.js app at `apps/calendar/` with this structure:

```
apps/calendar/
├── src/
│   ├── app/
│   │   ├── layout.tsx          ← Root layout with auth gate
│   │   ├── page.tsx            ← Calendar page (from calendar/page.tsx)
│   │   ├── globals.css         ← Minimal dark theme styles
│   │   └── api/
│   │       └── calendar/       ← Copy API routes from main app
│   │           ├── events/route.ts
│   │           └── calendars/route.ts
│   ├── components/
│   │   └── ui/                 ← Copy only needed shadcn components
│   └── lib/
│       ├── api.ts              ← Slim API client (auth via .balizero.com cookie)
│       └── utils.ts            ← cn() utility
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── vercel.json
```

### Step 2: Auth Gate Pattern

The root layout.tsx MUST implement this auth pattern:

```typescript
// Auth check: read JWT from cookie on .balizero.com domain
// If no valid session → redirect to kita.balizero.com/login?redirect=calendar.balizero.com
// If valid session → render children

// The cookie is set by kita.balizero.com on the .balizero.com domain
// so all subdomains can read it.
```

Read `apps/mouth/src/lib/api.ts` to find the exact cookie/token mechanism. Same pattern as Patch 1.

### Step 3: Refactor the Calendar Page

The current page.tsx uses inline `fetch("/api/calendar/events")`. In the new app:

1. Copy the API routes from `apps/mouth/src/app/api/calendar/` into the new app
2. These API routes call the backend (nuzantara-rag.fly.dev) or Google Calendar API directly
3. Read the existing API route code to understand the proxy pattern
4. The Google Calendar service account credentials come from environment variables — document which env vars are needed in a `.env.example`

### Step 4: Remove From Main App

After extraction, in `apps/mouth/`:

1. Remove the calendar route: delete `src/app/(workspace)/calendar/` directory
2. Update navigation in `src/types/navigation.ts`: change Calendar href to `https://calendar.balizero.com` (external link)
3. Add `ExternalLink` icon indicator
4. Keep the calendar API routes in the main app IF other features depend on them (check for imports)

### Step 5: Vercel Configuration

Create `apps/calendar/vercel.json`:

```json
{
  "framework": "nextjs",
  "buildCommand": "next build",
  "outputDirectory": ".next"
}
```

## Design Constraints

- Dark theme: bg #141416, text #ececec, accent #d4845a
- Geist Sans font
- FULL SCREEN layout — calendar needs maximum space
- Top bar: "Bali Zero Calendar" title left, app-switcher grid icon right
- "Back to Kita" link in top-left
- The calendar UI is already self-contained — keep as-is, just extract

## Important Notes

The calendar currently has Italian weekday names (WEEKDAYS = ["Dom", "Lun", "Mar", "Mer", "Gio", "Ven", "Sab"]). Keep them — this is intentional, the team lead is Italian.

The TEAM_CALENDAR_ID is hardcoded. Move it to an environment variable in the new app.

## DO NOT

- Do not change the Google Calendar integration logic
- Do not redesign the calendar UI
- Do not add new dependencies
- Do not create tests
