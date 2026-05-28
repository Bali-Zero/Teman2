/**
 * Cockpit launchctl helper: parse `launchctl print gui/<UID>/<label>`.
 * Cached 2s in-memory. Why `print` not `list`: print gives exit status + state.
 */
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { AGENTIC_CRON_ALLOWLIST } from "./cockpit-allowlist";

const execFileAsync = promisify(execFile);

export interface CronStatus {
  label: string;
  state: "running" | "waiting" | "not_loaded";
  lastExitStatus: number | null;
  pid: number | null;
}

const cache = new Map<string, { value: CronStatus; expiresAt: number }>();
const CACHE_MS = 2000;

async function getCronStatusUncached(label: string): Promise<CronStatus> {
  const uid = process.getuid?.() ?? 501;
  try {
    const { stdout } = await execFileAsync(
      "launchctl",
      ["print", `gui/${uid}/${label}`],
      { timeout: 3000 },
    );
    const stateMatch = stdout.match(/state\s*=\s*(\w+)/);
    const exitMatch = stdout.match(/last exit code\s*=\s*(-?\d+)/);
    const pidMatch = stdout.match(/pid\s*=\s*(\d+)/);
    const state = stateMatch?.[1];
    return {
      label,
      state:
        state === "running"
          ? "running"
          : state === "waiting"
            ? "waiting"
            : "not_loaded",
      lastExitStatus: exitMatch ? parseInt(exitMatch[1], 10) : null,
      pid: pidMatch ? parseInt(pidMatch[1], 10) : null,
    };
  } catch {
    return { label, state: "not_loaded", lastExitStatus: null, pid: null };
  }
}

export async function getCronStatus(label: string): Promise<CronStatus> {
  const cached = cache.get(label);
  const now = Date.now();
  if (cached && cached.expiresAt > now) return cached.value;
  const value = await getCronStatusUncached(label);
  cache.set(label, { value, expiresAt: now + CACHE_MS });
  return value;
}

export async function getAllAgenticCronStatus(): Promise<CronStatus[]> {
  return Promise.all(AGENTIC_CRON_ALLOWLIST.map(getCronStatus));
}

export async function startCron(
  label: string,
): Promise<{ ok: boolean; stderr?: string }> {
  if (!AGENTIC_CRON_ALLOWLIST.includes(label as never)) {
    return { ok: false, stderr: "not in allowlist" };
  }
  const uid = process.getuid?.() ?? 501;
  try {
    await execFileAsync("launchctl", ["kickstart", `gui/${uid}/${label}`], {
      timeout: 5000,
    });
    cache.delete(label);
    return { ok: true };
  } catch (e: any) {
    return { ok: false, stderr: e.message };
  }
}
