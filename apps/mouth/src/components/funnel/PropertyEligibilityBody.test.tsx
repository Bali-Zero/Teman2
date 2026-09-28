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
  verdict: {
    can_invest: true,
    risk_level: "MEDIUM",
    score: 63,
    label: "YELLOW",
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

  it("renders zone + verdict + opportunities from real backend shape, with no PMA-open badge (section 2 must not contradict section 3)", async () => {
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
    expect(screen.getByText(/Investment score:/)).toBeInTheDocument();
    expect(screen.getByText(/63\/100/)).toBeInTheDocument();
    expect(screen.getByText(/YELLOW/)).toBeInTheDocument();
    expect(screen.getByText(/MEDIUM/)).toBeInTheDocument();
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

  it("renders YELLOW verdict with colored pill (not plain gray text)", async () => {
    mockAnalyzeOnce(PROD_SHAPE_RESPONSE);

    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wni");
    selectUse("own_use");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    const yellowEl = await screen.findByText(/^YELLOW$/);
    // Pill span has explicit color style (not inherit text-secondary gray)
    const style = yellowEl.getAttribute("style") ?? "";
    expect(style).toMatch(/color:/);
    expect(style).toMatch(/background/);
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
