/**
 * "Your action margin" — the ownership queue of the kita dashboard.
 *
 * concept-K v2 "TEPAT FORTE" §2: the margin "uses only the existing review
 * count plus fetched practices whose `status` is `waiting_documents` and whose
 * assignment makes this viewer next. `complianceAlerts` remain in Compliance
 * radar."
 *
 * No new endpoint, no new request, no new field. Both families come from data
 * the page already fetches:
 *
 *   · the review queue — GET /api/intake/review/queue?status=review_pending,
 *     which the page already calls and whose items it used to discard on
 *     `.length` (concept DISPOSITION C3);
 *   · the practices array of GET /api/dashboard/summary, which the page
 *     already renders in the Process pipeline section below.
 *
 * THE OWNERSHIP RULE, and why it is not a status test.
 * Copper means "the signed-in viewer is the next actor". A status alone cannot
 * say that, and a date never can. So a practice enters the margin only when
 * BOTH hold: the record is waiting on documents, AND the array it came from is
 * scoped to the viewer. `/api/dashboard/summary` scopes its practice list with
 * `assigned_to = user_id` for every non-admin (backend
 * `app/routers/dashboard_summary.py`, the `assigned_to=None if is_admin else
 * user_id` argument). For an ADMIN the same array is the whole book, so
 * assignment is not derivable from it — and where ownership is not derivable
 * the module README's law 1 says use `wait`. An admin therefore gets no
 * practice family here at all, rather than a copper claim the data cannot
 * support.
 *
 * KNOWN LIMIT, recorded rather than papered over: that same endpoint asks for
 * `list_practices(status="in_progress", …)`, an exact `p.status = $n` match, so
 * today the array cannot contain a `waiting_documents` row and this family is
 * empty in production. The predicate is still written against the real status
 * vocabulary — both the CRM spelling (`waiting_documents`) and the dashboard
 * summary's own short code (`documents`, which its `status_map` emits) — so the
 * margin fills the day the summary widens its filter, with no change here.
 */

/** The statuses that mean "this record is blocked on its assignee". */
const OWNER_ACTIONABLE = new Set(["waiting_documents", "documents"]);

/** A practice as `/api/dashboard/summary` delivers it. */
export interface MarginPractice {
  id: number;
  title: string;
  client: string;
  status: string;
  daysRemaining?: number;
}

export interface ActionMarginItem {
  /** Stable key — the record's own id, never the array index. */
  id: string;
  /** The one-line claim. */
  title: string;
  /** Where the claim comes from, so the row is auditable at a glance. */
  detail: string;
  /** The WORD beside the copper. Colour never travels alone. */
  state: string;
  /** Tabular trailing value: "Now", "2d", or an empty string. */
  when: string;
  /** Urgency, never ownership: a countdown takes `warning`, not copper. */
  urgent: boolean;
  href: string;
}

export interface ActionMarginInput {
  /** Items the review queue returned, or undefined while it is in flight. */
  reviewItems?: unknown[];
  practices: MarginPractice[];
  /**
   * True when the practices array is the viewer's own assigned work. False for
   * an admin, whose array is the whole book.
   */
  practicesAreMine: boolean;
}

export interface ActionMargin {
  items: ActionMarginItem[];
  /** How many things the viewer is next on. Drives the masthead sentence. */
  count: number;
}

/** `3 documents await review` — a family that exposes only a count. */
function reviewFamily(reviewItems: unknown[] | undefined): ActionMarginItem[] {
  const n = reviewItems?.length ?? 0;
  if (n === 0) return [];
  return [
    {
      id: "review-queue",
      title: `${n} document${n === 1 ? "" : "s"} await${n === 1 ? "s" : ""} review`,
      detail: "Review queue",
      state: "Your review",
      when: "Now",
      urgent: false,
      href: "/review",
    },
  ];
}

function practiceFamily({
  practices,
  practicesAreMine,
}: Pick<ActionMarginInput, "practices" | "practicesAreMine">) {
  if (!practicesAreMine) return [];
  return practices
    .filter((p) => OWNER_ACTIONABLE.has(String(p.status).toLowerCase()))
    .map<ActionMarginItem>((p) => {
      const days = p.daysRemaining;
      return {
        id: `practice-${p.id}`,
        title: `${p.client} · ${p.title}`,
        detail: "Assigned to you",
        state: "Documents",
        when: days === undefined || days === null ? "" : `${days}d`,
        // Urgency is a property of the DATE. It modifies the trailing value and
        // it never promotes or demotes ownership (fusion DISPOSITION F3/F10).
        urgent: typeof days === "number" && days <= 3,
        href: `/process/${p.id}`,
      };
    });
}

/** Build the margin. Order is review first, then the viewer's blocked work. */
export function buildActionMargin(input: ActionMarginInput): ActionMargin {
  const items = [...reviewFamily(input.reviewItems), ...practiceFamily(input)];
  return { items, count: items.length };
}

/**
 * The masthead sentence, computed from the same two numbers the page paints.
 * It disappears rather than claim something the data cannot prove (fusion §6:
 * "Computed masthead sentences … disappear or stay muted when their data
 * cannot prove the claim").
 */
export function mastheadSentence(
  moving: number,
  needsYou: number,
): string | undefined {
  if (moving === 0 && needsYou === 0) return undefined;
  const left =
    moving === 0
      ? "Nothing is moving"
      : `${moving} thing${moving === 1 ? "" : "s"} ${moving === 1 ? "is" : "are"} moving`;
  const right =
    needsYou === 0
      ? "nothing needs your action"
      : `${needsYou} need${needsYou === 1 ? "s" : ""} your action`;
  return `${left}; ${right}.`;
}
