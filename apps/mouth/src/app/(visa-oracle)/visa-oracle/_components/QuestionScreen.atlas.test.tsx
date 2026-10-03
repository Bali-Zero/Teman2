/**
 * BUILD-SPEC §5/§8 — additive-only atlas presentation props on
 * `QuestionScreen` (ORACLE-PROD-20260927). "default" must render byte-for-
 * byte identical option markup to before this build (invariant §0.2); the
 * three named presentations only ever change the OPTIONS markup, never
 * accessible names (invariant §0.4), Back/notices/WhyWeAsk/NotSure.
 * Synthetic interaction only.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QUESTIONS } from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";
import { QuestionScreen } from "./QuestionScreen";

const IN_INDONESIA = QUESTIONS.in_indonesia;
const HOLDS_STAY_PERMIT = QUESTIONS.holds_stay_permit;
const CATEGORY = QUESTIONS.category;
const TRIP_SCOPE = QUESTIONS.trip_scope;

describe("QuestionScreen — world presentation (in_indonesia)", () => {
  it("pins the exact i18n option labels as accessible names, with data-answer hooks", () => {
    render(
      <QuestionScreen
        language="en"
        question={IN_INDONESIA}
        onAnswer={vi.fn()}
        onSkip={vi.fn()}
        onBack={vi.fn()}
        canGoBack={false}
        presentation="world"
      />,
    );
    const yes = screen.getByRole("button", { name: "Yes, I’m here" });
    const no = screen.getByRole("button", { name: "No, I’m planning ahead" });
    expect(yes).toHaveAttribute("data-answer", "yes");
    expect(no).toHaveAttribute("data-answer", "no");
    expect(yes.className).toContain("oracle-atlas-choice");
  });

  it("renders 'no' before 'yes' in DOM order regardless of the tree's own option order (FIX-ROUND-2 K4)", () => {
    render(
      <QuestionScreen
        language="en"
        question={IN_INDONESIA}
        onAnswer={vi.fn()}
        onSkip={vi.fn()}
        onBack={vi.fn()}
        canGoBack={false}
        presentation="world"
      />,
    );
    const buttons = screen
      .getAllByRole("button")
      .filter((button) => button.hasAttribute("data-answer"));
    expect(buttons.map((button) => button.getAttribute("data-answer"))).toEqual(
      ["no", "yes"],
    );
  });

  it("calls onAnswer with the option key", () => {
    const onAnswer = vi.fn();
    render(
      <QuestionScreen
        language="en"
        question={IN_INDONESIA}
        onAnswer={onAnswer}
        onSkip={vi.fn()}
        onBack={vi.fn()}
        canGoBack={false}
        presentation="world"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Yes, I’m here" }));
    expect(onAnswer).toHaveBeenCalledWith("yes");
  });
});

describe("QuestionScreen — permit presentation (holds_stay_permit)", () => {
  it("pins exact 'Yes'/'No' accessible names, with data-answer hooks", () => {
    render(
      <QuestionScreen
        language="en"
        question={HOLDS_STAY_PERMIT}
        onAnswer={vi.fn()}
        onSkip={vi.fn()}
        onBack={vi.fn()}
        canGoBack={false}
        presentation="permit"
      />,
    );
    const yes = screen.getByRole("button", { name: "Yes" });
    const no = screen.getByRole("button", { name: "No" });
    expect(yes).toHaveAttribute("data-answer", "yes");
    expect(no).toHaveAttribute("data-answer", "no");
    expect(yes.className).toContain("oracle-atlas-permit-answer");
  });
});

describe("QuestionScreen — watershed presentation (category)", () => {
  it("every tile's accessible name is exactly its q.category.opt.* label, glyph/arrow aria-hidden", () => {
    render(
      <QuestionScreen
        language="en"
        question={CATEGORY}
        onAnswer={vi.fn()}
        onSkip={vi.fn()}
        onBack={vi.fn()}
        canGoBack={false}
        presentation="watershed"
      />,
    );
    for (const option of CATEGORY.options) {
      const label = translate("en", option.labelI18nKey as I18nKey);
      const tile = screen.getByRole("button", { name: label });
      expect(tile).toHaveAttribute("data-category", option.key);
    }
  });

  it("previews on mouse pointerenter and resets on mouseleave, but not on touch", () => {
    // React's onPointerEnter/onMouseLeave plugins listen for the BUBBLING
    // native events (`pointerover`/`mouseout`), not the non-bubbling
    // `pointerenter`/`mouseleave` — `fireEvent.pointerOver`/`.mouseOut` are
    // what actually reach the React synthetic handlers under jsdom.
    const onPreviewOption = vi.fn();
    const { container } = render(
      <QuestionScreen
        language="en"
        question={CATEGORY}
        onAnswer={vi.fn()}
        onSkip={vi.fn()}
        onBack={vi.fn()}
        canGoBack={false}
        presentation="watershed"
        onPreviewOption={onPreviewOption}
      />,
    );
    const tourismTile = container.querySelector(
      '[data-category="tourism"]',
    ) as HTMLElement;
    const group = container.querySelector(".oracle-tiles") as HTMLElement;

    fireEvent.pointerOver(tourismTile, { pointerType: "touch" });
    expect(onPreviewOption).not.toHaveBeenCalled();

    fireEvent.pointerOver(tourismTile, { pointerType: "mouse" });
    expect(onPreviewOption).toHaveBeenCalledWith("tourism");

    fireEvent.mouseOut(group);
    expect(onPreviewOption).toHaveBeenCalledWith(null);
  });

  it("tile-to-tile focus keeps the preview; focus leaving the group clears it (FIX-ROUND-2 S1)", () => {
    const onPreviewOption = vi.fn();
    const { container } = render(
      <div>
        <button type="button">Back</button>
        <QuestionScreen
          language="en"
          question={CATEGORY}
          onAnswer={vi.fn()}
          onSkip={vi.fn()}
          onBack={vi.fn()}
          canGoBack={false}
          presentation="watershed"
          onPreviewOption={onPreviewOption}
        />
      </div>,
    );
    const tourismTile = container.querySelector(
      '[data-category="tourism"]',
    ) as HTMLElement;
    const workTile = container.querySelector(
      '[data-category="work"]',
    ) as HTMLElement;
    const back = screen.getByRole("button", { name: "Back" });

    tourismTile.focus();
    expect(onPreviewOption).toHaveBeenCalledWith("tourism");
    onPreviewOption.mockClear();

    // Tile -> tile: React's onBlur is synthesized from the BUBBLING native
    // `focusout` (like onFocus/`focusin` above) — relatedTarget is still
    // inside the group, so the preview must NOT clear.
    fireEvent.focusOut(tourismTile, { relatedTarget: workTile });
    expect(onPreviewOption).not.toHaveBeenCalledWith(null);
    workTile.focus();
    expect(onPreviewOption).toHaveBeenCalledWith("work");
    onPreviewOption.mockClear();

    // Tile -> Back (outside the group): must clear.
    fireEvent.focusOut(workTile, { relatedTarget: back });
    expect(onPreviewOption).toHaveBeenCalledWith(null);
  });

  it("previews on focus too (keyboard navigation)", () => {
    // React 17+ synthesizes onFocus from the BUBBLING native `focusin`
    // event, which only a real `.focus()` call dispatches under jsdom —
    // `fireEvent.focus` dispatches a non-bubbling `focus` only and never
    // reaches React's root-delegated listener.
    const onPreviewOption = vi.fn();
    const { container } = render(
      <QuestionScreen
        language="en"
        question={CATEGORY}
        onAnswer={vi.fn()}
        onSkip={vi.fn()}
        onBack={vi.fn()}
        canGoBack={false}
        presentation="watershed"
        onPreviewOption={onPreviewOption}
      />,
    );
    const workTile = container.querySelector(
      '[data-category="work"]',
    ) as HTMLElement;
    workTile.focus();
    expect(onPreviewOption).toHaveBeenCalledWith("work");
  });

  // ENDING-ROUND scope extension (Dux, coordinator-relayed): the watershed
  // "Your direction only chooses..." sentence (E10) is process explanation,
  // not a substantive hint — it now joins world/permit's collapsed
  // disclosure instead of always being visible inline. No copy removed.
  it("renders WhyWeAsk as a closed disclosure trigger, not an always-visible paragraph (ENDING-ROUND scope extension)", () => {
    render(
      <QuestionScreen
        language="en"
        question={CATEGORY}
        onAnswer={vi.fn()}
        onSkip={vi.fn()}
        onBack={vi.fn()}
        canGoBack={false}
        presentation="watershed"
      />,
    );
    const sentence = translate("en", "why.category" as I18nKey);
    expect(screen.queryByText(sentence)).toBeNull();
    const trigger = screen.getByRole("button", {
      name: translate("en", "whyweask.trigger.aria" as I18nKey),
    });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(trigger);
    expect(screen.getByText(sentence)).toBeInTheDocument();
  });
});

describe("QuestionScreen — default presentation stays byte-for-byte unchanged", () => {
  it("in_indonesia renders plain option cards, no data-answer/data-presentation pins leaking into options", () => {
    const { container } = render(
      <QuestionScreen
        language="en"
        question={IN_INDONESIA}
        onAnswer={vi.fn()}
        onSkip={vi.fn()}
        onBack={vi.fn()}
        canGoBack={false}
      />,
    );
    expect(container.querySelector("[data-answer]")).toBeNull();
    expect(container.querySelector(".oracle-atlas-choice")).toBeNull();
    expect(container.querySelector(".oracle-option-card")).not.toBeNull();
    expect(container.querySelector(".oracle-question")).toHaveAttribute(
      "data-presentation",
      "default",
    );
  });

  it("holds_stay_permit renders plain option cards by default", () => {
    const { container } = render(
      <QuestionScreen
        language="en"
        question={HOLDS_STAY_PERMIT}
        onAnswer={vi.fn()}
        onSkip={vi.fn()}
        onBack={vi.fn()}
        canGoBack={false}
      />,
    );
    expect(container.querySelector(".oracle-atlas-permit-answer")).toBeNull();
    expect(container.querySelector(".oracle-option-card")).not.toBeNull();
  });

  it("category renders plain tiles by default, no watershed branch class", () => {
    const { container } = render(
      <QuestionScreen
        language="en"
        question={CATEGORY}
        onAnswer={vi.fn()}
        onSkip={vi.fn()}
        onBack={vi.fn()}
        canGoBack={false}
      />,
    );
    expect(container.querySelector(".oracle-atlas-branch")).toBeNull();
    expect(container.querySelectorAll(".oracle-tile").length).toBe(
      CATEGORY.options.length,
    );
  });
});

describe("QuestionScreen — D11: no internal/technical metadata on the public surface", () => {
  const LEAKS = [
    "Decision input",
    "Input keputusan",
    "Human context only",
    "Hanya konteks manusia",
  ];

  it.each([
    ["world stage (in_indonesia)", IN_INDONESIA, "world"],
    ["permit stage (holds_stay_permit)", HOLDS_STAY_PERMIT, "permit"],
    ["landscape HUMAN_CONTEXT question (trip_scope)", TRIP_SCOPE, "default"],
  ] as const)(
    "%s leaks nothing, EN and ID",
    (_label, question, presentation) => {
      for (const language of ["en", "id"] as const) {
        const { container, unmount } = render(
          <QuestionScreen
            language={language}
            question={question}
            onAnswer={vi.fn()}
            onSkip={vi.fn()}
            onBack={vi.fn()}
            canGoBack={false}
            presentation={presentation}
          />,
        );
        const text = container.textContent ?? "";
        for (const needle of LEAKS) {
          expect(text).not.toContain(needle);
        }
        expect(container.querySelector(".oracle-decision-boundary")).toBeNull();
        unmount();
      }
    },
  );
});
