# Cursor Patch 4: Extract Knowledge Base → knowledge.balizero.com

## Model: Claude Sonnet 4.6

## Context

You are working on a Next.js monorepo at `apps/mouth/`. The current app has a full Knowledge Base system at `/knowledge` with multiple sub-pages covering visa guides, company licenses, tax info, TKA regulations, blueprints, and more. It needs to be extracted into a standalone Next.js app deployed to `knowledge.balizero.com`.

The knowledge feature is the SECOND HEAVIEST extraction (~6,619 lines across 12 route files + 219 lines of API/types = **~6,838 lines total**).

### Source Files to Extract

**Route pages (6,619 lines):**

```
apps/mouth/src/app/(workspace)/knowledge/page.tsx               (417 lines - main hub)
apps/mouth/src/app/(workspace)/knowledge/loading.tsx             (53 lines - skeleton loader)
apps/mouth/src/app/(workspace)/knowledge/error.tsx               (42 lines - error boundary)
apps/mouth/src/app/(workspace)/knowledge/kitas/page.tsx          (845 lines - visa guide list)
apps/mouth/src/app/(workspace)/knowledge/kitas/[id]/page.tsx     (611 lines - visa detail)
apps/mouth/src/app/(workspace)/knowledge/blueprints/page.tsx     (2,057 lines - KBLI blueprints)
apps/mouth/src/app/(workspace)/knowledge/company-licenses/page.tsx (175 lines - company setup)
apps/mouth/src/app/(workspace)/knowledge/licenses/page.tsx       (615 lines - license types)
apps/mouth/src/app/(workspace)/knowledge/tax/page.tsx            (684 lines - tax info)
apps/mouth/src/app/(workspace)/knowledge/tka-jabatan/page.tsx    (834 lines - TKA regulations)
apps/mouth/src/app/(workspace)/knowledge/our-journey/page.tsx    (152 lines - company history)
apps/mouth/src/app/(workspace)/knowledge/projects/page.tsx       (134 lines - projects)
```

**API client and types (219 lines):**

```
apps/mouth/src/lib/api/knowledge/knowledge.api.ts    (36 lines - KnowledgeApi class)
apps/mouth/src/lib/api/knowledge/knowledge.types.ts   (45 lines - search result types)
apps/mouth/src/lib/api/knowledge/visa.types.ts         (67 lines - visa type definitions)
apps/mouth/src/lib/api/knowledge-activity.api.ts       (71 lines - KB activity tracking)
```

### Shared Dependencies Used

```
apps/mouth/src/lib/api.ts              → API client (auth, fetch wrapper)
apps/mouth/src/lib/logger.ts           → Logging utility
apps/mouth/src/lib/utils.ts            → cn() classname utility
apps/mouth/src/lib/enhanced-analytics.tsx → Analytics tracking (useEnhancedAnalytics hook)
apps/mouth/src/components/ui/          → Shadcn UI components (button, skeleton)
lucide-react                           → Icons (extensive use across all pages)
next/navigation                        → useRouter for client-side navigation
```

### Key Characteristics

- **No external component files** — all components are inline within each page file (VisaCard, CategoryFilter, BlueprintCard, etc.)
- **No custom hooks** — uses only `useState`, `useEffect`, `useRouter`, and the shared `useEnhancedAnalytics`
- **No React Query** — uses direct `api.get()` and `api.knowledge.searchDocs()` calls
- **Backend API calls** via the api client:
  - `api.knowledge.searchDocs()` — semantic search
  - `api.get("/api/knowledge/visa/")` — visa types list
  - `api.get("/api/knowledge/visa/{id}")` — visa detail
  - `api.kbActivity.logView()` — activity tracking (fire-and-forget)
- **PDF download links** — blueprints page links to PDFs hosted externally
- **Heavy inline data** — blueprints page has ~1,200 lines of hardcoded blueprint data objects

## Task

### Step 1: Create New App

Create a new Next.js app at `apps/knowledge/` with this structure:

