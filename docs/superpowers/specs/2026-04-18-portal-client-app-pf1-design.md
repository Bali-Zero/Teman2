# Portal Client-App (L2) — Sessione PF1 Design

**Date**: 2026-04-18
**Branch target**: `pro/frontend-portal-client-app` (off `main`)
**Session**: PF1 — Pro, Opus 4.7 (1M ctx) xhigh
**Scope layer**: L2 Client App of v2 Subdomain Rollout 3-Layer (spec 2026-04-17)
**Robustness directive**: "robusto e infallibile" — no mock in prod, Zod end-to-end, RBAC verified, error boundaries ovunque, verification-before-completion.

---

## 0. Context & Scope Decisions

### 0.0 Portal URL convention (clarification)

CLAUDE.md §10 Resources elenca `my.balizero.com` come portal subdomain. Tutto il codice in `apps/mouth/src/app/portal/` è servito attraverso:

- `my.balizero.com` (canonico, via Vercel rewrites/middleware)
- `balizero.com/portal` (legacy path, probabilmente rewrite o alias)

Nel design **uso path-relativi `/portal/...`** perché:

- Funzionano identici su entrambi gli host
- `permanentRedirect('/portal/login-upgraded')` in Next resolve correctly per entrambi
- I consumatori (email, link esterni) tipicamente usano `my.balizero.com/...` senza `/portal` prefix oppure `balizero.com/portal/...`

**Audit §1.1 verifica** quale delle due convention domina i link esterni; se `my.balizero.com` (no `/portal` prefix nelle URL pubbliche), il `login/` vs `login-upgraded/` scelgo logica equivalente. Non cambia l'implementazione del redirect interno.

### 0.1 Branch strategy (decision D, scope-reduced)

Il worktree esistente `.worktrees/v2-client-app` contiene lavoro portal non-merged (dashboard hero cards, family adult/minor split, /portal/matters, notification prefs, iCal export, WA watchdog, ContextPanel chat). Non rifacciamo quel lavoro. Scope PF1 ridotto a **4 obiettivi** ad alto ROI + bassa sovrapposizione con `v2-client-app`:

- S1: **Login unification** (login vs login-upgraded → redirect 308)
- S2: **Process pages hardening** (timeline verticale con drawer)
- S3: **Vault UX** (sidebar, iframe PDF preview, drag-drop upload, search)
- S4: **Settings consolidation** (tab Account / Security / Notifications / Privacy / Language)

**Esclusi esplicitamente** da PF1 (delegati PF2/PF3):

- Dashboard redesign (fatto in v2-client-app, in attesa merge)
- Family validation (fatto in v2-client-app)
- Messages push (dipende backend)
- Billing clarity (dipende backend invoice endpoints)
- a11y/perf/i18n global pass (post-merge v2-client-app)

### 0.2 Commit plan

Approccio 2 (1 PR, 4 commit atomici):

1. `feat(portal): unify login — 308 legacy redirect with open-redirect guard, harden error states i18n, forgot-password flow`
2. `feat(portal): process timeline vertical — state machine visual, step detail drawer, blocked state CTA`
3. `feat(portal): vault UX — sidebar organization, iframe PDF preview with sandbox, drag-drop upload with scan status, search`
4. `feat(portal): settings tabs — account, security (password+2FA+sessions), notifications matrix, privacy, language switcher`

Commit backend aggiuntivi (se audit pre-impl rivela endpoint mancanti critici) vanno **prima** del commit frontend che li consuma, con prefisso `feat(api):` o `feat(portal-api):`.

### 0.3 Invarianti duri

- **RBAC**: cliente vede SOLO own data. Backend enforcement + frontend graceful 404.
- **SSO cookie `.balizero.com`**: non tocco middleware auth esistente.
- **Design tokens**: read-only da `packages/core/styles/bz-tokens.css`. Se mancano `--bz-danger/warning/success`, uso constants locali in `components/portal/.../colors.ts` con TODO tracciato — non aggiungo token a `packages/core` (scope fuori).
- **BZLogo**: riusato da `packages/core/components/BZLogo.tsx`, nessun logo custom.
- **Immagini**: `next/image` sempre, mai `<img>`.
- **i18n 3 lingue**: IT/EN/ID per tutte stringhe visibili.
- **Deploy env `NEXT_PUBLIC_*`**: via `git push`, mai `vercel --prod`.
- **Email**: mai SMTP diretto, sempre `/api/notifications/send-email` con `zantara@balizero.com`.
- **No touch**: `app/(workspace)/`, `app/chat/`, `app/(marketing|blog|book|visa-oracle)/`, `packages/core/`.

---

## 1. Pre-Implementation Audit Checklist (OBBLIGATORIO)

Prima di toccare codice applicativo, eseguo audit seguenti. Ogni finding documentato in commento commit o, se strutturale, in issue GitHub.

