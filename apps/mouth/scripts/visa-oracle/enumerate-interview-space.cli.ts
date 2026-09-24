/**
 * CLI entry point for `enumerate-interview-space.ts`, split out in Slice
 * B5-2 — see `generate-walk-corpus.cli.ts` for the shared rationale (the
 * CJS module-only-construct transform failure it fixes). The library
 * imports nothing from this file, only the reverse.
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  buildManifest,
  dryRunSummary,
  renderManifest,
} from "./enumerate-interview-space";

const HERE = dirname(fileURLToPath(import.meta.url));

/** Where the manifest is written by default. */
export const DEFAULT_OUT_PATH = resolve(
  HERE,
  "../../../../research/operations/visa-oracle-interview-space-manifest.json",
);

async function main(argv: string[]): Promise<void> {
  const manifest = buildManifest();
  if (argv.includes("--dry-run")) {
    const { line, ok } = dryRunSummary(manifest);
    console.log(line);
    process.exitCode = ok ? 0 : 1;
    return;
  }
  const outIndex = argv.indexOf("--out");
  const outPath =
    outIndex >= 0 && argv[outIndex + 1]
      ? resolve(argv[outIndex + 1])
      : DEFAULT_OUT_PATH;
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, await renderManifest(manifest), "utf8");
  console.log(
    `wrote ${manifest.coveringSubset.walks.length} covering walks to ${outPath} ` +
      `(walksTotalExact=${manifest.walksTotalExact}, bound=${manifest.bound})`,
  );
  if (!dryRunSummary(manifest).ok) process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv.slice(2)).catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
