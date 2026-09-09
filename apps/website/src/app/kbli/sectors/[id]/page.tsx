import { notFound } from "next/navigation";
import { CatalogPage } from "../../../../features/kbli/KbliPages";
import {
  getSections,
  type SearchParams,
} from "../../../../features/kbli/catalog.server";
export const dynamic = "force-dynamic";
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<SearchParams>;
}) {
  const { id } = await params;
  if (!getSections().some((section) => section.id === id)) notFound();
  return <CatalogPage params={await searchParams} fixedSection={id} />;
}
