# Portal Client-App (L2) PF1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden L2 Client Portal across 4 surfaces — unify duplicated login, add process timeline with drawer, rebuild vault UX with iframe PDF preview, consolidate settings into URL-synced tabs. All work is robust & infallible: Zod end-to-end, RBAC verified, error boundaries, verification-before-completion.

**Architecture:** Next.js 16 + React 19 App Router inside `apps/mouth/` monorepo workspace. 4 atomic commits in branch `pro/frontend-portal-client-app` (worktree `.worktrees/portal-client-app`). Path-relative URLs `/portal/...` valid on both `my.balizero.com` and `balizero.com/portal`. SWR for data layer with Zod parse-on-read. Radix Dialog/Tabs (already in deps). SSR redirects server-side.

**Tech Stack:** Next.js 16, React 19, TypeScript strict, Zod 3.25, SWR 2.2, Radix Dialog/Progress/ScrollArea/Select/Slot, Framer Motion 12, Lucide icons, Vitest + Testing Library, Playwright (e2e existing).

**Spec:** `docs/superpowers/specs/2026-04-18-portal-client-app-pf1-design.md`

---

## Preconditions (verify before Task 1)

- [ ] Worktree ready: `cd /Users/nuzantara/Desktop/nuzantara/.worktrees/portal-client-app && git branch --show-current` prints `pro/frontend-portal-client-app`
- [ ] Node installed: `node --version` ≥ 22
- [ ] Spec committed on `main` at `docs/superpowers/specs/2026-04-18-portal-client-app-pf1-design.md`
- [ ] Read `apps/mouth/CLAUDE.md` (RSC middleware gotcha, TypeScript band-aids, SSO cookie)
- [ ] Read top-level `CLAUDE.md` §10 Subdomains — portal = `my.balizero.com`

---

## File Structure

Files to create / modify, grouped by commit.

### Commit 1 — Login Unification

**Modify:**

- `apps/mouth/src/app/portal/login/page.tsx` — replace duplicated client page with server-side redirect (308) + open-redirect guard
- `apps/mouth/src/app/portal/login-upgraded/page.tsx` — harden error states, i18n keys, "Password dimenticata?" link

**Create:**

- `apps/mouth/src/lib/auth/sanitizeRedirect.ts` — url allowlist util (shared, no React)
- `apps/mouth/src/lib/auth/sanitizeRedirect.test.ts` — 12 adversarial cases
- `apps/mouth/src/app/portal/login/page.test.tsx` — redirect behavior
- `apps/mouth/src/i18n/portal/login.it.json` — new login error keys IT
- `apps/mouth/src/i18n/portal/login.en.json` — EN
- `apps/mouth/src/i18n/portal/login.id.json` — ID
- `apps/mouth/src/app/portal/forgot-password/page.tsx` — mailto fallback page (conditional)

### Commit 2 — Process Timeline

**Modify:**

- `apps/mouth/src/app/portal/(authenticated)/process/page.tsx` — list of active practices
- `apps/mouth/src/app/portal/(authenticated)/process/[practiceId]/page.tsx` (CREATE if absent) — detail with timeline

**Create:**

- `apps/mouth/src/lib/schemas/process.ts` — Zod `ProcessStep`, `ProcessStepsResponse`
- `apps/mouth/src/lib/schemas/process.test.ts`
- `apps/mouth/src/hooks/useProcessSteps.ts` — SWR + Zod parse
- `apps/mouth/src/hooks/useProcessSteps.test.ts`
- `apps/mouth/src/components/portal/process/ProcessTimeline.tsx`
- `apps/mouth/src/components/portal/process/TimelineStep.tsx`
- `apps/mouth/src/components/portal/process/StepDetailDrawer.tsx`
- `apps/mouth/src/components/portal/process/StateBadge.tsx`
- `apps/mouth/src/components/portal/process/BlockedStateCTA.tsx`
- `apps/mouth/src/components/portal/process/ProcessErrorBoundary.tsx`
- `apps/mouth/src/components/portal/process/TimelineSkeleton.tsx`
- `apps/mouth/src/components/portal/process/stateColors.ts`
- Tests: one `.test.tsx` sibling per component above
- `apps/mouth/src/i18n/portal/process.{it,en,id}.json`

### Commit 3 — Vault UX

**Modify:**

- `apps/mouth/src/app/portal/(authenticated)/vault/page.tsx` — layout with sidebar/grid/preview

**Create:**

- `apps/mouth/src/lib/schemas/vault.ts` — Zod
- `apps/mouth/src/lib/vault/mimeAllowlist.ts`
- `apps/mouth/src/lib/vault/sanitizeFilename.ts`
- `apps/mouth/src/lib/vault/*.test.ts` per each lib
- `apps/mouth/src/hooks/useVaultFiles.ts` — SWR list
- `apps/mouth/src/hooks/useVaultUpload.ts` — XHR upload with progress
- `apps/mouth/src/hooks/useVaultScanStatus.ts` — poll scan
- `apps/mouth/src/components/portal/vault/VaultLayout.tsx`
- `apps/mouth/src/components/portal/vault/VaultSidebar.tsx`
- `apps/mouth/src/components/portal/vault/VaultFileGrid.tsx`
- `apps/mouth/src/components/portal/vault/VaultPreviewPane.tsx`
- `apps/mouth/src/components/portal/vault/VaultUploadZone.tsx`
- `apps/mouth/src/components/portal/vault/VaultSearchBar.tsx`
- `apps/mouth/src/components/portal/vault/VaultErrorBoundary.tsx`
- Tests per component
- `apps/mouth/src/i18n/portal/vault.{it,en,id}.json`

### Commit 4 — Settings Tabs

**Modify:**

- `apps/mouth/src/app/portal/(authenticated)/settings/page.tsx` — host `<SettingsTabs>`

**Create:**

- `apps/mouth/src/lib/schemas/settings.ts` — Zod UserProfile, notification matrix
- `apps/mouth/src/hooks/useMe.ts`
- `apps/mouth/src/hooks/usePasswordChange.ts`
- `apps/mouth/src/hooks/use2FA.ts` (conditional on BE)
- `apps/mouth/src/hooks/useSessions.ts` (conditional on BE)
- `apps/mouth/src/hooks/useNotificationPrefs.ts`
- `apps/mouth/src/hooks/useLanguage.ts`
- `apps/mouth/src/components/portal/settings/SettingsTabs.tsx`
- `apps/mouth/src/components/portal/settings/AccountSettings.tsx`
- `apps/mouth/src/components/portal/settings/SecuritySettings.tsx`
- `apps/mouth/src/components/portal/settings/NotificationSettings.tsx`
- `apps/mouth/src/components/portal/settings/PrivacySettings.tsx`
- `apps/mouth/src/components/portal/settings/LanguageSettings.tsx`
- `apps/mouth/src/components/portal/settings/PasswordChangeForm.tsx`
- `apps/mouth/src/components/portal/settings/PasswordStrengthMeter.tsx`
- `apps/mouth/src/components/portal/settings/TwoFactorPanel.tsx` (conditional)
- `apps/mouth/src/components/portal/settings/SessionsPanel.tsx` (conditional)
- Tests per component
- `apps/mouth/src/i18n/portal/settings.{it,en,id}.json`

---

## Task 0: Bootstrap worktree

**Files:** none (environment setup only)

- [ ] **Step 1:** Install deps

Run: `cd /Users/nuzantara/Desktop/nuzantara/.worktrees/portal-client-app/apps/mouth && npm install`
Expected: exit 0, `node_modules/` populated.

- [ ] **Step 2:** Verify build baseline

Run: `npx tsc --noEmit`
Expected: exit 0 (no TypeScript errors introduced by baseline).
If errors exist on main (known baseline drift), record count and do NOT let the count increase in later tasks.

- [ ] **Step 3:** Verify test baseline

Run: `npm test -- --run`
Expected: existing tests pass (count them, call this N). Later tasks add tests — must NEVER let baseline tests regress.

- [ ] **Step 4:** Dev server smoke test

Run: `npm run dev` (background, `&`) then `curl -sI http://localhost:3000/portal/login | head -1`
Expected: `200 OK` or `307` redirect. Kill dev server after.

- [ ] **Step 5:** Audit checklist (from spec §1) — execute all 5 grep audits

Run each command, record result in a scratch file `audit-notes.md` (NOT committed, for your own use):

```bash
# 1.1 Login
grep -rn '/portal/login' apps/mouth/src apps/kita 2>/dev/null | head -20
grep -rn 'password-reset\|password_reset\|forgot-password\|forgotPassword' apps/backend-rag/backend/app/routers 2>/dev/null | head -10

# 1.2 Process
ls apps/mouth/src/app/portal/\(authenticated\)/process/
grep -rn 'practice.*step\|practice_step' apps/backend-rag/backend/app/routers 2>/dev/null | head -10
grep -rn 'PracticeState\|practice_state\|PracticeStatus' apps/backend-rag/backend/services 2>/dev/null | head -10
grep -E '^\s*--bz-(danger|warning|success)' packages/core/styles/bz-tokens.css 2>/dev/null || echo "NO SEMANTIC TOKENS"

# 1.3 Vault
grep -rn 'portal.*vault\|portal.*documents' apps/backend-rag/backend/app/routers 2>/dev/null | head -10
grep -rn 'scan_status\|clamav\|virus' apps/backend-rag/backend 2>/dev/null | head -10

# 1.4 Settings
grep -rn 'portal.*me\|portal_me\|/me/password\|2fa\|totp' apps/backend-rag/backend/app/routers 2>/dev/null | head -20
```

For each endpoint NOT found, the relevant task's commit is documented with: "BE endpoint missing → using placeholder + issue."

- [ ] **Step 6:** Record findings

Create `/tmp/pf1-audit.md` with a one-line verdict per sub-check (exists / missing). This drives which tasks are full-fat vs placeholder-mode.

---

# COMMIT 1 — Login Unification

## Task 1.1: sanitizeRedirect utility (TDD)

**Files:**

- Create: `apps/mouth/src/lib/auth/sanitizeRedirect.ts`
- Test: `apps/mouth/src/lib/auth/sanitizeRedirect.test.ts`

- [ ] **Step 1: Write failing tests**

