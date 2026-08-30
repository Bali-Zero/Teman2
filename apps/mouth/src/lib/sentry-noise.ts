/**
 * The one place that decides what is NOT worth a Sentry event.
 *
 * WHY THIS EXISTS, measured on `bali-zero-7p` over 7 days (2026-08-28): the
 * `error` category took 1,952 accepted against 753 rate_limited — **28% of
 * production errors dropped for quota**. A dropped event is indistinguishable
 * from an event that never happened, so the 28% is not a billing problem, it
 * is a blindness problem: the errors that get discarded are chosen by arrival
 * order, not by importance.
 *
 * The precedent this file answers to is #5096, where `/chat` fired two
 * authenticated calls at every anonymous visitor, each 401 reached
 * `logger.warn`, and `logger.warn` forwards to Sentry unconditionally in
 * production. One public page was posting one Sentry event per visitor and
 * Sentry answered 429 — real errors lost behind noise from an entirely
 * foreseeable condition.
 *
 * ────────────────────────────────────────────────────────────────────────
 * WHAT THIS FILE DELIBERATELY DOES NOT DROP, and it is the important half.
 *
 * It does NOT drop 401/403. That is exactly the #5096 signature, and the cure
 * for #5096 was the CAUSE (don't call an authenticated endpoint while logged
 * out), not the symptom. Muting the symptom here would mean the next
 * recurrence arrives silently — the same bug, one release later, invisible.
 * The rule this file follows: drop only what could not be actioned even if
 * somebody read it.
 *
 * Everything below is either (a) not our code at all, or (b) a browser
 * behaviour with no stack that anyone can act on. Each entry carries why.
 * ────────────────────────────────────────────────────────────────────────
 */

/** Frames from code we did not ship and cannot fix. */
const FOREIGN_FRAME_SCHEMES = [
  "chrome-extension://",
  "moz-extension://",
  "safari-extension://",
  "safari-web-extension://",
  "ms-browser-extension://",
];

/**
 * Message substrings that identify an event as un-actionable.
 *
 * Substring matching is the over-match risk here (superscar #3), so every
 * entry is long enough to be unambiguous: none of these can appear inside a
 * message about something real. `ResizeObserver loop` cannot show up in an
 * application error; `Load failed` alone could, which is why the shorter,
 * tempting forms are absent.
 */
export const UNIVERSAL_NOISE: readonly string[] = [
  // A promise rejected with a value that carries no diagnostic content: the
  // event contains literally nothing to act on, in any runtime.
  "Non-Error promise rejection captured with value: undefined",
  "Non-Error promise rejection captured with value: null",
];

/**
 * Browser-only, and the split is load-bearing rather than tidy.
 *
 * "The operation was aborted" in a BROWSER is a fetch the user cancelled by
 * navigating away. The same words on the SERVER are an application deadline
 * killing real I/O — an actionable timeout — and a cross-family reviewer
 * produced exactly that event: an `AbortError` from a nightly export, dropped
 * by a rule that assumed every abort came from a navigation there is no such
 * thing as in the server runtime.
 *
 * The strings are also anchored to the exact forms browsers emit rather than
 * to the English phrase, because substring matching is the over-match risk
 * here (superscar #3): "The operation was aborted while committing invoice 42"
 * is a real error and must survive.
 */
export const BROWSER_ONLY_NOISE: readonly string[] = [
  // Fired by the browser when a resize handler causes another resize. The
  // W3C spec acknowledges it as benign; no stack, nothing to fix.
  "ResizeObserver loop completed with undelivered notifications",
  "ResizeObserver loop limit exceeded",
  // DOMException forms, verbatim per engine — never the bare phrase.
  "AbortError: The operation was aborted",
  "AbortError: signal is aborted without reason",
  "The user aborted a request.",
];

export const KNOWN_NOISE_SUBSTRINGS: readonly string[] = [
  ...UNIVERSAL_NOISE,
  ...BROWSER_ONLY_NOISE,
];

