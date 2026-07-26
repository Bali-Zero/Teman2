import {
  MagazineShell,
  WorkspaceAccessRequired,
} from "@/components/magazine-shell";
import { ResearchWorkbench } from "@/components/research-workbench";
import { authorize, parseRoleAllowlist } from "@/lib/server/authorization";
import { requireMagazineViewer } from "@/lib/server/magazine-read-model";
import { publicResearchJob } from "@/lib/server/research-http";
import {
  createResearchRepository,
  parseResearchCatalog,
} from "@/lib/server/research-repository";
import { getMagazineBindings } from "@/lib/server/runtime-bindings";

export const dynamic = "force-dynamic";

export default async function ResearchPage() {
  const viewer = await requireMagazineViewer();
  if (viewer === null)
    return (
      <MagazineShell eyebrow="Private workspace">
        <WorkspaceAccessRequired />
      </MagazineShell>
    );
  const bindings = getMagazineBindings();
  if (bindings.DB === undefined)
    throw new Error("Research database is unavailable");
  const catalog = parseResearchCatalog(bindings.RESEARCH_CATALOG_JSON);
  const allowlist = parseRoleAllowlist(bindings.ROLE_ALLOWLIST_JSON);
  const repository = createResearchRepository(bindings.DB);
  const [jobs, evidence] = await Promise.all([
    repository.listJobs(),
    repository.listPublishedEvidence(),
  ]);
  return (
    <MagazineShell eyebrow="Bali Zero intelligence desk">
      <ResearchWorkbench
        catalog={catalog}
        jobs={jobs.map(publicResearchJob)}
        evidence={evidence}
        canCreate={authorize(viewer, "research:create", allowlist).allowed}
      />
    </MagazineShell>
  );
}
