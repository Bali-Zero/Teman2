import { buildWhatsAppIntent } from "./intents";
import { isArticleSlug } from "../article-slug";

export const contactTopics = {
  immigration: "visas and residence",
  company: "company setup and business licensing",
  tax: "tax and accounting",
  property: "property due diligence",
  compliance: "compliance retainers and regulatory obligations",
  evoa: "an E-VOA arrival plan",
  "second-home": "a Second Home plan",
  portal: "access to my client portal",
  general: "my plans in Indonesia",
} as const;

export type ContactTopic = keyof typeof contactTopics;

export const contactSourcePages = [
  "/",
  "/about",
  "/team",
  "/contact",
  "/services",
  "/journal",
  "/services/immigration",
  "/services/company-setup",
  "/services/tax",
  "/services/property",
  "/services/compliance",
  "/visa/voa",
  "/visa/clock",
  "/visa/match",
  "/visa/second-home",
  "/visa/second-home/studio",
  "/kbli",
  "/property/eligibility",
  "/taxes/gap",
  "/tax-calendar",
  "/visa-oracle",
  "/kbli-explorer",
  "/zoning",
  "/prime",
  "/book",
] as const;
export type ContactSourcePage = (typeof contactSourcePages)[number];
export interface LeadHandoffRequest {
  topic: ContactTopic;
  sourcePage: ContactSourcePage;
}
export interface HandoffOutcome {
  href: string;
  captured: boolean;
}
export interface HandoffMeasurement extends LeadHandoffRequest {
  captured: boolean;
}

const articlePath =
  /^\/(visas|business|taxes|property|living|trends)\/([^/]+)$/;

function articleCategory(pathname: string): string | undefined {
  const match = articlePath.exec(pathname);
  return match && isArticleSlug(match[2]) ? match[1] : undefined;
}

export function isContactTopic(value: unknown): value is ContactTopic {
  return typeof value === "string" && Object.hasOwn(contactTopics, value);
}

export function isContactSourcePage(
  value: unknown,
): value is ContactSourcePage {
  return (
    typeof value === "string" &&
    contactSourcePages.some((page) => page === value)
  );
}

/** Never preserve a query, fragment, result reference, or arbitrary article slug. */
export function contactSourcePage(value: unknown): ContactSourcePage {
  if (isContactSourcePage(value)) return value;
  if (typeof value !== "string") return "/contact";
  if (
    /^\/kbli\/(?:\d{5}|builder|decoder|sectors(?:\/[a-z0-9-]{1,100})?)$/.test(
      value,
    )
  )
    return "/kbli";
  if (/^\/prime\/proposal\/[A-Za-z0-9_-]{1,200}$/.test(value)) return "/prime";
  if (/^\/book\/[a-z0-9-]{1,200}$/.test(value)) return "/book";
  if (/^\/visa\/second-home\/(?:it|id)$/.test(value))
    return "/visa/second-home";
  const visa = /^\/visa\/(voa|clock|match)\/[A-Za-z0-9_-]{1,200}$/.exec(value);
  if (visa) return `/visa/${visa[1]}` as ContactSourcePage;
  if (value === "/visa" || value === "/visa-v2") return "/visa-oracle";
  return articleCategory(value) ? "/journal" : "/contact";
}

export function inferContactTopic(pathname: string): ContactTopic {
  const source = contactSourcePage(pathname);
  if (source === "/visa/voa") return "evoa";
  if (source.startsWith("/visa/second-home")) return "second-home";
  if (
    source.startsWith("/visa/") ||
    source === "/visa-oracle" ||
    source === "/services/immigration"
  )
    return "immigration";
  if (
    source === "/services/company-setup" ||
    source === "/kbli" ||
    source === "/kbli-explorer"
  )
    return "company";
  if (
    source === "/services/tax" ||
    source === "/taxes/gap" ||
    source === "/tax-calendar"
  )
    return "tax";
  if (
    source === "/services/property" ||
    source === "/property/eligibility" ||
    source === "/prime" ||
    source === "/zoning"
  )
    return "property";
  if (source === "/services/compliance") return "compliance";
  const category = articleCategory(pathname);
  if (category === "visas") return "immigration";
  if (category === "business") return "company";
  if (category === "taxes") return "tax";
  if (category === "property") return "property";
  return "general";
}

export function directHandoffHref({
  topic,
  sourcePage,
}: LeadHandoffRequest): string {
  return buildWhatsAppIntent({
    topic: `${contactTopics[topic]} (from ${sourcePage})`,
  });
}

export function safeCapturedWhatsAppHref(value: unknown): string | null {
  if (
    typeof value !== "string" ||
    value.length > 4096 ||
    value.trim() !== value
  )
    return null;
  try {
    const url = new URL(value);
    if (
      url.protocol !== "https:" ||
      url.hostname !== "wa.me" ||
      url.port ||
      url.username ||
      url.password ||
      url.pathname !== "/628213454721" ||
      url.hash ||
      [...url.searchParams.keys()].some((key) => key !== "text") ||
      url.searchParams.getAll("text").length !== 1 ||
      !url.searchParams.get("text")
    )
      return null;
    return url.href;
  } catch {
    return null;
  }
}

/** The same-origin gate is disabled by default. Failure never blocks the direct link. */
export async function requestLeadHandoff(
  request: LeadHandoffRequest,
  fetcher: typeof fetch = fetch,
  timeoutMs = 1800,
): Promise<HandoffOutcome> {
  const fallback = { href: directHandoffHref(request), captured: false };
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const capture = async (): Promise<HandoffOutcome> => {
      const response = await fetcher("/api/lead/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        credentials: "omit",
        cache: "no-store",
        redirect: "error",
        signal: controller.signal,
      });
      if (response.status !== 201) return fallback;
      const body: unknown = await response.json();
      const href =
        body && typeof body === "object" && "whatsapp_url" in body
          ? safeCapturedWhatsAppHref(body.whatsapp_url)
          : null;
      return href ? { href, captured: true } : fallback;
    };
    return await Promise.race([
      capture(),
      new Promise<HandoffOutcome>((resolve) => {
        timer = setTimeout(() => {
          controller.abort();
          resolve(fallback);
        }, timeoutMs);
      }),
    ]);
  } catch {
    return fallback;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

type AnalyticsConsumer = (
  command: "event",
  event: "lead_whatsapp_cta",
  parameters: {
    event_category: "Conversion";
    source: "cta_handoff";
    topic: ContactTopic;
    source_page: ContactSourcePage;
    captured: boolean;
    transport_type: "beacon";
  },
) => void;

/** No script loader or storage. Only an already-configured, consented consumer runs. */
export function measureLeadHandoff(
  measurement: HandoffMeasurement,
  consent: boolean,
  consumer?: AnalyticsConsumer,
  enabled = process.env.NEXT_PUBLIC_WEBSITE_LEAD_ANALYTICS_ENABLED === "true",
): void {
  if (!enabled || !consent || typeof consumer !== "function") return;
  try {
    consumer("event", "lead_whatsapp_cta", {
      event_category: "Conversion",
      source: "cta_handoff",
      topic: measurement.topic,
      source_page: measurement.sourcePage,
      captured: measurement.captured,
      transport_type: "beacon",
    });
  } catch {
    // Measurement cannot interrupt the visitor's chosen contact action.
  }
}

export function navigateToHandoff(href: string): void {
  window.location.assign(href);
}

export function browserAnalyticsConsumer(): AnalyticsConsumer | undefined {
  return (window as unknown as { gtag?: AnalyticsConsumer }).gtag;
}
