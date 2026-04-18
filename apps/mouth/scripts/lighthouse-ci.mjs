#!/usr/bin/env node
/**
 * Lighthouse CI runner for the mouth app.
 *
 * Usage (local):
 *   npm run build && npm start &   # or any production server on :3000
 *   npm run lighthouse             # runs lhci autorun
 *
 * In CI, use `npm run lighthouse:ci` which spins up the server + runs lhci.
 *
 * We prefer `npx --yes @lhci/cli@0.15.x autorun` so contributors don't need
 * a local install. Config lives in apps/mouth/.lighthouserc.json.
 */

import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appDir = path.resolve(__dirname, "..");

const args = [
  "--yes",
  "@lhci/cli@0.15.x",
  "autorun",
  `--config=${path.join(appDir, ".lighthouserc.json")}`,
];

const child = spawn("npx", args, {
  stdio: "inherit",
  cwd: appDir,
  env: { ...process.env, CI: "1" },
});

child.on("exit", (code) => {
  process.exit(code ?? 0);
});
