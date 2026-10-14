import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { afterEach, describe, expect, it, vi } from "vitest";

const emitVisaOracleTelemetry = vi.hoisted(() => vi.fn());
vi.mock("./telemetry", () => ({ emitVisaOracleTelemetry }));

import {
  GENERIC_NOTICE_CONDITION,
  NOTICE_CONDITION_COPY,
  PROHIBITED_ACTIVITY_COPY,
  PROHIBITED_ACTIVITY_PRODUCT_COPY,
  REVIEW_REASON_ELEMENTS,
  REVIEW_REASON_COPY,
  RETIRED_NEVER_EMITTED_SUPPORT_REASON_KEYS,
  RETIRED_REPLAYABLE_SUPPORT_REASON_KEYS,
  RETIRED_SUPPORT_REASON_KEYS,
  SECOND_HOME_DEPOSIT_THRESHOLD_USD,
  SECOND_HOME_PROPERTY_THRESHOLD_USD,
  SECOND_HOME_STUDIO_REVIEW_REASON_CODE,
  SOURCELESS_NO_PATH_CODES,
  STAY_PERMIT_LONGER_STAY_COPY,
  STAY_PERMIT_RENEWAL_COPY,
  SUPPORT_REASON_COPY,
  B1_MAX_STAY_DAYS,
  C1_MAX_STAY_DAYS,
  C2_MAX_STAY_DAYS,
  C6_MAX_STAY_DAYS,
  D1_PROOF_OF_FUNDS_USD,
  D2_PROOF_OF_FUNDS_USD,
  D12_PROOF_OF_FUNDS_USD,
  E33G_ANNUAL_INCOME_THRESHOLD_USD,
  E33E_DEPOSIT_THRESHOLD_USD,
  E33F_E33E_DEPOSIT_NOTE_CODE,
  RETIREMENT_INCOME_THRESHOLD_USD,
  buildEngineOutcome,
  e33fE33eDepositNote,
  isSecondHomeStudioOnly,
  nextStepsFor,
} from "./engine-adapter";
import {
  TEST_NOW,
  TEST_SOURCE_ID,
  makeVisaOracleResponse,
} from "./visa-oracle-test-fixture";
import { translate, type I18nKey } from "./i18n";
import { QUESTIONS, type OracleFacts } from "./tree";
import {
  parseVisaOracleEvaluateResponse,
  VisaOracleResponseError,
} from "./engine-response";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PACKS_DIR = path.resolve(
  HERE,
  "../../../../../../..",
  "apps/backend-rag/backend/services/visa_engine/contracts/packs",
);

interface SignedPackProduct {
  product_code: string;
  names: { en: string; id: string };
  sponsor_types: string[];
}

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
function highestSequencePack(): {
  rules?: Array<Record<string, unknown>>;
  products?: SignedPackProduct[];
} {
  let best: {
    payload: {
      sequence: number;
      rules?: Array<Record<string, unknown>>;
      products?: SignedPackProduct[];
    };
    sequence: number;
  } | null = null;
  for (const full of signedProductionPackFiles()) {
    const envelope = JSON.parse(fs.readFileSync(full, "utf-8")) as {
      payload?: {
        sequence?: unknown;
        rules?: Array<Record<string, unknown>>;
        products?: SignedPackProduct[];
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
          products?: SignedPackProduct[];
        },
        sequence: payload.sequence,
      };
    }
  }
  if (best === null) {
    throw new Error(`no signed pack under ${PACKS_DIR} had a numeric sequence`);
  }
  return best.payload;
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

  it("carries the working-day window into the timeline, and omits it from an older backend", () => {
    for (const withWindow of [true, false]) {
      const response = makeVisaOracleResponse();
      Object.assign(response.display.candidates[0].processing_timeline, {
        status: "AVAILABLE",
        reason_code: "BALI_ZERO_TYPICAL_PROCESSING_TIME",
        anchor_date: "2026-10-09",
        estimated_completion_from: "2026-10-20",
        estimated_completion_to: "2026-10-23",
        ...(withWindow ? { working_days_min: 7, working_days_max: 10 } : {}),
      });
      const outcome = buildEngineOutcome(response);
      if (outcome.state !== "SUPPORTED_CANDIDATES")
        throw new Error("unexpected state");
      const timeline = outcome.candidates[0].timeline;
      expect(timeline).toMatchObject({
        status: "AVAILABLE",
        earliestDateIso: "2026-10-20",
        latestDateIso: "2026-10-23",
      });
      expect("workingDaysMin" in timeline).toBe(withWindow);
      if (withWindow) {
        expect(timeline).toMatchObject({
          workingDaysMin: 7,
          workingDaysMax: 10,
        });
      }
    }
  });

  it("uses only processing/pricing/document assessments, never stay policy or mock content", () => {
    const outcome = buildEngineOutcome(makeVisaOracleResponse());
    expect(outcome.state).toBe("SUPPORTED_CANDIDATES");
    if (outcome.state !== "SUPPORTED_CANDIDATES")
      throw new Error("unexpected state");
    const candidate = outcome.candidates[0];
    expect(candidate.timeline).toMatchObject({ status: "UNAVAILABLE" });
    expect(candidate.price).toEqual({
      status: "CONTACT_REQUIRED",
      message: {
        en: "Price on consultation. You can ask a Bali Zero advisor.",
        id: "Harga melalui konsultasi. Anda dapat bertanya kepada konsultan Bali Zero.",
      },
    });
    expect(candidate.documents).toEqual([]);
    expect(JSON.stringify(candidate)).not.toContain("60 days");
  });

  it.each([
    "PRICING_KEY_NOT_CONFIGURED",
    "PRICING_ROW_MISSING",
    "PRICING_ROW_NOT_EXACT_AMOUNT",
  ])(
    "CONTACT_REQUIRED for %s never claims what that reason code does not prove",
    (reasonCode) => {
      // The backend (pricing_adapter.py resolve_pricing_key) returns
      // CONTACT_REQUIRED for a product left without a pricing key AND for a
      // catalogue row that is missing or has no exact amount. "No fixed
      // price is published" is true for the first only, so the one sentence
      // shown for all three says no more than "price on consultation".
      const response = makeVisaOracleResponse();
      response.display.candidates[0].pricing = {
        ...response.display.candidates[0].pricing,
        status: "CONTACT_REQUIRED",
        reason_code: reasonCode,
      };
      const outcome = buildEngineOutcome(response);
      if (outcome.state !== "SUPPORTED_CANDIDATES")
        throw new Error("unexpected state");
      const candidatePrice = outcome.candidates[0].price;
      expect(candidatePrice.status).toBe("CONTACT_REQUIRED");
      if (candidatePrice.status !== "CONTACT_REQUIRED")
        throw new Error("unexpected price status");
      expect(candidatePrice.message.en).not.toMatch(
        /no fixed price|published/i,
      );
      expect(candidatePrice.message.id).not.toMatch(
        /harga tetap|dipublikasikan/i,
      );
      expect(candidatePrice.message.en).toMatch(/Price on consultation/);
      expect(candidatePrice.message.id).toMatch(/Harga melalui konsultasi/);
    },
  );

  it("keeps E33A/B/C consultation copy honest and pins the E33A central-government exclusion in both languages", () => {
    expect(SUPPORT_REASON_COPY.E33A_GOVERNMENT_INVITATION_ELIGIBLE).toEqual({
      en: "You told us you hold a written invitation from an Indonesian central-government body for your special expertise — the Second Home Visa — Special-Expertise Government Invitation (E33A). This government-invitation route is handled with a Bali Zero advisor.",
      id: "Anda menyampaikan bahwa Anda memiliki undangan tertulis dari instansi pemerintah pusat Indonesia atas keahlian khusus Anda — Visa Rumah Kedua Tenaga Ahli Undangan Pemerintah (E33A). Jalur undangan pemerintah ini ditangani bersama konsultan Bali Zero.",
    });
    expect(SUPPORT_REASON_COPY.E33B_GOVERNMENT_COLLABORATION_ELIGIBLE).toEqual({
      en: "You told us you have a confirmed collaboration commitment with an Indonesian government body or institution based on your special expertise — the Second Home Golden Visa — Special-Expertise Collaboration (E33B). This collaboration route is handled with a Bali Zero advisor.",
      id: "Anda menyampaikan bahwa Anda memiliki komitmen kolaborasi yang terkonfirmasi dengan instansi atau lembaga pemerintah Indonesia berdasarkan keahlian khusus Anda — Visa Rumah Kedua Kolaborasi Keahlian Khusus (E33B). Jalur kolaborasi ini ditangani bersama konsultan Bali Zero.",
    });
    expect(SUPPORT_REASON_COPY.E33C_WORLD_FIGURE_INVITATION_ELIGIBLE).toEqual({
      en: "You told us you have an invitation letter from an Indonesian central-government agency inviting you as a world figure — the Second Home Golden Visa — World-Figure Government Invitation (E33C). This government-invitation route is handled with a Bali Zero advisor.",
      id: "Anda menyampaikan bahwa Anda memiliki surat undangan dari instansi pemerintah pusat Indonesia yang mengundang Anda sebagai tokoh dunia — Visa Rumah Kedua Tokoh Dunia Undangan Pemerintah (E33C). Jalur undangan pemerintah ini ditangani bersama konsultan Bali Zero.",
    });
    expect(SUPPORT_REASON_COPY.E33A_SPONSOR_NOT_GOVERNMENT).toEqual({
      en: "The Second Home Visa — Special-Expertise Government Invitation (E33A) is sponsored only by an Indonesian central-government body, and you did not name one as your sponsor.",
      id: "Visa Rumah Kedua Tenaga Ahli Undangan Pemerintah (E33A) hanya dijamin oleh instansi pemerintah pusat Indonesia, dan Anda tidak menyebutkan instansi pemerintah pusat sebagai penjamin Anda.",
    });
    expect(SUPPORT_REASON_COPY.E33B_SPONSOR_NOT_GOVERNMENT_OR_NONE).toEqual({
      en: "The Second Home Golden Visa — Special-Expertise Collaboration (E33B) is applied for without a sponsor, and you named a sponsor for your stay.",
      id: "Visa Rumah Kedua Kolaborasi Keahlian Khusus (E33B) diajukan tanpa penjamin, sedangkan Anda menyebutkan penjamin untuk masa tinggal Anda.",
    });
    expect(SUPPORT_REASON_COPY.E33C_SPONSOR_NOT_GOVERNMENT_OR_NONE).toEqual({
      en: "The Second Home Golden Visa — World-Figure Government Invitation (E33C) is sponsored only by an Indonesian central-government body, and you did not name one as your sponsor.",
      id: "Visa Rumah Kedua Tokoh Dunia Undangan Pemerintah (E33C) hanya dijamin oleh instansi pemerintah pusat Indonesia, dan Anda tidak menyebutkan instansi pemerintah pusat sebagai penjamin Anda.",
    });
  });

  it("states the E33G annual-income exclusion threshold in both languages", () => {
    expect(E33G_ANNUAL_INCOME_THRESHOLD_USD).toBe(60_000);
    expect(SUPPORT_REASON_COPY.E33G_INCOME_BELOW_THRESHOLD).toEqual({
      en: "The Remote Worker visa (E33G) needs a salary or income of at least USD 60,000 a year; the yearly figure you gave is below it.",
      id: "Visa Rumah Kedua Pekerja Jarak Jauh (E33G) memerlukan gaji atau penghasilan minimal USD 60.000 per tahun; angka tahunan yang Anda berikan berada di bawah batas tersebut.",
    });
  });

  it("states the E33G remote-work support threshold in both languages", () => {
    const threshold = gteThresholdInPack(
      "el.e33g.remote-work",
      "work.annual_foreign_income_usd",
    );
    expect(SUPPORT_REASON_COPY.REMOTE_WORK_ELIGIBLE).toEqual({
      en: "You work remotely for a non-Indonesian employer, serve no Indonesian clients, take no Indonesian-source compensation, and have a salary or income of USD 60,000 or more a year.",
      id: "Anda bekerja jarak jauh untuk pemberi kerja non-Indonesia, tidak melayani klien Indonesia, tidak menerima kompensasi dari sumber Indonesia, dan memiliki gaji atau penghasilan minimal USD 60.000 per tahun.",
    });
    expect(SUPPORT_REASON_COPY.REMOTE_WORK_ELIGIBLE.en).toContain(
      `USD ${threshold.toLocaleString("en-US")}`,
    );
    expect(SUPPORT_REASON_COPY.REMOTE_WORK_ELIGIBLE.id).toContain(
      `USD ${threshold.toLocaleString("id-ID")}`,
    );
    expect(SUPPORT_REASON_COPY.REMOTE_WORK_ELIGIBLE.en).toContain(
      "salary or income",
    );
    expect(SUPPORT_REASON_COPY.REMOTE_WORK_ELIGIBLE.id).toContain(
      "gaji atau penghasilan",
    );
  });

  it("writes the three seq-29 exclusion sentences in both languages, each naming its product and its figure", () => {
    const copy = SUPPORT_REASON_COPY;
    for (const [code, product] of [
      ["E31D_REQ_SPONSOR_INDONESIAN", "(E31D)"],
      ["E31J_REQ_UNDER_18", "(E31J)"],
      ["E31J_REQ_UNMARRIED", "(E31J)"],
    ] as const) {
      expect(copy[code].en).toContain(product);
      expect(copy[code].id).toContain(product);
      expect(copy[code].en).not.toBe(copy[code].id);
    }
    expect(copy.E31J_REQ_UNDER_18.en).toContain("under 18");
    expect(copy.E31J_REQ_UNDER_18.id).toContain("18 tahun");
    expect(copy.E31J_REQ_UNMARRIED.en).toContain("never married");
    expect(copy.E31J_REQ_UNMARRIED.id).toContain("belum menikah");
    const other = REVIEW_REASON_COPY.E31J_MARITAL_STATUS_OTHER_REVIEW;
    expect(other.en).toContain("(E31J)");
    expect(other.id).toContain("(E31J)");
    expect(other.en).toContain("another status");
    expect(other.id).toContain("status lain");
    expect(other.en).not.toBe(other.id);
    // the E31E sentences stay the E31E sentences
    expect(copy.REQ_UNDER_18.en).toContain("(E31E)");
    expect(copy.E31J_REQ_UNDER_18.en).not.toContain("(E31E)");
  });

  it("never offers a combined property-and-deposit route in Second Home or E33 copy", () => {
    const copy = REVIEW_REASON_COPY[SECOND_HOME_STUDIO_REVIEW_REASON_CODE];
    expect(copy.en).not.toMatch(/combination/i);
    expect(copy.id).not.toMatch(/kombinasi/i);
    const combined = /combination|combined|both together|split|mix/i;
    const gabungan = /kombinasi|gabungan|campuran/i;
    const entries = [
      ...Object.entries(REVIEW_REASON_COPY),
      ...Object.entries(SUPPORT_REASON_COPY),
    ].filter(([code]) => /^(SECOND_HOME_|E33)/.test(code));
    expect(entries.length).toBeGreaterThan(3);
    for (const [code, value] of entries) {
      expect([code, value.en]).not.toEqual([
        code,
        expect.stringMatching(combined),
      ]);
      expect([code, value.id]).not.toEqual([
        code,
        expect.stringMatching(gabungan),
      ]);
    }
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
    response.decision.review_reasons[0].code =
      "DISCLOSED_CRIMINAL_RECORD_REVIEW";

    const outcome = buildEngineOutcome(response);
    expect(outcome.state).toBe("HUMAN_REVIEW_REQUIRED");
    if (outcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    const message = outcome.reviewReasons[0].message;
    expect(message.en).toMatch(/criminal record/i);
    expect(message.id).toMatch(/catatan kriminal/i);
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

  it("throws for an unmapped review-reason code outside production", () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    response.decision.review_reasons[0].code = "SOME_FUTURE_RULE_CODE";
    expect(() => buildEngineOutcome(response)).toThrow(
      new VisaOracleResponseError("RESPONSE_INVARIANT"),
    );
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

  // PR-M (owner ruling 2026-09-27): the retirement branch asks the E33F-only
  // penjamin sibling, so `family.sponsor_confirmed` is now collected by THREE
  // questions. A retiree reaches the penjamin wording — never the family one.
  it("innocence: a retiree is asked the penjamin question their own walk reaches, not the family one", () => {
    const response = makeVisaOracleResponse("NEEDS_INPUT");
    response.decision.missing_facts = ["family.sponsor_confirmed"];
    const outcome = buildEngineOutcome(response, {
      facts: {
        in_indonesia: "no",
        category: "retirement",
        retirement_basis: "passive_income",
      },
      editableQuestionIds: ["category", "retirement_basis"],
    });
    if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
    expect(outcome.missingInputs[0]).toMatchObject({
      questionId: "retirement_penjamin_confirmed",
      followUp: true,
    });
    expect(outcome.missingInputs[0].message.en).toMatch(/penjamin/i);
    expect(outcome.missingInputs[0].message.en).not.toMatch(/family/i);
  });

  it("innocence: an already-answered penjamin question is a plain edit; family and D12 applicants never reach it", () => {
    const edit = makeVisaOracleResponse("NEEDS_INPUT");
    edit.decision.missing_facts = ["family.sponsor_confirmed"];
    const editOutcome = buildEngineOutcome(edit, {
      facts: {
        in_indonesia: "no",
        category: "retirement",
        retirement_basis: "passive_income",
        retirement_penjamin_confirmed: "no",
      },
      editableQuestionIds: [
        "category",
        "retirement_basis",
        "retirement_penjamin_confirmed",
      ],
    });
    if (editOutcome.state !== "NEEDS_INPUT")
      throw new Error("unexpected state");
    expect(editOutcome.missingInputs[0].questionId).toBe(
      "retirement_penjamin_confirmed",
    );
    expect(editOutcome.missingInputs[0].followUp).toBeUndefined();

    const otherBranches: OracleFacts[] = [
      { in_indonesia: "no", category: "family", family_relation: "SPOUSE" },
      {
        in_indonesia: "no",
        category: "business",
        business_activity: "exploring",
      },
    ];
    for (const facts of otherBranches) {
      const response = makeVisaOracleResponse("NEEDS_INPUT");
      response.decision.missing_facts = ["family.sponsor_confirmed"];
      const outcome = buildEngineOutcome(response, {
        facts,
        editableQuestionIds: ["category"],
      });
      if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
      expect(outcome.missingInputs[0].questionId).not.toBe(
        "retirement_penjamin_confirmed",
      );
    }
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

// Slice A3'-M: the mouth reads a sourceless named dead end before any
// backend sends one. `SOURCELESS_NO_PATH_CODES` narrows the usual
// decisive-ref invariant to exactly the one code no rule in the signed
// pack could ever cite a source for.
describe("Slice A3'-M: a sourceless named dead end (M1, M2)", () => {
  function noPathOutcomeFor(code: string, sourceRefs: readonly string[]) {
    const response = makeVisaOracleResponse("NO_SUPPORTED_PATH");
    response.decision.no_path_reasons = [
      {
        code,
        rule_ids: ["system.disclosed-no-path.activity-boundary"],
        source_refs: [...sourceRefs],
      },
    ];
    return buildEngineOutcome(response);
  }

  it("names a sourceless dead end instead of throwing RESPONSE_INVARIANT (M1)", () => {
    const outcome = noPathOutcomeFor("DISCLOSED_ACTIVITY_BOUNDARY_NO_PATH", []);
    expect(outcome.state).toBe("NO_SUPPORTED_PATH");
    if (outcome.state !== "NO_SUPPORTED_PATH")
      throw new Error("unexpected state");
    expect(outcome.noPathReasons[0].message).toEqual(
      SUPPORT_REASON_COPY.DISCLOSED_ACTIVITY_BOUNDARY_NO_PATH,
    );
    expect(outcome.noPathReasons[0].sourceIds).toEqual([]);
    expect(outcome.alternatives).toEqual([]);
  });

  it("innocence: an unlisted code with empty source_refs still throws RESPONSE_INVARIANT (M1)", () => {
    expect(() => noPathOutcomeFor("NOT_A_SYSTEM_CODE", [])).toThrow(
      new VisaOracleResponseError("RESPONSE_INVARIANT"),
    );
  });

  it("innocence: the listed code with a non-decisive ref still throws RESPONSE_INVARIANT (M1)", () => {
    expect(() =>
      noPathOutcomeFor("DISCLOSED_ACTIVITY_BOUNDARY_NO_PATH", [
        "not-a-known-source-id",
      ]),
    ).toThrow(new VisaOracleResponseError("RESPONSE_INVARIANT"));
  });

  it("guards the guard: every SOURCELESS_NO_PATH_CODES entry has SUPPORT_REASON_COPY (M2)", () => {
    const missing = [...SOURCELESS_NO_PATH_CODES].filter(
      (code) => !(code in SUPPORT_REASON_COPY),
    );
    expect(missing).toEqual([]);
  });

  // Slice A3'-B (backend-side counterpart of M2): the coupled test named in
  // the PR body, so it runs on both A3'-0 (backend) and mouth PRs. M2 above
  // only proves this module's OWN exemption set is internally consistent
  // (every SOURCELESS_NO_PATH_CODES entry has copy); it says nothing about
  // whether that set still matches what the backend actually derives a
  // dead end from. This reads `evaluate_path.py`'s
  // `_DISCLOSED_NO_PATH_REASON_CODES` — the ONE source of truth for which
  // codes `_apply_disclosed_review_flags` can emit as a sourceless dead
  // end — so a backend rename that forgets the mouth is a red HERE, not a
  // silent `RESPONSE_INVARIANT` discovered live.
  it("Slice A3'-B: every backend _DISCLOSED_NO_PATH_REASON_CODES value is SOURCELESS_NO_PATH_CODES and SUPPORT_REASON_COPY (B8)", () => {
    const EVALUATE_PATH = path.resolve(
      path.dirname(fileURLToPath(import.meta.url)),
      "../../../../../../..",
      "apps/backend-rag/backend/services/visa_engine/evaluate_path.py",
    );
    const evaluatePathText = fs.readFileSync(EVALUATE_PATH, "utf-8");
    const start = evaluatePathText.indexOf(
      "_DISCLOSED_NO_PATH_REASON_CODES: MappingProxyType",
    );
    if (start < 0) {
      throw new Error(
        "could not find _DISCLOSED_NO_PATH_REASON_CODES in evaluate_path.py",
      );
    }
    const end = evaluatePathText.indexOf("\n)", start);
    if (end < 0) {
      throw new Error(
        "could not isolate the _DISCLOSED_NO_PATH_REASON_CODES block",
      );
    }
    const codes =
      evaluatePathText
        .slice(start, end)
        .match(/"[A-Z][A-Z0-9_]*"/g)
        ?.map((code) => code.slice(1, -1)) ?? [];
    // Guard the guard (cicatrix family #3): an empty slice would make every
    // assertion below vacuously true.
    expect(codes.length).toBeGreaterThan(0);
    for (const code of codes) {
      expect(
        SOURCELESS_NO_PATH_CODES.has(code),
        `${code}: in evaluate_path.py's _DISCLOSED_NO_PATH_REASON_CODES but ` +
          "not in SOURCELESS_NO_PATH_CODES — the mouth would throw " +
          "RESPONSE_INVARIANT on a real dead end carrying this code",
      ).toBe(true);
      expect(
        code in SUPPORT_REASON_COPY,
        `${code}: in evaluate_path.py's _DISCLOSED_NO_PATH_REASON_CODES but ` +
          "has no SUPPORT_REASON_COPY entry — the mouth has no sentence to render for it",
      ).toBe(true);
    }
  });

  // The CTA the dead end's copy quotes is OracleShell.tsx's OWN consultant
  // toggle label — read from its source text, never retyped, so a rename
  // there cannot silently orphan the quote.
  const ORACLE_SHELL_PATH = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../_components/OracleShell.tsx",
  );

  function oracleShellConsultantLabels(): { en: string; id: string } {
    const src = fs.readFileSync(ORACLE_SHELL_PATH, "utf-8");
    const marker = "const SESSION_COPY = {";
    const start = src.indexOf(marker);
    if (start === -1) {
      throw new Error(
        `${marker} not found in ${ORACLE_SHELL_PATH} — SESSION_COPY renamed or moved`,
      );
    }
    const enStart = src.indexOf("en: {", start);
    const idStart = src.indexOf("id: {", enStart);
    const idBlockEnd = src.indexOf("\n  },", idStart);
    if (enStart === -1 || idStart === -1 || idBlockEnd === -1) {
      throw new Error(
        `en/id blocks not found in SESSION_COPY (${ORACLE_SHELL_PATH})`,
      );
    }
    const enMatch = /consultant:\s*"([^"]+)"/.exec(src.slice(enStart, idStart));
    const idMatch = /consultant:\s*"([^"]+)"/.exec(
      src.slice(idStart, idBlockEnd),
    );
    if (!enMatch || !idMatch) {
      throw new Error(
        `consultant label not found in SESSION_COPY (${ORACLE_SHELL_PATH})`,
      );
    }
    return { en: enMatch[1], id: idMatch[1] };
  }

  it("quotes OracleShell's own consultant CTA label verbatim, read from its source text (M2)", () => {
    const labels = oracleShellConsultantLabels();
    const copy = SUPPORT_REASON_COPY.DISCLOSED_ACTIVITY_BOUNDARY_NO_PATH;
    expect(copy.en).toContain(labels.en);
    expect(copy.id).toContain(labels.id);
  });
});

