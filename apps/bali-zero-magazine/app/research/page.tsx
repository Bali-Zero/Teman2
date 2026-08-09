import {
  MagazineShell,
  WorkspaceAccessRequired,
} from "@/components/magazine-shell";
import { ResearchWorkbench } from "@/components/research-workbench";
import { requireChatGPTUser } from "@/app/chatgpt-auth";
import { authorize, parseRoleAllowlist } from "@/lib/server/authorization";
import { requireMagazineViewer } from "@/lib/server/magazine-read-model";
import { publicResearchJob } from "@/lib/server/research-http";
import {
  createResearchRepository,
  parseResearchCatalog,
} from "@/lib/server/research-repository";
import { getMagazineBindings } from "@/lib/server/runtime-bindings";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default async function ResearchPage() {
  await requireChatGPTUser("/research");
  const viewer = await requireMagazineViewer("internal:read");
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
import type { Metadata } from "next";
