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
 * KNOWN RESIDUAL, tracked, not closed here: this page does not say WHOSE
 * application it is about to open. Both council seats (Codex sol and Kimi K3,
 * independently, 2026-08-28) reached the same conclusion — a generic
 * "Continue" plus an unbound landing GET is login CSRF: an attacker mails a
 * victim their OWN link, the victim clicks Continue, and the attacker's
 * session is planted in the victim's browser, which then uploads a passport
 * into the attacker's application. Closing it needs a non-consuming
 * recipient-identity lookup the backend does not expose yet, so the sentence
 * below is a mitigation and NOT a fix. The funnel is dark while this stands.
 */

function firstValue(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
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

  if (!ready) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
        <h1 className="text-xl font-semibold">This link is no longer valid</h1>
        <p className="text-gray-600">
          Sign-in links expire and can only be used once. Please request a new
          one from your eligibility result page.
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-6 p-6 text-center">
      <h1 className="text-xl font-semibold">Continue your application</h1>
      <p className="text-gray-600">
        You&apos;re one step from uploading your documents.
      </p>
      <p className="text-sm text-gray-500">
        Continuing opens the application this link was emailed for. If you did
        not ask us for it, close this page instead.
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
