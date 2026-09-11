import { describe, expect, it } from "vitest";
import config from "../../next.config";

/**
 * The gap this closes: the cutover's most irreversible change — every redirect
 * flipped to 308 — had no test at all. A 308 is cached by browsers and search
 * engines effectively forever, and nothing here would have gone red if one of
 * the ~40 entries were set back to `permanent: false`.
 */
describe("redirect permanence is a contract, not a habit", () => {
  it("declares every redirect permanent, and says how many", async () => {
    const redirects = await config.redirects!();
    const impermanent = redirects.filter(({ permanent }) => permanent !== true);

    expect(impermanent).toEqual([]);
    // Guilt control: an empty list would satisfy the assertion above.
    expect(redirects.length).toBeGreaterThan(30);
  });

  it("never redirects a path to itself", async () => {
    const redirects = await config.redirects!();
    expect(
      redirects.filter(({ source, destination }) => source === destination),
    ).toEqual([]);
  });
});
