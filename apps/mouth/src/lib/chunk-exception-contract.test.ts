// The chunk-exception contract, tested by EXECUTING it.
//
// Everything that proved this rule worked used to be a manual probe recorded in a
// pack: real evidence for a reader, but no protection for the next commit. The
// suite's only permanent check was that a particular LINE still appeared in the
// guard's source, so a rewrite that kept the line and broke the logic stayed green.
//
// The decision now lives in a pure module, so these are the probes as tests.
import { describe, it, expect } from "vitest";
import {
  chunkExceptionViolations,
  CLOSER_SHAPE,
} from "../../scripts/lib/chunk-exception-contract.mjs";

describe("chunk exception contract", () => {
  it("allows the state the repo is actually in: no exceptions at all", () => {
    expect(chunkExceptionViolations({ prefixes: [], closers: {} })).toEqual([]);
  });

  it("allows an exception that is properly declared", () => {
    expect(
      chunkExceptionViolations({
        prefixes: ["app/(workspace)/reports/"],
        closers: { "app/(workspace)/reports/": "#6391" },
      }),
    ).toEqual([]);
  });

  // ---- the four probes that were manual until now -------------------------

  it("rejects a blank prefix, which would silently skip every chunk", () => {
    const v = chunkExceptionViolations({
      prefixes: [""],
      closers: { "": "C4d" },
    });
    expect(v).toHaveLength(1);
    expect(v[0]).toMatch(/empty or blank/);
  });

  it("rejects an entry with no OWN closer, including inherited keys", () => {
    // `closers["constructor"]` is truthy via Object.prototype — a truthiness test
    // would wave this through.
    const v = chunkExceptionViolations({
      prefixes: ["constructor"],
      closers: { constructorName: "C4d" },
    });
    expect(v.some((m) => /no OWN entry/.test(m))).toBe(true);
  });

  it("rejects a closer that merely MENTIONS a reference", () => {
    for (const closer of [
      "TODO maybe C4b someday",
      "see C4b for history",
      "fix it in C9 probably",
      "later",
      "TBD",
      "",
    ]) {
      const v = chunkExceptionViolations({
        prefixes: ["app/(workspace)/reports/"],
        closers: { "app/(workspace)/reports/": closer },
      });
      expect(
        v,
        `${JSON.stringify(closer)} should not satisfy the contract`,
      ).toHaveLength(1);
      expect(v[0]).toMatch(/not a PR reference/);
    }
  });

  it("rejects a stale closer whose prefix has been removed", () => {
    const v = chunkExceptionViolations({
      prefixes: [],
      closers: { "app/(workspace)/reports/": "C4b" },
    });
    expect(v).toHaveLength(1);
    expect(v[0]).toMatch(/stale closing-PR claim/);
  });

  // ---- the shape itself ---------------------------------------------------

  it("accepts a bare PR number or lane id, and nothing looser", () => {
    for (const ok of ["#6391", "#1", "C4d", "C4b", "C10"]) {
      expect(CLOSER_SHAPE.test(ok), `${ok} should be accepted`).toBe(true);
    }
    for (const no of ["c4b", "C4b and more", "PR 6391", "#", "C"]) {
      expect(CLOSER_SHAPE.test(no), `${no} should be rejected`).toBe(false);
    }
  });

  it("trims the closer, so trailing whitespace is a typo and not a failure", () => {
    expect(
      chunkExceptionViolations({
        prefixes: ["app/(workspace)/reports/"],
        closers: { "app/(workspace)/reports/": "  #6391 " },
      }),
    ).toEqual([]);
  });

  it("refuses malformed declarations rather than trusting them", () => {
    expect(
      chunkExceptionViolations({ prefixes: "nope", closers: {} }),
    ).toHaveLength(1);
    expect(
      chunkExceptionViolations({ prefixes: [], closers: null }),
    ).toHaveLength(1);
  });
});
