import { describe, it, expect } from "vitest";
import {
  isAgenticCronLabel,
  AGENTIC_CRON_ALLOWLIST,
} from "@/lib/cockpit-allowlist";

describe("cockpit-allowlist", () => {
  it("has exactly 35 entries", () => {
    expect(AGENTIC_CRON_ALLOWLIST.length).toBe(35);
  });
  it("all start with com.balizero. or com.matagaruda.", () => {
    for (const label of AGENTIC_CRON_ALLOWLIST) {
      expect(label).toMatch(/^com\.(balizero|matagaruda)\./);
    }
  });
  it("whitelisted labels return true", () => {
    expect(isAgenticCronLabel("com.balizero.regulatory-watcher")).toBe(true);
  });
  it("non-whitelisted return false", () => {
    expect(isAgenticCronLabel("com.apple.dock")).toBe(false);
    expect(isAgenticCronLabel("")).toBe(false);
  });
  it("rejects null/undefined", () => {
    expect(isAgenticCronLabel(null as any)).toBe(false);
    expect(isAgenticCronLabel(undefined as any)).toBe(false);
  });
});
