import { describe, expect, it } from "vitest";

import { IGNORE_ERRORS, isKnownNoise } from "@/lib/sentry-noise";

/**
 * Guilt AND innocence, in that order of importance.
 *
 * The guilt half proves the filter drops what it claims to drop. The innocence
 * half is the one that matters more: this predicate runs on every production
 * error, and a false positive DELETES a real error with no trace anywhere. The
 * 401/403 cases below are not decoration — muting them is exactly how #5096
 * would come back invisibly, and the whole point of the file is that it does
 * not do that.
 */

const err = (
  value: string,
  frames?: Array<{ filename?: string; abs_path?: string }>,
) => ({
  exception: {
    values: [{ value, stacktrace: frames ? { frames } : undefined }],
  },
});

describe("isKnownNoise — guilt", () => {
  it("drops the ResizeObserver loop, in both wordings browsers use", () => {
    expect(isKnownNoise(err("ResizeObserver loop limit exceeded"))).toBe(true);
    expect(
      isKnownNoise(
        err("ResizeObserver loop completed with undelivered notifications."),
      ),
    ).toBe(true);
  });

  it("drops a fetch the user cancelled by navigating away", () => {
    expect(isKnownNoise(err("AbortError: The operation was aborted"))).toBe(
      true,
    );
    expect(isKnownNoise(err("The user aborted a request."))).toBe(true);
  });

  it("drops a promise rejection that carries nothing to act on", () => {
    expect(
      isKnownNoise(
        err("Non-Error promise rejection captured with value: undefined"),
      ),
    ).toBe(true);
  });

  it("drops an error whose stack is ENTIRELY browser-extension code", () => {
    expect(
      isKnownNoise(
        err("Cannot read properties of null", [
          { abs_path: "chrome-extension://abcdef/inject.js" },
          { abs_path: "moz-extension://123/content.js" },
        ]),
      ),
    ).toBe(true);
  });

  it("reads a top-level message, not only an exception value", () => {
    expect(
      isKnownNoise({ message: "ResizeObserver loop limit exceeded" }),
    ).toBe(true);
  });
});

describe("isKnownNoise — innocence, which is the half that costs if it is wrong", () => {
  it("KEEPS 401 and 403 — muting them is how #5096 returns invisibly", () => {
    expect(isKnownNoise(err("Request failed with status code 401"))).toBe(
      false,
    );
    expect(
      isKnownNoise(err("HTTP 403 Forbidden on conversations/history")),
    ).toBe(false);
    expect(isKnownNoise({ message: "Unauthorized" })).toBe(false);
  });

  it("keeps an ordinary application error", () => {
    expect(
      isKnownNoise(err("TypeError: cannot read properties of undefined")),
    ).toBe(false);
    expect(isKnownNoise(err("Failed to fetch pricing for KBLI 55130"))).toBe(
      false,
    );
  });

  it("keeps an error whose stack merely PASSES THROUGH an extension frame", () => {
    // All-foreign, not any-foreign: an extension that wrapped one of our calls
    // is still our stack trace, and still worth seeing.
    expect(
      isKnownNoise(
        err("TypeError: x is not a function", [
          { abs_path: "chrome-extension://abcdef/inject.js" },
          { abs_path: "https://balizero.com/_next/static/chunk.js" },
        ]),
      ),
    ).toBe(false);
  });

  it("keeps an error with no frames at all rather than guessing", () => {
    expect(isKnownNoise(err("Something broke"))).toBe(false);
  });

  it("keeps an error whose ROOT carries an EMPTY frames array", () => {
    // `[].every(...)` is true, so without the length guard an event Sentry
    // shipped with `frames: []` would read as "entirely foreign code" — the
    // wrong answer, said confidently, about a stack we simply do not have.
    expect(
      isKnownNoise({
        exception: {
          values: [
            { value: "Order finalization failed", stacktrace: { frames: [] } },
          ],
        },
      }),
    ).toBe(false);
  });

  it("keeps a message that merely CONTAINS a shorter English word from the list", () => {
    // The over-match guard (superscar family #3). Every needle is long enough
    // that it cannot appear inside a real message; this pins that property.
    expect(
      isKnownNoise(err("The operation was abandoned by the operator")),
    ).toBe(false);
    expect(
      isKnownNoise(err("Load failed while resizing the observer panel")),
    ).toBe(false);
  });
});

