import { notFound } from "next/navigation";
import { isGarudaVoaPublicEnabled } from "../flag";

/**
 * `/visa/voa/auth` — the page the emailed magic link opens.
 *
 * WHY THIS ROUTE EXISTS: until now nothing in this app consumed a magic-link
 * token. `POST /api/visa/voa/auth/sessions` (the exchange that mints the
 * `garuda_session` account cookie) had ZERO callers in the frontend, while
 * `upload/api-client.ts` and `orders/api-client.ts` both assume that cookie
 * already exists — so the whole authenticated half of the funnel (document
 * upload, order, tracker) was unreachable by construction.
 *
 * WHY THE EXCHANGE IS NOT DONE HERE, ON GET: the token is SINGLE-USE, and a
 * replay under a new Idempotency-Key is rejected as invalid while a replay
 * under the SAME key returns 204 with NO second `Set-Cookie`
 * (`garuda_portal_auth.py:381-450`). Either way, whoever gets there second
 * ends up without a session. Mail clients and link scanners (Gmail, Outlook
 * Safe Links, chat preview bots) routinely issue an unsolicited GET on a
 * link before any human clicks it — so consuming on GET means the scanner
 * burns the token and the customer sees "invalid link". This page therefore
 * consumes NOTHING: it renders a form, and the exchange happens on the POST
 * that only a human gesture produces.
 *
 * WHY THE FORM IS PLAIN HTML AND NOT A CLIENT COMPONENT: the token must
 * never reach client-side JavaScript. `sentry.client.config.ts` runs Session
 * Replay (`replaysOnErrorSampleRate: 1.0`) and its `beforeSend` does not
 * scrub URLs, so a magic token that lives in `window.location` or in a
 * client fetch is a credential one unhandled error away from a third-party
 * cloud. A no-JS form keeps it in a request body.
 *
 * The dark-launch gate is inherited from `../layout.tsx` (`notFound()` when
 * `GARUDA_PUBLIC_ENABLED` is not "true"). The sibling route handler at
 * `auth/exchange/route.ts` does NOT inherit it — route handlers do not run
 * layouts — and therefore re-checks the flag itself.
 */

// Mirrors `MagicLinkExchange.token` (min_length=32, max_length=2048) and
// `MagicLinkRequest.result_id` (^[A-Za-z0-9_-]{22,128}$) in
// `apps/backend-rag/backend/app/routers/garuda_portal_auth.py:225,234`.
// Validating here is not a security boundary (the backend is) — it is what
// lets a mangled link say "ask for a new one" instead of round-tripping.
const RESULT_ID_PATTERN = /^[A-Za-z0-9_-]{22,128}$/;
const TOKEN_MIN_LENGTH = 32;
const TOKEN_MAX_LENGTH = 2048;

function firstValue(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}

export default async function GarudaVoaAuthPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  // Defence in depth: the layout already gates this, but a future refactor
  // that moves this page out from under that layout must not silently open a
  // public surface while the rest of the funnel is dark.
  if (!isGarudaVoaPublicEnabled()) {
    notFound();
  }

  const sp = await searchParams;
  const magicToken = firstValue(sp.magic_token);
  const resultId = firstValue(sp.result_id);
  const failed = firstValue(sp.error) !== undefined;

  const linkUsable =
    !failed &&
    typeof magicToken === "string" &&
    magicToken.length >= TOKEN_MIN_LENGTH &&
    magicToken.length <= TOKEN_MAX_LENGTH &&
    typeof resultId === "string" &&
    RESULT_ID_PATTERN.test(resultId);

  if (!linkUsable) {
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
        <input type="hidden" name="magic_token" value={magicToken} />
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
