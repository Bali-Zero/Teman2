import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

const REPO_ROOT = path.resolve(process.cwd(), "../..");

function sourceFiles(root: string): string[] {
  const files: string[] = [];
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    if (
      entry.name === "node_modules" ||
      entry.name === ".next" ||
      entry.name === "dist" ||
      entry.name === "build"
    ) {
      continue;
    }
    const absolute = path.join(root, entry.name);
    if (entry.isDirectory()) files.push(...sourceFiles(absolute));
    else if (/\.(?:ts|tsx|js|jsx|py)$/.test(entry.name)) files.push(absolute);
  }
  return files;
}

describe("KBLI transition semantic-leak gate", () => {
  it("finds no production previousCodes ancestry claim outside the explicitly dormant twin", () => {
    const appsRoot = path.join(REPO_ROOT, "apps");
    const dormantRoot = path.join(appsRoot, "kbli-navigator");
    const mouthRoot = path.join(appsRoot, "mouth", "src");
    const kbliSurfaceRoots = [
      path.join(mouthRoot, "app", "kbli"),
      path.join(mouthRoot, "app", "kbli-explorer"),
      path.join(mouthRoot, "components", "kbli"),
    ];
    const kbliLibRoot = path.join(mouthRoot, "lib");

    // EXPLICIT EXEMPTION — corner ruling "SEVENTH copy DORMANT":
    // apps/kbli-navigator is not cured in this diff because /kbli-navigator and
    // all descendants permanently 308 to /kbli. The repository can prove only
    // that no .github/workflows file deploys the twin; a Vercel project wired
    // directly to apps/kbli-navigator is outside this check and is ledgered as
    // an explicit limit. Removing either redirect or adding a workflow deploy
    // signature makes this gate red before revival.
    //
    // Scope the identifier scan to the KBLI product surfaces it protects. An
    // unrelated `previousCodes` variable elsewhere in the monorepo must not
    // make this mandatory gate cry wolf.
    const productionFiles = [
      ...kbliSurfaceRoots.flatMap((root) => sourceFiles(root)),
      ...sourceFiles(kbliLibRoot).filter((file) =>
        path.basename(file).startsWith("kbli-"),
      ),
    ].filter((file) => !/\.(?:test|spec)\.[^.]+$/.test(file));
    const leaks = productionFiles.filter((file) => {
      const text = fs.readFileSync(file, "utf8");
      return (
        /\bpreviousCodes\b/.test(text) ||
        text.includes("Previous codes (KBLI 2020)")
      );
    });
    expect(leaks.map((file) => path.relative(REPO_ROOT, file))).toEqual([]);

    const nextConfig = fs.readFileSync(
      path.join(REPO_ROOT, "apps/mouth/next.config.ts"),
      "utf8",
    );
    expect(nextConfig).toMatch(
      /source:\s*"\/kbli-navigator"[\s\S]*?destination:\s*"\/kbli"[\s\S]*?permanent:\s*true/,
    );
    expect(nextConfig).toMatch(
      /source:\s*"\/kbli-navigator\/:path\*"[\s\S]*?destination:\s*"\/kbli\/:path\*"[\s\S]*?permanent:\s*true/,
    );

    expect(fs.existsSync(dormantRoot)).toBe(true);

    const workflowRoot = path.join(REPO_ROOT, ".github/workflows");
    const deployers = fs
      .readdirSync(workflowRoot)
      .filter((name) => /\.ya?ml$/.test(name))
      .filter((name) => {
        const text = fs.readFileSync(path.join(workflowRoot, name), "utf8");
        return [
          /working-directory:\s*apps\/kbli-navigator/,
          /cd\s+apps\/kbli-navigator/,
          /kbli-navigator-rebuild\.vercel\.app/,
          /vercel[^\n]*kbli-navigator/i,
          /netlify[^\n]*kbli-navigator/i,
        ].some((pattern) => pattern.test(text));
      });
    expect(deployers).toEqual([]);
  });

  it("keeps raw PP28 licensing provenance and its inheritance helper without using it as FAQ ancestry", () => {
    const dataServer = fs.readFileSync(
      path.join(REPO_ROOT, "apps/mouth/src/lib/kbli-data.server.ts"),
      "utf8",
    );
    const provenance = fs.readFileSync(
      path.join(REPO_ROOT, "apps/mouth/src/lib/kbli-provenance.ts"),
      "utf8",
    );
    const faq = fs.readFileSync(
      path.join(REPO_ROOT, "apps/mouth/src/lib/kbli-faq.ts"),
      "utf8",
    );

    expect(dataServer).toContain("raw.pp28_sources");
    expect(provenance).toContain("pp28ContentInheritedFrom");
    expect(faq).toContain(
      "const bpsCodes = code.transition.bpsCrosswalk?.codes ?? []",
    );
    expect(faq).not.toContain("was mapped from previous code");
  });

  it("binds both mappingStatus consumers to the BPS-aware TransitionBadge contract", () => {
    const page = fs.readFileSync(
      path.join(REPO_ROOT, "apps/mouth/src/app/kbli/[code]/page.tsx"),
      "utf8",
    );
    const card = fs.readFileSync(
      path.join(REPO_ROOT, "apps/mouth/src/components/kbli/KBLICard.tsx"),
      "utf8",
    );
    expect(page).toContain("<TransitionBadge transition={kbli.transition} />");
    expect(card).toContain("<TransitionBadge transition={code.transition} />");
    expect(page).not.toContain(
      "<TransitionBadge status={kbli.transition.mappingStatus}",
    );
    expect(card).not.toContain(
      "<TransitionBadge status={code.transition.mappingStatus}",
    );
  });
});
