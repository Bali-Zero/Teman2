import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  // Keep this package isolated even when Vitest is invoked from the monorepo
  // root. Without an explicit root, the broad include below collects tests
  // from sibling applications as well.
  root: __dirname,
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: [path.resolve(__dirname, "test/setup.tsx")],
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**", "coverage/**"],
    pool: "threads",
    minWorkers: 1,
    maxWorkers: 2,
    coverage: {
      // Match the frontend's provider. Vitest 4's v8 path currently has a
      // rolldown TSX parsing regression; Istanbul is stable for this package.
      provider: "istanbul",
      reporter: ["text", "json", "json-summary", "lcov"],
      reportsDirectory: "coverage",
      include: ["**/*.{ts,tsx}"],
      exclude: [
        "**/*.test.{ts,tsx}",
        "test/**",
        "coverage/**",
        "vitest.config.ts",
      ],
      thresholds: {
        statements: 80,
        branches: 70,
        functions: 80,
        lines: 80,
      },
    },
  },
});
