import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const execFileMock = vi.hoisted(() => vi.fn());
vi.mock("node:child_process", () => ({ execFile: execFileMock }));

import { resolveGatewayScript, sendTelegramAlert } from "../bridge/telegram.js";

type ExecCallback = (
  err: Error | null,
  stdout: string,
  stderr: string,
) => void;

function mockGatewayOutcome(outcome: string): void {
  execFileMock.mockImplementation(
    (_cmd: string, _args: string[], _opts: object, cb: ExecCallback) => {
      cb(null, "", `tg_notify: ${outcome}\n`);
    },
  );
}

function makeLogger() {
  return { debug: vi.fn(), warn: vi.fn() } as never;
}

beforeEach(() => {
  execFileMock.mockReset();
});

afterEach(() => {
  delete process.env.WA_MIRROR_TG_GATEWAY;
});

describe("resolveGatewayScript", () => {
  it("finds the repo tg_notify.py by walking up from the module", () => {
    const found = resolveGatewayScript();
    expect(found).not.toBeNull();
    expect(found).toMatch(/scripts\/tg_notify\.py$/);
  });

  it("honours the WA_MIRROR_TG_GATEWAY override", () => {
    process.env.WA_MIRROR_TG_GATEWAY = "/custom/path/tg_notify.py";
    expect(resolveGatewayScript()).toBe("/custom/path/tg_notify.py");
  });
});

describe("sendTelegramAlert — gateway routing", () => {
  it("routes a p0 alert with dedup key through python3 tg_notify.py", async () => {
    mockGatewayOutcome("sent");
    await sendTelegramAlert("wa-mirror LOGGED OUT: test", makeLogger(), {
      tier: "p0",
      dedupKey: "wa-bridge:loggedout:test",
    });

    expect(execFileMock).toHaveBeenCalledTimes(1);
    const [cmd, args] = execFileMock.mock.calls[0] as [string, string[]];
    expect(cmd).toBe("python3");
    expect(args[0]).toMatch(/scripts\/tg_notify\.py$/);
    expect(args).toContain("--tier");
    expect(args[args.indexOf("--tier") + 1]).toBe("p0");
    expect(args[args.indexOf("--source") + 1]).toBe("wa-mirror-bridge");
    expect(args[args.indexOf("--dedup-key") + 1]).toBe(
      "wa-bridge:loggedout:test",
    );
    // Text rides after the `--` separator so a leading dash can't be
    // mistaken for a flag by argparse.
    expect(args[args.indexOf("--") + 1]).toBe("wa-mirror LOGGED OUT: test");
  });

  it("defaults to the digest tier with no dedup key", async () => {
    mockGatewayOutcome("spooled");
    await sendTelegramAlert("wa-mirror connected: test", makeLogger());

    const [, args] = execFileMock.mock.calls[0] as [string, string[]];
    expect(args[args.indexOf("--tier") + 1]).toBe("digest");
    expect(args).not.toContain("--dedup-key");
  });

  it("never throws when the gateway subprocess fails (alerting is best-effort)", async () => {
    execFileMock.mockImplementation(
      (_cmd: string, _args: string[], _opts: object, cb: ExecCallback) => {
        cb(new Error("spawn python3 ENOENT"), "", "");
      },
    );
    const logger = makeLogger();
    await expect(
      sendTelegramAlert("boom", logger),
    ).resolves.toBeUndefined();
    expect((logger as { warn: ReturnType<typeof vi.fn> }).warn).toHaveBeenCalled();
  });

  it("trusts the WA_MIRROR_TG_GATEWAY override without an existence check", async () => {
    process.env.WA_MIRROR_TG_GATEWAY = "/nonexistent/tg_notify.py";
    // Override points at a missing file — resolveGatewayScript trusts the
    // override, so the subprocess DOES run and surfaces the error path
    // instead of silently swallowing a misconfiguration.
    mockGatewayOutcome("sent");
    await sendTelegramAlert("hello", makeLogger());
    expect(execFileMock).toHaveBeenCalledTimes(1);
  });
});
