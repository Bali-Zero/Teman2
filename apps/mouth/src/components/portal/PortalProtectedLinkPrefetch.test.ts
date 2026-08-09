import { existsSync, readdirSync, readFileSync } from "node:fs";
import { extname, join, relative, resolve } from "node:path";

import { describe, expect, it } from "vitest";

const mouthRoot = existsSync(resolve(process.cwd(), "src/app/portal"))
  ? process.cwd()
  : resolve(process.cwd(), "apps/mouth");

const authenticatedRoot = resolve(mouthRoot, "src/app/portal/(authenticated)");

const sharedProtectedComponents = [
  resolve(mouthRoot, "src/components/portal/PortalBackButton.tsx"),
  resolve(mouthRoot, "src/components/portal/PortalBottomNav.tsx"),
  resolve(mouthRoot, "src/components/portal/PortalEmptyState.tsx"),
  resolve(mouthRoot, "src/components/portal/process/BlockedStateCTA.tsx"),
];

function collectTsxFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return collectTsxFiles(path);
    if (extname(entry.name) !== ".tsx" || entry.name.includes(".test.")) {
      return [];
    }
    return [path];
  });
}

function executableLinkTags(source: string): string[] {
  const withoutComments = source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
  return [...withoutComments.matchAll(/<Link\b[\s\S]*?>/g)]
    .map(([tag]) => tag)
    .filter((tag) => /\bhref\s*=/.test(tag));
}

describe("protected portal Link prefetch policy", () => {
  it("disables speculative requests for every protected Link", () => {
    const violations = [
      ...collectTsxFiles(authenticatedRoot),
      ...sharedProtectedComponents,
    ].flatMap((path) =>
      executableLinkTags(readFileSync(path, "utf8"))
        .filter((tag) => !/\bprefetch=\{false\}/.test(tag))
        .map(() => relative(authenticatedRoot, path)),
    );

    expect(violations).toEqual([]);
  });
});
