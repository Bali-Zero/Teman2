import { notFound, redirect } from "next/navigation";
import type { SearchParams } from "../../../features/kbli/catalog.server";
export const dynamic = "force-dynamic";
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ retainedPath?: string[] }>;
  searchParams: Promise<SearchParams>;
}) {
  const segments = (await params).retainedPath ?? [];
  const path = segments.join("/");
  if (
    path &&
    !/^(?:\d{5}|builder|decoder|sectors(?:\/[A-Za-z0-9_-]{1,100})?)$/.test(path)
  )
    notFound();
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(await searchParams)) {
    if (typeof value === "string") query.set(key, value);
    else if (Array.isArray(value))
      value.forEach((item) => query.append(key, item));
  }
  redirect(`/kbli${path ? `/${path}` : ""}${query.size ? `?${query}` : ""}`);
}
