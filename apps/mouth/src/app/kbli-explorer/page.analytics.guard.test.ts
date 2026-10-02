import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * /kbli-explorer sent zero analytics events: a search of the route for every
 * helper of both analytics paths (@/lib/analytics and @balizero/core) returned
 * no line at 9282d24513, while 15 of its files import something. The page now
 * reports each answered query through the existing `kbli_search` helper.
 *
 * Declared limits: this reads the source, it does not render the page. It
 * proves the call is wired after the chat response, not that GA4 receives it.
 */
const PAGE = readFileSync(join(__dirname, "page.tsx"), "utf8");

describe("/kbli-explorer analytics", () => {
  it("positive control: the chat handler this guard anchors on exists", () => {
    expect(PAGE).toContain("await kbliApi.chat(text)");
  });

  it("imports trackKBLISearch from the shared analytics module", () => {
    expect(PAGE).toMatch(
      /import \{ trackKBLISearch \} from "@\/lib\/analytics";/,
    );
  });

  it("fires kbli_search after the chat response, with the result count", () => {
    const chat = PAGE.indexOf("await kbliApi.chat(text)");
    const track = PAGE.indexOf("trackKBLISearch(text,", chat);
    const nextAwait = PAGE.indexOf("await ", chat + 1);
    expect(track).toBeGreaterThan(chat);
    expect(nextAwait === -1 || track < nextAwait).toBe(true);
    expect(PAGE).toContain(
      "trackKBLISearch(text, response.results ? response.results.length : 0)",
    );
  });
});
