import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { isGarudaVoaPublicEnabled } from "../../flag";
import { PENDING_COOKIE, RESULT_ID_PATTERN } from "../contract";

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
 * this page is reachable by a scanner too. The exchange therefore runs only
 * on the POST that a human gesture produces.
 *
 * The form is plain HTML with no client component on purpose: there is no
 * value for JavaScript to read, and none to leak.
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

  const sp = await searchParams;
  const resultId = firstValue(sp.result_id);
  const failed = firstValue(sp.error) !== undefined;

  // The cookie is the only thing that proves a token is in flight. Without
  // it there is nothing to submit, so offering the button would be a lie.
  const pending = (await cookies()).get(PENDING_COOKIE)?.value;

  const ready =
    !failed &&
    typeof pending === "string" &&
    pending.length > 0 &&
    typeof resultId === "string" &&
    RESULT_ID_PATTERN.test(resultId);

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
      <form method="post" action="/visa/voa/auth/exchange">
        {/* Only the result id. The token stays in the HttpOnly cookie. */}
        <input type="hidden" name="result_id" value={resultId} />
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
