import { Suspense } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import VisaClockResultPage from "./page";

/**
 * A permitted stay that has already ended must never be rendered as a countdown.
 *
 * Measured live on balizero.com on 2026-08-28: a visitor 65 days into an
 * overstay was shown
 *
 *     "Expires 24 June 2026 — 0 days from today."
 *     "Valid until 24 June 2026"
 *
 * followed by a five-checkpoint plan whose every date was in the past and an
 * invitation to subscribe to reminder emails for those same past dates. The
 * cause was a single `Math.max(0, …)` around the day arithmetic: it does not
 * guard against NaN, it suppresses the negative, so −65 rendered as 0. The page
 * held no overstay branch at all.
 *
 * The same clamped value was also handed to the team: the WhatsApp context line
 * read "Days left: 0" instead of naming the overstay, so the staff member
 * picking the conversation up inherited the same false picture.
 *
 * These tests are a guilt/innocence pair. The overstay cases assert the page
 * refuses to reassure; the control asserts a genuinely valid stay still gets
 * its normal timeline, so a future "fix" cannot pass by simply removing the
 * countdown for everyone.
 */

const trackerMocks = vi.hoisted(() => ({
  resultViewed: vi.fn(),
  whatsappHandoff: vi.fn(),
  shareClicked: vi.fn(),
}));

/** Props the page hands to the WhatsApp CTA, captured for the handoff assertions. */
const ctaProps = vi.hoisted(() => ({
  current: null as Record<string, unknown> | null,
}));

vi.mock("@balizero/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@balizero/core")>();
  return {
    ...actual,
    useFunnelApp: () => ({
      viewed: vi.fn(),
      resultViewed: trackerMocks.resultViewed,
      whatsappHandoff: trackerMocks.whatsappHandoff,
      shareClicked: trackerMocks.shareClicked,
    }),
    useHaptic: () => vi.fn(),
    // Light stubs: this suite is about what the visitor is TOLD, not about how
    // the design system paints it. AppFrame keeps title/subtitle/children so the
    // assertions read the real, page-authored copy.
    AppFrame: ({ title, subtitle, children }: any) => (
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
        {children}
      </div>
    ),
    AppStampReveal: ({ code }: any) => <div>{code}</div>,
    AppResultTimeline: () => (
      <div data-testid="timeline">five-checkpoint timeline</div>
    ),
    AppEmailOptIn: ({ promise }: any) => (
      <div data-testid="email-optin">{promise}</div>
    ),
    AppShareBar: () => <div />,
    AppWhatsAppCTA: (props: any) => {
      ctaProps.current = props;
      return <div data-testid="wa-cta">{props.headline}</div>;
    },
  };
});

vi.mock("@/components/visa/ChatAccordion", () => ({
  ChatAccordion: () => <div data-testid="chat-accordion" />,
}));

const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

function isoDaysFromToday(delta: number): string {
  const d = new Date();
  d.setDate(d.getDate() + delta);
  return d.toISOString().slice(0, 10);
}

/** A clock result whose expiry sits `delta` days from today (negative = overstay). */
function clockResult(delta: number) {
  const expiry = isoDaysFromToday(delta);
  return {
    hash: "testhash123456ab",
    visa_type: "B1",
    entry_date: isoDaysFromToday(delta - 30),
    expiry_date: expiry,
    extensions_possible: 1,
    extension_days: 30,
    // The backend returns checkpoints regardless of whether the date has passed —
    // that is precisely why the page, not the payload, has to make this call.
    checkpoints: [
      {
        label: "D-60",
        at: isoDaysFromToday(delta - 60),
        title: "Start paperwork",
        body: "…",
      },
      {
        label: "D-1",
        at: isoDaysFromToday(delta - 1),
        title: "Final check",
        body: "…",
      },
    ],
    result_url: `/visa/clock/testhash123456ab`,
    session_jwt: null,
  };
}

/**
 * A promise pre-marked with React's own tracked-promise fields.
 *
 * The page reads its route params with `use(params)`, which SUSPENDS on a plain
 * promise — and under this runner the suspension never resolves, so the tree
 * renders nothing and the fetch effect never fires. An earlier draft of this
 * file therefore reported 6 vacuous passes: every `not.toBeInTheDocument()` is
 * trivially true on an empty document.
 *
 * `use()` short-circuits when a promise already carries `status: "fulfilled"`
 * and `value`, returning synchronously without suspending. That keeps the fix
 * in the test, where the problem is — the sibling `voa/[hash]` page happens to
 * avoid this only because it reads params via `params.then(...)` in an effect,
 * which is not a reason to rewrite this page.
 */
function settledParams<T>(value: T): Promise<T> {
  const p = Promise.resolve(value) as Promise<T> & { status: string; value: T };
  p.status = "fulfilled";
  p.value = value;
  return p;
}

