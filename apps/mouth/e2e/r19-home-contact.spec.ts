import { test, expect, type Page } from "@playwright/test";
import { WA_NUMBER } from "../src/lib/whatsapp-utm";

/**
 * The transplanted R19 home carries every WhatsApp / e-mail action of the
 * existing funnel: same company number, same lead source, same capture
 * payload, same analytics events. Nothing here reaches a real endpoint: the
 * capture, the funnel-event beacon and wa.me itself are all answered locally,
 * and GA4 is a recording stub.
 */
const WA = `https://wa.me/${WA_NUMBER}`;
const EMAIL = "zantara@balizero.com";

// DOM order of the tracked (WhatsAppLeadButton) actions on "/".
const ACTIONS = [
  { topic: "immigration", section: "services", subject: "Visas & residence" },
  {
    topic: "company",
    section: "services",
    subject: "Company setup & licensing",
  },
  { topic: "tax", section: "services", subject: "Tax & accounting" },
  { topic: "property", section: "services", subject: "Property due diligence" },
  {
    topic: "compliance",
    section: "services",
    subject: "Compliance & obligations",
  },
  { topic: "evoa", section: "arrival", subject: "E-VOA arrival planning" },
  { topic: "second-home", section: "studio", subject: "Second Home planning" },
  { topic: "general", section: "contact", subject: "A general question" },
] as const;

type Gtag = unknown[];

async function armGtag(page: Page) {
  const calls: Gtag[] = [];
  // The root layout defines the real `gtag()` as dataLayer.push(arguments); we
  // observe that push and leave the app's own function in charge. A binding
  // survives the navigation to wa.me that ends every handoff.
  await page.exposeBinding("__recordGtag", (_source, payload: string) => {
    calls.push(JSON.parse(payload));
  });
  await page.addInitScript(() => {
    const record = (
      window as unknown as { __recordGtag: (payload: string) => void }
    ).__recordGtag;
    const layer: unknown[] = [];
    layer.push = (...items: unknown[]) => {
      for (const item of items)
        record(JSON.stringify(Array.from(item as ArrayLike<unknown>)));
      return Array.prototype.push.apply(layer, items);
    };
    Object.assign(window, { dataLayer: layer });
  });
  return calls;
}

/**
 * Answers the funnel beacon locally and keeps the wa.me navigation pending
 * until that beacon has landed: the handoff leaves the page right after it
 * fires its events, and a page that is already gone cannot be observed.
 */
async function armBeacon(page: Page) {
  const beacons: unknown[] = [];
  let landed!: () => void;
  const seen = new Promise<void>((resolve) => (landed = resolve));
  await page.route("**/api/analytics/funnel-event", (route) => {
    beacons.push(route.request().postDataJSON());
    landed();
    return route.fulfill({ status: 204, body: "" });
  });
  await page.route("https://wa.me/**", async (route) => {
    await Promise.race([seen, new Promise((r) => setTimeout(r, 3000))]);
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<title>wa.me stub</title>",
    });
  });
  return beacons;
}

const events = (calls: Gtag[], name: string) =>
  calls
    .filter((c) => c[0] === "event" && c[1] === name)
    .map((c) => c[2] as Record<string, unknown>);

test.beforeEach(async ({ page }) => {
  await page.route("**/*", (route) => {
    const request = route.request();
    if (request.url().startsWith("https://wa.me/"))
      return route.fulfill({
        status: 200,
        contentType: "text/html",
        body: "<title>wa.me stub</title>",
      });
    return !["GET", "HEAD"].includes(request.method()) ||
      /google-analytics|doubleclick|googletagmanager|\/api\/funnel\//.test(
        request.url(),
      )
      ? route.fulfill({ status: 204, body: "" })
      : route.continue();
  });
});

