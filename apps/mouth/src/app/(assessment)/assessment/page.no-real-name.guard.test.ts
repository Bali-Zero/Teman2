import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect } from "vitest";

/**
 * /assessment is public and unauthenticated. It used to hardcode a real
 * employee's full name in CANDIDATE_NAME, which the page rendered and put in
 * the subject and body of the emails it sends (PENDING-ARMS L1737). The
 * constant must hold a generic label, never a person's name.
 */
const GENERIC_LABEL = "Kandidat";

function candidateNameDeclarations(source: string): string[] {
  const found: string[] = [];
  const re = /const\s+CANDIDATE_NAME\s*=\s*(["'`])([^"'`]*)\1/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(source)) !== null) found.push(m[2]);
  return found;
}

describe("assessment page carries no real candidate name", () => {
  it("the extractor reads a declared name (guilt fixture)", () => {
    expect(
      candidateNameDeclarations('const CANDIDATE_NAME = "Jane Doe";'),
    ).toEqual(["Jane Doe"]);
  });

  it("declares CANDIDATE_NAME exactly once, as the generic label", () => {
    const source = readFileSync(
      join(process.cwd(), "src/app/(assessment)/assessment/page.tsx"),
      "utf8",
    );
    expect(candidateNameDeclarations(source)).toEqual([GENERIC_LABEL]);
  });
});