async function renderWithExpiry(delta: number) {
  fetchMock.mockResolvedValue({
    ok: true,
    json: async () => clockResult(delta),
  });
  render(
    <Suspense fallback={<div>suspended</div>}>
      <VisaClockResultPage
        params={settledParams({ hash: "testhash123456ab" })}
      />
    </Suspense>,
  );
  // Wait for real content, never for the absence of something: absence is also
  // what a crashed render looks like, and that is exactly how the vacuous
  // version of this suite went green.
  await waitFor(() => expect(screen.getByTestId("wa-cta")).toBeInTheDocument());
}

beforeEach(() => {
  vi.clearAllMocks();
  fetchMock.mockReset();
  ctaProps.current = null;
});

describe("visa clock — a stay that already ended", () => {
  it("never tells an overstayer their visa is 'Valid until' anything", async () => {
    await renderWithExpiry(-65);

    expect(screen.queryByText(/Valid until/i)).not.toBeInTheDocument();
  });

  it("never renders the clamped '0 days' that hid the overstay", async () => {
    await renderWithExpiry(-65);

    // The exact string the live page served on 2026-08-28.
    expect(document.body.textContent).not.toMatch(/0 days from today/i);
    expect(document.body.textContent).not.toMatch(/\b0 days\b/i);
  });

  it("states how many days the stay has been over for", async () => {
    await renderWithExpiry(-65);

    expect(screen.getByText(/65 days ago/i)).toBeInTheDocument();
  });

  it("uses the singular on the first day over, not '1 days'", async () => {
    await renderWithExpiry(-1);

    expect(screen.getByText(/\b1 day ago\b/i)).toBeInTheDocument();
  });

  it("does not serve a plan whose every checkpoint is in the past", async () => {
    await renderWithExpiry(-65);

    expect(screen.queryByTestId("timeline")).not.toBeInTheDocument();
  });

  it("does not offer reminder emails for dates that have already passed", async () => {
    await renderWithExpiry(-65);

    expect(screen.queryByTestId("email-optin")).not.toBeInTheDocument();
  });

  it("hands the team the real overstay, never 'Days left: 0'", async () => {
    await renderWithExpiry(-65);

    const rows = (ctaProps.current?.whatsappContext ?? []) as {
      label: string;
      value: string;
    }[];
    const labels = rows.map((r) => r.label);

    expect(labels).not.toContain("Days left");
    expect(rows).toContainEqual({ label: "Days overstayed", value: "65" });
  });

  it("captures the lead under a source the backend actually accepts", async () => {
    await renderWithExpiry(-65);

    // `source` is validated server-side against PublicLeadSource. A value that
    // enum lacks returns 422, AppWhatsAppCTA swallows it, and the visitor is
    // redirected to the BARE wa.me link — no prefilled message, no lead row.
    // An earlier draft of this page shipped `visa_clock_overstay`, which the
    // backend does not define; the cross-stack tripwire caught it. The overstay
    // is a branch of the Visa Clock funnel, so it captures as `visa_clock` and
    // carries its discriminator in `context` instead.
    expect(ctaProps.current?.source).toBe("visa_clock");
    expect(ctaProps.current?.context).toMatchObject({
      overstay: true,
      days_overstayed: 65,
    });
  });

  it("invents no fine, threshold or penalty — those are domain facts, not ours", async () => {
    await renderWithExpiry(-65);

    // The page may say the situation is serious and urgent; it must not put a
    // number, a currency or a legal consequence on it. Getting those wrong on a
    // page read by someone already in trouble is worse than the defect it fixes.
    expect(document.body.textContent).not.toMatch(
      /IDR|Rp\b|rupiah|fine|penalt|deport|ban\b|jail|prison/i,
    );
  });
});

describe("visa clock — a stay that is still valid (control)", () => {
  it("still shows the normal countdown and timeline", async () => {
    await renderWithExpiry(45);

    expect(screen.getByText(/Valid until/i)).toBeInTheDocument();
    expect(screen.getByTestId("timeline")).toBeInTheDocument();
    expect(screen.getByTestId("email-optin")).toBeInTheDocument();
    expect(document.body.textContent).toMatch(/45 days from today/i);
  });

  it("does not accuse a valid visitor of overstaying", async () => {
    await renderWithExpiry(45);

    expect(document.body.textContent).not.toMatch(
      /already ended|days ago|overstay/i,
    );
  });

  it("hands the team days LEFT while the stay is still running", async () => {
    await renderWithExpiry(45);

    const rows = (ctaProps.current?.whatsappContext ?? []) as {
      label: string;
      value: string;
    }[];
    expect(rows).toContainEqual({ label: "Days left", value: "45" });
    expect(rows.map((r) => r.label)).not.toContain("Days overstayed");
    // Innocence half of the pair: a running stay is captured under the same
    // funnel source, and must NOT be flagged as an overstay in context.
    expect(ctaProps.current?.source).toBe("visa_clock");
    expect(ctaProps.current?.context).not.toHaveProperty("overstay");
  });
});
