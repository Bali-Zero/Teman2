import path from "node:path";
import { defineConfig } from "vitest/config";
export default defineConfig({
  resolve: {
    alias: [
      {
        find: "@/lib/kbli-status-labels",
        replacement: path.resolve(
          import.meta.dirname,
          "../mouth/src/lib/kbli-status-labels.ts",
        ),
      },
      {
        find: "@/lib/kbli-types",
        replacement: path.resolve(
          import.meta.dirname,
          "../mouth/src/lib/kbli-types.ts",
        ),
      },
      {
        find: "@/lib/kbli-provenance",
        replacement: path.resolve(
          import.meta.dirname,
          "../mouth/src/lib/kbli-provenance.ts",
        ),
      },
      {
        find: "@/lib/kbli-bali-block",
        replacement: path.resolve(
          import.meta.dirname,
          "../mouth/src/lib/kbli-bali-block.ts",
        ),
      },
      {
        find: "@/lib/kbli-pma-shape",
        replacement: path.resolve(
          import.meta.dirname,
          "../mouth/src/lib/kbli-pma-shape.ts",
        ),
      },
      {
        find: "@/lib/kbli-pma-disclosure",
        replacement: path.resolve(
          import.meta.dirname,
          "../mouth/src/lib/kbli-pma-disclosure.ts",
        ),
      },
      {
        find: "@/lib/kbli-derive",
        replacement: path.resolve(
          import.meta.dirname,
          "../mouth/src/lib/kbli-derive.ts",
        ),
      },
      {
        find: "@/lib/kbli-pma-source",
        replacement: path.resolve(
          import.meta.dirname,
          "../mouth/src/lib/kbli-pma-source.ts",
        ),
      },
    ],
  },
  test: {
    // Node 26's server localStorage shadows jsdom's real browser Storage.
    execArgv: ["--no-experimental-webstorage"],
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