test.describe("R19 home contact actions", () => {
  test("every WhatsApp, e-mail and phone action points at the existing company channels", async ({
    page,
  }) => {
    await page.goto("/");
    const links = await page.evaluate(() =>
      [...document.querySelectorAll("a[href]")].map((a) => ({
        href: a.getAttribute("href")!,
        lead: a.getAttribute("data-lead-source"),
      })),
    );
    const whatsapp = links.filter((l) => l.href.includes("wa.me"));
    // Eight tracked handoffs plus the footer's plain wa.me link.
    expect(whatsapp).toHaveLength(9);
    for (const { href } of whatsapp) {
      const url = new URL(href);
      expect(`${url.origin}${url.pathname}`).toBe(WA);
    }
    const tracked = whatsapp.filter((l) => l.lead);
    expect(tracked).toHaveLength(ACTIONS.length);
    expect(new Set(tracked.map((l) => l.lead))).toEqual(
      new Set(["cta_handoff"]),
    );
    expect(
      tracked.map((l) => new URL(l.href).searchParams.get("text")),
    ).toEqual(
      ACTIONS.map(
        (a) => `Hello Bali Zero, I would like to discuss ${a.subject}.`,
      ),
    );
    const mailto = links.filter((l) => l.href.startsWith("mailto:"));
    expect(mailto.length).toBeGreaterThanOrEqual(3);
    for (const { href } of mailto)
      expect(href.startsWith(`mailto:${EMAIL}`)).toBe(true);
    const tel = links.filter((l) => l.href.startsWith("tel:"));
    expect(tel.length).toBeGreaterThanOrEqual(1);
    for (const { href } of tel) expect(href).toBe(`tel:+${WA_NUMBER}`);
  });

  ACTIONS.forEach((action, index) => {
    test(`${action.section}/${action.topic}: capture payload, analytics events and handoff`, async ({
      page,
    }) => {
      const gtag = await armGtag(page);
      const captured: unknown[] = [];
      const beacons = await armBeacon(page);
      await page.route("**/api/lead/capture", (route) => {
        captured.push(route.request().postDataJSON());
        return route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            whatsapp_url: `${WA}?text=e2e-${index}`,
            lead_intent_id: `e2e-lead-${index}`,
          }),
        });
      });
      await page.goto("/");
      const link = page.locator("a[data-lead-source]").nth(index);
      await link.scrollIntoViewIfNeeded();
      const handoff = page.waitForRequest(
        (r) => r.url().startsWith("https://wa.me/") && r.isNavigationRequest(),
      );
      await link.click();
      expect((await handoff).url()).toBe(`${WA}?text=e2e-${index}`);

      expect(captured).toEqual([
        {
          source: "cta_handoff",
          context: {
            topic: action.topic,
            source_page: "/",
            section: action.section,
          },
          whatsapp_context: [
            { label: "Topic", value: action.subject },
            { label: "Page", value: "Bali Zero homepage" },
          ],
          utm: { page: "/" },
        },
      ]);

      const lead = `e2e-lead-${index}`;
      await expect.poll(() => events(gtag, "lead_whatsapp_cta").length).toBe(2);
      const [cta, funnel] = events(gtag, "lead_whatsapp_cta");
      expect(cta).toEqual({
        event_category: "Conversion",
        source: "cta_handoff",
        captured: true,
        transport_type: "beacon",
        lead_intent_id: lead,
      });
      expect(funnel).toMatchObject({
        event: "lead_whatsapp_cta",
        session_id: expect.any(String),
      });
      expect(JSON.parse(funnel.payload as string)).toEqual({
        source: "cta_handoff",
        captured: true,
        lead_intent_id: lead,
      });
      expect(events(gtag, "lead_created")).toEqual([
        { event_category: "Conversion", source: "cta_handoff" },
      ]);
      expect(beacons).toEqual([
        {
          session_id: expect.any(String),
          event: "lead_whatsapp_cta",
          payload: {
            source: "cta_handoff",
            captured: true,
            lead_intent_id: lead,
          },
          hostname: expect.any(String),
        },
      ]);
    });
  });

  test("a failed capture still hands off to the company number and reports captured=false", async ({
    page,
  }) => {
    const gtag = await armGtag(page);
    const beacons = await armBeacon(page);
    await page.route("**/api/lead/capture", (route) =>
      route.fulfill({ status: 500, body: "capture unavailable" }),
    );
    await page.goto("/");
    const link = page.locator("a[data-lead-source]").nth(3);
    await link.scrollIntoViewIfNeeded();
    const fallback = await link.getAttribute("href");
    const handoff = page.waitForRequest(
      (r) => r.url().startsWith("https://wa.me/") && r.isNavigationRequest(),
    );
    await link.click();
    const url = new URL((await handoff).url());
    expect(url.href).toBe(fallback);
    expect(`${url.origin}${url.pathname}`).toBe(WA);
    expect(url.searchParams.get("text")).toBe(
      "Hello Bali Zero, I would like to discuss Property due diligence.",
    );
    await expect.poll(() => events(gtag, "lead_whatsapp_cta").length).toBe(2);
    expect(events(gtag, "lead_whatsapp_cta")[0]).toEqual({
      event_category: "Conversion",
      source: "cta_handoff",
      captured: false,
      transport_type: "beacon",
    });
    expect(events(gtag, "lead_created")).toEqual([]);
    expect(beacons).toEqual([
      {
        session_id: expect.any(String),
        event: "lead_whatsapp_cta",
        payload: { source: "cta_handoff", captured: false },
        hostname: expect.any(String),
      },
    ]);
  });

  test("the e-mail action carries the chosen topic to the company address", async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByRole("combobox").selectOption("tax");
    const href = await page
      .getByRole("link", { name: /Write an email/ })
      .getAttribute("href");
    const url = new URL(href!);
    expect(url.protocol).toBe("mailto:");
    expect(url.pathname).toBe(EMAIL);
    expect(url.searchParams.get("subject")).toBe(
      "Bali Zero — Tax & accounting",
    );
    expect(url.searchParams.get("body")).toContain("Tax & accounting");
  });
});
