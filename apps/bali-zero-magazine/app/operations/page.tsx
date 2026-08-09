import {
  MagazineShell,
  WorkspaceAccessRequired,
} from "@/components/magazine-shell";
import { OperationsBoard } from "@/components/operations-board";
import { requireChatGPTUser } from "@/app/chatgpt-auth";
import { requireMagazineViewer } from "@/lib/server/magazine-read-model";
import { createOperationsRepository } from "@/lib/server/operations-repository";
import { getMagazineBindings } from "@/lib/server/runtime-bindings";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default async function OperationsPage() {
  await requireChatGPTUser("/operations");
  const viewer = await requireMagazineViewer("internal:read");
  if (viewer === null)
    return (
      <MagazineShell eyebrow="Private workspace">
        <WorkspaceAccessRequired />
      </MagazineShell>
    );
  const bindings = getMagazineBindings();
  if (bindings.DB === undefined)
    throw new Error("Operations database is unavailable");
  const repository = createOperationsRepository(bindings.DB);
  const [health, intents, actionTargets] = await Promise.all([
    repository.healthSnapshot(),
    repository.listIntents(),
    repository.actionTargets(),
  ]);
  return (
    <MagazineShell eyebrow="Bali Zero control plane">
      <OperationsBoard
        health={health}
        intents={intents}
        action_targets={actionTargets}
        canCreate={viewer.role === "operator"}
      />
    </MagazineShell>
  );
}
import type { Metadata } from "next";
