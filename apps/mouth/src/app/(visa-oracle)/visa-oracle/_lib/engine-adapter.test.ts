import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";
import {
  NEXT_STEPS,
  OUR_SOURCE_REVIEW_CODES,
  REVIEW_REASON_COPY,
  SUPPORT_REASON_COPY,
  buildEngineOutcome,
} from "./engine-adapter";
import {
  TEST_NOW,
  makeHumanReviewWithEligibleCandidates,
  makeVisaOracleResponse,
} from "./visa-oracle-test-fixture";

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

  /**
   * Cross-lane risk closed 2026-08-25: a synthetic-persona run against the
   * real seq-13 evaluator proved products with no `pricing_key` (e.g. E30,
   * E30E, E30F — the exact three the wizard's decomposed paths-counter
   * classifies as "consultant-routed", never sellable self-service) still
   * come back inside `SUPPORTED_CANDIDATES` with `pricing.status ==
   * "CONTACT_REQUIRED"` — the engine never drops a price-less candidate.
   * A generic "requires contact" line risked reading as self-service to a
   * skimming reader on a card that otherwise looks identical to a priced
   * one. This pins the explicit, WHY-it-needs-contact copy so a future edit
   * can't silently regress back to the vaguer wording.
   */
  it("explains WHY a price-less SUPPORTED_CANDIDATES card needs contact, not just that it does", () => {
    const outcome = buildEngineOutcome(makeVisaOracleResponse());
    expect(outcome.state).toBe("SUPPORTED_CANDIDATES");
    if (outcome.state !== "SUPPORTED_CANDIDATES")
      throw new Error("unexpected state");
    const { price } = outcome.candidates[0];
    if (price.status !== "CONTACT_REQUIRED")
      throw new Error("expected CONTACT_REQUIRED price");
    expect(price.message.en).toBe(
      "This path doesn't have a published all-inclusive price yet — our team will confirm the cost and next steps with you directly.",
    );
    expect(price.message.id).toBe(
      "Jalur ini belum memiliki harga all-inclusive yang dipublikasikan — tim kami akan memastikan biaya dan langkah selanjutnya langsung bersama Anda.",
    );
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

/**
 * Owner ruling #1 (2026-08-25, OWNER-RULINGS-2026-08-25.md §1, verbatim):
 * "sui T2 il consulente è incluso — lo schermo deve dirlo come valore ...
 * non offrirlo come opzione; ... sui T2 il contatto è promessa, non
 * scelta." Before this, `tier` did not appear anywhere in
 * `engine-adapter.ts` (SWITCHBOARD-5-PRICES-AND-TERMS.md's own finding) and
 * every SUPPORTED_CANDIDATES verdict — T1, T2 or T3 alike — rendered the
 * single flat "Choose whether to contact a Bali Zero advisor" line. Watched
 * RED against that flat `NEXT_STEPS` array (reverted locally) before
 * `nextStepsForTier` existed: every test below failed because
 * `outcome.nextSteps[2]` was always the T1 "consented-advice" step
 * regardless of `product_code`.
 */
describe("owner ruling #1 — the next-steps line is tier-aware (2026-08-25)", () => {
  it("keeps the T1 optional phrasing for a self-service product (default fixture product_code C1)", () => {
    const outcome = buildEngineOutcome(makeVisaOracleResponse());
    expect(outcome.state).toBe("SUPPORTED_CANDIDATES");
    if (outcome.state !== "SUPPORTED_CANDIDATES")
      throw new Error("unexpected state");
    expect(outcome.candidates[0].tier).toBe("T1");
    expect(outcome.nextSteps[2]).toEqual({
      id: "consented-advice",
      title: {
        en: "Choose whether to contact a Bali Zero advisor",
        id: "Pilih apakah akan menghubungi konsultan Bali Zero",
      },
    });
  });

  it("states the T2 consultant contact as included and automatic, never as a choice", () => {
    const response = makeVisaOracleResponse();
    response.decision.candidates[0].product_code = "E23";
    response.display.candidates[0].product_code = "E23";
    const outcome = buildEngineOutcome(response);
    expect(outcome.state).toBe("SUPPORTED_CANDIDATES");
    if (outcome.state !== "SUPPORTED_CANDIDATES")
      throw new Error("unexpected state");
    expect(outcome.candidates[0].tier).toBe("T2");
    expect(outcome.nextSteps[2].id).toBe("consultant-included");
    expect(outcome.nextSteps[2].title.en).toBe(
      "A consultant contacts you — included in your purchase",
    );
    expect(outcome.nextSteps[2].title.id).toBe(
      "Konsultan akan menghubungi Anda — sudah termasuk dalam pembelian Anda",
    );
    // Never the T1/optional framing, on either axis.
    expect(outcome.nextSteps[2].id).not.toBe("consented-advice");
    expect(outcome.nextSteps[2].title.en.toLowerCase()).not.toContain(
      "choose whether",
    );
    expect(outcome.nextSteps[2].body?.en).toContain("not an optional extra");
  });

  it("states the T3 consultant contact as the only route", () => {
    const response = makeVisaOracleResponse();
    // E28B (Investor Golden Visa — Company Establishment): 0 eligibility
    // rules, no pricing_key — T3 by construction (TIER-MAP.md).
    response.decision.candidates[0].product_code = "E28B";
    response.display.candidates[0].product_code = "E28B";
    const outcome = buildEngineOutcome(response);
    expect(outcome.state).toBe("SUPPORTED_CANDIDATES");
    if (outcome.state !== "SUPPORTED_CANDIDATES")
      throw new Error("unexpected state");
    expect(outcome.candidates[0].tier).toBe("T3");
    expect(outcome.nextSteps[2].id).toBe("consultant-only-route");
    expect(outcome.nextSteps[2].title.en).toBe(
      "A consultant is the only way to proceed",
    );
    // T3 is also CONTACT_REQUIRED at the price level (2026-08-25 cross-lane
    // fix, tested above) — this pins the two never contradicting each
    // other: both say "talk to a consultant", neither claims self-service.
    expect(outcome.candidates[0].price).toMatchObject({
      status: "CONTACT_REQUIRED",
    });
  });

  it("leaves the first two next-steps items identical across every tier", () => {
    for (const code of ["C1", "E23", "E28B"]) {
      const response = makeVisaOracleResponse();
      response.decision.candidates[0].product_code = code;
      response.display.candidates[0].product_code = code;
      const outcome = buildEngineOutcome(response);
      if (outcome.state !== "SUPPORTED_CANDIDATES")
        throw new Error("unexpected state");
      expect(outcome.nextSteps[0]).toEqual(NEXT_STEPS[0]);
      expect(outcome.nextSteps[1]).toEqual(NEXT_STEPS[1]);
    }
  });

  /**
   * CHANGED 2026-08-25 (ruling #5 blast radius): this loop used to include
   * "HUMAN_REVIEW_REQUIRED" as an unconditional member of "every
   * non-SUPPORTED_CANDIDATES state" — which read as a structural guarantee
   * that state can never carry a candidate. That premise is FALSE in
   * production (RULING5-BLAST-RADIUS-FRONTEND.md): it just happened to be
   * true of every fixture this loop exercised, because the default
   * `makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED")` fixture (like every
   * gold-oracle persona) carries zero candidates. NEEDS_INPUT,
   * NO_SUPPORTED_PATH and TEMPORARILY_UNAVAILABLE stay here unconditionally
   * — their `candidates` type is a fixed empty tuple, they can NEVER carry
   * one. HUMAN_REVIEW_REQUIRED moves to its own test below, spelling out
   * that the guarantee only holds for the zero-candidate case; the
   * non-zero case is pinned by "owner ruling #5" further down.
   */
  it("stays tier-agnostic (unchanged NEXT_STEPS) for every state that can never carry a candidate", () => {
    for (const state of [
      "NEEDS_INPUT",
      "NO_SUPPORTED_PATH",
      "TEMPORARILY_UNAVAILABLE",
    ] as const) {
      const outcome = buildEngineOutcome(makeVisaOracleResponse(state));
      expect(outcome.nextSteps).toEqual(NEXT_STEPS);
    }
  });

  it("stays tier-agnostic for HUMAN_REVIEW_REQUIRED too, but ONLY when it carries zero candidates (the gold-corpus case)", () => {
    const outcome = buildEngineOutcome(
      makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED"),
    );
    expect(outcome.state).toBe("HUMAN_REVIEW_REQUIRED");
    if (outcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    expect(outcome.candidates).toHaveLength(0);
    expect(outcome.nextSteps).toEqual(NEXT_STEPS);
  });

  it("leaves an unmapped product code's tier undefined, never guessed", () => {
    const response = makeVisaOracleResponse();
    response.decision.candidates[0].product_code = "NOT-A-REAL-CODE";
    response.display.candidates[0].product_code = "NOT-A-REAL-CODE";
    const outcome = buildEngineOutcome(response);
    if (outcome.state !== "SUPPORTED_CANDIDATES")
      throw new Error("unexpected state");
    expect(outcome.candidates[0].tier).toBeUndefined();
    // Safe-failure direction: an unmapped code falls back to the T1/optional
    // framing — it never claims "included" or "only route" for a product
    // this map does not (yet) cover.
    expect(outcome.nextSteps[2].id).toBe("consented-advice");
  });
});

/**
 * Owner ruling #5 (2026-08-25, OWNER-RULINGS-2026-08-25.md §5, verbatim):
 * "zero-risultati è vietato come schermata ... per E28B serve una persona,
 * ma con il tuo profilo E28A è supportato: eccolo" + consultant button.
 * "Ogni vicolo cieco diventa un candidato onesto + una mano tesa."
 *
 * Before this change `buildEngineOutcome`'s HUMAN_REVIEW_REQUIRED branch
 * hardcoded `candidates: []` — RULING5-BLAST-RADIUS-FRONTEND.md's site 2:
 * a real T2-eligible visitor who lands here saw the generic, tier-agnostic
 * `NEXT_STEPS` and nothing naming what they already qualify for, exactly
 * like a candidate-less review. Watched RED against the adapter before this
 * fix (reverted locally): every assertion below failed because
 * `outcome.candidates` was always `[]` on this branch and `outcome.nextSteps`
 * was always the flat `NEXT_STEPS` regardless of what the response carried.
 */
describe("owner ruling #5 — HUMAN_REVIEW_REQUIRED can carry honest candidates (2026-08-25)", () => {
  it("carries the products the visitor is genuinely already eligible for, not an empty list", () => {
    const outcome = buildEngineOutcome(makeHumanReviewWithEligibleCandidates());
    expect(outcome.state).toBe("HUMAN_REVIEW_REQUIRED");
    if (outcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    // TWO, never one (constraint (c)) — the measured production case.
    expect(outcome.candidates).toHaveLength(2);
    expect(outcome.candidates.map((c) => c.code)).toEqual(["D12", "E28A"]);
    // The review verdict itself is untouched by carrying candidates
    // (constraint (d)): precedence stays HUMAN_REVIEW_REQUIRED and the
    // review reason is still there.
    expect(outcome.reviewReasons.length).toBeGreaterThan(0);
  });

  it("never resolves a price for a candidate riding along on a review verdict (constraint (a))", () => {
    const outcome = buildEngineOutcome(makeHumanReviewWithEligibleCandidates());
    if (outcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    // Guard the guard: an empty list would make the loop below vacuously
    // true without proving anything.
    expect(outcome.candidates.length).toBeGreaterThan(0);
    for (const candidate of outcome.candidates) {
      expect(candidate.price.status).toBe("CONTACT_REQUIRED");
    }
    // No candidate here is ever purchasable in this response: `quotes` is
    // empty by contract (C1), matching the backend invariant this branch
    // must never violate even now that it carries candidates.
    expect(makeHumanReviewWithEligibleCandidates().decision.quotes).toEqual([]);
  });

  it("names BOTH eligible candidates in the next-steps line, never assuming a singular (constraint (b)+(c))", () => {
    const outcome = buildEngineOutcome(makeHumanReviewWithEligibleCandidates());
    if (outcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    const eligibleStep = outcome.nextSteps[1];
    expect(eligibleStep.body?.en).toContain("Multiple-Entry Business Visa");
    expect(eligibleStep.body?.en).toContain("Investor KITAS (E28A)");
    expect(eligibleStep.body?.en).toContain("D12");
    expect(eligibleStep.body?.en).toContain("E28A");
    // States eligibility plainly — never softened into "you might".
    expect(eligibleStep.body?.en.toLowerCase()).not.toContain("you might");
    expect(eligibleStep.body?.en.toLowerCase()).toContain("already");
    // No price on this line either — "talk to us about cost", never a number.
    expect(eligibleStep.body?.en).not.toMatch(/idr|rp\s?\d|\$\s?\d/i);
    // EN and ID both present (constraint (e)).
    expect(eligibleStep.body?.id).toContain("D12");
    expect(eligibleStep.body?.id).toContain("E28A");
  });

  it("keys the consultant step off the top candidate's own tier, same convention as SUPPORTED_CANDIDATES", () => {
    const outcome = buildEngineOutcome(makeHumanReviewWithEligibleCandidates());
    if (outcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    // D12 and E28A are both T2 in product-tier-map.ts.
    expect(outcome.candidates[0].tier).toBe("T2");
    expect(outcome.nextSteps[2].id).toBe("consultant-included");
  });

  it("stays exactly the tier-agnostic NEXT_STEPS when the branch carries zero candidates", () => {
    const outcome = buildEngineOutcome(
      makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED"),
    );
    if (outcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    expect(outcome.candidates).toHaveLength(0);
    expect(outcome.nextSteps).toEqual(NEXT_STEPS);
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
    // E5 increment 3 seq-9 fold (2026-08-19): review.e33g.income-evidence
    // (OD-1 pattern — the USD 60,000/year income floor is un-modelable, no
    // work-income FactPath exists, see cure-e33g.md). QW-4b (copy-deck
    // approval) still owns writing the actual sentence.
    "E33G_INCOME_EVIDENCE_REVIEW",
    "E33_WORK_RANGKAP_KEGIATAN_GATED",
    "GOVT_INVITATION_REQUIRED",
    // Pack-independent (evaluate_path.py).
    //
    // The six SOURCE holds and MINOR_GUARDIAN_PRIVACY_REVIEW left this list on
    // 2026-08-25: they now have their own copy. They were never a neutral gap —
    // with no entry they rendered GENERIC_REVIEW_REASON, "Some of your answers
    // need a person's judgment", which for a source hold is a FALSE statement
    // about whose problem it is (the applicant answered fine; OUR regulatory
    // source is the thing under re-verification). See the "every system-level
    // review hold explains itself honestly" describe block at the end of this
    // file: it reads those codes out of evaluate_path.py instead of mirroring
    // them here, so a backend rename cannot silently drop one back into the gap.
    "CONFLICTING_IMMIGRATION_STATUS_REVIEW",
    "DISCLOSED_AMBIGUOUS_SPONSOR_REVIEW",
    "DISCLOSED_CRIMINAL_RECORD_REVIEW",
    "DISCLOSED_DIPLOMATIC_PASSPORT_REVIEW",
    "DISCLOSED_HEALTH_CONCERN_REVIEW",
    "DISCLOSED_MULTI_PURPOSE_TRIP_REVIEW",
    "DISCLOSED_PEP_OR_SANCTIONS_REVIEW",
    "DISCLOSED_PRIOR_VISA_REFUSAL_REVIEW",
    "DISCLOSED_SOURCE_OF_FUNDS_REVIEW",
    "DISCLOSED_UNCERTAINTY_REVIEW",
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

describe("every system-level review hold explains itself honestly", () => {
  const HERE = path.dirname(fileURLToPath(import.meta.url));
  const EVALUATE_PATH = path.resolve(
    HERE,
    "../../../../../../..",
    "apps/backend-rag/backend/services/visa_engine/evaluate_path.py",
  );

  /**
   * Cross-language tripwire, deliberately NOT a hardcoded mirror of the
   * backend's constants: it reads the codes out of `evaluate_path.py` itself,
   * so renaming one on the Python side turns this RED instead of silently
   * dropping that hold back onto GENERIC_REVIEW_REASON.
   *
   * Why it matters, measured 2026-08-25: all seven of these holds shipped with
   * no copy at all, so each rendered "Some of your answers need a person's
   * judgment before we can confirm a path." For the six SOURCE holds that
   * sentence is false — the applicant answered fine, OUR regulatory source is
   * the thing under re-verification — and it is the kind of false attribution
   * a regulated advisory funnel must not make. Nothing caught it because a
   * missing key is a silent `??` fallback, never an error.
   *
   * Scope, stated rather than implied: only the `Reason(code=...)` holds
   * raised by the policy ADAPTERS are required to have copy here. The
   * `DisclosedReviewFlag` family maps to codes for which the generic sentence
   * is accurate (they really are about what the applicant disclosed), so they
   * are not forced into the map.
   */
  function systemReviewCodesFromBackend(): string[] {
    const src = fs.readFileSync(EVALUATE_PATH, "utf-8");
    const codes = new Set<string>();
    for (const m of src.matchAll(/\bcode="([A-Z][A-Z0-9_]+)"/g)) {
      const code = m[1];
      // The adapters' own review holds all end in one of these shapes; the
      // file also carries TEMPORARILY_UNAVAILABLE/outage codes, which are a
      // different surface entirely (they never reach REVIEW_REASON_COPY).
      if (
        code.startsWith("DECISIVE_") ||
        code.startsWith("SAFETY_CRITICAL_") ||
        code === "MINOR_GUARDIAN_PRIVACY_REVIEW"
      ) {
        codes.add(code);
      }
    }
    return [...codes].sort();
  }

  it("reads a non-empty set of holds out of the backend (anti-vacuity)", () => {
    const codes = systemReviewCodesFromBackend();
    // Guards the regex itself: if `evaluate_path.py` moves or the literal
    // shape changes, this fails loudly instead of vacuously passing the
    // per-code assertions below over an empty list.
    expect(codes.length).toBeGreaterThanOrEqual(7);
    expect(codes).toContain("MINOR_GUARDIAN_PRIVACY_REVIEW");
  });

  it("gives every one of them its own sentence, never the generic fallback", () => {
    const generic = REVIEW_REASON_COPY.DISCLOSED_ACTIVITY_BOUNDARY_REVIEW;
    for (const code of systemReviewCodesFromBackend()) {
      const copy = REVIEW_REASON_COPY[code];
      expect(copy, `no copy for system review hold ${code}`).toBeDefined();
      expect(copy.en.length).toBeGreaterThan(20);
      expect(copy.id.length).toBeGreaterThan(20);
      // ...and it is really ITS OWN sentence, not a shared placeholder.
      expect(copy.en).not.toBe(generic.en);
    }
  });

  it("never blames the applicant when the fault is our own source", () => {
    for (const code of OUR_SOURCE_REVIEW_CODES) {
      const copy = REVIEW_REASON_COPY[code];
      expect(copy, `no copy for ${code}`).toBeDefined();
      // GUILT: it must say whose problem this actually is.
      expect(copy.en.toLowerCase()).toContain("our source");
      expect(copy.id.toLowerCase()).toContain("sumber kami");
      // INNOCENCE: it must not tell the applicant their answers are at fault.
      expect(copy.en.toLowerCase()).not.toContain("your answers need");
    }
  });
});
