import { permanentRedirect } from "next/navigation";

/**
 * RETIRED DOOR — the legacy 4-question free-text quiz.
 *
 * RULING Zero 2026-08-25: «Due porte: 301 → `/visa-oracle` subito». This wizard
 * asked nationality / purpose / duration / budget and promised a visa *and a
 * cost* in four answers; the Oracle answers from a signed, versioned RulePack
 * instead. The wizard body is deleted, not shadowed.
 *
 * `[hash]` is deliberately untouched: result links already shared with visitors
 * still resolve at `/visa/match/<hash>` (acceptance A5). Only the entry point
 * retires. `POST /api/visa/match` keeps serving nothing new — it is outside this
 * window's perimeter and has no remaining caller in `apps/mouth`.
 *
 * See `../page.tsx` for why this is a route-level redirect and not an entry in
 * the shared `next.config.ts` redirect table (D1).
 */
export default function VisaMatchPage(): never {
  permanentRedirect("/visa-oracle");
}
