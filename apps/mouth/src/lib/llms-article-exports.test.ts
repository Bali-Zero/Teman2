import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

const app = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const require = createRequire(import.meta.url);

it("the build refreshes both article exports and freshness, excluding drafts and noIndex", () => {
  const cwd = mkdtempSync(join(tmpdir(), "llms-articles-"));
  try {
    const articles = join(cwd, "src/content/articles/immigration");
    const output = join(cwd, "public");
    mkdirSync(articles, { recursive: true });
    mkdirSync(output);
    mkdirSync(join(cwd, "data"));
    // An invalid KBLI input would throw if the article-only build touched it.
    writeFileSync(join(cwd, "data/KBLI_2025_FINAL_CLEAN.json"), "invalid JSON");
    writeFileSync(join(output, "llms-kbli.txt"), "curated KBLI sentinel");
    writeFileSync(join(output, "llms-full.txt"), "stale EN export");
    writeFileSync(join(output, "llms-id.txt"), "stale ID export");
    writeFileSync(
      join(output, "llms.txt"),
      "# Directory\n## Recently Published & Updated (Freshness Signal)\n\nold freshness\n\n## Services\nKeep this section\n",
    );
    for (const [file, title, extra] of [
      ["current.mdx", "Current EN", ""],
      ["current.id.mdx", "Current ID", ""],
      ["current.fr.mdx", "Current FR", ""],
      ["archived.mdx", "Archived EN", "noIndex: true\n"],
      ["archived.id.mdx", "Archived ID", "noIndex: true\n"],
      ["draft.mdx", "Draft EN", "status: draft\n"],
      ["draft.id.mdx", "Draft ID", "status: draft\n"],
    ]) {
      writeFileSync(
        join(articles, file),
        `---\ntitle: ${title}\npublishedAt: '2026-09-01'\n${extra}---\nBody for ${title}\n`,
      );
    }
    const { scripts } = JSON.parse(
      readFileSync(join(app, "package.json"), "utf8"),
    );
    // Read the real build's environment, so reverting its flag breaks this test.
    const flag = scripts.build.match(
      /^(LLMS_GENERATE_\w+)=1 tsx scripts\/generate-llms-full\.ts &&/,
    );
    expect(flag).not.toBeNull();
    execFileSync(
      process.execPath,
      [require.resolve("tsx/cli"), join(app, "scripts/generate-llms-full.ts")],
      {
        cwd,
        env: {
          ...process.env,
          LLMS_GENERATE_FULL_ONLY: "0",
          LLMS_GENERATE_ARTICLES_ONLY: "0",
          [flag[1]]: "1",
        },
        timeout: 15000,
      },
    );
    const en = readFileSync(join(output, "llms-full.txt"), "utf8");
    const id = readFileSync(join(output, "llms-id.txt"), "utf8");
    expect(en).toContain("TITLE: Current EN");
    expect(en).toContain("TITLE: Current FR");
    expect(id).toContain("TITLE: Current ID");
    expect(en + id).not.toMatch(/Archived|Draft|stale/);
    expect(en + id).toContain("URL: https://balizero.com/visas/current");
    const directory = readFileSync(join(output, "llms.txt"), "utf8");
    expect(directory).toContain(
      "[Current EN](https://balizero.com/visas/current)",
    );
    expect(directory).toContain("Keep this section");
    expect(directory).not.toContain("old freshness");
    expect(directory).not.toContain("Current FR");
    expect(
      directory.match(/https:\/\/balizero.com\/visas\/current/g),
    ).toHaveLength(1);
    expect(readFileSync(join(output, "llms-kbli.txt"), "utf8")).toBe(
      "curated KBLI sentinel",
    );
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
});
