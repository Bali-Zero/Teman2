import { describe, it, expect } from "vitest";
import { toIcalString, type IcalEvent } from "./ical";

describe("toIcalString", () => {
  it("emits a valid VCALENDAR with VEVENT entries", () => {
    const events: IcalEvent[] = [
      {
        uid: "deadline-pph-2026-05-15",
        summary: "PPh 25 — Maggio",
        start: new Date("2026-05-15T00:00:00Z"),
        end: new Date("2026-05-15T23:59:00Z"),
        description: "Pagamento PPh 25 mensile",
      },
    ];
    const out = toIcalString(events, { prodId: "BaliZero//TaxCalendar" });
    expect(out).toContain("BEGIN:VCALENDAR");
    expect(out).toContain("PRODID:BaliZero//TaxCalendar");
    expect(out).toContain("BEGIN:VEVENT");
    expect(out).toContain("UID:deadline-pph-2026-05-15");
    expect(out).toContain("SUMMARY:PPh 25 — Maggio");
    expect(out).toContain("DTSTART:20260515T000000Z");
    expect(out).toContain("END:VCALENDAR");
  });
});
