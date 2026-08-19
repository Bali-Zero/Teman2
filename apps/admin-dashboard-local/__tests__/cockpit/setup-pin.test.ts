import {
  existsSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  statSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { afterEach, describe, expect, it } from "vitest";
import {
  createCockpitSessionToken,
  verifyCockpitSessionToken,
} from "@/lib/cockpit-session";

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

  it("preserves the audit key but rotates a mode-0600 session key", async () => {
    const home = mkdtempSync(path.join(tmpdir(), "cockpit-pin-rotation-"));
    temporaryHomes.push(home);
    const configDir = path.join(home, ".config", "zantara-cockpit");
    const environment = { ...process.env, HOME: home };

    const first = spawnSync("bash", ["scripts/setup-cockpit-pin.sh"], {
      cwd: process.cwd(),
      encoding: "utf8",
      env: environment,
      input: "synthetic-passphrase-one\nsynthetic-passphrase-one\n",
    });
    expect(first.status).toBe(0);

    const hmacPath = path.join(configDir, "hmac.key");
    const sessionPath = path.join(configDir, "session.key");
    const firstHmac = readFileSync(hmacPath, "utf8");
    const firstSession = readFileSync(sessionPath, "utf8");
    const oldToken = await createCockpitSessionToken(
      firstSession,
      "http://localhost:3100",
    );

    const second = spawnSync("bash", ["scripts/setup-cockpit-pin.sh"], {
      cwd: process.cwd(),
      encoding: "utf8",
      env: environment,
      input: "y\nsynthetic-passphrase-two\nsynthetic-passphrase-two\n",
    });
    expect(second.status).toBe(0);

    const secondHmac = readFileSync(hmacPath, "utf8");
    const secondSession = readFileSync(sessionPath, "utf8");
    expect(secondHmac).toBe(firstHmac);
    expect(secondSession).not.toBe(firstSession);
    expect(statSync(hmacPath).mode & 0o777).toBe(0o600);
    expect(statSync(sessionPath).mode & 0o777).toBe(0o600);
    expect(
      await verifyCockpitSessionToken(
        oldToken,
        secondSession,
        "http://localhost:3100",
      ),
    ).toBe(false);
  });
});
