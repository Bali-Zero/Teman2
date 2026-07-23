import { render, screen } from "@testing-library/react";
import { OutcomeSheet } from "./OutcomeSheet";
import type { EvaluatedCandidate, EvaluateResult } from "../_lib/mock-engine";
import type { Language } from "../_lib/flow";

/**
 * W0b regression guard (2026-07-23): the shared footer — WhatsApp escape
 * hatch, print/copy, assumptions receipt and the 4-line Ditjen disclaimer —
 * was wrapped in `result.state !== "NEEDS_INPUT"`, so the NEEDS_INPUT
 * terminal state rendered with no disclaimer and no way out (spec §A.3.2:
 * "the escape hatch is always present", never a dead end; §A.9: the 4-line
 * disclaimer is KEEP-verbatim under every verdict). These tests pin the
 * disclaimer + footer on ALL five terminal states, in both languages, and
 * the print anatomy (recap + disclaimer print; CTAs stay screen-only).
 * Follow-up (owner call 2026-07-23, Fable MEDIUM): next-steps is pinned to
 * SUPPORTED_CANDIDATES only — its step copy references the candidate
 * checklist, absent on every other state.
 */

const TODAY = new Date("2026-07-23T12:00:00Z");

const FACTS = { in_indonesia: "yes", category: "tourism" };

const DISCLAIMER_EN = [
  "This is a private decision-support demonstration, not a government service.",
  "The result reflects only the facts you entered and the cited sample ruleset above.",
  "It is not an approval, a guarantee, or a filing.",
  "Complex or flagged cases always go to a human — Ditjen Imigrasi decides, not this tool.",
];

const DISCLAIMER_ID = [
  "Ini demonstrasi alat bantu keputusan privat, bukan layanan pemerintah.",
  "Hasil ini hanya mencerminkan data yang Anda masukkan dan aturan contoh yang dikutip di atas.",
  "Ini bukan persetujuan, jaminan, atau pengajuan resmi.",
  "Kasus kompleks atau ditandai selalu diteruskan ke manusia — Ditjen Imigrasi yang memutuskan, bukan alat ini.",
];

const CANDIDATE: EvaluatedCandidate = {
  code: "B1",
  nameI18nKey: "visa.B1.name",
  taglineI18nKey: "visa.B1.tagline",
  allInclusivePriceIDR: 500000,
  timelineDays: [3, 7],
  eligibility: "eligible",
  requirementI18nKeys: ["req.passport_valid"],
  categories: ["tourism"],
};

function resultFor(state: EvaluateResult["state"]): EvaluateResult {
  const base: EvaluateResult = {
    state,
    candidates: [],
    assumptions: [{ questionId: "tourism_duration" }],
    pathsRemaining: 0,
  };
  if (state === "SUPPORTED_CANDIDATES") {
    return { ...base, candidates: [CANDIDATE], pathsRemaining: 1 };
  }
  if (state === "NO_SUPPORTED_PATH") {
    return { ...base, alternativeCategories: ["remote", "business", "other"] };
  }
  return base;
}

const ALL_STATES: EvaluateResult["state"][] = [
  "SUPPORTED_CANDIDATES",
  "NEEDS_INPUT",
  "HUMAN_REVIEW_REQUIRED",
  "NO_SUPPORTED_PATH",
  "TEMPORARILY_UNAVAILABLE",
];

function renderSheet(
  state: EvaluateResult["state"],
  language: Language = "en",
) {
  return render(
    <OutcomeSheet
      language={language}
      result={resultFor(state)}
      facts={FACTS}
      today={TODAY}
    />,
  );
}

describe("OutcomeSheet — shared footer on every terminal state (W0b)", () => {
  it.each(ALL_STATES)(
    "renders the 4-line disclaimer on %s (EN, verbatim)",
    (state) => {
      const { container } = renderSheet(state);
      const disclaimer = container.querySelector(".oracle-disclaimer");
      expect(disclaimer).not.toBeNull();
      for (const line of DISCLAIMER_EN) {
        expect(disclaimer).toHaveTextContent(line);
      }
    },
  );

  it.each(ALL_STATES)(
    "renders the 4-line disclaimer on %s in Indonesian (EN/ID parity)",
    (state) => {
      const { container } = renderSheet(state, "id");
      const disclaimer = container.querySelector(".oracle-disclaimer");
      expect(disclaimer).not.toBeNull();
      for (const line of DISCLAIMER_ID) {
        expect(disclaimer).toHaveTextContent(line);
      }
    },
  );

  it("NEEDS_INPUT keeps the escape hatch + receipt + print/copy (never a dead end)", () => {
    const { container } = renderSheet("NEEDS_INPUT");
    // §A.3.2: "Talk to an adviser instead" is always present.
    const cta = screen.getByRole("link", { name: /continue on whatsapp/i });
    expect(cta.getAttribute("href")).toContain("wa.me/");
    // Assumptions receipt + freshness stamp are the honesty anchor of an
    // abstention state — they must render here too.
    expect(
      screen.getByText("Assumptions & caveats, dated"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Sample ruleset 2026\.07-prototype/),
    ).toBeInTheDocument();
    // Print + copy controls stay available.
    expect(
      screen.getByRole("button", { name: /print \/ save as pdf/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /copy summary/i }),
    ).toBeInTheDocument();
    // QR encodes byte-identically the visible WhatsApp link (existing
    // invariant — must hold on NEEDS_INPUT too).
    const qr = container.querySelector("[data-qr-value]");
    expect(qr?.getAttribute("data-qr-value")).toBe(cta.getAttribute("href"));
  });

  it.each([
    "NEEDS_INPUT",
    "HUMAN_REVIEW_REQUIRED",
    "NO_SUPPORTED_PATH",
    "TEMPORARILY_UNAVAILABLE",
  ] as const)(
    "hides next-steps on %s (no candidate checklist to reference)",
    (state) => {
      // "Gather the documents listed above" points at a checklist that exists
      // only under SUPPORTED_CANDIDATES — anywhere else the section dangles.
      // Gated on SUPPORTED_CANDIDATES (owner call 2026-07-23, Fable MEDIUM).
      renderSheet(state);
      expect(screen.queryByText("Your next 3 steps")).not.toBeInTheDocument();
    },
  );

  it("keeps next-steps on SUPPORTED_CANDIDATES (checklist present)", () => {
    // The only state where the default step copy ("documents listed above")
    // is unambiguously correct: the candidate checklist renders above it.
    renderSheet("SUPPORTED_CANDIDATES");
    expect(screen.getByText("Your next 3 steps")).toBeInTheDocument();
  });

  it("print anatomy on NEEDS_INPUT: answers recap + disclaimer print, CTAs stay screen-only", () => {
    const { container } = renderSheet("NEEDS_INPUT");
    // The print-only "your answers" recap renders (facts were answered).
    expect(container.querySelector(".oracle-print-only")).not.toBeNull();
    // Disclaimer + receipt are NOT hidden from print…
    expect(
      container.querySelector(".oracle-disclaimer.oracle-no-print"),
    ).toBeNull();
    expect(
      container.querySelector(".oracle-receipt.oracle-no-print"),
    ).toBeNull();
    // …while the interactive CTAs/actions are.
    expect(
      container.querySelector(".oracle-whatsapp-cta")?.closest("section"),
    ).toHaveClass("oracle-no-print");
    expect(container.querySelector(".oracle-outcome-actions")).toHaveClass(
      "oracle-no-print",
    );
  });
});
