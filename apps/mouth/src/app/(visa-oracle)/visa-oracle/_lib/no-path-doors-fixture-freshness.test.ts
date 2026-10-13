/**
 * Freshness pin for `fixtures/no-path-doors.replay.json`.
 *
 * The replay is recorded against ONE signed rule pack. When a newer signed pack
 * lands and the fixture stays recorded on the older one, the no-door tests keep
 * passing while proving nothing about the pack that is live — that is how the
 * fixture went stale before. This test fails the moment the fixture's recorded
 * pack is not the highest `rulepack-prod-NNN.signed.json` (numeric NNN max).
 * Regenerate with `apps/mouth/scripts/visa-oracle/replay-no-path-doors.py`.
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";
import replay from "./fixtures/no-path-doors.replay.json";

const PACKS_DIR = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../../../../backend-rag/backend/services/visa_engine/contracts/packs",
);

const SIGNED = /^rulepack-prod-(\d+)\.signed\.json$/;

/** The signed pack with the numerically highest NNN among `names`. */
function highestSignedPack(names: string[]): { file: string; seq: number } {
  let best: { file: string; seq: number } | null = null;
  for (const file of names) {
    const m = SIGNED.exec(file);
    if (!m) continue;
    const seq = Number(m[1]);
    if (best === null || seq > best.seq) best = { file, seq };
  }
  if (best === null) throw new Error("no rulepack-prod-NNN.signed.json found");
  return best;
}

/** Empty string when fresh; otherwise the reason the recording is stale. */
function stalenessOf(
  recorded: { file: string; sequence: number },
  names: string[],
): string {
  const top = highestSignedPack(names);
  if (recorded.file !== top.file) {
    return `fixture recorded on ${recorded.file}, highest signed pack is ${top.file}`;
  }
  if (recorded.sequence !== top.seq) {
    return `fixture sequence ${recorded.sequence} != ${top.seq} of ${top.file}`;
  }
  return "";
}

describe("no-path-doors replay fixture freshness", () => {
  const names = fs.readdirSync(PACKS_DIR);

  it("is recorded on the highest signed rule pack", () => {
    expect(
      stalenessOf(replay.pack, names),
      "re-run apps/mouth/scripts/visa-oracle/replay-no-path-doors.py",
    ).toBe("");
  });

  it("GUILT: a recording on an older pack name is reported stale", () => {
    const top = highestSignedPack(names);
    const older = names
      .map((n) => ({ n, m: SIGNED.exec(n) }))
      .filter((x) => x.m && Number(x.m[1]) < top.seq)
      .map((x) => x.n)
      .sort()
      .pop();
    expect(
      older,
      "need an older signed pack to build the guilt case",
    ).toBeTruthy();
    const stale = { ...replay.pack, file: older as string };
    expect(stalenessOf(stale, names)).toContain(
      `highest signed pack is ${top.file}`,
    );
  });

  it("GUILT: a synthetic newer signed pack makes the current recording stale", () => {
    const top = highestSignedPack(names);
    const next = `rulepack-prod-${String(top.seq + 1).padStart(3, "0")}.signed.json`;
    expect(stalenessOf(replay.pack, [...names, next])).toContain(next);
  });

  it("INNOCENCE: the numeric max is not the lexicographic max or a non-prod pack", () => {
    expect(
      highestSignedPack([
        "rulepack-prod-9.signed.json",
        "rulepack-prod-010.signed.json",
        "rulepack-test-c1-tourism.signed.json",
        "rulepack-prod-029.source.json",
      ]).file,
    ).toBe("rulepack-prod-010.signed.json");
  });
});
