import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The only WhatsApp hand-off on /kbli-explorer (the KBLI 2025 transition
 * modal) sent no event when clicked, so the route's one lead CTA could not be
 * counted. It now fires the existing `kbli_consult_click` funnel event
 * (`trackKBLICTA` → GA4 + internal bus + funnel store), the same event the
 * /v2 KBLI block uses; `kbli_consult_click` is already in FUNNEL_EVENTS.
 *
 * Declared limits: this reads source text. It proves the handler is wired on
 * the WhatsApp link, not that GA4 receives the hit.
 */
const MODAL = readFileSync(join(__dirname, "BlackBookModal.tsx"), "utf8");

describe("/kbli-explorer WhatsApp hand-off is counted", () => {
  it("positive control: the modal still links to the kbli WhatsApp line", () => {
    expect(MODAL).toContain('href={buildWhatsAppLink("kbli")}');
  });

  it("imports trackKBLICTA from the shared analytics module", () => {
    expect(MODAL).toMatch(
      /import \{ trackKBLICTA \} from "@\/lib\/analytics";/,
    );
  });

  it("fires consult_click on the same anchor as the WhatsApp link", () => {
    const href = MODAL.indexOf('href={buildWhatsAppLink("kbli")}');
    const anchorEnd = MODAL.indexOf(">", href);
    const click = MODAL.indexOf(
      'onClick={() => trackKBLICTA("consult_click")}',
      href,
    );
    expect(click).toBeGreaterThan(href);
    expect(click).toBeLessThan(anchorEnd);
  });
});
