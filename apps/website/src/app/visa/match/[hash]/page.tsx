import { notFound } from "next/navigation";
import { VisaResult } from "../../../../features/visa-tools/results";
export const metadata = {
  title: "Your Visa Match route",
  robots: { index: false, follow: false },
};
export default async function Page({
  params,
}: {
  params: Promise<{ hash: string }>;
}) {
  const { hash } = await params;
  if (!/^[A-Za-z0-9_-]{1,200}$/.test(hash)) notFound();
  return <VisaResult kind="match" reference={hash} />;
}
