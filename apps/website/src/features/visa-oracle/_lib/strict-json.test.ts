import { describe, expect, it } from "vitest";
import {
  parseStrictJson,
  StrictJsonError,
  VISA_ORACLE_MAX_JSON_DEPTH,
} from "./strict-json";

describe("parseStrictJson", () => {
  it("parses valid nested JSON", () => {
    expect(
      parseStrictJson(
        '{"mode":"ENGINE","decision":{"state":"NEEDS_INPUT"},"items":[1,true,null,"x"]}',
      ),
    ).toEqual({
      mode: "ENGINE",
      decision: { state: "NEEDS_INPUT" },
      items: [1, true, null, "x"],
    });
  });

  it("rejects duplicate keys at every nesting level", () => {
    for (const source of [
      '{"state":"NEEDS_INPUT","state":"SUPPORTED_CANDIDATES"}',
      '{"decision":{"state":"NEEDS_INPUT","state":"SUPPORTED_CANDIDATES"}}',
      '[{"rank":1,"rank":2}]',
    ]) {
      expect(() => parseStrictJson(source)).toThrowError(
        expect.objectContaining<Partial<StrictJsonError>>({
          code: "DUPLICATE_KEY",
        }),
      );
    }
  });

  it("treats escaped and literal spellings as the same key", () => {
    expect(() => parseStrictJson('{"state":1,"st\\u0061te":2}')).toThrowError(
      expect.objectContaining<Partial<StrictJsonError>>({
        code: "DUPLICATE_KEY",
      }),
    );
  });

  it("rejects prototype-pollution keys", () => {
    for (const key of ["__proto__", "constructor", "prototype"]) {
      expect(() => parseStrictJson(`{"${key}":{}}`)).toThrowError(
        expect.objectContaining<Partial<StrictJsonError>>({
          code: "DANGEROUS_KEY",
        }),
      );
    }
  });

  it("rejects malformed and oversized bodies", () => {
    for (const source of ["", "{", '{"a":}', '{"a":1,}', "[1,]", '"bad\\x"']) {
      expect(() => parseStrictJson(source)).toThrowError(
        expect.objectContaining<Partial<StrictJsonError>>({
          code: "INVALID_JSON",
        }),
      );
    }
    expect(() => parseStrictJson('{"a":1}', 3)).toThrowError(
      expect.objectContaining<Partial<StrictJsonError>>({
        code: "RESPONSE_TOO_LARGE",
      }),
    );
  });

  it("accepts depth 64 and rejects depth 65 before stack exhaustion", () => {
    const atLimit =
      "[".repeat(VISA_ORACLE_MAX_JSON_DEPTH) +
      "null" +
      "]".repeat(VISA_ORACLE_MAX_JSON_DEPTH);
    const overLimit = `[${atLimit}]`;

    expect(parseStrictJson(atLimit)).toBeDefined();
    expect(() => parseStrictJson(overLimit)).toThrowError(
      expect.objectContaining<Partial<StrictJsonError>>({ code: "MAX_DEPTH" }),
    );
  });
});