### 1.1 Login (S1)

- [ ] Read full `apps/mouth/src/app/portal/login/page.tsx` + `login-upgraded/page.tsx` — confermo quale è canonica o se identiche (grep iniziale suggerisce duplicazione/re-export)
- [ ] Grep tutti i link a `/portal/login` in: `apps/mouth`, `apps/kita`, `apps/funnel*`, email templates, docs, README — lista consumatori
- [ ] Grep backend endpoint auth: `/api/auth/password-reset-request`, `/api/auth/verify-reset-token`, `/api/auth/reset-password`
- [ ] Check middleware `/portal/*` per gestione `?redirect=` query param preservation
- [ ] Verifica `api.getProfile()` fallback cookie-based (commit 2026-03-22, memory) resta intatto

### 1.2 Process (S2)

- [ ] Read `/portal/(authenticated)/process/page.tsx` attuale — capire struttura, data source, eventuali sub-routes esistenti
- [ ] Grep backend endpoint: `/api/portal/practices`, `/api/portal/practice-steps`, `/api/portal/process`, `/api/portal/me/practices`
- [ ] Grep state machine: definizione stati in `apps/backend-rag/**/practice*.py` o migrations (stati `pending/in_progress/blocked/waiting_client/completed` + extra m087)
- [ ] Verifica nome reale stato m087 (memory dice `+1 extra m087` ma nome esatto da codice)
- [ ] Grep semantic tokens in `packages/core/styles/bz-tokens.css`: `--bz-danger`, `--bz-warning`, `--bz-success`
- [ ] Grep dialog/drawer deps esistenti: `@radix-ui/react-dialog`, `@headlessui/react` in `apps/mouth/package.json`

### 1.3 Vault (S3)

- [ ] Read `/portal/(authenticated)/vault/page.tsx` attuale — data source, schema, componenti
- [ ] Grep backend endpoint: `/api/portal/vault`, `/api/portal/documents`, `/api/portal/files`
- [ ] Check Drive integration: `folder_id` per cliente (memory `CRM Drive Population ✅`), Drive `/preview` URL iframe-ability
- [ ] Grep endpoint upload: `/api/portal/documents/upload` — multipart? presigned? chunked?
- [ ] Grep virus scan: `scan_status`, `ClamAV`, `virustotal` in backend
- [ ] Grep `react-virtual`, `react-window`, `fuse.js` in `apps/mouth/package.json`

### 1.4 Settings (S4)

- [ ] Read `/portal/(authenticated)/settings/page.tsx` + eventuali sub-routes — inventario setting sparsi
- [ ] Grep backend endpoint: `/api/portal/me`, `/api/portal/me/password`, `/api/portal/me/2fa`, `/api/portal/me/notifications`, `/api/portal/me/language`, `/api/portal/me/sessions`
- [ ] Check 2FA: TOTP enrollment endpoint? QR code? backup codes? (se assente, mostro TODO placeholder, non fake-implemento)
- [ ] Grep notification prefs schema (v2-client-app branch ha già lavoro qui — NON lo riuso, ma verifico schema BE per coerenza)
- [ ] Check endpoint export dati / account deletion (UU PDP — memory)
- [ ] Grep tabs deps: `@radix-ui/react-tabs` o equivalente

### 1.5 Shared audit

- [ ] Dev server boot check: `cd apps/mouth && npm run dev` parte senza errore
- [ ] TypeScript baseline: `npx tsc --noEmit` su `apps/mouth/` zero errori nuovi introdotti
- [ ] Lint baseline: `npm run lint` apps/mouth no warning nuovi
- [ ] Package audit: `next/image`, `swr`, `zod`, `react-hook-form`, `lucide-react` già in deps
- [ ] i18n infra: dove stanno `it.json|en.json|id.json`? Loader? Hook (`useTranslation`)?

**Blocker rule**: se audit rivela che implementazione robusta richiede change DB/migration/schema BE esteso, **fermo** e chiedo conferma utente prima di procedere. Non infilo migrations in PR frontend.

**Backend env note (se creo endpoint FastAPI)**: siamo su **Pro** → venv path `apps/backend-rag/.venv` (NON `venv`, vedi CLAUDE.md §14 — Air usa `venv`, Pro usa `.venv`). Test: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/...`

**Import chain invariant** (CLAUDE.md Pre-Deploy §11): dopo qualsiasi change in `backend/app/`, validare con `python -c "from backend.app.dependencies import get_current_user; print('OK')"` prima di committare.

---

## 2. Sezione 1 — Login Unification

### 2.1 Target

Eliminare duplicazione `login/` vs `login-upgraded/`, rendere canonica, hardenare error states, flusso forgot-password (o fallback mailto).

### 2.2 Implementazione

**`apps/mouth/src/app/portal/login/page.tsx`** (riscritto):

```tsx
import { permanentRedirect } from "next/navigation";

