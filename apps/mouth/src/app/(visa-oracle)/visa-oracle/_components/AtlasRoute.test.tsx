/**
 * BUILD-SPEC §8 — "Your route" ledger contract (ORACLE-PROD-20260927).
 * Presentation only: `onEdit`/`onSelectCategory` are the same reducer
 * actions OracleShell already wires to Back/Edit/category tiles — this
 * component never mutates state itself, it only recaps `history`/`facts`
 * the caller already owns. Synthetic history/facts only.
 *
 * The REQUIRED FIX (this mandate, superseding BUILD-SPEC §8's own
 * "Change ... closes ... focus returns to the opener" phrasing): a
 * "Change"/alternative-direction close must NOT return focus to the
 * opener — that would race the new question heading's own mount-focus.
 * Only a plain close (×, backdrop, Escape) still restores it.
 */
import { createRef } from "react";
import { fireEvent, render, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  CATEGORY_KEYS,
  QUESTIONS,
  questionPromptI18nKey,
  type OracleFacts,
} from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";
import type { OracleNode } from "../_lib/flow";
import { formatFactDisplay } from "./ConfirmationCard";
import { AtlasRoute, type AtlasRouteHandle } from "./AtlasRoute";

const HISTORY: OracleNode[] = [
  { kind: "framing" },
  { kind: "question", questionId: "in_indonesia" },
  { kind: "question", questionId: "holds_stay_permit" },
  { kind: "question", questionId: "nationalities" },
  { kind: "question", questionId: "birth_date" },
  { kind: "question", questionId: "category" },
  { kind: "confirmation" },
];

const FACTS: OracleFacts = {
  in_indonesia: "no",
  holds_stay_permit: "no",
  nationalities: "US",
  birth_date: "1990-01-01",
  category: "tourism",
};

const ANSWERED_ORDER = [
  "in_indonesia",
  "holds_stay_permit",
  "nationalities",
  "birth_date",
  "category",
];

function Harness({
  language = "en" as "en" | "id",
  history = HISTORY,
  facts = FACTS,
  onEdit = vi.fn(),
  onSelectCategory = vi.fn(),
}: {
  language?: "en" | "id";
  history?: OracleNode[];
  facts?: OracleFacts;
  onEdit?: (questionId: string) => void;
  onSelectCategory?: (category: string) => void;
}) {
  return (
    <AtlasRoute
      language={language}
      history={history}
      facts={facts}
      onEdit={onEdit}
      onSelectCategory={onSelectCategory}
    />
  );
}

describe("AtlasRoute ledger", () => {
  it("lists only answered questions, deduplicated, in HISTORY order", () => {
    const { container } = render(<Harness />);
    const rows = container.querySelectorAll(".oracle-atlas-route__ledger li");
    expect(rows.length).toBe(ANSWERED_ORDER.length);
    ANSWERED_ORDER.forEach((questionId, index) => {
      const prompt = translate(
        "en",
        questionPromptI18nKey(QUESTIONS[questionId], FACTS) as I18nKey,
      );
      const value = formatFactDisplay("en", questionId, FACTS[questionId]);
      const row = within(rows[index] as HTMLElement);
      expect(row.getByText(prompt)).toBeInTheDocument();
      expect(row.getByText(value)).toBeInTheDocument();
    });
  });

  it("shows the empty-ledger copy when nothing has been answered yet", () => {
    const { getByText, container } = render(
      <Harness history={[{ kind: "framing" }]} facts={{}} />,
    );
    expect(getByText("No answers yet.")).toBeInTheDocument();
    expect(container.querySelector(".oracle-atlas-route__ledger")).toBeNull();
  });
});

