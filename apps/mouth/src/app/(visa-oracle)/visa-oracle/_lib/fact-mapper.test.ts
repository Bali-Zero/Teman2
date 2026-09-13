import { APPLICANT_FACT_COUNT } from "@/lib/api/applicant-fact-paths";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";
import {
  CATEGORY_TO_PURPOSE,
  SCHEMA_VERSION,
  SPONSOR_TYPES,
  mapCurrentStatusExpiry,
  mapCurrentlyInIndonesia,
  mapDisclosedReviewFlags,
  mapEmployerIsIndonesianEntity,
  mapOracleFactsToApplicantFacts,
  mapPurposes,
  mapRemoteClientsDerived,
  mapSponsorType,
  mapStayDays,
  mapViolationHistory,
  requestCategoryForFacts,
  stableEvaluationInputKey,
  type FactValue,
  type UnknownReasonWire,
} from "./fact-mapper";
import { getCategoryQuestionIds } from "./flow";
import {
  CATEGORY_KEYS,
  QUESTIONS,
  STAY_PERMIT_CODES,
  type OracleFacts,
  type OracleQuestion,
} from "./tree";

// ---------------------------------------------------------------------------
// The backend contract, extracted from models.py itself (never hand-typed —
// test acceptance criterion #1). The only dotted `Field(alias="a.b")`
// occurrences in models.py live inside `ApplicantFactsData`; every other
// `alias=` in the file (`TimeRange.from_`) has no dot, so the dotted-alias
// regex below can only ever match ApplicantFactsData fields.
//
// `sponsor.type` used to be deliberately omitted from the deployed frontend
// request during its ordered-rollout window (the `sponsor_category`
// interview question did not exist yet). That window is now closed: the
// question ships (see tree.ts/flow.ts), and this mapper emits `sponsor.type`
// on every call like every other key — KNOWN when answered, otherwise an
// explicit UNKNOWN (NOT_ASKED by default), never omitted. The key is still
// optional on the wire (models.py keeps a transitional default so older
// 40-key clients don't 422) but the frontend emits the complete contract.
//
// Widened again 2026-08-23 (owner ruling — Visa Oracle fact vocabulary
// extension, vocabulary-only, no rule change): three more optional/defaulted
// keys join the same rollout idiom —
// `family.stepchild_marriage_certificate_confirmed`,
// `family.stepchild_birth_certificate_confirmed` and
// `family.sponsor_permit_basis`. Same posture as `sponsor.type`: this mapper
// emits all three on every call, KNOWN when answered, otherwise an explicit
// UNKNOWN, never omitted — the frontend emits the complete contract.
// ---------------------------------------------------------------------------

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// _lib -> visa-oracle -> (visa-oracle) -> app -> src -> mouth -> apps -> repo root (7 levels).
const REPO_ROOT = path.resolve(__dirname, "../../../../../../..");
const MODELS_PY = path.join(
  REPO_ROOT,
  "apps/backend-rag/backend/services/visa_engine/models.py",
);

function extractApplicantFactPathsFromModelsPy(): string[] {
  const source = fs.readFileSync(MODELS_PY, "utf-8");
  const matches = source.matchAll(/alias="([a-z_]+\.[a-z_]+)"/g);
  return Array.from(matches, (m) => m[1]);
}

const ASSESSMENT_ID = "11111111-1111-4111-8111-111111111111";
const COLLECTED_AT = new Date("2026-07-27T00:00:00.000Z");

function mapFacts(facts: OracleFacts) {
  return mapOracleFactsToApplicantFacts(facts, {
    assessmentId: ASSESSMENT_ID,
    collectedAt: COLLECTED_AT,
  });
}

const UNKNOWN_REASONS: UnknownReasonWire[] = [
  "NOT_ASKED",
  "NOT_PROVIDED",
  "UNVERIFIED",
  "CONFLICTING",
  "NOT_APPLICABLE",
];

function assertValidFactValue(value: unknown): void {
  expect(typeof value).toBe("object");
  expect(value).not.toBeNull();
  const v = value as Record<string, unknown>;
  if (v.status === "KNOWN") {
    expect(Object.prototype.hasOwnProperty.call(v, "value")).toBe(true);
    expect(Object.prototype.hasOwnProperty.call(v, "reason")).toBe(false);
  } else if (v.status === "UNKNOWN") {
    expect(UNKNOWN_REASONS).toContain(v.reason);
    expect(Object.prototype.hasOwnProperty.call(v, "value")).toBe(false);
  } else {
    throw new Error(`unexpected status: ${JSON.stringify(v.status)}`);
  }
}

function representativeAnswer(question: OracleQuestion): string {
  if (question.kind === "date") return "2026-08-01";
  if (question.kind === "country-codes") return "US";
  if (question.kind === "status-code") return "C1";
  if (question.kind === "number") {
    return String(question.numberInput?.min ?? 0);
  }
  if (question.kind === "review-gate") return "none";
  const answer = question.options.find(
    (option) =>
      question.decisionMapping.kind !== "FACT" ||
      !question.decisionMapping.unknownValues?.includes(option.key),
  );
  if (!answer) throw new Error(`No representative answer for ${question.id}`);
  return answer.key;
}

describe("mapOracleFactsToApplicantFacts — full contract (acceptance test 1)", () => {
  const backendPaths = extractApplicantFactPathsFromModelsPy();

  it("sanity: the backend contract matches the generated fact count, sponsor.type included", () => {
    expect(backendPaths.length).toBe(APPLICANT_FACT_COUNT);
    expect(backendPaths).toContain("sponsor.type");
    expect(backendPaths).toContain(
      "family.stepchild_marriage_certificate_confirmed",
    );
    expect(backendPaths).toContain(
      "family.stepchild_birth_certificate_confirmed",
    );
    expect(backendPaths).toContain("family.sponsor_permit_basis");
    expect(backendPaths).toContain("immigration.renewal_paid");
  });

  it("emits exactly the backend fact-path keys, sponsor.type included", () => {
    const result = mapFacts({});
    const actualKeys = Object.keys(result.facts).sort();
    expect(actualKeys).toEqual([...backendPaths].sort());
  });

  it("still emits exactly those contract keys on a fully-answered interview (no extra keys sneak in)", () => {
    const result = mapFacts({
      in_indonesia: "yes",
      permit_expiry: "2026-08-01",
      category: "work",
      sponsor_category: "EMPLOYER",
      work_payer: "yes",
      review_gate: "none",
    });
    const actualKeys = Object.keys(result.facts).sort();
    expect(actualKeys).toEqual([...backendPaths].sort());
  });
});

