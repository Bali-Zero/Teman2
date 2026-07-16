import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  describeRecommendOutcome,
  parseRecommendResponse,
  recommendVisas,
} from "./api";
import type { QuizAnswers, RecommendResponse } from "./types";

const ANSWERS: QuizAnswers = {
  nationality: "German",
  purpose: "work",
  duration: "long",
  family: "solo",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// ---------------------------------------------------------------------------
// parseRecommendResponse — runtime validation (PR0 W4, round2 spec §6.5)
// ---------------------------------------------------------------------------

describe("parseRecommendResponse", () => {
  it("passes through a well-formed SUPPORTED_CANDIDATES response", () => {
    const raw = {
      success: true,
      session_id: "s1",
      state: "SUPPORTED_CANDIDATES",
      missing_facts: [],
      review_reasons: [],
      visas: [
        {
          visa_name: "Working KITAS",
          category: "kitas_permits",
          price: "18.000.000 IDR",
          duration: "1 year",
          validity: "KITAS",
          notes: "",
          score: 4,
        },
      ],
    };

    const parsed = parseRecommendResponse(raw);
    expect(parsed.state).toBe("SUPPORTED_CANDIDATES");
    expect(parsed.visas).toHaveLength(1);
    expect(parsed.visas[0].visa_name).toBe("Working KITAS");
  });

  it("tolerates absence of state/missing_facts/review_reasons (legacy backend)", () => {
    const raw = {
      success: true,
      session_id: "s1",
      visas: [
        {
          visa_name: "Working KITAS",
          category: "kitas_permits",
          price: "18.000.000 IDR",
          duration: "1 year",
          validity: "KITAS",
          notes: "",
          score: 4,
        },
      ],
    };

    const parsed = parseRecommendResponse(raw);
    expect(parsed.state).toBeUndefined();
    // Legacy shape had no safety invariant — trust visas as before PR0.
    expect(parsed.visas).toHaveLength(1);
  });

  it("defensively empties visas when state is NOT SUPPORTED_CANDIDATES, even if the raw payload disagrees", () => {
    const raw = {
      success: true,
      session_id: "s1",
      state: "NEEDS_INPUT",
      missing_facts: ["nationality"],
      review_reasons: ["low_confidence_match"],
      // A buggy/legacy backend that violates its own invariant — the
      // frontend must not trust this.
      visas: [
        {
          visa_name: "Fabricated Visa",
          category: "x",
          price: "0 IDR",
          duration: "",
          validity: "",
          notes: "",
          score: 0,
        },
      ],
    };

    const parsed = parseRecommendResponse(raw);
    expect(parsed.state).toBe("NEEDS_INPUT");
    expect(parsed.visas).toEqual([]);
    expect(parsed.missing_facts).toEqual(["nationality"]);
  });

  it("drops an unrecognized state value rather than trusting it", () => {
    const raw = {
      success: true,
      session_id: "s1",
      state: "SOME_FUTURE_STATE_WE_DONT_KNOW",
      visas: [
        {
          visa_name: "X",
          category: "x",
          price: "",
          duration: "",
          validity: "",
          notes: "",
          score: 1,
        },
      ],
    };

    const parsed = parseRecommendResponse(raw);
    expect(parsed.state).toBeUndefined();
    expect(parsed.visas).toEqual([]);
  });

  it("filters out malformed visa entries instead of crashing", () => {
    const raw = {
      success: true,
      session_id: "s1",
      state: "SUPPORTED_CANDIDATES",
      visas: [
        {
          visa_name: "Valid Visa",
          category: "x",
          price: "1 IDR",
          duration: "",
          validity: "",
          notes: "",
          score: 1,
        },
        { visa_name: 123 }, // malformed
        null,
        "not an object",
      ],
    };

    const parsed = parseRecommendResponse(raw);
    expect(parsed.visas).toHaveLength(1);
    expect(parsed.visas[0].visa_name).toBe("Valid Visa");
  });

  it("throws on a fundamentally malformed payload rather than silently returning garbage", () => {
    expect(() => parseRecommendResponse(null)).toThrow();
    expect(() => parseRecommendResponse({})).toThrow();
    expect(() => parseRecommendResponse({ success: true })).toThrow();
  });

  // ---------------------------------------------------------------------
  // FIX-3 (Codex red-team P1 #2, garbage candidates): a visa row is only
  // valid with a non-empty `visa_name` AND a finite, non-negative `score`.
  // ---------------------------------------------------------------------

  it("FIX-3 guilt: a row missing visa_name entirely is not a valid candidate", () => {
    const raw = {
      success: true,
      session_id: "s1",
      state: "SUPPORTED_CANDIDATES",
      visas: [{ score: 2 }],
    };

    const parsed = parseRecommendResponse(raw);
    expect(parsed.visas).toEqual([]);
  });

  it("FIX-3 guilt: a row with an empty-string visa_name is not a valid candidate", () => {
    const raw = {
      success: true,
      session_id: "s1",
      state: "SUPPORTED_CANDIDATES",
      visas: [
        {
          visa_name: "   ",
          category: "x",
          price: "1 IDR",
          duration: "",
          validity: "",
          notes: "",
          score: 2,
        },
      ],
    };

    const parsed = parseRecommendResponse(raw);
    expect(parsed.visas).toEqual([]);
  });

  it("FIX-3 guilt: a row with a negative score is not a valid candidate", () => {
    const raw = {
      success: true,
      session_id: "s1",
      state: "SUPPORTED_CANDIDATES",
      visas: [
        {
          visa_name: "Suspicious Visa",
          category: "x",
          price: "1 IDR",
          duration: "",
          validity: "",
          notes: "",
          score: -1,
        },
      ],
    };

    const parsed = parseRecommendResponse(raw);
    expect(parsed.visas).toEqual([]);
  });

  it("FIX-3 guilt: a row with a non-finite score (NaN/Infinity) is not a valid candidate", () => {
    const raw = {
      success: true,
      session_id: "s1",
      state: "SUPPORTED_CANDIDATES",
      visas: [
        {
          visa_name: "NaN Visa",
          category: "x",
          price: "1 IDR",
          duration: "",
          validity: "",
          notes: "",
          score: NaN,
        },
        {
          visa_name: "Infinity Visa",
          category: "x",
          price: "1 IDR",
          duration: "",
          validity: "",
          notes: "",
          score: Infinity,
        },
      ],
    };

    const parsed = parseRecommendResponse(raw);
    expect(parsed.visas).toEqual([]);
  });

  it("FIX-3 innocence: a well-formed row with score 0 IS a valid candidate (0 is not negative)", () => {
    const raw = {
      success: true,
      session_id: "s1",
      state: "SUPPORTED_CANDIDATES",
      visas: [
        {
          visa_name: "Zero Score Visa",
          category: "x",
          price: "1 IDR",
          duration: "",
          validity: "",
          notes: "",
          score: 0,
        },
      ],
    };

    const parsed = parseRecommendResponse(raw);
    expect(parsed.visas).toHaveLength(1);
  });

  it("FIX-8 (b): SUPPORTED_CANDIDATES with an all-invalid visas array ends up empty, never trusted", () => {
    const raw = {
      success: true,
      session_id: "s1",
      state: "SUPPORTED_CANDIDATES",
      visas: [
        { score: 2 },
        { visa_name: "", score: 5 },
        { visa_name: "X", score: -3 },
      ],
    };

    const parsed = parseRecommendResponse(raw);
    expect(parsed.state).toBe("SUPPORTED_CANDIDATES");
    expect(parsed.visas).toEqual([]);
  });

  it("FIX-8 (c): passes through success=false unchanged (legacy no-state path)", () => {
    const raw = {
      success: false,
      session_id: "s1",
      visas: [],
    };

    const parsed = parseRecommendResponse(raw);
    expect(parsed.success).toBe(false);
    expect(parsed.state).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// recommendVisas — end-to-end fetch + parse
// ---------------------------------------------------------------------------

describe("recommendVisas", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("never crashes and never fabricates a candidate on an empty-candidates response", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        session_id: "s1",
        state: "NEEDS_INPUT",
        missing_facts: [],
        review_reasons: ["low_confidence_match"],
        visas: [],
      }),
    );

    const result = await recommendVisas(ANSWERS);
    expect(result.state).toBe("NEEDS_INPUT");
    expect(result.visas).toEqual([]);
  });

  it("handles TEMPORARILY_UNAVAILABLE without throwing", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        session_id: "s1",
        state: "TEMPORARILY_UNAVAILABLE",
        missing_facts: [],
        review_reasons: ["catalog_no_candidates"],
        visas: [],
      }),
    );

    const result = await recommendVisas(ANSWERS);
    expect(result.state).toBe("TEMPORARILY_UNAVAILABLE");
    expect(result.visas).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// describeRecommendOutcome — honest empty-candidates rendering (PR0 W4)
