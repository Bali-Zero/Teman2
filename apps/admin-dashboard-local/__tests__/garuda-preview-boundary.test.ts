import { readFileSync } from "node:fs";
import path from "node:path";
import type { FormEvent, ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const reactHarness = vi.hoisted(() => ({
  cursor: 0,
  setters: [] as Array<ReturnType<typeof vi.fn>>,
  stateValues: [] as unknown[],
}));

vi.mock("react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react")>();
  return {
    ...actual,
    useCallback: <T>(callback: T) => callback,
    useState: <T>(initial: T) => {
      const index = reactHarness.cursor++;
      const value =
        index < reactHarness.stateValues.length
          ? (reactHarness.stateValues[index] as T)
          : initial;
      return [value, reactHarness.setters[index] ?? vi.fn()] as const;
    },
  };
});

import {
  AUTHENTICATION_UNAVAILABLE_MESSAGE,
  cockpitLoginFailureMessage,
  PinGate,
} from "@/components/cockpit/PinGate";

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

  it("renders the engine price status and warning without an invented fallback", () => {
    const ui = source("app/garuda-voa/GarudaPreviewClient.tsx");
    expect(ui).toContain("Price status: {result.price_status}");
    expect(ui).toContain("result.price_warning");
    expect(ui).toContain('className="garuda-warning"');
    expect(ui).not.toContain("No catalogue source returned");
  });

  it("requires Bearer validation in every cockpit and GARUDA protected API", () => {
    for (const route of [
      "app/api/cockpit/session/route.ts",
      "app/api/cockpit/cron/list/route.ts",
      "app/api/cockpit/cron/run/route.ts",
      "app/api/cockpit/decisions/route.ts",
      "app/api/cockpit/intent/create/route.ts",
      "app/api/garuda-voa/evaluate/route.ts",
      "app/api/llm-costs/recommendations/route.ts",
    ]) {
      expect(source(route)).toContain("hasValidCockpitSession");
    }
  });

  it("routes recommendations through the private middleware and session gate", () => {
    const middleware = source("middleware.ts");
    const costDashboard = source("app/cost-dashboard/page.tsx");

    expect(middleware).toContain('"/api/llm-costs/recommendations"');
    expect(middleware).toContain(
      'req.nextUrl.pathname === "/api/llm-costs/recommendations"',
    );
    expect(costDashboard).toContain("<PinGate>");
    expect(costDashboard).toContain("<RecommendationPanel />");
  });

  it("carries the cockpit bearer through recommendation reads and writes", () => {
    const panel = source("components/RecommendationPanel.tsx");

    expect(panel).toContain("useCockpitSession");
    expect(panel).toContain("const { authorization, relock }");
    expect(panel).toContain("headers: { authorization }");
    expect(panel).toContain('"content-type": "application/json"');
    expect(panel.match(/status === 401/g)).toHaveLength(2);
    expect(panel.match(/relock\(\)/g)).toHaveLength(2);
    expect(panel).toContain("if (!response.ok)");
    expect(panel).toContain("[authorization, load, relock]");
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
  beforeEach(() => {
    reactHarness.cursor = 0;
    reactHarness.setters = [vi.fn(), vi.fn(), vi.fn(), vi.fn()];
    reactHarness.stateValues = [null, "SYNTHETIC_INPUT_SECRET", null, false];
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  async function submitPinGate(): Promise<void> {
    reactHarness.cursor = 0;
    const gate = PinGate({ children: null }) as ReactElement<{
      children: ReactElement<{
        onSubmit: (event: FormEvent) => Promise<void>;
      }>;
    }>;
    await gate.props.children.props.onSubmit({
      preventDefault: vi.fn(),
    } as unknown as FormEvent);
  }

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

  it("preserves the bounded rate-limit message", () => {
    expect(cockpitLoginFailureMessage(429)).toBe(
      "rate-limited: try again in 5 minutes",
    );
  });

  it("redacts malformed successful authentication responses", async () => {
    const responseSecret = "SYNTHETIC_RESPONSE_SECRET";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: vi.fn().mockResolvedValue(responseSecret),
      }),
    );

    await submitPinGate();

    const renderedErrors = JSON.stringify(reactHarness.setters[2].mock.calls);
    expect(reactHarness.setters[2]).toHaveBeenLastCalledWith(
      AUTHENTICATION_UNAVAILABLE_MESSAGE,
    );
    expect(renderedErrors).not.toContain(responseSecret);
    expect(renderedErrors).not.toContain("SYNTHETIC_INPUT_SECRET");
  });

  it("redacts network exception messages", async () => {
    const networkSecret = "SYNTHETIC_NETWORK_SECRET";
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error(networkSecret)));

    await submitPinGate();

    const renderedErrors = JSON.stringify(reactHarness.setters[2].mock.calls);
    expect(reactHarness.setters[2]).toHaveBeenLastCalledWith(
      AUTHENTICATION_UNAVAILABLE_MESSAGE,
    );
    expect(renderedErrors).not.toContain(networkSecret);
    expect(renderedErrors).not.toContain("SYNTHETIC_INPUT_SECRET");
  });
});
