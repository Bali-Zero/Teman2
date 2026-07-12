# Cursor Patch 3: Extract Documents → drive.balizero.com

## Model: Claude Sonnet 4.6

## Context

You are working on a Next.js monorepo at `apps/mouth/`. The current app has a full Google Drive-like document management system at `/documents`. It's the HEAVIEST feature (~9,062 lines) and needs to be extracted into a standalone Next.js app deployed to `drive.balizero.com`.

### Source Files to Extract

**Page and local components (164KB):**

```
apps/mouth/src/app/(workspace)/documents/page.tsx              (700 lines)
apps/mouth/src/app/(workspace)/documents/components/
├── DepartmentHome.tsx
├── DocumentsErrorBoundary.tsx
├── DriveBreadcrumb.tsx
├── DriveInfoPanel.tsx
├── DriveSidebar.tsx
├── DriveToolbar.tsx
├── DriveToolbarOptimized.tsx
├── FileGrid.tsx
├── FileGridSkeleton.tsx
├── FileGridVirtualized.tsx
├── FileList.tsx
├── FileListSkeleton.tsx
├── file-icon.tsx
└── index.ts
```

**Shared document components (88KB):**

```
apps/mouth/src/components/documents/
├── ContextMenu.tsx
├── DropZone.tsx
├── FileModal.tsx
├── FileUploadField.tsx
├── FileViewer.tsx
├── MoveDialog.tsx
├── PermissionDialog.tsx
├── UploadDialog.tsx
└── index.ts
```

**Hooks:**

```
apps/mouth/src/hooks/useDrive.ts              (React Query hooks for Drive API)
apps/mouth/src/hooks/useKeyboardNavigation.ts  (keyboard shortcuts)
```

**Logging:**

```
apps/mouth/src/lib/logging/drive-logger.ts     (structured Drive logging)
```

**API types:**

```
apps/mouth/src/lib/api/drive/drive.types.ts    (TypeScript types)
```

### Shared Dependencies Used

```
apps/mouth/src/lib/api.ts         → API client
apps/mouth/src/lib/logger.ts      → Logger
apps/mouth/src/lib/utils.ts       → cn()
apps/mouth/src/components/ui/     → Shadcn (button, input, dialog, etc.)
@tanstack/react-query             → Data fetching
framer-motion                     → Animations
lucide-react                      → Icons
```

## Task

### Step 1: Create New App

Create a new Next.js app at `apps/drive/` with this structure:

```
apps/drive/
├── src/
│   ├── app/
│   │   ├── layout.tsx              ← Root layout with auth gate + QueryProvider
│   │   ├── page.tsx                ← Main Drive page
│   │   ├── globals.css             ← Dark theme styles
│   │   └── providers.tsx           ← React Query provider
│   ├── components/
│   │   ├── drive/                  ← All Drive-specific components
│   │   │   ├── DepartmentHome.tsx
│   │   │   ├── DriveBreadcrumb.tsx
│   │   │   ├── DriveInfoPanel.tsx
│   │   │   ├── DriveSidebar.tsx
│   │   │   ├── DriveToolbar.tsx
│   │   │   ├── FileGrid.tsx
│   │   │   ├── FileGridSkeleton.tsx
│   │   │   ├── FileList.tsx
│   │   │   ├── FileListSkeleton.tsx
│   │   │   ├── file-icon.tsx
│   │   │   └── index.ts
│   │   ├── documents/              ← Shared document components
│   │   │   ├── ContextMenu.tsx
│   │   │   ├── DropZone.tsx
│   │   │   ├── FileModal.tsx
│   │   │   ├── FileViewer.tsx
│   │   │   ├── MoveDialog.tsx
│   │   │   ├── UploadDialog.tsx
│   │   │   └── index.ts
│   │   └── ui/                     ← Copy needed shadcn components
│   ├── hooks/
│   │   ├── useDrive.ts
│   │   └── useKeyboardNavigation.ts
│   └── lib/
│       ├── api.ts                  ← Slim API client
│       ├── api/drive/drive.types.ts
│       ├── logger.ts
│       ├── logging/drive-logger.ts
│       └── utils.ts
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── vercel.json
```

### Step 2: Auth Gate Pattern

Same as Patch 1 and 2:

```typescript
// Auth check: read JWT from cookie on .balizero.com domain
// If no valid session → redirect to kita.balizero.com/login?redirect=drive.balizero.com
// If valid session → render children
```

### Step 3: React Query Setup

The Drive feature uses @tanstack/react-query extensively (useDriveFiles, useDriveStatus, useDriveMutations). Create a providers.tsx that wraps the app with QueryClientProvider.

Read `apps/mouth/src/hooks/useDrive.ts` carefully — it contains:

- `useDriveFiles(folderId, searchQuery)` — paginated file listing
- `useDriveStatus()` — connection check
- `useDriveMutations()` — create, rename, delete, move operations
- `usePrefetchFolder()` — hover prefetch for instant navigation

These hooks call the backend API. Ensure the API base URL points to `nuzantara-rag.fly.dev` or through a proxy.

### Step 4: Handle API Routes

Check if there are Drive-related API routes in `apps/mouth/src/app/api/`:

- If they exist, copy them to the new app
- If the hooks call the backend directly via the api.ts client, just update the base URL

### Step 5: Remove From Main App

After extraction, in `apps/mouth/`:

1. Remove documents route: delete `src/app/(workspace)/documents/` directory
2. Remove document components: delete `src/components/documents/` directory
3. Remove Drive hooks: delete `src/hooks/useDrive.ts` and `src/hooks/useKeyboardNavigation.ts` (if only used by documents)
4. Remove drive logger: delete `src/lib/logging/drive-logger.ts`
5. Remove drive types: delete `src/lib/api/drive/` directory
6. Update navigation in `src/types/navigation.ts`: change Documents href to `https://drive.balizero.com`
7. Add `ExternalLink` icon indicator
8. Clean up any unused imports in package.json after removal

**WARNING:** Before deleting useKeyboardNavigation.ts, check if it's imported anywhere else. Use grep to verify.

### Step 6: Vercel Configuration

Create `apps/drive/vercel.json`:

```json
{
  "framework": "nextjs",
  "buildCommand": "next build",
  "outputDirectory": ".next"
}
```

## Design Constraints

- The Drive UI was specifically designed to look like Google Drive (blue accent #1a73e8 for selected states)
- Keep the 3-column layout: DriveSidebar (224px) | Main Content | DriveInfoPanel (320px)
- Dark theme base: bg #141416
- FULL SCREEN layout — Drive needs maximum space for file browsing
- Top bar: "Bali Zero Drive" title left, app-switcher grid right
- "Back to Kita" link top-left
- Keep ALL interactions: single click select, double click open, Cmd+click multi-select, keyboard nav, drag-drop upload

## This Is the Hardest Extraction

Drive has the most dependencies and the most complex state. Be methodical:

1. First, get the app rendering with hardcoded data
2. Then, connect the API hooks
3. Then, verify all interactions work
4. Finally, clean up the main app

## DO NOT

- Do not change the Drive UI or UX — it was specifically designed to match Google Drive
- Do not remove the virtualized file list (FileGridVirtualized.tsx) — it's there for performance
- Do not change the Google Drive API integration logic
- Do not simplify the keyboard navigation — power users depend on it
- Do not create tests
