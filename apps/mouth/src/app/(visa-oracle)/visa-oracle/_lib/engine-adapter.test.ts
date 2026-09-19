import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { afterEach, describe, expect, it, vi } from "vitest";

const emitVisaOracleTelemetry = vi.hoisted(() => vi.fn());
vi.mock("./telemetry", () => ({ emitVisaOracleTelemetry }));

import {
  GENERIC_NOTICE_CONDITION,
  NOTICE_CONDITION_COPY,
  REVIEW_REASON_COPY,
  SECOND_HOME_DEPOSIT_THRESHOLD_USD,
  SECOND_HOME_PROPERTY_THRESHOLD_USD,
  SECOND_HOME_STUDIO_REVIEW_REASON_CODE,
  SUPPORT_REASON_COPY,
  buildEngineOutcome,
  isSecondHomeStudioOnly,
} from "./engine-adapter";
import {
  TEST_NOW,
  TEST_SOURCE_ID,
  makeVisaOracleResponse,
} from "./visa-oracle-test-fixture";
import { translate, type I18nKey } from "./i18n";
import { QUESTIONS, type OracleFacts } from "./tree";

describe("Visa Oracle authoritative outcome adapter", () => {
  it("shows each source's own dates, not the decision's evaluation clock", () => {
    // The backend's `_build_sources_dto` stamps EVERY cited source's
    // applicability block with `decision.effective_at`/`observed_at` — the
    // evaluation clock — so those two fields say nothing about the document.
    // Reading them made every source on screen claim it took legal effect at
    // the instant the reader pressed the button.
    //
    // The shared fixture sets every date to TEST_NOW, so it cannot tell the
    // right field from the wrong one: give this source dates of its own.
    // Four DISTINCT dates, so each assertion can only be satisfied by the one
    // field it names. In particular `retrieved_at` and `verified_at` must not
    // share a value: they are adjacent candidates for "observed", and a test
    // that collapses them cannot tell which one the adapter read.
    //
    // `decisiveSource` (engine-adapter.ts) enforces the ordering that makes a
    // source usable as decisive evidence — `retrieved_at <= verified_at`,
    // `freshness.verified_at === verified_at`, `verified_at <= observed_at` —
    // so these move together, forward, inside the fixture's 86_400s window.
    const LEGAL_FROM = "2026-07-24T00:00:00Z";
    const RETRIEVED = "2026-08-02T04:00:00Z";
    const VERIFIED = "2026-08-02T05:00:00Z";
    const response = makeVisaOracleResponse();
    response.sources[0].legal_period_from = LEGAL_FROM;
    response.sources[0].retrieved_at = RETRIEVED;
    response.sources[0].verified_at = VERIFIED;
    response.sources[0].freshness.verified_at = VERIFIED;
    response.sources[0].applicability.effective_at = TEST_NOW;
    response.sources[0].applicability.observed_at = TEST_NOW;

    const outcome = buildEngineOutcome(response);
    const source = outcome.sources[0];
    expect(source.effectiveAtIso).toBe(LEGAL_FROM);
    expect(source.observedAtIso).toBe(VERIFIED);
    // Name every value it must NOT be: the evaluation clock (the bug) and
    // `retrieved_at` (the near-miss the freshness policy makes wrong).
    expect(source.effectiveAtIso).not.toBe(TEST_NOW);
    expect(source.observedAtIso).not.toBe(TEST_NOW);
    expect(source.observedAtIso).not.toBe(RETRIEVED);

    // Innocence: the ASSESSMENT's own dates are legitimately the evaluation
    // moment. This fix must not reach up and rewrite those too.
    expect(outcome.assessment).not.toBeNull();
    expect(outcome.assessment?.effectiveAtIso).toBe(
      response.decision.effective_at,
    );
  });

  it.each([
    "SUPPORTED_CANDIDATES",
    "NEEDS_INPUT",
    "HUMAN_REVIEW_REQUIRED",
    "NO_SUPPORTED_PATH",
    "TEMPORARILY_UNAVAILABLE",
  ] as const)(
    "maps engine state %s without fabricating candidates",
    (state) => {
      const outcome = buildEngineOutcome(makeVisaOracleResponse(state));
      expect(outcome.state).toBe(state);
      expect(outcome.provenance).toBe("ENGINE");
      expect(outcome.candidates).toHaveLength(
        state === "SUPPORTED_CANDIDATES" ? 1 : 0,
      );
    },
  );

  it("uses only processing/pricing/document assessments, never stay policy or mock content", () => {
    const outcome = buildEngineOutcome(makeVisaOracleResponse());
    expect(outcome.state).toBe("SUPPORTED_CANDIDATES");
    if (outcome.state !== "SUPPORTED_CANDIDATES")
      throw new Error("unexpected state");
    const candidate = outcome.candidates[0];
    expect(candidate.timeline).toMatchObject({ status: "UNAVAILABLE" });
    expect(candidate.price).toMatchObject({ status: "CONTACT_REQUIRED" });
    expect(candidate.documents).toEqual([]);
    expect(JSON.stringify(candidate)).not.toContain("60 days");
  });

  it("renders an exact PricingTool quote as one all-inclusive IDR amount", () => {
    const response = makeVisaOracleResponse();
    const candidate = response.display.candidates[0];
    candidate.pricing = {
      status: "AVAILABLE",
      reason_code: "PRICE_AVAILABLE",
      evaluated_at: "2026-08-03T04:00:00Z",
      catalog_last_updated: "2026-08-03",
      catalog_sha256: "b".repeat(64),
      row_sha256: "c".repeat(64),
    };
    response.decision.quotes = [
      {
        quote_id: "55555555-5555-4555-8555-555555555555",
        product_version_id: candidate.product_version_id,
        product_code: candidate.product_code,
        status: "AVAILABLE",
        currency: "IDR",
        amount: 3_250_000,
        pricing_key: { category: "visa", item_key: "C1" },
        catalog_version: "2026.08",
        catalog_sha256: "b".repeat(64),
        row_sha256: "c".repeat(64),
        quoted_at: "2026-08-03T04:00:00Z",
        valid_until: "2026-08-10T04:00:00Z",
        reason_code: "PRICE_AVAILABLE",
      },
    ];

    const outcome = buildEngineOutcome(response);
    expect(outcome.state).toBe("SUPPORTED_CANDIDATES");
    if (outcome.state !== "SUPPORTED_CANDIDATES")
      throw new Error("unexpected state");
    expect(outcome.candidates[0].price).toEqual({
      status: "AVAILABLE",
      currency: "IDR",
      amount: 3_250_000,
      allInclusive: true,
      quotedAtIso: "2026-08-03T04:00:00Z",
      validUntilIso: "2026-08-10T04:00:00Z",
    });
  });

  it("fails closed for CURATED, untrusted, stale or secondary decisive evidence", () => {
    for (const mutate of [
      (response: ReturnType<typeof makeVisaOracleResponse>) => {
        response.mode = "CURATED";
      },
      (response: ReturnType<typeof makeVisaOracleResponse>) => {
        response.sources[0].canonical_url =
          "https://imigrasi.go.id.evil.test/x";
      },
      (response: ReturnType<typeof makeVisaOracleResponse>) => {
        response.sources[0].freshness.status = "STALE";
      },
      (response: ReturnType<typeof makeVisaOracleResponse>) => {
        response.sources[0].is_primary_authority = false;
      },
    ]) {
      const response = makeVisaOracleResponse();
      mutate(response);
      expect(() => buildEngineOutcome(response)).toThrow();
    }
  });

  it("never renders a known operational or service axis without decisive evidence", () => {
    for (const axis of [
      "operational_availability",
      "bali_zero_service_availability",
    ] as const) {
      const missing = makeVisaOracleResponse();
      missing.display.candidates[0].availability[axis] = {
        status: "AVAILABLE",
        reason_code: "AXIS_AVAILABLE",
        observed_at: "2026-08-03T04:00:00Z",
        source_refs: [],
      };
      expect(() => buildEngineOutcome(missing)).toThrow();

      const untrusted = makeVisaOracleResponse();
      untrusted.display.candidates[0].availability[axis] = {
        status: "AVAILABLE",
        reason_code: "AXIS_AVAILABLE",
        observed_at: "2026-08-03T04:00:00Z",
        source_refs: [untrusted.sources[0].source_record_id],
      };
      untrusted.sources[0].canonical_url = "https://evil.test/source";
      expect(() => buildEngineOutcome(untrusted)).toThrow();
    }
  });

  it("rejects decisive evidence whose legal, recorded or verification clocks are in the future", () => {
    const mutations: Array<
      (response: ReturnType<typeof makeVisaOracleResponse>) => void
    > = [
      (response) => {
        response.sources[0].retrieved_at = "2026-08-03T05:00:00Z";
      },
      (response) => {
        response.sources[0].verified_at = "2026-08-03T05:00:00Z";
      },
      (response) => {
        response.sources[0].legal_period_from = "2026-08-03T05:00:00Z";
      },
      (response) => {
        response.sources[0].legal_period_to = "2026-08-03T03:59:59Z";
      },
      (response) => {
        response.sources[0].recorded_period_from = "2026-08-03T05:00:00Z";
      },
      (response) => {
        response.sources[0].applicability.effective_at = "2026-08-03T03:59:59Z";
      },
      (response) => {
        response.sources[0].applicability.observed_at = "2026-08-03T03:59:59Z";
      },
      (response) => {
        response.sources[0].freshness.evaluated_at = "2026-08-03T03:59:59Z";
      },
      (response) => {
        response.sources[0].freshness.verified_at = "2026-08-03T03:59:59Z";
      },
    ];
    for (const mutate of mutations) {
      const response = makeVisaOracleResponse();
      mutate(response);
      expect(() => buildEngineOutcome(response)).toThrow();
    }
  });

  it("keeps a trusted stale or unknown primary source as a review hold, not support", () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    response.sources[0].freshness.status = "UNKNOWN";
    response.sources[0].applicability.status = "UNKNOWN";
    response.sources[0].verified_at = "2026-08-04T04:00:00Z";
    response.decision.review_reasons[0].source_refs = [
      response.sources[0].source_record_id,
    ];

    const outcome = buildEngineOutcome(response, {
      interviewBranchesRemaining: 3,
    });
    expect(outcome).toMatchObject({
      state: "HUMAN_REVIEW_REQUIRED",
      pathsRemaining: 3,
    });
    expect(outcome.sources).toHaveLength(1);
  });

  it("rejects an untrusted source even when it is used only as a review hold", () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    response.sources[0].canonical_url = "https://imigrasi.go.id.evil.test/x";
    response.decision.review_reasons[0].source_refs = [
      response.sources[0].source_record_id,
    ];
    expect(() => buildEngineOutcome(response)).toThrow();
  });

  it("curates review-reason copy for a known code, EN and ID", () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    response.decision.review_reasons[0].code = "CALLING_VISA_REVIEW";

    const outcome = buildEngineOutcome(response);
    expect(outcome.state).toBe("HUMAN_REVIEW_REQUIRED");
    if (outcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    const message = outcome.reviewReasons[0].message;
    expect(message.en).toMatch(/calling visa/i);
    expect(message.id).toMatch(/calling visa/i);
    expect(message.en.toLowerCase()).not.toContain(
      "no evaluation was submitted",
    );
    expect(message.en).not.toContain("Verified reason:");
  });

  it("gives a STEPCHILD walk the same ambiguous-sponsor copy as anyone else — the dead sponsor-permit fact no longer branches it", () => {
    // D3-4 (PR-D3, owner ruling SHWEB-20260911) had `reviewReason` special-
    // case a STEPCHILD applicant's `family_stepchild_sponsor_permit_
    // confirmed` answer here. That question was REMOVED from tree.ts (owner
    // ruling SHWEB-20260911, 2026-09-13, fresh grader review; no such
    // requirement exists for E31D) and PR-D3d retired the now-unreachable
    // branch. `facts` below still carries the fact's old key — nothing in
    // the current interview can set it any more, but the adapter must not
    // resurrect the special case if a stale value ever showed up in it.
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    response.decision.review_reasons[0].code =
      "DISCLOSED_AMBIGUOUS_SPONSOR_REVIEW";
    const facts: OracleFacts = {
      family_relation: "STEPCHILD",
      family_stepchild_sponsor_permit_confirmed: "no",
    };

    const outcome = buildEngineOutcome(response, { facts });
    expect(outcome.state).toBe("HUMAN_REVIEW_REQUIRED");
    if (outcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    expect(outcome.reviewReasons[0].message).toEqual(
      REVIEW_REASON_COPY.DISCLOSED_AMBIGUOUS_SPONSOR_REVIEW,
    );
    expect(outcome.reviewReasons[0].message.en).not.toContain("KITAS/KITAP");
  });

  it("falls back to an honest generic sentence for an unmapped review-reason code", () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    response.decision.review_reasons[0].code = "SOME_FUTURE_RULE_CODE";

    const outcome = buildEngineOutcome(response);
    expect(outcome.state).toBe("HUMAN_REVIEW_REQUIRED");
    if (outcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    const message = outcome.reviewReasons[0].message;
    expect(message.en).not.toContain("SOME_FUTURE_RULE_CODE");
    expect(message.en).not.toContain("Verified reason:");
    expect(message.en.toLowerCase()).not.toContain(
      "no evaluation was submitted",
    );
    expect(message.en.toLowerCase()).toContain("judgment");
  });

  it("maps missing engine facts back to editable interview questions", () => {
    const outcome = buildEngineOutcome(makeVisaOracleResponse("NEEDS_INPUT"), {
      editableQuestionIds: ["stay_days"],
    });
    expect(outcome.state).toBe("NEEDS_INPUT");
    if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
    expect(outcome.missingInputs[0]).toMatchObject({
      code: "intent.stay_days",
      questionId: "stay_days",
    });
  });

  it.each([
    ["work.indonesia_source_compensation", "remote_compensation"],
    ["work.indonesia_source_compensation", "work_indonesia_compensation"],
    ["investment.pt_pma_committed", "investment_pt_pma"],
    ["investment.pt_pma_committed", "remote_pt_pma"],
    ["immigration.current_status_code", "stay_permit_code"],
  ] as const)(
    "routes missing %s to the visited %s question",
    (factPath, questionId) => {
      const response = makeVisaOracleResponse("NEEDS_INPUT");
      response.decision.missing_facts = [factPath];
      const outcome = buildEngineOutcome(response, {
        editableQuestionIds: ["category", questionId, "stay_days"],
      });
      if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
      expect(outcome.missingInputs[0]).toMatchObject({
        code: factPath,
        questionId,
        message: {
          en: translate("en", QUESTIONS[questionId].i18nKey as I18nKey),
          id: translate("id", QUESTIONS[questionId].i18nKey as I18nKey),
        },
      });
    },
  );

  it("retains both missing fact codes when neither has a visited question", () => {
    const response = makeVisaOracleResponse("NEEDS_INPUT");
    response.decision.missing_facts = [
      "work.indonesia_source_compensation",
      "investment.pt_pma_committed",
    ];
    const outcome = buildEngineOutcome(response, {
      editableQuestionIds: ["stay_days"],
    });
    if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
    expect(outcome.missingInputs.map((input) => input.code)).toEqual(
      response.decision.missing_facts,
    );
    expect(outcome.missingInputs.map((input) => input.questionId)).toEqual([
      undefined,
      undefined,
    ]);
    expect(outcome.missingInputs[0].message).toEqual(
      outcome.missingInputs[1].message,
    );
  });

  // ── 2026-09-06 decisiveness wave (PR-3): the follow-up loop ──────────
  // Before this, a NEEDS_INPUT naming a fact whose question exists in
  // QUESTIONS but was never asked on this walk rendered an unanswerable
  // row: `questionForFact` only ever looked inside the interview history.

  it("names a modelled-but-unasked question as a FOLLOW-UP, not as an edit", () => {
    const response = makeVisaOracleResponse("NEEDS_INPUT");
    response.decision.missing_facts = ["process.wants_onshore_conversion"];
    const outcome = buildEngineOutcome(response, {
      facts: { in_indonesia: "no", category: "tourism" },
      editableQuestionIds: ["category", "stay_days"],
    });
    if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
    expect(outcome.missingInputs[0]).toMatchObject({
      code: "process.wants_onshore_conversion",
      questionId: "wants_onshore_conversion",
      followUp: true,
    });
    // The row carries the question's own copy, never the raw fact path.
    expect(JSON.stringify(outcome.missingInputs[0].message)).not.toContain(
      "process.wants_onshore_conversion",
    );
  });

  // Adversarial review 2026-09-06, finding 1 (accepted, narrowed): the
  // follow-up may not bypass the tree's prerequisite ordering. Exactly one
  // question collects `family.marriage_registered`, and the family branch
  // asks it only for a SPOUSE or PARENT relation.
  it("guilt: a prerequisite-bearing fact the answers contradict is NOT pushed", () => {
    const response = makeVisaOracleResponse("NEEDS_INPUT");
    response.decision.missing_facts = ["family.marriage_registered"];
    const outcome = buildEngineOutcome(response, {
      facts: {
        in_indonesia: "no",
        category: "family",
        family_relation: "CHILD",
      },
      editableQuestionIds: ["category", "stay_days"],
    });
    if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
    expect(outcome.missingInputs[0].questionId).toBeUndefined();
    expect(outcome.missingInputs[0].followUp).toBeUndefined();
  });

  it("innocence: the same fact IS pushed once the relation satisfies it", () => {
    const response = makeVisaOracleResponse("NEEDS_INPUT");
    response.decision.missing_facts = ["family.marriage_registered"];
    const outcome = buildEngineOutcome(response, {
      facts: {
        in_indonesia: "no",
        category: "family",
        family_relation: "SPOUSE",
      },
      editableQuestionIds: ["category", "stay_days"],
    });
    if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
    expect(outcome.missingInputs[0]).toMatchObject({
      questionId: "family_marriage_registered",
      followUp: true,
    });
  });

  // D12 (SAETTA-20260916): `family.sponsor_confirmed` is collected by TWO
  // questions since the explorer got its own company-sponsor wording, and
  // `followUpPrerequisitesMet` calls both eligible (it replays the walk once
  // per category). Measured 2026-09-17: that sent the explorer to the
  // handoff row instead of asking the question their own branch asks.
  it("innocence: the D12 explorer is asked the sponsor question their own walk reaches", () => {
    const response = makeVisaOracleResponse("NEEDS_INPUT");
    response.decision.missing_facts = ["family.sponsor_confirmed"];
    const outcome = buildEngineOutcome(response, {
      facts: {
        in_indonesia: "no",
        category: "business",
        business_activity: "exploring",
      },
      editableQuestionIds: ["category", "business_activity"],
    });
    if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
    expect(outcome.missingInputs[0]).toMatchObject({
      questionId: "business_sponsor_confirmed",
      followUp: true,
    });
  });

  // The other side of the same narrowing: a family applicant reaches the
  // family wording, never the D12 one.
  it("innocence: a family applicant reaches the family sponsor question, not D12's", () => {
    const response = makeVisaOracleResponse("NEEDS_INPUT");
    response.decision.missing_facts = ["family.sponsor_confirmed"];
    const outcome = buildEngineOutcome(response, {
      facts: {
        in_indonesia: "no",
        category: "family",
        family_relation: "SPOUSE",
      },
      editableQuestionIds: ["category", "family_relation"],
    });
    if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
    expect(outcome.missingInputs[0].questionId).not.toBe(
      "business_sponsor_confirmed",
    );
  });

  it("guilt: no facts supplied means no follow-up — fail-closed", () => {
    const response = makeVisaOracleResponse("NEEDS_INPUT");
    response.decision.missing_facts = ["process.wants_onshore_conversion"];
    const outcome = buildEngineOutcome(response, {
      editableQuestionIds: ["category", "stay_days"],
    });
    if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
    expect(outcome.missingInputs[0].questionId).toBeUndefined();
  });

  it("innocence: an ALREADY-ASKED question stays a plain edit, with no followUp marker", () => {
    const outcome = buildEngineOutcome(makeVisaOracleResponse("NEEDS_INPUT"), {
      editableQuestionIds: ["stay_days"],
    });
    if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
    expect(outcome.missingInputs[0].questionId).toBe("stay_days");
    expect(outcome.missingInputs[0].followUp).toBeUndefined();
  });

  it.each([
    "work.indonesia_source_compensation",
    "investment.pt_pma_committed",
    "immigration.current_status_code",
  ] as const)(
    "innocence: %s is collected by two questions, so it is never followed up",
    (factPath) => {
      // Splicing in one of two candidate branches' questions would be the
      // adapter guessing which branch the applicant belongs to.
      const response = makeVisaOracleResponse("NEEDS_INPUT");
      response.decision.missing_facts = [factPath];
      const outcome = buildEngineOutcome(response, {
        editableQuestionIds: ["category", "stay_days"],
      });
      if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
      expect(outcome.missingInputs[0].questionId).toBeUndefined();
      expect(outcome.missingInputs[0].followUp).toBeUndefined();
      expect(outcome.missingInputs[0].message.en).toContain("Bali Zero");
    },
  );

  it("innocence: a fact no question collects still falls back to the handoff", () => {
    const response = makeVisaOracleResponse("NEEDS_INPUT");
    response.decision.missing_facts = ["intent.requested_product_code"];
    const outcome = buildEngineOutcome(response, {
      editableQuestionIds: ["category", "stay_days"],
    });
    if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
    expect(outcome.missingInputs[0].questionId).toBeUndefined();
    expect(outcome.missingInputs[0].followUp).toBeUndefined();
  });

  it.each([
    { editableQuestionIds: undefined },
    { editableQuestionIds: [] },
    { editableQuestionIds: ["stay_days"] },
    {
      editableQuestionIds: [
        "remote_compensation",
        "work_indonesia_compensation",
      ],
    },
  ])(
    "offers no arbitrary edit when the target is absent or ambiguous: %j",
    ({ editableQuestionIds }) => {
      const response = makeVisaOracleResponse("NEEDS_INPUT");
      response.decision.missing_facts = ["work.indonesia_source_compensation"];
      const outcome = buildEngineOutcome(response, { editableQuestionIds });
      if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
      expect(outcome.missingInputs[0].questionId).toBeUndefined();
      expect(outcome.missingInputs[0].message.en).toContain("Bali Zero");
      expect(outcome.missingInputs[0].message.id).toContain("Bali Zero");
      expect(JSON.stringify(outcome.missingInputs[0].message)).not.toContain(
        "work.indonesia_source_compensation",
      );
    },
  );
});

