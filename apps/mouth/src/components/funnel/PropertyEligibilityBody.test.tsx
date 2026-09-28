import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { PropertyEligibilityBody } from "./PropertyEligibilityBody";

vi.mock("@/lib/analytics", () => ({
  trackPropertyAnalyzeCTA: vi.fn(),
  trackPropertyWACTA: vi.fn(),
  trackPropertyBuyerSelected: vi.fn(),
  trackPropertyUseSelected: vi.fn(),
}));

const PROD_SHAPE_RESPONSE = {
  status: "analyzed",
  coordinates: { lat: -8.65, lng: 115.13 },
  zone: {
    code: "C-1",
    name: "High-Intensity Mixed Use",
    source: "batara_live",
    desa: "Desa Canggu",
    kecamatan: "",
    kdb: "60%",
    klb: "1,8",
    kdh: "30%",
    tb: "15 Meter",
    gsb: "One lane of road space and added with road verge.",
    overlays: {},
  },
  opportunities: [
    { title_en: "Villas", category_en: "Hospitality", pma_open: true },
    {
      title_en: "Software publishing",
      category_en: "Technology",
      pma_open: true,
    },
  ],
  sea_distance_m: 18563.3,
};

function fillCoord() {
  fireEvent.change(screen.getByPlaceholderText(/Google Maps/i), {
    target: { value: "-8.65, 115.13" },
  });
}

function selectBuyer(value: string) {
  fireEvent.change(screen.getByLabelText(/Buyer profile/i), {
    target: { value },
  });
}

function selectUse(value: string) {
  fireEvent.change(screen.getByLabelText(/Intended use/i), {
    target: { value },
  });
}

function mockAnalyzeOnce(body: unknown) {
  (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: true,
    json: async () => body,
  } as Response);
}

// B1 (gate-7596-report.md v2, REWORK-BUILD): the report must never grade the
// purchase — no GREEN/YELLOW/RED, no "Risk:", no "Investment score", no
// "Allowed", and no POSITIVE "open to ... PT PMA" claim. Two sentences
// legitimately contain that word sequence without being a positive claim:
// "is not open to a PT PMA" (the villa caveat) and "Whether this activity is
// open to a PT PMA here depends on the exact business code" (the conditional,
// generic-use copy) — both must stay allowed.
//
// Checked per <p> (not over the whole container's flattened textContent):
// RTL/jsdom's textContent concatenates ADJACENT ELEMENTS with no separator
// (e.g. a heading "...with it" directly followed by a paragraph "Whether...
// depends" reads back as "...with itWhether...depends", which breaks a
// \b-word-boundary check on "whether"/"depends" — there is no boundary
// between two letters). Every sentence this component renders lives whole
// inside one <p>, so scanning per-<p> sidesteps that DOM-flattening trap
// instead of trying to out-clever it with sentence-splitting regex.
function findPositivePmaOpenClaims(container: HTMLElement): string[] {
  const paragraphs = Array.from(container.querySelectorAll("p")).map(
    (p) => p.textContent ?? "",
  );
  return paragraphs.filter((s) => {
    if (!/open to (?:a |an |the )?PT\s?PMA/i.test(s)) return false;
    if (/\bnot open to (?:a |an |the )?PT\s?PMA/i.test(s)) return false;
    if (/\bwhether\b/i.test(s) && /\bdepends\b/i.test(s)) return false;
    return true;
  });
}

