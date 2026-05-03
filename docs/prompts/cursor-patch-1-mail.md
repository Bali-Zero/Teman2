# Cursor Patch 1: Extract Email → mail.balizero.com

## Model: Claude Sonnet 4.6

## Context

You are working on a Next.js monorepo at `apps/mouth/`. The current app has an email feature at `/email` that is a full email client integrated with Zoho Mail. It needs to be extracted into a standalone Next.js app that will be deployed to `mail.balizero.com`.

The email feature is currently ~2,774 lines across these files:

### Source Files to Extract

```
apps/mouth/src/app/(workspace)/email/page.tsx          (857 lines - main page)
apps/mouth/src/components/email/EmailCompose.tsx       (compose modal)
apps/mouth/src/components/email/EmailList.tsx           (email list view)
apps/mouth/src/components/email/EmailViewer.tsx         (email detail viewer)
apps/mouth/src/components/email/FolderSidebar.tsx       (folder navigation)
apps/mouth/src/components/email/ZohoConnectBanner.tsx   (Zoho connection UI)
apps/mouth/src/components/email/index.ts                (barrel exports)
apps/mouth/src/lib/api/email/email.types.ts             (TypeScript types)
```

### Shared Dependencies Used

```
apps/mouth/src/lib/api.ts         → API client (auth, fetch wrapper)
apps/mouth/src/lib/logger.ts      → Logging utility
apps/mouth/src/lib/utils.ts       → cn() classname utility
apps/mouth/src/components/ui/     → Shadcn UI components (button, input, etc.)
```

## Task

### Step 1: Create New App

Create a new Next.js app at `apps/mail/` with this structure:

```
apps/mail/
├── src/
│   ├── app/
│   │   ├── layout.tsx          ← Root layout with auth gate
│   │   ├── page.tsx            ← Email client (from email/page.tsx)
│   │   └── globals.css         ← Minimal styles from kbli-theme.css
│   ├── components/
│   │   ├── EmailCompose.tsx
│   │   ├── EmailList.tsx
│   │   ├── EmailViewer.tsx
│   │   ├── FolderSidebar.tsx
│   │   ├── ZohoConnectBanner.tsx
│   │   └── ui/                 ← Copy only needed shadcn components
│   └── lib/
│       ├── api.ts              ← Slim API client (auth via .balizero.com cookie)
│       ├── logger.ts           ← Copy of logger
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
// If no valid session → redirect to kita.balizero.com/login?redirect=mail.balizero.com
// If valid session → render children

// The cookie is set by kita.balizero.com on the .balizero.com domain
// so all subdomains can read it. Cookie name: "bz_token" or check the
// current cookie name in apps/mouth/src/lib/api.ts
```

Read `apps/mouth/src/lib/api.ts` to find the exact cookie/token mechanism used. The new app must use the SAME auth token format. Users must NOT need to log in again — if they logged into kita.balizero.com, they're already authenticated on mail.balizero.com.

### Step 3: Remove From Main App

After extraction, in `apps/mouth/`:

1. Remove the email route: delete `src/app/(workspace)/email/` directory
2. Remove email components: delete `src/components/email/` directory
3. Update navigation in `src/types/navigation.ts`: change the Email item's href from "/email" to point to `https://mail.balizero.com` (external link, open in same tab)
4. Add an `ExternalLink` icon indicator next to the Email nav item
5. Remove email-related API types if only used by email

### Step 4: Vercel Configuration

Create `apps/mail/vercel.json`:

```json
{
  "framework": "nextjs",
  "buildCommand": "next build",
  "outputDirectory": ".next"
}
```

The app will be deployed to Vercel and connected to `mail.balizero.com` via Cloudflare DNS (CNAME → cname.vercel-dns.com).

## Design Constraints

- Keep the EXACT same dark theme: bg #141416, text #ececec, accent #d4845a
- Keep the same Geist Sans font
- The layout should be FULL SCREEN (no sidebar from main app — this IS the app)
- Add a small "Back to Kita" link in the top-left corner (links to kita.balizero.com)
- Add an app-switcher icon (grid 3x3) in the top-right that shows: Kita, Mail, Calendar, Drive, Knowledge

## Backend

The email API routes are proxied through Next.js API routes to the backend at nuzantara-rag.fly.dev. Check `apps/mouth/src/app/api/` for any email-related API routes and replicate them in the new app, OR have the new app call the backend directly.

## DO NOT

- Do not change any backend code
- Do not modify the Zoho integration logic — copy it exactly
- Do not add new dependencies beyond what the email feature already uses
- Do not create tests (they will be added separately)
