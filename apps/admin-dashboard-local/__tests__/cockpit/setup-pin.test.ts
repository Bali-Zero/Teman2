import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { afterEach, describe, expect, it } from "vitest";

const temporaryHomes: string[] = [];

afterEach(() => {
  for (const home of temporaryHomes.splice(0)) {
    rmSync(home, { recursive: true, force: true });
  }
});

describe("cockpit passphrase setup", () => {
  it("reads plaintext from stdin rather than argv", () => {
    const setup = readFileSync(
      path.join(process.cwd(), "scripts/setup-cockpit-pin.sh"),
      "utf8",
    );
    expect(setup).toContain('fs.readFileSync(0, "utf8")');
    expect(setup).toContain('Buffer.byteLength(passphrase, "utf8")');
    expect(setup).not.toContain("process.argv[1]");
  });

  it("rejects a Unicode passphrase above 72 UTF-8 bytes", () => {
    const home = mkdtempSync(path.join(tmpdir(), "cockpit-pin-test-"));
    temporaryHomes.push(home);
    const tooWide = "😀".repeat(19);
    expect(tooWide.length).toBeLessThanOrEqual(64);
    expect(Buffer.byteLength(tooWide, "utf8")).toBeGreaterThan(72);

    const result = spawnSync("bash", ["scripts/setup-cockpit-pin.sh"], {
      cwd: process.cwd(),
      encoding: "utf8",
      env: { ...process.env, HOME: home },
      input: `${tooWide}\n${tooWide}\n`,
    });

    expect(result.status).toBe(1);
    expect(result.stderr).toContain("at most 72 UTF-8 bytes");
    expect(
      existsSync(path.join(home, ".config/zantara-cockpit/pin.hash")),
    ).toBe(false);
  });
});