```ts
// apps/mouth/src/lib/auth/sanitizeRedirect.test.ts
import { describe, it, expect } from "vitest";
import { sanitizeRedirect } from "./sanitizeRedirect";

describe("sanitizeRedirect", () => {
  it("returns null for undefined", () => {
    expect(sanitizeRedirect(undefined)).toBeNull();
  });
  it("returns null for empty string", () => {
    expect(sanitizeRedirect("")).toBeNull();
  });
  it("blocks protocol-relative //evil.com", () => {
    expect(sanitizeRedirect("//evil.com/steal")).toBeNull();
  });
  it("blocks absolute http://", () => {
    expect(sanitizeRedirect("http://evil.com")).toBeNull();
  });
  it("blocks absolute https://", () => {
    expect(sanitizeRedirect("https://evil.com")).toBeNull();
  });
  it("blocks javascript:", () => {
    expect(sanitizeRedirect("javascript:alert(1)")).toBeNull();
  });
  it("blocks data:", () => {
    expect(sanitizeRedirect("data:text/html,<script>")).toBeNull();
  });
  it("blocks backslash tricks", () => {
    expect(sanitizeRedirect("/portal\\evil")).toBeNull();
  });
  it("blocks relative without leading slash", () => {
    expect(sanitizeRedirect("portal/dashboard")).toBeNull();
  });
  it("blocks non-allowlisted prefix", () => {
    expect(sanitizeRedirect("/admin/console")).toBeNull();
  });
  it("allows /portal/dashboard", () => {
    expect(sanitizeRedirect("/portal/dashboard")).toBe("/portal/dashboard");
  });
  it("allows /portal/ root", () => {
    expect(sanitizeRedirect("/portal/")).toBe("/portal/");
  });
  it("allows /workspace/anything", () => {
    expect(sanitizeRedirect("/workspace/kita")).toBe("/workspace/kita");
  });
  it("blocks path traversal ../", () => {
    expect(sanitizeRedirect("/portal/../admin")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test — expect failure**

Run: `cd apps/mouth && npm test -- --run src/lib/auth/sanitizeRedirect.test.ts`
Expected: all 14 tests FAIL with "Cannot find module" or "sanitizeRedirect is not a function".

- [ ] **Step 3: Implement**

```ts
// apps/mouth/src/lib/auth/sanitizeRedirect.ts
const ALLOWED_PREFIXES = ["/portal/", "/workspace/"] as const;

export function sanitizeRedirect(
  raw: string | undefined | null,
): string | null {
  if (!raw) return null;
  if (raw.includes("\\")) return null;
  if (raw.startsWith("//")) return null;
  if (/^[a-z][a-z0-9+.\-]*:/i.test(raw)) return null; // any scheme
  if (!raw.startsWith("/")) return null;
  if (raw.includes("/../") || raw.endsWith("/..")) return null;
  if (
    !ALLOWED_PREFIXES.some((p) => raw.startsWith(p) || raw === p.slice(0, -1))
  ) {
    return null;
  }
  return raw;
}
```

- [ ] **Step 4: Run — expect pass**

Run: `npm test -- --run src/lib/auth/sanitizeRedirect.test.ts`
Expected: 14 passing.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/lib/auth/sanitizeRedirect.ts apps/mouth/src/lib/auth/sanitizeRedirect.test.ts
git commit -m "feat(portal): sanitizeRedirect util — open-redirect guard"
```

## Task 1.2: Replace /portal/login/page.tsx with server redirect

**Files:**

- Modify: `apps/mouth/src/app/portal/login/page.tsx` (full rewrite)
- Test: `apps/mouth/src/app/portal/login/page.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// apps/mouth/src/app/portal/login/page.test.tsx
import { describe, it, expect, vi } from "vitest";

vi.mock("next/navigation", () => ({
  permanentRedirect: vi.fn((url: string) => {
    throw new Error(`REDIRECT:${url}`);
  }),
}));

import LegacyLoginRedirect from "./page";

describe("LegacyLoginRedirect", () => {
  it("redirects to /portal/login-upgraded without redirect param", () => {
    expect(() => LegacyLoginRedirect({ searchParams: {} })).toThrow(
      "REDIRECT:/portal/login-upgraded",
    );
  });
  it("preserves safe redirect param", () => {
    expect(() =>
      LegacyLoginRedirect({ searchParams: { redirect: "/portal/dashboard" } }),
    ).toThrow("REDIRECT:/portal/login-upgraded?redirect=%2Fportal%2Fdashboard");
  });
  it("strips unsafe redirect param", () => {
    expect(() =>
      LegacyLoginRedirect({ searchParams: { redirect: "//evil.com" } }),
    ).toThrow("REDIRECT:/portal/login-upgraded");
  });
});
```

- [ ] **Step 2: Run test — expect failure**

Run: `npm test -- --run src/app/portal/login/page.test.tsx`
Expected: FAIL (current page is client component, throws on direct call).

- [ ] **Step 3: Replace page**

```tsx
// apps/mouth/src/app/portal/login/page.tsx
import { permanentRedirect } from "next/navigation";
import { sanitizeRedirect } from "@/lib/auth/sanitizeRedirect";

interface Props {
  searchParams: { redirect?: string };
}

export default function LegacyLoginRedirect({ searchParams }: Props) {
  const safe = sanitizeRedirect(searchParams.redirect);
  const qs = safe ? `?redirect=${encodeURIComponent(safe)}` : "";
  permanentRedirect(`/portal/login-upgraded${qs}`);
}
```

- [ ] **Step 4: Run — expect pass**

Run: `npm test -- --run src/app/portal/login/page.test.tsx`
Expected: 3 passing.

- [ ] **Step 5: Manual smoke**

Run in background: `npm run dev`
Then: `curl -sI 'http://localhost:3000/portal/login?redirect=/portal/dashboard' | head -3`
Expected: `HTTP/1.1 308 Permanent Redirect` with `location: /portal/login-upgraded?redirect=%2Fportal%2Fdashboard`
Also check unsafe: `curl -sI 'http://localhost:3000/portal/login?redirect=//evil.com' | head -3`
Expected: redirect but NO `redirect=` in location (stripped).
Kill dev server.

- [ ] **Step 6: Commit**

```bash
git add apps/mouth/src/app/portal/login/page.tsx apps/mouth/src/app/portal/login/page.test.tsx
git commit -m "feat(portal): /portal/login 308 redirect to login-upgraded with open-redirect guard"
```

## Task 1.3: i18n keys for login errors

**Files:**

- Create: `apps/mouth/src/i18n/portal/login.it.json`
- Create: `apps/mouth/src/i18n/portal/login.en.json`
- Create: `apps/mouth/src/i18n/portal/login.id.json`

- [ ] **Step 1: Determine i18n pattern**

Run: `grep -rn 'useTranslation\|i18next\|next-intl\|createTranslator' apps/mouth/src 2>/dev/null | head -10`

Based on result, adapt naming/loader. If NO i18n lib exists (likely given deps), we use the simpler pattern: flat JSON files consumed via `import` + lookup helper.

- [ ] **Step 2: Create IT file**

```json
// apps/mouth/src/i18n/portal/login.it.json
{
  "errors": {
    "invalid_credentials": "Email o PIN non corretti. Riprova.",
    "account_locked": "Account bloccato per sicurezza. Contatta team@balizero.com.",
    "rate_limited": "Troppi tentativi. Riprova tra {seconds} secondi.",
    "invalid_2fa": "Codice 2FA non valido.",
    "network_error": "Connessione persa. Verifica la rete e riprova.",
    "email_not_found": "Email non trovata.",
    "server_error": "Errore del server. Riprova tra qualche minuto.",
    "maintenance": "Manutenzione in corso. Torna più tardi."
  },
  "forgot_password": "PIN dimenticato?",
  "forgot_password_page": {
    "title": "Recupera accesso",
    "sent": "Abbiamo ricevuto la tua richiesta. Il team ti contatterà."
  }
}
```

- [ ] **Step 3: Create EN**

```json
// apps/mouth/src/i18n/portal/login.en.json
{
  "errors": {
    "invalid_credentials": "Wrong email or PIN. Please try again.",
    "account_locked": "Account locked for security. Contact team@balizero.com.",
    "rate_limited": "Too many attempts. Retry in {seconds} seconds.",
    "invalid_2fa": "Invalid 2FA code.",
    "network_error": "Connection lost. Check your network and retry.",
    "email_not_found": "Email not found.",
    "server_error": "Server error. Retry in a few minutes.",
    "maintenance": "Maintenance in progress. Please return later."
  },
  "forgot_password": "Forgot PIN?",
  "forgot_password_page": {
    "title": "Recover access",
    "sent": "We received your request. Our team will contact you."
  }
}
```

- [ ] **Step 4: Create ID**

```json
// apps/mouth/src/i18n/portal/login.id.json
{
  "errors": {
    "invalid_credentials": "Email atau PIN salah. Silakan coba lagi.",
    "account_locked": "Akun dikunci untuk keamanan. Hubungi team@balizero.com.",
    "rate_limited": "Terlalu banyak percobaan. Coba lagi dalam {seconds} detik.",
    "invalid_2fa": "Kode 2FA tidak valid.",
    "network_error": "Koneksi terputus. Periksa jaringan dan coba lagi.",
    "email_not_found": "Email tidak ditemukan.",
    "server_error": "Kesalahan server. Coba lagi dalam beberapa menit.",
    "maintenance": "Sedang dalam pemeliharaan. Silakan kembali nanti."
  },
  "forgot_password": "Lupa PIN?",
  "forgot_password_page": {
    "title": "Pemulihan akses",
    "sent": "Kami telah menerima permintaan Anda. Tim akan menghubungi Anda."
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/i18n/portal/login.it.json apps/mouth/src/i18n/portal/login.en.json apps/mouth/src/i18n/portal/login.id.json
git commit -m "feat(portal): login error i18n keys IT/EN/ID"
```

## Task 1.4: Harden login-upgraded error states

**Files:**

- Modify: `apps/mouth/src/app/portal/login-upgraded/page.tsx`

Minimal targeted change: map backend error codes to i18n keys; parse `Retry-After`; add "Forgot PIN?" link.

- [ ] **Step 1: Read current file** (already done in bootstrap, but confirm line numbers for edits)

- [ ] **Step 2: Add error-code mapping**

Insert after `ERROR_RESET_DELAY_MS`:

```tsx
// Error code → i18n key lookup
import loginIT from "@/i18n/portal/login.it.json";
const L = loginIT; // TODO: hook to user language when i18n infra lands

function errorKeyFor(status: number): string {
  switch (status) {
    case 401:
      return L.errors.invalid_credentials;
    case 403:
      return L.errors.account_locked;
    case 404:
      return L.errors.email_not_found;
    case 422:
      return L.errors.invalid_2fa;
    case 429:
      return L.errors.rate_limited;
    case 503:
      return L.errors.maintenance;
    default:
      return status >= 500 ? L.errors.server_error : L.errors.network_error;
  }
}
```

