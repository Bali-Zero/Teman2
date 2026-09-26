import { describe, expect, it } from "vitest";
import { metadata } from "./layout";

// Config-level guard: it goes red if the prime subtree loses its noindex.
// It does not prove the rendered <meta> tag; that was measured from a local
// `next start` against /prime/proposal/<token> when this was added.
describe("prime layout metadata", () => {
  it("keeps every /prime route, including /prime/proposal/[token], out of the index", () => {
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });
});
