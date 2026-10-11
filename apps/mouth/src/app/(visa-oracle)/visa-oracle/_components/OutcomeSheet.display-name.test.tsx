import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { buildEngineOutcome } from "../_lib/engine-adapter";
import type { Language } from "../_lib/flow";
import { makeVisaOracleResponse } from "../_lib/visa-oracle-test-fixture";
import { candidateDisplayName, OutcomeSheet } from "./OutcomeSheet";

// The pack names 37 of its 38 products with a trailing "(CODE)". The card
// eyebrow and the share line already lead with the code, so the same code
// must be printed once, not twice ("E23 - Working Visa (E23)").

describe("candidateDisplayName", () => {
  it("strips a trailing ' (CODE)' equal to the candidate's own code", () => {
    expect(candidateDisplayName("E23", "Working Visa (E23)")).toBe(
      "Working Visa",
    );
    expect(
      candidateDisplayName(
        "E23V",
        "Visa Kerja Kantor Dagang dan Ekonomi (E23V)",
      ),
    ).toBe("Visa Kerja Kantor Dagang dan Ekonomi");
  });

  it("keeps a suffix that is a different code, or not at the end", () => {
    expect(candidateDisplayName("E23", "Working Visa (E23U)")).toBe(
      "Working Visa (E23U)",
    );
    expect(candidateDisplayName("E23", "Working Visa (E23) renewal")).toBe(
      "Working Visa (E23) renewal",
    );
    expect(candidateDisplayName("E23", "Working Visa")).toBe("Working Visa");
  });

  it("never returns an empty name", () => {
    expect(candidateDisplayName("E23", "(E23)")).toBe("(E23)");
  });
});

function outcomeNamed(
  name: { en: string; id: string },
  code: string,
  quoted = true,
) {
  const response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
  const candidate = response.display.candidates[0];
  Object.assign(candidate, { name, product_code: code });
  if (!quoted) response.decision.quotes = [];
  return buildEngineOutcome(response);
}

async function renderAndCopy(
  outcome: ReturnType<typeof outcomeNamed>,
  language: Language,
) {
  const { container } = render(
    <OutcomeSheet language={language} outcome={outcome} facts={{}} />,
  );
  const writeText = navigator.clipboard.writeText as ReturnType<typeof vi.fn>;
  writeText.mockClear();
  fireEvent.click(
    screen.getByRole("button", {
      name: language === "id" ? "Salin ringkasan" : "Copy summary",
    }),
  );
  await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
  return {
    summary: writeText.mock.calls[0]?.[0] as string,
    title: container.querySelector(".oracle-candidate-card__title")
      ?.textContent,
    eyebrow: container.querySelector(".oracle-eyebrow")?.textContent,
  };
}

describe("OutcomeSheet — product code shown once", () => {
  const name = {
    en: "Working Visa - Trade and Economic Office (E23V)",
    id: "Visa Kerja Kantor Dagang dan Ekonomi (E23V)",
  };

  it.each([
    ["en", "Working Visa - Trade and Economic Office"],
    ["id", "Visa Kerja Kantor Dagang dan Ekonomi"],
  ] as const)(
    "%s: card title and share line carry the code once",
    async (language, bare) => {
      const { summary, title, eyebrow } = await renderAndCopy(
        outcomeNamed(name, "E23V"),
        language,
      );
      expect(eyebrow).toBe("E23V");
      expect(title).toBe(bare);
      expect(summary).toContain(`E23V — ${bare}`);
      expect(summary.match(/E23V/g)).toHaveLength(1);
    },
  );

  it("a name whose suffix is another code is left as the pack wrote it", async () => {
    const { summary, title } = await renderAndCopy(
      outcomeNamed(
        { en: "Working Visa (E23U)", id: "Visa Kerja (E23U)" },
        "E23",
      ),
      "en",
    );
    expect(title).toBe("Working Visa (E23U)");
    expect(summary).toContain("E23 — Working Visa (E23U)");
  });
});
