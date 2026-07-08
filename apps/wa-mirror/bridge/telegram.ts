import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type pino from "pino";

// Cohort-4 of the tg-gateway migration (2026-07-07): the bridge no longer
// calls the Telegram Bot API directly. Every alert routes through
// scripts/tg_notify.py — p0 (immediate, budgeted+deduped) for actionable
// failures, digest (spooled, flushed 2x/day) for connect/reconnect noise.
// The W67 reconnect storm becomes one deduped digest line instead of spam.

export interface TelegramAlertOptions {
  /** p0 = immediate (budget 12/day, dedup 6h) · digest = spooled 2x/day. */
  tier?: "p0" | "digest";
  /** Stable key so repeats within the 6h window collapse to one entry. */
  dedupKey?: string;
}

const GATEWAY_TIMEOUT_MS = 90_000;

export function resolveGatewayScript(): string | null {
  const override = process.env.WA_MIRROR_TG_GATEWAY;
  if (override) return override;

  const candidates: string[] = [];
  const root = process.env.NUZANTARA_ROOT;
  if (root) candidates.push(join(root, "scripts", "tg_notify.py"));

  // Walk up from this module (bridge/ in source, dist/bridge/ compiled —
  // depths differ, so probe every ancestor instead of hardcoding one).
  let dir = dirname(fileURLToPath(import.meta.url));
  for (let i = 0; i < 6; i += 1) {
    candidates.push(join(dir, "scripts", "tg_notify.py"));
    dir = dirname(dir);
  }

  candidates.push(
    join(homedir(), "Desktop", "nuzantara", "scripts", "tg_notify.py"),
  );
  return candidates.find((p) => existsSync(p)) ?? null;
}

export async function sendTelegramAlert(
  text: string,
  logger?: pino.Logger,
  opts: TelegramAlertOptions = {},
): Promise<void> {
  const gateway = resolveGatewayScript();
  if (!gateway) {
    logger?.warn("wa-mirror Telegram alert dropped: tg_notify.py not found");
    return;
  }

  const tier = opts.tier ?? "digest";
  const args = [gateway, "--tier", tier, "--source", "wa-mirror-bridge"];
  if (opts.dedupKey) args.push("--dedup-key", opts.dedupKey);
  args.push("--", text);

  try {
    const outcome = await new Promise<string>((resolve, reject) => {
      execFile(
        "python3",
        args,
        { timeout: GATEWAY_TIMEOUT_MS },
        (err, stdout, stderr) => {
          if (err) {
            reject(err);
            return;
          }
          // The gateway prints "tg_notify: <outcome>" on stderr; last line wins.
          const line = `${stderr}\n${stdout}`
            .split("\n")
            .reverse()
            .find((l) => l.startsWith("tg_notify:"));
          resolve(line ? line.slice("tg_notify:".length).trim() : "unknown");
        },
      );
    });
    logger?.debug({ tier, outcome }, "wa-mirror Telegram alert routed");
  } catch (err) {
    logger?.warn(
      { err: (err as Error).message },
      "wa-mirror Telegram alert threw",
    );
  }
}
