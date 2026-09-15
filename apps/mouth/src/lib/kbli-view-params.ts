/**
 * The two view controls the sector surfaces share — which codes are shown
 * (`?verified=`) and how they are drawn (`?view=`) — plus the history plumbing
 * that lets them live in the URL without disturbing the off-canvas panel.
 *
 * Why the URL and not component state: both surfaces that render the sector
 * code list are STATICALLY PRERENDERED (`/kbli/sectors/[id]`, 22 SSG pages, and
 * the intercepted panel beside it). A prerendered route serves the same output
 * for every query string, so these params can never be read on the server — the
 * measurement is in KBLISectorOffcanvas. They are written and read here, on the
 * client, which is what makes a filtered view survive a refresh and a paste
 * into someone else's tab.
 *
 * Why replaceState and never pushState: `?verified=`/`?view=` are not places.
 * The panel counts history entries to know how far to pop on close, and a Back
 * button that walks backwards through somebody's filter choices instead of
 * leaving the panel is the failure this avoids. Choosing a filter rewrites the
 * entry you stand on; it never adds one.
 */

export type KBLIVerifiedFilter = "all" | "verified" | "unverified";
export type KBLIViewType = "cards" | "table" | "list";

export const VERIFIED_PARAM = "verified";
export const VIEW_PARAM = "view";

/** Defaults are the pre-existing behaviour: everything, drawn as cards. */
export const DEFAULT_VERIFIED: KBLIVerifiedFilter = "all";
export const DEFAULT_VIEW: KBLIViewType = "cards";

/**
 * Marker the off-canvas writes on every history entry it creates (how many
 * entries to pop to leave the panel, and the href it was written for). It lives
 * here rather than in the panel because `writeViewParams` has to carry it
 * across a URL rewrite: the marker is matched by href, so changing the query
 * string without re-stamping it would strand the panel's pop count and leave a
 * visitor unable to close the panel in one gesture.
 */
export const PANEL_MARK_KEY = "kbliPanel";

function isVerified(value: string | null): value is KBLIVerifiedFilter {
  return value === "all" || value === "verified" || value === "unverified";
}

function isView(value: string | null): value is KBLIViewType {
  return value === "cards" || value === "table" || value === "list";
}

/**
 * Read both controls off a query string. An unknown or absent value degrades to
 * the default rather than throwing — these arrive from a pasted URL, so a typo
 * must show the full list, never an empty one.
 */
export function readViewParams(search: string): {
  verified: KBLIVerifiedFilter;
  view: KBLIViewType;
} {
  const params = new URLSearchParams(search);
  const verified = params.get(VERIFIED_PARAM);
  const view = params.get(VIEW_PARAM);
  return {
    verified: isVerified(verified) ? verified : DEFAULT_VERIFIED,
    view: isView(view) ? view : DEFAULT_VIEW,
  };
}

/**
 * Build the href for the current location with both controls applied. A control
 * left at its default is REMOVED from the query rather than spelled out, so the
 * shared link for the default view is the plain sector URL it always was.
 *
 * Every other param is preserved — `?code=` in particular: a drill-down opened
 * while a filter is on must stay inside that filter.
 */
export function viewParamsHref(
  currentHref: string,
  next: { verified: KBLIVerifiedFilter; view: KBLIViewType },
): string {
  const url = new URL(currentHref, "https://balizero.com");

  if (next.verified === DEFAULT_VERIFIED)
    url.searchParams.delete(VERIFIED_PARAM);
  else url.searchParams.set(VERIFIED_PARAM, next.verified);

  if (next.view === DEFAULT_VIEW) url.searchParams.delete(VIEW_PARAM);
  else url.searchParams.set(VIEW_PARAM, next.view);

  return url.pathname + url.search;
}

/**
 * Rewrite the entry we stand on with the new href, re-stamping the panel marker
 * so its href keeps matching where we are. Outside the panel there is no marker
 * and the rest of the history state is passed through untouched.
 */
export function writeViewParams(href: string): void {
  if (typeof window === "undefined") return;

  const state = (window.history.state ?? {}) as Record<string, unknown>;
  const mark = state[PANEL_MARK_KEY];
  const next =
    mark && typeof mark === "object"
      ? { ...state, [PANEL_MARK_KEY]: { ...mark, href } }
      : state;

  window.history.replaceState(next, "", href);
}
