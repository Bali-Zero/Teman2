import { describe, it, expect } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";
import type { ComponentProps } from "react";
import { OutcomeSheet } from "./OutcomeSheet";
import type { Language } from "../_lib/flow";
import { translate } from "../_lib/i18n";
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
    expect(screen.getAllByRole("link", { name: "Primary source fixture" })).toHaveLength(2);
  });

  it("NEEDS_INPUT exposes the mapped edit action", () => {
    const onEditMissingInput = vi.fn();
    renderSheet("NEEDS_INPUT", "en", { onEditMissingInput });
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(onEditMissingInput).toHaveBeenCalledWith("stay_days");
    expect(screen.queryByText(translate("en", "outcome.needs_input_advisor_body"))).toBeNull();
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
      expect(screen.getByText(translate(language, "outcome.needs_input_advisor_body"))).toBeVisible();
      expect(screen.getByText(translate(language, "outcome.assumptions_receipt_empty"))).toBeVisible();
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
      screen.getByText("Operational checklist unavailable"),
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

describe("OutcomeSheet — D12 Business catalog association", () => {
  const businessFacts = {
    in_indonesia: "no",
    category: "business",
    business_activity: "meetings",
    stay_days: "100",
    entry_pattern: "multiple",
  };

  function businessOutcome(): Extract<OutcomeViewModel, { state: "SUPPORTED_CANDIDATES" }> {
    return {
      ...common(),
      state: "SUPPORTED_CANDIDATES",
      pathsRemaining: 2,
      candidates: [
        { ...CANDIDATE, id: "d1", code: "D1", name: text("D1 fixture") },
        { ...CANDIDATE, id: "d2", code: "D2", rank: 2, name: text("D2 fixture") },
      ],
    };
  }

  it.each([
    {
      language: "en" as const,
      section: "Another Business option to check",
      title: "Pre-investment visit — multiple entry",
      scope: "For pre-investment visits or exploring a new business, including site surveys and feasibility studies.",
      status: "Eligibility not yet established",
      assessment: "This assessment has not established your eligibility for D12. Check that your planned activities and documents meet its requirements.",
    },
    {
      language: "id" as const,
      section: "Pilihan Bisnis lain untuk diperiksa",
      title: "Kunjungan prainvestasi — beberapa kali masuk",
      scope: "Untuk kunjungan prainvestasi atau menjajaki usaha baru, termasuk survei lapangan dan studi kelayakan.",
      status: "Kelayakan belum dipastikan",
      assessment: "Penilaian ini belum memastikan kelayakan Anda untuk D12. Periksa apakah rencana kegiatan dan dokumen Anda memenuhi persyaratannya.",
    },
  ])("shows D12 beside D1/D2 in $language without claiming support", (copy) => {
    renderSheet("SUPPORTED_CANDIDATES", copy.language, {
      facts: businessFacts,
      outcome: businessOutcome(),
    });
    const section = screen.getByRole("region", { name: copy.section });
    const card = within(section).getByRole("article");
    expect(within(card).getByText("D12")).toBeInTheDocument();
    expect(within(card).getByRole("heading", { name: copy.title })).toBeInTheDocument();
    expect(card).toHaveTextContent(copy.scope);
    expect(card).toHaveTextContent(copy.status);
    expect(card).toHaveTextContent(copy.assessment);
    expect(within(card).getByRole("link")).toHaveAttribute(
      "href",
      "https://www.imigrasi.go.id/wna/daftar-visa-indonesia/D12",
    );
    expect(card.querySelector(".oracle-axis-grid")).toBeNull();
    expect(card.querySelector(".oracle-candidate-card__rank")).toBeNull();
    expect(card.querySelector(".oracle-price")).toBeNull();
    expect(document.querySelectorAll(".oracle-candidate-list > article")).toHaveLength(2);
  });

  it.each(["tourism", "investment", undefined])(
    "does not add the Business catalog option for category %s",
    (category) => {
      renderSheet("SUPPORTED_CANDIDATES", "en", {
        facts: category ? { ...businessFacts, category } : { in_indonesia: "no" },
        outcome: businessOutcome(),
      });
      expect(screen.queryByText("D12")).not.toBeInTheDocument();
    },
  );

  it.each(ALL_STATES.filter((state) => state !== "SUPPORTED_CANDIDATES"))(
    "does not promote D12 on Business state %s",
    (state) => {
      renderSheet(state, "en", { facts: businessFacts });
      expect(screen.queryByText("D12")).not.toBeInTheDocument();
    },
  );

  it("does not duplicate a D12 candidate returned by the engine", () => {
    const outcome = businessOutcome();
    if (outcome.state !== "SUPPORTED_CANDIDATES") throw new Error("fixture state");
    outcome.candidates = [
      ...outcome.candidates,
      { ...CANDIDATE, id: "d12", code: "D12", rank: 3 },
    ];
    renderSheet("SUPPORTED_CANDIDATES", "en", { facts: businessFacts, outcome });
    expect(screen.getAllByText("D12")).toHaveLength(1);
    expect(document.querySelector("[data-catalog-visa='D12']")).toBeNull();
  });

  it("does not add the catalog option to a non-engine preview result", () => {
    renderSheet("SUPPORTED_CANDIDATES", "en", {
      facts: businessFacts,
      outcome: { ...businessOutcome(), provenance: "PREVIEW", assessment: null },
    });
    expect(screen.queryByText("D12")).not.toBeInTheDocument();
  });

  it("keeps answers, candidates, counts and the copied assessment unchanged", async () => {
    const outcome = businessOutcome();
    const before = JSON.stringify({ facts: businessFacts, outcome });
    const originalCandidates = outcome.candidates;
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    try {
      renderSheet("SUPPORTED_CANDIDATES", "en", { facts: businessFacts, outcome });
      fireEvent.click(screen.getByRole("button", { name: "Copy summary" }));
      await waitFor(() => expect(screen.getByText("Copied to clipboard")).toBeInTheDocument());
      expect(writeText).toHaveBeenCalledOnce();
      const summary = writeText.mock.calls[0][0] as string;
      expect(summary).toContain("D1 — D1 fixture");
      expect(summary).toContain("D2 — D2 fixture");
      expect(summary).not.toContain("D12");
      expect(outcome.candidates).toBe(originalCandidates);
      expect(outcome.pathsRemaining).toBe(2);
      expect(JSON.stringify({ facts: businessFacts, outcome })).toBe(before);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe("Loop 06 evidence layers", () => {
  it.each(["en", "id"] as const)("qualifies mixed-product no-path reasons without changing them in %s", (language) => {
    const outcome = outcomeFor("NO_SUPPORTED_PATH");
    if (outcome.state !== "NO_SUPPORTED_PATH") throw new Error("fixture state");
    const capitalSource = { ...source, id: "capital-source", title: "Capital source", url: "https://example.test/capital" };
    outcome.sources = [source, capitalSource];
    outcome.noPathReasons = [
      { code: "D12_LOCAL_COMPENSATION_NOT_ALLOWED", message: text("D12 compensation exclusion"), sourceIds: [source.id] },
      { code: "E28A_PAID_CAPITAL_BELOW_MIN", message: text("E28A capital exclusion"), sourceIds: [capitalSource.id] },
      { code: "UNSCOPED_REASON", message: text("A reason without product context"), sourceIds: [source.id] },
    ];
    const before = JSON.stringify(outcome);
    renderSheet("NO_SUPPORTED_PATH", language, { outcome });
    const context = screen.getByRole("region", { name: language === "en" ? "Reasons from the route assessment" : "Alasan dari penilaian jalur" });
    expect(context).toHaveTextContent(language === "en" ? "not a combined checklist for one visa" : "bukan gabungan persyaratan untuk satu visa");
    expect(context).toHaveTextContent(language === "en" ? "does not identify its product" : "tidak mengidentifikasi produknya");
    expect(within(context).getAllByRole("listitem")).toHaveLength(3);
    for (const item of outcome.noPathReasons) expect(within(context).getByText(item.message[language])).toBeInTheDocument();
    expect(within(context).getByRole("link", { name: "Capital source" })).toHaveAttribute("href", capitalSource.url);
    expect(within(context).getAllByRole("link", { name: "Primary source fixture" })).toHaveLength(2);
    expect(JSON.stringify(outcome)).toBe(before);
    expect(document.querySelector(".oracle-candidate-card")).toBeNull();
  });
  it.each(["en", "id"] as const)("qualifies source-record dates separately from the assessment clock in %s", (language) => {
    renderSheet("SUPPORTED_CANDIDATES", language);
    const sourceDates = screen.getByText(language === "en" ? /Recorded applicability from/ : /Awal keberlakuan tercatat/);
    expect(sourceDates).toHaveTextContent(language === "en" ? "source checked" : "sumber diperiksa");
    expect(sourceDates).toHaveTextContent(language === "en" ? "1 July 2026" : "1 Juli 2026");
    expect(sourceDates).toHaveTextContent(language === "en" ? "23 July 2026" : "23 Juli 2026");
  });
  it("separates matched facts from still-required documents without dropping source links", () => {
    const outcome = outcomeFor("SUPPORTED_CANDIDATES");
    const candidate = { ...CANDIDATE, decisionReasons: [
      { ...reason, code: "PURPOSE_PRODUCT_MATCH", message: text("The declared purpose matches") },
      { ...reason, code: "REQ_D12_PASSPORT", message: text("A valid passport must be provided") },
    ], documents: [] };
    renderSheet("SUPPORTED_CANDIDATES", "en", { outcome: { ...outcome, candidates: [candidate] } as OutcomeViewModel });
    const matches = screen.getByRole("heading", { name: "Facts used by the matching rules" }).parentElement!;
    const conditions = screen.getByRole("heading", { name: "Conditions and checks still to satisfy" }).parentElement!;
    expect(within(matches).getByText("The declared purpose matches")).toBeInTheDocument();
    expect(within(matches).queryByText("A valid passport must be provided")).toBeNull();
    expect(within(conditions).getByText("A valid passport must be provided")).toBeInTheDocument();
    expect(within(conditions).getByRole("link", { name: "Primary source fixture" })).toHaveAttribute("href", source.url);
    expect(screen.getByText("Operational checklist unavailable")).toBeInTheDocument();
    expect(screen.getByText(/not a comparison of suitability/)).toBeInTheDocument();
    expect(screen.queryByText(/from today/)).toBeNull();
  });
  it("keeps unsigned provenance in the dossier and copy action", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    renderSheet("SUPPORTED_CANDIDATES", "en", { localProof: "unsigned-proposal" });
    expect(screen.getByText(/Local unsigned proposal/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /copy/i }));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    expect(writeText.mock.calls[0][0]).toContain("not signed or activated");
  });
});
