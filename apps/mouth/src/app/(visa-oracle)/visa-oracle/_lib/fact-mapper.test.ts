import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";
import {
  CATEGORY_TO_PURPOSE,
  SCHEMA_VERSION,
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
// 40-key clients don't 422) but the frontend contract is now the full 41.
//
// Widened again 2026-08-23 (owner ruling — Visa Oracle fact vocabulary
// extension, vocabulary-only, no rule change): three more optional/defaulted
// keys join the same rollout idiom —
// `family.stepchild_marriage_certificate_confirmed`,
// `family.stepchild_birth_certificate_confirmed` and
// `family.sponsor_permit_basis`. Same posture as `sponsor.type`: this mapper
// emits all three on every call, KNOWN when answered, otherwise an explicit
// UNKNOWN, never omitted — the frontend contract is now the full 44.
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

  it("sanity: the backend contract has 45 fact paths, sponsor.type included", () => {
    expect(backendPaths.length).toBe(45);
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

  it("emits exactly the 45 backend fact-path keys, sponsor.type included", () => {
    const result = mapFacts({});
    const actualKeys = Object.keys(result.facts).sort();
    expect(actualKeys).toEqual([...backendPaths].sort());
  });

  it("still emits exactly those 45 keys on a fully-answered interview (no extra keys sneak in)", () => {
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

  it.each([
    ["trip_scope", "multiple", "MULTI_PURPOSE_TRIP"],
    ["business_activity", "meetings", "ACTIVITY_BOUNDARY"],
    ["work_role", "specialist", "ACTIVITY_BOUNDARY"],
    ["tourism_duration", "short", "ACTIVITY_BOUNDARY"],
    ["remote_income", "above", "ACTIVITY_BOUNDARY"],
    ["investment_vehicle", "property", "ACTIVITY_BOUNDARY"],
    ["retirement_basis", "property", "ACTIVITY_BOUNDARY"],
    ["family_sponsor_status_code", "FOO", "AMBIGUOUS_SPONSOR"],
    ["family_sponsor_permit_basis", "EXPERT", "AMBIGUOUS_SPONSOR"],
    ["diaspora_connection", "former_citizen", "ACTIVITY_BOUNDARY"],
    ["diaspora_documents", "passport", "ACTIVITY_BOUNDARY"],
    ["other_purpose", "medical", "ACTIVITY_BOUNDARY"],
    ["other_paid_activity", "yes", "ACTIVITY_BOUNDARY"],
  ])(
    "maps HUMAN_CONTEXT %s to a conservative review flag",
    (id, value, flag) => {
      expect(mapFacts({ [id]: value }).disclosed_review_flags).toContain(flag);
    },
  );
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

describe("V1/E28 (2026-08-24): investment_product_code -> intent.requested_product_code", () => {
  // Before the fix this field was unconditionally `unknownFact(NOT_ASKED)`
  // regardless of `facts` — every assertion below that supplies an answer
  // would have failed against that old behavior (the KNOWN ones on the
  // stale UNKNOWN shape; the "never asked" one is the one case the old code
  // also produced, kept here as the innocence control).
  it.each(["E28B", "E28C", "E28D", "E28F"])(
    "%s -> KNOWN, unchanged",
    (code) => {
      expect(
        mapFacts({ investment_product_code: code }).facts[
          "intent.requested_product_code"
        ],
      ).toEqual({ status: "KNOWN", value: code });
    },
  );

  it('"no specific code" (STANDARD) -> UNKNOWN NOT_PROVIDED, never blocks the ordinary E28A path', () => {
    expect(
      mapFacts({ investment_product_code: "STANDARD" }).facts[
        "intent.requested_product_code"
      ],
    ).toEqual({ status: "UNKNOWN", reason: "NOT_PROVIDED" });
  });

  it("unsure -> UNKNOWN UNVERIFIED", () => {
    expect(
      mapFacts({ investment_product_code: "unsure" }).facts[
        "intent.requested_product_code"
      ],
    ).toEqual({ status: "UNKNOWN", reason: "UNVERIFIED" });
  });

  it("never asked (e.g. any non-invest category) -> UNKNOWN NOT_ASKED", () => {
    expect(mapFacts({}).facts["intent.requested_product_code"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });

  // INNOCENCE test, per team-lead's 2026-08-25 PASS-grade finding: this
  // fact is `required_facts` on 13 pack rules, not just the 4 E28 ones —
  // among them `el.bridging.destination-stated` (SUPPORT,
  // `intent.purposes intersects [OTHER] AND intent.requested_product_code
  // != "BRIDGING"`), whose NEQ-against-one-sentinel `when` is the same
  // shape as PR #4797's defect (a rule whose condition doesn't actually
  // test what it claims). It stays unreachable ONLY because no real
  // applicant can ever have BOTH `intent.purposes` include OTHER AND
  // `intent.requested_product_code` KNOWN — `CATEGORY_TO_PURPOSE` maps
  // every category to a distinct purpose (`invest` -> INVESTMENT,
  // `other` -> OTHER, disjoint) and this question is only reachable when
  // `category === "invest"` (see the "is never reachable through a
  // non-invest category" property test in flow.test.ts, which already
  // iterates every CATEGORY_KEYS entry). This test pins the FACT-level
  // consequence directly, not just the question-reachability half: it
  // goes RED the day this question is asked from a non-invest branch,
  // which is exactly the change that would arm
  // `el.bridging.destination-stated`.
  it("OTHER purpose never co-occurs with a KNOWN requested_product_code (el.bridging.destination-stated's unreachability)", () => {
    for (const category of CATEGORY_KEYS) {
      const purpose = CATEGORY_TO_PURPOSE[category];
      if (purpose !== "OTHER") continue;
      // The real UI never populates `investment_product_code` outside the
      // "invest" branch (flow.test.ts), so a real applicant on this
      // category's path presents exactly this fact shape to the mapper.
      const result = mapFacts({ category } as OracleFacts);
      expect(result.facts["intent.purposes"]).toEqual({
        status: "KNOWN",
        value: ["OTHER"],
      });
      expect(result.facts["intent.requested_product_code"]).toEqual({
        status: "UNKNOWN",
        reason: "NOT_ASKED",
      });
      // And the structural guarantee itself: this question is not even
      // reachable on this category's path, so there is no real state in
      // which an "other"-purpose applicant could answer it.
      expect(getCategoryQuestionIds({ category } as OracleFacts)).not.toContain(
        "investment_product_code",
      );
    }
  });
});

describe("V1/E33 (2026-08-25): sponsor-gated E33A/B/C -> intent.requested_product_code", () => {
  // Same disease-shape as V1/E28 above, narrower cure: E33A/E33B/E33C are
  // reachable only through the sponsor-gated `employment_product_code_govt`/
  // `employment_product_code_none`/`investment_product_code_govt` questions
  // (tree.ts/flow.ts). Every case here mirrors the V1/E28 pattern exactly.
  it("employment_product_code_govt=E33A (sponsor GOVERNMENT) -> KNOWN E33A", () => {
    expect(
      mapFacts({
        category: "work",
        sponsor_category: "GOVERNMENT",
        employment_product_code_govt: "E33A",
      } as OracleFacts).facts["intent.requested_product_code"],
    ).toEqual({ status: "KNOWN", value: "E33A" });
  });

  it("employment_product_code_govt=E33B (sponsor GOVERNMENT) -> KNOWN E33B", () => {
    expect(
      mapFacts({
        category: "work",
        sponsor_category: "GOVERNMENT",
        employment_product_code_govt: "E33B",
      } as OracleFacts).facts["intent.requested_product_code"],
    ).toEqual({ status: "KNOWN", value: "E33B" });
  });

  it("employment_product_code_none=E33B (sponsor NONE) -> KNOWN E33B", () => {
    expect(
      mapFacts({
        category: "work",
        sponsor_category: "NONE",
        employment_product_code_none: "E33B",
      } as OracleFacts).facts["intent.requested_product_code"],
    ).toEqual({ status: "KNOWN", value: "E33B" });
  });

  it.each(["GOVERNMENT", "NONE"])(
    "investment_product_code_govt=E33C (sponsor %s) -> KNOWN E33C",
    (sponsorCategory) => {
      expect(
        mapFacts({
          category: "invest",
          sponsor_category: sponsorCategory,
          investment_product_code_govt: "E33C",
        } as OracleFacts).facts["intent.requested_product_code"],
      ).toEqual({ status: "KNOWN", value: "E33C" });
    },
  );

  it('employment_product_code_govt="STANDARD" -> UNKNOWN NOT_PROVIDED, never blocks a plausible E33A/B path', () => {
    expect(
      mapFacts({
        category: "work",
        sponsor_category: "GOVERNMENT",
        employment_product_code_govt: "STANDARD",
      } as OracleFacts).facts["intent.requested_product_code"],
    ).toEqual({ status: "UNKNOWN", reason: "NOT_PROVIDED" });
  });

  it("employment_product_code_govt=unsure -> UNKNOWN UNVERIFIED", () => {
    expect(
      mapFacts({
        category: "work",
        sponsor_category: "GOVERNMENT",
        employment_product_code_govt: "unsure",
      } as OracleFacts).facts["intent.requested_product_code"],
    ).toEqual({ status: "UNKNOWN", reason: "UNVERIFIED" });
  });

  it("never asked (no V1/E33 UI fact set at all) -> UNKNOWN NOT_ASKED", () => {
    expect(mapFacts({}).facts["intent.requested_product_code"]).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });

  // TEAM-LEAD-MANDATED INNOCENCE TEST, verbatim requirement (2026-08-25
  // ruling): "an applicant without a GOVERNMENT sponsor never produces a
  // KNOWN requested_product_code for E33[A|B|C]". `sponsor_category`'s real
  // option keys are read live from tree.ts (via QUESTIONS) rather than
  // hardcoded, so this test cannot silently go stale if the enum drifts.
  it("no sponsor_category value other than GOVERNMENT/NONE ever reaches the three E33-bearing questions or a KNOWN E33 code", () => {
    const sponsorCategoryKeys = QUESTIONS.sponsor_category.options.map(
      (option) => option.key,
    );
    const otherValues = sponsorCategoryKeys.filter(
      (value) => value !== "GOVERNMENT" && value !== "NONE",
    );
    expect(otherValues.sort()).toEqual(
      ["INDIVIDUAL", "EMPLOYER", "EDUCATION", "INVESTMENT"].sort(),
    );
    for (const sponsorCategory of otherValues) {
      const workIds = getCategoryQuestionIds({
        category: "work",
        sponsor_category: sponsorCategory,
      } as OracleFacts);
      expect(workIds).not.toContain("employment_product_code_govt");
      expect(workIds).not.toContain("employment_product_code_none");

      const investIds = getCategoryQuestionIds({
        category: "invest",
        sponsor_category: sponsorCategory,
      } as OracleFacts);
      expect(investIds).not.toContain("investment_product_code_govt");

      // Hence these three UI facts structurally cannot be set for this
      // applicant, hence the fact-mapper can never resolve
      // intent.requested_product_code to KNOWN via any of them.
      const mapped = mapFacts({
        category: "work",
        sponsor_category: sponsorCategory,
      } as OracleFacts);
      expect(mapped.facts["intent.requested_product_code"]).toEqual({
        status: "UNKNOWN",
        reason: "NOT_ASKED",
      });
    }
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

  it("is reachable (and answers KNOWN) on every category branch that asks it", () => {
    // The categories where the sponsor discriminates (design choice, see
    // FIXED_CATEGORY_QUESTIONS/getCategoryQuestionIds in flow.ts): work,
    // remote, study, invest, retirement, family. Derived from the flow
    // graph itself, not hardcoded, so this test breaks if a branch's
    // question list changes without this describe block being revisited.
    const categoriesAsking = CATEGORY_KEYS.filter((category) =>
      getCategoryQuestionIds({ category }).includes("sponsor_category"),
    );
    expect([...categoriesAsking].sort()).toEqual(
      ["family", "invest", "remote", "retirement", "study", "work"].sort(),
    );
    for (const category of categoriesAsking) {
      const result = mapFacts({ category, sponsor_category: "EMPLOYER" });
      expect(result.facts["sponsor.type"]).toEqual({
        status: "KNOWN",
        value: "EMPLOYER",
      });
    }
  });

  it("is never asked on categories where the sponsor doesn't discriminate", () => {
    for (const category of [
      "tourism",
      "business",
      "diaspora",
      "other",
    ] as const) {
      expect(getCategoryQuestionIds({ category })).not.toContain(
        "sponsor_category",
      );
    }
  });
});

describe("mapPurposes — category -> intent.purposes", () => {
  it("maps every tile with a clean VisaPurpose match (all except diaspora)", () => {
    for (const [tile, purpose] of Object.entries(CATEGORY_TO_PURPOSE)) {
      expect(mapPurposes({ category: tile })).toEqual({
        status: "KNOWN",
        value: [purpose],
      });
    }
  });

  it("diaspora has no clean VisaPurpose match -> UNKNOWN NOT_APPLICABLE", () => {
    expect(mapPurposes({ category: "diaspora" })).toEqual({
      status: "UNKNOWN",
      reason: "NOT_APPLICABLE",
    });
  });

  it("every one of the 10 CATEGORY_KEYS tiles is handled (mapped or explicitly diaspora)", () => {
    for (const tile of CATEGORY_KEYS) {
      const result = mapPurposes({ category: tile });
      assertValidFactValue(result);
      if (tile === "diaspora") {
        expect(result).toEqual({ status: "UNKNOWN", reason: "NOT_APPLICABLE" });
      } else {
        expect(result.status).toBe("KNOWN");
      }
    }
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

  it("holds unsupported retirement property context for human review", () => {
    expect(mapDisclosedReviewFlags({ retirement_basis: "property" })).toEqual([
      "ACTIVITY_BOUNDARY",
    ]);
  });
});

describe("family sponsor status — unverified human context", () => {
  it("never turns a plausible free-text status into a KNOWN signed fact", () => {
    const result = mapFacts({
      family_sponsor_confirmed: "yes",
      family_sponsor_status_code: "FOO",
    });
    expect(result.facts["family.sponsor_status_code"]).toEqual({
      status: "UNKNOWN",
      reason: "UNVERIFIED",
    });
    expect(result.disclosed_review_flags).toContain("AMBIGUOUS_SPONSOR");
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
    expect(result.disclosed_review_flags).toContain("AMBIGUOUS_SPONSOR");
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

describe("remote_income — no FactPath exists, never invented", () => {
  it("does not invent a FactPath and instead adds a monotone review hold", () => {
    const base: OracleFacts = { category: "remote", remote_clients: "foreign" };
    const withIncome: OracleFacts = { ...base, remote_income: "above" };
    const before = mapFacts(base);
    const after = mapFacts(withIncome);
    expect(after.facts).toEqual(before.facts);
    expect(before.disclosed_review_flags).toEqual([]);
    expect(after.disclosed_review_flags).toEqual(["ACTIVITY_BOUNDARY"]);
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
