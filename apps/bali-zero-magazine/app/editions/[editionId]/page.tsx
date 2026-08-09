import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { FrontPage } from "@/components/front-page";
import { MagazineShell } from "@/components/magazine-shell";
import { readArchivedEdition } from "@/lib/server/magazine-read-model";

export const dynamic = "force-dynamic";

type EditionPageProps = Readonly<{
  params: Promise<{ editionId: string }>;
}>;

export async function generateMetadata({
  params,
}: EditionPageProps): Promise<Metadata> {
  const { editionId } = await params;
  const page = await readArchivedEdition(editionId);
  if (page === null || page.edition === null) {
    return { title: "Edition not found | Bali Zero Magazine" };
  }
  const canonical = `/editions/${encodeURIComponent(editionId)}`;
  const title = `Edition ${page.edition.date} · Revision ${page.edition.revision}`;
  return {
    title: `${title} | Bali Zero Magazine`,
    description: "An archived, verified edition of Bali Zero Magazine.",
    alternates: { canonical },
    openGraph: {
      title,
      description: "An archived, verified edition of Bali Zero Magazine.",
      url: canonical,
      type: "website",
    },
  };
}

export default async function EditionPage({ params }: EditionPageProps) {
  const { editionId } = await params;
  const page = await readArchivedEdition(editionId);
  if (page === null) notFound();

  return (
    <MagazineShell eyebrow="Publication archive">
      <FrontPage page={page} archive />
    </MagazineShell>
  );
}
