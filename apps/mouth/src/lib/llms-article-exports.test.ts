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

// "1": a legacy LLMS_GENERATE_FULL_ONLY=1 inherited from the environment must not
// stop the build flag before the ID export and the freshness block.
it.each([["0"], ["1"]])(
  "the build refreshes both article exports and freshness, excluding drafts and noIndex (inherited FULL_ONLY=%s)",
  (inheritedFullOnly) => {
    const cwd = mkdtempSync(join(tmpdir(), "llms-articles-"));
    try {
      const articles = join(cwd, "src/content/articles/immigration");
      const output = join(cwd, "public");
      mkdirSync(articles, { recursive: true });
      mkdirSync(output);
      mkdirSync(join(cwd, "data"));
      // An invalid KBLI input would throw if the article-only build touched it.
      writeFileSync(
        join(cwd, "data/KBLI_2025_FINAL_CLEAN.json"),
        "invalid JSON",
      );
      writeFileSync(join(output, "llms-kbli.txt"), "curated KBLI sentinel");
      writeFileSync(join(output, "llms-full.txt"), "stale EN export");
      writeFileSync(join(output, "llms-id.txt"), "stale ID export");
      writeFileSync(
        join(output, "llms.txt"),
        "# Directory\n## Recently Published & Updated (Freshness Signal)\n\nold freshness\n\n## Services\nKeep this section\n",
      );
      for (const [file, title, date, extra] of [
        ["current.mdx", "Current EN", "2026-09-06", ""],
        ["current.id.mdx", "Current ID", "2026-09-06", ""],
        // The newest EN-side file is a translation: freshness must skip it.
        ["current.fr.mdx", "Current FR", "2026-09-07", ""],
        ["older-5.mdx", "Older 5", "2026-09-05", ""],
        ["older-4.mdx", "Older 4", "2026-09-04", ""],
        ["older-3.mdx", "Older 3", "2026-09-03", ""],
        ["older-2.mdx", "Older 2", "2026-09-02", ""],
        ["older-1.mdx", "Older 1", "2026-09-01", ""],
        ["archived.mdx", "Archived EN", "2026-09-08", "noIndex: true\n"],
        ["archived.id.mdx", "Archived ID", "2026-09-08", "noIndex: true\n"],
        ["draft.mdx", "Draft EN", "2026-09-08", "status: draft\n"],
        ["draft.id.mdx", "Draft ID", "2026-09-08", "status: draft\n"],
      ]) {
        writeFileSync(
          join(articles, file),
          `---\ntitle: ${title}\npublishedAt: '${date}'\n${extra}---\nBody for ${title}\n`,
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
        [
          require.resolve("tsx/cli"),
          join(app, "scripts/generate-llms-full.ts"),
        ],
        {
          cwd,
          env: {
            ...process.env,
            LLMS_GENERATE_FULL_ONLY: inheritedFullOnly,
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
      expect(en).not.toContain("TITLE: Current ID");
      expect(en).toContain("CONTENT:\nBody for Current EN");
      expect(id).toMatch(
        /TITLE: Current ID\nCATEGORY: .*\nURL: https:\/\/balizero\.com\/visas\/current\n/,
      );
      expect(id).toContain("KONTEN:\nBody for Current ID");
      expect(id).not.toMatch(/Current EN|Current FR|Older/);
      expect(en + id).not.toMatch(/Archived|Draft|stale/);
      const directory = readFileSync(join(output, "llms.txt"), "utf8");
      expect(directory).toContain(
        [
          "## Recently Published & Updated (Freshness Signal)",
          "",
          "- [Current EN](https://balizero.com/visas/current) (2026-09-06)",
          "- [Older 5](https://balizero.com/visas/older-5) (2026-09-05)",
          "- [Older 4](https://balizero.com/visas/older-4) (2026-09-04)",
          "- [Older 3](https://balizero.com/visas/older-3) (2026-09-03)",
          "- [Older 2](https://balizero.com/visas/older-2) (2026-09-02)",
          "",
        ].join("\n"),
      );
      expect(directory).toContain("Keep this section");
      expect(directory).not.toContain("old freshness");
      expect(directory).not.toMatch(/Current FR|Older 1/);
      expect(
        directory.match(/https:\/\/balizero.com\/visas\/current/g),
      ).toHaveLength(1);
      expect(readFileSync(join(output, "llms-kbli.txt"), "utf8")).toBe(
        "curated KBLI sentinel",
      );
    } finally {
      rmSync(cwd, { recursive: true, force: true });
    }
  },
);
