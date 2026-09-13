import { urlRoute } from "./app-routes.mjs";

// Which `(workspace)` routes are allowed to be STATIC, and the decision that says so.
//
// WHY THIS EXISTS. The chunk guard next door scans built JS chunks. It does NOT scan
// `.next/server/app`, where a PRERENDERED route's payload lands as a file — and a
// workspace route that becomes static writes its data there, cacheable and served
// without a session. C4c documented that boundary; documenting it stops nothing.
//
// WHY THIS IS A BASELINE AND NOT A BLANKET RULE. Asserting "no workspace route may be
// prerendered" fails the build today on every one of them, and turning an exposure
// that is already escalated and owner-held into a red build for every window is not
// how that decision gets made — it is how people learn to bypass the guard. Both
// review seats said so independently. So the routes measured as already static are
// ACCEPTED with their measurement written down, and a NEW one fails: nobody has
// accepted that, and today it would land in silence.
//
// THE ACCEPTED SET MUST SHRINK. Every entry here is exposure, not design. When the
// workspace gains a server-side session gate, this list should empty out; it is not a
// configuration knob to grow.

/**
 * Measured on the build of this commit, by walking the route tree — and the count was
 * wrong twice before it was right, which is the lesson this list carries.
 *
 * C4c's comment said FIVE routes were prerendered: that probe filtered the manifest
 * against a hardcoded tuple of five names, so five was the most it could ever return.
 * The first draft of THIS file said SEVENTEEN: it enumerated the filesystem, which was
 * the right idea, but only one level deep and only where a directory had its own
 * `page.tsx` — so every nested route was invisible. A refuter caught that, and the
 * measurement is FORTY-TWO: every `(workspace)` route without a dynamic segment is
 * prerendered, nested ones included (`hr/payroll`, `settings/profile`,
 * `intelligence/news-room`, …). None is dynamic.
 *
 * Both wrong numbers came from an enumeration narrower than the thing being counted,
 * and both looked like measurements. Walk the tree; do not list names.
 *
 * The exposure is narrower than forty-two suggests, and that belongs in the same
 * breath: of the forty-two payloads, exactly ONE carries staff-name markers —
 * `/lkpm`, with 4 hits. The rest are the client shell.
 */
export const ACCEPTED_PRERENDERED_WORKSPACE_ROUTES = [
  "accounting",
  "admin",
  "admin/cell",
  "admin/system",
  "admin/team-activity",
  "analytics/funnel",
  "clients",
  "clients/analytics",
  "clients/new",
  "dashboard",
  "garuda-voa",
  "hr",
  "hr/bonuses",
  "hr/employees",
  "hr/leave",
  "hr/leave/request",
  "hr/owner-cashout",
  "hr/payroll",
  "hr/settings",
  "intelligence",
  "intelligence/analytics",
  "intelligence/article-composer",
  "intelligence/news-room",
  "intelligence/visa-oracle",
  "intelligence/voice-concierge",
  "lkpm", // the only payload carrying staff markers (4), measured
  "lkpm/submit",
  "notifications",
  "obligations",
  "omnichannel",
  "partners",
  "partners/new",
  "process",
  "process/new",
  "review",
  "second-home",
  "second-home/new",
  "settings",
  "settings/appearance",
  "settings/integrations",
  "settings/profile",
  "terminal",
];

// urlRoute is IMPORTED, not redefined. It was a local copy here and a second local
// copy in the guard's walk, and the copies disagreed on five rules while happening to
// agree on today's tree. One definition, in scripts/lib/app-routes.mjs.
/**
 * @param {{ workspaceRoutes: string[], prerenderedPaths: string[], accepted?: string[] }} input
 * @returns {string[]} routes that are prerendered but not accepted
 */
export function unacceptedPrerenderedWorkspaceRoutes({
  workspaceRoutes,
  prerenderedPaths,
  accepted = ACCEPTED_PRERENDERED_WORKSPACE_ROUTES,
}) {
  const prerendered = new Set(prerenderedPaths);
  // Compare on the URL form at BOTH ends, so an accepted entry and a walked route
  // written with a group still mean the same route.
  const ok = new Set(accepted.map(urlRoute));
  return workspaceRoutes
    .filter((r) => prerendered.has(`/${urlRoute(r)}`))
    .filter((r) => !ok.has(urlRoute(r)))
    .sort();
}

/**
 * Accepted entries that are NOT prerendered any more — a promise the list is still
 * making about a route that no longer keeps it.
 *
 * The exception contract next door checks its pairing in BOTH directions and this one
 * did not, which a seat called an asymmetry with this file's own philosophy. It is
 * reported rather than fatal, and the distinction is the point: a stale accepted entry
 * cannot HIDE anything — it can only fail to flag a route that stopped being static —
 * so failing the build over it would punish the good direction of travel. What it does
 * do is rot, and a list nobody prunes is how an exposure baseline turns into config.
 *
 * @returns {string[]} accepted routes that are no longer prerendered
 */
export function staleAcceptedRoutes({
  workspaceRoutes,
  prerenderedPaths,
  accepted = ACCEPTED_PRERENDERED_WORKSPACE_ROUTES,
}) {
  const prerendered = new Set(prerenderedPaths);
  const known = new Set(workspaceRoutes.map(urlRoute));
  return accepted
    .filter((r) => known.has(r))
    .filter((r) => !prerendered.has(`/${r}`))
    .sort();
}
