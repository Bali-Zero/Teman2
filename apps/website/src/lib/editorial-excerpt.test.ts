import { describe, expect, it } from "vitest";
import { editorialExcerpt } from "./editorial-excerpt";

describe("editorial excerpt presentation", () => {
  it("retains complete short publisher prose", () => {
    expect(editorialExcerpt("A short published introduction.")).toBe("A short published introduction.");
  });
  it("uses a complete sentence instead of a later clipped source fragment", () => {
    const first = "Indonesia has announced changes to the registration process for existing businesses.";
    expect(editorialExcerpt(`${first} ${"Further information is available. ".repeat(8)} Asset Recovery Manageme`, 110)).toBe(first);
  });
  it("marks an extract without cutting a word or inventing a conclusion", () => {
    const source = "This very long sentence contains many descriptive words about the existing application process without a final sentence break";
    const result = editorialExcerpt(source, 65);
    expect(result.endsWith("…")).toBe(true);
    expect(source.startsWith(result.slice(0, -1))).toBe(true);
    expect(source[result.length - 1]).toBe(" ");
    expect(result.length).toBeLessThanOrEqual(65);
  });
});
