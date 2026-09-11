import { describe, expect, it } from "vitest";
import {
  countWords,
  emptyField,
  flagsFor,
  type ExerciseTelemetry,
} from "./telemetry";

function ex(overrides: Partial<ExerciseTelemetry> = {}): ExerciseTelemetry {
  return {
    elapsedMs: 600_000,
    awayMs: 0,
    awayCount: 0,
    fields: {},
    autoLocked: false,
    restored: false,
    composedChars: 0,
    ...overrides,
  };
}

function typed(chars: number, keys: number, backs = 0) {
  return { ...emptyField(), chars, keystrokes: keys, backspaces: backs };
}

const codes = (t: ExerciseTelemetry) => flagsFor(t).map((f) => f.code);

describe("countWords", () => {
  it("ignores surrounding and repeated whitespace", () => {
    expect(countWords("  two   words \n")).toBe(2);
    expect(countWords("   ")).toBe(0);
  });
});

describe("KEYSTROKE_DEFICIT", () => {
  it("fires when text is longer than the keys that produced it", () => {
    // 900 characters submitted, 40 keys pressed: the text was not typed here.
    expect(codes(ex({ fields: { a: typed(900, 40, 30) } }))).toContain(
      "KEYSTROKE_DEFICIT",
    );
  });

  it("stays quiet for ordinary typing with corrections", () => {
    // Corrections mean MORE keys than final characters, never fewer.
    expect(codes(ex({ fields: { a: typed(900, 1050, 150) } }))).not.toContain(
      "KEYSTROKE_DEFICIT",
    );
  });

  it("stays quiet on a short answer, where the ratio is noise", () => {
    expect(codes(ex({ fields: { a: typed(60, 10) } }))).not.toContain(
      "KEYSTROKE_DEFICIT",
    );
  });
});

describe("EXTERNAL_INSERT", () => {
  it("fires on a large insertion even when no paste event was seen", () => {
    const f = { ...typed(900, 950, 100), jumpInsertions: 1, jumpChars: 400 };
    expect(codes(ex({ fields: { a: f } }))).toContain("EXTERNAL_INSERT");
  });
});

describe("TAB_AWAY", () => {
  it("is silent for a glance away", () => {
    expect(codes(ex({ awayMs: 4_000, awayCount: 1 }))).not.toContain(
      "TAB_AWAY",
    );
  });

  it("fires on a long absence and escalates past a minute", () => {
    const flags = flagsFor(ex({ awayMs: 90_000, awayCount: 2 }));
    const away = flags.find((f) => f.code === "TAB_AWAY");
    expect(away?.severity).toBe("high");
  });

  it("fires on repeated absences that add up", () => {
    expect(codes(ex({ awayMs: 15_000, awayCount: 3 }))).toContain("TAB_AWAY");
  });
});

describe("a clean session raises nothing", () => {
  it("returns no flags for plausible human writing", () => {
    // 1200 characters over 10 minutes = ~24 wpm, revised throughout.
    expect(codes(ex({ fields: { a: typed(1200, 1400, 200) } }))).toEqual([]);
  });
});

describe("SUSTAINED_SPEED", () => {
  it("measures against active time, not wall-clock", () => {
    // 1200 chars in 60s of active time (600s elapsed, 540s away) = 240 wpm.
    const t = ex({
      elapsedMs: 600_000,
      awayMs: 540_000,
      awayCount: 1,
      fields: { a: typed(1200, 1400, 200) },
    });
    expect(codes(t)).toContain("SUSTAINED_SPEED");
  });
});

describe("the honest candidate is not accused", () => {
  it("suppresses the keystroke family after a restored session", () => {
    // A reload keeps the text and loses the keystrokes. Comparing one against
    // the other afterwards accuses her of exactly what the reload cost her.
    const f = { ...typed(900, 1, 0), jumpInsertions: 1, jumpChars: 900 };
    const got = codes(ex({ restored: true, fields: { a: f } }));
    expect(got).toContain("RESTORED_SESSION");
    expect(got).not.toContain("KEYSTROKE_DEFICIT");
    expect(got).not.toContain("EXTERNAL_INSERT");
  });

  it("counts IME and predictive-keyboard compositions as typing", () => {
    // 900 characters, 120 keydowns the browser reported, the rest committed
    // through composition events: an honest candidate on such a keyboard.
    const t = ex({ composedChars: 780, fields: { a: typed(900, 120, 20) } });
    expect(codes(t)).not.toContain("KEYSTROKE_DEFICIT");
  });

  it("still catches transplanted text when no composition explains it", () => {
    const t = ex({ composedChars: 0, fields: { a: typed(900, 120, 20) } });
    expect(codes(t)).toContain("KEYSTROKE_DEFICIT");
  });
});
