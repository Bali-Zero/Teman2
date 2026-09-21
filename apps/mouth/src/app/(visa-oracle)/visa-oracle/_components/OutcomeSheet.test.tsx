import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import type { ComponentProps } from "react";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import {
  OutcomeSheet,
  SYSTEM_REVIEW_REASON_CODES,
  demonstratedReviewCauses,
} from "./OutcomeSheet";
import {
  REVIEW_REASON_COPY,
  SECOND_HOME_STUDIO_REVIEW_REASON_CODE,
  SECOND_HOME_STUDIO_URL,
} from "../_lib/engine-adapter";
import { mapDisclosedReviewFlags } from "../_lib/fact-mapper";
import { QUESTIONS, REVIEW_GATE_ITEMS } from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";
import { assumptionDisplay } from "./ConfirmationCard";
import type { Language } from "../_lib/flow";
import type {
  HumanReviewOutcome,
  OutcomeCandidate,
  OutcomeReason,
  OutcomeState,
  OutcomeViewModel,
} from "../_lib/outcome-view-model";

const FACTS = { in_indonesia: "yes", category: "tourism" };

const DISCLAIMER_EN = [
  "This is a private decision-support tool, not a government service.",
  "The result reflects only the facts you entered and the dated sources shown above.",
  "It is not an approval, a guarantee, or a filing.",
  "A disclosed criminal record goes to a person before any path is confirmed; an answer the signed rules cannot assess is sent to a person or routed to a consultation. Every other disclosure stays on your result as a named condition our team checks with you before submission. Ditjen Imigrasi decides, not this tool.",
];

const DISCLAIMER_ID = [
  "Ini alat bantu keputusan privat, bukan layanan pemerintah.",
  "Hasil ini hanya mencerminkan data yang Anda masukkan dan sumber bertanggal yang ditampilkan di atas.",
  "Ini bukan persetujuan, jaminan, atau pengajuan resmi.",
  "Catatan kriminal yang Anda ungkapkan diteruskan ke seseorang sebelum jalur mana pun dikonfirmasi; jawaban yang tidak dapat dinilai oleh aturan yang telah disahkan diteruskan ke seseorang atau diarahkan ke konsultasi. Pengungkapan lainnya tetap melekat pada hasil Anda sebagai kondisi bernama yang diperiksa tim kami bersama Anda sebelum pengajuan. Ditjen Imigrasi yang memutuskan, bukan alat ini.",
];

const text = (en: string, id = en) => ({ en, id });
const reason = {
  code: "fixture.reason",
  message: text("Verified fixture reason", "Alasan fixture terverifikasi"),
  sourceIds: ["source-1"],
};
const source = {
  id: "source-1",
  title: "Primary source fixture",
  publisher: "Authority fixture",
  url: "https://example.test/primary-source",
  authority: "PRIMARY_LAW",
  primary: true,
  effectiveAtIso: "2026-07-01T00:00:00Z",
  observedAtIso: "2026-07-23T00:00:00Z",
  freshness: "CURRENT" as const,
};
const nextSteps = [
  { id: "one", title: text("Review this result", "Tinjau hasil ini") },
  { id: "two", title: text("Prepare carefully", "Siapkan dengan teliti") },
  {
    id: "three",
    title: text("Confirm before filing", "Konfirmasi sebelum mengajukan"),
  },
] as const;
const assessment = {
  publicId: "decisionfixture01",
  effectiveAtIso: "2026-07-23T00:00:00Z",
  observedAtIso: "2026-07-23T00:00:00Z",
  evaluatedAtIso: "2026-07-23T00:00:00Z",
};

const CANDIDATE: OutcomeCandidate = {
  id: "candidate-1",
  code: "TEST-1",
  rank: 1,
  name: text("Test path", "Jalur uji"),
  tagline: text("A UI fixture, not a recommendation"),
  legal: { status: "SUPPORTED", reasons: [reason] },
  operational: { status: "AVAILABLE", reasons: [] },
  service: { status: "CONTACT_REQUIRED", reasons: [] },
  decisionReasons: [reason],
  timeline: {
    status: "AVAILABLE",
    basisDateIso: "2026-07-23",
    earliestDateIso: "2026-07-26",
    latestDateIso: "2026-07-30",
  },
  price: {
    status: "AVAILABLE",
    currency: "IDR",
    amount: 1_000_000,
    allInclusive: true,
    quotedAtIso: "2026-07-23T00:00:00Z",
  },
  documents: [
    {
      id: "document-1",
      label: text("Fixture document", "Dokumen fixture"),
      status: "REQUIRED",
      sourceIds: [source.id],
    },
  ],
};

function common() {
  return {
    provenance: "ENGINE" as const,
    assessment,
    pathsRemaining: 0,
    assumptions: [],
    sources: [source],
    nextSteps,
    conditions: [] as readonly OutcomeReason[],
  };
}

function outcomeFor(
  state: OutcomeState,
  conditions: readonly OutcomeReason[] = [],
): OutcomeViewModel {
  switch (state) {
    case "SUPPORTED_CANDIDATES":
      return {
        ...common(),
        state,
        pathsRemaining: 1,
        candidates: [CANDIDATE],
        conditions,
      };
    case "NEEDS_INPUT":
      return {
        ...common(),
        state,
        candidates: [],
        missingInputs: [
          { ...reason, code: "missing.stay", questionId: "stay_days" },
        ],
        conditions,
      };
    case "HUMAN_REVIEW_REQUIRED":
      return {
        ...common(),
        state,
        candidates: [],
        reviewReasons: [reason],
        conditions,
      };
    case "NO_SUPPORTED_PATH":
      return {
        ...common(),
        state,
        candidates: [],
        noPathReasons: [reason],
        alternatives: [{ category: "remote" }],
        conditions,
      };
    case "TEMPORARILY_UNAVAILABLE":
      return {
        ...common(),
        state,
        candidates: [],
        outage: {
          code: "fixture.outage",
          message: text("Decision service unavailable"),
          retryable: true,
        },
        conditions,
      };
  }
}

const ALL_STATES: OutcomeState[] = [
  "SUPPORTED_CANDIDATES",
  "NEEDS_INPUT",
  "HUMAN_REVIEW_REQUIRED",
  "NO_SUPPORTED_PATH",
  "TEMPORARILY_UNAVAILABLE",
];