describe("support reasons are sentences, not machine codes", () => {
  const HERE = path.dirname(fileURLToPath(import.meta.url));
  const PACKS_DIR = path.resolve(
    HERE,
    "../../../../../../..",
    "apps/backend-rag/backend/services/visa_engine/contracts/packs",
  );

  /**
   * Every production pack, not just the one that happens to be active. Pinning
   * a single filename made this tripwire blind to the pack being authored:
   * seq-6 raised the SUPPORT reason count from 13 to 58 and this test stayed
   * green throughout, because it was still reading seq-5. A pack is written
   * before it is activated, so the check has to cover the ones on disk.
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

  function supportReasonCodesInPack(): string[] {
    const codes = new Set<string>();
    const walk = (node: unknown): void => {
      if (Array.isArray(node)) return node.forEach(walk);
      if (node === null || typeof node !== "object") return;
      const record = node as Record<string, unknown>;
      const effect = record.effect as Record<string, unknown> | undefined;
      if (
        effect &&
        effect.type === "SUPPORT" &&
        typeof effect.reason_code === "string"
      ) {
        codes.add(effect.reason_code);
      }
      Object.values(record).forEach(walk);
    };
    productionPackFiles().forEach((file) => {
      walk(JSON.parse(fs.readFileSync(file, "utf-8")));
    });
    return [...codes].sort();
  }

  function firstReasonEn(code: string): string {
    const response = makeVisaOracleResponse();
    response.decision.candidates[0].reason_codes = [code];
    const outcome = buildEngineOutcome(response);
    if (outcome.state !== "SUPPORTED_CANDIDATES")
      throw new Error("unexpected state");
    return outcome.candidates[0].legal.reasons[0].message.en;
  }

  it("renders a pack reason as prose, never the bare code", () => {
    const message = firstReasonEn("B1_VOA_ELIGIBLE");
    expect(message).not.toMatch(/^Verified reason: /);
    expect(message).not.toContain("B1_VOA_ELIGIBLE");
    expect(message).toContain("Visa on Arrival");
  });

  it("still surfaces an unmapped code instead of blanking it", () => {
    // A code with no copy must stay visible: hiding it would conceal a new
    // rule rather than reveal it.
    expect(firstReasonEn("SOMETHING_NEW_FROM_A_FUTURE_PACK")).toBe(
      "Verified reason: SOMETHING_NEW_FROM_A_FUTURE_PACK",
    );
  });

  it("states the Article 60(2) KITAP prerequisites without inventing status tenure", () => {
    const copy =
      SUPPORT_REASON_COPY.KITAP_TWO_YEAR_MARRIAGE_AND_INTEGRATION_NOT_VERIFIED;
    expect(copy.en).toMatch(/two years of marriage/i);
    expect(copy.en).toMatch(/signed Pernyataan Integrasi/i);
    expect(copy.en).toMatch(/not verified/i);
    expect(copy.en).not.toMatch(/two years on this status/i);
    expect(copy.id).toMatch(/dua tahun/i);
    expect(copy.id).toMatch(/Pernyataan Integrasi/i);
  });

  it("states Article 61 rights while separating employment from self-employment", () => {
    const copy = SUPPORT_REASON_COPY.SPOUSAL_WORK_ARTICLE_61_CONTEXT;
    expect(copy.en).toMatch(/Article 61/i);
    expect(copy.en).toMatch(/work and\/or conduct business/i);
    expect(copy.en).toMatch(/employment/i);
    expect(copy.en).toMatch(/self-employment|business/i);
    expect(copy.en).toMatch(/does not verify/i);
    expect(copy.en).not.toMatch(/only with.*Kemenaker/i);
    expect(copy.id).toMatch(/Pasal 61/i);
    expect(copy.id).toMatch(/pekerjaan dan\/atau usaha/i);
  });

  /**
   * The tripwire: a future pack that adds a SUPPORT reason without copy would
   * print a machine code at a real reader. Fail here first, naming the codes.
   */
  it("has copy for every SUPPORT reason code any production pack can emit", () => {
    const codes = supportReasonCodesInPack();
    // Guard the guard: a glob that silently matched nothing, or a pack whose
    // rules stopped parsing, would make the assertion below vacuously true.
    expect(codes.length).toBeGreaterThanOrEqual(13);
    expect(codes.filter((code) => !(code in SUPPORT_REASON_COPY))).toEqual([]);
  });

  /**
   * D3c/C-D2 (2026-09-13): the tests below read the SIGNED pack specifically
   * — a `.source.json` is a draft that need not have gone through signing at
   * all, so it is not "the pack" any decision was made under. Globbing
   * `*.signed.json` and reading rules from the envelope's `payload` (never
   * top-level, which only exists on the unsigned `.source.json` shape).
   */
  function signedProductionPackFiles(): string[] {
    const files = fs
      .readdirSync(PACKS_DIR)
      .filter((name) => /^rulepack-prod-\d+\.signed\.json$/.test(name))
      .map((name) => path.join(PACKS_DIR, name));
    if (files.length === 0) {
      throw new Error(`no signed production packs found under ${PACKS_DIR}`);
    }
    return files;
  }

  /**
   * The tripwire above walks SUPPORT effects only, but an EXCLUDE code reaches
   * a reader through the SAME `reasonMessage` fallback: `NO_SUPPORTED_PATH`
   * maps `no_path_reasons` through `reason()`. So a new hard filter can print
   * a machine code on the no-path sheet without failing anything above. seq-20
   * adds exactly one such rule — `hf.d2.indonesia-source-compensation`,
   * CL-D2-01's local-compensation prohibition — and its code is read OUT of
   * the highest-sequence SIGNED pack on disk rather than typed here, so a
   * rename in the fold moves this test with it instead of leaving it quietly
   * stale.
   */
  function highestSequencePack(): { rules?: Array<Record<string, unknown>> } {
    let best: {
      payload: { sequence: number; rules?: Array<Record<string, unknown>> };
      sequence: number;
    } | null = null;
    for (const full of signedProductionPackFiles()) {
      const envelope = JSON.parse(fs.readFileSync(full, "utf-8")) as {
        payload?: {
          sequence?: unknown;
          rules?: Array<Record<string, unknown>>;
        };
      };
      const payload = envelope.payload;
      // A pack without a numeric `sequence` cannot be compared — skip it
      // rather than let it win via a sentinel default.
      if (!payload || typeof payload.sequence !== "number") continue;
      if (best === null || payload.sequence > best.sequence) {
        best = {
          payload: payload as {
            sequence: number;
            rules?: Array<Record<string, unknown>>;
          },
          sequence: payload.sequence,
        };
      }
    }
    if (best === null) {
      throw new Error(
        `no signed pack under ${PACKS_DIR} had a numeric sequence`,
      );
    }
    return best.payload;
  }

  function excludeReasonCodeOfRule(ruleId: string): string {
    for (const rule of highestSequencePack().rules ?? []) {
      if (rule.rule_id !== ruleId) continue;
      const effect = rule.effect as Record<string, unknown> | undefined;
      if (
        effect &&
        effect.type === "EXCLUDE" &&
        typeof effect.reason_code === "string"
      ) {
        return effect.reason_code;
      }
      throw new Error(`${ruleId} is no longer an EXCLUDE rule`);
    }
    throw new Error(`${ruleId} is absent from the highest-sequence pack`);
  }

  /**
   * Walks a rule's `when` tree (the `all`/`args` structure, never regexed
   * off the raw JSON text) looking for a `{ op: "gte", fact, value }` node
   * on the named fact, at any nesting depth — `el.e33e.retirement` nests its
   * deposit-trio conjuncts inside an inner `all`, so a top-level-only walk
   * would miss it for that rule even though it happens not to be needed
   * here.
   */
  function findGteValue(node: unknown, fact: string): number | undefined {
    if (Array.isArray(node)) {
      for (const item of node) {
        const found = findGteValue(item, fact);
        if (found !== undefined) return found;
      }
      return undefined;
    }
    if (node === null || typeof node !== "object") return undefined;
    const record = node as Record<string, unknown>;
    if (
      record.op === "gte" &&
      record.fact === fact &&
      typeof record.value === "number"
    ) {
      return record.value;
    }
    if (Array.isArray(record.args)) {
      return findGteValue(record.args, fact);
    }
    return undefined;
  }

  function gteThresholdInPack(ruleId: string, fact: string): number {
    const rule = (highestSequencePack().rules ?? []).find(
      (r) => r.rule_id === ruleId,
    );
    if (!rule) {
      throw new Error(`${ruleId} is absent from the highest-sequence pack`);
    }
    const value = findGteValue(rule.when, fact);
    if (value === undefined) {
      throw new Error(
        `no gte(${fact}) node found in ${ruleId}'s when-tree — the rule's shape changed`,
      );
    }
    return value;
  }

  // D3-3 gate finding (owner escalation, 2026-09-13): `secondHomeBelow
  // ThresholdReason` (engine-adapter.ts) quotes these two constants to a
  // real applicant as a legal requirement, in both languages. They are a
  // SECOND COPY of a number the signed pack owns, with nothing tying them
  // together — and a seq-21 pack revision naming Second Home thresholds is
  // already in preparation. A wrong VERDICT is caught elsewhere (the
  // interview walks); a stale NUMBER INSIDE A SENTENCE is caught only here.
  it("SECOND_HOME_PROPERTY_THRESHOLD_USD and SECOND_HOME_DEPOSIT_THRESHOLD_USD track the signed pack's el.e33.property-basis / el.e33.deposit-basis gte thresholds", () => {
    expect(SECOND_HOME_PROPERTY_THRESHOLD_USD).toBe(
      gteThresholdInPack(
        "el.e33.property-basis",
        "secondhome.qualifying_property_value_usd",
      ),
    );
    expect(SECOND_HOME_DEPOSIT_THRESHOLD_USD).toBe(
      gteThresholdInPack("el.e33.deposit-basis", "secondhome.bank_deposit_usd"),
    );
  });

  // D3c/C-D5 (owner order, 2026-09-13): three more SUPPORT_REASON_COPY
  // sentences state a literal figure that a signed-pack rule actually backs
  // (`el.e28a.investment`, `el.e33e.retirement`, `el.e33f.retirement` — the
  // Second Home basis pair above is already covered by the pinned-constant
  // test). The figure is extracted from the PROSE STRING (never the pack
  // JSON — that stays a structural `when`-tree walk via `gteThresholdInPack`)
  // and compared to the rule's own `gte` threshold, in both languages, with
  // an explicit copy-key -> rule-id/fact map so a reader can see which rule
  // is claimed to back which sentence.
  function usdFromProse(copy: string): number {
    const match = copy.match(/USD\s+([\d,]+)/);
    if (!match) {
      throw new Error(`no "USD <n>" figure found in: ${copy}`);
    }
    return Number(match[1].replace(/,/g, ""));
  }

  function usdFromProseId(copy: string): number {
    const match = copy.match(/USD\s+([\d.]+)/);
    if (!match) {
      throw new Error(`no "USD <n>" figure found in: ${copy}`);
    }
    return Number(match[1].replace(/\./g, ""));
  }

  function idrBillionFromProse(copy: string): number {
    const match = copy.match(/IDR\s+([\d.]+)\s+billion/i);
    if (!match) {
      throw new Error(`no "IDR <n> billion" figure found in: ${copy}`);
    }
    return Math.round(Number(match[1]) * 1_000_000_000);
  }

  function rpMiliarFromProse(copy: string): number {
    const match = copy.match(/Rp\s+([\d,]+)\s+miliar/i);
    if (!match) {
      throw new Error(`no "Rp <n> miliar" figure found in: ${copy}`);
    }
    return Math.round(Number(match[1].replace(",", ".")) * 1_000_000_000);
  }

  const FIGURE_BACKED_BY_RULE: Record<
    string,
    {
      ruleId: string;
      fact: string;
      readEn: (copy: string) => number;
      readId: (copy: string) => number;
    }
  > = {
    E28A_INVESTMENT_ELIGIBLE: {
      ruleId: "el.e28a.investment",
      fact: "investment.paid_up_capital_idr",
      readEn: idrBillionFromProse,
      readId: rpMiliarFromProse,
    },
    E33E_RETIREMENT_ELIGIBLE: {
      ruleId: "el.e33e.retirement",
      fact: "secondhome.bank_deposit_usd",
      readEn: usdFromProse,
      readId: usdFromProseId,
    },
    E33F_RETIREMENT_ELIGIBLE: {
      ruleId: "el.e33f.retirement",
      fact: "secondhome.passive_monthly_income_usd",
      readEn: usdFromProse,
      readId: usdFromProseId,
    },
  };

  it("anchors every remaining SUPPORT-copy figure with a backing rule to that rule's gte threshold, EN and ID", () => {
    // Guard the guard: an empty map would make the loop below vacuously pass.
    expect(Object.keys(FIGURE_BACKED_BY_RULE).length).toBeGreaterThan(0);
    for (const [key, spec] of Object.entries(FIGURE_BACKED_BY_RULE)) {
      const copy = SUPPORT_REASON_COPY[key];
      const expected = gteThresholdInPack(spec.ruleId, spec.fact);
      expect(spec.readEn(copy.en)).toBe(expected);
      expect(spec.readId(copy.id)).toBe(expected);
    }
  });

  // Mirror image: these SUPPORT reasons named a dollar figure on `main` with
  // NO backing rule anywhere in the signed pack (verified: no fact for
  // proof-of-funds or living cost exists in ANY rule's `when` tree, and no
  // fact anywhere holds an ANNUAL income threshold). Narrowed (PR-D3d,
  // 2026-09-13, fresh grader review): the pack does carry ONE income fact —
  // `secondhome.passive_monthly_income_usd`, gte 3000 — but it is a MONTHLY
  // figure backing `el.e33e.retirement`/`el.e33f.retirement` (pinned by
  // `FIGURE_BACKED_BY_RULE` above), a different quantity from
  // `E33G_INCOME_60K_ADVISOR_CHECK`'s USD 60,000 PER YEAR below; it backs no
  // key in this list. Per the same rule as the anchor test above, an
  // unbacked figure may not be stated — this pins that the fix stays
  // applied.
  it("states no figure for SUPPORT reasons the signed pack has no rule to back", () => {
    const NO_BACKING_KEYS = [
      "PROOF_OF_FUNDS_D1",
      "PROOF_OF_FUNDS_D2",
      "PROOF_OF_FUNDS_D12",
      "REQ_FUNDS_2000",
      "LIVING_COST_USD2000",
      "E33G_INCOME_60K_ADVISOR_CHECK",
    ] as const;
    for (const key of NO_BACKING_KEYS) {
      const copy = SUPPORT_REASON_COPY[key];
      expect(copy.en).not.toMatch(/\d/);
      expect(copy.id).not.toMatch(/\d/);
    }
  });

  // D3c/C-D1 gate finding (2026-09-13): `fact-mapper.ts`'s
  // `depositBasisDecisivelyNotChosen`/`propertyBasisDecisivelyNotChosen`
  // synthesise KNOWN(0)/KNOWN(false) for the sibling Second Home basis's four
  // facts once the interview has decisively routed to the OTHER basis. That
  // synthesis is innocent only while every signed-pack rule reading these
  // facts stays SUPPORT-only: the moment a HARD_FILTER/EXCLUDE rule reads one
  // of them, or any rule compares one with `eq false`, the synthesised
  // "known false" stops meaning "not claimed here" and starts actively
  // EXCLUDING a visitor who never answered the question. Nobody else guards
  // this premise, so this walks the highest-sequence SIGNED pack's `when`
  // trees structurally (`all`/`any` via `args`, `not` via its singular `arg`
  // — never regexed off the JSON text) and must go RED the moment a future
  // pack rule breaks it.
  it("never lets a HARD_FILTER/EXCLUDE rule, or an eq-false comparison, read a synthesised Second-Home twin-basis fact", () => {
    const GUARDED_FACTS = [
      "secondhome.bank_deposit_usd",
      "secondhome.bank_deposit_at_state_bank",
      "secondhome.bank_deposit_in_own_name",
      "secondhome.qualifying_property_value_usd",
    ];

    function findGuardedFactNodes(
      node: unknown,
      out: Array<Record<string, unknown>>,
    ): void {
      if (Array.isArray(node)) {
        node.forEach((item) => findGuardedFactNodes(item, out));
        return;
      }
      if (node === null || typeof node !== "object") return;
      const record = node as Record<string, unknown>;
      if (
        typeof record.fact === "string" &&
        GUARDED_FACTS.includes(record.fact)
      ) {
        out.push(record);
      }
      if (Array.isArray(record.args)) {
        findGuardedFactNodes(record.args, out);
      }
      if (record.arg !== undefined) {
        findGuardedFactNodes(record.arg, out);
      }
    }

    const rules = highestSequencePack().rules ?? [];
    let rulesReferencingGuardedFacts = 0;
    const offendingStageRuleIds: string[] = [];
    const offendingEqFalseRuleIds: string[] = [];

    for (const rule of rules) {
      const nodes: Array<Record<string, unknown>> = [];
      findGuardedFactNodes(rule.when, nodes);
      if (nodes.length === 0) continue;
      rulesReferencingGuardedFacts += 1;

      const stage = rule.stage;
      const effectType = (rule.effect as Record<string, unknown> | undefined)
        ?.type;
      if (
        stage === "HARD_FILTER" ||
        stage === "EXCLUDE" ||
        effectType === "EXCLUDE"
      ) {
        offendingStageRuleIds.push(String(rule.rule_id));
      }
      for (const node of nodes) {
        if (node.op === "eq" && node.value === false) {
          offendingEqFalseRuleIds.push(String(rule.rule_id));
        }
      }
    }

    // Guard the guard: a glob/parse that silently found nothing would make
    // the assertions below vacuously pass.
    expect(rulesReferencingGuardedFacts).toBeGreaterThan(0);
    expect(offendingStageRuleIds).toEqual([]);
    expect(offendingEqFalseRuleIds).toEqual([]);
  });

  function firstNoPathReason(code: string, facts?: OracleFacts) {
    const response = makeVisaOracleResponse("NO_SUPPORTED_PATH");
    response.decision.no_path_reasons[0].code = code;
    const outcome = buildEngineOutcome(response, { facts });
    if (outcome.state !== "NO_SUPPORTED_PATH")
      throw new Error("unexpected state");
    return outcome.noPathReasons[0].message;
  }

  it("explains the seq-20 local-compensation exclusion in prose, in every locale", () => {
    const code = excludeReasonCodeOfRule("hf.d2.indonesia-source-compensation");
    expect(code).toBe("BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED");
    expect(code in SUPPORT_REASON_COPY).toBe(true);

    const message = firstNoPathReason(code);
    expect(message.en).not.toMatch(/^Verified reason: /);
    expect(message.en).not.toContain(code);
    expect(message.en).toMatch(/Indonesian source/i);
    expect(message.en).toMatch(/work route/i);
    expect(message.id).not.toContain(code);
    expect(message.id).toMatch(/sumber di Indonesia/i);
    expect(message.id).toMatch(/jalur kerja/i);
  });

  // D3-3 gate finding (owner escalation, 2026-09-13): `el.e33.property-basis`
  // / `el.e33.deposit-basis` are SUPPORT rules — a below-threshold value
  // makes them silently not fire, so the ENGINE'S only reason is the generic
  // `OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES` (verified against
  // rulepack-prod-020.source.json: no EXCLUDE rule names this threshold).
  // The frontend names it instead, from facts it already has.
  it("names the property threshold when the interview declared a below-threshold property (D3-1 invest route)", () => {
    const message = firstNoPathReason(
      "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES",
      {
        category: "invest",
        investment_vehicle: "property",
        secondhome_property_value_usd: "500000",
      },
    );
    expect(message.en).not.toMatch(/^Verified reason: /);
    expect(message.en).toMatch(/500,000/);
    expect(message.en).toMatch(/1,000,000/);
    expect(message.id).toMatch(/500\.000/);
    expect(message.id).toMatch(/1\.000\.000/);
  });

  it("names the deposit threshold when the interview declared a below-threshold deposit (D3-1 invest route)", () => {
    const message = firstNoPathReason(
      "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES",
      {
        category: "invest",
        investment_vehicle: "bank_deposit",
        secondhome_deposit_usd: "50000",
      },
    );
    expect(message.en).toMatch(/50,000/);
    expect(message.en).toMatch(/130,000/);
    expect(message.id).toMatch(/50\.000/);
    expect(message.id).toMatch(/130\.000/);
  });

  it("names the same thresholds on the direct second_home tile", () => {
    const property = firstNoPathReason(
      "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES",
      {
        category: "second_home",
        secondhome_basis: "property",
        secondhome_property_value_usd: "1",
      },
    );
    expect(property.en).toMatch(/1,000,000/);
    const deposit = firstNoPathReason(
      "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES",
      {
        category: "second_home",
        secondhome_basis: "bank_deposit",
        secondhome_deposit_usd: "1",
      },
    );
    expect(deposit.en).toMatch(/130,000/);
  });

  it("innocence: falls back to the generic sentence when the facts do not show a below-threshold Second Home basis", () => {
    const noFacts = firstNoPathReason(
      "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES",
    );
    expect(noFacts.en).toBe(
      SUPPORT_REASON_COPY.OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES.en,
    );
    // A property/deposit ABOVE threshold must not be misreported as a hold.
    const aboveThreshold = firstNoPathReason(
      "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES",
      {
        category: "invest",
        investment_vehicle: "property",
        secondhome_property_value_usd: "5000000",
      },
    );
    expect(aboveThreshold.en).toBe(
      SUPPORT_REASON_COPY.OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES.en,
    );
    // A DIFFERENT code must never be rewritten, even with matching facts.
    const otherCode = firstNoPathReason(
      "BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED",
      {
        category: "invest",
        investment_vehicle: "property",
        secondhome_property_value_usd: "500000",
      },
    );
    expect(otherCode.en).toBe(
      SUPPORT_REASON_COPY.BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED.en,
    );
  });

  // D3-3 (PR-D3): `hf.e33f.sponsor-required` is now reachable — a retirement
  // walk whose chosen basis fails AND whose sponsor is denied resolves
  // decisively to NO_SUPPORTED_PATH with this code (previously unreachable
  // from any corpus walk, so it fell through the raw-code fallback).
  it("explains hf.e33f.sponsor-required in prose, not a raw code dump", () => {
    expect("SPONSOR_REQUIRED" in SUPPORT_REASON_COPY).toBe(true);
    const message = firstNoPathReason("SPONSOR_REQUIRED");
    expect(message.en).not.toMatch(/^Verified reason: /);
    expect(message.en).toMatch(/sponsor/i);
    expect(message.id).toMatch(/sponsor/i);
  });
});

