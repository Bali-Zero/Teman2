import {
  contactSourcePage,
  inferContactTopic,
  isContactSourcePage,
  isContactTopic,
  type ContactTopic,
} from "./lead-handoff";

const sources: Record<string, string> = {
  home: "/",
  about: "/about",
  team: "/team",
  immigration: "/services/immigration",
  company: "/services/company-setup",
  tax: "/services/tax",
  property: "/services/property",
  compliance: "/services/compliance",
};

export function resolveContactSource(value: unknown): string {
  if (typeof value === "string" && Object.hasOwn(sources, value))
    return sources[value];
  return isContactSourcePage(value) ? value : "/contact";
}

export function contactPageHref(topic: ContactTopic, source: string): string {
  return `/contact?topic=${topic}&from=${encodeURIComponent(contactSourcePage(source))}`;
}

/** Extract only closed topic/source values; never forward an arbitrary URL query. */
export function assistantContactContext(url: URL): {
  topic: ContactTopic;
  source: string;
} {
  if (url.pathname === "/contact") {
    const topic = url.searchParams.get("topic");
    return {
      topic: isContactTopic(topic) ? topic : "general",
      source: resolveContactSource(url.searchParams.get("from")),
    };
  }
  return {
    topic: inferContactTopic(url.pathname),
    source: contactSourcePage(url.pathname),
  };
}
