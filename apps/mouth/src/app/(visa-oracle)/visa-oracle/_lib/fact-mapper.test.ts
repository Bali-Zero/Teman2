import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";
import {
  CATEGORY_TO_PURPOSE,
  SCHEMA_VERSION,
  TOURISM_DURATION_DAYS,
  VIOLATION_MEMBER_FOR_OVERSTAY_OR_BLACKLIST,
  mapCurrentStatusExpiry,
  mapCurrentlyInIndonesia,
  mapEmployerIsIndonesianEntity,
  mapOracleFactsToApplicantFacts,
  mapPurposes,
  mapRemoteClientsDerived,
  mapStayDays,
  mapViolationHistory,
  type FactValue,
  type UnknownReasonWire,
} from "./fact-mapper";
import { CATEGORY_KEYS, type OracleFacts } from "./tree";

// ---------------------------------------------------------------------------
// The 40-key contract, extracted from models.py itself (never hand-typed —
// test acceptance criterion #1). The only dotted `Field(alias="a.b")`
// occurrences in models.py live inside `ApplicantFactsData`; every other
// `alias=` in the file (`TimeRange.from_`) has no dot, so the dotted-alias
// regex below can only ever match the 40 ApplicantFactsData fields.
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

describe("mapOracleFactsToApplicantFacts — 40-key contract (acceptance test 1)", () => {
  const expectedPaths = extractApplicantFactPathsFromModelsPy();

  it("sanity: the extractor itself found 40 dotted paths in models.py", () => {
    expect(expectedPaths.length).toBe(40);
  });

  it("emits EXACTLY the 40 dotted keys models.py declares — no extra key, no missing key", () => {
    const result = mapFacts({});
    const actualKeys = Object.keys(result.facts).sort();
    expect(actualKeys).toEqual([...expectedPaths].sort());
  });

  it("still emits exactly those 40 keys on a fully-answered interview (no extra keys sneak in)", () => {
    const result = mapFacts({
      in_indonesia: "yes",
      permit_expiry: "2026-08-01",
      category: "work",
      work_payer: "yes",
      review_gate: "none",
    });
    const actualKeys = Object.keys(result.facts).sort();
    expect(actualKeys).toEqual([...expectedPaths].sort());
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

  it("unsure -> KNOWN true (conservative carve-out, verbatim task brief)", () => {
    expect(mapCurrentlyInIndonesia({ in_indonesia: "unsure" })).toEqual({
      status: "KNOWN",
      value: true,
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

describe("mapRemoteClientsDerived — remote_clients -> work.serves_indonesian_clients + work.indonesia_source_compensation", () => {
  it("foreign -> KNOWN false / KNOWN false", () => {
    expect(mapRemoteClientsDerived({ remote_clients: "foreign" })).toEqual({
      servesIndonesianClients: { status: "KNOWN", value: false },
      indonesiaSourceCompensation: { status: "KNOWN", value: false },
    });
  });

  it("indonesian -> KNOWN true / KNOWN true", () => {
    expect(mapRemoteClientsDerived({ remote_clients: "indonesian" })).toEqual({
      servesIndonesianClients: { status: "KNOWN", value: true },
      indonesiaSourceCompensation: { status: "KNOWN", value: true },
    });
  });

  it("mixed -> KNOWN true / KNOWN true", () => {
    expect(mapRemoteClientsDerived({ remote_clients: "mixed" })).toEqual({
      servesIndonesianClients: { status: "KNOWN", value: true },
      indonesiaSourceCompensation: { status: "KNOWN", value: true },
    });
  });

  it("unsure -> UNKNOWN UNVERIFIED for both", () => {
    expect(mapRemoteClientsDerived({ remote_clients: "unsure" })).toEqual({
      servesIndonesianClients: { status: "UNKNOWN", reason: "UNVERIFIED" },
      indonesiaSourceCompensation: { status: "UNKNOWN", reason: "UNVERIFIED" },
    });
  });

  it("never asked -> UNKNOWN NOT_ASKED for both", () => {
    expect(mapRemoteClientsDerived({})).toEqual({
      servesIndonesianClients: { status: "UNKNOWN", reason: "NOT_ASKED" },
      indonesiaSourceCompensation: { status: "UNKNOWN", reason: "NOT_ASKED" },
    });
  });
});

describe("mapStayDays — tourism_duration -> intent.stay_days", () => {
  it("short -> KNOWN 30 (the documented canonical bucket day-count)", () => {
    expect(mapStayDays({ tourism_duration: "short" })).toEqual({
      status: "KNOWN",
      value: TOURISM_DURATION_DAYS.short,
    });
    expect(TOURISM_DURATION_DAYS.short).toBe(30);
  });

  it("medium -> KNOWN 60", () => {
    expect(mapStayDays({ tourism_duration: "medium" })).toEqual({
      status: "KNOWN",
      value: 60,
    });
  });

  it("extended -> KNOWN 90 (documented arbitrary interior representative)", () => {
    expect(mapStayDays({ tourism_duration: "extended" })).toEqual({
      status: "KNOWN",
      value: 90,
    });
  });

  it("unsure -> UNKNOWN UNVERIFIED", () => {
    expect(mapStayDays({ tourism_duration: "unsure" })).toEqual({
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

  it('"overstay_or_blacklist" alone -> KNOWN [OVERSTAY]', () => {
    expect(
      mapViolationHistory({ review_gate: "overstay_or_blacklist" }),
    ).toEqual({
      status: "KNOWN",
      value: [VIOLATION_MEMBER_FOR_OVERSTAY_OR_BLACKLIST],
    });
    expect(VIOLATION_MEMBER_FOR_OVERSTAY_OR_BLACKLIST).toBe("OVERSTAY");
  });

  it("overstay_or_blacklist combined with other UI-only flags -> still KNOWN [OVERSTAY]", () => {
    expect(
      mapViolationHistory({
        review_gate: "criminal_record,overstay_or_blacklist",
      }),
    ).toEqual({ status: "KNOWN", value: ["OVERSTAY"] });
  });

  it("a UI-only flag WITHOUT overstay_or_blacklist -> KNOWN empty tuple", () => {
    expect(mapViolationHistory({ review_gate: "criminal_record" })).toEqual({
      status: "KNOWN",
      value: [],
    });
  });

  it('"not_certain" is one of the 4 UI-only items (brief is literal/exhaustive) -> still KNOWN empty tuple, NOT a special UNVERIFIED case', () => {
    expect(mapViolationHistory({ review_gate: "not_certain" })).toEqual({
      status: "KNOWN",
      value: [],
    });
  });

  it("not_certain combined with overstay_or_blacklist -> overstay_or_blacklist still wins (KNOWN [OVERSTAY])", () => {
    expect(
      mapViolationHistory({
        review_gate: "not_certain,overstay_or_blacklist",
      }),
    ).toEqual({ status: "KNOWN", value: ["OVERSTAY"] });
  });

  it("never asked -> UNKNOWN NOT_ASKED", () => {
    expect(mapViolationHistory({})).toEqual({
      status: "UNKNOWN",
      reason: "NOT_ASKED",
    });
  });
});

describe("remote_income — no FactPath exists, never invented", () => {
  it("has zero effect on the mapped output, present or absent", () => {
    const base: OracleFacts = { category: "remote", remote_clients: "foreign" };
    const withIncome: OracleFacts = { ...base, remote_income: "above" };
    expect(mapFacts(withIncome)).toEqual(mapFacts(base));
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
});