describe("support reasons are sentences, not machine codes", () => {
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

  it("never prints a raw code for an unmapped reason", () => {
    // A client must not read a machine code; the unmapped fallback is a
    // plain sentence.
    const copy = firstReasonEn("SOMETHING_NEW_FROM_A_FUTURE_PACK");
    expect(copy).toBe("Confirmed by the rules for this visa.");
    expect(copy).not.toContain("SOMETHING_NEW_FROM_A_FUTURE_PACK");
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
   * Slice A8-2: `highestSequencePack()` reads signed envelopes, but the pack
   * whose copy must exist BEFORE signing is the highest-sequence SOURCE pack
   * — the flat shape (`sequence` and `rules` are top-level, no `.payload`
   * wrapper, unlike the signed envelope).
   */
  function highestSequenceSourcePack(): {
    sequence: number;
    rules?: Array<Record<string, unknown>>;
  } {
    let best: {
      pack: { sequence: number; rules?: Array<Record<string, unknown>> };
      sequence: number;
    } | null = null;
    for (const full of productionPackFiles()) {
      const pack = JSON.parse(fs.readFileSync(full, "utf-8")) as {
        sequence?: unknown;
        rules?: Array<Record<string, unknown>>;
      };
      // A pack without a numeric `sequence` cannot be compared — skip it
      // rather than let it win via a sentinel default.
      if (typeof pack.sequence !== "number") continue;
      if (best === null || pack.sequence > best.sequence) {
        best = {
          pack: pack as {
            sequence: number;
            rules?: Array<Record<string, unknown>>;
          },
          sequence: pack.sequence,
        };
      }
    }
    if (best === null) {
      throw new Error(
        `no source pack under ${PACKS_DIR} had a numeric sequence`,
      );
    }
    return best.pack;
  }

  /** Every EXCLUDE reason code a pack's rules can emit. */
  function excludeReasonCodesOf(pack: {
    rules?: Array<Record<string, unknown>>;
  }): Set<string> {
    const codes = new Set<string>();
    for (const rule of pack.rules ?? []) {
      const effect = rule.effect as Record<string, unknown> | undefined;
      if (
        effect &&
        effect.type === "EXCLUDE" &&
        typeof effect.reason_code === "string"
      ) {
        codes.add(effect.reason_code);
      }
    }
    return codes;
  }

  /**
   * EXCLUDE codes of ONE numbered SIGNED pack — pinned to an explicit
   * sequence, never derived from "whichever signed pack is highest": once a
   * later slice signs seq-23, "highest signed" becomes 23 and the diff
   * against itself silently goes empty, making the A8-2 tripwire vacuous
   * exactly when it matters most. Same prior art as
   * `reviewReasonCodesInSignedPack(20)` above.
   */
  function excludeReasonCodesInSignedPack(sequence: number): Set<string> {
    const envelope = JSON.parse(
      fs.readFileSync(
        path.join(
          PACKS_DIR,
          `rulepack-prod-${String(sequence).padStart(3, "0")}.signed.json`,
        ),
        "utf-8",
      ),
    ) as { payload?: { rules?: Array<Record<string, unknown>> } };
    return excludeReasonCodesOf({ rules: envelope.payload?.rules ?? [] });
  }

  it("has copy for every EXCLUDE code the highest source pack adds beyond signed seq-22 (Slice A8-2)", () => {
    const seq22Excludes = excludeReasonCodesInSignedPack(22);
    const sourceExcludes = excludeReasonCodesOf(highestSequenceSourcePack());
    const owed = [...sourceExcludes]
      .filter((code) => !seq22Excludes.has(code))
      .sort();
    // eslint-disable-next-line no-console -- printed by design (A8-2 contract: "the set
    // difference is printed"), not left-over debugging.
    console.log("Slice A8-2 — EXCLUDE codes owed SUPPORT_REASON_COPY:", owed);
    // Guard-of-the-guard: a glob/parse that silently found nothing (e.g. the source pack
    // regressed to fewer EXCLUDE rules, or PACKS_DIR stopped resolving) would make the
    // assertion below vacuously true. The mandate fixes this floor at exactly 10 today;
    // >= 10 keeps this test from going quiet if a future pack adds an eleventh.
    expect(owed.length).toBeGreaterThanOrEqual(10);
    const missing = owed.filter((code) => !(code in SUPPORT_REASON_COPY));
    expect(missing).toEqual([]);
  });

  it("has copy for every EXCLUDE code the highest SIGNED pack can emit (Slice A10)", () => {
    const payload = highestSequencePack();
    const codes = excludeReasonCodesOf({ rules: payload.rules ?? [] });
    // Guard-of-the-guard: today's highest signed pack (seq-24) carries 34
    // distinct EXCLUDE codes; >= 34 keeps this from going quiet if a pack
    // regresses to fewer EXCLUDE rules or PACKS_DIR stops resolving. seq-24
    // (2026-09-27) retires `hf.e33f.sponsor-required`, the only emitter of
    // SPONSOR_REQUIRED, so the count moved 35 -> 34 (measured off the signed
    // pack's rules, never typed). Unlike the Slice A8-2 test above (a DELTA
    // against seq-22), this is an ABSOLUTE floor — the technique that let these 14 pre-existing codes go
    // uncopied for two pack cycles (they were already in seq-22, so a
    // seq22-vs-source diff can never name them; gate-a8-2's own finding).
    expect(codes.size).toBeGreaterThanOrEqual(34);
    const missing = [...codes].filter((code) => !(code in SUPPORT_REASON_COPY));
    expect(missing).toEqual([]);
  });

  /**
   * PR-15 (E33 audit, 2026-10-11): every reason_code, at any depth, of every
   * SIGNED pack whose sequence is at or after `fromSequence`, keyed by that
   * sequence. Any depth, not only `effect.reason_code` of a SUPPORT rule, so
   * an EXCLUDE, a HUMAN_REVIEW or a notice cannot carry a retired key past it.
   */
  function reasonCodesOfSignedPacksFrom(
    fromSequence: number,
  ): Map<number, Set<string>> {
    const bySequence = new Map<number, Set<string>>();
    for (const full of signedProductionPackFiles()) {
      const envelope = JSON.parse(fs.readFileSync(full, "utf-8")) as {
        payload?: { sequence?: unknown };
      };
      const sequence = envelope.payload?.sequence;
      if (typeof sequence !== "number" || sequence < fromSequence) continue;
      const codes = new Set<string>();
      const walk = (node: unknown): void => {
        if (Array.isArray(node)) return node.forEach(walk);
        if (node === null || typeof node !== "object") return;
        for (const [key, value] of Object.entries(node)) {
          if (key === "reason_code" && typeof value === "string") {
            codes.add(value);
          }
          walk(value);
        }
      };
      walk(envelope.payload);
      bySequence.set(sequence, codes);
    }
    return bySequence;
  }

  it("retired E33 advisor-check keys: none is emitted by a signed pack at seq >= 28; replayable ones keep copy, never-emitted ones have none (PR-15)", () => {
    const packs = reasonCodesOfSignedPacksFrom(28);
    // Guard the guard: seq-28 and seq-29 are on disk, so fewer than two packs
    // means the glob or the envelope shape broke and the loop below would pass
    // vacuously.
    expect(packs.size).toBeGreaterThanOrEqual(2);
    // And the walk must really see reason codes: a live E33 advisor check
    // proves it reads what the packs emit, not an empty set.
    for (const codes of packs.values()) {
      expect(codes.has("E33E_AGE_55_59_ADVISOR_CHECK")).toBe(true);
    }
    expect(RETIRED_SUPPORT_REASON_KEYS.length).toBeGreaterThanOrEqual(4);
    const cameBack: string[] = [];
    for (const [sequence, codes] of packs) {
      for (const key of RETIRED_SUPPORT_REASON_KEYS) {
        if (codes.has(key)) cameBack.push(`seq-${sequence}: ${key}`);
      }
    }
    expect(cameBack).toEqual([]);
    // Replayable: signed packs still emit each one somewhere, so its copy
    // must stay; never-emitted: no pack emits it, so it carries no copy.
    const everywhere = reasonCodesOfSignedPacksFrom(0);
    const emittedAnywhere = new Set<string>();
    for (const codes of everywhere.values()) {
      codes.forEach((code) => emittedAnywhere.add(code));
    }
    expect(
      RETIRED_REPLAYABLE_SUPPORT_REASON_KEYS.filter(
        (key) => !emittedAnywhere.has(key) || !(key in SUPPORT_REASON_COPY),
      ),
    ).toEqual([]);
    expect(
      RETIRED_NEVER_EMITTED_SUPPORT_REASON_KEYS.filter(
        (key) => emittedAnywhere.has(key) || key in SUPPORT_REASON_COPY,
      ),
    ).toEqual([]);
  });

  it("every E33 advisor-check key in the copy table is emitted by the highest signed pack or listed as retired (PR-15)", () => {
    const packs = reasonCodesOfSignedPacksFrom(0);
    const highest = Math.max(...packs.keys());
    const live = packs.get(highest)!;
    // Direction 1: every E33 advisor-check code the highest pack emits has copy.
    const liveE33 = [...live].filter((key) =>
      /^E33[A-Z]?_.*_ADVISOR_CHECK$/.test(key),
    );
    expect(liveE33.length).toBeGreaterThanOrEqual(2);
    expect(liveE33.filter((key) => !(key in SUPPORT_REASON_COPY))).toEqual([]);
    // Direction 2: every copy key is live or listed as retired.
    const orphans = Object.keys(SUPPORT_REASON_COPY)
      .filter((key) => /^E33[A-Z]?_.*_ADVISOR_CHECK$/.test(key))
      .filter(
        (key) => !live.has(key) && !RETIRED_SUPPORT_REASON_KEYS.includes(key),
      );
    expect(orphans).toEqual([]);
    // A retired key is, by definition, not live on the highest signed pack.
    expect(RETIRED_SUPPORT_REASON_KEYS.filter((key) => live.has(key))).toEqual(
      [],
    );
  });

  /**
   * Walks a rule's `when` tree looking for a `{ op: "lt", fact, value }`
   * node on the named fact, at any nesting depth — same shape as
   * `findGteValue` above, mirrored for the `lt` operator the two E28A
   * below-minimum rules use.
   */
  function findLtValue(node: unknown, fact: string): number | undefined {
    if (Array.isArray(node)) {
      for (const item of node) {
        const found = findLtValue(item, fact);
        if (found !== undefined) return found;
      }
      return undefined;
    }
    if (node === null || typeof node !== "object") return undefined;
    const record = node as Record<string, unknown>;
    if (
      record.op === "lt" &&
      record.fact === fact &&
      typeof record.value === "number"
    ) {
      return record.value;
    }
    if (Array.isArray(record.args)) {
      return findLtValue(record.args, fact);
    }
    return undefined;
  }

  it("Slice A10: the E28A below-minimum copy states the signed pack's own two thresholds, in each language's own thousands separator", () => {
    const payload = highestSequencePack();
    const rules = payload.rules ?? [];
    const paidCapitalRule = rules.find(
      (r) => r.rule_id === "hf.e28a.paid-capital-below-min",
    );
    const totalInvestmentRule = rules.find(
      (r) => r.rule_id === "hf.e28a.total-investment-below-min",
    );
    // Guard-of-the-guard: both rules must actually be found in the signed
    // pack, or the assertions below would vacuously pass on `undefined`.
    expect(paidCapitalRule).toBeDefined();
    expect(totalInvestmentRule).toBeDefined();
    const paidCapitalValue = findLtValue(
      paidCapitalRule!.when,
      "investment.paid_up_capital_idr",
    );
    const totalInvestmentValue = findLtValue(
      totalInvestmentRule!.when,
      "investment.investment_capital_idr",
    );
    expect(paidCapitalValue).toBeDefined();
    expect(totalInvestmentValue).toBeDefined();

    const paidCapitalEn = paidCapitalValue!.toLocaleString("en-US");
    const paidCapitalId = paidCapitalValue!.toLocaleString("id-ID");
    const totalInvestmentEn = totalInvestmentValue!.toLocaleString("en-US");
    const totalInvestmentId = totalInvestmentValue!.toLocaleString("id-ID");

    expect(SUPPORT_REASON_COPY.E28A_PAID_CAPITAL_BELOW_MIN.en).toContain(
      `IDR ${paidCapitalEn}`,
    );
    expect(SUPPORT_REASON_COPY.E28A_PAID_CAPITAL_BELOW_MIN.id).toContain(
      `IDR ${paidCapitalId}`,
    );
    expect(SUPPORT_REASON_COPY.E28A_TOTAL_INVESTMENT_BELOW_MIN.en).toContain(
      `IDR ${totalInvestmentEn}`,
    );
    expect(SUPPORT_REASON_COPY.E28A_TOTAL_INVESTMENT_BELOW_MIN.id).toContain(
      `IDR ${totalInvestmentId}`,
    );
  });

  describe("RETIREMENT_INCOME_BELOW_THRESHOLD names the figure the rules check", () => {
    function retirementNoPathMessage(facts?: OracleFacts) {
      const response = makeVisaOracleResponse("NO_SUPPORTED_PATH");
      response.decision.no_path_reasons = [
        {
          code: "RETIREMENT_INCOME_BELOW_THRESHOLD",
          rule_ids: ["hf.e33e.retirement-income-below-minimum"],
          source_refs: [TEST_SOURCE_ID],
        },
      ];
      const outcome = buildEngineOutcome(response, facts ? { facts } : {});
      if (outcome.state !== "NO_SUPPORTED_PATH")
        throw new Error("unexpected state");
      return outcome.noPathReasons[0].message;
    }

    it("echoes a declared 2,999 and names the USD 3,000 minimum, EN and ID", () => {
      const message = retirementNoPathMessage({
        category: "retire",
        retirement_basis: "passive_income",
        secondhome_passive_income_usd: "2999",
      });
      expect(message.en).toBe(
        "You declared USD 2,999 a month; the retirement visas (E33E/E33F) need documented income or allowance of at least USD 3,000 a month.",
      );
      expect(message.id).toBe(
        "Anda menyatakan USD 2.999 per bulan; visa pensiun (E33E/E33F) memerlukan penghasilan atau tunjangan terdokumentasi minimal USD 3.000 per bulan.",
      );
    });

    it("says a 'not sure' counted as zero instead of claiming a figure was given", () => {
      const message = retirementNoPathMessage({
        category: "retire",
        retirement_basis: "passive_income",
        secondhome_passive_income_usd: "unsure",
      });
      expect(message.en).toBe(
        "You were not sure of your monthly income or allowance, so it counted as zero. The retirement visas need documented income or allowance of at least USD 3,000 a month: come back with the figure, or ask a Bali Zero advisor.",
      );
      expect(message.id).toBe(
        "Anda belum yakin dengan penghasilan atau tunjangan bulanan Anda, sehingga dihitung nol. Visa pensiun memerlukan penghasilan atau tunjangan terdokumentasi minimal USD 3.000 per bulan: kembalilah dengan angkanya, atau tanyakan kepada konsultan Bali Zero.",
      );
    });

    it("falls back to the neutral static sentence (no claim about the visitor's figure) when the facts do not show a below-minimum income", () => {
      for (const facts of [
        undefined,
        {},
        { secondhome_passive_income_usd: "3000" },
        { secondhome_passive_income_usd: "abc" },
      ] as Array<OracleFacts | undefined>) {
        const message = retirementNoPathMessage(facts);
        expect(message).toEqual(
          SUPPORT_REASON_COPY.RETIREMENT_INCOME_BELOW_THRESHOLD,
        );
        expect(message.en).toBe(
          "The retirement visas (E33E/E33F) need documented income or allowance of at least USD 3,000 a month.",
        );
        expect(message.id).toBe(
          "Visa pensiun (E33E/E33F) memerlukan penghasilan atau tunjangan terdokumentasi minimal USD 3.000 per bulan.",
        );
      }
    });

    it("keeps the retirement sentence when unrelated Second Home and paid-activity facts are also populated", () => {
      const message = retirementNoPathMessage({
        // category "retire" with leftovers that would each trigger a
        // sibling builder if the retirement code ever reached them.
        category: "retire",
        retirement_basis: "passive_income",
        secondhome_passive_income_usd: "2999",
        secondhome_basis: "bank_deposit",
        investment_vehicle: "bank_deposit",
        secondhome_deposit_usd: "10000",
        secondhome_state_bank: "no",
        secondhome_own_name: "no",
        other_paid_activity: "yes",
        work_payer: "no",
      });
      expect(message.en).toBe(
        "You declared USD 2,999 a month; the retirement visas (E33E/E33F) need documented income or allowance of at least USD 3,000 a month.",
      );
    });
  });

  it("Slice A10: LEVEL_BAND_DIKTI renders its own copy beside the STUDY_ADMISSION_OR_SPONSOR_NOT_CONFIRMED copy", () => {
    const response = makeVisaOracleResponse("NO_SUPPORTED_PATH");
    response.decision.no_path_reasons = [
      {
        code: "LEVEL_BAND_DIKTI",
        rule_ids: ["hf.study.level-band-dikti"],
        source_refs: [TEST_SOURCE_ID],
      },
      {
        code: "STUDY_ADMISSION_OR_SPONSOR_NOT_CONFIRMED",
        rule_ids: ["hf.study.admission-or-sponsor-unconfirmed"],
        source_refs: [TEST_SOURCE_ID],
      },
    ];
    const outcome = buildEngineOutcome(response);
    if (outcome.state !== "NO_SUPPORTED_PATH")
      throw new Error("unexpected state");
    expect(outcome.noPathReasons[0].message).toEqual(
      SUPPORT_REASON_COPY.LEVEL_BAND_DIKTI,
    );
    expect(outcome.noPathReasons[1].message).toEqual(
      SUPPORT_REASON_COPY.STUDY_ADMISSION_OR_SPONSOR_NOT_CONFIRMED,
    );
  });

  it("E33G_ANNUAL_INCOME_THRESHOLD_USD tracks both signed seq-28 income rules", () => {
    const payload = highestSequencePack();

    const threshold = E33G_ANNUAL_INCOME_THRESHOLD_USD;
    expect(threshold).toBe(
      gteThresholdInPack(
        "el.e33g.remote-work",
        "work.annual_foreign_income_usd",
      ),
    );
    const hardFilter = (payload.rules ?? []).find(
      (rule) => rule.rule_id === "hf.e33g.annual-income-below-minimum",
    );
    if (!hardFilter) {
      throw new Error(
        "hf.e33g.annual-income-below-minimum is absent from seq-28",
      );
    }
    expect(findLtValue(hardFilter.when, "work.annual_foreign_income_usd")).toBe(
      threshold,
    );
  });

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

  function findLteValue(node: unknown, fact: string): number | undefined {
    if (Array.isArray(node)) {
      for (const item of node) {
        const found = findLteValue(item, fact);
        if (found !== undefined) return found;
      }
      return undefined;
    }
    if (node === null || typeof node !== "object") return undefined;
    const record = node as Record<string, unknown>;
    if (
      record.op === "lte" &&
      record.fact === fact &&
      typeof record.value === "number"
    ) {
      return record.value;
    }
    return Array.isArray(record.args)
      ? findLteValue(record.args, fact)
      : undefined;
  }

  function stayBoundInPack(ruleId: string): number {
    const rule = (highestSequencePack().rules ?? []).find(
      (r) => r.rule_id === ruleId,
    );
    if (!rule) throw new Error(`${ruleId} is absent from the pack`);
    const value = findLteValue(rule.when, "intent.stay_days");
    if (value === undefined) {
      throw new Error(`no lte(intent.stay_days) node in ${ruleId}`);
    }
    return value;
  }

  it("B1/C1/C2/C6 stay-bound constants track the signed pack's lte(intent.stay_days) nodes", () => {
    expect(B1_MAX_STAY_DAYS).toBe(stayBoundInPack("el.b1.tourism"));
    expect(C1_MAX_STAY_DAYS).toBe(stayBoundInPack("el.c1.tourism-family"));
    expect(C2_MAX_STAY_DAYS).toBe(stayBoundInPack("el.c2.business"));
    expect(C6_MAX_STAY_DAYS).toBe(stayBoundInPack("el.c6.social"));
    expect([B1_MAX_STAY_DAYS, C1_MAX_STAY_DAYS]).toEqual([60, 180]);
  });

  it("the B1/C1/C2/C6 support reasons name the stay bound their rule checks, in EN and ID", () => {
    const bounds = {
      B1_VOA_ELIGIBLE: B1_MAX_STAY_DAYS,
      C1_VISIT_ELIGIBLE: C1_MAX_STAY_DAYS,
      C2_BUSINESS_ELIGIBLE: C2_MAX_STAY_DAYS,
      C6_SOCIAL_ELIGIBLE: C6_MAX_STAY_DAYS,
    } as const;
    for (const [code, days] of Object.entries(bounds)) {
      const copy = SUPPORT_REASON_COPY[code];
      expect(copy.en).toContain(`${days} days or less`);
      expect(copy.id).toContain(`${days} hari atau kurang`);
    }
    expect(SUPPORT_REASON_COPY.B1_VOA_ELIGIBLE.en).not.toContain(
      "30 days or less",
    );
    expect(SUPPORT_REASON_COPY.B1_VOA_ELIGIBLE.id).not.toContain(
      "30 hari atau kurang",
    );
    for (const code of [
      "C1_VISIT_ELIGIBLE",
      "C2_BUSINESS_ELIGIBLE",
      "C6_SOCIAL_ELIGIBLE",
    ]) {
      // The old (wrong) bound, stated as the whole stay; a future sentence may
      // still name the 60-day initial stay when a snapshot supports it.
      expect(SUPPORT_REASON_COPY[code].en).not.toContain("60 days or less");
      expect(SUPPORT_REASON_COPY[code].id).not.toContain("60 hari atau kurang");
      expect(SUPPORT_REASON_COPY[code].en).toContain("planned total stay");
      expect(SUPPORT_REASON_COPY[code].id).toContain(
        "rencana total masa tinggal",
      );
    }
    expect(SUPPORT_REASON_COPY.C2_BUSINESS_ELIGIBLE.en).toContain(
      "confirmed sponsor",
    );
    expect(SUPPORT_REASON_COPY.C6_SOCIAL_ELIGIBLE.en).toContain(
      "confirmed sponsor",
    );
  });

  // Same pin for the retirement pair. The income figure is the `lt` bound of
  // the two retirement hard filters (the figure the no-path sentence quotes);
  // the deposit figure is `el.e33e.retirement`'s `gte`.
  it("RETIREMENT_INCOME_THRESHOLD_USD tracks the signed pack's retirement-income hard filters (lt) and E33E_DEPOSIT_THRESHOLD_USD its el.e33e.retirement gte", () => {
    for (const ruleId of [
      "hf.e33e.retirement-income-below-minimum",
      "hf.e33f.retirement-income-below-minimum",
    ]) {
      const rule = (highestSequencePack().rules ?? []).find(
        (r) => r.rule_id === ruleId,
      );
      if (!rule) throw new Error(`${ruleId} is absent from the pack`);
      expect(
        findLtValue(rule.when, "secondhome.passive_monthly_income_usd"),
      ).toBe(RETIREMENT_INCOME_THRESHOLD_USD);
    }
    expect(E33E_DEPOSIT_THRESHOLD_USD).toBe(
      gteThresholdInPack("el.e33e.retirement", "secondhome.bank_deposit_usd"),
    );
  });

  // E33E_RETIREMENT_ELIGIBLE states TWO figures; the first-figure reader in
  // FIGURE_BACKED_BY_RULE below pins the deposit, this pins the income.
  it("E33E_RETIREMENT_ELIGIBLE's second figure (monthly income) is el.e33e.retirement's passive-income gte, EN and ID", () => {
    const expected = gteThresholdInPack(
      "el.e33e.retirement",
      "secondhome.passive_monthly_income_usd",
    );
    const copy = SUPPORT_REASON_COPY.E33E_RETIREMENT_ELIGIBLE;
    const second = (c: string, sep: RegExp) =>
      Number([...c.matchAll(/USD\s+([\d.,]+)/g)][1][1].replace(sep, ""));
    expect(second(copy.en, /,/g)).toBe(expected);
    expect(second(copy.id, /\./g)).toBe(expected);
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
    RETIREMENT_INCOME_BELOW_THRESHOLD: {
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

  // V03: the D1/D2/D12 funds figures are not `gte` nodes (the pack models no
  // funds fact), so they are pinned to what the pack does carry: the rule id,
  // its PROOF_OF_FUNDS_* reason code, and a source record whose canonical_url
  // is the official page the figure is quoted from.
  it("the D1/D2/D12 proof-of-funds copy states the official-page figure, pinned to its rule and source record, in EN and ID", () => {
    const pack = highestSequencePack() as unknown as {
      rules: Array<{
        rule_id: string;
        effect: { reason_code?: string };
        source_refs: string[];
      }>;
      source_records: Array<{
        source_record_id: string;
        canonical_url: string;
      }>;
    };
    const specs = [
      {
        key: "PROOF_OF_FUNDS_D1",
        rule: "el.d1-funds-usd-2000",
        page: "/D1",
        usd: D1_PROOF_OF_FUNDS_USD,
        en: "USD 2,000",
        id: "USD 2.000",
      },
      {
        key: "PROOF_OF_FUNDS_D2",
        rule: "el.d2-funds-usd-2000",
        page: "/D2",
        usd: D2_PROOF_OF_FUNDS_USD,
        en: "USD 2,000",
        id: "USD 2.000",
      },
      {
        key: "PROOF_OF_FUNDS_D12",
        rule: "el.d12-funds-usd-5000",
        page: "/D12",
        usd: D12_PROOF_OF_FUNDS_USD,
        en: "USD 5,000",
        id: "USD 5.000",
      },
    ] as const;
    for (const spec of specs) {
      const rule = pack.rules.find((r) => r.rule_id === spec.rule);
      expect(rule, spec.rule).toBeDefined();
      expect(rule?.effect.reason_code).toBe(spec.key);
      const urls = (rule?.source_refs ?? []).map(
        (ref) =>
          pack.source_records.find((s) => s.source_record_id === ref)
            ?.canonical_url ?? "",
      );
      expect(
        urls.some((u) => u.endsWith(`/wna/daftar-visa-indonesia${spec.page}`)),
        `${spec.rule} cites the official ${spec.page} page`,
      ).toBe(true);
      const copy = SUPPORT_REASON_COPY[spec.key];
      expect(copy.en).toContain(spec.en);
      expect(copy.id).toContain(spec.id);
      expect(copy.en).toContain("3 months");
      expect(copy.id).toContain("3 bulan");
      expect(copy.en).toMatch(/official page/i);
      // The constant and the sentence agree, and the rule id's own digits
      // (2000 / 5000) agree with the constant.
      expect(spec.rule).toContain(String(spec.usd));
    }
    expect(SUPPORT_REASON_COPY.PROOF_OF_FUNDS_D12.en).not.toContain("2,000");
    expect(SUPPORT_REASON_COPY.PROOF_OF_FUNDS_D1.en).not.toContain("5,000");
    expect(SUPPORT_REASON_COPY.PROOF_OF_FUNDS_D2.id).not.toContain("5.000");
  });

  it("the shared passport line anchors validity to expiry, not to the date of entry, for D1/D2/D12/E30/E30A/E30B", () => {
    const pack = highestSequencePack() as unknown as {
      rules: Array<{ rule_id: string; effect: { reason_code?: string } }>;
    };
    for (const ruleId of [
      "el.d1-passport-validity",
      "el.d2-passport-validity",
      "el.d12-passport-validity",
      "el.e30-passport-validity.e30",
      "el.e30-passport-validity.e30a",
      "el.e30-passport-validity.e30b",
    ]) {
      expect(
        pack.rules.find((r) => r.rule_id === ruleId)?.effect.reason_code,
        ruleId,
      ).toBe("PASSPORT_VALIDITY_6_MONTHS_REQUIRED");
    }
    // Exact pin: any re-anchoring (entry, arrival, border crossing...) is a
    // change to this sentence and must be a deliberate one.
    const copy = SUPPORT_REASON_COPY.PASSPORT_VALIDITY_6_MONTHS_REQUIRED;
    expect(copy.en).toBe(
      "Your passport must have at least 6 months of validity remaining.",
    );
    expect(copy.id).toBe(
      "Paspor Anda harus masih berlaku paling singkat 6 bulan.",
    );
  });

  it("the shared support-letter line is true for D12 (institution only) and D1/D2 (institution or Indonesian spouse/parent)", () => {
    const pack = highestSequencePack() as unknown as {
      rules: Array<{ rule_id: string; effect: { reason_code?: string } }>;
    };
    for (const ruleId of [
      "el.d1-support-letter",
      "el.d2-support-letter",
      "el.d12-support-letter",
    ]) {
      expect(
        pack.rules.find((r) => r.rule_id === ruleId)?.effect.reason_code,
        ruleId,
      ).toBe("SUPPORT_LETTER_REQUIRED");
    }
    const copy = SUPPORT_REASON_COPY.SUPPORT_LETTER_REQUIRED;
    // The spouse/parent route is scoped to D1/D2 in the sentence itself, and
    // D12 is never named as accepting it.
    expect(copy.en).toBe(
      "You will need a letter, invitation or correspondence from a government agency or private institution explaining its link to you. For the D1 and D2 visit visas, a letter from an Indonesian-citizen spouse or parent also qualifies.",
    );
    expect(copy.id).toBe(
      "Anda memerlukan surat keterangan, undangan, atau korespondensi dari instansi pemerintah atau lembaga swasta yang menjelaskan hubungannya dengan Anda. Untuk visa kunjungan D1 dan D2, surat dari suami/istri atau orang tua WNI juga dapat diterima.",
    );
    expect(copy.en).not.toMatch(/D12/);
    expect(copy.id).not.toMatch(/D12/);
  });

  // The official-page snapshots the funds figures are quoted from. Reading
  // them here is what makes a wrong figure RED instead of merely consistent
  // with itself.
  it("the D1/D2/D12 funds figures match the saved official-page snapshots and their VERIFIED source records", () => {
    const snapshotsDir = path.resolve(
      PACKS_DIR,
      "../../../../../../..",
      "research/visa/2026-10-13-organ-reattest-seq29/text",
    );
    const pack = highestSequencePack() as unknown as {
      source_records: Array<{
        source_record_id: string;
        canonical_url: string;
        status: string;
      }>;
    };
    const specs = [
      { id8: "ca5a2ce8", page: "D1", usd: D1_PROOF_OF_FUNDS_USD },
      { id8: "d3ad622e", page: "D2", usd: D2_PROOF_OF_FUNDS_USD },
      { id8: "5e64ec6b", page: "D12", usd: D12_PROOF_OF_FUNDS_USD },
    ];
    for (const spec of specs) {
      const record = pack.source_records.find((r) =>
        r.source_record_id.startsWith(spec.id8),
      );
      expect(record?.canonical_url).toBe(
        `https://www.imigrasi.go.id/wna/daftar-visa-indonesia/${spec.page}`,
      );
      expect(record?.status).toBe("VERIFIED");
      const file = fs
        .readdirSync(snapshotsDir)
        .find((name) => name.startsWith(`${spec.id8}-`));
      expect(file, `snapshot for ${spec.page}`).toBeDefined();
      const text = fs.readFileSync(path.join(snapshotsDir, file!), "utf-8");
      expect(text).toMatch(
        new RegExp(
          `rekening koran 3 bulan terakhir[^\\n]*minimal USD${spec.usd}\\b`,
        ),
      );
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

  it("uses the visitor's E33B collaboration answer instead of the E33A sponsor sentence for a sponsorless walk", () => {
    const message = firstNoPathReason("E33A_SPONSOR_NOT_GOVERNMENT", {
      sponsor_category: "NONE",
      sponsor_government_collaboration: "no",
    });
    expect(message).toEqual({
      en: "You told us you do not have a confirmed collaboration commitment with an Indonesian government body or institution based on your special expertise; the Second Home Golden Visa — Special-Expertise Collaboration (E33B) needs that commitment.",
      id: "Anda menyampaikan bahwa Anda belum memiliki komitmen kolaborasi yang terkonfirmasi dengan instansi atau lembaga pemerintah Indonesia berdasarkan keahlian khusus Anda; Visa Rumah Kedua Kolaborasi Keahlian Khusus (E33B) memerlukan komitmen tersebut.",
    });
  });

  it("keeps the E33A sentence unless the visitor is sponsorless and answered no to the E33B question", () => {
    const cases: OracleFacts[] = [
      { sponsor_category: "EMPLOYER", sponsor_government_collaboration: "no" },
      {
        sponsor_category: "INDIVIDUAL",
        sponsor_government_collaboration: "no",
      },
      { sponsor_category: "NONE", sponsor_government_collaboration: "yes" },
      { sponsor_category: "NONE" },
    ];
    for (const facts of cases) {
      expect(firstNoPathReason("E33A_SPONSOR_NOT_GOVERNMENT", facts)).toEqual(
        SUPPORT_REASON_COPY.E33A_SPONSOR_NOT_GOVERNMENT,
      );
    }
  });

  it("E33-family no-path sentences restate the signed product record", () => {
    const products = highestSequencePack().products ?? [];
    const productByCode = (code: string) => {
      const found = products.find((p) => p.product_code === code);
      if (!found) {
        throw new Error(
          `product ${code} is absent from the highest-sequence pack`,
        );
      }
      return found;
    };
    const e33 = productByCode("E33");
    const e33b = productByCode("E33B");
    const e33c = productByCode("E33C");

    // GUILT: E33B sponsor_types is ["NONE"]
    expect(e33b.sponsor_types).toEqual(["NONE"]);
    const e33bCopy = SUPPORT_REASON_COPY.E33B_SPONSOR_NOT_GOVERNMENT_OR_NONE;
    expect(e33bCopy.en.startsWith(`The ${e33b.names.en}`)).toBe(true);
    expect(e33bCopy.id.startsWith(e33b.names.id)).toBe(true);
    expect(e33bCopy.en).toMatch(/without a sponsor/);
    expect(e33bCopy.en).not.toMatch(/government/i);
    expect(e33bCopy.id).toMatch(/tanpa penjamin/);
    expect(e33bCopy.id).not.toMatch(/pemerintah/);

    // GUILT: E33C sponsor_types is ["GOVERNMENT"]
    expect(e33c.sponsor_types).toEqual(["GOVERNMENT"]);
    const e33cCopy = SUPPORT_REASON_COPY.E33C_SPONSOR_NOT_GOVERNMENT_OR_NONE;
    expect(e33cCopy.en.startsWith(`The ${e33c.names.en}`)).toBe(true);
    expect(e33cCopy.id.startsWith(e33c.names.id)).toBe(true);
    expect(e33cCopy.en).toMatch(/central-government/);
    expect(e33cCopy.en).not.toMatch(/no sponsor|without a sponsor/i);
    expect(e33cCopy.id).toMatch(/pemerintah pusat/);
    expect(e33cCopy.id).not.toMatch(/tanpa penjamin/);

    // GUILT: below-threshold Second Home property and deposit sentences use E33's pack name, not "Golden"
    const propertyBelow = firstNoPathReason(
      "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES",
      {
        category: "invest",
        investment_vehicle: "property",
        secondhome_property_value_usd: "500000",
      },
    );
    const depositBelow = firstNoPathReason(
      "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES",
      {
        category: "invest",
        investment_vehicle: "bank_deposit",
        secondhome_deposit_usd: "50000",
      },
    );
    for (const msg of [propertyBelow, depositBelow]) {
      expect(msg.en).toContain(e33.names.en);
      expect(msg.en).not.toContain("Golden");
      expect(msg.id).toContain(e33.names.id);
      expect(msg.id).not.toContain("Golden");
    }

    // INNOCENCE: E33A exclusion, E33B/E33C *_ELIGIBLE support pins, and generic fallback
    expect(SUPPORT_REASON_COPY.E33A_SPONSOR_NOT_GOVERNMENT.en).toContain(
      "central-government",
    );
    expect(SUPPORT_REASON_COPY.E33A_SPONSOR_NOT_GOVERNMENT.id).toContain(
      "pemerintah pusat",
    );
    expect(
      SUPPORT_REASON_COPY.E33B_GOVERNMENT_COLLABORATION_ELIGIBLE.en,
    ).toContain(e33b.names.en);
    expect(
      SUPPORT_REASON_COPY.E33B_GOVERNMENT_COLLABORATION_ELIGIBLE.id,
    ).toContain(e33b.names.id);
    expect(
      SUPPORT_REASON_COPY.E33C_WORLD_FIGURE_INVITATION_ELIGIBLE.en,
    ).toContain(e33c.names.en);
    expect(
      SUPPORT_REASON_COPY.E33C_WORLD_FIGURE_INVITATION_ELIGIBLE.id,
    ).toContain(e33c.names.id);
    expect(
      firstNoPathReason("OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES"),
    ).toEqual(
      SUPPORT_REASON_COPY.OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES,
    );
  });

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

  // Audit finding `e33-ownname-dead-end-reason` (2026-10-11): the deposit
  // route with a deposit at/above the threshold but NOT at a state bank / NOT
  // in the visitor's own name used to show the unrelated age sentence (under
  // 55) or the generic catalogue sentence (55+). The 130,000 figure is the
  // SECOND_HOME_DEPOSIT_THRESHOLD_USD constant pinned to el.e33.deposit-basis
  // above, never a typed literal.
  describe("second_home deposit route: holder answers (e33-ownname-dead-end-reason)", () => {
    const AGE = "AGE_BELOW_55";
    const OPERATIONAL = "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES";
    const deposit = (extra: OracleFacts = {}): OracleFacts => ({
      category: "second_home",
      secondhome_basis: "bank_deposit",
      secondhome_deposit_usd: "200000",
      secondhome_state_bank: "yes",
      secondhome_own_name: "yes",
      ...extra,
    });
    const tail = {
      en: "The Second Home Visa (E33) deposit route needs at least USD 130,000 held in your own name at an Indonesian state-owned bank.",
      id: "Jalur deposito Visa Rumah Kedua (E33) membutuhkan minimal USD 130.000 atas nama Anda sendiri di bank milik negara Indonesia.",
    };

    it("pins the 130,000 figure to the pack's deposit-basis threshold", () => {
      expect(tail.en).toContain(
        `USD ${SECOND_HOME_DEPOSIT_THRESHOLD_USD.toLocaleString("en-US")}`,
      );
      expect(tail.id).toContain(
        `USD ${SECOND_HOME_DEPOSIT_THRESHOLD_USD.toLocaleString("id-ID")}`,
      );
    });

    it("state bank = no replaces the age sentence (age code) and the generic one (operational code)", () => {
      for (const code of [AGE, OPERATIONAL]) {
        const m = firstNoPathReason(
          code,
          deposit({ secondhome_state_bank: "no" }),
        );
        expect(m.en).toBe(
          `You told us your deposit of USD 200,000 is not deposited at an Indonesian state-owned bank. ${tail.en}`,
        );
        expect(m.id).toBe(
          `Anda menyampaikan bahwa deposito Anda sebesar USD 200.000 tidak disimpan di bank milik negara Indonesia. ${tail.id}`,
        );
      }
    });

    it("own name = no", () => {
      const m = firstNoPathReason(AGE, deposit({ secondhome_own_name: "no" }));
      expect(m.en).toBe(
        `You told us your deposit of USD 200,000 is not held in your own name. ${tail.en}`,
      );
      expect(m.id).toBe(
        `Anda menyampaikan bahwa deposito Anda sebesar USD 200.000 tidak atas nama Anda sendiri. ${tail.id}`,
      );
    });

    it("both answers = no", () => {
      const m = firstNoPathReason(
        OPERATIONAL,
        deposit({ secondhome_state_bank: "no", secondhome_own_name: "no" }),
      );
      expect(m.en).toBe(
        `You told us your deposit of USD 200,000 is not deposited at an Indonesian state-owned bank. You told us it is not held in your own name. ${tail.en}`,
      );
      expect(m.id).toBe(
        `Anda menyampaikan bahwa deposito Anda sebesar USD 200.000 tidak disimpan di bank milik negara Indonesia. Anda menyampaikan bahwa deposito tersebut tidak atas nama Anda sendiri. ${tail.id}`,
      );
    });

    it("'not sure' (conservative no on the wire) is named as not sure, never as a told no", () => {
      const bank = firstNoPathReason(
        AGE,
        deposit({ secondhome_state_bank: "unsure" }),
      );
      expect(bank.en).toBe(
        `You were not sure whether your deposit of USD 200,000 is deposited at an Indonesian state-owned bank. ${tail.en}`,
      );
      expect(bank.id).toBe(
        `Anda belum yakin apakah deposito Anda sebesar USD 200.000 disimpan di bank milik negara Indonesia. ${tail.id}`,
      );
      const own = firstNoPathReason(
        OPERATIONAL,
        deposit({ secondhome_own_name: "unsure" }),
      );
      expect(own.en).toBe(
        `You were not sure whether your deposit of USD 200,000 is held in your own name. ${tail.en}`,
      );
      expect(own.id).toBe(
        `Anda belum yakin apakah deposito Anda sebesar USD 200.000 atas nama Anda sendiri. ${tail.id}`,
      );
      const mixed = firstNoPathReason(
        AGE,
        deposit({ secondhome_state_bank: "no", secondhome_own_name: "unsure" }),
      );
      expect(mixed.en).toBe(
        `You told us your deposit of USD 200,000 is not deposited at an Indonesian state-owned bank. You were not sure whether it is held in your own name. ${tail.en}`,
      );
    });

    it("the invest deposit route is covered too", () => {
      const m = firstNoPathReason(AGE, {
        category: "invest",
        investment_vehicle: "bank_deposit",
        secondhome_deposit_usd: "200000",
        secondhome_state_bank: "no",
        secondhome_own_name: "yes",
      });
      expect(m.en).toContain("is not deposited at an Indonesian state-owned");
    });

    it("innocence: retirement walks keep the age sentence", () => {
      const m = firstNoPathReason(AGE, {
        ...deposit({ secondhome_state_bank: "no" }),
        category: "retirement",
      });
      expect(m.en).toBe(SUPPORT_REASON_COPY.AGE_BELOW_55.en);
      expect(m.id).toBe(SUPPORT_REASON_COPY.AGE_BELOW_55.id);
    });

    it("innocence: a deposit below the threshold keeps the existing copy", () => {
      const m = firstNoPathReason(
        AGE,
        deposit({
          secondhome_deposit_usd: "50000",
          secondhome_state_bank: "no",
        }),
      );
      expect(m.en).toBe(SUPPORT_REASON_COPY.AGE_BELOW_55.en);
      const op = firstNoPathReason(
        OPERATIONAL,
        deposit({
          secondhome_deposit_usd: "50000",
          secondhome_state_bank: "no",
        }),
      );
      expect(op.en).toMatch(/50,000/);
      expect(op.en).toMatch(/130,000/);
    });

    it("innocence: both answers yes, a skipped answer, the property basis, or another code keep the existing copy", () => {
      expect(firstNoPathReason(AGE, deposit()).en).toBe(
        SUPPORT_REASON_COPY.AGE_BELOW_55.en,
      );
      const { secondhome_state_bank: _skipped, ...skipped } = deposit();
      expect(firstNoPathReason(OPERATIONAL, skipped).en).toBe(
        SUPPORT_REASON_COPY[OPERATIONAL].en,
      );
      expect(
        firstNoPathReason(AGE, {
          ...deposit({ secondhome_state_bank: "no" }),
          secondhome_basis: "property",
        }).en,
      ).toBe(SUPPORT_REASON_COPY.AGE_BELOW_55.en);
      expect(
        firstNoPathReason(
          "SECOND_HOME_GUARANTEE_BELOW_THRESHOLD",
          deposit({ secondhome_state_bank: "no" }),
        ).en,
      ).toBe(SUPPORT_REASON_COPY.SECOND_HOME_GUARANTEE_BELOW_THRESHOLD.en);
    });
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

  // PR-M (owner ruling 2026-09-27): an E33F needs a penjamin, not a family
  // sponsor, and Bali Zero can act as one.
  it("names the penjamin — never a family sponsor — and offers Bali Zero as one (EN + ID)", () => {
    const message = firstNoPathReason("SPONSOR_REQUIRED");
    expect(message.en).toMatch(/penjamin/i);
    expect(message.en).not.toMatch(/family/i);
    expect(message.en).toContain("Bali Zero can act as your penjamin");
    expect(message.id).toMatch(/penjamin/i);
    expect(message.id).not.toMatch(/keluarga/i);
    expect(message.id).toContain(
      "Bali Zero dapat bertindak sebagai penjamin Anda",
    );
  });
});

describe("PR-M · E33F verdict copy: neutral eligibility sentence + the penjamin note", () => {
  const RETIREMENT_ANSWERS = ["no", "unsure"] as const;

  function e33fResponse(state: "SUPPORTED_CANDIDATES" | "NO_SUPPORTED_PATH") {
    const response = makeVisaOracleResponse(state);
    for (const candidate of response.decision.candidates) {
      candidate.product_code = "E33F";
    }
    for (const candidate of response.display.candidates) {
      candidate.product_code = "E33F";
    }
    return response;
  }

  it("the E33F eligibility sentence carries no sponsor clause in either language", () => {
    const copy = SUPPORT_REASON_COPY.E33F_RETIREMENT_ELIGIBLE;
    expect(copy.en).not.toMatch(/sponsor|penjamin/i);
    expect(copy.id).not.toMatch(/sponsor|penjamin/i);
  });

  it("the note reads exactly as the owner ruled, in EN and ID", () => {
    expect(SUPPORT_REASON_COPY.E33F_PENJAMIN_NOTE).toEqual({
      en: "A penjamin (licensed visa agency or person) must sponsor your E33F. Bali Zero can act as your penjamin.",
      id: "Visa E33F Anda harus disponsori oleh penjamin (biro visa berlisensi atau perorangan). Bali Zero dapat bertindak sebagai penjamin Anda.",
    });
  });

  it.each(RETIREMENT_ANSWERS)(
    "guilt: an E33F candidate + a penjamin answer of %s carries the note as a sourceless condition",
    (answer) => {
      const outcome = buildEngineOutcome(e33fResponse("SUPPORTED_CANDIDATES"), {
        facts: {
          category: "retirement",
          retirement_penjamin_confirmed: answer,
        },
      });
      expect(outcome.conditions).toEqual([
        {
          code: "E33F_PENJAMIN_NOTE",
          message: SUPPORT_REASON_COPY.E33F_PENJAMIN_NOTE,
          sourceIds: [],
        },
      ]);
    },
  );

  it("guilt: the note is appended AFTER the backend notices, never in place of one", () => {
    const response = e33fResponse("SUPPORTED_CANDIDATES");
    response.decision.notices = [
      {
        code: "DISCLOSED_HEALTH_CONCERN_CONDITION",
        rule_ids: [],
        source_refs: [],
      },
    ];
    const outcome = buildEngineOutcome(response, {
      facts: { category: "retirement", retirement_penjamin_confirmed: "no" },
    });
    expect(outcome.conditions.map((item) => item.code)).toEqual([
      "DISCLOSED_HEALTH_CONCERN_CONDITION",
      "E33F_PENJAMIN_NOTE",
    ]);
  });

  it("innocence: a confirmed penjamin, an unanswered one, or no facts at all carries no note", () => {
    const quietCases: (OracleFacts | undefined)[] = [
      { category: "retirement", retirement_penjamin_confirmed: "yes" },
      { category: "retirement" },
      undefined,
    ];
    for (const facts of quietCases) {
      const outcome = buildEngineOutcome(e33fResponse("SUPPORTED_CANDIDATES"), {
        facts,
      });
      expect(outcome.conditions).toEqual([]);
    }
  });

  it("innocence: the note is E33F's alone — another candidate, another sponsor question or another state never shows it", () => {
    const otherCandidate = buildEngineOutcome(
      makeVisaOracleResponse("SUPPORTED_CANDIDATES"),
      {
        facts: { category: "retirement", retirement_penjamin_confirmed: "no" },
      },
    );
    expect(otherCandidate.conditions).toEqual([]);

    const familyWording = buildEngineOutcome(
      e33fResponse("SUPPORTED_CANDIDATES"),
      {
        facts: { category: "family", family_sponsor_confirmed: "no" },
      },
    );
    expect(familyWording.conditions).toEqual([]);

    const noPath = buildEngineOutcome(e33fResponse("NO_SUPPORTED_PATH"), {
      facts: { category: "retirement", retirement_penjamin_confirmed: "no" },
    });
    expect(noPath.conditions).toEqual([]);
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
  //   - `_DISCLOSED_REVIEW_REASON_CODES` (14 `DisclosedReviewFlag` entries as
  //     of A3-B #6960 — PAST_OVERSTAY / BLACKLIST_ENTRY /
  //     IMMIGRATION_INVESTIGATION appended at `evaluate_path.py:1147-1149`;
  //     each is reachable only under the `VISA_ORACLE_HOLDING_FLAGS` kill
  //     switch and is accounted, not copied, by `HELD_ONLY_REVIEW_CODES`
  //     below — A5-3bis, R-A5-DRIFT-CURE)
  //   - `_apply_minor_privacy_hold`'s `MINOR_GUARDIAN_PRIVACY_REVIEW`
  //   - the decisive-source authority hold (`_apply_decisive_source_authority_hold` family,
  //     ~line 1030) and the safety-critical source hold
  //     (`_apply_safety_critical_source_hold`, ~line 1136): each forces
  //     `state: HUMAN_REVIEW_REQUIRED` with its own review reasons when a
  //     legally decisive/safety-critical source isn't CURRENT. Missed in
  //     the first cut of this test — `DECISIVE_SOURCE_STALE` is proven
  //     live-emitted in research/visa/2026-08-15-gold-replay-live-post-
  //     notice-report.json (persona 9/10, "actual").
  const EVALUATE_PATH = path.resolve(
    HERE,
    "../../../../../../..",
    "apps/backend-rag/backend/services/visa_engine/evaluate_path.py",
  );
  const evaluatePathText = fs.readFileSync(EVALUATE_PATH, "utf-8");

  function disclosedReviewReasonCodes(): string[] {
    const start = evaluatePathText.indexOf(
      "_DISCLOSED_REVIEW_REASON_CODES: MappingProxyType",
    );
    const end = evaluatePathText.indexOf("\n\n#: The nine disclosures", start);
    if (start < 0 || end < 0) {
      throw new Error("could not isolate _DISCLOSED_REVIEW_REASON_CODES");
    }
    const codes =
      evaluatePathText
        .slice(start, end)
        .match(/"[A-Z][A-Z0-9_]*"/g)
        ?.map((code) => code.slice(1, -1)) ?? [];
    if (codes.length !== 14) {
      throw new Error(
        `expected 14 disclosed review codes, found ${codes.length}`,
      );
    }
    return codes;
  }

  function minorPrivacyReviewCodes(): string[] {
    const match = evaluatePathText.match(
      /MINOR_GUARDIAN_PRIVACY_REVIEW_CODE\s*=\s*"([A-Z][A-Z0-9_]*)"/,
    );
    if (!match) throw new Error("could not find minor privacy review code");
    const codes = [match[1]];
    if (codes.length !== 1) {
      throw new Error(`expected 1 minor privacy code, found ${codes.length}`);
    }
    return codes;
  }

  function sourceGateReviewCodes(): string[] {
    const codes: string[] = [];
    for (const functionName of [
      "_apply_decisive_source_authority_hold",
      "_apply_safety_critical_source_hold",
    ]) {
      const start = evaluatePathText.indexOf(`def ${functionName}(`);
      const end = evaluatePathText.indexOf("\n\ndef ", start + 1);
      if (start < 0) throw new Error(`could not find ${functionName}`);
      const body = evaluatePathText.slice(start, end < 0 ? undefined : end);
      const found = Array.from(
        body.matchAll(/code\s*=\s*"([A-Z][A-Z0-9_]*)"/g),
        (match) => match[1],
      );
      if (found.length !== 3) {
        throw new Error(
          `expected 3 source-gate codes in ${functionName}, found ${found.length}`,
        );
      }
      codes.push(...found);
    }
    if (codes.length !== 6) {
      throw new Error(`expected 6 source-gate codes, found ${codes.length}`);
    }
    return codes;
  }

  const EXPECTED_21 = [
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
    // Appended by A5-3bis (R-A5-DRIFT-CURE): A3-B (#6960) added these three
    // to `_DISCLOSED_REVIEW_REASON_CODES`. Held-only under the
    // `VISA_ORACLE_HOLDING_FLAGS` kill switch — accounted, not copied, by
    // `HELD_ONLY_REVIEW_CODES` below.
    "DISCLOSED_PAST_OVERSTAY_REVIEW",
    "DISCLOSED_BLACKLIST_ENTRY_REVIEW",
    "DISCLOSED_IMMIGRATION_INVESTIGATION_REVIEW",
  ];
  const PACK_INDEPENDENT_REVIEW_REASON_CODES = [
    ...disclosedReviewReasonCodes(),
    ...minorPrivacyReviewCodes(),
    ...sourceGateReviewCodes(),
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

  // Held-only review codes (A5-3bis, R-A5-DRIFT-CURE amendment, 2026-09-20).
  // A3-B (#6960) released PAST_OVERSTAY / BLACKLIST_ENTRY /
  // IMMIGRATION_INVESTIGATION as named CONDITIONS on `origin/main` — each
  // review code below is reachable ONLY when `VISA_ORACLE_HOLDING_FLAGS`
  // names the flag (the kill switch, measured end to end in
  // GATE-A3B-REPORT-6960.md check 4: env unset -> condition, env set ->
  // HUMAN_REVIEW_REQUIRED with this exact code). No visitor-facing
  // REVIEW_REASON_COPY exists for any of them yet: the day a flag is held
  // for real in production, its copy is a slice of its own (A3-M, which
  // opens after this slice merges). This list is not a parking lot: an
  // entry naming a code the derivation stops producing is "stale" below; an
  // entry whose code gains REVIEW_REASON_COPY without being removed here is
  // "phantom" below — the same edit that adds the copy must delete the row.
  const HELD_ONLY_REVIEW_CODES = [
    "DISCLOSED_PAST_OVERSTAY_REVIEW", // evaluate_path.py:1147
    "DISCLOSED_BLACKLIST_ENTRY_REVIEW", // evaluate_path.py:1148
    "DISCLOSED_IMMIGRATION_INVESTIGATION_REVIEW", // evaluate_path.py:1149
  ];

  it("derives and pins every backend-independent review reason by name", () => {
    expect(PACK_INDEPENDENT_REVIEW_REASON_CODES.slice().sort()).toEqual(
      EXPECTED_21.slice().sort(),
    );
  });

  // EMPTY SINCE THE seq-23 ACTIVATION (2026-09-24). While signed seq-22 was
  // in force, the twelve codes signed seq-23 retires (its rules turn them
  // into named dead ends or NEEDS_INPUT) still reached real applicants, so
  // their copy had to stay and this list named them by name. Production now
  // evaluates on signed seq-23, which cannot emit any of them, so the copy
  // was deleted in the same change that emptied this list (Slice A9.6,
  // 2026-09-25, mirroring #6683's seq-22 retirement). An entry here is a
  // claim that a code is live on signed seq-22, gone from signed seq-23, and
  // still has copy; the honesty test below still enforces all three, so the
  // list cannot be used as a parking lot for a copy nobody wants to delete.
  const REVIEW_REASON_COPY_KEYS_LIVE_ON_SEQ22_ONLY: string[] = [];

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
    // above retired), + 18 pack-independent = 31, measured. The eight kept
    // their copy under a seq-20-only list until the seq-22 activation.
    //
    // 31 -> 34 measured after A5-3bis (R-A5-DRIFT-CURE, 2026-09-20): 13 pack
    // + 21 pack-independent (the three A3-B held-only codes joined
    // EXPECTED_21). Floor left at 31 — it is a regression tripwire, not a
    // pin; the three new codes are accounted by HELD_ONLY_REVIEW_CODES, not
    // REVIEW_REASON_COPY, so they do not change what "mapped or known gap"
    // means for this assertion.
    //
    // 34 -> 22 measured when the signed seq-23 bundle landed (Slice A9.3,
    // 2026-09-24): the highest source and the highest signed pack are both
    // seq-23, which emits one review code (SECOND_HOME_BELOW_THRESHOLD_STUDIO),
    // + 21 pack-independent = 22. The twelve codes seq-23 retires kept their
    // copy under REVIEW_REASON_COPY_KEYS_LIVE_ON_SEQ22_ONLY while seq-22 was
    // in force; Slice A9.6 (2026-09-25, the seq-23 activation) deleted that
    // copy and emptied the list in the same change, so the floor holds at 22.
    expect(allRealCodes.length).toBeGreaterThanOrEqual(22);

    const unaccounted = allRealCodes.filter(
      (code) =>
        !(code in REVIEW_REASON_COPY) &&
        !KNOWN_UNMAPPED_REVIEW_REASON_CODES.includes(code) &&
        !HELD_ONLY_REVIEW_CODES.includes(code),
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
      [...REVIEW_REASON_COPY_KEYS_LIVE_ON_SEQ22_ONLY].sort(),
    );
  });

  it("keeps the seq-22-only list honest: every entry is live on signed seq-22, gone from signed seq-23, and still has copy", () => {
    // The list above is a claim about production, not a parking lot: each
    // entry must be a code the signed seq-22 pack still emits (or its copy
    // really is dead and must go), must be absent from signed seq-23 (or it
    // is not "seq-22 only" and belongs in the ordinary stale-key check),
    // must not be a pack-independent code the backend emits on its own, and
    // must still have copy here. Both packs are named by sequence, never
    // "whichever is highest": once a later pack is signed, a
    // highest-vs-highest diff would go silently empty (the same reasoning as
    // A8-2's `excludeReasonCodesInSignedPack(22)`).
    const seq22 = reviewReasonCodesInSignedPack(22);
    const seq23 = reviewReasonCodesInSignedPack(23);
    // Guard the guard: if either pack stopped parsing, the sets below would
    // be empty and every filter assertion after them would pass vacuously.
    expect(seq22.size).toBeGreaterThan(0);
    expect(seq23.size).toBeGreaterThan(0);
    const derived = [...seq22].filter((code) => !seq23.has(code)).sort();
    expect(derived.length).toBeGreaterThan(0);
    const notLiveOnSeq22 = REVIEW_REASON_COPY_KEYS_LIVE_ON_SEQ22_ONLY.filter(
      (code) => !seq22.has(code),
    );
    expect(notLiveOnSeq22).toEqual([]);
    const stillEmittedBySeq23 =
      REVIEW_REASON_COPY_KEYS_LIVE_ON_SEQ22_ONLY.filter((code) =>
        seq23.has(code),
      );
    expect(stillEmittedBySeq23).toEqual([]);
    const emittedByBackend = REVIEW_REASON_COPY_KEYS_LIVE_ON_SEQ22_ONLY.filter(
      (code) => PACK_INDEPENDENT_REVIEW_REASON_CODES.includes(code),
    );
    expect(emittedByBackend).toEqual([]);
    const withoutCopy = REVIEW_REASON_COPY_KEYS_LIVE_ON_SEQ22_ONLY.filter(
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

  it("keeps the held-only allowlist honest: every entry is a code the derivation actually produces (stale)", () => {
    // Mirror image of the seq-22-only honesty test above, for
    // HELD_ONLY_REVIEW_CODES instead of REVIEW_REASON_COPY_KEYS_LIVE_ON_SEQ22_ONLY:
    // if A3-B's release is ever reverted or the flag renamed, the derivation
    // stops producing that name and this list would be naming a code that
    // is not derived — a dead placeholder no other assertion here would
    // catch (it never touches REVIEW_REASON_COPY, so the ordinary stale-key
    // test can't see it).
    const derived = new Set(PACK_INDEPENDENT_REVIEW_REASON_CODES);
    const staleHeldOnlyEntries = HELD_ONLY_REVIEW_CODES.filter(
      (code) => !derived.has(code),
    );
    expect(staleHeldOnlyEntries).toEqual([]);
  });

  it("keeps the held-only allowlist honest: no entry there already has copy (phantom)", () => {
    // The day a held-only code ships real visitor-facing copy, the same
    // change that adds it to REVIEW_REASON_COPY must delete the row here —
    // otherwise the code would be double-accounted (both mapped AND
    // held-only), and the row would be a phantom promise of a gap that
    // copy has already closed.
    const phantomHeldOnlyEntries = HELD_ONLY_REVIEW_CODES.filter(
      (code) => code in REVIEW_REASON_COPY,
    );
    expect(phantomHeldOnlyEntries).toEqual([]);
  });

  it("pins the held-only allowlist to exactly the three A3-B codes", () => {
    // Cardinality by literal, not derived — a test whose expectation shrinks
    // with the table it judges proves nothing (GATE-A2G OBS-A2g-4, the same
    // reasoning A5-1's four-field pin uses).
    expect(HELD_ONLY_REVIEW_CODES).toHaveLength(3);
  });
});

describe("criminal review elements and unmapped review reasons (slice A5)", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    emitVisaOracleTelemetry.mockReset();
  });

  const copy = REVIEW_REASON_ELEMENTS.DISCLOSED_CRIMINAL_RECORD_REVIEW!;
  it.each([
    [
      "rule",
      "This result is paused because you disclosed a criminal record or an ongoing case. A Bali Zero advisor can review it with you before any path is confirmed.",
      "Hasil ini ditunda karena Anda mengungkapkan catatan kriminal atau perkara yang masih berjalan. Konsultan Bali Zero dapat meninjaunya bersama Anda sebelum jalur mana pun dikonfirmasi.",
    ],
    [
      "checked",
      "A Bali Zero advisor can read what you disclosed against the immigration record requirements for the route you asked about, and assess whether it can be submitted as it stands.",
      "Konsultan Bali Zero dapat membaca apa yang Anda ungkapkan terhadap persyaratan catatan keimigrasian untuk jalur yang Anda tanyakan, lalu menilai apakah berkas tersebut dapat diajukan apa adanya.",
    ],
    [
      "prepare",
      "Have the dates and the issuing authority of any court or police record ready, together with any document showing the case is closed. Send nothing here — a Bali Zero advisor can tell you where each document goes.",
      "Siapkan tanggal dan instansi penerbit dari setiap catatan pengadilan atau kepolisian, beserta dokumen apa pun yang menunjukkan perkara telah ditutup. Jangan kirimkan apa pun di sini — konsultan Bali Zero dapat memberi tahu ke mana setiap dokumen harus dikirim.",
    ],
    [
      "handling",
      "A Bali Zero advisor can review this before a path is confirmed, and can tell you the timing for your case.",
      "Konsultan Bali Zero dapat meninjau hal ini sebelum jalur dikonfirmasi, dan dapat memberi tahu Anda perkiraan waktu untuk kasus Anda.",
    ],
  ] as const)("pins %s in EN and ID", (field, en, id) => {
    expect(copy[field]).toEqual({ en, id });
  });

  it("has exactly four criminal review element fields and exact labels", () => {
    expect(Object.keys(copy)).toHaveLength(4);
    expect(translate("en", "outcome.review.element.rule" as I18nKey)).toBe(
      "Why this is paused",
    );
    expect(translate("en", "outcome.review.element.checked" as I18nKey)).toBe(
      "What the reviewer checks",
    );
    expect(translate("en", "outcome.review.element.prepare" as I18nKey)).toBe(
      "What to prepare",
    );
    expect(translate("en", "outcome.review.element.handling" as I18nKey)).toBe(
      "How this is handled",
    );
    expect(translate("id", "outcome.review.element.rule" as I18nKey)).toBe(
      "Mengapa hasil ini ditunda",
    );
    expect(translate("id", "outcome.review.element.checked" as I18nKey)).toBe(
      "Apa yang diperiksa peninjau",
    );
    expect(translate("id", "outcome.review.element.prepare" as I18nKey)).toBe(
      "Apa yang perlu disiapkan",
    );
    expect(translate("id", "outcome.review.element.handling" as I18nKey)).toBe(
      "Bagaimana hal ini ditangani",
    );
  });

  // Slice A7-M (2026-09-22, M3): the shipped sentence described "being a
  // minor", which after A7-B no longer raises the code — GUILT: revert
  // `REVIEW_REASON_COPY.MINOR_GUARDIAN_PRIVACY_REVIEW` to that sentence and
  // this RED names the mismatch.
  it("pins the rewritten MINOR_GUARDIAN_PRIVACY_REVIEW lead sentence, EN and ID", () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    response.decision.review_reasons[0].code = "MINOR_GUARDIAN_PRIVACY_REVIEW";
    const outcome = buildEngineOutcome(response);
    if (outcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    expect(outcome.reviewReasons).toHaveLength(1);
    expect(outcome.reviewReasons[0].message).toEqual({
      en: "You told us no parent or legal guardian is filling this in with the applicant, who is under 18. A Bali Zero consultant can pick this up with you once an adult is present.",
      id: "Anda menyampaikan bahwa tidak ada orang tua atau wali sah yang mengisi ini bersama pemohon yang berusia di bawah 18 tahun. Konsultan Bali Zero dapat melanjutkan bersama Anda setelah ada orang dewasa yang mendampingi.",
    });
    // The rewritten sentence must not still describe "being a minor" as
    // what raises the code — A7-B narrowed the hold to a declared/unknown
    // guardian, so `true` no longer holds at all.
    expect(outcome.reviewReasons[0].message.en).not.toContain(
      "involves a minor",
    );
  });

  // GUILT: delete `REVIEW_REASON_ELEMENTS.MINOR_GUARDIAN_PRIVACY_REVIEW` and
  // this RED names the code (A5's shape, `engine-adapter.ts`).
  it("gives MINOR_GUARDIAN_PRIVACY_REVIEW its own four-element block (A5 shape, slice A7-M)", () => {
    const elements = REVIEW_REASON_ELEMENTS.MINOR_GUARDIAN_PRIVACY_REVIEW;
    if (!elements)
      throw new Error("MINOR_GUARDIAN_PRIVACY_REVIEW has no elements");
    expect(Object.keys(elements)).toHaveLength(4);
    expect(elements.rule).toEqual({
      en: "Indonesian personal-data law (UU PDP) does not let someone under 18 consent to this assessment on their own.",
      id: "Undang-undang pelindungan data pribadi Indonesia (UU PDP) tidak mengizinkan orang berusia di bawah 18 tahun memberikan persetujuan atas penilaian ini sendiri.",
    });
    expect(elements.checked).toEqual({
      en: "That an adult with parental responsibility or legal guardianship is acting for the applicant.",
      id: "Bahwa orang dewasa dengan tanggung jawab orang tua atau perwalian sah bertindak untuk pemohon.",
    });
    expect(elements.prepare).toEqual({
      en: "A parent or legal guardian who can complete the request together with the applicant.",
      id: "Orang tua atau wali sah yang dapat melengkapi permohonan bersama pemohon.",
    });
    expect(elements.handling).toEqual({
      en: "A Bali Zero consultant can confirm the guardian before any application step.",
      id: "Konsultan Bali Zero dapat memastikan wali sebelum langkah permohonan apa pun.",
    });
  });

  it("keeps the activity-boundary hold as a single sentence without elements", () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    response.decision.review_reasons[0].code =
      "DISCLOSED_ACTIVITY_BOUNDARY_REVIEW";
    const outcome = buildEngineOutcome(response);
    if (outcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    expect(outcome.reviewReasons).toHaveLength(1);
    expect(outcome.reviewReasons[0].message).toEqual({
      en: "One of your answers about your planned activity, investment vehicle, retirement basis or diaspora connection is one these rules cannot decide on their own, so no path can be confirmed yet. A Bali Zero advisor can go over it with you.",
      id: "Salah satu jawaban Anda mengenai aktivitas yang direncanakan, sarana investasi, dasar pensiun, atau hubungan diaspora tidak dapat diputuskan sendiri oleh aturan ini, sehingga belum ada jalur yang dapat dikonfirmasi. Konsultan Bali Zero dapat membahasnya bersama Anda.",
    });
    expect(
      REVIEW_REASON_ELEMENTS.DISCLOSED_ACTIVITY_BOUNDARY_REVIEW,
    ).toBeUndefined();
  });

  // This throw cannot fire in playwright.config.ts's e2e run because that
  // runs a production build (NODE_ENV === "production").
  it("throws for an unmapped review reason outside production (GUILT-a)", () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    response.decision.review_reasons[0].code = "NOT_A_REAL_REVIEW_CODE";
    expect(() => buildEngineOutcome(response)).toThrow(
      new VisaOracleResponseError("RESPONSE_INVARIANT"),
    );
  });

  it("falls back to generic copy and reports one unmapped review code in production (GUILT-b)", () => {
    vi.stubEnv("NODE_ENV", "production");
    const code = "ANOTHER_NOT_REAL_REVIEW_CODE";
    const first = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    first.decision.review_reasons[0].code = code;
    const second = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    second.decision.review_reasons[0].code = code;
    const firstOutcome = buildEngineOutcome(first);
    if (firstOutcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    const secondOutcome = buildEngineOutcome(second);
    if (secondOutcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    expect(firstOutcome.reviewReasons[0].message.en).toBe(
      "Some of your answers need a review before a path can be confirmed. A Bali Zero advisor can go over them with you.",
    );
    expect(secondOutcome.reviewReasons[0].message.en).toBe(
      "Some of your answers need a review before a path can be confirmed. A Bali Zero advisor can go over them with you.",
    );
    expect(emitVisaOracleTelemetry).toHaveBeenCalledTimes(1);
    expect(emitVisaOracleTelemetry).toHaveBeenCalledWith({
      event: "visa_oracle_v2_review_reason_unmapped_code",
      code,
    });
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
      { ...first, code: "DISCLOSED_CRIMINAL_RECORD_REVIEW" },
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

  it("has all thirteen codes N1 names, and no other code, EN and ID both non-empty (A3'-M M6: fourteen -> thirteen, ACTIVITY_BOUNDARY retired)", () => {
    const EXPECTED_CODES = [
      "OBSOLETE_PRODUCT_CODE",
      "DISCLOSED_HEALTH_CONCERN_CONDITION",
      "DISCLOSED_PRIOR_VISA_REFUSAL_CONDITION",
      "DISCLOSED_UNCERTAINTY_CONDITION",
      "DISCLOSED_PEP_OR_SANCTIONS_CONDITION",
      "DISCLOSED_SOURCE_OF_FUNDS_CONDITION",
      "DISCLOSED_DIPLOMATIC_PASSPORT_CONDITION",
      "DISCLOSED_AMBIGUOUS_SPONSOR_CONDITION",
      // DISCLOSED_ACTIVITY_BOUNDARY_CONDITION retired here (A3'-M, M6): the
      // kill switch can never release it into a live condition again (see
      // PRE_PROVISIONED_NOTICE_CODES below), so the pre-provisioned row is
      // gone rather than dead weight.
      "DISCLOSED_MULTI_PURPOSE_TRIP_CONDITION",
      "CONFLICTING_IMMIGRATION_STATUS_CONDITION",
      // Slice A3-M (DRAFT-SPEC-A3-1.v2-M §4.1, M4): three new keys.
      "DISCLOSED_PAST_OVERSTAY_CONDITION",
      "DISCLOSED_BLACKLIST_ENTRY_CONDITION",
      "DISCLOSED_IMMIGRATION_INVESTIGATION_CONDITION",
    ].sort();
    expect(Object.keys(NOTICE_CONDITION_COPY).sort()).toEqual(EXPECTED_CODES);
    for (const message of Object.values(NOTICE_CONDITION_COPY)) {
      expect(message.en.length).toBeGreaterThan(0);
      expect(message.id.length).toBeGreaterThan(0);
    }
  });

  // Slice A3-M (DRAFT-SPEC-A3-1.v2-M §4.1, M4-bis, routed from A5's gate):
  // the copy table must never carry a code the backend cannot emit, and any
  // code the backend CAN emit but the table deliberately withholds must be
  // named and justified — never silently absent. Ground truth verified
  // against the backend source on this base:
  const BACKEND_EMITTED_NOTICE_CODES = [
    "OBSOLETE_PRODUCT_CODE", // evaluator.py:1000
    "DISCLOSED_HEALTH_CONCERN_CONDITION", // evaluate_path.py:1163
    "DISCLOSED_PRIOR_VISA_REFUSAL_CONDITION", // evaluate_path.py:1164
    "DISCLOSED_UNCERTAINTY_CONDITION", // evaluate_path.py:1165
    "DISCLOSED_PEP_OR_SANCTIONS_CONDITION", // evaluate_path.py:1166
    "DISCLOSED_SOURCE_OF_FUNDS_CONDITION", // evaluate_path.py:1167
    "DISCLOSED_DIPLOMATIC_PASSPORT_CONDITION", // evaluate_path.py:1168
    "DISCLOSED_AMBIGUOUS_SPONSOR_CONDITION", // evaluate_path.py:1169
    "DISCLOSED_MULTI_PURPOSE_TRIP_CONDITION", // evaluate_path.py:1170
    "CONFLICTING_IMMIGRATION_STATUS_CONDITION", // evaluate_path.py:1171-1173
    "DISCLOSED_PAST_OVERSTAY_CONDITION", // evaluate_path.py:1174
    "DISCLOSED_BLACKLIST_ENTRY_CONDITION", // evaluate_path.py:1175
    "DISCLOSED_IMMIGRATION_INVESTIGATION_CONDITION", // evaluate_path.py:1176
  ];

  // A3' (slice A3'-M, M6) retires the row this list used to carry:
  // `DISCLOSED_ACTIVITY_BOUNDARY_CONDITION` is gone from
  // `NOTICE_CONDITION_COPY` above, and `DEAD_END_DISCLOSED_FLAGS` (slice
  // A3'-B, evaluate_path.py) moves ACTIVITY_BOUNDARY out of
  // `HOLDING_DISCLOSED_FLAGS` for good — the kill switch that used to make
  // this pre-provisioning unreachable BY CONSTRUCTION now has nothing left
  // to release into a condition. Nothing is provisioned and nothing is
  // sent; an empty list here is the honest state, not dead weight.
  const PRE_PROVISIONED_NOTICE_CODES: string[] = [];

  it("NOTICE_CONDITION_COPY carries no code the backend cannot emit and never provisioned", () => {
    const allowed = new Set([
      ...BACKEND_EMITTED_NOTICE_CODES,
      ...PRE_PROVISIONED_NOTICE_CODES,
    ]);
    const uncovered = Object.keys(NOTICE_CONDITION_COPY).filter(
      (key) => !allowed.has(key),
    );
    expect(uncovered).toEqual([]);

    // A3' (M6): nothing is provisioned any more — ACTIVITY_BOUNDARY's row
    // is retired, not replaced, so the list is empty rather than non-empty.
    expect(PRE_PROVISIONED_NOTICE_CODES).toEqual([]);
    const missingFromTable = PRE_PROVISIONED_NOTICE_CODES.filter(
      (code) => !(code in NOTICE_CONDITION_COPY),
    );
    expect(missingFromTable).toEqual([]);
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
  //
  // Updated for Slice A2-G (families are now GENERATED — see G1/G3/G5
  // above): OBS-A2c-7's ceiling stays open — "will in no way affect" needs
  // a fifth NEGATIONS-like token ("in no/any way") this PR does not add,
  // and "bukan masalah" needs a THIRD ID negator (`bukan`) alongside
  // `tidak`/`tak`; both are pure-synonym misses ("already settled / a
  // formality", "sudah final / tinggal formalitas") no finite list closes.
  // GATE-A2D-REPORT-6919 "Input for PR-G" adds ten more out-of-history
  // misses on the SAME two axes (idiom outside NEGATIONS, gap width,
  // register) plus one auxiliary decision (`need`/`dare`) and one `be`-form
  // decision — the PR body disposes of all thirteen row by row: caught
  // (widened apostrophe class, `tak`) or declared, never widened past what
  // G1/G3/G5 specify.
  interface BannedPattern {
    name: string;
    re: RegExp;
  }

  // G1 (Slice A2-G, MANDATE-vo.md): one list each, and the regexes are BUILT
  // from them — no auxiliary, negation, verb or ID token appears anywhere
  // else in this guard. buildNegationPatterns() and the property test below
  // both read these SAME lists, which is exactly why the cardinality pins
  // just under them have to be LITERAL: a mutation that shrinks a list
  // shrinks the generator and its own property test symmetrically and
  // would stay green otherwise — the precise shape (a test deriving its
  // expectation from the thing under test) that produced this slice's
  // three reds (OBS-A2c-1, GATE-A2C-REPORT-6859.md). #6859's two
  // hand-written alternations, and the omission that took three rounds to
  // surface, are exactly what this construction abolishes.
  const AUXILIARIES = [
    "do",
    "does",
    "did",
    "will",
    "would",
    "can",
    "could",
    "shall",
    "should",
    "may",
    "might",
  ] as const;
  type Auxiliary = (typeof AUXILIARIES)[number];

  const NEGATIONS = ["not", "n't", "n’t", "never"] as const;

  const EFFECT_VERBS = [
    "change",
    "affect",
    "alter",
    "impact",
    "influence",
    "matter",
  ] as const;

  // G3: a MAP owned by the generator, keyed by the SAME AUXILIARIES — never
  // a second list. An auxiliary with no entry here falls through, inside
  // buildNegationPatterns(), to `<aux>n't` with both apostrophes. Where an
  // auxiliary holds several forms (`can`), the property test synthesises
  // one sentence PER FORM, not per combination (G3).
  const IRREGULAR_CONTRACTIONS: Partial<Record<Auxiliary, readonly string[]>> =
    {
      will: ["won't"],
      can: ["can't", "cannot"],
      shall: ["shan't"],
    };

  // GATE-A2D-REPORT-6919 "Input for PR-G": only `'` (straight) and `’`
  // (curly) were in the apostrophe character class, so a backtick or acute
  // apostrophe ("don`t") slipped through GREEN. Widened here, in the
  // matching machinery — this is punctuation normalisation, not a fifth
  // NEGATIONS token, so NEGATIONS stays pinned at 4.
  const APOSTROPHES = "['’`´]";

  // Up to two intervening words between the negation and the verb of
  // effect, unchanged from #6859/#6919. GATE-A2D-REPORT-6919 named this gap
  // as a structural axis that a third word or a comma defeats ("do not, in
  // any event, change"; "don't in any way change") — a DECLARED LIMIT for
  // this PR (see the PR body's disposition table), not cured here: widening
  // it without a fixed bound chases an open-ended set of adverbial
  // insertions, and this construction fixes the list-omission defect, not
  // the gap's word count.
  const GAP = String.raw`(?:\s+\S+){0,2}`;

  function buildNegationPatterns(): BannedPattern[] {
    const auxAlt = AUXILIARIES.join("|");
    const verbAlt = `(?:${EFFECT_VERBS.join("|")})s?`;
    const spacedNegations = NEGATIONS.filter((n) => !/['’]/.test(n));
    const regularAuxiliaries = AUXILIARIES.filter(
      (aux) => !(aux in IRREGULAR_CONTRACTIONS),
    );
    const irregularForms = AUXILIARIES.flatMap(
      (aux) => IRREGULAR_CONTRACTIONS[aux] ?? [],
    );

    return [
      {
        name: "EN negated effect (spaced 'not'/'never'): aux + spaced negation + up to two words + verb of effect",
        re: new RegExp(
          String.raw`\b(?:${auxAlt})\s+(?:${spacedNegations.join("|")})\b${GAP}\s+${verbAlt}\b`,
          "gi",
        ),
      },
      {
        name: "EN negated effect (contracted auxn't): up to two words + verb of effect",
        re: new RegExp(
          String.raw`\b(?:${regularAuxiliaries.join("|")})n${APOSTROPHES}t\b${GAP}\s+${verbAlt}\b`,
          "gi",
        ),
      },
      {
        name: "EN negated effect, irregular contractions won't/cannot/can't: up to two words + verb of effect",
        re: new RegExp(
          `\\b(?:${irregularForms
            .map((f) => f.replace(/'/g, APOSTROPHES))
            .join("|")})\\b${GAP}\\s+${verbAlt}\\b`,
          "gi",
        ),
      },
    ];
  }

  // G5: the ID mirror, same construction — `tak` (OBS-A2c-8) now alongside
  // `tidak`, closing the exact contraction axis OBS-A2c-1 closed on the EN
  // side. GATE-A2D-REPORT-6919 named the ID side as having NO gap slack at
  // all, asymmetric with the EN side above ("tidak sama sekali mengubah",
  // "tidak pernah berpengaruh") — a DECLARED LIMIT for this PR (PR body),
  // not widened: G5's own text is exactly "tidak/tak (akan)? + verb", no
  // general gap, and widening it is a spec decision for a future round.
  const ID_NEGATORS = ["tidak", "tak"] as const;
  const ID_VERBS = [
    "mengubah",
    "berpengaruh",
    "memengaruhi",
    "mempengaruhi",
    "berdampak",
    "menjadi masalah",
  ] as const;

  function buildIdNegationPattern(): BannedPattern {
    const verbAlt = ID_VERBS.map((v) => v.replace(/ /g, "\\s+")).join("|");
    return {
      name: "ID negated effect: tidak/tak (akan)? + mengubah/berpengaruh/memengaruhi/mempengaruhi/berdampak/menjadi masalah",
      re: new RegExp(
        String.raw`\b(?:${ID_NEGATORS.join("|")})\s+(?:akan\s+)?(?:${verbAlt})\b`,
        "gi",
      ),
    };
  }

  // GUILT (G1) — the cardinalities are pinned by LITERAL, not derived from
  // the lists above: the generator and the property test read the SAME
  // lists, so a mutation that shrinks one shrinks both sides symmetrically
  // and would otherwise stay green. Delete an entry from any list and this
  // test names which one, alongside a literal GUILT_FIXTURES row going red
  // for the same deletion (see the four mutation proofs in the PR body).
  it("pins the negation generator's own source lists — a shrink here is a guard hole, not a refactor (G1)", () => {
    expect(AUXILIARIES).toHaveLength(11);
    expect(NEGATIONS).toHaveLength(4);
    expect(EFFECT_VERBS).toHaveLength(6);
    expect(Object.keys(IRREGULAR_CONTRACTIONS)).toHaveLength(3);
    expect(Object.values(IRREGULAR_CONTRACTIONS).flat()).toHaveLength(4);
    expect(ID_NEGATORS).toHaveLength(2);
    expect(ID_VERBS).toHaveLength(6);
  });

  const BANNED_PATTERNS: BannedPattern[] = [
    ...buildNegationPatterns(),
    {
      name: "EN 'no issue/problem/concern/bearing/effect/impact/risk(s)'",
      re: /\bno\s+(?:issue|problem|concern|bearing|effect|impact|risk)s?\b/gi,
    },
    { name: "EN stem: clear (unclear allowlisted below)", re: /clear/gi },
    { name: "EN stem: approv", re: /approv/gi },
    { name: "EN stem: guarantee", re: /guarantee/gi },
    { name: "EN 'eligible regardless'", re: /eligible\s+regardless/gi },
    buildIdNegationPattern(),
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
    // "persetujuan" ("consent") is the per-...-an NOMINALIZATION of
    // "setuju" — that prefix is not nasal, so it keeps the literal stem
    // (unlike "menyetujui", which already evades the family per the
    // comment above) and needs its own entry. Slice A7-M (2026-09-22):
    // `why.guardian_consent.id` names WHAT is being asked for — legal
    // consent under UU PDP — not a reassurance that the applicant's case
    // will be approved. The "setuju" family exists to catch the latter
    // ("kami sudah setuju", "pasti disetujui"); this is the domain noun
    // for the exact fact `person.guardian_consent` records, with no
    // synonym that both avoids the stem and keeps the legal term precise.
    /\bpersetujuan\b/gi,
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
    // A3'-M (FIX-5): the SOURCELESS_NO_PATH_CODES slice of SUPPORT_REASON_
    // COPY joins the scan too — the sourceless dead end's copy lives there,
    // never in noticeConditionCopy, so it needs its own source table rather
    // than smuggling it into the notice one.
    sourcelessNoPathCopy: Record<string, { en: string; id: string }>;
    translate: (
      language: "en" | "id",
      key:
        | "outcome.conditions.title"
        | "outcome.conditions.intro"
        // Slice A3-M (DRAFT-SPEC-A3-1.v2-M §4.1, M5): the scan is extended
        // to cover the review-gate question/reason copy too, since M6
        // rewrites both to stop promising a human review the engine no
        // longer performs.
        | "q.review_gate.hint"
        | "why.review_gate"
        | "q.guardian_consent.help"
        | "why.guardian_consent"
        // Slice A6-3 (DRAFT-SPEC-A6-1.v3.md §3, clause A6-3): all six
        // `assumption.*` keys join the scan — three are rewritten
        // (`in_indonesia`, `work_payer`, `remote_clients`); the other
        // three (`permit_expiry`, `stay_days`, `generic`) are added to the
        // scan unchanged and must still read clean in both languages.
        | "assumption.in_indonesia"
        | "assumption.permit_expiry"
        | "assumption.stay_days"
        | "assumption.work_payer"
        | "assumption.remote_clients"
        // Slice A6-2 delta A6-4b (RATIFIED 2026-09-21T15:20:33Z, gate
        // H-1): the seven declared-conservative questions get their own
        // `assumption.*` string naming the value assumed, instead of
        // falling through to the generic "no value was inferred" text
        // that was now false for them.
        | "assumption.secondhome_deposit_usd"
        | "assumption.secondhome_property_value_usd"
        | "assumption.secondhome_passive_income_usd"
        | "assumption.secondhome_state_bank"
        | "assumption.secondhome_own_name"
        | "assumption.study_admission_confirmed"
        | "assumption.study_sponsor_confirmed"
        // Slice A6-bis: two more declared-conservative questions get their
        // own `assumption.*` string, same reason as A6-4b above.
        | "assumption.diaspora_documents"
        | "assumption.retirement_basis"
        | "assumption.generic",
    ) => string;
  }

  // A3'-M (FIX-5): built from SUPPORT_REASON_COPY by filtering on
  // SOURCELESS_NO_PATH_CODES, never hand-typed — a code added to the set
  // without copy would otherwise slip the scan silently.
  const SOURCELESS_NO_PATH_COPY: Record<string, { en: string; id: string }> =
    Object.fromEntries(
      [...SOURCELESS_NO_PATH_CODES].map((code) => [
        code,
        SUPPORT_REASON_COPY[code],
      ]),
    );

  const DEFAULT_SOURCE_TABLES: ConditionsBlockSourceTables = {
    noticeConditionCopy: NOTICE_CONDITION_COPY,
    genericNoticeCondition: GENERIC_NOTICE_CONDITION,
    sourcelessNoPathCopy: SOURCELESS_NO_PATH_COPY,
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
    // A3'-M (FIX-5): the sourceless dead end's own copy joins the scan.
    for (const [code, message] of Object.entries(tables.sourcelessNoPathCopy)) {
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
      // Slice A3-M (DRAFT-SPEC-A3-1.v2-M §4.1, M5): the review-gate
      // question hint and its "why" copy are now scanned too.
      "q.review_gate.hint",
      "why.review_gate",
      "q.guardian_consent.help",
      "why.guardian_consent",
      // Slice A6-3: all six `assumption.*` keys.
      "assumption.in_indonesia",
      "assumption.permit_expiry",
      "assumption.stay_days",
      "assumption.work_payer",
      "assumption.remote_clients",
      // Slice A6-2 delta A6-4b: the seven declared-conservative questions'
      // own assumption strings.
      "assumption.secondhome_deposit_usd",
      "assumption.secondhome_property_value_usd",
      "assumption.secondhome_passive_income_usd",
      "assumption.secondhome_state_bank",
      "assumption.secondhome_own_name",
      "assumption.study_admission_confirmed",
      "assumption.study_sponsor_confirmed",
      // Slice A6-bis: two more declared-conservative questions' own
      // assumption strings.
      "assumption.diaspora_documents",
      "assumption.retirement_basis",
      "assumption.generic",
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
    // Slice A3'-M (FIX-5): the ONE sourceless dead-end code — a LITERAL
    // name, not a spread, since it lives in SUPPORT_REASON_COPY (via
    // SOURCELESS_NO_PATH_CODES), never in NOTICE_CONDITION_COPY. Moves
    // this pin 68 - 2 (M6 retires DISCLOSED_ACTIVITY_BOUNDARY_CONDITION,
    // fourteen codes -> thirteen) + 2 (this one code, EN+ID) = 68, net zero.
    "DISCLOSED_ACTIVITY_BOUNDARY_NO_PATH",
    "GENERIC_NOTICE_CONDITION",
    "outcome.conditions.title",
    "outcome.conditions.intro",
    // Slice A3-M (DRAFT-SPEC-A3-1.v2-M §4.1, M5): exactly two literal
    // names — the three new CONDITION codes arrive on their own through
    // the `...Object.keys(NOTICE_CONDITION_COPY)` spread above.
    "q.review_gate.hint",
    "why.review_gate",
    // Slice A7-M (2026-09-22, M6): two more literal names — the new
    // question's help/why copy joins the scan, moving this pin 64 → 68
    // (two keys × two languages = four new entries).
    "q.guardian_consent.help",
    "why.guardian_consent",
    // Slice A6-3 (DRAFT-SPEC-A6-1.v3.md §3, F12): all six `assumption.*`
    // keys join the scan, moving this pin 38 → 50 (six keys × two
    // languages = twelve new entries).
    "assumption.in_indonesia",
    "assumption.permit_expiry",
    "assumption.stay_days",
    "assumption.work_payer",
    "assumption.remote_clients",
    // Slice A6-2 delta A6-4b (RATIFIED 2026-09-21T15:20:33Z, gate H-1):
    // the seven declared-conservative questions' own `assumption.*` keys
    // join the scan too, moving this pin 50 → 64 (seven keys × two
    // languages = fourteen new entries).
    "assumption.secondhome_deposit_usd",
    "assumption.secondhome_property_value_usd",
    "assumption.secondhome_passive_income_usd",
    "assumption.secondhome_state_bank",
    "assumption.secondhome_own_name",
    "assumption.study_admission_confirmed",
    "assumption.study_sponsor_confirmed",
    // Slice A6-bis: two more declared-conservative questions' own
    // `assumption.*` keys join the scan, moving this pin 68 → 72 (two keys
    // × two languages = four new entries).
    "assumption.diaspora_documents",
    "assumption.retirement_basis",
    "assumption.generic",
  ].sort();

  it("pins the scan's own iteration: exactly the title, intro, generic fallback, thirteen codes, guardian consent, one sourceless dead-end code and fifteen assumption keys, both languages (V3, A6-3 + A6-4b + A6-bis + A7-M + A3'-M FIX-5)", () => {
    const entries = conditionsBlockEntries();
    expect(entries).toHaveLength(72);
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

  it("innocence: all 72 shipped strings pass the scan clean", () => {
    const hits = scanConditionsBlock();
    expect(hits, JSON.stringify(hits)).toEqual([]);
  });

  function a5EntryBuilder(): ConditionsBlockEntry[] {
    const entries: ConditionsBlockEntry[] = [];
    const elements = REVIEW_REASON_ELEMENTS.DISCLOSED_CRIMINAL_RECORD_REVIEW!;
    for (const field of ["rule", "checked", "prepare", "handling"] as const) {
      entries.push({
        key: `DISCLOSED_CRIMINAL_RECORD_REVIEW.${field}`,
        language: "en",
        text: elements[field].en,
      });
      entries.push({
        key: `DISCLOSED_CRIMINAL_RECORD_REVIEW.${field}`,
        language: "id",
        text: elements[field].id,
      });
    }
    for (const language of ["en", "id"] as const) {
      entries.push({
        key: "outcome.disclaimer.complex_to_human",
        language,
        text: translate(
          language,
          "outcome.disclaimer.complex_to_human" as I18nKey,
        ),
      });
    }
    for (const key of [
      "outcome.review.element.rule",
      "outcome.review.element.checked",
      "outcome.review.element.prepare",
      "outcome.review.element.handling",
    ] as const) {
      entries.push({
        key,
        language: "en",
        text: translate("en", key as I18nKey),
      });
      entries.push({
        key,
        language: "id",
        text: translate("id", key as I18nKey),
      });
    }
    return entries;
  }

  it("pins and scans all 18 A5 strings", () => {
    const entries = a5EntryBuilder();
    expect(entries).toHaveLength(18);
    expect(entries.filter((entry) => findBannedPattern(entry.text))).toEqual(
      [],
    );
  });

  it("a5 scan innocence: the matcher catches a certainty phrase", () => {
    expect(findBannedPattern("does not change the result")).toBeDefined();
  });

  // G2/G3 — the property test enumerates the FULL 11×4×6 EN product (264
  // combinations) and synthesises ≥264 sentences, one per generated FORM:
  // most combinations produce exactly one form, but a contracted
  // combination (NEGATIONS' "n't"/"n’t") on an IRREGULAR_CONTRACTIONS
  // auxiliary produces one form PER MAP ENTRY instead — `can` holds two
  // (can't, cannot), which is the "≥264" and the reason the pinned count
  // below exceeds the bare product. This is what makes an omission
  // impossible by construction: a token lives in exactly one place (the
  // lists above), and every token each list holds is proven RED here, in
  // the SAME run that proves the 28 shipped strings GREEN (G4) — over-
  // generation (e.g. "does never affect", not real English) is harmless,
  // because innocence is the only fence on breadth, not this test.
  interface GeneratedNegationCase {
    label: string;
    language: "en" | "id";
    sentence: string;
  }

  function buildEnNegationCases(): GeneratedNegationCase[] {
    const cases: GeneratedNegationCase[] = [];
    for (const aux of AUXILIARIES) {
      for (const negation of NEGATIONS) {
        for (const verb of EFFECT_VERBS) {
          if (!/['’]/.test(negation)) {
            // spaced: "not" or "never", a separate word after the aux
            cases.push({
              label: `${aux} ${negation} ${verb} (spaced)`,
              language: "en",
              sentence: `These ${aux} ${negation} ${verb} the result above.`,
            });
            continue;
          }
          // contracted: "n't" or "n’t" — the apostrophe THIS combination
          // carries, used only by the regular fall-through; an irregular
          // auxiliary ignores it and emits its map's own literal forms.
          const apostrophe = negation === "n't" ? "'" : "’";
          const irregular = IRREGULAR_CONTRACTIONS[aux];
          const forms = irregular ?? [`${aux}n${apostrophe}t`];
          for (const form of forms) {
            cases.push({
              label: `${aux} ${negation} ${verb} → "${form}" (contracted)`,
              language: "en",
              sentence: `These ${form} ${verb} the result above.`,
            });
          }
        }
      }
    }
    return cases;
  }

  function assertAllCasesCaught(cases: GeneratedNegationCase[]): void {
    const failures = cases.filter((generated) => {
      const tables = buildInjectedTables({
        label: generated.label,
        key: "outcome.conditions.intro",
        language: generated.language,
        text: generated.sentence,
      });
      const hits = scanConditionsBlock(tables);
      return !hits.some(
        (hit) =>
          hit.key === "outcome.conditions.intro" &&
          hit.language === generated.language,
      );
    });
    // Asserted on the WHOLE set at once, not a loop stopping at the first —
    // an omission anywhere in the lists shows up as every case it produced.
    expect(failures, JSON.stringify(failures, null, 2)).toEqual([]);
  }

  it("property test: every synthesised form of the full 11×4×6 EN negation product is reported by the scan (G2/G3)", () => {
    const cases = buildEnNegationCases();
    // 264 combinations, +12 extra forms from `can`'s two-entry map (12
    // contracted combinations × one extra form each) = 276. A shrink in
    // any of AUXILIARIES/NEGATIONS/EFFECT_VERBS/IRREGULAR_CONTRACTIONS
    // moves this number — that is the point of pinning it by literal.
    expect(cases).toHaveLength(276);
    assertAllCasesCaught(cases);
  });

  // G5 — the ID mirror, same construction and same property-test shape:
  // `["tidak","tak"]` × optional `akan` × the six ID verbs.
  function buildIdNegationCases(): GeneratedNegationCase[] {
    const cases: GeneratedNegationCase[] = [];
    for (const negator of ID_NEGATORS) {
      for (const withAkan of [false, true]) {
        for (const verb of ID_VERBS) {
          const middle = withAkan ? `akan ${verb}` : verb;
          cases.push({
            label: `${negator} ${withAkan ? "akan " : ""}${verb}`,
            language: "id",
            sentence: `Kondisi ini ${negator} ${middle} hasil di atas.`,
          });
        }
      }
    }
    return cases;
  }

  it("property test: every synthesised form of the full 2×2×6 ID negation product is reported by the scan (G5)", () => {
    const cases = buildIdNegationCases();
    // 2 negators × (with/without "akan") × 6 verbs = 24, no multi-form
    // auxiliary on this side to push it past the bare product.
    expect(cases).toHaveLength(24);
    assertAllCasesCaught(cases);
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
    {
      label:
        "G12: OBS-A2c-1 — contracted 'don't', one apostrophe from the EXACT EN string S1 ordered removed",
      key: "outcome.conditions.intro",
      language: "en",
      text: "These don't change the result above.",
    },
    {
      label:
        "G13: OBS-A2c-1 — contracted 'don’t' (curly apostrophe), same shape as G12",
      key: "outcome.conditions.intro",
      language: "en",
      text: "These don’t affect the result above.",
    },
    {
      label:
        "G14: OBS-A2c-1 — 'shall' contracts irregularly to shan't, same shape as G12/G13",
      key: "outcome.conditions.intro",
      language: "en",
      text: "These shan't change the result above.",
    },
    // Slice A2-G (G7): three LITERAL rows, one per mutation this PR's
    // GUILT proofs name — a fixture does not shrink when a list does,
    // which is what makes each mutation red for the reason it claims (the
    // property test's own generator would NOT catch the `will` deletion:
    // see the PR body's mutation 2).
    {
      label:
        "PR-G/1 (G3 mutation proof): literal 'won't' — deleting IRREGULAR_CONTRACTIONS.will makes the property test synthesise and match 'willn't' instead, so only a literal exposes the loss",
      key: "outcome.conditions.intro",
      language: "en",
      text: "These won't change the result above.",
    },
    {
      label:
        "PR-G/2 (G1 mutation proof): literal 'matter' — EFFECT_VERBS' sixth entry, contracted-family shape",
      key: "outcome.conditions.intro",
      language: "en",
      text: "This detail doesn't matter for the result above.",
    },
    {
      label:
        "PR-G/3 (G1/G5 mutation proof, OBS-A2c-8): literal 'tak berpengaruh' — the ID mirror's second negator, the everyday contraction of 'tidak'",
      key: "outcome.conditions.intro",
      language: "id",
      text: "Kondisi ini tak berpengaruh terhadap hasil Anda.",
    },
    {
      label:
        "A3'-M FIX-5: 'cleared' plant on the new sourceless dead-end copy — proves the scan reaches SUPPORT_REASON_COPY's SOURCELESS_NO_PATH_CODES entry, not just NOTICE_CONDITION_COPY",
      key: "DISCLOSED_ACTIVITY_BOUNDARY_NO_PATH",
      language: "en",
      text: "One of your answers is one our verified rules cannot assess; you are cleared for a consultation.",
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
    if (fixture.key === "DISCLOSED_ACTIVITY_BOUNDARY_NO_PATH") {
      // A3'-M (FIX-5): routed to the NEW table, never noticeConditionCopy —
      // this is the proof the scan really reaches SUPPORT_REASON_COPY's
      // sourceless entry, not a lucky hit through the wrong bucket.
      return {
        ...DEFAULT_SOURCE_TABLES,
        sourcelessNoPathCopy: {
          ...DEFAULT_SOURCE_TABLES.sourcelessNoPathCopy,
          [fixture.key]: {
            ...DEFAULT_SOURCE_TABLES.sourcelessNoPathCopy[fixture.key],
            [fixture.language]: fixture.text,
          },
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

describe("prohibitedActivities adapter mapping (PR-20)", () => {
  function responseForProduct(
    productCode: string,
    prohibitedActivities: string[] | undefined,
  ) {
    const response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
    response.decision.candidates[0].product_code = productCode;
    response.display.candidates[0].product_code = productCode;
    if (prohibitedActivities === undefined) {
      delete (
        response.display.candidates[0] as unknown as Record<string, unknown>
      ).prohibited_activities;
    } else {
      response.display.candidates[0].prohibited_activities =
        prohibitedActivities;
    }
    return parseVisaOracleEvaluateResponse(response);
  }

  it("maps prohibited_activities in order, deduplicates repeated identifiers, and maps an absent or empty list to []", () => {
    const absentOutcome = buildEngineOutcome(
      responseForProduct("C1", undefined),
    );
    expect(absentOutcome.candidates[0]?.prohibitedActivities).toEqual([]);

    const emptyOutcome = buildEngineOutcome(responseForProduct("C1", []));
    expect(emptyOutcome.candidates[0]?.prohibitedActivities).toEqual([]);

    const outcome = buildEngineOutcome(
      responseForProduct("E33G", [
        "overstay",
        "overstay",
        "sale_of_goods_or_services_beyond_remote_work",
        "work_for_indonesian_entity",
        "sale_of_goods_or_services_beyond_remote_work",
      ]),
    );
    expect(outcome.candidates[0]?.prohibitedActivities).toEqual([
      PROHIBITED_ACTIVITY_COPY.overstay,
      PROHIBITED_ACTIVITY_COPY.sale_of_goods_or_services_beyond_remote_work,
      PROHIBITED_ACTIVITY_COPY.work_for_indonesian_entity,
    ]);
  });

  it("resolves work_inconsistent_with_permit to dual-activity reporting only on E33 and E33E, and keeps the base copy on E33A/B/C/F", () => {
    for (const code of ["E33", "E33E"] as const) {
      const outcome = buildEngineOutcome(
        responseForProduct(code, [
          "overstay",
          "work_inconsistent_with_permit",
          "sale_of_goods_or_services",
        ]),
      );
      expect(outcome.candidates[0]?.prohibitedActivities).toEqual([
        PROHIBITED_ACTIVITY_COPY.overstay,
        PROHIBITED_ACTIVITY_PRODUCT_COPY[code].work_inconsistent_with_permit,
        PROHIBITED_ACTIVITY_COPY.sale_of_goods_or_services,
      ]);
      expect(outcome.candidates[0]?.prohibitedActivities[1]?.en).toContain(
        "reporting it to Immigration as a dual activity",
      );
      expect(outcome.candidates[0]?.prohibitedActivities[1]?.id).toContain(
        "melaporkannya ke Imigrasi sebagai rangkap kegiatan",
      );
    }

    for (const code of ["E33A", "E33B", "E33C", "E33F"] as const) {
      const outcome = buildEngineOutcome(
        responseForProduct(code, [
          "overstay",
          "work_inconsistent_with_permit",
          "sale_of_goods_or_services",
        ]),
      );
      expect(outcome.candidates[0]?.prohibitedActivities).toEqual([
        PROHIBITED_ACTIVITY_COPY.overstay,
        PROHIBITED_ACTIVITY_COPY.work_inconsistent_with_permit,
        PROHIBITED_ACTIVITY_COPY.sale_of_goods_or_services,
      ]);
      expect(outcome.candidates[0]?.prohibitedActivities[1]?.en).not.toMatch(
        /dual activity|rangkap/i,
      );
      expect(outcome.candidates[0]?.prohibitedActivities[1]?.id).not.toMatch(
        /rangkap kegiatan|melaporkan/i,
      );
    }
  });

  it("silently drops unknown and Object.prototype identifiers without throwing or leaking raw codes into the view model", () => {
    const outcome = buildEngineOutcome(
      responseForProduct("E33", [
        "overstay",
        "unknown_future_identifier_code",
        "constructor",
        "toString",
        "sale_of_goods_or_services",
      ]),
    );
    expect(outcome.candidates[0]?.prohibitedActivities).toEqual([
      PROHIBITED_ACTIVITY_COPY.overstay,
      PROHIBITED_ACTIVITY_COPY.sale_of_goods_or_services,
    ]);
    expect(JSON.stringify(outcome)).not.toContain(
      "unknown_future_identifier_code",
    );

    const protoOnly = buildEngineOutcome(
      responseForProduct("constructor", ["constructor", "toString"]),
    );
    expect(protoOnly.candidates[0]?.prohibitedActivities).toEqual([]);
  });
});

describe("V05 product-aware next steps: free A1 and onshore-only BRIDGING", () => {
  const HERE = path.dirname(fileURLToPath(import.meta.url));
  const REPO = path.resolve(HERE, "../../../../../../..");

  function outcomeFor(...productCodes: string[]) {
    const response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
    const [decision] = response.decision.candidates;
    const [display] = response.display.candidates;
    response.decision.candidates = productCodes.map((code, index) => ({
      ...decision,
      rank: index + 1,
      product_code: code,
      product_version_id: `22222222-2222-4222-8222-22222222222${index}`,
    }));
    response.display.candidates = productCodes.map((code, index) => ({
      ...display,
      rank: index + 1,
      product_code: code,
      product_version_id: `22222222-2222-4222-8222-22222222222${index}`,
    }));
    return buildEngineOutcome(parseVisaOracleEvaluateResponse(response));
  }

  const joined = (steps: ReturnType<typeof nextStepsFor>, lang: "en" | "id") =>
    steps.map((item) => item.title[lang]).join("\n");

  it("A1 alone: exactly the three official-page steps, no quote, timing or advisor step, EN and ID", () => {
    const { nextSteps } = outcomeFor("A1");
    expect(nextSteps.map((item) => item.id)).toEqual([
      "free-visit-arrival-documents",
      "free-visit-thirty-days",
      "free-visit-no-selling-or-paid-work",
    ]);
    expect(nextSteps).toBe(
      nextStepsFor("SUPPORTED_CANDIDATES", { productCodes: ["A1"] }),
    );
    for (const lang of ["en", "id"] as const) {
      expect(joined(nextSteps, lang)).not.toMatch(
        /quote|timing|price|advisor|e-?form|book travel|penawaran|jadwal|harga|konsultan|formulir|pesan perjalanan/i,
      );
    }
    expect(nextSteps.map((item) => item.title)).toEqual([
      {
        en: "At arrival, show a valid passport with at least 6 months left before it expires, and a return ticket or a ticket onward to another country (the official page exempts transport crew who stop over to join their vessel and travel on).",
        id: "Saat kedatangan, tunjukkan paspor yang sah dan masih berlaku paling singkat 6 bulan sebelum masa berlakunya habis, serta tiket kembali atau tiket terusan ke negara lain (halaman resmi mengecualikan awak alat angkut yang singgah untuk bergabung dengan kapalnya dan melanjutkan perjalanan).",
      },
      {
        en: "You can stay up to 30 days from the day you arrive. This stay cannot be extended or converted into another stay permit.",
        id: "Anda dapat tinggal maksimal 30 hari sejak tanggal kedatangan. Izin tinggal ini tidak dapat diperpanjang dan tidak dapat dialihkan menjadi izin tinggal lain.",
      },
      {
        en: "Do not sell goods or services, and do not receive payment or wages for work or business from anyone in Indonesia.",
        id: "Jangan menjual barang atau jasa, dan jangan menerima imbalan atau upah atas kerja atau usaha dari siapa pun di Indonesia.",
      },
    ]);
    expect(nextSteps[0].title.en).toMatch(/at least 6 months/);
    expect(nextSteps[0].title.en).toMatch(/transport crew/);
    expect(nextSteps[0].title.id).toMatch(/awak alat angkut/);
    expect(nextSteps[0].title.en).toMatch(/return ticket or a ticket onward/);
    expect(nextSteps[0].title.id).toMatch(/paling singkat 6 bulan/);
    expect(nextSteps[0].title.id).toMatch(/tiket kembali atau tiket terusan/);
    expect(nextSteps[1]?.title.en).toMatch(
      /30 days[^]*cannot be extended or converted/,
    );
    expect(nextSteps[1]?.title.id).toMatch(
      /30 hari[^]*tidak dapat diperpanjang dan tidak dapat dialihkan/,
    );
    expect(nextSteps[2]?.title.en).toMatch(/sell goods or services/);
    expect(nextSteps[2]?.title.id).toMatch(/menjual barang atau jasa/);
  });

  it("A1 next to another product keeps the generic list (a quote can exist)", () => {
    const generic = nextStepsFor("SUPPORTED_CANDIDATES");
    expect(outcomeFor("A1", "B1").nextSteps).toBe(generic);
    expect(outcomeFor("C1").nextSteps).toBe(generic);
  });

  it("the A1 items are quoted from the saved official A1 page", () => {
    const dir = path.join(REPO, "research/visa/2026-10-14-v05-a1-page");
    const file = fs.readdirSync(dir).find((name) => name.endsWith(".txt"));
    expect(file).toBeDefined();
    const lines = fs.readFileSync(path.join(dir, file!), "utf-8").split("\n");
    const at = (n: number) => lines[n - 1];
    expect(at(87)).toMatch(
      /paspor yang sah dan masih berlaku paling singkat 6 bulan sebelum masa berlakunya habis/,
    );
    expect(at(88)).toMatch(/tiket kembali atau tiket terusan ke negara lain/);
    expect(at(77)).toMatch(
      /maksimal 30 hari, dihitung sejak tanggal kedatangan/,
    );
    expect(at(75)).toMatch(
      /tidak dapat diperpanjang dan tidak dapat dialihkan menjadi izin tinggal lain/,
    );
    expect(at(95)).toMatch(
      /dilarang menjual barang atau jasa atau menerima imbalan, upah/,
    );
  });

  it("BRIDGING: the steps carry the exit warning, EN and ID", () => {
    for (const codes of [["BRIDGING"], ["BRIDGING", "B1"]]) {
      const { nextSteps } = outcomeFor(...codes);
      const exit = nextSteps.find(
        (item) => item.id === "bridging-do-not-leave-indonesia",
      );
      expect(exit?.title.en).toMatch(/do not leave Indonesia while/i);
      expect(exit?.title.id).toMatch(
        /jangan keluar dari wilayah Indonesia selama/i,
      );
      expect(exit?.title.en).toMatch(/stops being valid if you leave/);
      expect(exit?.title.id).toMatch(/tidak berlaku lagi apabila Anda keluar/);
    }
    expect(
      outcomeFor("BRIDGING").nextSteps.find(
        (item) => item.id === "bridging-do-not-leave-indonesia",
      )?.title,
    ).toEqual({
      en: "Do not leave Indonesia while the Bridging permit is in use: it stops being valid if you leave.",
      id: "Jangan keluar dari wilayah Indonesia selama Izin Tinggal Peralihan digunakan: izin ini tidak berlaku lagi apabila Anda keluar.",
    });
    expect(outcomeFor("BRIDGING").nextSteps).toHaveLength(3);
    expect(outcomeFor("BRIDGING", "B1").nextSteps).toHaveLength(3);
  });

  it("BRIDGING exit warning is quoted from the saved official press release", () => {
    const dir = path.join(
      REPO,
      "research/visa/2026-10-13-organ-reattest-seq29/text",
    );
    const file = fs
      .readdirSync(dir)
      .find((name) => name.startsWith("3da72c7b-"));
    const line = fs
      .readFileSync(path.join(dir, file!), "utf-8")
      .split("\n")[58];
    expect(line).toMatch(/hanya berlaku secara onshore/);
    expect(line).toMatch(
      /tidak berlaku lagi apabila WNA keluar wilayah Indonesia/,
    );
  });

  it("the product-aware lists carry no advisor promise and no fee split", () => {
    for (const steps of [
      outcomeFor("A1").nextSteps,
      outcomeFor("BRIDGING").nextSteps,
      outcomeFor("BRIDGING", "B1").nextSteps,
    ]) {
      for (const lang of ["en", "id"] as const) {
        expect(joined(steps, lang)).not.toMatch(
          /\b(we|our team|advisor (will|reviews|confirms))\b|kami|tim kami|konsultan (akan|memastikan)|PNBP|service fee|biaya jasa/i,
        );
      }
    }
  });
});

describe("stay-permit length, verified renewal, and longer-stay continuation (PR-7)", () => {
  function makePricedResponse(
    code = "E33F",
    amount = 14_000_000,
    pricingKey = { category: "visa", item_key: code },
  ) {
    const response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
    const candidate = response.display.candidates[0];
    response.decision.candidates[0].product_code = code;
    candidate.product_code = code;
    candidate.pricing = {
      status: "AVAILABLE",
      reason_code: "PRICE_AVAILABLE",
      evaluated_at: TEST_NOW,
      catalog_last_updated: "2026-08-03",
      catalog_sha256: "b".repeat(64),
      row_sha256: "c".repeat(64),
    };
    response.decision.quotes = [
      {
        quote_id: "55555555-5555-4555-8555-555555555555",
        product_version_id: candidate.product_version_id,
        product_code: code,
        status: "AVAILABLE",
        currency: "IDR",
        amount,
        pricing_key: pricingKey,
        catalog_version: "2026.08",
        catalog_sha256: "b".repeat(64),
        row_sha256: "c".repeat(64),
        quoted_at: TEST_NOW,
        valid_until: "2026-08-10T04:00:00Z",
        reason_code: "PRICE_AVAILABLE",
      },
    ];
    return response;
  }

  it("shows 1-year length, verified renewal, and continues-by-renewal for E33F and E33G within 2190-day coverage, and advisor line above 2190", () => {
    for (const code of ["E33F", "E33G"] as const) {
      const response = makePricedResponse(code, 14_000_000);
      response.display.candidates[0].stay_policy = {
        stay: {
          kind: "FIXED_DAYS",
          minimum_days: 365,
          maximum_days: 365,
        },
        extension: {
          status: "VERIFIED",
          reason_code: null,
          allowed: true,
          maximum_extensions: 5,
          days_per_extension: 365,
        },
      };

      const outcome = buildEngineOutcome(response, {
        facts: { stay_days: "400" },
      });
      if (outcome.state !== "SUPPORTED_CANDIDATES") {
        throw new Error("expected SUPPORTED_CANDIDATES");
      }
      const duration = outcome.candidates[0].duration;
      expect(duration).toEqual({
        selectedDays: 365,
        options: [],
        extensionRequired: false,
        renewal: {
          en: "This permit is renewable 1 year at a time, up to 5 times.",
          id: "Izin tinggal ini dapat diperpanjang hingga 5 kali, masing-masing 1 tahun.",
        },
        longerStay: {
          en: "Your planned stay is longer than the first permit — your stay can continue by renewal.",
          id: "Rencana tinggal Anda lebih lama dari izin pertama — masa tinggal Anda dapat dilanjutkan dengan perpanjangan.",
        },
      });

      // When requested stay_days do not exceed the first permit, longerStay is omitted.
      const withinFirstPermit = buildEngineOutcome(response, {
        facts: { stay_days: "365" },
      });
      if (withinFirstPermit.state !== "SUPPORTED_CANDIDATES") {
        throw new Error("expected SUPPORTED_CANDIDATES");
      }
      expect(
        withinFirstPermit.candidates[0].duration?.longerStay,
      ).toBeUndefined();
      expect(withinFirstPermit.candidates[0].duration?.renewal?.en).toContain(
        "renewable 1 year at a time, up to 5 times",
      );

      // Guilt boundary: max coverage = 365 + 5 * 365 = 2190 days -> verified line.
      const atMaxCoverage = buildEngineOutcome(response, {
        facts: { stay_days: "2190" },
      });
      if (atMaxCoverage.state !== "SUPPORTED_CANDIDATES") {
        throw new Error("expected SUPPORTED_CANDIDATES");
      }
      expect(atMaxCoverage.candidates[0].duration?.longerStay).toEqual(
        STAY_PERMIT_LONGER_STAY_COPY.verified,
      );

      // Guilt boundary: 2191, 3000, and 36500 exceed 2190-day coverage -> advisor (unknown) line, not verified.
      for (const days of ["2191", "3000", "36500"] as const) {
        const beyondCoverage = buildEngineOutcome(response, {
          facts: { stay_days: days },
        });
        if (beyondCoverage.state !== "SUPPORTED_CANDIDATES") {
          throw new Error("expected SUPPORTED_CANDIDATES");
        }
        expect(
          beyondCoverage.candidates[0].duration?.longerStay,
          `${code} at ${days} days`,
        ).toEqual(STAY_PERMIT_LONGER_STAY_COPY.unknown);
        expect(beyondCoverage.candidates[0].duration?.longerStay).not.toEqual(
          STAY_PERMIT_LONGER_STAY_COPY.verified,
        );
      }
    }
  });

  it("shows 1-year length with no renewal sentence for priced Working KITAS (E23), verified continuation at 600 days, and advisor line at 800 days", () => {
    const response = makePricedResponse("E23", 14_000_000, {
      category: "kitas_permits",
      item_key: "Working KITAS",
    });
    response.display.candidates[0].name = {
      en: "Working KITAS",
      id: "KITAS Kerja",
    };
    response.display.candidates[0].stay_policy = {
      stay: {
        kind: "FIXED_DAYS",
        minimum_days: 365,
        maximum_days: 365,
      },
      extension: {
        status: "VERIFIED",
        reason_code: null,
        allowed: true,
        maximum_extensions: 1,
        days_per_extension: 365,
      },
    };

    const withinFirst = buildEngineOutcome(response, {
      facts: { stay_days: "365" },
    });
    if (withinFirst.state !== "SUPPORTED_CANDIDATES") {
      throw new Error("expected SUPPORTED_CANDIDATES");
    }
    expect(withinFirst.candidates[0].duration).toEqual({
      selectedDays: 365,
      options: [],
      extensionRequired: false,
    });
    expect(withinFirst.candidates[0].duration?.renewal).toBeUndefined();
    expect(withinFirst.candidates[0].duration?.longerStay).toBeUndefined();

    // 600 days <= coverage (365 + 1 * 365 = 730) -> verified continuation line, still no renewal sentence.
    const at600 = buildEngineOutcome(response, {
      facts: { stay_days: "600" },
    });
    if (at600.state !== "SUPPORTED_CANDIDATES") {
      throw new Error("expected SUPPORTED_CANDIDATES");
    }
    expect(at600.candidates[0].duration).toEqual({
      selectedDays: 365,
      options: [],
      extensionRequired: false,
      longerStay: STAY_PERMIT_LONGER_STAY_COPY.verified,
    });
    expect(at600.candidates[0].duration?.renewal).toBeUndefined();

    // 800 days > coverage (730) -> unknown (advisor) line, not verified.
    const at800 = buildEngineOutcome(response, {
      facts: { stay_days: "800" },
    });
    if (at800.state !== "SUPPORTED_CANDIDATES") {
      throw new Error("expected SUPPORTED_CANDIDATES");
    }
    expect(at800.candidates[0].duration).toEqual({
      selectedDays: 365,
      options: [],
      extensionRequired: false,
      longerStay: STAY_PERMIT_LONGER_STAY_COPY.unknown,
    });
    expect(at800.candidates[0].duration?.renewal).toBeUndefined();
  });

  it("shows 5-year length for E33 and E33E with no extension sentence, and advisor longer-stay note when stay_days exceed 1825", () => {
    for (const [code, amount] of [
      ["E33", 19_000_000],
      ["E33E", 45_000_000],
    ] as const) {
      const response = makePricedResponse(code, amount);
      response.display.candidates[0].stay_policy = {
        stay: {
          kind: "FIXED_DAYS",
          minimum_days: 1825,
          maximum_days: 1825,
        },
        extension: {
          status: "UNKNOWN",
          reason_code: "EXTENSION_POLICY_NOT_VERIFIED",
          allowed: false,
          maximum_extensions: 0,
          days_per_extension: null,
        },
      };

      const normal = buildEngineOutcome(response, {
        facts: { stay_days: "1825" },
      });
      if (normal.state !== "SUPPORTED_CANDIDATES") {
        throw new Error("expected SUPPORTED_CANDIDATES");
      }
      expect(normal.candidates[0].price).toMatchObject({
        status: "AVAILABLE",
        amount,
      });
      expect(normal.candidates[0].duration).toEqual({
        selectedDays: 1825,
        options: [],
        extensionRequired: false,
      });
      expect(normal.candidates[0].duration?.renewal).toBeUndefined();
      expect(normal.candidates[0].duration?.longerStay).toBeUndefined();

      const longer = buildEngineOutcome(response, {
        facts: { stay_days: "2000" },
      });
      if (longer.state !== "SUPPORTED_CANDIDATES") {
        throw new Error("expected SUPPORTED_CANDIDATES");
      }
      expect(longer.candidates[0].duration?.renewal).toBeUndefined();
      expect(longer.candidates[0].duration?.longerStay).toEqual({
        en: "Your planned stay is longer than the first permit — a Bali Zero advisor confirms how a longer stay continues.",
        id: "Rencana tinggal Anda lebih lama dari izin pertama — konsultan Bali Zero akan memastikan cara melanjutkan masa tinggal yang lebih lama.",
      });
    }
  });

  it("omits permit length for unquoted candidates (E33A, E33B, E33C)", () => {
    for (const code of ["E33A", "E33B", "E33C"] as const) {
      const response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
      response.decision.candidates[0].product_code = code;
      response.display.candidates[0].product_code = code;
      response.decision.quotes = [];
      response.display.candidates[0].pricing.status = "UNAVAILABLE";
      response.display.candidates[0].stay_policy = {
        stay: {
          kind: "FIXED_DAYS",
          minimum_days: 1825,
          maximum_days: 1825,
        },
        extension: {
          status: "UNKNOWN",
          reason_code: "EXTENSION_POLICY_NOT_VERIFIED",
          allowed: false,
          maximum_extensions: 0,
          days_per_extension: null,
        },
      };

      const outcome = buildEngineOutcome(response, {
        facts: { stay_days: "2000" },
      });
      if (outcome.state !== "SUPPORTED_CANDIDATES") {
        throw new Error("expected SUPPORTED_CANDIDATES");
      }
      expect(outcome.candidates[0].price.status).not.toBe("AVAILABLE");
      expect(outcome.candidates[0].duration).toBeUndefined();
    }
  });

  it("keeps E31 duration-option candidates unchanged", () => {
    const response = makePricedResponse("E31A", 1_000_000, {
      category: "test",
      item_key: "test_item",
    });
    response.display.candidates[0].selected_duration_days = 365;
    response.display.candidates[0].extension_required = true;
    response.display.candidates[0].duration_options = [
      {
        days: 365,
        pricing_key: { category: "test", item_key: "test_item" },
        amount_idr: 1_000_000,
        selected: true,
        status: "AVAILABLE",
        reason_code: "PRICE_AVAILABLE",
      },
      {
        days: 730,
        pricing_key: { category: "test", item_key: "test_item_2y" },
        amount_idr: 2_000_000,
        selected: false,
        status: "AVAILABLE",
        reason_code: "PRICE_AVAILABLE",
      },
    ];
    response.display.candidates[0].stay_policy = {
      stay: {
        kind: "FIXED_DAYS",
        minimum_days: 365,
        maximum_days: 365,
      },
      extension: {
        status: "VERIFIED",
        reason_code: null,
        allowed: true,
        maximum_extensions: 5,
        days_per_extension: 365,
      },
    };

    const outcome = buildEngineOutcome(response, {
      facts: { stay_days: "400" },
    });
    if (outcome.state !== "SUPPORTED_CANDIDATES") {
      throw new Error("expected SUPPORTED_CANDIDATES");
    }
    expect(outcome.candidates[0].duration).toEqual({
      selectedDays: 365,
      options: [
        { days: 365, amountIdr: 1_000_000, selected: true },
        { days: 730, amountIdr: 2_000_000, selected: false },
      ],
      extensionRequired: true,
    });
  });

  it.each([null, undefined, "UNKNOWN"] as const)(
    "guilt: extension with status=%s and allowed=true renders no renewal line and no 'not extendable' text in EN or ID",
    (status) => {
      const response = makePricedResponse("E33F", 14_000_000);
      response.display.candidates[0].stay_policy = {
        stay: {
          kind: "FIXED_DAYS",
          minimum_days: 365,
          maximum_days: 365,
        },
        extension: {
          ...(status !== undefined ? { status } : {}),
          reason_code: null,
          allowed: true,
          maximum_extensions: 5,
          days_per_extension: 365,
        },
      };

      const outcome = buildEngineOutcome(response, {
        facts: { stay_days: "400" },
      });
      if (outcome.state !== "SUPPORTED_CANDIDATES") {
        throw new Error("expected SUPPORTED_CANDIDATES");
      }
      const duration = outcome.candidates[0].duration;
      expect(duration?.selectedDays).toBe(365);
      // Mutation check: turning `extension.status === "VERIFIED"` into `allowed === true` alone MUST turn this assertion RED.
      expect(duration?.renewal).toBeUndefined();
      expect(duration?.longerStay).toEqual(
        STAY_PERMIT_LONGER_STAY_COPY.unknown,
      );
      expect(JSON.stringify(duration)).not.toMatch(
        /not extendable|tidak dapat diperpanjang/i,
      );
    },
  );

  it("guilt: signed-pack E28A (730 + 100x365), E30A (365/730 UNKNOWN), BRIDGING (FIXED_DAYS null/60), and A1 (30/30 no extensions) render no unauthorized length, renewal, continuation, or raw identifiers", () => {
    // E28A signed-pack shape: 730-day fixed stay + maximum_extensions 100, days_per_extension 365 -> duration undefined
    const e28a = makePricedResponse("E28A", 20_000_000);
    e28a.display.candidates[0].stay_policy = {
      stay: { kind: "FIXED_DAYS", minimum_days: 730, maximum_days: 730 },
      extension: {
        status: "VERIFIED",
        reason_code: null,
        allowed: true,
        maximum_extensions: 100,
        days_per_extension: 365,
      },
    };
    const e28aOutcome = buildEngineOutcome(e28a, {
      facts: { stay_days: "1000" },
    });
    if (e28aOutcome.state !== "SUPPORTED_CANDIDATES") {
      throw new Error("expected SUPPORTED_CANDIDATES");
    }
    expect(e28aOutcome.candidates[0].duration).toBeUndefined();

    // E30A signed-pack shape: FIXED_DAYS 365..730, extension UNKNOWN -> duration undefined
    const e30a = makePricedResponse("E30A", 15_000_000);
    e30a.display.candidates[0].stay_policy = {
      stay: { kind: "FIXED_DAYS", minimum_days: 365, maximum_days: 730 },
      extension: {
        status: "UNKNOWN",
        reason_code: "EXTENSION_POLICY_NOT_VERIFIED",
        allowed: false,
        maximum_extensions: 0,
        days_per_extension: null,
      },
    };
    const e30aOutcome = buildEngineOutcome(e30a, {
      facts: { stay_days: "900" },
    });
    if (e30aOutcome.state !== "SUPPORTED_CANDIDATES") {
      throw new Error("expected SUPPORTED_CANDIDATES");
    }
    expect(e30aOutcome.candidates[0].duration).toBeUndefined();

    // BRIDGING signed-pack shape: FIXED_DAYS minimum_days null, maximum_days 60 -> duration undefined
    const bridging = makePricedResponse("BRIDGING", 5_000_000);
    bridging.display.candidates[0].stay_policy = {
      stay: {
        kind: "FIXED_DAYS",
        minimum_days: null,
        maximum_days: 60,
      },
      extension: {
        status: "VERIFIED",
        reason_code: null,
        allowed: false,
        maximum_extensions: 0,
        days_per_extension: null,
      },
    };
    const bridgingOutcome = buildEngineOutcome(bridging, {
      facts: { stay_days: "120" },
    });
    if (bridgingOutcome.state !== "SUPPORTED_CANDIDATES") {
      throw new Error("expected SUPPORTED_CANDIDATES");
    }
    expect(bridgingOutcome.candidates[0].duration).toBeUndefined();

    // A1 signed-pack shape: FIXED_DAYS 30/30, allowed false, maximum_extensions 0, days_per_extension null -> duration undefined
    const a1 = makePricedResponse("A1", 0);
    a1.display.candidates[0].stay_policy = {
      stay: { kind: "FIXED_DAYS", minimum_days: 30, maximum_days: 30 },
      extension: {
        status: "VERIFIED",
        reason_code: null,
        allowed: false,
        maximum_extensions: 0,
        days_per_extension: null,
      },
    };
    const a1Outcome = buildEngineOutcome(a1, { facts: { stay_days: "60" } });
    if (a1Outcome.state !== "SUPPORTED_CANDIDATES") {
      throw new Error("expected SUPPORTED_CANDIDATES");
    }
    expect(a1Outcome.candidates[0].duration).toBeUndefined();

    for (const outcome of [
      e28aOutcome,
      e30aOutcome,
      bridgingOutcome,
      a1Outcome,
    ]) {
      const candidate = outcome.candidates[0];
      expect(candidate.duration).toBeUndefined();
      expect(JSON.stringify(candidate)).not.toMatch(
        /FIXED_DAYS|VARIABLE_BY_GRANT|EXTENSION_POLICY_NOT_VERIFIED|not extendable|tidak dapat diperpanjang/i,
      );
    }

    // Unmapped fixed day counts (30, 60, 180, 730) -> no length, never raw days
    for (const days of [30, 60, 180, 730]) {
      const unmapped = makePricedResponse("C1", 3_250_000);
      unmapped.display.candidates[0].stay_policy = {
        stay: { kind: "FIXED_DAYS", minimum_days: days, maximum_days: days },
        extension: {
          status: "VERIFIED",
          reason_code: null,
          allowed: false,
          maximum_extensions: 0,
          days_per_extension: null,
        },
      };
      const out = buildEngineOutcome(unmapped);
      if (out.state !== "SUPPORTED_CANDIDATES") {
        throw new Error("expected SUPPORTED_CANDIDATES");
      }
      expect(out.candidates[0].duration).toBeUndefined();
    }
  });

  it("maintains non-empty distinct EN/ID parity across all PR-7 stay-permit copy tables", () => {
    for (const entry of [
      ...Object.values(STAY_PERMIT_RENEWAL_COPY),
      ...Object.values(STAY_PERMIT_LONGER_STAY_COPY),
    ]) {
      expect(entry.en.trim().length).toBeGreaterThan(0);
      expect(entry.id.trim().length).toBeGreaterThan(0);
      expect(entry.en).not.toBe(entry.id);
      expect(entry.en).not.toMatch(/not extendable/i);
      expect(entry.id).not.toMatch(/tidak dapat diperpanjang/i);
    }
  });

  it("guilt: omits duration without failing the page for each of the four stay-kind invariant breaks on a priced E33F candidate", () => {
    const brokenStays = [
      {
        label: "FIXED_DAYS with null min and max",
        stay: {
          kind: "FIXED_DAYS" as const,
          minimum_days: null,
          maximum_days: null,
        },
      },
      {
        label: "NOT_APPLICABLE with non-null days",
        stay: {
          kind: "NOT_APPLICABLE" as const,
          minimum_days: 60,
          maximum_days: 60,
        },
      },
      {
        label: "FIXED_DAYS with minimum_days > maximum_days",
        stay: {
          kind: "FIXED_DAYS" as const,
          minimum_days: 730,
          maximum_days: 365,
        },
      },
      {
        label: "unknown stay.kind",
        stay: {
          kind: "OPEN_ENDED",
          minimum_days: 365,
          maximum_days: 365,
        },
      },
    ];

    for (const { label, stay } of brokenStays) {
      const response = makePricedResponse("E33F", 14_000_000);
      response.display.candidates[0].stay_policy = {
        stay,
        extension: {
          status: "VERIFIED",
          reason_code: null,
          allowed: true,
          maximum_extensions: 5,
          days_per_extension: 365,
        },
      };

      const parsed = parseVisaOracleEvaluateResponse(response);
      const outcome = buildEngineOutcome(parsed, {
        facts: { stay_days: "400" },
      });
      if (outcome.state !== "SUPPORTED_CANDIDATES") {
        throw new Error(`expected SUPPORTED_CANDIDATES (${label})`);
      }
      expect(outcome.candidates[0].code, label).toBe("E33F");
      expect(outcome.candidates[0].price, label).toMatchObject({
        status: "AVAILABLE",
        amount: 14_000_000,
      });
      expect(outcome.candidates[0].duration, label).toBeUndefined();
    }
  });

  it("guilt: a candidate with a broken stay-kind invariant does not remove the permit-length line of a valid sibling", () => {
    const siblingProductId = "66666666-6666-4666-8666-666666666666";
    const siblingQuoteId = "77777777-7777-4777-8777-777777777777";
    const response = makePricedResponse("E33F", 14_000_000);

    response.display.candidates[0].stay_policy = {
      stay: {
        kind: "FIXED_DAYS",
        minimum_days: 730,
        maximum_days: 365,
      },
      extension: {
        status: "VERIFIED",
        reason_code: null,
        allowed: true,
        maximum_extensions: 5,
        days_per_extension: 365,
      },
    };

    response.decision.candidates.push({
      ...response.decision.candidates[0],
      rank: 2,
      product_version_id: siblingProductId,
      product_code: "E33G",
    });
    response.display.candidates.push({
      ...response.display.candidates[0],
      rank: 2,
      product_version_id: siblingProductId,
      product_code: "E33G",
      name: {
        en: "Second Home Visa — Elderly 1-Year Onshore (E33G)",
        id: "Visa Rumah Kedua Lansia 1 Tahun Dalam Negeri (E33G)",
      },
      stay_policy: {
        stay: {
          kind: "FIXED_DAYS",
          minimum_days: 365,
          maximum_days: 365,
        },
        extension: {
          status: "VERIFIED",
          reason_code: null,
          allowed: true,
          maximum_extensions: 5,
          days_per_extension: 365,
        },
      },
    });
    response.decision.quotes.push({
      ...response.decision.quotes[0],
      quote_id: siblingQuoteId,
      product_version_id: siblingProductId,
      product_code: "E33G",
      pricing_key: { category: "visa", item_key: "E33G" },
    });

    const parsed = parseVisaOracleEvaluateResponse(response);
    const outcome = buildEngineOutcome(parsed, {
      facts: { stay_days: "400" },
    });
    if (outcome.state !== "SUPPORTED_CANDIDATES") {
      throw new Error("expected SUPPORTED_CANDIDATES");
    }
    expect(outcome.candidates).toHaveLength(2);
    expect(outcome.candidates[0].code).toBe("E33F");
    expect(outcome.candidates[0].price).toMatchObject({
      status: "AVAILABLE",
      amount: 14_000_000,
    });
    expect(outcome.candidates[0].duration).toBeUndefined();

    expect(outcome.candidates[1].code).toBe("E33G");
    expect(outcome.candidates[1].price).toMatchObject({
      status: "AVAILABLE",
      amount: 14_000_000,
    });
    expect(outcome.candidates[1].duration).toEqual({
      selectedDays: 365,
      options: [],
      extensionRequired: false,
      renewal: {
        en: "This permit is renewable 1 year at a time, up to 5 times.",
        id: "Izin tinggal ini dapat diperpanjang hingga 5 kali, masing-masing 1 tahun.",
      },
      longerStay: {
        en: "Your planned stay is longer than the first permit — your stay can continue by renewal.",
        id: "Rencana tinggal Anda lebih lama dari izin pertama — masa tinggal Anda dapat dilanjutkan dengan perpanjangan.",
      },
    });
  });

  it("innocence: preserves 365-day and 1825-day duration objects in EN and ID and omits length for VARIABLE_BY_GRANT, NOT_APPLICABLE null/null, FIXED_DAYS null/60, and FIXED_DAYS 730/730 through parseVisaOracleEvaluateResponse", () => {
    const e33f = makePricedResponse("E33F", 14_000_000);
    e33f.display.candidates[0].stay_policy = {
      stay: {
        kind: "FIXED_DAYS",
        minimum_days: 365,
        maximum_days: 365,
      },
      extension: {
        status: "VERIFIED",
        reason_code: null,
        allowed: true,
        maximum_extensions: 5,
        days_per_extension: 365,
      },
    };
    const e33fOutcome = buildEngineOutcome(
      parseVisaOracleEvaluateResponse(e33f),
      { facts: { stay_days: "400" } },
    );
    if (e33fOutcome.state !== "SUPPORTED_CANDIDATES") {
      throw new Error("expected SUPPORTED_CANDIDATES");
    }
    expect(e33fOutcome.candidates[0].duration).toEqual({
      selectedDays: 365,
      options: [],
      extensionRequired: false,
      renewal: {
        en: "This permit is renewable 1 year at a time, up to 5 times.",
        id: "Izin tinggal ini dapat diperpanjang hingga 5 kali, masing-masing 1 tahun.",
      },
      longerStay: {
        en: "Your planned stay is longer than the first permit — your stay can continue by renewal.",
        id: "Rencana tinggal Anda lebih lama dari izin pertama — masa tinggal Anda dapat dilanjutkan dengan perpanjangan.",
      },
    });
    expect(e33fOutcome.candidates[0].duration?.renewal?.en).toBe(
      STAY_PERMIT_RENEWAL_COPY["365:5"].en,
    );
    expect(e33fOutcome.candidates[0].duration?.renewal?.id).toBe(
      STAY_PERMIT_RENEWAL_COPY["365:5"].id,
    );
    expect(e33fOutcome.candidates[0].duration?.longerStay?.en).toBe(
      STAY_PERMIT_LONGER_STAY_COPY.verified.en,
    );
    expect(e33fOutcome.candidates[0].duration?.longerStay?.id).toBe(
      STAY_PERMIT_LONGER_STAY_COPY.verified.id,
    );

    const e33 = makePricedResponse("E33", 19_000_000);
    e33.display.candidates[0].stay_policy = {
      stay: {
        kind: "FIXED_DAYS",
        minimum_days: 1825,
        maximum_days: 1825,
      },
      extension: {
        status: "UNKNOWN",
        reason_code: "EXTENSION_POLICY_NOT_VERIFIED",
        allowed: false,
        maximum_extensions: 0,
        days_per_extension: null,
      },
    };
    const e33Outcome = buildEngineOutcome(
      parseVisaOracleEvaluateResponse(e33),
      { facts: { stay_days: "2000" } },
    );
    if (e33Outcome.state !== "SUPPORTED_CANDIDATES") {
      throw new Error("expected SUPPORTED_CANDIDATES");
    }
    expect(e33Outcome.candidates[0].duration).toEqual({
      selectedDays: 1825,
      options: [],
      extensionRequired: false,
      longerStay: {
        en: "Your planned stay is longer than the first permit — a Bali Zero advisor confirms how a longer stay continues.",
        id: "Rencana tinggal Anda lebih lama dari izin pertama — konsultan Bali Zero akan memastikan cara melanjutkan masa tinggal yang lebih lama.",
      },
    });
    expect(e33Outcome.candidates[0].duration?.renewal).toBeUndefined();
    expect(e33Outcome.candidates[0].duration?.longerStay?.en).toBe(
      STAY_PERMIT_LONGER_STAY_COPY.unknown.en,
    );
    expect(e33Outcome.candidates[0].duration?.longerStay?.id).toBe(
      STAY_PERMIT_LONGER_STAY_COPY.unknown.id,
    );

    const noLengthStays = [
      {
        label: "VARIABLE_BY_GRANT",
        stay: {
          kind: "VARIABLE_BY_GRANT" as const,
          minimum_days: null,
          maximum_days: 365,
        },
      },
      {
        label: "NOT_APPLICABLE with null days",
        stay: {
          kind: "NOT_APPLICABLE" as const,
          minimum_days: null,
          maximum_days: null,
        },
      },
      {
        label: "FIXED_DAYS null/60 (Bridging)",
        stay: {
          kind: "FIXED_DAYS" as const,
          minimum_days: null,
          maximum_days: 60,
        },
      },
      {
        label: "FIXED_DAYS 730/730",
        stay: {
          kind: "FIXED_DAYS" as const,
          minimum_days: 730,
          maximum_days: 730,
        },
      },
    ];

    for (const { label, stay } of noLengthStays) {
      const response = makePricedResponse("E28A", 20_000_000);
      response.display.candidates[0].stay_policy = {
        stay,
        extension: {
          status: "VERIFIED",
          reason_code: null,
          allowed: false,
          maximum_extensions: 0,
          days_per_extension: null,
        },
      };
      const outcome = buildEngineOutcome(
        parseVisaOracleEvaluateResponse(response),
        { facts: { stay_days: "1000" } },
      );
      if (outcome.state !== "SUPPORTED_CANDIDATES") {
        throw new Error(`expected SUPPORTED_CANDIDATES (${label})`);
      }
      expect(outcome.candidates[0].duration, label).toBeUndefined();
    }
  });
});

describe("PR-10 · E33F-only retirement result explains what the 5-year E33E also needs", () => {
  function e33fResponse(state: "SUPPORTED_CANDIDATES" | "NO_SUPPORTED_PATH") {
    const response = makeVisaOracleResponse(state);
    for (const candidate of response.decision.candidates) {
      candidate.product_code = "E33F";
    }
    for (const candidate of response.display.candidates) {
      candidate.product_code = "E33F";
    }
    return response;
  }

  function e33eAndE33fResponse() {
    const response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
    const firstDec = response.decision.candidates[0];
    const firstDisp = response.display.candidates[0];
    response.decision.candidates = [
      {
        ...firstDec,
        rank: 1,
        product_code: "E33E",
        product_version_id: "e33e-version-id",
      },
      {
        ...firstDec,
        rank: 2,
        product_code: "E33F",
        product_version_id: "e33f-version-id",
      },
    ];
    response.display.candidates = [
      {
        ...firstDisp,
        rank: 1,
        product_code: "E33E",
        product_version_id: "e33e-version-id",
      },
      {
        ...firstDisp,
        rank: 2,
        product_code: "E33F",
        product_version_id: "e33f-version-id",
      },
    ];
    return response;
  }

  function depositNoteCondition(facts?: OracleFacts) {
    const outcome = buildEngineOutcome(
      e33fResponse("SUPPORTED_CANDIDATES"),
      facts ? { facts } : {},
    );
    if (outcome.state !== "SUPPORTED_CANDIDATES") {
      throw new Error("unexpected state");
    }
    expect(
      outcome.conditions.find(
        (item) => item.code === E33F_E33E_DEPOSIT_NOTE_CODE,
      ),
    ).toBeUndefined();
    expect(outcome.conditions).toEqual([]);
    const e33f = outcome.candidates.find((c) => c.code === "E33F");
    return e33f?.notes?.find(
      (item) => item.code === E33F_E33E_DEPOSIT_NOTE_CODE,
    );
  }

  // `property` is a real retirement_basis option in tree.ts (`q.retirement_basis.opt.property`),
  // and `depositBasisDecisivelyNotChosen` returns true for `passive_income`,
  // `family_sponsor`, and `property`.
  it.each(["passive_income", "family_sponsor", "property"] as const)(
    "non-deposit basis %s produces the fixed note naming the chosen option and the bank-deposit option in EN and ID",
    (basis) => {
      const condition = depositNoteCondition({
        category: "retirement",
        retirement_basis: basis,
      });
      expect(condition).toBeDefined();
      expect(condition!.sourceIds).toEqual([]);
      const chosenEn = translate(
        "en",
        `q.retirement_basis.opt.${basis}` as I18nKey,
      );
      const chosenId = translate(
        "id",
        `q.retirement_basis.opt.${basis}` as I18nKey,
      );
      const bankDepositEn = translate(
        "en",
        "q.retirement_basis.opt.bank_deposit",
      );
      const bankDepositId = translate(
        "id",
        "q.retirement_basis.opt.bank_deposit",
      );
      expect(condition!.message).toEqual({
        en: `${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.en} You chose "${chosenEn}", so we did not ask about a deposit; if you hold one, change your answer to "${bankDepositEn}".`,
        id: `${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.id} Anda memilih "${chosenId}", sehingga kami tidak menanyakan soal deposito; jika Anda memilikinya, ubah jawaban Anda menjadi "${bankDepositId}".`,
      });
    },
  );

  it("quotes the localized bank_deposit option label from i18n in EN and ID", () => {
    const note = e33fE33eDepositNote({
      category: "retirement",
      retirement_basis: "passive_income",
    });
    expect(note).toBeDefined();
    expect(translate("en", "q.retirement_basis.opt.bank_deposit")).toBe(
      "A bank deposit in my own name",
    );
    expect(note!.en).toContain(
      translate("en", "q.retirement_basis.opt.bank_deposit"),
    );
    expect(note!.id).toContain(
      translate("id", "q.retirement_basis.opt.bank_deposit"),
    );
  });

  it("undecided -> family_sponsor walk carries the note naming the family_sponsor option and never 'undecided'", () => {
    for (const basis of ["undecided", "unsure"] as const) {
      const condition = depositNoteCondition({
        category: "retirement",
        retirement_basis: basis,
        retirement_undecided_basis: "family_sponsor",
      });
      expect(condition).toBeDefined();
      expect(condition!.message.en).toContain(
        translate("en", "q.retirement_basis.opt.family_sponsor"),
      );
      expect(condition!.message.id).toContain(
        translate("id", "q.retirement_basis.opt.family_sponsor"),
      );
      expect(condition!.message.en.toLowerCase()).not.toContain("undecided");
      expect(condition!.message.id.toLowerCase()).not.toContain("undecided");
      expect(condition!.message.en).not.toContain(
        translate("en", "q.retirement_basis.opt.undecided"),
      );
      expect(condition!.message.id).not.toContain(
        translate("id", "q.retirement_basis.opt.undecided"),
      );
    }
  });

  // `deposit_or_income` is a `retirement_undecided_basis` option in tree.ts,
  // reached via the tree walk `retirement_basis: "undecided", retirement_undecided_basis: "deposit_or_income"`.
  it.each<OracleFacts>([
    { retirement_basis: "bank_deposit" },
    {
      retirement_basis: "undecided",
      retirement_undecided_basis: "deposit_or_income",
    },
  ])(
    "deposit basis %j with a 49,999 deposit names USD 49,999 and USD 50,000 in EN and ID, and shows no note at 50,000+ when bank and name are yes",
    (basisFacts) => {
      const below = depositNoteCondition({
        category: "retirement",
        ...basisFacts,
        secondhome_deposit_usd: "49999",
        secondhome_state_bank: "yes",
        secondhome_own_name: "yes",
      });
      expect(below).toBeDefined();
      expect(below!.message).toEqual({
        en: `You declared a bank deposit of USD 49,999, which is below USD 50,000. ${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.en}`,
        id: `Anda menyatakan deposito bank sebesar USD 49.999, di bawah USD 50.000. ${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.id}`,
      });

      for (const clearingAmount of ["50000", "60000"]) {
        const cleared = depositNoteCondition({
          category: "retirement",
          ...basisFacts,
          secondhome_deposit_usd: clearingAmount,
          secondhome_state_bank: "yes",
          secondhome_own_name: "yes",
        });
        expect(cleared).toBeUndefined();
      }
    },
  );

  it("names state bank = no, own name = no, and their combination on deposit bases", () => {
    const bankNo = depositNoteCondition({
      category: "retirement",
      retirement_basis: "bank_deposit",
      secondhome_deposit_usd: "60000",
      secondhome_state_bank: "no",
      secondhome_own_name: "yes",
    });
    expect(bankNo?.message).toEqual({
      en: `You told us the deposit is not at an Indonesian state-owned bank. ${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.en}`,
      id: `Anda menyampaikan bahwa deposito tersebut tidak disimpan di bank milik negara Indonesia. ${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.id}`,
    });

    const ownNameNo = depositNoteCondition({
      category: "retirement",
      retirement_basis: "bank_deposit",
      secondhome_deposit_usd: "60000",
      secondhome_state_bank: "yes",
      secondhome_own_name: "no",
    });
    expect(ownNameNo?.message).toEqual({
      en: `You told us the deposit is not in your own name. ${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.en}`,
      id: `Anda menyampaikan bahwa deposito tersebut tidak atas nama Anda sendiri. ${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.id}`,
    });

    const allThree = depositNoteCondition({
      category: "retirement",
      retirement_basis: "undecided",
      retirement_undecided_basis: "deposit_or_income",
      secondhome_deposit_usd: "49999",
      secondhome_state_bank: "no",
      secondhome_own_name: "no",
    });
    expect(allThree?.message).toEqual({
      en: `You declared a bank deposit of USD 49,999, which is below USD 50,000. You told us the deposit is not at an Indonesian state-owned bank. You told us the deposit is not in your own name. ${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.en}`,
      id: `Anda menyatakan deposito bank sebesar USD 49.999, di bawah USD 50.000. Anda menyampaikan bahwa deposito tersebut tidak disimpan di bank milik negara Indonesia. Anda menyampaikan bahwa deposito tersebut tidak atas nama Anda sendiri. ${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.id}`,
    });
  });

  it("explains each 'unsure' deposit answer as a conservative count and never asserts failure", () => {
    const amountUnsure = depositNoteCondition({
      category: "retirement",
      retirement_basis: "bank_deposit",
      secondhome_deposit_usd: "unsure",
      secondhome_state_bank: "yes",
      secondhome_own_name: "yes",
    });
    expect(amountUnsure?.message).toEqual({
      en: `You were not sure of your bank deposit amount, so it counted as zero. ${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.en}`,
      id: `Anda belum yakin dengan jumlah deposito bank Anda, sehingga dihitung nol. ${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.id}`,
    });
    expect(amountUnsure?.message.en).not.toMatch(/You declared|You told us/);
    expect(amountUnsure?.message.id).not.toMatch(
      /Anda menyatakan|Anda menyampaikan/,
    );

    const bankUnsure = depositNoteCondition({
      category: "retirement",
      retirement_basis: "bank_deposit",
      secondhome_deposit_usd: "60000",
      secondhome_state_bank: "unsure",
      secondhome_own_name: "yes",
    });
    expect(bankUnsure?.message).toEqual({
      en: `You were not sure whether the deposit is at an Indonesian state-owned bank, so it counted as no. ${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.en}`,
      id: `Anda belum yakin apakah deposito tersebut disimpan di bank milik negara Indonesia, sehingga dianggap "tidak". ${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.id}`,
    });
    expect(bankUnsure?.message.en).not.toMatch(/You told us|is not at/);
    expect(bankUnsure?.message.id).not.toMatch(
      /Anda menyampaikan|tidak disimpan/,
    );

    const nameUnsure = depositNoteCondition({
      category: "retirement",
      retirement_basis: "bank_deposit",
      secondhome_deposit_usd: "60000",
      secondhome_state_bank: "yes",
      secondhome_own_name: "unsure",
    });
    expect(nameUnsure?.message).toEqual({
      en: `You were not sure whether the deposit is in your own name, so it counted as no. ${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.en}`,
      id: `Anda belum yakin apakah deposito tersebut atas nama Anda sendiri, sehingga dianggap "tidak". ${SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE.id}`,
    });
    expect(nameUnsure?.message.en).not.toMatch(/You told us|is not in/);
    expect(nameUnsure?.message.id).not.toMatch(
      /Anda menyampaikan|tidak atas nama/,
    );
  });

  it("innocence: emits no note when E33E is also a candidate (E33E + E33F)", () => {
    for (const facts of [
      {
        category: "retirement",
        retirement_basis: "bank_deposit",
        secondhome_deposit_usd: "60000",
        secondhome_state_bank: "yes",
        secondhome_own_name: "yes",
      },
      {
        category: "retirement",
        retirement_basis: "passive_income",
      },
      {
        category: "retirement",
        retirement_basis: "bank_deposit",
        secondhome_deposit_usd: "49999",
        secondhome_state_bank: "no",
        secondhome_own_name: "no",
      },
    ] as OracleFacts[]) {
      const outcome = buildEngineOutcome(e33eAndE33fResponse(), { facts });
      if (outcome.state !== "SUPPORTED_CANDIDATES") {
        throw new Error("unexpected state");
      }
      expect(outcome.conditions).toEqual([]);
      for (const candidate of outcome.candidates) {
        expect(candidate.notes).toBeUndefined();
      }
    }
  });

  it("innocence: emits no note when E33F is absent, on sibling candidates, on dead ends, or on non-retirement categories, and keeps conditions restricted to PENJAMIN", () => {
    const retirementFacts: OracleFacts = {
      category: "retirement",
      retirement_basis: "passive_income",
    };
    // E33F absent (default fixture candidate is C1)
    const c1Only = buildEngineOutcome(
      makeVisaOracleResponse("SUPPORTED_CANDIDATES"),
      { facts: retirementFacts },
    );
    if (c1Only.state !== "SUPPORTED_CANDIDATES") {
      throw new Error("unexpected state");
    }
    expect(c1Only.conditions).toEqual([]);
    for (const candidate of c1Only.candidates) {
      expect(candidate.notes).toBeUndefined();
    }

    // Sibling candidate alongside E33F: only E33F gets `notes`, never the sibling;
    // `conditions` stays exactly what main produced (e.g. E33F_PENJAMIN_NOTE only).
    const e33fAndC1Response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
    const firstDec = e33fAndC1Response.decision.candidates[0];
    const firstDisp = e33fAndC1Response.display.candidates[0];
    e33fAndC1Response.decision.candidates = [
      {
        ...firstDec,
        rank: 1,
        product_code: "E33F",
        product_version_id: "e33f-version-id",
      },
      {
        ...firstDec,
        rank: 2,
        product_code: "C1",
        product_version_id: "c1-version-id",
      },
    ];
    e33fAndC1Response.display.candidates = [
      {
        ...firstDisp,
        rank: 1,
        product_code: "E33F",
        product_version_id: "e33f-version-id",
      },
      {
        ...firstDisp,
        rank: 2,
        product_code: "C1",
        product_version_id: "c1-version-id",
      },
    ];
    const e33fAndC1 = buildEngineOutcome(e33fAndC1Response, {
      facts: {
        ...retirementFacts,
        retirement_penjamin_confirmed: "no",
      },
    });
    if (e33fAndC1.state !== "SUPPORTED_CANDIDATES") {
      throw new Error("unexpected state");
    }
    expect(e33fAndC1.conditions.map((c) => c.code)).toEqual([
      "E33F_PENJAMIN_NOTE",
    ]);
    expect(e33fAndC1.candidates[0].notes?.map((n) => n.code)).toEqual([
      E33F_E33E_DEPOSIT_NOTE_CODE,
    ]);
    expect(e33fAndC1.candidates[1].notes).toBeUndefined();

    // Dead end (NO_SUPPORTED_PATH) and other non-supported states
    for (const state of [
      "NO_SUPPORTED_PATH",
      "HUMAN_REVIEW_REQUIRED",
      "NEEDS_INPUT",
    ] as const) {
      const nonSupported = buildEngineOutcome(makeVisaOracleResponse(state), {
        facts: retirementFacts,
      });
      expect(nonSupported.conditions).toEqual([]);
      expect(nonSupported.candidates).toEqual([]);
    }

    // Non-retirement categories even when candidate is E33F
    for (const category of ["second_home", "invest", "tourism", "family"]) {
      const nonRetirement = buildEngineOutcome(
        e33fResponse("SUPPORTED_CANDIDATES"),
        {
          facts: {
            category,
            retirement_basis: "passive_income",
            secondhome_basis: "property",
            secondhome_deposit_usd: "49999",
            secondhome_state_bank: "no",
            secondhome_own_name: "no",
          },
        },
      );
      if (nonRetirement.state !== "SUPPORTED_CANDIDATES") {
        throw new Error("unexpected state");
      }
      expect(nonRetirement.conditions).toEqual([]);
      for (const candidate of nonRetirement.candidates) {
        expect(candidate.notes).toBeUndefined();
      }
    }
  });

  it("EN/ID parity: every produced note is non-empty in both locales, differs between EN and ID, matches USD figure counts, and carries no raw code, promise words, or price/PNBP split", () => {
    const factCases: OracleFacts[] = [
      { category: "retirement", retirement_basis: "passive_income" },
      { category: "retirement", retirement_basis: "family_sponsor" },
      { category: "retirement", retirement_basis: "property" },
      {
        category: "retirement",
        retirement_basis: "undecided",
        retirement_undecided_basis: "family_sponsor",
      },
      {
        category: "retirement",
        retirement_basis: "bank_deposit",
        secondhome_deposit_usd: "49999",
        secondhome_state_bank: "yes",
        secondhome_own_name: "yes",
      },
      {
        category: "retirement",
        retirement_basis: "undecided",
        retirement_undecided_basis: "deposit_or_income",
        secondhome_deposit_usd: "60000",
        secondhome_state_bank: "no",
        secondhome_own_name: "yes",
      },
      {
        category: "retirement",
        retirement_basis: "bank_deposit",
        secondhome_deposit_usd: "60000",
        secondhome_state_bank: "yes",
        secondhome_own_name: "no",
      },
      {
        category: "retirement",
        retirement_basis: "bank_deposit",
        secondhome_deposit_usd: "unsure",
        secondhome_state_bank: "unsure",
        secondhome_own_name: "unsure",
      },
    ];

    for (const facts of factCases) {
      const note = e33fE33eDepositNote(facts);
      expect(note).toBeDefined();
      expect(note!.en.length).toBeGreaterThan(0);
      expect(note!.id.length).toBeGreaterThan(0);
      expect(note!.en).not.toBe(note!.id);
      const enUsdCount = (note!.en.match(/USD\s+[\d,]+/g) ?? []).length;
      const idUsdCount = (note!.id.match(/USD\s+[\d.]+/g) ?? []).length;
      expect(enUsdCount).toBeGreaterThanOrEqual(1);
      expect(idUsdCount).toBe(enUsdCount);
      for (const copy of [note!.en, note!.id]) {
        expect(copy).not.toContain(E33F_E33E_DEPOSIT_NOTE_CODE);
        expect(copy).not.toMatch(/qualif|will get|eligible|PNBP|IDR|\bRp\b/i);
      }
    }
  });
});
