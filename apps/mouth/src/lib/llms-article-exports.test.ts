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

// The freshness block slices the first five canonical articles off an array built by
// walking readdirSync. The case that exposes the tie is SIX canonical articles sharing
// one publishedAt: without a second sort key the excluded one is whatever the filesystem
// enumerated last, and on this repo's own volume readdirSync returns names in lexical
// order — so a test that only shuffles CREATION order proves nothing, and a mutant that
// deletes the sort outright can still look green. These fixtures put each article in a
// different content folder, because the URL's category comes from the FOLDER while
// enumeration follows the folder NAME: `business_regulations` enumerates first and
// serves `/business/`, `tax-legal` enumerates last and serves `/taxes/`, so the
// enumeration order and the URL order genuinely disagree.
const SAME_DATE = "2026-09-06";
// [folder, slug, servedCategory]
const TIED: Array<[string, string, string]> = [
  ["business_regulations", "zeta", "business"],
  ["digital-nomad", "yankee", "living"],
  ["emerging_trends", "xray", "trends"],
  ["immigration", "whisky", "visas"],
  ["property", "victor", "property"],
  ["tax-legal", "uniform", "taxes"],
];
// Date must outrank URL: this one is newer and its URL sorts LAST of all seven.
const NEWEST: [string, string, string] = ["immigration", "zulu", "visas"];

it.each([
  [TIED],
  [[...TIED].reverse()],
  [[TIED[3], TIED[0], TIED[5], TIED[1], TIED[4], TIED[2]]],
])(
  "freshness breaks a same-date tie by URL, not by filesystem order (creation order %#)",
  (creationOrder) => {
    const cwd = mkdtempSync(join(tmpdir(), "llms-freshness-"));
    try {
      const output = join(cwd, "public");
      mkdirSync(output, { recursive: true });
      mkdirSync(join(cwd, "data"));
      writeFileSync(
        join(output, "llms.txt"),
        "# Directory\n## Services\nKeep this section\n",
      );
      const write = (
        [folder, slug]: [string, string, string],
        date: string,
      ) => {
        const dir = join(cwd, "src/content/articles", folder);
        mkdirSync(dir, { recursive: true });
        writeFileSync(
          join(dir, `${slug}.mdx`),
          `---\ntitle: ${slug}\npublishedAt: '${date}'\n---\nBody for ${slug}\n`,
        );
      };
      for (const article of creationOrder) write(article, SAME_DATE);
      write(NEWEST, "2026-09-07");
      execFileSync(
        require.resolve("tsx/cli"),
        [join(app, "scripts/generate-llms-full.ts")],
        {
          cwd,
          env: { ...process.env, LLMS_GENERATE_ARTICLES_ONLY: "1" },
          stdio: "pipe",
        },
      );
      const directory = readFileSync(join(output, "llms.txt"), "utf8");
      // Newest first, then the four tied articles whose URLs sort first:
      // business < living < property < taxes < trends < visas. `xray` (/trends/) and
      // `whisky` (/visas/) are the two the slice drops. Under bare filesystem order the
      // survivors would be the first five FOLDERS instead — business_regulations,
      // digital-nomad, emerging_trends, immigration, property — which keeps `xray` and
      // `whisky` and drops `uniform`, so this assertion separates the two behaviours.
      expect(directory).toContain(
        [
          "## Recently Published & Updated (Freshness Signal)",
          "",
          "- [zulu](https://balizero.com/visas/zulu) (2026-09-07)",
          "- [zeta](https://balizero.com/business/zeta) (2026-09-06)",
          "- [yankee](https://balizero.com/living/yankee) (2026-09-06)",
          "- [victor](https://balizero.com/property/victor) (2026-09-06)",
          "- [uniform](https://balizero.com/taxes/uniform) (2026-09-06)",
          "",
        ].join("\n"),
      );
      expect(directory).not.toContain("xray");
      expect(directory).not.toContain("whisky");
    } finally {
      rmSync(cwd, { recursive: true, force: true });
    }
  },
);
