import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { PENDING_COOKIE } from "../contract";

/**
 * The only page of the magic-link flow a human sees. Three invariants: it
 * redeems nothing at render time (it may PREVIEW the token via the
 * non-consuming `previewMagicLink` backend lookup, but never calls the
 * consuming `exchangeMagicLink` endpoint), it holds no credential anywhere
 * in the document — the token lives in an HttpOnly cookie the page cannot
 * read into its markup, and it never offers Continue when that preview
 * lookup fails.
 */

const MASKED_EMAIL = "jo***@example.com";

function previewResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const notFoundMock = vi.hoisted(() =>
  vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
);
const cookieStore = vi.hoisted(() => ({
  value: undefined as string | undefined,
  /** The journey locale cookie — the only language channel that reaches a
   *  SERVER component opened from an email. */
  lang: undefined as string | undefined,
}));

vi.mock("next/navigation", () => ({ notFound: notFoundMock }));
vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (name: string) => {
      if (name === "garuda_magic_pending" && cookieStore.value !== undefined) {
        return { name, value: cookieStore.value };
      }
      if (name === "bz_voa_lang" && cookieStore.lang !== undefined) {
        return { name, value: cookieStore.lang };
      }
      return undefined;
    },
  }),
}));

const TOKEN = "t".repeat(40);
const RESULT_ID = "R".repeat(24);

async function renderPage(sp: Record<string, string>) {
  const { default: Page } = await import("./page");
  return Page({ searchParams: Promise.resolve(sp) });
}

describe("/visa/voa/auth/continue", () => {
  const original = process.env.GARUDA_PUBLIC_ENABLED;

  beforeEach(() => {
    notFoundMock.mockClear();
    process.env.GARUDA_PUBLIC_ENABLED = "true";
    cookieStore.value = `${RESULT_ID}.${TOKEN}`;
    cookieStore.lang = undefined;
    // Default: the preview lookup succeeds. Tests for the failure path
    // override this per-test.
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(previewResponse({ masked_email: MASKED_EMAIL })),
    );
  });

  afterEach(() => {
    if (original === undefined) delete process.env.GARUDA_PUBLIC_ENABLED;
    else process.env.GARUDA_PUBLIC_ENABLED = original;
    vi.unstubAllGlobals();
  });

  it("renders the form, previews (never exchanges) the token, and shows the recipient", async () => {
    const { container } = render(await renderPage({}));

    // Exactly one call, and it is the NON-consuming preview -- never the
    // consuming exchange endpoint.
    expect(fetch).toHaveBeenCalledTimes(1);
    const [target] = (fetch as Mock).mock.calls[0];
    expect(String(target)).toContain("/api/visa/voa/auth/magic-links/preview");
    expect(String(target)).not.toContain("/sessions");

    const form = container.querySelector("form");
    expect(form?.getAttribute("method")).toBe("post");
    expect(form?.getAttribute("action")).toBe("/visa/voa/auth/exchange");
    expect(
      screen.getByRole("button", { name: /continue/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(MASKED_EMAIL)).toBeInTheDocument();
  });

  it("puts NO token, NO raw email, and NO field of any kind in the document", async () => {
    const { container } = render(await renderPage({}));

    // The whole reason ../route.ts redirects instead of rendering: this
    // markup is what Google Analytics' page_view sits alongside.
    expect(container.innerHTML).not.toContain(TOKEN);
    expect(
      container.querySelector(`input[name="${PENDING_COOKIE}"]`),
    ).toBeNull();
    expect(container.querySelector('input[name="magic_token"]')).toBeNull();
    // The form submits NOTHING. A hidden result_id was forgeable and unbound
    // from the token; both halves now ride in the cookie (council, 2026-08-28).
    expect(container.querySelector("input")).toBeNull();
    expect(container.innerHTML).not.toContain(RESULT_ID);
    // Only the MASKED identifier the backend returned may appear -- never
    // an unmasked address (masking itself is pinned server-side; this only
    // proves the page never reconstructs or displays anything else).
    expect(container.innerHTML).toContain(MASKED_EMAIL);
  });

  it("404s when the dark-launch flag is off", async () => {
    delete process.env.GARUDA_PUBLIC_ENABLED;
    await expect(renderPage({})).rejects.toThrow("NEXT_NOT_FOUND");
    expect(notFoundMock).toHaveBeenCalled();
  });

  it("offers no button when no token is in flight", async () => {
    // Nothing to submit — a scanner that followed the redirect, or a stale
    // bookmark. Showing the button would be a lie.
    cookieStore.value = undefined;
    const { container } = render(await renderPage({}));

    expect(container.querySelector("form")).toBeNull();
    expect(screen.getByText(/used or has expired/i)).toBeInTheDocument();
  });

  it.each([
    ["an error marker from a refused exchange", { error: "invalid" }],
    ["an error marker with any other value", { error: "" }],
  ])("offers no form for %s", async (_label, sp) => {
    const { container } = render(
      await renderPage(sp as Record<string, string>),
    );

    expect(container.querySelector("form")).toBeNull();
    expect(screen.getByText(/used or has expired/i)).toBeInTheDocument();
  });

  it.each([
    ["holds a token but no result id", TOKEN],
    ["holds a result id but no token", RESULT_ID],
    ["has an empty result-id half", `.${TOKEN}`],
    ["has a malformed result id", `../...${TOKEN}`],
    ["has a token below the backend minimum", `${RESULT_ID}.short`],
  ])("offers no form when the pending cookie %s", async (_label, value) => {
    // The page must not promise a button the exchange will refuse: the
    // cookie has to decode to a WELL-FORMED pair, not merely be present.
    cookieStore.value = value;
    const { container } = render(await renderPage({}));

    expect(container.querySelector("form")).toBeNull();
    expect(screen.getByText(/used or has expired/i)).toBeInTheDocument();
  });

  // ============================================================
  // previewMagicLink lookup -- the residual login-CSRF finding this
  // revision closes. These are the safety property that matters: a
  // well-formed cookie is NOT enough to offer Continue if the backend says
  // the token itself is no longer live.
  // ============================================================

  it("offers no form when the preview lookup says the token is invalid", async () => {
    // A well-formed pending cookie (passes the earlier check) but a token
    // the backend no longer recognises -- expired, consumed, or foreign.
    // This is exactly the mutation-verify property from the brief: if the
    // page offered Continue here, this test must fail.
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          previewResponse({ code: "MAGIC_LINK_INVALID" }, 401),
        ),
    );

    const { container } = render(await renderPage({}));

    expect(container.querySelector("form")).toBeNull();
    expect(screen.getByText(/used or has expired/i)).toBeInTheDocument();
  });

  it("offers no form when the preview lookup transport fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNRESET")));

    const { container } = render(await renderPage({}));

    expect(container.querySelector("form")).toBeNull();
    expect(screen.getByText(/used or has expired/i)).toBeInTheDocument();
  });

  it("offers no form when the preview lookup returns a malformed body", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(previewResponse({})));

    const { container } = render(await renderPage({}));

    expect(container.querySelector("form")).toBeNull();
    expect(screen.getByText(/used or has expired/i)).toBeInTheDocument();
  });

  it("gives the SAME failure copy for an invalid-cookie failure and a preview-lookup failure", async () => {
    // DECISIONS.md Q1's non-enumeration requirement is about the wire
    // response, but this page must not let a human reading it infer WHICH
    // failure they hit either -- both dead-ends read identically.
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          previewResponse({ code: "MAGIC_LINK_INVALID" }, 401),
        ),
    );
    const previewFailure = render(await renderPage({}));

    cookieStore.value = undefined;
    const cookieFailure = render(await renderPage({}));

    expect(previewFailure.container.innerHTML).toBe(
      cookieFailure.container.innerHTML,
    );
  });
});

