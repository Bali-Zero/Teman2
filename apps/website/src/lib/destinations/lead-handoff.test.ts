import { afterEach, describe, expect, it, vi } from "vitest";
import {
  contactSourcePage,
  directHandoffHref,
  inferContactTopic,
  isContactTopic,
  measureLeadHandoff,
  requestLeadHandoff,
  safeCapturedWhatsAppHref,
  type LeadHandoffRequest,
} from "./lead-handoff";

const request: LeadHandoffRequest = {
  topic: "property",
  sourcePage: "/services/property",
};
const capturedHref = "https://wa.me/628213454721?text=Property%20enquiry";
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
});

describe("closed contact context", () => {
  it("preserves known routes and replaces article slugs with the journal route", () => {
    expect(contactSourcePage("/services/property")).toBe("/services/property");
    expect(contactSourcePage("/property/a-published-story")).toBe("/news");
    expect(inferContactTopic("/property/a-published-story")).toBe("property");
    expect(inferContactTopic("/business/a-published-story")).toBe("company");
    expect(inferContactTopic("/visa/voa")).toBe("evoa");
    expect(inferContactTopic("/visa/second-home/studio")).toBe("second-home");
  });

  it.each([
    "/contact?message=private",
    "/contact#private",
    "/unknown/private",
    "//other.example",
    "/property/private%40example",
    null,
  ])("discards unrecognized context %s", (source) => {
    expect(contactSourcePage(source)).toBe("/contact");
    if (typeof source === "string")
      expect(inferContactTopic(source)).toBe("general");
  });

  it("accepts only own topic names, including against prototype properties", () => {
    expect(isContactTopic("tax")).toBe(true);
    expect(isContactTopic("constructor")).toBe(false);
    expect(isContactTopic("__proto__")).toBe(false);
  });

  it("builds a direct fallback with topic and safe source without arbitrary fields", () => {
    const url = new URL(directHandoffHref(request));
    expect(url.hostname).toBe("wa.me");
    expect(url.pathname).toBe("/628213454721");
    expect(url.searchParams.get("text")).toContain(
      "property due diligence (from /services/property)",
    );
    expect([...url.searchParams.keys()]).toEqual(["text"]);
  });
});

describe("capture response validation", () => {
  it("accepts the exact business recipient", () =>
    expect(safeCapturedWhatsAppHref(capturedHref)).toBe(capturedHref));
  it.each([
    "https://evil.example/?text=enquiry",
    "javascript:alert(1)",
    "https://wa.me/111111111?text=enquiry",
    "http://wa.me/628213454721?text=enquiry",
    "https://user:pass@wa.me/628213454721?text=enquiry",
    "https://wa.me/628213454721?text=enquiry#other",
    "https://wa.me/628213454721?text=enquiry&redirect=elsewhere",
    "https://wa.me/628213454721?text=a&text=b",
    "https://wa.me/628213454721",
    "https://wa.me:444/628213454721?text=enquiry",
    null,
  ])("blocks an invalid returned handoff %s", (href) =>
    expect(safeCapturedWhatsAppHref(href)).toBeNull(),
  );
});

describe("bounded lead request", () => {
  it("sends one minimized same-origin request and accepts only a confirmed 201", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        Response.json({ whatsapp_url: capturedHref }, { status: 201 }),
      );
    expect(await requestLeadHandoff(request, fetcher)).toEqual({
      href: capturedHref,
      captured: true,
    });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toBe("/api/lead/capture");
    const init = fetcher.mock.calls[0][1]!;
    expect(init).toMatchObject({
      method: "POST",
      credentials: "omit",
      cache: "no-store",
      redirect: "error",
    });
    expect(JSON.parse(init.body as string)).toEqual(request);
  });

  it.each([503, 200])(
    "uses the contextual direct link for unconfirmed status %s",
    async (status) => {
      const fetcher = vi
        .fn<typeof fetch>()
        .mockResolvedValue(
          Response.json({ whatsapp_url: capturedHref }, { status }),
        );
      expect(await requestLeadHandoff(request, fetcher)).toEqual({
        href: directHandoffHref(request),
        captured: false,
      });
    },
  );

  it("retains the direct route after network failure or malformed output", async () => {
    const failure = vi
      .fn<typeof fetch>()
      .mockRejectedValue(new Error("offline"));
    const malformed = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        Response.json(
          { whatsapp_url: "https://evil.example" },
          { status: 201 },
        ),
      );
    for (const fetcher of [failure, malformed]) {
      expect(await requestLeadHandoff(request, fetcher)).toEqual({
        href: directHandoffHref(request),
        captured: false,
      });
    }
  });

  it("times out even if the transport ignores abort; it never retries", async () => {
    vi.useFakeTimers();
    const fetcher = vi
      .fn<typeof fetch>()
      .mockImplementation(() => new Promise(() => {}));
    const result = requestLeadHandoff(request, fetcher, 30);
    await vi.advanceTimersByTimeAsync(30);
    expect(await result).toEqual({
      href: directHandoffHref(request),
      captured: false,
    });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][1]?.signal?.aborted).toBe(true);
  });
});

describe("optional consented measurement", () => {
  it("requires the flag, consent, and a real consumer", () => {
    const consumer = vi.fn();
    const event = { ...request, captured: false };
    measureLeadHandoff(event, false, consumer, true);
    measureLeadHandoff(event, true, consumer, false);
    measureLeadHandoff(event, true, undefined, true);
    expect(consumer).not.toHaveBeenCalled();
  });

  it("does not emit when the integration flag has not been configured", () => {
    vi.stubEnv("NEXT_PUBLIC_WEBSITE_LEAD_ANALYTICS_ENABLED", "");
    const consumer = vi.fn();
    measureLeadHandoff({ ...request, captured: false }, true, consumer);
    expect(consumer).not.toHaveBeenCalled();
  });

  it.each([true, false])(
    "sends captured=%s to the configured consumer without session or client identifiers",
    (captured) => {
      const consumer = vi.fn();
      measureLeadHandoff({ ...request, captured }, true, consumer, true);
      expect(consumer).toHaveBeenCalledExactlyOnceWith(
        "event",
        "lead_whatsapp_cta",
        {
          event_category: "Conversion",
          source: "cta_handoff",
          topic: "property",
          source_page: "/services/property",
          captured,
          transport_type: "beacon",
        },
      );
    },
  );

  it("does not let a failed analytics consumer break contact", () => {
    expect(() =>
      measureLeadHandoff(
        { ...request, captured: false },
        true,
        () => {
          throw new Error("consumer unavailable");
        },
        true,
      ),
    ).not.toThrow();
  });
});
