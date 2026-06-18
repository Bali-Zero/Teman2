import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.tsx"],
    include: ["src/**/*.test.{ts,tsx}"],
    testTimeout: 20000,
    hookTimeout: 20000,
    // Coverage runs under istanbul (see coverage.provider note below): babel
    // instrumentation roughly doubles per-worker memory + time vs v8. vitest's
    // default `forks` pool spawns one full child *process* per worker sized to
    // the host CPU count, so on a 2-4 vCPU / ~7GB GitHub linux runner the forks
    // pool exhausts memory and fails to spawn workers ("[vitest-pool]: Failed to
    // start forks worker ..." for every test file). Switch to the `threads` pool
    // — worker_threads share the host process's memory arena and carry a far
    // lower per-worker baseline than forked processes — AND cap concurrency so
    // total instrumented heap stays bounded regardless of the runner's reported
    // core count. jsdom + the vi.mock setup are thread-safe here (no native
    // addon / no process-global mutation; vitest still isolates each test file's
    // module registry per worker). Verified locally: 197 files / 1707 tests green.
    pool: "threads",
    poolOptions: {
      threads: {
        maxThreads: 2,
        minThreads: 1,
      },
    },
    coverage: {
      // istanbul (babel-based instrumentation), NOT v8: the v8 provider on
      // vitest 4 routes source parsing through rolldown (pulled by vite 8),
      // and rolldown 1.0.3 has a JSX/`import type` parse regression that
      // throws RolldownError on valid .tsx (e.g. src/app/layout.tsx). On CI
      // (linux) that crashes `vitest --run --coverage`; istanbul's babel
      // parser handles JSX + `import type` cleanly and is platform-agnostic.
      provider: "istanbul",
      reporter: ["text", "json", "json-summary", "html", "lcov"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/test/**",
        "src/**/*.test.{ts,tsx}",
        "src/**/*.d.ts",
        "src/**/*.backup.{ts,tsx}",
      ],
    },
  },
  resolve: {
    // Array form (ordered) so the wildcard subpath rule mirrors tsconfig's
    // "@balizero/core/*": ["../../packages/core/*"]. The istanbul coverage
    // provider eagerly imports *uncovered* source files (e.g. src/app/layout.tsx)
    // to count them in the denominator; those RSC files import deep subpaths
    // like @balizero/core/components/ThemeProvider and @balizero/core/fonts/inter
    // that the old object-form alias map didn't cover, so the uncovered-include
    // pass failed to resolve them. Order matters: exact "@balizero/core" before
    // the subpath regex, and "@" last so it never shadows "@balizero/...".
    alias: [
      {
        find: "@balizero/core/analytics",
        replacement: path.resolve(
          __dirname,
          "../../packages/core/analytics/index.ts",
        ),
      },
      {
        find: "@balizero/core/auth",
        replacement: path.resolve(
          __dirname,
          "../../packages/core/auth/index.ts",
        ),
      },
      {
        find: "@balizero/core/utils",
        replacement: path.resolve(
          __dirname,
          "../../packages/core/utils/index.ts",
        ),
      },
      {
        find: /^@balizero\/core\/(.*)$/,
        replacement: path.resolve(__dirname, "../../packages/core/$1"),
      },
      {
        find: "@balizero/core",
        replacement: path.resolve(__dirname, "../../packages/core/index.ts"),
      },
      { find: "@", replacement: path.resolve(__dirname, "./src") },
    ],
  },
});
