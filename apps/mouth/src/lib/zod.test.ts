import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);

    if (entry.isDirectory()) return sourceFiles(path);
    return /\.[cm]?[jt]sx?$/.test(entry.name) ? [path] : [];
  });
}

describe("CSP-safe Zod bootstrap", () => {
  it("enables jitless mode before an object schema can probe Function", async () => {
    vi.resetModules();
    delete (
      globalThis as typeof globalThis & {
        __zod_globalConfig?: { jitless?: boolean };
      }
    ).__zod_globalConfig;

    const nativeFunction = globalThis.Function;
    const functionProbe = vi.fn(() => {
      throw new Error("Zod attempted an eval-like Function probe");
    });

    Object.defineProperty(globalThis, "Function", {
      configurable: true,
      writable: true,
      value: functionProbe,
    });

    try {
      const { z } = await import("./zod");
      const schema = z.object({ value: z.string() });

      expect(z.config().jitless).toBe(true);
      expect(schema.parse({ value: "client-safe" })).toEqual({
        value: "client-safe",
      });
      expect(functionProbe).not.toHaveBeenCalled();
    } finally {
      Object.defineProperty(globalThis, "Function", {
        configurable: true,
        writable: true,
        value: nativeFunction,
      });
    }
  });

  it("routes application Zod imports through the CSP-safe entrypoint", () => {
    const sourceRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
    const bootstrapPath = resolve(sourceRoot, "lib/zod.ts");
    const directImport =
      /(?:from\s+|import\s*\(\s*|require\s*\(\s*)(["'])zod(?:\/[^"']+)?\1/;
    const offenders = sourceFiles(sourceRoot)
      .filter((path) => resolve(path) !== bootstrapPath)
      .filter((path) => directImport.test(readFileSync(path, "utf8")))
      .map((path) => path.slice(sourceRoot.length + 1));

    expect(offenders).toEqual([]);
  });
});
