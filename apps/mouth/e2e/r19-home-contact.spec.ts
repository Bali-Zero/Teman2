import { test, expect, type Locator, type Page } from "@playwright/test";
import { WA_NUMBER, buildWhatsAppLink } from "../src/lib/whatsapp-utm";

/**
 * The transplanted R19 home carries every WhatsApp / e-mail action of the
 * existing funnel: same company number, same lead source, same capture
 * payload, same analytics events. Nothing here reaches a real endpoint: the
 * capture, the funnel-event beacon and wa.me itself are all answered locally,
 * and GA4 is observed as the app's own dataLayer pushes.
 */
const WA = `https://wa.me/${WA_NUMBER}`;
const EMAIL = "zantara@balizero.com";
// What both the header CTA (NavWhatsAppCTA) and the hero fallback dial today.
const HOME_LINK = buildWhatsAppLink("home");
const HOME_GREETING = new URL(HOME_LINK).searchParams.get("text");

// DOM order of the cta_handoff actions on "/" (HomeContactLink).
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

type Handoff = {
  name: string;
  source: string;
  locate: (page: Page) => Locator;
  capture: Record<string, unknown>;
};

// The live hero handoff (HeroCTA): same source, context and Source row.
const HERO: Handoff = {
  name: "hero/homepage_hero",
  source: "homepage_hero",
  locate: (page) =>
    page.locator('.entry-hero a[data-lead-source="homepage_hero"]'),
  capture: {
    source: "homepage_hero",
    context: { section: "hero", page: "home" },
    whatsapp_context: [{ label: "Source", value: "Homepage Hero" }],
    utm: { page: "/" },
  },
};

