import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { UploadFlow } from "./upload/UploadFlow";
import { messageFor, COPY_UNREADABLE_INSTRUCTION } from "./upload/messages";
import VoaEligibilityPage from "./page";
import VoaResultPage from "./[hash]/page";
import { CheckoutFlow } from "./checkout/[resultId]/CheckoutFlow";
import { OrderTracker } from "./orders/OrderTracker";

/**
 * GARUDA VOA DELIBERA (d) / design-A-claude.md §8 guard 2: an error message
 * must clear 4.5:1 against its own background, and it must never be carried
 * by a red-family Tailwind utility. This is the guard for the seven sites
 * lane S3 cured (M1: `text-red-600` at `upload/UploadFlow.tsx:182,215,223`,
 * 4.40:1 on paper — an AA fail; and the four `role="alert"` sites that read
 * `--color-error`, which resolves to copper on this surface — ownership, not
 * an error status).
 *
 * SCOPE, stated so this guard's green is never read as more than it proves
 * (cicatrix family #3 — a guard must declare what it does not see, same
 * discipline as `desk-no-red.guard.test.ts`). This file checks the ERROR-TONE
 * elements this PR touched — one per screen it changed (upload's three
 * states, the wizard's submit failure, the verdict page's magic-link
 * failure, checkout's order failure, the tracker's load failure). It does
 * NOT walk every text node on all six purchase screens; that fuller sweep is
 * a different, larger guard (design-A-claude.md §8 guard 2's full text) that
 * a later lane can build on top of this one's resolver.
 *
 * JSDOM LIMIT, read before trusting a green here. jsdom "applies no
 * stylesheet (no layout engine)" — the exact words `clients-desk.test.tsx`
 * uses for the same limit — so `getComputedStyle()` never resolves a
 * Tailwind utility class (arbitrary-value or not) to a real colour, and
 * never resolves a CSS custom property reference (`var(--x)`) to its
 * cascaded value even when an ancestor declares it. Two consequences follow,
 * both handled below rather than papered over:
 *
 *   1. Contrast math needs a real value, so `resolveColor` below resolves
 *      `var(--x[, fallback])` by hand, against a token table PARSED FROM
 *      `globals.css` itself (never hand-copied), for the
 *      `[data-theme="operative-light"][data-product="my"]` block this
 *      surface is mounted on today (`layout.tsx:54`). This is real WCAG
 *      relative-luminance math (`contrastRatio`), not a string comparison —
 *      pinned against design-A-claude.md's own M1 number below as a
 *      cross-check that the formula is right.
 *   2. A Tailwind class produces NO computed colour in jsdom at all (guilty
 *      or innocent), so `getComputedStyle` alone cannot see a regression
 *      back to `text-red-600` — it would just report the initial value.
 *      Each check below therefore ALSO reads the rendered element's actual
 *      `className` (the DOM the component produced, not the `.tsx` source
 *      text) and bans the red-family utility shape. Reverting the inline
 *      `style={{ color: "var(--tx-pure)" }}` fix back to
 *      `className="text-red-600"` trips THIS half of the guard, which is
 *      the one jsdom can actually see.
 */

const GLOBALS_CSS_PATH = join(__dirname, "..", "..", "globals.css");
const globalsCss = readFileSync(GLOBALS_CSS_PATH, "utf-8");

/** Brace-matched extraction — the block contains a nested `body { ... }` rule. */
function extractBlock(css: string, selector: string): string {
  const selectorStart = css.indexOf(selector);
  if (selectorStart === -1) {
    throw new Error(`selector not found in globals.css: ${selector}`);
  }
  const braceStart = css.indexOf("{", selectorStart);
  let depth = 0;
  let i = braceStart;
  for (; i < css.length; i++) {
    if (css[i] === "{") depth++;
    else if (css[i] === "}") {
      depth--;
      if (depth === 0) break;
    }
  }
  return css.slice(braceStart + 1, i);
}

