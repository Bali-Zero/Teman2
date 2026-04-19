import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    // Reuse apps/mouth's setup (localStorage mock, next/image mock, etc.)
    setupFiles: [
      path.resolve(__dirname, "../../apps/mouth/src/test/setup.tsx"),
    ],
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**"],
    deps: {
      inline: ["@testing-library/react"],
    },
  },
});