const HANDOFFS: Handoff[] = [
  HERO,
  ...ACTIONS.map((action, index): Handoff => ({
    name: `${action.section}/${action.topic}`,
    source: "cta_handoff",
    locate: (page) =>
      page.locator('a[data-lead-source="cta_handoff"]').nth(index),
    capture: {
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
  })),
];

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
 * Answers the funnel beacon locally. With `hold`, it also keeps the wa.me
 * navigation pending until that beacon has landed: a same-tab handoff leaves
 * the page right after it fires its events, and a page that is already gone
 * cannot be observed.
 */
async function armBeacon(page: Page, hold = true) {
  const beacons: unknown[] = [];
  let landed!: () => void;
  const seen = new Promise<void>((resolve) => (landed = resolve));
  await page.route("**/api/analytics/funnel-event", (route) => {
    beacons.push(route.request().postDataJSON());
    landed();
    return route.fulfill({ status: 204, body: "" });
  });
  if (hold)
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

const waStub = {
  status: 200,
  contentType: "text/html",
  body: "<title>wa.me stub</title>",
};

test.beforeEach(async ({ page, context }) => {
  // target="_blank" opens a popup, which page-level routes do not cover.
  await context.route("https://wa.me/**", (route) => route.fulfill(waStub));
  await page.route("**/*", (route) => {
    const request = route.request();
    if (request.url().startsWith("https://wa.me/"))
      return route.fulfill(waStub);
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
    // Header CTA, hero handoff, eight cta_handoff and the footer's plain link.
    expect(whatsapp).toHaveLength(11);
    for (const { href } of whatsapp) {
      const url = new URL(href);
      expect(`${url.origin}${url.pathname}`).toBe(WA);
    }
    const tracked = whatsapp.filter((l) => l.lead);
    expect(tracked.map((l) => l.lead)).toEqual([
      "homepage_hero",
      ...ACTIONS.map(() => "cta_handoff"),
    ]);
    // The header CTA and the hero fallback are the live home's own link.
    expect(whatsapp.filter((l) => l.href === HOME_LINK)).toHaveLength(2);
    expect(
      tracked
        .filter((l) => l.lead === "cta_handoff")
        .map((l) => new URL(l.href).searchParams.get("text")),
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

  for (const width of [390, 1440]) {
    test(`header and hero WhatsApp actions are above the fold and dial the company number at ${width}px`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/");
      await page.evaluate(() => document.fonts.ready);
      const header = page.locator(".site-header a[href*='wa.me']");
      const hero = HERO.locate(page);
      const lastDoor = page.locator(
        ".entry-hero .entry-categories li:last-child a",
      );
      await expect(header).toHaveCount(1);
      await expect(hero).toHaveCount(1);
      await expect(header).toBeVisible();
      await expect(hero).toBeVisible();
      const [headerBox, heroBox, doorBox] = await Promise.all([
        header.boundingBox(),
        hero.boundingBox(),
        lastDoor.boundingBox(),
      ]);
      for (const box of [headerBox, heroBox]) {
        expect(box).not.toBeNull();
        expect(box!.x).toBeGreaterThanOrEqual(0);
        expect(box!.x + box!.width).toBeLessThanOrEqual(width);
        expect(box!.y).toBeGreaterThanOrEqual(0);
        expect(box!.y + box!.height).toBeLessThanOrEqual(900);
      }
      expect(headerBox!.height).toBeGreaterThanOrEqual(44);
      expect(heroBox!.height).toBeGreaterThanOrEqual(48);
      // The hero action sits below the five doors, not among them.
      expect(heroBox!.y).toBeGreaterThanOrEqual(doorBox!.y + doorBox!.height);
      expect(await header.getAttribute("href")).toBe(HOME_LINK);
      expect(await hero.getAttribute("href")).toBe(HOME_LINK);
    });
  }

  for (const width of [360, 390, 981, 1024, 1240, 1440]) {
    test(`the header WhatsApp action fits the header without crowding it at ${width}px`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/");
      await page.evaluate(() => document.fonts.ready);
      const m = await page.evaluate(() => {
        const header = document.querySelector(".site-header")!;
        const box = (el: Element) => el.getBoundingClientRect();
        const cta = box(header.querySelector(".entry-header-cta a")!);
        const others = [
          ...header.querySelectorAll(
            ".brand, .entry-menu-toggle, .entry-navigation > a",
          ),
        ]
          .map((el) => ({ el, r: box(el) }))
          .filter(({ r }) => r.width > 0 && r.height > 0);
        return {
          overflow: document.documentElement.scrollWidth - innerWidth,
          headerOverflow: header.scrollWidth - header.clientWidth,
          ctaRight: cta.right,
          ctaLeft: cta.left,
          overlapping: others
            .filter(
              ({ r }) =>
                !(
                  r.right <= cta.left ||
                  r.left >= cta.right ||
                  r.bottom <= cta.top ||
                  r.top >= cta.bottom
                ),
            )
            .map(({ el }) => el.className || el.tagName),
          wrappedLinks: others.filter(
            ({ el, r }) => el.matches(".entry-navigation > a") && r.height > 52,
          ).length,
        };
      });
      expect(m.overflow).toBeLessThanOrEqual(1);
      expect(m.headerOverflow).toBeLessThanOrEqual(1);
      expect(m.ctaRight).toBeLessThanOrEqual(width);
      expect(m.ctaLeft).toBeGreaterThanOrEqual(0);
      expect(m.overlapping).toEqual([]);
      expect(m.wrappedLinks).toBe(0);
    });
  }

  test("the header WhatsApp action opens the company chat in a new tab and fires the nav event", async ({
    page,
    context,
  }) => {
    const gtag = await armGtag(page);
    const beacons = await armBeacon(page, false);
    await page.goto("/");
    const link = page.locator(".site-header a[href*='wa.me']");
    expect(await link.getAttribute("target")).toBe("_blank");
    const opened = context.waitForEvent("page");
    await link.click();
    const tab = await opened;
    await tab.waitForLoadState("domcontentloaded");
    expect(tab.url()).toBe(HOME_LINK);
    await expect.poll(() => events(gtag, "home_whatsapp_cta").length).toBe(1);
    const [nav] = events(gtag, "home_whatsapp_cta");
    expect(nav).toMatchObject({
      event: "home_whatsapp_cta",
      session_id: expect.any(String),
    });
    expect(JSON.parse(nav.payload as string)).toEqual({ trigger: "nav" });
    await expect.poll(() => beacons.length).toBe(1);
    expect(beacons).toEqual([
      {
        session_id: expect.any(String),
        event: "home_whatsapp_cta",
        payload: { trigger: "nav" },
        hostname: expect.any(String),
      },
    ]);
    // A bare wa.me link: no lead capture, so no capture events.
    expect(events(gtag, "lead_whatsapp_cta")).toEqual([]);
    expect(events(gtag, "lead_created")).toEqual([]);
  });

  HANDOFFS.forEach((handoff, index) => {
    test(`${handoff.name}: capture payload, analytics events and handoff`, async ({
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
      const link = handoff.locate(page);
      await link.scrollIntoViewIfNeeded();
      const navigation = page.waitForRequest(
        (r) => r.url().startsWith("https://wa.me/") && r.isNavigationRequest(),
      );
      await link.click();
      expect((await navigation).url()).toBe(`${WA}?text=e2e-${index}`);

      expect(captured).toEqual([handoff.capture]);

      const lead = `e2e-lead-${index}`;
      await expect.poll(() => events(gtag, "lead_whatsapp_cta").length).toBe(2);
      const [cta, funnel] = events(gtag, "lead_whatsapp_cta");
      expect(cta).toEqual({
        event_category: "Conversion",
        source: handoff.source,
        captured: true,
        transport_type: "beacon",
        lead_intent_id: lead,
      });
      expect(funnel).toMatchObject({
        event: "lead_whatsapp_cta",
        session_id: expect.any(String),
      });
      expect(JSON.parse(funnel.payload as string)).toEqual({
        source: handoff.source,
        captured: true,
        lead_intent_id: lead,
      });
      expect(events(gtag, "lead_created")).toEqual([
        { event_category: "Conversion", source: handoff.source },
      ]);
      await expect
        .poll(() => beacons)
        .toEqual([
          {
            session_id: expect.any(String),
            event: "lead_whatsapp_cta",
            payload: {
              source: handoff.source,
              captured: true,
              lead_intent_id: lead,
            },
            hostname: expect.any(String),
          },
        ]);
    });
  });

  for (const [name, handoff, text] of [
    ["hero", HERO, HOME_GREETING],
    [
      "property",
      HANDOFFS[4],
      "Hello Bali Zero, I would like to discuss Property due diligence.",
    ],
  ] as const) {
    test(`a failed capture on the ${name} action still hands off to the company number and reports captured=false`, async ({
      page,
    }) => {
      const gtag = await armGtag(page);
      const beacons = await armBeacon(page);
      await page.route("**/api/lead/capture", (route) =>
        route.fulfill({ status: 500, body: "capture unavailable" }),
      );
      await page.goto("/");
      const link = handoff.locate(page);
      await link.scrollIntoViewIfNeeded();
      const fallback = await link.getAttribute("href");
      const navigation = page.waitForRequest(
        (r) => r.url().startsWith("https://wa.me/") && r.isNavigationRequest(),
      );
      await link.click();
      const url = new URL((await navigation).url());
      expect(url.href).toBe(fallback);
      expect(`${url.origin}${url.pathname}`).toBe(WA);
      expect(url.searchParams.get("text")).toBe(text);
      await expect.poll(() => events(gtag, "lead_whatsapp_cta").length).toBe(2);
      expect(events(gtag, "lead_whatsapp_cta")[0]).toEqual({
        event_category: "Conversion",
        source: handoff.source,
        captured: false,
        transport_type: "beacon",
      });
      expect(events(gtag, "lead_created")).toEqual([]);
      await expect
        .poll(() => beacons)
        .toEqual([
          {
            session_id: expect.any(String),
            event: "lead_whatsapp_cta",
            payload: { source: handoff.source, captured: false },
            hostname: expect.any(String),
          },
        ]);
    });
  }

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
