import { afterEach, describe, expect, it, vi } from "vitest";

// The page is a server component: it must read GARUDA_PAYMENTS_LIVE per request and hand
// the result to CheckoutFlow. Codex review (W-L, 2026-09-15): without this file,
// hard-coding `paymentsLive={true}` left every focused test green and would have sent
// real tourists into a sandbox checkout.
vi.mock("./CheckoutFlow", () => ({
  CheckoutFlow: (props: { resultId: string; paymentsLive: boolean }) => props,
}));

import CheckoutPage from "./page";
import * as layout from "../../layout";

async function renderedProps(resultId = "result-12345678") {
  const element = (await CheckoutPage({
    params: Promise.resolve({ resultId }),
  })) as { props: { resultId: string; paymentsLive: boolean } };
  return element.props;
}

describe("checkout page — payment switch wiring", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("passes paymentsLive=false when GARUDA_PAYMENTS_LIVE is unset", async () => {
    vi.stubEnv("GARUDA_PAYMENTS_LIVE", "");
    expect(await renderedProps()).toEqual({
      resultId: "result-12345678",
      paymentsLive: false,
    });
  });

  it("passes paymentsLive=false for anything but the literal true", async () => {
    for (const value of ["false", "1", "yes", "tru"]) {
      vi.stubEnv("GARUDA_PAYMENTS_LIVE", value);
      expect((await renderedProps()).paymentsLive).toBe(false);
    }
  });

  it("passes paymentsLive=true only for GARUDA_PAYMENTS_LIVE=true, read at request time", async () => {
    vi.stubEnv("GARUDA_PAYMENTS_LIVE", "");
    expect((await renderedProps()).paymentsLive).toBe(false);
    vi.stubEnv("GARUDA_PAYMENTS_LIVE", "true");
    expect((await renderedProps()).paymentsLive).toBe(true);
  });

  it("the /visa/voa segment stays force-dynamic, so the flag is never baked at build", () => {
    expect(layout.dynamic).toBe("force-dynamic");
  });
});
