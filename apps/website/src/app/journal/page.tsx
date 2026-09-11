import { permanentRedirect } from "next/navigation";

// An allowlist, deliberately: unknown keys are dropped rather than forwarded.
// It previously carried only category|q|page, which silently discarded the
// locale switch and every campaign parameter into a PERMANENTLY cached
// redirect — /journal is an inbound link target, so the loss is per client.
const preservedQueryKeys = [
  "category",
  "q",
  "page",
  "lang",
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_term",
  "utm_content",
  "gclid",
  "fbclid",
] as const;

export default async function JournalRedirect({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const source = (await searchParams) ?? {};
  const query = new URLSearchParams();
  for (const key of preservedQueryKeys) {
    const value = source[key];
    if (Array.isArray(value)) {
      for (const item of value) query.append(key, item);
    } else if (typeof value === "string") {
      query.append(key, value);
    }
  }
  permanentRedirect(`/news${query.size ? `?${query}` : ""}`);
}