/**
 * For `Sentry.init({ ignoreErrors })`.
 *
 * NOT the same surface as `isKnownNoise`, and the earlier comment claiming
 * they were "in step" was wrong: the SDK's own matcher looks at the top-level
 * message and the ROOT exception, while this module additionally reads
 * `logentry` and inspects frames. They overlap deliberately — `ignoreErrors`
 * is cheaper (the SDK drops before building the event) and `beforeSend` sees
 * more — but neither is a superset of the other, and a test asserting parity
 * would be asserting something untrue.
 */
export const IGNORE_ERRORS: readonly string[] = KNOWN_NOISE_SUBSTRINGS;

type MinimalFrame = { filename?: string | null; abs_path?: string | null };
type MinimalValue = {
  value?: string | null;
  stacktrace?: { frames?: MinimalFrame[] | null } | null;
};
type MinimalEvent = {
  message?: string | null;
  // Sentry's own builder routes parameterised `captureMessage` here, and the
  // SDK's `ignoreErrors` matcher does NOT read it — so a templated
  // ResizeObserver message reached Sentry through both surfaces.
  logentry?: { message?: string | null; formatted?: string | null } | null;
  exception?: { values?: MinimalValue[] | null } | null;
};

/**
 * The ROOT exception, which Sentry places LAST in `values`.
 *
 * Reading every value was a false-positive machine: a linked error whose CAUSE
 * is a benign abort but whose ROOT is `CheckoutCommitError: Failed to persist
 * completed payment` had the whole event deleted because one entry matched.
 * A cross-family reviewer executed that exact input against the old predicate
 * and it returned true. The event's identity is its root; judge that.
 */
function rootValue(event: MinimalEvent): MinimalValue | null {
  const values = event.exception?.values;
  if (!Array.isArray(values) || values.length === 0) return null;
  return values[values.length - 1] ?? null;
}

function messagesOf(event: MinimalEvent): string[] {
  const out: string[] = [];
  if (typeof event.message === "string") out.push(event.message);
  const le = event.logentry;
  if (le && typeof le.formatted === "string") out.push(le.formatted);
  if (le && typeof le.message === "string") out.push(le.message);
  const root = rootValue(event);
  if (root && typeof root.value === "string") out.push(root.value);
  return out;
}

/**
 * True when the event is one of the declared un-actionable classes.
 *
 * Never throws: Sentry drops an event silently if `beforeSend` raises, so a
 * bug in this predicate would delete real errors rather than noise — the
 * opposite of what it is for. Any surprise returns false, which keeps the
 * event.
 */
export function isKnownNoise(
  event: unknown,
  opts: { browser?: boolean } = {},
): boolean {
  try {
    const e = (event ?? {}) as MinimalEvent;
    const browser = opts.browser !== false;
    const needles = browser ? KNOWN_NOISE_SUBSTRINGS : UNIVERSAL_NOISE;

    for (const msg of messagesOf(e)) {
      if (needles.some((needle) => msg.includes(needle))) {
        return true;
      }
    }

    // An event whose ROOT exception's stack is ENTIRELY foreign code is not
    // ours to fix. Three conditions, each earned:
    //  - the ROOT, not every value: flattening frames across values let a
    //    frameless root vanish while a foreign-framed CAUSE decided the verdict,
    //    and the real error was deleted (cross-family gate, executed input).
    //  - `length > 0`: "no stack" is unknown, not foreign. `[].every(...)` is
    //    vacuously true, which is the wrong answer said confidently.
    //  - `every`, not `some`: an extension frame inside our own stack usually
    //    means the extension wrapped one of our calls, and that IS worth seeing.
    const root = rootValue(e);
    const frames = root?.stacktrace?.frames;
    if (Array.isArray(frames) && frames.length > 0) {
      const isForeign = (f: MinimalFrame) => {
        const path = f?.abs_path ?? f?.filename ?? "";
        return FOREIGN_FRAME_SCHEMES.some((scheme) => path.startsWith(scheme));
      };
      if (frames.every(isForeign)) return true;
    }

    return false;
  } catch {
    return false;
  }
}