function parseTokens(block: string): Record<string, string> {
  const tokens: Record<string, string> = {};
  const re = /(--[a-z0-9-]+)\s*:\s*([^;]+);/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(block))) {
    tokens[m[1]] = m[2].trim();
  }
  return tokens;
}

// The surface's actual wrapper today (layout.tsx:54) — not the operative-dark
// block S1 may flip to later; this guard measures what is LIVE.
const LIGHT_TOKENS = parseTokens(
  extractBlock(globalsCss, '[data-theme="operative-light"][data-product="my"]'),
);

function resolveColor(
  raw: string,
  tokens: Record<string, string>,
  depth = 0,
): string {
  const trimmed = raw.trim();
  const varMatch = trimmed.match(/^var\(\s*(--[a-z0-9-]+)\s*(?:,\s*(.+))?\)$/i);
  if (!varMatch) return trimmed;
  if (depth > 5) {
    throw new Error(`var() resolution too deep for ${raw}`);
  }
  const [, name, fallback] = varMatch;
  const resolved = tokens[name] ?? fallback;
  if (resolved === undefined) {
    throw new Error(`token ${name} not found and no fallback in ${raw}`);
  }
  return resolveColor(resolved, tokens, depth + 1);
}

function toRgb(color: string): [number, number, number] {
  const hex = color.match(/^#([0-9a-f]{6}|[0-9a-f]{3})$/i);
  if (hex) {
    let h = hex[1];
    if (h.length === 3) {
      h = h
        .split("")
        .map((c) => c + c)
        .join("");
    }
    const num = parseInt(h, 16);
    return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
  }
  const rgb = color.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/i);
  if (rgb) return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])];
  throw new Error(`cannot parse colour: ${color}`);
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/** WCAG 2.1 contrast ratio, §1.4.3's own formula — verified below (M1 cross-check). */
function contrastRatio(fg: string, bg: string): number {
  const l1 = relativeLuminance(toRgb(fg));
  const l2 = relativeLuminance(toRgb(bg));
  const [lighter, darker] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (lighter + 0.05) / (darker + 0.05);
}

const RED_CLASS_RE =
  /\b(?:bg|text|border|ring|divide|fill|stroke|from|to|via)-(?:red|rose|pink|orange|crimson)-\d/;

/** The two checks a jsdom-honest guard can make: real WCAG math on whatever
 * colour is actually reachable, and a DOM-output ban on the one shape jsdom
 * cannot compute (see file header, consequence 2). */
function assertErrorTone(el: Element, tokens: Record<string, string>) {
  const style = (el as HTMLElement).style;
  expect(
    style.color,
    `${el.tagName} has no inline colour to judge — the guard only judges elements it can compute`,
  ).not.toBe("");
  const fg = resolveColor(style.color, tokens);
  expect(fg, "error text must use the ink tone, not copper or red").toBe(
    tokens["--tx-pure"],
  );
  const bg = tokens["--bz-base"];
  expect(contrastRatio(fg, bg)).toBeGreaterThanOrEqual(4.5);
  expect(el.className, `${el.tagName} className`).not.toMatch(RED_CLASS_RE);
}

