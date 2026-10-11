import { readdirSync, readFileSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";
import ts from "typescript";
import { describe, expect, it } from "vitest";
import { dict } from "./i18n";

// Dead-key census. A key in the dictionary that no code reaches is copy that
// can silently go false (nine of the 46 keys #8205 deleted were) while a
// truth table still "pins" it. This test fails when such a key is added, or
// re-added, without being named in UNRENDERED_ALLOWLIST.
//
// What counts as a reference (scanned: every non-test .ts/.tsx under
// (visa-oracle)/visa-oracle/, plus any other non-test src file importing this
// dictionary; i18n.ts itself is excluded; comments are stripped first, so a key
// named only in a comment is not a reference):
//   1. EXACT   - the key as a whole quoted literal: "q.in_indonesia".
//   2. TEMPLATE - a template literal with a static prefix, e.g.
//      `lane.${lane}.notice` or `q.stay_permit_code.opt.${key}`. Each ${...}
//      stands for ONE dotted segment (never several), so `outcome.${x}` can
//      only reach two-segment keys, not the whole outcome.* family. The
//      segment must also appear as a quoted literal somewhere in the scanned
//      sources (a real enum member or question id), so a template does not
//      vouch for a value nothing ever produces.
//   3. DERIVED  - a template that opens with an interpolation and ends in a
//      static suffix (`${promptKey}.hint`) makes <referenced key>.<suffix>
//      referenced; the base key must itself be referenced by rule 1 or 2.
// Anything else needs an entry in UNRENDERED_ALLOWLIST with a reason.
// Known limits (static analysis cannot see them): a template vouches for an
// enum member that is declared but never produced at runtime (for example
// outcome.document_status.CONDITIONAL/UNKNOWN: the adapter only emits
// REQUIRED); and a template whose interpolation spans several dotted segments
// is flagged, loudly, until the call site is split or the key allowlisted.
// Rule 2 is also wide on purpose: `q.${id}` and `why.${id}` in tree.ts cover
// every question id that appears as a literal (~119 keys plus their .hint),
// so such a key stays "referenced" while its question id survives anywhere,
// even after its last exact reference is removed.

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ORACLE_ROOT = path.resolve(HERE, "..");
const SRC_ROOT = path.resolve(HERE, "../../../..");

/** The 46 keys #8205 (bf953020ed) deleted. They must never come back. */
const TOMBSTONES: readonly string[] = [
  "process.announce_prune",
  "process.answer_unsure",
  "process.branch_preview_more",
  "process.branch_reopen_aria",
  "process.candidates_follow_up",
  "process.candidates_none",
  "process.candidates_pending",
  "process.candidates_title",
  "process.candidates_undecided",
  "process.categories_title",
  "process.category_status.current",
  "process.category_status.done",
  "process.category_status.pending",
  "process.category_status.pruned",
  "process.decides_awaiting",
  "process.decides_confirmation",
  "process.decides_context",
  "process.decides_fact",
  "process.decides_framing",
  "process.decides_none",
  "process.decides_review",
  "process.decides_title",
  "process.jump_aria",
  "process.jump_empty",
  "process.jump_title",
  "process.label",
  "process.outcome_node",
  "process.phase_status.current",
  "process.phase_status.done",
  "process.phase_status.partial",
  "process.phase_status.pending",
  "process.phase_status.pruned",
  "process.phase.details",
  "process.phase.identity",
  "process.phase.intent",
  "process.phase.location",
  "process.phase.outcome",
  "process.phase.review",
  "process.phases_label",
  "process.pruned_because",
  "process.pruned_none",
  "process.step_of",
  "question.human_context_notice",
  "whyweask.fact_prefix",
  "whyweask.human_context",
  "whyweask.review_only",
];

/** The allowlist may only shrink: lower this with it, never raise it. */
const ALLOWLIST_CEILING = 102;

const UNRENDERED_ALLOWLIST: readonly {
  reason: string;
  keys: readonly string[];
}[] = [
  // Frozen. It may only shrink: delete a key from the dictionary and from here
  // together, or render it and remove it from here.
  {
    reason:
      "the retired interview-tree/breadcrumb panel: no component or helper builds a tree.* key",
    keys: [
      "tree.edit_aria",
      "tree.breadcrumb_label",
      "tree.framing",
      "tree.in_indonesia",
      "tree.permit_expiry",
      "tree.holds_stay_permit",
      "tree.current_status_code",
      "tree.stay_permit_code",
      "tree.renewal_paid",
      "tree.overstay_days",
      "tree.wants_onshore_conversion",
      "tree.application_channel",
      "tree.nationalities",
      "tree.birth_date",
      "tree.category",
      "tree.trip_scope",
      "tree.entry_pattern",
      "tree.sponsor_category",
      "tree.business_activity",
      "tree.business_sponsor_confirmed",
      "tree.work_payer",
      "tree.work_indonesia_compensation",
      "tree.work_sponsor_confirmed",
      "tree.sponsor_government_invitation",
      "tree.sponsor_government_collaboration",
      "tree.sponsor_world_figure_invitation",
      "tree.sponsor_diplomatic_household",
      "tree.sponsor_trade_office",
      "tree.remote_clients",
      "tree.remote_compensation",
      "tree.remote_employer_country",
      "tree.remote_pt_pma",
      "tree.stay_days",
      "tree.investment_vehicle",
      "tree.investment_pt_pma",
      "tree.investment_capital_idr",
      "tree.investment_paid_up_capital_idr",
      "tree.investment_role",
      "tree.investment_establishes_company",
      "tree.investment_foreign_branch",
      "tree.investment_ikn_subsidiary",
      "tree.investment_capital_market_only",
      "tree.investment_meets_threshold",
      "tree.family_relation",
      "tree.marital_status",
      "tree.family_sponsor_nationalities",
      "tree.family_sponsor_status_code",
      "tree.family_sponsor_permit_basis",
      "tree.family_marriage_registered",
      "tree.family_stepchild_marriage_certificate_confirmed",
      "tree.family_stepchild_birth_certificate_confirmed",
      "tree.family_sponsor_confirmed",
      "tree.retirement_penjamin_confirmed",
      "tree.retirement_basis",
      "tree.secondhome_basis",
      "tree.secondhome_deposit_usd",
      "tree.secondhome_state_bank",
      "tree.secondhome_own_name",
      "tree.secondhome_property_value_usd",
      "tree.secondhome_passive_income_usd",
      "tree.study_level",
      "tree.study_admission_confirmed",
      "tree.study_sponsor_confirmed",
      "tree.diaspora_connection",
      "tree.diaspora_documents",
      "tree.other_purpose",
      "tree.other_paid_activity",
      "tree.review_gate",
      "tree.confirmation",
      "tree.verdict",
      "tree.sr_path_label",
      "tree.sr_status.done",
      "tree.sr_status.current",
      "tree.sr_status.pending",
      "tree.sr_status.pruned",
      "tree.investment_currency",
      "tree.investment_amount_usd",
      "tree.retirement_undecided_basis",
    ],
  },
  {
    reason:
      "outcome sheet and verdict copy no component renders (no literal, no template reaches them)",
    keys: [
      "verdict.evaluating",
      "verdict.eligibility.eligible",
      "verdict.eligibility.likely",
      "verdict.eligibility.conditional",
      "verdict.eligibility.likely-not",
      "outcome.price_free",
      "outcome.whatsapp_summary_header",
      "outcome.whatsapp_cta",
      "outcome.qr_aria",
      "outcome.rank",
      "outcome.why_supported",
      "outcome.sources_title",
      "outcome.freshness_stamp",
      "outcome.temporarily_unavailable_body",
      "outcome.overstay_reassurance",
    ],
  },
  {
    reason:
      "question copy whose key is never built: q.current_status_code.label, q.guardian_consent.help, q.review_gate.none_selected, question.invalid_country_codes",
    keys: [
      "q.current_status_code.label",
      "q.guardian_consent.help",
      "q.review_gate.none_selected",
      "question.invalid_country_codes",
    ],
  },
  {
    reason:
      "shell chrome never rendered: paths counter, prototype detail, theme toggle light/dark labels",
    keys: [
      "paths.counter.label",
      "paths.counter.aria",
      "prototype.badge.detail",
      "theme.toggle.light",
      "theme.toggle.dark",
    ],
  },
];

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (
      /\.(ts|tsx)$/.test(entry.name) &&
      !/\.test\.tsx?$/.test(entry.name)
    )
      out.push(full);
  }
  return out;
}

