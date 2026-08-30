import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * auth-gates-cookie-primary — repo-wide regression guard.
 *
 * `ApiClientBase.isAuthenticated()` is a local-token-only, POSITIVE-only
 * signal (see the docstring on it in ./client.ts): its absence does not mean
 * the visitor is anonymous, because auth here is cookie-PRIMARY (httpOnly
 * `nz_access_token`, invisible to JS — a Safari Private session, a blocked
 * localStorage, or an expired local token with a still-live cookie all read
 * as "not authenticated" to it). Gating rendering/redirects on it is exactly
 * the split-brain PR #5181 cured at 14 call-sites: use `hasSession()` /
 * `useSessionState()` instead, which resolve "authenticated" | "anonymous" |
 * "unknown" against the server.
 *
 * Pinning the 14 already-fixed files (the pre-sweep version of this guard)
 * can only ever re-verify surfaces someone already fixed; it can never catch
 * the NEXT file that reaches for `.isAuthenticated()` as a gate. Every
 * source file under apps/mouth/src is swept instead — mirrors
 * app/whatsapp-ink.guard.test.ts.
 *
 * client.ts itself is allowlisted: it OWNS the method (the definition has no
 * leading `.`, so the call-regex below never matches it) and its own
 * `hasSession()` calls `this.isAuthenticated()` once, deliberately, as the
 * sanctioned fast path INSIDE the cookie-confirming flow — not a bypass of
 * it.
 */

const REPO_ROOT = join(__dirname, "..", "..", "..", "..", "..");
const MOUTH_SRC = join(REPO_ROOT, "apps", "mouth", "src");
const SWEEP_EXCLUDED_DIRS = new Set(["node_modules", ".next", "dist", "build"]);
const SWEEP_EXTENSION_RE = /\.tsx?$/;
const TEST_FILE_RE = /\.(?:test|spec)\.[^./]+$/;

const ALLOWLIST = new Set([join(MOUTH_SRC, "lib", "api", "client.ts")]);

/**
 * Call-sites only — never the method definition (`isAuthenticated(): boolean
 * {`) or the interface declaration (`isAuthenticated(): boolean;`), neither
 * of which has a leading `.`. Comments are stripped first so prose that
 * *mentions* the old call-site (e.g. this file's own docstring, or the
 * migration-note comments PR #5181 left behind) doesn't trip the sweep.
 */
const GATE_CALL_RE = /\.isAuthenticated\s*\(/;

function stripComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
}

function gateCallSites(source: string): string[] {
  const stripped = stripComments(source);
  return [...stripped.matchAll(new RegExp(GATE_CALL_RE, "g"))].map(
    ([match]) => match,
  );
}

function sweepFiles(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (SWEEP_EXCLUDED_DIRS.has(entry.name)) continue;
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      sweepFiles(full, acc);
    } else if (
      SWEEP_EXTENSION_RE.test(entry.name) &&
      !TEST_FILE_RE.test(entry.name)
    ) {
      acc.push(full);
    }
  }
  return acc;
}

const SWEPT_FILES = sweepFiles(MOUTH_SRC).filter((f) => !ALLOWLIST.has(f));

describe("auth-localstorage-gate guard", () => {
  it("GUILT: catches a call-site gating on the local-token-only check", () => {
    const guilty = [
      "if (api.isAuthenticated()) {",
      "  return <Dashboard />;",
      "}",
      'if (!this.isAuthenticated()) router.push("/login");',
    ].join("\n");

    expect(gateCallSites(guilty)).toHaveLength(2);
  });

  it("INNOCENCE: ignores the server-resolved hook and prose mentioning the old call-site", () => {
    const innocent = [
      "const session = useSessionState();",
      'if (session === "anonymous") router.push("/login");',
      "// used to gate on api.isAuthenticated() before PR #5181",
      "/**",
      " * Every consumer that used to gate on `api.isAuthenticated()` now",
      " * asks hasSession() instead.",
      " */",
    ].join("\n");

    expect(gateCallSites(innocent)).toEqual([]);
  });

  it("the sweep actually visits a realistic number of files (not a silently-empty glob)", () => {
    // apps/mouth/src is in the low thousands of .ts/.tsx files; a handful
    // would mean MOUTH_SRC/extension are wrong, not that the app shrank.
    expect(SWEPT_FILES.length).toBeGreaterThan(500);
  });

  it("no file under apps/mouth/src (other than client.ts, which owns the method) gates on isAuthenticated()", () => {
    const offenders: string[] = [];
    for (const file of SWEPT_FILES) {
      const source = readFileSync(file, "utf8");
      const sites = gateCallSites(source);
      if (sites.length > 0) {
        offenders.push(`${relative(REPO_ROOT, file)}: ${sites.join(", ")}`);
      }
    }
    expect(
      offenders,
      offenders.length === 0
        ? ""
        : `\nlocalStorage-only auth gate reintroduced (auth is cookie-primary — ` +
            `see client.ts docstring on isAuthenticated()):\n  ${offenders.join("\n  ")}\n` +
            `  Fix: gate on useSessionState() / api.hasSession() instead.\n`,
    ).toEqual([]);
  });
});