describe("AtlasRoute focus management", () => {
  // The opener lives in the header, which scrolls away on a long verdict: a
  // focus return that scrolls it into view jumps the page back to the top.
  it("a plain close (×) restores focus to the opener without scrolling the page", () => {
    const ref = createRef<AtlasRouteHandle>();
    const { container } = render(
      <>
        <button type="button">opener</button>
        <AtlasRoute
          ref={ref}
          language="en"
          history={HISTORY}
          facts={FACTS}
          onEdit={vi.fn()}
          onSelectCategory={vi.fn()}
        />
      </>,
    );
    const opener = container.querySelector("button") as HTMLButtonElement;
    const focusSpy = vi.spyOn(opener, "focus");
    ref.current?.open(opener);

    fireEvent.click(
      container.querySelector(
        ".oracle-atlas-route__close",
      ) as HTMLButtonElement,
    );

    expect(focusSpy).toHaveBeenCalledTimes(1);
    expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true });
  });

  it("Escape (the native `cancel` event) closes once and returns focus to the opener (FIX-ROUND-2 K5)", () => {
    const ref = createRef<AtlasRouteHandle>();
    const { container } = render(
      <>
        <button type="button">opener</button>
        <AtlasRoute
          ref={ref}
          language="en"
          history={HISTORY}
          facts={FACTS}
          onEdit={vi.fn()}
          onSelectCategory={vi.fn()}
        />
      </>,
    );
    const opener = container.querySelector("button") as HTMLButtonElement;
    const focusSpy = vi.spyOn(opener, "focus");
    ref.current?.open(opener);
    const dialog = container.querySelector(
      ".oracle-atlas-route",
    ) as HTMLDialogElement;

    // jsdom's <dialog> never fires `cancel` on its own (no native Escape
    // handling) — this is what a real browser dispatches when Escape is
    // pressed; AtlasRoute's `onCancel` is what must react to it, not a
    // manual `onKeyDown` Escape branch (removed by this fix).
    fireEvent(
      dialog,
      new Event("cancel", { cancelable: true, bubbles: false }),
    );

    expect(focusSpy).toHaveBeenCalledTimes(1);
    expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true });
    expect(dialog).not.toHaveAttribute("open");
  });

  it("Change calls onEdit and closes WITHOUT returning focus to the opener", () => {
    const ref = createRef<AtlasRouteHandle>();
    const onEdit = vi.fn();
    const { container } = render(
      <>
        <button type="button">opener</button>
        <AtlasRoute
          ref={ref}
          language="en"
          history={HISTORY}
          facts={FACTS}
          onEdit={onEdit}
          onSelectCategory={vi.fn()}
        />
      </>,
    );
    const opener = container.querySelector("button") as HTMLButtonElement;
    const focusSpy = vi.spyOn(opener, "focus");
    ref.current?.open(opener);

    const firstRow = container.querySelector(
      ".oracle-atlas-route__ledger li",
    ) as HTMLElement;
    fireEvent.click(within(firstRow).getByRole("button", { name: /^change/i }));

    expect(onEdit).toHaveBeenCalledWith("in_indonesia");
    expect(focusSpy).not.toHaveBeenCalled();
    expect(container.querySelector("dialog")?.hasAttribute("open")).toBe(false);
  });

  it("an alternative-direction click calls onSelectCategory and closes WITHOUT returning focus to the opener", () => {
    const ref = createRef<AtlasRouteHandle>();
    const onSelectCategory = vi.fn();
    const { container, getByText } = render(
      <>
        <button type="button">opener</button>
        <AtlasRoute
          ref={ref}
          language="en"
          history={HISTORY}
          facts={FACTS}
          onEdit={vi.fn()}
          onSelectCategory={onSelectCategory}
        />
      </>,
    );
    const opener = container.querySelector("button") as HTMLButtonElement;
    const focusSpy = vi.spyOn(opener, "focus");
    ref.current?.open(opener);

    fireEvent.click(getByText("Explore another direction"));
    const alternatives = container.querySelector(
      ".oracle-atlas-route__alternatives div",
    ) as HTMLElement;
    const workButton = within(alternatives).getByText(
      translate("en", "q.category.opt.work" as I18nKey),
    );
    fireEvent.click(workButton);

    expect(onSelectCategory).toHaveBeenCalledWith("work");
    expect(focusSpy).not.toHaveBeenCalled();
  });

  it("the alternatives list excludes the currently selected category", () => {
    const { container } = render(<Harness />);
    fireEvent.click(container.querySelector("summary") as HTMLElement);
    const alternatives = container.querySelector(
      ".oracle-atlas-route__alternatives div",
    ) as HTMLElement;
    const labels = CATEGORY_KEYS.map((key) =>
      translate("en", `q.category.opt.${key}` as I18nKey),
    );
    const tourismLabel = translate("en", "q.category.opt.tourism" as I18nKey);
    for (const label of labels) {
      if (label === tourismLabel) {
        expect(within(alternatives).queryByText(label)).toBeNull();
      } else {
        expect(within(alternatives).getByText(label)).toBeInTheDocument();
      }
    }
  });
});

describe("AtlasRoute Indonesian copy", () => {
  it("renders the ID heading and empty-ledger copy", () => {
    const { getByText } = render(
      <Harness language="id" history={[{ kind: "framing" }]} facts={{}} />,
    );
    expect(getByText("Jalan yang Anda tempuh.")).toBeInTheDocument();
    expect(getByText("Belum ada jawaban.")).toBeInTheDocument();
  });
});
