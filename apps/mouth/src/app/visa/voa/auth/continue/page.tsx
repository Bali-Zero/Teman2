import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { isGarudaVoaPublicEnabled } from "../../flag";
import { PENDING_COOKIE, decodePending } from "../contract";

/**
 * `/visa/voa/auth/continue` — the one page of the magic-link flow a human
 * sees. `../route.ts` has already taken the token out of the URL and put it
 * in an HttpOnly cookie, so NOTHING here — not the URL, not the DOM, not the
 * form — carries the credential. That matters because this page, like every
 * page in this app, inherits `<GoogleAnalytics>` and `<RouteChangeTracker>`
 * from the root layout, and both send the full `window.location.href` to
 * Google.
 *
 * NOTHING IS REDEEMED ON GET. The token is single-use: a replay under a new
 * Idempotency-Key is rejected, and a replay under the same key returns 204
 * with no second `Set-Cookie`, so whoever arrives second gets no session
 * either way. Mail scanners (Gmail, Safe Links, chat preview bots) routinely
 * GET an emailed link before any human clicks — and they follow redirects, so
 * this page is reachable by a scanner too. Redemption happens only on the
 * POST. That is not the same as proof of a human gesture (see
 * `exchange/route.ts`); what it guarantees is that no PASSIVE fetch spends
 * the token.
 *
 * The form carries NO fields: both the token and the result id it was issued
 * for live in the one HttpOnly cookie, bound together. It is plain HTML with
 * no client component on purpose — there is no value for JavaScript to read,
 * and none to leak.
 *
 * CLOSED 2026-08-29 (this revision): the residual above described a generic
 * "Continue" behind an unbound landing GET as login CSRF — an attacker mails
 * a victim their OWN link, the victim clicks Continue, and the attacker's
 * session is planted in the victim's browser. `previewMagicLink` below calls
 * the backend's non-consuming `previewMagicLink` handler
 * (`apps/backend-rag/backend/app/routers/garuda_portal_auth.py`) to close
 * it: this page now shows WHOSE application the link opens, and refuses to
 * offer Continue at all when the lookup fails, rather than only discovering
 * a dead or foreign link by spending it. The fetch happens HERE, server-side
 * during render (not from a client component): the token never leaves this
 * process, and the page's own "no client component" property — nothing for
 * JavaScript to read or leak — is unaffected because nothing about this call
 * is reachable from the browser.
 */

function firstValue(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

/**
 * Shared by both failure exits below (a malformed/absent cookie, and a
 * cookie that decodes but whose token the preview lookup rejects). Kept
 * byte-identical between the two on purpose: DECISIONS.md Q1's
 * non-enumeration requirement is about the WIRE response, but a human
 * reading two different-looking "invalid" pages side by side could still
 * infer which failure class they hit.
 */
function InvalidLinkNotice() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-xl font-semibold">This link is no longer valid</h1>
      <p className="text-gray-600">
        Sign-in links expire and can only be used once. Please request a new one
        from your eligibility result page.
      </p>
    </main>
  );
}

/**
 * Mirrors `src/app/api/[...path]/route.ts`'s private `getBackendBaseUrl()`
 * (same two env vars, same fallback, same trailing-`/api` strip) rather than
 * importing it: that function is unexported, owned by a shared proxy file
 * outside this lane, and `../exchange/route.ts`'s own docstring already
 * explains why a Route Handler in THIS app instead bounces through its own
 * `/api/*` proxy path (it has a `NextRequest` to build a same-origin URL
 * from, and it needs the proxy to forward the upstream `Set-Cookie`). A
 * Server Component render has no `NextRequest`, and this call mints no
 * cookie to forward, so going straight to the backend is the smaller
 * surface, not a shortcut around either of that route's two stated reasons.
 */
function backendBaseUrl(): string {
  const raw =
    process.env.NUZANTARA_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "https://nuzantara-rag.fly.dev";
  return raw
    .trim()
    .replace(/\/+$/, "")
    .replace(/\/api$/, "");
}

/**
 * Calls `previewMagicLink` (backend, NOT part of the frozen GARUDA VOA
 * contract — see that handler's docstring) with the token this page already
 * decoded from the HttpOnly pending cookie. Returns the masked identifier on
 * success, or `null` for every failure shape alike (network error, non-200,
 * malformed body) — the caller must not distinguish WHY the lookup failed,
 * only whether it succeeded, to stay non-enumerating the same way the
 * backend's own 401 does.
 */
async function previewMagicLink(token: string): Promise<string | null> {
  try {
    const res = await fetch(
      `${backendBaseUrl()}/api/visa/voa/auth/magic-links/preview`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token }),
        cache: "no-store",
      },
    );
    if (!res.ok) return null;
    const body = (await res.json()) as { masked_email?: unknown };
    return typeof body.masked_email === "string" ? body.masked_email : null;
  } catch {
    return null;
  }
}

export default async function GarudaVoaAuthContinuePage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  // Defence in depth: `../../layout.tsx` already gates this, but a refactor
  // that moves this page out from under that layout must not silently open a
  // public surface while the rest of the funnel is dark.
  if (!isGarudaVoaPublicEnabled()) {
    notFound();
  }

  const failed = firstValue((await searchParams).error) !== undefined;

  // The cookie is the only thing that proves a token is in flight, and it
  // must decode to a well-formed pair. Without that there is nothing to
  // submit, so offering the button would be a lie.
  const pending = decodePending((await cookies()).get(PENDING_COOKIE)?.value);
  const ready = !failed && pending !== null;

  // Cookie-shape check ONLY -- fast, no network. It proves the cookie
  // decodes to a well-formed pair, not that the token the backend holds is
  // still live; the preview lookup below is what proves that.
  // The `pending === null` half of this condition is redundant with `ready`
  // at runtime (see its definition above) but not to the TYPE CHECKER: only
  // spelling it out here narrows `pending` to non-null for the
  // `pending.token` read below.
  if (!ready || pending === null) {
    return <InvalidLinkNotice />;
  }

  // Non-consuming: proves the token is still live AND says whose
  // application it opens, WITHOUT spending it (`MagicLinkStore.peek`,
  // backend). A link that expired or was already consumed between the
  // emailed redirect and this render is caught HERE -- refusing to offer
  // Continue -- instead of only being discovered by spending it.
  const maskedEmail = await previewMagicLink(pending.token);

  if (maskedEmail === null) {
    return <InvalidLinkNotice />;
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-6 p-6 text-center">
      <h1 className="text-xl font-semibold">Continue your application</h1>
      <p className="text-gray-600">
        You&apos;re one step from uploading your documents.
      </p>
      <p className="text-sm text-gray-500">
        This link opens the application for <strong>{maskedEmail}</strong>. If
        that is not you, close this page instead.
      </p>
      <form method="post" action="/visa/voa/auth/exchange">
        <button
          type="submit"
          className="rounded-md bg-black px-6 py-3 text-white"
        >
          Continue
        </button>
      </form>
    </main>
  );
}
