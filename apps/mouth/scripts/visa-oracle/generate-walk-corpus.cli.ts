/**
 * CLI entry point for `generate-walk-corpus.ts`, split out in Slice B5-2.
 *
 * `apps/mouth/package.json` has no `"type": "module"` (only the monorepo
 * root does), so Playwright's CJS transform throws a SyntaxError about a
 * module-only construct the moment a spec imports a module that contains
 * one — a top-level import killed `--list` for the WHOLE e2e suite. The
 * four sites across the two enumerator scripts are all CLI-only (`HERE`,
 * `DEFAULT_OUT_PATH`/`DEFAULT_OUT_DIR`, `main()`, the module-URL guard), so
 * they live here and in `enumerate-interview-space.cli.ts`; the library
 * (`generate-walk-corpus.ts`) imports nothing from this file, only the
 * reverse.
 */

import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { writeWalkCorpus } from "./generate-walk-corpus";

const HERE = dirname(fileURLToPath(import.meta.url));

/** Where the census test reads the corpus from. */
export const DEFAULT_OUT_DIR = resolve(
  HERE,
  "../../../backend-rag/backend/tests/services/visa_engine/gold_coverage/fixtures/walks",
);

async function main(argv: string[]): Promise<void> {
  const outIndex = argv.indexOf("--out");
  const outDir =
    outIndex >= 0 && argv[outIndex + 1]
      ? resolve(argv[outIndex + 1])
      : DEFAULT_OUT_DIR;
  const { written, orphans } = await writeWalkCorpus(outDir);
  console.log(`wrote ${written.length} walks to ${outDir}`);
  if (orphans.length > 0) {
    // Not deleted on purpose: a stale fixture is a review signal, and the
    // determinism test already fails on it (it compares the file SET too).
    console.error(
      `WARNING: ${orphans.length} stale fixture(s) no longer generated — delete them by hand:\n  ${orphans.join("\n  ")}`,
    );
    process.exitCode = 1;
  }
}

if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv.slice(2)).catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
