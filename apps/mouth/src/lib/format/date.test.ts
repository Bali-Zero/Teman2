import { describe, expect, it } from "vitest";
import { formatDate, formatDateTime, localeTagFor } from "./date";

describe("localeTagFor", () => {
  it("maps it to it-IT", () => {
    expect(localeTagFor("it")).toBe("it-IT");
  });

  it("maps en to en-US", () => {
    expect(localeTagFor("en")).toBe("en-US");
  });

  it("maps id to id-ID", () => {
    expect(localeTagFor("id")).toBe("id-ID");
  });

  it("maps null/undefined to undefined (browser default)", () => {
    expect(localeTagFor(null)).toBeUndefined();
    expect(localeTagFor(undefined)).toBeUndefined();
  });
});

describe("formatDate", () => {
  const sample = "2026-03-25T00:00:00.000Z";

  it("returns empty string for null/undefined", () => {
    expect(formatDate(null, "en")).toBe("");
    expect(formatDate(undefined, "en")).toBe("");
  });

  it("returns empty string for an unparseable value", () => {
    expect(formatDate("not-a-date", "en")).toBe("");
  });

  it("matches Intl.DateTimeFormat for the mapped locale, with no options", () => {
    const date = new Date(sample);
    expect(formatDate(sample, "it")).toBe(
      new Intl.DateTimeFormat("it-IT").format(date),
    );
    expect(formatDate(sample, "id")).toBe(
      new Intl.DateTimeFormat("id-ID").format(date),
    );
  });

  it("passes an explicit options object through unchanged", () => {
    const date = new Date(sample);
    const options: Intl.DateTimeFormatOptions = {
      day: "numeric",
      month: "short",
      year: "numeric",
    };
    expect(formatDate(sample, "en", options)).toBe(
      new Intl.DateTimeFormat("en-US", options).format(date),
    );
  });

  it("accepts a Date instance directly", () => {
    const date = new Date(sample);
    expect(formatDate(date, "en")).toBe(
      new Intl.DateTimeFormat("en-US").format(date),
    );
  });
});

describe("formatDateTime", () => {
  const sample = "2026-03-25T14:30:00.000Z";

  it("returns empty string for null/undefined/unparseable input", () => {
    expect(formatDateTime(null, "en")).toBe("");
    expect(formatDateTime(undefined, "en")).toBe("");
    expect(formatDateTime("not-a-date", "en")).toBe("");
  });

  it("matches Date#toLocaleString for a null language (browser default)", () => {
    const date = new Date(sample);
    expect(formatDateTime(sample, null)).toBe(date.toLocaleString(undefined));
  });

  it("passes an explicit options object through unchanged", () => {
    const date = new Date(sample);
    const options: Intl.DateTimeFormatOptions = {
      hour: "2-digit",
      minute: "2-digit",
    };
    expect(formatDateTime(sample, "id", options)).toBe(
      new Intl.DateTimeFormat("id-ID", options).format(date),
    );
  });
});