```
apps/knowledge/
├── src/
│   ├── app/
│   │   ├── layout.tsx                  ← Root layout with auth gate
│   │   ├── page.tsx                    ← Knowledge hub (from knowledge/page.tsx)
│   │   ├── loading.tsx                 ← Skeleton loader
│   │   ├── error.tsx                   ← Error boundary
│   │   ├── globals.css                 ← Dark theme styles
│   │   ├── kitas/
│   │   │   ├── page.tsx                ← Visa guide list
│   │   │   └── [id]/
│   │   │       └── page.tsx            ← Visa detail page
│   │   ├── blueprints/
│   │   │   └── page.tsx                ← KBLI blueprints
│   │   ├── company-licenses/
│   │   │   └── page.tsx                ← Company setup guide
│   │   ├── licenses/
│   │   │   └── page.tsx                ← License types
│   │   ├── tax/
│   │   │   └── page.tsx                ← Tax & NPWP info
│   │   ├── tka-jabatan/
│   │   │   └── page.tsx                ← TKA regulations
│   │   ├── our-journey/
│   │   │   └── page.tsx                ← Company history
│   │   └── projects/
│   │       └── page.tsx                ← Projects
│   ├── components/
│   │   └── ui/                         ← Copy needed shadcn components (button, skeleton)
│   └── lib/
│       ├── api.ts                      ← Slim API client (auth via .balizero.com cookie)
│       ├── api/
│       │   └── knowledge/
│       │       ├── knowledge.api.ts    ← KnowledgeApi class
│       │       ├── knowledge.types.ts  ← Search types
│       │       └── visa.types.ts       ← Visa types
│       ├── knowledge-activity.api.ts   ← KB activity tracking
│       ├── enhanced-analytics.tsx      ← Simplified analytics (or stub)
│       ├── logger.ts                   ← Copy of logger
│       └── utils.ts                    ← cn() utility
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── vercel.json
```

### Step 2: Auth Gate Pattern

Same as Patches 1-3:

```typescript
// Auth check: read JWT from cookie on .balizero.com domain
// If no valid session → redirect to kita.balizero.com/login?redirect=knowledge.balizero.com
// If valid session → render children
```

Read `apps/mouth/src/lib/api.ts` to find the exact cookie/token mechanism. Same SSO pattern.

### Step 3: Fix Internal Navigation

All pages use `router.push("/knowledge/...")` for internal navigation. In the new app:

1. The main hub page is now at `/` (was `/knowledge`)
2. Sub-pages are at `/kitas`, `/blueprints`, etc. (were `/knowledge/kitas`, `/knowledge/blueprints`, etc.)
3. **Update ALL `router.push()` calls** to remove the `/knowledge` prefix:
   - `router.push("/knowledge")` → `router.push("/")`
   - `router.push("/knowledge/kitas")` → `router.push("/kitas")`
   - `router.push("/knowledge/kitas/${visa.id}")` → `router.push("/kitas/${visa.id}")`
   - etc.
4. **Update ALL `href` attributes** in the category grid on the main page:
   - `href: "/knowledge/kitas"` → `href: "/kitas"`
   - `href: "/knowledge/company-licenses"` → `href: "/company-licenses"`
   - etc.
5. The "Back to Knowledge Base" links on sub-pages should point to `/` instead of `/knowledge`
6. The "Ask Zantara AI" button on the kitas page currently points to `/chat` — change this to `https://kita.balizero.com/chat` (or `https://kita.balizero.com/chat` depending on where chat lives)

### Step 4: Handle the API Client

The knowledge pages use these API patterns:

```typescript
// Search (main page)
const response = await api.knowledge.searchDocs({ query, limit: 20 });

// Visa list
const response = await api.get<VisaTypeListResponse>("/api/knowledge/visa/");

// Visa detail (check kitas/[id]/page.tsx for exact call)
const response = await api.get<VisaType>(`/api/knowledge/visa/${id}`);

// Activity tracking (fire-and-forget)
api.kbActivity.logView("knowledge_hub", undefined, "Knowledge Base", "main");
```

