import { redirect } from "next/navigation";

const preservedQueryKeys = ["category", "q", "page"] as const;

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
  redirect(`/news${query.size ? `?${query}` : ""}`);
}
