import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

export default defineConfig({
  resolve: {
    alias: {
      "next/cache": fileURLToPath(new URL("./proofs/architecture/cache-shim.ts", import.meta.url)),
      "gray-matter": require.resolve("gray-matter"),
      // Architecture proofs execute server modules in Node, never a client bundle.
      "server-only": require.resolve("next/dist/compiled/server-only/empty.js"),
    },
    dedupe: ["react", "react-dom"],
  },
  test: {
    environment: "node", include: ["proofs/architecture/*.test.tsx"],
    maxWorkers: 1, fileParallelism: false,
  },
});
