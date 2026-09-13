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

/**
 * A directory wrapped in parentheses is a ROUTE GROUP: it organises files and does not
 * appear in the URL. So `(workspace)/(admin)/settings/page.tsx` is served at
 * `/settings`, and a walk that reported `(admin)/settings` would never match the
 * manifest key — the route would be prerendered, unscanned, and invisible to this
 * check. There are no nested groups under `(workspace)` today; a seat pointed out that
 * the guard's job is to catch the NEXT change, not today's.
 *
 * @param {string} route
 * @returns {string} the route as it appears in a URL
 */
export function urlRoute(route) {
  return route
    .split("/")
    .filter((seg) => !(seg.startsWith("(") && seg.endsWith(")")))
    .join("/");
}

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
