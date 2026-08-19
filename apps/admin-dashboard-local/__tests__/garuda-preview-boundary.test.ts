import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { cockpitLoginFailureMessage } from "@/components/cockpit/PinGate";

function source(relativePath: string): string {
  return readFileSync(path.join(process.cwd(), relativePath), "utf8");
}

describe("GARUDA internal preview boundaries", () => {
  it("labels the surface synthetic-only and omits client identity fields", () => {
    const ui = source("app/garuda-voa/GarudaPreviewClient.tsx");
    expect(ui).toContain("INTERNAL / SYNTHETIC DATA ONLY");
    expect(ui).toContain("Use fabricated dates only");
    expect(ui).not.toMatch(
      /passport_number|client_name|phone_number|email_address/,
    );
    expect(ui).not.toContain("localStorage");
    expect(ui).not.toContain("sessionStorage");
    expect(source("components/cockpit/PinGate.tsx")).not.toContain(
      "document.cookie",
    );
    expect(source("lib/cockpit-session.ts")).not.toContain("request.cookies");
  });

  it("never renders the disputed earliest-filing marker", () => {
    const ui = source("app/garuda-voa/GarudaPreviewClient.tsx");
    expect(ui).not.toContain("D-14");
    expect(ui).toContain('new Set(["D-10", "D-3", "D-1"])');
  });

  it("pins every runtime command to loopback", () => {
    const packageJson = JSON.parse(source("package.json")) as {
      scripts: Record<string, string>;
    };
    expect(packageJson.scripts.dev).toBe(
      "next dev --webpack -H 127.0.0.1 -p 3100",
    );
    expect(packageJson.scripts.start).toBe("next start -H 127.0.0.1 -p 3100");
    expect(source("scripts/start-cockpit.sh")).toContain(
      "next dev --webpack -H 127.0.0.1 -p 3100",
    );
    expect(source("scripts/start-cockpit.sh")).toContain(
      "http://localhost:3100/cockpit",
    );
  });

  it("documents the exact browser origin and production-mode commands", () => {
    const readme = source("README.md");
    expect(readme).toContain("http://localhost:3100/garuda-voa");
    expect(readme).toContain("-L 127.0.0.1:3100:127.0.0.1:3100");
    expect(readme).toContain("http://127.0.0.1:3100/garuda-voa");
    expect(readme).toContain("LOCAL_ONLY=1 npm run build");
    expect(readme).toContain("npm run start");
  });

  it("derives the preview checkout from its own Git worktree", () => {
    const launcher = source("scripts/start-cockpit.sh");
    expect(launcher).toContain(
      'git -C "$SCRIPT_DIR" rev-parse --show-toplevel',
    );
    expect(launcher).toContain(
      'export COCKPIT_REPO_ROOT="$LAUNCHER_REPO_ROOT"',
    );
    expect(launcher).toContain(
      'PREVIEW_PYTHON="$BACKEND_ROOT/.venv/bin/python"',
    );
    expect(launcher).toContain(
      '"$BACKEND_ROOT/backend/services/garuda_flow/internal_preview_cli.py"',
    );
    expect(launcher).toContain(
      'PREVIEW_CWD="$BACKEND_ROOT/backend/services/garuda_flow"',
    );
    expect(launcher).toContain('"$PREVIEW_CWD/.env"');
    expect(launcher).toContain("GARUDA preview/login remain available");
    expect(launcher).toContain("DB-backed widgets will be unavailable");
    expect(launcher).not.toContain('COCKPIT_REPO_ROOT="${COCKPIT_REPO_ROOT:-');
  });

  it("loads optional env before exporting both protected file keys", () => {
    const launcher = source("scripts/start-cockpit.sh");
    const envOffset = launcher.indexOf("source .env");
    const hmacOffset = launcher.indexOf(
      'export COCKPIT_HMAC_KEY="$(<"$HMAC_KEY_FILE")"',
    );
    const sessionOffset = launcher.indexOf(
      'export COCKPIT_SESSION_KEY="$(<"$SESSION_KEY_FILE")"',
    );
    const protectedRootOffset = launcher.indexOf(
      'export COCKPIT_REPO_ROOT="$LAUNCHER_REPO_ROOT"',
    );
    const protectedKeyPathOffset = launcher.indexOf(
      'HMAC_KEY_FILE="$CONFIG_DIR/hmac.key"',
    );
    const sessionKeyPathOffset = launcher.indexOf(
      'SESSION_KEY_FILE="$CONFIG_DIR/session.key"',
    );
    expect(envOffset).toBeGreaterThan(-1);
    expect(protectedRootOffset).toBeGreaterThan(envOffset);
    expect(protectedKeyPathOffset).toBeGreaterThan(envOffset);
    expect(sessionKeyPathOffset).toBeGreaterThan(envOffset);
    expect(hmacOffset).toBeGreaterThan(envOffset);
    expect(sessionOffset).toBeGreaterThan(envOffset);
    expect(source("scripts/setup-cockpit-pin.sh")).toContain(
      'chmod 0600 "$SESSION_KEY_FILE"',
    );
  });

  it("keeps passphrase authentication independent of database audit", () => {
    const authRoute = source("app/api/cockpit/auth/route.ts");
    expect(authRoute).not.toContain("cockpit-pg");
    expect(authRoute).not.toContain("insertAuditRow");
    expect(authRoute).toContain("readCockpitSessionKey");
    expect(authRoute).toContain("req.nextUrl.origin");
  });

  it("sets no-store and noindex headers on page and API", () => {
    const config = source("next.config.mjs");
    expect(config).toContain('source: "/garuda-voa"');
    expect(config).toContain('source: "/api/garuda-voa/:path*"');
    expect(config).toContain("no-store, max-age=0");
    expect(config).toContain("noindex, nofollow, noarchive");
  });

  it("never labels an estimated issuance date as the last legal day", () => {
    const ui = source("app/garuda-voa/GarudaPreviewClient.tsx");
    expect(ui).not.toContain("Last legal day");
    expect(ui).toContain("Computed stay end (estimate)");
    expect(ui).toContain("No GARUDA case payload is persisted");
    expect(ui).not.toContain("database write occurs");
  });

  it("shows both materialized operating-calendar coverage boundaries", () => {
    const ui = source("app/garuda-voa/GarudaPreviewClient.tsx");
    expect(ui).toContain("formatDate(result.calendar_coverage_start)");
    expect(ui).toContain("formatDate(result.calendar_coverage_end)");
    expect(ui).toContain("Verified coverage:");
    expect(ui).not.toContain("Verified coverage ends");
  });

  it("requires Bearer validation in every cockpit and GARUDA protected API", () => {
    for (const route of [
      "app/api/cockpit/session/route.ts",
      "app/api/cockpit/cron/list/route.ts",
      "app/api/cockpit/cron/run/route.ts",
      "app/api/cockpit/decisions/route.ts",
      "app/api/cockpit/intent/create/route.ts",
      "app/api/garuda-voa/evaluate/route.ts",
    ]) {
      expect(source(route)).toContain("hasValidCockpitSession");
    }
  });

  it("uses the shared same-origin JSON guard on every local mutation", () => {
    for (const route of [
      "app/api/cockpit/auth/route.ts",
      "app/api/cockpit/cron/run/route.ts",
      "app/api/cockpit/intent/create/route.ts",
      "app/api/garuda-voa/evaluate/route.ts",
      "app/api/llm-costs/recommendations/route.ts",
    ]) {
      expect(source(route)).toContain("sameOriginJsonFailure");
    }
  });
});

describe("PinGate login feedback", () => {
  it("identifies an origin or host rejection with the canonical URL", () => {
    expect(cockpitLoginFailureMessage(403)).toBe(
      "origin/host blocked: use http://localhost:3100",
    );
  });

  it("keeps an invalid passphrase distinct without echoing input", () => {
    const syntheticPassphrase = "not-a-real-passphrase";
    const message = cockpitLoginFailureMessage(401);

    expect(message).toBe("invalid passphrase");
    expect(message).not.toContain(syntheticPassphrase);
    expect(message).not.toContain("origin/host");
  });
});
