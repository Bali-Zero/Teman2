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
    coverage: {
      provider: "v8",
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
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@balizero/core/analytics": path.resolve(
        __dirname,
        "../../packages/core/analytics/index.ts",
      ),
      "@balizero/core/auth": path.resolve(
        __dirname,
        "../../packages/core/auth/index.ts",
      ),
      "@balizero/core/utils": path.resolve(
        __dirname,
        "../../packages/core/utils/index.ts",
      ),
      "@balizero/core": path.resolve(__dirname, "../../packages/core/index.ts"),
    },
  },
});