describe("question registry -> wire coverage", () => {
  it("never leaves an answered FACT/REVIEW_ONLY path as NOT_ASKED", () => {
    for (const question of Object.values(QUESTIONS)) {
      if (question.decisionMapping.kind === "HUMAN_CONTEXT") continue;
      const result = mapFacts({
        [question.id]: representativeAnswer(question),
      });
      for (const path of question.decisionMapping.factPaths) {
        const fact = result.facts[path as keyof typeof result.facts];
        expect(fact, `${question.id} -> ${path}`).toBeDefined();
        expect(fact, `${question.id} -> ${path}`).not.toEqual({
          status: "UNKNOWN",
          reason: "NOT_ASKED",
        });
      }
    }
  });

  // Re-stated 2026-09-06 (spec §4 PR-4 + owner ruling decision 6): the flag is
  // raised for an ANSWER the signed vocabulary cannot decide, never for the
  // fact that a question was answered. The pairs that must NOT flag are pinned
  // directly below — guilt and innocence of the same table.

  // 2026-09-06, owner ruling 6. `work_role` sat fifth in the fixed `work`
  // sequence, so it was ALWAYS answered, so this presence-triggered flag
  // was ALWAYS attached — and any disclosed flag is terminal backend-side
  // (`_apply_disclosed_review_flags` rewrites the decision with zero
  // candidates). E23, the one product seq-19 answers cleanly for an
  // employment interview, was therefore never shown to anybody. Measured
  // offline against the signed seq-19 pack, this exact fact set: with the
  // flag `HUMAN_REVIEW_REQUIRED` / 0 candidates, without it
  // `SUPPORTED_CANDIDATES [E23]`.
  it("guilt: a completed work interview attaches NO disclosed review flag", () => {
    expect(
      mapFacts({
        category: "work",
        sponsor_category: "EMPLOYER",
        work_payer: "yes",
        work_indonesia_compensation: "yes",
        work_sponsor_confirmed: "yes",
        stay_days: "365",
        trip_scope: "single",
        review_gate: "none",
      }).disclosed_review_flags,
    ).toEqual([]);
  });

  it("innocence: the other presence-triggered clauses are untouched by that deletion", () => {
    // `business_activity` USED to be pinned here, with the condition that PR-4
    // owns its removal "only AFTER the seq-20 fold compiles the D2
    // local-compensation prohibition — removing it before that is a measured
    // fail-open". That condition is now MET: rule-pack seq-20 was signed
    // (payload_sha256 df02287b…) and activated in production on 2026-09-06,
    // and it carries the EXCLUDE `hf.d2.indonesia-source-compensation`. The
    // prohibition the flag was standing in for is therefore enforced by the
    // signed vocabulary itself, so the pair moves to the must-NOT-flag table
    // below rather than being deleted — the assertion changed sides, it did
    // not disappear. Measured live the same day: `offshore/business` returns
    // NO_SUPPORTED_PATH with `BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED`.
    //
    // `diaspora_connection`/`diaspora_documents` released 2026-09-08 for the
    // SAME reason (measured 2026-09-07: all 15 corpus diaspora walks reach
    // SUPPORTED_CANDIDATES with `disclosed_review_flags=[]`) — moved out of
    // this list to the must-NOT-flag table below, `former_wni` included.
    for (const [id, value] of [["other_purpose", "medical"]] as const) {
      expect(mapFacts({ [id]: value }).disclosed_review_flags).toContain(
        "ACTIVITY_BOUNDARY",
      );
    }
  });

  it.each([
    ["trip_scope", "multiple", "MULTI_PURPOSE_TRIP"],
    ["business_activity", "training", "ACTIVITY_BOUNDARY"],
    ["business_activity", "other", "ACTIVITY_BOUNDARY"],
    ["diaspora_connection", "former_citizen", "ACTIVITY_BOUNDARY"],
    ["diaspora_documents", "passport", "ACTIVITY_BOUNDARY"],
    ["other_purpose", "medical", "ACTIVITY_BOUNDARY"],
  ])(
    "maps an undecidable HUMAN_CONTEXT answer (%s=%s) to a conservative review flag",
    (id, value, flag) => {
      expect(mapFacts({ [id]: value }).disclosed_review_flags).toContain(flag);
    },
  );

  // NARROW-1 (owner ruling SHWEB-20260911, 2026-09-12): `family_sponsor_
  // status_code`/`family_sponsor_permit_basis` USED to be pinned in the
  // "must flag" table above, on the mere presence of either fact — i.e.
  // because the sponsor is foreign, regardless of whether any candidate the
  // pack had proven actually reads it. Measured: `el.c1.tourism-family`
  // (rulepack-prod-020) reads no sponsor fact at all, so that was the
  // OVER-match shape (guard #3) — deleting a verdict the flag cannot affect.
  // The pair moves to the must-NOT-flag table below, replaced by the
  // narrower guilt cases in "AMBIGUOUS_SPONSOR — narrowed to unsure or a
  // sponsor-dependent relation" beneath it.
  it.each([
    ["business_activity", "meetings"],
    ["business_activity", "negotiation"],
    ["business_activity", "conference"],
    ["investment_vehicle", "pt_pma"],
    // Released (PR-D3, D3-1) — `mapPurposes` routes both to SECOND_HOME
    // alone and the Second Home facts the interview already collects for
    // them decide E33 on the pack's own terms. See fact-mapper.ts.
    ["investment_vehicle", "property"],
    ["investment_vehicle", "bank_deposit"],
    ["retirement_basis", "bank_deposit"],
    ["retirement_basis", "passive_income"],
    // Released 2026-09-12 (NARROW-2) — el.e33f.retirement decides SUPPORT
    // off `secondhome.passive_monthly_income_usd`/`family.sponsor_confirmed`
    // alone, never `retirement_basis` itself. See fact-mapper.ts.
    ["retirement_basis", "family_sponsor"],
    // Released (PR-D3, D3-3) — `property` and `undecided` now ask
    // `family_sponsor_confirmed` too (flow.ts), so both are exactly as
    // decidable as `family_sponsor` above, for the identical reason.
    ["retirement_basis", "property"],
    ["retirement_basis", "undecided"],
    // Engine-inert: no rule reads a work role (owner ruling, decision 6).
    // All five options are swept in `activity-boundary.test.ts`.
    ["work_role", "specialist"],
    // Released 2026-09-08 — see the "innocence" test above for the measurement.
    ["diaspora_connection", "former_wni"],
    ["diaspora_connection", "descendant"],
    ["diaspora_connection", "family"],
    ["diaspora_documents", "yes"],
    ["diaspora_documents", "no"],
    // Released 2026-09-12 (NARROW-1) — no relation is set, so there is no
    // pack product this presence can be protecting. See the describe block
    // below for the STEPCHILD (relation-dependent) counter-case.
    ["family_sponsor_status_code", "FOO"],
    // Dropped from the trigger entirely, for every relation: no rule in
    // seq-20 reads `family.sponsor_permit_basis` (HUMAN_CONTEXT only, never
    // wired to a FACT — see `mapFamilySponsorPermitBasis`).
    ["family_sponsor_permit_basis", "EXPERT"],
    // Released (PR-D3, D3-2) — `mapPurposes` routes `yes` to EMPLOYMENT
    // (only `el.e23-employment-support` covers it) and `no` stays OTHER
    // (`el.c6.social` reachable); both are decisive on the pack's own
    // terms. See fact-mapper.ts.
    ["other_paid_activity", "yes"],
    ["other_paid_activity", "no"],
    // Released (D4a, owner ruling SHWEB-20260911) — `mapPurposes` now routes
    // `transit` to the TRANSIT purpose, which `el.a1.tourism`/`el.d1-*`
    // (rulepack-prod-020) decide on. See fact-mapper.ts.
    ["other_purpose", "transit"],
  ])(
    "leaves a decidable answer (%s=%s) unflagged — it must not veto a proven candidate",
    (id, value) => {
      expect(mapFacts({ [id]: value }).disclosed_review_flags).toEqual([]);
    },
  );
});

