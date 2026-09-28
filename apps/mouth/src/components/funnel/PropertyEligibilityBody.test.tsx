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
  kbli: null as unknown,
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
  // country name (spec-property-check.md §3).
  it("sends only the literal WNA nationality for a foreign buyer, never a country name", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => PROD_SHAPE_RESPONSE,
    } as Response);

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
    expect(body.is_pma).toBe(false);
  });

  // Guard test (b): "villa rental" must send KBLI 68112 (never 55203, which
  // is reserved 0% to Koperasi/UMKM) and must render the caveat.
  it("sends KBLI 68112 (not 55203) for villa rental and renders the caveat", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ...PROD_SHAPE_RESPONSE,
        kbli: {
          code: "68112",
          title: "Aktivitas Penyewaan Bangunan dan Lahan Hunian",
          state: "WARNING",
          reason: "PMA_NOT_VERIFIED",
          max_foreign_ownership: null,
        },
      }),
    } as Response);

    render(<PropertyEligibilityBody />);
    fillCoord();
    selectBuyer("wna_pma");
    selectUse("villa_rental");
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(call[1].body);
    expect(body.kbli_code).toBe("68112");

    expect(
      await screen.findByText(/never offers KBLI 55203/i),
    ).toBeInTheDocument();
  });

  it("renders zone + verdict + opportunities from real backend shape", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => PROD_SHAPE_RESPONSE,
    } as Response);

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

  it("shows WA Delega CTA after successful analyze", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => PROD_SHAPE_RESPONSE,
    } as Response);

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
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => dupeResponse,
    } as Response);

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
    // Villas still shown + PMA badge visible
    expect(screen.getByText("Villas")).toBeInTheDocument();
    expect(screen.getByText("PMA open")).toBeInTheDocument();
  });

  it("renders YELLOW verdict with colored pill (not plain gray text)", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => PROD_SHAPE_RESPONSE,
    } as Response);

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
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => PROD_SHAPE_RESPONSE,
    } as Response);

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
});
