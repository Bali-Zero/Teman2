import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PropertyCheck } from "./PropertyCheck";
import { TaxCalendar } from "./TaxCalendar";
import { Preparation } from "./Preparation";
import { Proposal } from "./Proposal";
import { ZoneAtlas } from "./ZoneAtlas";

describe("native property journeys", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockReset();
  });
  afterEach(() => vi.unstubAllGlobals());
  it("waits for submission and clears stale findings when coordinates change", async () => {
    fetchMock.mockResolvedValue(
      Response.json({
        status: "analyzed",
        zone: { code: "FIXTURE", name: "Synthetic zone" },
        verdict: { score: 42, label: "YELLOW", risk_level: "MEDIUM" },
        roi: { golden_strategy: { roi: 12 }, total_investment_idr: 100 },
      }),
    );
    render(<PropertyCheck />);
    const input = screen.getByLabelText("Property coordinates");
    fireEvent.change(input, { target: { value: "-8.5, 115.25" } });
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Analyze property →" }));
    expect(
      await screen.findByRole("heading", { name: "FIXTURE · Synthetic zone" }),
    ).toBeInTheDocument();
    expect(screen.getByText("ROI · engine estimate")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/property/analyze");
    fireEvent.change(input, { target: { value: "-8.6, 115.25" } });
    expect(
      screen.queryByRole("heading", { name: "FIXTURE · Synthetic zone" }),
    ).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("keeps unsupported coverage distinct from a successful eligibility result", async () => {
    fetchMock.mockResolvedValue(
      Response.json({
        status: "analyzed",
        zone: null,
        verdict: { score: 0, label: "RED" },
      }),
    );
    render(<PropertyCheck />);
    fireEvent.change(screen.getByLabelText("Property coordinates"), {
      target: { value: "-8.5, 115.25" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyze property →" }));
    expect(
      await screen.findByRole("heading", {
        name: "No supported zone returned.",
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Engine assessment")).not.toBeInTheDocument();
  });
  it("shows configuration failures without manufacturing findings", async () => {
    fetchMock.mockResolvedValue(
      Response.json({ error: "not_configured" }, { status: 503 }),
    );
    render(<PropertyCheck />);
    fireEvent.change(screen.getByLabelText("Property coordinates"), {
      target: { value: "-8.5, 115.25" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyze property →" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "not connected in this preview",
    );
    expect(screen.queryByText("Engine assessment")).not.toBeInTheDocument();
  });
  it("requires explicit proposal open and preserves expired state", async () => {
    fetchMock.mockResolvedValue(
      Response.json({ error: "expired" }, { status: 410 }),
    );
    render(<Proposal token="synthetic-token" />);
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Open proposal →" }));
    expect(
      await screen.findByRole("heading", {
        name: "This proposal has expired.",
      }),
    ).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(
      screen.queryByRole("button", { name: "Open proposal →" }),
    ).not.toBeInTheDocument();
  });
  it("loads actual returned geometry and supports keyboard zone selection and comparison", async () => {
    const onSelect = vi.fn();
    fetchMock.mockResolvedValue(
      Response.json({
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            geometry: {
              type: "Polygon",
              coordinates: [
                [
                  [115, -8],
                  [115.1, -8],
                  [115.1, -8.1],
                  [115, -8],
                ],
              ],
            },
            properties: {
              zone_code: "FIXTURE",
              zone_type: "Test zone",
              color: "#aabbcc",
              kdb: 40,
            },
          },
        ],
      }),
    );
    render(<ZoneAtlas selected={null} onSelect={onSelect} />);
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Load zoning layer" }));
    const select = await screen.findByLabelText("Inspect a zone");
    fireEvent.change(select, { target: { value: "FIXTURE" } });
    expect(onSelect).toHaveBeenCalledWith({ lat: -8, lng: 115 });
    fireEvent.click(screen.getByRole("button", { name: "Compare zone" }));
    expect(
      screen.getByRole("region", { name: "Zone comparison" }),
    ).toHaveTextContent("40");
    fireEvent.click(screen.getByRole("button", { name: "Remove FIXTURE" }));
    expect(
      screen.queryByRole("region", { name: "Zone comparison" }),
    ).not.toBeInTheDocument();
  });
});

describe("tax and due diligence journeys", () => {
  it("filters the visible archive and updates the export link", () => {
    render(<TaxCalendar />);
    expect(
      screen.getByText("Historical calendar · April–July 2026"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "PB1" }));
    fireEvent.change(screen.getByLabelText("Regency"), {
      target: { value: "Badung" },
    });
    expect(screen.getByRole("status")).toHaveTextContent("1 record");
    expect(
      screen.queryByRole("heading", { name: "PB1 Gianyar" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Export filtered archive (.ics) ↓" }),
    ).toHaveAttribute("href", "/api/tax-calendar/ical?kind=PB1&regency=Badung");
  });
  it.each(["tax", "property"] as const)(
    "provides a reversible preparation checklist for %s",
    async (family) => {
      render(<Preparation family={family} />);
      const boxes = screen.getAllByRole("checkbox");
      expect(boxes.length).toBeGreaterThan(3);
      fireEvent.click(boxes[0]);
      expect(screen.getByRole("status")).toHaveTextContent("1 of");
      fireEvent.click(screen.getByRole("button", { name: "Reset checklist" }));
      await waitFor(() => expect(boxes[0]).not.toBeChecked());
    },
  );
});
