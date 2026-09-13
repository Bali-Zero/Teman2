import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { KBLIDivergence, authorityLabel } from "./KBLIDivergence";

describe("authorityLabel helper", () => {
  it("returns null for undefined", () => {
    expect(authorityLabel(undefined)).toBeNull();
  });

  it("returns null for empty string ''", () => {
    expect(authorityLabel("")).toBeNull();
  });

  it("returns trimmed string for single non-empty string 'OSS'", () => {
    expect(authorityLabel("OSS")).toBe("OSS");
  });

  it("returns null for empty array []", () => {
    expect(authorityLabel([])).toBeNull();
  });

  it("returns single element string for array ['Gubernur']", () => {
    expect(authorityLabel(["Gubernur"])).toBe("Gubernur");
  });

  it("joins multiple array elements with comma-space", () => {
    expect(authorityLabel(["Bupati/Walikota", "Menteri", "Gubernur"])).toBe(
      "Bupati/Walikota, Menteri, Gubernur",
    );
  });

  it("filters out empty and whitespace-only elements inside array", () => {
    expect(authorityLabel(["", "   "])).toBeNull();
    expect(authorityLabel(["Gubernur", "", "  ", "Menteri"])).toBe(
      "Gubernur, Menteri",
    );
  });
});

describe("KBLIDivergence component rendering", () => {
  const baseProvenance = {
    state: "not_classifiable" as const,
    definition: { locator: null, assembly: null },
    licensing: {
      status: "detached" as const,
      locator: null,
      vintage: null,
      noOssScope: false,
      contentInheritedFrom: null,
    },
    pma: {
      source: null,
      vintage: null,
      status: "declared_gap" as const,
      locator: null,
    },
    dataNote: "Test correction note",
  };

  it("does not render Authority line when kewenangan is empty array []", () => {
    const provenance = {
      ...baseProvenance,
      disputed: {
        key: "per_skala_disputed_pp28_test",
        rows: [
          {
            skala_usaha: ["Mikro" as const],
            kategori_risiko: "Rendah",
            kewenangan: [],
          },
        ],
      },
    };

    render(<KBLIDivergence code="12345" provenance={provenance} />);
    expect(screen.queryByText(/Authority:/)).toBeNull();
  });

  it("renders joined Authority line when kewenangan is an array of strings", () => {
    const provenance = {
      ...baseProvenance,
      disputed: {
        key: "per_skala_disputed_pp28_test",
        rows: [
          {
            skala_usaha: ["Mikro" as const],
            kategori_risiko: "Rendah",
            kewenangan: ["Bupati/Walikota", "Menteri", "Gubernur"],
          },
        ],
      },
    };

    render(<KBLIDivergence code="12345" provenance={provenance} />);
    expect(
      screen.getByText("Authority: Bupati/Walikota, Menteri, Gubernur"),
    ).toBeInTheDocument();
  });
});
