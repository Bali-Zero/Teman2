/**
 * content-freshness-sentinel.test.ts
 *
 * THE DEAD-MAN'S SWITCH between published content and regulatory ground-truth.
 *
 * Born 2026-06-14 (Mythos M3 — knowledge-decay TAC of the public site).
 *
 * The malattia-delle-malattie this guards against: there is no SSOT for the
 * regulatory claims the site publishes, and nothing detects when a fact on the
 * site diverges from verified ground-truth. Articles are AI-generated /
 * hand-written in isolation, so the SAME stale code (55110, B211A, "by the
 * 10th", "Sarbagita freeze") reappears across many files and silently rots.
 *
 * This test reads the verified claim ledger (_regulatory-claim-ledger.json) and
 * FAILS if any `stale_pattern` reappears in published MDX *outside* a recognised
 * migration / correction context. A green run does not prove the site is
 * perfect — it proves the known-stale facts have not regressed. When the world
 * changes, re-verify against NotebookLM, update the ledger, and this test
 * keeps the regression closed.
 *
 * Scope: English canonical .mdx only (.it/.id/.ru/.fr/.de/.es/.nl are
 * translations, audited separately). Run: `npm test` (Vitest).
 */

import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const CONTENT_ROOT = __dirname; // apps/mouth/src/content
const LEDGER_PATH = path.join(CONTENT_ROOT, "_regulatory-claim-ledger.json");

/** Translation locale suffixes to skip (canonical EN is the auditable surface). */
const TRANSLATION_SUFFIX = /\.(it|id|ru|fr|de|es|nl|ja|zh|ko|pt|nl)\.mdx$/;

interface Claim {
  id: string;
  domain: string;
  stale_pattern: string;
  current_fact: string;
  source: string;
  severity: string;
}

interface Ledger {
  verified_on: string;
  claims: Claim[];
}

/**
 * Phrases that, when present in the same paragraph/line window as a stale
 * pattern, mark it as a deliberate historical / migration / correction
 * reference (legitimate) rather than the site asserting the stale fact as
 * current. Lower-cased match.
 */
const MIGRATION_CONTEXT = [
  "superseded",
  "supersede",
  "recoded",
  "recoding",
  "replaced by",
  "replaced the",
  "no longer issued",
  "no longer accepted",
  "old kbli 2020",
  "kbli 2020 code",
  "kbli 2020 had",
  "had one code",
  "splits them",
  "now split",
  "legacy",
  "was the cancelled",
  "cancelled september",
  "cancelled sept",
  "the september 2024 proposal",
  "pre-2024",
  "abolished",
  "not codified",
  "does not have a single",
  "not an investor",
  "is the remote worker",
  "cannot legally hold",
  "cannot hold",
  "common misconception",
  "used to say",
  "previously",
  "formerly",
  "now e23",
  "now c1",
  "split by star rating",
  "split into",
  "moved to the 15th",
  "not nib suspension",
  "the old",
] as const;

function collectMdx(dir: string, acc: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      collectMdx(full, acc);
    } else if (
      entry.name.endsWith(".mdx") &&
      !TRANSLATION_SUFFIX.test(entry.name)
    ) {
      acc.push(full);
    }
  }
  return acc;
}

/**
 * Returns the line indices of `file` where `pattern` appears WITHOUT a
 * migration-context cue in the surrounding window (the matching line plus the
 * line before and after — claims and their correction notes live close).
 */
function staleHits(content: string, pattern: string): number[] {
  const lines = content.split("\n");
  const needle = pattern.toLowerCase();
  const hits: number[] = [];

  for (let i = 0; i < lines.length; i++) {
    if (!lines[i].toLowerCase().includes(needle)) continue;
    const windowText = [lines[i - 1] ?? "", lines[i], lines[i + 1] ?? ""]
      .join(" ")
      .toLowerCase();
    const excused = MIGRATION_CONTEXT.some((cue) => windowText.includes(cue));
    if (!excused) hits.push(i + 1);
  }
  return hits;
}

const ledger: Ledger = JSON.parse(fs.readFileSync(LEDGER_PATH, "utf-8"));
const mdxFiles = collectMdx(path.join(CONTENT_ROOT, "articles")).concat(
  collectMdx(path.join(CONTENT_ROOT, "visa")),
);

describe("regulatory claim ledger integrity", () => {
  it("ledger has a recent verification date and well-formed claims", () => {
    expect(ledger.claims.length).toBeGreaterThan(0);
    for (const c of ledger.claims) {
      expect(c.id, "claim missing id").toBeTruthy();
      expect(c.stale_pattern, `${c.id} missing stale_pattern`).toBeTruthy();
      expect(c.current_fact, `${c.id} missing current_fact`).toBeTruthy();
      expect(c.source, `${c.id} missing ground-truth source`).toBeTruthy();
    }
  });
});

describe("knowledge-freshness sentinel: no stale regulatory fact reasserted as current", () => {
  for (const claim of ledger.claims) {
    it(`[${claim.id}] "${claim.stale_pattern}" must not appear as a current fact`, () => {
      const offenders: string[] = [];
      for (const file of mdxFiles) {
        const content = fs.readFileSync(file, "utf-8");
        const hits = staleHits(content, claim.stale_pattern);
        if (hits.length > 0) {
          const rel = path.relative(CONTENT_ROOT, file);
          offenders.push(`${rel}:${hits.join(",")}`);
        }
      }
      expect(
        offenders,
        offenders.length === 0
          ? ""
          : `\nSTALE REGULATORY FACT reasserted (${claim.severity}): "${claim.stale_pattern}"\n` +
              `  Current fact: ${claim.current_fact}\n` +
              `  Source: ${claim.source}\n` +
              `  Offending file(s): \n    ${offenders.join("\n    ")}\n` +
              `  Fix: correct the fact, or wrap it in a migration/correction note ` +
              `(e.g. "superseded", "old KBLI 2020 code", "now ...").\n`,
      ).toEqual([]);
    });
  }
});