const printer = ts.createPrinter({ removeComments: true });

/** The file's code with every comment removed (literals keep their text). */
function withoutComments(file: string): string {
  const source = ts.createSourceFile(
    file,
    readFileSync(file, "utf8"),
    ts.ScriptTarget.Latest,
    false,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  return printer.printFile(source);
}

function scannedSources(): string[] {
  const i18nFile = path.join(HERE, "i18n.ts");
  const files = new Set(walk(ORACLE_ROOT));
  for (const file of walk(SRC_ROOT)) {
    if (files.has(file)) continue;
    if (/visa-oracle\/_lib\/i18n["']/.test(readFileSync(file, "utf8")))
      files.add(file);
  }
  files.delete(i18nFile);
  return [...files].map((file) => withoutComments(file));
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function referencedKeys(keys: readonly string[], sources: string[]) {
  const text = sources.join("\n");
  const literals = new Set<string>();
  for (const m of text.matchAll(/["'`]([^"'`\s${}]+)["'`]/g))
    literals.add(m[1]);

  const patterns: RegExp[] = [];
  const suffixes = new Set<string>();
  for (const m of text.matchAll(/`([^`]*\$\{[^`]*)`/g)) {
    const parts = m[1].split(/\$\{[^}]*\}/);
    if (parts[0] === "") {
      const tail = parts[parts.length - 1];
      if (parts.length === 2 && /^\.[A-Za-z0-9_-]+$/.test(tail))
        suffixes.add(tail);
      continue;
    }
    if (!parts[0].includes(".")) continue;
    patterns.push(new RegExp("^" + parts.map(escapeRe).join("([^.]+)") + "$"));
  }

  const direct = new Set<string>();
  for (const key of keys) {
    if (literals.has(key)) {
      direct.add(key);
      continue;
    }
    for (const re of patterns) {
      const hit = re.exec(key);
      if (hit && hit.slice(1).every((seg) => literals.has(seg))) {
        direct.add(key);
        break;
      }
    }
  }
  const referenced = new Set(direct);
  for (const key of keys) {
    for (const suffix of suffixes) {
      if (key.endsWith(suffix) && direct.has(key.slice(0, -suffix.length)))
        referenced.add(key);
    }
  }
  return referenced;
}

describe("visa-oracle i18n dead-key census", () => {
  const enKeys = Object.keys(dict.en);
  const referenced = referencedKeys(enKeys, scannedSources());
  const allowlist = new Set(UNRENDERED_ALLOWLIST.flatMap((g) => g.keys));

  it("has the same key set in EN and ID", () => {
    expect(Object.keys(dict.id).sort()).toEqual([...enKeys].sort());
  });

  it("has no key that nothing references and the allowlist does not name", () => {
    const dead = enKeys.filter((k) => !referenced.has(k) && !allowlist.has(k));
    expect(
      dead,
      `unreferenced i18n keys (render them, or delete them; do not extend the allowlist):\n${dead.join("\n")}`,
    ).toEqual([]);
  });

  it("keeps the allowlist honest: every entry exists and is still unreferenced", () => {
    const stale = [...allowlist].filter(
      (k) => !(k in dict.en) || referenced.has(k),
    );
    expect(
      stale,
      `allowlisted keys that were deleted or are now referenced (remove them from UNRENDERED_ALLOWLIST):\n${stale.join("\n")}`,
    ).toEqual([]);
  });

  it("never grows the allowlist, repeats a key, or leaves a group unexplained", () => {
    const all = UNRENDERED_ALLOWLIST.flatMap((g) => g.keys);
    expect(new Set(all).size, "duplicate allowlist entry").toBe(all.length);
    expect(all.length).toBeLessThanOrEqual(ALLOWLIST_CEILING);
    for (const group of UNRENDERED_ALLOWLIST)
      expect(group.reason.trim().length).toBeGreaterThan(0);
  });

  it("never brings back a key #8205 deleted", () => {
    const back = TOMBSTONES.filter((k) => k in dict.en || k in dict.id);
    expect(back, `tombstoned keys re-added:\n${back.join("\n")}`).toEqual([]);
  });

  it("lists each tombstone once and all 46 of them", () => {
    expect(new Set(TOMBSTONES).size).toBe(TOMBSTONES.length);
    expect(TOMBSTONES).toHaveLength(46);
  });
});
