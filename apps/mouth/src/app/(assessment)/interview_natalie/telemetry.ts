/**
 * Assessment integrity telemetry.
 *
 * These are SIGNALS, never a verdict. Every flag says what was observed, not
 * what it means: "text appeared that was not typed" is a fact; "she used AI"
 * is an inference the panel makes with the answer in front of it. A page that
 * prints a verdict would be trusted as one, and this instrument cannot earn
 * that trust — a candidate typing with a dictation tool, or one who drafted on
 * paper first and transcribed, trips the same wires as a candidate pasting
 * from a chatbot.
 *
 * The load-bearing signal is KEYSTROKE_DEFICIT: it compares characters that
 * ended up in the field against printable keys actually pressed. It survives
 * a blocked paste handler, drag-and-drop, middle-click, autofill, speech
 * input, and any devtools insertion, because it measures the RESULT rather
 * than the gesture. Every other flag is corroboration.
 */

export interface FieldTelemetry {
  /** Printable keydowns observed in this field. */
  keystrokes: number;
  /** Backspace / Delete presses — human prose revises, transplanted text does not. */
  backspaces: number;
  /** Paste gestures intercepted (the paste itself is blocked). */
  pasteAttempts: number;
  /** Characters carried by those blocked pastes. */
  pastedChars: number;
  /** Copy / cut out of the page — the question text going somewhere else. */
  copyEvents: number;
  cutEvents: number;
  /** Right-click / context menu opens. */
  contextMenus: number;
  /** Input events that added more characters at once than a keypress can. */
  jumpInsertions: number;
  jumpChars: number;
  /** ms from field first focused to first printable key. */
  timeToFirstKeyMs: number | null;
  /** Longest gap between two consecutive edits, ms. */
  maxIdleMs: number;
  /** Final content size. */
  chars: number;
  words: number;
}

export interface ExerciseTelemetry {
  /** Wall-clock ms from the moment the exercise window opened. */
  elapsedMs: number;
  /** ms the tab spent hidden or unfocused while this exercise was open. */
  awayMs: number;
  /** Number of times focus left the tab. */
  awayCount: number;
  /** Per-field detail, keyed by field id. */
  fields: Record<string, FieldTelemetry>;
  /** True when the countdown reached zero and the window locked itself. */
  autoLocked: boolean;
  /**
   * True when this exercise's text was restored from a previous browser
   * session. The text survives a reload; the keystrokes that produced it do
   * not. Counting one against the other after a restore accuses an honest
   * candidate of exactly the thing the reload cost her — so the keystroke
   * family is suppressed and the panel is told why.
   */
  restored: boolean;
  /** Characters entered through an IME / predictive keyboard composition. */
  composedChars: number;
}

export function emptyField(): FieldTelemetry {
  return {
    keystrokes: 0,
    backspaces: 0,
    pasteAttempts: 0,
    pastedChars: 0,
    copyEvents: 0,
    cutEvents: 0,
    contextMenus: 0,
    jumpInsertions: 0,
    jumpChars: 0,
    timeToFirstKeyMs: null,
    maxIdleMs: 0,
    chars: 0,
    words: 0,
  };
}

export function countWords(text: string): number {
  const t = text.trim();
  return t ? t.split(/\s+/).length : 0;
}

/** A paste gesture cannot deliver fewer characters than this and still matter. */
export const JUMP_THRESHOLD = 25;

export interface Flag {
  code: string;
  detail: string;
  /** high = the text demonstrably did not come from this keyboard. */
  severity: "high" | "medium" | "low";
}

/**
 * Aggregate one exercise's fields into flags.
 *
 * Thresholds are deliberately generous. A false positive costs a candidate a
 * question she has to answer in the room; the panel should be arguing about
 * two flags, not thirty.
 */