describe("isKnownNoise — never throws, because a throw deletes the event", () => {
  it("returns false on shapes it was never designed for", () => {
    // Sentry drops an event silently if beforeSend raises, so a bug here would
    // delete real errors rather than noise — the opposite of the purpose.
    for (const weird of [
      null,
      undefined,
      42,
      "a string",
      [],
      { exception: null },
      { exception: { values: null } },
    ]) {
      expect(isKnownNoise(weird)).toBe(false);
    }
    expect(
      isKnownNoise({
        exception: { values: [{ value: null, stacktrace: { frames: null } }] },
      }),
    ).toBe(false);
  });

  it("KEEPS the event when reading it actually throws", () => {
    // The catch has to fail OPEN. Measured: a catch that returned `true`
    // instead survived every other case in this file, because none of them
    // makes the predicate throw — so the branch that decides the fate of an
    // unreadable event was untested. An object with a throwing getter is the
    // shape that reaches it.
    const hostile = {
      get message(): string {
        throw new Error("this event refuses to be read");
      },
    };
    expect(isKnownNoise(hostile)).toBe(false);
  });
});

describe("the shapes a cross-family reviewer executed against the first version", () => {
  it("KEEPS a linked error whose CAUSE is benign but whose ROOT is actionable", () => {
    // Sentry puts the ROOT last. Reading every value deleted the whole event
    // because one entry matched — the reviewer ran this exact input and the old
    // predicate returned true.
    expect(
      isKnownNoise({
        exception: {
          values: [
            {
              type: "AbortError",
              value: "AbortError: The operation was aborted",
            },
            {
              type: "CheckoutCommitError",
              value: "Failed to persist completed payment",
              stacktrace: {
                frames: [
                  { filename: "https://balizero.com/_next/checkout.js" },
                ],
              },
            },
          ],
        },
      }),
    ).toBe(false);
  });

  it("KEEPS a frameless ROOT whose CAUSE happens to be extension code", () => {
    // Flattening frames across values let the frameless root vanish and a
    // foreign-framed cause decide the verdict. `[].every()` is vacuously true,
    // which is the wrong answer said confidently.
    expect(
      isKnownNoise({
        exception: {
          values: [
            {
              type: "ExtensionError",
              value: "extension failed",
              stacktrace: {
                frames: [{ filename: "chrome-extension://abc/inject.js" }],
              },
            },
            {
              type: "OrderFinalizationError",
              value: "Order finalization failed",
            },
          ],
        },
      }),
    ).toBe(false);
  });

  it("DROPS ResizeObserver noise that arrives via logentry", () => {
    // Parameterised captureMessage lands in event.logentry, which neither the
    // old predicate nor the SDK's own ignoreErrors matcher reads — so this
    // noise reached Sentry through both surfaces.
    expect(
      isKnownNoise({
        logentry: { message: "ResizeObserver loop limit exceeded" },
      }),
    ).toBe(true);
    expect(
      isKnownNoise({
        logentry: { formatted: "ResizeObserver loop limit exceeded" },
      }),
    ).toBe(true);
  });
});

describe("browser-only vs universal noise — the same words, opposite meanings", () => {
  const abort = err("AbortError: The operation was aborted");

  it("drops a cancelled navigation in the BROWSER", () => {
    expect(isKnownNoise(abort)).toBe(true);
    expect(isKnownNoise(abort, { browser: true })).toBe(true);
  });

  it("KEEPS the same abort on the SERVER, where it is a deadline killing real I/O", () => {
    // There is no navigation in the server runtime. A nightly export aborted by
    // an application deadline is an actionable timeout, and the shared list
    // deleted it (cross-family gate).
    expect(isKnownNoise(abort, { browser: false })).toBe(false);
  });

  it("keeps a value-less promise rejection filter in BOTH runtimes", () => {
    const universal = err(
      "Non-Error promise rejection captured with value: undefined",
    );
    expect(isKnownNoise(universal, { browser: true })).toBe(true);
    expect(isKnownNoise(universal, { browser: false })).toBe(true);
  });

  it("KEEPS an application message that merely contains the English phrase", () => {
    // The needles are anchored to the exact DOMException forms browsers emit,
    // not to the phrase, because this sentence is a real error.
    expect(
      isKnownNoise(
        err("The operation was aborted while committing invoice 42"),
      ),
    ).toBe(false);
  });
});

describe("IGNORE_ERRORS is a DIFFERENT surface, and the earlier parity claim was false", () => {
  it("every ignore-list needle is also caught as a ROOT message", () => {
    // Not parity: the SDK's matcher reads the top-level message and the root
    // exception, while this module also reads logentry and inspects frames.
    // Neither is a superset. What must hold is the overlap they share.
    expect(IGNORE_ERRORS.length).toBeGreaterThan(0);
    for (const needle of IGNORE_ERRORS) {
      expect(isKnownNoise(err(`prefix ${needle} suffix`))).toBe(true);
    }
  });
});
