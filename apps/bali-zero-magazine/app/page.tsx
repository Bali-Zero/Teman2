import { FrontPage } from "@/components/front-page";
import { MagazineShell } from "@/components/magazine-shell";
import { readCurrentFrontPage } from "@/lib/server/magazine-read-model";

export const dynamic = "force-dynamic";

export default async function Home() {
  const page = await readCurrentFrontPage();
  return (
    <MagazineShell>
      <FrontPage page={page} />
    </MagazineShell>
  );
}