describe("review reasons cover every code the current pack can emit", () => {
  const HERE = path.dirname(fileURLToPath(import.meta.url));
  const PACKS_DIR = path.resolve(
    HERE,
    "../../../../../../..",
    "apps/backend-rag/backend/services/visa_engine/contracts/packs",
  );

  /**
   * Unlike SUPPORT reason codes (grown purely additively, seq-1 through
   * seq-8, `supportReasonCodesInPack` above safely globs every file), the
   * HUMAN_REVIEW taxonomy was CONSOLIDATED at seq-6: rulepack-prod-001/002/
   * 004/005 carried 51-53 granular review codes that were renamed/merged
   * down to a stable 14 in seq-6/7/8 (verified identical across those
   * three). Globbing every pack file for review codes would resurrect that
   * dead pre-seq-6 taxonomy as a permanent "known gap" that can never
   * actually fire again — so this reads only the pack with the HIGHEST
   * `sequence` field on disk (the one closest to going live, same
   * "not-yet-activated" blind-spot concern `supportReasonCodesInPack`
   * documents, without the false positives a full-file glob would add).
   */
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
      // A pack without a numeric `sequence` cannot be compared — skip it
      // rather than let it silently win via a sentinel default (a pack
      // missing this field is malformed, not "oldest").
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

  /**
   * The highest-sequence SIGNED pack's payload. Only a signed pack can be in
   * force, so this is the upper bound of what production can emit today —
   * while `latestProductionPackFile()` is the upper bound of what it will
   * emit next. W-VO-S21 (2026-09-13) is why both are read: an unsigned
   * seq-21 source retires eight review codes that the signed, live seq-20
   * still carries. Reading only the source would call their copy "stale"
   * and delete it from the live pack's sheet; reading only the signed pack
   * would miss a code the next pack adds. The union keeps every code either
   * pack can emit covered — and the day seq-21's signed bundle lands, the
   * eight retired keys stop being in the union and the stale-key test below
   * names them, which is the moment their copy is allowed to go.
   */
  function latestSignedProductionPayload(): {
    rules?: Array<Record<string, unknown>>;
  } {
    let best: {
      payload: { rules?: Array<Record<string, unknown>> };
      sequence: number;
    } | null = null;
    for (const name of fs.readdirSync(PACKS_DIR)) {
      if (!/^rulepack-prod-\d+\.signed\.json$/.test(name)) continue;
      const envelope = JSON.parse(
        fs.readFileSync(path.join(PACKS_DIR, name), "utf-8"),
      ) as {
        payload?: {
          sequence?: unknown;
          rules?: Array<Record<string, unknown>>;
        };
      };
      const payload = envelope.payload;
      if (!payload || typeof payload.sequence !== "number") continue;
      if (best === null || payload.sequence > best.sequence) {
        best = { payload, sequence: payload.sequence };
      }
    }
    if (best === null) {
      throw new Error(
        `no signed pack under ${PACKS_DIR} had a numeric sequence`,
      );
    }
    return best.payload;
  }

  function reviewReasonCodesInPack(): string[] {
    const source = JSON.parse(
      fs.readFileSync(latestProductionPackFile(), "utf-8"),
    ) as { rules?: Array<Record<string, unknown>> };
    const codes = new Set<string>();
    for (const rule of [
      ...(source.rules ?? []),
      ...(latestSignedProductionPayload().rules ?? []),
    ]) {
      const effect = rule.effect as Record<string, unknown> | undefined;
      if (!effect || typeof effect.reason_code !== "string") continue;
      // A HUMAN_REVIEW-stage rule contributes its reason on a definite TRUE
      // (`evaluator.py::evaluate_product`, `_true_reasons`). A HARD_FILTER
      // rule ALSO contributes its reason — the SAME `effect.reason_code`,
      // via `_reason_from_rule` — when its own condition is UNKNOWN and it
      // declares `on_unknown: "HUMAN_REVIEW"`
      // (`_partition_unknowns_by_policy` + `_reason_from_rule`,
      // evaluator.py:355-410, 741-751): a rule author asking for human
      // judgment on an uncertain exclusion outranks merely asking the
      // applicant for more facts. Support-stage (ELIGIBILITY) on_unknown
      // escalation feeds SUPPORT_REASON_COPY instead, not this map, so it is
      // deliberately not included here.
      if (
        rule.stage === "HUMAN_REVIEW" ||
        (rule.stage === "HARD_FILTER" && rule.on_unknown === "HUMAN_REVIEW")
      ) {
        codes.add(effect.reason_code);
      }
    }
    return [...codes].sort();
  }

  // Codes the backend emits itself, independent of any rule pack. These
  // never appear in a pack's `rules[]`, so no glob over pack JSON can
  // discover them — they have to be named here, from three sources in
  // evaluate_path.py:
  //   - `_DISCLOSED_REVIEW_REASON_CODES` (11 `DisclosedReviewFlag` entries)
  //   - `_apply_minor_privacy_hold`'s `MINOR_GUARDIAN_PRIVACY_REVIEW`
  //   - the decisive-source gate (`_apply_decisive_source_gate` family,
  //     ~line 1030) and the safety-critical source hold
  //     (`_apply_safety_critical_source_hold`, ~line 1136): each forces
  //     `state: HUMAN_REVIEW_REQUIRED` with its own review reasons when a
  //     legally decisive/safety-critical source isn't CURRENT. Missed in
  //     the first cut of this test — `DECISIVE_SOURCE_STALE` is proven
  //     live-emitted in research/visa/2026-08-15-gold-replay-live-post-
  //     notice-report.json (persona 9/10, "actual").
  const PACK_INDEPENDENT_REVIEW_REASON_CODES = [
    "CONFLICTING_IMMIGRATION_STATUS_REVIEW",
    "DECISIVE_PRIMARY_SOURCE_NOT_APPLICABLE",
    "DECISIVE_SOURCE_FRESHNESS_UNKNOWN",
    "DECISIVE_SOURCE_STALE",
    "DISCLOSED_ACTIVITY_BOUNDARY_REVIEW",
    "DISCLOSED_AMBIGUOUS_SPONSOR_REVIEW",
    "DISCLOSED_CRIMINAL_RECORD_REVIEW",
    "DISCLOSED_DIPLOMATIC_PASSPORT_REVIEW",
    "DISCLOSED_HEALTH_CONCERN_REVIEW",
    "DISCLOSED_MULTI_PURPOSE_TRIP_REVIEW",
    "DISCLOSED_PEP_OR_SANCTIONS_REVIEW",
    "DISCLOSED_PRIOR_VISA_REFUSAL_REVIEW",
    "DISCLOSED_SOURCE_OF_FUNDS_REVIEW",
    "DISCLOSED_UNCERTAINTY_REVIEW",
    "MINOR_GUARDIAN_PRIVACY_REVIEW",
    "SAFETY_CRITICAL_PRIMARY_SOURCE_NOT_APPLICABLE",
    "SAFETY_CRITICAL_SOURCE_FRESHNESS_UNKNOWN",
    "SAFETY_CRITICAL_SOURCE_STALE",
  ];

  // Real, currently-emittable review reason codes with no copy yet (QW-4a
  // scope: rename the stale keys + prove exhaustiveness; QW-4b, separately
  // gated on copy-deck approval, writes the actual sentences). Every entry
  // here must shrink out as QW-4b lands copy for it — the test below fails
  // if a code that already has copy is still listed, and fails if a REAL
  // unmapped code appears that isn't listed. A THIRD test below fails if an
  // entry here stops naming a real code (renamed/retired upstream) — this
  // list is not exempt from going stale the same way REVIEW_REASON_COPY's
  // keys were.
  //
  // Emptied by PR-O2 (QW-4b, D1, 2026-09-12): all 29 codes below now have
  // dedicated copy in REVIEW_REASON_COPY. The historical note that used to
  // sit here about `E33G_INCOME_EVIDENCE_REVIEW`'s seq-20 retirement (a
  // THIRD, already-removed code, never part of this 29) had no entry left to
  // attach to once the list emptied, so it went with it rather than sit
  // orphaned in an empty array.
  const KNOWN_UNMAPPED_REVIEW_REASON_CODES: string[] = [];

  // EMPTY SINCE THE seq-22 ACTIVATION (2026-09-16T20:16:45Z, activation_id
  // 10937ac5, payload 3d7555af…6e37). While seq-20 was in force, the eight
  // codes seq-22 retires still reached real applicants, so their copy had to
  // stay and this list named them by name. Production now evaluates on
  // seq-22, which cannot emit any of them, so the copy was deleted in the
  // same change that emptied this list. An entry here is a claim that a code
  // is live on signed seq-20 and gone from the highest signed pack; the
  // honesty test below still enforces that, so the list cannot be used as a
  // parking lot for a copy nobody wants to delete.
  const REVIEW_REASON_COPY_KEYS_LIVE_ON_SEQ20_ONLY: string[] = [];

  /** Review reason codes a given signed pack's rules can emit. */
  function reviewReasonCodesInSignedPack(sequence: number): Set<string> {
    const envelope = JSON.parse(
      fs.readFileSync(
        path.join(
          PACKS_DIR,
          `rulepack-prod-${String(sequence).padStart(3, "0")}.signed.json`,
        ),
        "utf-8",
      ),
    ) as { payload?: { rules?: Array<Record<string, unknown>> } };
    const codes = new Set<string>();
    for (const rule of envelope.payload?.rules ?? []) {
      const effect = rule.effect as Record<string, unknown> | undefined;
      if (!effect || typeof effect.reason_code !== "string") continue;
      if (
        rule.stage === "HUMAN_REVIEW" ||
        (rule.stage === "HARD_FILTER" && rule.on_unknown === "HUMAN_REVIEW")
      ) {
        codes.add(effect.reason_code);
      }
    }
    return codes;
  }

  it("names every code the current pack + backend can emit, mapped or in the known gap", () => {
    const allRealCodes = [
      ...reviewReasonCodesInPack(),
      ...PACK_INDEPENDENT_REVIEW_REASON_CODES,
    ].sort();
    // Guard the guard: a glob/parse that silently found nothing would make
    // every assertion below vacuously true. 20 pack (16 HUMAN_REVIEW-stage +
    // 4 HARD_FILTER with on_unknown=HUMAN_REVIEW, PR-O2) + 18
    // pack-independent = 38, all of them mapped as of PR-O2. Floor raised
    // from 32 to the measured 38 (round-1 refuter finding, Gemini 3.1 Pro +
    // Kimi K3): 32 would still pass a regression that silently dropped up
    // to 5 real codes.
    //
    // Unchanged at 38 by W-VO-S21 (2026-09-13): the unsigned seq-21 source
    // retires eight of the 20 pack codes, but `reviewReasonCodesInPack()`
    // reads the signed seq-20 payload too, so all 20 are still counted
    // while seq-20 is the newest pack that can be in force.
    //
    // 38 -> 31 when the signed seq-22 bundle landed (SAETTA-20260916): the
    // highest signed pack is now seq-22, which emits 13 codes (the eight
    // above retired), + 18 pack-independent = 31, measured. The eight keep
    // their copy under REVIEW_REASON_COPY_KEYS_LIVE_ON_SEQ20_ONLY below.
    expect(allRealCodes.length).toBeGreaterThanOrEqual(31);

    const unaccounted = allRealCodes.filter(
      (code) =>
        !(code in REVIEW_REASON_COPY) &&
        !KNOWN_UNMAPPED_REVIEW_REASON_CODES.includes(code),
    );
    expect(unaccounted).toEqual([]);
  });

  it("never lets a stale key sit in the copy map", () => {
    const allRealCodes = new Set([
      ...reviewReasonCodesInPack(),
      ...PACK_INDEPENDENT_REVIEW_REASON_CODES,
    ]);
    const staleKeys = Object.keys(REVIEW_REASON_COPY)
      .filter((code) => !allRealCodes.has(code))
      .sort();
    expect(staleKeys).toEqual(
      [...REVIEW_REASON_COPY_KEYS_LIVE_ON_SEQ20_ONLY].sort(),
    );
  });

  it("keeps the seq-20-only list honest: every entry is live on signed seq-20 and gone from the highest signed pack", () => {
    // The list above is a claim about production, not a parking lot: each
    // entry must be a code the signed seq-20 pack still emits (or its copy
    // really is dead and must go), and must be absent from the highest
    // signed pack (or it is not "seq-20 only" and belongs in the ordinary
    // stale-key check).
    const seq20 = reviewReasonCodesInSignedPack(20);
    const highest = new Set([
      ...reviewReasonCodesInPack(),
      ...PACK_INDEPENDENT_REVIEW_REASON_CODES,
    ]);
    const notLiveOnSeq20 = REVIEW_REASON_COPY_KEYS_LIVE_ON_SEQ20_ONLY.filter(
      (code) => !seq20.has(code),
    );
    expect(notLiveOnSeq20).toEqual([]);
    const stillEmittedByHighest =
      REVIEW_REASON_COPY_KEYS_LIVE_ON_SEQ20_ONLY.filter((code) =>
        highest.has(code),
      );
    expect(stillEmittedByHighest).toEqual([]);
    const withoutCopy = REVIEW_REASON_COPY_KEYS_LIVE_ON_SEQ20_ONLY.filter(
      (code) => !(code in REVIEW_REASON_COPY),
    );
    expect(withoutCopy).toEqual([]);
  });

  it("keeps the known-gap list honest: no entry there already has copy", () => {
    // If QW-4b lands copy for a code, that code must be removed from
    // KNOWN_UNMAPPED_REVIEW_REASON_CODES in the same change — otherwise the
    // gap list silently stops shrinking and stops meaning anything.
    const alreadyMapped = KNOWN_UNMAPPED_REVIEW_REASON_CODES.filter(
      (code) => code in REVIEW_REASON_COPY,
    );
    expect(alreadyMapped).toEqual([]);
  });

  it("keeps the known-gap list honest: no entry there names a code that stopped being real", () => {
    // Mirror image of the stale-key test above, but for
    // KNOWN_UNMAPPED_REVIEW_REASON_CODES instead of REVIEW_REASON_COPY: if
    // an upstream rename/retirement drops a code this list still names, that
    // entry becomes a dead placeholder no other assertion here would catch
    // (it isn't a REVIEW_REASON_COPY key, so the stale-key test can't see
    // it; it has no copy, so the "already has copy" test can't see it
    // either).
    const allRealCodes = new Set([
      ...reviewReasonCodesInPack(),
      ...PACK_INDEPENDENT_REVIEW_REASON_CODES,
    ]);
    const phantomEntries = KNOWN_UNMAPPED_REVIEW_REASON_CODES.filter(
      (code) => !allRealCodes.has(code),
    );
    expect(phantomEntries).toEqual([]);
  });
});