// ---------------------------------------------------------------------------
// THE HOP THIS PAGE EXISTS ON THE FAR SIDE OF.
//
// The funnel carries `?lang=id` across `router.push` in sessionStorage. This
// screen is reached from an EMAIL — a new tab, where that carry is gone — and
// it is a SERVER component, so browser storage is unreadable from here even in
// principle. The journey cookie is the only channel left, and these are the
// tests that say so out loud.
// ---------------------------------------------------------------------------
describe("/visa/voa/auth/continue — the language survives the email", () => {
  const original = process.env.GARUDA_PUBLIC_ENABLED;

  beforeEach(() => {
    notFoundMock.mockClear();
    process.env.GARUDA_PUBLIC_ENABLED = "true";
    cookieStore.value = `${RESULT_ID}.${TOKEN}`;
    cookieStore.lang = undefined;
    (fetch as Mock).mockReset();
    (fetch as Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ masked_email: MASKED_EMAIL }),
    });
  });

  afterEach(() => {
    process.env.GARUDA_PUBLIC_ENABLED = original;
  });

  it("speaks Indonesian when the journey cookie says so, with NO query string", async () => {
    cookieStore.lang = "id";
    render(await renderPage({}));
    expect(screen.getByText("Lanjutkan permohonan Anda")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Lanjutkan" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Continue your application")).toBeNull();
  });

  it("FALSIFICATION: no cookie, no query — the door is English", async () => {
    render(await renderPage({}));
    expect(screen.getByText("Continue your application")).toBeInTheDocument();
    expect(screen.queryByText("Lanjutkan permohonan Anda")).toBeNull();
  });

  it("an explicit ?lang= on this url outranks the cookie", async () => {
    cookieStore.lang = "id";
    render(await renderPage({ lang: "en" }));
    expect(screen.getByText("Continue your application")).toBeInTheDocument();
  });

  it("a junk cookie is an English visitor, not an error", async () => {
    cookieStore.lang = "klingon";
    render(await renderPage({}));
    expect(screen.getByText("Continue your application")).toBeInTheDocument();
    expect(notFoundMock).not.toHaveBeenCalled();
  });

  /**
   * The masked address is the anti-CSRF affordance of this screen ("if that
   * is not you, close this page"), so it must keep its emphasis in BOTH
   * languages — the sentence is split on the `{email}` placeholder rather
   * than flattened, and this is the test that would catch a flattening.
   */
  it("the masked address keeps its emphasis in both languages", async () => {
    for (const lang of ["en", "id"]) {
      cookieStore.lang = lang;
      const { container, unmount } = render(await renderPage({}));
      const strong = container.querySelector("strong");
      expect(strong?.textContent, lang).toBe(MASKED_EMAIL);
      unmount();
    }
  });

  it("the expired-link notice is Indonesian too", async () => {
    cookieStore.lang = "id";
    cookieStore.value = undefined; // no token in flight → InvalidLinkNotice
    render(await renderPage({}));
    expect(
      screen.getByText("Tautan ini sudah dipakai atau sudah kedaluwarsa."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Kirimkan tautan baru" }),
    ).toBeInTheDocument();
  });
});
