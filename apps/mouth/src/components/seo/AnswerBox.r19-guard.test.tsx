// R19 skin guard: fails if AnswerBox/KeyTakeaway (the MDX callout boxes used
// across the tax article corpus, e.g. content/articles/tax/npwp-foreigners-guide.mdx)
// still paint the pre-R19 sand/gold gradient and hardcoded hex instead of the
// R19 wash/surface + copper tokens.
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AnswerBox, KeyTakeaway } from "./AnswerBox";

const FORBIDDEN: RegExp[] = [
  /\btext-white\b/,
  /\bbg-white\//,
  /\bborder-white\//,
  /bg-gradient-to-\w+\s+from-\[#/,
  /bg-\[#[0-9a-fA-F]{3,6}\]/,
  /border-\[#[0-9a-fA-F]{3,6}\]/,
  /\bfont-black\b/,
  /\bfont-extrabold\b/,
];

function assertNoForbiddenClasses(html: string) {
  for (const re of FORBIDDEN) {
    expect(html).not.toMatch(re);
  }
}

describe("AnswerBox / KeyTakeaway R19 skin guard", () => {
  it("AnswerBox has no pre-R19 literal colour classes", () => {
    const html = renderToString(
      <AnswerBox>
        PT PMA is Indonesia&apos;s foreign-owned company structure.
      </AnswerBox>,
    );
    assertNoForbiddenClasses(html);
  });

  it("KeyTakeaway (points) has no pre-R19 literal colour classes", () => {
    const html = renderToString(
      <KeyTakeaway
        points={["KITAS required for work", "PT PMA = 100% foreign ownership"]}
      />,
    );
    assertNoForbiddenClasses(html);
  });

  it("KeyTakeaway (children) has no pre-R19 literal colour classes", () => {
    const html = renderToString(
      <KeyTakeaway>
        <strong>TL;DR:</strong> MDX-authored takeaway text.
      </KeyTakeaway>,
    );
    assertNoForbiddenClasses(html);
  });
});