- [ ] **Step 3: Replace catch block in `handleLogin`**

Find the `catch (error) { ... }` block (around line 87-103). Extract status from error; compute error message; display via new state field `errorMessage`. Amend `ACCESS DENIED OVERLAY` to show `errorMessage` if set.

Concrete diff (applied against current file):

- Add state: `const [errorMessage, setErrorMessage] = useState<string>('');`
- In catch:
  ```ts
  const status =
    (error as { status?: number; response?: { status?: number } })?.response
      ?.status ??
    (error as { status?: number })?.status ??
    0;
  setErrorMessage(errorKeyFor(status));
  ```
- Amend overlay denied:

  ```tsx
  <h1 className="...">Access Denied</h1>;
  {
    errorMessage && <p className="...">{errorMessage}</p>;
  }
  ```

- [ ] **Step 4: Add "Forgot PIN?" link**

Inside `.motion.form key="pin-step"`, near the "← {email.split("@")[0]}" back button, add:

```tsx
<a
  href="/portal/forgot-password"
  className="text-[11px] text-accent-gold-muted/50 hover:text-accent-gold-muted transition-colors"
>
  {L.forgot_password}
</a>
```

- [ ] **Step 5: Run typecheck + test**

Run: `cd apps/mouth && npx tsc --noEmit && npm test -- --run`
Expected: no new errors / regressions.

- [ ] **Step 6: Manual smoke**

Dev server, navigate to `/portal/login-upgraded`, check "Forgot PIN?" link appears in pin step. Simulate failed login (bad pin) and verify error text shows localized message.

- [ ] **Step 7: Commit**

```bash
git add apps/mouth/src/app/portal/login-upgraded/page.tsx
git commit -m "feat(portal): harden login-upgraded error mapping + Forgot PIN link"
```

## Task 1.5: Forgot password page (mailto fallback)

**Rationale:** Audit step 0.5 determines whether BE supports password reset. This plan assumes **mailto fallback** (most robust and ships regardless). If BE endpoints exist, replace mailto CTA with a proper form in a follow-up commit.

**Files:**

- Create: `apps/mouth/src/app/portal/forgot-password/page.tsx`

- [ ] **Step 1: Implement**

```tsx
// apps/mouth/src/app/portal/forgot-password/page.tsx
import Link from "next/link";
import loginIT from "@/i18n/portal/login.it.json";

const L = loginIT.forgot_password_page;

export const metadata = { title: "Forgot PIN — Bali Zero Portal" };

export default function ForgotPasswordPage() {
  const subject = encodeURIComponent("Portal Access Recovery");
  const body = encodeURIComponent(
    "Hi, I need help recovering access to my Bali Zero client portal.\n\nRegistered email: ",
  );
  const mailto = `mailto:team@balizero.com?subject=${subject}&body=${body}`;
  return (
    <main className="min-h-screen bg-black text-[#f0ece4] flex items-center justify-center px-6">
      <div className="max-w-md w-full">
        <h1 className="text-3xl font-light mb-4">{L.title}</h1>
        <p className="text-sm text-[#c9a96e]/70 mb-6">
          Per motivi di sicurezza, il recupero PIN viene gestito manualmente dal
          nostro team.
        </p>
        <a
          href={mailto}
          className="block w-full text-center py-4 rounded-xl bg-gradient-to-br from-[#d9bd7a] to-[#a07838] text-black font-bold uppercase tracking-[0.08em]"
        >
          Scrivi al team
        </a>
        <Link
          href="/portal/login-upgraded"
          className="block mt-6 text-center text-xs text-[#c9a96e]/60 hover:text-[#c9a96e] uppercase tracking-[2px]"
        >
          ← Torna al login
        </Link>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Verify**

Run: `npm run dev` then `curl -sI http://localhost:3000/portal/forgot-password | head -1`
Expected: `200 OK`.

- [ ] **Step 3: Commit (finalize commit 1)**

```bash
git add apps/mouth/src/app/portal/forgot-password/page.tsx
git commit -m "feat(portal): /portal/forgot-password mailto fallback"
```

- [ ] **Step 4: Squash OR keep atomic**

Commits 1.1-1.5 are already atomic-at-concern-level. Push as-is or squash with:

```bash
git reset --soft HEAD~5
git commit -m "feat(portal): unify login — 308 legacy redirect with open-redirect guard, harden error states i18n, forgot-password flow"
```

Prefer keeping unsquashed for rollback granularity per spec §0.2.

---

# COMMIT 2 — Process Timeline

## Task 2.1: Zod schemas for process

**Files:**

- Create: `apps/mouth/src/lib/schemas/process.ts`
- Test: `apps/mouth/src/lib/schemas/process.test.ts`

- [ ] **Step 1: Write schemas**

```ts
// apps/mouth/src/lib/schemas/process.ts
import { z } from "zod";

export const ProcessStepState = z.enum([
  "pending",
  "in_progress",
  "blocked",
  "waiting_client",
  "completed",
]);
export type ProcessStepState = z.infer<typeof ProcessStepState>;

export const AssignedTeamMember = z.object({
  id: z.string(),
  name: z.string(),
  avatar_url: z.string().url().nullable(),
  role: z.string().nullable(),
});
export type AssignedTeamMember = z.infer<typeof AssignedTeamMember>;

export const WaitingDoc = z.object({
  doc_type: z.string(),
  uploaded: z.boolean(),
  vault_file_id: z.string().nullable(),
});

export const ProcessStep = z.object({
  id: z.string(),
  practice_id: z.string(),
  title: z.string(),
  description: z.string().nullable(),
  state: ProcessStepState,
  assigned_to: AssignedTeamMember.nullable(),
  waiting_for: z.array(WaitingDoc).default([]),
  estimated_completion: z.string().datetime().nullable(),
  blocked_reason: z.string().nullable(),
  order: z.number().int(),
});
export type ProcessStep = z.infer<typeof ProcessStep>;

export const ProcessStepsResponse = z.object({
  version: z.literal(1),
  practice_id: z.string(),
  steps: z.array(ProcessStep),
});
export type ProcessStepsResponse = z.infer<typeof ProcessStepsResponse>;
```

- [ ] **Step 2: Write tests**

```ts
// apps/mouth/src/lib/schemas/process.test.ts
import { describe, it, expect } from "vitest";
import { ProcessStepsResponse, ProcessStep, ProcessStepState } from "./process";

const validStep = {
  id: "s1",
  practice_id: "p1",
  title: "Raccolta documenti",
  description: null,
  state: "pending",
  assigned_to: null,
  waiting_for: [],
  estimated_completion: null,
  blocked_reason: null,
  order: 1,
};

describe("ProcessStepsResponse", () => {
  it("parses minimal valid response", () => {
    const out = ProcessStepsResponse.parse({
      version: 1,
      practice_id: "p1",
      steps: [validStep],
    });
    expect(out.steps).toHaveLength(1);
  });
  it("rejects unknown state", () => {
    expect(() =>
      ProcessStep.parse({ ...validStep, state: "unknown" }),
    ).toThrow();
  });
  it("defaults waiting_for to []", () => {
    const { waiting_for, ...rest } = validStep;
    const parsed = ProcessStep.parse(rest);
    expect(parsed.waiting_for).toEqual([]);
  });
  it("rejects version != 1", () => {
    expect(() =>
      ProcessStepsResponse.parse({ version: 2, practice_id: "p1", steps: [] }),
    ).toThrow();
  });
  it("rejects non-int order", () => {
    expect(() => ProcessStep.parse({ ...validStep, order: 1.5 })).toThrow();
  });
});

describe("ProcessStepState", () => {
  it("has all 5 states", () => {
    expect(ProcessStepState.options).toEqual([
      "pending",
      "in_progress",
      "blocked",
      "waiting_client",
      "completed",
    ]);
  });
});
```

- [ ] **Step 3: Run — expect pass after create**

```bash
npm test -- --run src/lib/schemas/process.test.ts
```

Expected: 6 passing.

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/lib/schemas/process.ts apps/mouth/src/lib/schemas/process.test.ts
git commit -m "feat(portal): Zod schemas for process steps"
```

## Task 2.2: stateColors constants

**Files:**

- Create: `apps/mouth/src/components/portal/process/stateColors.ts`
- Test: `apps/mouth/src/components/portal/process/stateColors.test.ts`

- [ ] **Step 1: Test**

```ts
// apps/mouth/src/components/portal/process/stateColors.test.ts
import { describe, it, expect } from "vitest";
import { STATE_COLORS } from "./stateColors";
import { ProcessStepState } from "@/lib/schemas/process";

describe("STATE_COLORS", () => {
  it("has entry for every state", () => {
    for (const state of ProcessStepState.options) {
      expect(STATE_COLORS[state]).toBeDefined();
      expect(STATE_COLORS[state].fg).toBeTruthy();
    }
  });
});
```

- [ ] **Step 2: Implement**

```ts
// apps/mouth/src/components/portal/process/stateColors.ts
// TODO(shared-tokens): move to packages/core/styles/bz-tokens.css when --bz-danger|warning|success land
import type { ProcessStepState } from "@/lib/schemas/process";

export interface StateStyle {
  bg: string;
  fg: string;
  border: string;
}

export const STATE_COLORS: Record<ProcessStepState, StateStyle> = {
  pending: {
    bg: "var(--bz-muted-bg, rgba(138,138,142,0.12))",
    fg: "var(--bz-muted-fg, #8a8a8e)",
    border: "var(--bz-muted-fg, #8a8a8e)",
  },
  in_progress: {
    bg: "var(--bz-accent-bg, rgba(212,132,90,0.15))",
    fg: "var(--bz-accent, #d4845a)",
    border: "var(--bz-accent, #d4845a)",
  },
  blocked: {
    bg: "var(--bz-danger-bg, rgba(201,74,74,0.15))",
    fg: "var(--bz-danger, #c94a4a)",
    border: "var(--bz-danger, #c94a4a)",
  },
  waiting_client: {
    bg: "var(--bz-warning-bg, rgba(201,161,74,0.15))",
    fg: "var(--bz-warning, #c9a14a)",
    border: "var(--bz-warning, #c9a14a)",
  },
  completed: {
    bg: "var(--bz-success-bg, rgba(74,156,92,0.15))",
    fg: "var(--bz-success, #4a9c5c)",
    border: "var(--bz-success, #4a9c5c)",
  },
};
```

- [ ] **Step 3: Run, commit**

```bash
npm test -- --run src/components/portal/process/stateColors.test.ts
git add apps/mouth/src/components/portal/process/stateColors.ts apps/mouth/src/components/portal/process/stateColors.test.ts
git commit -m "feat(portal): state colors constants with token fallback"
```

## Task 2.3: StateBadge component

**Files:**

- Create: `apps/mouth/src/components/portal/process/StateBadge.tsx`
- Test: `apps/mouth/src/components/portal/process/StateBadge.test.tsx`

- [ ] **Step 1: Test**

```tsx
// apps/mouth/src/components/portal/process/StateBadge.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StateBadge } from "./StateBadge";

