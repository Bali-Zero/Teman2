import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import {
  DeskStrip,
  EmptyState,
  Field,
  HairlineBody,
  HairlineGrid,
  HairlineHead,
  HairlineRow,
  Notice,
  NumberedList,
  Numeral,
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
 * sanctioned exception is `COPPER_RULE`, the 56x3 masthead graphic, which
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
    // The exemption is the NAME, so a copy of the class string is still guilty.
    expect(
      findCopperFill('const FAKE = "h-[3px] w-14 bg-[var(--bz-copper)]";'),
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
    expect(btn.className).toContain("bg-[var(--state-info)]");
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
});

describe("DeskStrip", () => {
  it("names its filter group so the slate fill is not the only signal", () => {
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
});

describe("the remaining primitives render their contract", () => {
  it("Numeral pads to two digits and takes the ownership tone", () => {
    render(<Numeral n={3} tone="you" />);
    expect(screen.getByText("03").className).toContain("--bz-copper-text");
    expect(pad2(9)).toBe("09");
    expect(pad2(12)).toBe("12");
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

  it("Stamp states who reviewed and when", () => {
    render(<Stamp on="14 Sep 2026" />);
    expect(screen.getByText(/Reviewed · Bali Zero · 14 Sep 2026/)).toBeTruthy();
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
});
