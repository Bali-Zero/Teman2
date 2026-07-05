import { describe, expect, it } from "vitest";
import crypto from "crypto";
import fs from "fs";
import path from "path";

// Guard for data/kbli-dataset-version.json: the sidecar is the SEO source of
// truth for "when did the KBLI dataset really change" (file mtime is clone
// time on git/Vercel checkouts). If the dataset changes without a sidecar
// bump, sitemap lastmod and JSON-LD dateModified silently go stale — this
// test makes that a red build instead.
describe("kbli-dataset-version sidecar", () => {
  const dataDir = path.join(process.cwd(), "data");

  it("matches the current dataset hash — bump kbli-dataset-version.json when the dataset changes", () => {
    const dataset = fs.readFileSync(
      path.join(dataDir, "KBLI_2025_FINAL_CLEAN.json"),
    );
    const sha = crypto.createHash("sha256").update(dataset).digest("hex");
    const sidecar = JSON.parse(
      fs.readFileSync(path.join(dataDir, "kbli-dataset-version.json"), "utf-8"),
    ) as { datasetSha256: string; lastModified: string };

    // "sha256:" prefix keeps secret scanners from flagging the bare hex.
    expect(sidecar.datasetSha256).toBe(`sha256:${sha}`);
    expect(new Date(sidecar.lastModified).toString()).not.toBe("Invalid Date");
  });
});