const ALLOWED_REDIRECT_PREFIXES = ["/portal/", "/workspace/"];

function sanitizeRedirect(raw: string | undefined): string | null {
  if (!raw) return null;
  // Blocca protocol-relative e absolute URL
  if (raw.startsWith("//") || /^[a-z][a-z0-9+.-]*:/i.test(raw)) return null;
  // Blocca backslash tricks
  if (raw.includes("\\")) return null;
  // Normalizza
  if (!raw.startsWith("/")) return null;
  // Allowlist prefix
  if (!ALLOWED_REDIRECT_PREFIXES.some((p) => raw.startsWith(p))) return null;
  return raw;
}

export default function LegacyLoginRedirect({
  searchParams,
}: {
  searchParams: { redirect?: string };
}) {
  const safe = sanitizeRedirect(searchParams.redirect);
  const qs = safe ? `?redirect=${encodeURIComponent(safe)}` : "";
  permanentRedirect(`/portal/login-upgraded${qs}`);
}
```

**`login-upgraded/page.tsx`**: audit + hardening error states:

- Tutti error message i18n keys `portal.login.errors.*`
- Rate-limit: parse `Retry-After` header, countdown UI
- Password strength meter rimosso dal login (non ha senso), spostato in register e password-change (S4)

### 2.3 Forgot Password

Condizionale all'audit:

**Caso A — endpoint backend esistono**:

- `apps/mouth/src/app/portal/forgot-password/page.tsx` — form email → POST `/api/auth/password-reset-request` → sempre risponde 200 generico "Se l'email esiste, riceverai un link" (no enumeration)
- `apps/mouth/src/app/portal/reset-password/[token]/page.tsx` — form 2 password (new+confirm), valida token via `/api/auth/verify-reset-token`, submit → `/api/auth/reset-password`

**Caso B — endpoint mancano**:

- Link login-upgraded "Password dimenticata?" apre `mailto:team@balizero.com?subject=Password%20Reset&body=Richiedo%20reset%20password%20per%20<email>`
- Commento TODO in codice + issue GitHub (via `gh issue create`) aperta a parte (non blocco sessione)

### 2.4 i18n keys nuove

```json
{
  "portal.login.errors.invalid_credentials": "Email o password non corretti. Riprova.",
  "portal.login.errors.account_locked": "Account bloccato per sicurezza. Contatta team@balizero.com.",
  "portal.login.errors.rate_limited": "Troppi tentativi. Riprova tra {seconds} secondi.",
  "portal.login.errors.invalid_2fa": "Codice 2FA non valido.",
  "portal.login.errors.network_error": "Connessione persa. Verifica la rete e riprova.",
  "portal.login.errors.email_not_found": "Email non trovata.",
  "portal.login.errors.server_error": "Errore del server. Riprova tra qualche minuto.",
  "portal.login.errors.maintenance": "Manutenzione in corso. Torna più tardi.",
  "portal.login.forgot_password": "Password dimenticata?",
  "portal.forgot_password.title": "Recupera password",
  "portal.forgot_password.sent": "Se l'email è registrata, riceverai un link di reset."
}
```

(EN e ID analoghe).

### 2.5 Testing

- **Unit**: `sanitizeRedirect` con 10+ casi (open-redirect, protocol-relative, backslash, valid, empty, null, absolute http, javascript:, data:, relative senza slash, path traversal `../`)
- **Unit**: `LegacyLoginRedirect` chiama `permanentRedirect` con URL corretto (mock `next/navigation`)
- **Unit**: login-upgraded error rendering per ogni `error_code` in mock response
- **Integration MSW**: login happy path, 401 → invalid_credentials, 429 → rate_limited con countdown, 503 → maintenance
- **Manual**: dev server, `/portal/login?redirect=/portal/dashboard` → URL finale `/portal/login-upgraded?redirect=%2Fportal%2Fdashboard`, cookie SSO preservato, 3 error scenarios
- **Security**: open-redirect test `?redirect=//evil.com`, `?redirect=javascript:alert(1)`, `?redirect=/portal/../workspace/admin`

### 2.6 Commit

`feat(portal): unify login — 308 legacy redirect with open-redirect guard, harden error states i18n, forgot-password flow`

---

## 3. Sezione 2 — Process Timeline Verticale

### 3.1 Target

Trasformare `/portal/(authenticated)/process/` da lista testuale a timeline verticale con card inline, drawer dettagli, blocked state CTA.

### 3.2 Architettura