describe("StateBadge", () => {
  it("renders label for pending", () => {
    render(<StateBadge state="pending" />);
    expect(screen.getByText(/pending/i)).toBeInTheDocument();
  });
  it("uses aria-label for sr", () => {
    const { container } = render(<StateBadge state="blocked" />);
    const el = container.querySelector("[aria-label]");
    expect(el?.getAttribute("aria-label")).toMatch(/blocked/i);
  });
  it("applies state color via style", () => {
    const { container } = render(<StateBadge state="completed" />);
    const el = container.firstChild as HTMLElement;
    expect(el.style.color).toBeTruthy();
  });
});
```

- [ ] **Step 2: Implement**

```tsx
// apps/mouth/src/components/portal/process/StateBadge.tsx
import type { ProcessStepState } from "@/lib/schemas/process";
import { STATE_COLORS } from "./stateColors";

const LABELS: Record<ProcessStepState, string> = {
  pending: "Pending",
  in_progress: "In progress",
  blocked: "Blocked",
  waiting_client: "Waiting for you",
  completed: "Completed",
};

export function StateBadge({ state }: { state: ProcessStepState }) {
  const c = STATE_COLORS[state];
  const label = LABELS[state];
  return (
    <span
      aria-label={`Status: ${label}`}
      style={{ backgroundColor: c.bg, color: c.fg, borderColor: c.border }}
      className="inline-flex items-center px-2.5 py-1 rounded-full border text-xs font-medium"
    >
      {label}
    </span>
  );
}
```

- [ ] **Step 3: Run, commit**

```bash
npm test -- --run src/components/portal/process/StateBadge.test.tsx
git add apps/mouth/src/components/portal/process
git commit -m "feat(portal): StateBadge component"
```

## Task 2.4: useProcessSteps hook

**Files:**

- Create: `apps/mouth/src/hooks/useProcessSteps.ts`
- Test: `apps/mouth/src/hooks/useProcessSteps.test.ts`

- [ ] **Step 1: Determine API client pattern**

Run: `grep -rn "export const api\|export.*api =" apps/mouth/src/lib/api.ts apps/mouth/src/lib/api/ 2>/dev/null | head -5`
Locate how `api.get` / `api.login` work (login-upgraded uses `api.login`). Hook uses same pattern.

- [ ] **Step 2: Write test**

```ts
// apps/mouth/src/hooks/useProcessSteps.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { SWRConfig } from 'swr';
import React from 'react';
import { useProcessSteps } from './useProcessSteps';

vi.mock('@/lib/api', () => ({
  api: { get: vi.fn() },
}));

import { api } from '@/lib/api';

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>{children}</SWRConfig>
);

const validResp = {
  data: {
    version: 1,
    practice_id: 'p1',
    steps: [{
      id: 's1', practice_id: 'p1', title: 'Raccolta', description: null,
      state: 'pending', assigned_to: null, waiting_for: [],
      estimated_completion: null, blocked_reason: null, order: 1,
    }],
  },
};