function renderSheet(
  state: OutcomeState,
  language: Language = "en",
  props: Partial<ComponentProps<typeof OutcomeSheet>> = {},
) {
  return render(
    <OutcomeSheet
      language={language}
      outcome={outcomeFor(state)}
      facts={FACTS}
      {...props}
    />,
  );
}

describe("OutcomeSheet — honest five-state rendering", () => {
  it.each(ALL_STATES)("renders the disclaimer on %s in EN", (state) => {
    const { container } = renderSheet(state);
    const disclaimer = container.querySelector(".oracle-disclaimer");
    for (const line of DISCLAIMER_EN)
      expect(disclaimer).toHaveTextContent(line);
  });

  it.each(ALL_STATES)("renders the disclaimer on %s in ID", (state) => {
    const { container } = renderSheet(state, "id");
    const disclaimer = container.querySelector(".oracle-disclaimer");
    for (const line of DISCLAIMER_ID)
      expect(disclaimer).toHaveTextContent(line);
  });

  it.each(ALL_STATES)("renders exactly three next steps on %s", (state) => {
    const { container } = renderSheet(state);
    expect(screen.getByText("Your next 3 steps")).toBeInTheDocument();
    expect(container.querySelectorAll(".oracle-next-steps > li")).toHaveLength(
      3,
    );
  });

  it("renders one supported candidate with three distinct status axes", () => {
    renderSheet("SUPPORTED_CANDIDATES");
    expect(
      screen.getByRole("heading", { name: "Test path" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Legal eligibility")).toBeInTheDocument();
    expect(screen.getByText("Operational availability")).toBeInTheDocument();
    expect(screen.getByText("Bali Zero service")).toBeInTheDocument();
    expect(document.querySelector(".oracle-price__value")).toHaveTextContent(
      /IDR.*1,000,000/,
    );
    expect(screen.getAllByText("Primary source fixture")).toHaveLength(2);
  });

  it("NEEDS_INPUT exposes the mapped edit action", () => {
    const onEditMissingInput = vi.fn();
    renderSheet("NEEDS_INPUT", "en", { onEditMissingInput });
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(onEditMissingInput).toHaveBeenCalledWith("stay_days");
  });

  it.each<Language>(["en", "id"])(
    "shows repeated unroutable details only once in %s without an Edit action",
    (language) => {
      const message = text("Additional detail needed", "Perlu detail tambahan");
      const outcome: OutcomeViewModel = {
        ...common(),
        state: "NEEDS_INPUT",
        candidates: [],
        missingInputs: [
          { code: "missing.a", message, sourceIds: [] },
          { code: "missing.b", message, sourceIds: [] },
        ],
      };
      const { container } = renderSheet("NEEDS_INPUT", language, {
        outcome,
        onEditMissingInput: vi.fn(),
      });
      expect(screen.getAllByText(message[language])).toHaveLength(1);
      expect(
        container.querySelectorAll(".oracle-action-list > li"),
      ).toHaveLength(1);
      expect(
        screen.queryByRole("button", { name: /edit|ubah/i }),
      ).not.toBeInTheDocument();
      expect(outcome.missingInputs.map((input) => input.code)).toEqual([
        "missing.a",
        "missing.b",
      ]);
    },
  );

  it("keeps editable details distinct from identical fallback copy and each other", () => {
    const message = text("Detail needed");
    const onEditMissingInput = vi.fn();
    const outcome: OutcomeViewModel = {
      ...common(),
      state: "NEEDS_INPUT",
      candidates: [],
      missingInputs: [
        { code: "missing.a", message, sourceIds: [] },
        {
          code: "missing.stay",
          message,
          sourceIds: [],
          questionId: "stay_days",
        },
        { code: "missing.b", message, sourceIds: [] },
        {
          code: "missing.entry",
          message,
          sourceIds: [],
          questionId: "entry_pattern",
        },
        { code: "missing.c", message: text("Different detail"), sourceIds: [] },
      ],
    };
    const { container } = renderSheet("NEEDS_INPUT", "en", {
      outcome,
      onEditMissingInput,
    });
    expect(screen.getAllByText("Detail needed")).toHaveLength(3);
    expect(screen.getByText("Different detail")).toBeInTheDocument();
    expect(container.querySelectorAll(".oracle-action-list > li")).toHaveLength(
      4,
    );
    const buttons = screen.getAllByRole("button", { name: "Edit" });
    expect(buttons).toHaveLength(2);
    buttons.forEach((button) => fireEvent.click(button));
    expect(onEditMissingInput.mock.calls).toEqual([
      ["stay_days"],
      ["entry_pattern"],
    ]);
  });

  it("has no always-on WhatsApp/QR handoff and renders only an explicit slot", () => {
    const first = renderSheet("NEEDS_INPUT");
    expect(first.container.querySelector("[href*='wa.me']")).toBeNull();
    expect(first.container.querySelector("[data-qr-value]")).toBeNull();
    first.unmount();

    renderSheet("NEEDS_INPUT", "en", {
      handoffSlot: <button type="button">Consent-gated handoff</button>,
    });
    expect(
      screen.getByRole("button", { name: "Consent-gated handoff" }),
    ).toBeInTheDocument();
  });

  it("distinguishes a network failure from an engine decision", () => {
    const engineOutcome = outcomeFor("TEMPORARILY_UNAVAILABLE");
    if (engineOutcome.state !== "TEMPORARILY_UNAVAILABLE") {
      throw new Error("test fixture state mismatch");
    }
    const networkOutcome: OutcomeViewModel = {
      ...engineOutcome,
      provenance: "NETWORK_FAILURE",
      assessment: null,
      candidates: [],
    };
    render(
      <OutcomeSheet language="en" outcome={networkOutcome} facts={FACTS} />,
    );
    expect(screen.getAllByText("Decision service unavailable")).toHaveLength(2);
    expect(screen.getByText(/engine did not answer/i)).toBeInTheDocument();
  });

  it("renders SHADOW as verification-only with no decision receipt or candidates", () => {
    const engineOutcome = outcomeFor("TEMPORARILY_UNAVAILABLE");
    if (engineOutcome.state !== "TEMPORARILY_UNAVAILABLE") {
      throw new Error("test fixture state mismatch");
    }
    const shadowOutcome: OutcomeViewModel = {
      ...engineOutcome,
      provenance: "SHADOW",
      assessment: null,
      candidates: [],
      sources: [],
    };
    render(
      <OutcomeSheet language="en" outcome={shadowOutcome} facts={FACTS} />,
    );

    expect(screen.getByText("Verification mode")).toBeInTheDocument();
    expect(
      screen.getByText(/no engine candidate is exposed/i),
    ).toBeInTheDocument();
    expect(screen.queryByText("Test path")).not.toBeInTheDocument();
    expect(screen.queryByText(/decision reference/i)).not.toBeInTheDocument();
  });

  it("renders PREVIEW as zero-candidate test scaffolding", () => {
    const engineOutcome = outcomeFor("TEMPORARILY_UNAVAILABLE");
    if (engineOutcome.state !== "TEMPORARILY_UNAVAILABLE") {
      throw new Error("test fixture state mismatch");
    }
    const previewOutcome: OutcomeViewModel = {
      ...engineOutcome,
      provenance: "PREVIEW",
      assessment: null,
      candidates: [],
      sources: [],
    };
    render(
      <OutcomeSheet language="en" outcome={previewOutcome} facts={FACTS} />,
    );

    expect(screen.getByText("Preview data")).toBeInTheDocument();
    expect(
      screen.getByText(/only for testing the interface/i),
    ).toBeInTheDocument();
    expect(screen.queryByText("Test path")).not.toBeInTheDocument();
    expect(screen.queryByText("Fixture document")).not.toBeInTheDocument();
    expect(screen.queryByText(/IDR/)).not.toBeInTheDocument();
  });

  it("hides empty document and availability cards", () => {
    const engineOutcome = outcomeFor("SUPPORTED_CANDIDATES");
    if (engineOutcome.state !== "SUPPORTED_CANDIDATES") {
      throw new Error("test fixture state mismatch");
    }
    const unavailableCandidate: OutcomeCandidate = {
      ...CANDIDATE,
      timeline: {
        status: "UNAVAILABLE",
        message: text("No verified operational calendar"),
      },
      operational: { status: "UNKNOWN", reasons: [] },
      service: { status: "UNKNOWN", reasons: [] },
      documents: [],
    };
    const unavailableOutcome: OutcomeViewModel = {
      ...engineOutcome,
      candidates: [unavailableCandidate],
    };
    render(
      <OutcomeSheet language="en" outcome={unavailableOutcome} facts={FACTS} />,
    );

    expect(
      screen.getByText("Timeline unavailable — no verified calendar estimate"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("No verified operational calendar"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Documents you’ll want ready" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Operational availability"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Bali Zero service")).not.toBeInTheDocument();
    expect(screen.queryByText(/26 July 2026/)).not.toBeInTheDocument();
  });

  it("renders the required documents card when the product has documents", () => {
    renderSheet("SUPPORTED_CANDIDATES");

    expect(
      screen.getByRole("heading", { name: "Documents you’ll want ready" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Fixture document")).toBeInTheDocument();
  });

  it("keeps print/copy/share controls and print anatomy on abstention", () => {
    const { container } = renderSheet("NEEDS_INPUT");
    expect(container.querySelector(".oracle-print-only")).not.toBeNull();
    expect(
      screen.getByRole("button", { name: /print \/ save as pdf/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /share summary/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /copy summary/i }),
    ).toBeInTheDocument();
    expect(container.querySelector(".oracle-outcome-actions")).toHaveClass(
      "oracle-no-print",
    );
  });
});

// PR-O4 / Δ2 (spec §3): a held visitor must read a DEMONSTRATED cause, and a
// hold that is ours must not be worded — or grouped — as something they did.
describe("OutcomeSheet — PR-O4 review causes", () => {
  const reviewReasonFor = (code: string): OutcomeReason => ({
    code,
    message: text(`Copy for ${code}`, `Salinan untuk ${code}`),
    sourceIds: [],
  });

  const reviewOutcome = (
    codes: readonly [string, ...string[]],
  ): HumanReviewOutcome => ({
    ...common(),
    state: "HUMAN_REVIEW_REQUIRED",
    candidates: [],
    reviewReasons: [
      reviewReasonFor(codes[0]),
      ...codes.slice(1).map(reviewReasonFor),
    ],
  });

  function renderReview(
    codes: readonly [string, ...string[]],
    facts: Record<string, string>,
    props: Partial<ComponentProps<typeof OutcomeSheet>> = {},
    language: Language = "en",
  ) {
    return render(
      <OutcomeSheet
        language={language}
        outcome={reviewOutcome(codes)}
        facts={facts}
        {...props}
      />,
    );
  }

  it.each([
    [
      "en",
      [
        "Why this is held",
        "What the reviewer checks",
        "What to prepare",
        "How this is handled",
      ],
      [
        "This result is held because you disclosed a criminal record or an ongoing case. It is one of the two disclosures the signed rules still send to a person; the other nine now stay on your result as named conditions.",
        "A specialist reads what you disclosed against the immigration record requirements for the route you asked about, and decides whether it can be submitted as it stands.",
        "Have the dates and the issuing authority of any court or police record ready, together with any document showing the case is closed. Send nothing here — our team tells you where each document goes.",
        "A specialist reviews this before we confirm a path, and our team comes back to you with the timing for your case.",
      ],
    ],
    [
      "id",
      [
        "Mengapa hasil ini ditahan",
        "Apa yang diperiksa peninjau",
        "Apa yang perlu disiapkan",
        "Bagaimana hal ini ditangani",
      ],
      [
        "Hasil ini ditahan karena Anda mengungkapkan catatan kriminal atau perkara yang masih berjalan. Ini salah satu dari dua pengungkapan yang masih diteruskan ke seseorang oleh aturan yang telah disahkan; sembilan pengungkapan lainnya kini tetap melekat pada hasil Anda sebagai kondisi bernama.",
        "Seorang spesialis membaca apa yang Anda ungkapkan terhadap persyaratan catatan keimigrasian untuk jalur yang Anda tanyakan, lalu menilai apakah berkas tersebut dapat diajukan apa adanya.",
        "Siapkan tanggal dan instansi penerbit dari setiap catatan pengadilan atau kepolisian, beserta dokumen apa pun yang menunjukkan perkara telah ditutup. Jangan kirimkan apa pun di sini — tim kami akan memberi tahu ke mana setiap dokumen harus dikirim.",
        "Seorang spesialis meninjau hal ini sebelum kami mengonfirmasi jalur, dan tim kami akan mengabari Anda mengenai perkiraan waktu untuk kasus Anda.",
      ],
    ],
  ] as const)(
    "renders all four criminal review elements in %s",
    (language, labels, texts) => {
      renderReview(["DISCLOSED_CRIMINAL_RECORD_REVIEW"], {}, {}, language);
      labels.forEach((label) =>
        expect(screen.getByText(label)).toBeInTheDocument(),
      );
      texts.forEach((value) =>
        expect(screen.getByText(value)).toBeInTheDocument(),
      );
      expect(
        document.querySelectorAll(".oracle-review-elements dt"),
      ).toHaveLength(4);
      expect(
        document.querySelectorAll(".oracle-review-elements dd"),
      ).toHaveLength(4);
    },
  );

  it("renders no review elements for the activity-boundary hold", () => {
    const { container } = renderReview(
      ["DISCLOSED_ACTIVITY_BOUNDARY_REVIEW"],
      {},
    );
    expect(
      screen.getByText("Copy for DISCLOSED_ACTIVITY_BOUNDARY_REVIEW"),
    ).toBeInTheDocument();
    expect(
      container.querySelectorAll(".oracle-review-elements dt"),
    ).toHaveLength(0);
    expect(
      container.querySelectorAll(".oracle-review-elements dd"),
    ).toHaveLength(0);
  });

  it("names the question the visitor answered “Not sure” and edits back to it", () => {
    const onEditMissingInput = vi.fn();
    const { container } = renderReview(
      ["DISCLOSED_UNCERTAINTY_REVIEW"],
      { category: "business", trip_scope: "unsure" },
      { onEditMissingInput },
    );

    expect(
      screen.getByText(
        "You answered “Not sure” to: Is this your only purpose for the trip?",
      ),
    ).toBeInTheDocument();
    expect(container.querySelectorAll("[data-review-cause]")).toHaveLength(1);

    fireEvent.click(
      screen.getByRole("button", {
        name: "Edit your answer to: Is this your only purpose for the trip?",
      }),
    );
    expect(onEditMissingInput).toHaveBeenCalledWith("trip_scope");
  });

  it("names the same cause in Indonesian", () => {
    renderReview(
      ["DISCLOSED_UNCERTAINTY_REVIEW"],
      { trip_scope: "unsure" },
      {},
      "id",
    );
    expect(
      screen.getByText(
        "Anda menjawab “Tidak yakin” pada: Apakah ini satu-satunya tujuan perjalanan Anda?",
      ),
    ).toBeInTheDocument();
  });

  it("quotes the answer itself when the hold is an undecidable activity", () => {
    renderReview(["DISCLOSED_ACTIVITY_BOUNDARY_REVIEW"], {
      category: "business",
      business_activity: "training",
    });
    expect(
      screen.getByText(
        "You answered “Giving or receiving training” to: What will you mainly do on the business trip?",
      ),
    ).toBeInTheDocument();
  });

  it("attributes a disclosure hold to the review gate the visitor ticked", () => {
    const { container } = renderReview(["DISCLOSED_HEALTH_CONCERN_REVIEW"], {
      review_gate: "health_flag",
    });
    expect(
      container.querySelector('[data-review-cause="review_gate"]'),
    ).not.toBeNull();
  });

  it("attributes nothing when no answer of this walk demonstrates the code", () => {
    const { container } = renderReview(
      ["DISCLOSED_MULTI_PURPOSE_TRIP_REVIEW"],
      {
        category: "business",
        trip_scope: "single",
      },
    );
    expect(container.querySelectorAll("[data-review-cause]")).toHaveLength(0);
    expect(
      screen.getByText("Copy for DISCLOSED_MULTI_PURPOSE_TRIP_REVIEW"),
    ).toBeInTheDocument();
  });

  it("groups a source hold as ours and never attributes it to an answer", () => {
    const { container } = renderReview(["DECISIVE_SOURCE_STALE"], {
      category: "business",
      trip_scope: "unsure",
    });
    expect(
      screen.getByRole("heading", {
        name: "Checks on our side, not on your answers",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", {
        name: "What a person will check about your case",
      }),
    ).toBeNull();
    expect(container.querySelectorAll("[data-review-cause]")).toHaveLength(0);
  });

  it("renders both groups under their own headings when both are held", () => {
    renderReview(
      ["DISCLOSED_UNCERTAINTY_REVIEW", "SAFETY_CRITICAL_SOURCE_STALE"],
      { trip_scope: "unsure" },
    );
    expect(
      screen.getByRole("heading", {
        name: "What a person will check about your case",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Checks on our side, not on your answers",
      }),
    ).toBeInTheDocument();
  });

  // Guard, not decoration: a new source/system code added to the copy map
  // would otherwise render silently under "about your case" — the exact
  // mis-attribution PR-O4 exists to remove.
  it("classifies every source/system code the copy map knows", () => {
    const unclassified = Object.keys(REVIEW_REASON_COPY).filter(
      (code) =>
        /^(DECISIVE_|SAFETY_CRITICAL_|MINOR_GUARDIAN_PRIVACY)/.test(code) &&
        !SYSTEM_REVIEW_REASON_CODES.has(code),
    );
    expect(unclassified).toEqual([]);
  });

  // The attribution mirrors `mapDisclosedReviewFlags`; if either side drifts,
  // this goes red rather than showing a cause the engine never held on.
  it.each<[string, string, Record<string, string>]>([
    ["DISCLOSED_UNCERTAINTY_REVIEW", "NOT_CERTAIN", { trip_scope: "unsure" }],
    [
      "DISCLOSED_ACTIVITY_BOUNDARY_REVIEW",
      "ACTIVITY_BOUNDARY",
      { business_activity: "training" },
    ],
    [
      "DISCLOSED_MULTI_PURPOSE_TRIP_REVIEW",
      "MULTI_PURPOSE_TRIP",
      { trip_scope: "multiple" },
    ],
    [
      "DISCLOSED_CRIMINAL_RECORD_REVIEW",
      "CRIMINAL_RECORD",
      { review_gate: "criminal_record" },
    ],
  ])(
    "only attributes %s when the mapper really raises %s",
    (code, flag, facts) => {
      expect(demonstratedReviewCauses(code, facts).length).toBeGreaterThan(0);
      expect(mapDisclosedReviewFlags(facts)).toContain(flag);
      expect(demonstratedReviewCauses(code, {})).toEqual([]);
    },
  );

  it("names the question in the assumptions receipt instead of a raw key", () => {
    render(
      <OutcomeSheet
        language="en"
        outcome={{
          ...reviewOutcome(["DISCLOSED_UNCERTAINTY_REVIEW"]),
          assumptions: [
            {
              id: "assumption-1",
              questionId: "trip_scope",
              editable: true,
            },
          ],
        }}
        facts={{ trip_scope: "unsure" }}
      />,
    );
    expect(
      screen.getByText(
        "You marked “Not sure” for “Is this your only purpose for the trip?”; no value was inferred.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("assumption.trip_scope")).toBeNull();
  });

  // Slice A6-2 delta A6-4b (RATIFIED 2026-09-21T15:20:33Z, gate H-1): the
  // seven declared-conservative questions reach the wire as "0"/"no", but
  // before this delta the receipt still rendered the generic "no value was
  // inferred" sentence for them — now FALSE, since a value WAS inferred.
  // `assumptionDisplay` must resolve their own `assumption.<id>` key
  // instead of falling through to `assumption.generic`, in both languages.
  const SEVEN_DECLARED_CONSERVATIVE_QUESTIONS = [
    "secondhome_deposit_usd",
    "secondhome_property_value_usd",
    "secondhome_passive_income_usd",
    "secondhome_state_bank",
    "secondhome_own_name",
    "study_admission_confirmed",
    "study_sponsor_confirmed",
  ] as const;

  it.each(SEVEN_DECLARED_CONSERVATIVE_QUESTIONS)(
    "assumptionDisplay names the value assumed for %s instead of falling through to the generic sentence (A6-4b)",
    (questionId) => {
      for (const language of ["en", "id"] as const) {
        const question = QUESTIONS[questionId];
        const generic = translate(language, "assumption.generic", {
          question: question
            ? translate(language, question.i18nKey as I18nKey)
            : questionId,
        });
        const text = assumptionDisplay(language, questionId);
        expect(text).not.toBe(generic);
        expect(text).toBe(
          translate(language, `assumption.${questionId}` as I18nKey),
        );
      }
    },
  );

  it("the OutcomeSheet receipt renders the specific assumption string, not the generic fallback, for a declared-conservative question", () => {
    render(
      <OutcomeSheet
        language="en"
        outcome={{
          ...reviewOutcome(["DISCLOSED_UNCERTAINTY_REVIEW"]),
          assumptions: [
            {
              id: "assumption-1",
              questionId: "secondhome_deposit_usd",
              editable: true,
            },
          ],
        }}
        facts={{ secondhome_deposit_usd: "0" }}
      />,
    );
    expect(
      screen.getByText(
        translate("en", "assumption.secondhome_deposit_usd" as I18nKey),
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(
        "You marked “Not sure” for “What bank deposit can you document?”; no value was inferred.",
      ),
    ).toBeNull();
  });

  // flow.ts's EDIT resets the whole interview when its target is absent from
  // history, and `facts` is pruned to history — so a cause is only ever
  // offered for a question this walk actually asked.
  it("never attributes a question this walk did not answer", () => {
    expect(
      demonstratedReviewCauses("DISCLOSED_MULTI_PURPOSE_TRIP_REVIEW", {
        category: "business",
      }),
    ).toEqual([]);
    expect(
      demonstratedReviewCauses("DISCLOSED_UNCERTAINTY_REVIEW", {
        not_a_question: "unsure",
      }),
    ).toEqual([]);
  });
});

// Slice A3-M, M7-bis (routed from a conductor ruling on the builder's own
// finding): the doc comment above `REVIEW_GATE_CAUSE_ITEM`
// (OutcomeSheet.tsx:183-190) claims the file "re-derives every row through
// mapDisclosedReviewFlags" — the `it.each` above only exercises 4 curated
// examples, not every row. `REVIEW_GATE_CAUSE_ITEM` itself is module-private
// by design (mirrored, never imported, per that same comment), so this
// suite proves coverage INDIRECTLY through the exported
// `demonstratedReviewCauses`, never by touching production code. Shared
// with M7-ter below (same derivation), so the two helpers live at module
// scope rather than duplicated per describe block.
const M7_HERE = path.dirname(fileURLToPath(import.meta.url));
const M7_EVALUATE_PATH = path.resolve(
  M7_HERE,
  "../../../../../../..",
  "apps/backend-rag/backend/services/visa_engine/evaluate_path.py",
);

/**
 * Derives the DisclosedReviewFlag -> REVIEW code map straight from the
 * backend's own `_DISCLOSED_REVIEW_REASON_CODES`
 * (evaluate_path.py:1132-1150) — never hand-typed, so a rename on either
 * side turns this red instead of silently drifting. Handles both the
 * single-line and the one parenthesised multi-line entry
 * (CONFLICTING_IMMIGRATION_STATUS) the same way A5's own extractor does.
 */
function reviewCodeByFlag(): Record<string, string> {
  const text = fs.readFileSync(M7_EVALUATE_PATH, "utf-8");
  const marker =
    "_DISCLOSED_REVIEW_REASON_CODES: MappingProxyType[DisclosedReviewFlag, str] = MappingProxyType(";
  const start = text.indexOf(marker);
  if (start === -1) {
    throw new Error(
      `_DISCLOSED_REVIEW_REASON_CODES not found in ${M7_EVALUATE_PATH} — evaluate_path.py renamed or moved the map`,
    );
  }
  const end = text.indexOf("\n)\n", start);
  const block = text.slice(start, end);
  const pattern = /DisclosedReviewFlag\.(\w+):\s*\(?\s*"([A-Z_]+)"/g;
  const map: Record<string, string> = {};
  let match: RegExpExecArray | null;
  // eslint-disable-next-line no-cond-assign
  while ((match = pattern.exec(block)) !== null) {
    map[match[1]] = match[2];
  }
  return map;
}

// Independently-sourced list of the real checklist items — never
// hand-typed alongside REVIEW_GATE_CAUSE_ITEM's own rows.
const REAL_REVIEW_GATE_ITEMS = REVIEW_GATE_ITEMS.filter(
  (item) => item !== "none",
);

describe("OutcomeSheet — REVIEW_GATE_CAUSE_ITEM row coverage (M7-bis)", () => {
  it("derives: every review_gate item's flag demonstrably attributes back through REVIEW_GATE_CAUSE_ITEM", () => {
    const flagToReviewCode = reviewCodeByFlag();
    const badFlagCount: string[] = [];
    const unmappedFlag: string[] = [];
    const missing: string[] = [];
    for (const item of REAL_REVIEW_GATE_ITEMS) {
      const flags = mapDisclosedReviewFlags({ review_gate: item });
      if (flags.length !== 1) {
        badFlagCount.push(`${item} raised ${flags.length} flags, expected 1`);
        continue;
      }
      const [flag] = flags;
      const code = flagToReviewCode[flag];
      if (!code) {
        unmappedFlag.push(
          `${flag} (from ${item}) has no REVIEW code in evaluate_path.py`,
        );
        continue;
      }
      const causes = demonstratedReviewCauses(code, { review_gate: item });
      if (causes.length === 0) missing.push(`${item} (${code})`);
    }
    expect(badFlagCount).toEqual([]);
    expect(unmappedFlag).toEqual([]);
    expect(missing).toEqual([]);
  });

  // A literal pin of the row-key SET, observed indirectly through
  // `demonstratedReviewCauses` since `REVIEW_GATE_CAUSE_ITEM` stays
  // module-private by design. Twelve entries verified against the source
  // on this base (the nine pre-A3-M rows plus M1's three) — not fourteen:
  // `CONFLICTING_IMMIGRATION_STATUS` and `MULTI_PURPOSE_TRIP` are two of
  // the fourteen DisclosedReviewFlag members that are NOT review_gate
  // checklist items (PLAN §1.5 / M7's own note), so they are correctly
  // absent here.
  const EXPECTED_REVIEW_GATE_CODES = [
    "DISCLOSED_CRIMINAL_RECORD_REVIEW",
    "DISCLOSED_HEALTH_CONCERN_REVIEW",
    "DISCLOSED_PRIOR_VISA_REFUSAL_REVIEW",
    "DISCLOSED_PEP_OR_SANCTIONS_REVIEW",
    "DISCLOSED_SOURCE_OF_FUNDS_REVIEW",
    "DISCLOSED_DIPLOMATIC_PASSPORT_REVIEW",
    "DISCLOSED_AMBIGUOUS_SPONSOR_REVIEW",
    "DISCLOSED_UNCERTAINTY_REVIEW",
    "DISCLOSED_ACTIVITY_BOUNDARY_REVIEW",
    "DISCLOSED_PAST_OVERSTAY_REVIEW",
    "DISCLOSED_BLACKLIST_ENTRY_REVIEW",
    "DISCLOSED_IMMIGRATION_INVESTIGATION_REVIEW",
  ].sort();

  it("pins the row-key set: exactly twelve codes attribute a review_gate cause", () => {
    const flagToReviewCode = reviewCodeByFlag();
    const attributing = REAL_REVIEW_GATE_ITEMS.map((item) => {
      const [flag] = mapDisclosedReviewFlags({ review_gate: item });
      return flagToReviewCode[flag];
    }).sort();
    expect(attributing).toEqual(EXPECTED_REVIEW_GATE_CODES);
    const noItemFound: string[] = [];
    const noCauseFound: string[] = [];
    for (const code of EXPECTED_REVIEW_GATE_CODES) {
      const item = REAL_REVIEW_GATE_ITEMS.find((candidate) => {
        const [flag] = mapDisclosedReviewFlags({ review_gate: candidate });
        return flagToReviewCode[flag] === code;
      });
      if (item === undefined) {
        noItemFound.push(code);
        continue;
      }
      if (demonstratedReviewCauses(code, { review_gate: item }).length === 0) {
        noCauseFound.push(code);
      }
    }
    expect(noItemFound).toEqual([]);
    expect(noCauseFound).toEqual([]);
  });
});

// Slice A3-M, M7-ter (conductor ruling R-REWORK-A3M, OBS-A3M-2): M7-bis's
// row-key pin cannot go RED in the ADD direction — `demonstratedReviewCauses`
// has no way to observe a row that no disclosed flag ever triggers, so an
// extra `BOGUS_GATE_PROBE_REVIEW: "criminal_record"` row stays invisible to
// it. This suite closes that gap with a TEST-ONLY change: it enumerates
// `REVIEW_GATE_CAUSE_ITEM`'s declared KEYS straight from OutcomeSheet.tsx's
// own source text — the same technique `reviewCodeByFlag` above already
// applies to evaluate_path.py — so both an added and a dropped row are
// visible without exporting the module-private map.
describe("OutcomeSheet — REVIEW_GATE_CAUSE_ITEM keys enumerated from source text (M7-ter)", () => {
  const OWN_PATH = path.resolve(M7_HERE, "OutcomeSheet.tsx");

  function sourceDeclaredKeys(): string[] {
    const text = fs.readFileSync(OWN_PATH, "utf-8");
    const marker = "const REVIEW_GATE_CAUSE_ITEM";
    const start = text.indexOf(marker);
    if (start === -1) {
      throw new Error(
        `${marker} not found in ${OWN_PATH} — REVIEW_GATE_CAUSE_ITEM renamed or moved`,
      );
    }
    const end = text.indexOf("\n};", start);
    if (end === -1) {
      throw new Error(
        `no closing "\\n};" found for REVIEW_GATE_CAUSE_ITEM in ${OWN_PATH}`,
      );
    }
    const block = text.slice(start, end);
    const pattern = /^\s*([A-Z_]+):\s*"/gm;
    const keys: string[] = [];
    let match: RegExpExecArray | null;
    // eslint-disable-next-line no-cond-assign
    while ((match = pattern.exec(block)) !== null) {
      keys.push(match[1]);
    }
    return keys;
  }

  it("declares REVIEW_GATE_CAUSE_ITEM with no duplicate key", () => {
    const keys = sourceDeclaredKeys();
    const duplicates = keys.filter((key, i) => keys.indexOf(key) !== i);
    expect(duplicates).toEqual([]);
  });

  it("declares exactly the key set REVIEW_GATE_ITEMS derives — an extra or a missing row is named", () => {
    const flagToReviewCode = reviewCodeByFlag();
    const derived = REAL_REVIEW_GATE_ITEMS.map((item) => {
      const [flag] = mapDisclosedReviewFlags({ review_gate: item });
      return flagToReviewCode[flag];
    }).sort();
    const declared = [...sourceDeclaredKeys()].sort();
    expect(declared).toEqual(derived);
  });

  it("declares exactly as many rows as REVIEW_GATE_ITEMS has real checklist items (derived, not typed)", () => {
    expect(sourceDeclaredKeys().length).toEqual(REAL_REVIEW_GATE_ITEMS.length);
  });
});

describe("OutcomeSheet — D23 Second Home Studio", () => {
  const reviewReasonFor = (code: string): OutcomeReason => ({
    code,
    message: text(`Copy for ${code}`, `Salinan untuk ${code}`),
    sourceIds: [],
  });

  const reviewOutcome = (
    codes: readonly [string, ...string[]],
  ): HumanReviewOutcome => ({
    ...common(),
    state: "HUMAN_REVIEW_REQUIRED",
    candidates: [],
    reviewReasons: [
      reviewReasonFor(codes[0]),
      ...codes.slice(1).map(reviewReasonFor),
    ],
  });

  function renderReview(
    codes: readonly [string, ...string[]],
    language: Language = "en",
  ) {
    return render(
      <OutcomeSheet
        language={language}
        outcome={reviewOutcome(codes)}
        facts={FACTS}
      />,
    );
  }

  // GUILT: the only review reason is the Studio code — this hold must never
  // read as "a person will check", and the self-serve link must be present.
  it("links to the Second Home Studio and drops the consultant wording when it is the only hold", () => {
    renderReview([SECOND_HOME_STUDIO_REVIEW_REASON_CODE]);

    const link = screen.getByRole("link", {
      name: "Open the Second Home Studio",
    });
    expect(link).toHaveAttribute("href", SECOND_HOME_STUDIO_URL);

    expect(
      screen.queryByText(
        "Your case needs a person’s judgment — nothing here was guessed on your behalf.",
      ),
    ).toBeNull();
    expect(
      screen.queryByRole("heading", {
        name: "What a person will check about your case",
      }),
    ).toBeNull();
    expect(
      screen.queryByRole("heading", {
        name: "Checks on our side, not on your answers",
      }),
    ).toBeNull();
    expect(
      screen.getByText(`Copy for ${SECOND_HOME_STUDIO_REVIEW_REASON_CODE}`),
    ).toBeInTheDocument();
  });

  it("shows the Studio link's ID label and drops the ID consultant wording", () => {
    renderReview([SECOND_HOME_STUDIO_REVIEW_REASON_CODE], "id");

    expect(
      screen.getByRole("link", { name: "Buka Second Home Studio" }),
    ).toHaveAttribute("href", SECOND_HOME_STUDIO_URL);
    expect(
      screen.queryByText(
        "Kasus Anda butuh penilaian manusia — tidak ada yang ditebak atas nama Anda.",
      ),
    ).toBeNull();
  });

  // INNOCENCE: any other review code renders exactly as before — generic
  // body, normal case-review heading, and no Studio link anywhere.
  it("leaves an unrelated review reason unchanged, with no Studio link", () => {
    renderReview(["DISCLOSED_UNCERTAINTY_REVIEW"]);

    expect(
      screen.getByText(
        "Your case needs a person’s judgment — nothing here was guessed on your behalf.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "What a person will check about your case",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Open the Second Home Studio" }),
    ).toBeNull();
  });

  // A case that ALSO carries a different hold keeps the generic body and the
  // normal groups — the override is scoped to "Studio is the ONLY reason".
  it("keeps the generic body, and still links the Studio, when the Studio code shares the hold with another reason", () => {
    renderReview([
      SECOND_HOME_STUDIO_REVIEW_REASON_CODE,
      "DISCLOSED_UNCERTAINTY_REVIEW",
    ]);

    expect(
      screen.getByText(
        "Your case needs a person’s judgment — nothing here was guessed on your behalf.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open the Second Home Studio" }),
    ).toHaveAttribute("href", SECOND_HOME_STUDIO_URL);
  });

  // GUILT: the disclaimer's "always go to a human" line must not appear
  // anywhere on the page when the Studio code is the only hold.
  it("swaps the disclaimer's human line for Studio-specific copy when it is the only hold", () => {
    const { container } = renderReview([SECOND_HOME_STUDIO_REVIEW_REASON_CODE]);
    const disclaimer = container.querySelector(".oracle-disclaimer");
    expect(disclaimer).toHaveTextContent(
      "This hold is about a declared guarantee figure below the Second Home (E33) thresholds — the Second Home Studio shows the routes and the numbers for your case.",
    );
    expect(container.textContent).not.toMatch(/\ba human\b/i);
    expect(container.textContent).not.toMatch(/consultant/i);
  });

  // GUILT (ID): "penahanan" reads as detention to an applicant — a decision
  // hold on an immigration page must never be worded that way.
  it("swaps the ID disclaimer line too, without detention or human wording", () => {
    const { container } = renderReview(
      [SECOND_HOME_STUDIO_REVIEW_REASON_CODE],
      "id",
    );
    const disclaimer = container.querySelector(".oracle-disclaimer");
    expect(disclaimer).toHaveTextContent(
      "Hasil ini berkaitan dengan angka jaminan yang Anda nyatakan, yang masih di bawah ambang batas Rumah Kedua (E33)",
    );
    expect(disclaimer?.textContent ?? "").not.toMatch(/penahanan|ditahan/i);
    expect(container.textContent).not.toMatch(/manusia/i);
  });

  // INNOCENCE: a mixed hold (Studio + another reason) keeps the generic
  // disclaimer line.
  it("keeps the generic disclaimer line when the Studio code shares the hold with another reason", () => {
    const { container } = renderReview([
      SECOND_HOME_STUDIO_REVIEW_REASON_CODE,
      "DISCLOSED_UNCERTAINTY_REVIEW",
    ]);
    const disclaimer = container.querySelector(".oracle-disclaimer");
    expect(disclaimer).toHaveTextContent(
      "A disclosed criminal record goes to a person before any path is confirmed; an answer the signed rules cannot assess is sent to a person or routed to a consultation. Every other disclosure stays on your result as a named condition our team checks with you before submission. Ditjen Imigrasi decides, not this tool.",
    );
  });

  it("removes the old human-review footer in EN and ID", () => {
    const { container: en } = renderReview(["DISCLOSED_UNCERTAINTY_REVIEW"]);
    expect(en.textContent).not.toContain(
      "Complex or flagged cases always go to a human",
    );
    const { container: id } = renderReview(
      ["DISCLOSED_UNCERTAINTY_REVIEW"],
      "id",
    );
    expect(id.textContent).not.toContain("selalu diteruskan ke manusia");
  });

  // GUILT: the share text (built from the same headline VerdictReveal
  // shows, per `engine-adapter.ts`'s `isSecondHomeStudioOnly`) must not
  // carry "needs a human, not an algorithm" for a Studio-only hold.
  it("builds Studio-specific share text with no human/algorithm wording", async () => {
    renderReview([SECOND_HOME_STUDIO_REVIEW_REASON_CODE]);
    const writeText = navigator.clipboard.writeText as ReturnType<typeof vi.fn>;
    writeText.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Copy summary" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    const summary = writeText.mock.calls[0]?.[0] as string;
    expect(summary).toContain("Below the Second Home guarantee threshold");
    expect(summary).not.toMatch(/\ba human\b/i);
    expect(summary).not.toMatch(/algorithm/i);
  });

  // INNOCENCE: any other review code keeps the pre-existing share headline.
  it("keeps the generic human-review headline in share text for an unrelated review code", async () => {
    renderReview(["DISCLOSED_UNCERTAINTY_REVIEW"]);
    const writeText = navigator.clipboard.writeText as ReturnType<typeof vi.fn>;
    writeText.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Copy summary" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    const summary = writeText.mock.calls[0]?.[0] as string;
    expect(summary).toContain("This needs a human, not an algorithm");
  });
});

// Slice A2 (PLAN VISA-ORACLE-DW-20260919 §1.6, N4-N5): `notices[]` renders
// with the verdict, never behind a disclosure glyph.
describe("OutcomeSheet — conditions on the verdict", () => {
  const CONDITION_ONE: OutcomeReason = {
    code: "DISCLOSED_HEALTH_CONCERN_CONDITION",
    message: text(
      "Health concern condition fixture",
      "Fixture kondisi kesehatan",
    ),
    sourceIds: [],
  };
  const CONDITION_TWO: OutcomeReason = {
    code: "DISCLOSED_PEP_OR_SANCTIONS_CONDITION",
    message: text("PEP condition fixture", "Fixture kondisi PEP"),
    sourceIds: [],
  };

  it.each<Language>(["en", "id"])(
    "renders a single condition with the verdict in %s",
    (language) => {
      const outcome = outcomeFor("SUPPORTED_CANDIDATES", [CONDITION_ONE]);
      renderSheet("SUPPORTED_CANDIDATES", language, { outcome });
      expect(
        screen.getByText(CONDITION_ONE.message[language]),
      ).toBeInTheDocument();
    },
  );

  it("shows the new footer on a supported verdict with a notice", () => {
    const outcome = outcomeFor("SUPPORTED_CANDIDATES", [CONDITION_ONE]);
    const { container } = renderSheet("SUPPORTED_CANDIDATES", "en", {
      outcome,
    });
    expect(container.textContent).toContain(
      "A disclosed criminal record goes to a person before any path is confirmed; an answer the signed rules cannot assess is sent to a person or routed to a consultation. Every other disclosure stays on your result as a named condition our team checks with you before submission. Ditjen Imigrasi decides, not this tool.",
    );
  });

  it("renders many conditions, in order, on the same outcome", () => {
    const outcome = outcomeFor("SUPPORTED_CANDIDATES", [
      CONDITION_ONE,
      CONDITION_TWO,
    ]);
    const { container } = renderSheet("SUPPORTED_CANDIDATES", "en", {
      outcome,
    });
    const items = container.querySelectorAll(
      ".oracle-outcome__conditions .oracle-reason-list > li",
    );
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent(CONDITION_ONE.message.en);
    expect(items[1]).toHaveTextContent(CONDITION_TWO.message.en);
  });

  it("renders a condition next to a HUMAN_REVIEW_REQUIRED verdict too — notices has no state constraint", () => {
    const outcome = outcomeFor("HUMAN_REVIEW_REQUIRED", [CONDITION_ONE]);
    renderSheet("HUMAN_REVIEW_REQUIRED", "en", { outcome });
    expect(screen.getByText(CONDITION_ONE.message.en)).toBeInTheDocument();
  });

  it("renders no conditions section when there are none", () => {
    const { container } = renderSheet("SUPPORTED_CANDIDATES");
    expect(
      container.querySelector(".oracle-outcome__conditions"),
    ).not.toBeInTheDocument();
  });

  // V6 (GATE-A2B-REPORT-6857.md OBS-A2b-6): S6's `aria-labelledby` was
  // structurally correct but pinned by no test — this asserts the section's
  // `aria-labelledby` actually resolves to the rendered title's own `id`,
  // not just that both attributes are present somewhere in the markup.
  it("names the conditions section via aria-labelledby, resolving to the rendered title's id (S6, V6)", () => {
    const outcome = outcomeFor("SUPPORTED_CANDIDATES", [CONDITION_ONE]);
    const { container } = renderSheet("SUPPORTED_CANDIDATES", "en", {
      outcome,
    });
    const section = container.querySelector(".oracle-outcome__conditions");
    expect(section).toBeInTheDocument();
    const labelledBy = section!.getAttribute("aria-labelledby");
    expect(labelledBy).toBeTruthy();
    const title = container.querySelector(`#${labelledBy}`);
    expect(title).toBeInTheDocument();
    expect(title).toHaveTextContent(
      translate("en", "outcome.conditions.title"),
    );
  });
});
