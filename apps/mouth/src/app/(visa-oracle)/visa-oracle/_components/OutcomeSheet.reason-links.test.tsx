import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { buildEngineOutcome } from "../_lib/engine-adapter";
import { makeVisaOracleResponse } from "../_lib/visa-oracle-test-fixture";
import { OutcomeSheet } from "./OutcomeSheet";

afterEach(cleanup);

const BVK_URL =
  "https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-bebas-visa-kunjungan";

function renderNoPath(
  language: "en" | "id",
  mutate?: (messages: { en: string; id: string }) => void,
  code = "BVK_NATIONALITY_ONLY",
) {
  const response = makeVisaOracleResponse("NO_SUPPORTED_PATH");
  response.decision.no_path_reasons[0].code = code;
  const outcome = buildEngineOutcome(response, {
    facts: { category: "tourism" },
  });
  if (outcome.state !== "NO_SUPPORTED_PATH") throw new Error("unexpected");
  if (mutate) mutate(outcome.noPathReasons[0].message);
  return render(
    <OutcomeSheet language={language} outcome={outcome} facts={{}} />,
  );
}

describe("OutcomeSheet links the official URL inside a reason", () => {
  it.each(["en", "id"] as const)(
    "BVK reason renders an anchor to the official list (%s)",
    (language) => {
      const { container } = renderNoPath(language);
      const link = container.querySelector(`a[href="${BVK_URL}"]`);
      expect(link).not.toBeNull();
      expect(link?.getAttribute("target")).toBe("_blank");
      expect(link?.getAttribute("rel")).toBe("noopener noreferrer");
      expect(link?.textContent).toBe(BVK_URL);
    },
  );

  it("keeps the trailing period and comma outside the href", () => {
    const { container } = renderNoPath("en", (m) => {
      m.en = `See https://example.org/list. Then (https://example.org/b), done https://example.org/c.`;
    });
    const hrefs = Array.from(
      container.querySelectorAll(".oracle-reason-list a"),
    ).map((a) => a.getAttribute("href"));
    expect(hrefs).toEqual([
      "https://example.org/list",
      "https://example.org/b",
      "https://example.org/c",
    ]);
    expect(container.textContent).toContain(
      "See https://example.org/list. Then (https://example.org/b), done https://example.org/c.",
    );
  });

  it("does not link http:// or javascript: and injects no HTML", () => {
    const { container } = renderNoPath("en", (m) => {
      m.en =
        "Plain http://example.org/x and javascript:alert(1) and <b>bold</b> https://";
    });
    expect(container.querySelectorAll(".oracle-reason-list a")).toHaveLength(0);
    expect(container.querySelector("b")).toBeNull();
    expect(container.textContent).toContain(
      "Plain http://example.org/x and javascript:alert(1) and <b>bold</b> https://",
    );
  });

  it("a reason without a URL renders as plain text, no anchor", () => {
    const { container } = renderNoPath("en", (m) => {
      m.en = "No link here.";
    });
    expect(container.querySelectorAll(".oracle-reason-list a")).toHaveLength(0);
    expect(container.textContent).toContain("No link here.");
  });
});
