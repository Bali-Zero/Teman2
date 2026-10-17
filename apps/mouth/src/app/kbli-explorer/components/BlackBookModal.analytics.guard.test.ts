import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The only WhatsApp hand-off on /kbli-explorer (the KBLI 2025 transition
 * modal) sent no event when clicked, so the route's one lead CTA could not be
 * counted. It fires the repo's WhatsApp convention for the KBLI funnel:
 * `kbli_whatsapp_cta` with a `trigger` payload, like HeaderWhatsAppCTA
 * ("header") and MobileNav ("drawer").
 *
 * Review 12 Oct (REWORK-DESIGN): the first version fired `kbli_consult_click`,
 * which is the documented Pricing CTA event, so explorer WhatsApp leads were
 * mixed into the pricing metric. The GUILT test keeps that out.
 *
 * Declared limits: this reads source text. It proves the handler is wired on
 * the WhatsApp link, not that the event is stored (/kbli-explorer mounts no
 * SessionInit, so the funnel-store leg only updates an existing session).
 */
const MODAL = readFileSync(join(__dirname, "BlackBookModal.tsx"), "utf8");

describe("/kbli-explorer WhatsApp hand-off is counted as a WhatsApp CTA", () => {
  it("positive control: the modal still links to the kbli WhatsApp line", () => {
    expect(MODAL).toContain('href={buildWhatsAppLink("kbli")}');
  });

  it("imports the funnel tracker and the session id helper", () => {
    expect(MODAL).toContain(
      'import { trackFunnelEvent } from "@balizero/core/analytics";',
    );
    expect(MODAL).toContain(
      'import { getOrCreateSessionId } from "@balizero/core/auth";',
    );
  });

  it("fires kbli_whatsapp_cta with trigger explorer_modal on the WhatsApp anchor", () => {
    const href = MODAL.indexOf('href={buildWhatsAppLink("kbli")}');
    const anchorEnd = MODAL.indexOf("target=", href);
    const event = MODAL.indexOf('trackFunnelEvent("kbli_whatsapp_cta"', href);
    const trigger = MODAL.indexOf('trigger: "explorer_modal"', href);
    expect(event).toBeGreaterThan(href);
    expect(event).toBeLessThan(anchorEnd);
    expect(trigger).toBeGreaterThan(event);
    expect(trigger).toBeLessThan(anchorEnd);
  });

  it("GUILT: does not fire the pricing CTA event", () => {
    expect(MODAL).not.toContain("consult_click");
    expect(MODAL).not.toContain("trackKBLICTA");
  });
});
