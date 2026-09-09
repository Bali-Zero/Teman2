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
