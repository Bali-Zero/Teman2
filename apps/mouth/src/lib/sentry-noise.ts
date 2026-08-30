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
export const KNOWN_NOISE_SUBSTRINGS: readonly string[] = [
  // Fired by the browser when a resize handler causes another resize. The
  // W3C spec acknowledges it as benign; no stack, nothing to fix.
  "ResizeObserver loop completed with undelivered notifications",
  "ResizeObserver loop limit exceeded",
  // A fetch the user cancelled by navigating away. Not a failure of ours.
  "The operation was aborted",
  "The user aborted a request",
  "AbortError: signal is aborted without reason",
  // A promise rejected with a value that carries no diagnostic content: the
  // event contains literally nothing to act on.
  "Non-Error promise rejection captured with value: undefined",
  "Non-Error promise rejection captured with value: null",
];

/**
 * Passed to `Sentry.init({ ignoreErrors })` as well as checked in
 * `beforeSend`. Both, on purpose: `ignoreErrors` is cheaper (the SDK drops
 * before building the event) but only sees the message, while `beforeSend`
 * can see the stack frames. Neither alone covers both shapes.
 */
export const IGNORE_ERRORS: readonly string[] = KNOWN_NOISE_SUBSTRINGS;

type MinimalFrame = { filename?: string | null; abs_path?: string | null };
type MinimalEvent = {
  message?: string | null;
  exception?: {
    values?: Array<{
      value?: string | null;
      stacktrace?: { frames?: MinimalFrame[] | null } | null;
    }> | null;
  } | null;
};

function messagesOf(event: MinimalEvent): string[] {
  const out: string[] = [];
  if (typeof event.message === "string") out.push(event.message);
  for (const v of event.exception?.values ?? []) {
    if (typeof v?.value === "string") out.push(v.value);
  }
  return out;
}

function framesOf(event: MinimalEvent): MinimalFrame[] {
  const out: MinimalFrame[] = [];
  for (const v of event.exception?.values ?? []) {
    for (const f of v?.stacktrace?.frames ?? []) out.push(f);
  }
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
export function isKnownNoise(event: unknown): boolean {
  try {
    const e = (event ?? {}) as MinimalEvent;

    for (const msg of messagesOf(e)) {
      if (KNOWN_NOISE_SUBSTRINGS.some((needle) => msg.includes(needle))) {
        return true;
      }
    }

    // An event whose stack is ENTIRELY foreign code is not ours to fix. All,
    // not any: an extension frame appearing inside our own stack usually means
    // the extension wrapped one of our calls, and that IS worth seeing.
    const frames = framesOf(e);
    if (frames.length > 0) {
      const isForeign = (f: MinimalFrame) => {
        const path = f.abs_path ?? f.filename ?? "";
        return FOREIGN_FRAME_SCHEMES.some((scheme) => path.startsWith(scheme));
      };
      if (frames.every(isForeign)) return true;
    }

    return false;
  } catch {
    return false;
  }
}
