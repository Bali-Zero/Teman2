import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";

const discoveryFiles = [
  "llms.txt",
  "llms-full.txt",
  "llms-id.txt",
  "llms-kbli.txt",
  "sitemap-ai.xml",
] as const;

describe("LLM discovery files", () => {
  it("keeps the five public files byte-identical to their Mouth sources", async () => {
    for (const filename of discoveryFiles) {
      const [website, mouth] = await Promise.all([
        readFile(path.join(process.cwd(), "public", filename)),
        readFile(path.join(process.cwd(), "../mouth/public", filename)),
      ]);

      expect(website.byteLength, filename).toBe(mouth.byteLength);
      expect(Buffer.compare(website, mouth), filename).toBe(0);
    }
  });
});
