import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import type { ComponentProps } from "react";
import { OutcomeSheet } from "./OutcomeSheet";
import type { Language } from "../_lib/flow";
import type {
  OutcomeCandidate,
  OutcomeState,
  OutcomeViewModel,
} from "../_lib/outcome-view-model";
import {
  T2_CONSULTANT_TERMS,
  T2_CONSULTANT_TERMS_TITLE,
  buildEngineOutcome,
} from "../_lib/engine-adapter";
import { makeHumanReviewWithEligibleCandidates } from "../_lib/visa-oracle-test-fixture";

const FACTS = { in_indonesia: "yes", category: "tourism" };

const DISCLAIMER_EN = [
  "This is a private decision-support tool, not a government service.",
  "The result reflects only the facts you entered and the dated sources shown above.",
  "It is not an approval, a guarantee, or a filing.",
  "Complex or flagged cases always go to a human — Ditjen Imigrasi decides, not this tool.",
];

const DISCLAIMER_ID = [
  "Ini alat bantu keputusan privat, bukan layanan pemerintah.",
  "Hasil ini hanya mencerminkan data yang Anda masukkan dan sumber bertanggal yang ditampilkan di atas.",
  "Ini bukan persetujuan, jaminan, atau pengajuan resmi.",
  "Kasus kompleks atau ditandai selalu diteruskan ke manusia — Ditjen Imigrasi yang memutuskan, bukan alat ini.",
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
  };
}

function outcomeFor(state: OutcomeState): OutcomeViewModel {
  switch (state) {
    case "SUPPORTED_CANDIDATES":
      return {
        ...common(),
        state,
        pathsRemaining: 1,
        candidates: [CANDIDATE],
      };
    case "NEEDS_INPUT":
      return {
        ...common(),
        state,
        candidates: [],
        missingInputs: [
          { ...reason, code: "missing.stay", questionId: "stay_days" },
        ],
      };
    case "HUMAN_REVIEW_REQUIRED":
      return {
        ...common(),
        state,
        candidates: [],
        reviewReasons: [reason],
      };
    case "NO_SUPPORTED_PATH":
      return {
        ...common(),
        state,
        candidates: [],
        noPathReasons: [reason],
        alternatives: [{ category: "remote" }],
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
      };
  }
}

/** Same "SUPPORTED_CANDIDATES" shape `outcomeFor` builds, but with a
 * caller-supplied candidate — needed to exercise a specific `tier` without
 * fighting `outcomeFor`'s `OutcomeViewModel` return type (a union that
 * doesn't expose `candidates` until narrowed on `state`). */
function outcomeWithCandidate(candidate: OutcomeCandidate): OutcomeViewModel {
  return {
    ...common(),
    state: "SUPPORTED_CANDIDATES",
    pathsRemaining: 1,
    candidates: [candidate],
  };
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

  /**
   * Owner ruling #2 (2026-08-25, OWNER-RULINGS-2026-08-25.md §2): the T2
   * terms text must appear on the "product page" surface — this candidate
   * card is the only per-product client-facing surface this route has
   * (there is no separate checkout page yet). Watched RED: with
   * `CandidateCard` reverted to before this change, `candidate.tier` was
   * never read at all and this block did not exist for any tier.
   */
  it("shows the T2 product-page consultant terms for a T2-tier candidate", () => {
    render(
      <OutcomeSheet
        language="en"
        outcome={outcomeWithCandidate({ ...CANDIDATE, tier: "T2" })}
        facts={FACTS}
      />,
    );
    expect(screen.getByText(T2_CONSULTANT_TERMS_TITLE.en)).toBeInTheDocument();
    expect(screen.getByText(T2_CONSULTANT_TERMS.en)).toBeInTheDocument();
  });

  it("omits the T2 consultant terms for a T1-tier candidate", () => {
    render(
      <OutcomeSheet
        language="en"
        outcome={outcomeWithCandidate({ ...CANDIDATE, tier: "T1" })}
        facts={FACTS}
      />,
    );
    expect(screen.queryByText(T2_CONSULTANT_TERMS_TITLE.en)).toBeNull();
    expect(screen.queryByText(T2_CONSULTANT_TERMS.en)).toBeNull();
  });

  it("omits the T2 consultant terms for a candidate with no mapped tier (the fixture default)", () => {
    renderSheet("SUPPORTED_CANDIDATES"); // CANDIDATE fixture carries no `tier`
    expect(screen.queryByText(T2_CONSULTANT_TERMS_TITLE.en)).toBeNull();
    expect(screen.queryByText(T2_CONSULTANT_TERMS.en)).toBeNull();
  });

  it("NEEDS_INPUT exposes the mapped edit action", () => {
    const onEditMissingInput = vi.fn();
    renderSheet("NEEDS_INPUT", "en", { onEditMissingInput });
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(onEditMissingInput).toHaveBeenCalledWith("stay_days");
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

  it("does not fabricate document requirements or calendar dates when absent", () => {
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
      screen.getByText("Document requirements unknown — not verified"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/26 July 2026/)).not.toBeInTheDocument();
  });

  /**
   * Owner ruling #5 (2026-08-25, OWNER-RULINGS-2026-08-25.md §5) — the
   * danger-pinning test the task explicitly calls for: even though a
   * HUMAN_REVIEW_REQUIRED outcome can now carry real `OutcomeCandidate`
   * objects (each with its own `price` field, per the type), NOTHING on this
   * screen may ever render a price, a currency string, or a purchase
   * affordance — `OutcomeSheet`'s `SUPPORTED_CANDIDATES`-only
   * `CandidateCard` list (the only place `Price` renders) never mounts for
   * this state; the candidates only feed the next-steps line's text.
   * Precedence stays HUMAN_REVIEW_REQUIRED throughout — the review reason
   * itself is untouched by carrying a candidate.
   */
  it("renders no price/currency and no purchase affordance on a HUMAN_REVIEW_REQUIRED screen that carries candidates", () => {
    const outcome = buildEngineOutcome(makeHumanReviewWithEligibleCandidates());
    expect(outcome.state).toBe("HUMAN_REVIEW_REQUIRED");
    if (outcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    // Guard the guard: an empty candidate list would make every assertion
    // below vacuously true.
    expect(outcome.candidates.length).toBeGreaterThan(0);

    const { container } = render(
      <OutcomeSheet language="en" outcome={outcome} facts={FACTS} />,
    );

    // No price/currency string anywhere on this screen.
    expect(screen.queryByText(/IDR/)).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/Rp\s?\d/);
    expect(container.textContent).not.toMatch(/\$\s?\d/);
    expect(container.querySelector(".oracle-price__value")).toBeNull();
    // No purchase affordance — no "buy"-shaped control anywhere.
    expect(screen.queryByRole("button", { name: /buy/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /buy/i })).toBeNull();

    // The review verdict itself stays visible — carrying a candidate never
    // hides or demotes it (constraint (d)).
    expect(
      screen.getByText(outcome.reviewReasons[0].message.en),
    ).toBeInTheDocument();

    // The visitor is told plainly they qualify, and BOTH candidates are
    // named — never a singular (constraints (b)+(c)).
    expect(container.textContent).toContain("D12");
    expect(container.textContent).toContain("E28A");
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
