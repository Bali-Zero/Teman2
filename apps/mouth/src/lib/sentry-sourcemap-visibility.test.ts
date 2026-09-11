import { describe, expect, it } from "vitest";

import { sentryWebpackPluginOptions } from "../../next.config";

/**
 * A failed source-map upload must never be SILENT.
 *
 * The plugin's default on a failed release creation or source-map upload is to
 * throw and stop the build. Two options can take that away, and both were, or
 * nearly were, present here:
 *
 *   - `silent: true` suppresses ALL build logs including errors, so the deploy
 *     still fails but says nothing about why. It was set for months under a
 *     comment claiming it only hid "source map uploading logs".
 *   - `errorHandler` makes compilation CONTINUE past the failure, which is
 *     worse: a green deploy whose release has no source maps, so every
 *     production stack trace stays minified and nobody is told.
 *
 * The concrete failure this guards is an expired or revoked
 * `SENTRY_AUTH_TOKEN` — the credential rotated on 2026-08-28, whose previous
 * value had been live on Vercel for 205 days.
 */
describe("sentry source-map upload failures stay visible", () => {
  it("does not suppress build logs", () => {
    expect(sentryWebpackPluginOptions).not.toHaveProperty("silent", true);
  });

  it("does not swallow upload errors with an errorHandler", () => {
    expect(
      (sentryWebpackPluginOptions as Record<string, unknown>).errorHandler,
    ).toBeUndefined();
  });

  it("still targets the org and project from the environment", () => {
    expect(sentryWebpackPluginOptions).toHaveProperty("org");
    expect(sentryWebpackPluginOptions).toHaveProperty("project");
  });
});
