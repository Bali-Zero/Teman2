---
paths:
  [
    "apps/mouth/**/*.{ts,tsx,js,jsx}",
    "apps/admin-dashboard/**/*.{ts,tsx}",
    "apps/webapp/**/*.{ts,tsx}",
  ]
---

# Frontend Next.js Rules

- Use App Router patterns (server components by default, `"use client"` only when needed)
- Warm Depth UI tokens: `packages/core/styles/bz-tokens.css` (`--bz-base: #0c0c0e`, `--bz-accent: #d4845a`)
- Logo component: `packages/core/components/BZLogo.tsx`
- SSO cookie: `nz_access_token` on `.balizero.com` domain
- Deploy mouth/kita from monorepo root, NOT from apps/mouth
- Use `NEXT_PUBLIC_` env vars via `git push` not `vercel --prod` for build env
- KBLI routes: `/kbli` (navigator), `/kbli/[code]` (detail, 1563 SSG), `/kbli-explorer` (AI chat)
- After deploy: mandatory QA screenshots (CLAUDE.md §13)
