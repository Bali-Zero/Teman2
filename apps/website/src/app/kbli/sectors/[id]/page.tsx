import { notFound } from "next/navigation";
import { CatalogPage } from "../../../../features/kbli/KbliPages";
import {
  getSections,
  type SearchParams,
} from "../../../../features/kbli/catalog.server";
export const dynamic = "force-dynamic";
export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const section = getSections().find((item) => item.id === id);
  if (!section) notFound();
  return {
    title: `${section.nameEn} KBLI sector | Bali Zero`,
    description: section.description,
    alternates: { canonical: `/kbli/sectors/${section.id}` },
  };
}

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
import type { Metadata } from "next";
