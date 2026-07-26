// =============================================================================
// CANONICAL PIN GATE — the derived pins on the KBLI canonical must agree with it.
//
// WHY THIS LIVES IN apps/mouth, guarding a repo-root filiera artifact.
//
// The canonical KBLI dataset carries derived pins that go stale the instant a cure
// rewrites it. Two of them exist, and their histories diverge in a way that is the
// whole reason this file was written:
//
//   * the SIDECAR pin (`apps/mouth/data/kbli-dataset-version.json`) is guarded by
//     `kbli-dataset-version.test.ts` inside "Frontend Tests (Next.js) (mouth, true)",
//     which is a REQUIRED check. Every filiera compiler grew an `update_sidecar()`
//     that bumps it automatically.
//   * the MEMBERSHIP pin (`data/kbli-filiera/membership/batch-a-members.json`,
//     `canonical_sha256`) is guarded only by `kbli-filiera-vault-compilers`, which is
//     NOT among main's required contexts. No compiler bumps it. It has now been
//     missed three times — #3114 (repaired out-of-band by #3130) and twice on #3181.
//
// The gate that can BLOCK got engineered around; the gate that cannot got forgotten.
// So the membership pin is asserted HERE, from the one required suite that runs on
// every PR (`tests.yml` has no path filter) — no branch-protection change needed.
//
// It cannot be fixed inside the compilers instead: `emit_batch_membership.py` fences
// on "working canonical == HEAD's blob", so it refuses to run while a cure holds the
// canonical dirty. The re-emit is structurally a separate, later step — which is
// exactly why a human keeps forgetting it and why a machine has to ask.
//
// REMEDIATION when this fails: `python3 scripts/kbli_filiera/emit_batch_membership.py --apply`
// then verify the diff moved ONLY `canonical_revision` + `canonical_sha256` — if
// `members` moved too, the cure changed WHO is in the batch, which is a different and
// much larger claim than a provenance refresh.
// =============================================================================

import crypto from "crypto";
import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

// Anchored to this file, not to cwd — same discipline as kbli-internal-leak.test.ts:
// the verdict must not depend on whether vitest was invoked from apps/mouth (CI) or
// from the repo root (local sweep).
const REPO_ROOT = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  "../../../..",
);

const CANONICAL = path.join(
  REPO_ROOT,
  "data/source_documents/KBLI_2025_FINAL_CLEAN.json",
);
const MEMBERSHIP = path.join(
  REPO_ROOT,
  "data/kbli-filiera/membership/batch-a-members.json",
);

// Every published copy of the same dataset. Measured byte-identical on main; the
// filiera compilers keep them in sync via scripts/sync_kbli_dataset.sh.
const COPIES = [
  "data/source_documents/KBLI_2025_FINAL_CLEAN.json",
  "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json",
  "apps/kbli-navigator/data/kbli-2025.json",
];

const sha256 = (file: string) =>
  crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");

describe("KBLI canonical derived pins", () => {
  it("fails loudly if an input is missing, instead of passing blind", () => {
    // W102: a gate whose input vanished must accuse itself, not report all-clear.
    for (const f of [CANONICAL, MEMBERSHIP]) {
      expect(fs.existsSync(f), `gate input missing: ${f}`).toBe(true);
    }
  });

  it("membership canonical_sha256 matches the canonical on disk — re-emit it when a cure moves the dataset", () => {
    const membership = JSON.parse(fs.readFileSync(MEMBERSHIP, "utf-8")) as {
      canonical_sha256?: string;
    };
    // A legacy artifact predating the field would silently skip this assertion —
    // demand it, so "no pin" can never read as "pin agrees".
    expect(
      typeof membership.canonical_sha256,
      "batch-a-members.json carries no canonical_sha256 — re-emit it",
    ).toBe("string");

    expect(
      membership.canonical_sha256,
      "membership pin is stale: run `python3 scripts/kbli_filiera/emit_batch_membership.py --apply`",
    ).toBe(sha256(CANONICAL));
  });

  it("every published copy of the canonical is byte-identical", () => {
    const hashes = COPIES.map((rel) => {
      const abs = path.join(REPO_ROOT, rel);
      expect(fs.existsSync(abs), `canonical copy missing: ${rel}`).toBe(true);
      return `${rel} -> ${sha256(abs)}`;
    });
    const distinct = new Set(hashes.map((h) => h.split(" -> ")[1]));
    expect(
      distinct.size,
      `canonical copies diverged — run scripts/sync_kbli_dataset.sh:\n${hashes.join("\n")}`,
    ).toBe(1);
  });
});