describe("isSecondHomeStudioOnly (D23 B-STUDIO)", () => {
  const studioHold = () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    response.decision.review_reasons[0].code =
      SECOND_HOME_STUDIO_REVIEW_REASON_CODE;
    return buildEngineOutcome(response);
  };

  it("is true when the Studio code is the only review reason", () => {
    expect(isSecondHomeStudioOnly(studioHold())).toBe(true);
  });

  it("is false when the Studio code shares the hold with another reason", () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    const [first] = response.decision.review_reasons;
    response.decision.review_reasons = [
      { ...first, code: SECOND_HOME_STUDIO_REVIEW_REASON_CODE },
      { ...first, code: "CALLING_VISA_REVIEW" },
    ];
    expect(isSecondHomeStudioOnly(buildEngineOutcome(response))).toBe(false);
  });

  it("is false for a review hold whose reason list arrived empty", () => {
    // The non-empty tuple type is a cast over the server list: an empty
    // list must read as the generic human hold, never as the Studio one.
    const outcome = studioHold();
    const emptied = { ...outcome, reviewReasons: [] } as unknown as Parameters<
      typeof isSecondHomeStudioOnly
    >[0];
    expect(isSecondHomeStudioOnly(emptied)).toBe(false);
  });

  it("is false for every state that is not a review hold", () => {
    expect(
      isSecondHomeStudioOnly(
        buildEngineOutcome(makeVisaOracleResponse("SUPPORTED_CANDIDATES")),
      ),
    ).toBe(false);
  });
});