describe('useProcessSteps', () => {
  beforeEach(() => { vi.mocked(api.get).mockReset(); });

  it('returns parsed data on success', async () => {
    vi.mocked(api.get).mockResolvedValue(validResp);
    const { result } = renderHook(() => useProcessSteps('p1'), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.steps).toHaveLength(1);
  });

  it('surfaces schema drift as error', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { version: 99, steps: [] } });
    const { result } = renderHook(() => useProcessSteps('p1'), { wrapper });
    await waitFor(() => expect(result.current.error).toBeTruthy());
  });

  it('does not fetch when practiceId empty', () => {
    const { result } = renderHook(() => useProcessSteps(''), { wrapper });
    expect(result.current.data).toBeUndefined();
    expect(api.get).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Implement**

```ts
// apps/mouth/src/hooks/useProcessSteps.ts
"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import { ProcessStepsResponse } from "@/lib/schemas/process";

export function useProcessSteps(practiceId: string) {
  return useSWR(
    practiceId ? ["portal-process-steps", practiceId] : null,
    async () => {
      const res = await api.get(`/api/portal/practices/${practiceId}/steps`);
      return ProcessStepsResponse.parse(res.data);
    },
    {
      revalidateOnFocus: true,
      dedupingInterval: 2000,
      shouldRetryOnError: (err: { status?: number }) =>
        (err?.status ?? 0) >= 500,
    },
  );
}
```

- [ ] **Step 4: Run, commit**

```bash
npm test -- --run src/hooks/useProcessSteps.test.ts
git add apps/mouth/src/hooks/useProcessSteps.ts apps/mouth/src/hooks/useProcessSteps.test.ts
git commit -m "feat(portal): useProcessSteps SWR hook with Zod parse"
```

## Task 2.5: TimelineStep + ProcessTimeline + Skeleton

**Files:**

- Create: `apps/mouth/src/components/portal/process/TimelineStep.tsx`
- Create: `apps/mouth/src/components/portal/process/ProcessTimeline.tsx`
- Create: `apps/mouth/src/components/portal/process/TimelineSkeleton.tsx`
- Tests: sibling `.test.tsx` each

- [ ] **Step 1: TimelineStep**

```tsx
// apps/mouth/src/components/portal/process/TimelineStep.tsx
"use client";
import type { ProcessStep } from "@/lib/schemas/process";
import { StateBadge } from "./StateBadge";
import { STATE_COLORS } from "./stateColors";

interface Props {
  step: ProcessStep;
  onSelect: (step: ProcessStep) => void;
  isLast: boolean;
}

export function TimelineStep({ step, onSelect, isLast }: Props) {
  const c = STATE_COLORS[step.state];
  return (
    <li className="relative flex gap-4">
      <div className="flex flex-col items-center">
        <span
          aria-hidden
          className="w-3 h-3 rounded-full border-2 bg-black"
          style={{ borderColor: c.border }}
        />
        {!isLast && <span className="flex-1 w-px bg-white/10 my-1" />}
      </div>
      <button
        type="button"
        onClick={() => onSelect(step)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelect(step);
          }
        }}
        className="flex-1 text-left pb-6 rounded-md focus:outline-none focus:ring-2 focus:ring-[#c9a96e]"
      >
        <div className="flex items-center gap-3 mb-1">
          <h3 className="text-sm font-medium text-[#f0ece4]">{step.title}</h3>
          <StateBadge state={step.state} />
        </div>
        {step.assigned_to && (
          <p className="text-xs text-[#c9a96e]/70">
            Assigned: {step.assigned_to.name}
          </p>
        )}
        {step.waiting_for.length > 0 && (
          <p className="text-xs text-[#c9a96e]/50 mt-1">
            {step.waiting_for.filter((w) => !w.uploaded).length} document(s)
            pending
          </p>
        )}
      </button>
    </li>
  );
}
```

Tests: click fires onSelect, keyboard Enter fires onSelect, aria visible, state badge rendered.

- [ ] **Step 2: ProcessTimeline**

```tsx
// apps/mouth/src/components/portal/process/ProcessTimeline.tsx
"use client";
import type { ProcessStep } from "@/lib/schemas/process";
import { TimelineStep } from "./TimelineStep";

interface Props {
  steps: ProcessStep[];
  onSelect: (step: ProcessStep) => void;
}

export function ProcessTimeline({ steps, onSelect }: Props) {
  if (steps.length === 0) {
    return (
      <p className="text-sm text-[#c9a96e]/60 py-8 text-center">
        Questa pratica non ha ancora step. Il team li creerà a breve.
      </p>
    );
  }
  const ordered = [...steps].sort((a, b) => a.order - b.order);
  return (
    <ol className="list-none p-0 m-0">
      {ordered.map((step, i) => (
        <TimelineStep
          key={step.id}
          step={step}
          onSelect={onSelect}
          isLast={i === ordered.length - 1}
        />
      ))}
    </ol>
  );
}
```

Tests: empty array renders empty state, steps sorted by `order`, onSelect prop propagates.

- [ ] **Step 3: TimelineSkeleton**

```tsx
// apps/mouth/src/components/portal/process/TimelineSkeleton.tsx
export function TimelineSkeleton({ count = 3 }: { count?: number }) {
  return (
    <ul aria-label="Loading timeline" className="list-none p-0 m-0">
      {Array.from({ length: count }).map((_, i) => (
        <li key={i} className="flex gap-4 pb-6">
          <div className="flex flex-col items-center">
            <span className="w-3 h-3 rounded-full bg-white/10 animate-pulse" />
            {i < count - 1 && <span className="flex-1 w-px bg-white/5 my-1" />}
          </div>
          <div className="flex-1 space-y-2">
            <div className="h-4 w-1/2 bg-white/10 animate-pulse rounded" />
            <div className="h-3 w-1/3 bg-white/5 animate-pulse rounded" />
          </div>
        </li>
      ))}
    </ul>
  );
}
```

Test: renders `count` items, aria-label present.

- [ ] **Step 4: Run all, commit**

```bash
npm test -- --run src/components/portal/process/
git add apps/mouth/src/components/portal/process
git commit -m "feat(portal): TimelineStep + ProcessTimeline + Skeleton"
```

## Task 2.6: StepDetailDrawer (Radix Dialog)

**Files:**

- Create: `apps/mouth/src/components/portal/process/StepDetailDrawer.tsx`
- Test: sibling `.test.tsx`

- [ ] **Step 1: Test**

```tsx
// StepDetailDrawer.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StepDetailDrawer } from "./StepDetailDrawer";

const step = {
  id: "s1",
  practice_id: "p1",
  title: "Raccolta",
  description: "lorem",
  state: "blocked" as const,
  assigned_to: null,
  waiting_for: [],
  estimated_completion: null,
  blocked_reason: "missing NPWP",
  order: 1,
};

describe("StepDetailDrawer", () => {
  it("renders when open", () => {
    render(<StepDetailDrawer step={step} open={true} onClose={() => {}} />);
    expect(screen.getByText(/Raccolta/)).toBeInTheDocument();
  });
  it("shows blocked reason", () => {
    render(<StepDetailDrawer step={step} open={true} onClose={() => {}} />);
    expect(screen.getByText(/missing NPWP/)).toBeInTheDocument();
  });
  it("calls onClose on ESC", async () => {
    const onClose = vi.fn();
    render(<StepDetailDrawer step={step} open={true} onClose={onClose} />);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Implement**

```tsx
// StepDetailDrawer.tsx
"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ProcessStep } from "@/lib/schemas/process";
import { StateBadge } from "./StateBadge";

interface Props {
  step: ProcessStep | null;
  open: boolean;
  onClose: () => void;
}

export function StepDetailDrawer({ step, open, onClose }: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 data-[state=open]:animate-in data-[state=closed]:animate-out" />
        <Dialog.Content
          aria-describedby={step?.description ? "step-desc" : undefined}
          className="fixed right-0 top-0 bottom-0 w-full max-w-[480px] bg-[#0a0804] border-l border-[#c9a96e]/20 z-50 overflow-y-auto"
        >
          <div className="p-6 flex items-center justify-between border-b border-[#c9a96e]/10">
            <Dialog.Title className="text-lg font-medium text-[#f0ece4]">
              {step?.title ?? "—"}
            </Dialog.Title>
            <Dialog.Close
              className="p-2 rounded hover:bg-white/5"
              aria-label="Close"
            >
              <X className="w-5 h-5" />
            </Dialog.Close>
          </div>
          {step && (
            <div className="p-6 space-y-4">
              <StateBadge state={step.state} />
              {step.description && (
                <p id="step-desc" className="text-sm text-[#c9a96e]/80">
                  {step.description}
                </p>
              )}
              {step.blocked_reason && (
                <div className="rounded-lg p-4 border border-[#c94a4a]/40 bg-[#c94a4a]/10">
                  <p className="text-sm text-[#c94a4a]">
                    Blocked: {step.blocked_reason}
                  </p>
                </div>
              )}
              {step.assigned_to && (
                <p className="text-xs text-[#c9a96e]/60">
                  Assigned to {step.assigned_to.name}
                  {step.assigned_to.role && ` · ${step.assigned_to.role}`}
                </p>
              )}
              {step.waiting_for.length > 0 && (
                <div>
                  <h4 className="text-xs uppercase tracking-[2px] text-[#c9a96e]/50 mb-2">
                    Documents
                  </h4>
                  <ul className="space-y-1">
                    {step.waiting_for.map((w, i) => (
                      <li
                        key={i}
                        className="flex items-center justify-between text-sm"
                      >
                        <span>{w.doc_type}</span>
                        <span
                          className={
                            w.uploaded ? "text-[#4a9c5c]" : "text-[#c9a14a]"
                          }
                        >
                          {w.uploaded ? "uploaded" : "pending"}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

- [ ] **Step 3: Run, commit**

```bash
npm test -- --run src/components/portal/process/StepDetailDrawer.test.tsx
git add apps/mouth/src/components/portal/process/StepDetailDrawer.tsx apps/mouth/src/components/portal/process/StepDetailDrawer.test.tsx
git commit -m "feat(portal): StepDetailDrawer with Radix Dialog, focus trap, ESC close"
```

## Task 2.7: BlockedStateCTA + ProcessErrorBoundary

**Files:**

- Create: `BlockedStateCTA.tsx`, `ProcessErrorBoundary.tsx`, tests

- [ ] **Step 1: BlockedStateCTA**

```tsx
// BlockedStateCTA.tsx
import Link from "next/link";
import { AlertTriangle } from "lucide-react";

interface Props {
  practiceId: string;
  reason: string | null;
}

export function BlockedStateCTA({ practiceId, reason }: Props) {
  const href = `/portal/messages?topic=${encodeURIComponent(`practice-${practiceId}`)}`;
  return (
    <div
      role="alert"
      className="rounded-lg p-4 border border-[#c94a4a]/40 bg-[#c94a4a]/10 flex items-start gap-3"
    >
      <AlertTriangle className="w-5 h-5 text-[#c94a4a] shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="text-sm text-[#c94a4a] mb-2">
          Pratica bloccata{reason ? `: ${reason}` : ""}.
        </p>
        <Link
          href={href}
          className="inline-block text-xs uppercase tracking-[2px] text-[#d4845a] hover:underline"
        >
          Contatta il team →
        </Link>
      </div>
    </div>
  );
}
```

Test: renders reason, href encodes practice id, `role="alert"` present.

- [ ] **Step 2: ProcessErrorBoundary**

```tsx
// ProcessErrorBoundary.tsx
"use client";
import React from "react";

interface State {
  hasError: boolean;
}

export class ProcessErrorBoundary extends React.Component<
  { children: React.ReactNode },
  State
> {
  state: State = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    console.error("[ProcessErrorBoundary]", error);
  }

  handleRetry = () => this.setState({ hasError: false });

  render() {
    if (this.state.hasError) {
      return (
        <div className="rounded-lg p-6 text-center border border-white/10">
          <p className="text-sm text-[#c9a96e]/70 mb-4">
            Impossibile caricare i dettagli. Il team è stato notificato.
          </p>
          <button
            onClick={this.handleRetry}
            className="text-xs uppercase tracking-[2px] text-[#d4845a] hover:underline"
          >
            Riprova
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

Test: catches thrown error in child, shows fallback, Retry resets state.

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/components/portal/process/BlockedStateCTA.tsx apps/mouth/src/components/portal/process/BlockedStateCTA.test.tsx apps/mouth/src/components/portal/process/ProcessErrorBoundary.tsx apps/mouth/src/components/portal/process/ProcessErrorBoundary.test.tsx
git commit -m "feat(portal): BlockedStateCTA + ProcessErrorBoundary"
```

## Task 2.8: Wire page [practiceId]/page.tsx

**Files:**

- Create: `apps/mouth/src/app/portal/(authenticated)/process/[practiceId]/page.tsx`

- [ ] **Step 1: Check existing process/page.tsx**

Run: `cat apps/mouth/src/app/portal/\(authenticated\)/process/page.tsx | head -50`

This page stays as the list. The detail route gets created fresh.

- [ ] **Step 2: Implement detail page**

```tsx
// apps/mouth/src/app/portal/(authenticated)/process/[practiceId]/page.tsx
"use client";
import { useState } from "react";
import { useProcessSteps } from "@/hooks/useProcessSteps";
import { ProcessTimeline } from "@/components/portal/process/ProcessTimeline";
import { StepDetailDrawer } from "@/components/portal/process/StepDetailDrawer";
import { TimelineSkeleton } from "@/components/portal/process/TimelineSkeleton";
import { BlockedStateCTA } from "@/components/portal/process/BlockedStateCTA";
import { ProcessErrorBoundary } from "@/components/portal/process/ProcessErrorBoundary";
import type { ProcessStep } from "@/lib/schemas/process";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

interface Props {
  params: { practiceId: string };
}

export default function PracticeDetailPage({ params }: Props) {
  const { data, error, isLoading, mutate } = useProcessSteps(params.practiceId);
  const [selected, setSelected] = useState<ProcessStep | null>(null);

  const blockedStep = data?.steps.find((s) => s.state === "blocked") ?? null;

  return (
    <ProcessErrorBoundary>
      <main className="max-w-3xl mx-auto px-4 py-6">
        <Link
          href="/portal/process"
          className="inline-flex items-center gap-1 text-xs text-[#c9a96e]/60 hover:text-[#c9a96e] mb-6"
        >
          <ArrowLeft className="w-3 h-3" /> All practices
        </Link>

        {isLoading && <TimelineSkeleton count={4} />}

        {error && (
          <div
            role="alert"
            className="rounded-lg p-4 border border-white/10 text-sm"
          >
            <p className="mb-2">Impossibile caricare la pratica.</p>
            <button
              onClick={() => mutate()}
              className="text-xs uppercase tracking-[2px] text-[#d4845a] hover:underline"
            >
              Riprova
            </button>
          </div>
        )}

        {data && (
          <>
            {blockedStep && (
              <div className="mb-6">
                <BlockedStateCTA
                  practiceId={params.practiceId}
                  reason={blockedStep.blocked_reason}
                />
              </div>
            )}
            <ProcessTimeline steps={data.steps} onSelect={setSelected} />
          </>
        )}

        <StepDetailDrawer
          step={selected}
          open={selected !== null}
          onClose={() => setSelected(null)}
        />
      </main>
    </ProcessErrorBoundary>
  );
}
```

- [ ] **Step 3: Typecheck + manual smoke**

```bash
npx tsc --noEmit
npm run dev &
# Manual: visit /portal/process/p1 (fake id). Verify error state renders with Retry.
```

- [ ] **Step 4: Commit (finalize commit 2)**

```bash
git add apps/mouth/src/app/portal/\(authenticated\)/process/\[practiceId\]/page.tsx
git commit -m "feat(portal): process timeline vertical — state machine visual, step detail drawer, blocked state CTA"
```

---

# COMMIT 3 — Vault UX

## Task 3.1: Zod schema for vault

**Files:**

- Create: `apps/mouth/src/lib/schemas/vault.ts` + `.test.ts`

- [ ] **Step 1: Schema**

```ts
// apps/mouth/src/lib/schemas/vault.ts
import { z } from "zod";

export const VaultScanStatus = z.enum([
  "pending",
  "clean",
  "infected",
  "error",
]);
export type VaultScanStatus = z.infer<typeof VaultScanStatus>;

export const VaultFile = z.object({
  id: z.string(),
  name: z.string(),
  mime_type: z.string(),
  size_bytes: z.number().int().nonnegative(),
  practice_id: z.string().nullable(),
  practice_title: z.string().nullable(),
  category: z.string().nullable(),
  uploaded_at: z.string().datetime(),
  uploaded_by: z.string(),
  drive_file_id: z.string().nullable(),
  preview_url: z.string().url().nullable(),
  download_url: z.string().url(),
  scan_status: VaultScanStatus.default("pending"),
});
export type VaultFile = z.infer<typeof VaultFile>;

export const VaultListResponse = z.object({
  version: z.literal(1),
  files: z.array(VaultFile),
  total: z.number().int().nonnegative(),
});
export type VaultListResponse = z.infer<typeof VaultListResponse>;
```

- [ ] **Step 2: Test** — 5 cases: valid minimal, invalid url, invalid scan_status, default scan_status, rejects negative size.

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/lib/schemas/vault.ts apps/mouth/src/lib/schemas/vault.test.ts
git commit -m "feat(portal): Zod schemas for vault"
```

## Task 3.2: Vault utility libs

**Files:**

- Create: `src/lib/vault/mimeAllowlist.ts` + test
- Create: `src/lib/vault/sanitizeFilename.ts` + test

- [ ] **Step 1: mimeAllowlist**

```ts
// src/lib/vault/mimeAllowlist.ts
export const ALLOWED_MIMES = [
  "application/pdf",
  "image/jpeg",
  "image/png",
  "image/webp",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/msword",
  "application/vnd.ms-excel",
] as const satisfies readonly string[];

export type AllowedMime = (typeof ALLOWED_MIMES)[number];

const PREVIEWABLE = new Set<string>([
  "application/pdf",
  "image/jpeg",
  "image/png",
  "image/webp",
]);

export function isAllowedMime(mime: string): boolean {
  return (ALLOWED_MIMES as readonly string[]).includes(mime);
}

export function isPreviewable(mime: string): boolean {
  return PREVIEWABLE.has(mime);
}

export const MAX_SIZE_BYTES = Number(
  process.env.NEXT_PUBLIC_VAULT_MAX_SIZE ?? String(20 * 1024 * 1024),
);
```

Test: 6 cases (allowed PDF, allowed PNG, disallowed SVG, disallowed EXE, previewable true/false, MAX_SIZE_BYTES is number).

- [ ] **Step 2: sanitizeFilename**

```ts
// src/lib/vault/sanitizeFilename.ts
export function sanitizeFilename(raw: string): string {
  return (
    raw
      .replace(/[\/\\]/g, "_")
      .replace(/\.\./g, "_")
      .replace(/[<>:"|?*\x00-\x1f]/g, "_")
      .replace(/^\.+/, "_") // leading dots
      .trim()
      .slice(0, 240) || "unnamed"
  );
}
```

Test: 8 adversarial (path traversal, null byte, windows specials, leading dots, empty → unnamed, length cap, unicode preserved, normal preserved).

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/lib/vault
git commit -m "feat(portal): vault mime allowlist + filename sanitize"
```

## Task 3.3: Vault hooks

**Files:**

- Create: `src/hooks/useVaultFiles.ts` + `.test.ts`
- Create: `src/hooks/useVaultUpload.ts` + `.test.ts`
- Create: `src/hooks/useVaultScanStatus.ts` + `.test.ts`

- [ ] **Step 1: useVaultFiles**

```ts
// src/hooks/useVaultFiles.ts
"use client";
import useSWR from "swr";
import { api } from "@/lib/api";
import { VaultListResponse } from "@/lib/schemas/vault";

export function useVaultFiles() {
  return useSWR(
    ["portal-vault-files"],
    async () => {
      const res = await api.get("/api/portal/vault");
      return VaultListResponse.parse(res.data);
    },
    { revalidateOnFocus: true, dedupingInterval: 5000 },
  );
}
```

Test: success parse, schema drift throws, cached data same key.

- [ ] **Step 2: useVaultUpload**

```ts
// src/hooks/useVaultUpload.ts
"use client";
import { useCallback, useState } from "react";
import { isAllowedMime, MAX_SIZE_BYTES } from "@/lib/vault/mimeAllowlist";
import { sanitizeFilename } from "@/lib/vault/sanitizeFilename";
import { VaultFile } from "@/lib/schemas/vault";

type UploadState =
  | { status: "idle" }
  | { status: "validating" }
  | { status: "uploading"; progress: number }
  | { status: "done"; file: VaultFile }
  | { status: "error"; message: string };

export function useVaultUpload(practiceId?: string | null) {
  const [state, setState] = useState<UploadState>({ status: "idle" });

  const upload = useCallback(
    (file: File) => {
      setState({ status: "validating" });
      if (!isAllowedMime(file.type)) {
        setState({ status: "error", message: "File type not allowed" });
        return;
      }
      if (file.size > MAX_SIZE_BYTES) {
        setState({
          status: "error",
          message: `File exceeds ${MAX_SIZE_BYTES} bytes`,
        });
        return;
      }

      const fd = new FormData();
      fd.append("file", file, sanitizeFilename(file.name));
      if (practiceId) fd.append("practice_id", practiceId);

      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/portal/documents/upload");
      xhr.withCredentials = true;

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          setState({
            status: "uploading",
            progress: (e.loaded / e.total) * 100,
          });
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const parsed = VaultFile.parse(JSON.parse(xhr.responseText));
            setState({ status: "done", file: parsed });
          } catch {
            setState({ status: "error", message: "Invalid server response" });
          }
        } else {
          setState({
            status: "error",
            message: `Upload failed (${xhr.status})`,
          });
        }
      };
      xhr.onerror = () =>
        setState({ status: "error", message: "Network error" });
      xhr.send(fd);
    },
    [practiceId],
  );

  return { state, upload };
}
```

Test: rejects oversize, rejects bad mime, progress updates (mock XHR), schema drift → error.

- [ ] **Step 3: useVaultScanStatus**

```ts
// src/hooks/useVaultScanStatus.ts
"use client";
import useSWR from "swr";
import { api } from "@/lib/api";
import { z } from "zod";
import { VaultScanStatus } from "@/lib/schemas/vault";

const ScanResp = z.object({ scan_status: VaultScanStatus });

export function useVaultScanStatus(fileId: string | null, enabled: boolean) {
  return useSWR(
    enabled && fileId ? ["vault-scan", fileId] : null,
    async () => {
      const res = await api.get(`/api/portal/documents/${fileId}/scan-status`);
      return ScanResp.parse(res.data).scan_status;
    },
    {
      refreshInterval: (latest) =>
        latest === "clean" || latest === "infected" || latest === "error"
          ? 0
          : 2000,
      dedupingInterval: 1000,
    },
  );
}
```

Test: polls while pending, stops on terminal status, disabled when enabled=false.

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/hooks/useVault*.ts apps/mouth/src/hooks/useVault*.test.ts
git commit -m "feat(portal): vault hooks — list, upload with progress+scan poll"
```

## Task 3.4: Vault components

**Files:**

- Create: `VaultPreviewPane.tsx`, `VaultSearchBar.tsx`, `VaultSidebar.tsx`, `VaultFileGrid.tsx`, `VaultUploadZone.tsx`, `VaultLayout.tsx`, `VaultErrorBoundary.tsx` + tests

Implementazione sintetica — each file follows spec §4.2.

- [ ] **Step 1: VaultPreviewPane (iframe)**

```tsx
// VaultPreviewPane.tsx
"use client";
import { useState } from "react";
import { Download } from "lucide-react";
import type { VaultFile } from "@/lib/schemas/vault";
import { isPreviewable } from "@/lib/vault/mimeAllowlist";

export function VaultPreviewPane({ file }: { file: VaultFile | null }) {
  const [iframeError, setIframeError] = useState(false);

  if (!file) {
    return (
      <div className="h-full flex items-center justify-center text-sm text-[#c9a96e]/50">
        Select a file to preview
      </div>
    );
  }

  const canPreview =
    isPreviewable(file.mime_type) && file.preview_url && !iframeError;

  if (!canPreview) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-4">
        <p className="text-sm text-[#c9a96e]/70">
          Preview not available for this file.
        </p>
        <a
          href={file.download_url}
          download={file.name}
          className="inline-flex items-center gap-2 px-4 py-2 rounded bg-[#d4845a] text-black text-xs uppercase tracking-[0.08em]"
        >
          <Download className="w-4 h-4" /> Download
        </a>
      </div>
    );
  }

  return (
    <iframe
      src={file.preview_url!}
      sandbox="allow-scripts allow-same-origin"
      referrerPolicy="no-referrer"
      title={`Preview ${file.name}`}
      loading="lazy"
      onError={() => setIframeError(true)}
      className="w-full h-full border-0 bg-black"
    />
  );
}
```

Test: null file → select msg, non-previewable → download fallback, iframe error → download fallback, sandbox attribute correct.

- [ ] **Step 2: VaultSearchBar**

```tsx
// VaultSearchBar.tsx
"use client";
import { useEffect, useState } from "react";
import { Search } from "lucide-react";

interface Props {
  value: string;
  onChange: (v: string) => void;
}

export function VaultSearchBar({ value, onChange }: Props) {
  const [local, setLocal] = useState(value);
  useEffect(() => {
    setLocal(value);
  }, [value]);
  useEffect(() => {
    const t = setTimeout(() => onChange(local), 200);
    return () => clearTimeout(t);
  }, [local, onChange]);
  return (
    <div className="relative">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#c9a96e]/50" />
      <input
        role="searchbox"
        aria-label="Search vault files"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        placeholder="Search files…"
        className="w-full pl-10 pr-3 py-2 bg-white/5 rounded border border-white/10 text-sm text-[#f0ece4]"
      />
    </div>
  );
}
```

Test: debounces onChange 200ms, controlled via `value`.

- [ ] **Step 3: VaultSidebar (filter by practice/category)**

```tsx
// VaultSidebar.tsx
"use client";
import type { VaultFile } from "@/lib/schemas/vault";

interface Props {
  files: VaultFile[];
  practiceFilter: string | null;
  categoryFilter: string | null;
  onPracticeChange: (id: string | null) => void;
  onCategoryChange: (c: string | null) => void;
}

export function VaultSidebar({
  files,
  practiceFilter,
  categoryFilter,
  onPracticeChange,
  onCategoryChange,
}: Props) {
  const practices = Array.from(
    new Map(
      files
        .filter((f) => f.practice_id)
        .map((f) => [f.practice_id!, f.practice_title ?? f.practice_id!]),
    ).entries(),
  );
  const categories = Array.from(
    new Set(files.map((f) => f.category).filter((c): c is string => !!c)),
  );

  const countPractice = (id: string) =>
    files.filter((f) => f.practice_id === id).length;
  const countCategory = (c: string) =>
    files.filter((f) => f.category === c).length;

  return (
    <aside className="space-y-6">
      <section>
        <h3 className="text-xs uppercase tracking-[2px] text-[#c9a96e]/50 mb-2">
          Practices
        </h3>
        <ul className="space-y-1">
          <li>
            <button
              className={`w-full text-left text-sm px-2 py-1 rounded ${!practiceFilter ? "bg-white/10" : "hover:bg-white/5"}`}
              onClick={() => onPracticeChange(null)}
            >
              All <span className="text-[#c9a96e]/40">({files.length})</span>
            </button>
          </li>
          {practices.map(([id, title]) => (
            <li key={id}>
              <button
                className={`w-full text-left text-sm px-2 py-1 rounded ${practiceFilter === id ? "bg-white/10" : "hover:bg-white/5"}`}
                onClick={() => onPracticeChange(id)}
              >
                {title}{" "}
                <span className="text-[#c9a96e]/40">({countPractice(id)})</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      {categories.length > 0 && (
        <section>
          <h3 className="text-xs uppercase tracking-[2px] text-[#c9a96e]/50 mb-2">
            Categories
          </h3>
          <ul className="space-y-1">
            {categories.map((c) => (
              <li key={c}>
                <button
                  className={`w-full text-left text-sm px-2 py-1 rounded ${categoryFilter === c ? "bg-white/10" : "hover:bg-white/5"}`}
                  onClick={() =>
                    onCategoryChange(categoryFilter === c ? null : c)
                  }
                >
                  {c}{" "}
                  <span className="text-[#c9a96e]/40">
                    ({countCategory(c)})
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </aside>
  );
}
```

Test: lists unique practices, counts correct, clicking toggles filter.

- [ ] **Step 4: VaultFileGrid**

```tsx
// VaultFileGrid.tsx
"use client";
import { FileText, Image as ImgIcon, File as FileIcon } from "lucide-react";
import type { VaultFile } from "@/lib/schemas/vault";

function iconFor(mime: string) {
  if (mime === "application/pdf") return FileText;
  if (mime.startsWith("image/")) return ImgIcon;
  return FileIcon;
}

interface Props {
  files: VaultFile[];
  selectedId: string | null;
  onSelect: (file: VaultFile) => void;
}

export function VaultFileGrid({ files, selectedId, onSelect }: Props) {
  if (files.length === 0) {
    return (
      <p className="text-sm text-[#c9a96e]/60 py-8 text-center">No files.</p>
    );
  }
  return (
    <ul className="grid grid-cols-2 md:grid-cols-3 gap-3">
      {files.map((f) => {
        const Icon = iconFor(f.mime_type);
        const selected = f.id === selectedId;
        return (
          <li key={f.id}>
            <button
              onClick={() => onSelect(f)}
              className={`w-full p-3 rounded-lg border text-left ${selected ? "border-[#d4845a] bg-white/10" : "border-white/10 hover:border-white/30"}`}
              aria-pressed={selected}
            >
              <Icon className="w-8 h-8 text-[#c9a96e]/70 mb-2" />
              <p className="text-xs text-[#f0ece4] truncate" title={f.name}>
                {f.name}
              </p>
              {f.scan_status === "infected" && (
                <p className="text-[10px] text-[#c94a4a] uppercase mt-1">
                  blocked
                </p>
              )}
              {f.scan_status === "pending" && (
                <p className="text-[10px] text-[#c9a14a] uppercase mt-1">
                  scanning…
                </p>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
```

Test: empty state, selected aria-pressed, icon per mime.

- [ ] **Step 5: VaultUploadZone**

```tsx
// VaultUploadZone.tsx
"use client";
import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { useVaultUpload } from "@/hooks/useVaultUpload";

interface Props {
  practiceId?: string | null;
  onDone?: () => void;
}

export function VaultUploadZone({ practiceId, onDone }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const { state, upload } = useVaultUpload(practiceId);

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    upload(files[0]);
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
      className={`rounded-lg border-2 border-dashed p-6 text-center transition ${dragOver ? "border-[#d4845a] bg-white/5" : "border-white/20"}`}
    >
      <Upload className="w-6 h-6 mx-auto text-[#c9a96e]/60 mb-2" />
      <p className="text-sm text-[#c9a96e]/70 mb-3">Drag & drop here, or</p>
      <button
        onClick={() => inputRef.current?.click()}
        className="text-xs uppercase tracking-[2px] text-[#d4845a] hover:underline"
      >
        Choose file
      </button>
      <input
        ref={inputRef}
        type="file"
        className="sr-only"
        onChange={(e) => handleFiles(e.target.files)}
        aria-label="Upload file"
      />
      {state.status === "uploading" && (
        <p role="status" className="text-xs text-[#c9a96e]/60 mt-3">
          Uploading… {Math.round(state.progress)}%
        </p>
      )}
      {state.status === "error" && (
        <p role="alert" className="text-xs text-[#c94a4a] mt-3">
          {state.message}
        </p>
      )}
      {state.status === "done" && (
        <p role="status" className="text-xs text-[#4a9c5c] mt-3">
          Uploaded: {state.file.name}
          {onDone?.()}
        </p>
      )}
    </div>
  );
}
```

Test: drag-over class toggles, file chosen triggers upload, error state renders.

- [ ] **Step 6: VaultErrorBoundary** — identico pattern a `ProcessErrorBoundary`, duplica file + adatta messaggio.

- [ ] **Step 7: VaultLayout** — assemble:

```tsx
// VaultLayout.tsx
"use client";
import { useMemo, useState } from "react";
import { VaultSidebar } from "./VaultSidebar";
import { VaultFileGrid } from "./VaultFileGrid";
import { VaultPreviewPane } from "./VaultPreviewPane";
import { VaultSearchBar } from "./VaultSearchBar";
import { VaultUploadZone } from "./VaultUploadZone";
import { VaultErrorBoundary } from "./VaultErrorBoundary";
import { useVaultFiles } from "@/hooks/useVaultFiles";
import type { VaultFile } from "@/lib/schemas/vault";

export function VaultLayout() {
  const { data, error, isLoading, mutate } = useVaultFiles();
  const [selected, setSelected] = useState<VaultFile | null>(null);
  const [practiceFilter, setPracticeFilter] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [q, setQ] = useState("");

  const files = data?.files ?? [];
  const filtered = useMemo(() => {
    const ql = q.toLowerCase();
    return files.filter((f) => {
      if (practiceFilter && f.practice_id !== practiceFilter) return false;
      if (categoryFilter && f.category !== categoryFilter) return false;
      if (
        ql &&
        !(
          f.name.toLowerCase().includes(ql) ||
          f.category?.toLowerCase().includes(ql) ||
          f.practice_title?.toLowerCase().includes(ql)
        )
      )
        return false;
      return f.scan_status !== "infected";
    });
  }, [files, practiceFilter, categoryFilter, q]);

  return (
    <VaultErrorBoundary>
      <div className="grid grid-cols-1 md:grid-cols-[220px_1fr_minmax(0,480px)] gap-4 h-[calc(100vh-120px)]">
        <div className="md:col-span-3 flex gap-3 items-center">
          <div className="flex-1">
            <VaultSearchBar value={q} onChange={setQ} />
          </div>
          <VaultUploadZone
            practiceId={practiceFilter}
            onDone={() => mutate()}
          />
        </div>
        <VaultSidebar
          files={files}
          practiceFilter={practiceFilter}
          categoryFilter={categoryFilter}
          onPracticeChange={setPracticeFilter}
          onCategoryChange={setCategoryFilter}
        />
        <div className="overflow-y-auto">
          {isLoading && <p className="text-sm text-[#c9a96e]/60">Loading…</p>}
          {error && (
            <div role="alert">
              <p className="text-sm">Unable to load vault.</p>
              <button
                onClick={() => mutate()}
                className="text-xs uppercase tracking-[2px] text-[#d4845a]"
              >
                Retry
              </button>
            </div>
          )}
          {data && (
            <VaultFileGrid
              files={filtered}
              selectedId={selected?.id ?? null}
              onSelect={setSelected}
            />
          )}
        </div>
        <div className="rounded-lg border border-white/10 overflow-hidden h-full">
          <VaultPreviewPane file={selected} />
        </div>
      </div>
    </VaultErrorBoundary>
  );
}
```

- [ ] **Step 8: Wire into page**

```tsx
// apps/mouth/src/app/portal/(authenticated)/vault/page.tsx
import { VaultLayout } from "@/components/portal/vault/VaultLayout";
export default function VaultPage() {
  return <VaultLayout />;
}
```

- [ ] **Step 9: Typecheck + run tests + commit (finalize commit 3)**

```bash
cd apps/mouth && npx tsc --noEmit
npm test -- --run src/lib/schemas/vault src/lib/vault src/hooks/useVault src/components/portal/vault
git add apps/mouth/src/components/portal/vault apps/mouth/src/app/portal/\(authenticated\)/vault/page.tsx
git commit -m "feat(portal): vault UX — sidebar organization, iframe PDF preview with sandbox, drag-drop upload with scan status, search"
```

---

# COMMIT 4 — Settings Tabs

## Task 4.1: Settings Zod schemas

**Files:**

- Create: `src/lib/schemas/settings.ts` + `.test.ts`

```ts
// src/lib/schemas/settings.ts
import { z } from "zod";

export const Language = z.enum(["it", "en", "id"]);
export type Language = z.infer<typeof Language>;

export const UserProfile = z.object({
  id: z.string(),
  email: z.string().email(),
  name: z.string(),
  avatar_url: z.string().url().nullable(),
  language: Language,
  created_at: z.string().datetime(),
  two_factor_enabled: z.boolean(),
  email_verified: z.boolean(),
});
export type UserProfile = z.infer<typeof UserProfile>;

export const NotificationChannel = z.enum([
  "email",
  "push",
  "telegram",
  "whatsapp",
]);
export type NotificationChannel = z.infer<typeof NotificationChannel>;

export const NotificationEvent = z.enum([
  "practice_update",
  "deadline_reminder",
  "new_message",
  "billing_reminder",
  "security_alert",
]);
export type NotificationEvent = z.infer<typeof NotificationEvent>;

export const NotificationPrefs = z.record(
  NotificationEvent,
  z.record(NotificationChannel, z.boolean()),
);
export type NotificationPrefs = z.infer<typeof NotificationPrefs>;
```

Tests: valid parse, invalid email rejected, unknown language rejected, matrix record works.

- [ ] Commit: `feat(portal): Zod schemas for settings`

## Task 4.2: useMe + useLanguage

```ts
// src/hooks/useMe.ts
"use client";
import useSWR from "swr";
import { api } from "@/lib/api";
import { UserProfile } from "@/lib/schemas/settings";

export function useMe() {
  return useSWR(
    ["portal-me"],
    async () => {
      const res = await api.get("/api/portal/me");
      return UserProfile.parse(res.data);
    },
    { revalidateOnFocus: true },
  );
}
```

```ts
// src/hooks/useLanguage.ts
"use client";
import { useCallback } from "react";
import { Language } from "@/lib/schemas/settings";

const COOKIE = "preferred_language";

async function postLanguage(lang: Language): Promise<void> {
  await fetch("/api/portal/me/language", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language: lang }),
  });
}

export function useLanguage() {
  const setLanguage = useCallback(async (lang: Language) => {
    document.cookie = `${COOKIE}=${lang}; domain=.balizero.com; path=/; max-age=31536000; secure; samesite=lax`;
    try {
      await postLanguage(lang);
    } catch {
      /* cookie set locally; BE sync failure is non-fatal */
    }
  }, []);
  return { setLanguage };
}
```

Tests: schema drift throws, cookie written correctly.

- [ ] Commit: `feat(portal): useMe + useLanguage hooks`

## Task 4.3: SettingsTabs URL-synced

```tsx
// src/components/portal/settings/SettingsTabs.tsx
"use client";
import * as Tabs from "@radix-ui/react-tabs";
import { useRouter, useSearchParams } from "next/navigation";
import { AccountSettings } from "./AccountSettings";
import { SecuritySettings } from "./SecuritySettings";
import { NotificationSettings } from "./NotificationSettings";
import { PrivacySettings } from "./PrivacySettings";
import { LanguageSettings } from "./LanguageSettings";

const TABS = [
  "account",
  "security",
  "notifications",
  "privacy",
  "language",
] as const;
type TabId = (typeof TABS)[number];

export function SettingsTabs() {
  const router = useRouter();
  const sp = useSearchParams();
  const raw = sp.get("tab") ?? "account";
  const active: TabId = (TABS as readonly string[]).includes(raw)
    ? (raw as TabId)
    : "account";

  const setTab = (t: string) => {
    const params = new URLSearchParams(sp.toString());
    params.set("tab", t);
    router.replace(`/portal/settings?${params.toString()}`);
  };

  return (
    <Tabs.Root value={active} onValueChange={setTab}>
      <Tabs.List
        className="flex gap-1 border-b border-white/10 mb-6"
        aria-label="Settings"
      >
        {TABS.map((t) => (
          <Tabs.Trigger
            key={t}
            value={t}
            className="px-4 py-2 text-sm text-[#c9a96e]/70 data-[state=active]:text-[#f0ece4] data-[state=active]:border-b-2 data-[state=active]:border-[#d4845a] capitalize"
          >
            {t}
          </Tabs.Trigger>
        ))}
      </Tabs.List>
      <Tabs.Content value="account">
        <AccountSettings />
      </Tabs.Content>
      <Tabs.Content value="security">
        <SecuritySettings />
      </Tabs.Content>
      <Tabs.Content value="notifications">
        <NotificationSettings />
      </Tabs.Content>
      <Tabs.Content value="privacy">
        <PrivacySettings />
      </Tabs.Content>
      <Tabs.Content value="language">
        <LanguageSettings />
      </Tabs.Content>
    </Tabs.Root>
  );
}
```

Test: default active=account; `?tab=security` syncs; unknown tab falls back to account.

## Task 4.4: Tab components — minimal functional scaffolds

**Rationale:** Each tab component is a non-trivial surface. Rather than expand each into full TDD micro-tasks (would ~double plan length), we ship **minimal functional implementations** with explicit contract: controlled inputs, Zod validate on submit, toast feedback, error mapping. No fake flows. The engineer writing these follows the **same TDD pattern** used in Tasks 1-3 (test-first, one component per commit).

**Per-component contract (non-negotiable):**

1. File at exact path below
2. Sibling `.test.tsx` with ≥3 behavior tests
3. Zod schema validation for any form inputs (use schemas from Task 4.1)
4. Error mapping for HTTP status codes (401/403/422/429/5xx)
5. `aria-*` attrs for controls
6. IT/EN/ID labels in `i18n/portal/settings.*.json` (new file, create same way as login i18n in Task 1.3)

**Checkpoint:** after each of the 9 sub-tasks below, run `npm test -- --run <path>` and commit the single component + test + any i18n updates as a separate commit. At task 4.5 the pieces get wired together.

- [ ] **AccountSettings** (`components/portal/settings/AccountSettings.tsx`) — form name + avatar_url readonly + email readonly; save via `api.patch('/api/portal/me', ...)`. Zod validate. If `api.patch` not available, use `fetch(url, { method: 'PATCH', credentials: 'include' })` instead.
- [ ] **SecuritySettings** — composes `<PasswordChangeForm />`, `<TwoFactorPanel />`, `<SessionsPanel />`. If BE absent for 2FA/Sessions: panel renders "Coming soon — issue #TODO".
- [ ] **PasswordChangeForm** — controlled inputs current/new/confirm + `<PasswordStrengthMeter />`; submit POST `/api/portal/me/password`; error mapping (401 current wrong, 422 weak, 429 rate limited).
- [ ] **PasswordStrengthMeter** — compute score (length ≥12 + has upper + has number + has symbol → 0-4 bar). `role="progressbar"`, `aria-valuenow`, `aria-valuemax`.
- [ ] **TwoFactorPanel** — skeleton: if BE endpoint `/api/portal/me/2fa` 404s on detect, render "Coming soon". Otherwise enroll flow: fetch QR → verify code → activate.
- [ ] **SessionsPanel** — skeleton: if `/api/portal/me/sessions` absent, "Coming soon". Otherwise list + revoke-others.
- [ ] **NotificationSettings** — matrix checkbox grid 5 events × 4 channels, debounced 500ms save. Push permission probe.
- [ ] **PrivacySettings** — 2 CTA: "Request data export" (mailto fallback), "Delete account" (modal confirm → mailto fallback).
- [ ] **LanguageSettings** — 3 radio buttons IT/EN/ID; `useLanguage().setLanguage()` on change.

For each component, sibling `.test.tsx` covers 2-3 core behaviors.

- [ ] **Commit for each tab component** (micro-commits ok, or single batched commit at end)

## Task 4.5: Wire settings/page.tsx

```tsx
// apps/mouth/src/app/portal/(authenticated)/settings/page.tsx
import { SettingsTabs } from "@/components/portal/settings/SettingsTabs";
export default function SettingsPage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-6">
      <h1 className="text-2xl font-light mb-6 text-[#f0ece4]">Settings</h1>
      <SettingsTabs />
    </main>
  );
}
```

Note: existing `notifications/` subroute can stay or be removed later (out of PF1 scope).

- [ ] **Step: Final commit (commit 4)**

```bash
git add apps/mouth/src/app/portal/\(authenticated\)/settings apps/mouth/src/components/portal/settings apps/mouth/src/hooks/useMe.ts apps/mouth/src/hooks/useLanguage.ts apps/mouth/src/lib/schemas/settings.ts
git commit -m "feat(portal): settings tabs — account, security (password+2FA+sessions), notifications matrix, privacy, language switcher"
```

---

# POST-COMMIT VERIFICATION

## Task 5.1: Type + lint + test final sweep

- [ ] **Step 1:** `cd apps/mouth && npx tsc --noEmit` → zero new errors
- [ ] **Step 2:** `npm run lint` → zero new warnings
- [ ] **Step 3:** `npm test -- --run` → all tests pass (count ≥ baseline + 40 new tests)
- [ ] **Step 4:** `npm run build` → production build success
- [ ] **Step 5:** `npm run dev` background; manual smoke on 4 routes:
  - `/portal/login` → 308 → `/portal/login-upgraded`
  - `/portal/forgot-password` → 200
  - `/portal/process/any-id` → loading/error handled gracefully
  - `/portal/vault` → layout renders
  - `/portal/settings?tab=security` → tab active

## Task 5.2: Security checklist (spec §6.5)

Run through manually, confirm each:

- [ ] No secrets in diff: `git log -p pro/frontend-portal-client-app ^main | grep -iE 'secret|token|api_key|password.*=.*[A-Za-z0-9]{12,}'` returns nothing
- [ ] No `dangerouslySetInnerHTML` additions: `git diff main.. apps/mouth/src | grep dangerouslySetInnerHTML` — only pre-existing instances (login CSS autofill) remain
- [ ] Iframes sandboxed: `grep -rn '<iframe' apps/mouth/src/components/portal` — all have `sandbox="allow-scripts allow-same-origin"`
- [ ] Upload mime+size+filename enforced: checked in `useVaultUpload`
- [ ] Open-redirect allowlist: `sanitizeRedirect` test 14 cases pass
- [ ] 2FA secret: never stored outside React component state (TwoFactorPanel only)
- [ ] Password: never logged — grep `logger.*password` returns zero in new code

## Task 5.3: RBAC manual cross-user test

- [ ] Login as user A in dev; note network `Cookie` header
- [ ] Attempt `/portal/process/${user_B_practice_id}` — expect 404 UI, no data leak
- [ ] Attempt `/portal/vault` — see only user A's files
- [ ] Same for `/portal/settings` — only own profile

If any fail → STOP, file issue, do not merge.

## Task 5.4: Lighthouse spot check (optional but recommended)

- [ ] Run Lighthouse mobile on `/portal/login-upgraded` and `/portal/vault`
- [ ] Target ≥80 performance. Note any regression vs baseline.

---

# OPTIONAL: Open PR

- [ ] Push branch: `git push -u origin pro/frontend-portal-client-app`
- [ ] `gh pr create --title "feat(portal): client-app L2 PF1 — login unify, process timeline, vault, settings" --body "..."` with:
  - Summary of 4 commits
  - Spec link: `docs/superpowers/specs/2026-04-18-portal-client-app-pf1-design.md`
  - Screenshots before/after per section (capture with `mcp__claude-in-chrome__*`)
  - Test plan checklist (from §5)
  - Note: worktree `.worktrees/portal-client-app` cleanup after merge

---

## Appendix A — Git / Rollback Guide

Each commit is atomic at section level. Rollback strategies:

- Rollback one section: `git revert <sha>` on that commit
- Rollback all: `git revert <first-sha>..<last-sha>`
- Before push, squash if desired: `git rebase -i main` (interactive)

## Appendix B — If Audit Finds Missing BE Endpoints

| Endpoint                                     | If missing                                                                                            |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `GET /api/portal/practices/:id/steps`        | Use mock local data + issue #TODO; stop before committing task 2.8 and flag                           |
| `POST /api/auth/password-reset-request`      | Keep mailto fallback (already the plan default)                                                       |
| `/api/portal/vault`                          | Stop before task 3.4 step 9 and flag                                                                  |
| `/api/portal/documents/upload` + scan-status | Upload UI can be built; if endpoint missing, state="error: upload not yet available" shown; add issue |
| `/api/portal/me/2fa`                         | TwoFactorPanel renders "Coming soon" placeholder (already planned)                                    |
| `/api/portal/me/sessions`                    | SessionsPanel renders "Coming soon" placeholder                                                       |

Per spec §1 blocker rule: if an endpoint requires DB migration/new schema, **stop** and ask user before proceeding.

## Appendix C — File count estimate

New files: ~55 (components, hooks, schemas, tests, i18n)
Modified: ~5 (login, login-upgraded, settings page, vault page, process page)
LOC delta: +2500 / -50 est.
Test count delta: +40+ new tests