```
/portal/(authenticated)/process/page.tsx            — lista practice attive (card compatte, link a detail)
/portal/(authenticated)/process/[practiceId]/page.tsx — detail con timeline verticale

components/portal/process/
  ├─ ProcessTimeline.tsx         — wrapper, linea verticale + dot
  ├─ TimelineStep.tsx             — card: titolo, stato badge, assignee, date, docs count
  ├─ StepDetailDrawer.tsx         — right slide-in, focus trap, ESC close
  ├─ StateBadge.tsx               — badge riusabile, colori semantici
  ├─ BlockedStateCTA.tsx          — alert + CTA "Contatta team"
  ├─ ProcessErrorBoundary.tsx     — cattura render errors
  ├─ TimelineSkeleton.tsx         — loading state deterministic
  └─ stateColors.ts               — costanti colore (fallback se bz-tokens mancano)

hooks/
  └─ useProcessSteps.ts           — SWR + Zod parse

lib/schemas/
  └─ process.ts                   — Zod schemas
```

### 3.3 Data layer (Zod-first)

```ts
// lib/schemas/process.ts
import { z } from "zod";

export const ProcessStepState = z.enum([
  "pending",
  "in_progress",
  "blocked",
  "waiting_client",
  "completed",
  // + stato m087 (nome esatto da audit BE)
]);
export type ProcessStepState = z.infer<typeof ProcessStepState>;

export const AssignedTeamMember = z.object({
  id: z.string(),
  name: z.string(),
  avatar_url: z.string().url().nullable(),
  role: z.string().nullable(),
});

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

export const ProcessStepsResponse = z.object({
  version: z.literal(1),
  practice_id: z.string(),
  steps: z.array(ProcessStep),
});
```

**Hook**:

```ts
// hooks/useProcessSteps.ts
export function useProcessSteps(practiceId: string) {
  return useSWR(
    practiceId ? ["portal-process-steps", practiceId] : null,
    async () => {
      const res = await api.get(`/api/portal/practices/${practiceId}/steps`);
      return ProcessStepsResponse.parse(res.data);
    },
    {
      revalidateOnFocus: true,
      shouldRetryOnError: (err) => err.status >= 500,
      onError: (err) => logger.error("process-steps-fetch", err),
    },
  );
}
```

Schema drift (Zod parse fail) → errore strutturato → UI mostra fallback generico "Impossibile caricare i dettagli. Team notificato." + log.

### 3.4 Backend endpoint (se audit rivela assenza)

```
GET /api/portal/practices/{practice_id}/steps
  Auth: Depends(verify_portal_client)
  RBAC: SELECT * FROM practices WHERE id=$1 AND client_id=$cookie_client_id
  404 se non esiste o non appartiene al client (anti-IDOR, no 403)
  Response: { version: 1, practice_id, steps: [...] }
  Error shape: { error: { code, message } }
```

Pytest: 4 casi (happy, 404 not-mine, 404 not-exist, 401 no-auth).