describe("resolver + contrast math — guilt and innocence (cicatrix #3)", () => {
  it("parses real hex tokens out of globals.css, not a hand-copied guess", () => {
    expect(LIGHT_TOKENS["--tx-pure"]).toBe("#1d2c3b");
    expect(LIGHT_TOKENS["--bz-base"]).toBe("#f7f4ee");
    expect(LIGHT_TOKENS["--bz-border"]).toBe("#dad8d1");
  });

  it("INNOCENT: the cured tone (ink on paper) clears 4.5:1", () => {
    const fg = resolveColor("var(--tx-pure)", LIGHT_TOKENS);
    const bg = LIGHT_TOKENS["--bz-base"];
    expect(contrastRatio(fg, bg)).toBeGreaterThanOrEqual(4.5);
  });

  it("GUILTY: the ORIGINAL text-red-600 hex (#DC2626) on paper measures 4.40:1 — an AA fail, matching design-A-claude.md M1's own number", () => {
    const ratio = contrastRatio("#DC2626", LIGHT_TOKENS["--bz-base"]);
    expect(ratio).toBeCloseTo(4.4, 1);
    expect(ratio).toBeLessThan(4.5);
  });

  it("GUILTY: copper (--color-error's resolved value on this surface) is a real colour but the wrong ONE — the guard demands ink specifically, not merely 'passes contrast'", () => {
    const copper = LIGHT_TOKENS["--state-danger"];
    expect(copper).toBe("#a44b36");
    // Copper-on-paper actually clears AA (it is the sanctioned "needs you"
    // tone) — proving a bare contrast check would NOT catch M2's finding
    // that role="alert" read the wrong meaning, only the identity check does.
    expect(
      contrastRatio(copper, LIGHT_TOKENS["--bz-base"]),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("GUILTY, the DOM-output shape a computed check cannot see any other way: a red Tailwind class in the rendered className", () => {
    const { container } = render(
      <p className="text-sm text-red-600">rendered, not sourced</p>,
    );
    const p = container.querySelector("p")!;
    expect(p.className).toMatch(RED_CLASS_RE);
    // And, matching consequence 2 in the file header: jsdom gives this
    // element NO inline colour at all, so a naive computed-only check would
    // stay silent on it — which is exactly why assertErrorTone also checks
    // className, not color alone.
    expect(p.style.color).toBe("");
  });

  it("INNOCENT: the kita idiom (border/text tokens, not a fill) never trips the red-class ban", () => {
    const { container } = render(
      <p className="text-sm" style={{ color: "var(--tx-pure)" }}>
        fine
      </p>,
    );
    expect(container.querySelector("p")!.className).not.toMatch(RED_CLASS_RE);
  });
});

// ---------------------------------------------------------------------------
// The seven real sites, rendered through the actual production components.
// ---------------------------------------------------------------------------

const trackerMocks = vi.hoisted(() => ({
  viewed: vi.fn(),
  wizardStep: vi.fn(),
  wizardAbandoned: vi.fn(),
  formSubmitted: vi.fn(),
  formSubmitFailed: vi.fn(),
  resultViewed: vi.fn(),
  ctaClicked: vi.fn(),
  whatsappHandoff: vi.fn(),
  shareClicked: vi.fn(),
  emailSubscribed: vi.fn(),
}));

vi.mock("@balizero/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@balizero/core")>();
  return {
    ...actual,
    useFunnelApp: () => trackerMocks,
  };
});

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock.mockReset();
  window.localStorage.clear();
  window.sessionStorage.clear();
  vi.clearAllMocks();
});

describe("upload — three error-tone states (M1's own site)", () => {
  it("client_rejected: oversized file, rejected client-side, no fetch", async () => {
    // A wrong-MIME file (e.g. a PDF) never reaches `selectFile` here:
    // `userEvent.upload` enforces the input's own `accept` attribute the way
    // a real browser's file picker does, so a mismatched type is silently
    // not selected. An oversized JPEG has the RIGHT type and clears that
    // gate, then trips `precheckFile`'s size check — the same
    // `client_rejected` branch, reached the way a real user reaches it.
    render(<UploadFlow resultId="guard-upload-1" />);
    const input = screen.getByLabelText("Upload passport photo");
    const bigFile = new File(
      [new Uint8Array(16 * 1024 * 1024)],
      "passport.jpg",
      { type: "image/jpeg" },
    );
    await userEvent.upload(input, bigFile);

    const alert = await screen.findByRole("alert");
    const p = alert.querySelector("p")!;
    assertErrorTone(p, LIGHT_TOKENS);
  });

  it("unreadable: server returns UNREADABLE_DOCUMENT", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(422, {
        code: "UNREADABLE_DOCUMENT",
        retryable: false,
        message_key: "garuda_voa.error.unreadable_document",
      }),
    );
    render(<UploadFlow resultId="guard-upload-2" />);
    const input = screen.getByLabelText("Upload passport photo");
    const goodFile = new File([new Uint8Array(10)], "passport.jpg", {
      type: "image/jpeg",
    });
    await userEvent.upload(input, goodFile);

    const p = await screen.findByText(COPY_UNREADABLE_INSTRUCTION);
    assertErrorTone(p, LIGHT_TOKENS);
  });

  it("error: a retryable 503 (document store unavailable)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(503, {
        code: "DOCUMENT_PROCESSING_UNAVAILABLE",
        retryable: true,
        message_key: "garuda_voa.error.document_processing_unavailable",
      }),
    );
    render(<UploadFlow resultId="guard-upload-3" />);
    const input = screen.getByLabelText("Upload passport photo");
    const goodFile = new File([new Uint8Array(10)], "passport.jpg", {
      type: "image/jpeg",
    });
    await userEvent.upload(input, goodFile);

    const p = await screen.findByText(
      messageFor("DOCUMENT_PROCESSING_UNAVAILABLE"),
    );
    assertErrorTone(p, LIGHT_TOKENS);
  });
});

