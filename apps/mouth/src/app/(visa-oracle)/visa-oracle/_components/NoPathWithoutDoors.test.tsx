import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  buildEngineOutcome,
  isNoPathWithoutDoors,
} from "../_lib/engine-adapter";
import type { Language } from "../_lib/flow";
import type {
  NoSupportedPathOutcome,
  OutcomeViewModel,
} from "../_lib/outcome-view-model";
import { makeVisaOracleResponse } from "../_lib/visa-oracle-test-fixture";
import { OutcomeSheet } from "./OutcomeSheet";
import { VerdictReveal } from "./VerdictReveal";

afterEach(cleanup);

const OLD_HEADLINE = {
  en: "This exact path isn’t supported — here’s what instead",
  id: "Jalur persis ini belum didukung — ini alternatifnya",
};
const OLD_SUB = {
  en: "We won’t force a fit that isn’t there — here is what your answers do open.",
  id: "Kami tidak akan memaksakan jalur yang tidak cocok — inilah yang dibuka oleh jawaban Anda.",
};
const NEW_HEADLINE = {
  en: "This path isn’t one this tool can confirm",
  id: "Alat ini tidak dapat memastikan jalur tersebut",
};
const NEW_SUB = {
  en: "We won’t force a fit that isn’t there. A Bali Zero advisor can review details this tool does not cover.",
  id: "Kami tidak akan memaksakan jalur yang tidak cocok. Konsultan Bali Zero dapat meninjau informasi tambahan yang tidak dicakup oleh alat ini.",
};
const OPEN_DOOR_STEP = {
  en: "Look at the open door above, if one is shown.",
  id: "Lihat alternatif di atas, jika ada.",
};
const ADVISOR_STEP = {
  en: "Talk to a Bali Zero advisor — some routes depend on facts this tool does not ask.",
  id: "Bicarakan dengan konsultan Bali Zero — beberapa jalur bergantung pada hal yang tidak ditanyakan alat ini.",
};
const SUMMARY_STEP = {
  en: "Keep this summary: it shows exactly what was checked.",
  id: "Simpan ringkasan ini: isinya menunjukkan apa saja yang sudah diperiksa.",
};

/** A real engine outcome with ZERO doors: the sourceless dead end names none. */
function zeroDoorOutcome(): NoSupportedPathOutcome {
  const response = makeVisaOracleResponse("NO_SUPPORTED_PATH");
  response.decision.no_path_reasons = [
    {
      code: "DISCLOSED_ACTIVITY_BOUNDARY_NO_PATH",
      rule_ids: ["system.disclosed-no-path.activity-boundary"],
      source_refs: [],
    },
  ];
  const outcome = buildEngineOutcome(response);
  if (outcome.state !== "NO_SUPPORTED_PATH") throw new Error("unexpected");
  return outcome;
}

/** A real engine outcome with one door: a non-tourism purpose and a short
 * stay open the C1 tourism door in `buildNoPathDoors`. */
function oneDoorOutcome(): NoSupportedPathOutcome {
  const response = makeVisaOracleResponse("NO_SUPPORTED_PATH");
  const outcome = buildEngineOutcome(response, {
    facts: { category: "work", stay_days: "30" },
  });
  if (outcome.state !== "NO_SUPPORTED_PATH") throw new Error("unexpected");
  return outcome;
}

function titles(outcome: OutcomeViewModel, language: Language): string[] {
  return outcome.nextSteps.map((s) => s.title[language]);
}

async function sharedSummary(outcome: OutcomeViewModel, language: Language) {
  render(<OutcomeSheet language={language} outcome={outcome} facts={{}} />);
  const writeText = navigator.clipboard.writeText as ReturnType<typeof vi.fn>;
  writeText.mockClear();
  fireEvent.click(
    screen.getByRole("button", {
      name: language === "id" ? /salin ringkasan/i : "Copy summary",
    }),
  );
  await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
  return writeText.mock.calls[0]?.[0] as string;
}

describe.each(["en", "id"] as const)(
  "NO_SUPPORTED_PATH with no open door (%s)",
  (language) => {
    it("the adapter emits zero doors and the two-step list without the open-door step", () => {
      const outcome = zeroDoorOutcome();
      expect(outcome.alternatives).toEqual([]);
      expect(isNoPathWithoutDoors(outcome)).toBe(true);
      expect(titles(outcome, language)).toEqual([
        ADVISOR_STEP[language],
        SUMMARY_STEP[language],
      ]);
      expect(titles(outcome, language)).not.toContain(OPEN_DOOR_STEP[language]);
    });

    it("VerdictReveal shows the no-promise headline and sub-headline", () => {
      render(
        <VerdictReveal
          language={language}
          state="NO_SUPPORTED_PATH"
          provenance="ENGINE"
          isNoPathWithoutDoors
        />,
      );
      expect(screen.getByRole("heading").textContent).toBe(
        NEW_HEADLINE[language],
      );
      expect(screen.getByText(NEW_SUB[language])).toBeInTheDocument();
      expect(screen.queryByText(OLD_HEADLINE[language])).toBeNull();
      expect(screen.queryByText(OLD_SUB[language])).toBeNull();
    });

    it("the sheet renders the steps without the open-door step, and the share text carries the new headline", async () => {
      const outcome = zeroDoorOutcome();
      const summary = await sharedSummary(outcome, language);
      expect(summary).toContain(NEW_HEADLINE[language]);
      expect(summary).not.toContain(OLD_HEADLINE[language]);
      expect(screen.queryByText(OPEN_DOOR_STEP[language])).toBeNull();
      expect(screen.getByText(ADVISOR_STEP[language])).toBeInTheDocument();
    });

    it("with at least one door everything is unchanged", async () => {
      const outcome = oneDoorOutcome();
      expect(outcome.alternatives.length).toBeGreaterThan(0);
      expect(isNoPathWithoutDoors(outcome)).toBe(false);
      expect(titles(outcome, language)).toEqual([
        OPEN_DOOR_STEP[language],
        ADVISOR_STEP[language],
        SUMMARY_STEP[language],
      ]);
      const { unmount } = render(
        <VerdictReveal
          language={language}
          state="NO_SUPPORTED_PATH"
          provenance="ENGINE"
          isNoPathWithoutDoors={isNoPathWithoutDoors(outcome)}
        />,
      );
      expect(screen.getByRole("heading").textContent).toBe(
        OLD_HEADLINE[language],
      );
      expect(screen.getByText(OLD_SUB[language])).toBeInTheDocument();
      unmount();
      const summary = await sharedSummary(outcome, language);
      expect(summary).toContain(OLD_HEADLINE[language]);
      expect(summary).not.toContain(NEW_HEADLINE[language]);
    });
  },
);
