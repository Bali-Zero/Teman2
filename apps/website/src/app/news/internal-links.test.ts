import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";

async function sourceFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const candidate = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...(await sourceFiles(candidate)));
    if (
      entry.isFile() &&
      /\.tsx?$/.test(entry.name) &&
      !entry.name.includes(".test.")
    ) {
      files.push(candidate);
    }
  }
  return files;
}

describe("canonical News links", () => {
  it("leaves no internal Journal href in production source", async () => {
    const files = await sourceFiles(path.join(process.cwd(), "src"));
    const forbidden = `"/${"jour"}nal`;
    const offenders: string[] = [];
    for (const file of files) {
      if ((await readFile(file, "utf8")).includes(forbidden)) {
        offenders.push(path.relative(process.cwd(), file));
      }
    }
    expect(offenders).toEqual([]);
  });
});
