import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";
import {
  REVIEW_REASON_COPY,
  SUPPORT_REASON_COPY,
  buildEngineOutcome,
} from "./engine-adapter";
import { TEST_NOW, makeVisaOracleResponse } from "./visa-oracle-test-fixture";
import { translate, type I18nKey } from "./i18n";
import { QUESTIONS } from "./tree";

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
   * The tripwire above walks SUPPORT effects only, but an EXCLUDE code reaches
   * a reader through the SAME `reasonMessage` fallback: `NO_SUPPORTED_PATH`
   * maps `no_path_reasons` through `reason()`. So a new hard filter can print
   * a machine code on the no-path sheet without failing anything above. seq-20
   * adds exactly one such rule — `hf.d2.indonesia-source-compensation`,
   * CL-D2-01's local-compensation prohibition — and its code is read OUT of
   * the highest-sequence pack on disk rather than typed here, so a rename in
   * the fold moves this test with it instead of leaving it quietly stale.
   */
  function highestSequencePack(): { rules?: Array<Record<string, unknown>> } {
    let best: {
      payload: { sequence: number; rules?: Array<Record<string, unknown>> };
      sequence: number;
    } | null = null;
    for (const full of productionPackFiles()) {
      const payload = JSON.parse(fs.readFileSync(full, "utf-8")) as {
        sequence?: unknown;
        rules?: Array<Record<string, unknown>>;
      };
      // A pack without a numeric `sequence` cannot be compared — skip it
      // rather than let it win via a sentinel default.
      if (typeof payload.sequence !== "number") continue;
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
      throw new Error(`no pack under ${PACKS_DIR} had a numeric sequence`);
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

  function firstNoPathReason(code: string) {
    const response = makeVisaOracleResponse("NO_SUPPORTED_PATH");
    response.decision.no_path_reasons[0].code = code;
    const outcome = buildEngineOutcome(response);
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

  function reviewReasonCodesInPack(): string[] {
    const payload = JSON.parse(
      fs.readFileSync(latestProductionPackFile(), "utf-8"),
    ) as { rules?: Array<Record<string, unknown>> };
    const codes = new Set<string>();
    for (const rule of payload.rules ?? []) {
      const effect = rule.effect as Record<string, unknown> | undefined;
      if (
        rule.stage === "HUMAN_REVIEW" &&
        effect &&
        typeof effect.reason_code === "string"
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
  const KNOWN_UNMAPPED_REVIEW_REASON_CODES = [
    // From rulepack-prod-007+ (HUMAN_REVIEW stage):
    "E28B_USD_THRESHOLD_MANUAL_CHECK",
    "E28C_USD_THRESHOLD_AND_INSTRUMENT_CHECK",
    "E28D_USD_THRESHOLD_AND_TURNOVER_CHECK",
    "E28F_IKN_THRESHOLD_MANUAL_CHECK",
    "E33B_EXPERTISE_QUALIFICATION_CHECK",
    "E33G_EXCLUDES_LOCAL_COMPANY_OWNERSHIP",
    // `E33G_INCOME_EVIDENCE_REVIEW` was here from the E5 increment 3 seq-9
    // fold (2026-08-19) until the seq-20 decisiveness fold retired the rule
    // that emitted it: `review.e33g.income-evidence`'s `when` was a
    // byte-for-byte copy of `el.e33g.remote-work`'s, so it vetoed E33G on
    // the product's own success condition and E33G could never be
    // recommended (2026-09-06 investigation §2.3 L3-b). It is removed here,
    // not merely left unmapped, because the test below fails on a gap-list
    // entry naming a code the highest-sequence pack no longer emits.
    "E33_WORK_RANGKAP_KEGIATAN_GATED",
    "GOVT_INVITATION_REQUIRED",
    // Pack-independent (evaluate_path.py):
    "CONFLICTING_IMMIGRATION_STATUS_REVIEW",
    "DECISIVE_PRIMARY_SOURCE_NOT_APPLICABLE",
    "DECISIVE_SOURCE_FRESHNESS_UNKNOWN",
    "DECISIVE_SOURCE_STALE",
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

  it("names every code the current pack + backend can emit, mapped or in the known gap", () => {
    const allRealCodes = [
      ...reviewReasonCodesInPack(),
      ...PACK_INDEPENDENT_REVIEW_REASON_CODES,
    ].sort();
    // Guard the guard: a glob/parse that silently found nothing would make
    // every assertion below vacuously true. 14 pack + 18 pack-independent.
    expect(allRealCodes.length).toBeGreaterThanOrEqual(32);

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
    const staleKeys = Object.keys(REVIEW_REASON_COPY).filter(
      (code) => !allRealCodes.has(code),
    );
    expect(staleKeys).toEqual([]);
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