describe("AMBIGUOUS_SPONSOR — narrowed to unsure or a sponsor-dependent relation (NARROW-1)", () => {
  it("guilt: an unsure family_sponsor_status_code answer holds, for any relation", () => {
    expect(
      mapFacts({
        family_relation: "SPOUSE",
        family_sponsor_status_code: "unsure",
      }).disclosed_review_flags,
    ).toContain("AMBIGUOUS_SPONSOR");
  });

  it("guilt: an unsure family_sponsor_confirmed answer holds, for any relation", () => {
    expect(
      mapFacts({
        family_relation: "OTHER",
        family_sponsor_confirmed: "unsure",
      }).disclosed_review_flags,
    ).toContain("AMBIGUOUS_SPONSOR");
  });

  // D3-4 (PR-D3) had a proxy here: STEPCHILD held on the sponsor's own
  // permit (`family_stepchild_sponsor_permit_confirmed`) being anything
  // other than "yes". REMOVED (owner ruling SHWEB-20260911, 2026-09-13,
  // fresh grader review): no pack requirement for the sponsor's permit
  // exists for E31D (Permenkumham 11/2024 Pasal 33 ayat (2) huruf h names
  // no permit for E31D, unlike its E31E neighbour; Pasal 193 makes E31D's
  // guarantor a WNI, who cannot hold a KITAS/KITAP at all) — this was the
  // same OVER-match shape NARROW-1 cured for SPOUSE/PARENT/CHILD/SIBLING
  // above. The question itself is gone from `QUESTIONS` (tree.ts); these
  // guilt tests become innocence tests — a STEPCHILD relation never holds
  // via this route any more, for any answer.
  it("innocence: STEPCHILD never holds on the sponsor's own permit any more — the D3-4 requirement did not exist", () => {
    expect(
      mapFacts({
        family_relation: "STEPCHILD",
        family_sponsor_status_code: "E23",
      }).disclosed_review_flags,
    ).not.toContain("AMBIGUOUS_SPONSOR");
  });

  it("innocence: no relation holds on a resolved (non-unsure) sponsor status code", () => {
    for (const relation of [
      "SPOUSE",
      "CHILD",
      "PARENT",
      "SIBLING",
      "DEPENDENT",
      "STEPCHILD",
      "OTHER",
    ]) {
      expect(
        mapFacts({
          family_relation: relation,
          family_sponsor_status_code: "E23",
        }).disclosed_review_flags,
      ).not.toContain("AMBIGUOUS_SPONSOR");
    }
  });

  it("innocence: STEPCHILD with an Indonesian sponsor (status code never asked) releases", () => {
    expect(
      mapFacts({
        family_relation: "STEPCHILD",
      }).disclosed_review_flags,
    ).not.toContain("AMBIGUOUS_SPONSOR");
  });

  it("innocence: a resolved family_sponsor_permit_basis never holds, even for STEPCHILD — dropped from the trigger entirely", () => {
    expect(
      mapFacts({
        family_relation: "STEPCHILD",
        family_sponsor_permit_basis: "EXPERT",
      }).disclosed_review_flags,
    ).not.toContain("AMBIGUOUS_SPONSOR");
  });

  /**
   * The door back for the STEPCHILD/E31D sponsor-permit hold this file just
   * removed (owner ruling SHWEB-20260911, 2026-09-13) is THE PACK, not a
   * frontend revert: if a future pack ever adds a rule that reads
   * `family.sponsor_status_code` for an `el.e31d-*` product, the frontend
   * would need a real fact-collection path for it again. Reads the highest-
   * sequence signed production pack on disk (same posture as "AMBIGUOUS_
   * SPONSOR relation proxy tracks the signed pack" below) and fails the
   * moment that happens.
   */
  it("no E31D rule in the signed pack reads family.sponsor_status_code", () => {
    const PACKS_DIR = path.resolve(
      REPO_ROOT,
      "apps/backend-rag/backend/services/visa_engine/contracts/packs",
    );

    function latestProductionPackFile(): string {
      const files = fs
        .readdirSync(PACKS_DIR)
        .filter((name) => /^rulepack-prod-\d+\.source\.json$/.test(name));
      if (files.length === 0) {
        throw new Error(`no production packs found under ${PACKS_DIR}`);
      }
      let best: { file: string; sequence: number } | null = null;
      for (const name of files) {
        const full = path.join(PACKS_DIR, name);
        const payload = JSON.parse(fs.readFileSync(full, "utf-8")) as {
          sequence?: unknown;
        };
        if (typeof payload.sequence !== "number") continue;
        if (best === null || payload.sequence > best.sequence) {
          best = { file: full, sequence: payload.sequence };
        }
      }
      if (best === null) {
        throw new Error(`no pack under ${PACKS_DIR} had a numeric sequence`);
      }
      return best.file;
    }

    function referencesFact(node: unknown, fact: string): boolean {
      if (Array.isArray(node)) {
        return node.some((item) => referencesFact(item, fact));
      }
      if (node === null || typeof node !== "object") return false;
      const record = node as Record<string, unknown>;
      if (record.fact === fact) return true;
      return Object.values(record).some((value) => referencesFact(value, fact));
    }

    const pack = JSON.parse(
      fs.readFileSync(latestProductionPackFile(), "utf-8"),
    ) as {
      rules?: Array<{ rule_id?: unknown; when?: unknown }>;
    };
    const e31dRules = (pack.rules ?? []).filter(
      (rule): rule is { rule_id: string; when?: unknown } =>
        typeof rule.rule_id === "string" && rule.rule_id.startsWith("el.e31d"),
    );
    expect(e31dRules.length).toBeGreaterThan(0);
    for (const rule of e31dRules) {
      expect(
        referencesFact(rule.when, "family.sponsor_status_code"),
        `${rule.rule_id} must not read family.sponsor_status_code`,
      ).toBe(false);
    }
  });

  /**
   * Pins the hardcoded relation set inside `mapDisclosedReviewFlags`
   * (`RELATIONS_WITH_SPONSOR_DEPENDENT_PRODUCT`) against every production
   * pack on disk — not just the active one, same reasoning as
   * `engine-adapter.test.ts`'s "support reasons are sentences" tripwire: a
   * pack is written before it is activated. For each relation named on a
   * `family.relation_to_sponsor eq` rule, this collects every OTHER
   * `family.sponsor_*` fact that relation's rules read, together with that
   * rule's `on_unknown`. A relation counts as sponsor-dependent only when at
   * least one such read has a real effect (`on_unknown` other than
   * `NO_EFFECT`) — `family.sponsor_nationalities` is excluded on purpose,
   * it is the directly-answered, trusted fact that decides whether the
   * self-declared ones get asked at all, not one of the ambiguous facts
   * AMBIGUOUS_SPONSOR exists to guard.
   *
   * Goes RED the moment the pack stops matching the code's belief: STEPCHILD
   * loses its dependency, or a new one appears elsewhere (SPOUSE/PARENT/
   * CHILD/SIBLING/DEPENDENT/OTHER) — either is a signal to revisit
   * `RELATIONS_WITH_SPONSOR_DEPENDENT_PRODUCT` in fact-mapper.ts.
   */
  it("AMBIGUOUS_SPONSOR relation proxy tracks the signed pack", () => {
    const PACKS_DIR = path.resolve(
      REPO_ROOT,
      "apps/backend-rag/backend/services/visa_engine/contracts/packs",
    );

    // Reads only the HIGHEST-`sequence` pack on disk, deliberately NOT every
    // pack file (same posture as `engine-adapter.test.ts`'s
    // `latestProductionPackFile`): the FAMILY relation rules have been
    // reshaped across the pack's history (STEPCHILD/E31D itself only landed
    // 2026-07-24), so globbing every file on disk would resurrect
    // superseded rule shapes as permanent, unfixable "dependencies" no
    // current interview can ever produce.
    function latestProductionPackFile(): string {
      const files = fs
        .readdirSync(PACKS_DIR)
        .filter((name) => /^rulepack-prod-\d+\.source\.json$/.test(name));
      if (files.length === 0) {
        throw new Error(`no production packs found under ${PACKS_DIR}`);
      }
      let best: { file: string; sequence: number } | null = null;
      for (const name of files) {
        const full = path.join(PACKS_DIR, name);
        const payload = JSON.parse(fs.readFileSync(full, "utf-8")) as {
          sequence?: unknown;
        };
        if (typeof payload.sequence !== "number") continue;
        if (best === null || payload.sequence > best.sequence) {
          best = { file: full, sequence: payload.sequence };
        }
      }
      if (best === null) {
        throw new Error(`no pack under ${PACKS_DIR} had a numeric sequence`);
      }
      return best.file;
    }

    const NON_AMBIGUOUS_SPONSOR_FACTS = new Set([
      "family.sponsor_nationalities",
    ]);

    function factsAndRelations(when: unknown): {
      facts: Array<{ fact: string; onUnknown: unknown }>;
      relations: Set<string>;
    } {
      const facts: Array<{ fact: string; onUnknown: unknown }> = [];
      const relations = new Set<string>();
      const walk = (node: unknown): void => {
        if (Array.isArray(node)) {
          node.forEach(walk);
          return;
        }
        if (node === null || typeof node !== "object") return;
        const record = node as Record<string, unknown>;
        if (typeof record.fact === "string") {
          if (
            record.fact === "family.relation_to_sponsor" &&
            record.op === "eq" &&
            typeof record.value === "string"
          ) {
            relations.add(record.value);
          }
          facts.push({ fact: record.fact, onUnknown: undefined });
        }
        for (const value of Object.values(record)) walk(value);
      };
      walk(when);
      return { facts, relations };
    }

    const pack = JSON.parse(
      fs.readFileSync(latestProductionPackFile(), "utf-8"),
    ) as {
      rules?: Array<{ when?: unknown; on_unknown?: unknown }>;
    };
    expect(pack.rules?.length ?? 0).toBeGreaterThan(0);

    const dependentRelations = new Set<string>();
    for (const rule of pack.rules ?? []) {
      const { facts, relations } = factsAndRelations(rule.when);
      if (relations.size === 0) continue;
      const sponsorFacts = facts
        .map((f) => f.fact)
        .filter(
          (fact) =>
            fact.startsWith("family.sponsor_") &&
            !NON_AMBIGUOUS_SPONSOR_FACTS.has(fact),
        );
      if (sponsorFacts.length === 0) continue;
      if (rule.on_unknown === "NO_EFFECT") continue;
      for (const relation of relations) {
        dependentRelations.add(relation);
      }
    }

    expect(dependentRelations).toEqual(new Set(["STEPCHILD"]));
  });
});

describe("mapOracleFactsToApplicantFacts — discriminated-union validity (acceptance test 2)", () => {
  it("every emitted fact is a valid KNOWN(+value)/UNKNOWN(+reason) shape on an empty interview", () => {
    const result = mapFacts({});
    for (const value of Object.values(result.facts)) {
      assertValidFactValue(value);
    }
  });

  it("every emitted fact is a valid KNOWN(+value)/UNKNOWN(+reason) shape on a fully-answered interview", () => {
    const result = mapFacts({
      in_indonesia: "unsure",
      permit_expiry: "unsure",
      category: "remote",
      remote_clients: "mixed",
      remote_income: "above",
      review_gate: "criminal_record,overstay_or_blacklist",
    });
    for (const value of Object.values(result.facts)) {
      assertValidFactValue(value);
    }
  });
});

describe("mapCurrentlyInIndonesia — in_indonesia -> immigration.currently_in_indonesia", () => {
  it("yes -> KNOWN true", () => {
    expect(mapCurrentlyInIndonesia({ in_indonesia: "yes" })).toEqual({
      status: "KNOWN",
      value: true,
    });
  });

  it("no -> KNOWN false", () => {
    expect(mapCurrentlyInIndonesia({ in_indonesia: "no" })).toEqual({
      status: "KNOWN",
      value: false,
    });
  });

  it("unsure -> UNKNOWN UNVERIFIED even when UI navigation is conservative", () => {
    expect(mapCurrentlyInIndonesia({ in_indonesia: "unsure" })).toEqual({
      status: "UNKNOWN",
      reason: "UNVERIFIED",
    });
  });

  it("never asked -> UNKNOWN NOT_ASKED", () => {
    expect(mapCurrentlyInIndonesia({})).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });
});

