import { notFound } from "next/navigation";

import { FrontPage } from "@/components/front-page";
import {
  MagazineShell,
  WorkspaceAccessRequired,
} from "@/components/magazine-shell";
import {
  readArchivedEdition,
  requireMagazineViewer,
} from "@/lib/server/magazine-read-model";

export const dynamic = "force-dynamic";

type EditionPageProps = Readonly<{
  params: Promise<{ editionId: string }>;
}>;

export default async function EditionPage({ params }: EditionPageProps) {
  const viewer = await requireMagazineViewer();
  if (viewer === null) {
    return (
      <MagazineShell eyebrow="Private workspace">
        <WorkspaceAccessRequired />
      </MagazineShell>
    );
  }

  const { editionId } = await params;
  const page = await readArchivedEdition(editionId);
  if (page === null) notFound();

  return (
    <MagazineShell eyebrow="Publication archive">
      <FrontPage page={page} archive />
    </MagazineShell>
  );
}