**File location** (CLAUDE.md §5): router sta in `apps/backend-rag/backend/app/routers/portal.py` (o file esistente se c'è già un `portal_*` router), NON in `backend/routers/`. Registrare in `backend/app/setup/router_registration.py` se nuovo file.

**Cache invalidation** (CLAUDE.md §14): dopo qualsiasi mutation endpoint (es. carica doc che cambia step state), `await invalidate_cache("zantara:portal_practice_steps:*")`. Per GET non serve.

**Async I/O** (Golden Rule 4+10): usa `httpx.AsyncClient` persistente, NON `requests`, NON `httpx.AsyncClient()` in-loop. Query DB via pattern esistente (BaseRepository / connection pool S07).

### 3.5 Colori stati

`components/portal/process/stateColors.ts`:

```ts
// TODO(shared-tokens): move to packages/core/styles/bz-tokens.css when --bz-danger|warning|success land (#<issue>)
export const STATE_COLORS: Record<
  ProcessStepState,
  { bg: string; fg: string; border: string }
> = {
  pending: {
    bg: "var(--bz-muted-bg, #2a2a2d)",
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

Uso `var(--*, fallback)` così quando i token arrivano in `packages/core`, il codice si allinea automaticamente senza refactor.

### 3.6 Drawer (a11y)

- Radix Dialog se `@radix-ui/react-dialog` già in deps (da audit)
- Focus trap, ESC close, click outside close, scroll-lock body
- `role="dialog"`, `aria-labelledby`, `aria-describedby`
- Mobile: full-screen modal; desktop ≥1024px: slide-in da destra 480px

### 3.7 Error & edge cases

- `practiceId` invalid/404 → redirect `/portal/process` + toast "Pratica non trovata"
- Loading → `<TimelineSkeleton count={3} />`
- Empty → "Nessuna pratica attiva. Contatta il team per avviarne una."
- Stato unknown (non in enum Zod) → parse fail → error boundary → fallback UI
- `assigned_to === null` → "Non ancora assegnato"
- `estimated_completion === null` → "Da definire"
- Date parse fail → `—`
- Timeline vuota ma valida → "Questa pratica non ha ancora step. Il team li creerà a breve."

### 3.8 Testing

- **Unit** (Vitest): 15 test
  - `StateBadge`: render per ogni stato + unknown fallback
  - `TimelineStep`: click, keyboard (Enter/Space), aria, date formatting
  - `StepDetailDrawer`: focus trap, ESC, outside click, aria
  - `useProcessSteps`: success, 404, 500, schema drift
  - `BlockedStateCTA`: href corretto, i18n keys
  - `ProcessErrorBoundary`: cattura render error
  - `stateColors`: exhaustive map (compile-time assertion)
- **Integration MSW**: timeline load + drawer open + retry
- **Backend pytest** (se creo endpoint): 4 casi RBAC
- **Manual**: dev server, golden path + 3 edge (404, network error, empty), Lighthouse mobile ≥85
- **RBAC manual**: cross-user check (vietato vedere practice altrui via URL guess)

### 3.9 Commit

`feat(portal): process timeline vertical — state machine visual, step detail drawer, blocked state CTA`

---

## 4. Sezione 3 — Vault UX

### 4.1 Target

Sidebar organizzata (practice/categoria), iframe PDF preview sandboxed, drag-drop upload con scan-status, search client-side.

### 4.2 Architettura

```
/portal/(authenticated)/vault/page.tsx
  └─ <VaultLayout>
      ├─ <VaultSidebar practices categories onFilter />         — left, mobile=bottom sheet
      ├─ <VaultFileGrid files={filtered} onSelect />             — center
      ├─ <VaultPreviewPane file={selected} />                    — right, iframe/fallback
      ├─ <VaultUploadZone onUpload />                            — floating + drag overlay
      ├─ <VaultSearchBar query onChange debounced=200ms />       — top
      └─ <VaultErrorBoundary />                                  — wrapper

components/portal/vault/
  ├─ VaultLayout.tsx
  ├─ VaultSidebar.tsx
  ├─ VaultFileGrid.tsx
  ├─ VaultPreviewPane.tsx
  ├─ VaultUploadZone.tsx
  ├─ VaultSearchBar.tsx
  ├─ VaultErrorBoundary.tsx
  ├─ vaultMimeAllowlist.ts
  └─ vaultFilename.ts              — sanitize

hooks/
  ├─ useVaultFiles.ts               — SWR + Zod
  ├─ useVaultUpload.ts              — XHR progress + retry + scan poll
  └─ useVaultScanStatus.ts          — poll scan until terminal

lib/schemas/
  └─ vault.ts
```

### 4.3 Data layer

```ts
// lib/schemas/vault.ts
export const VaultScanStatus = z.enum([
  "pending",
  "clean",
  "infected",
  "error",
]);

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

export const VaultListResponse = z.object({
  version: z.literal(1),
  files: z.array(VaultFile),
  total: z.number().int(),
});
```

### 4.4 Upload robusto

**`vaultMimeAllowlist.ts`**:

```ts
export const ALLOWED_MIMES = [
  "application/pdf",
  "image/jpeg",
  "image/png",
  "image/webp",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/msword",
  "application/vnd.ms-excel",
] as const;
export const MAX_SIZE_BYTES = Number(
  process.env.NEXT_PUBLIC_VAULT_MAX_SIZE ?? 20 * 1024 * 1024,
);
```

**`vaultFilename.ts`**:

```ts
export function sanitizeFilename(raw: string): string {
  return raw
    .replace(/[\/\\]/g, "_") // path separators
    .replace(/\.\./g, "_") // traversal
    .replace(/[<>:"|?*\x00-\x1f]/g, "_") // special + control
    .slice(0, 240); // name length cap
}
```

**Upload hook** (`useVaultUpload.ts`):

- XHR per `upload.onprogress` (fetch non supporta)
- Controlli pre-upload: size cap, mime allowlist, filename sanitize
- Retry con backoff exp (base 1s, max 3 tentativi) su 5xx
- Dopo upload success → avvia poll scan-status
- Return `{ progress, status, error, result }`

**Scan poll** (`useVaultScanStatus.ts`):

- Poll `/api/portal/documents/{id}/scan-status` ogni 2s
- Stop su: `clean`, `infected`, `error`, timeout 60s
- Se `infected`: toast rosso + nasconde file dalla grid + log
- Se timeout: toast "Scan in corso, ricontrolla tra qualche minuto"

### 4.5 Preview iframe sandbox

```tsx
<iframe
  src={file.preview_url}
  sandbox="allow-scripts allow-same-origin"
  referrerPolicy="no-referrer"
  title={`Anteprima ${file.name}`}
  loading="lazy"
  onError={handleIframeError}
/>
```

- Solo se `preview_url !== null` AND `mime_type ∈ {pdf, jpeg, png, webp}`
- Fallback (DOCX, XLSX, mime non supportati): card icona + "Scarica per visualizzare" + CTA download
- `onError`: retry 1 volta, poi fallback card
- Loading: skeleton box

### 4.6 Search & filter

- Sidebar: checkbox per practice, checkbox per category (multi-select), count per gruppo
- Search bar: substring case-insensitive su `name`, `category`, `practice_title` (Fuse.js solo se già in deps)
- Debounce 200ms, `role="searchbox"`, live region count
- Empty results: "Nessun file corrisponde a '{query}'."

### 4.7 Virtualization

- `react-virtual` solo se già in deps
- Altrimenti: grid normale CSS, funziona fino ~500 file; sopra → TODO paginazione server-side

### 4.8 RBAC

- Backend filtra per client_id da cookie
- Upload: `practice_id` nel body verificato contro client_id del cookie (anti-IDOR)
- Download/preview URL: presigned o proxied, MAI diretto Drive link pubblico
- Cross-user test manuale

### 4.9 Error paths

- Network → banner + retry
- 413 payload too large → toast max size
- 415 unsupported media → toast formati accettati
- 401 → redirect login (middleware)
- Drive quota full → toast "Spazio esaurito, contatta team"
- Scan timeout → toast "Ricontrolla tra qualche minuto"

### 4.10 Accessibility

- File grid: frecce arrow (row/col), Enter selezione, Tab esce
- Drop zone: `aria-label`, fallback click, `aria-describedby` hint
- Preview iframe: `title` obbligatorio
- Search: `role="searchbox"`, `aria-live="polite"` per results count

### 4.11 Testing

- **Unit**: sanitizeFilename (10 casi adversarial), mime allowlist, size cap, Zod schema
- **Component**: upload success/fail/progress, preview render pdf/image/fallback, search filter, sidebar filter multi-select
- **Integration MSW**: full flow upload → poll scan clean → display; upload → scan infected → hide
- **Manual**: dev server, upload 5 file types (PDF ok, PNG ok, DOCX ok fallback, SVG bloccato, 50MB bloccato), network 3G, RBAC cross-user
- **Security**: XSS filename, iframe sandbox bypass test, SVG XSS bloccato

### 4.12 Commit

`feat(portal): vault UX — sidebar organization, iframe PDF preview with sandbox, drag-drop upload with scan status, search`

---

## 5. Sezione 4 — Settings Consolidation

### 5.1 Target

5 tab organizzati: Account / Security / Notifications / Privacy / Language. URL-synced, mobile=accordion.

### 5.2 Architettura

```
/portal/(authenticated)/settings/page.tsx
  └─ <SettingsTabs defaultTab="account" urlParam="tab">
      ├─ <AccountSettings />
      ├─ <SecuritySettings />
      ├─ <NotificationSettings />
      ├─ <PrivacySettings />
      └─ <LanguageSettings />

components/portal/settings/
  ├─ SettingsTabs.tsx           — Radix Tabs o headless, URL-synced
  ├─ AccountSettings.tsx
  ├─ SecuritySettings.tsx
  │   ├─ PasswordChangeForm.tsx
  │   ├─ TwoFactorPanel.tsx     — TOTP enroll/disable (condizionale BE)
  │   └─ SessionsPanel.tsx      — lista sessioni + revoke (condizionale BE)
  ├─ NotificationSettings.tsx   — matrix channel×event
  ├─ PrivacySettings.tsx        — export/delete (UU PDP)
  ├─ LanguageSettings.tsx
  └─ PasswordStrengthMeter.tsx

hooks/
  ├─ useMe.ts                   — SWR profilo utente
  ├─ usePasswordChange.ts
  ├─ use2FA.ts                  — enroll/verify/disable
  ├─ useSessions.ts             — list + revoke
  ├─ useNotificationPrefs.ts
  └─ useLanguage.ts             — cookie + BE sync

lib/schemas/settings.ts
```

### 5.3 Data layer

```ts
// lib/schemas/settings.ts
export const UserProfile = z.object({
  id: z.string(),
  email: z.string().email(),
  name: z.string(),
  avatar_url: z.string().url().nullable(),
  language: z.enum(["it", "en", "id"]),
  created_at: z.string().datetime(),
  two_factor_enabled: z.boolean(),
  email_verified: z.boolean(),
});

export const NotificationChannel = z.enum([
  "email",
  "push",
  "telegram",
  "whatsapp",
]);
export const NotificationEvent = z.enum([
  "practice_update",
  "deadline_reminder",
  "new_message",
  "billing_reminder",
  "security_alert",
]);
export const NotificationPref = z.record(
  NotificationEvent,
  z.record(NotificationChannel, z.boolean()),
);
```

### 5.4 Tab Account

- Form: `name`, `avatar_url` (via upload endpoint), `email` readonly
- Zod + react-hook-form
- Optimistic UI + rollback on error
- Toast "Salvato"

### 5.5 Tab Security

**Password change**:

- Form: current_password, new_password, confirm_password
- Strength meter (`PasswordStrengthMeter`): se `zxcvbn` in deps lo uso, altrimenti regole base (length ≥12, 3 di 4 class)
- Submit → `/api/portal/me/password` → handle 401 (current wrong), 429 (rate limit), 422 (weak)
- Success → toast + logout altri dispositivi (prompt)

**2FA** (condizionale audit):

- Se BE supporta:
  - Disabilitato → CTA "Abilita 2FA" → fetch `/api/portal/me/2fa/enroll` → QR code (data URL) + secret text + backup codes (mostra una volta, download .txt) → form verifica codice TOTP → attiva
  - Abilitato → CTA "Disabilita" → richiede password + codice TOTP corrente → conferma → disabilita
- Se BE NON supporta: placeholder "2FA in arrivo" + issue GitHub, no fake flow

**Sessions** (condizionale audit):

- Se BE `/api/portal/me/sessions` esiste: lista (device UA parsed, last_seen, IP masked `192.168.*.*`, current badge) + CTA "Revoca tutte le altre" → `/api/portal/me/sessions/revoke-others`
- Se non esiste: placeholder

### 5.6 Tab Notifications

- Matrix UI: righe = event, colonne = channel, celle = checkbox
- Salvataggio debounced 500ms on-change (non bottone esplicito)
- Se channel Push: verifica `Notification.permission`. Se `default` → CTA "Autorizza notifiche". Se `denied` → mostra istruzioni browser
- Telegram: se user non ha linked Telegram, mostra CTA "Collega account Telegram" (link a bot) + disable colonna

### 5.7 Tab Privacy

- **Export dati** (UU PDP): CTA "Richiedi export" → `/api/portal/me/data-export` se esiste, altrimenti mailto fallback
- **Elimina account**: CTA rosso + modal conferma (digita "ELIMINA" + password + 2FA se attivo) → `/api/portal/me/delete` o ticket team
- Link privacy policy
- Cookie/tracking prefs se applicabile

### 5.8 Tab Language

- Radio IT/EN/ID, label in ogni lingua
- Cambio: `i18next.changeLanguage(lang)` + cookie `.balizero.com` `preferred_language=lang` + POST `/api/portal/me/language` (sync cross-device)
- Re-render immediato, no reload

### 5.9 Error handling globale settings

- 400 validation → errori field-level (react-hook-form)
- 401 → silent refresh; se fail → redirect login
- 403 (step-up auth required) → modal 2FA inline
- 409 conflict → toast "Dati aggiornati altrove, ricarica"
- 500 → toast generic + retry
- Unsaved changes warning: `beforeunload` se dirty form

### 5.10 Accessibility

- Tabs keyboard (Radix gestisce: Arrow L/R, Home, End)
- Form labels esplicite, errori `aria-describedby`
- Strength meter `aria-live="polite"`, `aria-valuenow`, `aria-valuemax`
- Focus management: al cambio tab, focus al primo input
- Mobile: accordion fallback con `aria-expanded`

### 5.11 Testing

- **Unit**: ogni Zod schema, strength meter edge cases, sanitization password, language cookie write
- **Component**: tab switching preserva URL, dirty warning, password change form flow, 2FA enroll mock, notification matrix save
- **Integration MSW**: full password change, 2FA enroll happy + wrong code, language switch cross-tab sync
- **Security**: password not logged, 2FA secret mai in localStorage (solo durante enroll in memoria), CSRF token su mutation, backup codes generate una volta sola
- **Manual**: 5 tab golden path + 5 error scenarios
- **i18n smoke**: switch IT→EN→ID, verifica strings cambiano ovunque

### 5.12 Commit

`feat(portal): settings tabs — account, security (password+2FA+sessions), notifications matrix, privacy, language switcher`

---

## 6. Cross-Cutting Concerns

### 6.1 Performance

- Tutti i componenti heavy dynamic import: `StepDetailDrawer`, `VaultPreviewPane`, `TwoFactorPanel`, `PasswordStrengthMeter`
- `next/image` per avatar + icone raster
- SWR con `revalidateOnFocus: true`, `dedupingInterval: 2000`
- Bundle budget: ogni PR misura `npm run build` size delta, soglia allerta +50KB initial

### 6.2 Observability

- `logger.error|warn|info` su ogni error boundary catch, Zod parse fail, network retry
- Sentry (se in bundle) con tag `scope: portal`, `section: login|process|vault|settings`
- No PII in log (password, token, email) — solo `client_id_hash`, `request_id`

### 6.3 i18n infrastructure

- Tutte chiavi nuove in `apps/mouth/src/i18n/it.json|en.json|id.json`
- Namespace per sezione: `portal.login.*`, `portal.process.*`, `portal.vault.*`, `portal.settings.*`
- Script CI (futuro) per detect hardcoded strings (TODO: rimando a PF sessione i18n dedicata)

### 6.4 RBAC invariante globale

- **Backend enforcement sempre**: cookie → client_id, query su DB sempre filtrata
- **Frontend graceful**: 404 backend → "non trovato" UI, mai crash, mai dump
- **Manual test cross-user**: login come user A, URL guess risorse user B, verifica 404

### 6.5 Security checklist pre-PR

- [ ] No secrets in repo
- [ ] No `dangerouslySetInnerHTML` senza sanitize
- [ ] iframe sempre sandboxed
- [ ] Upload: mime+size+filename enforced
- [ ] Open-redirect allowlist
- [ ] CSRF: token/cookie SameSite
- [ ] 2FA secret mai persistito client-side
- [ ] Password mai loggato (anche in error boundary)

### 6.6 Verification-before-completion (da skill)

Prima di ogni claim "done":

- `cd apps/mouth && npm run dev` dev server boot senza errore
- `npm run build` success
- `npx tsc --noEmit` zero errori nuovi
- `npm run lint` zero warning nuovi
- `npm test` tutti test green
- Manual golden path: ogni sezione dev server + browser, screenshot before/after
- Lighthouse mobile spot check per sezione ≥80

---

## 7. Work Plan — Execution Order

1. **Audit** (§1, obbligatorio) — 20 min
2. **Worktree + baseline screenshot** — 10 min
3. **S1 Login** — 30 min (più semplice, sblocca test surface)
4. **S2 Process** — 50 min (più complesso, potenziale BE endpoint)
5. **S3 Vault** — 50 min (upload + preview + scan)
6. **S4 Settings** — 40 min (5 tab, condizionale 2FA)
7. **Cross-cutting**: screenshot after, i18n review, lint/type/test finale — 20 min
8. **PR**: `feat(portal): client-app L2 redesign — login unify, process timeline, vault UX, settings tabs`

Tempo stimato totale ~220 min. Se audit rivela backend endpoint mancanti critici (S2 steps endpoint, S4 2FA), tempo +30-60 min → potenzialmente taglio S4 2FA/sessions a placeholder.

---

## 8. Open Questions / Deferred

- **m087 stato**: nome esatto da codice backend, non da memoria. Audit §1.2 lo identifica.
- **Drive preview URL iframe-ability**: se Drive richiede auth interattiva per `/preview`, cerco endpoint proxy backend. Fallback: download-only UX.
- **2FA/Sessions backend**: se assenti, placeholder con issue, non fake-implemento.
- **Forgot-password backend**: idem, mailto fallback.
- **Push notification service worker**: non implemento in PF1 (scope creep), solo permission prompt UX in S4 Notifications.

---

## 9. Success Criteria

Definition of Done per PF1:

- [ ] 4 commit atomici in branch `pro/frontend-portal-client-app` off main
- [ ] Audit §1 completato, findings documentati
- [ ] Backend endpoint eventuali creati con pytest RBAC 4-casi (commit separato)
- [ ] Tutti unit + integration test green (target ≥40 test nuovi totali)
- [ ] `npm run build` success, TypeScript zero nuovi errori, lint zero nuovi warning
- [ ] Dev server boot, manual golden path OK per 4 sezioni
- [ ] Screenshot before/after per ogni sezione
- [ ] Lighthouse mobile ≥80 spot check
- [ ] Security checklist §6.5 tutti tick
- [ ] i18n IT/EN/ID chiavi nuove popolate in tutte 3 lingue
- [ ] PR description strutturata per sezione con screenshot
- [ ] Nessun tocco a scope Air F1/F2/F3 + packages/core
- [ ] RBAC cross-user manual test OK (4 sezioni)

---

## 9a. Scope Boundary — Explicit Non-Goals

Per evitare scope creep durante l'implementazione:

- **NOT**: push service worker implementation (solo permission prompt in S4)
- **NOT**: nuove Alembic migrations (blocker rule §1)
- **NOT**: refactor `packages/core/` (read-only)
- **NOT**: tocco a `(workspace)/`, `chat/`, `(marketing)/`, `(blog)/`, `(book)/`, `(visa-oracle)/`
- **NOT**: design token additions a `packages/core/styles/bz-tokens.css`
- **NOT**: modifica middleware auth / SSO cookie logic
- **NOT**: implementazione fake flows (2FA fake UX, sessions fake list): se BE non supporta, placeholder + issue
- **NOT**: change `zantara_core.py` o altri prompt SSOT
- **NOT**: touch `fly.toml`, `.env*`, `alembic/env.py`

---

## 10. Rollback Strategy

Se post-deploy emerge regressione:

- PR unica + 4 commit atomici permette `git revert <sha>` chirurgico per sezione
- Login redirect 308: rollback = ripristina file originale `login/page.tsx` (un commit revert)
- Process/Vault/Settings: dynamic import garantisce che un componente broken non sbriciola il resto dell'app (error boundary)
- Flag feature: NO (overhead non giustificato; preferisco revert granulare)