describe("wizard — eligibility-check submit failure (page.tsx:541)", () => {
  it("network failure renders the WhatsApp-fallback alert in ink, not copper", async () => {
    fetchMock.mockRejectedValue(new Error("network down"));
    render(<VoaEligibilityPage />);

    fireEvent.click(
      screen.getByRole("button", { name: /Get a new Visa on Arrival/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Tourism" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.change(screen.getByLabelText("Nationality"), {
      target: { value: "ITA" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.change(screen.getByLabelText("Entry date"), {
      target: { value: "2026-09-01" },
    });
    fireEvent.change(screen.getByLabelText("Passport expiry date"), {
      target: { value: "2027-09-01" },
    });
    fireEvent.click(
      screen.getByLabelText("Storage and deletion notice acknowledgement"),
    );
    fireEvent.click(screen.getByRole("button", { name: "See result" }));

    const alert = await waitFor(() => screen.getByRole("alert"));
    assertErrorTone(alert, LIGHT_TOKENS);
  });
});

describe("verdict — magic-link resend failure ([hash]/page.tsx:404)", () => {
  it("a failed resend renders the alert in ink, not copper", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        verdict: "ACCEPT",
        reason_codes: [],
        price_idr: 790000,
      }),
    });
    fetchMock.mockResolvedValueOnce({ status: 500 });
    render(<VoaResultPage params={Promise.resolve({ hash: "guard-hash" })} />);
    await waitFor(() =>
      expect(screen.getByTestId("bz-stamp")).toBeInTheDocument(),
    );

    const user = userEvent.setup();
    await user.type(
      screen.getByLabelText(/continue by email/i),
      "customer@example.com",
    );
    await user.click(screen.getByRole("button", { name: /email me a link/i }));

    const alert = await screen.findByRole("alert");
    assertErrorTone(alert, LIGHT_TOKENS);
  });
});

describe("checkout — order-creation failure (CheckoutFlow.tsx:201)", () => {
  it("a failed order submit renders the alert in ink, not copper", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(500, {}));
    const user = userEvent.setup();
    render(<CheckoutFlow resultId="guard-checkout-1" paymentsLive={true} />);

    await user.type(
      screen.getByLabelText(/full name \(as in passport\)/i),
      "Jane Doe",
    );
    await user.type(screen.getByLabelText(/^passport number$/i), "X1234567");
    await user.type(screen.getByLabelText(/email/i), "customer@example.com");
    await user.type(screen.getByLabelText(/phone/i), "+6281234567890");
    await user.click(
      screen.getByRole("button", { name: /continue to payment/i }),
    );

    const alert = await screen.findByRole("alert");
    assertErrorTone(alert, LIGHT_TOKENS);
  });
});

describe("tracker — order load failure (OrderTracker.tsx:49)", () => {
  it("a failed order fetch renders the alert in ink, not copper", async () => {
    fetchMock.mockResolvedValue(jsonResponse(500, {}));
    render(<OrderTracker orderId="guard-order-1" />);

    const alert = await screen.findByRole("alert");
    assertErrorTone(alert, LIGHT_TOKENS);
  });
});
