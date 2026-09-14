import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import {
  CellStack,
  DeskStrip,
  EmptyState,
  Field,
  HairlineBody,
  HairlineGrid,
  HairlineHead,
  HairlineRow,
  LedgerSection,
  Masthead,
  Notice,
  NumberedList,
  Numeral,
  OrdinalMargin,
  PILL_TONE,
  Slip,
  Stamp,
  StatePill,
  pad2,
} from "..";

const DIR = join(__dirname, "..");
const sources = readdirSync(DIR)
  .filter((f) => f.endsWith(".ts") || f.endsWith(".tsx"))
  .map((f) => [f, readFileSync(join(DIR, f), "utf8")] as const);

/**
 * Guilt and innocence (cicatrix-superscar #3). Each detector below is a pure
 * function run against a planted violation as well as against the real module,
 * so a green run means the detector works rather than that it is asleep.
 *
 * They judge CODE, not prose. A doc comment naming `--state-danger` as the
 * thing kita re-aliases, or citing PR #6483, is documentation; scanning it
 * would make the guard fire on its own explanation, which is how a guard
 * becomes noise and then gets deleted. `stripComments` is itself tested.
 */

/** Remove line and block comments, so a detector reads code only. */
export function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

/** A module that paints kita must never read a danger token or a raw hex. */
export function findForbiddenPaint(src: string): string[] {
  const found: string[] = [];
  if (/var\(--state-danger\)/.test(src)) found.push("--state-danger");
  if (/var\(--bz-red\)/.test(src)) found.push("--bz-red");
  if (/var\(--bz-neon-purple\)/.test(src)) found.push("--bz-neon-purple");
  for (const hex of src.match(/(?<![\w#&])#[0-9a-fA-F]{3,8}(?![\w])/g) ?? [])
    found.push(hex.toLowerCase());
  return found;
}

/**
 * Copper as a background is the law this module exists to hold. The single
 * sanctioned exception is `COPPER_RULE`, the 96x4 masthead graphic, which
 * carries no label — so the exemption is by NAMED CONSTANT, never by shape:
 * a second copper fill cannot hide behind a similar-looking class string.
 */
export function findCopperFill(src: string): string[] {
  const out: string[] = [];
  for (const line of src.split("\n")) {
    if (/\bCOPPER_RULE\b/.test(line)) continue;
    for (const m of line.matchAll(/\bbg-\[var\(--([a-z0-9-]+)\)\]/g))
      if (/copper/.test(m[1])) out.push(m[0]);
    for (const m of line.matchAll(/background:\s*"var\(--([a-z0-9-]+)\)"/g))
      if (/copper/.test(m[1])) out.push(m[0]);
  }
  return out;
}

describe("the r19 module obeys the kita laws", () => {
  it("reads no danger token and hardcodes no colour", () => {
    for (const [name, src] of sources)
      expect([name, findForbiddenPaint(stripComments(src))]).toEqual([
        name,
        [],
      ]);
  });

  it("never paints copper as a fill", () => {
    for (const [name, src] of sources)
      expect([name, findCopperFill(stripComments(src))]).toEqual([name, []]);
  });

  it("does not import the page-local garuda-voa copy", () => {
    for (const [name, src] of sources)
      expect([name, /garuda-voa/.test(stripComments(src))]).toEqual([
        name,
        false,
      ]);
  });

  it("the paint detector is awake (guilt)", () => {
    expect(findForbiddenPaint("color: var(--state-danger)")).toEqual([
      "--state-danger",
    ]);
    expect(findForbiddenPaint('border: "1px solid #b91c1c"')).toEqual([
      "#b91c1c",
    ]);
    expect(findCopperFill("className={'bg-[var(--bz-copper)]'}")).toEqual([
      "bg-[var(--bz-copper)]",
    ]);
    // The exemption is the NAME, so a copy of the class string is still
    // guilty — RE-PINNED to v2's 96x4 geometry (was "h-[3px] w-14" in v1);
    // the point proved is unchanged.
    expect(
      findCopperFill('const FAKE = "h-[4px] w-[72px] bg-[var(--bz-copper)]";'),
    ).toEqual(["bg-[var(--bz-copper)]"]);
  });

  it("the comment stripper keeps code and drops prose (guilt and innocence)", () => {
    expect(stripComments("/* --state-danger */ const a = 1;").trim()).toBe(
      "const a = 1;",
    );
    expect(stripComments("const a = 1; // PR #6483").trim()).toBe(
      "const a = 1;",
    );
    // It must NOT eat a URL's double slash, or it would swallow real code.
    expect(stripComments('const u = "https://x.test/a";')).toContain(
      "https://x.test/a",
    );
    // And a planted violation in real CODE still gets through it.
    expect(
      findForbiddenPaint(stripComments("/* ok */ color: var(--state-danger);")),
    ).toEqual(["--state-danger"]);
  });

  it("does not accuse a legal copper read (innocence)", () => {
    expect(findForbiddenPaint("text-[var(--bz-copper-text)]")).toEqual([]);
    expect(findCopperFill("text-[var(--bz-copper-text)]")).toEqual([]);
    expect(findCopperFill("bg-[var(--state-info)]")).toEqual([]);
    expect(
      findCopperFill('export const COPPER_RULE = "bg-[var(--bz-copper)]";'),
    ).toEqual([]);
  });
});

describe("StatePill", () => {
  it("is an inert span with a dot when it reports a state", () => {
    const { container } = render(
      <StatePill tone="you" label="Waiting on you" />,
    );
    expect(screen.getByText("Waiting on you").tagName).toBe("SPAN");
    expect(container.querySelector("button")).toBeNull();
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull();
  });

  it("the dot is a diamond pip, not a circle", () => {
    const { container } = render(<StatePill tone="ours" label="Ours" />);
    const pip = container.querySelector('[aria-hidden="true"]') as HTMLElement;
    expect(pip.className).toContain("rotate-45");
    expect(pip.className).not.toContain("rounded-full");
  });

  it("is square (2px radius), never a circle", () => {
    render(<StatePill tone="wait" label="Waiting" />);
    expect(screen.getByText("Waiting").className).toContain("rounded-[2px]");
  });

  it("becomes a focusable aria-pressed button when it is a filter", () => {
    const onClick = vi.fn();
    render(
      <StatePill
        tone="wait"
        label="Active"
        pressed={false}
        onClick={onClick}
      />,
    );
    const btn = screen.getByRole("button", { name: /Active/ });
    expect(btn.getAttribute("aria-pressed")).toBe("false");
    btn.click();
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("shows the tick as a second signal when selected, not fill alone", () => {
    render(<StatePill tone="wait" label="Active" pressed />);
    const btn = screen.getByRole("button", { name: /Active/ });
    expect(btn.getAttribute("aria-pressed")).toBe("true");
    expect(btn.textContent).toContain("✓");
    // v2 fills the selected pill INK with paper text, not slate —
    // RE-PINNED from `bg-[var(--state-info)]` (v1) onto `bg-[var(--tx-pure)]`
    // (v2, PILL_SELECTED). The point proved (a fill alone is not the only
    // signal — the tick is) is unchanged.
    expect(btn.className).toContain("bg-[var(--tx-pure)]");
  });

  it("carries five tones and only ink is filled", () => {
    expect(Object.keys(PILL_TONE)).toEqual([
      "ok",
      "ours",
      "you",
      "wait",
      "ink",
    ]);
    const filled = Object.entries(PILL_TONE).filter(([, v]) =>
      v.includes("bg-"),
    );
    expect(filled.map(([k]) => k)).toEqual(["ink"]);
  });

  it("never has a copper background — the guard is armed against a planted violation (guilt)", () => {
    // Simulates a future edit that fills a pill copper directly, the way
    // `StatePill`'s own BASE/className plumbing could if someone "simplified"
    // it. `findCopperFill` must flag it RED.
    const planted =
      'className={cn(BASE, "bg-[var(--bz-copper)]", pressed ? PILL_SELECTED : PILL_TONE[tone])}';
    expect(findCopperFill(planted)).toEqual(["bg-[var(--bz-copper)]"]);
  });
});

describe("DeskStrip", () => {
  it("names its filter group so the fill is not the only signal", () => {
    render(
      <DeskStrip
        count={40}
        filters={<StatePill tone="wait" label="Active" pressed={false} />}
        right={<span>right</span>}
      />,
    );
    expect(screen.getByRole("group", { name: "Filter" })).toBeTruthy();
    expect(screen.getByText("40")).toBeTruthy();
    expect(screen.getByText("right")).toBeTruthy();
  });

  it("the count is the 22px Fraunces count token", () => {
    render(<DeskStrip count={7} />);
    expect(screen.getByText("7").className).toContain("text-[22px]");
  });
});

describe("HairlineGrid", () => {
  it("puts the header row OUTSIDE the body on one shared --cols template", () => {
    const { container } = render(
      <HairlineGrid cols="1fr 120px">
        <HairlineHead>
          <span>Name</span>
          <span>Status</span>
        </HairlineHead>
        <HairlineBody>
          <HairlineRow>
            <span>Row</span>
            <span>Open</span>
          </HairlineRow>
        </HairlineBody>
      </HairlineGrid>,
    );
    const grid = container.firstElementChild as HTMLElement;
    expect(grid.style.getPropertyValue("--cols")).toBe("1fr 120px");
    const head = container.querySelector('[role="row"]')!;
    const body = grid.children[1];
    expect(head.parentElement).toBe(grid);
    expect(body.contains(head)).toBe(false);
  });

  it("reserves the action column and keeps a touch fallback", () => {
    const { container } = render(
      <HairlineGrid cols="1fr 92px">
        <HairlineBody>
          <HairlineRow
            actions={<button>Open</button>}
            touchAction={<button>More</button>}
          >
            <span>Row</span>
          </HairlineRow>
        </HairlineBody>
      </HairlineGrid>,
    );
    expect(screen.getByText("Open")).toBeTruthy();
    expect(screen.getByText("More")).toBeTruthy();
    expect(container.innerHTML).toContain("group-focus-within/row:opacity-100");
  });

  it("HairlineHead sticks at the header height by default and takes an override", () => {
    const { container, rerender } = render(
      <HairlineGrid cols="1fr">
        <HairlineHead>
          <span>Name</span>
        </HairlineHead>
      </HairlineGrid>,
    );
    const head = container.querySelector('[role="row"]') as HTMLElement;
    expect(head.style.top).toBe("var(--bz-header-height, 48px)");
    expect(head.className).toContain("border-[var(--tx-pure)]");

    rerender(
      <HairlineGrid cols="1fr">
        <HairlineHead stickyTop="96px">
          <span>Name</span>
        </HairlineHead>
      </HairlineGrid>,
    );
    const head2 = container.querySelector('[role="row"]') as HTMLElement;
    expect(head2.style.top).toBe("96px");
  });

  it("emits a scoped collapse style when both colsCollapsed and id are given", () => {
    const { container } = render(
      <HairlineGrid cols="1.7fr 1fr 1fr" colsCollapsed="1.7fr 1fr" id="clients">
        <HairlineBody>
          <HairlineRow>
            <span>Row</span>
          </HairlineRow>
        </HairlineBody>
      </HairlineGrid>,
    );
    const style = container.querySelector("style");
    expect(style).not.toBeNull();
    expect(style!.textContent).toContain("max-width:1360px");
    expect(style!.textContent).toContain(
      '[data-hgrid="clients"]{--cols:1.7fr 1fr}',
    );
    expect(style!.textContent).toContain(
      '[data-hgrid="clients"] [data-collapse]{display:none}',
    );
    expect(style!.textContent).toContain(
      '[data-hgrid="clients"] [data-collapsed-meta]{display:inline}',
    );
  });

  it("honours a custom collapseAt", () => {
    const { container } = render(
      <HairlineGrid
        cols="1fr 1fr"
        colsCollapsed="1fr"
        id="obligations"
        collapseAt={900}
      >
        <HairlineBody>
          <HairlineRow>
            <span>Row</span>
          </HairlineRow>
        </HairlineBody>
      </HairlineGrid>,
    );
    expect(container.querySelector("style")!.textContent).toContain(
      "max-width:900px",
    );
  });

  it("emits no scoped style when colsCollapsed is given without id (innocence)", () => {
    const { container } = render(
      <HairlineGrid cols="1fr 1fr" colsCollapsed="1fr">
        <HairlineBody>
          <HairlineRow>
            <span>Row</span>
          </HairlineRow>
        </HairlineBody>
      </HairlineGrid>,
    );
    expect(container.querySelector("style")).toBeNull();
  });

  it("CellStack's collapsed slot renders hidden by default", () => {
    render(<CellStack primary="PT Contoh Abadi" collapsed="Owner: Member A" />);
    const meta = screen.getByText("Owner: Member A");
    expect(meta.hasAttribute("data-collapsed-meta")).toBe(true);
    expect(meta.className).toContain("hidden");
  });

  describe("HairlineRow href/keyboard/stopPropagation", () => {
    it("activates on click, on Enter and on Space; Space preventDefaults", () => {
      const onActivate = vi.fn();
      render(
        <HairlineGrid cols="1fr">
          <HairlineBody>
            <HairlineRow href="/clients/0412" onActivate={onActivate}>
              <span>Client 0412</span>
            </HairlineRow>
          </HairlineBody>
        </HairlineGrid>,
      );
      const row = screen.getByRole("link");
      expect(row.getAttribute("tabindex")).toBe("0");
      expect(row.getAttribute("data-href")).toBe("/clients/0412");

      fireEvent.click(row);
      expect(onActivate).toHaveBeenNthCalledWith(1, "/clients/0412");

      fireEvent.keyDown(row, { key: "Enter" });
      expect(onActivate).toHaveBeenNthCalledWith(2, "/clients/0412");

      const notCancelled = fireEvent.keyDown(row, { key: " " });
      expect(onActivate).toHaveBeenNthCalledWith(3, "/clients/0412");
      // fireEvent returns false when the event was cancelable and
      // preventDefault() was called — proving Space did not scroll the page.
      expect(notCancelled).toBe(false);
    });

    it("a click inside actions does NOT activate the row", () => {
      const onActivate = vi.fn();
      render(
        <HairlineGrid cols="1fr">
          <HairlineBody>
            <HairlineRow
              href="/clients/0412"
              onActivate={onActivate}
              actions={<button>Open</button>}
            >
              <span>Client 0412</span>
            </HairlineRow>
          </HairlineBody>
        </HairlineGrid>,
      );
      fireEvent.click(screen.getByText("Open"));
      expect(onActivate).not.toHaveBeenCalled();
    });

    it("without href the row carries no role and no tabIndex (innocence)", () => {
      const { container } = render(
        <HairlineGrid cols="1fr">
          <HairlineBody>
            <HairlineRow>
              <span>Client 0412</span>
            </HairlineRow>
          </HairlineBody>
        </HairlineGrid>,
      );
      const grid = container.firstElementChild as HTMLElement;
      const body = grid.children[0] as HTMLElement;
      const row = body.children[0] as HTMLElement;
      expect(row.getAttribute("role")).toBeNull();
      expect(row.hasAttribute("tabindex")).toBe(false);
      expect(row.hasAttribute("data-href")).toBe(false);
    });
  });
});

describe("the remaining primitives render their contract", () => {
  it("Numeral pads to two digits and takes the ownership tone", () => {
    render(<Numeral n={3} tone="you" />);
    expect(screen.getByText("03").className).toContain("--bz-copper-text");
    expect(pad2(9)).toBe("09");
    expect(pad2(12)).toBe("12");
  });

  it("Numeral size maps to the three token classes and refuses none silently", () => {
    const { rerender } = render(<Numeral n={1} size="kpi" />);
    expect(screen.getByText("01").className).toContain("text-[38px]");
    expect(screen.getByText("01").className).toContain("md:text-[44px]");

    rerender(<Numeral n={1} size="count" />);
    expect(screen.getByText("01").className).toContain("text-[22px]");

    rerender(<Numeral n={1} size="ordinal" />);
    expect(screen.getByText("01").className).toContain("text-[18px]");
  });

  it("NumberedList numbers from 01 and keys on the caller's id", () => {
    render(
      <NumberedList
        items={[
          { id: "a", title: "Late note" },
          { id: "b", title: "Documents", tone: "you" },
        ]}
      />,
    );
    expect(screen.getByText("01")).toBeTruthy();
    expect(screen.getByText("02")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("owned renders the copper inset rule; not-owned renders neither the rule nor its padding", () => {
    const { container: ownedContainer } = render(
      <NumberedList owned items={[{ id: "a", title: "Late note" }]} />,
    );
    const ownedOl = ownedContainer.querySelector("ol")!;
    expect(ownedOl.className).toContain("border-l-4");
    expect(ownedOl.className).toContain("border-[var(--bz-copper)]");
    expect(ownedOl.className).toContain("pl-[11px]");

    const { container: plainContainer } = render(
      <NumberedList items={[{ id: "a", title: "Late note" }]} />,
    );
    const plainOl = plainContainer.querySelector("ol")!;
    expect(plainOl.className).not.toContain("border-l-4");
    expect(plainOl.className).not.toContain("pl-[11px]");
  });

  it('the ordinal is the ownership margin: an item\'s own tone="you" wins even when the list is not owned', () => {
    render(
      <NumberedList items={[{ id: "a", title: "Late note", tone: "you" }]} />,
    );
    expect(screen.getByText("01").className).toContain("--bz-copper-text");
  });

  it("an item in an owned list takes the copper ordinal without its own tone", () => {
    render(<NumberedList owned items={[{ id: "a", title: "Late note" }]} />);
    expect(screen.getByText("01").className).toContain("--bz-copper-text");
  });

  it("an item with no tone in a NOT-owned list defaults to wait (innocence)", () => {
    render(<NumberedList items={[{ id: "a", title: "Late note" }]} />);
    expect(screen.getByText("01").className).toContain("--tx-secondary");
  });

  it("Stamp tone=forest without a timestamp renders nothing", () => {
    const { container } = render(<Stamp tone="forest" />);
    expect(container.firstChild).toBeNull();
  });

  it("Stamp tone=forest with a timestamp renders the full line", () => {
    render(<Stamp tone="forest" on="14 Sep 2026" />);
    expect(screen.getByText(/Reviewed · Bali Zero · 14 Sep 2026/)).toBeTruthy();
  });

  it("Stamp states who reviewed and when (default tone)", () => {
    render(<Stamp on="14 Sep 2026" />);
    expect(screen.getByText(/Reviewed · Bali Zero · 14 Sep 2026/)).toBeTruthy();
  });

  it("Stamp tone=copper without owned renders nothing", () => {
    const { container } = render(<Stamp tone="copper" />);
    expect(container.firstChild).toBeNull();
  });

  it("Stamp tone=copper with owned renders the word", () => {
    render(<Stamp tone="copper" owned />);
    expect(screen.getByText("Needs you")).toBeTruthy();
  });

  it("EmptyState is one sentence and at most one action", () => {
    render(
      <EmptyState action={<button>New client</button>}>
        Nothing is waiting.
      </EmptyState>,
    );
    expect(screen.getByText("Nothing is waiting.")).toBeTruthy();
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("Slip announces politely and its Undo is a real 44px target", () => {
    const onUndo = vi.fn();
    render(<Slip onUndo={onUndo}>Assigned to you.</Slip>);
    const status = screen.getByRole("status");
    expect(status.getAttribute("aria-live")).toBe("polite");
    const undo = screen.getByRole("button", { name: "Undo" });
    expect(undo.className).toContain("min-h-11");
    undo.click();
    expect(onUndo).toHaveBeenCalledOnce();
  });

  it("Notice carries a role only when the caller asks for one", () => {
    const { rerender } = render(<Notice>Blocking</Notice>);
    expect(screen.queryByRole("alert")).toBeNull();
    rerender(<Notice role="alert">Blocking</Notice>);
    expect(screen.getByRole("alert")).toBeTruthy();
  });

  it("Field labels the input and leaves its attributes to the caller", () => {
    render(
      <Field
        id="pin"
        label="PIN"
        inputMode="numeric"
        type="password"
        name="pin"
      />,
    );
    const input = screen.getByLabelText("PIN") as HTMLInputElement;
    expect(input.getAttribute("inputmode")).toBe("numeric");
    expect(input.type).toBe("password");
    expect(input.name).toBe("pin");
  });

  it("Masthead renders the eyebrow, the sub and the actions slot", () => {
    render(
      <Masthead
        eyebrow="Client 0412"
        title="PT Contoh Abadi"
        sub="Everything the desk owes this client."
        actions={<button>New task</button>}
      />,
    );
    expect(screen.getByText("Client 0412")).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "PT Contoh Abadi" }),
    ).toBeTruthy();
    expect(
      screen.getByText("Everything the desk owes this client."),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "New task" })).toBeTruthy();
  });

  it("Masthead still answers to v1's `subtitle` and `right` (the K2a dashboard)", () => {
    // PR #6512 put the kita dashboard on this module between this window's
    // base sha and the branch it shipped from, so the v2 rename was a
    // breaking change for a page this window is forbidden to edit. CI caught
    // it; this pins the compatibility so a later tidy-up cannot drop it
    // silently while (workspace)/dashboard/page.tsx still writes v1.
    render(
      <Masthead
        title="PT Contoh Abadi"
        subtitle="The v1 spelling of sub."
        right={<button>Legacy slot</button>}
      />,
    );
    expect(screen.getByText("The v1 spelling of sub.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Legacy slot" })).toBeTruthy();
  });

  it("Masthead prefers the v2 spelling when both are given (guilt)", () => {
    render(
      <Masthead
        title="PT Contoh Abadi"
        sub="v2 wins"
        subtitle="v1 loses"
        actions={<button>v2 slot</button>}
        right={<button>v1 slot</button>}
      />,
    );
    expect(screen.getByText("v2 wins")).toBeTruthy();
    expect(screen.queryByText("v1 loses")).toBeNull();
    expect(screen.getByRole("button", { name: "v2 slot" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "v1 slot" })).toBeNull();
  });

  it("OrdinalMargin renders its ordinal and a hairline column", () => {
    const { container } = render(<OrdinalMargin n={4} tone="you" />);
    expect(screen.getByText("04").className).toContain("--bz-copper-text");
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull();
  });

  it("LedgerSection renders its ordinal and heading", () => {
    render(
      <LedgerSection n={2} title="Obligations">
        <p>Body</p>
      </LedgerSection>,
    );
    expect(screen.getByText("02")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Obligations" })).toBeTruthy();
    expect(screen.getByText("Body")).toBeTruthy();
  });
});