describe("PropertyEligibilityBody", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders input + analyze button on mount", () => {
    render(<PropertyEligibilityBody />);
    expect(screen.getByPlaceholderText(/Google Maps/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Analyze/i }),
    ).toBeInTheDocument();
  });

  it("rejects bad input with error message", async () => {
    render(<PropertyEligibilityBody />);
    fillCoord();
    fireEvent.change(screen.getByPlaceholderText(/Google Maps/i), {
      target: { value: "garbage" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));
    expect(
      await screen.findByText(/Format not recognized/i),
    ).toBeInTheDocument();
  });

  // Guard test (a): the buyer selector has no default, and analyzing without
  // one selected never reaches fetch — so a country name (or anything else)
  // can never be sent in its place.
  it("has no default buyer selected, and blocks analyze until one is chosen", async () => {
    render(<PropertyEligibilityBody />);
    const buyerSelect = screen.getByLabelText(
      /Buyer profile/i,
    ) as HTMLSelectElement;
    expect(buyerSelect.value).toBe("");

    fillCoord();
    selectUse("restaurant");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));
    expect(
      await screen.findByText(/Select who is buying/i),
    ).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  // Guard test (a), continued: once a buyer IS selected, the request body's
  // investor_profile.nationality is always the literal "WNI"/"WNA" — never a
  // country name (spec-property-check.md §3). REWORK-DESIGN v2
  // (spec-property-check-v2.md): the request also never carries kbli_code or
  // is_pma — section 3 is static copy, not a KBLIEye call.
  it("sends only the literal WNA nationality for a foreign buyer, never a country name or kbli_code/is_pma", async () => {
    mockAnalyzeOnce(PROD_SHAPE_RESPONSE);

    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wna_individual");
    selectUse("own_use");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call[0]).toBe("/api/prime/v2/analyze");
    const body = JSON.parse(call[1].body);
    expect(body.investor_profile).toEqual({ nationality: "WNA" });
    expect(body).not.toHaveProperty("kbli_code");
    expect(body).not.toHaveProperty("is_pma");
  });

  it("renders zone + opportunities from real backend shape, with no PMA-open badge (section 2 must not contradict section 3)", async () => {
    mockAnalyzeOnce(PROD_SHAPE_RESPONSE);

    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wni");
    selectUse("own_use");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    await waitFor(() => expect(screen.getByText(/C-1/)).toBeInTheDocument());
    expect(screen.getByText(/High-Intensity Mixed Use/)).toBeInTheDocument();
    expect(screen.getByText(/Desa Canggu/)).toBeInTheDocument();
    expect(screen.getByText(/KDB: 60%/)).toBeInTheDocument();
    expect(screen.getByText(/KLB: 1,8/)).toBeInTheDocument();
    expect(screen.getByText(/TB: 15 Meter/)).toBeInTheDocument();
    expect(screen.getByText(/What may be built here/)).toBeInTheDocument();
    expect(screen.getByText(/Villas/)).toBeInTheDocument();
    expect(screen.getByText(/Software publishing/)).toBeInTheDocument();
    expect(screen.queryByText(/PMA open/)).not.toBeInTheDocument();
  });

  it("shows HTTP error toast on non-ok response", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 502,
      json: async () => ({ error: "upstream" }),
    } as Response);

    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wni");
    selectUse("own_use");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    await waitFor(() =>
      expect(
        screen.getByText(/Error 502: zone not analyzable/),
      ).toBeInTheDocument(),
    );
  });

  // F4 (gate-7596-report.md): the proxy (api/prime/v2/analyze/route.ts)
  // answers HTTP 200 with {status:"error"} on an upstream failure — the
  // component must not render "Zone: n/a" for that shape.
  it("treats an HTTP 200 {status:'error'} proxy response as an error, never 'Zone: n/a'", async () => {
    mockAnalyzeOnce({ status: "error", error: "Analysis unavailable" });

    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wni");
    selectUse("own_use");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.queryByText(/Zone: n\/a/)).not.toBeInTheDocument();
  });

  it("treats a 200 response with no zone payload as an error, never 'Zone: n/a'", async () => {
    mockAnalyzeOnce({ status: "analyzed" });

    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wni");
    selectUse("own_use");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.queryByText(/Zone: n\/a/)).not.toBeInTheDocument();
  });

  it("shows WA Delega CTA after successful analyze", async () => {
    mockAnalyzeOnce(PROD_SHAPE_RESPONSE);

    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wni");
    selectUse("own_use");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    const waLink = (await screen.findByRole("link", {
      name: /Talk to Bali Zero/i,
    })) as HTMLAnchorElement;
    expect(waLink.href).toContain("wa.me/628213454721");
  });

  it("dedupes duplicate opportunities from backend", async () => {
    const dupeResponse = {
      ...PROD_SHAPE_RESPONSE,
      opportunities: [
        {
          title_en: "Government Elementary School (SD/MI)",
          category_en: "Education",
          pma_open: false,
        },
        {
          title_en: "Government Elementary School (SD/MI)",
          category_en: "Education",
          pma_open: false,
        },
        { title_en: "Villas", category_en: "Hospitality", pma_open: true },
      ],
    };
    mockAnalyzeOnce(dupeResponse);

    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wni");
    selectUse("own_use");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    await waitFor(() =>
      expect(
        screen.getByText(/Government Elementary School/),
      ).toBeInTheDocument(),
    );
    // Only ONE "Government Elementary School" despite 2 in payload
    const schools = screen.getAllByText(/Government Elementary School/);
    expect(schools).toHaveLength(1);
    // Villas still shown, no PMA badge (section 2 never renders one anymore)
    expect(screen.getByText("Villas")).toBeInTheDocument();
    expect(screen.queryByText(/PMA open/)).not.toBeInTheDocument();
  });

  it("accepts Google Maps DMS paste (8°39'17.4\"S 115°08'22.3\"E)", async () => {
    mockAnalyzeOnce(PROD_SHAPE_RESPONSE);

    render(<PropertyEligibilityBody />);
    fireEvent.change(screen.getByPlaceholderText(/Google Maps/i), {
      target: { value: "8°39'17.4\"S 115°08'22.3\"E" },
    });
    selectBuyer("wni");
    selectUse("own_use");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    await waitFor(() => expect(screen.getByText(/C-1/)).toBeInTheDocument());
    // Verify backend was called with decimal-converted lat/lng
    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(call[1].body);
    expect(body.lat).toBeCloseTo(-8.6548, 3);
    expect(body.lng).toBeCloseTo(115.1395, 3);
  });

  // --- Section 3 ("What you can do with it") — REWORK-DESIGN v2 ---

  it("own use: no section 3 at all", async () => {
    mockAnalyzeOnce(PROD_SHAPE_RESPONSE);
    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wni");
    selectUse("own_use");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    await waitFor(() => expect(screen.getByText(/C-1/)).toBeInTheDocument());
    expect(
      screen.queryByText(/What you can do with it/),
    ).not.toBeInTheDocument();
  });

  it("WNI + business use: renders the PT PMDN registration copy", async () => {
    mockAnalyzeOnce(PROD_SHAPE_RESPONSE);
    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wni");
    selectUse("restaurant");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    expect(
      await screen.findByText(/local company \(PT PMDN\)/i),
    ).toBeInTheDocument();
  });

  it("WNA individual + business use: renders the PT PMA requirement, then the PMA copy for that use", async () => {
    mockAnalyzeOnce(PROD_SHAPE_RESPONSE);
    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wna_individual");
    selectUse("restaurant");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    expect(
      await screen.findByText(/can.t run a business in Indonesia/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Rp 10 billion per business activity/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/depends on the exact business code/i),
    ).toBeInTheDocument();
  });

  it("PT PMA + villa rental: renders the villa-closed-to-PMA caveat, citing Perpres 10/2021 jo. 49/2021", async () => {
    mockAnalyzeOnce(PROD_SHAPE_RESPONSE);
    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wna_pma");
    selectUse("villa_rental");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    expect(
      await screen.findByText(/reserved for Indonesian small businesses/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Perpres 10\/2021 jo\. 49\/2021/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^49\/2021\D/)).not.toBeInTheDocument();
  });

  it("PT PMA + non-villa business use: renders the generic PMA-eligibility copy, not the villa caveat", async () => {
    mockAnalyzeOnce(PROD_SHAPE_RESPONSE);
    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wna_pma");
    selectUse("office");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    expect(
      await screen.findByText(/depends on the exact business code/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/reserved for Indonesian small businesses/i),
    ).not.toBeInTheDocument();
  });

  // L1: the dataset's l4_bali.closure.effective says third week of May 2026;
  // "13 May 2026" was an agency date, not the dataset's.
  it("the generic PMA-eligibility copy cites 'since May 2026', never a specific day", async () => {
    mockAnalyzeOnce(PROD_SHAPE_RESPONSE);
    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wna_pma");
    selectUse("office");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    expect(await screen.findByText(/since May 2026/)).toBeInTheDocument();
    expect(screen.queryByText(/13 May 2026/)).not.toBeInTheDocument();
  });

  // B1 (gate-7596-report.md v2): even when the backend hands back a graded,
  // GREEN/LOW/90 verdict, the report must never print any of it — across
  // every (buyer, use) combination, own use included (which renders no
  // section 3 body at all, but still must not leak the zone-level verdict).
  it.each([
    ["wni", "own_use"],
    ["wni", "villa_rental"],
    ["wni", "restaurant"],
    ["wni", "retail"],
    ["wni", "office"],
    ["wna_individual", "own_use"],
    ["wna_individual", "villa_rental"],
    ["wna_individual", "restaurant"],
    ["wna_individual", "retail"],
    ["wna_individual", "office"],
    ["wna_pma", "own_use"],
    ["wna_pma", "villa_rental"],
    ["wna_pma", "restaurant"],
    ["wna_pma", "retail"],
    ["wna_pma", "office"],
  ] as const)(
    "never grades the purchase for buyer=%s use=%s",
    async (buyer, use) => {
      mockAnalyzeOnce({
        ...PROD_SHAPE_RESPONSE,
        verdict: {
          can_invest: true,
          risk_level: "LOW",
          score: 90,
          label: "GREEN",
        },
      });
      const { container, unmount } = render(<PropertyEligibilityBody />);
      fillCoord();
      selectBuyer(buyer);
      selectUse(use);
      fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));
      await waitFor(() => expect(screen.getByText(/C-1/)).toBeInTheDocument());

      const text = container.textContent ?? "";
      expect(text).not.toMatch(/\bGREEN\b/);
      expect(text).not.toMatch(/\bYELLOW\b/);
      expect(text).not.toMatch(/\bRED\b/);
      expect(text).not.toMatch(/Risk:/);
      expect(text).not.toMatch(/Investment score/i);
      expect(text).not.toMatch(/\bAllowed\b/i);
      expect(findPositivePmaOpenClaims(container)).toEqual([]);
      unmount();
    },
  );

  // F8 (gate-7596-report.md): section 3 must read the analysed snapshot, not
  // the live selects.
  it("section 3 stays on the analysed snapshot after the selects change, until the next analyze", async () => {
    mockAnalyzeOnce(PROD_SHAPE_RESPONSE);
    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wni");
    selectUse("restaurant");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    expect(
      await screen.findByText(/local company \(PT PMDN\)/i),
    ).toBeInTheDocument();

    // Change the live selects post-analysis — the printed copy must not move.
    selectBuyer("wna_pma");
    selectUse("villa_rental");

    expect(screen.getByText(/local company \(PT PMDN\)/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/reserved for Indonesian small businesses/i),
    ).not.toBeInTheDocument();
  });
});