// ---------------------------------------------------------------------------

describe("describeRecommendOutcome", () => {
  function response(overrides: Partial<RecommendResponse>): RecommendResponse {
    return {
      success: true,
      session_id: "s1",
      visas: [],
      ...overrides,
    };
  }

  it("never fabricates a candidate: with visas present, describes a real match", () => {
    const outcome = describeRecommendOutcome(
      response({
        state: "SUPPORTED_CANDIDATES",
        visas: [
          {
            visa_name: "Working KITAS",
            category: "x",
            price: "1 IDR",
            duration: "",
            validity: "",
            notes: "",
            score: 4,
          },
        ],
      }),
    );
    expect(outcome.showWhatsAppEscape).toBe(false);
    expect(outcome.headline).not.toMatch(/error|crash|undefined/i);
  });

  it("NEEDS_INPUT with empty visas renders an honest 'need more info' outcome with an escape hatch", () => {
    const outcome = describeRecommendOutcome(
      response({
        state: "NEEDS_INPUT",
        missing_facts: ["nationality"],
        visas: [],
      }),
    );
    expect(outcome.showWhatsAppEscape).toBe(true);
    expect(outcome.detail).toContain("nationality");
  });

  it("HUMAN_REVIEW_REQUIRED renders an honest 'human specialist' outcome", () => {
    const outcome = describeRecommendOutcome(
      response({ state: "HUMAN_REVIEW_REQUIRED", visas: [] }),
    );
    expect(outcome.showWhatsAppEscape).toBe(true);
    expect(outcome.headline.toLowerCase()).toContain("human");
  });

  it("NO_SUPPORTED_PATH renders an honest 'human specialist' outcome", () => {
    const outcome = describeRecommendOutcome(
      response({ state: "NO_SUPPORTED_PATH", visas: [] }),
    );
    expect(outcome.showWhatsAppEscape).toBe(true);
  });

  it("TEMPORARILY_UNAVAILABLE renders an honest degraded outcome, never a crash", () => {
    const outcome = describeRecommendOutcome(
      response({ state: "TEMPORARILY_UNAVAILABLE", visas: [] }),
    );
    expect(outcome.showWhatsAppEscape).toBe(true);
    expect(outcome.headline).toBeTruthy();
  });

  it("absent state (legacy) with empty visas still renders honestly, never undefined", () => {
    const outcome = describeRecommendOutcome(
      response({ state: undefined, visas: [] }),
    );
    expect(outcome.headline).toBeTruthy();
    expect(outcome.detail).toBeTruthy();
    expect(outcome.showWhatsAppEscape).toBe(true);
  });

  // ---------------------------------------------------------------------
  // FIX-8 (Codex red-team P2 #7, success semantics + parser contradictions)
  // ---------------------------------------------------------------------

  it("FIX-8 (a) guilt: success=false always yields an error outcome, never 'here's what fits'", () => {
    const outcome = describeRecommendOutcome(
      response({
        success: false,
        state: "TEMPORARILY_UNAVAILABLE",
        visas: [],
      }),
    );
    expect(outcome.headline).not.toMatch(/here's what fits/i);
    expect(outcome.showWhatsAppEscape).toBe(true);
  });

  it("FIX-8 (a) guilt: success=false wins even when state/visas look like a clean match", () => {
    // A contradictory payload (should never happen from a well-behaved
    // backend, but the frontend must not trust the label alone) — success
    // is a stronger signal than a non-empty visas array.
    const outcome = describeRecommendOutcome(
      response({
        success: false,
        state: "SUPPORTED_CANDIDATES",
        visas: [
          {
            visa_name: "Working KITAS",
            category: "x",
            price: "1 IDR",
            duration: "",
            validity: "",
            notes: "",
            score: 4,
          },
        ],
      }),
    );
    expect(outcome.headline).not.toMatch(/here's what fits/i);
    expect(outcome.showWhatsAppEscape).toBe(true);
  });

  it("FIX-8 (a) innocence: success=true with a real match still renders 'here's what fits'", () => {
    const outcome = describeRecommendOutcome(
      response({
        success: true,
        state: "SUPPORTED_CANDIDATES",
        visas: [
          {
            visa_name: "Working KITAS",
            category: "x",
            price: "1 IDR",
            duration: "",
            validity: "",
            notes: "",
            score: 4,
          },
        ],
      }),
    );
    expect(outcome.headline).toMatch(/here's what fits/i);
    expect(outcome.showWhatsAppEscape).toBe(false);
  });

  it("FIX-8 (b) guilt: SUPPORTED_CANDIDATES with empty visas downgrades to a human-review outcome, never a fabricated match", () => {
    const outcome = describeRecommendOutcome(
      response({ success: true, state: "SUPPORTED_CANDIDATES", visas: [] }),
    );
    expect(outcome.headline).not.toMatch(/here's what fits/i);
    expect(outcome.headline.toLowerCase()).toContain("human");
    expect(outcome.showWhatsAppEscape).toBe(true);
  });
});