export function flagsFor(ex: ExerciseTelemetry): Flag[] {
  const flags: Flag[] = [];
  const fields = Object.values(ex.fields);

  const chars = fields.reduce((n, f) => n + f.chars, 0);
  const keys = fields.reduce((n, f) => n + f.keystrokes, 0);
  const backs = fields.reduce((n, f) => n + f.backspaces, 0);
  const pastes = fields.reduce((n, f) => n + f.pasteAttempts, 0);
  const pastedChars = fields.reduce((n, f) => n + f.pastedChars, 0);
  const jumps = fields.reduce((n, f) => n + f.jumpInsertions, 0);
  const jumpChars = fields.reduce((n, f) => n + f.jumpChars, 0);
  const copies = fields.reduce((n, f) => n + f.copyEvents + f.cutEvents, 0);

  // The primary signal. Typing produces roughly one printable key per
  // character; below 70% the surplus text arrived some other way.
  //
  // `composedChars` is added to the key count, not subtracted from the
  // characters: an IME, an Indonesian predictive keyboard or an autocorrect
  // substitution commits several characters against one or two keydowns, and
  // without this an honest candidate on a phone keyboard fails every time.
  if (ex.restored) {
    flags.push({
      code: "RESTORED_SESSION",
      detail:
        "This exercise was resumed after a reload. Keystroke accounting is not meaningful for it and was suppressed — read the answer on its merits.",
      severity: "low",
    });
  } else if (chars >= 120 && keys + ex.composedChars < chars * 0.7) {
    flags.push({
      code: "KEYSTROKE_DEFICIT",
      detail: `${chars} characters submitted, ${keys + ex.composedChars} keys/compositions observed (${Math.round(((keys + ex.composedChars) / Math.max(chars, 1)) * 100)}%).`,
      severity: "high",
    });
  }

  if (jumps > 0 && !ex.restored) {
    flags.push({
      code: "EXTERNAL_INSERT",
      detail: `${jumps} insertion(s) larger than ${JUMP_THRESHOLD} characters at once, ${jumpChars} characters in total — drag-and-drop, autofill, dictation or a paste route the handler did not see.`,
      severity: "high",
    });
  }

  if (pastes > 0) {
    flags.push({
      code: "PASTE_BLOCKED",
      detail: `${pastes} paste attempt(s) blocked, carrying ${pastedChars} characters.`,
      severity: "medium",
    });
  }

  if (copies > 0) {
    flags.push({
      code: "COPY_OUT",
      detail: `${copies} copy event(s) from an answer field. Where the text went is not observable from here — it may have been copied within the answer.`,
      severity: "medium",
    });
  }

  if (ex.awayMs > 20_000 || (ex.awayCount >= 3 && ex.awayMs > 8_000)) {
    flags.push({
      code: "TAB_AWAY",
      detail: `Left the tab ${ex.awayCount} time(s), ${Math.round(ex.awayMs / 1000)}s away in total.`,
      severity: ex.awayMs > 60_000 ? "high" : "medium",
    });
  }

  // Unrevised prose is the shape of transcription, not composition.
  if (chars >= 400 && keys > 0 && backs / keys < 0.015) {
    flags.push({
      code: "LOW_REVISION",
      detail: `${backs} corrections across ${keys} keys (${((backs / keys) * 100).toFixed(1)}%) — text written without revising.`,
      severity: "low",
    });
  }

  const typingMs = Math.max(ex.elapsedMs - ex.awayMs, 1);
  const wpm = chars / 5 / (typingMs / 60_000);
  if (chars >= 200 && wpm > 90) {
    flags.push({
      code: "SUSTAINED_SPEED",
      detail: `${Math.round(wpm)} words per minute sustained over ${Math.round(typingMs / 1000)}s of active time.`,
      severity: "low",
    });
  }

  return flags;
}

/** Compact one-line summary for the subject line of the panel's email. */
export function flagSummary(flags: Flag[]): string {
  if (flags.length === 0) return "clean";
  return flags.map((f) => f.code).join(",");
}
