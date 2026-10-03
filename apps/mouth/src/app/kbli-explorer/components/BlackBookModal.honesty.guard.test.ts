import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The /kbli-explorer "Black Book" funnel collected an email and a WhatsApp
 * number, waited on a timer, sent nothing, and then told the visitor that a
 * dossier had been dispatched to their inbox and that the team was reviewing
 * their company codes. Measured at 9282d24513. No dossier exists.
 *
 * Declared limits: this reads source text. It cannot tell whether a future
 * dossier is real; if one is built, this guard is the place to say so.
 */
const read = (rel: string) => readFileSync(join(__dirname, rel), "utf8");
const MODAL = read("BlackBookModal.tsx");
const ALERT = read("LegacyAlert.tsx");
const PAGE = read("../page.tsx");

describe("/kbli-explorer transition entry says only what is true", () => {
  it("positive control: the modal still hands off to the kbli WhatsApp line", () => {
    expect(MODAL).toContain('buildWhatsAppLink("kbli")');
    expect(PAGE).toContain("<BlackBookModal");
  });

  it("the modal no longer fakes a submission", () => {
    expect(MODAL).not.toMatch(/<form\b/);
    expect(MODAL).not.toContain("setTimeout");
    expect(MODAL).not.toContain('type="email"');
  });

  it("the modal makes none of the removed claims", () => {
    for (const claim of [
      "sent to your inbox",
      "dispatched",
      "reviewing the status of your company codes",
      "We have identified",
      "compliance audit",
    ]) {
      expect(MODAL).not.toContain(claim);
    }
  });

  it("no entry point promises a download that does not exist", () => {
    for (const src of [PAGE, ALERT]) {
      expect(src).not.toContain("Download the dossier");
      expect(src).not.toContain("UNLOCK 2025 BLACK BOOK");
      expect(src).not.toContain("Get the 2025 Black Book");
    }
  });
});