// Slice A2 (PLAN VISA-ORACLE-DW-20260919 §1.6, N1-N3): `notices[]` was wired
// to the wire and dark in the UI — this pins the render.
describe("notices render as named conditions (slice A2)", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    emitVisaOracleTelemetry.mockReset();
  });

  it("maps a single OBSOLETE_PRODUCT_CODE notice — the one code the engine already emits", () => {
    const response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
    response.decision.notices = [
      {
        code: "OBSOLETE_PRODUCT_CODE",
        rule_ids: [],
        source_refs: [TEST_SOURCE_ID],
      },
    ];
    const outcome = buildEngineOutcome(response);
    expect(outcome.conditions).toEqual([
      {
        code: "OBSOLETE_PRODUCT_CODE",
        message: NOTICE_CONDITION_COPY.OBSOLETE_PRODUCT_CODE,
        sourceIds: [TEST_SOURCE_ID],
      },
    ]);
  });

  it("maps many notices in order, each with its own copy", () => {
    const response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
    response.decision.notices = [
      {
        code: "DISCLOSED_HEALTH_CONCERN_CONDITION",
        rule_ids: [],
        source_refs: [],
      },
      {
        code: "DISCLOSED_PEP_OR_SANCTIONS_CONDITION",
        rule_ids: [],
        source_refs: [],
      },
    ];
    const outcome = buildEngineOutcome(response);
    expect(outcome.conditions.map((item) => item.code)).toEqual([
      "DISCLOSED_HEALTH_CONCERN_CONDITION",
      "DISCLOSED_PEP_OR_SANCTIONS_CONDITION",
    ]);
    expect(outcome.conditions[0].message).toEqual(
      NOTICE_CONDITION_COPY.DISCLOSED_HEALTH_CONCERN_CONDITION,
    );
    expect(outcome.conditions[1].message).toEqual(
      NOTICE_CONDITION_COPY.DISCLOSED_PEP_OR_SANCTIONS_CONDITION,
    );
  });

  it.each([
    "SUPPORTED_CANDIDATES",
    "NEEDS_INPUT",
    "HUMAN_REVIEW_REQUIRED",
    "NO_SUPPORTED_PATH",
  ] as const)(
    "carries a condition on %s — notices has no backend state constraint",
    (state) => {
      const response = makeVisaOracleResponse(state);
      response.decision.notices = [
        {
          code: "DISCLOSED_UNCERTAINTY_CONDITION",
          rule_ids: [],
          source_refs: [],
        },
      ];
      const outcome = buildEngineOutcome(response);
      expect(outcome.conditions).toHaveLength(1);
      expect(outcome.conditions[0].code).toBe(
        "DISCLOSED_UNCERTAINTY_CONDITION",
      );
    },
  );

  it("has all eleven codes N1 names, and no other code, EN and ID both non-empty", () => {
    const EXPECTED_CODES = [
      "OBSOLETE_PRODUCT_CODE",
      "DISCLOSED_HEALTH_CONCERN_CONDITION",
      "DISCLOSED_PRIOR_VISA_REFUSAL_CONDITION",
      "DISCLOSED_UNCERTAINTY_CONDITION",
      "DISCLOSED_PEP_OR_SANCTIONS_CONDITION",
      "DISCLOSED_SOURCE_OF_FUNDS_CONDITION",
      "DISCLOSED_DIPLOMATIC_PASSPORT_CONDITION",
      "DISCLOSED_AMBIGUOUS_SPONSOR_CONDITION",
      "DISCLOSED_ACTIVITY_BOUNDARY_CONDITION",
      "DISCLOSED_MULTI_PURPOSE_TRIP_CONDITION",
      "CONFLICTING_IMMIGRATION_STATUS_CONDITION",
    ].sort();
    expect(Object.keys(NOTICE_CONDITION_COPY).sort()).toEqual(EXPECTED_CODES);
    for (const message of Object.values(NOTICE_CONDITION_COPY)) {
      expect(message.en.length).toBeGreaterThan(0);
      expect(message.id.length).toBeGreaterThan(0);
    }
  });

  // S2 (GATE-A2-REPORT-6849 MEDIUM-2), hardened (GATE-A2B-REPORT-6857.md
  // OBS-A2b-1): the guard must see EVERY string the conditions block can
  // render — every `NOTICE_CONDITION_COPY` entry, the generic fallback, AND
  // the two `outcome.conditions.*` i18n keys — and must not be evadable by
  // inflection or an affixed form. The FIRST attempt at this (an inflected-
  // literal stem list) itself missed one: the list carried "does not
  // change" but not "do not change", so the exact EN sentence #6849 shipped
  // and S1 ordered removed — "These do not change the result above" — sailed
  // through GREEN. V1: the guard is therefore PATTERN FAMILIES (case-
  // insensitive regexes), not inflected literals — a family is what catches
  // every inflection of a shape at once, which is exactly what a literal
  // list, however long, cannot do.
  //
  // V4 — the declared ceiling: no finite pattern list forecloses every
  // reassuring synonym in two languages (GATE-A2B-REPORT-6857.md OBS-A2b-7
  // named four real ones outside these families: "no bearing", "tidak
  // berpengaruh", "will not affect your result", "no concern" — the
  // families below now cover exactly those). What this file pins is these
  // families PLUS the historical fixtures in GUILT_FIXTURES below; a new
  // reassuring phrasing found in review is added there as a fixture, never
  // patched by narrowing a family.
  interface BannedPattern {
    name: string;
    re: RegExp;
  }

  const BANNED_PATTERNS: BannedPattern[] = [
    {
      name: "EN negated effect (spaced 'not'): aux + not + up to two words + verb of effect",
      re: /\b(?:do|does|did|will|would|can|could|shall|should|may|might)\s+not\b(?:\s+\S+){0,2}\s+(?:change|affect|alter|impact|influence|matter)s?\b/gi,
    },
    {
      name: "EN negated effect (contracted auxn't): up to two words + verb of effect",
      re: /\b(?:does|did|would|could|should|may|might)n['’]t\b(?:\s+\S+){0,2}\s+(?:change|affect|alter|impact|influence|matter)s?\b/gi,
    },
    {
      name: "EN negated effect, irregular contractions won't/cannot/can't: up to two words + verb of effect",
      re: /\b(?:won['’]t|cannot|can['’]t)\b(?:\s+\S+){0,2}\s+(?:change|affect|alter|impact|influence|matter)s?\b/gi,
    },
    {
      name: "EN 'no issue/problem/concern/bearing/effect/impact/risk(s)'",
      re: /\bno\s+(?:issue|problem|concern|bearing|effect|impact|risk)s?\b/gi,
    },
    { name: "EN stem: clear (unclear allowlisted below)", re: /clear/gi },
    { name: "EN stem: approv", re: /approv/gi },
    { name: "EN stem: guarantee", re: /guarantee/gi },
    { name: "EN 'eligible regardless'", re: /eligible\s+regardless/gi },
    {
      name: "ID negated effect: tidak (akan)? + mengubah/berpengaruh/memengaruhi/mempengaruhi/berdampak/menjadi masalah",
      re: /\btidak\s+(?:akan\s+)?(?:mengubah|berpengaruh|memengaruhi|mempengaruhi|berdampak|menjadi\s+masalah)\b/gi,
    },
    {
      name: "ID 'tanpa masalah/kendala/hambatan'",
      re: /\btanpa\s+(?:masalah|kendala|hambatan)\b/gi,
    },
    {
      name: "ID 'tidak ada masalah/kendala/hambatan'",
      re: /\btidak\s+ada\s+(?:masalah|kendala|hambatan)\b/gi,
    },
    { name: "ID stem: aman", re: /aman/gi },
    { name: "ID stem: lulus", re: /lulus/gi },
    { name: "ID stem: lolos", re: /lolos/gi },
    { name: "ID stem: diterima", re: /diterima/gi },
    { name: "ID stem: setuju", re: /setuju/gi },
    { name: "ID stem: jamin", re: /jamin/gi },
    { name: "ID stem: pasti", re: /pasti/gi },
  ];

  // Exact words that legitimately contain a banned stem WITHOUT carrying its
  // reassuring sense — the fix for a false positive is always an allowlist
  // entry here, NEVER narrowing the family (that would also let a real
  // evasion sharing the same shape through).
  const BANNED_PATTERN_ALLOWLIST = [
    // "unclear" is the OPPOSITE of "cleared":
    // `DISCLOSED_SOURCE_OF_FUNDS_CONDITION.en` reads "an unclear source of
    // funds", which is the defect this whole condition exists to flag.
    /\bunclear\b/gi,
    // "dipastikan" ("cannot yet be confirmed" / "will be confirmed") is a
    // HEDGE, not a reassurance of certainty — the "pasti" family exists to
    // catch reassuring certainty ("sudah pasti", "pasti aman"), not this.
    // Shipped in `DISCLOSED_UNCERTAINTY_CONDITION.id` and
    // `DISCLOSED_AMBIGUOUS_SPONSOR_CONDITION.id`. "memastikan"/
    // "memastikannya" never trip the "pasti" family in the first place:
    // Indonesian me-+p- nasal assimilation (peluluhan) drops the "p" (the
    // same phenomenon that turns "setuju" into "menyetujui" — di- prefixes
    // do not assimilate, so "disetujui"/"dipastikan" keep the literal
    // stem and "menyetujui"/"memastikan" do not), so only "dipastikan"
    // needs an entry here.
    /\bdipastikan\b/gi,
  ];

  function stripAllowlisted(text: string): string {
    let stripped = text;
    for (const allowed of BANNED_PATTERN_ALLOWLIST) {
      stripped = stripped.replace(allowed, "");
    }
    return stripped;
  }

  function findBannedPattern(text: string): string | undefined {
    const stripped = stripAllowlisted(text);
    for (const pattern of BANNED_PATTERNS) {
      pattern.re.lastIndex = 0;
      if (pattern.re.test(stripped)) {
        return pattern.name;
      }
    }
    return undefined;
  }

  interface ConditionsBlockEntry {
    key: string;
    language: "en" | "id";
    text: string;
  }

  // V3 (OBS-A2b-3): the iteration's source tables are PARAMETERS, defaulted
  // to the real production tables — the guilt tests below inject a table
  // carrying a plant instead of hardcoding a string past the matcher, so a
  // plant that never reached the iteration (e.g. a key silently dropped
  // from it) cannot pass by accident.
  interface ConditionsBlockSourceTables {
    noticeConditionCopy: Record<string, { en: string; id: string }>;
    genericNoticeCondition: { en: string; id: string };
    translate: (
      language: "en" | "id",
      key: "outcome.conditions.title" | "outcome.conditions.intro",
    ) => string;
  }

  const DEFAULT_SOURCE_TABLES: ConditionsBlockSourceTables = {
    noticeConditionCopy: NOTICE_CONDITION_COPY,
    genericNoticeCondition: GENERIC_NOTICE_CONDITION,
    translate,
  };

  function conditionsBlockEntries(
    tables: ConditionsBlockSourceTables = DEFAULT_SOURCE_TABLES,
  ): ConditionsBlockEntry[] {
    const entries: ConditionsBlockEntry[] = [];
    for (const [code, message] of Object.entries(tables.noticeConditionCopy)) {
      entries.push({ key: code, language: "en", text: message.en });
      entries.push({ key: code, language: "id", text: message.id });
    }
    entries.push({
      key: "GENERIC_NOTICE_CONDITION",
      language: "en",
      text: tables.genericNoticeCondition.en,
    });
    entries.push({
      key: "GENERIC_NOTICE_CONDITION",
      language: "id",
      text: tables.genericNoticeCondition.id,
    });
    for (const key of [
      "outcome.conditions.title",
      "outcome.conditions.intro",
    ] as const) {
      entries.push({ key, language: "en", text: tables.translate("en", key) });
      entries.push({ key, language: "id", text: tables.translate("id", key) });
    }
    return entries;
  }

  function scanConditionsBlock(
    tables?: ConditionsBlockSourceTables,
  ): Array<ConditionsBlockEntry & { matchedFamily: string }> {
    const hits: Array<ConditionsBlockEntry & { matchedFamily: string }> = [];
    for (const entry of conditionsBlockEntries(tables)) {
      const matchedFamily = findBannedPattern(entry.text);
      if (matchedFamily !== undefined) {
        hits.push({ ...entry, matchedFamily });
      }
    }
    return hits;
  }

  const EXPECTED_CONDITIONS_BLOCK_KEYS = [
    ...Object.keys(NOTICE_CONDITION_COPY),
    "GENERIC_NOTICE_CONDITION",
    "outcome.conditions.title",
    "outcome.conditions.intro",
  ].sort();

  it("pins the scan's own iteration: exactly the title, intro, generic fallback and eleven codes, both languages (V3)", () => {
    const entries = conditionsBlockEntries();
    expect(entries).toHaveLength(28);
    expect(Array.from(new Set(entries.map((e) => e.key))).sort()).toEqual(
      EXPECTED_CONDITIONS_BLOCK_KEYS,
    );
    for (const key of EXPECTED_CONDITIONS_BLOCK_KEYS) {
      expect(
        entries
          .filter((e) => e.key === key)
          .map((e) => e.language)
          .sort(),
        key,
      ).toEqual(["en", "id"]);
    }
  });

  it("innocence: all 28 shipped strings pass the scan clean", () => {
    const hits = scanConditionsBlock();
    expect(hits, JSON.stringify(hits)).toEqual([]);
  });

  // V2: the guard's guilt table is the real history, not invented cases.
  // Rows 1-2 are the exact EN/ID intro #6849 shipped — copied by command
  // (`git show 6ff563eb23:.../i18n.ts`), never retyped — the single
  // sentence this whole slice exists to keep off the surface. Rows 3-13 are
  // ALL ELEVEN plants from GATE-A2B-REPORT-6857.md's check-3 table
  // (P1-P11), copied from the report, INCLUDING P3/P5/P6/P9, which slipped
  // last time as "unlisted synonyms" — the families in BANNED_PATTERNS are
  // what closes them. P10/P11 duplicate rows 1-2's text (the report itself
  // notes P10 is "the EXACT string S1 ordered removed") — both are kept as
  // distinct rows for traceability to their source.
  interface GuiltFixture {
    label: string;
    key: string;
    language: "en" | "id";
    text: string;
  }

  const GUILT_FIXTURES: GuiltFixture[] = [
    {
      label:
        "#6849 shipped EN intro (the sentence this slice exists to remove)",
      key: "outcome.conditions.intro",
      language: "en",
      text: "These do not change the result above — they name what our team checks with you before submission.",
    },
    {
      label:
        "#6849 shipped ID intro (the sentence this slice exists to remove)",
      key: "outcome.conditions.intro",
      language: "id",
      text: "Kondisi ini tidak mengubah hasil di atas — kondisi ini menyebutkan apa yang akan diperiksa tim kami bersama Anda sebelum pengajuan.",
    },
    {
      label: "P1: inflection of the listed 'does not change'",
      key: "outcome.conditions.intro",
      language: "en",
      text: "These conditions do not change the result above. Our team checks each one with you before submission.",
    },
    {
      label: "P2: listed stem 'aman'",
      key: "outcome.conditions.title",
      language: "id",
      text: "Kondisi pada hasil ini yang sudah aman",
    },
    {
      label: "P3: 'no bearing' — unlisted synonym last time",
      key: "GENERIC_NOTICE_CONDITION",
      language: "en",
      text: "An additional condition applies to this result — it has no bearing on your eligibility, and our team will confirm it with you before submission.",
    },
    {
      label: "P4: listed stem 'lolos'",
      key: "DISCLOSED_PEP_OR_SANCTIONS_CONDITION",
      language: "id",
      text: "Anda telah lolos pemeriksaan awal. Tim kami akan memberi tahu dokumen yang perlu disiapkan.",
    },
    {
      label: "P5: 'tidak berpengaruh' — unlisted synonym last time",
      key: "DISCLOSED_HEALTH_CONCERN_CONDITION",
      language: "id",
      text: "Anda menandai adanya masalah kesehatan dalam pengungkapan Anda. Kondisi ini tidak berpengaruh terhadap hasil Anda.",
    },
    {
      label:
        "P6: 'this will not affect your result' — unlisted synonym last time",
      key: "DISCLOSED_SOURCE_OF_FUNDS_CONDITION",
      language: "en",
      text: "You flagged an unclear source of funds in your disclosures. This will not affect your result.",
    },
    {
      label: "P7: listed stem 'jamin'",
      key: "GENERIC_NOTICE_CONDITION",
      language: "id",
      text: "Kondisi tambahan berlaku untuk hasil ini — Hasil Anda sudah dijamin.",
    },
    {
      label: "P8: allowlist probe — 'unclear' and 'cleared' in the same string",
      key: "DISCLOSED_SOURCE_OF_FUNDS_CONDITION",
      language: "en",
      text: "You flagged an unclear source of funds in your disclosures. You are cleared for submission. A source-of-funds compliance check runs at submission.",
    },
    {
      label: "P9: 'no concern' — unlisted synonym last time",
      key: "DISCLOSED_HEALTH_CONCERN_CONDITION",
      language: "en",
      text: "You flagged a health concern in your disclosures. There is no concern about your eligibility.",
    },
    {
      label: "P10: the EXACT EN string S1 ordered removed",
      key: "outcome.conditions.intro",
      language: "en",
      text: "These do not change the result above — they name what our team checks with you before submission.",
    },
    {
      label: "P11: the EXACT ID string S1 ordered removed",
      key: "outcome.conditions.intro",
      language: "id",
      text: "Kondisi ini tidak mengubah hasil di atas — kondisi ini menyebutkan apa yang akan diperiksa tim kami bersama Anda sebelum pengajuan.",
    },
  ];

  function buildInjectedTables(
    fixture: GuiltFixture,
  ): ConditionsBlockSourceTables {
    if (
      fixture.key === "outcome.conditions.title" ||
      fixture.key === "outcome.conditions.intro"
    ) {
      return {
        ...DEFAULT_SOURCE_TABLES,
        translate: (language, key) =>
          language === fixture.language && key === fixture.key
            ? fixture.text
            : translate(language, key),
      };
    }
    if (fixture.key === "GENERIC_NOTICE_CONDITION") {
      return {
        ...DEFAULT_SOURCE_TABLES,
        genericNoticeCondition: {
          ...GENERIC_NOTICE_CONDITION,
          [fixture.language]: fixture.text,
        },
      };
    }
    return {
      ...DEFAULT_SOURCE_TABLES,
      noticeConditionCopy: {
        ...NOTICE_CONDITION_COPY,
        [fixture.key]: {
          ...NOTICE_CONDITION_COPY[fixture.key],
          [fixture.language]: fixture.text,
        },
      },
    };
  }

  it.each(GUILT_FIXTURES)(
    "guilt: $label — $key ($language) is reported by the scan",
    (fixture) => {
      const tables = buildInjectedTables(fixture);
      const hits = scanConditionsBlock(tables);
      const hit = hits.find(
        (h) => h.key === fixture.key && h.language === fixture.language,
      );
      expect(
        hit,
        `expected ${fixture.key} (${fixture.language}) to be reported by the scan for: "${fixture.text}"`,
      ).toBeDefined();
    },
  );

  it("PEP/sanctions and source-of-funds conditions say the check runs at submission", () => {
    // N2: these two specifically must not imply the check already happened.
    expect(
      NOTICE_CONDITION_COPY.DISCLOSED_PEP_OR_SANCTIONS_CONDITION.en,
    ).toMatch(/at submission/i);
    expect(
      NOTICE_CONDITION_COPY.DISCLOSED_SOURCE_OF_FUNDS_CONDITION.en,
    ).toMatch(/at submission/i);
    expect(
      NOTICE_CONDITION_COPY.DISCLOSED_PEP_OR_SANCTIONS_CONDITION.id,
    ).toMatch(/pada saat pengajuan/i);
    expect(
      NOTICE_CONDITION_COPY.DISCLOSED_SOURCE_OF_FUNDS_CONDITION.id,
    ).toMatch(/pada saat pengajuan/i);
  });

  it("throws on an unmapped notice code outside production (N3)", () => {
    const response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
    response.decision.notices = [
      { code: "SOME_FUTURE_CONDITION_CODE", rule_ids: [], source_refs: [] },
    ];
    expect(() => buildEngineOutcome(response)).toThrow();
  });

  it("falls back to a neutral sentence and reports the gap once in production (N3)", () => {
    vi.stubEnv("NODE_ENV", "production");
    const response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
    response.decision.notices = [
      { code: "ANOTHER_FUTURE_CONDITION_CODE", rule_ids: [], source_refs: [] },
    ];
    const outcome = buildEngineOutcome(response);
    expect(outcome.conditions).toEqual([
      {
        code: "ANOTHER_FUTURE_CONDITION_CODE",
        message: GENERIC_NOTICE_CONDITION,
        sourceIds: [],
      },
    ]);
    // S5 de-duplicates a REPEATED code within one decision before it ever
    // reaches this fallback, so "once per code, not once per occurrence" is
    // now proven ACROSS two separate decisions sharing the same unmapped
    // code — the session-scoped case S5's per-decision dedupe cannot cover.
    const second = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
    second.decision.notices = [
      { code: "ANOTHER_FUTURE_CONDITION_CODE", rule_ids: [], source_refs: [] },
    ];
    buildEngineOutcome(second);
    expect(emitVisaOracleTelemetry).toHaveBeenCalledTimes(1);
    expect(emitVisaOracleTelemetry).toHaveBeenCalledWith({
      event: "visa_oracle_v2_notice_unmapped_code",
      code: "ANOTHER_FUTURE_CONDITION_CODE",
    });
  });

  it("de-duplicates a repeated code within one decision, first occurrence wins (S5)", () => {
    // ReasonList keys each item on `reason.code` (OutcomeSheet.tsx) — two
    // conditions sharing a code would collide as React keys. No producer
    // emits this today; the adapter guarantees it rather than assuming it.
    const response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
    response.decision.notices = [
      {
        code: "OBSOLETE_PRODUCT_CODE",
        rule_ids: [],
        source_refs: [TEST_SOURCE_ID],
      },
      { code: "OBSOLETE_PRODUCT_CODE", rule_ids: [], source_refs: [] },
    ];
    const outcome = buildEngineOutcome(response);
    expect(outcome.conditions).toEqual([
      {
        code: "OBSOLETE_PRODUCT_CODE",
        message: NOTICE_CONDITION_COPY.OBSOLETE_PRODUCT_CODE,
        // The FIRST occurrence's source_refs survive, not the second's.
        sourceIds: [TEST_SOURCE_ID],
      },
    ]);
  });
});
