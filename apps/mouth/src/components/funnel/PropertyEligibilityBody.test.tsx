import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { PropertyEligibilityBody } from "./PropertyEligibilityBody";

vi.mock("@/lib/analytics", () => ({
  trackPropertyAnalyzeCTA: vi.fn(),
  trackPropertyWACTA: vi.fn(),
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
    const input = screen.getByPlaceholderText(/Google Maps/i);
    fireEvent.change(input, { target: { value: "garbage" } });
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));
    expect(
      await screen.findByText(/Format not recognized/i),
    ).toBeInTheDocument();
  });

  it("renders zone + verdict + opportunities from real backend shape", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => PROD_SHAPE_RESPONSE,
    } as Response);

    render(<PropertyEligibilityBody />);
    fireEvent.change(screen.getByPlaceholderText(/Google Maps/i), {
      target: { value: "-8.65, 115.13" },
    });
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
    expect(
      screen.getByText(/KBLI opportunities open to PMA:/),
    ).toBeInTheDocument();
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
    fireEvent.change(screen.getByPlaceholderText(/Google Maps/i), {
      target: { value: "-8.65, 115.13" },
    });
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
    fireEvent.change(screen.getByPlaceholderText(/Google Maps/i), {
      target: { value: "-8.65, 115.13" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    const waLink = (await screen.findByRole("link", {
      name: /Talk to Bali Zero/i,
    })) as HTMLAnchorElement;
    expect(waLink.href).toContain("wa.me/628213107363");
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
    fireEvent.change(screen.getByPlaceholderText(/Google Maps/i), {
      target: { value: "-8.65, 115.13" },
    });
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
    expect(screen.getByText("PMA")).toBeInTheDocument();
  });

  it("renders YELLOW verdict with colored pill (not plain gray text)", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => PROD_SHAPE_RESPONSE,
    } as Response);

    render(<PropertyEligibilityBody />);
    fireEvent.change(screen.getByPlaceholderText(/Google Maps/i), {
      target: { value: "-8.65, 115.13" },
    });
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
    fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));

    await waitFor(() => expect(screen.getByText(/C-1/)).toBeInTheDocument());
    // Verify backend was called with decimal-converted lat/lng
    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(call[1].body);
    expect(body.lat).toBeCloseTo(-8.6548, 3);
    expect(body.lng).toBeCloseTo(115.1395, 3);
  });
});
