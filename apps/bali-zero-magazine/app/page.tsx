import { FrontPage } from "@/components/front-page";
import {
  MagazineShell,
  WorkspaceAccessRequired,
} from "@/components/magazine-shell";
import {
  readCurrentFrontPage,
  requireMagazineViewer,
} from "@/lib/server/magazine-read-model";

export const dynamic = "force-dynamic";

export default async function Home() {
  const viewer = await requireMagazineViewer();
  if (viewer === null) {
    return (
      <MagazineShell eyebrow="Private workspace">
        <WorkspaceAccessRequired />
      </MagazineShell>
    );
  }

  const page = await readCurrentFrontPage();
  return (
    <MagazineShell>
      <FrontPage page={page} />
    </MagazineShell>
  );
}
