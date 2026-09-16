/**
 * Read-side resolution of a stored tax-consultant address to the value the
 * dropdown can display.
 *
 * WHY THIS IS ITS OWN MODULE, and not a function inside `roster-directory.ts`:
 * that module imports the team roster, and `src/lib/client-roster-boundary.test.ts`
 * fails the build if any `"use client"` module reaches the roster graph — the
 * roster would be compiled into a route's static chunk, which Next serves from
 * the CDN path with no session (the C4b/D6 boundary). The two consumers here
 * ARE client modules, so this function has to live where it carries no roster
 * dependency at all. The guard caught exactly that on the first attempt.
 *
 * Migration 319 rewrote every production row onto the real staff addresses and
 * the backend normalizes both spellings on write, so nothing here is ever SENT.
 * What it protects is the READ: a row written by a client that predates the
 * deploy, or a cached response, can still come back carrying a retired alias,
 * and a `<select>` whose `value` matches no `<option>` renders as the
 * placeholder — so an ASSIGNED client would read as "— not assigned —". The
 * consultant is not gone; the screen just cannot say her name.
 *
 * Deletable once no row can carry a retired alias — the same moment the
 * backend's contract migration drops them from the CHECK constraint.
 */
const RETIRED_TAX_CONSULTANT_ALIASES: Readonly<Record<string, string>> = {
  "veronika.tax@balizero.com": "tax@balizero.com",
  "faisha.tax@balizero.com": "faysha.tax@balizero.com",
};

/**
 * Case- and whitespace-insensitive, matching the backend's own `normalize()`:
 * what must never happen is a real assignment rendering as unassigned over a
 * spelling. Anything unrecognised is returned trimmed but otherwise untouched,
 * so a genuinely unknown value stays visible as itself rather than being
 * quietly mapped onto someone.
 */
export function normalizeTaxConsultant(
  value: string | null | undefined,
): string {
  if (!value) return "";
  const trimmed = value.trim();
  return RETIRED_TAX_CONSULTANT_ALIASES[trimmed.toLowerCase()] ?? trimmed;
}
