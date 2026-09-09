import { notFound } from "next/navigation";
import { CodePage } from "../../../features/kbli/KbliPages";
import { getCode } from "../../../features/kbli/catalog.server";
export const dynamic = "force-dynamic";
export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code: id } = await params;
  const code = /^\d{5}$/.test(id) ? getCode(id) : undefined;
  return {
    title: code
      ? "KBLI " + id + " · " + code.titleEn + " | Bali Zero"
      : "Activity not found | Bali Zero",
  };
}
export default async function Page({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code: id } = await params;
  if (!/^\d{5}$/.test(id)) notFound();
  const code = getCode(id);
  if (!code) notFound();
  return <CodePage code={code} />;
}