describe("mapCurrentStatusExpiry — permit_expiry -> immigration.current_status_expiry", () => {
  it("a valid ISO date -> KNOWN with that exact string", () => {
    expect(mapCurrentStatusExpiry({ permit_expiry: "2026-08-01" })).toEqual({
      status: "KNOWN",
      value: "2026-08-01",
    });
  });

  it("unsure -> UNKNOWN UNVERIFIED", () => {
    expect(mapCurrentStatusExpiry({ permit_expiry: "unsure" })).toEqual({
      status: "UNKNOWN",
      reason: "UNVERIFIED",
    });
  });

  it("never asked -> UNKNOWN NOT_ASKED", () => {
    expect(mapCurrentStatusExpiry({})).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });

  it("a calendar-impossible date string -> UNKNOWN NOT_PROVIDED, never sent as KNOWN", () => {
    expect(mapCurrentStatusExpiry({ permit_expiry: "2026-02-30" })).toEqual({
      status: "UNKNOWN",
      reason: "NOT_PROVIDED",
    });
  });
});

describe("renewal_paid -> immigration.renewal_paid (F4, 2026-08-24 owner ruling)", () => {
  it("yes -> KNOWN true", () => {
    expect(
      mapFacts({ renewal_paid: "yes" }).facts["immigration.renewal_paid"],
    ).toEqual({
      status: "KNOWN",
      value: true,
    });
  });

  it("no -> KNOWN false", () => {
    expect(
      mapFacts({ renewal_paid: "no" }).facts["immigration.renewal_paid"],
    ).toEqual({
      status: "KNOWN",
      value: false,
    });
  });

  it('"not sure" -> UNKNOWN UNVERIFIED, never a guessed false', () => {
    const fact = mapFacts({ renewal_paid: "unsure" }).facts[
      "immigration.renewal_paid"
    ];
    expect(fact).toEqual({ status: "UNKNOWN", reason: "UNVERIFIED" });
    expect(fact).not.toEqual({ status: "KNOWN", value: false });
  });

  it("never asked -> UNKNOWN NOT_ASKED", () => {
    expect(mapFacts({}).facts["immigration.renewal_paid"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });
});

describe("mapCurrentStatusCode — the synthesized NO_STAY_PERMIT sentinel (2026-08-24 P0 fix)", () => {
  // mapCurrentStatusCode is not exported (internal to mapOracleFactsToApplicantFacts);
  // reached here through the same `immigration.current_status_code` wire key
  // every other test in this file uses for the exported facts, mapper.ts's
  // own convention.
  it("stay_permit_code answered -> KNOWN with the E-code, unaffected by holds_stay_permit", () => {
    expect(
      mapFacts({
        stay_permit_code: "E28A",
        holds_stay_permit: "yes",
      }).facts["immigration.current_status_code"],
    ).toEqual({ status: "KNOWN", value: "E28A" });
  });

  it("current_status_code answered (onshore 'no' path) -> KNOWN with the real visit-class code, never the sentinel", () => {
    expect(
      mapFacts({
        current_status_code: "C1",
        holds_stay_permit: "no",
      }).facts["immigration.current_status_code"],
    ).toEqual({ status: "KNOWN", value: "C1" });
  });

  it("neither raw field answered, holds_stay_permit='no' (offshore convergence) -> KNOWN NO_STAY_PERMIT, no question asked", () => {
    expect(
      mapFacts({ holds_stay_permit: "no" }).facts[
        "immigration.current_status_code"
      ],
    ).toEqual({ status: "KNOWN", value: "NO_STAY_PERMIT" });
  });

  it("neither raw field answered, holds_stay_permit='yes' -> UNKNOWN NOT_ASKED (still waiting on stay_permit_code)", () => {
    expect(
      mapFacts({ holds_stay_permit: "yes" }).facts[
        "immigration.current_status_code"
      ],
    ).toEqual({ status: "UNKNOWN", reason: "NOT_ASKED" });
  });

  it("nothing answered at all -> UNKNOWN NOT_ASKED", () => {
    expect(mapFacts({}).facts["immigration.current_status_code"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });
});

describe("mapSponsorType — sponsor_category -> sponsor.type", () => {
  it("never asked -> UNKNOWN NOT_ASKED (the pre-existing default value)", () => {
    expect(mapSponsorType({})).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
    expect(mapFacts({}).facts["sponsor.type"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });

  it("unsure -> UNKNOWN UNVERIFIED", () => {
    expect(mapSponsorType({ sponsor_category: "unsure" })).toEqual({
      status: "UNKNOWN",
      reason: "UNVERIFIED",
    });
  });

  it.each([
    "NONE",
    "INDIVIDUAL",
    "EMPLOYER",
    "EDUCATION",
    "INVESTMENT",
    "GOVERNMENT",
  ] as const)("%s -> KNOWN with that exact value", (value) => {
    expect(mapSponsorType({ sponsor_category: value })).toEqual({
      status: "KNOWN",
      value,
    });
  });

  it("is reachable (and answers KNOWN) on every category branch that asks it unconditionally", () => {
    // The categories where the sponsor discriminates for EVERY facts value
    // (design choice, see FIXED_CATEGORY_QUESTIONS/getCategoryQuestionIds in
    // flow.ts): work, remote, study, invest, retirement, family — and, since
    // 2026-09-06, diaspora, which now serves the FAMILY question set
    // verbatim (owner ruling 4) and therefore inherits its
    // `sponsor_category`. `other` is deliberately EXCLUDED from this list
    // (PR-D4d): it asks the question only down its `other_paid_activity ===
    // "yes"` branch — see the dedicated describe block below.
    // `second_home` does NOT ask it at all — not because no rule reads
    // `sponsor.type` (the ACTIVE pack's `hf.e33a/b/c` do, and PR-D4d's
    // pack-vocabulary pin below proves it), but because Zero's ruling 3
    // (2026-09-06) stands: every extra question here carries `notSure: {
    // mode: "human-review" }`, so a ceremonial one could only add review
    // volume for a fact measured (PR-D4d) to change no `second_home`
    // walk's outcome on the pack in force today. Derived from the flow
    // graph itself, not hardcoded, so this test breaks if a branch's
    // question list changes without this describe block being revisited.
    const categoriesAsking = CATEGORY_KEYS.filter(
      (category) =>
        category !== "other" &&
        getCategoryQuestionIds({ category }).includes("sponsor_category"),
    );
    expect([...categoriesAsking].sort()).toEqual(
      [
        "diaspora",
        "family",
        "invest",
        "remote",
        "retirement",
        "study",
        "work",
      ].sort(),
    );
    for (const category of categoriesAsking) {
      const result = mapFacts({ category, sponsor_category: "EMPLOYER" });
      expect(result.facts["sponsor.type"]).toEqual({
        status: "KNOWN",
        value: "EMPLOYER",
      });
    }
  });

  it("is never asked on categories where the sponsor never discriminates", () => {
    for (const category of ["tourism", "business", "second_home"] as const) {
      expect(getCategoryQuestionIds({ category })).not.toContain(
        "sponsor_category",
      );
    }
  });

  it("`other`: asked only down the other_paid_activity=yes branch (PR-D4d)", () => {
    // `yes` is EMPLOYMENT purpose (D3-2) and is the second reachable path
    // (besides `work`) into seq-21's sponsor.type-gated rules
    // (el.e33a/b.government-*, el.e23u.diplomatic-household,
    // el.e23v.trade-office). `no`/`unsure` stay OTHER purpose, which none
    // of those rules cover, so they must not gain the question.
    expect(
      getCategoryQuestionIds({
        category: "other",
        other_paid_activity: "yes",
      }),
    ).toContain("sponsor_category");
    for (const other_paid_activity of ["no", "unsure"] as const) {
      expect(
        getCategoryQuestionIds({ category: "other", other_paid_activity }),
      ).not.toContain("sponsor_category");
    }
    expect(getCategoryQuestionIds({ category: "other" })).not.toContain(
      "sponsor_category",
    );

    const result = mapFacts({
      category: "other",
      other_paid_activity: "yes",
      sponsor_category: "GOVERNMENT",
    });
    expect(result.facts["sponsor.type"]).toEqual({
      status: "KNOWN",
      value: "GOVERNMENT",
    });
  });
});

describe("sponsor.type vocabulary — pack ⊆ SPONSOR_TYPES, one direction only (PR-D4d)", () => {
  const PACKS_DIR = path.resolve(
    REPO_ROOT,
    "apps/backend-rag/backend/services/visa_engine/contracts/packs",
  );

  /**
   * Every production pack on disk, not just the highest sequence — same
   * posture as engine-adapter.test.ts's `productionPackFiles()`: "a pack is
   * written before it is activated", so a DRAFT that names a sponsor.type
   * value the UI cannot produce must fail here the moment it lands, not
   * only once signed. Reads `.source.json` (every sequence ever authored
   * carries one; the matching `.signed.json`, when it exists, nests the
   * identical rule list one level deeper under `payload` and is not read
   * separately here for that reason).
   */
  function productionPackFiles(): string[] {
    const files = fs
      .readdirSync(PACKS_DIR)
      .filter((name) => /^rulepack-prod-\d+\.source\.json$/.test(name))
      .map((name) => path.join(PACKS_DIR, name));
    if (files.length === 0) {
      throw new Error(`no production packs found under ${PACKS_DIR}`);
    }
    return files;
  }

  function sponsorTypeValuesInPack(file: string): string[] {
    const values = new Set<string>();
    const walk = (node: unknown): void => {
      if (Array.isArray(node)) {
        node.forEach(walk);
        return;
      }
      if (node === null || typeof node !== "object") return;
      const record = node as Record<string, unknown>;
      if (record.fact === "sponsor.type") {
        if (typeof record.value === "string") values.add(record.value);
        if (Array.isArray(record.values)) {
          for (const v of record.values) {
            if (typeof v === "string") values.add(v);
          }
        }
      }
      Object.values(record).forEach(walk);
    };
    walk(JSON.parse(fs.readFileSync(file, "utf-8")));
    return [...values];
  }

  function allPackSponsorTypeValues(): Set<string> {
    const values = new Set<string>();
    for (const file of productionPackFiles()) {
      for (const value of sponsorTypeValuesInPack(file)) values.add(value);
    }
    return values;
  }

  /**
   * ONE direction only, deliberately not a bidirectional deep-equal (D4a's
   * technique elsewhere in this file) — that pin would be red TODAY:
   * `EMPLOYER`/`INVESTMENT` are declared UI-only values no pack rule
   * compares against, and being unread is not itself a defect. The failure
   * THIS pin guards against is the other direction: a pack value the UI has
   * no way to ever send, which makes that rule unreachable through the
   * funnel however the pack itself reads — the exact class of gap this PR
   * closes for the `other` tile.
   */
  it("every sponsor.type value any production pack compares against is one SPONSOR_TYPES can send", () => {
    const packValues = allPackSponsorTypeValues();
    // Guard the guard: a glob or walker that silently matched nothing would
    // make the assertion below vacuously true.
    expect(packValues.size).toBeGreaterThan(0);
    const unreachable = [...packValues].filter(
      (value) => !(SPONSOR_TYPES as readonly string[]).includes(value),
    );
    expect(unreachable).toEqual([]);
  });

  it("EMPLOYER: UI-only — mapSponsorType still sends it KNOWN, but no production-pack rule compares against it", () => {
    expect(mapSponsorType({ sponsor_category: "EMPLOYER" })).toEqual({
      status: "KNOWN",
      value: "EMPLOYER",
    });
    expect(allPackSponsorTypeValues().has("EMPLOYER")).toBe(false);
  });

  it("INVESTMENT: UI-only — mapSponsorType still sends it KNOWN, but no production-pack rule compares against it", () => {
    expect(mapSponsorType({ sponsor_category: "INVESTMENT" })).toEqual({
      status: "KNOWN",
      value: "INVESTMENT",
    });
    expect(allPackSponsorTypeValues().has("INVESTMENT")).toBe(false);
  });
});

describe("investment.investment_amount_usd — PR-D4c-2, currency-bound amount on the merit/family/undecided branches only", () => {
  it("stays UNKNOWN(NOT_ASKED) when the branch never asks it — pt_pma is untouched (E28A innocence)", () => {
    const wire = mapFacts({
      category: "invest",
      investment_vehicle: "pt_pma",
    }).facts;
    expect(wire["investment.investment_amount_usd"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });

  it("stays UNKNOWN(NOT_ASKED) on the property/bank_deposit Second Home routes too", () => {
    for (const vehicle of ["property", "bank_deposit"] as const) {
      const wire = mapFacts({
        category: "invest",
        investment_vehicle: vehicle,
      }).facts;
      expect(wire["investment.investment_amount_usd"]).toEqual({
        status: "UNKNOWN",
        reason: "NOT_ASKED",
      });
    }
  });

  it("resolves KNOWN from investment_amount_usd when usd is the chosen currency", () => {
    const wire = mapFacts({
      category: "invest",
      investment_vehicle: "merit",
      investment_currency: "usd",
      investment_amount_usd: "250000",
    }).facts;
    expect(wire["investment.investment_amount_usd"]).toEqual({
      status: "KNOWN",
      value: 250000,
    });
    // No conversion: the sibling IDR fact is never touched by a USD answer.
    expect(wire["investment.investment_capital_idr"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });

  it("resolves KNOWN from the EXISTING investment_capital_idr question when idr is chosen — reused, not duplicated", () => {
    const wire = mapFacts({
      category: "invest",
      investment_vehicle: "family",
      investment_currency: "idr",
      investment_capital_idr: "5000000000",
    }).facts;
    expect(wire["investment.investment_capital_idr"]).toEqual({
      status: "KNOWN",
      value: 5_000_000_000,
    });
    // No conversion: the sibling USD fact is never touched by an IDR answer.
    expect(wire["investment.investment_amount_usd"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });

  it("emits NEITHER amount fact on the 'I can't say yet' answer — the honest UNKNOWN state", () => {
    const wire = mapFacts({
      category: "invest",
      investment_vehicle: "undecided",
      investment_currency: "still_unsure",
    }).facts;
    expect(wire["investment.investment_amount_usd"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
    expect(wire["investment.investment_capital_idr"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });

  it("the 'I can't say yet' answer costs zero review holds — its value is never the literal \"unsure\"", () => {
    // fact-mapper.ts's NOT_CERTAIN scan (`mapDisclosedReviewFlags`) is an
    // EXACT-equality `Object.values(facts).includes("unsure")` — proven
    // directly here: `"still_unsure" !== "unsure"`, so it cannot match.
    expect(
      mapDisclosedReviewFlags({
        category: "invest",
        investment_vehicle: "undecided",
        investment_currency: "still_unsure",
      }),
    ).not.toContain("NOT_CERTAIN");
  });
});

describe("investment.investment_amount_usd vocabulary — one-directional pin (PR-D4c-2, models PR-D4d's sponsor.type pin)", () => {
  const PACKS_DIR = path.resolve(
    REPO_ROOT,
    "apps/backend-rag/backend/services/visa_engine/contracts/packs",
  );

  function productionPackFiles(): string[] {
    const files = fs
      .readdirSync(PACKS_DIR)
      .filter((name) => /^rulepack-prod-\d+\.source\.json$/.test(name))
      .map((name) => path.join(PACKS_DIR, name));
    if (files.length === 0) {
      throw new Error(`no production packs found under ${PACKS_DIR}`);
    }
    return files;
  }

  /** Every numeric comparator value any production pack on disk compares
   * `investment.investment_amount_usd` against, whichever operator a future
   * seq-22 rule uses (`gte`/`lte`/`gt`/`lt`/`eq`) — all of them carry the
   * threshold as a bare `value` beside the `fact` key. */
  function investmentAmountUsdThresholds(file: string): number[] {
    const values: number[] = [];
    const walk = (node: unknown): void => {
      if (Array.isArray(node)) {
        node.forEach(walk);
        return;
      }
      if (node === null || typeof node !== "object") return;
      const record = node as Record<string, unknown>;
      if (
        record.fact === "investment.investment_amount_usd" &&
        typeof record.value === "number"
      ) {
        values.push(record.value);
      }
      Object.values(record).forEach(walk);
    };
    walk(JSON.parse(fs.readFileSync(file, "utf-8")));
    return values;
  }

  /**
   * ONE direction only, same posture as PR-D4d's sponsor.type pin above: a
   * future PACK VALUE the UI has no way to ever send is what makes a rule
   * unreachable through the funnel, however the pack itself reads — that is
   * the failure this guards against. A bidirectional deep-equal would be RED
   * TODAY, because no seq-22 rule reads this fact in any pack on disk yet
   * (the activation dependency stated in this PR's body) — the pack-side set
   * is empty by design, not by omission.
   */
  it("every investment.investment_amount_usd threshold any production pack compares against is inside the UI's own numberInput bounds", () => {
    const { min, max, step } = QUESTIONS.investment_amount_usd.numberInput!;
    const thresholds = productionPackFiles().flatMap((file) =>
      investmentAmountUsdThresholds(file),
    );
    const unreachable = thresholds.filter(
      (value) =>
        !Number.isInteger(value) ||
        value < min ||
        value > max ||
        (value - min) % step !== 0,
    );
    expect(unreachable).toEqual([]);
  });
});

describe("mapPurposes — category -> intent.purposes", () => {
  it("maps every tile with a clean VisaPurpose match", () => {
    for (const [tile, purpose] of Object.entries(CATEGORY_TO_PURPOSE)) {
      expect(mapPurposes({ category: tile })).toEqual({
        status: "KNOWN",
        value: [purpose],
      });
    }
  });

  // Owner ruling 4 (2026-09-06) reversed the previous "diaspora is
  // represented only by request_category" design. It was not a
  // simplification: `mapPurposes` returned UNKNOWN(NOT_APPLICABLE), so
  // every diaspora interview dead-ended in NEEDS_INPUT on `intent.purposes`
  // — a fact the interview HAD collected — no matter what else the
  // applicant answered.
  it("diaspora maps to FAMILY, the purpose of the products it actually reaches (E31C/E31F)", () => {
    expect(mapPurposes({ category: "diaspora" })).toEqual({
      status: "KNOWN",
      value: ["FAMILY"],
    });
  });

  // Owner ruling 3: SECOND_HOME must be the ONLY declared purpose. The
  // pack's `hit_policy.eligibility = COVER_ALL_DECLARED_PURPOSES` drops
  // E33 the moment a second purpose rides along, so a second_home tile
  // that also emitted RETIREMENT would be a silent no-path.
  it("second_home emits SECOND_HOME alone, never joined to RETIREMENT", () => {
    expect(mapPurposes({ category: "second_home" })).toEqual({
      status: "KNOWN",
      value: ["SECOND_HOME"],
    });
  });

  it("every one of the CATEGORY_KEYS tiles now yields a KNOWN purpose", () => {
    for (const tile of CATEGORY_KEYS) {
      const result = mapPurposes({ category: tile });
      assertValidFactValue(result);
      expect(result.status, `${tile} must map to a purpose`).toBe("KNOWN");
    }
  });

  it("guilt: a category outside CATEGORY_KEYS is UNKNOWN, never guessed into a purpose", () => {
    expect(mapPurposes({ category: "not-a-tile" })).toEqual({
      status: "UNKNOWN",
      reason: "NOT_APPLICABLE",
    });
  });

  it("category never asked -> UNKNOWN NOT_ASKED", () => {
    expect(mapPurposes({})).toEqual({ status: "UNKNOWN", reason: "NOT_ASKED" });
  });
});

describe("mapEmployerIsIndonesianEntity — work_payer -> work.employer_is_indonesian_entity", () => {
  it("yes -> KNOWN true", () => {
    expect(mapEmployerIsIndonesianEntity({ work_payer: "yes" })).toEqual({
      status: "KNOWN",
      value: true,
    });
  });

  it("no -> KNOWN false", () => {
    expect(mapEmployerIsIndonesianEntity({ work_payer: "no" })).toEqual({
      status: "KNOWN",
      value: false,
    });
  });

  it("unsure -> UNKNOWN UNVERIFIED", () => {
    expect(mapEmployerIsIndonesianEntity({ work_payer: "unsure" })).toEqual({
      status: "UNKNOWN",
      reason: "UNVERIFIED",
    });
  });

  it("never asked (e.g. non-work category) -> UNKNOWN NOT_ASKED", () => {
    expect(mapEmployerIsIndonesianEntity({})).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });
});

describe("mapRemoteClientsDerived — remote_clients -> work.serves_indonesian_clients only", () => {
  it("foreign -> KNOWN false", () => {
    expect(mapRemoteClientsDerived({ remote_clients: "foreign" })).toEqual({
      servesIndonesianClients: { status: "KNOWN", value: false },
    });
  });

  it("indonesian -> KNOWN true", () => {
    expect(mapRemoteClientsDerived({ remote_clients: "indonesian" })).toEqual({
      servesIndonesianClients: { status: "KNOWN", value: true },
    });
  });

  it("mixed -> KNOWN true", () => {
    expect(mapRemoteClientsDerived({ remote_clients: "mixed" })).toEqual({
      servesIndonesianClients: { status: "KNOWN", value: true },
    });
  });

  it("unsure -> UNKNOWN UNVERIFIED", () => {
    expect(mapRemoteClientsDerived({ remote_clients: "unsure" })).toEqual({
      servesIndonesianClients: { status: "UNKNOWN", reason: "UNVERIFIED" },
    });
  });

  it("never asked -> UNKNOWN NOT_ASKED", () => {
    expect(mapRemoteClientsDerived({})).toEqual({
      servesIndonesianClients: { status: "UNKNOWN", reason: "NOT_ASKED" },
    });
  });

  it("never infers compensation source from client location", () => {
    for (const remoteClients of ["foreign", "indonesian", "mixed"]) {
      const mapped = mapFacts({ remote_clients: remoteClients });
      expect(mapped.facts["work.indonesia_source_compensation"]).toEqual({
        status: "UNKNOWN",
        reason: "NOT_ASKED",
      });
    }
  });
});

describe("mapStayDays — exact stay_days -> intent.stay_days", () => {
  it("preserves an exact canonical whole-number answer", () => {
    expect(mapStayDays({ stay_days: "31" })).toEqual({
      status: "KNOWN",
      value: 31,
    });
  });

  it.each(["short", "medium", "extended"])(
    "never converts legacy bucket %s to an invented day count",
    (bucket) => {
      expect(mapStayDays({ tourism_duration: bucket })).toEqual({
        status: "UNKNOWN",
        reason: "NOT_ASKED",
      });
    },
  );

  it.each(["0", "0001", "1.5", "36501", "-1", "not-a-number"])(
    "rejects non-canonical or out-of-range input %s",
    (stayDays) => {
      expect(mapStayDays({ stay_days: stayDays })).toEqual({
        status: "UNKNOWN",
        reason: "NOT_PROVIDED",
      });
    },
  );

  it("accepts the sanity-range boundaries", () => {
    expect(mapStayDays({ stay_days: "1" })).toEqual({
      status: "KNOWN",
      value: 1,
    });
    expect(mapStayDays({ stay_days: "36500" })).toEqual({
      status: "KNOWN",
      value: 36_500,
    });
  });

  it("unsure -> UNKNOWN UNVERIFIED", () => {
    expect(mapStayDays({ stay_days: "unsure" })).toEqual({
      status: "UNKNOWN",
      reason: "UNVERIFIED",
    });
  });

  it("never asked -> UNKNOWN NOT_ASKED", () => {
    expect(mapStayDays({})).toEqual({ status: "UNKNOWN", reason: "NOT_ASKED" });
  });
});

describe("mapViolationHistory — review_gate -> immigration.violation_history", () => {
  it('"none" -> KNOWN empty tuple (asked, zero violations)', () => {
    expect(mapViolationHistory({ review_gate: "none" })).toEqual({
      status: "KNOWN",
      value: [],
    });
  });

  it('legacy "overstay_or_blacklist" -> UNKNOWN CONFLICTING, never a guessed enum', () => {
    expect(
      mapViolationHistory({ review_gate: "overstay_or_blacklist" }),
    ).toEqual({
      status: "UNKNOWN",
      reason: "CONFLICTING",
    });
  });

  it("maps split overstay and blacklist disclosures exactly", () => {
    expect(mapViolationHistory({ review_gate: "overstay" })).toEqual({
      status: "KNOWN",
      value: ["OVERSTAY"],
    });
    expect(mapViolationHistory({ review_gate: "blacklist,overstay" })).toEqual({
      status: "KNOWN",
      value: ["OVERSTAY", "BLACKLIST"],
    });
  });

  it("a UI-only flag never becomes a KNOWN empty violation history", () => {
    expect(mapViolationHistory({ review_gate: "criminal_record" })).toEqual({
      status: "UNKNOWN",
      reason: "UNVERIFIED",
    });
  });

  it('"not_certain" remains UNKNOWN UNVERIFIED', () => {
    expect(mapViolationHistory({ review_gate: "not_certain" })).toEqual({
      status: "UNKNOWN",
      reason: "UNVERIFIED",
    });
  });

  it('rejects an impossible "none" plus flag combination as CONFLICTING', () => {
    expect(mapViolationHistory({ review_gate: "none,overstay" })).toEqual({
      status: "UNKNOWN",
      reason: "CONFLICTING",
    });
  });

  it("never asked -> UNKNOWN NOT_ASKED", () => {
    expect(mapViolationHistory({})).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });
});

describe("mapDisclosedReviewFlags — monotone abstention metadata", () => {
  it("maps UI-only disclosures to the closed backend vocabulary", () => {
    expect(
      mapDisclosedReviewFlags({
        review_gate:
          "prior_refusal,criminal_record,pep_or_sanctions,health_flag,not_certain",
      }),
    ).toEqual([
      "CRIMINAL_RECORD",
      "HEALTH_CONCERN",
      "NOT_CERTAIN",
      "PEP_OR_SANCTIONS",
      "PRIOR_VISA_REFUSAL",
    ]);
  });

  it("does not turn legal violation values into disclosed review flags", () => {
    expect(
      mapDisclosedReviewFlags({ review_gate: "blacklist,overstay" }),
    ).toEqual([]);
  });

  it("keeps the backend-derived conflicting-immigration flag outside the client mapper", () => {
    expect(
      mapDisclosedReviewFlags({
        in_indonesia: "no",
        overstay_days: "5",
        review_gate: "immigration_investigation",
      }),
    ).toEqual([]);
    expect(
      mapViolationHistory({ review_gate: "immigration_investigation" }),
    ).toEqual({
      status: "KNOWN",
      value: ["IMMIGRATION_INVESTIGATION"],
    });
  });

  // Released (PR-D3, D3-3): `property` now asks `family_sponsor_confirmed`
  // too (flow.ts), so the bare `retirement_basis` answer alone no longer
  // holds — see the ACTIVITY_BOUNDARY guilt/innocence table above.
  it("releases a bare retirement property context — the basis alone no longer holds", () => {
    expect(mapDisclosedReviewFlags({ retirement_basis: "property" })).toEqual(
      [],
    );
  });
});

describe("family sponsor status — closed catalogue, trusted only when confirmed (D4a)", () => {
  // Guilt (D4a): a value outside the pack-derived 29-code catalogue must
  // NEVER reach the wire as KNOWN — this is mechanism 1 from
  // `research/visa/doctrine-factory/e5/inc6-pack-edits/
  // HELD-fix4-sponsor-status-2026-08-23.json` (a KNOWN value the pack's
  // `op:"in"` cannot match evaluates the rule silently FALSE, with no
  // reason code at all). "NONE" is the exact sentinel that HELD note's
  // corpus observed for this fact; "FOO" pins the general out-of-catalogue
  // case. Both must resolve UNKNOWN, never KNOWN, and neither is `unsure`
  // so AMBIGUOUS_SPONSOR must not fire either (no `family_relation` is set
  // here — see "AMBIGUOUS_SPONSOR — narrowed…" for the relation-dependent
  // case).
  it.each(["FOO", "NONE"])(
    "guilt: a sponsor status outside the 29-code catalogue (%s) never reaches KNOWN",
    (value) => {
      const result = mapFacts({
        family_sponsor_confirmed: "yes",
        family_sponsor_status_code: value,
      });
      expect(result.facts["family.sponsor_status_code"]).toEqual({
        status: "UNKNOWN",
        reason: "NOT_PROVIDED",
      });
      expect(result.disclosed_review_flags).not.toContain("AMBIGUOUS_SPONSOR");
    },
  );

  // Innocence (D4a): a real catalogue code, once the sponsor is confirmed,
  // now resolves KNOWN — this is the fix itself. Verified against the
  // signed pack (`rulepack-prod-020.source.json`): every one of the 9
  // `family.sponsor_status_code` rules already reads this exact 29-code
  // set via `op:"in"`, so a KNOWN member of it can never be a value the
  // pack cannot also accept. See `mapFamilySponsorStatus` (fact-mapper.ts).
  it("innocence: a catalogue code resolves KNOWN once the sponsor is confirmed", () => {
    const result = mapFacts({
      family_sponsor_confirmed: "yes",
      family_sponsor_status_code: "E23",
    });
    expect(result.facts["family.sponsor_status_code"]).toEqual({
      status: "KNOWN",
      value: "E23",
    });
  });

  it("stays UNVERIFIED on the explicit 'I don't know' answer, never a guessed KNOWN", () => {
    const result = mapFacts({
      family_sponsor_confirmed: "yes",
      family_sponsor_status_code: "unsure",
    });
    expect(result.facts["family.sponsor_status_code"]).toEqual({
      status: "UNKNOWN",
      reason: "UNVERIFIED",
    });
  });

  // 2026-08-23: `family.sponsor_permit_basis` shipped in PR #4650 wired to
  // `enumFact()` directly — a self-declared choice resolved straight to
  // KNOWN, missing the parallel to the sibling test immediately above.
  // Corrected to mirror it exactly: collected, flagged, never trusted.
  it("never turns a self-declared permit-basis category into a KNOWN signed fact", () => {
    const result = mapFacts({
      family_sponsor_confirmed: "yes",
      family_sponsor_permit_basis: "EXPERT",
    });
    expect(result.facts["family.sponsor_permit_basis"]).toEqual({
      status: "UNKNOWN",
      reason: "UNVERIFIED",
    });
    // NARROW-1 (2026-09-12): dropped from the trigger entirely — no rule in
    // seq-20 reads `family.sponsor_permit_basis` at all.
    expect(result.disclosed_review_flags).not.toContain("AMBIGUOUS_SPONSOR");
  });

  it("resolves NOT_APPLICABLE for both sponsor facts when no sponsor is confirmed", () => {
    const result = mapFacts({
      family_sponsor_confirmed: "no",
      family_sponsor_status_code: "E28B",
      family_sponsor_permit_basis: "EXPERT",
    });
    expect(result.facts["family.sponsor_status_code"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_APPLICABLE",
    });
    expect(result.facts["family.sponsor_permit_basis"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_APPLICABLE",
    });
  });

  it("resolves NOT_ASKED for both sponsor facts on an empty interview", () => {
    const result = mapFacts({});
    expect(result.facts["family.sponsor_status_code"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
    expect(result.facts["family.sponsor_permit_basis"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });
});

describe("sponsor status code catalogue — derived pin against the signed pack (D4a)", () => {
  /**
   * The 29-code catalogue backing `family_sponsor_status_code`'s (and
   * `stay_permit_code`'s) SELECT — `tree.ts`'s `STAY_PERMIT_CODES` — is not
   * derived from the pack at Next.js build time: this app has no existing
   * build step that reads `apps/backend-rag`'s contracts, and standing one
   * up for a single literal array was judged more invasive and riskier
   * than the fallback below, argued in full in the PR body. This test IS
   * that fallback — a BIDIRECTIONAL pin, re-derived from the highest-
   * sequence signed production pack on disk every run, that fails on an
   * extra code as well as a missing one — same posture as "AMBIGUOUS_
   * SPONSOR relation proxy tracks the signed pack" above and
   * `engine-adapter.test.ts`'s `latestProductionPackFile`.
   */
  it("STAY_PERMIT_CODES matches every family.sponsor_status_code rule's op:in set, exactly", () => {
    const PACKS_DIR = path.resolve(
      REPO_ROOT,
      "apps/backend-rag/backend/services/visa_engine/contracts/packs",
    );

    function latestProductionPackFile(): string {
      const files = fs
        .readdirSync(PACKS_DIR)
        .filter((name) => /^rulepack-prod-\d+\.source\.json$/.test(name));
      if (files.length === 0) {
        throw new Error(`no production packs found under ${PACKS_DIR}`);
      }
      let best: { file: string; sequence: number } | null = null;
      for (const name of files) {
        const full = path.join(PACKS_DIR, name);
        const payload = JSON.parse(fs.readFileSync(full, "utf-8")) as {
          sequence?: unknown;
        };
        if (typeof payload.sequence !== "number") continue;
        if (best === null || payload.sequence > best.sequence) {
          best = { file: full, sequence: payload.sequence };
        }
      }
      if (best === null) {
        throw new Error(`no pack under ${PACKS_DIR} had a numeric sequence`);
      }
      return best.file;
    }

    function collectSponsorStatusInSets(node: unknown, sets: string[][]): void {
      if (Array.isArray(node)) {
        for (const item of node) collectSponsorStatusInSets(item, sets);
        return;
      }
      if (node === null || typeof node !== "object") return;
      const record = node as Record<string, unknown>;
      if (
        record.fact === "family.sponsor_status_code" &&
        record.op === "in" &&
        Array.isArray(record.values)
      ) {
        sets.push([...(record.values as string[])].sort());
      }
      for (const value of Object.values(record)) {
        collectSponsorStatusInSets(value, sets);
      }
    }

    const pack = JSON.parse(
      fs.readFileSync(latestProductionPackFile(), "utf-8"),
    ) as { rules?: Array<{ when?: unknown }> };
    expect(pack.rules?.length ?? 0).toBeGreaterThan(0);

    const sets: string[][] = [];
    for (const rule of pack.rules ?? []) {
      collectSponsorStatusInSets(rule.when, sets);
    }

    // Guilt on absence: if the pack ever stops naming this fact via
    // `op:in`, this must fail loudly rather than pass vacuously.
    expect(sets.length).toBeGreaterThan(0);

    // Bidirectional: every rule's own `in` set must equal the frontend's
    // catalogue exactly — an extra pack code this UI doesn't offer, or a
    // frontend option the pack doesn't accept, both fail this assertion.
    const expected = [...STAY_PERMIT_CODES].sort();
    for (const set of sets) {
      expect(set).toEqual(expected);
    }
  });
});

describe("remote_income — a dead question id, never invented", () => {
  it("does not invent a FactPath, and no longer holds on a question tree.ts does not have", () => {
    // One of the 2 dead legacy nodes (pinned absent by `tree.test.ts`), so its
    // ACTIVITY_BOUNDARY clause was unreachable code, not a live guard.
    const base: OracleFacts = { category: "remote", remote_clients: "foreign" };
    const withIncome: OracleFacts = { ...base, remote_income: "above" };
    const before = mapFacts(base);
    const after = mapFacts(withIncome);
    expect(after.facts).toEqual(before.facts);
    expect(before.disclosed_review_flags).toEqual([]);
    expect(after.disclosed_review_flags).toEqual([]);
  });

  it("is never one of the 40 emitted keys", () => {
    const result = mapFacts({ remote_income: "above" });
    for (const key of Object.keys(result.facts)) {
      expect(key).not.toContain("remote_income");
      expect(key).not.toBe("intent.remote_income");
    }
  });
});

describe("mapOracleFactsToApplicantFacts — envelope shape (acceptance test 4)", () => {
  it("schema_version is the literal 1.0.0", () => {
    const result = mapFacts({});
    expect(result.schema_version).toBe("1.0.0");
    expect(SCHEMA_VERSION).toBe("1.0.0");
  });

  it("assessment_id round-trips whatever the caller (shadow-client.ts) generated", () => {
    const id = "9c858901-8a57-4791-81fe-4c455b099bc9";
    const result = mapOracleFactsToApplicantFacts(
      {},
      { assessmentId: id, collectedAt: COLLECTED_AT },
    );
    expect(result.assessment_id).toBe(id);
    expect(result.assessment_id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );
  });

  it("collected_at ends in Z, never +00:00, and matches Date#toISOString()", () => {
    const result = mapFacts({});
    expect(result.collected_at.endsWith("Z")).toBe(true);
    expect(result.collected_at).not.toContain("+00:00");
    expect(result.collected_at).toBe(COLLECTED_AT.toISOString());
  });

  it("includes sorted conservative review disclosures outside engine facts", () => {
    const result = mapFacts({
      review_gate: "prior_refusal,criminal_record",
    });
    expect(result.disclosed_review_flags).toEqual([
      "CRIMINAL_RECORD",
      "PRIOR_VISA_REFUSAL",
    ]);
  });
});

/**
 * `flow.ts` now refuses to record a self-contradictory
 * wants_onshore_conversion/application_channel pair before it is ever
 * handed to this mapper (see `channelConflictsWithOnshoreIntent`). These
 * tests are the innocence half of that fix, verified at the wire: this
 * mapper itself is UNCHANGED — a coherent pair, or "unsure" on either
 * side, arrives byte-unchanged (no derivation, no coercion), exactly as
 * it did before the guard existed.
 */
describe("process.wants_onshore_conversion / process.application_channel — arrive byte-unchanged (2026-08-23)", () => {
  it.each([
    ["no", "OFFSHORE"],
    ["yes", "ONSHORE_CONVERSION"],
    ["yes", "STATUS_BRIDGING"],
  ] as const)(
    "wants_onshore_conversion=%s + application_channel=%s reach the wire exactly as answered",
    (wants, channel) => {
      const result = mapFacts({
        wants_onshore_conversion: wants,
        application_channel: channel,
      });
      expect(result.facts["process.wants_onshore_conversion"]).toEqual({
        status: "KNOWN",
        value: wants === "yes",
      });
      expect(result.facts["process.application_channel"]).toEqual({
        status: "KNOWN",
        value: channel,
      });
    },
  );

  it('"unsure" on wants_onshore_conversion never becomes CONFLICTING, and does not touch application_channel', () => {
    const result = mapFacts({
      wants_onshore_conversion: "unsure",
      application_channel: "ONSHORE_CONVERSION",
    });
    expect(result.facts["process.wants_onshore_conversion"]).toEqual({
      status: "UNKNOWN",
      reason: "UNVERIFIED",
    });
    expect(result.facts["process.application_channel"]).toEqual({
      status: "KNOWN",
      value: "ONSHORE_CONVERSION",
    });
  });

  it('"unsure" on application_channel never becomes CONFLICTING, and does not touch wants_onshore_conversion', () => {
    const result = mapFacts({
      wants_onshore_conversion: "no",
      application_channel: "unsure",
    });
    expect(result.facts["process.wants_onshore_conversion"]).toEqual({
      status: "KNOWN",
      value: false,
    });
    expect(result.facts["process.application_channel"]).toEqual({
      status: "UNKNOWN",
      reason: "UNVERIFIED",
    });
  });

  it("neither fact ever emits CONFLICTING — this mapper has no cross-question check to remove", () => {
    // Documents the design choice in the PR: the contradiction is caught
    // upstream (flow.ts refuses the ANSWER), so this mapper — unlike
    // pairedBooleanFact's same-FactPath merges — never needs to know the
    // two questions are related at all.
    for (const wants of ["yes", "no", "unsure", undefined]) {
      for (const channel of [
        "OFFSHORE",
        "ONSHORE_CONVERSION",
        "STATUS_BRIDGING",
        "unsure",
        undefined,
      ]) {
        const result = mapFacts({
          ...(wants !== undefined ? { wants_onshore_conversion: wants } : {}),
          ...(channel !== undefined ? { application_channel: channel } : {}),
        });
        expect(result.facts["process.wants_onshore_conversion"]).not.toEqual(
          expect.objectContaining({ reason: "CONFLICTING" }),
        );
        expect(result.facts["process.application_channel"]).not.toEqual(
          expect.objectContaining({ reason: "CONFLICTING" }),
        );
      }
    }
  });
});

describe("mapOracleFactsToApplicantFacts — determinism", () => {
  it("identical facts + options always produce an identical (deep-equal) result", () => {
    const facts: OracleFacts = {
      in_indonesia: "yes",
      permit_expiry: "2026-08-01",
      category: "work",
      work_payer: "no",
      review_gate: "overstay_or_blacklist",
    };
    expect(mapFacts(facts)).toEqual(mapFacts({ ...facts }));
  });

  it("binds disclosed review flags even when the 40 facts are identical", () => {
    const baseFacts: OracleFacts = {
      category: "tourism",
      stay_days: "30",
      review_gate: "pep_or_sanctions",
    };
    const base = mapFacts(baseFacts);
    const flagged = mapFacts({ ...baseFacts, review_gate: "health_flag" });
    expect(flagged.facts).toEqual(base.facts);
    expect(stableEvaluationInputKey(base)).not.toBe(
      stableEvaluationInputKey(flagged),
    );
  });
});

describe("country-code facts: one code is not a set of one", () => {
  // `work.employer_country_code` is `KnownCountryCode` (a bare string) while
  // `person.nationalities` is `KnownCountrySet` (an array). They were mapped
  // by the same helper, and the resulting type error was silenced with an
  // `as` cast — the only one in the mapper. The API answered 422
  // `string_type`, and the interview showed that as a "Client safety hold",
  // so every remote-work interview that named an employer country died
  // before reaching the engine. Assert the SHAPES, side by side.
  it("sends the employer country as a string and nationalities as an array", () => {
    const mapped = mapFacts({
      category: "remote",
      nationalities: "AL",
      remote_employer_country: "AL",
    } as OracleFacts);

    const employer = mapped.facts["work.employer_country_code"];
    const nationalities = mapped.facts["person.nationalities"];
    expect(employer).toEqual({ status: "KNOWN", value: "AL" });
    expect(typeof (employer as { value: unknown }).value).toBe("string");
    expect(Array.isArray((employer as { value: unknown }).value)).toBe(false);
    // Same answer, different contract: this one really is a set.
    expect(nationalities).toEqual({ status: "KNOWN", value: ["AL"] });
  });

  it("refuses more than one employer country rather than truncating", () => {
    const mapped = mapFacts({
      category: "remote",
      remote_employer_country: "AL,IT",
    } as OracleFacts);
    expect(mapped.facts["work.employer_country_code"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_PROVIDED",
    });
  });

  it("keeps the not-asked and unsure answers representable", () => {
    expect(
      mapFacts({ category: "remote" } as OracleFacts).facts[
        "work.employer_country_code"
      ],
    ).toEqual({ status: "UNKNOWN", reason: "NOT_ASKED" });
    expect(
      mapFacts({
        category: "remote",
        remote_employer_country: "unsure",
      } as OracleFacts).facts["work.employer_country_code"],
    ).toEqual({ status: "UNKNOWN", reason: "UNVERIFIED" });
  });
});
