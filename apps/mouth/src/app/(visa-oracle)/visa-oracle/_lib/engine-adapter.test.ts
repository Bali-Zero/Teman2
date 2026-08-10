import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";
import { SUPPORT_REASON_COPY, buildEngineOutcome } from "./engine-adapter";
import { TEST_NOW, makeVisaOracleResponse } from "./visa-oracle-test-fixture";

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
    const outcome = buildEngineOutcome(makeVisaOracleResponse("NEEDS_INPUT"));
    expect(outcome.state).toBe("NEEDS_INPUT");
    if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
    expect(outcome.missingInputs[0]).toMatchObject({
      code: "intent.stay_days",
      questionId: "stay_days",
    });
  });
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
});
