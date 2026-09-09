import { CatalogPage } from "../../../features/kbli/KbliPages";
import type { SearchParams } from "../../../features/kbli/catalog.server";
export const dynamic = "force-dynamic";
export const metadata = { title: "KBLI shortlist builder | Bali Zero" };
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  return <CatalogPage params={await searchParams} mode="builder" />;
}
