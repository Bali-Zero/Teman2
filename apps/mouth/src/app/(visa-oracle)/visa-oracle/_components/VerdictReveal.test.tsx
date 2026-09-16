import { render, screen } from "@testing-library/react";
import {
  REVIEW_REASON_COPY,
  SECOND_HOME_STUDIO_REVIEW_REASON_CODE,
} from "../_lib/engine-adapter";
import { translate, type I18nKey } from "../_lib/i18n";
import { VerdictReveal } from "./VerdictReveal";

describe("VerdictReveal — D23 Second Home Studio", () => {
  // GUILT: the Studio-only hold must never render the generic human-review
  // headline/description anywhere — no "human", no "algorithm", no
  // "person's judgment".
  it("renders Studio-specific copy, with no human/algorithm wording, when isSecondHomeStudioOnly is true", () => {
    render(
      <VerdictReveal
        language="en"
        state="HUMAN_REVIEW_REQUIRED"
        provenance="ENGINE"
        isSecondHomeStudioOnly
      />,
    );

    expect(
      screen.getByText("Below the Second Home guarantee threshold"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /The guarantee figure you declared doesn.t reach the Second Home \(E33\) thresholds/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("This needs a human, not an algorithm"),
    ).toBeNull();
    expect(
      screen.queryByText(/Bali Zero advisor reviews cases like yours/),
    ).toBeNull();
    expect(document.body.textContent).not.toMatch(/algorithm/i);
    expect(document.body.textContent).not.toMatch(/\ba human\b/i);
  });

  it("renders the ID Studio-specific copy, with no human wording, when isSecondHomeStudioOnly is true", () => {
    render(
      <VerdictReveal
        language="id"
        state="HUMAN_REVIEW_REQUIRED"
        provenance="ENGINE"
        isSecondHomeStudioOnly
      />,
    );

    expect(
      screen.getByText("Di bawah ambang batas jaminan Second Home"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/belum mencapai ambang batas Rumah Kedua \(E33\)/),
    ).toBeInTheDocument();
    expect(screen.queryByText("Ini butuh manusia, bukan algoritma")).toBeNull();
    expect(document.body.textContent).not.toMatch(/manusia/i);
  });

  // INNOCENCE: an unrelated (or absent) Studio flag keeps the pre-existing
  // generic human-review copy exactly as before.
  it("keeps the generic human-review headline when isSecondHomeStudioOnly is false or absent", () => {
    render(
      <VerdictReveal
        language="en"
        state="HUMAN_REVIEW_REQUIRED"
        provenance="ENGINE"
      />,
    );
    expect(
      screen.getByText("This needs a human, not an algorithm"),
    ).toBeInTheDocument();
  });

  it("ignores isSecondHomeStudioOnly on every other state", () => {
    render(
      <VerdictReveal
        language="en"
        state="SUPPORTED_CANDIDATES"
        provenance="ENGINE"
        isSecondHomeStudioOnly
      />,
    );
    expect(screen.getByText("Supported paths found")).toBeInTheDocument();
    expect(
      screen.queryByText("Below the Second Home guarantee threshold"),
    ).toBeNull();
  });
});

describe("VerdictReveal — the Studio description never repeats the reason body", () => {
  // The reason copy for SECOND_HOME_BELOW_THRESHOLD_STUDIO renders right under
  // the verdict and already ends with the Studio sentence; saying it twice in
  // a row reads as a broken page.
  it.each(["en", "id"] as const)("%s", (language) => {
    const description = translate(
      language,
      "verdict.state_description.SECOND_HOME_STUDIO" as I18nKey,
    );
    const reasonBody =
      REVIEW_REASON_COPY[SECOND_HOME_STUDIO_REVIEW_REASON_CODE][language];
    const sentences = description
      .split(/(?<=\.)\s+/)
      .map((sentence) => sentence.trim())
      .filter(Boolean);
    for (const sentence of sentences) {
      expect(reasonBody).not.toContain(sentence);
    }
  });
});