All calls go to the backend at `nuzantara-rag.fly.dev`. The slim API client should:

1. Read the auth token from the `.balizero.com` cookie
2. Prepend the backend base URL to API paths
3. Include the `KnowledgeApi` and `KnowledgeActivityApi` classes

### Step 5: Handle Enhanced Analytics

The `useEnhancedAnalytics` hook is used in 5 of the knowledge pages. Options:

**Option A (Recommended):** Create a stub that no-ops. The analytics calls are non-critical:

```typescript
export function useEnhancedAnalytics() {
  return {
    trackPageView: () => {},
    trackUserInteraction: () => {},
    trackPerformance: () => {},
    trackEvent: () => {},
  };
}
```

**Option B:** Copy the full enhanced-analytics.tsx if you want to preserve tracking. Read the file first to understand its dependencies.

### Step 6: Remove From Main App

After extraction, in `apps/mouth/`:

1. Remove knowledge routes: delete `src/app/(workspace)/knowledge/` directory entirely
2. Update navigation in `src/types/navigation.ts`: change Knowledge href to `https://knowledge.balizero.com`
3. Add `ExternalLink` icon indicator next to the Knowledge nav item
4. **Keep** `src/lib/api/knowledge/` and `src/lib/api/knowledge-activity.api.ts` IF other features depend on them (the search/chat features may use `api.knowledge.searchDocs`). Use grep to verify:
   ```bash
   grep -r "api.knowledge" src/ --include="*.ts" --include="*.tsx" | grep -v "knowledge/"
   grep -r "api.kbActivity" src/ --include="*.ts" --include="*.tsx" | grep -v "knowledge/"
   ```
5. If `api.knowledge` or `api.kbActivity` are used elsewhere (likely in chat or search components), keep the API files in the main app
6. Clean up any unused imports in package.json after removal

### Step 7: Vercel Configuration

Create `apps/knowledge/vercel.json`:

```json
{
  "framework": "nextjs",
  "buildCommand": "next build",
  "outputDirectory": ".next"
}
```

## Design Constraints

- Dark theme: bg #141416, text #ececec, accent #d4845a (terracotta)
- Geist Sans font
- FULL SCREEN layout — knowledge base needs maximum reading space
- Top bar: "Bali Zero Knowledge" title left, app-switcher grid icon right
- "Back to Kita" link in top-left (links to kita.balizero.com)
- Keep ALL the category grid styling on the main page
- Keep the visa card design (gradient backgrounds, difficulty badges, series grouping)
- Keep the blueprint cards with PDF download links
- The feature uses CSS variables extensively (`var(--foreground)`, `var(--accent)`, `var(--border)`, etc.) — make sure globals.css defines these

## Extraction Order

This is a large feature. Be methodical:

1. First, create the app scaffold with layout, globals.css, and the API client
2. Then, copy the main hub page (`/`) and verify it renders
3. Then, add sub-pages one by one, starting with the simplest:
   - `our-journey` (152 lines)
   - `projects` (134 lines)
   - `company-licenses` (175 lines)
   - `kitas` list (845 lines)
   - `kitas/[id]` detail (611 lines)
   - `licenses` (615 lines)
   - `tax` (684 lines)
   - `tka-jabatan` (834 lines)
   - `blueprints` (2,057 lines — largest, do last)
4. Verify all navigation links work between pages
5. Finally, clean up the main app

## DO NOT

- Do not change any backend code
- Do not redesign or restyle the knowledge pages — keep them exactly as they are
- Do not remove the activity tracking (kbActivity) — just ensure it calls the backend
- Do not simplify the visa card component or blueprint card styling
- Do not add new dependencies beyond what the knowledge feature already uses
- Do not create tests
- Do not merge the inline components into separate files — keep the same file structure where components are defined within their page files
