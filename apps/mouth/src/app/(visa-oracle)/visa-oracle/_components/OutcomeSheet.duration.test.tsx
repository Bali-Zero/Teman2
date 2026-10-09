import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { buildEngineOutcome } from "../_lib/engine-adapter";
import type { Language } from "../_lib/flow";
import { makeVisaOracleResponse } from "../_lib/visa-oracle-test-fixture";
import { OutcomeSheet } from "./OutcomeSheet";

const option = (days: number, amount: number | null, selected: boolean) => ({
  days,
  amount_idr: amount,
  selected,
  status: "AVAILABLE",
  reason_code: "DURATION_OPTION",
  pricing_key: {
    category: "visa",
    item_key: days === 365 ? "E31A_1Y" : "E31A_2Y",
  },
});

function outcomeWith(extra: Record<string, unknown>) {
  const response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
  const candidate = response.display.candidates[0];
  Object.assign(candidate, extra);
  candidate.pricing = {
    status: "AVAILABLE",
    reason_code: "PRICE_AVAILABLE",
    evaluated_at: "2026-08-03T04:00:00Z",
    catalog_last_updated: "2026-08-03",
    catalog_sha256: "b".repeat(64),
    row_sha256: "c".repeat(64),
  };
  const chosen = (
    (extra.duration_options as ReturnType<typeof option>[] | undefined) ?? []
  ).find((item) => item.selected);
  response.decision.quotes = [
    {
      quote_id: "55555555-5555-4555-8555-555555555555",
      product_version_id: candidate.product_version_id,
      product_code: candidate.product_code,
      status: "AVAILABLE",
      currency: "IDR",
      amount: chosen?.amount_idr ?? 15_000_000,
      pricing_key: chosen?.pricing_key ?? { category: "visa", item_key: "C1" },
      catalog_version: "2026.08",
      catalog_sha256: "b".repeat(64),
      row_sha256: "c".repeat(64),
      quoted_at: "2026-08-03T04:00:00Z",
      valid_until: null,
      reason_code: "PRICE_AVAILABLE",
    },
  ];
  return buildEngineOutcome(response);
}

function priceText(
  extra: Record<string, unknown>,
  language: Language = "en",
): string {
  const { container } = render(
    <OutcomeSheet
      language={language}
      outcome={outcomeWith(extra)}
      facts={{}}
    />,
  );
  return container.querySelector(".oracle-price")?.textContent ?? "";
}

async function copiedSummary(
  extra: Record<string, unknown>,
  language: Language = "en",
): Promise<string> {
  render(
    <OutcomeSheet
      language={language}
      outcome={outcomeWith(extra)}
      facts={{}}
    />,
  );
  const writeText = navigator.clipboard.writeText as ReturnType<typeof vi.fn>;
  writeText.mockClear();
  fireEvent.click(
    screen.getByRole("button", {
      name: language === "id" ? "Salin ringkasan" : "Copy summary",
    }),
  );
  await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
  return writeText.mock.calls[0]?.[0] as string;
}

describe("OutcomeSheet — stay-permit duration under the price", () => {
  it("365 selected: names the 1-year permit and offers the 2-year one", () => {
    const text = priceText({
      selected_duration_days: 365,
      duration_options: [
        option(365, 11_000_000, true),
        option(730, 15_000_000, false),
      ],
      extension_required: false,
    });
    expect(text).toContain("1-year stay permit");
    expect(text).toMatch(/Also available: 2 years — .*15,000,000/);
    expect(text).not.toContain("longer than the longest permit");
  });

  it("730 selected: names the 2-year permit and offers the 1-year one", () => {
    const text = priceText({
      selected_duration_days: 730,
      duration_options: [
        option(365, 11_000_000, false),
        option(730, 15_000_000, true),
      ],
    });
    expect(text).toContain("2-year stay permit");
    expect(text).toMatch(/Also available: 1 year — .*11,000,000/);
  });

  it("a stay beyond the longest permit adds the renewal line", () => {
    const text = priceText({
      selected_duration_days: 730,
      duration_options: [
        option(365, 11_000_000, false),
        option(730, 15_000_000, true),
      ],
      extension_required: true,
    });
    expect(text).toContain("ask your advisor about renewal");
  });

  it("reads in Indonesian", () => {
    const text = priceText(
      {
        selected_duration_days: 730,
        duration_options: [
          option(365, 11_000_000, false),
          option(730, 15_000_000, true),
        ],
      },
      "id",
    );
    expect(text).toContain("Izin tinggal 2 tahun");
    expect(text).toMatch(/Pilihan lain: 1 tahun — /);
  });

  it("lists no option without an amount, and counts non-year permits in days", () => {
    const text = priceText({
      selected_duration_days: 180,
      duration_options: [
        option(180, 5_000_000, true),
        option(365, null, false),
      ],
    });
    expect(text).toContain("180-day stay permit");
    expect(text).not.toContain("Also available");
  });

  it("a product without duration renders the price block exactly as before", () => {
    const text = priceText({});
    expect(text).not.toMatch(/stay permit|Also available/);
    expect(text).toMatch(/Government fees and Bali Zero service included\.$/);
  });

  it("share summary: a candidate with a duration carries price and permit after its name", async () => {
    const summary = await copiedSummary({
      selected_duration_days: 730,
      duration_options: [
        option(365, 11_000_000, false),
        option(730, 15_000_000, true),
      ],
    });
    expect(summary).toMatch(/: IDR\s15,000,000 · 2-year stay permit$/m);
  });

  it("share summary: a candidate without a duration is unchanged", async () => {
    const summary = await copiedSummary({});
    expect(summary).not.toMatch(/stay permit|·/);
    expect(summary).toMatch(/^[A-Z0-9]+ — .+$/m);
  });

  it("share summary reads in Indonesian", async () => {
    const summary = await copiedSummary(
      {
        selected_duration_days: 365,
        duration_options: [
          option(365, 11_000_000, true),
          option(730, 15_000_000, false),
        ],
      },
      "id",
    );
    expect(summary).toMatch(/ · Izin tinggal 1 tahun$/m);
  });
});
